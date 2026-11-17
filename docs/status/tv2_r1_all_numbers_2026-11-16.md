# TV2 · R1: toàn bộ số liệu retrieval (50 task dev), 16/11/2026

Tổng hợp mọi số liệu retrieval hiện có cho RQ2, kèm cách đọc. Không có lượt chạy mới trong báo cáo này. Số liệu được tính lại từ kết quả từng task đã lưu.

- **Dữ liệu:** 50 task dev của SWE-bench Verified (`~/rt1/data/manifests/w10-dev-50-gold.json`), 12 repo; 49 task có gold mức hàm.
- **Truy vấn:** chỉ `problem_statement`, không có hint và không có gold.
- **Ngân sách:** 12.000 token, đếm bằng UTF-8 bytes/4. Mỗi mục kèm snippet tối đa 80 dòng.
- **Số liệu là trung bình trên các task.** CI95 dùng bootstrap ghép cặp 2.000 lần.
- **Kết quả gốc (WSL):** `~/rt1/results/r1_50`, `r1_now50`, `r1_full50_noflag`, `r1_full50`. Mỗi thư mục có `tasks/*.json` và `summary.json`; các file `compare_vs_*.json` nằm trong thư mục của lượt ứng viên.
- **Báo cáo liên quan:** `tv2_r1_retrieval_ablation_2026-11-11.md` (R1 gốc), `tv2_r1_full_layers_2026-11-16.md` (bật layer).
- Lượt `r1_now50` (code hiện tại, không layer) cho thứ hạng giống hệt `r1_50` ở cả 9 cấu hình × 50 task, nên Phần 1 cũng là số của code hiện tại.

**Tên cấu hình**

| Tên | Ứng với | Cách lấy ứng viên |
|---|---|---|
| `bm25` | Baseline §13.1 | BM25 trên chunk 80 dòng (chồng lấn 16 dòng), k1 = 1,2, b = 0,75 |
| `grep` | Baseline §13.1 | Đếm dòng khớp định danh trong issue; từ hiếm nặng hơn |
| `neighbor` | Baseline §13.1 | File được issue nhắc tới, rồi theo khoảng cách thư mục; BM25 khi bằng khoảng cách |
| `no_task_trace` | A1: repo symbol graph only | Anchor theo tên symbol, không dùng `G_task` |
| `task_trace` | A2: repo graph + task trace | Anchor từ overlay `G_task` |
| `a3` | A3 | A2 + component phụ thuộc + trace component |
| `ast_no_task_trace` | AST-only graph | Như A1 nhưng chỉ giữ cạnh chứa |
| `arch_no_task_trace` | repo graph + architecture | A1 + component phụ thuộc |
| `task_trace_rt1` | A2 + `RT1_CONFIG` | A2 + `may_call_factor=0.5` |

---

## Phần 1. R1 đầy đủ: 9 cấu hình, không bật layer (`r1_50`)

### A. Mức file

| Cấu hình | R@1 | R@3 | R@5 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|
| bm25 | 0,247 | 0,632 | 0,707 | 0,788 | 0,840 | 0,476 |
| grep | 0,162 | 0,508 | 0,548 | 0,675 | 0,765 | 0,376 |
| neighbor | 0,287 | 0,632 | 0,747 | 0,828 | 0,880 | 0,505 |
| no_task_trace | 0,260 | 0,490 | 0,650 | 0,805 | 0,873 | 0,448 |
| task_trace | 0,337 | 0,623 | 0,743 | 0,753 | 0,773 | 0,514 |
| a3 | 0,357 | 0,583 | 0,753 | 0,783 | 0,803 | 0,526 |
| ast_no_task_trace | 0,260 | 0,490 | 0,630 | 0,805 | 0,853 | 0,443 |
| arch_no_task_trace | 0,260 | 0,490 | 0,650 | 0,805 | 0,873 | 0,448 |
| task_trace_rt1 | **0,377** | 0,603 | 0,723 | 0,753 | 0,798 | **0,537** |

**Cách đọc:**
- R@k là tỉ lệ file mà patch gold sửa nằm trong k kết quả đầu; MRR = 1 / hạng của file gold đầu tiên.
- Graph đặt đúng file ở hạng 1 tốt nhất (`task_trace_rt1` R@1 0,377 so với BM25 0,247).
- Ở top-5, các hệ gần như ngang nhau.
- Ở top-10/20, `task_trace` kém neighbor, vì graph chỉ giữ khoảng 100 ứng viên.

### B. Mức hàm

| Cấu hình | R@1 | R@3 | R@5 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|
| bm25 | 0,181 | 0,338 | 0,389 | 0,495 | 0,550 | 0,340 |
| grep | 0,069 | 0,210 | 0,286 | 0,365 | 0,433 | 0,209 |
| neighbor | **0,222** | **0,399** | **0,471** | **0,536** | **0,570** | **0,384** |
| no_task_trace | 0,112 | 0,167 | 0,207 | 0,314 | 0,414 | 0,184 |
| task_trace | 0,137 | 0,250 | 0,338 | 0,434 | 0,485 | 0,253 |
| a3 | 0,137 | 0,229 | 0,277 | 0,403 | 0,444 | 0,238 |
| ast_no_task_trace | 0,112 | 0,167 | 0,248 | 0,334 | 0,414 | 0,190 |
| arch_no_task_trace | 0,112 | 0,167 | 0,207 | 0,314 | 0,393 | 0,184 |
| task_trace_rt1 | 0,147 | 0,270 | 0,363 | 0,434 | 0,485 | 0,270 |

**Cách đọc:**
- Chỉ các mục là hàm/method mới được tính hạng.
- Neighbor tốt nhất ở mọi cột; graph tốt nhất (`task_trace_rt1`) còn kém BM25.
- `G_task` giúp rõ nhất ở mức hàm: R@5 tăng từ 0,207 lên 0,338.
- Kiến trúc không giúp.
- Graph tìm đúng file nhưng chọn sai hàm. Ví dụ sympy-12481: class `Permutation` đứng hạng 1, còn `Permutation.__new__` không có trong top-100, trong khi BM25 và neighbor đặt nó ở hạng 2.

### C. Acc@k kiểu LocAgent (task chỉ được tính đúng khi **mọi** gold nằm trong top-k)

| Cấu hình | File @1 | File @5 | File @10 | Hàm @1 | Hàm @5 | Hàm @10 |
|---|---|---|---|---|---|---|
| bm25 | 0,220 | 0,660 | 0,740 | 0,163 | 0,347 | 0,429 |
| grep | 0,140 | 0,520 | 0,640 | 0,061 | 0,245 | 0,306 |
| neighbor | 0,260 | 0,700 | 0,780 | **0,204** | **0,429** | **0,469** |
| no_task_trace | 0,240 | 0,640 | **0,800** | 0,102 | 0,184 | 0,286 |
| task_trace | 0,320 | **0,720** | 0,740 | 0,122 | 0,306 | 0,388 |
| a3 | 0,340 | **0,720** | 0,760 | 0,122 | 0,245 | 0,367 |
| ast_no_task_trace | 0,240 | 0,620 | **0,800** | 0,102 | 0,224 | 0,306 |
| arch_no_task_trace | 0,240 | 0,640 | **0,800** | 0,102 | 0,184 | 0,286 |
| task_trace_rt1 | **0,360** | 0,700 | 0,740 | 0,122 | 0,327 | 0,388 |

**Cách đọc:**
- Acc@k khắt khe hơn R@k, nên luôn nhỏ hơn hoặc bằng R@k.
- Thứ tự các hệ giống bảng A–B.
- Dùng bảng này khi đặt kết quả cạnh LocAgent (2503.09089). LocAgent đo trên SWE-bench Lite và có dùng LLM, nên chỉ để tham khảo, không so thắng/thua trực tiếp.

### D. Mức component

| Cấu hình | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0,517 | 0,777 | 0,877 | 0,681 |
| grep | 0,367 | 0,743 | 0,823 | 0,589 |
| neighbor | 0,557 | **0,817** | 0,897 | 0,718 |
| no_task_trace | 0,560 | 0,770 | **0,920** | 0,705 |
| task_trace | 0,587 | 0,783 | 0,883 | 0,726 |
| a3 | **0,607** | 0,763 | 0,883 | 0,735 |
| ast_no_task_trace | 0,560 | 0,770 | **0,920** | 0,706 |
| arch_no_task_trace | 0,560 | 0,770 | **0,920** | 0,705 |
| task_trace_rt1 | **0,607** | 0,783 | 0,893 | **0,738** |

**Cách đọc:**
- Component là nhóm file do `G_arch` suy ra; đây là đơn vị thô nhất.
- Graph định vị khu vực tốt nhất, nhưng chênh lệch với baseline văn bản chưa có ý nghĩa thống kê (Phần 2).

### E. Trong ngân sách 12.000 token (Recall@B)

| Cấu hình | Recall@B file | Recall@B hàm | Đủ mọi file gold | Đủ mọi hàm gold | Token tới file gold đầu tiên | Token tới hàm gold đầu tiên |
|---|---|---|---|---|---|---|
| bm25 | 0,883 | 0,532 | 0,860 | 0,469 | 2.401 | 2.400 |
| grep | 0,735 | 0,429 | 0,700 | 0,367 | 3.146 | 4.168 |
| neighbor | 0,883 | **0,572** | 0,860 | **0,510** | 2.137 | 2.330 |
| no_task_trace | **0,918** | 0,327 | **0,880** | 0,286 | 1.892 | 3.729 |
| task_trace | 0,773 | 0,348 | 0,760 | 0,327 | **1.201** | 1.960 |
| a3 | 0,823 | 0,348 | 0,800 | 0,327 | 1.570 | 2.094 |
| ast_no_task_trace | 0,873 | 0,301 | 0,840 | 0,265 | 1.659 | 2.649 |
| arch_no_task_trace | **0,918** | 0,327 | **0,880** | 0,286 | 1.892 | 3.738 |
| task_trace_rt1 | 0,818 | 0,348 | 0,800 | 0,327 | 1.692 | **1.873** |

**Cách đọc:**
- Bảng này chấm **gói context thực tế** đưa cho agent: các mục được lấy theo thứ tự xếp hạng cho tới khi đầy 12.000 token. Đây là metric trung tâm của proposal §8.2.
- **Mức file:** graph phủ tốt nhất (0,918), vì gói của nó gồm nhiều mục nhỏ.
- **Mức hàm:** graph chỉ đạt khoảng 0,30–0,35, trong khi BM25 và neighbor đạt 0,53–0,57. Đây là chênh lệch lớn nhất trong toàn bộ số liệu.
- Hai cột "token tới gold đầu tiên" chỉ tính trên các task có gold trong gói, và càng nhỏ càng tốt. Graph gặp gold sớm nhất, nhưng nhóm task được tính của graph nhỏ hơn.

### F. Chi phí và chẩn đoán

| Cấu hình | Token context | Số mục đóng gói | Số mục được xếp hạng | Số anchor | File gold có trong danh sách | Hàm gold có trong danh sách | Thời gian retrieve (giây) |
|---|---|---|---|---|---|---|---|
| bm25 | 11.996 | 29,5 | 9.425 | — | 1,000 | 1,000 | — |
| grep | 11.996 | 19,4 | 4.621 | — | 1,000 | 0,908 | — |
| neighbor | 11.996 | 41,9 | 9.448 | — | 1,000 | 1,000 | — |
| no_task_trace | 11.964 | 48,6 | 100 | 47,7 | 0,925 | 0,525 | 4,5 |
| task_trace | 11.873 | 45,7 | 97,5 | 96,7 | 0,780 | 0,597 | 1,0 |
| a3 | 11.974 | 42,6 | 179 | 96,7 | 0,850 | 0,597 | 4,8 |
| ast_no_task_trace | 11.524 | 48,9 | 100 | 47,7 | 0,873 | 0,591 | 4,6 |
| arch_no_task_trace | 11.966 | 48,5 | 206 | 47,7 | 0,925 | 0,566 | 4,2 |
| task_trace_rt1 | 11.898 | 45,4 | 98,1 | 96,7 | 0,818 | 0,573 | 4,9 |

**Cách đọc:**
- **Chi phí context gần như bằng nhau** (11.500–12.000 token), nên so sánh công bằng: khác biệt chỉ nằm ở việc gói chứa code gì.
- Baseline văn bản xếp hạng toàn bộ repo (khoảng 9.400 chunk); graph chỉ giữ khoảng 100 ứng viên.
- **Hàm gold có trong danh sách (reach) của graph chỉ 0,52–0,60:** khoảng 40–48% số hàm gold không bao giờ vào nhóm ứng viên, nên không thể được xếp hạng hay đưa vào context. Đây là nguyên nhân chính khiến graph thua ở mức hàm.
- Thứ tự sửa nên là: (1) tăng reach mức hàm, bằng cách giảm anchor nhiễu và xếp method con của class/file được anchor theo nội dung thân hàm; (2) sau đó mới cải thiện thứ hạng.
- Số anchor trung bình khoảng 97 khi dùng `G_task`; có task lên tới 671 anchor (sklearn-10297).

### Tóm tắt A–F

| Đơn vị | Hệ tốt nhất | Graph so với văn bản |
|---|---|---|
| Component (D) | Graph | Nhỉnh hơn, chưa có ý nghĩa thống kê |
| File, hạng đầu (A, C) | Graph | Tốt hơn ở R@1 và MRR |
| File, danh sách dài (A @10–20) | Neighbor | Graph kém hơn (chỉ khoảng 100 ứng viên) |
| File trong ngân sách (E) | Graph không dùng `G_task` | Tốt hơn (0,918 so với 0,883) |
| Hàm (B, C, E) | Neighbor | **Graph kém rõ rệt** |

---

## Phần 2. Các cặp so sánh trong R1 (CI95; in đậm khi CI không chứa 0)

Chênh lệch = cấu hình ứng viên trừ cấu hình nền.

| Cặp | R@5 file | R@5 hàm | MRR hàm | Recall@B file | Recall@B hàm | R@5 component |
|---|---|---|---|---|---|---|
| A1 − bm25 | −0,057 [−0,20; +0,09] | **−0,182 [−0,31; −0,07]** | **−0,156** | +0,035 | **−0,205 [−0,35; −0,07]** | +0,043 |
| A1 − grep | +0,102 [−0,06; +0,26] | −0,078 | −0,025 | **+0,183 [+0,07; +0,31]** | −0,102 | +0,097 |
| A1 − neighbor | −0,097 | **−0,263 [−0,41; −0,13]** | **−0,200** | +0,035 | **−0,246** | +0,023 |
| A2 − bm25 | +0,037 [−0,07; +0,16] | −0,051 [−0,18; +0,08] | −0,087 | −0,110 [−0,22; 0,00] | **−0,183 [−0,32; −0,05]** | +0,007 |
| A2 − A1 (tác động của task trace) | +0,093 [0,00; +0,20] | **+0,131 [+0,05; +0,22]** | **+0,069** | **−0,145 [−0,25; −0,06]** | +0,021 | −0,037 |
| A3 − A2 (tác động của kiến trúc) | +0,010 | −0,061 [−0,12; 0,00] | **−0,016** | +0,050 [0,00; +0,12] | 0 | 0 |
| A1 − AST-only (cạnh gọi/import) | +0,020 | −0,041 | **−0,005** | +0,045 [0,00; +0,11] | +0,026 | 0 |
| A1+arch − A1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A2+RT1 − A2 | −0,020 | +0,024 [0,00; +0,07] | +0,017 | +0,045 [0,00; +0,11] | 0 | +0,010 |

Nguồn: `tv2_r1_retrieval_ablation_2026-11-11.md`.

---

## Phần 3. Bật layer và cờ: ba lượt

- **Lượt 1, `r1_50`:** không bật layer.
- **Lượt 2, `r1_full50_noflag`:** bật tree-sitter-graph + Joern + JARVIS, không bật cờ.
- **Lượt 3, `r1_full50`:** bật đủ layer và cờ `--use-variable-references`.

Mỗi ô ghi **lượt 1 / lượt 2 / lượt 3**.

| Cấu hình | R@1 file | R@5 file | R@5 hàm | MRR hàm | Recall@B hàm |
|---|---|---|---|---|---|
| no_task_trace | 0,260 / 0,260 / 0,260 | 0,650 / 0,650 / 0,650 | 0,207 / 0,207 / 0,207 | 0,184 / 0,184 / 0,184 | 0,327 / 0,327 / 0,327 |
| task_trace | 0,337 / 0,337 / 0,337 | 0,743 / 0,743 / 0,733 | 0,338 / 0,318 / 0,311 | 0,253 / 0,251 / 0,250 | 0,348 / 0,328 / 0,328 |
| a3 | 0,357 / 0,357 / 0,357 | 0,753 / 0,733 / 0,733 | 0,277 / 0,277 / 0,277 | 0,238 / 0,236 / 0,236 | 0,348 / 0,328 / 0,328 |
| ast_no_task_trace | 0,260 / 0,260 / 0,260 | 0,630 / 0,630 / 0,630 | 0,248 / 0,248 / 0,248 | 0,190 / 0,190 / 0,190 | 0,301 / 0,301 / 0,301 |
| arch_no_task_trace | 0,260 / 0,260 / 0,260 | 0,650 / 0,650 / 0,650 | 0,207 / 0,207 / 0,207 | 0,184 / 0,184 / 0,184 | 0,327 / 0,327 / 0,327 |
| task_trace_rt1 | 0,377 / 0,377 / 0,377 | 0,723 / 0,723 / 0,723 | 0,363 / 0,363 / 0,363 | 0,270 / 0,259 / 0,259 | 0,348 / 0,328 / 0,328 |

BM25, grep và neighbor giống hệt nhau ở cả ba lượt.

| Chi phí | Lượt 1 | Lượt 2 | Lượt 3 |
|---|---|---|---|
| Số node trung bình | 88.178 | 213.710 | 213.710 |
| Số cạnh trung bình | 138.106 | 556.935 | 556.935 |
| Thời gian build (trung vị/task) | 8,3 s | 153,9 s | 148,4 s |
| Tổng thời gian chạy 50 task | 1,28 giờ | 5,62 giờ | 5,61 giờ |

**Trạng thái layer ở lượt 2 và 3:**
- tree-sitter-graph chạy được 50/50 task;
- Joern chạy được 49/50 (`sympy-13480` quá 900 giây);
- JARVIS chạy được 41/50: 5 task lỗi `AttributeError` bên trong JARVIS (`get_ns`, `add_def`), 4 task quá 120 giây (sympy, sphinx).

**Tách nguồn ảnh hưởng:**

| So sánh | Đo cái gì | Thay đổi |
|---|---|---|
| `r1_50` → `r1_now50` | Thay đổi code | Không có (`rank_hash` giống hệt ở cả 9 cấu hình × 50 task) |
| `r1_now50` → `r1_full50_noflag` | Layer | Chỉ task `pydata__xarray-4629`: `task_trace` R@5 hàm 1,0 → 0,0; `a3` R@5 file 1,0 → 0,0; kéo theo MRR hàm và Recall@B hàm của `task_trace_rt1`. Không task nào tăng |
| `r1_full50_noflag` → `r1_full50` | Cờ `use_variable_references` | Chỉ task `pydata__xarray-6992`: `task_trace` R@5 hàm 0,67 → 0,33. Không task nào tăng |

**Sửa nhận định trong `tv2_r1_full_layers_2026-11-16.md`:** báo cáo đó cho rằng cả hai lần thua ở `task_trace` "nhiều khả năng do cờ". Lượt 2 cho thấy `xarray-4629` thua do **layer**, còn `xarray-6992` thua do **cờ**.

**Kết luận:** layer và cờ không cải thiện ô nào, trong khi thời gian build tăng khoảng 18 lần. Giữ cả hai ở trạng thái tắt cho retrieval.

---

## Phần 4. Trộn bằng RRF (thử nghiệm offline, chưa có trong code của repo)

**Cách làm:** đọc danh sách top-100 đã lưu của từng cấu hình trong `~/rt1/results/r1_50`, trộn bằng Reciprocal Rank Fusion: mỗi danh sách cho mỗi mục 1/(60 + hạng) điểm, cộng lại rồi xếp. k = 60, không tinh chỉnh. Phần graph dùng cấu hình `task_trace_rt1`. Mức file trộn theo đường dẫn; mức hàm trộn theo `function_id`, chỉ xét mục là function/method.

**Kiểm tra:** cách tính lại khớp số đã lưu trên 50/50 task.

| Cấu hình | R@1 file | R@5 file | R@5 hàm | R@10 hàm | MRR hàm |
|---|---|---|---|---|---|
| bm25 | 0,247 | 0,707 | 0,389 | 0,495 | 0,339 |
| neighbor | 0,287 | 0,747 | 0,471 | 0,536 | 0,383 |
| graph (`task_trace_rt1`) | 0,377 | 0,723 | 0,363 | 0,434 | 0,270 |
| Trộn chỉ văn bản: bm25 + neighbor | 0,307 | 0,747 | 0,471 | — | 0,383 |
| RRF graph + bm25 | 0,427 | 0,728 | 0,516 | 0,577 | 0,403 |
| RRF graph + neighbor | 0,427 | 0,728 | 0,475 | 0,556 | 0,423 |
| **RRF graph + bm25 + neighbor** | **0,447** | 0,728 | **0,536** | 0,572 | **0,445** |

| So sánh (CI95, seed 0) | R@1 file | R@5 file | R@5 hàm | MRR hàm |
|---|---|---|---|---|
| Trộn 3 nguồn − bm25 | **+0,200 [+0,10; +0,32]** | — | **+0,147 [+0,06; +0,25]** | **+0,106 [+0,02; +0,20]** |
| Trộn 3 nguồn − neighbor | **+0,160 [+0,06; +0,26]** | — | **+0,065 [+0,007; +0,14]** | +0,062 [−0,01; +0,14] |
| Trộn 3 nguồn − graph | +0,070 [−0,08; +0,21] | — | **+0,173 [+0,08; +0,29]** | **+0,175 [+0,09; +0,26]** |
| **Phần graph đóng góp:** trộn 3 nguồn − trộn chỉ văn bản | **+0,140 [+0,06; +0,24]** | −0,018 [−0,09; +0,06] | **+0,065 [+0,007; +0,14]** | +0,062 [−0,01; +0,14] |

**Giới hạn:**
- 25/50 task từng dùng để chọn `RT1_CONFIG`.
- Recall@B của bản trộn chưa đo, vì cần đóng gói lại theo ngân sách.
- Theo proposal, đây là cấu hình hybrid: §9.2 định nghĩa graph-guided là "ứng viên từ graph + đặc trưng `task_similarity`"; việc trộn với danh sách BM25 độc lập chỉ dựa được vào mitigation "fallback to text/embedding" ở §15. Cần nhóm xác nhận có dùng nó làm bằng chứng cho RQ2 không.

---

## Phần 5. Dataset và cỡ mẫu

| Mục | Giá trị |
|---|---|
| SWE-bench Verified (revision `c104f840…`) | 500 task: **208 dev / 292 held-out**, chia theo `sha256(instance_id)` (40% dev). Manifest held-out bắt buộc có `freeze_sha256` (`dataset.py:71-73`) |
| Pilot dev | 50 task, 12 repo: astropy, django, matplotlib, xarray, pylint, pytest, scikit-learn, sphinx (mỗi repo 5); requests, sympy (mỗi repo 4); seaborn, flask (mỗi repo 1) |
| Task đa file / đa hàm | 5/50 có từ 2 file gold; 11/50 có từ 2 hàm gold |
| Issue có traceback Python đầy đủ | 5/50 |
| Ngữ nghĩa nhãn gold | `developer_changed_code_proxy_not_complete_relevance` (chỗ đã sửa là đại diện gần đúng, không phải toàn bộ phần liên quan) |
| Lọc file test | Baseline và graph cùng loại file test khi đọc mã nguồn (`is_source` trong `read_archive_sources`). Dòng "Giới hạn" của báo cáo R1 ngày 11/11 nói baseline xếp hạng cả file test là **sai** |
| Độ lệch chuẩn của chênh lệch ghép cặp (trộn 3 nguồn − trộn chỉ văn bản) | R@1 file 0,351; R@5 hàm 0,252; MRR hàm 0,287 |
| Số task cần để phát hiện chênh lệch 0,05 / 0,10 (α = 0,05, power 80%) | R@5 hàm: khoảng 200 / 50; R@1 file: khoảng 386 / 97; MRR hàm: khoảng 258 / 65 |
| Chênh lệch nhỏ nhất phát hiện được trên held-out 292 task | R@5 hàm khoảng 0,041; MRR hàm khoảng 0,047; R@1 file khoảng 0,058 |
| Nhãn hop depth ngoài (Bellam, arXiv 2610.33958, CC BY 4.0) | 468/500 task Verified có nhãn: hop 0/1/2/3+ là 186/128/78/76. Chưa gắn vào 50 task dev |

---

## Phần 6. Các RQ khác (số đã có)

| Kết quả | Số liệu | Nguồn |
|---|---|---|
| Cạnh gọi trên repo test case: CALLS + MAY_CALL | Precision 0,579 / recall 0,746 | `tv2_l2_2_may_call_run_2026-11-08.md` |
| JARVIS | Precision của CALLS không giảm, recall tăng | `tv2_l2_1_jarvis_run_2026-11-10.md` |
| Trace link (31 task dev) | Top-1: P 0,70 / R 0,50; ngưỡng ≥ 0,7: P 0,45 / R 0,58 | `tv2_tr_1_trace_links_run_2026-11-10.md` |
| Cập nhật tăng dần (U1) | 12/12 kịch bản giống hệt build lại; nhanh hơn 3,3–11 lần (django: 8,9 s so với 29,6 s); RAM lớn nhất 3,4 GB | `tv2_u1_incremental_2026-11-11.md` |
| I1 (RQ3) | **Chưa chạy.** Hiện chỉ 23/50 task có đủ file đầu vào (`configs/m3/w10_dev/tasks`) và checkout (`~/w10/repositories`) | `layers_in_build_measurement_guide.md` |

---

## Tái tạo

```bash
# Trong WSL, từ thư mục chứa các script ở ablation_matrix/r1_numbers/
python3 ablation_matrix/r1_numbers/all_tables.py                     # bảng A–F (Phần 1)
python3 ablation_matrix/r1_numbers/fusion_probe.py ~/rt1/results/r1_50   # Phần 4 (kèm CI)
python3 ablation_matrix/r1_numbers/fair_probe.py ~/rt1/results/r1_50     # lọc test, cỡ mẫu (Phần 5)

# So sánh từng cặp lượt chạy (Phần 3)
python3 ~/rt1/compare_full50.py r1_now50 r1_full50_noflag
python3 ~/rt1/compare_full50.py r1_full50_noflag r1_full50
python3 ~/rt1/compare_full50.py r1_50 r1_now50
```

Các script chỉ đọc `tasks/*.json`, không chạy lại retrieval.
