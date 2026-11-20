# TV2 · R1: baseline embedding và `dependency_frontier_recall@B` (50 task dev), 17/11/2026

> Plan 2026-11-17, Task 8. Proposal §13.1 (baseline "embedding search"), §13.2 R1 (dòng 1311–1317: `dependency_frontier_recall@B`).
> Bổ sung cho `tv2_r1_all_numbers_2026-11-16.md`; 9 cấu hình cũ không đổi (xem "Kiểm tra lượt chạy").

## Lượt chạy

- **Dữ liệu:** 50 task dev SWE-bench Verified (`~/rt1/data/manifests/w10-dev-50-gold.json`, `manifest_hash` `sha256:48b65e9b…`), chỉ `problem_statement`, ngân sách 12.000 token (UTF-8 bytes/4).
- **Kết quả gốc (WSL):** `~/rt1/results/r1_emb50_t1024` (`summary.json`, `tasks/*.json`), log `~/rt1/r1_emb50_t1024.log`. 50/50 SUCCEEDED.
- **Model:** `nomic-ai/CodeRankEmbed`, revision `3c4b60807d71f79b43f3c4363786d9493691f8b1`; tiền tố truy vấn `Represent this query for searching relevant code: `; **mỗi chunk và truy vấn cắt ở 1024 token của model**; batch 8; GPU RTX 4050 6 GB.
- **Môi trường:** torch 2.5.1+cu121, transformers 4.57.6, sentence-transformers 5.7.0 (`transformers` 5.x không chạy với torch 2.5.1).
- **Chunk:** cùng chunk 80 dòng (chồng lấn 16) với BM25; xếp theo cosine giữa issue và chunk, trên toàn corpus.
- **Lượt hỏng trước đó:** `~/rt1/results/r1_emb50` (không giới hạn token, batch 32) hết bộ nhớ GPU ở 35/50 task; không dùng số của lượt này.

## Kiểm tra lượt chạy

| Kiểm tra | Kết quả |
|---|---|
| 9 cấu hình cũ trùng `r1_50` | 450/450 `rank_hash` (9 cấu hình × 50 task) trùng; 153/153 ô trung bình trùng |
| Corpus của embedding = corpus của BM25 | `corpus_hash` trùng 50/50 task; số chunk của embedding = số chunk của BM25 ở 50/50 task |
| Model và cấu hình được ghi lại | `summary.json` khóa `embedding`: model, revision, tiền tố, `max_tokens` 1024 |
| Nhãn hàm | 0/50 task có nhãn hàm chưa đủ; 49 task có gold mức hàm |

## Bảng chính (trung bình trên task)

| Cấu hình | R@1 file | R@5 file | R@10 file | R@1 hàm | R@5 hàm | R@10 hàm | MRR file | MRR hàm | gold file trong B | gold hàm trong B | frontier trong B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0,247 | 0,707 | 0,788 | 0,181 | 0,389 | 0,495 | 0,476 | 0,340 | 0,883 | 0,532 | 0,360 |
| grep | 0,162 | 0,548 | 0,675 | 0,069 | 0,286 | 0,365 | 0,376 | 0,209 | 0,735 | 0,429 | 0,319 |
| neighbor | 0,287 | **0,747** | 0,828 | 0,222 | 0,471 | 0,536 | 0,505 | 0,384 | 0,883 | 0,572 | 0,384 |
| **embedding** | **0,412** | 0,703 | **0,843** | **0,295** | **0,478** | **0,592** | **0,598** | **0,425** | **0,970** | **0,641** | **0,440** |
| no_task_trace (A1) | 0,260 | 0,650 | 0,805 | 0,112 | 0,207 | 0,314 | 0,448 | 0,184 | 0,918 | 0,327 | 0,328 |
| task_trace (A2) | 0,337 | 0,743 | 0,753 | 0,137 | 0,338 | 0,434 | 0,514 | 0,253 | 0,773 | 0,348 | 0,341 |
| task_trace_rt1 | 0,377 | 0,723 | 0,753 | 0,147 | 0,363 | 0,434 | 0,537 | 0,270 | 0,818 | 0,348 | 0,344 |

"trong B" = tỉ lệ gold nằm trong context đóng gói theo ngân sách 12.000 token (`packed_*_in_context`). Các cấu hình graph khác (frontier trong B): `a3` 0,339; `ast_no_task_trace` 0,316; `arch_no_task_trace` 0,328.

## `dependency_frontier_recall@B` (theo `F*_approx`)

- **Định nghĩa dùng ở đây:** `F*_approx` = hàm gold cộng mọi hàm của repo có tên ngắn xuất hiện như token NAME trên dòng được thêm vào file nguồn của patch gold, và có đúng một định nghĩa trong corpus (`src/vgar/evaluation/retrieval/frontier.py`). Đây là **xấp xỉ của `F*`** ở proposal §8.2, không phải `F*` đầy đủ.
- 50/50 task có `F*_approx`; trung bình thêm 1,18 hàm ngoài gold.
- **Kết quả:** embedding 0,440 là cao nhất; các cấu hình graph 0,316–0,344; bm25 0,360.

## So sánh từng cặp (CI95 bootstrap ghép cặp; nhóm chính hiệu chỉnh Holm trên 24 phép so)

Nhóm chính (`primary`, đăng ký trước): 4 cặp × 6 metric = 24, không thiếu ô nào. In đậm khi p sau Holm < 0,05.

| Cặp | Metric | Chênh | CI95 | p | p Holm |
|---|---|---|---|---|---|
| task_trace_rt1 − embedding | R@1 file | −0,035 | [−0,235; +0,155] | 0,750 | 1,000 |
| task_trace_rt1 − embedding | R@5 file | +0,020 | [−0,150; +0,180] | 0,848 | 1,000 |
| task_trace_rt1 − embedding | R@5 hàm | −0,116 | [−0,259; +0,041] | 0,132 | 1,000 |
| task_trace_rt1 − embedding | MRR hàm | −0,155 | [−0,288; −0,020] | 0,029 | 0,522 |
| task_trace_rt1 − embedding | **gold hàm trong B** | **−0,293** | [−0,437; −0,143] | 0,002 | **0,046** |
| task_trace_rt1 − embedding | frontier trong B | −0,096 | [−0,211; +0,012] | 0,084 | 1,000 |
| task_trace_rt1 − bm25 | R@1 file | +0,130 | [−0,050; +0,300] | 0,178 | 1,000 |
| task_trace_rt1 − bm25 | gold hàm trong B | −0,183 | [−0,322; −0,051] | 0,008 | 0,160 |
| task_trace_rt1 − bm25 | frontier trong B | −0,016 | [−0,132; +0,098] | 0,819 | 1,000 |
| task_trace_rt1 − grep | R@5 file | +0,175 | [+0,055; +0,300] | 0,003 | 0,066 |
| task_trace − no_task_trace | **R@5 hàm** | **+0,131** | [+0,049; +0,224] | 0,001 | **0,024** |
| task_trace − no_task_trace | MRR hàm | +0,069 | [+0,017; +0,134] | 0,003 | 0,066 |

Các ô còn lại của nhóm chính có p Holm = 1,000 (số gốc: `summary.json`, khóa `primary`).

Cặp phụ với embedding (không thuộc nhóm chính):

| Cặp | R@1 file | R@5 hàm | MRR hàm | frontier trong B |
|---|---|---|---|---|
| no_task_trace − embedding | −0,152 [−0,317; +0,013] | −0,271 [−0,434; −0,096] | −0,241 [−0,377; −0,094] | −0,113 [−0,242; +0,009] |
| task_trace − embedding | −0,075 [−0,270; +0,115] | −0,140 [−0,286; +0,017] | −0,172 [−0,308; −0,031] | −0,099 [−0,213; +0,009] |

## RRF (phân tích thêm ngoài proposal)

k = 60, không tinh chỉnh; mức file theo đường dẫn, mức hàm theo `function_id`.

| Bản trộn | R@1 file | R@5 file | R@5 hàm | R@10 hàm | MRR hàm |
|---|---|---|---|---|---|
| bm25 + neighbor | 0,307 | 0,747 | 0,471 | 0,536 | 0,383 |
| graph + bm25 + neighbor | 0,447 | 0,728 | 0,536 | 0,572 | 0,445 |
| embedding + bm25 | 0,442 | 0,768 | 0,543 | 0,604 | 0,428 |
| graph + embedding | 0,447 | 0,768 | 0,546 | 0,618 | 0,424 |

| So sánh | R@1 file | R@5 file | R@5 hàm | MRR hàm |
|---|---|---|---|---|
| graph+bm25+neighbor − bm25+neighbor | **+0,140 [+0,06; +0,24]** | −0,018 [−0,10; +0,06] | **+0,065 [+0,004; +0,14]** | +0,062 [−0,02; +0,15] |
| graph+embedding − embedding+bm25 | +0,005 [−0,14; +0,15] | 0,000 [−0,09; +0,10] | +0,003 [−0,08; +0,08] | −0,004 [−0,10; +0,10] |

Số RRF cũ (graph+bm25+neighbor 0,447 / 0,536 / 0,445; chênh +0,140) trùng phần 4 của `tv2_r1_all_numbers_2026-11-16.md`.

## Cách đọc

- **Embedding là cấu hình đơn mạnh nhất** trên gần mọi metric (trừ R@5 file, nơi neighbor 0,747 nhỉnh hơn 0,703).
- **Graph phục vụ (`task_trace_rt1`) không hơn embedding hay BM25 có ý nghĩa thống kê.** Sau Holm, embedding hơn graph ở "gold hàm trong B" (−0,293, p Holm 0,046); các ô khác không có ý nghĩa.
- **Task trace có ích trong graph:** A2 hơn A1 ở R@5 hàm (+0,131, p Holm 0,024).
- **Khi đã có embedding, graph không thêm gì trong bản trộn:** graph+embedding ≈ embedding+bm25 (mọi chênh ≈ 0). Phần đóng góp +0,140 R@1 file của graph chỉ thấy khi trộn với bm25+neighbor.
- **Theo milestone M2 của proposal** ("improve gold file/function recall over grep/BM25/embedding"): trên 50 task dev, graph hơn grep nhưng **không hơn BM25 và embedding**. Đây là số dev; kết luận cuối dựa vào lượt held-out.

## Giới hạn

- Embedding **cắt mỗi chunk ở 1024 token**, BM25 đọc toàn chunk; chưa đếm số chunk bị cắt.
- `F*_approx` vẫn lấy tên trên dòng nằm giữa docstring nhiều dòng (mỗi dòng được tách token riêng); trên 12 task đo được, 2/29 hàm của `F*_approx` đến từ đó.
- 25/50 task từng dùng để chọn `RT1_CONFIG`.
- Recall@B của bản trộn RRF chưa đo.
- Baseline "agent default exploration" của §13.1 chưa có (D2-2, đề nghị TV1).

## Tái tạo

```bash
R=/mnt/d/kltn/vgar_mcp_mvp_demo
cd ~/rt1
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
  --out ~/rt1/results/r1_emb50_t1024 --allow-fallback-counter --prune \
  --embedding-model nomic-ai/CodeRankEmbed --embedding-revision 3c4b60807d71f79b43f3c4363786d9493691f8b1 \
  --embedding-max-tokens 1024 --embedding-batch-size 8 \
  --embedding-cache ~/rt1/emb_cache 2>&1 | tee ~/rt1/r1_emb50_t1024.log
```

_Mọi số trong báo cáo được đọc trực tiếp từ `~/rt1/results/r1_emb50_t1024/summary.json` ngày 17/11/2026._
