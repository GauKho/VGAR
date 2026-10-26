# M2-W9-0 — Ghi nhận và xử lý review M3

**Kết luận:** hoàn thành deliverable interface sau xử lý phản hồi M3; không thay engine/API/DTO và không triển khai W9-3/W9-4.

## 1. Nguồn và mức phê duyệt

- Nguồn do người dùng cung cấp: `D:\Project\CAPSTONES\docs\review_M2-W9-0.md`.
- SHA-256 bytes nguồn: `9a50433e988121d11126e3098ac2f98b0f0cacd4e4f95ef9a3384abd19d78987`.
- [Bản phản hồi nguyên văn trong repo](review_M2-W9-0_M3_original.md), giữ cả dòng lặp/lỗi trình bày; bản sao UTF-8 được chuẩn hóa kết thúc dòng khi tạo bằng patch. Không giả định hash bytes bản sao bằng hash bytes nguồn; kiểm nội dung và ghi hai hash riêng trong evidence.
- Reviewer: **M3**, theo nguồn review và xác nhận của người dùng. Không tự bổ sung tên cá nhân, chữ ký, ngày hoặc commit mà M3 không cung cấp.
- Ngày M2 ghi nhận/xử lý: **22/10/2026**. File nguồn không nêu ngày review hoặc hash chính tài liệu interface được M3 đọc; không tuyên bố đáp ứng lịch “ngày 1” từ ngày này.
- Phân biệt với review agent: phản hồi M3 là căn cứ human approval; review độc lập của agent chỉ kiểm chất lượng xử lý phản hồi.

M3 APPROVE entrypoint, hướng lifecycle/output/resume và nguyên tắc A0/A1 optional static. M3 yêu cầu chỉnh tài liệu ở (a)/(b), ví dụ fake, và APPROVE **có điều kiện** đối với experiment. M2 áp dụng lựa chọn sửa tài liệu được M3 cho phép; không thay đổi hành vi Ctrl+C.

## 2. Bảng xử lý

| ID / phần | M3 yêu cầu | M2 xử lý | Vị trí | Trạng thái / phần tiếp theo |
|---|---|---|---|---|
| §2 entrypoint | Gọi run_repair, executor=None, nhận RunHandle, tối đa một generation mỗi call | Giữ API hiện tại, ghi nhận M3 chấp thuận | Interface §2; decision D2 | Đã ghi nhận; không đổi code |
| (a) Ctrl+C | Nêu engine có thể bắt KeyboardInterrupt hoặc sửa để ném lại | Chọn tài liệu-only: observe ghi rồi re-raise; _step có thể chuyển thành outcome ERROR; reason tùy stage; complete không phải PASS | Interface §3.2 | Đã xử lý tài liệu; không claim runtime interruption tests mới |
| (b) timeout | Phân biệt record reason với bundle DTO; chỉ rõ nơi đọc timed_out | Liệt kê command/stage/nested exception và vị trí TEST_TIMEOUT trong DTO; không chỉ kiểm reason ngoài cùng hoặc giả missing=false | Interface §4.1 và §4.1.1 | Đã xử lý; không đổi taxonomy lỗi |
| (c) resume | M3 dùng runner.lock thay theo dõi PID | Ghi nhận phương án, mục tiêu không duplicate và điều kiện coverage/recovery; không bắt đổi sang PID | Interface §4.2 | Đã ghi nhận; implementation runner/lock chưa được M2 kiểm chứng |
| (d) tên trường | Chốt names/path để ledger khớp experiment | Giữ record.experiment.* là ví dụ của M3, chưa tự chốt schema hoặc emit fields | Interface §5.1; decision D8 | Follow-up W9-4: M2/M3 thống nhất trước integration; public contract đổi cần nhóm review |
| (d) save/load | Profile phải giữ nguyên khi RepairSession.load | Ghi yêu cầu persist/reload variant/policy/provenance cho direct/MCP | Interface §5.1 | Follow-up W9-4; chưa implement/verify trong W9-0 |
| (d) MCP regression | Sau mỗi lần sửa session/pipeline, test repair server PASS | Ghi tests/m2/w78/test_w78_repair_server.py là gate khi thay code tương ứng | Interface §5.1 | Lần này không đổi code, không chạy hoặc ghi PASS mới |
| Fake example | Không truyền real profile vào run_repair khi fake | build_generation vẫn dùng profile cho tokenizer/counter; run_repair nhận profile=None như CLI | Interface §2.3 | Đã chỉnh ví dụ, kiểm syntax; không claim đã chạy fixture |
| Optional static | ACCEPT theo policy, không theo raw static FAIL | Phân biệt verifier opt-in đã có với root integration còn thiếu; không sửa raw result | Interface §5 | Nguyên tắc được M3 đồng ý; không suy ra mapping retrieval đã duyệt |

## 3. Những phần chưa được duyệt hoặc chưa triển khai thay

- D1 mapping arm, D3 environment, D4 oracle visibility, D5 context packing, D6 scope và D7 real runtime/budget vẫn giữ trạng thái riêng trong [decision log](../m2_w9_decisions.md).
- D2 chấp thuận entrypoint hiện tại; D8 chỉ ghi nhận **M3** đồng ý có điều kiện về hướng interface. Không suy ra M1 hoặc cả nhóm đã phê duyệt public DTO/schema.
- M3 báo đã implement runner/SIGINT/lock/aggregate; chưa có code runner tương ứng trong checkout được M2 đối chiếu. Không nâng các lời thông báo đó thành evidence local runtime PASS.
- Baseline environment/full W78 vẫn NOT_RUN theo evidence cũ. Không cài dependency/tokenizer hoặc chạy model/harness trong lần này; không dùng trạng thái baseline để chặn đóng riêng interface W9-0.
- W9-1/W9-2 giữ nguyên kết quả đã nghiệm thu, không chạy lại hoặc sửa implementation của chúng.

## 4. Evidence và điểm dừng

Evidence mới: `results/m2/w9/m2-w9-0/20261022-close-interface/` (ignored): snapshots/hash source review và tài liệu/source trước/sau; kiểm cú pháp ví dụ, code references, Markdown/links, diff whitespace; receipt review độc lập. Không ghi đè evidence 21/10 hoặc results W9-1/W9-2.

Trong bước thu bản nguồn, command PowerShell ConvertTo-Json mang cả metadata của Get-Content thay vì chỉ string, và lần đầu output bị cắt; đã lấy trường value với output đủ và kiểm nội dung bản sao. Đây là lỗi thu tài liệu của agent, không phải lỗi VGAR hoặc test failure. Không lặp lại cách parse whole-object như string.

Chỉ tài liệu/checkpoint được sửa; không commit/push hoặc sửa Task Status.md. **Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**
