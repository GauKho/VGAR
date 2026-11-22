# Bảng đáp án ShopFlow (để chấm agent — không dán vào prompt)

Repo: `D:\kltn\shopflow-buggy-no-tests\shopflow-buggy-no-tests` (commit `fb79b86`). Đọc toàn bộ code ngày 22/11/2026.
13 dòng = 16 chỗ sai (dòng 1, 2, 4 có hai chỗ). Lỗi 1–5 đi qua nhiều file.

| # | Chỗ sai | File |
|---|---|---|
| 1a | `coupon_rate` trả phần trăm (10) thay vì tỉ lệ (0.10); `config.COUPONS` lưu phần trăm | `services/discount.py` (+ `config.py`) |
| 1b | `place_order` chỉ nhả giữ chỗ khi `OutOfStockError`; README: mọi lỗi phải nhả | `services/order_service.py` |
| 2a | `quote_order` gọi `shipping_fee(weight, value)`, đảo thứ tự so với chữ ký `shipping_fee(order_value, weight_kg)` | `services/pricing.py` (+ `services/shipping.py`) |
| 2b | Thuế tính trên `discounted + shipping` | `services/pricing.py` |
| 3 | `Order.__init__(lines=[])`: danh sách mặc định dùng chung giữa mọi đơn trong tiến trình | `models/order.py` |
| 4a | `order_shipped` dùng `customer.email_address` (không tồn tại) → giao hàng lỗi sau khi đã đổi trạng thái, trừ kho | `services/notifications.py` (+ `models/customer.py`) |
| 4b | `commit` trừ `stock` nhưng không trừ `reserved` | `services/inventory.py` |
| 5 | `ALLOWED_TRANSITIONS` cho phép shipped → cancelled; `cancel_order` nhả kho | `models/order.py` (+ `services/order_service.py`) |
| 6 | `reserve` so với `stock` thay vì `available` | `services/inventory.py` |
| 7 | `is_business_day` dùng `<= 5` (tính cả thứ 7) | `utils/dates.py` |
| 8 | `to_money` làm tròn qua `float`, không dùng `ROUND_HALF_UP` | `utils/money.py` |
| 9 | `average_order_value` chia cho `len(orders)` thay vì số đơn có doanh thu | `services/reporting.py` |
| 10 | `paginate` cắt `start:start + page_size - 1` | `repositories/base.py` |
| 11 | GET `/products/<sku>` dùng `products.get` (None) thay vì `require` → 500 | `api/handlers.py` |
| 12 | `find_low_stock` dùng `<` thay vì `<=` (trái docstring) | `repositories/product_repo.py` |
| 13 | `find_by_email` không lowercase đầu vào (docstring: email lưu chữ thường) | `repositories/customer_repo.py` |

## Ghi chú khi chấm

- Sửa 1b đúng nghĩa là nhả giữ chỗ với **mọi** exception (ví dụ SKU không tồn tại ở dòng thứ hai → `NotFoundError`).
  Lượt `ses_e009bef39ffeXxSzCK452yqpSW` chỉ bắt thêm `ValidationError` — chưa đủ (đã chạy thử: còn giữ 1).
- Lỗi 3 làm nhiễu mọi lần tái hiện chạy chung một tiến trình Python.
- Lượt `ses_e009bef39ffeXxSzCK452yqpSW` (9Router `my-combo`): bước rà lỗi tìm đúng 12/16 chỗ (đủ 9/13 dòng); bỏ sót 6,
  12, 13 (không đọc `product_repo.py`, `customer_repo.py`); 11 nằm ngoài phạm vi prompt; 1 dòng gắn nhãn sai (hệ quả của
  8) và 3 dòng lặp.
