# M1-W9-3 — Báo cáo nghiệm thu kỹ thuật ngày 23/10/2026

## 1. Kết luận và phạm vi

**Đạt tiêu chí kỹ thuật 10/10 bundle:** graph và BM25 cho cùng năm task dev đã
được consumer M2 `context_adapter.load_handoff()` chấp nhận, rồi đọc lại độc lập
từ artifacts đã lưu. Đây là nghiệm thu **retrieval handoff**, không phải kết quả
repair, pytest collection, baseline qualification hoặc SWE-bench resolved rate.

Chưa commit/push/merge; chưa có phê duyệt M3 cho task này. Ngoại lệ review do
người dùng cho M1-W9-1 không áp dụng ở đây. Dừng tại W9-3, không làm W9-4.

## 2. Bản chạy cuối và index bàn giao M2

- Run: `artifacts/m1/w9/bundles/20261023T071017Z-4ab71bbef7a0/`.
- Index đầy đủ: `run_record.json` dưới run trên; chứa task/arm, đường dẫn bundle,
  graph/source identities, sidecar hashes và command/exit/time từng task.
- Hai bundle mỗi task nằm tại `<run>/<instance_id>/graph/` và
  `<run>/<instance_id>/bm25/`. Mỗi nơi có `context.json`,
  `context_manifest.json`, `test_links.json`, `repair-context.txt`.
- Export toàn phiên: **PASS**, exit0, 10 validated và 10 accepted bundles;
  **514,787 giây** từ 07:10:17 đến 07:18:52 UTC ngày 23/10/2026.
  Không task nào timeout; mỗi task dưới giới hạn600giây.
- Audit riêng: `results/m1/w9/m1-w9-3/20261023-export/pilot_audit.json` và
  `pilot_audit_command.json`, exit0. Chỉ đọc lại consumer, không chạy lại retrieval.

| Task | Graph: items / tokens | BM25: items / tokens | Fallback files chung | Tổng export task (giây) | Kết quả hai arm |
|---|---|---|---|---|---|
| astropy__astropy-13398 | 15 / 7994 | 9 / 7999 | 415 | 155,243 | PASS / PASS |
| django__django-11138 | 22 / 7995 | 9 / 7999 | 1717 | 199,850 | PASS / PASS |
| matplotlib__matplotlib-14623 | 29 / 7993 | 5 / 8000 | 92 | 91,506 | PASS / PASS |
| pydata__xarray-3305 | 47 / 7970 | 8 / 7999 | 43 | 37,386 | PASS / PASS |
| pylint-dev__pylint-4551 | 55 / 7617 | 4 / 8000 | 700 | 30,791 | PASS / PASS |

Fallback files là danh sách đường dẫn từ source baseline, **không phải số tests
đã collect hoặc đã PASS**. Thời gian task gồm shared graph build, packing,
producer/consumer checks và worker overhead. Không lấy riêng BM25 arm latency
để tuyên bố đó là tổng chi phí BM25 độc lập.

## 3. Inputs, profile và provenance

| Thành phần | Giá trị được khóa |
|---|---|
| Dataset | princeton-nlp/SWE-bench_Verified@c104f840cc67f8b6eec6f759ebc8b2693d585d4a |
| Cached Parquet SHA-256 | a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd |
| Manifest | configs/m1/w9_pilot_manifest.json; sha256:98984466d59da122d4798d436359275030f79e1190936d7d9a6f9a0a58458425 |
| Profile | configs/m1/w9_bundle_profile.json; sha256:7fbbe444267b94c021d31951a17d205b92c9d7216ae10941e8aa0af2fbb3421a |
| Tokenizer | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554 |
| Tokenizer manifest bytes | sha256:691f593426cdbdba3c4674d4735862bc9e1f81bf04efdba7d4ba3f5abc674d61 |
| Accounting | Exact snippet encode, add_special_tokens=false, tổng từng item; 8000 tokens/arm |
| Graph | Static resolver, retriever hiện hữu; không tune ranking hoặc chuyển resolver |
| BM25 | k1=1.2, b=0.75; path + symbol + exact node-range snippet; không edges/gold |
| Test hints | Issue-only; links/failing selectors rỗng; cùng fallback files; coverage_verified=false, collection_verified=false |

Split dev được tính lại từ ID theo policy của dự án và chọn repo-round-robin;
đây không phải split `dev` do Hugging Face cung cấp. Developer patch chỉ dùng
để chọn multi-file stratum, không truyền vào retrieval projection/ranking.
Full base commits và query hashes nằm trong manifest, không dùng manifest25 cũ
mang split `test`. Source là full Git checkout đúng base SHA, HEAD và clean state
đã kiểm trước/sau mỗi worker. Tokenizer chỉ dùng bốn assets; không tải weights.

Runtime thực: Python3.11.6, Tree-sitter0.25.2/python0.25.0, tokenizers0.22.2,
Pydantic2.14.0, pyarrow23.0.1, pytest8.4.2 trong environment có sẵn
`environments/vgar-week78-cuda`. Lint dùng Ruff0.16.5 thực có, không tuyên bố
qualification đúng pin Ruff0.17. Không cài dependencies hoặc đổi environment chung.

## 4. Kiểm thử, findings và lỗi được giữ lại

Evidence root: `results/m1/w9/m1-w9-3/20261023-export/`.

| Kiểm tra/finding | Kết quả và xử lý | Evidence |
|---|---|---|
| Modules chưa có | RED missing-module failures trước implementation | red.json |
| Tokenizer khác model/revision bị nhận nhầm | Thêm identity guard so approved manifest; RED→GREEN | review_red.json, review_green.json |
| Chỉ đếm arm PASS có thể nhận run worker exit lỗi | Run cần cả5task finalized PASS và10accepted bundles | review_red.json, review_green.json |
| JSON worker hỏng / timeout / mixed arm | Vẫn đủ5×2 records, giữ ERROR; không mất task | controller_red.json, controller_green.json và controller tests |
| Empty/whitespace File/Module | Tái hiện lỗi consumer; thêm chung usable-source filter, không nới validator | empty_source_red.json, shared_empty_red.json, empty_source_green.json |
| Selected regression cuối | **391 PASS, 1 SKIP, 2 deselected**, exit0; 69,13giây pytest | post_filter_regression.json và .junit.xml |
| Ruff touched files | PASS | post_filter_lint_green.json |
| Real pilot cuối | **10/10 PASS**,5task finalized/source unchanged | run_record.json, worker_result.json và validation JSON từng arm |
| Independent saved-bundle audit | **10/10 PASS**, real tokenizer/consumer, source/bundle identities, common hints | pilot_audit.json, pilot_audit_command.json |
| Kiểm đóng task | Runtime319files không đổi trong campaign; M2/Task Status giữ nguyên; Markdown links/tables và git diff --check PASS | before.json, before_real2.json, after.json, close_verification.json |

Review độc lập là technical code QA, không phải M3 approval. Các findings
tokenizer identity và worker-finalization đã có regression RED→GREEN trước real
export. Runtime của mỗi campaign được giữ cố định khi workers đang chạy.

Campaign đầu `20261023T065655Z-37324a98e210` giữ nguyên: graph5PASS/BM25 5ERROR,
run INCOMPLETE, accepted0, tổng607,160giây. Empty source được rank nhờ path/symbol
nhưng không có nội dung hữu dụng; consumer từ chối đúng. Không phải tokenizer,
timeout hoặc lỗi model. Sau khi campaign đầu terminal, sửa shared eligibility
và chạy lại **cả hai arm trên đủ năm task**. Không ghép kết quả hai runtime.
Lượt đầu lỗi trước khi trả bundle nên không có BM25 ranked diagnostics đầy đủ;
raw traceback và các records lỗi vẫn được bảo toàn, không tự điền lại lịch sử.

SKIP: filesystem symlink thật cần quyền Windows. Hai exclusions W7–8:
`test_baseline_to_repair_and_static_evidence` và
`test_verify_patch_equals_tests_then_completion`; tokenizer qualification riêng
chưa chạy. **Full repository suite NOT_RUN**; không suy từ391 selected tests.

## 5. Cách dùng và giới hạn bàn giao

Xem [hướng dẫn M1-W9-3](m1_w9_3_dual_arm_bundles.md) cho commands và flow.
M2 nhận từng thư mục `graph/` hoặc `bm25/` cùng task/source identity từ index;
gọi consumer hiện hữu, không sửa sidecars để vượt validation. Ranked candidates,
packing omissions và scores nằm ngoài bundle ở `graph-retrieval.json` và
`bm25-retrieval.json`; BM25 confidence không phải xác suất relevance.

**8000 snippet tokens không đảm bảo full repair prompt vừa cap6000**. Không thay
repair cap, không chạy model/harness, không gọi kết quả export là baseline đã
qualify. Admission, execution environment và runner/session integration vẫn là
task khác. Không dùng pilot này để kết luận graph tốt hơn BM25 về retrieval quality.

Inputs/cache/checkouts/tokenizer/bundles và test evidence lớn là ignored local
artifacts; scripts/configs/manifest/report mới là phần Git có thể bàn giao. Đồng đội
cần provision đúng cached dataset/tokenizer và full sources rồi chạy exporter,
hoặc nhận riêng artifacts; clone code không tự mang theo dữ liệu ignored.
