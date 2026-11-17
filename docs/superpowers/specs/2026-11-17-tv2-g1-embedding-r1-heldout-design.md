# TV2 · Ba việc tiếp theo: chốt G1, baseline embedding cho R1, R1 trên held-out (17/11/2026)

> **Bản nháp, chờ duyệt.** Phạm vi: plan 2 tuần (`docs/status/plan_2_weeks_mcp_server_2026-11-07.md`), tuần 2 ngày 2–6 của TV2, và proposal.
> Mục **Cần quyết định** ở cuối mỗi phần là những chỗ tôi không tự chốt.

## 0. Hiện trạng đã kiểm tra (17/11)

| Việc | Hiện trạng thật | Bằng chứng |
|---|---|---|
| G1 | **Đã chạy xong 16/11**: 300 nhãn do Claude gán đã khóa; 30 mục lượt hai **do một lượt Claude khác gán theo yêu cầu của người dùng**, đã khóa; 1 mục lệch (C017) đã chốt; báo cáo đã sinh | `~/rt1/g1/report/g1_report.md`, `manifest.json` (`agreement_lock`), `settlement.csv` (WSL) |
| R1 | 9 cấu hình trên 50 task dev; baseline văn bản `bm25`, `grep`, `neighbor`; **chưa có embedding, chưa có agent default** | `docs/status/tv2_r1_results_comparison_2026-11-16.md`; code `ablation_matrix/text_baselines.py`, `ablation_matrix/run_r1_ablation.py` |
| Môi trường | WSL `~/.vgar-wsl` **không có** `torch`, `sentence-transformers`; máy có GPU RTX 4050 Laptop (6 GB) | kiểm tra `importlib.util.find_spec` |
| Freeze | `docs/protocol_freeze_heldout.md` là bản nháp cho **repair A0–A3 của M3** (kế hoạch 16 tuần), không có mục cho R1 | đọc file |

Số G1 hiện có (n = 150 lời gọi, 150 tên dùng; CI95 bootstrap):

| Graph | Call edge `CALLS` P / R | `CALLS + MAY_CALL` P / R | Symbol (tên dùng, có tree-sitter-graph) P / R |
|---|---|---|---|
| static | 1,000 / 0,418 | 0,486 / 0,609 | không áp dụng |
| tsg | 1,000 / 0,418 | 0,486 / 0,609 | 0,978 / 0,333 |
| tsg + JARVIS | 1,000 / 0,527 | 0,526 / 0,645 | 0,978 / 0,333 |

---

## 1. Việc 1: chốt G1

G1 trong plan gồm 5 metric ([P] dòng 1341–1347): symbol P/R, call edge P/R, trace link P/R, component boundary quality, incremental update correctness. Gán nhãn đã xong; phần còn lại là ghép đủ 5 metric, đưa báo cáo vào repo và đối chiếu §8.3.

### 1.1 Việc cần làm

| # | Việc | Đầu ra |
|---|---|---|
| G1-a | Chép báo cáo WSL vào repo, ghi rõ ai gán nhãn | `docs/status/tv2_g1_graph_quality_2026-11-17.md` |
| G1-b | Ghép 5 metric vào một bảng: symbol, call edge (từ G1); trace link (TR-1: top-1 P 0,70 / R 0,50; ngưỡng ≥ 0,7: P 0,45 / R 0,58); incremental correctness (U1: 12/12 khớp build lại); component boundary (xem 1.2) | cùng file |
| G1-c | Đối chiếu 2 điều kiện §8.3 về cạnh ([P] dòng 835–841) bằng số G1, **không đặt ngưỡng mới** (proposal chỉ nói "đủ cao", "không quá thấp") | một mục trong báo cáo, ghi số và để nhóm kết luận |
| G1-d | Cánh `scip_tsg` (báo cáo ghi "not run: needs --scip-entry") | chạy nếu D1-3 chọn có |

### 1.2 Component boundary quality

Cần nhãn kiến trúc làm tay (plan O7); proposal không nêu cỡ mẫu. Đề xuất: mỗi repo trong 12 repo dev, người gán đánh dấu Component nào **đúng ranh giới** / **nên gộp** / **nên tách** (khoảng 429 Component; có thể lấy mẫu 60). Đây là việc của người, Claude không gán thay.

### 1.3 Cần quyết định

| Mã | Câu hỏi | Lựa chọn | Đề xuất |
|---|---|---|---|
| D1-1 | 30 nhãn lượt hai hiện là Claude so với Claude. Giữ hay để người gán mù lại? | (a) giữ, báo cáo ghi "độ nhất quán của Claude", là giới hạn; (b) người gán mù 30 mục (khoảng 1 giờ), bộ chấm so lại | **(b)** nếu còn thời gian: hội đồng sẽ hỏi nhãn có người kiểm không. Lưu ý: file `agreement_user.csv` đã khóa; gán lại phải dùng file mới `agreement_human.csv` và ghi hash riêng, không sửa file cũ |
| D1-2 | Component boundary quality | (a) người gán mẫu 60 Component; (b) ghi là chưa đo | (a) nếu D1-1 chọn (b) thì làm chung buổi |
| D1-3 | Chạy cánh `scip_tsg` | có / không | không: SCIP không phải cấu hình đang phục vụ, và R1 không dùng nó |

---

## 2. Việc 2: baseline embedding cho R1

### 2.1 Vì sao cần

Proposal nêu embedding là baseline retrieval (§13.1 dòng 1283), RQ2 hỏi thẳng "tốt hơn BM25/embedding/grep không" (dòng 85), và tiêu chí thành công của M2 là "improve gold file/function recall over grep/BM25/embedding baseline" (dòng 1408). Thiếu embedding thì không trả lời đủ RQ2. Vì vậy **đề xuất cài thêm, không ghi là giới hạn**.

### 2.2 Thiết kế

- **Đơn vị**: cùng chunk 80 dòng với BM25 (`extract_chunks`), để cùng corpus và cùng cách đóng gói ngân sách 12.000 token. Kiểm tra `corpus_hash` trùng với `bm25`.
- **Truy vấn**: `problem_statement` như mọi cánh khác (chính sách `problem_statement_only_no_hints_or_gold`).
- **Xếp hạng**: cosine giữa embedding truy vấn và embedding chunk; xếp hạng **toàn bộ** chunk (giống BM25, nên reach = 1,0).
- **Model** (D2-1): đề xuất `nomic-ai/CodeRankEmbed` (137M tham số, huấn luyện cho truy hồi code, Apache-2.0); dự phòng `jinaai/jina-embeddings-v2-base-code` (161M). Ghim revision SHA của model, ghi vào kết quả.
- **Cache**: embedding chunk lưu theo `(model revision, corpus_hash)`, chạy lại không tính lại.
- **Code**: `ablation_matrix/embedding_baseline.py` với hàm `embedding_rank(instance_id, issue_text, sources) -> RankRecord`, cùng chữ ký `bm25_rank`; thêm `"embedding"` vào `TEXT_ARMS` và các cặp so sánh `A1 − embedding`, `A2 − embedding`, `A2+RT1 − embedding`; thêm vào lượt trộn RRF ở phần 4 của báo cáo R1.
- **Test**: test đơn vị dùng embedder giả (vector cố định) để kiểm thứ tự, ngân sách, cùng chunk với BM25; không tải model trong CI.
- **Môi trường**: cài `sentence-transformers` + `torch` vào `~/.vgar-wsl`. Ước tính khoảng 9.400 chunk mỗi task; với GPU, vài chục giây mỗi task; 50 task dưới 1 giờ (phải đo).
- **Ai chạy**: **người dùng chạy lượt có model** (GPU); Claude viết code, test, và lệnh chạy.

### 2.3 Baseline "agent default exploration"

Proposal liệt kê baseline này trong "Retrieval baselines" (§13.1, dòng 1278–1286), nên **không được tự bỏ**. R1 không có agent, nên baseline này cần trace của một coding agent thật chạy trên cùng task. Đề xuất (D2-2):

- Ghi là **baseline còn thiếu** trong báo cáo R1, kèm lý do.
- Đề nghị TV1 (phụ trách MCP usability, plan tuần 2 ngày 3) cho trace cánh A0 (agent không có MCP). Nếu có: lấy thứ tự file agent đọc lần đầu làm danh sách xếp hạng, chấm bằng cùng bộ chấm R1 (file R@k, MRR), chỉ ở mức file. Việc chuyển trace thành danh sách xếp hạng là quy ước của nhóm, proposal không định nghĩa.

### 2.4 `dependency_frontier_recall@B`

Proposal định nghĩa `F*(T, R)` là tập node "cần biết để sinh patch đúng" và `Recall@B = |C ∩ F*| / |F*|` (§8.2, dòng 793–816), nhưng không nói cách lấy `F*`. R1 hiện chỉ đo Recall@B trên file/hàm của patch gold, hẹp hơn `F*` (plan O1). Đề xuất (D2-4) một cách xấp xỉ, **không dùng graph** để không thiên vị cánh graph:

`F*_approx` = hàm bị sửa trong patch gold ∪ định nghĩa trong repo được **nhắc tên** ở dòng thêm (`+`) của patch gold, chỉ lấy tên có **đúng một** định nghĩa trong repo (bảng định nghĩa `CorpusIndex`, cùng bảng với nhãn gold).

Không đưa test (`FAIL_TO_PASS`) vào, dù ví dụ của proposal có node Test: corpus của R1 loại file test cho **mọi** cánh, nên không cánh nào lấy được test và metric chỉ bị kéo xuống đều. Báo cáo ghi rõ điểm này.

Báo cáo gọi đây là "xấp xỉ của `F*`", không gọi là `F*`. Thay thế: ghi là chưa đo.

### 2.5 Cần quyết định

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| D2-1 | Model embedding | `nomic-ai/CodeRankEmbed`, dự phòng `jina-embeddings-v2-base-code` |
| D2-2 | "Agent default exploration" | ghi là còn thiếu; đề nghị TV1 cho trace A0, có thì chấm ở mức file |
| D2-3 | Chạy embedding trên 50 task dev trước khi freeze | có: số dev cho embedding phải có trước khi freeze, giống các cánh khác |
| D2-4 | `dependency_frontier_recall@B` | đo bằng `F*_approx` ở trên, ghi rõ là xấp xỉ |

---

## 3. Việc 3: R1 trên held-out

Plan tuần 2: ngày 5 cả nhóm freeze protocol, ngày 6 chạy held-out **đúng một lần**. Phần này chỉ thiết kế phần R1; buổi freeze là việc của cả nhóm.

**Nguồn:** proposal **không** nói tới held-out, freeze hay kiểm định thống kê (chỉ yêu cầu "protocol đo lại", dòng 1490). Quy trình dev/held-out lấy từ plan 2 tuần (nguồn [test] mục 3). Bootstrap và Holm là lựa chọn của nhóm; nguồn [mm] 1.4 ghi rõ phần thống kê là "suy luận, proposal không định nghĩa". Báo cáo phải ghi nguồn như vậy.

### 3.1 Những gì phải đóng băng (đề xuất một file riêng)

Đề xuất file mới `docs/protocol_freeze_r1_heldout.md`, tách khỏi file freeze của repair. Nội dung:

| Mục | Giá trị đề xuất |
|---|---|
| Commit | commit có tag `protocol-freeze-r1` |
| Dataset | SWE-bench Verified, parquet đã ghim hash; held-out = 292 task theo `sha256_instance_id_first8hex_mod100_lt40_dev_v1` |
| Lọc task | D3-1 |
| Cấu hình | 9 cấu hình hiện có + `embedding`; layer và cờ **tắt** (theo kết quả phần 3 của báo cáo R1) |
| Ngân sách, đếm token | 12.000 token, `utf8_bytes_ceil_div4` |
| Config ranking | hash của `RT1_CONFIG` hiện tại |
| Metric chính (đăng ký trước; đều thuộc §13.2) | file R@1, file R@5, hàm R@5, hàm MRR, Recall@B hàm, `dependency_frontier_recall@B` (theo `F*_approx`, nếu D2-4 chọn đo) |
| Cặp so sánh chính (đăng ký trước) | graph so với baseline của §13.1, đúng câu hỏi RQ2 và tiêu chí M2: `A2+RT1 − bm25`, `A2+RT1 − embedding`, `A2+RT1 − grep`, `A2 − A1` |
| Thống kê (nguồn: plan, không phải proposal) | bootstrap ghép cặp 2.000 lần, CI95; hiệu chỉnh Holm trên các cặp chính |
| RRF (kết quả phụ) | đưa vào runner, k = 60, cố định trước; báo cáo ghi là **phân tích thêm ngoài proposal**, không dùng để trả lời RQ2 |

Với 292 task, chênh lệch nhỏ nhất phát hiện được là khoảng 0,041 (hàm R@5), 0,047 (hàm MRR), 0,058 (file R@1), theo phần 5 của báo cáo R1.

### 3.2 Quy trình chạy

1. Trước tag: R1 runner có cánh embedding và RRF; chạy trọn trên 50 task dev; test xanh.
2. Cả nhóm duyệt `docs/protocol_freeze_r1_heldout.md`, tạo tag.
3. Tạo manifest held-out **sau** tag bằng `scripts/prepare_manifest.py --split heldout --allow-heldout`; `dataset.py` ghi log mỗi lần mở held-out.
4. Người dùng chạy một lượt trong WSL (ước tính khoảng 7,5 giờ cho 292 task không bật layer, theo tốc độ 1,28 giờ / 50 task, cộng phần embedding).
5. Nếu task lỗi hạ tầng (không phải do cấu hình): chạy lại đúng task đó trên cùng commit, ghi vào báo cáo; không đổi cấu hình.
6. Báo cáo `docs/status/tv2_r1_heldout_<ngày>.md`, mỗi số kèm lệnh tái tạo.

### 3.3 Cần quyết định

| Mã | Câu hỏi | Lựa chọn | Đề xuất |
|---|---|---|---|
| D3-1 | Lọc held-out | (a) cả 292; (b) chỉ task có patch gold sửa ≥ 2 file (`min_source_files=2`, như cách chọn bộ dev; điều kiện §8.3 cuối) | ĐANG CHỜ: cần đếm trước bao nhiêu task held-out qua bộ lọc (plan O6) mà **không xem nội dung** |
| D3-2 | File freeze riêng cho R1 hay thêm mục vào file freeze hiện có | riêng / chung | riêng: file hiện có gắn với repair A0–A3 của M3 |
| D3-3 | RRF là kết quả chính hay phụ | chính / phụ | **phụ**: proposal không nói tới trộn graph với văn bản (gần nhất là "fallback to text/embedding" trong bảng rủi ro, dòng 1471); RQ2 và M2 hỏi graph so với baseline |

---

## 4. Thứ tự đề xuất

1. Duyệt spec này, trả lời D1-1…D3-3 (gồm D2-4).
2. Việc 1 (G1-a, G1-b, G1-c) làm ngay, không cần chờ ai; G1 lượt người nếu D1-1 = (b). File cho lượt người đã tạo 17/11: `~/rt1/g1/agreement_human.csv` và `agreement_human_items.md` (bản sao trong Downloads).
3. Việc 2: code và test; người dùng cài môi trường và chạy 50 task dev.
4. Việc 3: viết `protocol_freeze_r1_heldout.md`, nhóm duyệt và tag, rồi chạy held-out.
