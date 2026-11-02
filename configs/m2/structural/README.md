# Structural policy W11

`example.yaml` chỉ là fixture cho `demo/structural`, không phải rule tự suy ra cho
VGAR hoặc 25 repo dev. Repo thật cần người hiểu kiến trúc cung cấp config phù hợp.
`schema.json` mô tả JSON shape; runtime còn kiểm Python module identifiers,
references giữa các layer, repo identity và prefix không bị khai báo trùng.

- `repo_key`: phải khớp cả hai graph.
- `forbidden_imports`: danh sách `{source, target}`. Prefix `a` khớp `a`/`a.child`,
  không khớp `abc`. Không dùng glob, regex, biểu thức hoặc code.
- `layers`: `tên layer -> danh sách module prefix`. Prefix dài nhất thắng nếu
  các namespace lồng nhau; cùng một prefix không được thuộc hai layer.
- `allowed_layer_imports`: phải có đúng tập tên layer đã khai báo. Mỗi giá trị là
  các layer đích được phép, kể cả self-layer nếu muốn cho phép. Không có quyền ẩn.
- Hai field layer phải xuất hiện cùng nhau. Module ngoài các prefix được khai
  báo nằm ngoài policy scope, được đếm/ghi diagnostic, không bị gán layer đoán.

Forbidden rules kiểm lexical import target, gồm thư viện ngoài và `from pkg
import sub` qua cả `pkg` và `pkg.sub`. Đây không phải suy ra dependency graph mới.
Cycle/layer dùng cạnh graph đã resolve nội bộ, đủ confidence. Mọi rule chỉ FAIL
cho vi phạm mới so với baseline; không coi violation đã có sẵn là lỗi patch mới.

Không có config: cycle rule vẫn chạy; forbidden/layer là `NOT_RUN`. Đây là quyết
định người dùng đã chốt khi duyệt plan M2 W11–W12. `forbidden_imports: []` là policy
rỗng tường minh và có thể PASS với zero violation, khác field chưa cấu hình.

`load_structural_config(path)` đọc UTF-8 bằng `yaml.safe_load`, từ chối duplicate
keys, aliases và unsafe tags. Thiếu file/không có path trả `None`; file hỏng raise
`ValueError`. Không tự đọc config từ repository đích hoặc chọn một policy mặc định.
Environment hiện tại có PyYAML 6.0.3; task không cài thêm package hoặc sửa dependency
manifest do M3 sở hữu. M3 cần giữ dependency loader này trong môi trường tích hợp.

API/checker và hướng dẫn test: `docs/m2_w11_2_structural_check.md`.
