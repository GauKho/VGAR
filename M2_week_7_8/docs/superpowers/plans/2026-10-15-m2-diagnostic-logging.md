# M2 — bổ sung diagnostics, không chạy thêm repair

Yêu cầu đã được user giao thực hiện: vị trí/counts parser, full traceback và
effective generation config/attention mask. Chỉ M2_week_7_8; không sửa VGAR,
fixtures, prompt, ngân sách, public DTO, parser acceptance hoặc verdict logic.
Đây là ba thay đổi nhỏ của task logging, không mở lại plan real repair đã terminal.

## Thiết kế thực hiện

- Parser giữ ValueError/message cũ; bổ sung diagnostics raw line (1-based),
  path/hunk, expected counts, actual valid body counts và invalid body lines.
  Actual counts không suy đoán dòng model thiếu prefix; đánh dấu incomplete.
- Exception được ghi tại ranh giới pipeline/worker/executor/checks/CLI:
  type/message/full chained traceback, không capture locals/env/secrets.
  Control-flow StopRun, exception được rethrow và process bị OS kill không được
  diễn giải là có traceback Python mới nếu thực tế không có.
- Quan sát config/mask tại `_get_logits_processor` (pre-decode) của runtime HF đã pin;
  giữ nguyên generate args/sampling/tensor, không tự bổ sung mask hoặc đổi model.
  Lưu supplied config, overrides, full effective config và mask summary/hash;
  ghi file generation_diagnostics.json trước decode để lỗi sau đó vẫn truy vết được.
  Restore observer khi success/error; unsupported decoder ghi rõ chưa quan sát.
  Review phát hiện HF4.57.6 dispatch decoder qua type(self), nên KHÔNG patch
  instance._sample; test phải mô phỏng class dispatch thực tế.

## Các bước

- [x] Kiểm checkpoint, boundary non-Git, archive runtime/evidence V5+ trước sửa.
  Snapshot: results/diagnostics-preflight/20261015T012505328670Z-d98793260a4a/archive_manifest.json.
- [x] TDD parser diagnostics và traceback; giữ guards bằng legacy/full suite.
- [x] TDD generation observer/worker persistence bằng CPU-safe doubles, không
  load weights/inference. Không claim real GPU validation từ doubles.
- [x] TDD propagation ở pipeline, command, static/test errors và CLI caught errors.
- [x] Full tests/Ruff; replay bốn raw B offline; audit hai archives/evidence.
- [x] Update PROGRESS và hướng dẫn tiếng Việt. No commit/push/real attempt.

## Lịch sử và giới hạn

Không sửa frozen_inputs.json/canonical/manifest cũ để cho code mới khớp code cũ.
Sau logging change, --status của campaign cũ tiếp tục fail-closed vì code hash
khác. Đọc campaign JSON và --history --archive-manifest với snapshot V5+ ở trên
để chứng minh lịch sử; không reset campaign hoặc chạy B5.

Log đầy đủ không phải chứng minh nguyên nhân nội tại của LLM. Không có real
generation mới; B vẫn BLOCKED, C V9 PASS là kết quả runtime cũ.
