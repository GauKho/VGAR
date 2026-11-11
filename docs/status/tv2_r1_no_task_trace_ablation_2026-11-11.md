# TV2 · R1: retrieval không có và có task trace (R-A1 vs R-A2), 11/11/2026

Code: `ablation_matrix/` (chỉ gọi `vgar`, không sửa `src/`). Spec nháp: `docs/superpowers/specs/2026-11-11-tv2-r1-retrieval-ablation-design.md`.

## Cách đo

- 50 task dev (`~/rt1/data/manifests/w10-dev-50-gold.json`), mỗi task build graph một lần tại `base_commit`, chạy hai arm trên cùng graph, cùng `RetrievalConfig()` (hash đóng băng), ngân sách 12.000 token, bộ đếm bytes/4, cùng `include` và `evaluate_graph_task`.
- `task_trace` (R-A2): issue đưa vào `G_task` (overlay theo task), anchor từ grounding. Đây là cách repo đang chạy; trên cả 50 task, kết quả khớp đúng run RT-1 `full50/default` arm `graph` (kiểm 2 task đầu, cùng mọi chỉ số).
- `no_task_trace` (R-A1): không dựng `G_task`; anchor là symbol có tên trùng rồi chứa từ khóa của issue (tối đa 50, xếp theo loại khớp rồi IDF), như agent gọi `search_symbols`. Không dùng traceback, đường dẫn, ErrorMessage, test fail hay `TRACES_TO`.
- 50/50 task SUCCEEDED ở cả hai arm; không task nào thiếu anchor.

```bash
python ablation_matrix/run_no_trace_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
    --out ~/rt1/results/no_trace50 --allow-fallback-counter --prune --resume --only ~/rt1/all50.txt
```

## Kết quả (50 task)

| Chỉ số | Có `G_task` (R-A2) | Không `G_task` (R-A1) | Chênh (R-A1 − R-A2) | CI95 | R-A1 tốt hơn / kém đi |
|---|---|---|---|---|---|
| Recall@1 file | 0,337 | 0,260 | | | |
| Recall@3 file | 0,623 | 0,490 | **−0,133** | [−0,247; −0,033] | 1 / 8 |
| Recall@5 file | 0,743 | 0,650 | −0,093 | [−0,193; 0,000] | 1 / 6 |
| Recall@10 file | 0,753 | 0,805 | +0,052 | [−0,048; +0,165] | 6 / 3 |
| Recall@3 hàm | 0,250 | 0,167 | **−0,083** | [−0,170; −0,014] | 1 / 5 |
| Recall@5 hàm | 0,338 | 0,207 | **−0,131** | [−0,225; −0,049] | 0 / 7 |
| Recall@10 hàm | 0,434 | 0,314 | **−0,120** | [−0,235; −0,010] | 3 / 9 |
| MRR file | 0,514 | 0,448 | −0,066 | [−0,142; +0,007] | 11 / 17 |
| MRR hàm | 0,253 | 0,184 | **−0,069** | [−0,132; −0,019] | 7 / 17 |
| Recall@B file (12.000 token) | 0,773 | 0,918 | **+0,145** | [+0,055; +0,245] | 8 / 0 |
| Recall@B hàm | 0,348 | 0,327 | −0,021 | [−0,094; +0,048] | 3 / 3 |
| Token của context | 11.873 | 11.964 | +91 | [−13; +236] | |

In đậm: CI95 không chứa 0.

## Nhận định

- **`G_task` giúp xếp hạng:** có task trace thì file và hàm gold lên cao hơn rõ rệt; ở mức hàm, chênh lệch có ý nghĩa ở mọi k và ở MRR. Đây là bằng chứng cho cặp A2 so với A1 của ma trận ablation (tác dụng của task trace) và cho RQ2.
- **Không có `G_task` thì context phủ rộng hơn:** Recall@B file tăng (+0,145, 8 task tốt hơn, 0 task kém đi), vì 50 anchor từ khóa rải ra nhiều file nên context 12.000 token chứa nhiều file hơn; nhưng mức hàm không tăng và thứ hạng kém đi. Nói cách khác, cách này đúng file thường hơn nhưng chỉ đúng chỗ ít hơn.
- **Quyết định cho repo chính:** giữ retrieval có `G_task` như hiện nay; không đổi code.
- Hướng có thể thử sau (không làm trong lần này): gộp anchor của hai cách (task trace trước, từ khóa sau) để giữ thứ hạng của R-A2 mà vẫn phủ rộng như R-A1. Phải đo lại vì có thể làm loãng thứ hạng.

## Giới hạn

- R-A1 là mô phỏng cách agent tìm symbol, không phải agent thật.
- Chưa có baseline văn bản (BM25, grep, embedding) và các cấu hình còn lại của spec (R-AST, R-A3); đây mới là cặp A2/A1.
- Bộ đếm token bytes/4; F\* xấp xỉ bằng file và hàm của patch gold.
- Recall theo component chưa đo (spec §4.5).
