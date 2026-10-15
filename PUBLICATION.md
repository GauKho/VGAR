# Bản bàn giao Git — M2 tuần 7–8

Ngày chuẩn bị: 15/10/2026. Nhánh: `feat/m2-w7-w8-v11-r002-20261015`.
Đích: https://github.com/GauKho/VGAR.git

## Phạm vi

Nhánh độc lập này chứa **nội dung M2_week_7_8 ở root**, không phải toàn bộ
VGAR main và không gộp/thay thế main. Bản chuẩn bị Git tách biệt với thư mục
M2 local đang chạy; các source bytes được đối chiếu SHA256 khi sao chép.

Đưa lên: source/scripts/tests/config/prompts, prepared examples/handoffs,
ba tài liệu chính và guides/checkpoints, qualification/provenance/history,
final A/B/C và manual run `20261015T114826234Z-922d5c80`, cùng test evidence
trước push. Không chỉ copy source rồi bỏ những results mà runner dùng để
đối chiếu r002.

Không đưa lên: `.venv`, model weights, caches/bytecode/egg-info, private
workspaces, pytest scratch `temp`/`runtime_tmp`, `.env`, owner locks, file
atomic-write tạm hoặc nested Git metadata. Không xóa những dữ liệu local đó.

Root `.gitattributes` là metadata đóng gói thêm để giữ EOL/bytes đúng hashes,
không đổi parser/verifier/prompt/source. `PUBLICATION.md` là ghi chú bàn giao.
Inventory trong File02 là snapshot local theo mốc đã ghi, không danh sách
mọi file bắt buộc đưa lên Git và không tự cập nhật sau mỗi run.

## Clone đúng thư mục

Ví dụ clone nhánh này vào thư mục M2 riêng, **không ghi đè VGAR của M1**:

```powershell
git clone --single-branch --branch feat/m2-w7-w8-v11-r002-20261015 https://github.com/GauKho/VGAR.git M2_week_7_8
```

Đọc README và requirement.txt sau clone. Cần sibling VGAR đúng source pin,
tokenizer assets, model snapshot, Git/driver và hai Python environments.
Clone không tự cung cấp những tài nguyên này; không sửa frozen hashes/old
records để bỏ checks khi chuyển máy hoặc đổi paths.

## Evidence và Git ignore

Các files evidence được chọn đã được stage tường minh mặc dù `.gitignore`
giữ `results/` để tránh commit nhầm logs/temp của những lượt tương lai.
Files đã tracked vẫn được Git theo dõi. Khi bàn giao run mới, review đúng
paths cần thêm; không force-add toàn bộ temp/weights/venv.

Fresh pre-push core suite:234PASS131.47s, RuffPASS. Đây không phải generation
mới: real3PASS V11/r002 đã có trong final và manual user run được lưu.
Đọc baseline FAIL là trước sửa; post/final PASS là kết quả sau sửa.

Không tạo Pull Request hoặc merge main trong lần bàn giao này. Lịch sử
commit và remote branch là nguồn xác định trạng thái xuất bản thực tế.
