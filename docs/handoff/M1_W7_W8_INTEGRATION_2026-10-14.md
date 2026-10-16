# Tích hợp M1 tuần 7–8 vào VGAR — 14/10/2026

## 1. Kết quả và phạm vi

Đã clone nhánh `m1-w7-w8-handoff-20261014` từ
<https://github.com/GauKho/VGAR/tree/m1-w7-w8-handoff-20261014> và tích hợp
vào `D:/Project/CAPSTONES/VGAR`. Không tích hợp vào `vgar_mcp_mvp`, không
triển khai các kế hoạch đang đóng băng, không tự commit hoặc push.

- Clone đối chiếu: `D:/Project/CAPSTONES/.integration-m1-w7-w8-20261014`.
- HEAD trước: `73814b8f89666c71b1911e42e98b8ecc7f6e3e99`.
- HEAD sau: `b8e2461635b81d1ae790445efea5c9757d91700a`.
- Nhánh local giữ nguyên: `integration/main-m1-w5-w6-20261013`.
- Phương pháp: fetch commit từ clone local, `merge --ff-only --no-autostash`.
  Commit M1 là hậu duệ trực tiếp của HEAD local; không tạo merge commit,
  không reset, không stash/apply hoặc ghi đè code M2.
- 24 file incoming khớp byte/hash với clone M1. Hai file M2 đang sửa
  `compare.py`, `scoring.py` và các tài liệu/evidence chưa commit vẫn được giữ.

## 2. Nội dung mới của M1

| Nhóm | File | Chức năng |
|---|---|---|
| Consumer | `src/vgar/contracts/consumer.py` — mới | Nhận bundle theo task identity độc lập; validate snapshot/context/token counts; render context lại; chẩn đoán mapping của changed paths |
| Handoff | `src/vgar/contracts/handoff.py` — cập nhật | Giữ mapping/selectors cũ, bổ sung diagnostics; kiểm boolean limit flags và fallback metadata; giữ failing tests/fallback scope |
| Test selection | `src/vgar/graph/test_selection.py` — cập nhật | Ưu tiên đường ít hops, confidence mạnh hơn khi cùng hops; chọn chính test bị thay đổi; báo hop/candidate limits, không coi hints là coverage |
| CLI nhận gói | `scripts/consume_m1_handoff.py` — mới | Kiểm gói với approved task config; ghi prompt context, test inputs, diagnostics và log cho từng invocation |
| CLI demo | `scripts/demo_w7_w8_handoff.py` — mới | Build/retrieve/export/receive trên ba fixture; không gọi LLM/apply patch/chạy pytest target |
| Task identity | `configs/m1_handoff_target.example.json` — mới | Mẫu task ID, repo key, revision, graph version; phải điền từ task được duyệt, không tự tin vào manifest nhận |
| Đóng gói/chạy test | `scripts/package_m1.py`, `scripts/run_m1_tests.py` — cập nhật | Bao gồm consumer, demos và tests mới |
| Tài liệu | `README.md`, `docs/context_payload_contract.md` — cập nhật | API/CLI, mapping status, fallback policy và giới hạn bàn giao |
| Regression | `tests/test_m1_handoff.py` — cập nhật; `tests/test_test_selection.py`, `tests/test_w7_w8_handoff_demo.py` — mới | Kiểm portable snapshot, identity/source/tokenizer guards, routes/limits, fallback, CLI success/error và fixture baseline |
| Fixtures | `tests/fixtures/w7_w8_handoff/` — mới, 11 file | `cases.json`; ba repo mẫu single-file login, multi-file invoice và missing links |

Danh sách đầy đủ 24 paths và hash trước tích hợp nằm trong
[`before.json`](../audit/2026-10-14-m1-w7-w8/before.json).

### Luồng bàn giao

```text
Snapshot nguồn gốc + issue/failing selectors
    → M1 graph/anchors/retrieval
    → context.json + context_manifest.json + test_links.json
    → M2/consumer kiểm identity độc lập, source hashes, ranges, token counts
    → render repair context + test inputs/diagnostics
    → M2 tiếp tục prompt/model/diff/worktree/collection/verification
```

`receive_context_handoff` không dùng trực tiếp `repair-context.txt` của producer.
Changed paths phải lấy từ diff thực tế, đối chiếu trên **snapshot gốc trước patch**.
Snapshot đã sửa không thể dùng để kiểm manifest của source gốc.
`linked`/`PASS` của consumer không đồng nghĩa tests đã collect, coverage đã đủ
hoặc repair thành công. `collection_verified` và `coverage_verified` vẫn false.

## 3. Kiểm thử đã chạy và evidence

Mọi command receipt trong `docs/audit/2026-10-14-m1-w7-w8/commands/` có argv,
cwd, interpreter, source fingerprint, stdout/stderr, exit code, UTC start/end
và duration. XML giữ testcase results. Không cài thêm dependencies hoặc tải weights.

| Kiểm tra | Kết quả | Evidence trong audit directory |
|---|---|---|
| Baseline trước tích hợp: HF + handoff + M1 W7–8 + M2 consumer | 88 passed, 1 failed, 1 skipped; pytest 57.05s, process 59.46s; exit 1 | `commands/20261014T072050428739Z-baebc1942545/result.json`, `baseline.xml` |
| Suite M1 sau tích hợp | 434 passed, 1 skipped; pytest 49.66s, process 50.84s; exit 0 | `commands/20261014T072232904265Z-5c5543084e2c/result.json`, `m1.xml` |
| Demo với tokenizer Qwen local thật | 3/3 PASS; process 1.97s; exit 0 | `commands/20261014T072244701540Z-74bc9a927da2/result.json` |
| Danh sách đóng gói | PASS/exit 0; file bắt buộc của M1 hiện diện; không tạo ZIP | `commands/20261014T072300019889Z-acf9eacde07e/result.json` |
| Suite chung VGAR sau tích hợp | 564 passed, 1 failed, 2 skipped; pytest 76.13s, process 79.85s; exit 1 | `commands/20261014T072340596612Z-b5ab3240b9e8/result.json`, `integrated-full.xml` |
| Bảo toàn code/dữ liệu trước đó | PASS: 24 incoming matches; 0 unrelated tracked changes; 0 lost/changed protected untracked files | `preservation.json` |
| Git whitespace/conflict check | `git diff --check` exit 0 | Kiểm tại cuối phiên; không có sửa source mới ngoài incoming commit |

Interpreter test M1/full/baseline:
`D:/Project/CAPSTONES/vgar_mcp_mvp/.venv/Scripts/python.exe` — chỉ tái sử dụng
interpreter và dependencies; child `PYTHONPATH` trỏ vào **VGAR/src**.
Không chạy source hay sửa môi trường của repo cũ.

Interpreter demo/package:
`D:/Project/CAPSTONES/VGAR/.venv-m2-w5-w6/Scripts/python.exe`;
tokenizers 0.22.1, tokenizer Qwen3-4B-Instruct-2507 tại revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. Chỉ đọc assets đã có, không inference.

Hai skipped cases của suite chung: hệ thống không cho tạo symlink trong một
workspace test; optional Matplotlib chưa cài cho plot test. Không đổi skip thành PASS.
Suite M1 là tập con suite chung, không cộng hai counts thành số tests độc lập.

### Ba demo

Output tại:
`artifacts/m1/w7-w8/handoff-demos/20261014T072245Z-a8015356523c45cfa264244c07d252b0/`.

| Case | Context | Mapping | Kết luận đúng phạm vi |
|---|---|---|---|
| `single_file_login` | 3 items, 40 snippet tokens | `auth.py`: linked | Gói/source/test hints hợp lệ, source unchanged |
| `multi_file_invoice` | 5 items, 119 snippet tokens | `invoice.py`, `pricing.py`: linked | Hai file có context/hints, source unchanged |
| `missing_links` | 2 items, 100 snippet tokens | `formatter.py`: unlinked; fallback required | Giữ failing selector và scope `tests`, không giả graph coverage |

Mỗi case giữ `graph.json`, `graph.db`, source copies, `bundle/`, approved target,
rendered context, `test-inputs.json`, `test-targets.json`, `events.jsonl`, `result.json`.
Các fixture cố ý vẫn lỗi. PASS ở đây **không** phải LLM đã sửa được ba repo đó.
Unit tests kiểm riêng các baseline fail được khai báo bằng pytest trên bản copy.

## 4. Lỗi/giới hạn còn tồn tại

1. Full suite chưa xanh: `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`
   vẫn `KeyError: generation_config` tại dòng 53. Baseline **trước** tích hợp
   đã tái hiện chính lỗi này. Commit M1 không sửa model/test HF; không tự sửa
   lỗi ngoài phạm vi tích hợp. Không kết luận hệ thống repair thật đã chạy được.
2. Không chạy LLM, benchmark dev25, official SWE-bench harness hoặc SCIP/LSP
   runtime thật trong phiên này. M1 suite có các controlled enrichment tests;
   chúng không thay thế qualification trên target repositories.
3. Không nghiệm thu ranking improvement hay toàn bộ M1/M2 tuần 7–8 từ số unit tests.
   M2 prompt, model, parser/apply/verification và M3 orchestration còn theo
   task plan; clone một handoff không tự hoàn thiện các phần này.
4. Không ký thay M1-owner review cho M2 W5–6. Ba SymPy timeouts và report ngày
   13/10 giữ nguyên; các kết quả đó thuộc source fingerprint cũ, không trở thành
   benchmark của HEAD mới. Không chạy lại historical acceptance script với
   source mới rồi coi hash mismatch là benchmark mới fail.
5. `Task Status.md` vẫn là audit tại HEAD 73814b8f ngày 13/10; xem checkpoint
   này để biết delta mới. Không tự đổi tất cả task states hoặc ownership gates.

Full-suite mở SQLite fixture làm thay byte của `artifacts/sample_graph.db`.
Đã giữ bản sau test tại `docs/audit/2026-10-14-m1-w7-w8/sample_graph-after-tests.db`,
giữ bản trước tại `originals/artifacts/sample_graph.db`, rồi phục hồi **chỉ**
fixture do lượt test này thay đổi. Preservation trước/sau nằm ở hai JSON riêng;
không rollback source, không xóa evidence hoặc dữ liệu của người dùng.

## 5. Điểm dừng

Tích hợp M1 đã hoàn tất ở local; không còn test process của phiên này.
Không có commit do assistant tạo, không push, không đổi remote/nhánh local.
Các uncommitted M2 changes còn nguyên. Có thể tiếp tục nối consumer vào M2
tuần 7–8 bằng plan được duyệt; lỗi HF cần task sửa riêng nếu người dùng yêu cầu.

Không cần clone/merge lại hoặc chạy lại dev25 chỉ để xác nhận handoff này.
Để kiểm riêng M1 sau này: chạy `python scripts/run_m1_tests.py` trong môi trường
có các dependencies tương ứng. Cách nhận gói/demo đầy đủ nằm trong
[`context_payload_contract.md`](../context_payload_contract.md).
