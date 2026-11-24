# So sánh A/B: OpenCode có / không có VGAR MCP trên ShopFlow clean (22/11/2026)

Lượt thử đầu tiên có số liệu, mỗi nhánh **1 lượt**. Chưa đủ để kết luận; dùng làm mốc và để chạy lặp.

## Điều kiện

| | Lần A (có VGAR) | Lần B (không VGAR) |
|---|---|---|
| Phiên OpenCode | `ses_dfd43685cffeFV963UwPkyBtdS` (17:12–17:27) | `ses_dfd27b638ffeBCFHSUuuR386e8` (17:41–17:55) |
| Repo / nhánh | `D:\kltn\shopflow-clean\shopflow`, `run-vgar` (commit `b7d9c70`) | cùng repo, `run-nomcp` (chưa commit) |
| Code xuất phát | `77426bb` (17 lỗi B01–B17) | `77426bb` |
| Mô hình | `oc/nemotron-3.5-lightning-free` (9Router)¹ | `oc/nemotron-3.5-lightning-free` |
| VGAR | bật, server ở commit `352ffbef` (đợt 3: kiểm patch không cần diff) | `"disabled": true` cả 3 server, 0 lần gọi |
| Prompt | kịch bản bản 3 (`repair_agent/shopflow_opencode_scenario.md`) | phần "Nhánh đối chứng không có VGAR" cùng file |
| Thứ tự | Bước 1, Bước 2, lỗi 3, 1, 2, 4, 5 | giống A |

¹ Lần gửi đầu ở A bằng `nemotron-3-ultra-550b` không trả về gì; số liệu dưới đây bỏ lượt đó.

## Kết quả

| | Lần A (VGAR) | Lần B (không VGAR) |
|---|---|---|
| **Bước 2: rà lỗi (đúng / 17)** | 5 (B01 B02 B03 B09 B11) | **7** (thêm B07 B08) |
| Lỗi nhiều file tìm được (/15) | 5 | 7 |
| Báo sai / khẳng định sai "không có lỗi" | 1 (mã 409) / 4 (B07 B08 B13 B16) | 0 / 0 |
| File đọc trực tiếp ở Bước 1–2 | 0 (chỉ dùng context của graph) | 30 |
| **Bước 3: sửa đúng hẳn** | B11, B16 (+ B09 vòng qua bằng alias `Customer.email_address`) | **B03, B09, B11, B16, B17** |
| Sửa một phần | B04 (không copy list), B08 (SKU không tồn tại vẫn rò), B17 (nhả ở `ship_order`, `commit` vẫn sai) | B04, B08 (giống A) |
| Chưa sửa | B03 (tái hiện sau sửa vẫn lỗi), B13 | B13 |
| Bộ test ẩn trên repo (gốc 40/105 FAIL) | 26 FAIL | **21 FAIL** |
| Báo kết quả sai | lỗi 4–5: dựng lại graph trước khi kiểm, `analyze` ERROR + `verify` NOT_RUN nhưng báo PASS | lỗi 5 báo ✅ (hiểu ngược đề, A cũng vậy) |
| File nháp để lại trong repo | 0 | 4 |
| Thời gian | 15,5 phút | 14,0 phút |
| Lần gọi tool | **103** (45 VGAR, 10 lần đọc file) | 148 (38 đọc file, 85 shell) |

Bộ test ẩn theo lỗi (pass / số test của lỗi; bị nhiễu bởi các lỗi chưa sửa, ví dụ B11/B16 ở A FAIL vì B03):

| | B03 | B04 | B08 | B09 | B11 | B13 | B16 | B17 |
|---|---|---|---|---|---|---|---|---|
| A | 0/4 | 12/20 | 1/1 | 1/4 | 4/7 | 0/3 | 5/8 | 1/3 |
| B | 4/4 | 15/20 | 1/1 | 1/4 | 7/7 | 0/3 | 8/8 | 2/3 |

Chấm riêng (thay file của agent vào `reference_fixed/`): B không làm hỏng gì thêm (6 FAIL = B13 ×3, copy list B04, B06 ×2 không được giao). B08 kiểm thêm bằng tay (đơn có SKU không tồn tại): cả A và B còn rò 1 — bộ test ẩn không bắt trường hợp này.

## Token (từ log OpenCode, `tokens` của từng tin nhắn; `cost` = 0 vì mô hình miễn phí)

| | Lần A (VGAR) | Lần B (không VGAR) |
|---|---|---|
| Input chưa cache | 897.810 | 5.712.554 |
| Input đọc từ cache | 9.275.904 | 6.500.736 |
| **Tổng token đầu vào (input + cache)** | **10.173.714** | **12.213.290** (+20%) |
| Output | 25.074 | 33.152 |
| Reasoning | 18.314 | 34.033 |
| Lần gọi mô hình | 110 | 133 |

Theo bước (tổng token đầu vào = input + cache):

| Bước | A | B |
|---|---|---|
| Bước 1 hiểu repo | 129.145 | 185.606 |
| Bước 2 rà lỗi | 329.101 | 29.825 |
| Lỗi 3 | 1.013.866 | 2.438.554 |
| Lỗi 1 | 1.363.289 | 1.462.422 |
| Lỗi 2 | 5.873.865 | 4.435.977 |
| Lỗi 4 | 705.023 | 2.838.649 |
| Lỗi 5 | 759.425 | 822.257 |

Số liệu từng lượt gọi mô hình (bước, thời điểm, mô hình, input, cache, output, reasoning, tool đã gọi):
`docs/status/tv2_opencode_ab_tokens_2026-11-22.csv` (A 110 dòng, B 133 dòng). Log gốc (ngoài repo):
`D:\kltn\vgar-work\opencode-logs\runA.json`, `runB.json` (`opencode session export <id>`).

Ghi chú: tỉ lệ cache phụ thuộc nhà cung cấp phía sau 9Router, nên so **tổng token đầu vào**, không so riêng phần "input chưa cache". Lần A tổng thấp hơn khoảng 17% (10,2 so với 12,2 triệu), output và reasoning cũng thấp hơn.

## Nhận định (thận trọng, n = 1)

- A tốn ít công hơn (ít gọi tool, ít token) nhưng kết quả kém hơn. Ở Bước 1–2, agent có VGAR không đọc file, chỉ dựa vào đoạn code graph trả về, rồi khẳng định sai "không có lỗi" ở B07, B08, B13, B16. Với mô hình yếu này, context của graph có vẻ đã **thay** việc đọc code thay vì **bổ sung**.
- Điểm yếu cụ thể ở A: anchor nhiễu (`Customer` cho lỗi 1, 4, 5), dựng lại graph trước khi kiểm (lỗi 4, 5), báo PASS khi tool báo lỗi.
- Hai nhánh đều hiểu ngược lỗi 5: mô tả trong kịch bản bản 3 không nói đó là sai. Đã sửa 22/11 (thêm "shipped là trạng thái cuối…").
- Mốc tổng tiền đúng của đơn coupon (C003, 1 MOU-2001, WELCOME10) khi đã sửa hết lỗi là 29.56.

## Việc tiếp theo

1. Chạy lặp mỗi nhánh thêm 1–2 lượt với kịch bản đã sửa lỗi 5, cùng mô hình, đảo thứ tự (B trước A).
2. Thử cho nhánh VGAR: prompt Bước 2 yêu cầu đọc lại code các hàm graph chỉ ra trước khi kết luận; server cảnh báo khi `build_or_update_graph` được gọi lúc còn thay đổi chưa kiểm.
3. Điền kết quả các lượt lặp vào bảng này (thêm cột).

## Chẩn đoán theo lớp VGAR (từ log lần A, kiểm bằng chạy thử trên graph của `77426bb`)

| Lớp / thành phần | Vấn đề | Bằng chứng | Hệ quả ở lần A |
|---|---|---|---|
| **G_task: grounding** (`graph/grounding.py`, `find_task_anchors`) | Chỉ khớp **nguyên tên** symbol (`_symbols_by_name.get(token)`): "coupon" không khớp `coupon_rate`. Từ viết hoa đầu câu bị coi là code (`code_like = ... any(char.isupper())`) → `Customer` 0,6 | Lần A: anchor `Customer` ở 4/5 lỗi, không lần nào đúng. Chạy thử 5 câu mô tả lỗi tiếng Việt của prompt: 4/5 không có anchor | Context lệch khỏi file lỗi: lỗi 1 không có `discount.py` (B03 không sửa), lỗi 5 không có `models/order.py` (B13 sửa nhầm), lỗi 4 không có `inventory.py` (B17 sửa vòng qua) |
| **`search_symbols`** (`graph/sqlite_store.py`) | Một `LIKE '%<cả truy vấn>%'`: truy vấn nhiều từ không bao giờ khớp; chỉ tìm theo tên, không theo thân hàm | 19/19 truy vấn nhiều từ ở hai phiên `my-combo` ra 0, kể cả `"combine_rates tier_discount_rate coupon_rate"`; lần A: `round`, `quantize` ra 0 | Agent kết luận "không có symbol", bỏ qua quy tắc |
| **L1 builder: hằng số cấp module** (`graph/builder.py`) | Không có node cho hằng số (`ALLOWED_TRANSITIONS`, `EMAIL_RE`, `COUPONS`, `LOW_STOCK_THRESHOLD`) | Loại node của graph ShopFlow: File, Module, Import, Class, Method, Function, CallSite, Component, Port, Connector | B13, B14 (và phần dữ liệu của B03, B05) không thể là anchor hay kết quả tìm kiếm |
| **Version cũ trong cache** (`sqlite_service._document`, `retrieval.py:818`) | Version đã bị prune vẫn được phục vụ từ bộ nhớ; retrieval báo "Source content differs from graph snapshot; rebuild graph" dù graph đã dựng lại — lỗi thật là agent dùng `graph_version` cũ | Lần A: 3 lần `get_related_context` lỗi như vậy (truyền `09e580…` sau khi đã dựng lại) | Agent dựng lại graph thêm 3 lần, rồi ở lỗi 4–5 dựng lại **trước** khi kiểm → `analyze` ERROR, `verify` NOT_RUN, agent báo PASS |
| **Trình tự kiểm** (`build_or_update_graph`) | Không cảnh báo khi còn thay đổi chưa kiểm | Lỗi 4–5 lần A | Mất bước kiểm khi mô hình làm sai thứ tự |

Không phải nguyên nhân: retrieval khi anchor đúng (từ `cancel_order`, context có `Order.transition_to`, `can_transition`, `InvalidTransitionError`); kiểm patch đợt 3 (PASS đúng ở lỗi 3, 1, 2; ERROR/NOT_RUN đúng khi đã dựng lại); `explain_dependency_path` (đúng chiều, `found: true`); dựng graph.

Hành vi agent (không phải code VGAR, nhưng bị các lỗi trên khuếch đại): lần A không đọc file nào ở Bước 1–2, bảng Bước 2 khai đã dùng `find_task_anchors`/`search_symbols` cho cả 6 quy tắc nhưng log chỉ có 2 + 4 lần gọi; báo PASS khi tool báo lỗi.

## Lượt lặp 1: B-en (tiếng Anh, không VGAR), 23/11/2026

Điều kiện: phiên `ses_dfba595caffey06mzR1csvCWLG` (00:42–00:58), nhánh `run-nomcp-en` (commit `af208a4`) từ `77426bb`,
cùng mô hình, VGAR tắt (0 lần gọi), prompt `repair_agent/shopflow_opencode_scenario_en.md` (bản dịch; mô tả lỗi 5 đã sửa).

| | A-vi (VGAR) | B-vi | **B-en** |
|---|---|---|---|
| Bước 2: đúng / 17 | 5 | 7 | 7 (B01 B02 B03 B08 B09 B11 B13) |
| Lỗi nhiều file tìm được / 15 | 5 | 7 | 7 |
| Báo sai / khẳng định sai "không có lỗi" | 1 / 4 | 0 / 0 | 0 / 0 |
| Bước 3: sửa đúng hẳn | B11, B16 (+ B09 vòng qua) | B03, B09, B11, B16, B17 | **B03, B08, B11, B13, B16, B17** |
| Sửa một phần / giấu lỗi | B04, B08, B17 (vòng qua) | B04, B08 | B04; **B09 bị nuốt lỗi** (`try/except AttributeError: pass` quanh `order_shipped`: hết lỗi 500 nhưng không gửi email) |
| Chưa sửa | B03, B13 | B13 | — |
| Bộ test ẩn trên repo (FAIL / 105) | 26 | 21 | **18** |
| File nháp để lại trong repo | 0 | 4 | 15 (đã commit) |
| Thời gian agent làm việc (cộng các bước) | 8,8 phút | 11,3 phút | 7,4 phút |
| Lần gọi tool | 103 (45 VGAR) | 148 | 102 |
| Tổng token đầu vào (input + cache) | 10,17 triệu | 12,21 triệu | **5,18 triệu** |
| Output / reasoning | 25k / 18k | 33k / 34k | 21k / 18k |
| Lần gọi mô hình | 110 | 133 | 86 |

Bộ test ẩn theo lỗi (B-en, toàn repo): B03 4/4, B04 17/20, B08 1/1, B09 3/4, B11 7/7, B13 3/3, B16 8/8, B17 3/3. Chấm riêng
(thay 5 file agent sửa vào `reference_fixed/`): 3 FAIL = B06 ×2 (không được giao) + copy list của B04. B08 kiểm tay với SKU
không tồn tại: nhả về 0 (lần đầu ở nhánh nemotron).

"Thời gian agent làm việc" = cộng thời gian từ lúc gửi prompt tới lúc agent trả lời xong ở từng bước, bỏ khoảng người dùng
chưa gửi prompt tiếp; các con số 15,5 / 14,0 phút ở bảng đầu là tính cả khoảng đó.

Nhận định:
- Cùng nhánh không VGAR, đổi sang tiếng Anh: Bước 2 bằng nhau (7/17, đổi B07 lấy B13); Bước 3 sửa đúng nhiều hơn (B08 đủ,
  B13 đúng) nhưng B09 bị giấu lỗi; token giảm hơn một nửa. B13 đúng có thể nhờ mô tả lỗi 5 đã sửa chứ không phải nhờ tiếng
  Anh — lượt này không tách được hai yếu tố.
- Chênh lệch giữa hai lượt cùng nhánh (B-vi và B-en) cỡ bằng chênh lệch A–B ở lượt tiếng Việt: biến động giữa các lượt lớn,
  cần thêm lượt trước khi kết luận về tác dụng của VGAR.
- Tiếp theo: lượt A-en (có VGAR) theo cùng kịch bản tiếng Anh, để so A-en với B-en.

## Lượt lặp 2: A-en (tiếng Anh, có VGAR), 23/11/2026

Điều kiện: phiên `ses_dfb8e5136ffeO3k6sZALVuDuUL` (01:08–01:21), nhánh `run-vgar-en` từ `77426bb` (lúc chấm chưa commit:
5 file sửa + `test_bug.py` do agent tạo dù prompt cấm), cùng mô hình, 3 server VGAR bật (48 lần gọi VGAR), prompt tiếng Anh
như B-en. Người chạy tự dừng lỗi 4 và lỗi 5 ở lần gửi đầu rồi gửi lại ngay; điểm lỗi 4–5 tính theo code cuối. Ngữ cảnh mô hình
vẫn giữ hai prompt đầu, nên lần gửi lại lỗi 4 làm cả lỗi 4 lẫn lỗi 5 và chỉ báo cáo lỗi 5. Cả hai lượt tiếng Anh đều không gửi
prompt Bước 4–5.

| | A-vi (VGAR) | B-vi | B-en | **A-en (VGAR)** |
|---|---|---|---|---|
| Bước 2: đúng / 17 | 5 | 7 | 7 | **8** (B01 B02 B03 B07 B08 B09 B11 B13) |
| Lỗi nhiều file tìm được / 15 | 5 | 7 | 7 | 8 |
| Báo sai / khẳng định sai "không có lỗi" | 1 / 4 | 0 / 0 | 0 / 0 | 0 / 1 (mã lỗi HTTP ở `handlers.py` "đúng" → sót B12) |
| Bước 3: sửa đúng hẳn | B11, B16 (+ B09 vòng qua) | B03, B09, B11, B16, B17 | B03, B08, B11, B13, B16, B17 | **B03, B08, B09, B11, B16** |
| Sửa một phần / vòng qua / giấu lỗi | B04, B08, B17 (vòng qua) | B04, B08 | B04; B09 nuốt lỗi | B04; **B13 vòng qua** (chặn ở `cancel_order`; bảng chuyển trạng thái vẫn cho SHIPPED → CANCELLED) |
| Chưa sửa | B03, B13 | B13 | — | **B17** (available vẫn −1) |
| Lỗi mới do agent gây ra (giao đơn còn pending) | không | không | không | **có**: vẫn báo lỗi nhưng kho 3 → 1, giữ chỗ 2 → 0 |
| Bộ test ẩn trên repo (FAIL / 105) | 26 | 21 | 18 | **22** |
| Thời gian agent làm việc (cộng các bước) | 8,8 phút | 11,3 phút | 7,4 phút | 7,9 phút (gồm 0,4 phút lần bị dừng) |
| Lần gọi tool | 103 (45 VGAR) | 148 | 102 | 105 (48 VGAR) |
| Token đầu vào: input + cache | 10,17 triệu | 12,21 triệu | 5,18 triệu | **7,75 triệu** |
| trong đó input không cache | 0,90 triệu | 5,71 triệu | 2,21 triệu | 1,26 triệu |
| Output / reasoning | 25k / 18k | 33k / 34k | 21k / 18k | 23k / 22k |
| Lần gọi mô hình | 110 | 133 | 86 | 112 |

Bộ test ẩn theo lỗi (A-en, toàn repo): B03 4/4, B04 15/20, B08 1/1, B09 1/4, B11 7/7, B13 1/3, B16 8/8, B17 0/3. Chấm riêng
(thay 5 file agent sửa vào `reference_fixed/`): 2 FAIL = copy list của B04 + `test_cannot_cancel_shipped_order` (B13 ở tầng
model). B09 qua khi chấm riêng: FAIL của B09 trên repo là do B17 chưa sửa. B08 kiểm tay với SKU không tồn tại: nhả về 0.
"Lỗi mới" kiểm tay bằng cùng kịch bản trên code của cả 4 lượt và trên `reference_fixed/`: chỉ A-en làm mất kho. Nguyên nhân là
`ship_order` bị viết lại (commit kho trước, đổi trạng thái sau, lỗi thì gọi `release`). Tổng token theo phiên (`info.tokens`)
cao hơn khoảng 0,1 triệu vì bước bị dừng không ghi token vào message; CSV dùng tổng theo message như các lượt khác.

Token theo bước (input + cache, triệu):

| Bước | B1 | B2 | Lỗi 3 | Lỗi 1 | Lỗi 2 | Lỗi 4 + 5 |
|---|---|---|---|---|---|---|
| B-en | 0,19 | 0,03 | 0,60 | 0,60 | 2,52 | 1,25 |
| A-en | 0,20 | 0,81 | 0,93 | 1,18 | 1,77 | 2,87 (gồm 0,48 lần bị dừng) |

Kiểm VGAR ở A-en: lỗi 3, 1, 2 chạy đủ `analyze_patch_impact` + `verify_patch_graph_constraints` (đều PASS). Lỗi 4–5 bị
NO_CHANGES vì graph đã được dựng lại trước khi kiểm, và agent báo đúng là "NOT checked" (lượt A-vi báo PASS). Grounding: không
anchor nào trúng hàm lỗi (giống lần chạy thử 0/5). Lỗi 3 → `Order.subtotal` (đúng file `order.py`); lỗi 4 → `Order`,
`Product.available` (triệu chứng của B17, không phải `InventoryService.commit`); lỗi 1–2 → `Customer` (sai); lỗi 5 → không có.
`search_symbols` với nhiều từ vẫn trả 0 (3 lần). Bước 2 chỉ gọi `find_task_anchors` 1 lần cho 6 quy tắc rồi đọc 19 file.

Vấn đề server mới thấy ở A-en (chưa sửa):
- `get_related_context` từ chối trả lời khi working tree khác graph: `retrieval.py:798-818` (`_verify_snapshot`) đọc snippet
  từ working tree, nên chỉ cần sửa một file hoặc có một file `.py` nháp là báo "Source content/file set differs from graph
  snapshot; rebuild graph". Agent làm theo → dựng lại graph → thay đổi chưa kiểm bị nuốt vào graph → lần kiểm sau báo
  NO_CHANGES. Ở A-en: sửa `ship_order` [93] → `get_related_context` lỗi [99] → dựng lại [100]. Chính thay đổi gây lỗi mất kho
  không bao giờ được kiểm. Ở [56], file nháp `test_bug.py` cộng với `graph_version` cũ → dựng lại thừa [57] (ra lại version cũ).
- Hướng sửa: đợt 3 đã lưu mã nguồn theo từng `graph_version` (bảng `sources`). Retrieval có thể đọc snippet từ đó
  (`sqlite_service.snapshot_sources`) thay vì working tree, và chỉ giữ hành vi cũ cho graph không có `sources`. Thông báo nên
  nói "có thay đổi chưa có trong graph: kiểm trước (analyze_patch_impact không cần diff) rồi mới dựng lại".
- Giới hạn cần ghi nhận: kể cả khi kiểm được, `analyze` + `verify` (tác động tĩnh + ràng buộc cấu trúc) không bắt được lỗi
  hành vi như `ship_order`; ShopFlow không có test nên `run_relevant_tests` không có gì để chạy.

Nhận định (cặp tiếng Anh):
- Bước 2: A-en nhỉnh hơn (8 so với 7, thêm B07), nhưng chủ yếu nhờ đọc file chứ không nhờ graph. Cả hai đều sót `reporting.py`
  (B10) dù nói đã xét mọi module.
- Bước 3: B-en hơn một chút (6 so với 5 lỗi sửa đúng; 18 so với 22 FAIL). Mỗi bên mạnh ở chỗ khác: A-en sửa B09 đúng gốc (B-en
  nuốt lỗi); B-en sửa đúng B13, B17 (A-en vòng qua B13, sót B17). A-en còn gây một lỗi mới không bị phát hiện.
- Token: A-en tốn hơn khoảng 50% (ngược với lượt tiếng Việt). Phần chênh nằm ở Bước 2: B-en trả lời bằng 1 lần gọi từ các file
  đã đọc ở Bước 1, còn A-en ở Bước 1 chỉ dùng tool graph nên Bước 2 phải đọc lại file. Phần còn lại ở lỗi 4–5 (gồm lần bị dừng).
  Input không cache thì A-en thấp hơn (1,26 so với 2,21 triệu). Tỉ lệ cache phụ thuộc nhà cung cấp, nên vẫn lấy input + cache
  làm số chính.
- Ngôn ngữ: cả hai nhánh tốt hơn khi dùng tiếng Anh (A: sửa đúng 2 → 5, FAIL 26 → 22; B: 5 → 6, 21 → 18). Nhưng mô tả lỗi 5
  cũng đã sửa giữa hai cặp lượt, và chênh lệch giữa các lượt cùng điều kiện lớn, nên chưa tách được tác động của từng yếu tố.
  Với 1 lượt mỗi ô, chưa kết luận được về tác dụng của VGAR.

## Lượt lặp 3: cặp nemotron sau đợt 4 và cặp big-pickle high, 23/11/2026 (tối)

### Điều kiện

| | A-en ② (VGAR) | B-en ② | A-en big-pickle (VGAR) | B-en big-pickle |
|---|---|---|---|---|
| Phiên | `ses_df7751f6` (20:14–20:25) | `ses_df7873d2` (19:54–20:09) | `ses_df7276b7` (21:39–22:02) | `ses_df736817` (21:22–21:34) |
| Commit kết quả | `d5e9b85` | `ce2e371` | `c04d180` | `d29d718` |
| Code xuất phát | `97cff65` | `97cff65` | `ee54b36` | `ee54b36` |
| Mô hình | `oc/nemotron-3.5-lightning-free` | như A | `oc/big-pickle`, variant `high` | như A |
| Server VGAR | đợt 4 (A + B: grounding) | tắt | đợt 4 | tắt |
| Prompt rerun cuối | **không gửi** | **không gửi** | **có** | **có** |

- Repo được tạo lại hai lần (`97cff65` lúc 19:51, `ee54b36` lúc 21:19). Mã nguồn giống `77426bb`: cả ba cho 40/105 FAIL trên
  bộ test ẩn, và `ee54b36` so trực tiếp với `97cff65` không khác dòng nào.
- Lượt bị loại:
  - `ses_df7d3171` (B-en 18:31): nhiễm. Phiên A-en `ses_df7eaf84` vẫn chạy sau khi commit gốc và sửa `pricing.py` (B16)
    lúc 18:29.
  - `ses_df7600d2` (big-pickle 20:37): chạy nhầm trên nhánh A-en ② đã có sẵn các bản sửa.
  - `ses_df74bf88` (B-en big-pickle 20:59): bỏ khỏi bảng theo yêu cầu. Lượt này cho kết quả 18 FAIL, cùng danh sách với lượt
    B-en big-pickle được giữ.
- Prompt rerun ("Rerun every reproduction…") chỉ có ở hai lượt big-pickle, và không lượt nào sửa code trong bước đó (chỉ
  `python -c`, `git`, đọc file). Vì vậy kết quả test ẩn so thẳng được với mọi lượt trước. Chi phí bên dưới chỉ tính **phần
  lõi** (Bước 1, Bước 2, 5 lỗi), cùng phạm vi với các lượt trước; bước rerun ghi riêng. Prompt rerun của nhánh A còn yêu cầu
  dán nguyên văn kết quả `analyze`/`verify`, nên dài hơn của B.
- Token cộng từ `tokens` của từng message, như CSV, nên có thể lệch vài phần trăm so với `info.tokens` của phiên.

### Big-pickle: A so với B (phần lõi)

| | A-en (VGAR) | B-en | A / B |
|---|---|---|---|
| Bộ test ẩn (FAIL / 105) | **18** | **18** | bằng nhau, cùng danh sách test |
| Bước 2: đúng / 17 | 15 (sót B05, B14) | 14 (sót B05, B14, B15) | +1 |
| Bước 3: sửa đúng hẳn | B03, B08, B09, B11, B13, B16, B17 | như A | bằng nhau |
| Sửa một phần | B04 (giữ dùng chung list truyền vào) | như A | – |
| Thời gian agent làm việc | 16,7 phút | 8,3 phút | ×2,0 |
| Token đầu vào: input + cache (gồm nén ngữ cảnh) | 7,44 triệu (7,04 + 0,40 nén) | 3,15 triệu | ×2,4 |
| Output + reasoning (gồm nén ngữ cảnh) | 121k (106k + 15k nén) | 53k | ×2,3 |
| — Bước 1–2: thời gian / token | 6,4 phút / 2,15 triệu | 2,4 phút / 0,17 triệu | ×2,7 / ×12,6 |
| — 5 lỗi: thời gian / token | 10,3 phút / 5,30 triệu | 5,9 phút / 2,99 triệu | ×1,75 / ×1,8 |
| Lần gọi mô hình | 92 | 54 | ×1,7 |
| Lần gọi tool (VGAR) | 210 (116) | 109 | ×1,9 |
| Thời gian chạy của server VGAR | 19 giây | – | – |
| Output VGAR | ≥ 1,19 MB (9 lần bị OpenCode cắt ở 50 KB) | – | ≈ 43 lần toàn bộ mã nguồn (27,6 KB) |
| Lần đọc mã nguồn | 62 (5 lỗi: 29) | 57 (5 lỗi: 33) | không giảm |
| Lần đọc lại output VGAR bị cắt | 4 | – | – |
| Lần edit / write | 7 | 9 | tương đương |
| Lần nén ngữ cảnh | 3 | 0 | – |
| File nháp để lại | 0 | 0 | – |
| *Bước rerun (riêng)* | *0,50 triệu, 1,7 phút* | *0,49 triệu, 1,3 phút* | *tương đương* |

Ghi chú cho bảng:
- Token của từng lần nén ngữ cảnh nằm trong message `compaction`, không nằm trong message của assistant. Bản đầu của bảng
  này bỏ sót phần đó (0,40 triệu input + cache, 15k output); số trên đã cộng vào. Lần nén ở Bước 2 thuộc Bước 1–2, hai lần
  còn lại thuộc 5 lỗi.
- Đã bỏ hàng "input không cache" (A 0,54 so với B 0,09 triệu): lượt B trúng cache khoảng 97%, tỉ lệ này phụ thuộc nhà cung
  cấp nên không dùng để so sánh.
- Thời gian chênh lệch nằm ở phía mô hình: chờ token đầu 466 so với 218 giây, sinh output 468 so với 263 giây. Server VGAR
  chỉ chạy tổng cộng 19 giây.
- Output VGAR theo tool: `get_related_context` 13 lần, 545 KB (trung bình 42 KB, 8 lần bị cắt; budget mặc định bằng trần
  12.000 token); `verify_patch_graph_constraints` 5 lần, 239 KB (trung bình 48 KB, 1 lần bị cắt); `find_task_anchors` 14
  lần, 165 KB; còn lại dưới 75 KB mỗi tool. Lần nén ngữ cảnh đầu xảy ra ngay sau 6 lần `get_related_context` ở Bước 2, sau
  đó agent đọc lại cả 27 file.
- Prompt A bắt buộc ít nhất 38 lần gọi VGAR (1 build ở Bước 1, 12 ở Bước 2, 5 mỗi lỗi) và đòi dán nguyên văn kết quả kiểm
  tra. Khoảng 78 lần gọi còn lại do mô hình tự chọn, 40 lần ở Bước 1 (gồm 7 lần đưa diff giả vào `analyze_patch_impact`).
- B08 "sửa đúng" ở cả hai, nhưng diff khác nhau: A đổi 1 dòng (`except Exception`); B viết lại 13 dòng, đưa cả bước lưu đơn
  và gửi thông báo vào `try`. Chạy thử trên bản copy: nếu gửi thông báo lỗi sau khi đơn đã lưu, bản của B nhả giữ chỗ nhưng
  đơn vẫn còn trong repo, và `ship` sau đó báo `cannot commit 2 of HUB-5001: only 0 reserved` (đơn không bao giờ giao được).
  Bản của A giữ hành vi gốc. Test ẩn không kiểm trường hợp này.

### Tất cả các lượt (phần lõi, cùng bộ test)

| Lượt | Mô hình | Server | FAIL / 105 | Bước 2 / 17 | Input + cache | Input không cache | Đọc file | Edit | Phút |
|---|---|---|---|---|---|---|---|---|---|
| A-vi | nemotron | đợt 3 | 26 | 5 | 10,28 triệu | 0,90 triệu | 10 | 13 | 9,9 |
| B-vi | nemotron | – | 21 | 7 | 12,21 triệu | 5,71 triệu | 38 | 24 | 11,3 |
| A-en ① | nemotron | đợt 3 | 22 | 8 | 7,86 triệu | 1,26 triệu | 24 | 12 | 7,6 |
| B-en ① | nemotron | – | 18 | 7 | 5,18 triệu | 2,21 triệu | 35 | 25 | 7,5 |
| A-en ② | nemotron | đợt 4 | 28 | 6 | 8,57 triệu | 0,99 triệu | 25 | 11 | 8,8 |
| B-en ② | nemotron | – | 25 | 8 | 15,13 triệu | 8,02 triệu | 41 | 28 | 13,5 |
| **A-en big-pickle** | big-pickle high | đợt 4 | **18** | **15** | 7,44 triệu | 0,54 triệu | 62 | 7 | 16,7 |
| **B-en big-pickle** | big-pickle high | – | **18** | **14** | 3,15 triệu | 0,09 triệu | 57 | 9 | 8,3 |
| **A-en big-pickle medium** | big-pickle medium | đợt 4 | **18** | **15** | 8,56 triệu | 0,49 triệu | 48 | 8 | 14,1 |
| **B-en big-pickle medium** | big-pickle medium | – | **17** | **14** | 4,57 triệu | 1,42 triệu | 51 | 9 | 8,2 |
| **A-en big-pickle medium (đợt 5)** | big-pickle medium | đợt 5 | **18** | **15** | 13,27 triệu | 0,57 triệu | 56 | 7 | 15,9 |
| **A-en big-pickle medium (đợt 6, SCIP)** | big-pickle medium | đợt 6 | **18** | **15** | 13,13 triệu | 0,91 triệu | 55 | 10 | 21,5 |

"Input + cache" đã cộng token của các lần nén ngữ cảnh (message `compaction`). Mọi lượt A đều có nén ngữ cảnh (A-vi,
A-en ①: 1 lần, 0,11 triệu; A-en ②: 1 lần, 0,22 triệu; A-en big-pickle: 3 lần, 0,40 triệu; A-en big-pickle medium: 3 lần,
0,39 triệu), không lượt B nào có. Hai lượt medium (24/11) xem ở Lượt lặp 4. Các bảng
ở Lượt lặp 1–2 và CSV chưa cộng phần này, nên số của nhánh A ở đó thấp hơn 0,11 triệu. Cột "Đọc file" của hai lượt
big-pickle chỉ tính file mã nguồn (A còn 4 lần đọc lại output VGAR bị cắt). Cột "Input không cache" phụ thuộc cách nhà cung
cấp cache, chỉ để tham khảo. "Edit" gồm cả tạo file nháp. Lượt A-vi gửi Bước 1 hai lần, A-en ① gửi lại lỗi 4–5, B-en ② bị dừng một lần ở lỗi 2 rồi
"continue".

Cặp nemotron sau đợt 4 (A-en ② / B-en ②), tóm tắt:
- A-en ②: sửa đúng B03, B13, B16, B17. B08 chỉ sửa một phần (SKU không tồn tại vẫn để lại hàng giữ chỗ).
  - B04 sửa nhưng thêm chặn SKU trùng trong `add_line`: hành vi mới, không ai yêu cầu.
  - Bỏ B09 dù `find_task_anchors` xếp `order_shipped` đứng đầu: gọi lỗi `email_address` là "lỗi có sẵn, không liên quan".
  - Không sửa B11.
  - `verify` NOT_RUN ở lỗi 3 và lỗi 5 (`API_UNSUPPORTED_EXPORT` / `API_UNSUPPORTED_DECLARATION`) nhưng tóm tắt cuối báo
    "pass".
- B-en ②: sửa đúng B03, B08, B09, B13, B16, B17; B04 một phần.
  - Không sửa B11: tự thêm coupon vào bản tái hiện lỗi 2 rồi cho rằng con số mong đợi của đề sai.
- Đợt 4 có tác dụng ở phía công cụ:
  - Anchor trúng ít nhất một file lỗi ở 5/5 lỗi (lượt A-en ① là 0/5).
  - Build tự kiểm thay đổi chưa kiểm trước khi cập nhật (`checks_before_update: CHECKED`).
  - Không còn lỗi "rebuild graph" do version cũ.

Ghi nhận về VGAR ở lượt A-en big-pickle:
- 116 lần gọi VGAR, output tổng 1,19 MB (đọc file trực tiếp: 118 KB). OpenCode cắt bớt output dài, agent phải đọc lại file
  `tool-output`. Đây cũng là nguyên nhân chính của 3 lần nén ngữ cảnh.
- Bước 1 (chỉ đọc): agent đưa 7 diff giả vào `analyze_patch_impact` để dò phụ thuộc giữa module (2 lần `INVALID_ARGUMENT`).
  Server chưa có tool trả lời trực tiếp "module/component nào phụ thuộc module nào".
- Anchor đúng cả 5 lỗi (lỗi 2 khớp nguyên văn thông báo lỗi với `combine_rates`, lỗi 4 ra `order_shipped`), nhưng lượt B
  cùng mô hình tự tìm ra đúng các chỗ đó. Không lần kiểm `analyze`/`verify` nào làm agent đổi bản sửa.
- Lỗi 5: sửa hằng số `ALLOWED_TRANSITIONS` cho `analyze` `changed: []` và `verify` NOT_RUN (hằng số cấp module chưa là node).
  Agent báo đúng là NOT_RUN.

### Nhận định (lượt lặp 3)

- Mô hình quan trọng hơn VGAR.
  - Đổi nemotron sang big-pickle: Bước 2 tăng từ 5–8 lên 14–15. Cả hai nhánh cùng sửa đúng mọi lỗi trong prompt (B04 một
    phần), không còn file nháp hay lỗi bị nuốt.
  - Thêm VGAR chưa cải thiện kết quả ở cặp nào. Nemotron: A kém hơn B 3–5 test ở cả 3 cặp, ngang mức dao động giữa các lượt
    (B nemotron dao động 18–25). Big-pickle: A bằng B.
- Lợi ích chi phí thấy ở nemotron không còn ở big-pickle.
  - Nemotron: A luôn có input không cache khoảng 1 triệu (B: 2,2–8,0 triệu) và đọc ít file hơn (10–25 so với 35–41).
  - Big-pickle tự đọc mỗi file khoảng một lần và tận dụng cache, nên B đã rẻ. A big-pickle vừa đọc file vừa gọi VGAR, nên
    tốn gấp 2,0 lần thời gian và 2,4 lần token. Phần chênh nằm chủ yếu ở Bước 1–2 (token ×12,6): B đọc hết 27 file với 0,14
    triệu token và trả lời Bước 2 bằng 1 lần gọi mô hình. Với repo nhỏ như ShopFlow, đọc cả repo rẻ hơn mọi truy vấn graph,
    nên con số ×2 không áp dụng được cho repo lớn.
  - Nguyên nhân không nằm ở server (19 giây). Phần chênh đến từ: output VGAR quá lớn (≥ 1,19 MB, gấp khoảng 43 lần mã nguồn)
    gây 3 lần nén ngữ cảnh và đọc lại file; prompt A bắt buộc ít nhất 38 lần gọi và đòi dán nguyên văn JSON; mô hình tự gọi
    thêm khoảng 78 lần.
- Báo cáo kết quả kiểm VGAR: nemotron 2/3 lượt báo PASS khi kết quả là NOT_RUN hoặc ERROR. Big-pickle báo đúng.
- ShopFlow đã chạm trần với mô hình mạnh: 17/18 test còn FAIL thuộc lỗi không có trong 5 prompt, test còn lại là B04 giữ dùng
  chung list. Bài này không còn phân biệt được A với B về chất lượng.
- Mỗi ô big-pickle mới có 1 lượt sau khi bỏ `ses_df74bf88`. Lượt bị bỏ cũng cho 18 FAIL cùng danh sách, nhưng không tính vào
  bảng.

### Việc tiếp theo (đề xuất)

- Benchmark khó hơn: repo lớn hơn, lỗi nhiều file mà mô tả không nêu tên hàm. Đo khả năng tìm đúng chỗ lỗi (file hoặc hàm trúng
  ở lần đầu, số file phải đọc), đúng phạm vi "lỗi nhiều file" của đề tài.
- Giảm kích thước output, ưu tiên `get_related_context` (hạ budget mặc định hoặc co theo kích thước repo; mặc định hiện
  bằng trần 12.000 token) và `verify_patch_graph_constraints` (chế độ tóm tắt). Mục tiêu là mỗi lần trả lời nhỏ hơn hẳn
  ngưỡng cắt 50 KB của OpenCode, để tránh bị cắt và tránh nén ngữ cảnh.
- Thêm tool phụ thuộc giữa module/component, để agent không phải dùng diff giả.
- Tách chi phí của giao thức khỏi chi phí của VGAR: chạy biến thể A dùng prompt giống hệt B (bật tool, không bắt gọi tool,
  không đòi dán JSON). Thêm ít nhất 2 lượt mỗi nhánh để ước lượng độ dao động.
- NOT_RUN không được để mô hình đọc thành PASS (status ngoài cùng hoặc thông báo "not verified"). Đưa hằng số cấp module thành
  node.

## Lượt lặp 4: cặp big-pickle medium, 24/11/2026

### Điều kiện

| | A-en medium (VGAR) | B-en medium |
|---|---|---|
| Phiên | `ses_df5c9ffa` (04:00–04:19) | `ses_df5ec401` (03:23–03:37) |
| Repo | `D:\kltn\shopflow-clean1\shopflow` (repo mới) | `D:\kltn\shopflow-clean\shopflow` |
| Code xuất phát | `b8a60fb` (03:59; tree giống hệt `ee54b36`) | `ee54b36` |
| Commit kết quả | `13dbdae` (trên `master`) | `0c7119f` (trên `master`) |
| Mô hình | `oc/big-pickle`, variant `medium` | như A |
| Server VGAR | đợt 4 (không đổi so với lượt high) | tắt |
| Prompt | như lượt high, có prompt rerun cuối | như lượt high, có prompt rerun cuối |

- `b8a60fb` có cùng tree hash với `ee54b36` (`2f95ff90…`), nên hai lượt medium xuất phát từ đúng code của cặp high.
- Lượt bị loại: `ses_df5da86a` (A-en medium, 03:42–03:55). Lượt này chạy trên `master` của repo cũ, lúc đó đã là `0c7119f` (có
  sẵn mọi bản sửa của B-en medium). Agent không sửa gì, báo đúng là "None by me", mọi lần kiểm đều NO_CHANGES.
- Hai lượt đều không có lần sửa nào trong bước rerun.
- CSV thêm 6 lượt, tổng 584 dòng: `B_nomcp_en_2` 151, `A_vgar_en_2` 106 (cặp nemotron ② của Lượt lặp 3),
  `B_nomcp_en_bigpickle_high` 59, `A_vgar_en_bigpickle_high` 101, `B_nomcp_en_bigpickle_medium` 60,
  `A_vgar_en_bigpickle_medium` 107. Khác 4 lượt nemotron cũ trong CSV: có cả dòng nén ngữ cảnh (`tools` = `compaction`) và bước
  rerun (`step` = `Rerun`, chỉ có ở các lượt big-pickle). Cột `model` của các lượt big-pickle ghi kèm variant
  (`oc/big-pickle:high`, `oc/big-pickle:medium`). Ở `B_nomcp_en_2`, prompt "continue" sau lần bị dừng được tính vào bước Lỗi 2.

### Big-pickle medium: A so với B (phần lõi)

| | A-en medium (VGAR) | B-en medium | A / B |
|---|---|---|---|
| Bộ test ẩn (FAIL / 105) | **18** | **17** | B hơn 1 test (`test_order_copies_input_lines`) |
| Bước 2: đúng / 17 | 15 (sót B05, B14), không báo thừa | 14 (sót B05, B14, B15), 2 mục thừa | +1 |
| Bước 3: sửa đúng hẳn | B03, B08, B09, B11, B13, B16, B17 | như A, thêm B04 | – |
| Sửa một phần | B04 (giữ dùng chung list truyền vào) | – | – |
| Thời gian agent làm việc | 14,1 phút | 8,2 phút | ×1,7 |
| Token đầu vào: input + cache (gồm nén ngữ cảnh) | 8,56 triệu (8,17 + 0,39 nén) | 4,57 triệu | ×1,9 |
| Output + reasoning (gồm nén ngữ cảnh) | 89k (75k + 14k nén) | 49k | ×1,8 |
| — Bước 1–2: thời gian / token | 5,9 phút / 2,08 triệu | 3,0 phút / 0,47 triệu | ×2,0 / ×4,4 |
| — 5 lỗi: thời gian / token | 8,3 phút / 6,48 triệu | 5,2 phút / 4,09 triệu | ×1,6 / ×1,6 |
| Lần gọi mô hình | 95 | 57 | ×1,7 |
| Lần gọi tool (VGAR) | 205 (116) | 106 | ×1,9 |
| Thời gian chạy của server VGAR | 18 giây | – | – |
| Output VGAR | ≥ 1,29 MB (11 lần bị OpenCode cắt ở 50 KB) | – | ≈ 47 lần toàn bộ mã nguồn |
| Lần đọc mã nguồn | 48 (5 lỗi: 21) | 51 (5 lỗi: 24) | không giảm |
| Lần đọc lại output VGAR bị cắt | 0 | – | – |
| Lần edit / write | 8 | 9 | tương đương |
| Lần nén ngữ cảnh | 3 | 0 | – |
| File nháp để lại | 0 (nhưng commit có 27 file `__pycache__/*.pyc`) | 0 | – |
| *Bước rerun (riêng)* | *0,63 triệu, 2,2 phút* | *0,41 triệu, 1,0 phút* | – |

Ghi chú cho bảng:
- Cách đo giống Lượt lặp 3: thời gian là wall time từng prompt (gồm cả thời gian nén ngữ cảnh), token cộng theo message.
  Riêng B-en medium, tổng theo message (4,98 triệu cả phiên) thấp hơn `info.tokens` (5,08 triệu) khoảng 0,1 triệu.
- Bộ test ẩn: 17 FAIL của B-en medium đều thuộc lỗi không có trong 5 prompt (B01, B02, B05, B06, B07, B10, B12, B14, B15).
  Đây là mức trần của phạm vi 5 prompt. A-en medium FAIL thêm đúng 1 test của B04, cùng danh sách 18 test với cả hai lượt high.
  Code sửa của hai lượt medium giống hệt nhau, trừ một dòng: B sửa `self.lines = list(lines) if lines is not None else []`,
  A bỏ `list(...)`.
- Cả hai lượt sửa B08 bằng 1 dòng `except Exception` (như A high). Không lượt nào gặp vấn đề "đơn đã lưu nhưng giữ chỗ đã
  nhả" của B high.
- Mức cache khác nhiều giữa các lượt B (B medium: input không cache 1,42 triệu, khoảng 31%; B high: 0,09 triệu, khoảng 3%).
  Tỉ lệ này phụ thuộc nhà cung cấp, nên vẫn so bằng input + cache.
- Thời gian chênh lệch nằm ở phía mô hình: chờ token đầu 434 so với 215 giây. Server VGAR chạy tổng cộng 18 giây.
- Output VGAR theo tool: `get_related_context` 14 lần, 625 KB (trung bình 45 KB, 9 lần bị cắt); `verify_patch_graph_constraints`
  6 lần, 289 KB (2 lần bị cắt); `find_task_anchors` 14 lần, 155 KB; còn lại dưới 70 KB mỗi tool. Lần nén ngữ cảnh đầu lại xảy
  ra ở Bước 2, ngay sau loạt `get_related_context` cho 6 quy tắc.
- Phân bổ 116 lần gọi VGAR: Bước 1: 23, Bước 2: 42, 5 lỗi: 8 / 14 / 8 / 9 / 12. Prompt bắt buộc ít nhất 38 lần, nên khoảng 78
  lần do mô hình tự chọn (bằng lượt high). Khác lượt high: không có diff giả nào ở Bước 1.

### Ghi nhận về VGAR ở lượt A-en medium

- Anchor trúng ít nhất một file lỗi ở cả 5 lỗi, giống lượt high: lỗi 3 → `OrderLine`, `Order.subtotal`; lỗi 1 →
  `combine_rates` (0,85, khớp nguyên văn thông báo lỗi), `coupon_rate`; lỗi 2 → `quote_order`, `shipping_fee`; lỗi 4 →
  `order_shipped`; lỗi 5 → `cancel_order`. Chỗ sửa thứ hai của các lỗi ghép không được anchor (`place_order` cho B08,
  `InventoryService.commit` cho B17), và hằng số `ALLOWED_TRANSITIONS` chưa là node.
- Kiểm patch: `verify` PASS ở lỗi 3, 1, 2, 4. Mỗi lần build đều có `checks_before_update: CHECKED` đúng các file vừa sửa. Lỗi 5:
  `verify` NOT_RUN (`API_UNSUPPORTED_DECLARATION`), và agent báo đúng là NOT CHECKED. Không lần kiểm nào làm agent đổi bản sửa.
- Lỗi 1: agent gọi lại `analyze` + `verify` lần hai chỉ vì OpenCode đã cắt output `verify` lần đầu, nên chưa có bản nguyên
  văn để dán. Output `verify` lần hai cũng bị cắt.
- Bước 2: A-en medium là lượt duy nhất tìm ra B15 (`find_by_email` không lowercase), và không báo mục thừa nào. Agent cũng chạy
  thử triệu chứng trong bộ nhớ ở nhiều mục. Lượt B cùng mô hình tìm được 14 lỗi, sót đúng các lỗi mà B high đã sót.

### Nhận định (lượt lặp 4)

- Kết luận của lượt lặp 3 không đổi khi hạ mức suy nghĩ từ high xuống medium:
  - Kết quả: A 18 so với B 17. Phần chênh chỉ là 1 dòng copy list ở B04, chưa đủ để coi là khác biệt (n = 1). Cả 4 lượt
    big-pickle đều sửa đúng mọi lỗi trong prompt.
  - Chi phí: A tốn ×1,9 token và ×1,7 thời gian (lượt high: ×2,4 và ×2,0). Phần chênh vẫn nằm nhiều nhất ở Bước 1–2.
- Medium so với high: B medium dùng nhiều token hơn B high (4,57 so với 3,15 triệu) nhưng thời gian bằng nhau. A medium dùng
  nhiều token hơn A high (8,56 so với 7,44 triệu) nhưng nhanh hơn (14,1 so với 16,7 phút). Bước 2 bằng nhau ở cả hai nhánh
  (A 15, B 14). Với 1 lượt mỗi ô, chưa thấy medium kém hơn high trên ShopFlow.
- Output VGAR quá lớn tiếp tục là nguyên nhân chính gây cắt output, gọi lại tool và nén ngữ cảnh. Điều này ủng hộ việc giảm
  kích thước output (spec đợt 5).
- ShopFlow vẫn chạm trần: B-en medium đạt đúng mức trần của phạm vi 5 prompt. Hướng tiếp theo giữ như Lượt lặp 3: cần
  benchmark khó hơn.

## Lượt lặp 5: A-en big-pickle medium sau đợt 5 (thu nhỏ output), 24/11/2026

### Điều kiện

| | A-en medium sau đợt 5 | A-en medium đợt 4 (Lượt lặp 4) |
|---|---|---|
| Phiên | `ses_df3c1717` | `ses_df5c9ffa` |
| Repo | `D:\kltn\shopflow-clean1\shopflow` (tạo lại, xuất phát `68c96af`) | như cột bên, `b8a60fb` |
| Commit kết quả | `9119471` | `13dbdae` |
| Mô hình | `oc/big-pickle`, variant `medium` | như cột bên |
| Server VGAR | đợt 5 (spec `2026-11-24-tv2-smaller-tool-output-design.md`, chưa commit) | đợt 4 |
| Prompt | như Lượt lặp 4, có prompt rerun | như cột bên |

Chưa có lượt B chạy cùng thời điểm; lượt này so với lượt A đợt 4. Số liệu đo bằng
`D:\kltn\vgar-work\opencode-logs\session_metrics.py`, **tính cả bước rerun** (bảng Lượt lặp 4 không tính rerun, nên số cột
đợt 4 ở đây lớn hơn bảng đó).

### Kết quả

| | Đợt 4 | Đợt 5 |
|---|---|---|
| Bộ test ẩn (FAIL / 105) | 18 | **18** (cùng danh sách) |
| Bước 2: đúng / 17 | 15 (sót B05, B14) | 15 (sót B05, B14), thêm 1 mục ngoài đáp án |
| Bước 3: code sửa | | giống hệt đợt 4, kể cả B04 sửa một phần |
| Output VGAR | 1.485 KB | **595 KB** (−60%) |
| Lần bị OpenCode cắt ở 50 KB | 11 | **0** |
| `get_related_context` lớn nhất | 85,6 KB | **32,8 KB** |
| `verify_patch_graph_constraints` mỗi lần | 49–54 KB | **~1,1 KB** |
| Lần nén ngữ cảnh | 3 | **1** |
| Lần gọi VGAR | 116 | 82 |
| Lần đọc mã nguồn | 55 | 56 |
| Lần gọi mô hình | 104 | 127 |
| Thời gian (wall, cả phiên) | 16,4 phút | 17,7 phút |
| Token đầu vào: input + cache | 9,18 triệu | **13,55 triệu** (+48%) |
| Output + reasoning | 110k | 92k |

Ghi chú:
- Mục ngoài đáp án ở Bước 2: `ship_order` đổi trạng thái sang SHIPPED trước `inventory.commit()`. Không phải lỗi cài sẵn.
- `get_related_context`: 14 lần, mọi response ≤ 32,8 KB, 5 lần bị giới hạn 32 KiB bỏ mục (6–13 mục). Không hàm lỗi nào mất:
  code sửa và kết quả chấm giống đợt 4.
- Lỗi 5: `verify` trả `status` ngoài cùng NOT_RUN, summary nêu `API_UNSUPPORTED_DECLARATION: ALLOWED_TRANSITIONS`. Agent
  báo đúng "NOT checked — verification did not complete". Các lượt trước có lúc báo NOT_RUN thành PASS.
- Token tăng gần hết ở Bước 2 (6,71 so với 1,70 triệu): 59 lần gọi mô hình, **mỗi lần đúng 1 tool**, không nén ngữ cảnh,
  mỗi lần đọc lại khoảng 114k token. Đợt 4: 23 lần gọi, nhiều lần chạy 6–11 tool song song, và bị nén ngay trong Bước 2.
  Mô hình thôi gọi tool song song là biến động của mô hình/nhà cung cấp, chưa quy được cho đợt 5 (n=1).

### Nhận xét

- Đợt 5 đạt mục tiêu của nó: output nhỏ, không bị cắt, kết luận kiểm hiện ở `status` ngoài cùng và được agent báo đúng.
- Chưa thấy lợi về chi phí: chi phí do số lần gọi mô hình × độ dài ngữ cảnh quyết định, không chỉ do kích thước output.
  Cần lặp ≥ 3 lượt mỗi cấu hình và tính $/task solved có tách giá cache (spec đợt 5 §5.4).
- ShopFlow vẫn chạm trần (17–18 FAIL ở mọi lượt big-pickle); cần benchmark khó hơn để thấy khác biệt chất lượng.

## Lượt lặp 6: A-en big-pickle medium với SCIP mặc định (đợt 6), 24/11/2026

### Điều kiện

| | A-en medium đợt 6 (SCIP) | A-en medium đợt 5 (Lượt lặp 5) |
|---|---|---|
| Phiên | `ses_df1ad49d` | `ses_df3c1717` |
| Repo (gốc MCP) | `D:\kltn\shopflow-clean\shopflow` (thư mục chứa package `shopflow\`) | `D:\kltn\shopflow-clean1\shopflow` |
| Code xuất phát / kết quả | `2c9b176` → `c7cce6f` (commit thẳng trên `master`) | `68c96af` → `9119471` |
| Mô hình | `oc/big-pickle`, variant `medium` | như cột bên |
| Server VGAR | đợt 6: SCIP → LSP (khi SCIP lỗi) → tĩnh, mặc định | đợt 5, không layer |
| Prompt | như Lượt lặp 4–5, có prompt rerun | như cột bên |

- Lượt bị loại: `ses_df211e36` (cùng ngày). MCP trỏ vào thư mục package `shopflow\shopflow`, nên module mất tiền tố
  `shopflow.`, 136/139 import thành "external", graph chỉ 33 CALLS. Không dùng số của lượt đó.
- Bảng "Tất cả các lượt" không tính bước rerun; bảng dưới tính cả rerun.

### SCIP trong phiên thật

| Kiểm | Kết quả |
|---|---|
| `layers` ở 6/6 lần `build_or_update_graph` | `scip: ready`, `lsp: skipped` ("SCIP ready") |
| Graph | 615 node, 931 cạnh (136 CALLS từ SCIP, như `tv2_scip_in_served_graph_run_2026-11-24.md`) |
| Thời gian mỗi lần dựng (đầy đủ) | 2,8–3,4 s |
| `changed_files` sau mỗi lỗi | đúng file, có tiền tố `shopflow/` |
| `checks_before_update.verify` | PASS ở lỗi 1–4, NOT_RUN ở lỗi 5 (`ALLOWED_TRANSITIONS`) |
| File lạ trong repo | không |

### Kết quả

| | Đợt 5 (Lượt lặp 5, không SCIP) | Đợt 6 (SCIP) |
|---|---|---|
| Bộ test ẩn (FAIL / 105) | 18 | **18** (cùng danh sách; B04 vẫn không copy list) |
| Bước 2: đúng / 17 | 15 (sót B05, B14) + 1 mục ngoài đáp án | 15 (sót B05, B14) + 1 mục ngoài đáp án khác (body `items` sai định dạng) |
| Output VGAR | 595 KB | 648 KB (0 lần bị cắt) |
| Lần gọi mô hình | 127 | 132 |
| Lần gọi VGAR | 82 | 96 |
| Lần đọc mã nguồn | 56 | 59 |
| Lần edit | 7 | 10 |
| Lần nén ngữ cảnh | 1 | 2 |
| Thời gian (cả phiên) | 17,7 phút | 24,2 phút |
| Token đầu vào: input + cache | 13,55 triệu | **13,93 triệu** |
| Output + reasoning | 92k | 88k |

Ghi chú:
- Bước 2 rẻ (0,74 triệu; 6–11 tool mỗi lần gọi), nhưng phần sửa lỗi đắt (1,9–3,2 triệu mỗi lỗi). Lỗi 1 mất 5,9 phút,
  35 lần gọi VGAR: agent gọi `verify` với `details=true` hai lần (34–38 KB mỗi lần); lần sửa đầu chuyển đoạn lưu đơn vào
  `try` nên `verify` NOT_RUN (`API_UNSUPPORTED_EXPORT`), agent sửa lại rồi kiểm tiếp.
- Bước rerun: agent tự gõ diff đưa vào `verify` → ERROR `PATCH_DOES_NOT_APPLY`.
- B08 được sửa bằng cách đưa cả bước lưu đơn và gửi thông báo vào `try` (giống B high): nếu thông báo lỗi sau khi đơn đã lưu,
  giữ chỗ bị nhả mà đơn vẫn còn. Test ẩn không kiểm trường hợp này.

### Nhận xét

- RQ1: SCIP (Layer 2, §5.4) chạy ổn định trong phiên agent thật với graph đầy đủ: 6/6 lần dựng `ready`, khoảng 3 s mỗi
  lần, `verify` đúng, không ghi file vào repo.
- Chi phí: SCIP **không giảm token** trên ShopFlow (13,93 so với 13,55 triệu); chi phí do số lần gọi mô hình và cách agent
  dùng tool (`details=true`, sửa lại) quyết định.
- Chất lượng: như đợt 5 (18 FAIL, 15/17). ShopFlow vẫn chạm trần; cần benchmark khó hơn và ≥ 2–3 lượt mỗi cấu hình.
