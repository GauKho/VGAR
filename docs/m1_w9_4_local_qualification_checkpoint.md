# M1-W9-4 — Checkpoint chuẩn bị nghiệm thu local

**Trạng thái mới nhất24/10: HOÀN THÀNH KỸ THUẬT,3/3 official gold RESOLVED.**
Xem [báo cáo nghiệm thu](m1_w9_4_acceptance_report.md) và checkpoint_gold_final_07.json.
Các mục BLOCKED phía dưới là lịch sử; không reinstall/rerun theo các checkpoint cũ.

Ngày23/10/2026. **Task chưa hoàn thành; gold qualification BLOCKED.** Đây là
phần tiếp nối plan local đã được người dùng duyệt, không thay evidence offline.

## Đã thực hiện

| Nội dung | Kết quả thực |
|---|---|
| Snapshot trước thao tác | Đã lưu hashes/HEAD; không checkout/reset/commit |
| Gate ban đầu | Windows available5644480512bytes, C/D đủreserve10/20GiB |
| Docker Desktop hiện có | Đã khởi động, Desktop4.48.0 / Engine28.5.1 linux/amd64 |
| Dữ liệu Docker cũ | Giữ tại D:\DockerDesktopWSL; không di chuyển/xóa/prune |
| Distro mới | VGAR-Harness-W9, Ubuntu24.04.5LTS, WSL2 trênD |
| Vị trí distro | D:\Project\CAPSTONES\environments\wsl-vgar-harness-w9 |
| Python Linux có sẵn | Python3.12.3; chưa cài packages/venvs/harness |
| Gate sau boot | **FAIL**: Windows available3137372160bytes≈2,92GiB <4GiB |
| Linux Docker socket | Chưa có /var/run/docker.sock; Desktop yêu cầu bật WSL integration |
| Images / gold / campaigns | Chưa pull image, chưa gold run;0/2campaign,0/6attempt |

Distro mới đã cài thành công, lần quan sát sau probe là **Stopped do idle**;
không phải cài lỗi. Distro mặc định vẫn docker-desktop, không bị đổi.
Docker Desktop đang Running để người dùng vào Settings; không tự tắt ứng dụng
của người dùng, sửa RAM/swap/.wslconfig hoặc restart toàn bộWSL.

## Việc người dùng cần làm trước khi tiếp tục

1. Trong Docker Desktop, mở **Settings → Resources → WSL Integration**.
2. Chỉ bật integration cho **VGAR-Harness-W9**, rồi **Apply & Restart**. Nếu có
   containers của công việc khác đang chạy, kiểm tra trước khi Apply/Restart;
   agent không tự dừng containers không rõ owner.
3. Đóng bớt ứng dụng không cần thiết để Windows có ít nhất **4GiB RAM available**
   khi Docker/WSL đang hoạt động. Không chỉ kiểm tổngRAM16GB; cầnavailable thực.
4. Yêu cầu: **“Tôi đã bật integration và giải phóng RAM, tiếp tục M1-W9-4.”**

Không cần cài lại Ubuntu, Docker Desktop hoặc dependencies Windows. Khi resume,
agent kiểm lại socket/daemon identity và resource gates trước, không tiếp tục
theo giả định GUI hoặc RAM đã đạt. Nếu vẫn không đạt, giữBLOCKED và xin hướng
tài nguyên mới; không giảm ngưỡng để chạy.

## Phần còn lại khi gates đạt

- Linux controller/harness venv riêng; source đúngcommit và packages constraints.
- Pull/reuse đúng3image digests đã duyệt, lưuID/RepoDigest, không latest drift.
- Linux48tests, owned process/container smoke, shell/preflight thật.
- Chạy3gold task fixed, đạt ít nhất2resolved và kiểm raw reports/cleanup/integrity.
- Cập nhật status/checkpoint rồi dừngW9-4; không tự W9-5 hoặc commit/push.

## Evidence

Root: `results/m1/w9/m1-w9-4/20261023-local-qualification/` (ignored).

- `before.json`, `resource_before.json`, `docker_start.json`, `wsl_install.json`.
- `linux_probe.json`: source của OS/Python/Linux resources/socket failure.
- `resource_after_boot.json`: lỗiRAM với fullstdout/stderr/exit/duration.
- `distro_after.json`, `docker_server_after.json`, `docker_cli_capabilities.json`.
- `checkpoint.json`: blocked state và quota chưa dùng; mỗi command có rawbinary,
  decodedlog, argv, UTCstart/end và duration. Không ghi đè evidence cũ.

Public runtime profile skeleton vẫnUNQUALIFIED; không có gold-resolved report nào.

## Cập nhật sau khi người dùng bật integration — 23/10/2026

**Trạng thái hiện tại: BLOCKED bởi RAM Windows, không còn bị chặn bởi integration.**
Các bảng phía trên là lịch sử của lần dừng trước, không phải inventory hiện tại.

| Hạng mục | Kết quả mới đã quan sát |
|---|---|
| WSL integration | PASS: `/usr/bin/docker`, `/var/run/docker.sock`, Engine28.5.1 Linux/amd64 truy cập được từ distro |
| Gate lúc resume | PASS: Windows available6.375.936.000bytes≈5,94GiB; Linux available7.426.637.824bytes≈6,92GiB |
| Packages hệ điều hành | Đã cài `python3-venv` và dependencies cần thiết; apt cập nhật Python3.12/Git/CA trong distro riêng, không Windows |
| Hai venv riêng | Đã tạo `/home/vgar/w9/venvs/controller` và `/home/vgar/w9/venvs/harness` |
| Harness source | `/home/vgar/w9/swebench`, HEAD `726c5461e2ef52d83cf1ea2107870a8bb3328d57`, clean |
| Cài Python dependencies | **Chưa hoàn thành**; controller pip đang tải pyarrow thì được agent dừng do resource gate. Hai `pip freeze` sau dừng rỗng; harness editable chưa được cài |
| Astropy image | Đã pull/inspect đúng digest `4d7e922…fe69f`, local tag `vgar-w9-20261023` |
| Django image | Đã pull/inspect đúng digest `811f9bf…61f4`, local tag `vgar-w9-20261023` |
| Matplotlib image | **Chưa pull**; gate chặn trước `docker pull` |
| Gate sau hai images | FAIL: Windows available3.846.205.440bytes≈3,58GiB <4GiB; C14.478.110.720bytes/D69.649.788.928bytes còn đủ reserve |
| Linux sau dừng | Available7.227.367.424bytes≈6,73GiB; Linux không phải gate đang fail |
| Gold / Linux48tests / qualified profile | NOT_RUN / NOT_RUN / chưa tạo; skeleton vẫn UNQUALIFIED |
| Quota | **0/2 campaigns, 0/6 real task attempts** |

Không kết luận RAM giảm là lỗi wrapper hoặc harness. Phép đo chứng minh Windows
available dưới ngưỡng sau các thao tác provisioning/images; chưa cô lập nguyên
nhân tiêu thụ RAM theo từng process/cache. Không tự drop cache, chỉnh RAM/swap,
restart Docker/WSL, xóa images hoặc tắt ứng dụng người dùng để vượt gate.

Pip controller PID6726 được xác nhận argv và parent là `install_python.sh` của
đúng phiên này rồi gửi SIGTERM. `install_python_01.json` exit143 là **dừng chủ
động theo resource gate**, không phải bằng chứng pip resolver/install failure.
Script cha đã terminal; không để installation tiếp tục ngầm. Không chạm process
ngoài ownership. Installation logs và phần tải dở được giữ, không xóa cache.

### Khi tiếp tục lần sau

1. Người dùng giải phóng thêm RAM **khi Docker/WSL và hai images đã ở trạng thái
   hiện tại**; giữ ít nhất4GiB available, có thêm khoảng đệm thì tốt hơn.
2. Yêu cầu tiếp tục M1-W9-4; agent đo Windows/Linux lại trước khi thao tác.
3. **Không cài lại distro/venvs hoặc clone lại source.** Kiểm source pin/clean;
   tiếp tục dependencies còn thiếu, lưu installation logs/freeze mới.
4. Reuse Astropy/Django nếu identity đúng; chỉ chuẩn bị Matplotlib còn thiếu,
   vẫn kiểm gate trước pull. Không dùng tag `latest` Astropy khác digest đã có
   trước phiên này, không xóa hoặc thay tag đó.
5. Sau đủ runtime/images mới Linux48tests, owned process/container smoke,
   preflight rồi ba gold tasks theo plan. Không đổi thresholds/timeout/population.

Evidence mới cùng root: `resource_resume_01.json`, `linux_probe_resume_01.json`,
`provision_linux_01.json`, `install_python_01.json`, `image_astropy_01.json`,
`image_django_01.json`, `image_matplotlib_01.json`,
`resource_after_two_images_01.json`, `stop_owned_install_01.json`,
`provision_inventory_01.json`, `checkpoint_resume_01.json`. Mỗi command có
stdout/stderr raw + decoded logs, argv, UTC và duration; evidence cũ giữ nguyên.

## Checkpoint mới nhất — 24/10/2026

**Đọc mục này trước các bảng lịch sử phía trên.** `checkpoint_resume_02.json`
ghi điểm tiếp tục mới, không thay checkpoint 01.

- RAM/ổ đĩa PASS: sau cài Windows available ≈4,91 GiB, Linux ≈7,13 GiB;
  số đo của phiên không bảo đảm lần sau vẫn đủ.
- Hai Linux venv đã cài hoàn tất; pip check/freeze đầy đủ. Harness editable
  đúng source pin và clean. Controller pyarrow23.0.1, harness pyarrow26.0.0 là
  hai venv riêng; Docker SDK7.1.0 và ghapi1.1.1 theo constraints đã duyệt.
- **48 Linux tests PASS**, shell syntax/help, official CLI --help và actual
  owned process-tree timeout/cleanup PASS. Synthetic reports không phải gold;
  container cleanup smoke còn NOT_RUN.
- Docker Desktop đã start một lần rồi backend thoát. Log trực tiếp:
  `starting services: initializing Inference manager ... dockerInference ...
  The file cannot be accessed by the system`.
  Daemon không kết nối; Linux docker.sock thiếu. Config vẫn có integration distro.
- Nguyên nhân sâu socket/filesystem chưa được xác định. Không xóa/đổi tên socket,
  reset dữ liệu, sửa registry, restart WSL hoặc đổi RAM/swap để thử mò.
- Giữ hai images chuẩn bị từ trước, chưa inspect lại được khi daemon lỗi.
  Matplotlib/profile/gold chưa chạy; quota vẫn 0/2 campaigns, 0/6 attempts.
- Không còn owned install/QA processes; smoke children đã cleanup.

### Tiếp tục đúng điểm dừng

1. Xử lý riêng startup Docker Desktop trong phạm vi được người dùng cho phép;
   không start lặp unchanged hoặc reset/xóa dữ liệu dùng chung.
2. Khi daemon hoạt động, đo lại gates, kiểm integration, CLI/SDK server ID và
   identities images đã có. Không mặc định cache mất để pull lại.
3. Reuse distro, venvs, clean source pin và Linux QA, không reinstall/reclone.
   Chỉ hoàn tất Matplotlib, container ownership/cleanup, profile và preflight
   rồi ba gold tasks đúng thứ tự theo kế hoạch đã duyệt.

Evidence mới cùng root: resource_resume_02_host.json, resource_after_boot_02.json,
resource_during_install_02.json, resource_after_install_02.json, docker_start_02.json,
docker_server_resume_02.json, desktop_status_02.json, docker_boot_diagnostics_02.json,
integration_config_02.json, install_python_02.json, linux_qa_02.json,
linux_wrapper_02.junit.xml, linux_process_smoke_02/, harness_cli_help_02.json,
runtime_inventory_02.json. Các probes sandbox access denied được giữ, không coi
là lỗi VGAR; probes host đã được cấp quyền là căn cứ đo tài nguyên.

## Bổ sung chẩn đoán — 24/10/2026, chờ duyệt sửa

- [Báo cáo đầy đủ](m1_w9_4_docker_startup_diagnosis_20261024.md) và evidence
  checkpoint_docker_diagnosis_03.json: hai Docker sockets có AF_UNIX tag
  0x80000023 nhưng native no-follow open lỗi1920; parent thường/ACL full control,
  afunix RUNNING. Native controls C/D PASS và đã dọn, không chạm Docker endpoints.
- Root cause khởi đầu chưa được chứng minh; không quy thành global AF_UNIX,
  thiếu quyền admin, NTFS hỏng hoặc image/VHDX hỏng. VHDX chỉ được đọc metadata.
- A: sau khi được duyệt, quit Docker an toàn, quarantine **chỉ thư mục run**
  bằng rename có thể hoàn tác, thử một start và kiểm daemon/images. Chưa thử.
- B: update chính thức in-place có offline backup và qualification mới nếu A
  fail/tái diễn hoặc người dùng chọn. Không tự update/reset/uninstall.
- Chờ duyệt phương án; không tiếp tục gold, quota không đổi. Resume02 vẫn là
  baseline phần Linux đã xong, không reinstall hoặc rerun các bước đó.


## M1-W9-4 resume sau Quit Docker ? 24/10/2026

- Ng??i d?ng x?c nh?n ?? Quit. Kh?ng c?n Docker processes; runtime run l?
  directory th??ng v? tr?ng. Guard quarantine d?ng v? inventory ?? ??i;
  kh?ng rename/delete runtime ho?c endpoints. M?t l?n start sau Quit ?? ??a
  Linux daemon/WSL integration ho?t ??ng l?i; ch?a k?t lu?n root cause ?? ch?a.
- Resource gates PASS, harness source ??ng pin/clean v? c? hai pip check PASS.
  Kh?ng reinstall/reclone ho?c ch?y l?i Linux48tests ?? c? evidence.
- Blocker m?i: daemon b?o0images/0containers, pinned Astropy tag kh?ng t?n t?i;
  Django cache c?ng kh?ng th?y trong inventory. VHDX metadata hi?n4.934.598.656
  bytes so v?i9.736.028.160bytes tr??c. Ch?a x?c ??nh nguy?n nh?n cache thay ??i;
  kh?ng suy r?ng user x?a d? li?u ho?c store kh?c ch? t? inventory tr?ng.
- CustomWslDistroDir v?nD:\DockerDesktopWSL, UseContainerdSnapshotter=true.
  Kh?ng ??i Docker settings/store/VHDX; kh?ng reset/prune ho?c pull l?i ?? che
  missing cache. Matplotlib/container smoke/profile/gold v?nNOT_RUN.
- Evidence m?i c?ng root local-qualification: quarantine_runtime_05.json
  (guardFAIL, ch?a mutation), runtime_empty_after_quit_05.json, docker_start_05.json,
  docker_server_05.json, linux_probe_05.json, runtime_qualification_05.json,
  runtime_05/ v? cache_inventory_05.json. Checkpoint hi?n t?i:
  results/m1/w9/m1-w9-4/20261023-local-qualification/checkpoint_resume_05.json.
- Source/HEAD tr??c/sau runtime gi? nguy?n. Gold0campaign/0attempt, kh?ng pending
  commands. M1-W9-4 v?nBLOCKED_IMAGE_CACHE_IDENTITY; ch? user x?c nh?n thao t?c
  images/reset/store ho?c h??ng chu?n b? l?i cache. Kh?ng W9-5/commit/push/TaskStatus.


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
