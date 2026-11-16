# Kế hoạch 2 tuần: build MCP server VGAR và ra kết quả test (3 thành viên)

> **ĐỀ XUẤT, CHƯA ĐƯỢC NHÓM DUYỆT.** Soạn ngày 07/11/2026, bản sửa lần 2.
>
> **Nguyên tắc của bản này:**
> 1. Chỉ dùng 5 nguồn ở bảng dưới.
> 2. Mọi hạng mục mà các nguồn nêu ra đều có task.
> 3. Không xếp task nào vào hay ra khỏi phạm vi.
> 4. Chỗ nào nguồn ghi "không áp dụng", "optional" hoặc "chưa kiểm chứng" thì chép đúng lời nguồn vào cột Ghi chú. Đó là lời của nguồn, không phải quyết định phạm vi.
>
> Chia vai và lịch theo ngày là phần sắp xếp thêm để thành plan; các nguồn không quy định.

## Nguồn

| Mã | Nguồn | Vị trí |
|---|---|---|
| **[P]** | Proposal VGAR-MCP (Final corrected draft, 2026-06-18) | `D:\kltn\proposal_vgar_mcp_final_corrected.md` (dẫn theo § và số dòng) |
| **[test]** | Phân biệt test server và đo metric; quy trình 3 tầng | `C:\Users\nlhnh\Downloads\test.txt` |
| **[rq]** | Dataset, dữ liệu cần cho từng metric, điều kiện §8.3 | `C:\Users\nlhnh\Downloads\rq metrics matrix.txt` |
| **[mm]** | Metric và ma trận §11–§15, milestone §14 | `C:\Users\nlhnh\Downloads\metrics matrix.txt` |
| **[cp]** | Đối chiếu tool của proposal với repo; cách build graph Python theo §6–§10 | `C:\Users\nlhnh\Downloads\check proposal.txt` |

---

## 1. Những điều các nguồn đã làm rõ

### 1.1 Phạm vi ngôn ngữ và sản phẩm

- Graph được build cho **code Python** ([cp] Phần 2: "Theo §6–§10, graph cho code Python được build như thế nào").
- Sản phẩm là **MCP server** đưa graph ra cho coding agent ([P] §10.1, §18: "graph infrastructure layer cho coding agents").
- Server đang dùng `FastMCP` của SDK 1.x, **chưa phải `MCPServer` của SDK 2.x** ([cp] Phần 1, Layer 6).
- Kết nối phải được kiểm tra bằng Inspector ở cả `modern` lẫn `legacy`, và nối thử vào Claude Code ([test] mục 1).

### 1.2 Tình trạng 6 layer ([P] §5.2; [cp] Phần 1)

| Layer | Tool trong [P] | Trong repo ([cp]) |
|---|---|---|
| 1 | tree-sitter | ✅ `tree-sitter-python`, kèm `ast`/`symtable` |
| 1 | tree-sitter-graph | ❌ Chưa có |
| 2 | SCIP | ✅ `scip-python` 0.6.6 |
| 2 | LSP | ✅ `pyright-langserver` |
| 2 | PyCG/JARVIS | ❌ Chưa có |
| 2 | ts-morph, SootUp/WALA | ➖ "Không áp dụng cho Python" ([cp]) |
| 3 | Joern, CodeQL, Glean, Kythe | ❌ Chưa có; schema không có cạnh CFG hay dataflow |
| 4 | GumTree/DAT-GumTree, RefactoringMiner, UTango | ❌ Chưa có; chỉ có diff dạng text |
| 5 | Daikon-style | ❌ Chưa có |
| 5 | test runner, type checker, linter | ✅ pytest, mypy, ruff |
| 6 | SQLite | ✅ |
| 6 | Kùzu/Neo4j | ❌ Chưa có ("proposal để tùy chọn", [cp]) |
| 6 | MCP SDK | ✅ nhưng là `FastMCP` 1.x |

### 1.3 Tình trạng 8 bước build graph Python ([P] §6.2; [cp] Phần 2)

| Bước | Trạng thái | Còn thiếu |
|---|---|---|
| 1. Parse | ✅ | Node `Identifier`; cạnh `HAS_METHOD`, `HAS_CALLSITE` |
| 2. `G_repo` | ⚠️ | Node Field, GlobalVariable, ConfigEntry, Route, Schema; cạnh `IMPLEMENTS`, `CONFIGURES`; `coverage_count` của `TESTS` |
| 3. Nối symbol | ✅ | Cạnh `MAY_CALL`; PyCG |
| 4. `G_code` | ⚠️ | CFG, dataflow |
| 5. `G_arch` | ❌ | Toàn bộ |
| 6. `G_task` | ⚠️ | Node BugReport, Requirement, AcceptanceCriterion, StackTraceFrame, Constraint…; cạnh `TRACES_TO` |
| 7. Trace | ⚠️ | Nối tới `G_arch` |
| 8. Schema | ✅ | Check "mất port" (phải đợi `G_arch`) |
| §7 GraphDiff | ❌ | Toàn bộ |
| §9 Retrieval/Impact | ⚠️ | `recent_change_frequency`, `components_depending_on`; impact theo `DEPENDS_ON` và cạnh port |
| §10 MCP | ⚠️ | 5 resource, prompt, các tool còn thiếu |

### 1.4 Đánh giá ([test], [rq], [mm])

- **Ba tầng test** ([test] mục 3): test chức năng trên repo mẫu → dry-run 1–5 task SWE-bench → đánh giá đầy đủ (bộ dev, rồi freeze protocol và chạy held-out đúng một lần).
- **Dataset** ([rq]): proposal không chỉ định dataset. Repo đang dùng SWE-bench Verified:
  - Bộ dev 50 task, `min_source_files=2`.
  - Chính sách truy vấn `problem_statement_only_no_hints_or_gold`.
  - Held-out gắn với protocol đã freeze.
- **Dữ liệu phải tự làm:** mẫu cạnh gán nhãn tay, tập `F*`, nhãn kiến trúc, sample commit cho GraphDiff, mutant ([rq] mục 1, 3, 4, 7).

---

## 2. Chia vai

| Thành viên | Phụ trách | Phần proposal |
|---|---|---|
| **TV1** | **Layer 6**: MCP server, resource, prompt, bảo mật, incremental update; chạy Repair, MCP usability, ablation | [P] §5.2 Layer 6, §10, §11, §13.2 (Repair, MCP usability), §13.3 |
| **TV2** | **Layer 1–3**: `G_repo`, `G_code`, `G_arch`, `G_task`, Trace, schema, retrieval, impact; chạy Retrieval, Graph quality, Incremental benchmark | [P] §4, §5.2 Layer 1–3, §6, §8.4, §9.2–9.3 |
| **TV3** | **Layer 4–5**: GraphDiff, invariant, evidence, các check §12; chạy Verification, GraphDiff, Impact | [P] §5.2 Layer 4–5, §7, §8.5, §12 |

---

## 3. Tuần 1: build

### Sáng ngày 1: cả nhóm chốt "hợp đồng"

Lý do và cách làm ở Phụ lục B. Thống nhất 3 thứ:

1. Schema mọi node và cạnh mới của §4 và §7.
2. Chữ ký 11 tool (§10.3).
3. Định dạng file đáp án cho repo mẫu ([test] mục 1).

### TV1: Layer 6

| Mã | Ngày | Việc | Nguồn | Ghi chú của nguồn |
|---|---|---|---|---|
| L6-1 | 1 | Chuyển 4 server từ `FastMCP` (SDK 1.x) sang `MCPServer` (SDK 2.x) | [cp] Layer 6 | |
| L6-2 | 2 | Đủ 11 tool: `build_or_update_graph`, `search_symbols`, `find_task_anchors`, `get_related_context`, `get_callers`, `get_callees`, `explain_dependency_path`, `analyze_patch_impact`, `verify_patch_graph_constraints`, `run_relevant_tests`, `rank_patch_candidates` | [P] dòng 1074–1102 | Phần do TV2/TV3 làm thì tạm trả dữ liệu giả theo hợp đồng |
| L6-3 | 3 | Đủ 8 resource: `vgar://repo/summary`, `vgar://repo/schema`, `vgar://graph/node/{node_id}`, `vgar://graph/subgraph/{node_id}?k=2`, `vgar://component/{component_id}`, `vgar://task/{task_id}`, `vgar://evidence/baseline`, `vgar://audit/log` | [P] dòng 1045–1052; [cp] §10 | Repo hiện có 3 resource |
| L6-4 | 3 | Prompt `repair_with_graph_context` (7 bước) | [P] dòng 1108–1120 | Repo chưa có prompt |
| L6-5 | 3 | Bảo mật: path jail, graph tool mặc định chỉ đọc, thao tác ghi tách riêng và cần xác nhận, allowlist lệnh, timeout và giới hạn tài nguyên, không gửi secret/env var vào prompt, audit log mọi lần gọi tool, từ chối prompt injection trong docs của repo | [P] dòng 1129–1150 | |
| L6-6 | 4 | Incremental update theo thuật toán §11.2 cho `build_or_update_graph`, có cache | [P] dòng 1163–1180 | |
| L6-7 | 4 | Lưu graph: SQLite; Kùzu/Neo4j | [P] §5.2 Layer 6 | [P] dòng 390: Kùzu/Neo4j "for graph queries at scale"; [cp]: "proposal để tùy chọn" |
| L6-8 | 5 | Ghép nối với TV2/TV3; Inspector ở cả `modern` lẫn `legacy`; nối thử vào Claude Code | [test] mục 1 | |

### TV2: Layer 1–3 và các tầng graph

| Mã | Ngày | Việc | Nguồn | Ghi chú của nguồn |
|---|---|---|---|---|
| L1-1 | 1 | tree-sitter-graph | [P] §5.2 Layer 1, §5.3 | [P] §5.3: "biến parse tree thành graph theo DSL", "không nên dùng để thay thế toàn bộ static analysis" |
| L1-2 | 1 | Node `Identifier`; cạnh `HAS_METHOD`, `HAS_CALLSITE` | [P] dòng 526–540; [cp] Bước 1 | |
| L1-3 | 2 | Bổ sung `G_repo`: Field, GlobalVariable, ConfigEntry, Route, Schema; `IMPLEMENTS`, `CONFIGURES` | [P] dòng 212–237; [cp] Bước 2 | |
| L2-1 | 1 | PyCG/JARVIS cho call graph Python | [P] §5.4 ("Python: PyCG/JARVIS + pytest + mypy/ruff") | |
| L2-2 | 1 | Cạnh `MAY_CALL` kèm confidence và provenance (`source_tool`, `evidence`) | [P] dòng 551–567; [cp] Bước 3 | |
| L2-3 | — | ts-morph, SootUp/WALA | [P] §5.2 Layer 2 | [cp]: "Không áp dụng cho Python" |
| L3-1 | 2 | `G_code`: `AST_CHILD`, `CFG_NEXT`, `DATA_DEPENDS_ON`, `CONTROL_DEPENDS_ON` | [P] dòng 193–197, 482; [cp] Bước 4 | [cp]: "Joern pysrc2cpg, CodeQL Python, hoặc bản gọn bằng beniget (dataflow) cộng staticfg (CFG)" |
| L3-2 | 2–3 | Joern | [P] §5.2 Layer 3, dòng 202 | [P] §5.3: "không nên dùng để làm core duy nhất cho mọi language"; [P] dòng 1453: "optional Joern backend" |
| L3-3 | 3 | CodeQL | [P] §5.2 Layer 3, dòng 204 | [P] dòng 1454: "optional CodeQL backend" |
| L3-4 | 3 | Glean | [P] §5.2 Layer 3 | [P] §5.3: "không nên dùng cho MVP nhỏ nếu setup quá nặng" |
| L3-5 | 3 | Kythe | [P] §5.2 Layer 3 | [P] §5.3: "không nên dùng cho dynamic-language MVP" |
| GA-1 | 3 | Lift `G_arch`: các tín hiệu ở dòng 576–585, cohesion/coupling, `infer_public_ports`, `DEPENDS_ON` có trọng số | [P] dòng 576–614; [cp] Bước 5 | [cp] gợi ý với Python: Component = package, Port = hàm công khai hoặc trong `__all__`, Route = decorator Flask/FastAPI |
| GA-2 | 4 | Node và cạnh `G_arch`: Component, Port, Connector, Service, Module, DeploymentUnit, ExternalSystem; `DEPENDS_ON`, `EXPOSES_PORT`, `CONSUMES_PORT`, `COMMUNICATES_WITH`, `CONTAINS_COMPONENT`, `DEPLOYS_TO` | [P] dòng 251–270 | |
| GT-1 | 4 | `G_task`: BugReport, Requirement, UserStory, AcceptanceCriterion, FailingTest, ErrorMessage, StackTraceFrame, Constraint, Actor; `TRACES_TO`, `DEPENDS_ON`, `CONFLICTS_WITH` | [P] dòng 299–323, 621–630; [cp] Bước 6 | |
| TR-1 | 5 | Trace links từ `G_task` tới `G_repo` và `G_arch` | [P] §6.2 bước 7; [cp] Bước 7 | |
| SC-1 | 5 | Schema `S = (TN, TE, beta, delta, Gamma)` cho mọi loại mới; validate trong `O(\|V\|+\|E\|)` | [P] dòng 857–882; [cp] Bước 8 | |
| RT-1 | 5 | Retrieval: đủ 6 đặc trưng xếp hạng (`task_similarity`, `graph_distance`, `edge_confidence`, `failing_test_proximity`, `recent_change_frequency`, `public_api_risk`) và `components_depending_on` | [P] dòng 972–993; [cp] §8–§9 | [cp]: `recent_change_frequency` cần lịch sử commit (Layer 4) |
| IM-1 | 5 | Impact: đi ngược thêm theo `DEPENDS_ON`, `CONSUMES_PORT`/`EXPOSES_PORT`; check "mất port" | [P] dòng 892, 1007–1024; [cp] §8–§9 | |

### TV3: Layer 4–5, evidence và các check

| Mã | Ngày | Việc | Nguồn | Ghi chú của nguồn |
|---|---|---|---|---|
| L4-1 | 1 | Đọc lịch sử commit | [P] §7.3 | [cp]: "đọc lịch sử commit bằng dulwich" |
| L4-2 | 1 | Phát hiện refactoring: RefactoringMiner | [P] §7.3 bước 1, §5.3 | [P] §5.3: "không nên dùng cho mọi ngôn ngữ/mọi refactor" |
| L4-3 | 2 | Phát hiện thay đổi lẫn lộn: UTango-style | [P] §7.3 bước 2 | |
| L4-4 | 2 | Diff AST: GumTree/DAT-GumTree | [P] §7.3 bước 3, §5.3 | [cp]: "diff AST trên tree-sitter-python/libcst" |
| L4-5 | 3 | Đổi thay đổi AST thành graph edit (ví dụ `UPDATE_METHOD_BODY`); id entity trùng id node trong `G_repo` | [P] dòng 688–696, 717; [cp] §7 | |
| L4-6 | 3 | Chấm confidence theo công thức §7.4 | [P] dòng 727–741 | |
| L4-7 | 4 | Bộ dữ liệu gán nhãn tay: sample commit, nhãn bug-fix / refactor / formatting / unrelated | [P] dòng 753–760, 1438; [rq] mục 7 | |
| L5-1 | 3–4 | Invariant kiểu Daikon từ trace lúc chạy test | [P] §5.2 Layer 5, dòng 1244–1261 | |
| L5-2 | 4 | Check invariant ngữ nghĩa trước và sau patch | [P] §12.4 | |
| L5-3 | 4 | Điền `coverage_count` cho cạnh `TESTS`; check coverage của node bị chạm | [P] dòng 1269; [cp] Bước 2 | [cp]: "Package coverage có thể điền số này" |
| EV-1 | 5 | Evidence bundle đủ 9 trường và `score(patch)` có trọng số; dùng cho `rank_patch_candidates` | [P] dòng 900–929 | |
| EV-2 | 5 | Đủ check §12.1–§12.3: schema; cấu trúc kiến trúc (cycle, import ngược tầng, import bị cấm, xóa port, fanout); API | [P] dòng 1213–1240 | [P] dòng 285–293: check phải "baseline-preserving" |
| EV-3 | 5 | Check test §12.5: test fail chuyển sang pass, test hồi quy vẫn pass, suite rộng hơn, coverage | [P] dòng 1265–1270 | |

### Cổng cuối Tuần 1

1. Test tầng 1 của mọi tool xanh ([test] mục 1).
2. Inspector liệt kê được tool ở cả `modern` lẫn `legacy`; nối được vào Claude Code ([test] mục 1).
3. Graph của repo mẫu qua validate schema ([P] §8.4).

---

## 4. Tuần 2: test và ra kết quả

| Ngày | TV1 | TV2 | TV3 |
|---|---|---|---|
| 1 | **Tầng 2:** dry-run 1–5 task SWE-bench (`dry_run_heldout_chain.py`) ([test] mục 3) | Test tầng 1 cho Layer 1–3; test incremental: graph sau cập nhật phải giống hệt graph build lại ([test] mục 1) | Test tầng 1 cho Layer 4–5 |
| 2 | **Repair** trên bộ dev: `run_repair_experiment.py`, `grade_repair_candidates.py --execute` ([rq] mục 2) | **Graph quality:** symbol resolution P/R, call edge P/R, trace link P/R, component boundary quality (`compare_static_vs_scip.py`; mẫu gán nhãn tay) ([rq] mục 4) | Hoàn thiện bộ gán nhãn GraphDiff |
| 3 | **MCP usability:** A0 (không MCP) so với A1+ (có MCP); `aggregate_agent_traces.py --traces … --audit …` ([rq] mục 5) | **Retrieval:** đủ baseline §13.1 (grep, BM25, embedding, file-neighbor, agent default) so với các cấu hình graph; `run_bm25_retrieval.py`, `run_graph_retrieval.py`, `compare_graph_vs_bm25.py` ([rq] mục 1) | **GraphDiff:** precision/recall/F1, retention rate ([rq] mục 7) |
| 4 | **Ablation A0–A5** trên cùng một bộ task ([rq] "Ma trận ablation") | **Incremental benchmark:** `bench_incremental.py` ([rq] mục 6) | **Verification:** `build_mutant_pool.py`, `evaluate_mutant_pool.py`; FAR, FRR, overfitting, schema violation, API break; so 4 baseline verification ở §13.1 ([rq] mục 3) |
| 5 | **Cả nhóm:** kiểm tra 5 điều kiện §8.3 ([rq]); **freeze protocol** ([test] mục 3) | | **Impact (RQ3):** `measure_patch_impact.py` ([mm] 1.4); tác động của GraphDiff xuống retrieval/repair ([P] dòng 760) |
| 6 | **Cả nhóm:** chạy **held-out đúng một lần** ([test] mục 3); tổng hợp báo cáo, mỗi số kèm lệnh tái tạo | | |

---

## 5. Các kết quả test sẽ có

| Mã | Kết quả | Tầng | Metric ([P] §13.2) | Người | Nguồn |
|---|---|---|---|---|---|
| T1 | Test chức năng từng tool, cả 6 layer | 1 | Pass/fail so với đáp án | Cả 3 | [test] mục 1 |
| T2 | Kết nối MCP | 1 | Inspector `modern`/`legacy`; Claude Code gọi được tool | TV1 | [test] mục 1 |
| T3 | Dry-run trên repo thật | 2 | Mỗi bước ra file đúng | TV1 | [test] mục 3 |
| R1 | Retrieval | 3 | `gold_file_recall@k`, `gold_function_recall@k`, `dependency_frontier_recall@B`, MRR, context token cost | TV2 | [P] dòng 1311–1317; [rq] mục 1 |
| RP1 | Repair | 3 | patch success rate, resolved issue rate, số vòng lặp, latency, LLM token cost | TV1 | [P] dòng 1321–1327; [rq] mục 2 |
| V1 | Verification | 3 | FAR, FRR, overfitting detection, schema violation detection, API break detection | TV3 | [P] dòng 1331–1337; [rq] mục 3 |
| G1 | Graph quality | 3 | symbol P/R, call edge P/R, trace link P/R, component boundary quality, incremental update correctness | TV2 | [P] dòng 1341–1347; [rq] mục 4 |
| U1 | Incremental | 3 | cold build time, warm update time, changed files, affected nodes, cache hit rate | TV2 | [P] dòng 1201–1207; [rq] mục 6 |
| GD1 | GraphDiff | 3 | precision/recall/F1, retention, tác động xuống các bước sau | TV3 | [P] dòng 753–760; [rq] mục 7 |
| I1 | Patch impact (RQ3) | 3 | Graph so với chỉ đọc diff | TV3 | [mm] 1.4 |
| M1 | MCP usability | 3 | tool calls/task, average tool latency, success with/without MCP, unnecessary file reads avoided, auditability | TV1 | [P] dòng 1351–1357; [rq] mục 5 |
| AB | Ablation | 3 | A0–A5, so từng cặp liền kề | TV1 | [P] dòng 1361–1368; [mm] 1.5 |
| HO | Held-out | 3 | Chạy đúng một lần sau freeze | Cả 3 | [test] mục 3 |

---

## 6. Đối chiếu với các milestone ([P] §14)

| Milestone | Task | Tiêu chí thành công ([P]) | Kết quả chứng minh | Ghi chú của nguồn |
|---|---|---|---|---|
| M1 Graph MVP | L1-1 → L1-3, SC-1, L6-2 | build graph for medium repo; caller/callee/import queries; context under token budget | T1, U1 | [mm]: đủ deliverables |
| M2 Task trace and retrieval | GT-1, TR-1, RT-1 | improve gold file/function recall over grep/BM25/embedding | R1 | [mm]: chưa khẳng định achievement; baseline embedding chưa được kiểm chứng là có |
| M3 Patch impact and verification | IM-1, EV-1 → EV-3 | detect risky patches; reduce unnecessary full test runs; evidence bundle per patch | V1, I1 | [mm]: đủ deliverables |
| M4 GraphDiff | L4-1 → L4-7 | higher precision graph edits than raw diff; downstream benefit or documented failure cases | GD1 | [mm]: chưa bắt đầu |
| M5 Deep static analysis | L2-1, L3-1 → L3-5 | precision improves for supported languages; fallback still works without heavy backend | G1 | [P] dòng 1453–1455: deliverables đều ghi "optional"; [mm]: repo đã có fallback về resolver static (`builder.py:193-195`) |

---

## 7. Điều kiện để kết quả diễn giải được ([P] §8.3, dòng 835–841; [rq])

| Điều kiện | Lấy từ |
|---|---|
| Graph edge recall đủ cao | G1 |
| Graph edge precision không quá thấp | G1 |
| Issue hoặc test có anchor vào được graph | Tỉ lệ anchor trong R1 |
| Context budget có hạn | Ngân sách B trong R1 |
| Patch gold thật sự phụ thuộc thông tin cross-file | Bộ lọc `min_source_files=2` |

---

## 8. Rủi ro và cách giảm ([P] §15, dòng 1469–1477; [mm] §15)

| Rủi ro | Cách giảm ([P]) | Đo bằng ([mm]) |
|---|---|---|
| Symbol resolution thiếu | Lưu confidence/provenance; fallback sang text/embedding; đo chất lượng cạnh | Call edge P/R |
| Call graph của Python nhiễu | Cạnh `MAY_CALL`, trace lúc chạy, analyzer riêng cho ngôn ngữ | (repo chưa có `MAY_CALL`) → L2-2 |
| Lift kiến trúc sai | Dùng tín hiệu path/config/test/deployment; cho phép sửa tay; check giữ baseline | Component boundary quality |
| Verification từ chối nhầm | Check có thể cấu hình; báo cáo dạng evidence | FRR |
| MCP chậm | Incremental update, cache, lấy subgraph theo ngân sách | Latency trung bình mỗi tool |
| Toolchain khó cài | Lõi nhẹ cộng backend tùy chọn | Tiêu chí fallback của M5 |
| Prompt injection qua docs trong repo | Coi text trong repo là không đáng tin; tool tự giữ luật | Audit log |

---

## 9. Các điểm nguồn ghi là chưa có câu trả lời

Plan không tự chốt các điểm này. Nhóm cần trả lời trước khi chạy phần liên quan.

| # | Điểm | Nguồn | Task liên quan |
|---|---|---|---|
| O1 | Tập `F*` cho `dependency_frontier_recall@B` rộng hơn patch gold: "phải gán nhãn thêm hoặc định nghĩa cách xấp xỉ" | [rq] mục 1 | R1 |
| O2 | Patch sai cho Verification: "proposal không nói lấy từ đâu" (gợi ý: mutant từ patch gold, patch qua test nhưng sai) | [rq] mục 3 | V1 |
| O3 | Overfitting detection rate và kiểm định thống kê là "suy luận, proposal không định nghĩa" | [mm] 1.4 | V1, toàn bộ tầng 3 |
| O4 | A0–A3 của repo là policy verify của M2, "không cùng nghĩa" với A0–A3 của proposal | [mm] 1.5 | AB |
| O5 | Baseline embedding "chưa được kiểm chứng là có" | [mm] Phần 2 | R1 |
| O6 | Số task SWE-bench Verified có patch gold sửa ≥ 2 file "chưa đếm được" | [test] mục 2 | Toàn bộ tầng 3 |
| O7 | Component boundary cần "nhãn kiến trúc làm tay"; proposal không nêu cỡ mẫu cạnh gán nhãn | [rq] mục 4 | G1 |

---

## Phụ lục A. Ngữ cảnh lấy từ từng nguồn

### A.1 [P] Proposal

**Định nghĩa Arch-CPG (§4.1, dòng 162):**
`Arch-CPG = (G_code, G_repo, G_arch, G_task, Lift, Trace, S, Evidence)`.

**Các tầng graph:**

| Tầng | Node | Cạnh | Dòng |
|---|---|---|---|
| `G_code` | METHOD, CALL, IDENTIFIER, IF, RETURN | `AST_CHILD`, `CFG_NEXT`, `DATA_DEPENDS_ON`, `CONTROL_DEPENDS_ON`, `CALLS` | 176–204 |
| `G_repo` | Module, File, Class, Function, Method, Field, GlobalVariable, TestCase, ConfigEntry, Route, Schema | `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `REFERENCES`, `TESTS`, `CONFIGURES` | 206–243 |
| `G_arch` | Component, Port, Connector, Service, Module, DeploymentUnit, ExternalSystem | `DEPENDS_ON`, `EXPOSES_PORT`, `CONSUMES_PORT`, `COMMUNICATES_WITH`, `CONTAINS_COMPONENT`, `DEPLOYS_TO` | 245–293 |
| `G_task` | Issue, BugReport, Requirement, UserStory, AcceptanceCriterion, FailingTest, ErrorMessage, StackTraceFrame, Constraint, Actor | `MENTIONS`, `TRACES_TO`, `TESTS`, `DEPENDS_ON`, `CONFLICTS_WITH`, `REPRODUCES` | 295–340 |

**Stack 6 layer (§5.2, dòng 359–392):**

| Layer | Tool |
|---|---|
| 1 Syntax extraction | tree-sitter, tree-sitter-graph |
| 2 Symbol/reference enrichment | SCIP, LSP, ts-morph, PyCG/JARVIS, SootUp/WALA |
| 3 Deep static analysis / CPG / security | Joern, CodeQL, Glean, Kythe |
| 4 Diff and history cleaning | GumTree/DAT-GumTree, RefactoringMiner, UTango-style |
| 5 Invariant and runtime evidence | Daikon-style, test runner, type checker, linter |
| 6 Graph storage and serving | SQLite, Kùzu/Neo4j, MCP server |

**Vai trò từng tool (§5.3, dòng 396–411):**

| Tool | Vai trò | Không nên dùng để |
|---|---|---|
| tree-sitter | parse đa ngôn ngữ, incremental AST/CST | semantic resolution chính xác tuyệt đối |
| tree-sitter-graph | biến parse tree thành graph theo DSL | thay thế toàn bộ static analysis |
| SCIP | symbol/reference index | biểu diễn full CPG |
| Joern | CPG, CFG, PDG, dataflow, call graph | core duy nhất cho mọi language |
| CodeQL | code database + query + security/dataflow | dependency bắt buộc nếu cần fully OSS/commercial-neutral |
| Glean | typed fact DB | MVP nhỏ nếu setup quá nặng |
| Kythe | cross-reference graph | dynamic-language MVP |
| GumTree/DAT-GumTree | AST diff | semantic truth tuyệt đối |
| RefactoringMiner | phát hiện refactoring | mọi ngôn ngữ/mọi refactor |
| PyCG/JARVIS | Python call graph | đa ngôn ngữ |
| ts-morph | TypeScript compiler API | Python/Java |
| SootUp/WALA | Java/JVM static analysis | dynamic web framework không build được |
| Daikon-style | dynamic likely invariants | proof tuyệt đối |
| MCP SDK | expose tools/resources/prompts | thay thế graph engine |

**MVP (§5.4, dòng 415–432):**
- Bắt buộc: tree-sitter, SCIP hoặc symbol resolver dựa trên LSP, SQLite hoặc Kùzu, MCP server, test runner.
- Phần cho Python: "PyCG/JARVIS + pytest + mypy/ruff".

**Pipeline build `ArchCPGBuilder.build()` (§6.2, dòng 467–510), 8 bước:**

1. Parse bằng tree-sitter.
2. Trích entity cho `G_repo`.
3. Nối symbol bằng SCIP.
4. Dựng `G_code` ("Joern CPG, CodeQL facts, or lightweight AST/call graph", dòng 482).
5. Lift lên `G_arch`.
6. Trích `G_task`.
7. Trace links.
8. Schema và evidence ban đầu, rồi `validate_schema`.

**Các chi tiết được plan dùng tới:**

- **Cạnh chưa resolve (§6.4):** `CallSite --MAY_CALL[confidence=0.42]--> CandidateMethod` (dòng 554). Mỗi cạnh lưu `confidence` và provenance như `"source_tool": "scip-python"` (dòng 559–567).
- **Lift (§6.5):**
  - Tín hiệu gom component: package/module path, import/call density, class ownership, naming, route/config, co-change history, deployment/config, test grouping (dòng 576–585).
  - Cohesion và coupling (dòng 590–595); `DEPENDS_ON` có `weight` (dòng 609–612).
- **Task graph (§6.6):** MVP "không cần NLP phức tạp" (dòng 619). Trích file path, symbol, stack trace, route, error message, failing test, label, acceptance criteria (dòng 621–630).
- **GraphDiff (§7):**
  - Pipeline: detect refactoring → detect tangled changes → AST diff → convert AST edits to graph edits → score confidence (dòng 701–722).
  - Công thức confidence (dòng 727–733).
  - Đầu ra mẫu `UPDATE_METHOD_BODY` (dòng 688–696).
  - Đánh giá bằng manual-label protocol (dòng 753–760).
- **Evidence (§8.5, dòng 900–929):** 9 trường (tests_passed, previously_failing_tests_fixed, static_typecheck_passed, lint_passed, schema_conformance_passed, no_new_forbidden_dependency, public_api_compatible, semantic_invariant_preserved, impact_radius_acceptable) và `score(patch)` có trọng số. "Không claim patch đúng tuyệt đối".
- **Schema (§8.4):** `S = (TN, TE, beta, delta, Gamma)`, kiểm tra trong `O(|V| + |E|)` (dòng 857–882). Sau patch: dựng `G'` rồi hỏi còn đúng schema không, có cạnh sai kiểu không, có cycle mới không, có mất port/public API không (dòng 886–893).
- **Agent loop (§9.1, dòng 937–965):** agent hỏi MCP lấy anchor và context, sửa code, MCP xác minh, agent sửa lại hoặc nộp patch kèm evidence.
- **Context extraction (§9.2, dòng 972–993)** và **impact (§9.3, dòng 1007–1024):** đi ngược theo `CALLS`, `IMPORTS`, `TESTS`, `DEPENDS_ON`, `CONSUMES_PORT`/`EXPOSES_PORT`.
- **MCP (§10):**
  - Resources (dòng 1045–1052): xem L6-3.
  - Tools (dòng 1074–1084): xem L6-2.
  - Prompt `repair_with_graph_context` (dòng 1108–1120).
  - Bảo mật (dòng 1129–1137); mẫu audit log ở dòng 1143–1150.
- **Incremental (§11):** thuật toán ở dòng 1163–1180. Đo cold build time, warm update time, changed files count, affected nodes count, cache hit rate (dòng 1201–1207). "Speedup chỉ là empirical claim, phải đo bằng benchmark nội bộ" (dòng 1199).
- **Verification checks (§12, dòng 1213–1270):** schema, cấu trúc kiến trúc, API, invariant ngữ nghĩa, test.
- **Baselines (§13.1, dòng 1278–1305):** retrieval (grep, BM25, embedding, file-neighbor, agent default); graph (AST-only → full Arch-CPG); verification (tests only → tests + graph + semantic invariants).
- **Metrics (§13.2, dòng 1309–1357):** xem mục 5.
- **Ablation (§13.3, dòng 1361–1368):**

  | Variant | Graph | Task trace | Architecture | Verification | MCP |
  |---|---|---|---|---|---|
  | A0 | none | none | none | tests only | no |
  | A1 | repo graph | none | none | tests only | yes |
  | A2 | repo graph | yes | none | tests only | yes |
  | A3 | repo graph | yes | yes | tests only | yes |
  | A4 | repo graph | yes | yes | graph checks | yes |
  | A5 | full | yes | yes | graph + semantic + tests | yes |

- **Milestones (§14, dòng 1374–1463):** xem mục 6.
- **Rủi ro (§15, dòng 1469–1477):** xem mục 8.
- **Dataset:** proposal **không chỉ định dataset**. Chỉ nhắc "Python/SWE-bench" một lần (dòng 407), "medium repo" (dòng 1389), "sample commit từ nhiều repo/language" và "manual-label evaluation dataset" (dòng 756, 1438), "benchmark nội bộ" (dòng 1199), và nguyên tắc chỉ dùng số benchmark "khi có nguồn và protocol đo lại" (dòng 1490).
- **Định vị (§18, dòng 1522):** "VGAR-MCP không nên được hiểu là một model mới. Nó là một graph infrastructure layer cho coding agents."

### A.2 [test] Test server so với đo metric

- **Hai việc khác nhau:**
  - **Test MCP server có chạy đúng không:** không cần SWE-bench; dùng repo mẫu nhỏ, biết trước đáp án.
  - **Đo metric và ablation §13–§14:** cần nhiều task thật có đáp án (issue, repo, patch gold, test).
- **Bảng test chức năng (mục 1):**

  | Kiểm tra | Cách làm | Đáp án biết trước |
  |---|---|---|
  | `build_or_update_graph` | Build graph cho repo mẫu | Danh sách node và cạnh viết tay, ví dụ `pay → discount_amount → is_eligible` |
  | `get_callers` / `get_callees` / `explain_dependency_path` | Hỏi về một hàm cụ thể | Caller, callee và đường đi đúng |
  | `find_task_anchors` | Đưa vào một issue có traceback | File và hàm phải được tìm ra |
  | `analyze_patch_impact` | Đưa vào một patch biết trước | Các node bị ảnh hưởng |
  | `verify_patch` | Một patch đúng và một patch sai | Patch đúng PASS, patch sai FAIL |
  | Incremental (§11) | Sửa 1 file rồi cập nhật | Graph sau cập nhật phải giống hệt graph build lại toàn bộ |
  | Schema (§8.4) | Validate graph | Không có lỗi |
  | Kết nối MCP | Inspector ở cả `modern` lẫn `legacy`, nối thử vào Claude Code | List và gọi được tool |

  Repo mẫu có sẵn: `tests/fixtures/m2/` (`clean_repo`, `failing_repo`, `reference_patches`, `wrong_patches`) và repo demo `vgar-demo-shop`. Phần này chạy bằng `pytest`, mất vài giây, đưa vào CI được.

- **Nhóm metric nào cần SWE-bench (mục 2):**

  | Nhóm | Cần SWE-bench? |
  |---|---|
  | Retrieval, Repair, MCP usability, Ablation | Có |
  | Verification | Một phần: patch gold lấy từ SWE-bench, patch sai do nhóm tự sinh (mutant) |
  | Graph quality, Incremental, GraphDiff | Không bắt buộc |

- **Lý do SWE-bench Verified hợp lý:** là benchmark duy nhất proposal nhắc tên (dòng 407); toàn bộ là Python; mỗi task có issue, `base_commit`, patch gold, FAIL_TO_PASS và PASS_TO_PASS, harness chính thức; repo đã ghim phiên bản và chia dev/held-out.
- **Quy trình 3 tầng (mục 3):**
  1. Test chức năng trên repo mẫu.
  2. Dry-run 1–5 task SWE-bench (`scripts/dry_run_heldout_chain.py`).
  3. Đánh giá đầy đủ: bộ dev để phát triển; freeze protocol rồi chạy held-out đúng một lần. Với mỗi task: build graph tại `base_commit` → chạy từng nhánh (baseline và A0–A5) → so với gold → gom bảng → kiểm định thống kê.

### A.3 [rq] Dataset và dữ liệu cho từng metric

- **Dataset repo đang dùng:**
  - SWE-bench Verified, ghim theo revision (`dataset.py:125-132`).
  - Bộ dev `configs/m1/w10_dev_manifest.json`: 50 task trên 12 repo Python (astropy, django, matplotlib, xarray, pylint, pytest, scikit-learn, sphinx: mỗi repo 5; requests, sympy: mỗi repo 4; seaborn, flask: mỗi repo 1).
  - Bộ lọc `min_source_files=2`.
  - Chính sách truy vấn `problem_statement_only_no_hints_or_gold`.
  - Held-out phải gắn với protocol đã freeze (`dataset.py:127-129`).
  - Patch gold lưu ở `data/gold/patches/`.
- **Dữ liệu và script cho từng nhóm metric:**

  | Nhóm | Dữ liệu cần | Script |
  |---|---|---|
  | Retrieval | Nhãn gold (file/hàm trong patch gold). `dependency_frontier_recall@B` cần tập `F*` (§8.2), rộng hơn patch gold | `run_bm25_retrieval.py`, `run_graph_retrieval.py`, `compare_graph_vs_bm25.py` |
  | Repair | Task chạy được, có harness chính thức | `run_repair_experiment.py`, `grade_repair_candidates.py --execute` |
  | Verification | Patch đúng (gold) và patch sai (mutant). FAR = sai bị chấp nhận / tổng sai; FRR = đúng bị từ chối / tổng đúng | `build_mutant_pool.py`, `evaluate_mutant_pool.py` |
  | Graph quality | Cạnh gán nhãn tay. Trace link có thể xấp xỉ bằng file trong patch gold. Component boundary cần `G_arch` | `compare_static_vs_scip.py`, `bench_incremental.py` |
  | MCP usability | Cùng bộ task với Repair, so A0 với A1+ | `aggregate_agent_traces.py --traces … --audit …` |
  | Incremental | Một repo cỡ trung bình cùng chuỗi thay đổi | `bench_incremental.py` trên `pydata__xarray-4629` |
  | GraphDiff | Sample commit, gán nhãn bug-fix/refactor/formatting/unrelated | (chưa có) |

- **Ablation:** cùng một bộ task cho cả 6 cấu hình, so từng cặp liền kề. A3/A4 cần `G_arch`, A5 cần invariant ngữ nghĩa.
- **Năm điều kiện của §8.3** (dòng 835–841): edge recall đủ cao; edge precision không quá thấp; issue/test có anchor; context budget có hạn; patch gold cần thông tin cross-file.

### A.4 [mm] Metric, ma trận và milestone

- §12 định nghĩa các check (schema, kiến trúc, API, invariant ngữ nghĩa, test). Kết quả đi vào evidence bundle và được đo bằng nhóm Verification của §13.2.
- **RQ3 (impact)** không có metric riêng trong §13.2; đo bằng `measure_patch_impact.py` ("bảng I1, graph impact vs diff-only trên gold patch").
- **Hai chỗ suy luận, proposal không định nghĩa:**
  - Overfitting detection rate: so patch qua test nhìn thấy được với kết quả official harness.
  - Kiểm định thống kê: repo có code bootstrap và Holm trong `evaluation/retrieval/compare.py` và `report.py`.
- **A0–A3 của repo** là các policy verify do M2 đặt ra, không cùng nghĩa với A0–A3 trong [P]. Ví dụ A3 của repo là check API.
- **Trạng thái milestone:**

  | Milestone | Trạng thái | Bằng chứng |
  |---|---|---|
  | M1 | ✅ Đủ deliverables | `builder.py`, `schema.py`, `sqlite_store.py`, 4 tool trong `graph_server.py`; đã chạy trên xarray |
  | M2 | ⚠️ Đủ deliverables, chưa khẳng định achievement | `grounding.py`, `task_overlay.py`, `retrieval.py`; baseline embedding chưa được kiểm chứng là có |
  | M3 | ✅ Đủ deliverables | `impact.py`, `schema.py`, `api_check.py`, `test_selection.py`, `repair/evidence.py` |
  | M4 | ❌ Chưa bắt đầu | — |
  | M5 | ❌ Chưa có | Riêng tiêu chí fallback: `builder.py:193-195` lùi về resolver static khi SCIP lỗi |

- **Tiêu chí ngầm định:** §11 yêu cầu incremental phải cho kết quả như build lại toàn bộ; §12 yêu cầu check "baseline-preserving" (§4.4, dòng 285–293).

### A.5 [cp] Đối chiếu proposal với repo (Python)

- **Tool đã có:**

  | Tool | Bằng chứng |
  |---|---|
  | tree-sitter (`tree-sitter-python`), kèm `ast`/`symtable` | `builder.py:13-14, 118, 316`; `ast.parse` ở `builder.py:250, 1246`; `symtable` ở `builder.py:1230`; `pyproject.toml` ghim `tree-sitter==0.25.2` |
  | SCIP (`scip-python` 0.6.6, chạy qua Node) | `scip_resolver.py:25, 108, 227`; `scip_profile.py:93-94` |
  | LSP (`pyright-langserver`) | `lsp_resolver.py:1-5, 328`; `scip_profile.py:95-96` |
  | pytest | `mcp/pytest_runner.py`, `repair/test_runner.py`, `repair/docker_executor.py` |
  | mypy, ruff | `repair/static_checks.py:26-31` |
  | SQLite | `graph/sqlite_store.py` |
  | MCP SDK (`FastMCP` 1.x) | 4 server trong `mcp/servers/` |

- **Tool chưa có:** tree-sitter-graph, PyCG/JARVIS, Joern, CodeQL, Glean, Kythe, GumTree, RefactoringMiner, UTango, Daikon, Kùzu/Neo4j.
- **Chi tiết 8 bước:**

  | Bước | Chi tiết |
  |---|---|
  | 1. Parse | Dùng chung `CONTAINS` cho Class→Method và Method→CallSite (`schema.py:32-50`) |
  | 2. `G_repo` | Có Repository, File, Module, Class, Function, Method, Import, CallSite, Test, Issue (`schema.py:8-19`). `TESTS` chỉ dựng từ lời gọi trực tiếp (`builder.py:1170-1178`, luật `python.test.direct_call.v1`), `coverage_count: None` |
  | 3. Nối symbol | Confidence: scip 0.98, lsp 0.95, constructor 0.95/0.60, typed_parameter 0.85, classmethod 0.80 (`builder.py:1090-1105`); provenance bắt buộc (`schema.py:242-248`). Lời gọi chưa resolve chỉ được đếm trong `unresolved_call_count` (`builder.py:240`) |
  | 4. `G_code` | Chỉ có `CallSite` + `CALLS` |
  | 5. `G_arch` | Chỉ có tín hiệu rời: `grounding.py:424` (`_static_route`), luật tầng import (`structural_check.py:298-314`) |
  | 6. `G_task` | `TaskAnchorFinder` (`grounding.py:206, 240`), đọc traceback (`grounding.py:291`), `MENTIONS`/`REPRODUCES` (`task_overlay.py:66, 84`) |
  | 8. Schema | `validate_graph_document` (`schema.py:153-248`), check cycle (`structural_check.py`), check API (`api_check.py`) |

- **GraphDiff (§7):** chưa có. Gợi ý cho Python: diff AST trên `tree-sitter-python`/`libcst`, đọc lịch sử bằng `dulwich`; id entity phải trùng id node trong `G_repo`.
- **§8–§9:** `graph/retrieval.py` đã có. Impact mới đi theo `CALLS`, `IMPORTS`, `INHERITS`, `TESTS` (`impact.py:187`).
- **§10:** có 3 resource (`graph_server.py:107, 138, 171`), có các tool chính, chưa có prompt.
- **Kết luận của [cp]:** đã xong lõi `G_repo` (bước 1–3 và 8). Còn trống `G_code` sâu và `G_arch`, kéo theo `TRACES_TO`, check "mất port", và các cạnh `DEPENDS_ON`/port trong impact và retrieval. GraphDiff chưa bắt đầu.

---

## Phụ lục B. Điểm phụ thuộc giữa các thành viên

Buổi chốt "hợp đồng" sáng ngày 1 là phần sắp xếp để 3 người làm song song. Không có buổi này thì Tuần 1 có các chỗ phải chờ nhau:

| # | Ai chờ ai | Lý do |
|---|---|---|
| 1 | TV1 (L6-2) chờ TV2 (GA-1, GA-2, IM-1) | `explain_dependency_path`, `verify_patch_graph_constraints`, `analyze_patch_impact` cần `G_arch`, cạnh port, check "mất port" |
| 2 | TV1 (L6-2) chờ TV3 (EV-1, L4-5) | `rank_patch_candidates` cần `score(patch)`; định dạng graph edit của GraphDiff |
| 3 | Đáp án test của mỗi người chờ schema mới | Repo mẫu phải có Component/Port, `MAY_CALL`, cạnh `G_code` |
| 4 | TV2 (RT-1) chờ TV3 (L4-1) | [cp]: `recent_change_frequency` cần lịch sử commit |
| 5 | Mọi người chờ cổng cuối Tuần 1 | Điểm đồng bộ có chủ đích |

**Khi đã có hợp đồng:**
- **Ngày 1–4:** mỗi người làm theo hợp đồng; TV1 tạm trả dữ liệu giả cho phần của TV2 và TV3.
- **Ngày 5:** ghép nối.

**Tuần 2** gần như song song hoàn toàn, vì mỗi người chạy bộ đánh giá của layer mình. Ngoại lệ là hai buổi chung: freeze protocol và chạy held-out.
