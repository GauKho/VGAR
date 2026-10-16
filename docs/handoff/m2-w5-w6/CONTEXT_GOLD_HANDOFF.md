# Bàn giao M2 tuần 5–6 — Context và gold mapping

**Owner review:** `PENDING_M1_OWNER_REVIEW`. M2 đã kiểm code/fixtures nhưng không ký thay M1.
**Source baseline:** `73814b8f89666c71b1911e42e98b8ecc7f6e3e99` + tracked M2 diff; source fingerprints trong receipts/runs.
**Scope:** consumer/evaluation, không đổi graph builder, resolver, weights, schema hoặc MCP tools.

## Input/output giữa hai bên

| M1 input cho M2 | M2 sử dụng | Quy tắc |
|---|---|---|
| Repository snapshot + graph document | `CorpusIndex(sources)` và node lookup | Same repo/base_commit/corpus, normalized POSIX paths |
| `RetrievalResult.candidates` | `graph_rank(...)` | Giữ order M1; không sort bằng gold |
| Native `ContextPayload` | Source/range/token validation và native metrics | UTF-8 byte columns,1-based lines,exclusive end; snippets-only token count |
| Function/Method path+qualified_name+range | Canonical parent_id | Name AND source span must bind to definition; không lấy tên gần giống |
| Class/File/Module candidates | File-level metric | Không biến class chứa function thành exact function hit |
| Missing/unsupported/non-corpus node | Unmapped/excluded diagnostics | Không thêm label để làm đẹp recall |

Gold patch chỉ vào `extract_gold` sau M1 retrieve và M2 rank freeze. Gold là changed-code proxy, không phải toàn bộ relevant context/root cause.
Fair-packed metrics dùng shared scorer80lines/header/overlap, khác native packing; giữ counter/provenance/config rõ.

## Những lỗi consumer đã sửa bằng RED → GREEN

| Bug | RED evidence | Sửa | Test |
|---|---|---|---|
| Compare hai developerpatches khác nhau vẫn accepted | `artifacts/m2/test-runs/20261013T112504100380Z-49c006ef1b4b464fae4baa5ced28c19b.json` | Same patch_hash bắt buộc per paired task | test_compare_rejects_patch_hash_mismatch |
| Một definition khớp tên nhưng range ngoài source vẫn function hit | `artifacts/m2/test-runs/20261013T113403752051Z-4960ccc60659477e91d87cd290ea4c38.json` | Function mapping yêu cầu span containment kể cả single definition | test_single_definition_outside_range_is_not_a_function_hit |
| End-exclusive column0 thêm header function kế tiếp | `artifacts/m2/test-runs/20261013T113744502165Z-199bc82d7a374225beacc79947aa0238.json` | Endline-1 khi end_col0/endline>startline; legacy fixtures không cols giữ inclusive line convention | test_end_exclusive_next_line_does_not_add_unrelated_code |
| Range thiếu/rỗng/zero-length, sai kiểu, vượt source hoặc cắt giữa UTF-8 vẫn được đoán hit | `artifacts/m2/test-runs/20261013T115802447312Z-67c7be8e7cc44e5ea4232413c35573f0.json` (12 failed/12 passed) | Kiểm line/byte bounds/end-exclusive trước projection; loại item thiếu source binding với INVALID_SOURCE_RANGE | test_malformed_source_range_is_diagnostic_not_a_function_hit và UTF-8 tests |

Source sửa: `src/vgar/evaluation/retrieval/compare.py`, `scoring.py`; test mới `tests/m2/test_context_gold_handoff.py`.
Targeted retrieval GREEN48passed/0failed/0skip: `artifacts/m2/test-runs/20261013T113831791725Z-464d49316d304853b5755e7a671e3e91.json`.
Existing native handoff contract regression61passed/0failed/0skip: `artifacts/m2/test-runs/20261013T114201127598Z-4d3e30668a5642b7b953e9e9d5d184dd.json`.

**Regression sau sửa cuối:** 121 passed, 0 failed/skip tại `artifacts/m2/test-runs/20261013T115854955079Z-65e7f223162744848886560ea140285a.json`. Bao gồm 60 retrieval/consumer và 61 native handoff tests. Expected RED không tính vào failure budget hạ tầng.

**Diagnostic mới chỉ phía M2:** range sai không có source snippet đáng tin nên không được ghi file/function hit; giữ item ID/path/reason ở `unmapped` scope=item. Range hợp lệ nhưng qualified name không map vẫn giữ file-level item, function_id=null. Native columns phải đủ hai trường; legacy hai line rõ ràng vẫn được hỗ trợ. Không đổi public ContextPayload/schema.

## Proof dùng producer M1 thật

- Fixture source: `artifacts/m2/w5-w6/handoff_fixture/src/auth.py`, `src/service.py`.
- Script probe: `artifacts/m2/w5-w6/check_native_handoff.py`.
- Producer: existing PythonGraphBuilder static, TaskOverlayBuilder, GraphContextRetriever.
- Counter: actual LocalTokenizerCounter tokenizers0.22.1, pinned tokenizer hash/revision.
- Inputs/graph/context/labels/scoring: `artifacts/m2/w5-w6/native_handoff/`.
- Canonical proof: `native_handoff/result.json`, stdout receipt `commands/20261013T114156939970Z-c414c54f0e89/result.json`.
- Result:2contextitems,47snippet tokens,0unmapped; actual byte slices/accounting match; original fixture unchanged; rank hash unchanged after labels.
- Đây là consumer integration trên fixture, không phải benchmark repair, runtime coverage hoặc M1-owner approval.

Proof sau sửa review: `artifacts/m2/w5-w6/native_handoff_final/result.json`, command `20261013T120019234067Z-84d397fed368`. Vẫn 2 items/47 snippet tokens/0 unmapped; đây là proof hiện hành. Proof trước sửa giữ nguyên để đối chiếu, không ghi đè.

## Checklist dành cho M1 review

- [ ] Xác nhận path/qualified_name/range conventions đúng producer hiện tại.
- [ ] Xác nhận consumer giữ candidate order, không dùng gold để chọn context.
- [ ] Xác nhận Class/File chỉ có file-level hits; unmapped không được đoán thành function.
- [ ] Review end_col0/exclusive normalization và legacy test behavior.
- [ ] Đọc final paired report/source/config/metrics/denominators sau khi chạy xong.
- [ ] Ghi tên người review, ngày, scope source/receipt hashes, nhận xét và accept/request-change.

Chưa có review từ chủ task M1 thì W05-06-M2-04 vẫn MP, dù technical tests/proof đã đạt.

## Bổ sung bàn giao sau final evaluation

- Comparison hiện hành: `results/retrieval/20261013T125307312086Z-6d6b0b52b105/REPORT.md`,22paired tasks/25attempted. BaSymPytimeout300s/attempt1 giữ nguyên, không dùng để tínhpairedmeans như score0.
- Current acceptance: `artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json`,source digestf00423af.../samepopulation/counter/input hashes verified.
- Final targeted pytest: command20261013T125931577415Z-c5e38fe74935,121PASS/5,47s. Legacy full-workspace recorder cuối bị ngắt vìhashcache lớn; xem COMPLETION_REPORT6.3, không suy outcome củainvocation bịngắt.
- Graph issue-only có4unmapped trong22validtasks, cần M1 review diagnostics, không tự gán function ID để nângrecall. FileRecall@5 thấp hơnBM25,FunctionRecall@5 cao hơn nhẹ; cả hai pairedCI chứa0. Đây là kết quả exploratory, không sửa ranking để épGraphthắng.
- Người phụ trách M1 cần ghi reviewer/date/accept hoặc requestchanges cùng scope củareceipt này; checklist trên vẫn chưa được tựtick.
