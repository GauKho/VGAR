# Audit workflow và các tool server: logic, latency, đối chiếu proposal và plan W1–W16 (06/11/2026)

Nhánh `m3/w12-all`, HEAD `3f77fcf6`. Đi kèm `docs/status/m3_system_audit_2026-11-06.md` (metric, thuật toán, repo thật).

Nguồn đối chiếu:
- Proposal: `D:\kltn\proposal_vgar_mcp_final_corrected.md`, §9 (workflow), §10 (MCP), §11 (incremental), RQ5.
- Kế hoạch 16 tuần: `D:\kltn\project_plan_16_weeks.md`.
- Deliverables v2 (bản kế hoạch chính thức): `D:\kltn\VGAR_W9_W16_Deliverables (1).md`.

Số đo lấy từ 3 run agent thật (`~/vgar-x2b/results/m3/w12/agent/{20261103T151652Z,20261104T050429Z,20261104T083227Z}/m1/m1.md`)
và từ lần đo graph tool ngày 06/11 (§3.2).

## 1. Kết luận

- **Workflow pipeline A0–A3 khớp plan.** Kế hoạch W7–8 ghi "vòng một lượt retrieve → generate → patch → verify", và
  `agents/workflow.py` làm đúng như vậy. Verdict do engine M2 quyết định.
- **Đường agent lệch so với proposal §9.1.** Proposal mô tả agent tự hỏi graph (anchors, context, callers/callees),
  tự sửa code rồi tự sửa lại. Còn `solve --agent` là *constrained agent*: 6 tool không có tham số, context do host dựng
  sẵn, diff do generator V11 sinh. Nhóm đã chọn hướng này ngày 31/10, nhưng luận văn phải ghi rõ đây là thay đổi so với
  proposal.
- **MCP surface mới làm được khoảng một nửa proposal §10.** Có 8 trong 11 tool (2 tool được gộp vào tool khác), 3 trong
  8 resource, và **0 prompt**.
- **Latency:** sinh patch chiếm phần lớn thời gian. Ở tầng MCP còn có một chi phí cố định khoảng 2,3 s cho mỗi lần gọi
  tool, vì adapter mở tiến trình server mới cho từng lần gọi. Phía server chỉ mất 3–8 ms.
- **`analyze_patch_impact` chưa chạy thành công lần nào trên run thật** (0/4 call, cả 4 đều invalid), dù đây là
  deliverable W9–10 ("impact report vào feedback").

## 2. Đối chiếu workflow

| Hạng mục | Proposal / plan | Code hiện tại | Đánh giá |
|---|---|---|---|
| Pipeline A0–A3 | Plan W7–8: vòng một lượt retrieve → generate → patch → verify | `agents/workflow.py`: initialize → retrieve → generate → apply → (test) → verify → finalize; mỗi bước là một tool `repair_*` qua MCP; `max_iterations=1` | **Khớp** |
| Vòng agent | Proposal §9.1: agent gọi `find_task_anchors` → `get_context_subgraph`/callers/callees → tự sửa → verify, impact, test → sửa lại | `agents/tool_agent.py`: 6 tool không tham số (`get_task_context`, `generate_patch`, `apply_patch`, `run_relevant_tests`, `verify_patch`, `analyze_patch_impact`); tối đa 3 attempt, tối đa 15 tool call. Agent **không** gọi tool graph để lấy context | **Lệch có chủ đích** (chốt 31/10). Cần amendment trong Methodology |
| Agent có thực sự quyết định? | RQ5: agent dùng graph qua MCP | Agent làm theo gợi ý `NEXT` của host 40/42 lượt; mỗi lượt chỉ ra khoảng 15 token | Gần như là workflow do host điều khiển. Nên báo cáo trung thực, đừng trình bày như agent tự chủ |
| Lấy context | Proposal §9.2: 6 feature, budget 12.000 token | `graph/retrieval.py:30`: đủ 6 feature; budget 8.000 token (deliverables v2 M1-W9-3). Không có `components_depending_on` (ghi là `architecture_dependencies` unavailable) | Khớp deliverables v2. Lớp G_arch không tham gia retrieval |
| Impact | Proposal §9.3: reverse CALLS, IMPORTS, TESTS, DEPENDS_ON, ports; có risk feature | `graph/impact.py`: reverse CALLS/IMPORTS/subclass/TESTS. Không có DEPENDS_ON, ports, cycle | Một phần |
| Incremental | Proposal §11; plan W11–12 | `graph/incremental.py` có sẵn nhưng **không đường agent hay MCP nào dùng**. `analyze_patch_impact` dựng lại toàn bộ graph ở lần gọi đầu (`agents/runtime.py:36`). Không có tool `build_or_update_graph` | Chưa nối vào hệ thống |
| Chat / run trên repo thật | Proposal §10.4: prompt `repair_with_graph_context` | `vgar run` (chỉ đọc), `vgar chat --task` | Hỏng 4 tool graph (R1, R2 ở audit đi kèm) |

## 3. Các block tool server

### 3.1. Có gì so với proposal §10

| Nhóm | Proposal | Có | Thiếu / khác |
|---|---|---|---|
| Tool (11) | `build_or_update_graph`, `search_symbols`, `find_task_anchors`, `get_related_context`, `get_callers`, `get_callees`, `explain_dependency_path`, `analyze_patch_impact`, `verify_patch_graph_constraints`, `run_relevant_tests`, `rank_patch_candidates` | 6 tool graph cùng tên, cộng `run_relevant_tests` (repair). `verify_patch_graph_constraints` được gộp vào `repair_verify_patch` (check api/structural của A3) | Không có `build_or_update_graph`, `explain_dependency_path`, `rank_patch_candidates`. Có thêm `get_related_tests`, `read_file`, `run_pytest`, `get_task_context`, `apply_patch` |
| Resource (8) | repo/summary, repo/schema, graph/node, graph/subgraph, component, task, evidence/baseline, audit/log | 3: `vgar://repo/summary`, `graph/node/{id}`, `graph/subgraph/{id}` | Thiếu 5. Agent cũng không đọc được resource, vì adapter chỉ nạp tool (`client.get_tools()`) |
| Prompt | `repair_with_graph_context` | **0** (`grep @mcp.prompt` không ra kết quả) | Thiếu toàn bộ |
| Security §10.5 | path jail, read-only mặc định, write tách riêng có xác nhận, command allowlist, timeout mỗi tool, audit | Có path jail, allowlist selector (đã chạy thử `SELECTOR_REJECTED`), redaction, audit (completeness 100% ở cả 3 run); pytest có timeout ở server | Tool graph **không có timeout**. Trong `chat`, tool ghi được mở ngay từ lượt đầu (G4) |

### 3.2. Latency (đo 06/11, Windows, graph `src/` VGAR 15.432 node, mỗi tool 3–5 lần)

| Tool | Phía client p50 (ms) | Phía server (ms) |
|---|---|---|
| khởi động client và liệt kê tool | 2.298 | — |
| `graph_search_symbols` | 2.397 | 8 |
| `graph_get_callers` / `get_callees` (depth 2) | 2.345 / 2.375 | 3 / 3 |
| `graph_find_task_anchors` | 4.015 | 1.575 |
| `graph_get_related_tests` | 3.002 | 787 |
| `graph_get_related_context` (budget 8.000) | 5.831 | 3.300 |

**W1 (H): mỗi lần gọi tool tốn thêm khoảng 2,3 s.**
- `langchain-mcp-adapters` mở một session stdio mới, tức một tiến trình Python mới, cho **mỗi** lần gọi tool khi không
  truyền session vào (`.venv/Lib/site-packages/langchain_mcp_adapters/tools.py:460-466`).
- `agents/core.py:44` và `agents/nodes/mcp_repair.py:25` đều chỉ dùng `client.get_tools()`.
- Mỗi lần gọi, server graph còn nạp lại graph từ SQLite, nên `find_task_anchors` và `get_related_context` mất 1,5–3,3 s
  ngay ở phía server. Trên repo SWE-bench lớn hơn, thời gian này sẽ tăng theo.
- Đây chính là "MCP overhead" mà plan W11–12 (Definition of Done) yêu cầu đo. Đề xuất ghi số này vào bảng M1 và tách
  rõ thời gian client với thời gian server.
- **Hướng sửa:** giữ session trong suốt phiên làm việc
  (`async with client.session(name) as s: tools = await load_mcp_tools(s)`), và cache document trong server graph.
- **Rủi ro:** đổi vòng đời tiến trình server sẽ đổi số latency trong bảng M1. Vì vậy nên làm sau đợt chốt W12, hoặc ghi
  đây là lựa chọn có chủ đích ("stateless, cô lập mỗi lần gọi").

### 3.3. Latency của agent trên SWE-bench (3 run X2b, A2, Qwen3-4B, 45% model offload sang CPU)

| Bước | Số call | p50 | p95 | Nhận xét |
|---|---|---|---|---|
| `generate_patch` | 14 / 9 / 8 | 274 / 315 / 153 s | 1.035 / 551 / 878 s | Chiếm 52–65% thời gian. p95 vượt `generation_timeout` 900 s vì `AgentModelGenerator` không áp timeout (đã sửa 04/11, chưa commit) |
| `get_task_context` | 14 / 11 / 10 | 78 / 101 / 97 s | 297 / 371 / 333 s | **W2 (M):** khoảng 2–3 call mỗi task. Mỗi attempt mở run mới, nên có thể baseline (Docker pytest, mypy) bị chạy lại mỗi lần, dù cùng một task và revision. Cần xác nhận trong `repair_server.get_task_context` rồi cache theo (task, revision, policy) |
| Lượt model (agent) | 47 / 35 / 27 | 10,3 / 11,6 / 9,7 s | 84 / 139 / 69 s | Mỗi lượt chỉ ra khoảng 15 token để chọn tool. Tổng khoảng 8 phút trong 157 phút (khoảng 5%) |
| `apply_patch` / `verify_patch` | 13 / 13 | 3,1 / 2,7 s | 41 / 110 s | p50 phần lớn là chi phí W1; p95 do Docker chậm (X2b §3.1) |
| `analyze_patch_impact` | 2 / 1 / 1 | 31 / 67 / 0 s | — | **W3 (H): invalid 100% (0/4 thành công).** Run 03/11 lỗi ở host (`Rename/duplicate file`, đã sửa 04/11, chưa commit); run 04/11 vẫn invalid. Lần gọi đầu dựng lại toàn bộ graph, không dùng incremental |

**Đối chiếu yêu cầu đo trong plan:**
- Deliverables M3-W12-1 yêu cầu p50/p95 cho từng tool và từng lượt model: **đã có**.
- Plan W11–12 yêu cầu read redundancy: **n/a**, vì agent không có tool đọc code.
- Plan W11–12 yêu cầu so sánh cold và warm graph update: **chưa có** (bảng U1 trong `docs/paper/results_draft_v1.md`
  còn trống).

## 4. Logic

| # | Mức | Vấn đề | Bằng chứng | Hướng sửa |
|---|---|---|---|---|
| L1 | H | `analyze_patch_impact` chưa thành công lần nào trên run thật, nên nhánh "impact vào feedback" (W9–10) chưa có bằng chứng | §3.3 | **Smoke 06/11: PASS ở HEAD** trên diff django-10914 (2 node đổi, 21 phụ thuộc), nhưng mỗi call khoảng 43 s. Còn thiếu bước agent gọi tool và đưa impact vào feedback, cần model thật. Chi tiết: `m3_status_synthesis_2026-11-06.md` §2 |
| L2 | M | `generate_patch` không bị chặn bởi `generation_timeout` khi dùng `--generator agent` | `docs/status/m3.md` (seaborn 856–1076 s) | Đã sửa 04/11, chưa commit |
| L3 | M | Mỗi attempt có thể chạy lại baseline; cần xác nhận (W2) | §3.3 | Cache baseline theo (task, revision, policy hash) |
| L4 | M | Agent gần như chỉ làm theo NEXT của host (40/42), nên khó nói agent có giá trị quyết định | `m1.md` run 03/11 | Trong luận văn gọi là "constrained agent"; nêu đúng con số |
| L5 | L | Tool graph không có timeout; `get_related_context` trên repo lớn có thể treo agent | `mcp/servers/graph_server.py` | Thêm timeout ở server, hoặc dựa vào `ToolCallLimitMiddleware` cộng timeout phía client |
| L6 | L | Trong `vgar run` / `chat`, agent không biết `graph_version`, và host thiếu biến tokenizer / repo root | Audit đi kèm, R1–R2 | Như audit đi kèm |

## 5. Test

Chạy `pytest -m "not hf and not docker"` ngày 06/11, chia hai đợt (đợt đầu dừng ở lỗi đầu tiên do `-x`):
- Đợt 1: 1751 passed, 17 skipped, 1 xfailed.
- Đợt 2 (các file từ `test_official_harness.py` trở đi, cộng `tests/unit`): 546 passed, 3 skipped.
- Cả hai đợt đều chỉ có 1 test fail: `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`.
  Có vẻ trùng lỗi harness đã có từ trước (ghi nhận 02/11); chưa đối chiếu lại.

## 6. Thứ tự đề xuất

1. Commit các sửa ngày 04/11 (L1, L2), rồi smoke `analyze_patch_impact` trên 1 task.
2. Sửa R1, R2 (audit đi kèm) để đường demo có đủ tool graph.
3. Ghi vào Methodology: (a) agent là constrained agent, lệch §9.1; (b) MCP surface thực tế so với §10; (c) chi phí cố
   định khoảng 2,3 s mỗi lần gọi MCP, tách thời gian client và server.
4. Sau đợt chốt W12: giữ session MCP (W1), cache baseline (W2), nối incremental vào đường impact.
