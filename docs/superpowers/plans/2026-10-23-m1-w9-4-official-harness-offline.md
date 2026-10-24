# M1-W9-4 — Wrapper official harness và kiểm thử offline

Kế hoạch được người dùng duyệt ngày23/10/2026; thực hiện riêng W9-4 rồi dừng.

## Mục tiêu và giới hạn

- Implement wrapper gold validation, CLI mặc định preflight; chỉ `--execute`
  mới có thể chạy harness sau khi đủ qualification. Phiên này chỉ code/mock tests.
- Không cài dependencies, start Docker/WSL, tải images, chạy gold/model thật,
  thay environment chung, commit/push hoặc sửa Task Status.md/W9-5.
- Bảo toàn W9-1/2/3, code M2 và các thay đổi chưa commit. Làm trong VGAR hiện tại
  theo yêu cầu người dùng, không tạo worktree thiếu implementation chưa commit.

## Thiết kế đã chốt

- SWE-bench v4.1.0@726c5461e2ef52d83cf1ea2107870a8bb3328d57, không latest/main.
- Đúng3IDs đầu manifest W9: astropy__astropy-13398, django__django-11138,
  matplotlib__matplotlib-14623. Snapshot c104f840cc67f8b6eec6f759ebc8b2693d585d4a;
  Parquet hash đã pin. So ID/repo/basecommit/query trước trích gold/test metadata.
- Gold chỉ trong evaluation ignored. Project dev khác upstream partition test.
- API run_gold_validation(pilot_manifest, *, harness_profile, instance_ids,
  output_root)->dict. Module official wrapper; input/profile helpers tách nhỏ.
- Linux harness interpreter/source pin/CLI/Docker/image identity phải có thật;
  config skeleton UNQUALIFIED không thể launch. Một task/invocation, worker1,
  test1800s/subprocess3600s, run ID mới; không tự retry hoặc tăng budget.
- Parser report không tự chấm lại F2P/P2P; đúng task, boolean strict, log/patch
  binding. Exit0 không đủ resolved. Giữ ERROR/TIMEOUT/BLOCKED/NOT_RUN riêng.
- Evidence append-only, stdout/stderr/traceback/UTC/duration/hash/raw reports.
  Cleanup chỉ container của run có owner xác minh; không prune/delete chung.

## Các bước và nghiệm thu

- [x] Snapshot status/checkpoint và ghi baseline trước sửa.
- [x] RED tests cho gold projection/identity, argv/report và fake process/error.
- [x] Implement input/profile, wrapper, CLI và shell entrypoint; GREEN.
- [x] Regression selected + Ruff; Bash syntax PASS, Linux execution chưa nghiệm thu.
- [x] Review độc lập một lần;5findings quan trọng/6tests RED→GREEN,48PASS.
- [x] CLI preflight thật không launch harness; BLOCKED/exit2,3taskNOT_RUN.
- [x] Cập nhật hướng dẫn, statusM1, PROGRESS; closing checks lưu trong evidence QA.

Nghiệm thu offline không đóng gold qualification. Task đầy đủ còn cần ít nhất
2/3 task fixed resolved từ official harness, giữ cả kết quả task thứ ba.

## Nguồn đã đối chiếu

- https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/run_evaluation.py
- https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/utils.py
- https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/grading.py
