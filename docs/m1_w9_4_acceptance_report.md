# M1-W9-4 — Nghiệm thu official gold local, 24/10/2026

**Hoàn thành kỹ thuật: QUALIFIED, 3/3 task RESOLVED**, đạt gate ít nhất2/3 của
[kế hoạch local](superpowers/plans/2026-10-23-m1-w9-4-local-gold-qualification.md).
Đây là qualification hạ tầng bằng developer gold patch. Chưa có kết quả model tự
repair, pilot A0–A2, held-out, review M3 hoặc PR/merge nhóm từ bằng chứng này.

## Kết quả hiện hành

Campaign: `20261024T081750218758Z-3af0d2d105bc`, `run_record.json` complete=true, resolved_count=3;
monotonic wall duration **213.538s** (không phải thời gian test riêng).
Raw inputs, commands, stdout/stderr, patch, reports và cleanup ở `results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/` (ignored).

| Task | Canonical | F2P success/failure | P2P success/failure | Wall seconds |
|---|---|---|---|---|
| astropy__astropy-13398 | RESOLVED | 4/0 | 68/0 | 93.083 |
| django__django-11138 | RESOLVED | 1/0 | 73/0 | 30.799 |
| matplotlib__matplotlib-14623 | RESOLVED | 1/0 | 400/0 | 84.610 |

Mỗi task có `logs/run_evaluation/<invocation_id>/vgar-w9-gold/<task>/` với
`report.json`, `patch.diff`, `test_output.txt`, `run_instance.log`, `eval.sh`.
Kiểm toán độc lập đọc Parquet gốc đúng SHA, so gold bytes với patch thật, strict
booleans/identity, hashes artifacts/inputs/profile/manifest, runtime sau từng task
và cleanup. Kết quả PASS: `results/m1/w9/m1-w9-4/20261023-local-qualification/independent_gold_audit_07.json`.

**Giới hạn raw test output:** Astropy ghi `1 failed,72 passed,3 skipped`;
Matplotlib ghi `179 failed,402 passed,73 skipped`. Official report vẫn resolved=true
vì các tập F2P/P2P bắt buộc trong bảng đều không có failure. Giữ nguyên toàn bộ
output và không gọi toàn bộ pytest của các repo là PASS; chưa phân tích các lỗi
ngoài tập official grading trong W9-4. Django có1 F2P và73 P2P success.

## Runtime/pins và thao tác đã làm

- WSL2 VGAR-Harness-W9, Ubuntu24.04/Python3.12; hai venv controller/harness riêng.
  Harness4.1.0@726c5461e2ef52d83cf1ea2107870a8bb3328d57 clean/editable; pip check PASS.
- DockerDesktop4.48.0/Engine28.5.1 Linux/amd64; Unix socket rõ, CLI/SDK cùng daemon.
  Sau người dùng Quit, runtime directory đã trống. Guard dừng trước quarantine;
  không rename/delete endpoints. Một start sau Quit thành công. Chưa chứng minh
  nguyên nhân sâu lỗi socket hoặc bảo đảm lỗi startup không tái diễn.
- Cache0images được giữ evidence; người dùng cho biết có thể đã dọn cache thủ công.
  Chuẩn bị lại đúng3digest trong plan, không đổi image store/settings hoặc reset/prune.
  Profile identities thực: `results/m1/w9/m1-w9-4/runtime/qualified-profile.json`.
- RAM/đĩa đạt gate trước gold. User duyệt tối đa3 lần sync+drop_caches=1 khi không
  có container chạy; thực dùng **2/3** lần, có reservations/results.
  Không đổi RAM/swap/.wslconfig, restart WSL hoặc cài lại môi trường.
- Container smoke create/start/inspect/cleanup thật PASS. Tất cả task cleanup và
  runtime/input integrity PASS; audit cuối không còn container. Không xóa images.

## Lỗi tìm thấy và regression

Campaign đầu `20261024T080530283089Z-8b6443653c6d` giữ nguyên **UNMET**, 0 canonical
resolved/3ERROR dù raw official reports3resolved. Wrapper đọc `logs/evaluation`,
trong khi hằng `RUN_EVALUATION_LOG_DIR` của pin là `logs/run_evaluation`.
Không sửa runtime đang chạy. Sau terminal, sửa đúng một path trong
`src/vgar/evaluation/harness/official.py`, sửa synthetic boundary fixture cho đúng
upstream layout và thêm test campaign đọc report thật từ layout đó.

- Windows RED đầu bị temp ACL ERROR trước test; giữ log, không coi là RED logic.
- Linux regression RED1FAIL → GREEN; full wrapper **49PASS**,2.68s.
- Selected regression **467PASS/1SKIP**,162.70s; SKIP real symlink do quyền Windows.
  Nhóm tests giữ cùng nhóm offline trước đó, gồm harness/retrieval/impact/M2 W9/evidence.
- Ruff có đúng một E741 có sẵn tại tests/test_official_harness.py:85; baseline và
  current findings giống nhau. Scoped lint với E741 cũ excluded PASS; không claim
  full lint sạch. Không sửa style ngoài phạm vi. Full repository suite NOT_RUN.
- Campaign thứ hai chạy mới sau fix, giữ nguyên3IDs/profile/manifest/pins/timeouts,
  đạt3RESOLVED. Tổng quota **2/2 campaigns,6/6 real attempts**, không còn lượt;
  không retry hoặc trộn PASS giữa campaigns, không sửa record cũ.

Evidence root: `results/m1/w9/m1-w9-4/20261023-local-qualification/`.
Xem `path_red_linux_06.json`, `path_green_linux_06.json`, `final_regression_06.json`,
`path_fix_06/lint_baseline_comparison.json`, `runtime_07/result.json`,
`gold_07_control/gold-summary.json` và `progress_resume_06.md`.
Audit child đã PASS; recorder trùng tên output JSON nên receipt ngoài báo FileExistsError.
Giữ audit JSON/raw stdout và lỗi recorder; kiểm xác nhận riêng, không ghi đè file.

## Bảo toàn và điểm dừng

HEAD giữ525f9936a3c0abe5ea056c532c1f889ce84627a7. Source trước campaign2 chỉ đổi
wrapper path và tests tương ứng; snapshot trước/sau campaign2 byte-identical.
Code M1/M2 khác, manifest/bundles/fixtures/configs và Task Status.md giữ nguyên.
Không commit/push, không triển khai W9-5. Tài liệu/checkpoint mới được ghi riêng;
không thay receipts/hashes lịch sử để che delta.

Quyết định thực thi: giữ dirty checkout theo chỉ định; evidence ledger thay
worktree/commit để dùng đúng implementation đang qualification. Không quarantine
runtime trống sau Quit; vẫn phải kiểm daemon/image identities. Chi phí nếu sai:
chọn checkout khác sẽ bỏ mất inputs chưa commit; coi start thành sửa gốc sẽ bỏ
qua rủi ro tái diễn. Các nguyên nhân sâu vẫn được ghi chưa xác định.

Bước kế chỉ thực hiện theo task mới của người dùng. Review độc lập là code/evidence
QA; không thay phê duyệt M3, PR/merge nhóm, clean-machine hoặc benchmark acceptance.


## Review v? closing QA

[Review ??c l?p](reviews/2026-10-24-m1-w9-4-local-gold-review.md):0Critical/0Important,
kh?ng c? minor m?i c?n x? l?; reviewer ki?m c?6rawreports v?30artifacthash kh?ng
mismatch. C?c gi?i h?n/decisions v? chi ph? n?u suy sai ???c ghi trong receipt.
Host/WSL receipts c? ?o?n UTC kh?ng ??n ?i?u; durations d?ng monotonic, kh?ng suy
performance ho?c cross-host chronology t? ph?p tr? UTC. Closing evidence:
`delivery_final_07.json`, `delivery_final_receipt_07.json`,
`checkpoint_gold_final_07.json` trong evidence root.
