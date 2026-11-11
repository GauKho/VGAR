# TV2 · R1: ablation retrieval offline (A0–A3) cho RQ2

> **Trạng thái:** bản nháp, 11/11/2026, chờ duyệt.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), **[rq]** `rq metrics matrix.txt`, **[mm]** `metrics matrix.txt`, **[test]** `test.txt`, **[cp]** `check proposal.txt`. Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec. **(chờ chốt)** là câu hỏi còn mở.

## 1. Bối cảnh

- **RQ2** ([P] dòng 85): graph-guided retrieval có tìm đúng **file/function/component** tốt hơn **BM25/embedding/grep** không?
- [plan] dòng 167 giao TV2 tuần 2 ngày 3: "đủ baseline §13.1 (grep, BM25, embedding, file-neighbor, agent default) so với các cấu hình graph". Milestone M2 (dòng 199): "improve gold file/function recall over grep/BM25/embedding", đo bằng R1.
- [P] §13.1 (dòng 1276–1297) liệt kê hai nhóm baseline cho retrieval:
  - Retrieval baselines: grep/ripgrep, BM25, embedding search, file-neighbor heuristic, agent default exploration.
  - Graph baselines: AST-only graph, repo symbol graph only, repo graph + architecture lift, repo graph + task trace, full Arch-CPG.
- [rq] mục 1: metric `gold_file_recall@k`, `gold_function_recall@k`, `dependency_frontier_recall@B`, MRR, context token cost; chạy mọi baseline và cấu hình graph "trên cùng bộ task và cùng ngân sách B".
- Ma trận ablation [P] §13.3 (dòng 1361–1368) là của agent (cột MCP; [rq] mục 2 "Agent sinh patch theo từng variant A0–A5"), do TV1 chạy tuần 2 ngày 4. Spec này chỉ làm **nhóm metric retrieval** của A0–A3, đo offline, không chạy agent.
- Hợp đồng TV1 (mục E04, dòng 142 và 149): khác biệt giữa các arm A0–A5 là quyết định của nhóm; "không tự lấy old A0–A3 semantics". [plan] mục O4 (dòng 241): A0–A3 trong repo cũ là chính sách verify của M2, khác nghĩa.

**Hiện trạng repo:**

| Có | Thiếu |
|---|---|
| BM25 (`run_bm25_retrieval.py`, `scoring.bm25_rank`) | grep, embedding, file-neighbor |
| Graph retrieval qua overlay task (arm `graph`, `graph_f2p` trong `run_graph_retrieval.py`) | Cấu hình graph không dùng overlay (A1); cấu hình chỉ cạnh AST |
| Cờ `G_arch` của RT-1 (`use_component_dependents`, `use_trace_component`) | Cấu hình gom cờ thành A3 |
| `score_record`: recall@k file/hàm, MRR, Recall@B (`packed_gold_*_in_context`), `context_tokens` | Recall theo component |
| Run 50 task RT-1 `~/rt1/results/full50/default` (arm `graph`, 12.000 token, bytes/4) | Run của các cấu hình khác |
| `run_rt1_ablation.py` (một graph mỗi task, nhiều cấu hình, `--prune`, `--resume`) | Hỗ trợ cấu hình không phải `RetrievalConfig` (BM25, A1) |

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Có số retrieval cho từng bước A0 → A1 → A2 → A3 trên cùng bộ task, cùng ngân sách, để trả lời RQ2 và các cặp liền kề.
2. So graph với baseline văn bản (M2).
3. Đo cả mức component, vì RQ2 nhắc "component".

**Ngoài phạm vi**

- Chạy agent, sinh patch, chấm repair, MCP usability (TV1); verify A4/A5 (TV3).
- Baseline "agent default exploration" (cần agent; TV1).
- Cho retrieval đọc cạnh `G_code` (chưa có trong plan); "full Arch-CPG" vì vậy không khác A3 ở retrieval (§4.4).
- `dependency_frontier_recall@B` theo nghĩa F\* rộng hơn patch gold ([rq] mục 1 nói cần gán nhãn thêm): dùng file/hàm của patch gold làm F\* và ghi rõ là xấp xỉ.
- Held-out: chỉ chạy dev.

**Điều cần tránh**

- Gọi kết quả này là "ablation §13.3" hay "A0–A3 của nhóm" trước khi nhóm chốt E04. Trong báo cáo dùng tên `R-A0`…`R-A3` kèm bảng ánh xạ.
- Đổi `RetrievalConfig()` hay `FROZEN_RANKING_HASH`.
- Dùng patch gold, `FAIL_TO_PASS` hay dữ liệu sau `base_commit` khi xếp hạng (riêng arm có tên test fail là giao thức cũ, báo riêng).
- Chỉnh tham số trên chính kết quả báo cáo: các cấu hình ở đây chốt trước khi chạy.

## 3. Các cấu hình

| Tên | Ứng với | Nguồn ứng viên | Graph dùng | Đánh dấu |
|---|---|---|---|---|
| `R-A0-bm25` | A0; §13.1 BM25 | BM25 trên chunk mã nguồn, truy vấn = `problem_statement` | Không | có sẵn |
| `R-A0-grep` | A0; §13.1 grep/ripgrep | §4.1 | Không | **(đề xuất)** làm mới |
| `R-A0-neighbor` | A0; §13.1 file-neighbor | §4.2 | Không | **(đề xuất)** làm mới |
| `R-A0-embed` | A0; §13.1 embedding | §4.3 | Không | **(chờ chốt)** |
| `R-AST` | §13.1 AST-only graph | anchor như `R-A1`; chỉ đi cạnh chứa (`CONTAINS`, `SOURCE_CONTAINS`) | `G_repo` bỏ `CALLS`, `IMPORTS`, `REFERENCES`, `INHERITS`, `TESTS` | **(đề xuất)** |
| `R-A1` | A1; §13.1 repo symbol graph only | §4.4: anchor từ tìm symbol theo từ khóa issue, **không** overlay | `G_repo` | **(đề xuất)** |
| `R-A2` | A2; §13.1 repo graph + task trace | anchor từ overlay task (`TaskOverlayBuilder`, không `FAIL_TO_PASS`) | `G_repo` + `G_task` | = run `full50/default` arm `graph` |
| `R-A2-f2p` | A2 có tên test fail | như `R-A2` + `FAIL_TO_PASS` | như trên | = arm `graph_f2p`; báo riêng |
| `R-A1+arch` | §13.1 repo graph + architecture lift | như `R-A1` + `use_component_dependents` | `G_repo` + `G_arch` | **(đề xuất)** |
| `R-A3` | A3 | như `R-A2` + `use_component_dependents` + `use_trace_component` | `G_repo` + `G_task` + `G_arch` | **(đề xuất)** |

Mọi cấu hình graph dùng `RetrievalConfig()` mặc định (hash đóng băng) cộng đúng các cờ ghi ở bảng, để mỗi bước chỉ khác một tầng. `RT1_CONFIG` (`may_call_factor=0.5`) đo thêm một dòng `R-A2+rt1` để nối với báo cáo RT-1, không nằm trong chuỗi A0→A3.

Cặp so sánh chính: `R-A1` vs mỗi `R-A0-*`; `R-A2` vs `R-A1`; `R-A3` vs `R-A2`. Cặp phụ (§13.1): `R-AST` vs `R-A1`; `R-A1+arch` vs `R-A1`.

## 4. Thiết kế

### 4.1 grep

Mô phỏng `rg -i -w` với từ khóa của issue: lấy các từ định danh trong `issue_symbol_text(problem_statement)` (đã có trong `grounding`), bỏ từ dừng `_TOPIC_STOP` và từ < 3 ký tự. Điểm của một file = tổng số dòng khớp mỗi từ, mỗi từ nhân `log(1 + N / df)` để từ hiếm nặng hơn; hòa thì theo đường dẫn. Đơn vị xếp hạng là chunk như BM25 (`extract_chunks`, 80 dòng, chồng 16) để chấm cùng `score_record`.

### 4.2 file-neighbor

File được nhắc trong issue (đường dẫn khớp corpus hoặc tên module) đứng đầu; sau đó các file cùng thư mục, rồi thư mục cha, theo khoảng cách thư mục; trong cùng khoảng cách xếp theo BM25. Issue không nhắc file nào thì kết quả bằng BM25 và ghi `no_mentioned_file`.

### 4.3 embedding (chờ chốt)

Repo chưa có. Hai cách:

| Cách | Cần gì | Rủi ro |
|---|---|---|
| A. Model nhỏ chạy CPU (ví dụ `sentence-transformers` với một model code công khai), nhúng chunk và issue, xếp theo cosine | Thêm thư viện và tải model (ghim phiên bản và hash) | Thêm dependency; vài phút mỗi repo lớn trên CPU |
| B. Không làm, báo cáo ghi thiếu baseline embedding | Không | M2 ghi "over grep/BM25/embedding"; [mm] đã ghi "baseline embedding chưa được kiểm chứng là có" |

Đề xuất B trong R1 lần này, A làm sau nếu nhóm cần, vì thêm dependency và model là quyết định của nhóm.

### 4.4 Anchor của R-A1

A1 không có task trace, nên không dùng `G_task`: không frame traceback, không đường dẫn/selector, không ErrorMessage, không test fail, không `TRACES_TO`. Anchor lấy như agent gọi `search_symbols` qua MCP:

1. Từ khóa = từ định danh trong `issue_symbol_text` (giống §4.1).
2. Mỗi từ khớp **tên** (không phân biệt hoa thường) của Class/Function/Method/Test trong graph; tên khớp nguyên vẹn đứng trước tên chứa từ đó.
3. Lấy tối đa `max(1, max_candidates // 2)` anchor (bằng `_anchor_seed_limit()`), xếp theo IDF của từ rồi theo id; confidence anchor 0,6 (mức grounding hiện gán cho symbol trông giống code nhưng không có đường dẫn hay tên đầy đủ; tên đầy đủ được 0,8, từ thường 0,4).
4. Gọi `retrieve(anchors, budget, issue_text=problem_statement, overlay=None, include=...)`.

Đây là xấp xỉ của "agent tự tìm symbol", không phải hành vi agent thật; báo cáo ghi rõ.

### 4.5 Recall theo component

Gold component = Component của `G_arch` có `properties.files` giao với file gold (như `trace_quality.py`). Với mỗi danh sách xếp hạng (kể cả BM25/grep), map từng mục sang Component chứa file của nó, rồi tính `gold_component_recall@k` (k = 1, 3, 5) và `gold_component_mrr`. Task có graph không có Component (repo phẳng) ghi `None` và không tính vào trung bình.

### 4.6 Chạy

- Bộ task: manifest dev 50 task có gold `~/rt1/data/manifests/w10-dev-50-gold.json` (từ RT-1), giữ `source_manifest_hash`.
- Mỗi task: tải archive tại `base_commit`, build graph một lần, chạy mọi cấu hình, ghi JSON, xóa dữ liệu task (`--prune`), chạy lại được (`--resume`), như `run_rt1_ablation.py`.
- `R-A2` và `R-A2-f2p` dùng lại `full50/default`; `R-A2+rt1` dùng lại `full50/rt1_config`. Các cấu hình khác chạy mới trên cùng 50 task.
- Ngân sách 12.000 token ([P] 972), snippet 80 dòng, cùng `include`, cùng `score_record`.
- Bộ đếm token: **(chờ chốt)** giữ bytes/4 như RT-1 để dùng lại run cũ, hay tokenizer thật (`--tokenizer-manifest`; phải chạy lại cả `R-A2`). Đề xuất giữ bytes/4 và ghi rõ trong báo cáo.

### 4.7 Thống kê

Bootstrap ghép cặp theo task (2.000 lần, seed 0) cho từng cặp ở §3: chênh trung bình, CI95, số task tốt hơn/kém đi, cho `file_recall@5`, `function_recall@5`, `component_recall@5`, MRR file, Recall@B file/hàm, `context_tokens`. Báo cả nhóm 25 task chưa dùng để chỉnh RT-1, vì 25 task kia đã dùng để chọn `RT1_CONFIG`.

## 5. Tiêu chí nghiệm thu

1. Test cho grep, file-neighbor, anchor A1, recall component trên repo nhỏ dựng trong test; A1 không đọc node/cạnh `G_task` (test: overlay có traceback vẫn cho đúng kết quả như không có).
2. `R-A2` tính lại từ code mới cho đúng số của `full50/default` trên vài task (kiểm hồi quy).
3. Mọi cấu hình chạy đủ 50/50 task hoặc ghi lý do từng task lỗi.
4. Báo cáo `docs/status/` có bảng các cấu hình, bảng các cặp với CI95, bảng ánh xạ `R-A*` ↔ A0–A3 ↔ §13.1, giới hạn (F\* xấp xỉ, A1 là mô phỏng, không có agent default, embedding nếu chưa làm, bộ đếm token), mỗi số kèm lệnh tái tạo ([plan] dòng 170).
5. Test chạy trên Windows và WSL; toàn bộ suite chỉ còn 3 test fail đã biết.

## 6. Câu hỏi còn mở

| # | Câu hỏi | Đề xuất |
|---|---|---|
| 1 | Baseline embedding | B: không làm lần này, ghi thiếu (§4.3) |
| 2 | Bộ đếm token | Giữ bytes/4 để dùng lại run RT-1 |
| 3 | Bộ task: 50 task dev, hay bộ task repair của TV1 (chưa chốt) | 50 task dev; khi TV1 chốt bộ repair, tính lại trên tập con (đã có kết quả từng task) |
| 4 | Ánh xạ `R-A*` ↔ A0–A3 | Đưa bảng §3 cho nhóm xác nhận theo E04 |
