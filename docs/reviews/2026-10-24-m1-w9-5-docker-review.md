# Review cuối M1-W9-5 — 24/10/2026

Fresh reviewer: /root/final_m1_w9_5_review. Read-only; không chạy tests, Docker,
WSL/network/model hoặc sửa checkout. Không dispatch reviewer phụ.

## Kết luận kỹ thuật

Reviewer không phát hiện Critical hoặc Important trong phạm vi kỹ thuật. Đã đọc
raw reports/profile hashes của cả 5 task, frozen controller hashes, source binding,
cleanup và run ERROR được giữ nguyên. Bằng chứng 45 Linux tests, 320 regression và
lint PASS phù hợp. Đạt technical acceptance sau closing QA, không thay group approval.

## Findings và xử lý

1. Reviewer ghi Minor: phần tiếng Việt mới bị thay ký tự bằng ASCII '?', gồm
   contract, row/status và PROGRESS. Executor đánh giá đây là lỗi bàn giao cần sửa
   trước nghiệm thu vì contract không đọc được. Đã sửa bằng script UTF-8 ghi trực
   tiếp từ .NET rồi thực thi từ file, tránh stdin PowerShell bị mất ký tự.
   Khôi phục đúng baseline bytes của PROGRESS và status bằng SHA trước khi chỉnh
   phần W9-5; chỉ viết lại nội dung của task này. Backup và bằng chứng nằm trong
   documents_before_encoding_fix/ và document_encoding_fix.json. Không sửa tài liệu
   lịch sử ngoài task. Closing QA yêu cầu phần mới không còn '?' hoặc U+FFFD.
2. Reviewer ghi Minor: checklist chốt sớm trong lúc checkpoint còn REVIEW_PENDING.
   Đã đưa bước closing về pending; chỉ đổi thành complete trong closing QA sau khi
   mọi assertion đã qua. Không còn code finding hoặc minor tùy chọn bị bỏ lại.

## Các mục reviewer không kết luận và quyết định của executor

| Mục | Quyết định | Giới hạn nếu suy sai |
|---|---|---|
| Fresh rerun/live Docker/WSL/máy khác | Dùng actual run và live-owned-container audit đã lưu; không chạy lại để review | Không bảo đảm môi trường tương lai hoặc máy sạch |
| Full-repo preservation/unrelated dirty files | Closing QA so toàn bộ file được snapshot trước task; không audit lại logic repo | Defect cũ ngoài phạm vi vẫn có thể còn |
| Registry authenticity/availability hiện tại | Giữ metadata official registry và frozen digest; không resolve latest sau kết quả | Không chứng minh availability tương lai hoặc chữ ký publisher |
| Adversarial report authentication | Profile hashes là consistency/identity, không phải signed attestation | Consumer không được coi hash là quyền admission |
| Toàn filesystem trong image | Chỉ clean tracked source và Python inventory đã khai báo | Installed/untracked/build files thuộc immutable environment, không được gọi là full filesystem attestation |
| M2 repair/private lease/plugin/static/overlay | NOT_IMPLEMENTED, giữ thành bridge/admission task riêng | Collection profile không tự thực thi hoặc verify candidate patch |
| Model/gold/native/full suite/task sau | Không chạy, không suy PASS | Không có benchmark hoặc full VGAR acceptance mới |
| Sửa Astropy/Django hoặc population | Giữ reasons và 5 candidate; không đổi dependencies/warnings/scope sau outcomes | Chưa đủ 5 task runnable cho pilot; không tự bỏ denominator |
| Group approval/merge/publish/commit | Giữ riêng, không ký thay | Technical delivery không là group integration |
| Final preservation/checkpoint/doc QA | Thực hiện trong close_delivery.py rồi mới đánh dấu complete | Không tuyên bố hoàn thành nếu assertion/receipt chưa PASS |

## Quyết định thực thi

- Giữ dirty checkout được chỉ định; worktree từ HEAD sẽ thiếu inputs chưa commit.
  No commit/push; snapshot/ledger là hồ sơ bảo toàn.
- Dùng pytest discovery/config gốc cho cả hai arm. Fallback retrieval chứa negative
  data fixtures; ép import tất cả sẽ gây lỗi nhân tạo. Không suy collection này
  đã qualify mọi fallback file hoặc M2 selectors/plugin.
- Image có commit setup SWE-bench khác base: verify original object/root rồi reset
  chỉ trong container mới có ownership. Không nới HEAD/source guard; chấp nhận
  collection failure thật sau reset thay vì đổi base hoặc môi trường để ép PASS.
- Bounded cache reclaim được user duyệt riêng W9-5 max6, dùng1, có empty-container
  guard. Không thay resource threshold, settings, restart hoặc source/images host.

Evidence: results/m1/w9/m1-w9-5/20261024-docker-only/independent_audit.json,
regression_base_fix.json, lint_base_fix.json, base_prepare_red/green.json,
document_encoding_fix.json và closing QA/checkpoint cuối.
