# Đợt 4: sửa vòng sửa lỗi của agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tool đọc graph chạy được khi code đã sửa, không thay đổi nào vào graph mà chưa kiểm, `search_symbols` nhận nhiều từ (phần A); grounding theo §6.6/§15 (phần B).

**Architecture:** Phần A: retriever nhận mã đã lưu của đợt 3 thay cho thư mục làm việc; tool `build_or_update_graph` tự chạy `analyze` + `verify` trên thay đổi chưa kiểm trước khi build; service từ chối `graph_version` đã bị xoá; `search_symbols` gộp kết quả theo từng từ. Phần B: thêm bốn luật vào `TaskAnchorFinder`, bộ trích thông báo trong `source_evidence.py` và `TaskOverlayBuilder`, đo bằng R1 dev-50 trước/sau.

**Tech Stack:** Python 3.11, SQLite, mcp SDK 2.2, pytest; R1 trong WSL (`~/.vgar-wsl`, code `~/vgar-rt1`, dữ liệu `~/rt1`).

**Spec:** `docs/superpowers/specs/2026-11-23-tv2-agent-loop-fixes-design.md` (quyết định áp dụng: D1 = c, D2 = R1 hai lần, D3 = phần A trước).

## Global Constraints

- Tool không ghi vào thư mục làm việc của người dùng; mọi bước kiểm chạy trên bản sao tạm hoặc trong bộ nhớ.
- Cùng nội dung → cùng kết quả trên Windows và Linux.
- Chữ ký tool MCP không đổi; `tests/fixtures/mcp_server/expected_contract.json` không đổi.
- Nhánh host tin cậy của TV1 (`_trusted_build_host`) và contract `DiffRequest` không đổi.
- Quy tắc build-server: không in ra stdout, logger theo module, docstring có `Args:`.
- Graph không lưu mã (database cũ) giữ hành vi cũ.
- Không commit, không push: hết mỗi phần, đưa TV2 danh sách file và lệnh commit.
- Làm trong `D:\kltn\vgar_mcp_mvp_demo`, chạy test bằng `.venv\Scripts\python.exe -m pytest`.
- Bộ test toàn phần: không thêm lỗi ngoài danh sách lỗi đã biết ghi trong `.superpowers/sdd/2026-11-22-tv2-patch-checks-from-snapshot/progress.md`.

## Review Focus

- File của graph bị xoá khỏi thư mục làm việc: `get_related_context` vẫn chạy, `worktree_changes` liệt kê file đó (test ở Task 1).
- Build hai lần liên tiếp không sửa gì: lần hai báo `NO_CHANGES`, không chạy kiểm (test ở Task 3).
- Truy vấn `search_symbols` chỉ gồm từ ngắn (`"a b"`): dùng cả chuỗi như hiện nay, không lỗi (test ở Task 4).
- Đề bài có một từ trong ngoặc kép (`"WELCOME10"`) hoặc cụm trong backtick: không thành thông báo lỗi (test ở Task 9).
- Database chưa có graph: các tool vẫn báo `GRAPH_NOT_READY` như cũ, không bị lỗi "version cũ" che (test ở Task 2).

---

## Phần A

### Task 1: Retrieval đọc mã đã lưu, báo file đang khác graph

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`GraphContextRetriever.__init__` dòng 142-150, `_verify_snapshot` dòng 798-818, dòng 410)
- Modify: `src/vgar/graph/snapshot_sources.py` (thêm hàm)
- Modify: `src/vgar/graph/sqlite_service.py` (`_retriever` dòng 105-116, `get_related_context` dòng 125-170)
- Modify: `src/vgar/mcp/servers/graph_server.py` (`get_related_context` dòng 210-255: giữ trường mới khi rút gọn diagnostics; docstring)
- Test: `tests/test_agent_loop_fixes.py` (mới; dùng lại `SHOP`, `_write`, `_build` như `tests/test_patch_checks_from_snapshot.py:25-150`)

**Interfaces:**
- Produces: `GraphContextRetriever(..., sources: Mapping[str, bytes] | None = None)`; `worktree_changes(sources: Mapping[str, bytes], root: Path) -> list[str]` trong `snapshot_sources.py` (đường dẫn POSIX đã sắp xếp của file `.py` sửa, thêm hoặc mất, theo `discover_python_files`); kết quả `get_related_context` có `diagnostics.worktree_changes: list[str]` và, khi danh sách không rỗng, `diagnostics.worktree_note: str`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_related_context_after_an_edit_uses_the_graph_code(tmp_path):
    service, version, root = _build(tmp_path)
    stored = (root / "shop/pricing.py").read_bytes()
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return round(amount)\n", encoding="utf-8")
    data = service.get_related_context([], 2000, graph_version=version, task_id="t", issue_text="round_vnd is wrong")
    texts = [item["snippet"] for item in data["context"]["items"] if item["path"] == "shop/pricing.py"]
    assert texts and all(text.encode() in stored for text in texts)
    assert data["diagnostics"]["worktree_changes"] == ["shop/pricing.py"]
    assert "not in this context" in data["diagnostics"]["worktree_note"]

def test_related_context_ignores_a_scratch_file_and_a_deleted_file(tmp_path):
    service, version, root = _build(tmp_path)
    (root / "scratch.py").write_text("x = 1\n", encoding="utf-8")
    (root / "shop/checkout.py").unlink()
    data = service.get_related_context([], 2000, graph_version=version, task_id="t", issue_text="round_vnd")
    assert data["diagnostics"]["worktree_changes"] == ["scratch.py", "shop/checkout.py"]

def test_find_task_anchors_with_a_labelled_error_line_after_an_edit(tmp_path):
    service, version, root = _build(tmp_path)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8")
    result = service.find_task_anchors("ValueError: something broke", graph_version=version, task_id="t")
    assert result["graph_version"] == version

def test_graph_without_stored_source_keeps_the_snapshot_check(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8")
    with pytest.raises(GraphError, match="Source content differs"):
        service.get_related_context([], 2000, graph_version=version, task_id="t", issue_text="round_vnd")

def test_clean_tree_ranks_the_same_with_and_without_stored_source(tmp_path):
    service, version, root = _build(tmp_path)
    document = service._document(version)
    kwargs = dict(count_tokens=len, counter_label="test")
    with_store = GraphContextRetriever(document, root, sources=service.snapshot_sources(version), **kwargs)
    without = GraphContextRetriever(document, root, **kwargs)
    a = with_store.retrieve([], 2000, issue_text="total uses round_vnd")
    b = without.retrieve([], 2000, issue_text="total uses round_vnd")
    assert a.candidates == b.candidates and a.context == b.context
```

Và một test cho tool (fixture `served` như `test_patch_checks_from_snapshot.py:287-298`): `graph_server.get_related_context(...)` sau khi sửa file trả `status == "PASS"` và `data["diagnostics"]["worktree_changes"] == ["shop/pricing.py"]`.

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py -q -p no:cacheprovider`
Expected: FAIL (`unexpected keyword argument 'sources'`, `KeyError: 'worktree_changes'`, GraphError "Source content differs" ở các test đầu)

- [ ] **Step 3: Cài đặt**

- `GraphContextRetriever.__init__` lưu `self._stored_sources = dict(sources) if sources is not None else None`. `_verify_snapshot()` trả `self._stored_sources` khi khác `None` (đã được `snapshot_sources` kiểm hash). Lời gọi ở dòng 410 chỉ chạy khi `self._stored_sources is None`.
- `SQLiteGraphService._retriever` truyền `sources=self.snapshot_sources(graph_version)`.
- `get_related_context` của service: khi `snapshot_sources(graph_version)` khác `None`, thêm `diagnostics["worktree_changes"] = worktree_changes(sources, self.repository_root)`; khi danh sách không rỗng, thêm `diagnostics["worktree_note"] = "context is the code the graph was built from; changes in these files are not in this context until you check them and rebuild the graph"`.
- Tool `get_related_context` (graph_server): khi thay `data["diagnostics"]` bằng bản rút gọn, giữ `worktree_changes` và `worktree_note` nếu có. Docstring thêm một câu: ngữ cảnh là mã graph được dựng từ đó; `diagnostics.worktree_changes` liệt kê file đang khác.

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py tests/test_graph_retrieval.py tests/test_graph_tools_agent_feedback.py tests/test_patch_checks_from_snapshot.py -q -p no:cacheprovider`
Expected: PASS

### Task 2: Từ chối `graph_version` đã bị xoá

**Files:**
- Modify: `src/vgar/graph/sqlite_store.py` (thêm `is_ready`)
- Modify: `src/vgar/graph/sqlite_service.py` (`_document` dòng 73-81; thêm `forget_other_versions`)
- Test: `tests/test_agent_loop_fixes.py`

**Interfaces:**
- Produces: `SQLiteGraphStore.is_ready(graph_version: str) -> bool`; `SQLiteGraphService.forget_other_versions(keep: str) -> None` (bỏ document và retriever của version khác khỏi cache; Task 3 gọi sau mỗi lần build). Lỗi version cũ: `InvalidQueryError(message, details={"reason": "stale_graph_version", "current_graph_version": current})`, message:
  `"graph_version {old} is no longer the graph of this repository (each build_or_update_graph replaces it); current: {current}; use the current version and call find_task_anchors again if you need anchors"`.

- [ ] **Step 1: Viết test hỏng**

```python
def _rebuild_with_edit(tmp_path, service, root):
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return round(amount)\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/snap", repository_revision="rev").build(root)
    service.store.ingest(document, sources=read_graph_sources(root, document))
    service.store.prune_other_versions(document["graph_version"], document["repo_key"])
    return document["graph_version"]

@pytest.mark.parametrize("call", [
    lambda s, v: s.find_task_anchors("round_vnd", graph_version=v, task_id="t"),
    lambda s, v: s.get_related_context([], 2000, graph_version=v, task_id="t", issue_text="round_vnd"),
    lambda s, v: s.get_related_tests([], graph_version=v),
    lambda s, v: s.analyze_patch_impact("", graph_version=v),
])
def test_a_pruned_version_is_refused_with_the_current_one(tmp_path, call):
    service, old, root = _build(tmp_path)
    service.find_task_anchors("round_vnd", graph_version=old, task_id="t")   # load the old version into the cache
    new = _rebuild_with_edit(tmp_path, service, root)
    with pytest.raises(InvalidQueryError, match="no longer the graph") as error:
        call(service, old)
    assert error.value.details == {"reason": "stale_graph_version", "current_graph_version": new}

def test_forget_other_versions_drops_cached_documents(tmp_path):
    service, old, root = _build(tmp_path)
    service.find_task_anchors("round_vnd", graph_version=old, task_id="t")
    service.forget_other_versions("sha256:other")
    assert old not in service._documents and not [k for k in service._retrievers if k[0] == old]

def test_empty_database_still_says_graph_not_ready(tmp_path):
    service = SQLiteGraphService(SQLiteGraphStore(tmp_path / "empty.db"), repository_root=tmp_path,
                                 count_tokens=len, counter_label="test")
    with pytest.raises(GraphNotReadyError):
        service.find_task_anchors("x", graph_version="sha256:none", task_id="t")
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py -k "pruned or forget or not_ready" -q -p no:cacheprovider`
Expected: FAIL (version cũ vẫn được phục vụ từ cache; `forget_other_versions` chưa có)

- [ ] **Step 3: Cài đặt**

`_document`: nếu `not self.store.is_ready(graph_version)`, bỏ version đó khỏi `_documents` và `_retrievers`, lấy `current = self.store.resolve_graph_version()` (để `GraphNotReadyError` tự đi lên khi database trống) rồi raise lỗi ở Interfaces. `is_ready` là một `SELECT 1 FROM graph_metadata WHERE graph_version = ? AND status = 'ready'`.

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py tests/mcp_server -q -p no:cacheprovider`
Expected: PASS

### Task 3: Build tự kiểm thay đổi chưa kiểm (D1 = c)

**Files:**
- Modify: `src/vgar/mcp/servers/graph_server.py` (`analyze_patch_impact` dòng 296-326, cache dòng 363-397, `build_or_update_graph` dòng 427-454)
- Modify: `README.md` (bước 4)
- Test: `tests/test_agent_loop_fixes.py` (fixture build như `tests/mcp_server/test_tv2_build_tool.py:15-36`: đặt `VGAR_GRAPH_BACKEND`, `VGAR_GRAPH_DATABASE`, `VGAR_REPOSITORY_ROOT`, `_live_builder = None`; `graph_service` trỏ cùng database)

**Interfaces:**
- Consumes: `resolve_diff(service, graph_version, diff) -> (str, dict)` (`patch_evidence.py:63`); `_verified(diff)`; `SQLiteGraphService.snapshot_sources`; `forget_other_versions` (Task 2).
- Produces: `_analyzed(diff: str, graph_version: str, max_hops: int = 2, max_nodes: int = 200) -> dict` với cache `_impact_cache` khoá `(graph_version, _diff_hash(diff), max_hops, max_nodes)`, không lưu kết quả lỗi; `_checks_before_update() -> dict[str, Any]`; kết quả build có `checks_before_update` với `status` ∈ `{"NO_CHANGES", "NOT_RUN", "CHECKED"}`.

- [ ] **Step 1: Viết test hỏng**

```python
def build(root): return anyio.run(graph_server.build_or_update_graph, str(root))["data"]

def test_build_with_an_unchecked_edit_checks_it_first(build_served):
    root = build_served
    build(root)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return round(amount)\n", encoding="utf-8")
    checks = build(root)["checks_before_update"]
    assert checks["status"] == "CHECKED"
    assert checks["checked_diff"]["files"] == ["shop/pricing.py"]
    assert checks["verify"]["status"] in {"PASS", "FAIL"} and checks["impact"]["changed_count"] >= 1
    assert checks["tests"] == "not run"

def test_build_reuses_the_checks_the_agent_already_ran(build_served, monkeypatch):
    root = build_served
    build(root)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return round(amount)\n", encoding="utf-8")
    calls = {"verify": 0, "impact": 0}
    real_verify, real_impact = patch_evidence.verify_patch, graph_server.graph_service.analyze_patch_impact
    monkeypatch.setattr(patch_evidence, "verify_patch", lambda *a, **k: calls.__setitem__("verify", calls["verify"] + 1) or real_verify(*a, **k))
    monkeypatch.setattr(graph_server.graph_service, "analyze_patch_impact", lambda *a, **k: calls.__setitem__("impact", calls["impact"] + 1) or real_impact(*a, **k))
    version = graph_server.graph_service.get_repository_summary().graph_version
    anyio.run(graph_server.verify_patch_graph_constraints)
    graph_server.analyze_patch_impact(version)
    build(root)
    assert calls == {"verify": 1, "impact": 1}

def test_clean_tree_build_reports_no_changes(build_served):
    build(build_served)
    assert build(build_served)["checks_before_update"] == {"status": "NO_CHANGES"}

def test_first_build_runs_no_checks(build_served):
    assert build(build_served)["checks_before_update"]["status"] == "NOT_RUN"

def test_a_new_file_only_is_not_run_and_the_build_still_runs(build_served):
    build(build_served)
    (build_served / "shop/extra.py").write_text("def extra():\n    return 1\n", encoding="utf-8")
    data = build(build_served)
    assert data["checks_before_update"]["status"] == "NOT_RUN" and "shop/extra.py" in data["changed_files"]

def test_analyze_after_a_rebuild_points_to_checks_before_update(build_served):
    build(build_served)
    version = build(build_served)["graph_version"]
    result = graph_server.analyze_patch_impact(version)
    assert "checks_before_update" in result["error"]["message"]
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py -k "build or analyze_after" -q -p no:cacheprovider`
Expected: FAIL (`KeyError: 'checks_before_update'`)

- [ ] **Step 3: Cài đặt**

- `_checks_before_update()`, theo đúng thứ tự (mỗi nhánh trả ngay):
  1. `graph_service.get_repository_summary()` raise `GraphNotReadyError` → `{"status": "NOT_RUN", "reason": "first build"}`.
  2. `graph_service.snapshot_sources(version) is None` → `{"status": "NOT_RUN", "reason": "graph has no stored source"}`.
  3. `checked, record = resolve_diff(graph_service, version, "")`; `ValueError` → `{"status": "NOT_RUN", "reason": str(error)}`.
  4. `checked == ""`: có `record["not_checked"]` → `{"status": "NOT_RUN", "reason": "only changes the checks cannot carry", "checked_diff": record}`; không có → `{"status": "NO_CHANGES"}`.
  5. Còn lại: `verify = _verified(checked)`, `impact = _analyzed(checked, version)` →
     `{"status": "CHECKED", "verify": {"status": verify["status"], "reasons": verify["reasons"]}, "impact": {"status": impact["impacted"]["status"], "changed_count": len(impact["changed"]), "impacted_count": len(impact["impacted"]["items"]), "port_check": impact.get("port_check")}, "checked_diff": record, "tests": "not run"}`.
  6. Mọi exception khác ở bước 3–5 → `{"status": "NOT_RUN", "reason": f"{type(error).__name__}: {error}"}`.
- Trong `checked()` của `build_or_update_graph` (nhánh không phải TV1): `checks = _checks_before_update()`, `data = call()`, `data["checks_before_update"] = checks`, `graph_service.forget_other_versions(data["graph_version"])`. Hàm audit thêm `"checks_status": data["checks_before_update"]["status"]`.
- Tool `analyze_patch_impact` dùng `_analyzed(...)` thay cho gọi service trực tiếp. Câu NO_CHANGES đổi thành: `"no change between the working tree and graph {version}; if you just rebuilt the graph, the change is already in it and that build checked it: see checks_before_update in its result"`.
- Docstring `build_or_update_graph`: thêm "If the working tree has changes the graph does not have, the server first checks them (analyze_patch_impact and verify_patch_graph_constraints, no tests) and returns the results in checks_before_update; read them before continuing."
- README bước 4: một câu về `checks_before_update`.

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py tests/mcp_server tests/test_patch_checks_from_snapshot.py tests/test_w10_impact_mcp.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: `search_symbols` nhiều từ

**Files:**
- Modify: `src/vgar/graph/sqlite_store.py` (`search_symbols` dòng 332-370)
- Modify: `src/vgar/mcp/servers/graph_server.py` (docstring `search_symbols` dòng 105)
- Test: `tests/test_agent_loop_fixes.py`

**Interfaces:**
- Produces: `search_symbols(query, limit)` giữ chữ ký và kiểu trả; hàm nội bộ `_search_terms(query: str) -> list[str]`.

- [ ] **Step 1: Viết test hỏng**

Fixture: repo có `shop/orders.py` với `cancel_order`, `ship_order`, `transition_to`, `order_total`.

```python
def test_three_names_return_three_symbols(order_store):
    names = [s.name for s in order_store.search_symbols("cancel_order ship_order transition_to", 20)]
    assert set(names) >= {"cancel_order", "ship_order", "transition_to"}

def test_single_term_is_unchanged(order_store):
    assert [s.name for s in order_store.search_symbols("order", 20)] == EXPECTED_ORDER_RESULTS   # captured before the change

def test_more_matched_terms_rank_first(order_store):
    assert order_store.search_symbols("order total", 20)[0].name == "order_total"

def test_short_terms_are_dropped_and_short_only_query_uses_the_whole_string(order_store):
    assert {s.name for s in order_store.search_symbols("to ship_order", 20)} == {"ship_order"}
    assert order_store.search_symbols("a b", 20) == []

def test_limit_applies_after_ranking(order_store):
    assert [s.name for s in order_store.search_symbols("order total cancel", 1)] == ["order_total"]
```

Ghi `EXPECTED_ORDER_RESULTS` bằng cách chạy truy vấn `"order"` trên code hiện tại trước khi sửa (Step 1).

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py -k "names or term or ranking" -q -p no:cacheprovider`
Expected: FAIL ở test ba tên, xếp hạng và limit; test một từ PASS

- [ ] **Step 3: Cài đặt**

`_search_terms`: tách theo `[\s,]+`, bỏ trùng giữ thứ tự, bỏ từ dưới 3 ký tự, tối đa 10; nếu không còn từ nào thì `[query.strip()]`. Một từ → câu SQL hiện tại, không đổi. Nhiều từ → chạy câu SQL hiện tại cho từng từ với `LIMIT 200`, gộp theo `id`, xếp theo `(-số từ khớp, 0 nếu tên trùng nguyên một từ (không phân biệt hoa thường) else 1, qualified_name, id)`, cắt `limit`. Docstring tool: "Several names separated by spaces return the symbols matching any of them, the ones matching the most names first."

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_loop_fixes.py tests/test_graph_tools_agent_feedback.py tests/mcp_server -q -p no:cacheprovider`
Expected: PASS

### Task 5: Kiểm phần A và bàn giao commit

**Files:**
- Modify: `docs/superpowers/specs/2026-11-23-tv2-agent-loop-fixes-design.md` (dòng Trạng thái: phần A đã cài đặt, quyết định D1–D3 theo đề xuất)

- [ ] **Step 1: Chạy toàn bộ test**

Run: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`
Expected: chỉ các lỗi đã biết (so với ledger đợt 3)

- [ ] **Step 2: Chạy tay trên bản sao ShopFlow**

Chép `D:\kltn\shopflow-clean\shopflow` vào thư mục tạm của job; trong một script Python (không đưa vào repo) đặt ba biến `VGAR_*` trỏ bản sao, gọi tool: build → sửa `shopflow/services/order_service.py` → `get_related_context` (`status == "PASS"`, `worktree_changes == ["shopflow/services/order_service.py"]`) → build (`checks_before_update.status == "CHECKED"`) → `search_symbols("cancel_order ship_order transition_to")` trả đủ ba tên.

- [ ] **Step 3: Bàn giao cho TV2 commit phần A**

Đưa danh sách file của Task 1–5 và lệnh: `git add <files>; git commit -m "feat(mcp): read tools use the graph's stored source, builds check unchecked edits first, stale graph versions are refused, search_symbols takes several names (TV2 batch 4 part A)"`. Chờ TV2 commit xong mới sang phần B.

---

## Phần B

### Task 6: Số nền trước khi đổi grounding

**Files:**
- Create: `scripts/probe_task_anchors.py`
- Create: `repair_agent/shopflow_grounding_cases.json`
- Create: `docs/status/tv2_batch4_grounding_2026-11-23.md` (phần "Trước")

**Interfaces:**
- Produces: `python scripts/probe_task_anchors.py <repo_root> <cases.json> --out <json>`: build graph trong bộ nhớ, gọi `TaskOverlayBuilder(document).build(case_id, text, None, sources=<byte file .py>)`, ghi cho mỗi ca: top 5 anchor (id, điểm, loại evidence), trúng file / trúng hàm. In bảng tổng.
- Cases: 20 ca = 14 dòng bảng lỗi + 6 quy tắc đặc tả (văn bản tiếng Anh trong `repair_agent/shopflow_opencode_scenario_en.md`), mỗi ca `{"id", "text", "files", "symbols"}` lấy từ `buggy_locations`/`symbol` của `bugs.json` (B13 chỉ có file vì `ALLOWED_TRANSITIONS` không phải node). Quy tắc → lỗi: tiền tệ → B02; giảm giá + coupon → B03; ship/thuế → B11, B16; giữ chỗ → B06, B08; trạng thái → B13; ngày làm việc → B07.

- [ ] **Step 1: Chạy probe trên code phần A, ghi số "Trước"**

Run: `.venv\Scripts\python.exe scripts/probe_task_anchors.py D:\kltn\shopflow-clean\shopflow repair_agent/shopflow_grounding_cases.json --out <job tmp>/probe_before.json`
Expected: bảng 20 dòng; ghi vào báo cáo.

- [ ] **Step 2: Đồng bộ code và kiểm dữ liệu R1 trong WSL**

Run: `wsl -e bash -lc "rsync -a --delete --exclude .git --exclude .venv --exclude __pycache__ /mnt/d/kltn/vgar_mcp_mvp_demo/ ~/vgar-rt1/ && ls ~/rt1/data/manifests/w10-dev-50-gold.json ~/rt1/all50.txt && ls ~/rt1/data/repositories | head -3"`
Expected: hai file tồn tại, có thư mục repo. Thiếu thì dừng, báo TV2.

- [ ] **Step 3: Chạy R1 nền (khoảng 1,5 giờ)**

Run (Bash `run_in_background`, theo dõi bằng Monitor trên file log; không dùng `nohup` vì WSL tắt khi không còn phiên):
`wsl -e bash -lc "cd ~/vgar-rt1 && PYTHONPATH=src ~/.vgar-wsl/bin/python ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/results/r1_b4_base --allow-fallback-counter --prune --resume --only ~/rt1/all50.txt 2>&1 | tee -a ~/rt1/r1_b4_base.log"`
Expected: 50/50 SUCCEEDED.

### Task 7: G2 — chữ hoa đầu câu không phải tên code

**Files:**
- Modify: `src/vgar/graph/grounding.py` (dòng 393)
- Test: `tests/test_grounding_batch4.py` (mới; graph tổng hợp dựng bằng `PythonGraphBuilder` trên repo tạm)

**Interfaces:**
- Produces: `_sentence_start(text: str, position: int) -> bool` trong `grounding.py`.

- [ ] **Step 1: Viết test hỏng**

```python
def score(finder, text, name): return next(a.score for a in finder.find_task_anchors(text).anchors if a.symbol.endswith(name))

def test_capitalized_word_at_sentence_start_is_prose(finder):
    assert score(finder, "Customer C003 cannot order.", "Customer") == 0.4

def test_capitalized_word_mid_sentence_keeps_its_score(finder):
    assert score(finder, "It returns a Customer object.", "Customer") == 0.6

def test_camel_case_at_sentence_start_stays_code(finder):
    assert score(finder, "OrderService fails here.", "OrderService") == 0.6
```

- [ ] **Step 2: Chạy, xác nhận test đầu hỏng (0.6)**

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py -q -p no:cacheprovider`

- [ ] **Step 3: Cài đặt**

`_sentence_start` đúng khi phần trước `position` (bỏ khoảng trắng) rỗng, hoặc kết thúc bằng xuống dòng, `.`, `!`, `?`, `:`, hoặc dòng hiện tại chỉ có dấu gạch đầu dòng (`-`, `*`, `•`, số + `.`) trước từ. Ở dòng 393: một từ dạng Title-case (`token[0].isupper() and token[1:].islower()`, không `_`, không `.`) mà `_sentence_start(text, match.start())` thì không tính là `code_like`.

- [ ] **Step 4: Chạy test, xác nhận đạt; chạy `tests/test_task_anchors.py tests/test_task_overlay.py`**

Expected: PASS (test cũ nào dựa vào điểm 0.6 của từ đầu câu thì sửa giá trị mong đợi, ghi lý do vào báo cáo)

### Task 8: G1 — khớp phần của tên

**Files:**
- Modify: `src/vgar/graph/grounding.py` (`TaskAnchorFinder.__init__`, `find_task_anchors`)
- Test: `tests/test_grounding_batch4.py`

**Interfaces:**
- Produces: `_name_parts(name: str) -> tuple[str, ...]` (chữ thường, tách theo `_` và chữ hoa giữa tên); evidence `AnchorEvidence("name_part", "<các từ khớp, cách nhau một dấu cách>", "issue")`.
- Hằng số (chốt trước R1, không chỉnh sau khi xem kết quả): phần hiếm = xuất hiện trong ≤ 3 symbol; idf = `log(1 + N / df)` với N = số symbol (Class/Function/Method, không Test); độ phủ = tổng idf phần khớp / tổng idf mọi phần; nhận khi có ≥ 1 phần hiếm khớp và độ phủ ≥ 0,5; điểm = `0.3 + 0.2 * coverage`; tối đa 5; luật tiền tố khi phần dài ≥ 4 ký tự; từ của đề bài = `[a-z]+` chữ thường dài ≥ 3, bỏ `_COMMON_PROSE_NAMES`.

- [ ] **Step 1: Viết test hỏng**

Graph: `discount.coupon_rate`, `discount.tier_discount_rate`, `orders.cancel_order`, `orders.ship_order`, `orders.order_total`, `orders.order_lines`, `orders.order_status`, `orders.order_id`, class `Order`.

```python
def anchors(finder, text): return {a.symbol.rsplit(".", 1)[-1]: a for a in finder.find_task_anchors(text).anchors}

def test_coupon_word_anchors_coupon_rate(finder):
    a = anchors(finder, "Orders with coupon WELCOME10 get a wrong rate.")["coupon_rate"]
    assert 0.3 <= a.score <= 0.5 and a.evidence[0].kind == "name_part"

def test_a_common_part_alone_makes_no_anchor(finder):
    assert not [a for a in finder.find_task_anchors("the order is wrong").anchors
                if a.evidence[0].kind == "name_part"]

def test_an_inflected_word_matches_by_prefix(finder):
    assert "cancel_order" in anchors(finder, "A shipped order can be cancelled.")

def test_an_exact_mention_outranks_a_name_part(finder):
    a = anchors(finder, "`ship_order` breaks when shipped")
    assert a["ship_order"].score == 0.75

def test_at_most_five_name_part_anchors(many_finder):
    assert len([a for a in many_finder.find_task_anchors(LONG_TEXT).anchors if a.evidence[0].kind == "name_part"]) <= 5

def test_failing_test_text_gets_no_name_part(finder):
    result = finder.find_task_anchors("", ["tests/test_x.py::test_coupon"])
    assert not [a for a in result.anchors if any(e.kind == "name_part" for e in a.evidence)]
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py -k "part or prefix or mention or five" -q -p no:cacheprovider`

- [ ] **Step 3: Cài đặt**

`__init__` lập chỉ mục phần tên → symbol và df. Trong `find_task_anchors`, sau vòng `_SYMBOL` của nguồn `"issue"` (trước khi dùng `prose_fallbacks`), tính điểm theo các hằng số trên và gọi `add([node], evidence, score)` cho tối đa 5 symbol điểm cao nhất (hoà: `qualified_name`, `id`).

- [ ] **Step 4: Chạy test grounding, overlay và retrieval; xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py tests/test_task_anchors.py tests/test_task_overlay.py tests/test_graph_retrieval.py -q -p no:cacheprovider`

### Task 9: G3 — thông báo lỗi được trích trong câu

**Files:**
- Modify: `src/vgar/graph/source_evidence.py` (`diagnostic_matches`, thêm `quoted_phrases`, `quoted_message_matches`; `SourceEvidence` lưu `self.tokenize`)
- Modify: `src/vgar/graph/task_overlay.py` (`build` nhận `evidence`; `_add_error_anchors` thêm loại `quoted_message`)
- Modify: `src/vgar/graph/retrieval.py` (dòng 244: `logs` gồm cả `quoted_phrases`)
- Modify: `src/vgar/graph/sqlite_service.py` (`_message_sources` → `_overlay_sources`; cache `_source_evidence`)
- Test: `tests/test_grounding_batch4.py`

**Interfaces:**
- Produces: `quoted_phrases(text: str) -> tuple[str, ...]` (cụm trong `"…"`, `“…”`, ≥ 2 từ, bỏ phần trong backtick trước khi tìm, chữ thường, gộp khoảng trắng); `quoted_message_matches(nodes, verified_sources, issue_text, *, evidence: SourceEvidence | None = None) -> dict[str, list[str]]`; `TaskOverlayBuilder.build(..., sources=None, evidence: Callable[[], SourceEvidence] | None = None)`; `SQLiteGraphService._source_evidence(graph_version: str) -> SourceEvidence` (tạo một lần mỗi version, `tokenize=_words`, `include_messages=True`).
- Luật khớp trong `diagnostic_matches(lines)`: `frag = fragment.strip(" :;,.!?'\"")`; khớp khi `frag in line` hoặc (`len(line.split()) >= 4` và `line in frag`). Điểm `quoted_message` = điểm `error_message` (0,85 / 0,5).
- `_overlay_sources`: graph có mã đã lưu → luôn trả mã đã lưu; graph cũ → giữ điều kiện hiện tại (chỉ khi có dòng có nhãn).

- [ ] **Step 1: Viết test hỏng**

Repo tổng hợp: `shop/discount.py` có `def combine_rates(a, b):` raise `ValueError(f"discount rate out of range: {a}")`; `shop/validators.py` raise `ValueError(f"invalid email: {e!r}")`.

```python
def test_quoted_message_in_prose_anchors_the_raising_function(service_and_version):
    service, version = service_and_version
    result = service.find_task_anchors('Paying always gets "discount rate out of range".', graph_version=version, task_id="t")
    top = result["anchors"][0]
    assert top["symbol"].endswith("combine_rates") and top["evidence"][0]["kind"] == "quoted_message" and top["score"] == 0.85

def test_a_two_word_generic_message_does_not_match(service_and_version):
    service, version = service_and_version
    result = service.find_task_anchors('Registering fails with "invalid email".', graph_version=version, task_id="t")
    assert not [a for a in result["anchors"] if a["evidence"][0]["kind"] == "quoted_message"]

def test_one_quoted_word_or_backticked_text_is_not_a_phrase():
    assert quoted_phrases('use coupon "WELCOME10" and `"discount rate out of range"`') == ()

def test_a_labelled_line_still_matches(service_and_version):
    service, version = service_and_version
    result = service.find_task_anchors("ValueError: discount rate out of range: 10", graph_version=version, task_id="t")
    assert result["anchors"][0]["symbol"].endswith("combine_rates")

def test_source_evidence_is_built_once_per_version(service_and_version, monkeypatch):
    service, version = service_and_version
    built = []
    real = source_evidence.SourceEvidence.__init__
    monkeypatch.setattr(source_evidence.SourceEvidence, "__init__", lambda self, *a, **k: built.append(1) or real(self, *a, **k))
    for _ in range(3):
        service.find_task_anchors('it says "discount rate out of range"', graph_version=version, task_id="t")
    assert len(built) == 1
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py -k "quoted or generic or labelled or once" -q -p no:cacheprovider`

- [ ] **Step 3: Cài đặt theo Interfaces**

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py tests/test_source_evidence.py tests/test_task_overlay_error_anchors.py tests/test_graph_retrieval.py -q -p no:cacheprovider`

### Task 10: G4 — lùi về tìm theo văn bản; đổi profile overlay

**Files:**
- Modify: `src/vgar/graph/task_overlay.py` (sau `_add_error_anchors`; profile dòng 68 `task-overlay-v13-error-anchors` → `task-overlay-v14-batch4-grounding`)
- Test: `tests/test_grounding_batch4.py`

**Interfaces:**
- Consumes: `evidence` của Task 9; khi chỉ có `sources` (harness R1), tạo `SourceEvidence(nodes, sources, _words, include_messages=True)` với `from vgar.graph.retrieval import _words` đặt trong hàm (tránh import vòng).
- Hằng số (chốt trước R1): chỉ chạy khi không còn anchor nào sau mọi luật khác; xếp Function/Method không thuộc test (`qualified_name` không bắt đầu bằng `tests.`) theo `evidence.similarity(node_id, frozenset(evidence.tokenize(issue_symbol_text(issue_text))))`; lấy tối đa 3 hàm có similarity ≥ 0,1; điểm 0,2; evidence `AnchorEvidence("text_match", "<3 từ chung nặng nhất>", "issue")`.

- [ ] **Step 1: Viết test hỏng**

Repo tổng hợp: `shop/repo.py` có `def paginate(items, page, page_size): return items[(page - 1) * page_size:page * page_size]`.

```python
def test_text_fallback_finds_a_function_by_its_body(service_and_version):
    service, version = service_and_version
    result = service.find_task_anchors("Asking for page 1 with page size 2 returns one item.", graph_version=version, task_id="t")
    assert [a["symbol"].rsplit(".", 1)[-1] for a in result["anchors"]] == ["paginate"]
    assert result["anchors"][0]["score"] == 0.2 and result["anchors"][0]["evidence"][0]["kind"] == "text_match"

def test_no_text_fallback_when_another_anchor_exists(service_and_version):
    service, version = service_and_version
    result = service.find_task_anchors("`paginate` returns one item for page size 2", graph_version=version, task_id="t")
    assert all(a["evidence"][0]["kind"] != "text_match" for a in result["anchors"])

def test_no_text_fallback_without_stored_source(legacy_service_and_version):
    service, version = legacy_service_and_version
    assert service.find_task_anchors("page size returns one item", graph_version=version, task_id="t")["anchors"] == []

def test_overlay_profile_is_v14(service_and_version):
    ...  # TaskOverlayBuilder(...).build(...) → overlay.nodes[0]["properties"]["profile"] == "task-overlay-v14-batch4-grounding"
```

- [ ] **Step 2–4: Chạy hỏng → cài đặt → chạy đạt**

Cùng lúc cài đặt, đổi docstring tool `find_task_anchors` (`graph_server.py:195`) thành dạng có `Args:` và một câu về các loại anchor: tên/đường dẫn/route được nhắc, phần của tên (`name_part`), thông báo lỗi có nhãn hoặc được trích (`error_message`, `quoted_message`), và `text_match` khi không tìm được gì khác (điểm thấp, nên kiểm lại).

Run: `.venv\Scripts\python.exe -m pytest tests/test_grounding_batch4.py tests/test_task_overlay.py tests/test_task_overlay_error_anchors.py tests/mcp_server -q -p no:cacheprovider`

### Task 11: Đo phần B, cổng chấp nhận, bàn giao

**Files:**
- Modify: `docs/status/tv2_batch4_grounding_2026-11-23.md` (phần "Sau", R1, kết luận)
- Modify: `docs/superpowers/specs/2026-11-23-tv2-agent-loop-fixes-design.md` (Trạng thái)

- [ ] **Step 1: Toàn bộ test**

Run: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`
Expected: chỉ các lỗi đã biết.

- [ ] **Step 2: Probe ShopFlow "Sau"**

Run lại lệnh của Task 6 Step 1 với `--out <job tmp>/probe_after.json`; ghi bảng trước/sau (trúng file, trúng hàm trong top 5) vào báo cáo.

- [ ] **Step 3: R1 sau phần B**

Đồng bộ code như Task 6 Step 2, chạy như Task 6 Step 3 với `--out ~/rt1/results/r1_b4_grounding` và log `~/rt1/r1_b4_grounding.log`. So theo cặp:
`wsl -e bash -lc "cd ~/vgar-rt1 && python3 ablation_matrix/compare_runs.py ~/rt1/results r1_b4_base r1_b4_grounding"`
Expected: bảng chênh lệch có CI95 cho từng cấu hình.

- [ ] **Step 4: Áp cổng D2**

Chấp nhận khi ở cấu hình `task_trace` và RT-1 không chỉ số nào có CI95 nằm hẳn dưới 0. Không đạt: ghi chỉ số và task gây giảm vào báo cáo, dừng và hỏi TV2 (không chỉnh hằng số rồi chạy lại cho tới khi đạt).

- [ ] **Step 5: Bàn giao cho TV2 commit phần B**

Đưa danh sách file của Task 6–11 và lệnh: `git add <files>; git commit -m "feat(graph): grounding uses name parts, quoted error messages and a source-text fallback; sentence-initial capitals are prose (TV2 batch 4 part B)"`.
