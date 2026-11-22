# Chỉnh phần TV2 theo proposal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa retrieval, kết quả tool graph, G_task và harness T1/T2 của TV2 về đúng proposal (13 mục của spec), rồi đo lại T1 từng bước và T2 v3.

**Architecture:** Đổi mặc định của `RetrievalConfig` và code lõi để mặc định chạy đúng §9.2; thông báo lỗi thành anchor ở overlay G_task; server trả confidence cho callers/callees và chỉ trả gói context; harness có cánh `graph_v1` (issue gắn sẵn, prompt §10.4, tool subgraph). Đo bằng các runner sẵn có (`baseline/run_offline.py`, `baseline/nav/run_nav.py`, `ablation_matrix/compare_runs.py`, `baseline/nav/nav_paired.py`).

**Tech Stack:** Python 3.11, SQLite, MCP SDK 2.2 (stdio), pytest; chạy đo trong WSL (`~/.vgar-wsl`), Qwen3-4B 4-bit trên RTX 4050.

**Spec:** `docs/superpowers/specs/2026-11-20-tv2-proposal-alignment-design.md` (đã duyệt 20/11; danh sách lệch: `docs/status/tv2_proposal_gaps_2026-11-20.md`).

## Global Constraints

- Proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md` là chuẩn; con số proposal không cho thì ghi là lựa chọn của nhóm.
- Không commit/push (người dùng tự commit). Làm trong `D:\kltn\vgar_mcp_mvp_demo`, không dùng worktree.
- Không sửa code dựng graph (`builder.py`, resolver, `arch_lift.py`).
- Test trên Windows: `.venv/Scripts/python.exe -m pytest <paths> -q -p no:cacheprovider`; lint: `.venv/Scripts/ruff.exe check <paths>` (không thêm lỗi mới so với HEAD).
- Chạy đo trong WSL: `MSYS_NO_PATHCONV=1 wsl -e bash -lc 'cd /mnt/d/kltn/vgar_mcp_mvp_demo && PYTHONPATH=src ~/.vgar-wsl/bin/python ...'`; **không chạy hai việc nặng cùng lúc** (thiếu RAM đã làm hỏng một lượt T2); kiểm không có tiến trình `run_nav`/`run_offline` nào đang chạy trước khi bắt đầu.
- Server MCP: không in ra stdout, mỗi module một logger, docstring có `Args` (luật build-server 28/07).
- Đổi định dạng kết quả tool chỉ theo kiểu thêm trường, trừ mục 7 (bỏ `diagnostics` lớn khỏi kết quả, chuyển vào audit log).
- Giới hạn tài nguyên tạm `RESOURCE_LIMIT_CANDIDATES = 5000` cho tới khi Task 6 chọn N.

## Review Focus

1. Graph cỡ sympy với toàn bộ anchor của G_task: chạm N phải trả `traversal_limited`, không tràn bộ nhớ, thời gian mỗi lần gọi đo được (Task 6 ghi lại).
2. Issue không có dòng log: `message_matches` không được đọc hay parse source (đa số task) — test ở Task 2.
3. `get_related_context` gọi khi chưa có `find_task_anchors` cho `task_id`: dùng `issue_text` được truyền như cũ — test ở Task 3.
4. Graph không có node Component: `find_task_anchors` trả `components: []`, không lỗi — test ở Task 2.
5. `get_callers`/`get_callees` với `depth` > 1 qua đường `traverse` cũ vẫn có confidence; đường traversal của proposal (đã có `evidence_edges`) không đổi — test ở Task 3.

---

### Task 1: Retrieval theo §9.2 (mục 1, 2, 3, 4)

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`RetrievalConfig`, `_anchor_seed_limit`, `_index_relations`, `_walk`, `_path_similarity`, `retrieve`)
- Modify: `ablation_matrix/retrieval_variants.py` (giới hạn anchor tìm theo tên của arm `symbols`)
- Test: `tests/test_retrieval_proposal_alignment.py` (mới); sửa kỳ vọng trong `tests/test_graph_retrieval.py`, `tests/test_retrieval_rt1.py`, `tests/test_rt1_ablation.py`, `tests/test_run_graph_retrieval_config.py`, `tests/test_scip_enrichment.py`, `tests/test_source_evidence.py`, `ablation_matrix/tests/*` khi chúng ghim giá trị cũ

**Interfaces:**
- Produces: `RESOURCE_LIMIT_CANDIDATES: int = 5000`; `RetrievalConfig()` mặc định `max_candidates=RESOURCE_LIMIT_CANDIDATES`, `may_call_factor=1.0`, `reference_budget_fraction=0.0`, `use_component_seeds=False`; `_anchor_seed_limit() -> int` trả `max_candidates`; hằng `_SEMANTIC_RELATIONS` gồm `CALLS, CALLERS, TESTS, TESTED_BY, MEMBER_REFERENCE, MEMBER_REFERENCED_BY, MAY_CALL, MAY_CALLED_BY` dùng ở cả 4 chỗ đang chép cứng; cạnh `MAY_CALL` gấp vào adjacency với nhãn `MAY_CALL`/`MAY_CALLED_BY`; `retrieve` không đưa khớp thông báo lỗi vào hạt giống (vẫn dùng làm `diagnostic_scores` cho độ giống). `retrieval_variants.SYMBOL_ANCHOR_LIMIT = 50` thay cho `retriever._anchor_seed_limit()` ở arm `symbols`.

- [ ] **Step 1: Viết test hỏng** trong `tests/test_retrieval_proposal_alignment.py`, dùng helper dựng document sẵn có của `tests/test_graph_retrieval.py`:
  - `test_default_config_follows_proposal_9_2`: `RetrievalConfig()` có 4 giá trị mặc định trên.
  - `test_every_two_hop_neighbour_is_a_candidate_past_the_old_cap`: anchor gọi 150 hàm → ≥ 150 ứng viên, `traversal_limited is False`.
  - `test_mentioned_directory_and_log_line_do_not_seed`: issue nhắc tên thư mục và một dòng `ERROR: ...` khớp chuỗi trong code; một anchor → không ứng viên nào có `graph_rationale[0]` là `SOURCE_COMPONENT` hay `SOURCE_DIAGNOSTIC`.
  - `test_may_call_neighbour_is_walked_with_its_stored_confidence`: chỉ có cạnh `MAY_CALL` 0,5 → hàng xóm là ứng viên, `confidence == 0.5`, `graph_rationale` chứa `MAY_CALL:`.
  - `test_no_budget_is_reserved_for_reference_dependencies`: `result.config["reference_reserved_tokens"] == 0`.
  - `ablation_matrix/tests/test_retrieval_variants.py::test_symbol_arm_keeps_at_most_50_anchors`: arm `no_task_trace` có ≤ 50 anchor với mặc định mới.
- [ ] **Step 2:** Chạy `.venv/Scripts/python.exe -m pytest tests/test_retrieval_proposal_alignment.py ablation_matrix/tests/test_retrieval_variants.py -q -p no:cacheprovider` → Expected: các test mới FAIL vì mặc định cũ.
- [ ] **Step 3:** Sửa code theo Interfaces.
- [ ] **Step 4:** Chạy lại Step 2 → PASS. Chạy 6 file test đang ghim giá trị cũ và `ablation_matrix/tests`; với mỗi test hỏng, nếu test kiểm hành vi cũ thì truyền cấu hình cũ tường minh, nếu chỉ ghim giá trị mặc định/hash thì cập nhật kỳ vọng. Ghi ruling cho từng hash đổi.
- [ ] **Step 5:** Ruff các file đã sửa (không thêm lỗi mới).

### Task 2: Thông báo lỗi thành anchor, component ứng viên (mục 9, 10)

**Files:**
- Modify: `src/vgar/graph/source_evidence.py` (hàm mới `message_matches`)
- Modify: `src/vgar/graph/task_overlay.py` (`TaskOverlayBuilder.build`)
- Modify: `src/vgar/graph/sqlite_service.py` (`find_task_anchors`)
- Modify: `ablation_matrix/retrieval_variants.py` (`variant_outputs`), `baseline/run_offline.py` (truyền `sources`)
- Test: `tests/test_task_overlay_error_anchors.py` (mới)

**Interfaces:**
- Consumes: Task 1 (`retrieve` không còn tự gieo hạt từ thông báo lỗi).
- Produces: `message_matches(nodes, verified_sources, issue_text) -> dict[str, list[str]]` (rỗng và không đọc source khi `diagnostic_lines(issue_symbol_text(issue_text))` rỗng); `TaskOverlayBuilder.build(task_id, issue_text, failing_tests=None, *, labels=None, sources: Mapping[str, str] | None = None) -> TaskOverlay` thêm anchor `error` (đích `RESOLVES_TO` của node `ErrorMessage`, điểm = confidence của trace link) và, khi có `sources`, anchor `error_message` (0,85 nếu một node khớp, 0,5 nếu nhiều node), mỗi anchor mới có cạnh `MENTIONS` từ Issue; anchor trùng node thì gộp bằng chứng và lấy điểm lớn hơn; giữ thứ tự sắp xếp hiện có của `grounding.anchors`. `find_task_anchors` trả thêm `components: list[{"component_id", "confidence", "anchor_count"}]` từ `rank_component_traces` trên các cạnh `TRACES_TO` của overlay, và truyền source đã kiểm hash (`retriever._verify_snapshot()` của retriever mặc định) vào `build`. `variant_outputs(..., sources: Mapping[str, str] | None = None)` truyền xuống `build`.

- [ ] **Step 1: Viết test hỏng** trong `tests/test_task_overlay_error_anchors.py`:
  - `test_exception_named_in_the_issue_becomes_an_error_anchor`: repo có `class WidgetError(Exception)`, issue có traceback `WidgetError: bad` → anchor trên node lớp đó với bằng chứng `error` và có cạnh `MENTIONS`.
  - `test_log_line_matching_one_string_literal_is_an_error_message_anchor_0_85` và `..._two_functions_share_0_5`.
  - `test_without_sources_no_error_message_anchor_is_added`.
  - `test_issue_without_log_lines_never_reads_sources`: `sources` là mapping ném lỗi khi bị đọc → không lỗi, không anchor mới.
  - `test_find_task_anchors_lists_traced_components` và `test_find_task_anchors_without_components_returns_empty_list`.
- [ ] **Step 2:** Chạy file test → Expected: FAIL (`build()` chưa nhận `sources`; chưa có `components`).
- [ ] **Step 3:** Sửa code theo Interfaces.
- [ ] **Step 4:** Chạy file test → PASS; chạy `tests/test_graph_retrieval.py tests/test_mcp_tool_contract.py ablation_matrix/tests` → PASS.
- [ ] **Step 5:** Ruff.

### Task 3: Kết quả tool phía server (mục 6, 7, 8)

**Files:**
- Modify: `src/vgar/graph/sqlite_store.py` (`StoredSymbol`, `get_callers`, `get_callees`)
- Modify: `src/vgar/contracts/graph.py` (model `SymbolRelation`)
- Modify: `src/vgar/graph/sqlite_service.py` (`get_related_context`, `get_callers`, `get_callees`, `traverse`)
- Modify: `src/vgar/mcp/servers/graph_server.py` (`get_related_context`)
- Test: `tests/test_graph_tools_proposal_alignment.py` (mới); sửa `tests/test_mcp_tool_contract.py`, `tests/test_mcp_day5.py`, `tests/test_w3_w4_graph_resources.py` nếu ghim định dạng cũ

**Interfaces:**
- Produces: `StoredSymbol` thêm `confidence: float | None = None`, `resolution: str | None = None`, `source_tool: str | None = None`; SQL callers/callees nhóm theo symbol, lấy `MAX(call_edge.confidence)` cùng `resolution` và `provenance_json` của cạnh đó (SQLite trả cột trần theo hàng có max), `source_tool` đọc từ provenance; thứ tự giữ nguyên. `SymbolRelation(SymbolRef)` thêm 3 trường đó; `SymbolRelationsResult.symbols: list[SymbolRelation]`; `traverse()` thêm 3 trường vào mỗi symbol. `SQLiteGraphService.get_related_context`: nếu `self._tasks` có `task_id`, dùng `issue_text`/`failing_tests` của node Issue đã lưu (`trace_nodes[0]["properties"]`). Tool `get_related_context` trả `diagnostics = {"traversal_limited", "budget"}`; phần còn lại vào audit qua `summarize`.

- [ ] **Step 1: Viết test hỏng**:
  - `test_callers_carry_the_confidence_resolution_and_tool_of_their_best_call_edge` (hai call site 0,6 và 0,9 → 0,9).
  - `test_depth_two_traversal_keeps_confidence`.
  - `test_related_context_ranks_against_the_task_bound_by_find_task_anchors` (sau `find_task_anchors` với issue đầy đủ, gọi lại với `issue_text` rút gọn → cùng danh sách item như khi truyền đủ).
  - `test_related_context_without_a_bound_task_uses_the_given_issue_text`.
  - `test_related_context_result_keeps_only_budget_and_traversal_flag` và `test_related_context_audit_line_holds_the_full_diagnostics` (qua tool server thật, như test hiện có trong `tests/test_mcp_tool_contract.py`).
- [ ] **Step 2:** Chạy → Expected: FAIL.
- [ ] **Step 3:** Sửa code theo Interfaces.
- [ ] **Step 4:** Chạy test mới và các test MCP hiện có → PASS.
- [ ] **Step 5:** Ruff.

### Task 4: Harness T1 (mục 13; phục vụ đo từng bước)

**Files:**
- Modify: `baseline/profiles.py`, `baseline/report.py`, `baseline/run_offline.py`
- Test: `baseline/tests/test_profiles.py`, `test_report.py`, `test_run_offline.py`

**Interfaces:**
- Consumes: `variant_outputs(..., sources=...)` (Task 2).
- Produces: `PROFILES["A1_arch"] = ("base", "arch_no_task_trace")`; `report.BASELINE_PROFILE = {"A1_arch": "A1"}` (so với profile mốc này, không chen vào chuỗi A1 → A2); `run_offline --arm-flags JSON` áp cùng cờ `RetrievalConfig` cho mọi arm graph; metrics mỗi profile thêm `candidate_count`, `traversal_limited`.

- [ ] **Step 1:** Test hỏng: `test_a1_arch_profile_uses_the_arch_arm_on_the_base_build`; `test_layer_table_compares_a1_arch_with_a1_and_keeps_a2_against_a1`; `test_arm_flags_reach_every_graph_arm` (truyền `{"max_candidates": 7}` → `result.config["max_candidates"] == 7` trong diagnostics); `test_metrics_record_candidate_count_and_traversal_flag`.
- [ ] **Step 2:** Chạy `baseline/tests` → FAIL ở các test mới.
- [ ] **Step 3:** Sửa code.
- [ ] **Step 4:** `baseline/tests` → PASS; ruff `baseline`.

### Task 5: Harness T2 — cánh `graph_v1` (mục 15, 16, 17)

**Files:**
- Modify: `baseline/nav/tools.py`, `baseline/nav/run_nav.py`
- Test: `baseline/tests/test_nav_tools.py`, `baseline/tests/test_run_nav.py`

**Interfaces:**
- Consumes: server đã chỉnh (Task 1–3).
- Produces: `GraphTools(tree, db, graph_version, task_id, audit_log, *, issue_text: str | None = None, context_budget=1000, timeout_seconds=300)`; khi có `issue_text`: gắn sẵn `issue_text` (đầy đủ) và `failing_tests=None` cho tool nào có hai tham số này, bỏ chúng khỏi schema; thêm tool `get_context_subgraph(node_id)` đọc resource `vgar://graph/subgraph/{node_id}?k=2` (node; cạnh kèm loại và confidence; cắt 1.500 token); `async GraphTools.prompt() -> tuple[str, str]` lấy prompt `repair_with_graph_context` (`failing_tests="[]"`, `context_budget=str(self.context_budget)`) → (tin hệ thống = phần quy trình + câu "This run stops after step 3" + đúng câu yêu cầu định dạng trả lời của `SYSTEM_PROMPT`, tin người dùng = phần JSON task). `run_task(..., prompt: tuple[str, str] | None = None)`; `ARMS["graph_v1"] = "base"`, `PROPOSAL_ARMS = {"graph_v1"}`; bỏ cánh `graph_conf`, `CONFIDENCE_ARMS`, `with_confidence`, `_add_confidence`, `edge_evidence`, `_EDGE_SQL` và test của chúng.

- [ ] **Step 1:** Test hỏng (server thật trên graph nhỏ, như các test hiện có): `test_proposal_mode_hides_and_binds_issue_text_and_failing_tests`; `test_find_task_anchors_receives_the_full_issue`; `test_get_context_subgraph_returns_typed_edges_with_confidence`; `test_prompt_follows_the_server_workflow_and_keeps_the_answer_format`; `test_run_task_uses_the_given_prompt`; `test_graph_v1_arm_is_known_and_graph_conf_is_gone`.
- [ ] **Step 2:** Chạy `baseline/tests` → FAIL ở các test mới.
- [ ] **Step 3:** Sửa code.
- [ ] **Step 4:** `baseline/tests` → PASS; ruff `baseline`.
- [ ] **Step 5:** Chạy cả bộ test của repo: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -x --ignore=.claude` (ghi số pass/fail; lỗi đã biết từ trước thì ghi tên).

### Task 6: Đo T1 từng bước và chọn N (chạy trong WSL, không GPU)

**Files:**
- Modify (nếu N ≠ 5000): `src/vgar/graph/retrieval.py` (`RESOURCE_LIMIT_CANDIDATES`)
- Create: `docs/status/tv2_proposal_alignment_results_2026-11-21.md`

- [ ] **Step 1:** Chạy đo kích thước: `run_offline.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/align_nhuge --profiles A2 --arm-flags '{"max_candidates": 100000, "may_call_factor": 0.0, "reference_budget_fraction": 0.2}'` (lượt đầu dựng lại graph do hash nguồn đổi, khoảng 12 phút). Expected: 50 task SUCCEEDED; có `candidate_count`, `retrieve_seconds`.
- [ ] **Step 2:** Chọn N theo spec 6.2 (bao ≥ 95% task, một lần gọi trên sympy ≤ 30 giây; không đạt thì lấy N lớn nhất còn đạt và báo tỉ lệ chạm N). Nếu N ≠ 5000: sửa hằng số và test, ghi ruling.
- [ ] **Step 3:** Chạy B1 `--arm-flags '{"max_candidates": 100, "may_call_factor": 0.0, "reference_budget_fraction": 0.2}'` → `align_b1`; B2 `'{"may_call_factor": 0.0, "reference_budget_fraction": 0.2}'` → `align_b2` (bỏ qua nếu N ≥ số ứng viên lớn nhất ở Step 1: dùng lại `align_nhuge`); B3 `'{"reference_budget_fraction": 0.2}'` → `align_b3`; B4 không cờ → `align_b4`; profile `A1,A1_arch` không cờ → `align_arch`. Mỗi lượt chạy xong mới chạy lượt sau.
- [ ] **Step 4:** So cặp: `compare_runs.py ~/rt1/results layers align_b1`, `align_b1 align_b2`, `align_b2 align_b3`, `align_b3 align_b4` (và `--min-gold-files 2`); `report.py --layers ~/rt1/results/align_arch`. Ghi bảng vào file kết quả.

### Task 7: T2 v3 (GPU)

- [ ] **Step 1:** Kiểm không có tiến trình nặng nào; chạy thử `run_nav.py ... --out ~/rt1/results/nav_v3 --arms graph_v1 --limit 2`. Expected: 2 lượt OK, log có `find_task_anchors` với issue đầy đủ.
- [ ] **Step 2:** Chạy đủ: cùng lệnh với `--resume` và bỏ `--limit` (khoảng 1,5–2 giờ). Sau đó `--rescore`.
- [ ] **Step 3:** Liên kết kết quả cũ để so cặp: `ln -s ~/rt1/results/nav_k20/base ~/rt1/results/nav_v3/base` và `ln -s ~/rt1/results/nav_k20/graph_v0 ~/rt1/results/nav_v3/graph_v0`; chạy `nav_paired.py ~/rt1/results/nav_v3 --arms base,graph_v1` và `--arms graph_v0,graph_v1`.
- [ ] **Step 4:** Ghi bảng vào file kết quả; cập nhật báo cáo harness, ledger, memory.
