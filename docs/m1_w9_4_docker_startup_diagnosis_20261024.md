# Chẩn đoán Docker Desktop startup — 24/10/2026

## 1. Kết luận và mức độ chắc chắn

**Đã xác định bước trực tiếp chặn khởi động:** Docker Desktop 4.48.0.207573
không xử lý được endpoint `dockerInference` đang tồn tại trong thư mục runtime;
Inference manager lỗi, backend thoát, nên Linux engine API không xuất hiện.

Endpoint đó và `userAnalyticsOtlpHttp.sock` cùng có tag native **0x80000023
(IO_REPARSE_TAG_AF_UNIX)**, zero-byte, attributes 0x420. Đây là endpoint IPC,
không phải image/volume database. Microsoft định nghĩa tag này là UNIX-domain
socket [1]; không suy loại đối tượng chỉ từ tên file hoặc thuộc tính ReparsePoint.

**Chưa chứng minh được nguyên nhân sâu** khiến các endpoint cũ bị inaccessible:
không khẳng định NTFS hỏng, ACL sai, kernel giữ handle, antivirus hoặc Docker
bug cụ thể nếu chưa có bằng chứng. Việc driver chạy và controls PASS chỉ loại
trừ giả thuyết Windows hoàn toàn không hỗ trợ/tạo được AF_UNIX trong phép thử này.

M1-W9-4 vẫn **BLOCKED**, chưa chấm gold; chẩn đoán không phải repair hoàn tất.

## 2. Bằng chứng trên máy

Root evidence: `results/m1/w9/m1-w9-4/20261023-local-qualification/`.
Mỗi command có argv, UTC start/end, duration, exit code, raw/decoded streams.

| Kiểm tra | Kết quả | Evidence |
|---|---|---|
| Metadata thư mục run | Directory thông thường, không phải junction/reparse; chỉ thấy hai endpoints nêu trên | docker_socket_readonly_03.json |
| Native FindFirstFileW | Cả hai endpoints: tag 0x80000023, size 0, attributes 0x420 | docker_native_readonly_03.json |
| Native CreateFileW no-follow, desired access 0, share read/write/delete | Cả hai vẫn lỗi 1920 | docker_native_readonly_03.json |
| fsutil query | Cả hai lỗi 1920; không dùng lệnh delete | docker_reparse_readonly_03.json; docker_sibling_reparse_03.json |
| Parent ACL native | Tài khoản TMT\\pc, SYSTEM, Administrators có Full Control | docker_parent_acl_readonly_03.json |
| ACL endpoint | icacls /L lỗi 1920 trước khi đọc được ACL; không kết luận endpoint ACL hợp lệ hoặc sai | docker_acl_readonly_03.json |
| Driver afunix | RUNNING; SYSTEM_START | afunix_driver_state_03.json; afunix_driver_config_03.json |
| Control native Winsock trên D | Create/bind/listen/closesocket/cleanup PASS, thư mục test đã dọn | winsock_control_probe_04.json |
| Control native Winsock trên C, cùng volume với endpoint Docker | Cùng lifecycle PASS, ngoài Docker và đã dọn | winsock_c_control_probe_05.json |
| Docker integration | Config vẫn chứa VGAR-Harness-W9; không tự đổi settings | docker_socket_readonly_03.json |
| Docker persistent data metadata | VHDX được thấy ở D:/DockerDesktopWSL/disk/docker_data.vhdx, size 9.736.028.160 bytes; VHD distro ở main/ext4.vhdx | docker_data_metadata_03.json |

File command metadata VHDX kết thúc exit 1 vì câu Get-Process cuối không tìm thấy
backend; phần liệt kê VHDX đã trả dữ liệu. Không diễn giải exit đó thành VHDX hỏng.
Chỉ đọc metadata VHDX, **không hash toàn disk, mount, copy, compact hoặc sửa nó**;
chưa inspect được image contents khi daemon vắng mặt.

### Giới hạn của các probes

- Get-Acl PowerShell không load được Microsoft.PowerShell.Security: lỗi công cụ
  này không chứng minh ACL Docker sai; đã dùng icacls native thay thế.
- Probe CPython socket.AF_UNIX không chạy được vì Windows CPython environment
  này không expose hằng AF_UNIX. Không coi đó là Windows thiếu hỗ trợ. Hai probes
  sau dùng trực tiếp Winsock API theo giao diện Windows [2] và đã PASS.
- Không tạo control trong Docker/run; không thử remove/rename các endpoints cũ.
- Không stop/start thêm Docker, reboot, sửa driver/ACL/registry, upload log hoặc
  diagnostics ra ngoài. Logs cũ đã có được dùng để đối chiếu causal chain.

## 3. Đối chiếu upstream

Issue **docker/desktop-feedback #625** có cùng lỗi startup/endpoint/error 1920.
Một số người báo cách ly thư mục runtime giúp vượt bước đầu nhưng lỗi có thể
tái diễn. Maintainer cho biết đã phát hành sửa liên quan trong 4.92; đây không
phải bảo đảm máy này sẽ hết lỗi sau một thao tác hoặc một bản update [3].

Vì vậy không khuyến nghị chỉnh EnableInference=false như một giải pháp chắc chắn,
không tiếp tục thử force-delete endpoint đã không mở được bằng API native.

## 4. Đề xuất sửa hẹp — CHƯA THỰC HIỆN

### Phương án A: cách ly duy nhất runtime directory, có rollback

Mục đích: kiểm tra liệu Docker tạo lại endpoints mới có khởi động được hay không.
Đây là workaround có giới hạn, không tuyên bố chữa nguyên nhân sâu.

1. Xin người dùng duyệt thao tác. Thoát Docker Desktop theo cách bình thường;
   kiểm không còn backend/GUI/build processes liên quan trước thay filesystem.
   Không tự force-kill process hoặc shutdown toàn bộ WSL. Nếu không thoát an toàn
   thì dừng; không đoán không có workload chỉ vì API không truy cập được.
2. Recheck absolute path, loại Directory thường và inventory. Chỉ target:
   `C:/Users/pc/AppData/Local/Docker/run`.
   Nếu path thành junction, xuất hiện nội dung khác hoặc process quay lại thì dừng.
3. Đổi tên nguyên thư mục trong cùng parent thành tên quarantine duy nhất có
   timestamp, ví dụ `run.quarantine-<timestamp>`. Không xóa/traverse endpoint,
   không overwrite destination. **Chưa biết rename parent có thành công trên máy
   này hay không**; lỗi thì ghi log và dừng, không lặp bằng nhiều cách xóa.
4. Tạo `run` mới trống nếu Docker không tự tạo; giữ kế thừa ACL, không cấp quyền
   rộng hơn. Start Docker một lượt sau thay đổi có căn cứ; lưu startup logs mới.
5. Kiểm daemon Linux hoạt động và integration, server ID, hai image digests/IDs
   đã pin. Không tự pull lại để che việc cache mất; không xóa quarantine.
6. Nếu cùng lỗi tái diễn hoặc chuyển sang endpoint khác: dừng, giữ evidence.
   Không cách ly tiếp nhiều thư mục theo đuổi một chuỗi lỗi chưa hiểu.

**Không đụng:** D:/DockerDesktopWSL, mọi VHDX, Docker settings/credentials,
volumes/images, source VGAR, venv/harness pins; không uninstall/reset/prune.
Thao tác vẫn có ảnh hưởng tới IPC/runtime Docker và cần duyệt trước, không phải
không có rủi ro chỉ vì endpoints có size 0.

**Rollback:** khi Docker đã dừng an toàn, đổi tên `run` mới sang một tên lưu thử
khác (không xóa), rồi đổi quarantine gốc về `run`, với guard không overwrite.
Rollback khôi phục layout cũ, có thể khôi phục cả lỗi cũ; không hứa endpoint
runtime còn giá trị sau một phiên khác. Không chạy rollback khi process còn sống.

### Phương án B: vendor in-place update, chỉ khi A thất bại/tái diễn hoặc người dùng chọn

- Chọn bản chính thức còn hỗ trợ có sửa liên quan, ít nhất qua mốc 4.92; xác minh
  installer/signature/checksum và release notes tại thời điểm thực hiện, không
  tự tải/cài trong lượt chẩn đoán này.
- Trước upgrade, cần backup offline VHDX tại **vị trí tùy chỉnh đang dùng trên D**
  và cấu hình cần thiết; Docker yêu cầu Desktop dừng hoàn toàn khi backup disk [4].
- Đây là thay đổi rộng hơn A (engine/CLI có thể đổi); phải xin duyệt và kiểm lại
  server/image identities, SDK compatibility, readiness trước tiếp tục harness.
- Không uninstall để upgrade, không Factory Reset/Clean/Purge, không unregister
  distro. Nếu installer không hỗ trợ an toàn thì dừng thay vì tự chuyển sang uninstall.
- Có backup không bảo đảm downgrade ngược sau data migration an toàn; cần kế
  hoạch restore riêng trước upgrade, không gọi binary downgrade là rollback đủ.

## 5. Tiêu chí chấp nhận trước tiếp tục M1-W9-4

- Docker daemon/API hoạt động; endpoint không tái lỗi ở lần start có kiểm soát.
- Integration VGAR-Harness-W9 và CLI/SDK cùng server; cache hai images đúng pins.
- Windows/Linux RAM và C/D reserve đạt gates; không tăng quota hoặc timeout.
- Chưa gọi repaired nếu chỉ có GUI lên hoặc exit 0 của lệnh start.
- Sau readiness mới tiếp tục Matplotlib/container smoke/profile/preflight/gold;
  không reinstall Linux venvs hoặc chạy lại các bước offline đã xong.

## 6. Điểm dừng

Chẩn đoán đã xong trong phạm vi được giao; **chưa sửa môi trường Docker**.
Đề xuất thử **A một lần** để can thiệp tối thiểu/có thể hoàn tác. Nếu ưu tiên
hướng vendor thay workaround, người dùng có thể chọn B với backup và qualification.
M1-W9-4 giữ BLOCKED; campaigns/real attempts vẫn 0/0. Không commit/push hoặc
sửa Task Status.md. Chờ người dùng duyệt phương án trước mọi mutation Docker.

## References — nội dung đã kiểm ngày 24/10/2026

1. [Microsoft — Reparse tags](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/c8e77b37-3909-4fe6-a4ea-2b9d423b1ee4): định danh AF_UNIX 0x80000023, không chứng minh endpoint hợp lệ.
2. [Microsoft — AF_UNIX comes to Windows](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/): native Winsock AF_UNIX/SOCK_STREAM và sockaddr_un.
3. [Docker official issue tracker — #625](https://github.com/docker/desktop-feedback/issues/625): báo cáo từ người dùng và phản hồi maintainer; không phải cam kết support cho workaround.
4. [Docker Docs — Backup and restore](https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/): bảo vệ dữ liệu và backup disk khi Desktop dừng; dùng custom path nếu đã đổi vị trí disk.
