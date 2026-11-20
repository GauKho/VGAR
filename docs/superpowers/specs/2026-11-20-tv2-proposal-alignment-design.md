# Chỉnh phần TV2 theo proposal sau T2 (design)

- Ngày: 20/11/2026 · Người làm: TV2 · Trạng thái: **chờ duyệt**
- Proposal: `D:\kltn\proposal_vgar_mcp_final_corrected.md` · Plan: `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`
  (TV2 = Layer 1–3: G_repo, G_code, G_arch, G_task, Trace, schema, retrieval, impact)
- Nguồn: đối chiếu proposal với code ngày 20/11 (36 mục lệch/chưa làm, ghi trong
  `.superpowers/sdd/2026-11-19-tv2-layer-harness/progress.md`); spec này chỉ lấy các mục của TV2.
- Bắt đầu làm khi lượt T2 `nav_k20` đã chạy xong và đã `--rescore`.

## 1. Mục đích

Đưa phần graph do TV2 phụ trách (retrieval, kết quả tool graph, G_task) và harness T2 về đúng proposal, rồi đo lại,
để T1/T2 kiểm chứng đúng phương pháp của proposal chứ không phải các lựa chọn riêng của nhóm. Người dùng chốt: chạy
xong T2 hiện tại (mốc "trước khi chỉnh"), sau đó **bám sát proposal**; cải tiến ngoài proposal để sau khi harness ổn định.

## 2. Mục tiêu, không làm, không được xảy ra

**Mục tiêu**
- `get_related_context` chạy đúng §9.2: gom hết vùng k=2 quanh các anchor bên gọi truyền vào, xếp hạng bằng 6 đặc trưng,
  đóng gói đến hết ngân sách; chỉ có một giới hạn tài nguyên rộng theo §10.5.
- Tool graph trả đúng những gì proposal nêu (§6.4 confidence/provenance của cạnh, §6.6 thông báo lỗi, §9.1 component).
- Harness T2 chạy đúng bước 1–3 của §9.1/§10.4.
- Biết từng thay đổi làm chỉ số tăng hay giảm (T1 từng bước), rồi chạy T2 v3 so với `nav_k20`.

**Không làm**
- Chỉnh trọng số xếp hạng, điểm anchor, điểm confidence của cạnh; cải tiến phạm vi A; thứ tự kết quả `search_symbols`.
- Các mục của TV1 (vòng agent đầy đủ, §10.5, §11) và TV3 (GraphDiff, §12, xác minh); chạy held-out.

**Không được xảy ra**
- Sửa `src/` khi một lượt T2 đang chạy (mỗi task cánh graph khởi động server mới từ `src/`).
- Gộp thay đổi định dạng kết quả tool (mục 7, 8) khi TV1 chưa biết (hợp đồng L6-2 của TV1).
- Dùng lại bản freeze held-out cũ: hash cấu hình xếp hạng đổi, bản freeze (đang là nháp) phải cập nhật trước khi ký.

## 3. Phạm vi

| Mục | Proposal | Việc |
|---|---|---|
| 1 | §9.2, §10.5 | Gom hết vùng k=2; giới hạn ứng viên thành giới hạn tài nguyên N |
| 2 | §9.2 | Hạt giống chỉ là `anchor_ids` |
| 3 | §6.4, §9.2 | `MAY_CALL` vào vùng k=2 với confidence đã lưu |
| 4 | §9.2 | `pack_until_budget(ranked)` thuần |
| 6 | §10.3, §9.2 | Xếp hạng theo issue của task đã gắn, không theo câu agent tự viết |
| 7 | §9.2 | Kết quả `get_related_context` chỉ còn gói context (chi tiết vào audit log) |
| 8 | §6.4 | `get_callers`/`get_callees` trả confidence và provenance |
| 9 | §9.1 | `find_task_anchors` trả cả component ứng viên |
| 10 | §6.6 | Thông báo lỗi thành anchor |
| 13 | §13.1 | Baseline "repo graph + architecture lift" trong harness |
| 15 | §9.1, §10.4 | Harness: host gắn `issue_text` và `failing_tests` |
| 16 | §10.4 | Harness: cánh graph dùng prompt `repair_with_graph_context` |
| 17 | §9.1, §10.2 | Harness: tool `get_context_subgraph` (resource k=2) |

Ngoài phạm vi, ghi vào luận văn (mục 10 của spec này): 5, 11, 12, 14 và hạt giống `TRACE_COMPONENT` của profile A3.

## 4. Cách làm (đã chọn)

| Cách | Mô tả | Quyết định |
|---|---|---|
| **(1) Đổi mặc định** | Đổi giá trị mặc định của `RetrievalConfig` và code lõi để mặc định chạy đúng proposal; giá trị cũ vẫn truyền được qua các trường cấu hình để đo trước/sau | **Chọn**: người dùng muốn code các layer bám proposal |
| (2) Cấu hình riêng | Thêm một cấu hình có tên cho server và harness, giữ mặc định cũ | Loại: code lõi vẫn để mặc định lệch, hai cấu hình song song dễ nhầm |

## 5. Thiết kế

### 5.1 Retrieval §9.2 (mục 1, 2, 3, 4, 6) — `src/vgar/graph/retrieval.py`, `sqlite_service.py`

- **Mục 1.** `RetrievalConfig.max_candidates` mặc định 100 → **N** (chọn theo 6.2, ghi là lựa chọn của nhóm theo §10.5;
  giá trị tạm 5.000 cho tới khi đo xong, test dùng hằng số chứ không ghi số cứng).
  Trần hạt giống `_anchor_seed_limit()` đang là `max_candidates // 2` → bằng N: mọi `anchor_ids` đều là hạt giống, giới hạn
  chỉ áp lên số ứng viên. Thứ tự ưu tiên khi đi graph giữ nguyên; nó chỉ còn tác dụng khi chạm N. Kết quả vẫn báo
  `traversal_limited`.
- **Mục 2.** Hạt giống = `anchor_ids` (cộng `trace_seeds` chỉ khi bật `use_trace_component`, tức profile A3).
  `use_component_seeds` mặc định → `False` (hạt giống tên thư mục). Khớp thông báo lỗi không còn thêm vào hạt giống
  (chuyển thành anchor ở mục 10); vẫn được dùng làm bằng chứng trong `task_similarity` như hiện tại.
- **Mục 3.** `may_call_factor` mặc định 0 → **1.0**: cạnh `MAY_CALL` vào vùng k=2 với đúng confidence đã lưu (0,3/0,5),
  `edge_confidence` hạ điểm khi xếp hạng. Trong `graph_rationale`, bước đi qua cạnh này ghi đúng tên `MAY_CALL`
  (chiều ngược `MAY_CALLED_BY`), không ghi `CALLS`; khi đi graph nó thuộc cùng nhóm quan hệ gọi với `CALLS`.
- **Mục 4.** `reference_budget_fraction` mặc định 0,2 → **0**: đóng gói thuần theo thứ hạng.
- **Mục 6.** `SQLiteGraphService.get_related_context`: nếu `find_task_anchors` đã lưu task cho `task_id` (`self._tasks`),
  lấy `issue_text` (thuộc tính của node Issue) và `failing_tests` của task đó để dựng overlay và xếp hạng; `issue_text`
  do bên gọi truyền chỉ dùng khi chưa có task. Giữ tham số để hợp đồng tool không đổi.

### 5.2 Kết quả tool (mục 7, 8, 9)

- **Mục 7.** Kết quả `get_related_context` giữ `diagnostics.budget` (đã ghi trong docstring tool) và
  `diagnostics.traversal_limited`; phần còn lại (`config`, `candidates`, `omissions`, `unavailable_features`, `history`)
  ghi vào audit log của lời gọi. Harness đã giữ file audit theo task, nên log kiểm chứng của T2 vẫn còn. Báo TV1.
- **Mục 8.** `get_callers`/`get_callees` (cả `depth` 1 và lớn hơn 1) trả thêm cho mỗi mục: `confidence` (lớn nhất trong
  các cạnh `CALLS` song song), `resolution`, `source_tool` (từ provenance). Thứ tự giữ nguyên. Báo TV1. Cánh
  `graph_conf` của harness bỏ đi vì server đã trả confidence.
- **Mục 9.** `find_task_anchors` trả thêm `components`: đích của cạnh `TRACES_TO` trong overlay (đã dựng bởi
  `build_trace_links`), xếp bằng `rank_component_traces` sẵn có; mỗi mục có id component, điểm, số anchor.

### 5.3 G_task: thông báo lỗi thành anchor (mục 10)

- (a) Node `ErrorMessage` (tên exception) đã nối `RESOLVES_TO` tới lớp exception (trace links): đích này thành anchor,
  loại bằng chứng `error`, điểm = confidence của trace link.
- (b) Dòng log/thông báo lỗi trong issue khớp chuỗi trong source (`diagnostic_lines` và
  `SourceEvidence.diagnostic_matches`, đang dùng trong retrieval): thành anchor, loại bằng chứng `error_message`,
  điểm 0,85 nếu khớp một chỗ, 0,5 nếu khớp nhiều chỗ (giá trị code đang dùng). Phần này cần đọc source nên đặt ở nơi có
  repository root (service); T1 gọi cùng hàm để có cùng anchor.
- Anchor mới đi qua cùng bước gộp và giới hạn của grounding như anchor hiện có, và có cạnh `MENTIONS` từ node Issue trong
  overlay như các anchor khác, để G_task vẫn qua kiểm schema.

### 5.4 Baseline arch-only (mục 13) — `baseline/profiles.py`, `baseline/report.py`

Thêm profile `A1_arch` = (`base`, `arch_no_task_trace`); arm này đã có trong `ablation_matrix/retrieval_variants.py`.
Bảng T1 so `A1_arch` với `A1`; cặp `A1 → A2` giữ nguyên để không lẫn tác dụng của G_task.

### 5.5 Harness T2 (mục 15, 16, 17) — `baseline/nav/`

- **Mục 15.** `GraphTools.BOUND` thêm `issue_text` (= `problem_statement` đầy đủ) và `failing_tests` (rỗng: SWE-bench
  không đưa test lỗi cho agent); hai tham số này bị bỏ khỏi schema hiển thị cho Qwen.
- **Mục 16.** Cánh graph lấy prompt `repair_with_graph_context` từ server (`get_prompt`; đầu vào: issue,
  `failing_tests="[]"`, `context_budget` = ngân sách harness đang dùng cho `get_related_context`), thêm một câu: lượt này
  dừng sau bước 3 và trả JSON `{files, functions}`, dùng **đúng câu yêu cầu định dạng như `nav_k20`** để so được. Cánh
  `base` giữ prompt hiện tại.
- **Mục 17.** Tool `get_context_subgraph(node_id)` = đọc resource `vgar://graph/subgraph/{node_id}?k=2`, trình bày gọn
  (node; cạnh kèm loại và confidence), cắt 1.500 token như các tool khác.
- Cánh mới tên `graph_v1` (server đã chỉnh); `graph_v0` giữ cho dữ liệu cũ.

## 6. Đo lại (sau khi code xong, chạy offline trước, GPU sau)

### 6.1 T1 từng bước — 50 task dev, bản dựng `base`, profile A2

| Bước | Cấu hình | Đo tác dụng của |
|---|---|---|
| B0 | Kết quả T1 đã có (code trước khi chỉnh) | mốc |
| B1 | Code mới, chỉ đặt lại 3 trường: N = 100, `may_call_factor` = 0, `reference_budget_fraction` = 0,2 (hạt giống thư mục vẫn tắt) | mục 2, 10 (hạt giống chỉ từ anchor; thông báo lỗi thành anchor) |
| B2 | B1 + N | mục 1 (gom hết vùng 2 bước) |
| B3 | B2 + `may_call_factor` = 1 | mục 3 (`MAY_CALL`) |
| B4 | B3 + `reference_budget_fraction` = 0 (= mặc định mới) | mục 4 (đóng gói thuần) |

Thêm profile `A1_arch`. Chỉ số như báo cáo T1 (recall@k file/hàm, MRR, `native_*`), tách nhóm đa file; thêm số lần chạm N,
thời gian mỗi lần gọi, số token gói. Các bước **không phải cổng chặn**: proposal là chuẩn, số liệu để giải thích.

### 6.2 Chọn N

Chạy B2 một lần với N rất lớn chỉ để đo; lấy phân bố số ứng viên khi đưa toàn bộ anchor (trường hợp nặng nhất).
N = mức bao được ít nhất 95% số task, với điều kiện một lần gọi trên sympy không quá 30 giây. Nếu điều kiện thời gian
không đạt, lấy N lớn nhất còn đạt và báo tỉ lệ task chạm N. Ghi N và cách chọn vào luận văn như lựa chọn của nhóm theo §10.5.

### 6.3 T2 v3

Sau khi `nav_k20` xong và `--rescore`: chỉ chạy cánh `graph_v1` trên 50 task dev (chạy thử `--limit 2` trước); cánh
`base` dùng lại kết quả của `nav_k20`, vì đường code của nó (prompt, tool, giới hạn, model, cách đọc câu trả lời) không đổi,
nên tiết kiệm khoảng một phần ba thời gian GPU. So cặp
`graph_v1` − `base` (CI 95%), so `graph_v1` với `graph_v0` của `nav_k20`, tách nhóm đa file. Ghi rõ cánh graph đổi cả
server lẫn quy trình (prompt §10.4, issue gắn sẵn, tool subgraph).

### 6.4 Sau spec này

Cập nhật bản freeze held-out (hash cấu hình mới, cánh, chỉ số) → nhóm ký → chạy held-out một lần.

## 7. Test (viết trước, xem hỏng, rồi mới sửa code)

- `RetrievalConfig()` có mặc định mới: N, `may_call_factor` 1.0, `reference_budget_fraction` 0, `use_component_seeds` False.
- Graph nhỏ có hơn 100 hàng xóm trong 2 bước: mọi hàng xóm là ứng viên, `traversal_limited` là False.
- Thư mục được nhắc trong issue và dòng log khớp source không tự thành hạt giống.
- Hàng xóm chỉ nối bằng `MAY_CALL` là ứng viên với confidence 0,3/0,5, `graph_rationale` ghi `MAY_CALL`, và xếp sau hàng xóm
  `CALLS` có cùng độ giống.
- Không có mục nào được giữ chỗ bằng ngân sách tham chiếu.
- Sau `find_task_anchors` cho một `task_id`, gọi `get_related_context` với `issue_text` rỗng hoặc rút gọn cho cùng kết quả như
  khi truyền đủ issue.
- Kết quả `get_related_context` không còn `candidates`/`config`; audit log có đủ.
- `get_callers`/`get_callees` (depth 1 và 2): mỗi mục có `confidence`, `resolution`, `source_tool`.
- `find_task_anchors`: có `components` khi có `TRACES_TO`; issue có tên exception → lớp exception là anchor `error`; dòng log
  khớp một chuỗi duy nhất → anchor `error_message` điểm 0,85.
- Harness: schema Qwen thấy không có `issue_text`, server nhận đủ issue; prompt cánh graph chứa bước 1–3 của server;
  `get_context_subgraph` trả node/cạnh có confidence.
- Các test đang ghim giá trị cũ (`tests/test_graph_retrieval.py`, `test_retrieval_rt1.py`, `test_rt1_ablation.py`,
  `test_run_graph_retrieval_config.py`, `test_scip_enrichment.py`, `test_source_evidence.py`): sửa giá trị kỳ vọng, hoặc
  truyền cấu hình cũ tường minh khi test đang kiểm hành vi cũ.

## 8. Rủi ro

- `MAY_CALL` nhiều (django: 54 nghìn so với 21 nghìn `CALLS`) → nhiều ứng viên nhiễu; B3 sẽ cho thấy.
- N lớn → chậm trên repo lớn; 6.2 đặt điều kiện thời gian.
- Mục 10(b) đọc source trong `find_task_anchors` → lần gọi đầu chậm hơn; đo thời gian.
- Mặc định đổi → vòng sửa lỗi của TV1 đổi theo; mục 7, 8 đổi định dạng kết quả tool → báo TV1 trước khi gộp.
- Hash cấu hình đổi → các kết quả R1/T1/T2 cũ gắn với cấu hình cũ; báo cáo ghi rõ "trước khi chỉnh".

## 9. Để lại cho người làm

Giá trị N (theo 6.2); tên trường mới trong kết quả tool (theo kiểu envelope đang dùng); cách truyền cấu hình các bước
B1–B3 (profile trong `baseline/profiles.py` hoặc tham số của runner); cách gộp anchor lỗi với anchor hiện có khi trùng node.

## 10. Ghi vào luận văn (các mục không làm)

- Mục 5: trọng số do nhóm chọn; kiểm chứng mức 2 trên dev cho thấy trọng số chỉ quyết định khoảng 7% hàm gold;
  `recent_change_frequency` không có vì bộ dữ liệu không kèm lịch sử commit.
- Mục 11: tín hiệu co-change của Lift không có (cần lịch sử commit).
- Mục 12: F\*_approx chỉ gồm hàm (spec 17/11 §2.4).
- Mục 14: chất lượng ranh giới component chờ nhãn người.
- Hạt giống `TRACE_COMPONENT` (`use_trace_component`) chỉ thuộc profile A3, nằm ngoài vòng lặp §9.2; giữ nguyên.
