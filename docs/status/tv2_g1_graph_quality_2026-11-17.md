# TV2 · G1 Graph quality: kết quả (viết 17/11/2026, số sinh 16/11/2026)

> Plan 2 tuần, tuần 2 ngày 2 (G1). Proposal §13.2 "Graph quality" (dòng 1341–1347).
> Spec gán nhãn: `docs/superpowers/specs/2026-11-16-g1-labelled-edges-design.md`; spec chốt: `docs/superpowers/specs/2026-11-17-tv2-g1-embedding-r1-heldout-design.md` §1.
> Số gốc: `~/rt1/g1/report/g1_report.json` (WSL), sinh 16/11/2026 13:10.

## Ai gán nhãn

- 300 mục (150 lời gọi, 150 tên dùng; 12 repo dev, một task mỗi repo) là **nhãn do Claude gán**, chỉ nhìn code và danh sách ứng viên cùng tên, trước khi build graph. Không phải "gán nhãn tay".
- 30 mục được gán lần hai bởi **một lượt Claude khác**, theo yêu cầu của người dùng (16/11). Độ khớp raw 0,967, kappa 1,000 (n = 30), một mục lệch (C017) do người dùng chốt. Hai số khác nhau vì cách tính khác nhau (`g1_labels.agreement`): kappa chỉ so **loại nhãn**, còn độ khớp raw so cả loại nhãn lẫn **tập đích** trong repo. C017 cùng loại nhãn ở cả hai lượt, chỉ khác đích, nên raw là 29/30 mà kappa vẫn là 1,000. Đây là **độ nhất quán của Claude**, không phải độ khớp với người.
- Lượt người: xem mục "Độ khớp với người" (Task 2 của plan 17/11).

## Năm metric của proposal

| Metric ([P] dòng 1341–1347) | Kết quả | Nguồn |
|---|---|---|
| Call edge precision/recall | Bảng dưới | G1 (150 lời gọi) |
| Symbol resolution precision/recall | Bảng dưới (tên dùng: biến toàn cục, field, tên đọc trong thân hàm) | G1 (150 tên dùng) |
| Trace link precision/recall | top-1: P 0,70 / R 0,50; ngưỡng ≥ 0,7: P 0,45 / R 0,58 (31 task dev; gold xấp xỉ bằng file của patch gold) | `tv2_tr_1_trace_links_run_2026-11-10.md` |
| Incremental update correctness | 12/12 kịch bản: graph sau cập nhật giống hệt graph build lại | `tv2_u1_incremental_2026-11-11.md` |
| Component boundary quality | Chưa đo; cần nhãn kiến trúc của người (plan O7) | Task 3 của plan 17/11 |

### Call edge (n = 150; CI95 bootstrap)

| Graph | `CALLS` P | `CALLS` R | `CALLS + MAY_CALL` P | `CALLS + MAY_CALL` R |
|---|---|---|---|---|
| static (cấu hình phục vụ mặc định) | 1,000 [1,000; 1,000] | 0,418 [0,315; 0,529] (tp 46, fn 64) | 0,486 [0,387; 0,610] | 0,609 [0,489; 0,732] (tp 67, fp 71, fn 43) |
| tsg | 1,000 [1,000; 1,000] | 0,418 [0,315; 0,529] | 0,486 [0,387; 0,610] | 0,609 [0,489; 0,732] |
| tsg + JARVIS | 1,000 [1,000; 1,000] | 0,527 [0,411; 0,649] (tp 58, fn 52) | 0,526 [0,423; 0,656] | 0,645 [0,524; 0,766] (tp 71, fp 64, fn 39) |

Trạng thái từng lời gọi (static): 94 đúng, 1 đúng một phần, 37 không có cạnh, 18 không có CallSite tương ứng; 0 cạnh nối nhầm tới thư viện ngoài hay builtin.

### Symbol resolution (tên dùng; cần tree-sitter-graph)

| Phạm vi | P | R |
|---|---|---|
| Mọi tên dùng (n = 150) | 0,978 [0,927; 1,000] | 0,333 [0,248; 0,419] (tp 45, fp 1, fn 90) |
| Trong thân hàm (n = 141) | 0,978 [0,931; 1,000] | 0,349 [0,263; 0,435] |
| Biểu diễn được (biến toàn cục và field, n = 84) | 1,000 [1,000; 1,000] | 0,469 [0,359; 0,588] |

Graph static không có cạnh đọc tên (`REFERENCES` từ tree-sitter-graph), nên ô này không áp dụng cho static. JARVIS không đổi số tên dùng.

## Đối chiếu §8.3 (hai điều kiện về cạnh)

[P] dòng 835–841 yêu cầu "graph edge recall đủ cao" và "graph edge precision không quá thấp", **không đặt ngưỡng**. Báo cáo này không đặt ngưỡng mới; nhóm kết luận từ số:

| Điều kiện | Cấu hình phục vụ (static) | Có `MAY_CALL` |
|---|---|---|
| Edge recall | 0,418 | 0,609 |
| Edge precision | 1,000 | 0,486 |

Đánh đổi thấy rõ: chỉ cạnh chắc chắn thì precision tuyệt đối nhưng bỏ sót hơn nửa lời gọi; thêm `MAY_CALL` lấy thêm 21 lời gọi đúng nhưng kèm 71 cạnh sai.

## Giới hạn

- Lỗi đã biết của bộ công cụ gán nhãn: tham số lambda không bị loại (N023, N075 gán `unknown`); `examples/` của matplotlib bị tính là code sản phẩm; bí danh module (`capi`, `connect`, `models`, `u`, `mcolors`, `_pytest.config`) gán `unknown`.
- JARVIS lỗi ở một số task (`AttributeError ... get_ns`, timeout 120 s, xem `~/rt1/g1/eval.log`).
- Cánh `scip_tsg` không chạy (D1-3: SCIP không phải cấu hình phục vụ, R1 không dùng).
- Một task mỗi repo, 150 mục mỗi loại: CI rộng (recall ±0,1).

## Độ khớp với người

Chưa có (đang chờ chấm `agreement_human.csv`, Task 2).

_Ngày 17/11 đã đối chiếu từng số với `g1_report.json` sinh ngày 16/11/2026 13:10._
