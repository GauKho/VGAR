# Review kỹ thuật độc lập — M2-W9-4

Ngày ghi nhận: 23/10/2026. Phạm vi: experiment, context adapter, session/pipeline,
MCP repair server và các tests mới. Đây là review kỹ thuật của agent đọc độc lập,
**không phải phê duyệt của M3** hoặc kiểm thử runner M3.

## Findings và xử lý

| Mức | Finding | Bản sửa tối thiểu | Evidence |
|---|---|---|---|
| Important | Xóa `experiment` ở cả session và canonical record có thể làm reload rơi về legacy | Ghi marker `experiment_required=true` ở hai phía ngay từ start; nếu marker còn mà profile mất thì từ chối trước `load_run` ghi dữ liệu | `review_missing_red.json`: 1 FAIL tái hiện; `review_green.json`: PASS |
| Important | Baseline chỉ kiểm hash nếu session có; mất hash session hoặc sửa/mất hash canonical chưa bị chặn | Khi baseline PASS, bắt buộc cả hai bản có status PASS và cùng policy hash hiệu lực; hash sai luôn bị từ chối | `review_baseline_red.json`: 4 FAIL tái hiện; `review_green.json`: PASS |

`review_green.json`: **6 PASS, 19 deselected**, bao gồm năm trường hợp tamper
và một trường hợp baseline ERROR sớm chưa có hash vẫn load được. Đây là focused
check, không thay thế full W7–8/W9. Các tests kiểm bytes trước/sau để chứng minh
reload bị từ chối trước thao tác ghi; lease dùng trong test được chính owner dọn.

Marker không phải chữ ký. Nếu bên ngoài chủ động viết lại mọi dấu vết và hashes
thì không có xác thực mật mã để chứng minh lịch sử; task chỉ kiểm consistency.
Record legacy thực sự không có experiment/marker vẫn đi nhánh cũ.

## Phần không tự mở rộng

- Arm do caller khai từ handoff/index; consumer không chứng minh thuật toán retrieval.
- Không thay admission, registry, public DTO, parser/apply guards, prompt hoặc model.
- Không review thay các thay đổi M1/M2 khác đã có trước phiên này.
- Pilot, qualification model, environment SWE-bench và runner M3 không được ghi PASS.

Một lượt sửa findings đã được thực hiện; kết quả các gate sau sửa và preservation
nằm trong [báo cáo W9-4](../m2_w9_4_variant_provenance.md), không suy từ review này.
Evidence root: `results/m2/w9/m2-w9-4/20261023-implementation/`.
