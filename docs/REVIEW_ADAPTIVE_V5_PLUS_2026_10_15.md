# Review trước inference V5+ — 15/10/2026

Một fresh-context gpt-6-astra reviewer, read-only; không model/tests/agents phụ.
Baseline đối chiếu là archive runtime trước thay đổi, không Git diff (M2 non-Git).

| Finding | Phân loại sau review | Xử lý |
|---|---|---|
| Crash giữa revision file và manifest, hoặc directory và reservation | Important | Reconcile immutable orphan registration; durable reservation trước mkdir |
| Đổi tên V5→V6 nhưng nội dung y hệt vẫn chạy lại | Important | Reject identical normalized template hash của failed parent; không mất attempt |
| Recovery terminal PASS/WAIT_PROMPT báo command ERROR | Regrade Minor→Important: ảnh hưởng resume thông thường | Kiểm next_action sau recovery, không reserve khi terminal/wait; export profile chỉ terminalPASS |
| Static-check FAIL nhưng feedback lấy stdout pytest PASS | Minor deferred | Full diagnostics vẫn có trong canonical; Codex phải đọc failed static stage, không chỉ feedback summary |

Một TDD fix pass: RED4 +9priorPASS tại
`results/tests/20261015T003232409439Z-45a30e887790/run_record.json`;
GREEN22 combined tại `results/tests/20261015T003334787835Z-188f03ecb3a7/run_record.json`.
Fullsuite cuối fix và Ruff/audit lưu ở PROGRESS. Không có review thứ hai.
Không sửa parser/verifier/source/tests/gold fixtures để đạt PASS.

Reviewer không đánh giá empirical modelquality, future revision semantics/goldabsence,
hostile coordinated local-file rewriting, global GPU scheduler/arbitrary API callers,
Linux orphanworker behavior, futuredocs/humanrepro/M3, Git workflows. Các giới hạn
này được root ledger riêng; không được dùng làm bằng chứng nghiệm thu.
