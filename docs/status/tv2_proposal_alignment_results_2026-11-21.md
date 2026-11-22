# Kết quả chỉnh TV2 theo proposal — T1 từng bước và T2 v3

Plan: `docs/superpowers/plans/2026-11-20-tv2-proposal-alignment.md` (Task 6, 7). Spec: `docs/superpowers/specs/2026-11-20-tv2-proposal-alignment-design.md` §6.
Dữ liệu: 50 task dev (`w10-dev-50-gold.json`), 5 task có ≥ 2 file gold. Số thô trong `~/rt1/results/align_*` và `~/rt1/results/nav_v3` (WSL).
So cặp: `ablation_matrix/compare_runs.py` (bootstrap 2.000 vòng, seed 7), profile A2, Δ = sau − trước, CI95, thắng/thua.

## 1. Chọn N (spec §6.2)

Lượt đo `align_nhuge` (cấu hình cuối, `max_candidates=100000`): 50/50 SUCCEEDED, số ứng viên trung vị 1.449, p95 5.694,
lớn nhất 7.661 (matplotlib-23476), không task nào `traversal_limited`.

Thời gian: lần gọi chậm nhất là sympy-13480 (38,8 s). Đo riêng: N = 5.000 → 46,2 s (chạm N), N = 100.000 → 41,1 s.
cProfile: trong `retrieve()`, dựng `SourceEvidence` (AST của cả repo, một lần cho mỗi retriever) chiếm 68,6/97 s, đi graph
`_walk` 0,56 s. T1 dựng retriever mới cho mỗi task (khởi động lạnh); server MCP giữ retriever trong cache nên chỉ lần gọi
đầu trên mỗi graph trả chi phí này. Vì vậy điều kiện thời gian không phân biệt N.

**N = 6.000** (lựa chọn của nhóm theo §10.5): bao 49/50 task (98%); chỉ matplotlib-23476 chạm N.
`RESOURCE_LIMIT_CANDIDATES = 6000`, hash cấu hình mặc định `sha256:5849ebb8…6c6d`.

## 2. T1 từng bước (A2, n = 50)

| Bước | Thay đổi | fn R@5 | fn MRR | file R@1 | file R@5 | gold fn trong context (server) | frontier trong context (server) | context tokens |
|---|---|---|---|---|---|---|---|---|
| cũ → B1 | hạt giống chỉ từ anchor; lỗi thành anchor (mục 2, 10) | +0,051 [0; 0,122] | **+0,015 [0,002; 0,033]** | +0,040 [0; 0,10] | −0,020 [−0,06; 0] | +0,010 [−0,031; 0,061] | +0,020 [−0,002; 0,048] | **−22,6 [−53,0; −0,9]** |
| B1 → B2 | N 100 → 6.000 (mục 1) | **−0,078 [−0,156; −0,017]** | **−0,015 [−0,036; −0,002]** | −0,040 [−0,10; 0] | −0,020 [−0,10; 0,04] | −0,037 [−0,088; 0] | **−0,048 [−0,091; −0,011]** | **+47,3 [+7,6; +106,0]** |
| B2 → B3 | `MAY_CALL` (mục 3) | 0 | +0,007 [−0,005; 0,030] (2/17) | 0 | −0,020 [−0,06; 0] | −0,010 [−0,031; 0] | −0,013 [−0,043; 0,014] | **+45,6 [+0,6; +116,0]** |
| B3 → B4 | đóng gói thuần (mục 4) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **cũ → B4** | tổng | −0,027 [−0,075; 0] | +0,006 [−0,007; 0,030] | 0 | −0,060 [−0,14; 0] | −0,037 [−0,092; 0] | **−0,041 [−0,075; −0,014]** | **+70,3 [+14,1; +146,7]** |
| **B1 → B4** | mục 1 + 3 + 4 | **−0,078 [−0,156; −0,017]** | −0,008 [−0,034; 0,023] | −0,040 [−0,10; 0] | −0,040 [−0,12; 0,04] | **−0,048 [−0,102; −0,007]** | **−0,060 [−0,102; −0,025]** | **+92,9 [+25,7; +175,8]** |

In đậm: CI loại 0. Task nhiều file (n = 5): không cặp nào có CI loại 0 (cũ → B4: fn R@5 −0,067, fn MRR +0,1 do 1 task).

Đọc kết quả:
- Chỉ B1 có ích. Gom hết vùng k = 2 (B2) làm hàm gold bị đẩy khỏi top-5 và frontier rơi khỏi context: bộ xếp hạng
  không lọc được 1.449 ứng viên (trung vị) như với 100.
- `MAY_CALL` không đổi recall, thêm token; 17 task bị hạ MRR nhẹ.
- B3 = B4 vì phần giữ ngân sách không bao giờ chạy: `reference_reserved_tokens = 0` ở 50/50 task (kể cả lượt cũ) —
  không anchor nào có `reference_dependencies` trên graph `base`. Mục 4 không có tác dụng trên benchmark này.

## 3. Lớp kiến trúc (A1 → A1_arch, `align_arch`)

A1_arch bằng A1 trên mọi metric (fn MRR −0,000, 1/12; token −0,04). Task nhiều file: không đổi.
Báo cáo đầy đủ: `~/rt1/results/align_arch/report.md`.

## 4. T2 v3 (Qwen, cánh `graph_v1`)

`~/rt1/results/nav_v3` (chạy lại sau khi sửa lỗi audit, 14:21–16:03 UTC 20/11, `--rescore`); `base` và `graph_v0` là
liên kết tới `nav_k20` (cùng prompt hệ thống, đã kiểm byte-identical). `baseline/nav/nav_paired.py`, n = 50, mỗi cánh 1
BAD_ANSWER (base: sklearn-10908; graph_v1: sklearn-13135, Qwen hết lượt khi còn đang suy luận). `get_related_context`
được gọi ở 50/50 task, không lỗi.

| Metric | no-graph (`base`) | `graph_v0` | `graph_v1` | v1 − no-graph | v1 − v0 |
|---|---|---|---|---|---|
| file R@1 | 0,647 | 0,597 | 0,592 | −0,055 [−0,200; 0,085] | −0,005 [−0,145; 0,125] |
| file R@5 | 0,677 | 0,662 | 0,662 | −0,015 [−0,160; 0,125] | 0,000 [−0,120; 0,110] |
| fn R@1 | 0,316 | 0,382 | 0,255 | −0,061 [−0,204; 0,102] | **−0,127 [−0,245; −0,004]** |
| fn R@5 | 0,347 | 0,382 | 0,265 | −0,082 [−0,245; 0,082] | −0,116 [−0,233; 0,008] |
| fn MRR | 0,339 | 0,408 | 0,265 | −0,074 [−0,224; 0,082] | **−0,143 [−0,265; −0,020]** |
| thấy đủ file gold | 0,720 | 0,620 | 0,700 | −0,020 [−0,180; 0,140] | +0,080 [−0,060; 0,220] |
| frontier đã thấy | 0,327 | 0,275 | 0,270 | −0,056 [−0,186; 0,082] | −0,005 [−0,134; 0,133] |
| file đã đọc | 1,80 | 1,30 | 0,62 | **−1,18 [−1,58; −0,78]** | **−0,68 [−0,98; −0,40]** |
| file không gold đã đọc | 1,10 | 0,62 | 0,34 | **−0,76 [−1,10; −0,42]** | **−0,28 [−0,52; −0,04]** |
| số lời gọi tool | 8,24 | 8,74 | 4,04 | **−4,20 [−5,24; −3,24]** | **−4,70 [−5,66; −3,80]** |
| completion tokens | 827 | 792 | 426 | **−401 [−570; −207]** | **−365 [−531; −175]** |
| giây/task | 105 | 118 | 60 | | |

Task nhiều file (n = 5), v1 − no-graph: frontier đã thấy **+0,215 [+0,029; +0,427]** (3/0), thấy đủ file gold +0,20,
file MRR +0,20 (CI chạm 0); v1 − v0: không CI nào loại 0.

Đọc kết quả:
- `graph_v1` theo đúng quy trình server (find_task_anchors 50/50, get_related_context 52 lần) và hiệu quả hơn hẳn: nửa
  số lời gọi tool, ít file đọc, ít token, nhanh gần gấp đôi.
- Độ đúng mức hàm thấp hơn `graph_v0` (fn R@1, fn MRR có CI loại 0); so với không dùng graph thì không khác có ý nghĩa.
  Qwen tin vào gói context (1.000 token) và dừng sau bước 3, đọc 0,62 file/task, nên khi gói context xếp sai thì không
  tự sửa. Gói context dùng mặc định mới (B4), mà T1 cho thấy N = 6.000 làm hàm gold bị đẩy xuống (B1 → B2).
- Bug nhiều file: frontier đã thấy tăng so với không dùng graph, nhưng n = 5.

### 4.1 Hai cách sửa sau T2 v3 (21/11)

**Sửa bộ chấm.** 9/62 câu trả lời hàm của `graph_v1` viết `path.py:qualname` (chép từ dòng `Node:` của context), các
cánh khác không có; `_resolve` chỉ hiểu `::` nên chấm trượt. Bộ chấm nay đọc `path.py:name` như `path.py::name` (test
`test_path_with_a_single_colon_is_read_like_path_double_colon`); `--rescore` cả ba cánh, `base`/`graph_v0` không đổi.
`graph_v1` fn R@1 0,255 → 0,320; v1 − v0: fn R@1 −0,061 [−0,184; +0,082], fn MRR −0,061 [−0,184; +0,082] (CI chứa 0);
v1 − no-graph: fn R@1 +0,004. Đây là sửa phép đo, không phải cải thiện hệ thống. Bảng §4 ở trên là số trước khi sửa.

**Ngân sách context 3.000 (`graph_v1_b3000`).** Lý do: Qwen truyền trung vị 1 trong 31 anchor; hàm gold trong context
chỉ 13/49 task. Mô phỏng offline (`~/rt1/results/sim_context.jsonl`, 49 task): anchor Qwen chọn + ngân sách 3.000 → 16
(+3/−0); tất cả anchor + 3.000 → 14 (+3/−2); top-5 hoặc tất cả anchor + 1.000 → 12, 11 (nhiều anchor làm loãng thứ hạng).
Chạy GPU (50 task, 18:07–19:55 UTC 21/11), `graph_v1` → `graph_v1_b3000`:

| Metric | v1 | v1_b3000 | Δ [CI95] |
|---|---|---|---|
| fn R@1 | 0,320 | 0,320 | 0,000 [−0,122; +0,133] |
| fn MRR | 0,347 | 0,357 | +0,010 [−0,122; +0,143] |
| file R@5 | 0,662 | 0,637 | −0,025 [−0,130; +0,075] |
| frontier đã thấy | 0,270 | 0,347 | **+0,077 [+0,006; +0,153]** |
| thấy đủ file gold | 0,700 | 0,640 | −0,060 [−0,140; 0,000] |
| file đã đọc | 0,62 | 0,28 | **−0,34 [−0,60; −0,12]** |
| số lời gọi tool | 4,04 | 3,02 | **−1,02 [−1,64; −0,44]** |
| BAD_ANSWER | 1 | 2 (vòng lặp khi giải mã tham lam) | |

So với `graph_v0`: fn R@1 −0,061 [−0,194; +0,082]; so với no-graph: +0,004. Task nhiều file (n = 5): không cặp nào có CI
loại 0 trừ frontier đã thấy so với no-graph (+0,222).

**Giới hạn ứng viên N = 100 (`graph_v1_n100`, 21/11).** Lý do: T1 B1 → B2 cho thấy N = 6.000 làm hàm gold tụt hạng; trong
T2 có 28/47 lần gọi `get_related_context` vượt 100 ứng viên. Server đọc `VGAR_RETRIEVAL_MAX_CANDIDATES` (host đặt);
harness truyền 100 cho cánh này. Chạy GPU 50 task (20:16–21:57 UTC), `graph_v1` → `graph_v1_n100`: fn R@1 −0,010
[−0,082; +0,061] (2/2), fn MRR 0,000, file R@5 −0,020, frontier đã thấy +0,020; 1 BAD_ANSWER mỗi cánh. Hàm hạng 1 của
gói context giống nhau ở 48/49 task (cả gói giống ở 34/49): với 1 anchor và ngân sách 1.000, phần bị cắt bởi N chỉ là
ứng viên hạng thấp. Kết luận: trong T2, N không phải đòn bẩy; hiệu ứng của N ở T1 đến từ cách T1 đưa toàn bộ anchor vào.

**Phép thử chọn trong gói (21–22/11, `spikes/pick_in_pack/pick_in_pack.py`).** Không tool, một lần sinh: issue + gói
context luôn có hàm gold (hàm nhiễu lấy từ gói thật của `graph_v1_b3000`, tối đa 7; điểm relevance gán lại giảm dần theo
vị trí). 45 task × 3 vị trí, gói trung vị 8 hàm. Đúng ở hạng 1: gold đầu gói 0,889 [0,80; 0,98]; giữa 0,733 [0,60; 0,87];
cuối 0,556 [0,40; 0,69]. Giữa − đầu −0,156 [−0,267; −0,044] (0/7), cuối − đầu −0,333 [−0,467; −0,200] (0/15), cuối −
giữa −0,178 [−0,289; −0,067] (0/8). Câu trả lời đầu nằm ngoài gói tăng từ 7% lên 27% khi gold ở cuối. 25/45 task đúng
ở cả ba vị trí, 5/45 sai cả ba.

Đọc kết quả: Qwen3-4B đọc hiểu được context (0,89 khi gold đứng đầu, khớp 9/10 trong T2) nhưng thiên lệch mạnh về thứ
tự: gold ở cuối gói 8 hàm thì đúng chỉ khoảng một nửa. Vì điểm relevance giảm dần theo vị trí (như context thật của server),
phép thử không tách được Qwen bám thứ tự hay bám điểm; cả hai đều nghĩa là nó dựa vào thứ hạng của server hơn là nội dung.
Hệ quả cho T2: thêm gold ở hạng thấp (ngân sách 3.000) gần như không thành câu trả lời đúng; đòn bẩy vẫn là đưa gold lên
hạng 1, và mô hình mạnh hơn nhiều khả năng giảm được thiên lệch này.

Vì sao độ phủ tăng mà độ đúng không tăng (41 task đầu, 40 có nhãn hàm): ở `graph_v1` hàm gold có trong context ở 10 task,
cả 10 đều ở vị trí 1, Qwen đúng 9/10. Ở `graph_v1_b3000` có 13 task, nhưng các task thêm vào có gold ở vị trí 2, 2, 12, 15;
Qwen đúng 8/13 (2 chọn hàm khác trong gói, 3 không trả lời). Qwen gần như chọn hàm đứng đầu và ít tự đọc thêm, nên độ đúng
≈ độ chính xác hạng 1 của retrieval; tăng ngân sách chỉ thêm hàm ở hạng thấp. Đòn bẩy là thứ hạng (T1: N = 100 tốt hơn
N = 6.000), không phải ngân sách.

### 4.2 Lớp SCIP/LSP ở T1 (22/11, `~/rt1/results/layers_scip`)

Cùng một lượt, cùng code: profile `A3` (graph `base`), `A3_scip`, `A3_scip_lsp` (graph dựng mới, SCIP chạy được 41/50,
LSP 50/50; SCIP thất bại ở seaborn-3069, scikit-learn ×4 (mã -6), sympy ×3 (mã 1)). Dựng graph trung bình 198 s (`scip`),
206 s (`scip_lsp`) so với ~13 s (`base`).

| So với A3 | n | fn MRR | fn R@1 | file R@5 | gold fn / frontier trong context |
|---|---|---|---|---|---|
| `A3_scip`, 50 task | 50 | **−0,014 [−0,038; −0,001]** (4/16) | −0,010 | −0,020 | 0 / 0 |
| `A3_scip`, task SCIP chạy được | 41 | **−0,017 [−0,043; −0,001]** (4/16) | −0,013 | −0,024 | 0 / 0 |
| `A3_scip`, nhiều file | 5 | −0,100 | −0,100 | 0 | 0 / 0 |
| `A3_scip_lsp` | | giống hệt `A3_scip` ở mọi metric | | | |

Top-5 giống A3 ở 32/50 task. LSP không thêm gì so với SCIP (bị giới hạn 200 request). Khớp với R1 ngày 18/11: thêm cạnh
CALLS đúng (precision 0,967) không đưa thêm hàm gold vào context mà chỉ làm đổi thứ tự, hơi xấu đi. Các điểm R1, R2 của
review `tv2_retrieval_review_2026-11-22.md` (anchor luôn đứng đầu; hàng xóm thừa hưởng điểm anchor, hòa điểm xếp theo chữ
cái) là cơ chế phù hợp với kiểu thay đổi này nhưng chưa được kiểm trực tiếp.

### 4.3 Sửa sau review retrieval (22/11, T1, profile A2)

| Lượt | Thay đổi | So với | fn MRR | fn R@5 | fn R@1 | gold fn / frontier trong context (server) | hạng 1 giống |
|---|---|---|---|---|---|---|---|
| `fix_r2` | khi hòa điểm xếp theo độ giống riêng (code) | `align_b4` | +0,001 | +0,020 (1/0) | 0 | 0 / 0 | 50/50 |
| `fix_w01` | trọng số `graph_distance` 0,1 | `fix_r2` | **−0,039** (1/19) | −0,020 | −0,031 | +0,041 / +0,034 (CI chạm 0) | 2/50 |
| `fix_w0` | trọng số `graph_distance` 0 | `fix_r2` | **−0,058** (3/22) | **−0,102** (0/5) | −0,031 | 0 / −0,007 | 1/50 |

Giảm lợi thế khoảng cách làm anchor rời hạng 1 (anchor ở hạng 1: 34 → 26/50 với 0,1) và các hàm hàng xóm có tên khớp
issue nhưng không phải gold chen lên (ở 10 task bị tụt: 129 hàm/method không phải anchor, 18 anchor). Trong T1 anchor của
G_task là ưu tiên tốt; giả thuyết R1 của review (anchor áp đảo gây hại) bị bác ở T1. Giữ trọng số 0,2; giữ sửa R2.

## 5. Ghi chú

- Hiệu năng còn mở: `message_matches` (Task 2) đọc và parse lại source ở mỗi lần dựng overlay cho issue có dòng log
  (~46 s khi profile trên sympy-13480), tức mỗi lần gọi `find_task_anchors` của server với các issue đó. Chưa sửa.
- Lỗi tìm thấy khi chạy T2 v3 (đã sửa): Task 3 ghi toàn bộ diagnostics vào dòng audit, nhưng `vgar/mcp/audit.py`
  từ chối dòng > 64 KiB, nên `get_related_context` trả `INTERNAL_ERROR` khi có hơn khoảng 55 ứng viên (22/32 task của
  lượt đầu). Sửa: audit giữ 20 ứng viên/omission đầu kèm tổng số (`graph_server._audit_diagnostics`). Lượt hỏng giữ ở
  `nav_v3/graph_v1_broken_audit`, không dùng để báo cáo.
- `compare_runs.py` sửa để so được arm profile của T1 (A2, A1_arch) và bỏ `build_seconds` khi task không có bản ghi
  `graph`; test `test_t1_runs_compare_their_profile_arms_without_a_graph_record`.
- Số T1/R1/T2 trước ngày 20/11 gắn với hash cấu hình cũ; bản freeze held-out (nháp) phải cập nhật hash trước khi ký.
