# TV2 · Đợt 4 phần B: grounding theo §6.6/§15, đo trước và sau (23/11/2026)

Spec: `docs/superpowers/specs/2026-11-23-tv2-agent-loop-fixes-design.md` §4.5. Plan:
`docs/superpowers/plans/2026-11-23-tv2-agent-loop-fixes.md` Task 6–11. Code "Trước" = commit `a2980ea3` (phần A).

## Bốn luật

- **G1 `name_part`**: từ trong đề bài khớp phần của tên ghép (`coupon` → `coupon_rate`, `cancelled` → `cancel_order`). Chỉ
  tên có từ 2 phần; phần hiếm (≤ 3 symbol) phải được nhắc; độ phủ IDF > 0,5; điểm 0,3 + 0,2 × độ phủ; tối đa 5; bỏ đoạn
  mà luật khác đã xét (đường dẫn, route, traceback).
- **G2**: từ viết hoa chữ đầu, đứng đầu câu ("Customer C003 …") là chữ thường của câu: 0,4 thay vì 0,6.
- **G3 `quoted_message`**: cụm trong ngoặc kép (≥ 2 từ, ngoài backtick) khớp mảnh thông báo trong code (≥ 4 từ, bỏ dấu câu
  hai đầu): 0,85 nếu một hàm khớp, 0,5 nếu dùng chung. Retrieval cũng dùng cụm trích làm tín hiệu thông báo.
- **G4 `text_match`**: không còn anchor nào → tối đa 3 hàm có `SourceEvidence.similarity` ≥ 0,1 với đề bài, điểm 0,2.
  `SourceEvidence` chỉ đếm thuộc tính, chuỗi ngắn và tên tự do, không đếm tham số và biến cục bộ.

Hằng số chốt trong plan trước khi đo; hai điều chỉnh trước khi chạy R1 sau (ledger): G1 chỉ cho tên ≥ 2 phần và độ phủ
phải > 0,5 (không phải ≥), để giữ các test chính xác có sẵn (`login fails`, `unknown.login`, traceback hỏng, route hỏng).

## Thăm dò ShopFlow (20 ca: 14 dòng lỗi + 6 quy tắc, tiếng Anh; top 5 anchor)

`python scripts/probe_task_anchors.py <shopflow> repair_agent/shopflow_grounding_cases.json --out …`. "File" = có anchor
trong file lỗi; "Hàm" = có anchor là hàm lỗi (`bugs.json`); "—" = lỗi nằm ở hằng (không phải node).

| | Trúng file | Trúng hàm |
|---|---|---|
| Trước (phần A) | 3/20 | 1/17 |
| **Sau (phần B)** | **14/20** | **9/17** |

| Ca | Trước file / hàm | Sau file / hàm | Top 3 anchor sau |
|---|---|---|---|
| row1-B03-B08 | ❌ / ❌ | ✅ / ✅ | combine_rates 0.85 (quoted_message), _create_order 0.50 (name_part), coupon_rate 0.50 (name_part) |
| row2-B16-B11 | ❌ / ❌ | ✅ / ✅ | ship_order 0.50 (name_part), quote_order 0.50 (name_part), shipping_fee 0.50 (name_part) |
| row3-B04 | ✅ / ❌ | ✅ / ❌ | OrderLine 0.50 (name_part), _revenue_orders 0.41 (name_part), subtotal 0.40 (symbol) |
| row4-B09-B17 | ❌ / ❌ | ✅ / ✅ | order_shipped 0.50 (name_part), confirm_order 0.50 (name_part), ship_order 0.50 (name_part) |
| row5-B13 | ❌ / — | ❌ / — | order_cancelled 0.50 (name_part), order_shipped 0.50 (name_part), cancel_order 0.50 (name_part) |
| row6-B06 | ❌ / ❌ | ✅ / ❌ | available 0.20 (text_match), to_dict 0.20 (text_match), commit 0.20 (text_match) |
| row7-B07 | ❌ / ❌ | ✅ / ✅ | build_app 0.75 (name_part/symbol), ship_order 0.50 (name_part), is_business_day 0.43 (name_part) |
| row8-B02 | ❌ / ❌ | ❌ / ❌ | PriceQuote 0.41 (name_part) |
| row9-B10 | ✅ / ✅ | ✅ / ✅ | average_order_value 0.60 (name_part/symbol), confirm_order 0.50 (name_part), _revenue_orders 0.41 (name_part) |
| row10-B01 | ❌ / ❌ | ❌ / ❌ | ProductRepository 0.41 (name_part) |
| row11-B12 | ❌ / ❌ | ❌ / ❌ | validate_sku 0.41 (name_part) |
| row12-B05 | ❌ / ❌ | ✅ / ✅ | available 0.75 (symbol), find_low_stock 0.44 (name_part), ProductRepository 0.41 (name_part) |
| row13-B15 | ❌ / ❌ | ✅ / ✅ | find_by_email 0.44 (name_part), validate_email 0.41 (name_part), CustomerRepository 0.40 (name_part) |
| row14-B14 | ❌ / — | ✅ / — | register_customer 0.50 (name_part), validate_email 0.41 (name_part), CustomerRepository 0.40 (name_part) |
| rule1-money-B02 | ❌ / ❌ | ✅ / ✅ | place_order 0.44 (name_part), to_money 0.41 (name_part) |
| rule2-discount-B03 | ❌ / ❌ | ✅ / ✅ | tier_discount_rate 0.44 (name_part), coupon_rate 0.41 (name_part), percent_of 0.41 (name_part) |
| rule3-shipping-tax-B11-B16 | ❌ / ❌ | ❌ / ❌ | shipping_fee 0.50 (name_part), ship_order 0.44 (name_part) |
| rule4-reservations-B06-B08 | ✅ / ❌ | ✅ / ❌ | release 0.40 (symbol) |
| rule5-status-B13 | ❌ / — | ❌ / — | order_cancelled 0.44 (name_part), order_shipped 0.44 (name_part), cancel_order 0.44 (name_part) |
| rule6-business-days-B07 | ❌ / ❌ | ✅ / ❌ | add_business_days 0.44 (name_part) |

Còn trượt: B02 (dòng 8, giá trị số không có tên), B01 (`paginate`: từ của đề bài chỉ là tham số), B12 (`_dispatch`),
B13 (hằng `ALLOWED_TRANSITIONS` không phải node), quy tắc 3 (`quote_order` không vào top 5). Một số anchor nhiễu do G1
(`_revenue_orders`, `CustomerRepository`, `by_customer`) có điểm 0,40–0,41, thấp hơn anchor đúng.

## R1 dev-50 (cổng D2)

Hai lượt trên cùng máy (WSL), cùng manifest 50 task dev, ngân sách 12.000 token: `r1_b4_base` (code phần A, `a2980ea3`)
và `r1_b4_grounding` (code phần B). Cả hai 50/50 SUCCEEDED. So theo cặp:
`python3 ablation_matrix/compare_runs.py ~/rt1/results r1_b4_base r1_b4_grounding` (CI95 bootstrap; thắng/thua theo task).

Kiểm tra chéo: `bm25`, `grep`, `neighbor`, `no_task_trace`, `ast_no_task_trace`, `arch_no_task_trace` có mọi chênh lệch
bằng 0, nên chỉ grounding thay đổi giữa hai lượt.

| Chỉ số (chênh lệch B − A) | `task_trace` (cấu hình server) | `task_trace_rt1` |
|---|---|---|
| R@5 file | +0,040 [0,000; 0,100] (2/0) | +0,040 [0,000; 0,100] (2/0) |
| R@10 file | +0,045 [0,000; 0,110] (3/0) | +0,040 [0,000; 0,100] (2/0) |
| MRR file | −0,001 [−0,025; 0,027] (5/9) | −0,002 [−0,025; 0,025] (5/9) |
| R@5 hàm | −0,020 [−0,061; 0,000] (0/1) | −0,020 [−0,061; 0,000] (0/1) |
| R@10 hàm | +0,020 [0,000; 0,061] (1/0) | +0,020 [0,000; 0,061] (1/0) |
| MRR hàm | −0,020 [−0,049; 0,001] (5/18) | −0,020 [−0,050; 0,001] (5/17) |
| **Reach hàm** | **+0,082 [0,020; 0,163] (4/0)** | **+0,082 [0,020; 0,163] (4/0)** |
| File gold trong context | +0,025 [0,000; 0,070] | +0,025 [0,000; 0,070] |
| Token context (đóng gói) | +49 [−0; +128] | +48 [−1; +126] |

**Cổng D2: đạt.** Không chỉ số nào có CI95 nằm hẳn dưới 0. Tăng có ý nghĩa: reach hàm +0,082 (thêm hàm gold vào danh
sách ứng viên ở 4 task, không task nào mất). Cần ghi nhận: MRR hàm giảm nhẹ −0,020 với 5 task thắng / 17–18 task thua, CI
chạm 0 ở cận trên (0,001); tức anchor mới đưa thêm hàm gold vào nhưng ở nhiều task đẩy thứ hạng hàm gold xuống một chút
(cùng hướng với lượt SCIP và full layer: thêm ứng viên làm loãng thứ hạng). Đây là ứng viên đầu tiên cho lần chỉnh sau
(ví dụ hạ trọng số anchor `name_part` trong xếp hạng), không chỉnh trong đợt này để giữ hằng số đã chốt.

## Kết luận

- ShopFlow (tiếng Anh): trúng file 3/20 → 14/20, trúng hàm 1/17 → 9/17.
- SWE-bench dev-50: không có giảm có ý nghĩa; reach hàm tăng có ý nghĩa; MRR hàm có xu hướng giảm nhẹ (chưa có ý nghĩa).
- Bước tiếp theo: chạy lại OpenCode A/B (≥ 3 lượt mỗi nhánh, tiếng Anh) với phần A + B.
