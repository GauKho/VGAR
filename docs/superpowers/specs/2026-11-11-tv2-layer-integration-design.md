# TV2 · Nối layer 1–3 vào layer 4–6 theo hướng dẫn build-server (bản thiết kế)

Ngày: 11/11/2026. Trạng thái: **ĐÃ DUYỆT ngày 11/11/2026**. Người làm: TV2, đồng thời là người gom code của nhóm.

Nguồn:
- [P] proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`.
- [plan] `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`.
- [guide] <https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server> (nhóm build MCP theo trang này).
- Code: nhánh hiện tại sau khi **đã pull** `mcp/server-h1-l6-8-checkpoint-20261109` (TV1, layer 6) và `mcp/tv3-ev-l4-checkpoint-20261111` (TV3, layer 4–5) ngày 11/11 (§4.1).

Chỉ dùng proposal, plan 2 tuần và các file context; không dùng plan 16 tuần. Code có sẵn từ trước plan 2 tuần chỉ được tận dụng như hiện trạng (plan mục 1.2–1.3), không làm tiếp deliverable của plan 16 tuần.

## 1. Mục đích và mô hình nối

Theo [guide], một MCP server là `MCPServer` cộng các hàm có `@mcp.tool()` (type hint + docstring `Args:`), `@mcp.resource(...)`, `@mcp.prompt()`, chạy `mcp.run(transport="stdio")`, không ghi ra stdout. Ví dụ `get_forecast()` của [guide] gọi NWS API rồi trả kết quả. Với VGAR, "NWS API" được thay bằng **code layer 1–5**:

```
Claude (host) ──hỏi người dùng──► gọi tool qua stdio ──► MCPServer (layer 6, TV1)
                                                          │  thân hàm tool gọi:
                     ┌────────────────────────────────────┼─────────────────────────┐
                     ▼                                    ▼                         ▼
             Layer 1–3 (TV2)                       Layer 5 (TV3)              Layer 4 (TV3)
       graph SQLite, G_task, retrieval,      check §12, test, evidence,   lịch sử commit, chỉ đi vào
       impact, schema                        score(patch)                 retrieval (không có tool riêng)
```

**Nối các layer = viết đúng các hàm mỏng đó** cho 11 tool (§10.3), 8 resource (§10.2) và 1 prompt (§10.4). Mỗi layer chỉ phải đưa ra **hàm Python thường**: nhận tham số đơn giản, trả `dict` JSON được. Layer 6 không cần biết bên trong.

Mục "What's happening under the hood" của [guide] (client gửi câu hỏi → Claude chọn tool → server chạy → Claude đọc kết quả) chính là vòng agent §9.1 của [P]. Prompt `repair_with_graph_context` gợi ý cho Claude thứ tự 7 bước.

Arch-CPG (§4.1) là chỗ các layer gặp nhau. Các hàm trao cho nhau đúng 6 loại dữ liệu:

| # | Dữ liệu | [P] | Sinh | Dùng |
|---|---|---|---|---|
| D1 | Graph document + schema S | §4, §8.4 | TV2 | Cả nhóm; layer 6 lưu SQLite |
| D2 | Node id của `G_repo` | §7.3, §9.3 | TV2 | L4 graph edit, L5 evidence, resource |
| D3 | Diff → node bị chạm | §9.3; Milestone 3 | TV2 (IM-1) | L5 check, evidence |
| D4 | G_task + Trace | §4.5, §6.6 | TV2 (GT-1, TR-1) | `find_task_anchors`, `vgar://task`, L5 |
| D5 | Evidence 9 trường + `score(patch)` | §8.5 | TV3, dùng D1/D3 | `rank_patch_candidates`, prompt bước 7 |
| D6 | Lịch sử / graph edit | §7.2, §9.2 | TV3 (L4) | `recent_change_frequency` của retrieval |

## 2. Phạm vi

**Làm:**
- Thân các tool/resource đang chưa chạy được gọi thẳng hàm layer 1–5 theo kiểu [guide] (§6).
- Thêm phương thức cho `SQLiteGraphService` (code TV2) và nạp graph một lần cho mỗi `graph_version`.
- Ba tool layer 5 theo kiểu [guide], do TV2 làm trong đợt này (quyết định của bạn, Q1):
  - `verify_patch_graph_constraints`: ghép các check của layer 5 với `port_check` của IM-1 (§7.3).
  - `run_relevant_tests`: hàm thường chạy test liên quan trên bản copy có patch (§7.6).
  - `rank_patch_candidates`: hàm thường dựng evidence 9 trường và tính `score(patch)` (§7.7).
- Nối lịch sử L4-1 vào `get_related_context` (mặc định tắt).
- Contract test cho từng chỗ nối; kiểm theo [guide] và [plan] (§9).

**Không làm (giao trả, §11):** L4-2/3/5/6/7, L5-1/3, EV-3 qua Docker (TV3); L6-6 theo §11.2, L6-8 Inspector/Claude Code thật, backend `snapshot` với document SC-1 đầy đủ (TV1); cải thiện retrieval (không có trong plan).

**Không được:**
- Xóa lớp `CoreTools` / grant / `ProviderRegistry` của TV1. Khi host đăng ký provider thì đường đó vẫn được dùng.
- Đổi tên tool hay URI.
- Bật cờ RT-1 làm đổi `FROZEN_RANKING_HASH`.
- Trả kết quả rỗng hay `PASS` khi thiếu dữ liệu; phải báo lỗi rõ.
- Chạy thật (R1, AB, RP1, M1) với backend `demo`.
- Ghi ra stdout trong server ([guide]).

## 3. Hiện trạng (đã kiểm ngày 11/11)

Graph server SDK2 của TV1 đã dựng trên `MCPServer`, nhưng tool đi theo hai kiểu:

| Kiểu | Tool / resource | Tình trạng |
|---|---|---|
| Đã theo [guide], gọi `graph_service` (code TV2) | `search_symbols`, `get_callers`/`get_callees` (`depth=1`), `find_task_anchors`, `get_related_context`, `analyze_patch_impact`; resource `summary`, `node`, `subgraph` | Chạy được với backend `sqlite`/`snapshot` |
| Qua `CoreTools`, cần provider + context do host ký | `get_callers`/`get_callees` khi `depth>1` (`_multihop`), `explain_dependency_path`, resource `schema`/`component`/`task`/`baseline` | Báo `CAPABILITY_UNAVAILABLE` vì cổng `GraphProvider` trống |
| Qua `CoreTools`, provider TV3 | `verify_patch_graph_constraints`, `rank_patch_candidates`, `run_relevant_tests` | Cần context do host ký |
| Qua `CoreTools`, thao tác ghi | `build_or_update_graph` (worker gọi `IncrementalGraphBuilder` của TV2) | Cần grant của host |

Backend của `graph_service`:
- `SQLiteGraphService` (`src/vgar/graph/sqlite_service.py`): cầu nối thật lên layer 1–3. Có từ M1 W3–W4, mở rộng tới W10; trong plan 2 tuần chỉ sửa ở RT-1 (thêm `config`). Proposal không nêu tên nhưng nêu vai trò: §5.4 ("SQLite hoặc Kùzu", "MCP server"), §14 Milestone 1. Mỗi lần gọi đều `load_document(...)`; `get_related_context` còn tạo retriever mới (chép sâu graph).
- `DemoGraphService`: dữ liệu giả 3 symbol (ghi chú L6-2 "tạm trả dữ liệu giả"); `demo` đang là backend mặc định. Đợt này bỏ (§7.8).

Layer 5 vốn là **hàm thường**, provider TV3 chỉ bọc quanh chúng: `validate_graph_document` (§12.1), `check_structure` (§12.2), `check_api(..., changed_only=True)` (§12.3), `check_source_import_cycles` (vòng import trong hàm), `select_related_tests` (cạnh TESTS), `analyze_patch_impact` (§9.3, IM-1). Công thức điểm §8.5 nằm ở hàm riêng `_score_interval` trong `ranking_provider.py`.

## 4. Lấy code

### 4.1 Đã pull hai nhánh (ngày 11/11, theo yêu cầu của bạn)

- Lệnh: `git merge --no-commit --no-ff origin/mcp/tv3-ev-l4-checkpoint-20261111` vào nhánh đang đứng. Nhánh TV3 chứa trọn nhánh TV1, nên có đủ 5 commit: TV1 `45a924cf`, `f37df85f`; TV3 `bb25fff3`; và 2 commit M2 nằm sẵn trong nhánh của họ (`7b5368ac`, `a1287ae5`).
- **Không có conflict.** 157 file vào hàng chờ commit. **Chờ bạn commit.**
- **Code TV2 giữ nguyên.** Chỉ 3 file TV2 thay đổi và đều chỉ được thêm: `pyproject.toml` (+ extra `history = ["dulwich==1.2.18"]`), `sqlite_store.py` (+ hook `_before_ready`, 4 dòng), `graph_server.py` (TV1 viết lại cho SDK2; docstring IM-1 của TV2 còn nguyên). 6 file TV2 chưa commit (follow-up SC-1…) không bị đụng.
- Test trên bản đã gộp (test TV2 + test TV3/TV1 không cần SDK2): **408 pass, 9 fail, 2 skip**; cả 9 lỗi là `ImportError: cannot import name 'Client' from 'mcp'` (máy này có SDK 1.30, TV1 dùng venv SDK2 riêng). Suite đầy đủ đã chạy trước đó trên bản gộp tương tự: các lỗi còn lại đều do thiếu SDK2, thiếu Docker, hoặc có sẵn trên HEAD (`test_w9_bundle::test_checked_in_fixture…`, `test_runner_contract::test_different_arm_contexts…`, `test_official_harness::test_campaign_reads…`).
- **Lưu ý phạm vi:** spec chỉ dùng một thứ đến từ commit M2: tham số `check_api(..., changed_only=True)` (§7.3), vì provider EV-2 của TV3 cũng dùng nó.

### 4.2 Thứ tự phụ thuộc theo proposal

§6.1 là đường thẳng cho layer 1–3 → G_arch → G_task → Trace → layer 6. Layer 4 chạy ngoại tuyến trên lịch sử và trả về retrieval (§9.2); layer 5 chạy sau khi agent sửa code (§12); §9.1 là vòng lặp. Thứ tự nối: **layer 1–3 → (layer 4 ∥ layer 5) → layer 6**, xếp theo ablation §13.3 (A1 → A4).

## 5. Hợp đồng chung

| # | Hợp đồng | Quyết định | Nguồn |
|---|---|---|---|
| H1 | Schema | `src/vgar/contracts/schema.py` (SC-1) là nguồn duy nhất; không dùng DTO Component/Port nháp H1 của TV1 cho dữ liệu graph | [P] 857–882 |
| H2 | Node id | Giữ quy ước builder (`vgar:<repo>:python:<kind>:<path>:<qualname>`); đổi tên/chuyển file = xóa + thêm. *(Quyết định của TV2: đổi lúc này làm mất hiệu lực R1/U1/TR-1)* | [P] 688–696, 717 |
| H3 | MAY_CALL | Callers/callees (mọi `depth`) giữ danh sách chính chỉ gồm CALLS, để `depth=1` và `depth>1` nhất quán và không đổi output `depth=1` hiện có. Cạnh MAY_CALL được trả **riêng** trong trường `may_call` (kèm `confidence`, `edge_type`). `explain_dependency_path` được đi qua MAY_CALL nhưng ghi rõ loại cạnh trên từng bước. *(Quyết định của TV2)* | [P] 551–567 |
| H4 | Chữ ký tool | Giữ chữ ký đang có trên server. Tool đọc không nhận `repo_path` (repo do backend cấu hình); `build_or_update_graph(repo_path)` có `repo_path` nhưng chỉ nhận repo host đã ghim. Chỗ khác §10.3 (vd `graph_version`, `task_id` ở `find_task_anchors`; `max_hops` thay `max_depth`) ghi thành độ lệch có lý do, đưa nhóm chốt | [P] 1074–1102; [plan] mục 3 |
| H5 | Xác nhận thao tác ghi | Theo [guide]: tool chạy "with user approval", host hỏi người dùng. Tool ghi (`build_or_update_graph`, `run_relevant_tests`, `apply_patch`) tách riêng khỏi tool đọc (§10.5 "write operations tách riêng"). Grant của TV1 vẫn còn cho tool ghi | [P] §10.5; [guide] |
| H6 | Retrieval | `RetrievalConfig()` mặc định (hash đóng băng) | [plan] RT-1 |
| H7 | Lịch sử | `read_commit_history(revision=<repository_revision của graph>)`; không dùng HEAD | [P] 972–993 |
| H8 | Chỉ dữ liệu thật | **Bỏ backend `demo`** (quyết định của bạn, Q2). Server chỉ chạy `sqlite` (mặc định) hoặc `snapshot`; thiếu file graph thì báo lỗi ngay khi khởi động. Mọi kết quả ghi `backend_name` | [P] §5.4, Milestone 1; [plan] L6-2 ghi chú "tạm" |
| H9 | Kiểu dữ liệu trả về | Mọi hàm layer trả `dict` JSON được; resource trả chuỗi JSON; lỗi thiếu dữ liệu là `GraphNotReadyError` | [guide] |
| H10 | Trọng số `score(patch)` | Proposal không cho giá trị. Tạm dùng đúng trọng số pilot của TV3 (`tests=0.5, schema_conformance=0.15, architecture=0.1, api=0.15, semantic=0.1, impact_risk=0.2`), lưu ở `configs/mcp_server/ranking_weights.json`, ghi rõ là **tạm, chờ nhóm chốt** | [P] §8.5 |

## 6. Bảng nối

### 6.1 11 tool (§10.3, [plan] L6-2)

| Tool | Thân hàm gọi | Layer | Chủ code | Có sẵn | Việc đợt này |
|---|---|---|---|---|---|
| `build_or_update_graph` | `IncrementalGraphBuilder` → SQLite (§11) | 1–3 → 6 | TV2 | ✅ qua worker TV1 | Giữ (tool ghi) |
| `search_symbols` | `SQLiteGraphService.search_symbols` | 1–3 | TV2 | ✅ | Contract test |
| `find_task_anchors` | `TaskOverlayBuilder` | 1–3 | TV2 | ✅ | Lưu overlay theo `task_id` cho resource task |
| `get_related_context` | `GraphContextRetriever` (§9.2) (+ `read_commit_history`) | 1–3 (+4) | TV2 (+TV3) | ✅ | Dùng graph đã nạp, giữ retriever; lịch sử tùy chọn |
| `get_callers` / `get_callees` | Duyệt CALLS theo `depth`, MAY_CALL trả riêng (H3) | 1–3 | TV2 | ⚠️ chỉ `depth=1` | `traverse()`; server gọi khi chưa có provider |
| `explain_dependency_path` | Đường ngắn nhất trên graph | 1–3 | TV2 | ❌ | `explain_dependency_path()` |
| `analyze_patch_impact` | `vgar.graph.impact.analyze_patch_impact` (§9.3) | 1–3 | TV2 | ✅ | Contract test |
| `verify_patch_graph_constraints` | Dựng G' (builder TV2) → `validate_graph_document` + `check_structure` + `check_api` + `check_source_import_cycles` + `port_check` IM-1 | 5 dùng 1–3 | TV3 + TV2 | ⚠️ sau `CoreTools` | Hàm `verify_patch()` kiểu [guide] (§7.3) |
| `run_relevant_tests` | `select_related_tests` → `pytest_runner.run_selector` trên bản copy, trước và sau khi áp patch (§12.5) | 5 dùng 1–3 | TV2 (đợt này) | ⚠️ sau `CoreTools` | Hàm `run_patch_tests()` kiểu [guide] (§7.6) |
| `rank_patch_candidates` | Evidence 9 trường + `score(patch)` (§8.5) từ kết quả verify và test | 5 | TV2 (đợt này) | ⚠️ sau `CoreTools` | Hàm `rank_candidates()` kiểu [guide] (§7.7) |

### 6.2 8 resource (§10.2, [plan] L6-3)

| Resource | Lấy từ | Có sẵn | Việc đợt này |
|---|---|---|---|
| `vgar://repo/summary`, `graph/node/{id}`, `graph/subgraph/{id}?k=2` | SQLite store (TV2) | ✅ | Contract test |
| `vgar://repo/schema` | `schema_description()` (SC-1, `schema.py:352`) | ❌ | `get_schema()` |
| `vgar://component/{id}` | Node G_arch, đúng các khóa ví dụ §10.2 | ❌ | `get_component()` |
| `vgar://task/{id}` | Overlay G_task | ❌ | `get_task()` |
| `vgar://evidence/baseline` | Fingerprint graph (TV2) + evidence nền §6.2 bước 8 (TV3) | ⚠️ | `get_baseline()`, phần test/invariant `NOT_RUN` |
| `vgar://audit/log` | Audit TV1 | ✅ | — |

### 6.3 Prompt (§10.4)

`repair_with_graph_context(issue_text, failing_tests, context_budget)`: TV1 đã có, đúng 3 input và 7 bước. Không đổi.

## 7. Thiết kế chi tiết

### 7.1 `SQLiteGraphService` (code TV2)

- **Nạp một lần:** `_document(graph_version)` giữ document đã nạp; các phương thức hiện có dùng chung. Retriever của `get_related_context` giữ theo `(graph_version, config)`.
- **Phương thức mới:**

| Phương thức | Hành vi | [P] |
|---|---|---|
| `traverse(symbol_id, direction, depth, max_nodes)` | BFS (callers: cạnh vào, callees: cạnh ra) trên CALLS; trả symbol kèm hop và cạnh làm chứng; `may_call` liệt kê riêng các đích qua MAY_CALL kèm `confidence` (H3); `truncated` khi chạm giới hạn. Kết quả hop 1 phải trùng `get_callers`/`get_callees` hiện có | §10.3 |
| `explain_dependency_path(source_id, target_id, max_hops, max_nodes)` | Đường ngắn nhất có hướng trên CALLS, MAY_CALL, IMPORTS, DEPENDS_ON, CONTAINS; không có đường thì danh sách rỗng kèm `examined_edges` | §10.3 |
| `get_schema()` | `schema_description()` | §10.2 |
| `get_component(component_id)` | `component`, `files`, `public_ports` (EXPOSES_PORT), `dependencies` / `dependents` (DEPENDS_ON ra/vào), `tests` (cạnh TESTS tới node trong component), `risk` (suy từ `coupling`, `cohesion`, fan-in; không suy được thì `null`) | §10.2 ví dụ `vgar://component/Auth` |
| `get_task(task_id)` | Overlay của lần `find_task_anchors` gần nhất cho `task_id`; chưa có thì `GraphNotReadyError` | §10.2 |
| `get_baseline()` | Fingerprint graph/schema, số node/cạnh theo loại; test/invariant `NOT_RUN` | §10.2, §6.2 bước 8 |

- `DemoGraphService` bị xóa (§7.8), nên không cần thêm phương thức cho nó.

### 7.2 Graph server (sửa nhỏ code TV1)

- `get_callers`/`get_callees` khi `depth>1` và `explain_dependency_path`: nếu `core_tools` có provider cho capability thì giữ đường TV1; nếu không thì gọi `graph_service.traverse` / `graph_service.explain_dependency_path` qua `_tool(...)` như các tool kiểu [guide] khác (có audit, đánh dấu `untrusted`).
- `ResourceReader`: `schema`/`component`/`task`/`baseline` không có provider thì đọc từ `graph_service` như `summary`/`node`/`subgraph`.
- `verify_patch_graph_constraints`: không có provider thì gọi `verify_patch()` (§7.3).
- Docstring tool có `Args:`; không ghi stdout; log bằng `logging.getLogger(__name__)`.

### 7.3 `verify_patch()` kiểu [guide] (TV2 ghép, không sửa code TV3)

Vị trí đề xuất cho cả ba hàm layer 5 (§7.3, §7.6, §7.7): `src/vgar/repair/patch_evidence.py`, cạnh các check có sẵn trong `vgar.repair`. Chữ ký: `verify_patch(service, diff, *, graph_version) -> dict`.

0. **Điều kiện:** service phải có `repository_root` (`VGAR_REPOSITORY_ROOT`); thiếu thì `GraphNotReadyError`, giống `analyze_patch_impact` hiện có. `PatchPolicy` dựng như `SQLiteGraphService.analyze_patch_impact` đang làm: danh sách file `File` trong graph, không đường dẫn bảo vệ.
1. Đọc graph baseline từ service (D1); `parse_unified_diff(diff, policy)` (`vgar.repair.patch`); áp diff lên bản copy tạm của repo; dựng graph candidate G' bằng cùng `PythonGraphBuilder` và `source_roots`.
2. Gọi các hàm layer 5 có sẵn: `validate_graph_document(G')`; `check_structure(baseline, G', before_sources=…, after_sources=…)`; `check_api(before, after, changed_only=True)` với `before`/`after` là bytes của các file bị sửa; `check_source_import_cycles(baseline, G', before_sources, after_sources)`.
3. Gọi `analyze_patch_impact(diff, document, repository_root, patch_policy=…)` (`vgar.graph.impact`) để lấy `port_check` (mục "no public port deletion" của §12.2) và vùng ảnh hưởng.
4. Trả `dict`: `status` (`PASS`/`FAIL`/`NOT_RUN`/`ERROR`), `checks` theo tên, `reasons`, `graph_version`, `diff_sha256`. Fanout chưa đo thì ghi `NOT_RUN`. Không ghi vào repo gốc; bản copy tạm luôn được dọn.

### 7.4 Lịch sử L4-1 → retrieval

`get_related_context` nhận tùy chọn bật lịch sử. Khi bật: `read_commit_history(repository_root, revision=<repository_revision>, max_commits=50)`, truyền `change_counts`, `history_label` vào retriever. Thiếu dulwich hoặc thiếu object thì chạy như cũ và ghi `recent_change_frequency` vào `unavailable_features`. Mặc định tắt để R1 giữ nguyên số.

### 7.5 Mẫu (minh họa kiểu [guide], không phải code cuối)

```python
import logging
from mcp.server import MCPServer
from vgar.graph.factory import create_graph_service

logger = logging.getLogger(__name__)
mcp = MCPServer("vgar-graph")
graph = create_graph_service()

@mcp.tool()
def get_callers(symbol_id: str, depth: int = 1) -> dict:
    """Find functions that call a symbol, up to `depth` hops.

    Args:
        symbol_id: Graph node id of the function or method.
        depth: Number of caller hops to follow (1 = direct callers).
    """
    return graph.traverse(symbol_id, "callers", depth)

@mcp.resource("vgar://component/{component_id}")
def component(component_id: str) -> str:
    """Files, public ports, dependencies, dependents and tests of one component."""
    return json.dumps(graph.get_component(component_id))

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 7.6 `run_patch_tests()` kiểu [guide] (TV2, đợt này)

Chữ ký: `run_patch_tests(service, diff, *, graph_version, failing_tests=None, timeout_seconds=300) -> dict`. Tool `run_relevant_tests(diff)` trên execution server gọi hàm này khi chưa có provider.

1. **Chọn test (§12.5 "relevant regression tests"):** lấy node bị chạm từ `analyze_patch_impact` (D3), rồi `select_related_tests(document, symbol_ids, changed_paths=…, failing_tests=…)`. Không chọn được test nào thì `NOT_RUN`.
2. **Chạy trên bản copy tạm** của `repository_root` (bỏ `.git`):
   - Baseline: chạy các selector đã chọn bằng `vgar.mcp.pytest_runner.run_selector(root, selector, timeout_seconds=…, output_cap=…)`. Hàm này yêu cầu caller tự kiểm selector, nên chỉ chạy selector có file test tồn tại trong bản copy.
   - Áp diff **đúng một lần** lên bản copy (`parse_unified_diff` có sẵn), chạy lại cùng selector.
3. **Kết quả:**
   - `PASS`: mọi test lỗi ở baseline (gồm `failing_tests` nếu có) chuyển sang pass, và mọi test pass ở baseline vẫn pass.
   - `FAIL`: còn test lỗi, hoặc có test hồi quy.
   - `NOT_RUN`: không có test, hoặc `failing_tests` không tái hiện lỗi ở baseline.
   - `ERROR`: runner lỗi hoặc hết thời gian.
   - Kèm: `selectors`, `baseline` / `candidate` outcomes, `previously_failing_fixed`, `regressions`, `diff_sha256`, `cleaned: true`.
4. **An toàn tối thiểu:** không bao giờ ghi vào repo gốc; bản copy luôn được dọn (cả khi lỗi); selector chỉ lấy từ `select_related_tests`, không nhận tùy ý từ model. Xin phép chạy là việc của host (H5).
5. Ngoài phạm vi: broader suite và coverage (§12.5 dòng 3–4), Docker. Ghi `NOT_RUN`.

### 7.7 `rank_candidates()` kiểu [guide] (TV2, đợt này)

Chữ ký: `rank_candidates(candidates, *, verify_results, test_results, weights) -> dict`. Tool `rank_patch_candidates(candidates)` (mỗi candidate gồm `candidate_id`, `diff`, như DTO `Candidate` của TV1) gọi hàm này khi chưa có provider. Kết quả `verify_patch` và `run_patch_tests` được giữ trong server theo `diff_sha256`; diff nào chưa được verify hay test thì hàm tự gọi.

1. **Evidence 9 trường (§8.5)** cho mỗi candidate:

| Trường | Lấy từ |
|---|---|
| `tests_passed`, `previously_failing_tests_fixed` | `run_patch_tests` |
| `schema_conformance_passed`, `no_new_forbidden_dependency`, `public_api_compatible` | `verify_patch` (schema, structural/forbidden imports, api) |
| `impact_radius_acceptable` | `port_check` trong `verify_patch`: mất port công khai → `FAIL` |
| `static_typecheck_passed`, `lint_passed`, `semantic_invariant_preserved` | `NOT_RUN` (ngoài đợt này) |

2. **`score(patch)`** đúng công thức §8.5 và cách làm của TV3: phần test chia đều cho hai trường test; trường `PASS` cộng trọng số; trường `NOT_RUN`/`ERROR` để vào cận trên. `impact_risk` = 1 nếu mất port công khai, 0 nếu không, và **trừ toàn bộ** `w_risk` khi chưa đo được (giống TV3). Trả `score` là cận dưới, kèm `score_interval`. *(Quyết định của TV2: rủi ro dựa trên "number of public ports changed" của §9.3.)* Test kiểm: khi impact chưa đo, điểm trùng với `_score_interval` của TV3.
3. **Thứ tự:** candidate đủ điều kiện (verify `PASS` và test `PASS`) đứng trước, rồi điểm giảm dần, rồi `candidate_id`. Điểm cao không bao giờ vượt qua một check bắt buộc bị `FAIL`.
4. Trọng số đọc từ `configs/mcp_server/ranking_weights.json` (H10).

Provider của TV3 (`DiffTestsProvider`, `EvidenceRankingProvider`, `StaticVerificationProvider`) **giữ nguyên**; khi host đăng ký chúng thì server vẫn đi đường TV3.

### 7.8 Chỉ chạy với dữ liệu thật: bỏ backend `demo`

**Lý do:** `demo` là dữ liệu giả 3 symbol (`auth.login`, `web.login_handler`, `auth.validate_token`) viết cứng trong `src/vgar/graph/demo_service.py`, dùng tạm ở tuần 1 khi layer 1–3 chưa xong. Nó đang là backend **mặc định**, nên nếu quên cấu hình, server vẫn chạy và Claude nhận graph giả mà không có lỗi nào.

**Thay đổi trong phần build server (2 file + 1 file xóa):**

| File | Thay đổi |
|---|---|
| `src/vgar/graph/demo_service.py` | Xóa |
| `src/vgar/graph/factory.py` | Bỏ nhánh `demo`; mặc định `VGAR_GRAPH_BACKEND=sqlite`. Thiếu `VGAR_GRAPH_DATABASE` (hoặc file không tồn tại) thì `RuntimeError` rõ ràng khi khởi động. Giá trị `demo` bị từ chối với thông báo hướng dẫn dùng `vgar index` |
| `src/vgar/config/settings.py` | Mặc định `backend = "sqlite"`; bỏ `demo` khỏi chú thích |

Các file server (`graph_server.py`, `execution_server.py`, `repository_server.py`, `repair_server.py`) **không sửa**.

**Cách có graph thật:** dựng một lần cho repo cần làm việc bằng lệnh đã có:
```bash
vgar index <đường dẫn repo> --db <file>.db
```
Sau đó khai báo server trong config của host theo [guide], thêm khóa `env`:
```json
"vgar-graph": {
  "command": "uv",
  "args": ["--directory", "D:\\kltn\\vgar_mcp_mvp_demo", "run", "python", "-m", "vgar.mcp.servers.graph_server"],
  "env": {
    "VGAR_GRAPH_BACKEND": "sqlite",
    "VGAR_GRAPH_DATABASE": "<file>.db",
    "VGAR_REPOSITORY_ROOT": "<đường dẫn repo>"
  }
}
```
Agent cũng có thể gọi tool `build_or_update_graph` để cập nhật graph khi code đổi (§11).

**Sửa theo để không vỡ (không thuộc phần build server):**
- **Test** đang dùng `demo` (khoảng 13 file, gồm `tests/mcp_server/test_*_wire.py`, `test_resources.py`, `test_sdk_runtime.py`, `test_tv3_ranking.py`, `test_tv3_verification.py`, `test_mcp_tool_contract.py`, `test_sqlite_graph_service.py`, `test_w10_impact_mcp.py`, `test_settings.py`, `tests/fixtures/mcp_server/resource_fixture_server.py`): chuyển sang một **fixture graph SQLite thật nhỏ**, dựng lúc chạy test từ `tests/fixtures/vgar-arch-cases` bằng cùng builder. Test vì vậy kiểm trên graph thật, không phải 3 symbol giả.
- **Script kiểm tra của TV1** (`scripts/mcp_server/smoke_mcp.py`, `check_runtime.py`, `_preflight_worker.py`): đổi `VGAR_GRAPH_BACKEND=demo` sang `sqlite` + fixture graph.
- **Docs TV1** (6 file trong `docs/mcp_server/`): sửa lệnh trong runbook; báo TV1.

## 8. Thứ tự làm và điểm kiểm (theo ablation §13.3)

| Bước | Mở khóa | Việc | Xong khi |
|---|---|---|---|
| 0 | — | Bạn commit phần gộp TV1/TV3 đang chờ (§4.1) và commit follow-up SC-1 | Suite chỉ còn các lỗi đã biết ở §4.1 |
| 0b | Dữ liệu thật | Bỏ backend `demo` (§7.8): fixture graph SQLite cho test, sửa `factory.py`/`settings.py`, chuyển test và script | Không còn chỗ nào import `DemoGraphService`; server không có `VGAR_GRAPH_DATABASE` thì báo lỗi khi khởi động; `VGAR_GRAPH_BACKEND=demo` bị từ chối; suite không thêm lỗi ngoài các lỗi đã biết |
| 1 | A1 | Nạp graph một lần + giữ retriever (§7.1) | Hai lần gọi cùng version chỉ một lần `load_document`; output `get_related_context` không đổi |
| 2 | A1 | `traverse`, `explain_dependency_path`, `get_schema`; rẽ nhánh server (§7.2) | Fixture `vgar-arch-cases` có đáp án viết tay (gồm cạnh MAY_CALL trong `may_call`); hop 1 của `traverse` trùng `get_callers`/`get_callees` hiện có; gọi in-process `get_callers(depth=2)`, path, resource schema trả dữ liệu với backend `sqlite` |
| 3 | A2, A3 | `get_task`, `get_component` + resource | Component đủ 7 khóa §10.2; task có sau `find_task_anchors`, chưa có thì lỗi rõ |
| 4 | A4 | `verify_patch()` + rẽ nhánh tool (§7.3) | Trên `tests/fixtures/m2/` (`reference_patches` / `wrong_patches`): patch đúng `PASS`, patch sai `FAIL`; patch xóa hàm công khai bị `FAIL` vì `port_check` |
| 4b | A4 | `run_patch_tests()` + rẽ nhánh `run_relevant_tests` (§7.6) | Trên fixture `tests/fixtures/m2/`: patch đúng làm test lỗi chuyển pass → `PASS`; patch sai còn lỗi hoặc làm hỏng test khác → `FAIL`; repo gốc không đổi byte nào; bản copy đã dọn |
| 4c | A4 | `rank_candidates()` + rẽ nhánh `rank_patch_candidates` (§7.7) | Patch đúng đứng trên patch sai; candidate có check bắt buộc `FAIL` không bao giờ đứng đầu; khi impact chưa đo, điểm trùng `_score_interval` của TV3 |
| 5 | §9.2 | Lịch sử L4-1 (§7.4) | Lịch sử dừng ở `repository_revision`; thiếu dulwich có `unavailable_features`; tắt thì R1 không đổi |
| 6 | Cuối tuần 1 | `get_baseline` + kiểm §9 | Đủ các mục §9 |

Test chạy in-process bằng `.venv` (máy này không có SDK2): `tests/test_tv2_integration_*.py`, `tests/mcp_server/test_tv2_*.py`.

## 9. Kiểm theo [guide] và tiêu chí cuối tuần 1 của [plan]

1. `uv run` server không lỗi; không gì ghi ra stdout (test bắt stdout rỗng ngoài JSON-RPC).
2. Inspector CLI liệt kê đủ tool và resource ở **`--protocol-era modern` và `legacy`**. [guide] đưa lệnh ở tab TypeScript; với Python thay phần khởi động bằng `uv run …`. Cần môi trường SDK2: nếu máy này chưa có thì ghi vào danh sách bàn giao cho TV1.
3. Dựng graph thật bằng `vgar index`, khai báo server trong config Claude Desktop / Claude Code (đường dẫn tuyệt đối và khóa `env` như §7.8); trên repo mẫu, một issue có traceback cho chuỗi gọi anchors → context → impact → verify, và kết quả ghi `backend_name = "sqlite"`.
4. Graph repo mẫu qua `validate_graph_document`.
5. Test tầng 1 xanh.

## 10. Bảng truy vết (đã điền sau khi chạy; báo cáo: `docs/status/tv2_layer_integration_run_2026-11-11.md`)

| Chỗ nối | [P] | [plan] | Test |
|---|---|---|---|
| callers/callees `depth>1` | §10.3 | L6-2 + L1/L2 | `tests/test_tv2_integration_service.py::test_traverse_*`, `test_callees_list_may_call_separately`; `tests/mcp_server/test_tv2_guide_routing.py::test_get_*_depth_two_*` |
| explain_dependency_path | §10.3 | L6-2 + GA | `test_path_*`; `test_explain_dependency_path_runs_without_a_provider` |
| resource schema/component/task/baseline | §10.2 | L6-3 + SC-1/GA/GT-1 | `test_schema_resource_is_the_sc1_description`, `test_component_*`, `test_task_*`, `test_baseline_*`; `test_resources_are_served_without_a_context`; `tests/mcp_server/test_resources.py::test_graph_resources_are_served_without_context_when_no_provider` |
| verify_patch | §8.4, §12.1–12.3, §9.3 | EV-2 + IM-1 + SC-1 | `tests/test_tv2_patch_evidence.py` (Task 5 tests) |
| run_patch_tests | §12.5 | EV-3 + L1 (TESTS) | `tests/test_tv2_patch_evidence.py` (Task 6 tests) |
| rank_candidates | §8.5, §9.3 | EV-1 + IM-1 | `tests/test_tv2_patch_evidence.py` (Task 7 tests) |
| Lịch sử → retrieval | §9.2 | RT-1 + L4-1 | `test_history_*` |
| Xác nhận ghi | §10.5 | L6-5 | H5 (độ lệch có lý do) |
| Chữ ký tool | §10.3 | L6-2 | H4 (độ lệch có lý do) |

## 11. Danh sách bàn giao

- **TV3:** L4-5 (dùng H2), L4-2/3/6/7, L5-1/3, EV-3 qua Docker, §12.3 field schema/OpenAPI, §12.4 (Daikon hoặc ghi "semantic contract" là phương án thay thế), V1 trên bộ dev, fanout của EV-2.
- **TV1:** L6-6 theo §11.2 (U1: liên kết vẫn O(N)); Inspector modern/legacy và Claude Code thật (L6-8); backend `snapshot` với document SC-1 đầy đủ; `pyproject.toml` còn `mcp<2`; phát hiện prompt injection (§10.5).
- **Nhóm:** chốt H2, H3, H4, H5.

## 12. Câu hỏi còn mở

- ~~Q1~~ **Đã chốt:** TV2 làm `run_relevant_tests` và `rank_patch_candidates` theo kiểu [guide] trong đợt này (§7.6, §7.7).
- ~~Q2~~ **Đã chốt:** bỏ backend `demo`, server chỉ chạy với dữ liệu thật (§7.8, H8).

Không còn câu hỏi mở. Spec chờ duyệt.
