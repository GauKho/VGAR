# TV2 · R1 full layer (tree-sitter-graph + Joern + JARVIS) so với R1 ngày 11/11 (50 task), 16/11/2026

Kết quả từng task: `~/rt1/results/r1_full50/` (WSL). So sánh theo cặp: `~/rt1/results/r1_full50/compare_vs_r1_50.json`, script `~/rt1/compare_full50.py`. Nền so sánh: `~/rt1/results/r1_50/` (báo cáo `docs/status/tv2_r1_retrieval_ablation_2026-11-11.md`).

## Kết luận

- **Bật đủ layer không làm retrieval tốt hơn.** Không cấu hình graph nào tăng được metric nào có ý nghĩa thống kê. Hai thay đổi có CI95 không chứa 0 đều là **giảm** và rất nhỏ: MRR hàm của `task_trace` giảm 0,004 và của `task_trace_rt1` giảm 0,012.
- **Code thay đổi từ 11/11 không đóng góp gì vào chênh lệch.** Lượt `r1_now50` (code hiện tại, không layer) cho ranking giống hệt `r1_50` ở cả 9 arm × 50 task (mục "Giới hạn").
- **Cờ `use_variable_references` không có ích trên bộ này.** Arm `task_trace` (arm duy nhất bật cờ) có R@5 hàm giảm từ 0,338 xuống 0,311 (−0,027, CI95 [−0,075; 0]): 0 task thắng, 2 task thua.
- **Chi phí tăng nhiều.** Thời gian build graph tăng 16 lần (trung vị). Tổng thời gian 50 task tăng từ 1,3 giờ lên 5,6 giờ. Số cạnh tăng 4,8 lần (trung vị).
- Kết quả này khớp với nhận xét của R1 ngày 11/11: thêm cạnh làm loãng thứ hạng hàm. Khuyến nghị: **giữ các layer và cờ context tắt mặc định trong retrieval**. Các layer vẫn có giá trị cho impact (cờ A/B, đo I1) và cho agent tra cứu, nhưng không phải cho xếp hạng context.
- Lượt chạy này phát hiện và đã sửa **một lỗi thật** trong adapter G_code (xem mục "Lỗi tìm được").

## Cách đo

- Cùng 50 task dev, cùng manifest (`manifest_hash` giống nhau), cùng ngân sách 12.000 token, cùng bộ đếm bytes/4, cùng 9 cấu hình như R1 ngày 11/11.
- Graph được build với tree-sitter-graph (layer 1), JARVIS (layer 2, Docker) và Joern (layer 3, Docker). SCIP và LSP vẫn tắt như lượt 11/11.
- Cờ `use_variable_references` chỉ áp lên arm `task_trace`. 8 arm graph còn lại khác lượt 11/11 ở graph (do các layer) và ở code đã thay đổi từ 11/11 (`builder_hash` khác, xem mục "Giới hạn").

```bash
LAYERS="--tsg-executable $HOME/tsg/bin/tree-sitter-graph --tsg-tree-sitter-dir $HOME/tsg/config --joern --enable-jarvis"
python ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
    --out ~/rt1/results/r1_full50 --allow-fallback-counter --prune --resume --only ~/rt1/all50.txt \
    $LAYERS --use-variable-references
python3 ~/rt1/compare_full50.py
```

Phiên bản công cụ: tree-sitter-graph 0.12.0 (build trong WSL bằng cargo 1.93), grammar tree-sitter-python v0.23.6, image `vgar/jarvis-analyzer:v1.0`, Joern image mặc định của `joern_runner`. Timeout: Joern 900 s, JARVIS 120 s (mặc định).

### Quá trình chạy

- Lượt đầu mất 11 task vì WSL không phân giải được tên miền GitHub (`Temporary failure in name resolution` khi tải archive repo). Lượt đó cũng bị kill vì hết RAM ở `sympy__sympy-13031` (6,2 GB, trong khi WSL chỉ có 7,8 GB). Đã sửa bằng `.wslconfig` (`memory=12GB`, `swap=8GB`, `dnsTunneling=true`), xóa file của các task FAILED rồi chạy tiếp bằng `--resume`.
- Một task bị Joern lỗi vì Docker Desktop chưa khởi động lại sau `wsl --shutdown`. Task đó đã bị xóa và chạy lại.
- `matplotlib__matplotlib-23476` FAILED vì lỗi code (mục dưới). Sau khi sửa, task này được chạy lại và SUCCEEDED.
- Kết quả cuối: **50/50 SUCCEEDED**.

### Trạng thái từng layer (ghi trong `layers_and_flags.layer_status` của mỗi task)

| Layer | ready | failed | Lý do failed |
|---|---|---|---|
| tree-sitter-graph | 50 | 0 | (không có) |
| Joern | 49 | 1 | `sympy__sympy-13480`: Joern chạy quá 900 s |
| JARVIS | 41 | 9 | JARVIS tự crash trên pylint-6386, 7080, 7277 (`'NoneType' object has no attribute 'add_def'`) và sphinx-10673, 11510 (`'str' object has no attribute 'get_ns'`); quá 120 s trên sympy-11618, 12481, 13031, 13480 |

Task có layer failed vẫn có graph dùng được, chỉ thiếu layer đó. Các lỗi JARVIS là lỗi của chính công cụ trên code của repo, nên chạy lại vẫn cho kết quả như cũ.

## Kiểm tra chéo

- Ba baseline văn bản (`bm25`, `grep`, `neighbor`) không đọc graph. `rank_hash` của chúng giống hệt lượt 11/11 ở cả 50/50 task, và mọi metric đều trùng. Điều này cho thấy dữ liệu task, gold và cách chấm không đổi giữa hai lượt.
- `ast_no_task_trace` chỉ giữ cạnh chứa, nên các layer không tác động tới nó. `rank_hash` của arm này cũng giống hệt ở 50/50 task.
- Ranking của các arm graph còn lại **có thay đổi** (số task có `rank_hash` khác: `task_trace` 45, `no_task_trace`, `a3`, `arch_no_task_trace` mỗi arm 41, `task_trace_rt1` 36). Nhưng thay đổi chủ yếu nằm dưới top-10, nên metric gần như không đổi.

## Trung bình (50 task; hàm: 49 task có gold hàm)

Mỗi ô ghi `r1_50 → full`.

| Cấu hình | R@1 file | R@5 file | R@5 hàm | R@10 hàm | MRR file | MRR hàm | Recall@B file | Recall@B hàm | Context token |
|---|---|---|---|---|---|---|---|---|---|
| no_task_trace (A1) | 0,260 → 0,260 | 0,650 → 0,650 | 0,207 → 0,207 | 0,314 → 0,314 | 0,448 → 0,448 | 0,184 → 0,184 | 0,918 → 0,918 | 0,327 → 0,327 | 11.964 → 11.952 |
| task_trace (A2, có cờ) | 0,337 → 0,337 | 0,743 → 0,733 | 0,338 → **0,311** | 0,434 → 0,424 | 0,514 → 0,509 | 0,253 → 0,250 | 0,773 → 0,773 | 0,348 → 0,328 | 11.873 → 11.902 |
| a3 (A3) | 0,357 → 0,357 | 0,753 → 0,733 | 0,277 → 0,277 | 0,403 → 0,403 | 0,526 → 0,526 | 0,238 → 0,236 | 0,823 → 0,803 | 0,348 → 0,328 | 11.974 → 11.970 |
| ast_no_task_trace | 0,260 → 0,260 | 0,630 → 0,630 | 0,248 → 0,248 | 0,334 → 0,334 | 0,443 → 0,443 | 0,190 → 0,190 | 0,873 → 0,873 | 0,301 → 0,301 | 11.524 → 11.524 |
| arch_no_task_trace | 0,260 → 0,260 | 0,650 → 0,650 | 0,207 → 0,207 | 0,314 → 0,314 | 0,448 → 0,448 | 0,184 → 0,184 | 0,918 → 0,918 | 0,327 → 0,327 | 11.966 → 11.982 |
| task_trace_rt1 | 0,377 → 0,377 | 0,723 → 0,723 | 0,363 → 0,363 | 0,434 → 0,434 | 0,537 → 0,539 | 0,270 → 0,259 | 0,818 → 0,818 | 0,348 → 0,328 | 11.898 → 11.886 |

Baseline văn bản không đổi: neighbor vẫn đứng đầu ở R@5 hàm (0,471) và MRR hàm (0,384). Khoảng cách giữa graph và text ở cấp hàm vẫn như ngày 11/11.

## Các cặp (full − r1_50; CI95 bootstrap 2.000 lần, seed 7; in đậm khi CI không chứa 0)

Chỉ liệt kê các metric có ít nhất một task thay đổi. Mọi metric khác của mọi arm đều có delta đúng bằng 0.

| Cấu hình | Metric | Delta | CI95 | Thắng / thua |
|---|---|---|---|---|
| task_trace | R@5 file | −0,010 | [−0,060; 0,030] | 1 / 1 |
| task_trace | R@10 file | +0,020 | [0,000; 0,060] | 1 / 0 |
| task_trace | R@5 hàm | −0,027 | [−0,075; 0,000] | 0 / 2 |
| task_trace | R@10 hàm | −0,010 | [−0,031; 0,000] | 0 / 1 |
| task_trace | MRR hàm | **−0,004** | [−0,008; −0,001] | 3 / 11 |
| task_trace | Recall@B hàm | −0,020 | [−0,061; 0,000] | 0 / 1 |
| task_trace | Context token | **+28** | [+3; +68] | 22 / 19 |
| a3 | R@5 file, Recall@B file, Recall@B hàm | −0,020 mỗi metric | [−0,06; 0] | 0 / 1 |
| a3 | MRR hàm | −0,001 | [−0,003; −0,000] | 2 / 7 |
| task_trace_rt1 | MRR file | +0,002 | [0,000; 0,005] | 2 / 0 |
| task_trace_rt1 | MRR hàm | **−0,012** | [−0,034; −0,000] | 0 / 5 |
| task_trace_rt1 | Recall@B hàm | −0,020 | [−0,061; 0,000] | 0 / 1 |
| no_task_trace, arch_no_task_trace | MRR hàm | −0,001 | chứa 0 | 3–4 / 4 |

Hai task mà `task_trace` mất R@5 hàm là `pydata__xarray-4629` (1,0 → 0,0) và `pydata__xarray-6992` (0,67 → 0,33). Ở cả hai, top-3 giữ nguyên. Một hàm mới chen vào hạng 4 hoặc 6 (`xarray/core/utils.py`, `xarray/core/variable.py`) và đẩy hàm gold ra khỏi top-5 hàm. `task_trace_rt1` cũng chạy trên graph có layer nhưng không bật cờ, và R@5 hàm của nó không đổi ở task nào. Vì vậy hai lần thua này nhiều khả năng do cờ `use_variable_references`, không phải do layer. Kết luận này chưa chắc chắn hoàn toàn, vì `task_trace_rt1` còn khác `task_trace` ở `may_call_factor`.

## Chi phí

| | r1_50 | full | Tỉ lệ (trung vị theo task) |
|---|---|---|---|
| Node trung bình | 88.178 | 213.710 | 2,8× |
| Cạnh trung bình | 138.106 | 556.935 | 4,8× |
| Build graph trung bình | 12,7 s | 186,5 s | 16× |
| Tổng thời gian 50 task | 1,28 giờ | 5,61 giờ | |
| Task lâu nhất | | 2.082 s (`sympy__sympy-13480`) | |
| RAM | đỉnh 5,1 GB | > 6,2 GB với sympy (bị OOM khi WSL chỉ có 7,8 GB) | |

Context token gần như không đổi (mọi arm vẫn dùng gần hết 12.000), nên chi phí phía model không đổi. Toàn bộ chi phí tăng thêm nằm ở bước build graph.

## Lỗi tìm được

`matplotlib__matplotlib-23476` FAILED với `GraphValidationError: nodes[135351].name must be a non-empty string`.

- **Nguyên nhân:** `lib/matplotlib/axis.py:1836` có f-string `f"{ticklabels:=} must be a sequence"`. Python chấp nhận cú pháp này (format spec `=`), nhưng tree-sitter-python hiểu nhầm `:=` là walrus thiếu vế phải. Khi tự sửa lỗi cú pháp, tree-sitter chèn vào một node `identifier` **MISSING**: rỗng, rộng 0 ký tự, không có thật trong source. `function_identifiers` (`src/vgar/graph/code_graph.py`) lấy luôn node đó và tạo ra một Identifier tên rỗng.
- **Sửa:** bỏ qua các node `is_missing`. Test `test_missing_identifier_from_error_recovery_is_skipped` (`tests/test_code_graph.py`) fail trước khi sửa và pass sau khi sửa. Build lại graph repo thật với Joern: ít hơn đúng 1 node, không còn node tên rỗng (`~/rt1/debug/empty_name.py`).
- **Phạm vi:** lỗi này làm build graph thất bại ở mọi repo có cú pháp tương tự khi bật Joern, kể cả trong `build_or_update_graph` của MCP server, không riêng R1.

Lượt chạy này cũng dùng tính năng mới thêm ngày 15/11: R1 ghi `layer_status` cho từng task. Nhờ đó các layer failed ở bảng trên mới thấy được. Trước đó, một task thiếu layer vẫn chỉ hiện SUCCEEDED.

## Giới hạn

- ~~Code khác giữa hai lượt.~~ **Đã loại trừ** bằng lượt `r1_now50` (code hiện tại, không layer, không cờ; 50/50 SUCCEEDED; 1,32 giờ). So với `r1_50`, `rank_hash` của cả 9 arm giống hệt ở 50/50 task, graph có cùng số node và cạnh, mọi metric bằng nhau. Code thay đổi từ 11/11 không ảnh hưởng tới retrieval khi tắt layer, nên mọi chênh lệch ở trên đều do layer + cờ. (`python3 ~/rt1/compare_full50.py r1_50 r1_now50`; so `r1_now50` với `r1_full50` cho đúng các số ở bảng trên.)
- **Chưa tách được tác dụng của cờ.** Cờ `use_variable_references` chỉ được đo cùng lúc với các layer. Để tách, cần chạy thêm một lượt full layer không bật cờ (khoảng 5,6 giờ), như cách đo trong `layers_in_build_measurement_guide.md` mục 4.
- **Một số task thiếu layer.** 9 task thiếu JARVIS và 1 task thiếu Joern, như bảng trạng thái ở trên.
- **Chưa đo hết các layer.** SCIP và LSP vẫn tắt. Layer 4 (GraphDiff, `--history`) cần repo có lịch sử git, mà `~/rt1` chỉ có cây mã. Layer 5 (Daikon) không phải layer retrieval.
- **Chỉ có tập dev.** Đây là kết quả trên 50 task dev; tập held-out chưa được mở.
