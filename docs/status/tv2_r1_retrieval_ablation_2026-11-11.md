# TV2 · R1: ablation retrieval offline đủ cấu hình (50 task), 11/11/2026

Code: `ablation_matrix/run_r1_ablation.py` (chỉ gọi `vgar`, không sửa `src/`). Spec: `docs/superpowers/specs/2026-11-11-tv2-r1-retrieval-ablation-design.md`. Kết quả từng task: `~/rt1/results/r1_50/` (WSL), tổng hợp `summary.json`.

## Cách đo

- 50 task dev (`~/rt1/data/manifests/w10-dev-50-gold.json`), 50/50 SUCCEEDED ở cả 9 cấu hình. Mỗi task build graph một lần tại `base_commit`; mọi cấu hình được xếp hạng trước khi đọc patch gold, rồi chấm bằng cùng `score_record` (cùng gold, ngân sách 12.000 token, snippet 80 dòng, bộ đếm bytes/4).
- Cấu hình graph dùng `RetrievalConfig()` mặc định (hash đóng băng) cộng đúng các cờ ghi ở bảng; tên `R-A*` để không nhầm với A0–A5 của nhóm (hợp đồng TV1 mục E04).
- Kiểm chéo: `task_trace` và `no_task_trace` cho đúng số của lượt R-A1/R-A2 trước; `task_trace_rt1` đúng số của run RT-1 `full50/rt1_config`.
- Lượt chạy bị dừng một lần vì hết RAM ở `sympy__sympy-13480` (5 retriever cùng giữ bản chép graph). Đã sửa để mỗi lúc chỉ một retriever sống (test `test_graph_arms_keep_at_most_one_retriever_alive`, kết quả một task chạy lại giống hệt), chạy tiếp 8 task bằng `--resume`; RAM lớn nhất 5,1 GB.

```bash
python ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
    --out ~/rt1/results/r1_50 --allow-fallback-counter --prune --resume --only ~/rt1/all50.txt
```

| Tên | Ứng với | Cách lấy ứng viên |
|---|---|---|
| `bm25` | A0; §13.1 BM25 | BM25 trên chunk 80 dòng, truy vấn = issue |
| `grep` | A0; §13.1 grep/ripgrep | Đếm dòng khớp từ định danh của issue, từ hiếm nặng hơn |
| `neighbor` | A0; §13.1 file-neighbor | File issue nhắc tới, rồi theo khoảng cách thư mục; BM25 trong cùng khoảng cách |
| `no_task_trace` | A1; §13.1 repo symbol graph only | Anchor = symbol trùng tên từ khóa issue; không `G_task` |
| `task_trace` | A2; §13.1 repo graph + task trace | Anchor từ `G_task` (overlay); cách repo đang chạy |
| `a3` | A3 | `task_trace` + `use_component_dependents` + `use_trace_component` |
| `ast_no_task_trace` | §13.1 AST-only graph | Như A1 nhưng graph chỉ còn cạnh chứa (bỏ CALLS, IMPORTS, REFERENCES, CallSite) |
| `arch_no_task_trace` | §13.1 repo graph + architecture | A1 + `use_component_dependents` |
| `task_trace_rt1` | A2 + `RT1_CONFIG` | `task_trace` + `may_call_factor=0.5` |

## Trung bình (50 task)

| Cấu hình | R@1 file | R@5 file | R@5 hàm | MRR file | MRR hàm | Recall@B file | Recall@B hàm | R@1 comp. | R@5 comp. |
|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0,247 | 0,707 | 0,389 | 0,476 | 0,340 | 0,883 | 0,532 | 0,517 | 0,877 |
| grep | 0,162 | 0,548 | 0,286 | 0,376 | 0,209 | 0,735 | 0,429 | 0,367 | 0,823 |
| **neighbor** | 0,287 | 0,747 | **0,471** | 0,505 | **0,384** | 0,883 | **0,572** | 0,557 | 0,897 |
| no_task_trace (A1) | 0,260 | 0,650 | 0,207 | 0,448 | 0,184 | **0,918** | 0,327 | 0,560 | **0,920** |
| task_trace (A2) | 0,337 | 0,743 | 0,338 | 0,514 | 0,253 | 0,773 | 0,348 | 0,587 | 0,883 |
| a3 (A3) | 0,357 | **0,753** | 0,277 | 0,526 | 0,238 | 0,823 | 0,348 | **0,607** | 0,883 |
| ast_no_task_trace | 0,260 | 0,630 | 0,248 | 0,443 | 0,190 | 0,873 | 0,301 | 0,560 | 0,920 |
| arch_no_task_trace | 0,260 | 0,650 | 0,207 | 0,448 | 0,184 | 0,918 | 0,327 | 0,560 | 0,920 |
| task_trace_rt1 | **0,377** | 0,723 | 0,363 | **0,537** | 0,270 | 0,818 | 0,348 | **0,607** | 0,893 |

Recall@10 và chi phí context (token của context đã đóng gói, trung bình mỗi task; ngân sách 12.000, bộ đếm bytes/4):

| Cấu hình | R@10 file | R@10 hàm | Context token |
|---|---|---|---|
| bm25 | 0,788 | 0,495 | 11.996 |
| grep | 0,675 | 0,365 | 11.996 |
| **neighbor** | **0,828** | **0,536** | 11.996 |
| no_task_trace (A1) | 0,805 | 0,314 | 11.964 |
| task_trace (A2) | 0,753 | 0,434 | 11.873 |
| a3 (A3) | 0,783 | 0,403 | 11.974 |
| ast_no_task_trace | 0,805 | 0,334 | 11.524 |
| arch_no_task_trace | 0,805 | 0,314 | 11.966 |
| task_trace_rt1 | 0,753 | 0,434 | 11.898 |

Mọi cấu hình đều dùng gần hết ngân sách (11.524 đến 11.996 token), nên chi phí context gần như không phân biệt các cấu hình. Ở cùng mức chi phí, khác biệt nằm ở việc context chứa đúng code hay không, tức các cột Recall@B. Ở R@10, A2 thu hẹp khoảng cách hàm với BM25 (0,434 so với 0,495) nhưng vẫn kém neighbor.

## Các cặp (ứng viên − nền; CI95 bootstrap 2.000 lần; in đậm khi CI không chứa 0)

| Cặp | R@5 file | R@5 hàm | MRR hàm | Recall@B file | Recall@B hàm | R@5 comp. |
|---|---|---|---|---|---|---|
| A1 − bm25 | −0,057 [−0,20; +0,09] | **−0,182 [−0,31; −0,07]** | **−0,156** | +0,035 | **−0,205 [−0,35; −0,07]** | +0,043 |
| A1 − grep | +0,102 [−0,06; +0,26] | −0,078 | −0,025 | **+0,183 [+0,07; +0,31]** | −0,102 | +0,097 |
| A1 − neighbor | −0,097 | **−0,263 [−0,41; −0,13]** | **−0,200** | +0,035 | **−0,246** | +0,023 |
| A2 − bm25 | +0,037 [−0,07; +0,16] | −0,051 [−0,18; +0,08] | −0,087 | −0,110 [−0,22; 0,00] | **−0,183 [−0,32; −0,05]** | +0,007 |
| A2 − A1 (task trace) | +0,093 [0,00; +0,20] | **+0,131 [+0,05; +0,22]** | **+0,069** | **−0,145 [−0,25; −0,06]** | +0,021 | −0,037 |
| A3 − A2 (kiến trúc) | +0,010 | −0,061 [−0,12; 0,00] | **−0,016** | +0,050 [0,00; +0,12] | 0 | 0 |
| A1 − AST-only (cạnh gọi/import) | +0,020 | −0,041 | **−0,005** | +0,045 [0,00; +0,11] | +0,026 | 0 |
| A1+arch − A1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A2+RT1 − A2 | −0,020 | +0,024 [0,00; +0,07] | +0,017 | +0,045 [0,00; +0,11] | 0 | +0,010 |

## Nhận định (RQ2, milestone M2)

- **Graph chưa vượt baseline văn bản trên bộ dev.** File-neighbor và BM25 tốt hơn graph ở mức hàm (Recall@5 hàm, MRR hàm, Recall@B hàm). Ở mức file, A2 và A3 ngang BM25/neighbor (chênh nhỏ, CI chứa 0). Graph chỉ thắng grep, và thắng ở Recall@B file khi không dùng `G_task`. Tiêu chí M2 ("recall cao hơn grep/BM25/embedding", [P] dòng 1408) **chưa đạt** trên 50 task dev; embedding chưa đo.
- **Ở mức component, graph không kém:** A1 0,920 và A3 có R@1 component 0,607, cao nhất bảng; nhưng chênh với BM25/neighbor không có ý nghĩa thống kê.
- **Task trace (`G_task`) là tầng có tác dụng rõ nhất:** A2 so với A1 tăng Recall@5 hàm +0,131 và MRR hàm, đổi lại context phủ ít file hơn (Recall@B file −0,145).
- **Kiến trúc (`G_arch`) gần như không giúp:** A3 so với A2 tăng nhẹ R@1 file và Recall@B file nhưng giảm R@5 và MRR hàm; A1+arch giống hệt A1 vì 50 anchor từ khóa đã phủ các hàm gọi.
- **Cạnh gọi/import so với AST-only:** chỉ tăng nhẹ ở mức file; ở mức hàm còn kém một chút.
- `RT1_CONFIG` (MAY_CALL) cải thiện nhỏ ở R@1 file, MRR và Recall@B file như báo cáo RT-1.

## Giới hạn

- Baseline văn bản xếp hạng trên mọi file kể cả file test (đúng như pipeline BM25 sẵn có); nhóm graph bỏ file test. Baseline văn bản chịu bất lợi này mà vẫn tốt hơn ở mức hàm.
- A1 là mô phỏng cách agent tìm symbol; không có agent default exploration và embedding (chờ nhóm quyết).
- Bộ đếm token bytes/4; F\* xấp xỉ bằng file và hàm của patch gold.
- Trên 50 task dev; 25 task trong số này từng dùng để chọn `RT1_CONFIG`, nên dòng `task_trace_rt1` hơi lạc quan.
- Tên `R-A*` ↔ A0–A3 cần nhóm xác nhận theo E04.

## Phân tích: các task file-neighbor thắng graph (`task_trace`, Recall@5 hàm)

Script: `~/rt1/nb_vs_graph.py`, `~/rt1/nb_vs_graph2.py` (WSL, chỉ đọc `tasks/*.json`). Neighbor thắng 10 task, graph thắng 3, hòa 37. Ở cả 10 task neighbor thắng, graph **vẫn có file gold trong top-5** (R@5 file = 1,0). Graph không thua vì đi sai chỗ; nó thua vì xếp hạng bên trong vùng đúng.

| Nguyên nhân | Task | Dấu hiệu |
|---|---|---|
| Sai mức chi tiết: top-5 là class/file chứa hàm gold, không phải hàm | requests-1724, sklearn-10297, sklearn-11310, sklearn-13135, sympy-12481 | Ví dụ sympy-12481: hạng 1 là class `Permutation`, còn `Permutation.__new__` không có trong top-100. Ví dụ sklearn-13135: hạng 1 là class `KBinsDiscretizer`, còn `.fit` không có. Top-5 của graph có 23% class, 18% file và 8% module; top-5 của neighbor chỉ có method/function/module chunk |
| Anchor ngập, độ tin cậy bằng nhau | sklearn-10297 (671 anchor, 663 ở mức 0,5), sklearn-11310 (290 anchor, phần lớn là `fit` ở 0,45), sklearn-13135 (355), django-11087 (198), astropy-13977 (146) | Số anchor trung vị: 88,5 ở task thua, 29 ở các task khác |
| Traceback: các frame ngoài cùng chiếm top | django-11087, requests-1724 | Mọi frame cùng 0,95, nên `run_from_argv` và `execute` (django), `adapters.send` (requests) đứng trước hàm gold `Collector.collect` / `Session.request` |
| Trùng tên | xarray-6461 | `xr.where` neo vào `duck_array_ops.where` (0,8), không vào `computation.where` |
| Anchor từ test/doc | pylint-7277 (13/22 anchor), pytest-7236 | Tỉ lệ anchor nhiễu ở task thua không cao hơn task khác (0,26 so với 0,33), nên đây không phải nguyên nhân phân biệt |

Trên cả 50 task, hàm gold của `task_trace` nằm trong top-100 nhưng ở hạng > 5 tại 17 task, và không có trong top-100 tại 19 task. Neighbor có lợi khi issue nêu thẳng đường dẫn file: 6/10 task neighbor thắng có file gold trong `mentioned_files`, và BM25 chunk 80 dòng rơi trúng thân hàm.

Hướng sửa (chưa làm, cần spec riêng vì đụng `src/vgar/graph/retrieval.py`): (1) khi class/file lọt top, bung ra các method con và xếp theo độ giống issue; (2) giảm trọng số anchor có tên phổ biến (IDF) hoặc giới hạn số anchor cùng mức tin cậy; (3) với traceback, ưu tiên frame trong repo khớp từ khóa issue thay vì cho mọi frame cùng 0,95.
