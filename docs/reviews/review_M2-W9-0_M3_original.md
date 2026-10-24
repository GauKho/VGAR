1. repair_runner_interface.md: chỉ M3 duyệt

┌─────────────────────────┬─────────────────────────────────────────────────────┬────────────────────────────────┐
│           Mục           │                      Nội dung                       │            Đề xuất             │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §2 Entrypoint           │ run_repair(...), executor=None, trả về RunHandle,   │ APPROVE. Runner đã gọi đúng    │
│                         │ mỗi lượt gọi một generation                         │ như vậy                        │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §3 Vòng đời và deadline │ Các bước của session; RepairSession.load có ghi     │ APPROVE kèm yêu cầu sửa tài    │
│                         │ file nên không chỉ để đọc                           │ liệu, xem (a)                  │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §4 Kết quả và mã lỗi    │ complete ≠ PASS, không có status TIMEOUT, có thể    │ APPROVE kèm yêu cầu sửa tài    │
│                         │ file nên không chỉ để đọc                           │ liệu, xem (a)                  │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §4 Kết quả và mã lỗi    │ complete ≠ PASS, không có status TIMEOUT, có thể    │ APPROVE kèm yêu cầu sửa tài    │
│                         │ thiếu bundle                                        │ liệu, xem (b)                  │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §4.2 Quy tắc resume     │ Sáu quy tắc, M3 sở hữu                              │ APPROVE. Đã cài đặt, chỉ khác  │
│                         │                                                     │ một điểm, xem (c)              │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §5 Đề xuất              │ Thêm keyword, profile phải giữ nguyên khi session   │ APPROVE có điều kiện, xem (d)  │
│ experiment=None         │ được nạp lại                                        │                                │
├─────────────────────────┼─────────────────────────────────────────────────────┼────────────────────────────────┤
│ §5 A0/A1 ACCEPT dù      │ Kết luận theo policy, không theo kết quả static thô │ APPROVE. Aggregate của M3 đếm  │
│ static FAIL             │                                                     │ theo status                    │

Những điểm M3 phát hiện khi cài đặt runner, nên ghi vào receipt:

- (a) Engine nuốt Ctrl+C.
  - _step, observe và lời gọi generate bắt BaseException. Nhấn Ctrl+C sẽ thành record ERROR/INTERNAL_ERROR với complete=true, và KeyboardInterrupt không về tới runner.
  - §3.1 chưa nói điều này. Yêu cầu M2 ghi vào tài liệu, hoặc cho engine ném lại KeyboardInterrupt.
  - Runner M3 đã tự xử lý trường hợp này (bắt SIGINT, xem error_detail.type).
- (b) TEST_TIMEOUT không bao giờ là reason trong record.
  - Mã này chỉ có trong DTO của bundle. Trong record, timeout chỉ hiện qua cờ timed_out: true trong stage, còn reason là VERIFICATION_INCOMPLETE.
  - Yêu cầu bảng §4.1 ghi rõ chỗ M3 phải đọc để biết có timeout.
- (c) Quy tắc 3 ("đang chạy dở mà còn tiến trình thì chờ").
  - M3 không theo dõi PID mà dùng khóa độc quyền theo từng experiment (runner.lock).
  - Vì vậy reservation nào còn treo lúc khởi động thì chắc chắn là run bị gián đoạn. Kết quả vẫn đúng tinh thần quy tắc; chỉ cần báo M2 biết.
- (d) Điều kiện cho experiment=:
  - Vì vậy reservation nào còn treo lúc khởi động thì chắc chắn là run bị gián đoạn. Kết quả vẫn đúng tinh thần quy tắc; chỉ cần báo M2 biết.
- (d) Điều kiện cho experiment=:
  - Tên trường phải chốt sớm để ledger của M3 khớp, ví dụ record['experiment']['variant_id' | 'arm' | 'policy_hash'].
  - Profile phải đi qua được RepairSession.load, để đường MCP không bị vỡ.
  - Sau mỗi lần sửa session/pipeline, tests/m2/w78/test_w78_repair_server.py phải PASS (điều kiện D8).
- Lỗi nhỏ ở ví dụ §2.3: ví dụ truyền profile=profile ở mode fake, trong khi CLI chỉ truyền ở mode real. Nên sửa cho thống nhất.
