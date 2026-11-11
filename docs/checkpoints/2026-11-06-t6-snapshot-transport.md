# T6 — snapshot transport lifecycle, 06/11/2026

## Điểm dừng có thẩm quyền

**T6 DONE code/fixture local; dừng chờ người dùng chốt T7.** Chưa Docker smoke
thật, chưa dọn dữ liệu lịch sử hoặc cache baseline, không commit/push.

- Gate cuối:144 PASS,1 SKIP,0 FAIL/ERROR,56,956s JUnit. Một skip là POSIX modes
  đã có; Windows junction test thực thi PASS. Không thêm skip/xfail để làm xanh.
- Ruff scoped và whitespace scoped exit0. Báo cáo Codex Diff dirty từ trước
  giữ nguyên bytes, không bị đưa vào chỉnh whitespace của T6.
- Review độc lập:2 Important,0 Critical/Minor/declined; cả2 test RED→GREEN.
  Final regression đã chạy sau fix; không có finding bị hoãn.
- Fixture14 operation:143.360 logical archive bytes được xóa,0 archive host
  còn lại; bản container giả lập độc lập được kiểm hash/size. Không đo campaign
  thật hoặc khẳng định giải phóng55GB trên ổ đĩa.
- Evidence: `results/m2/w1112/t6/20261106-snapshot-transport/`;
  `tests/final.log/.xml`, `final_commands.json`, `commands.md`,
  `fixture_summary.json`, `container_copy_checks.json`, `review.json`,
  `preservation.json`, `artifact_hashes.json`.
- Hướng dẫn/bàn giao: `docs/m2_t6_snapshot_transport.md`.
- Phạm vi source chỉ `docker_executor.py` và tests Docker admission. M2/PROGRESS
  và checkpoint được bổ sung; source cũ khác/report/DB/artifact cũ được bảo toàn.
- Việc chờ M3: smoke transport thật trên image/profile đã qualify, xác minh
  archive host mất sau copy, target attestation/report/container cleanup đạt.

Những mục sau là lịch sử triển khai trước gate cuối, không phải phần còn phải làm lại.

## Phạm vi đã duyệt

Chỉ dọn `control/snapshot.tar` của operation mới; giữ control metadata và
authoritative evidence. Cleanup archive lỗi: warning, giữ verdict/exception
chính. Nghiệm thu code/fixture Windows; smoke Docker thật chờ M3.
Không dọn archive lịch sử, cache baseline, đổi verifier/timeout hoặc làm T7.
Không commit/push; giữ báo cáo M2-W12/D15 đang có Codex Diff chưa commit.

## Lịch sử triển khai và điểm tiếp tục

- HEAD publication `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`.
- Snapshot/brief/ledger: `C:/Users/pc/AppData/Local/Temp/vgt6-20261106-zcf_esz7/`.
- Đã thêm tests lifecycle ở `tests/m2/w910/test_docker_admission.py`.
- Gate RED đang chạy: `red.log`/`red.xml` trong thư mục TEMP trên.
- Chưa sửa production code hoặc kết luận gate PASS.
- Tiếp theo: đọc RED, implement, GREEN, một review độc lập và fixes có test,
  regressions scoped, artifact/status/preservation, rồi dừng sau T6.

### Mốc sau review

- RED13 FAIL/17 PASS/1 SKIP; GREEN46 PASS/1 SKIP; coverage49 PASS/1 SKIP.
- Windows junction case chạy thật; skip là kiểm POSIX modes đã có.
- Scoped regression trước fix review:142 PASS/1 SKIP.
- Review read-only có2 Important, không Critical/Minor và không có declined scope.
  Metadata stat lỗi có thể ngăn cleanup; interrupt fallback hash có thể che
  lỗi build và bỏ qua container cleanup. Hai test đã RED2→GREEN2.
- Code đã sửa best-effort metadata, unlink độc lập metadata, nested finally
  bảo đảm container cleanup; giữ chính sách fatal của container cleanup cũ.
- Gate cuối đang chạy: `final_gate.py`, `final.log/.xml` và `final_commands.json`
  trong TEMP trên. Không chạy lại khi chưa đọc kết quả cuối.
- Sau gate: archive receipts/fixture14 operation, kiểm preservation và cập nhật
  trạng thái. Chưa có Docker smoke thật; không tự chuyển T7.

Đọc checkpoint này trước khi resume; không chạy lại phần đã PASS nếu không
có thay đổi liên quan. Kết quả fixture không phải dung lượng campaign thật.
