# Bảng tra tên: proposal → code (22/11/2026)

Proposal: `D:\kltn\proposal_vgar_mcp_final_corrected.md`. Đối chiếu bằng grep trên working tree ngày 22/11 (gồm thay
đổi chưa commit của plan alignment). Mục lệch nội dung xem `tv2_proposal_gaps_2026-11-20.md`; bảng này chỉ trả lời
"tên trong proposal nằm ở đâu trong code".

Quy ước: **=** cùng tên · **≈** khác tên, cùng vai trò · **✗** chưa có.

Không đổi tên trong code vì: tên tool/resource/prompt đã đúng §10; tên trong §6, §7, §9 là pseudo-code minh họa;
đổi tên loại node/cạnh hoặc tham số tool sẽ đổi định dạng graph và hợp đồng MCP (phải dựng lại graph, đổi hash cấu
hình và bản freeze, TV1/TV3 đang dùng). Nếu nhóm muốn đổi, làm một lần sau khi đo xong và báo TV1/TV3.

## 1. MCP (§10)

### 1.1 Tool (§10.3) — server `vgar-graph` (`src/vgar/mcp/servers/graph_server.py`) và server thực thi

| Proposal | Code | | Ghi chú |
|---|---|---|---|
| `build_or_update_graph(repo_path)` | `build_or_update_graph` | = | Repo lấy từ cấu hình host, không nhận `repo_path` |
| `search_symbols(query)` | `search_symbols` | = | |
| `find_task_anchors(issue_text)` | `find_task_anchors(issue_text, graph_version, task_id, failing_tests)` | = | §9.1 gọi là `search_task_anchors` (proposal tự khác tên) |
| `get_related_context(anchor_ids, budget_tokens)` | `get_related_context` | = | Đây là `extract_context_graph` của §9.2 |
| `get_callers(symbol_id, depth)` / `get_callees` | `get_callers` / `get_callees` | = | |
| `explain_dependency_path(source_id, target_id)` | `explain_dependency_path` | = | |
| `analyze_patch_impact(repo_path, diff, max_depth)` | `analyze_patch_impact(diff, graph_version, max_hops)` | ≈ | Khác tên tham số |
| `verify_patch_graph_constraints(diff)` | `verify_patch_graph_constraints` | = | |
| `run_relevant_tests(diff)` | `run_relevant_tests` | = | Server thực thi |
| `rank_patch_candidates(candidates)` | `rank_patch_candidates` | = | |
| — | `read_file`, `get_related_tests`, `run_pytest`, `health` | | Thêm ngoài §10.3 |

### 1.2 Resource (§10.2) — `src/vgar/mcp/proposal/resources.py`, `graph_server.py`

| Proposal | Code | |
|---|---|---|
| `vgar://repo/summary`, `vgar://repo/schema` | cùng URI | = |
| `vgar://graph/node/{node_id}` | cùng URI | = |
| `vgar://graph/subgraph/{node_id}?k=2` (= `get_context_subgraph(anchor, k=2)` của §9.1) | cùng URI; alias `vgar://graph/subgraph/{node_id}` | = |
| `vgar://component/{id}`, `vgar://task/{id}`, `vgar://evidence/baseline`, `vgar://audit/log` | cùng URI | = |
| `get_context_subgraph` dạng tool | Chỉ có trong harness T2: `baseline/nav/tools.py` (`SUBGRAPH_TOOL`) | ≈ |

### 1.3 Prompt (§10.4)

| Proposal | Code | |
|---|---|---|
| `repair_with_graph_context(issue_text, failing_tests, context_budget)`, 7 bước | `src/vgar/mcp/proposal/prompts.py` (`PROMPT_NAME`, `WORKFLOW`) | = |

## 2. Dựng graph (§5, §6)

| Proposal | Code | |
|---|---|---|
| `ArchCPGBuilder.build(repo_path, task)` | `PythonGraphBuilder.build(repository_root)` — `src/vgar/graph/builder.py:116,180`; G_task dựng riêng theo task (dưới) | ≈ |
| `parse_with_tree_sitter` / `extract_repo_entities` | trong `PythonGraphBuilder.build`; luật Layer 1 ở `graph/layer1_rules.py`; tree-sitter-graph ở `graph/tsg_extractor.py` | ≈ |
| `build_or_load_scip_index` / `link_symbols` | `graph/scip_resolver.py` (`ScipResolver`), LSP ở `graph/lsp_resolver.py`, JARVIS ở `graph/jarvis_runner.py` + `jarvis_merge.py`; cạnh đoán `graph/may_call.py` | ≈ |
| `build_code_graph` (G_code) | `PythonGraphBuilder._run_joern` + `_add_code_graph` (`builder.py:1924,2052`), chuyển đổi ở `graph/code_graph.py`; chỉ khi bật Joern (bản dựng `full`, Docker) | ≈ |
| `lift_to_architecture` | `arch_lift.lift(...)` — `graph/arch_lift.py:344` | ≈ |
| `extract_task_graph(issue_text, failing_tests)` | `task_graph.extract_task_facts` (`graph/task_graph.py:169`) + `TaskOverlayBuilder.build` (`graph/task_overlay.py:37`) | ≈ |
| `parse_stack_trace` | trong `extract_task_facts` (node `StackTraceFrame`) | ≈ |
| `build_trace_links` | `trace_links.build_trace_links` (`graph/trace_links.py:39`); `rank_component_traces` (dòng 80) | = |
| `load_schema` / `validate_schema` (S, §8.4) | `contracts/schema.py` (`validate_graph_document`, dòng 404; `EDGE_PROPERTIES`, `INVARIANTS`) | ≈ |
| `collect_baseline_evidence` | resource `vgar://evidence/baseline` | ≈ |
| Bản dựng theo lớp (§5.2) | `baseline/profiles.py`: `base`, `scip`, `scip_lsp`, `full`; cấu hình lớp `graph/layer_config.py` (`LayerConfigs`) | ≈ |

## 3. Loại node và cạnh khác tên (§4, §6.3–6.4)

| Proposal | Code |
|---|---|
| `TestCase` | `Test` |
| `Class --HAS_METHOD--> Method`, `Method --HAS_CALLSITE--> CallSite` | `CONTAINS` |
| `CallSite --RESOLVES_TO--> Method` | `CALLS` (từ CallSite) |
| `Interface` | không có (Python) |
| `TESTS: Test -> Requirement` (G_task) | chưa có (mục lệch #42) |

Các loại còn lại (Module, File, Class, Function, Method, Field, GlobalVariable, ConfigEntry, Route, Schema, Component,
Port, Connector, Service, DeploymentUnit, ExternalSystem, Issue, BugReport, Requirement, UserStory, AcceptanceCriterion,
FailingTest, ErrorMessage, StackTraceFrame, Constraint, Actor; IMPORTS, CALLS, INHERITS, IMPLEMENTS, REFERENCES, TESTS,
CONFIGURES, DEPENDS_ON, EXPOSES_PORT, CONSUMES_PORT, COMMUNICATES_WITH, CONTAINS_COMPONENT, DEPLOYS_TO, MENTIONS,
TRACES_TO, CONFLICTS_WITH, REPRODUCES, MAY_CALL, AST_CHILD, CFG_NEXT, DATA_DEPENDS_ON, CONTROL_DEPENDS_ON) cùng tên.

## 4. GraphDiff (§7) — `src/vgar/graph/graphdiff.py`

| Proposal | Code |
|---|---|
| Pipeline §7.3 | `run_graphdiff` (dòng 482) |
| Graph edit có confidence/provenance (§7.2) | `GraphEdit` (dòng 100); `type_commit_edits` (dòng 209) |
| `confidence(edit)` (§7.4) | `score_edit` (dòng 439), trọng số `_default_weights` |
| AST diff (GumTree) | `graph/ast_diff.py`; RefactoringMiner ở `graph/refactorings.py` |

## 5. Workflow và retrieval (§8, §9)

| Proposal | Code | |
|---|---|---|
| `extract_context_graph(task_anchors, k=2, budget_tokens=12000)` (§9.2) | `GraphContextRetriever.retrieve` (`graph/retrieval.py:141,193`); đi graph `_walk` (dòng 677); phục vụ qua tool `get_related_context` | ≈ |
| `rank_by(features=[...])` | `RetrievalConfig.weights` (`retrieval.py`), đặc trưng trong `retrieve` | ≈ |
| `pack_until_budget` | trong `retrieve` (`reference_budget_fraction = 0`) | ≈ |
| Giới hạn tài nguyên (§10.5) | `RESOURCE_LIMIT_CANDIDATES = 6000`; host đặt `VGAR_RETRIEVAL_MAX_CANDIDATES` | ≈ |
| Impact (§9.3): Touched, Impact_k, risk features | `impact.diff_to_nodes` (dòng 135), `compute_impact` (dòng 290), `analyze_patch_impact` (dòng 492) — `graph/impact.py` | ≈ |
| `F*` dependency frontier (§8.2) | `baseline/frontier_v2.py` (`frontier_core_v2`, dòng 35) | ≈ |
| `Evidence(patch)` 9 trường, `score(patch)` (§8.5) | `repair/patch_evidence.py` (`score_patch`, dòng 276) | ≈ |
| Agent loop §9.1 | ✗ chưa có agent trọn vòng (mục #18); harness T2 bước 1–3: `baseline/nav/run_nav.py` | ✗ |

## 6. Cập nhật dần và kiểm patch (§11, §12)

| Proposal | Code |
|---|---|
| `incremental_update(changed_files)` (§11.2) | `IncrementalGraphBuilder.update` (`graph/incremental.py:165,185`) |
| Schema check (§12.1) | `contracts/schema.py` (`validate_graph_document`) |
| Port/API check (§12.2–12.3) | `graph/port_check.py` (`check_lost_ports`), `graph/return_contracts.py` |
| Test chọn lọc (§12.5) | `graph/test_selection.py`; tool `run_relevant_tests` |
| Kiểm patch tổng hợp | `repair/patch_evidence.py` (`verify_patch`, dòng 64) |
| Invariant (§12.4) | `repair/daikon.py` |

## 7. Đánh giá (§13)

| Proposal | Code / tên trong kết quả |
|---|---|
| A0 (no graph) | cánh T2 `base` (thư mục), gọi là no-graph trong báo cáo |
| A1 / A2 / A3 (§13.3) | profile T1 `A1`, `A2`, `A3` (`baseline/profiles.py`); chỉ phần retrieval |
| AST-only, repo graph + arch lift (§13.1) | profile `P0`, `A1_arch` |
| A4 / A5 | ✗ (mục #20) |
| `gold_file_recall@k`, `gold_function_recall@k` | `file_recall@k`, `function_recall@k` |
| `dependency_frontier_recall@B` | `packed_frontier_in_context`, `native_frontier_in_context` (T1); `seen_frontier_recall` (T2) |
| `mean reciprocal rank` | `file_mrr`, `function_mrr` |
| `context token cost` | `context_tokens`, `native_context_tokens` |
| `tool calls per task`, `average tool latency`, `unnecessary file reads avoided` | `tool_calls`, `mean_tool_seconds`, `non_gold_files_read` (T2) |
