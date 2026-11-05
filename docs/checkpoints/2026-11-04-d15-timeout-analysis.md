# D15 — checkpoint triển khai, 04/11/2026

## Điểm dừng hiện tại — 05/11/2026

**Công cụ/fixture D15 đạt gate; dừng, chờ lệnh tiếp. D15 toàn bộ chưa nghiệm
thu thực nghiệm.** Không còn bước code/test bắt buộc trong phạm vi tool này.

- Gate cuối: **120 PASS, 0 FAIL/ERROR/SKIP, 77,444 giây JUnit**:
  54 test D15 +66 regression failure/runner/aggregate-class.
- Ruff scoped và `git -c core.whitespace=cr-at-eol diff --check`: exit 0.
- Review độc lập: cả 6 finding đã có test tái hiện RED→GREEN trong một lượt;
  không còn finding bị hoãn. Đây không thay review/approval chính thức của nhóm.
- Raw evidence: `results/m2/w1112/d15/20261105-tool-fixture/`.
  `tests/final.log`, `tests/final.xml`, `final_commands.json`, `commands.md`,
  `review.json`, `preservation.json`, `artifact_hashes.json`.
- `readiness/`: WAITING_DATA, exit 2, 75 W10+25 A3 slot, không measurement giả.
- `fixture_output_a/` và `fixture_output_b/`: synthetic, PARTIAL/exit 2;
  100 rows, 99 selected engine+1 runner exclusion; 75/25 unique resolved.
  Output byte-identical, fixture input unchanged. Không phải số liệu W10/A3 thật.
- Hướng dẫn: `docs/m2_d15_timeout_analysis.md`.
- Chỉ thêm script/test/tài liệu D15, prepend PROGRESS và append m2; bảo toàn
  nguyên bytes các thay đổi A3/pool/spec/report/fixture DB đã có trước D15.
- Chờ M3 export experiment/ledger/linked run records thật của W10 và A3;
  sau đó phân tích dữ liệu, review và đề xuất timeout. Giữ 900/1800; ứng viên
  1500/2700 chưa được chọn. Không tự chạy campaign, D15 thực nghiệm, task kế,
  Docker/model/held-out hoặc commit/push.

Các phần phía dưới là lịch sử trước khi gate cuối hoàn thành.

## Phạm vi được duyệt

Chỉ công cụ phân tích offline và fixture D15. Không chạy campaign, model,
Docker hoặc đổi engine/runner/policy/timeout; không commit/push.

## Điểm tiếp tục

- HEAD `c88290a147bc42b70261b39e50b7f11d5e5137ea`, nhánh M2 hiện tại.
- Snapshot trước triển khai: `C:/Users/pc/AppData/Local/Temp/vgd15-20261104-ht47o7kd/before.json`.
- Giữ nguyên các thay đổi A3/mutant pool và tài liệu chưa commit.
- Đã đọc schema batch experiment/attempt/run record; không dùng loader cần source/model.
- Bước tiếp theo: test RED → script → GREEN → review → regression → evidence/tài liệu.

Đây là checkpoint đang thực hiện, chưa tuyên bố gate PASS. D15 toàn bộ vẫn
chờ raw W10/A3 và đề xuất timeout dựa trên dữ liệu thật.

## Khôi phục ngày 05/11/2026

- Đã có script, tài liệu M2 và 46 test D15 PASS (`green-02.log/.xml` trong TEMP trên).
- Regression failure/runner: 66 PASS/44,77 giây (`regression.log/.xml`).
- Review độc lập đã xong, không review lặp: 3 Important và 3 Minor;
  khi đánh giá tác động, cả 6 được xử lý trong một lượt vì ảnh hưởng readiness,
  report generation hoặc evidence chính xác. Không có hành vi bị reviewer bỏ qua.
- Các lỗi cần sửa: interrupted predecessor chỉ có engine_output_root; mất input
  tokens có sẵn ở prompt khi generation timeout; READY dù invalid/unbound;
  median overflow; failure metadata NaN làm report abort; evidence attempt-10
  bị trỏ nhầm attempt-9 do thứ tự từ điển.
- Đã thêm 8 test tái hiện, đang chạy `review-red.log/.xml`. Tiếp theo đọc RED,
  sửa script, chạy GREEN + regression, lưu fixture/readiness và preservation,
  cập nhật trạng thái. Chưa có evidence final dưới results, chưa tuyên bố hoàn tất.
- Không có thay đổi mới cho engine/runner/aggregate/policy/spec nguồn/board;
  các file pre-existing còn nguyên bytes theo snapshot lúc đầu.
