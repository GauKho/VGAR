# Snapshot xuất bản VGAR — 16/10/2026

Nhánh dự kiến: `feat/vgar-integrated-m2-w7-w8-20261016`, remote
`https://github.com/GauKho/VGAR.git`. Không cập nhật/force-push `main`.

## Nội dung snapshot

- Toàn bộ source VGAR hiện có, diff M2 W5–6, package M2 W7–8 (source,
  prompts, config, fixtures, tests, scripts, original bytes/relocation receipt).
- README/requirement root, Task Status, PROGRESS, tài liệu bàn giao/thiết kế và
  audit không bị Git ignore.
- Chọn thêm evidence bị ignore: final real A/B/C V11/r002, manual A/B/C Run
  của người dùng (không thư mục temp), full M2 core qualification, manifest
  runtime r002/frozen B và summary/report ba retrieval runs W5–6 đã nghiệm thu.

## Không có trong snapshot

- Môi trường ảo, `__pycache__`, Node runtime, downloaded tokenizer assets,
  model weights, dataset/source archives, temporary workspaces và secrets.
- Raw retrieval task artifacts lớn (BM25 run gồm khoảng756MB). Có summary và
  REPORT, nhưng audit lại mọi raw artifact cần bàn giao cache/evidence riêng.
- Toàn bộ các campaign/results phát triển khác không tự được force-add.
  Những file này vẫn giữ nguyên ở máy local, không bị xóa.

Vì vậy bản clone có code/test/docs và các evidence được chọn, không đồng nghĩa
đã có toàn bộ tài nguyên local hoặc clean-install qualification. Xem README.

## Source pin và checkout đang test

Git local bật `core.autocrlf=true`. `.gitattributes` mới giữ nguyên bytes cho
package M2, shared boundary12files và các evidence được chọn, tránh clone đổi
LF/CRLF làm sai hash. Một số shared files trong commit có delta line endings
so với HEAD cũ vì lưu đúng approved Windows bytes; không sửa source local.
Whitespace có sẵn ở fixture/diff/log được bảo toàn, không normalize để PASS.

M2 hiện khóa reference HEAD `b8e2461635b81d1ae790445efea5c9757d91700a` và12
shared boundary hashes. Tạo bất kỳ commit mới nào cũng thay HEAD ở checkout
nhánh mới. Không sửa/bỏ guard hoặc viết lại frozen hashes chỉ để push.

Commit snapshot được tạo bằng Git index riêng và nhánh xuất bản riêng; HEAD,
branch, index và working-tree bytes của checkout hiện dùng test được giữ.
Local vẫn có thể hiển thị các changes vì nó không checkout commit xuất bản.

**Máy đồng đội clone nhánh mới cần qualification/profile relocation được review
trước khi chạy final M2.** Chỉ `pip install` hoặc copy venv không đủ. Historical
records giữ absolute paths/hashes cũ để truy vết, không sửa hồi tố thành paths
máy mới. Không tuyên bố snapshot này đã giải quyết portability hoặc nối MCP.

## Kết quả và kiểm chứng

Kết quả toàn hệ thống đã lưu: M2 core236PASS; VGAR571PASS/1FAIL/2SKIP;
historical real A/B/C3PASS V11/r002. Failure HF legacy còn nguyên.

Trước xuất bản chạy lại QA README/requirements và focused regression của
compare/scoring + integration/preservation. Console/JUnit/kiểm tra staged
snapshot ở `docs/audit/2026-10-16-publish-vgar/`. Không chạy lại generation,
benchmark, không cài lại dependencies. Trạng thái push thực tế phải đối chiếu
commit với remote branch sau lệnh push; không suy thành công từ tên nhánh.

Fresh checks:31/31tests PASS9,69s; README18tables/71local-links/15PowerShell
blocks hợp lệ. Profile Check sau staging PASS4,221s, CUDA True; đây là probe
prerequisite, không phải generation mới. Snapshot index được so raw bytes với
426package/evidence files và12shared hashes; pattern scan không tìm credential
mẫu phổ biến. Pattern scan không phải bảo đảm tuyệt đối không có mọi secrets.
