# M1-W9-4 — Nghiệm thu gold thật local

Plan người dùng duyệt23/10/2026, kế thừa phần offline đã xong; không redo wrapper.

## Mục tiêu / giới hạn

- Đúng3IDs đầu pilot: astropy__astropy-13398, django__django-11138,
  matplotlib__matplotlib-14623. Ít nhất2official resolved, giữ kết quả task thứ ba.
- Harness4.1.0@726c5461e2ef52d83cf1ea2107870a8bb3328d57; snapshot/gold/manifest
  và M1/M2 cũ giữ nguyên. Không LLM, W9-5, commit/push hoặc Task Status.md.
- Hai campaign mới tối đa6task attempts; không lặp unchanged hoặc trộn runtime.
  Test1800s, subprocess3600s/task, worker1; cleanup/integrity fail phải dừng.

## Runtime đã chốt

- Ubuntu24.04 WSL2 tên VGAR-Harness-W9, cài tại
  D:\Project\CAPSTONES\environments\wsl-vgar-harness-w9. Không đổi default distro.
- DockerDesktop hiện có, VHD D:\DockerDesktopWSL giữ nguyên. Chỉ bật integration
  cho distro mới, không DockerEngine trong Ubuntu. GUI/admin/reboot không thao
  tác an toàn được thì dừng xin người dùng, không registryhack/TCP không auth.
- Hai Linux venv controller/harness riêng, Python3.12; controller Pydantic+pyarrow,
  không fullVGAR/Torch. Harness editable đúng sourcepin, docker7.1.0, ghapi<2;
  freeze/logs đủ. Explicit Unix socket, CLI/SDK daemon ID cùng nhau.
- Reserve C10GiB/D20GiB; trước execution Windows/Linux mỗi bên available RAM4GiB.
  Không tự sửa .wslconfig/RAM/swap/resizeVHD hoặc thuê máy. Thiếu thìBLOCKED.

## Images Linux/amd64 pinned

Repository namespace swebench, instance __ thay _1776_, localtag vgar-w9-20261023.
Pull digest, không dùng latest làm identity; cache đúng thìreuse, không overwrite
tag khác. Ghi actualimageID/RepoDigest vào qualified-profile ignored.

| Task | Digest |
|---|---|
| astropy__astropy-13398 | sha256:4d7e922ae3b796147f85b37861f6dec5463001a964bd941ed6933109245fe69f |
| django__django-11138 | sha256:811f9bf0ca067b334b574cd3589cdc989b350b2a24b68e1ddcd288fbb97d61f4 |
| matplotlib__matplotlib-14623 | sha256:52cdd8ac0f4a8b05f40507d500680ec613092186310cbaf7895d1554e9d654dc |

## Checklist

- [x] Đối chiếu status/diff/checkpoint, snapshotbefore và resource gateWindows.
- [x] Distro + Desktop integration + Linux venv/source/images đúngpins.
- [x] Linux48wrapper tests, shellhelp và owned tree timeout/cleanup thật (24/10).
- [x] Daemon/image identity, owned container cleanup và preflight readiness.
- [x] Preflight inputs thật đủ readiness; modepreflight các taskNOT_RUN.
- [x] Chạy3gold task tuần tự, logs/report/identity/integrity/cleanup đầy đủ.
- [x] Đọc lại reports độc lập, status/docs/PROGRESS và before/after; dừngW9-4.

Checkpoint23/10: distro đã cài và DesktopRunning; dừng trước provisionpackages/
images vì Windows availableRAM2,92GiB<4GiB và integration distro chưa bật.
Xem `docs/m1_w9_4_local_qualification_checkpoint.md`;0campaign/0attempt.

Resume23/10 sau khi user bậtintegration: integrationPASS và resourcegate đầuPASS.
Đã provision Linuxvenv prerequisites, hai venv và harnessclean đúngpin; haiimage
Astropy/Django đúngdigest/tagriêng. Dừng trướcMatplotlib vìWindows available
3.846.205.440bytes≈3,58GiB<4GiB. Pipcontroller đang tải đượcSIGTERM đúngownership;
dependencies chưa cài xong, hai freeze rỗng, chưaqualifiedprofile/LinuxQA/gold.
Không thay thresholds hoặc chỉnhWindows/WSL resources;0campaign/0attempt.
Tiếp từresourcegate, reusevenvs/source/haiimages, không reinstall hoặc redooffline.

Evidence mới: results/m1/w9/m1-w9-4/20261023-local-qualification/.
Runtime profile: results/m1/w9/m1-w9-4/runtime/qualified-profile.json (ignored).

Resume24/10: resource gates PASS; hai Linux venv dependencies/pip check/freeze
đã hoàn tất, clean pinned source PASS. Linux48tests/shell/CLIhelp/owned process
timeout PASS. Gold0campaign/0attempt. BLOCKED mới: Docker Desktop startup lỗi ở
Inference manager/dockerInference socket, backend thoát; config integration vẫn
có distro. Không reset/xóa socket hoặc retry unchanged. checkpoint_resume_02.json
ghi phần đã xong để không reinstall/reclone/redo phần offline Windows lần sau.

## Reference

- https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- https://docs.docker.com/desktop/features/wsl/
- https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/README.md


## Đóng kỹ thuật M1-W9-4 — 24/10/2026

- Campaign cuối `20261024T081750218758Z-3af0d2d105bc`: **QUALIFIED,3/3RESOLVED**, 213.538s.
  Raw reports/logs/patch bytes ở `results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/`; kiểm toán độc lập PASS.
- Fix đúng report path logs/run_evaluation của harness pin; Linux RED1FAIL→GREEN49PASS.
  Selected regression467PASS/1SKIP; skip real symlink Windows. Lint có E741 cũ,
  baseline/current giống nhau; scoped exclusion PASS, full suite NOT_RUN.
- Giữ campaign1 UNMET/3ERROR và raw3resolved; campaign2 sau fix3RESOLVED.
  Quota đã dùng2/2campaigns,6/6attempts; không chạy thêm. Gold qualification
  không là model repair hoặc pilot. Raw Astropy1FAIL/Matplotlib179FAIL vẫn giữ;
  official F2P/P2P bắt buộc không có failure, không claim mọi pytestPASS.
- User duyệt bounded cache reclaim, dùng2/3. Không quarantine/reset/prune/update,
  đổi settings/RAM/swap hoặc restartWSL. Images chuẩn bị lại đúngpins sau user
  báo có thể đã dọncache; rootcause socket/cache chưa được chứng minh đầy đủ.
- Báo cáo: docs/m1_w9_4_acceptance_report.md. Checkpoint chốt:
  results/m1/w9/m1-w9-4/20261023-local-qualification/checkpoint_gold_final_07.json.
  Wrapper49tests, audit rawgold, cleanup và preservation là các gate riêng.
- Hoàn thành kỹ thuật W9-4; review/merge nhóm chưa thực hiện. Source khác/TaskStatus
  giữ nguyên, không commit/push/W9-5/model/held-out; dừng chờ task mới.
