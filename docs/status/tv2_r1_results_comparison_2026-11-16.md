# TV2 — Kết quả so sánh retrieval R1 (16/11/2026)

Tài liệu tổng hợp toàn bộ số liệu retrieval để dùng cho Chương 4. Pilot dev 50 task SWE-bench Verified, ngân sách context 12.000 token.

## Cấu hình

| Tên | Mô tả |
|---|---|
| `bm25`, `grep`, `neighbor` | Baseline văn bản |
| `no_task_trace` (A1) | Graph, anchor theo tên symbol |
| `task_trace` (A2) | Graph + G_task |
| `a3` (A3) | A2 + kiến trúc + trace |
| `ast_no_task_trace` | Graph chỉ còn cạnh chứa (AST-only) |
| `arch_no_task_trace` | A1 + kiến trúc |
| `task_trace_rt1` | A2 + `may_call_factor=0.5` |

## Cách đọc chỉ số

- **R@k**: trong k kết quả đầu, tìm được bao nhiêu phần trăm số đơn vị (file, hàm, component) mà patch gold đã sửa. Lấy trung bình trên 50 task.
- **MRR**: trung bình của 1 / hạng của mục gold đầu tiên. Chỉ số này thưởng cho việc đặt đúng mục lên đầu.
- **Acc@k (kiểu LocAgent)**: một task chỉ được tính đúng khi *mọi* mục gold đều nằm trong top-k. Chỉ số này chặt hơn R@k với task đa file hoặc đa hàm.
- **Recall@B**: tỉ lệ gold lọt vào context sau khi đóng gói vào ngân sách 12.000 token.
- **Reach**: tỉ lệ gold có mặt ở bất kỳ vị trí nào trong danh sách xếp hạng.

---

## Phần 1. R1 đầy đủ: 9 cấu hình, không bật layer

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

Nhận định:
- Graph đặt đúng file ở hạng 1 tốt nhất: `task_trace_rt1` đạt R@1 0,377, so với bm25 0,247 và neighbor 0,287.
- Ở top-5, các hệ gần như ngang nhau (0,72–0,75).
- Ở top-10 và top-20, `task_trace` tụt dưới neighbor, vì graph chỉ giữ khoảng 100 ứng viên.
- G_task có ích ở thứ hạng đầu: R@1 của `task_trace` là 0,337, của `no_task_trace` là 0,260.

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

Nhận định: ở mức hàm, baseline văn bản thắng graph ở mọi k. Nguyên nhân chính là reach (xem bảng F): khoảng 40–48% số hàm gold không có trong danh sách ứng viên của graph.

### C. Acc@k kiểu LocAgent

| Cấu hình | File @1 | File @5 | File @10 | Hàm @1 | Hàm @5 | Hàm @10 |
|---|---|---|---|---|---|---|
| bm25 | 0,220 | 0,660 | 0,740 | 0,163 | 0,347 | 0,429 |
| grep | 0,140 | 0,520 | 0,640 | 0,061 | 0,245 | 0,306 |
| neighbor | 0,260 | 0,700 | 0,780 | 0,204 | 0,429 | 0,469 |
| no_task_trace | 0,240 | 0,640 | 0,800 | 0,102 | 0,184 | 0,286 |
| task_trace | 0,320 | 0,720 | 0,740 | 0,122 | 0,306 | 0,388 |
| a3 | 0,340 | 0,720 | 0,760 | 0,122 | 0,245 | 0,367 |
| ast_no_task_trace | 0,240 | 0,620 | 0,800 | 0,102 | 0,224 | 0,306 |
| arch_no_task_trace | 0,240 | 0,640 | 0,800 | 0,102 | 0,184 | 0,286 |
| task_trace_rt1 | 0,360 | 0,700 | 0,740 | 0,122 | 0,327 | 0,388 |

Nhận định: thứ hạng giữa các hệ giống bảng A–B. Vì chỉ 5/50 task có từ 2 file gold, Acc@k ở mức file gần với R@k.

### D. Mức component

| Cấu hình | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0,517 | 0,777 | 0,877 | 0,681 |
| grep | 0,367 | 0,743 | 0,823 | 0,589 |
| neighbor | 0,557 | 0,817 | 0,897 | 0,718 |
| no_task_trace | 0,560 | 0,770 | 0,920 | 0,705 |
| task_trace | 0,587 | 0,783 | 0,883 | 0,726 |
| a3 | 0,607 | 0,763 | 0,883 | 0,735 |
| ast_no_task_trace | 0,560 | 0,770 | 0,920 | 0,706 |
| arch_no_task_trace | 0,560 | 0,770 | 0,920 | 0,705 |
| task_trace_rt1 | 0,607 | 0,783 | 0,893 | 0,738 |

Nhận định: ở mức thô nhất này, graph ngang hoặc nhỉnh hơn baseline. Khoảng cách giữa các hệ nhỏ.

### E. Trong ngân sách 12.000 token (Recall@B)

| Cấu hình | Recall@B file | Recall@B hàm | Đủ mọi file gold | Đủ mọi hàm gold | Token tới file gold đầu tiên | Token tới hàm gold đầu tiên |
|---|---|---|---|---|---|---|
| bm25 | 0,883 | 0,532 | 0,860 | 0,469 | 2.401 | 2.400 |
| grep | 0,735 | 0,429 | 0,700 | 0,367 | 3.146 | 4.168 |
| neighbor | 0,883 | 0,572 | 0,860 | 0,510 | 2.137 | 2.330 |
| no_task_trace | 0,918 | 0,327 | 0,880 | 0,286 | 1.892 | 3.729 |
| task_trace | 0,773 | 0,348 | 0,760 | 0,327 | 1.201 | 1.960 |
| a3 | 0,823 | 0,348 | 0,800 | 0,327 | 1.570 | 2.094 |
| ast_no_task_trace | 0,873 | 0,301 | 0,840 | 0,265 | 1.659 | 2.649 |
| arch_no_task_trace | 0,918 | 0,327 | 0,880 | 0,286 | 1.892 | 3.738 |
| task_trace_rt1 | 0,818 | 0,348 | 0,800 | 0,327 | 1.692 | 1.873 |

Hai cột "token tới gold đầu tiên" chỉ tính trên các task có gold lọt vào context; số càng nhỏ càng tốt. Graph đưa gold vào context sớm hơn (ít token hơn), nhưng phủ hàm gold kém hơn baseline.

### F. Chi phí và chẩn đoán

| Cấu hình | Token context | Số mục đóng gói | Số mục được xếp hạng | Số anchor | Reach file gold | Reach hàm gold | Thời gian retrieve (s) |
|---|---|---|---|---|---|---|---|
| bm25 | 11.996 | 29,5 | 9.425 (chunk) | — | 1,000 | 1,000 | — |
| grep | 11.996 | 19,4 | 4.621 | — | 1,000 | 0,908 | — |
| neighbor | 11.996 | 41,9 | 9.448 | — | 1,000 | 1,000 | — |
| no_task_trace | 11.964 | 48,6 | 100 | 47,7 | 0,925 | 0,525 | 4,5 |
| task_trace | 11.873 | 45,7 | 97,5 | 96,7 | 0,780 | 0,597 | 1,0 |
| a3 | 11.974 | 42,6 | 179 | 96,7 | 0,850 | 0,597 | 4,8 |
| ast_no_task_trace | 11.524 | 48,9 | 100 | 47,7 | 0,873 | 0,591 | 4,6 |
| arch_no_task_trace | 11.966 | 48,5 | 206 | 47,7 | 0,925 | 0,566 | 4,2 |
| task_trace_rt1 | 11.898 | 45,4 | 98,1 | 96,7 | 0,818 | 0,573 | 4,9 |

Baseline văn bản xếp hạng toàn bộ chunk của repo nên luôn chạm gold. Graph chỉ giữ khoảng 100 ứng viên, nên khoảng 40–48% số hàm gold không có mặt trong danh sách của graph. **Đây là nguyên nhân lớn nhất khiến graph thua ở mức hàm.**

---

## Phần 2. So sánh từng cặp trong R1 (CI95, bootstrap 2.000 lần)

Chênh lệch = cấu hình ứng viên − cấu hình nền. In đậm khi CI không chứa 0. Ô không ghi CI là ô chỉ có số trung bình.

| Cặp | R@5 file | R@5 hàm | MRR hàm | Recall@B file | Recall@B hàm | R@5 component |
|---|---|---|---|---|---|---|
| A1 − bm25 | −0,057 [−0,20; +0,09] | **−0,182 [−0,31; −0,07]** | −0,156 | +0,035 | **−0,205 [−0,35; −0,07]** | +0,043 |
| A1 − grep | +0,102 [−0,06; +0,26] | −0,078 | −0,025 | **+0,183 [+0,07; +0,31]** | −0,102 | +0,097 |
| A1 − neighbor | −0,097 | **−0,263 [−0,41; −0,13]** | −0,200 | +0,035 | −0,246 | +0,023 |
| A2 − bm25 | +0,037 [−0,07; +0,16] | −0,051 [−0,18; +0,08] | −0,087 | −0,110 [−0,22; 0,00] | **−0,183 [−0,32; −0,05]** | +0,007 |
| A2 − A1 (tác động của task trace) | +0,093 [0,00; +0,20] | **+0,131 [+0,05; +0,22]** | +0,069 | **−0,145 [−0,25; −0,06]** | +0,021 | −0,037 |
| A3 − A2 (tác động của kiến trúc) | +0,010 | −0,061 [−0,12; 0,00] | −0,016 | +0,050 [0,00; +0,12] | 0 | 0 |
| A1 − AST-only (cạnh gọi/import) | +0,020 | −0,041 | −0,005 | +0,045 [0,00; +0,11] | +0,026 | 0 |
| A1+arch − A1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A2+RT1 − A2 | −0,020 | +0,024 [0,00; +0,07] | +0,017 | +0,045 [0,00; +0,11] | 0 | +0,010 |

Kết luận:
- **Task trace (G_task) có ích** ở mức hàm: R@5 tăng +0,131 và CI không chứa 0. Đổi lại, Recall@B file giảm.
- **Kiến trúc** không cải thiện; riêng `A1+arch` giống hệt A1.
- **Cạnh gọi/import** (so với AST-only) không cho khác biệt có ý nghĩa.
- **RT1** (`may_call_factor=0.5`) chỉ cho cải thiện nhỏ, sát mép 0.

---

## Phần 3. Bật layer và cờ (ba lượt)

Mỗi ô ghi: `r1_50` (không layer) / `r1_full50_noflag` (có layer, không cờ) / `r1_full50` (có layer và cờ).

| Cấu hình | R@1 file | R@5 file | R@5 hàm | MRR hàm | Recall@B hàm |
|---|---|---|---|---|---|
| no_task_trace | 0,260 / 0,260 / 0,260 | 0,650 / 0,650 / 0,650 | 0,207 / 0,207 / 0,207 | 0,184 / 0,184 / 0,184 | 0,327 / 0,327 / 0,327 |
| task_trace | 0,337 / 0,337 / 0,337 | 0,743 / 0,743 / 0,733 | 0,338 / 0,318 / 0,311 | 0,253 / 0,251 / 0,250 | 0,348 / 0,328 / 0,328 |
| a3 | 0,357 / 0,357 / 0,357 | 0,753 / 0,733 / 0,733 | 0,277 / 0,277 / 0,277 | 0,238 / 0,236 / 0,236 | 0,348 / 0,328 / 0,328 |
| ast_no_task_trace | 0,260 / 0,260 / 0,260 | 0,630 / 0,630 / 0,630 | 0,248 / 0,248 / 0,248 | 0,190 / 0,190 / 0,190 | 0,301 / 0,301 / 0,301 |
| arch_no_task_trace | 0,260 / 0,260 / 0,260 | 0,650 / 0,650 / 0,650 | 0,207 / 0,207 / 0,207 | 0,184 / 0,184 / 0,184 | 0,327 / 0,327 / 0,327 |
| task_trace_rt1 | 0,377 / 0,377 / 0,377 | 0,723 / 0,723 / 0,723 | 0,363 / 0,363 / 0,363 | 0,270 / 0,259 / 0,259 | 0,348 / 0,328 / 0,328 |

| Chi phí | Không layer | Có layer, không cờ | Có layer và cờ |
|---|---|---|---|
| Số node trung bình | 88.178 | 213.710 | 213.710 |
| Số cạnh trung bình | 138.106 | 556.935 | 556.935 |
| Thời gian build (trung vị/task) | 8,3 s | 153,9 s | 148,4 s |
| Tổng thời gian chạy 50 task | 1,28 giờ | 5,62 giờ | 5,61 giờ |

Trạng thái layer:
- tree-sitter-graph: chạy được 50/50 task.
- Joern: 49/50 (`sympy-13480` quá 900 giây).
- JARVIS: 41/50 (AttributeError bên trong JARVIS ở 5 task, quá 120 giây ở 4 task).

Nguồn của các ô giảm:
- bật layer: chỉ do task `xarray-4629`;
- bật cờ: chỉ do task `xarray-6992`;
- thay đổi code (`r1_50` so với `r1_now50`): không có ô nào đổi.

**Kết luận:** bật layer làm build chậm khoảng 19 lần mà không cải thiện retrieval. Vì vậy layer và cờ giữ mặc định tắt.

---

## Phần 4. Trộn bằng RRF (thử nghiệm offline, chưa có trong repo)

Trộn các danh sách top-100 đã lưu bằng Reciprocal Rank Fusion, k = 60. Phần graph dùng `task_trace_rt1`.

| Cấu hình | R@1 file | R@5 file | R@5 hàm | R@10 hàm | MRR hàm |
|---|---|---|---|---|---|
| bm25 | 0,247 | 0,707 | 0,389 | 0,495 | 0,339 |
| neighbor | 0,287 | 0,747 | 0,471 | 0,536 | 0,383 |
| graph (task_trace_rt1) | 0,377 | 0,723 | 0,363 | 0,434 | 0,270 |
| Trộn chỉ văn bản: bm25 + neighbor | 0,307 | 0,747 | 0,471 | — | 0,383 |
| RRF graph + bm25 | 0,427 | 0,728 | 0,516 | 0,577 | 0,403 |
| RRF graph + neighbor | 0,427 | 0,728 | 0,475 | 0,556 | 0,423 |
| RRF graph + bm25 + neighbor | **0,447** | 0,728 | **0,536** | 0,572 | **0,445** |

| So sánh (CI95) | R@1 file | R@5 file | R@5 hàm | MRR hàm |
|---|---|---|---|---|
| Trộn 3 nguồn − bm25 | **+0,200 [+0,10; +0,32]** | — | **+0,147 [+0,06; +0,25]** | **+0,106 [+0,02; +0,20]** |
| Trộn 3 nguồn − neighbor | **+0,160 [+0,06; +0,26]** | — | **+0,065 [+0,007; +0,14]** | +0,062 [−0,01; +0,14] |
| Trộn 3 nguồn − graph | +0,070 [−0,08; +0,21] | — | **+0,173 [+0,08; +0,29]** | **+0,175 [+0,09; +0,26]** |
| Phần graph đóng góp: trộn 3 nguồn − trộn chỉ văn bản | **+0,140 [+0,06; +0,24]** | −0,018 [−0,09; +0,06] | **+0,065 [+0,007; +0,14]** | +0,062 [−0,01; +0,14] |

**Kết luận:** graph đứng riêng không thắng văn bản ở mức hàm, nhưng khi trộn với văn bản thì graph đóng góp có ý nghĩa thống kê (R@1 file +0,14; R@5 hàm +0,065). Đây là lập luận chính cho giá trị của graph retrieval.

---

## Phần 5. Dataset và cỡ mẫu

| Mục | Giá trị |
|---|---|
| SWE-bench Verified | 500 task: 208 dev / 292 held-out (chia theo hash của `instance_id`) |
| Pilot dev | 50 task, 12 repo (8 repo × 5 task; requests và sympy mỗi repo 4; seaborn và flask mỗi repo 1) |
| Task đa file / đa hàm | 5/50 có từ 2 file gold; 11/50 có từ 2 hàm gold |
| Issue có traceback đầy đủ | 5/50 |
| Độ lệch chuẩn của chênh lệch ghép cặp | R@1 file 0,351; R@5 hàm 0,252; MRR hàm 0,287 |
| Số task cần để phát hiện chênh lệch 0,05 / 0,10 | R@5 hàm: khoảng 200 / 50; R@1 file: khoảng 386 / 97; MRR hàm: khoảng 258 / 65 |
| Chênh lệch nhỏ nhất phát hiện được trên held-out 292 task | R@5 hàm khoảng 0,041; MRR hàm khoảng 0,047; R@1 file khoảng 0,058 |
| Thời gian chạy | 50 task × 9 cấu hình mất 1,28 giờ khi không bật layer |

---

## Phần 6. Các RQ khác

| Kết quả | Số liệu | Nguồn |
|---|---|---|
| Cạnh gọi (repo test case): CALLS + MAY_CALL | Precision 0,579 / recall 0,746 | `tv2_l2_2_may_call_run_2026-11-08.md` |
| Trace link (31 task dev) | Top-1: P 0,70 / R 0,50; ngưỡng ≥ 0,7: P 0,45 / R 0,58 | `tv2_tr_1_trace_links_run_2026-11-10.md` |
| Cập nhật tăng dần (U1) | 12/12 kịch bản giống hệt build lại; nhanh hơn 3,3–11 lần (django: 8,9 s so với 29,6 s); RAM lớn nhất 3,4 GB | `tv2_u1_incremental_2026-11-11.md` |
| I1 (RQ3) | Chưa chạy | — |

---

## Dữ liệu gốc

- `~/rt1/results/r1_50`, `r1_now50`, `r1_full50_noflag`, `r1_full50` (WSL): mỗi thư mục có `tasks/*.json` và `summary.json`; các file `compare_vs_*.json` nằm trong thư mục của lượt ứng viên.
- Script tạo bảng ở Phần 1: `ablation_matrix/r1_numbers/all_tables.py`.
