# Ablation matrix: đo retrieval offline

Thư mục này đo nhóm metric **retrieval** của ma trận ablation ([P] §13.3) và các graph baseline ([P] §13.1), không chạy agent. Code ở đây chỉ gọi `vgar` như thư viện, không sửa `src/`. Test nằm ngoài `testpaths` của repo, chạy riêng:

```bash
python -m pytest -q -p no:cacheprovider ablation_matrix/tests
```

Kết quả ghi vào `ablation_matrix/results/` (git bỏ qua). Bảng tổng hợp đưa vào `docs/status/`.

## Các cấu hình

| Tên | Ý nghĩa | Ứng với |
|---|---|---|
| `task_trace` (R-A2) | Issue được đưa vào `G_task` (overlay theo task: frame, đường dẫn, error message, `TRACES_TO`); anchor của nó bắt đầu lượt duyệt graph | A2; §13.1 "repo graph + task trace"; cách repo đang chạy |
| `no_task_trace` (R-A1) | Không dựng `G_task`; anchor là symbol có tên trùng (rồi chứa) từ khóa của issue, như agent gọi `search_symbols` | A1; §13.1 "repo symbol graph only" |

Hai arm dùng chung `RetrievalConfig()`, cùng graph, cùng ngân sách và cách chấm điểm, nên chênh lệch chỉ đến từ `G_task`. Tên `R-A*` dùng để không nhầm với A0–A5 của nhóm (hợp đồng TV1 mục E04).

## Chạy (WSL)

```bash
python ablation_matrix/run_no_trace_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
    --out ablation_matrix/results/no_trace --allow-fallback-counter --prune --resume
```

Manifest gold do `scripts/materialize_dev_gold.py` tạo. Mỗi task tải archive tại `base_commit`, build graph một lần, chạy hai arm, ghi `tasks/<id>.json`, rồi xóa archive và cây mã nguồn. `summary.json` có trung bình từng arm và chênh lệch ghép cặp (`no_task_trace − task_trace`, CI95 bootstrap).
