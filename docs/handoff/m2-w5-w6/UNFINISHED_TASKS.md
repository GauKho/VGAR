# M2 W5–6 — Lỗi, blocker và phương pháp không lặp lại

| Task/phase | Method/profile | Attempts | Symptom/root cause | Evidence | Không lặp / Next action |
|---|---|---:|---|---|---|
| R0 tokenizer preflight | Current manifest + root Python3.13 |1|FileNotFoundError tại assets_directory; manifest có,4asset chưa có ở folder đã pin|Preliminary diagnostic in execution transcript; recorded checks follow after provisioning|Không chạy lại unchanged; provision exact tokenizer-only bundle, không weights |
| W05-06-M2-04 | Owner review |0|Chưa có xác nhận M1; agent không ký thay|CONTEXT_GOLD_HANDOFF.md, native_handoff_final/result.json,121-tests GREEN|Giữ MP đến khi M1 xác nhận; không chạy lại benchmark chỉ để thay owner review |
| W05-06-M2-03 | Final profile — task đã đóng |1 invocation mỗi arm|BM25 25success/Graph22success3timeout;22validpairs đạtgate≥20, evaluationtask HT nhưng3Graphcases chưa chạy được|Comparison20261013T125307312086Z-6d6b0b52b105; final-verification20261013T125343095888Z-13d9f9501ba3|Không chạy lại final25; xem3case limitations bên dưới; nếu cần đủ25pairs phải có profile/profiling riêng và quyết định mới |
| R0 environment | Root venv Python3.13/tokenizers0.23.1 |1|M1 counter requires major/minor0.22; assets đã tải đúng hashes nhưng interpreter không tương thích|artifacts/m2/w5-w6/commands/20261013T112502337428Z-29b8bc4d2d02/result.json|Không downgrade root venv; tạo .venv-m2-w5-w6 với pins retrieval tối thiểu |
| R0 network permission | Provision in sandbox |1|WinError10013 socket permission, không phải asset/revision lỗi|artifacts/m2/w5-w6/commands/20261013T111520142264Z-9446b2c27045/result.json|Escalated provisioning đã PASS tại20261013T112219371791Z-854191753cec; không lặp download |
| Graph task sympy__sympy-16597 | Final static/300s |1|TimeoutError: Task exceeded300s; biết deadline bị vượt, chưa có profiling đủ để kết luận do RAM/phase cụ thể|results/retrieval/20261013T121221258372Z-9ae258fd202e/result.json → task_results|Không retry task/counter/budget; báo M1 cần profiling riêng nếu muốn đủ25pairs; vẫn giữ task trong attempted25 và skipped pairing |
| Graph task sympy__sympy-17318 | Final static/300s |1|TimeoutError: Task exceeded300s; task khác, không phải retry16597; phase/RAM bottleneck chưa đủ evidence|Cùng final Graph run → task_results|Không retry17318 hoặc full-profile; giữ failure. M1 cần profiling nếu muốn chạy được đủ SymPy; không đổi timeout/dataset trong đợt M2 |
| Graph task sympy__sympy-20438 | Final static/300s |1|TimeoutError: Task exceeded300s; ID thứ ba của population, không retry hai ID trước; chưa xác định bottleneck sâu|Cùng final Graph run → task_results|Không retry hoặc nới deadline; giữ attempted/skipped. Không dùng GPU/API model để chữa một retrieval-only timeout khi chưa có profiling |
| R4 recorder | record_m2_test.py sau khi caches lớn |1 interrupted|Whole-workspace fingerprint đọc cảdata/results/isolated env; >5min chưa có terminal evidence, không coi là pytest fail/pass|commands/20261013T125931493926Z-ed28d248bb9f/result.json +clarification.json|Không lặp cùng method trên cache lớn; bounded direct pytest qua existing record_command đã121PASS; không sửa W3–4 runner |

## Expected RED, không phải hạ tầng

- `test_compare_rejects_patch_hash_mismatch`:1failed/1passed, đúng `DID NOT RAISE ValueError`. Evidence `artifacts/m2/test-runs/20261013T112504100380Z-49c006ef1b4b464fae4baa5ced28c19b.json`.
- Sửa hẹp: thêm `patch_hash` vào per-task fairness guard; GREEN đã đạt, xem handoff và final121-tests evidence.

## Đã xử lý kỹ thuật (không xóa lịch sử failure)

- Root venv tokenizers0.23.1 không sửa/downgrade; isolated `.venv-m2-w5-w6` với0.22.1 đã qualify PASS. Dependency install relative exe failWinError2 được xử lý bằng absolute exe; không lỗi package source.
- Ba consumer bugs có RED→GREEN,48retrieval tests PASS và61native contract tests PASS. Xem CONTEXT_GOLD_HANDOFF.md.
- Dev25 prepared tại pinnedSHA; parquet verified/reused,10archives reused,15archives fetched/verified. Historical metrics/split=test không dùng như current evidence.
- Optional process resource probe qua Win32_Process bị Access denied trong sandbox; không cần để quyết định retrieval gate, không chạy lặp hoặc mở quyền không cần thiết. Worker receipts vẫn có measured peakRSS nếu API của worker đọc được.
- Một Important từ review: malformed source ranges vẫn có function hits. Đã xử lý trong một fix pass, RED12fail/12pass → GREEN121pass. Native valid UTF-8 và CRLF vẫn pass; không sửa producer/schema.
- Final25 comparison/denominators đã nghiệm thu22pairs; M2-03 HT. M2-04 chỉ còn M1-owner review; ba Graph/SymPy cases vẫn timeout, có thể cần M1 profiling ở scope riêng. Không coi failures hạ tầng đã xử lý là benchmark performance failures.

Expected RED được ghi riêng, không tính là infrastructure failure. Permission/network retry sau escalation không phải thử lại thuật toán/profile để đổi kết quả.
