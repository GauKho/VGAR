# TV2 — So sánh R1 với các bài báo theo cùng điều kiện cốt lõi (17/11/2026)

Tài liệu này kiểm tra bảng so sánh được dán vào ngày 17/11, đối chiếu với bài báo gốc, rồi tính lại số liệu của VGAR theo đúng định nghĩa chỉ số của từng bài.

- Số liệu VGAR lấy từ `~/rt1/results/r1_50` (WSL): 50 task thuộc phần dev của SWE-bench Verified, cùng các danh sách top-100 với báo cáo `tv2_r1_results_comparison_2026-11-16.md`.
- Script tính lại chỉ đọc dữ liệu, không thay đổi repo. Nó tái tạo đúng số đã báo cáo: MRR file của bm25 là 0,475 so với 0,476 trong báo cáo, Acc@k khớp bảng C.
- CI95 là bootstrap theo task, 2.000 lần lấy mẫu.

## 1. Điều kiện cốt lõi cần cố định

| # | Điều kiện | VGAR R1 hiện tại | Cần làm để so được với bài báo |
|---|---|---|---|
| C1 | Cùng tập task | 50 task dev của **Verified** | So với bảng **Verified** của CoSIL (Table III). Muốn so với LocAgent hoặc ARISE thì phải chạy trên **Lite** |
| C2 | Cùng định nghĩa chỉ số | R@k là tỉ lệ số mục gold tìm được | CoSIL và ARISE dùng **Hit@k** (ít nhất 1 gold trong top-k). LocAgent và Agentless dùng **Acc@k** (đủ mọi gold trong top-k) |
| C3 | Cùng cách lấy gold | Hàm bị patch sửa (`function_id`), loại file test | LocAgent loại các chỉnh sửa chỉ ở docstring, import, comment. ARISE gán mỗi hunk vào scope bao quanh. CoSIL không mô tả. Cần ghi rõ phần chênh này |
| C4 | Cùng tập con ở mức hàm | Bỏ task không có hàm gold (49/50) | LocAgent làm giống vậy (274/300) |
| C5 | Cùng đầu vào | Chỉ dùng `problem_statement` | Các bài cũng chỉ dùng issue. Giữ nguyên |
| C6 | Ngân sách context | 12.000 token, bytes/4 | **Không bài nào chấm localization trong một ngân sách.** Hit/Acc/MRR là chỉ số trên danh sách xếp hạng, nên ngân sách không ảnh hưởng. Recall@B không có số đối chiếu bên ngoài (Coverage của ARISE dùng 8.000 token nhưng ở mức dòng) |
| C7 | Ghi chi phí | 0 lời gọi LLM; build trung vị 8,3 s, retrieve 1–5 s | Ghi kèm backbone LLM và chi phí của từng hệ |
| C8 | Ghi cỡ mẫu và CI | n = 50, CI rộng ±0,12–0,14 | Bài báo dùng 300 hoặc 500 task. Muốn khẳng định hơn/kém thì phải chạy trên 292 task held-out sau khi đóng băng cấu hình |
| C9 | Không chọn cấu hình trên tập đánh giá | RRF (k = 60) được chọn **sau khi xem** 50 task dev. Từ commit 3f73a3a5, RRF đã có trong runner (`ablation_matrix/fusion.py`) như một phân tích phụ | Ghi RRF, và Hit@k nếu dùng, vào `docs/protocol_freeze_r1_heldout.md` trước tag `protocol-freeze-r1`. Chỉ báo cáo số held-out |

## 2. Lỗi trong bảng được dán

| Ô trong bảng dán | Thực tế (nguồn) |
|---|---|
| "1250 task", "350 task" | Là chú thích 1, 2, 3 dính vào chữ "50 task". VGAR chạy **50 task** |
| Agentless 0,583 / 0,247 / 0,427 / 0,325, xếp vào nhóm A "không LLM" | Đây là dòng **Agentless-FL** trong CoSIL Table II (**Lite**, Qwen2.5-Coder-32B). Agentless **có gọi LLM** để chọn file (bài Agentless dùng GPT-4o), nên không thuộc nhóm truy xuất tĩnh. Chỉ số là Hit@k, không phải R@k |
| ARISE-RAG "8.000 tokens" | Theo phần tóm tắt trích từ bài ARISE (chưa đối chiếu nguyên văn), dòng RAG là truy xuất file bằng BM25, không có vòng agent và **không có ngân sách**. Con số 8.000 là ngân sách gói context của chính ARISE. Các số 0,30 / 0,15 / 0,25 (R@3) / 0,18 khớp Table 3 |
| ARISE-Full 0,670 / 0,600 / 0,630 | Khớp Table 3 (Lite 300, Qwen2.5-Coder-32B). Số được trích từ bản HTML bị cắt ngắn, **cần đối chiếu PDF** trước khi dẫn |
| "40 lượt gọi tool" | Chưa kiểm chứng được. Bài có nhắc cả "T_max" và "32-step cap" |
| CoSIL 0,607 / 0,430 / 0,577 / 0,489 | CoSIL v3, Table II (Lite, 32B) ghi **0,613 / 0,433 / 0,580 / 0,493** |
| LocAgent "Function R@5 = 0,643 (Acc@5)" | Function Acc@5 = **71,90**. Số 64,27 là **NDCG@5** mức hàm (Table 11). LocAgent chạy trên 274 task Lite, chỉ số Acc |
| "RRF R@5 hàm 0,536 vượt Agentless 0,427" | **Không so được.** Bên trái là tỉ lệ recall trên 50 task Verified. Bên phải là Hit@5 trên 300 task Lite. Xem cách so đúng ở mục 3 |
| "tốc độ tức thì" | Build graph trung vị 8,3 s/task, retrieve 1–5 s. Nên viết "không gọi LLM", không viết "tức thì" |
| "G_task giúp tiệm cận các hệ phức tạp" | Mức +0,131 R@5 hàm (A2 − A1) là đúng trong nội bộ R1. Phần "tiệm cận" thì không có số nào chứng minh |

## 3. Bảng so sánh chuẩn hóa: SWE-bench Verified, chỉ số Hit@k / MRR kiểu CoSIL

Định nghĩa của CoSIL (§IV-D): "counts how often at least one bug location appears within the top N", chia cho số task. MRR tính theo vị trí của mục gold đầu tiên. Đây cũng là định nghĩa R@k của ARISE.

| Hệ | LLM | Tập task | File Hit@1 | File Hit@3 | File Hit@5 | File MRR | Hàm Hit@1 | Hàm Hit@3 | Hàm Hit@5 | Hàm MRR |
|---|---|---|---|---|---|---|---|---|---|---|
| VGAR bm25 | — | 50 dev Verified | 0,280 | 0,680 | 0,760 | 0,475 | 0,224 | 0,388 | 0,449 | 0,339 |
| VGAR neighbor | — | 50 dev Verified | 0,320 | 0,680 | 0,800 | 0,502 | 0,265 | 0,449 | 0,531 | 0,383 |
| VGAR graph `task_trace_rt1` | — | 50 dev Verified | 0,400 | 0,620 | 0,740 | 0,537 | 0,184 | 0,306 | 0,388 | 0,270 |
| VGAR RRF bm25 + neighbor (chỉ văn bản) | — | 50 dev Verified | 0,340 | 0,700 | 0,800 | 0,519 | 0,265 | 0,449 | 0,531 | 0,383 |
| **VGAR RRF graph + bm25 + neighbor** | — | 50 dev Verified | **0,480** [0,34; 0,62] | 0,680 | 0,760 | **0,617** [0,51; 0,73] | **0,347** [0,22; 0,47] | **0,510** [0,37; 0,65] | **0,571** [0,43; 0,69] | **0,445** [0,33; 0,57] |
| Agentless-FL (CoSIL T.III) | Qwen2.5-Coder-32B | 500 Verified | 0,624 | 0,784 | 0,834 | 0,709 | 0,326 | 0,460 | 0,484 | 0,394 |
| OrcaLoca (CoSIL T.III) | Qwen2.5-Coder-32B | 500 Verified | 0,612 | 0,654 | 0,654 | 0,633 | 0,254 | 0,468 | 0,486 | 0,359 |
| LocAgent (CoSIL T.III) | Qwen2.5-Coder-32B | 500 Verified | 0,686 | 0,806 | 0,816 | 0,743 | 0,250 | 0,464 | 0,530 | 0,367 |
| CoSIL (CoSIL T.III) | Qwen2.5-Coder-32B | 500 Verified | 0,640 | 0,822 | 0,864 | 0,730 | 0,446 | 0,606 | 0,650 | 0,531 |

Cách đọc (n = 50, CI rộng khoảng ±0,13):
- **Mức file:** VGAR thấp hơn rõ. File Hit@1 0,48 so với 0,61–0,69, và cận trên của CI (0,62) chỉ chạm mức thấp nhất của các hệ có LLM. Không được viết là VGAR ngang các hệ đó ở mức file.
- **Mức hàm:** RRF 3 nguồn nằm trong khoảng của các hệ LLM 32B. Hit@5 0,571 so với Agentless 0,484, LocAgent 0,530, CoSIL 0,650. MRR 0,445 so với 0,394 / 0,367 / 0,531. Cả bốn số của bài báo đều nằm trong CI của VGAR, nên với 50 task **chỉ kết luận được "cùng khoảng"**, không kết luận hơn hay kém.
- Số của CoSIL được trích từ bản HTML v3. Cần đối chiếu PDF trước khi đưa vào luận văn.

## 4. Bảng phụ: chỉ số Acc@k kiểu LocAgent (đủ mọi gold trong top-k)

Chỉ đặt cạnh số LocAgent sau khi có lượt chạy trên Lite. Bảng này để sẵn phần của VGAR.

| Hệ | File Acc@1 | File Acc@3 | File Acc@5 | Hàm Acc@5 | Hàm Acc@10 |
|---|---|---|---|---|---|
| VGAR bm25 | 0,220 | 0,600 | 0,660 | 0,347 | 0,429 |
| VGAR neighbor | 0,260 | 0,600 | 0,700 | 0,429 | 0,469 |
| VGAR graph `task_trace_rt1` | 0,360 | 0,580 | 0,700 | 0,327 | 0,388 |
| VGAR RRF 3 nguồn | 0,420 | 0,640 | 0,700 | 0,490 | 0,510 |
| *Tham khảo, Lite 274:* LocAgent BM25 | 0,387 | 0,518 | 0,617 | 0,318 | 0,369 |
| *Tham khảo, Lite 274:* CodeRankEmbed | 0,526 | 0,777 | 0,847 | 0,518 | 0,588 |
| *Tham khảo, Lite 274:* LocAgent Qwen2.5-32B(ft) | 0,759 | 0,905 | 0,927 | 0,719 | 0,770 |

Các dòng tham khảo khác tập task (Lite so với Verified). **Chưa được dùng làm kết luận.**

## 5. Cách chia nhóm đúng cho Chương 4

- **Nhóm A, không gọi LLM khi truy xuất:** các cấu hình VGAR R1; BM25 và các embedding retriever trong LocAgent Table 4 (Lite 274, Acc); dòng RAG của ARISE (Lite 300, Hit).
- **Nhóm B, pipeline cố định có gọi LLM:** Agentless / Agentless-FL.
- **Nhóm C, agent duyệt graph bằng LLM:** OrcaLoca, LocAgent, CoSIL, ARISE.

So VGAR với nhóm B và C chỉ để định vị khoảng hiệu năng, kèm cột chi phí: VGAR không tốn token LLM. Theo CoSIL Table VII, trên tập mini 50 task, CoSIL tốn khoảng 0,07–0,14 triệu token mỗi task, LocAgent 0,5–2 triệu.

## 6. Việc cần làm để có kết quả so được thật sự

1. RRF đã có trong runner. Việc còn lại là ghi nó vào file freeze của R1, đúng như spec 17/11: RRF là **kết quả phụ ngoài proposal** (D3-3), không dùng để trả lời RQ2.
2. Nếu muốn có bảng ở mục 3 cho held-out: thêm Hit@k (k = 1, 3, 5) vào metric của R1 **trước khi freeze**, bên cạnh R@k và Acc@k. Thêm sau khi xem kết quả held-out là vi phạm C9.
3. Chạy 292 task held-out của Verified: n đủ để phát hiện chênh lệch khoảng 0,05, rồi so với CoSIL Table III. Nếu chỉ chạy trên 292 task, phải ghi rõ là tập con của 500.
4. Tùy chọn: chạy trên SWE-bench Lite (300 task, hoặc 274 task theo cách lọc của LocAgent) để so với LocAgent Table 4 và ARISE Table 3. Phải đếm phần giao giữa Lite và Verified trước, vì có task chồng nhau.
5. Đối chiếu PDF của CoSIL và ARISE cho các số trong mục 3 và 4.

## Nguồn

- CoSIL: arXiv 2503.22424v3 (ASE 2025), Table II (Lite), Table III (Verified), Table VII (chi phí), §IV-D (định nghĩa Top-N).
- LocAgent: arXiv 2503.09089v2, Table 4 (Acc), Table 11 (NDCG), §5.1 (274/300 task, Acc@k = đủ mọi gold).
- ARISE: arXiv 2605.03117v2, Table 3 (Lite 300), §3.3 (ngân sách 8.000 token), §3.5 (R@k = gold xuất hiện trong top-k).
- Agentless: arXiv 2407.01489v2, Table 1–2 (GPT-4o; chọn file bằng LLM kết hợp embedding).
- Probe tính lại: `ablation_matrix/paper_metrics.py`, chạy bằng `python3 ablation_matrix/paper_metrics.py ~/rt1/results/r1_50` (WSL).
