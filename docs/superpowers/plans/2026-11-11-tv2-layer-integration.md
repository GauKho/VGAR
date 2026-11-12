# TV2 · Nối layer 1–3 vào layer 4–6 theo hướng dẫn build-server · Plan triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mọi tool, resource của MCP server (11 tool §10.3, 8 resource §10.2) chạy bằng graph thật theo kiểu hướng dẫn build-server, gọi thẳng code layer 1–5, không cần context do host ký và không còn backend giả `demo`.

**Architecture:** Server giữ nguyên khung `MCPServer` của TV1. Ở các chỗ đang rẽ vào `CoreTools`, thêm nhánh: khi host chưa đăng ký provider thì gọi hàm thường. Hàm layer 1–3 nằm trong `SQLiteGraphService` (thêm phương thức, nạp graph một lần cho mỗi version); hàm layer 5 nằm trong một module mới `src/vgar/repair/patch_evidence.py`, ghép các check có sẵn với `port_check` của IM-1.

**Tech Stack:** Python 3.11, MCP Python SDK (`MCPServer`), SQLite, pytest. Không Docker. Máy này chỉ có MCP SDK 1.30 trong `.venv`, nên test chạy **in-process**.

**Spec:** `docs/superpowers/specs/2026-11-11-tv2-layer-integration-design.md` (đã duyệt 11/11/2026).

## Global Constraints

- Chỉ làm trong phạm vi plan 2 tuần và proposal; code có sẵn chỉ được tận dụng như hiện trạng.
- **Không commit.** Người dùng tự commit; mỗi task kết thúc bằng danh sách file và lệnh commit gợi ý (kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Không add `artifacts/sample_graph.db`, file `olve --agent…`, `tests/fixtures/vgar-demo-shop/`.
- Server: không ghi ra stdout (không `print`), mỗi module mới một `logger = logging.getLogger(__name__)`, docstring tool có mục `Args:`.
- Không xóa `CoreTools` / grant / `ProviderRegistry` / provider của TV1, TV3; khi host đăng ký provider thì đường đó vẫn được dùng.
- Không đổi tên tool, URI.
- `RetrievalConfig()` mặc định; không đổi `FROZEN_RANKING_HASH`.
- Thiếu dữ liệu thì báo lỗi rõ (`GraphNotReadyError`, `NodeNotFoundError`, `status: NOT_RUN/ERROR`), không trả rỗng hay `PASS`.
- Backend chỉ `sqlite` (mặc định) hoặc `snapshot`; `demo` bị từ chối.
- Hàm layer trả `dict` JSON được; resource trả chuỗi JSON.
- Trọng số `score(patch)` tạm (H10): `tests=0.5, schema_conformance=0.15, architecture=0.1, api=0.15, semantic=0.1, impact_risk=0.2`.
- Test chạy bằng `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <file>` từ gốc repo.

## Review Focus

1. **Symbol id không tồn tại** gửi vào `traverse`, `explain_dependency_path`, `get_component`: phải ra `NODE_NOT_FOUND`, không trả danh sách rỗng như thể "không có ai gọi". Test ở Task 3 và Task 4.
2. **Graph lớn chạm giới hạn**: `traverse`/`explain_dependency_path` dừng ở `max_nodes` và báo `truncated: true`. Test ở Task 3.
3. **Diff hỏng hoặc sửa file ngoài graph**: `verify_patch` / `run_patch_tests` trả `status: ERROR` kèm lý do, repo gốc không đổi byte nào. Test ở Task 5 và Task 6.
4. **Pytest treo hoặc quá thời gian**: `run_patch_tests` trả `ERROR`, bản copy tạm vẫn được dọn. Test ở Task 6.
5. **Graph đổi version sau `build_or_update_graph`**: bộ đệm document theo `graph_version`, không trả graph cũ cho version mới. Test ở Task 2.

---

### Task 0: Chuẩn bị (người dùng + ghi baseline)

**Files:** không sửa code.

- [ ] **Step 1 (người dùng):** commit phần gộp TV1/TV3 đang chờ và follow-up SC-1.

```bash
git commit -m "Merge TV1 (mcp/server-h1-l6-8-checkpoint-20261109) and TV3 (mcp/tv3-ev-l4-checkpoint-20261111) into the TV2 branch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add src/vgar/contracts/schema.py tests/test_schema_contract.py tests/test_retrieval_rt1.py \
  docs/superpowers/specs/2026-11-10-tv2-sc-1-schema-design.md docs/status/tv2_rt_1_retrieval_run_2026-11-10.md
git commit -m "fix(graph): SC-1 follow-up (TV2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Ghi baseline suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider > <workspace>/baseline.log 2>&1; grep -E "^(FAILED|ERROR) " <workspace>/baseline.log | sed -E 's/ - .*//' | sort > <workspace>/baseline_failures.txt`
Expected: chỉ các lỗi đã biết ở spec §4.1 (thiếu SDK2 `mcp.Client`/`mcp_types`; không Docker; `test_w9_bundle::test_checked_in_fixture…`, `test_runner_contract::test_different_arm_contexts…`, `test_official_harness::test_campaign_reads…`). Mọi task sau so suite với file này: **không thêm lỗi mới**.

---

### Task 1: Chỉ dữ liệu thật — bỏ backend `demo` (spec §7.8, H8)

**Files:**
- Create: `tests/graph_fixture.py`, `tests/conftest.py`, `tests/test_tv2_real_backend.py`
- Delete: `src/vgar/graph/demo_service.py`
- Modify: `src/vgar/graph/factory.py`, `src/vgar/config/settings.py` (dòng 79, 122)
- Modify (test/script dùng `demo`): `tests/test_mcp_tool_contract.py:141-146`, `tests/test_w10_impact_mcp.py:11,75-76`, `tests/test_settings.py`, `tests/mcp_server/test_resources.py:18-25,97-108`, `tests/fixtures/mcp_server/resource_fixture_server.py:8,38`, `tests/mcp_server/test_core_wire.py:24`, `test_incremental_serving.py:97`, `test_prompt_wire.py:25,83`, `test_resource_wire.py:26`, `test_sdk_runtime.py:94`, `test_tv3_ranking.py:172`, `test_tv3_verification.py:159`, `scripts/mcp_server/_preflight_worker.py:15`, `scripts/mcp_server/smoke_mcp.py:207`, các lệnh `VGAR_GRAPH_BACKEND=demo` trong `docs/mcp_server/*.md`

**Interfaces:**
- Produces: `tests/graph_fixture.py`
  - `FIXTURE_REPO: Path` = `tests/fixtures/vgar-arch-cases/multi_package`
  - `build_fixture_database(target_dir: Path, repo: Path = FIXTURE_REPO) -> tuple[Path, str]` → `(đường dẫn .db, graph_version)`; dựng bằng `PythonGraphBuilder(repo_key="fixture/multi_package", repository_revision="fixture").build(repo)` rồi `SQLiteGraphStore(db).ingest(document)`.
  - `fixture_service(target_dir: Path, repo: Path = FIXTURE_REPO) -> SQLiteGraphService` (có `repository_root=repo`).
- Produces: `tests/conftest.py` dựng DB fixture **một lần lúc import** vào thư mục tạm và `os.environ.setdefault` cho `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_GRAPH_DATABASE=<db>`, `VGAR_REPOSITORY_ROOT=<FIXTURE_REPO>`, để mọi module import `graph_server` (gọi `create_graph_service()` ngay khi import) có graph thật.

- [ ] **Step 1: Viết test hỏng**

```python
# tests/test_tv2_real_backend.py
def test_demo_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "demo")
    with pytest.raises(RuntimeError, match="vgar index"):
        create_graph_service()

def test_default_backend_is_sqlite_and_needs_a_database(monkeypatch):
    monkeypatch.delenv("VGAR_GRAPH_BACKEND", raising=False)
    monkeypatch.delenv("VGAR_GRAPH_DATABASE", raising=False)
    with pytest.raises(RuntimeError, match="VGAR_GRAPH_DATABASE"):
        create_graph_service()

def test_missing_database_file_fails_at_startup(monkeypatch, tmp_path):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "absent.db"))
    with pytest.raises(RuntimeError, match="absent.db"):
        create_graph_service()

def test_fixture_database_serves_real_symbols(monkeypatch, tmp_path):
    db, version = build_fixture_database(tmp_path)
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite"); monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(db))
    service = create_graph_service()
    assert service.backend_name == "sqlite"
    assert service.get_repository_summary().graph_version == version
    assert any(s.path.startswith("app/") for s in service.search_symbols("service").symbols)

def test_settings_default_backend_is_sqlite(monkeypatch):
    monkeypatch.delenv("VGAR_GRAPH_BACKEND", raising=False)
    assert reload_settings().graph.backend == "sqlite"   # vgar.config.settings.reload_settings

def test_no_module_imports_the_demo_service():
    import importlib.util
    assert importlib.util.find_spec("vgar.graph.demo_service") is None
```

- [ ] **Step 2: Chạy, thấy hỏng**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tv2_real_backend.py`
Expected: FAIL (demo vẫn được chấp nhận; `graph_fixture` chưa có).

- [ ] **Step 3: Cài đặt**
  - `factory.py`: mặc định `os.getenv("VGAR_GRAPH_BACKEND", "sqlite")`; `demo` → `RuntimeError("Backend 'demo' was removed; build a real graph with `vgar index <repo> --db <file>.db` and set VGAR_GRAPH_DATABASE")`; nhánh `sqlite` kiểm file tồn tại, thiếu thì `RuntimeError` có đường dẫn; thông báo lỗi backend lạ chỉ còn `'sqlite' or 'snapshot'`.
  - `settings.py`: mặc định `backend = "sqlite"` ở cả hai chỗ.
  - Xóa `demo_service.py`.
  - Test/fixture server dùng `DemoGraphService` chuyển sang `fixture_service(...)`; `SyntheticService` trong `resource_fixture_server.py` kế thừa `SQLiteGraphService` (dựng bằng `fixture_service`) và giữ nguyên các override hiện có. Test `test_demo_backend_uses_the_same_error_code` đổi thành cùng khẳng định với `fixture_service`. Nửa `DemoGraphService` của `test_tool_needs_a_repository_root_and_a_snapshot_backend` bỏ đi (nửa SQLite thiếu root vẫn giữ).
  - Env `VGAR_GRAPH_BACKEND: "demo"` trong test wire và script TV1 → `sqlite` + `VGAR_GRAPH_DATABASE` của DB fixture dựng trong test đó (test wire cần SDK2, máy này không chạy được; chỉ cần đúng cú pháp và import).
  - Runbook TV1: thay lệnh `demo` bằng hai bước `vgar index` + `VGAR_GRAPH_DATABASE`.

- [ ] **Step 4: Chạy, thấy qua; suite không thêm lỗi**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tv2_real_backend.py tests/test_mcp_tool_contract.py tests/test_w10_impact_mcp.py tests/test_settings.py tests/mcp_server/test_resources.py` rồi suite đầy đủ so với `baseline_failures.txt`.
Expected: PASS; `rg -n "DemoGraphService|demo_service|BACKEND.{0,4}demo" src scripts tests docs/mcp_server` không còn kết quả (trừ thông báo lỗi trong `factory.py`).

- [ ] **Step 5: Bàn giao commit** — danh sách file của task; message `refactor(graph): serve real graphs only and drop the demo backend (TV2 integration)`.

---

### Task 2: Nạp graph một lần cho mỗi version (spec §7.1)

**Files:**
- Modify: `src/vgar/graph/sqlite_service.py`
- Test: `tests/test_tv2_integration_service.py`

**Interfaces:**
- Produces: `SQLiteGraphService._document(graph_version: str) -> dict` (bộ đệm theo version; mọi phương thức đang gọi `self.store.load_document(...)` chuyển sang gọi hàm này); retriever của `get_related_context` giữ theo khóa `(graph_version, ranking_config_hash)`.
- Consumes: `fixture_service` (Task 1).

- [ ] **Step 1: Viết test hỏng**

```python
def test_document_is_loaded_once_per_version(tmp_path, monkeypatch):
    service = fixture_service(tmp_path); version = service.get_repository_summary().graph_version
    calls = []
    original = service.store.load_document
    monkeypatch.setattr(service.store, "load_document", lambda v: calls.append(v) or original(v))
    service.find_task_anchors("app service fails", graph_version=version, task_id="t1")
    service.find_task_anchors("app service fails", graph_version=version, task_id="t2")
    assert calls == [version]

def test_cache_never_serves_another_version(tmp_path):
    service = fixture_service(tmp_path); version = service.get_repository_summary().graph_version
    service._document(version)
    with pytest.raises(Exception):              # version không có trong DB → lỗi của store, không trả graph cũ
        service._document("sha256:" + "0" * 64)

def test_related_context_output_is_unchanged_by_the_cache(tmp_path):
    # chạy get_related_context hai lần trên cùng service (tokenizer bytes/4 hoặc counter của test hiện có)
    # → hai output bằng nhau và bằng output của một service mới tạo
```

- [ ] **Step 2: Chạy, thấy hỏng** — Expected: `calls == [v, v]`.
- [ ] **Step 3: Cài đặt** bộ đệm `dict[str, dict]` trong instance.
- [ ] **Step 4: Chạy, thấy qua** + `tests/test_sqlite_graph_service.py tests/test_w5_w6_mcp.py tests/test_retrieval_rt1.py`.
- [ ] **Step 5: Bàn giao commit** — `perf(graph): load each graph version once per service (TV2 integration)`.

---

### Task 3: Callers/callees nhiều bước và đường phụ thuộc (spec §7.1, §7.2, H3)

**Files:**
- Modify: `src/vgar/graph/sqlite_service.py`, `src/vgar/mcp/servers/graph_server.py` (`get_callers`, `get_callees`, `_multihop`, `explain_dependency_path`)
- Test: `tests/test_tv2_integration_service.py`, `tests/mcp_server/test_tv2_guide_routing.py`

**Interfaces:**
- Produces:
  - `SQLiteGraphService.traverse(symbol_id: str, direction: Literal["callers","callees"], depth: int, max_nodes: int = 200) -> dict` với khóa `symbol_id, direction, depth, symbols, may_call, truncated, examined`. `symbols`: `[{symbol_id, name, kind, path, hop, via}]`, mỗi hop dùng đúng `store.get_callers` / `store.get_callees` (nên hop 1 trùng tool `depth=1`); `may_call`: các đích qua cạnh `MAY_CALL` của document, `[{symbol_id, hop, confidence, via}]`.
  - `SQLiteGraphService.explain_dependency_path(source_id: str, target_id: str, max_hops: int = 6, max_nodes: int = 200) -> dict` với khóa `source_id, target_id, found, nodes, edges, examined_edges, truncated`; BFS có hướng trên các cạnh `CALLS, MAY_CALL, IMPORTS, DEPENDS_ON, CONTAINS, HAS_METHOD, HAS_CALLSITE`; mỗi phần tử `edges` là `{edge_id, edge_type, source_id, target_id, confidence}`.
  - Hai hàm báo `NodeNotFoundError` khi id không có trong graph.
  - `graph_server._has_provider(capability: str) -> bool` = `core_tools.registry.get(capability) is not None`.

- [ ] **Step 1: Viết test hỏng** (đáp án viết tay từ `tests/fixtures/vgar-arch-cases/multi_package`: đọc `app/service.py`, `app/parser.py`, `db/store.py`, ghi cặp gọi thật làm hằng số trong test)

```python
def test_traverse_hop_one_matches_direct_callers(tmp_path):
    service = fixture_service(tmp_path)
    target = <id hàm trong db/store.py được app/service.py gọi>
    direct = [s.symbol_id for s in service.get_callers(target).symbols]
    result = service.traverse(target, "callers", depth=1)
    assert [s["symbol_id"] for s in result["symbols"] if s["hop"] == 1] == direct

def test_traverse_depth_two_reaches_callers_of_callers(tmp_path): ...  # hằng số viết tay
def test_traverse_reports_truncation(tmp_path):
    assert service.traverse(<id>, "callers", depth=5, max_nodes=1)["truncated"] is True
def test_traverse_unknown_symbol_is_not_found(tmp_path):
    with pytest.raises(NodeNotFoundError): service.traverse("missing:x", "callers", depth=2)
def test_may_call_is_listed_separately(tmp_path):
    # dùng document có cạnh MAY_CALL: dựng repo nhỏ trong tmp_path có lời gọi qua tham số không định kiểu,
    # hoặc chèn một cạnh MAY_CALL hợp lệ vào document trước khi ingest
    assert all(item["symbol_id"] not in symbol_ids for item in result["may_call"])
def test_path_follows_typed_edges(tmp_path):
    result = service.explain_dependency_path(<hàm app/service.py>, <hàm db/store.py>)
    assert result["found"] and result["nodes"][0] == <src> and result["nodes"][-1] == <dst>
    assert {e["edge_type"] for e in result["edges"]} <= {"CALLS","MAY_CALL","IMPORTS","DEPENDS_ON","CONTAINS","HAS_METHOD","HAS_CALLSITE"}
def test_path_absent_returns_found_false(tmp_path): ...

# tests/mcp_server/test_tv2_guide_routing.py (in-process, monkeypatch graph_server.graph_service = fixture_service(...))
def test_get_callers_depth_two_runs_without_a_provider(...):
    data = graph_server.get_callers(<id>, depth=2)
    assert data["status"] == "PASS" and data["data"]["callers"]
def test_explain_dependency_path_runs_without_a_provider(...): ...
def test_registered_provider_still_wins(...):
    # đăng ký provider giả cho "traversal" bằng ProviderRegistry(..., test_only=True) như test hiện có của TV1
    # → get_callers(depth=2) đi đường core_tools (không gọi service.traverse)
```

- [ ] **Step 2: Chạy, thấy hỏng** — Expected: `AttributeError: traverse`; tool trả `CAPABILITY_UNAVAILABLE`.
- [ ] **Step 3: Cài đặt** hai phương thức; trong `graph_server`, `get_callers`/`get_callees` với `depth>1` và `explain_dependency_path`: `if _has_provider(...)` giữ code cũ, không thì gọi service qua `_tool(...)` (cùng kiểu `search_symbols`, docstring có `Args:`). Giới hạn `max_nodes` lấy từ `core_tools.limits.max_nodes`, `max_hops` từ `core_tools.limits.max_hops`.
- [ ] **Step 4: Chạy, thấy qua** + `tests/test_mcp_tool_contract.py tests/mcp_server/test_core_tools.py`.
- [ ] **Step 5: Bàn giao commit** — `feat(mcp): multi-hop callers/callees and dependency paths from the real graph (TV2 integration)`.

---

### Task 4: Resource schema, component, task, baseline (spec §6.2, §7.1, §7.2)

**Files:**
- Modify: `src/vgar/graph/sqlite_service.py`, `src/vgar/mcp/proposal/resources.py` (`ResourceReader.read`, `_content`)
- Test: `tests/test_tv2_integration_service.py`, `tests/mcp_server/test_tv2_guide_routing.py`

**Interfaces:**
- Produces:
  - `get_schema() -> dict` = `schema_description()`.
  - `get_component(component_id: str) -> dict` khóa đúng §10.2: `component, files, public_ports, dependencies, dependents, tests, risk`. `component_id` là id node Component hoặc tên duy nhất. `files`, `tests` từ `properties` của node; `public_ports` = Port qua `EXPOSES_PORT` (chuỗi `qualified_name`); `dependencies`/`dependents` = Component qua `DEPENDS_ON` ra/vào; `risk` = `"high_fanin"` khi số `dependents` ≥ 3, `"high_coupling"` khi `coupling` ≥ 1.0, không thì `null`.
  - `find_task_anchors` lưu kết quả vào `self._tasks[task_id]`; `get_task(task_id: str) -> dict` trả bản đã lưu, chưa có thì `GraphNotReadyError("Call find_task_anchors for this task first")`.
  - `get_baseline() -> dict` khóa `graph_version, schema_version, node_counts, edge_counts, tests: "NOT_RUN", invariants: "NOT_RUN"`.
  - `ResourceReader`: với `schema/component/task/baseline`, nếu `tools.registry.get("resource_"+kind) is None` thì đọc từ service (`json.dumps(...)`), kể cả khi không có context; nếu có provider thì giữ đường cũ.

- [ ] **Step 1: Viết test hỏng**

```python
def test_component_has_the_proposal_keys(tmp_path):
    service = fixture_service(tmp_path)
    component = next(n for n in service._document(v)["nodes"] if n["type"] == "Component")
    data = service.get_component(component["id"])
    assert set(data) == {"component","files","public_ports","dependencies","dependents","tests","risk"}
    assert data["files"] == component["properties"]["files"]
def test_unknown_component_is_not_found(tmp_path): ...       # NodeNotFoundError
def test_task_exists_only_after_find_task_anchors(tmp_path):
    with pytest.raises(GraphNotReadyError): service.get_task("t1")
    service.find_task_anchors("app/service.py fails", graph_version=v, task_id="t1")
    assert service.get_task("t1")["task_id"] == "t1"
def test_baseline_marks_tests_and_invariants_not_run(tmp_path): ...
def test_resources_are_served_without_a_context(...):   # in-process qua graph_server._read_resource
    for uri in ("vgar://repo/schema", f"vgar://component/{cid}", "vgar://evidence/baseline"):
        assert json.loads(graph_server._read_resource(uri))
def test_resource_with_a_registered_provider_keeps_the_provider_path(...): ...  # test hiện có của TV1 vẫn xanh
```

- [ ] **Step 2: Chạy, thấy hỏng** — Expected: `"Host-bound context required for new resources"`.
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy, thấy qua** + `tests/mcp_server/test_resources.py`.
- [ ] **Step 5: Bàn giao commit** — `feat(mcp): schema, component, task and baseline resources from the real graph (TV2 integration)`.

---

### Task 5: `verify_patch` (spec §7.3)

**Files:**
- Create: `src/vgar/repair/patch_evidence.py`
- Modify: `src/vgar/mcp/servers/graph_server.py` (`verify_patch_graph_constraints`)
- Test: `tests/test_tv2_patch_evidence.py`

**Interfaces:**
- Consumes: `SQLiteGraphService._document`, `repository_root`.
- Produces: `verify_patch(service: SQLiteGraphService, diff: str, *, graph_version: str) -> dict` khóa `status, checks, reasons, graph_version, diff_sha256`; `checks` có `schema, structural, api, source_imports, port_check, fanout` (mỗi mục `{status, details}`; `fanout.status = "NOT_RUN"`).
- Cách làm: thiếu `repository_root` → `GraphNotReadyError`. `PatchPolicy(<path các node File>, ())`; `parse_unified_diff(diff, policy)` + `_bind(parsed, root)` (`vgar.repair.patch`, như provider TV3) cho bytes sau patch; chép repo vào thư mục tạm, ghi bytes mới, dựng `G'` bằng `PythonGraphBuilder` cùng `repo_key`, `repository_revision`, `source_roots` của graph; rồi `validate_graph_document(G')`, `check_structure(baseline, G', before_sources=…, after_sources=…)`, `check_api(before, after, changed_only=True)`, `check_source_import_cycles(baseline, G', before, after)`, `analyze_patch_impact(diff, document, root, patch_policy=policy)["port_check"]` (lấy qua `json.loads(report.canonical_json())`). `status = PASS` khi mọi check bắt buộc (schema, structural, api, source_imports, port_check) `PASS`; có `FAIL` → `FAIL`; lỗi parse/bind → `ERROR` với lý do. Thư mục tạm dọn trong `finally`.

Fixture: repo `tests/fixtures/w7_w8_handoff/single_file_login/repo` và `multi_file_invoice/repo`; patch đúng `tests/fixtures/m2/reference_patches/<task>.diff`, patch sai `tests/fixtures/m2/wrong_patches/<task>.diff`. Graph dựng bằng `fixture_service(tmp_path, repo=<repo>)`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_reference_patch_passes_graph_checks(tmp_path): assert verify_patch(svc, REF, graph_version=v)["status"] == "PASS"
def test_removing_a_public_function_fails_on_port_or_api(tmp_path):
    # diff viết tay xóa hàm công khai `login` khỏi auth.py
    result = verify_patch(svc, REMOVE_LOGIN, graph_version=v)
    assert result["status"] == "FAIL" and "FAIL" in {result["checks"]["api"]["status"], result["checks"]["port_check"]["status"]}
def test_malformed_diff_is_error_and_repo_is_untouched(tmp_path):
    before = _hash_tree(repo); result = verify_patch(svc, "not a diff", graph_version=v)
    assert result["status"] == "ERROR" and _hash_tree(repo) == before
def test_diff_outside_the_graph_is_error(tmp_path): ...
def test_missing_repository_root_is_not_ready(tmp_path): ...   # GraphNotReadyError
def test_tool_uses_verify_patch_without_a_provider(...): ...   # graph_server.verify_patch_graph_constraints(REF)
```

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt** (`logger` module, không `print`).
- [ ] **Step 4: Chạy, thấy qua** + `tests/mcp_server/test_tv3_verification.py` (phần không cần SDK2).
- [ ] **Step 5: Bàn giao commit** — `feat(repair): guide-style graph verification of a patch (TV2 integration)`.

---

### Task 6: `run_patch_tests` (spec §7.6)

**Files:**
- Modify: `src/vgar/repair/patch_evidence.py`, `src/vgar/mcp/servers/execution_server.py` (`run_relevant_tests`)
- Test: `tests/test_tv2_patch_evidence.py`

**Interfaces:**
- Produces: `run_patch_tests(service: SQLiteGraphService, diff: str, *, graph_version: str, failing_tests: list[str] | None = None, timeout_seconds: int = 300) -> dict` khóa `status, selectors, baseline, candidate, previously_failing_fixed, regressions, diff_sha256, cleaned, broader_suite: "NOT_RUN", coverage: "NOT_RUN"`.
- Cách làm: node bị chạm lấy từ `analyze_patch_impact` (D3); `select_related_tests(document, symbol_ids, changed_paths=…, failing_tests=…)`; chép repo (bỏ `.git`) vào thư mục tạm; mỗi selector có file tồn tại chạy `pytest_runner.run_selector(root, selector, timeout_seconds=…, output_cap=…)` trước và sau khi ghi bytes của patch (một lần). Quy tắc `PASS/FAIL/NOT_RUN/ERROR` đúng spec §7.6 bước 3. Hết giờ hoặc runner lỗi → `ERROR`. `cleaned` là `True` chỉ khi thư mục tạm đã bị xóa.
- `execution_server.run_relevant_tests`: không có provider `tests` thì gọi `run_patch_tests` với service tạo **lười** bằng `create_graph_service()` ở lần gọi đầu (không tạo lúc import).

- [ ] **Step 1: Viết test hỏng**

```python
def test_reference_patch_fixes_the_failing_test(tmp_path):
    r = run_patch_tests(svc, REF, graph_version=v, failing_tests=["tests/test_auth.py::test_login_rejects_whitespace"])
    assert r["status"] == "PASS" and r["previously_failing_fixed"] and not r["regressions"] and r["cleaned"]
def test_wrong_patch_fails(tmp_path): assert run_patch_tests(svc, WRONG, graph_version=v, failing_tests=[...])["status"] == "FAIL"
def test_no_related_tests_is_not_run(tmp_path): ...
def test_timeout_is_error_and_copy_is_cleaned(tmp_path, monkeypatch):
    # monkeypatch pytest_runner.run_selector để ném/trả timeout → status ERROR, cleaned True
def test_original_repository_is_never_modified(tmp_path): ...   # hash cây trước/sau bằng nhau
def test_execution_tool_runs_without_a_provider(...): ...      # asyncio.run(execution_server.run_relevant_tests(REF))
```

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy, thấy qua** + `tests/mcp_server/test_tv3_diff_tests.py` (phần không cần SDK2).
- [ ] **Step 5: Bàn giao commit** — `feat(repair): guide-style relevant test run for a patch (TV2 integration)`.

---

### Task 7: `rank_candidates` (spec §7.7, H10)

**Files:**
- Create: `configs/mcp_server/ranking_weights.json` (giá trị H10, kèm khóa `"status": "provisional, pending team decision"`)
- Modify: `src/vgar/repair/patch_evidence.py`, `src/vgar/mcp/servers/graph_server.py` (`rank_patch_candidates`)
- Test: `tests/test_tv2_patch_evidence.py`

**Interfaces:**
- Produces:
  - `evidence_fields(verify: dict, tests: dict) -> dict[str, str]`: 9 trường §8.5, nguồn đúng bảng spec §7.7 bước 1.
  - `score_patch(fields: dict[str, str], weights: dict[str, float], impact_risk: float | None) -> tuple[float, float]` → `(lower, upper)`; cùng các số hạng với `_score_interval` của TV3; `impact_risk is None` → trừ toàn bộ `w_risk`.
  - `rank_candidates(candidates: list[dict], *, verify_results: dict[str, dict], test_results: dict[str, dict], weights: dict[str, float]) -> dict` (khóa `diff_sha256` → kết quả) trả `{"ranking": [{candidate_id, eligible, score, score_interval, evidence_fields}]}`, sắp: đủ điều kiện trước, `score` giảm dần, `candidate_id`.
  - `graph_server`: giữ `_verify_cache`, `_test_cache` theo `diff_sha256`; `verify_patch_graph_constraints` và (qua service) kết quả test được ghi vào cache; `rank_patch_candidates` không có provider `ranking` thì tính phần thiếu rồi gọi `rank_candidates`. `impact_risk` = 1.0 khi `port_check` báo mất port công khai, 0.0 khi không, `None` khi `port_check` không `PASS`/`FAIL`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_score_matches_tv3_when_impact_is_unmeasured():
    from vgar.mcp.proposal.ranking_provider import ScoreWeights, _score_interval
    w = {"tests":0.5,"schema_conformance":0.15,"architecture":0.1,"api":0.15,"semantic":0.1,"impact_risk":0.2}
    fields = {... 9 trường, hỗn hợp PASS/FAIL/NOT_RUN ...}
    assert score_patch(fields, w, None) == _score_interval(fields, ScoreWeights(**w))
def test_reference_patch_ranks_above_wrong_patch(tmp_path): ...
def test_failed_required_check_never_ranks_first(tmp_path): ...   # candidate điểm cao nhưng verify FAIL → eligible False, không đứng đầu
def test_weights_file_holds_the_provisional_values(): ...
def test_rank_tool_runs_without_a_provider(...): ...
```

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy, thấy qua** + `tests/mcp_server/test_tv3_ranking.py` (phần không cần SDK2).
- [ ] **Step 5: Bàn giao commit** — `feat(repair): guide-style candidate ranking from patch evidence (TV2 integration)`.

---

### Task 8: Lịch sử L4-1 vào `get_related_context` (spec §7.4, H7)

**Files:**
- Modify: `src/vgar/graph/sqlite_service.py` (`get_related_context`)
- Test: `tests/test_tv2_integration_service.py`

**Interfaces:**
- Produces: `get_related_context(..., use_history: bool = False, history_commits: int = 50)`. Khi bật: `read_commit_history(repository_root, revision=document["repository_revision"], max_commits=history_commits)` (`vgar.graph.history`), truyền `change_counts`, `history_label` vào `GraphContextRetriever`. Thiếu dulwich, revision không phải SHA 40 ký tự, hoặc thiếu object → chạy như tắt và thêm `"recent_change_frequency"` vào `diagnostics.unavailable_features`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_history_is_off_by_default_and_output_is_unchanged(tmp_path): ...
def test_history_window_stops_at_the_graph_revision(tmp_path):
    # repo git tạm: commit A (base, graph dựng ở A), commit B sau đó sửa file khác
    # → change_counts chỉ chứa file của A, không có file chỉ B sửa
def test_missing_history_is_reported_not_hidden(tmp_path):
    # repository_revision="fixture" (không phải SHA) → unavailable_features có "recent_change_frequency"
```

- [ ] **Step 2: Chạy, thấy hỏng.** — [ ] **Step 3: Cài đặt.** — [ ] **Step 4: Chạy, thấy qua** + `tests/test_commit_history.py tests/test_retrieval_rt1.py`.
- [ ] **Step 5: Bàn giao commit** — `feat(graph): optional commit history signal for related context (TV2 integration)`.

---

### Task 9: Kiểm cuối theo hướng dẫn và plan (spec §9, §10)

**Files:**
- Create: `tests/mcp_server/test_tv2_no_stdout.py`, `docs/status/tv2_layer_integration_run_2026-11-11.md`
- Modify: spec §10 (điền tên test thật vào bảng truy vết)

- [ ] **Step 1: Test không ghi stdout**

```python
def test_new_modules_never_print():
    for path in ("src/vgar/repair/patch_evidence.py", "src/vgar/graph/sqlite_service.py", "src/vgar/graph/factory.py"):
        assert "print(" not in Path(path).read_text(encoding="utf-8")
def test_guide_tools_write_nothing_to_stdout(capsys, ...):
    # gọi in-process get_callers(depth=2), explain_dependency_path, 4 resource, verify, rank trên fixture
    assert capsys.readouterr().out == ""
def test_fixture_graph_passes_schema_validation(tmp_path): ...   # validate_graph_document
```

- [ ] **Step 2: Chạy suite đầy đủ** — Expected: không có lỗi ngoài `baseline_failures.txt`. Kiểm thêm: envelope của các tool kiểu hướng dẫn có `backend == "sqlite"` (H8; `vgar.mcp.tooling` đã ghi trường `backend`).
- [ ] **Step 3: Kiểm tay theo hướng dẫn** (ghi kết quả thật vào báo cáo, kể cả bước không chạy được):
  - `vgar index tests/fixtures/w7_w8_handoff/multi_file_invoice/repo --db <tmp>/invoice.db`.
  - Khởi động `graph_server` với `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_GRAPH_DATABASE`, `VGAR_REPOSITORY_ROOT`: tiến trình chạy, stdout chỉ có JSON-RPC.
  - Inspector modern/legacy và Claude Code cần SDK2: máy này không có thì ghi "chưa chạy, giao TV1" (spec §11).
- [ ] **Step 4: Viết báo cáo** `docs/status/tv2_layer_integration_run_2026-11-11.md`: bảng tool/resource → chạy được chưa, test tương ứng, độ lệch H4/H5, phần giao TV1/TV3, lệnh tái tạo.
- [ ] **Step 5: Bàn giao commit** — `docs(mcp): layer integration run report and traceability (TV2 integration)`.
