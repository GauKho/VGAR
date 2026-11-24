# Đợt 6: SCIP mặc định, LSP dự phòng trong graph MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server `vgar-graph` dùng resolver SCIP → LSP → tĩnh → MAY_CALL mặc định, và các tool kiểm patch, thư mục chạy,
`changed_files` đúng khi có resolver này, để một lượt OpenCode thật có `layers.scip = ready`.

**Architecture:** Builder đã có thứ tự SCIP → LSP → tĩnh khi có cả hai cấu hình (`builder.py:247-258`, `1073-1093`,
`1196-1256`). Plan thêm: (1) giá trị mặc định đặt ở nhánh `__main__` của server; (2) cờ `fallback_only` trên `LspConfig` để LSP
chỉ chạy khi SCIP không `ready`; (3) `verify_patch` dựng ứng viên bằng đúng resolver graph đã dùng; (4) thư mục chạy cạnh
database có giới hạn; (5) `changed_files` tính bằng hash file khi phải dựng lại đầy đủ.

**Tech Stack:** Python 3.11, tree-sitter, scip-python 0.6.6 và pyright 1.1.414 qua node, SQLite, MCP SDK 2.2.0, pytest.

**Spec:** `docs/superpowers/specs/2026-11-24-tv2-scip-in-served-graph-design.md` (bản nháp 2, TV2 duyệt 24/11/2026).

## Global Constraints

- Không `git commit`: TV2 tự commit. Bước cuối mỗi task là liệt kê file đã đổi.
- Chạy test: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <đường dẫn>` trong `D:\kltn\vgar_mcp_mvp_demo`.
- Luật server MCP: không in ra stdout; `logger = logging.getLogger(__name__)`; hàm public có docstring với mục `Args:`.
- Runtime đã ghim (đã cài trên máy này): `layer_config.SCIP_RUNTIME`, `layer_config.LSP_RUNTIME`. Test cần runtime thật dùng
  marker `needs_resolvers` của `tests/resolver_fixture.py` (Task 2) và **bỏ qua** khi thiếu runtime hoặc `node`.
  `tests/conftest.py` đã đưa `tests/` vào `sys.path`, nên mọi file test import được `from resolver_fixture import …`.
- Không đổi: retrieval, `ContextPayload`, hình dạng output tool (đợt 5), `IncrementalGraphBuilder`, hành vi của script đo
  (`build_graph.py`, R1, G1: khi được truyền cả SCIP lẫn LSP, hai tool vẫn cùng chạy như hiện nay).
- Giá trị và chuỗi cố định (chép đúng):
  - biến tắt: `VGAR_SCIP=off`, `VGAR_LSP=off` (so sánh không phân biệt hoa thường, sau `strip()`);
  - thư mục chạy: `<thư mục chứa VGAR_GRAPH_DATABASE>/scip-runs`, `<…>/lsp-runs`; giữ `3` thư mục chạy mới nhất;
  - trạng thái LSP khi SCIP `ready`: report `{"status": "skipped", "reason": "SCIP ready"}`; `layers.lsp` = `skipped`;
  - reason của `verify` khi resolver ứng viên không chạy được: `f"CANDIDATE_RESOLVER_UNAVAILABLE: {resolver}: {lý do}"`,
    với `resolver` là `scip` hoặc `lsp`; lý do khi server không cấu hình resolver đó: `"not configured"`.

### Quyết định của plan (chi tiết hoá spec)

1. Spec §4.2 ghi `layers.scip` = `fallback` khi SCIP lỗi. Code hiện trả `failed` cho mọi layer không chạy được
   (`layer_config._status`, đã có test). Plan giữ `failed` (không đổi hợp đồng), chỉ thêm `skipped`.
2. Cờ "LSP là dự phòng" đặt trên `LspConfig` (`fallback_only: bool = False`), không đặt trên `LayerConfigs`:
   `builder_kwargs()` và các script dùng nó không phải đổi.
3. Khi SCIP lỗi và LSP chạy, `resolver_report` giữ `requested`/`status`/`reason` của SCIP (để `layers.scip` báo `failed` kèm lý
   do) và chỉ đổi `active` theo LSP (`"lsp"` hoặc `"static"`). `verify` đọc `active`.
4. LSP report `not_needed` (không có lời gọi thiếu hoặc yếu) cũng hiện `layers.lsp` = `skipped` (hiện đang thành `failed`).

## Review Focus

- `node` không có trên máy chạy server: cả SCIP và LSP phải báo `failed` kèm lý do, graph vẫn dựng bằng resolver tĩnh (test ở Task 2).
- `verify_patch` gọi trực tiếp không truyền `layers` trên graph dựng bằng SCIP: phải NOT_RUN `… scip: not configured`, không
  ERROR, không so chéo với graph tĩnh (test ở Task 3).
- `VGAR_GRAPH_DATABASE` thiếu hoặc tương đối khi gọi `layer_configs` (test, script): không lỗi, giữ thư mục mặc định cũ (test ở Task 4).
- LSP không có gì để hỏi (`not_needed`) khi SCIP lỗi: `layers.lsp` là `skipped`, không phải `failed` (test ở Task 2).
- Server khởi động bằng `python -m` mà host đã đặt sẵn `VGAR_SCIP_ENTRY` riêng: giữ giá trị của host, không ghi đè (test ở Task 1).

---

### Task 1: Bật SCIP và LSP mặc định cho tiến trình server

**Files:**
- Modify: `src/vgar/graph/layer_config.py`
- Modify: `src/vgar/mcp/servers/graph_server.py` (nhánh `__main__` dòng 42–43; `main()` dòng 669–681)
- Modify: `README.md` (bảng biến môi trường quanh dòng 150–160; mục cài đặt)
- Test: `tests/test_layer_config.py`

**Interfaces:**
- Produces: `default_resolver_entries(env: Mapping[str, str], *, scip_runtime: Path = SCIP_RUNTIME, lsp_runtime: Path = LSP_RUNTIME) -> dict[str, str]`
  trong `layer_config.py`: trả các biến cần thêm (`VGAR_SCIP_ENTRY`, `VGAR_LSP_ENTRY`), không sửa `env`.

- [ ] **Step 1: Viết test** (cuối `tests/test_layer_config.py`)

```python
@pytest.fixture
def runtimes(tmp_path):
    scip, lsp = tmp_path / "scip.js", tmp_path / "lsp.js"
    scip.write_text("", encoding="utf-8"); lsp.write_text("", encoding="utf-8")
    return scip, lsp

def test_default_entries_point_to_installed_runtimes(runtimes):
    scip, lsp = runtimes
    assert default_resolver_entries({}, scip_runtime=scip, lsp_runtime=lsp) == {
        "VGAR_SCIP_ENTRY": str(scip.resolve()), "VGAR_LSP_ENTRY": str(lsp.resolve())}

@pytest.mark.parametrize("name,entry", [("VGAR_SCIP", "VGAR_SCIP_ENTRY"), ("VGAR_LSP", "VGAR_LSP_ENTRY")])
def test_off_switch_leaves_that_resolver_unset(runtimes, name, entry):
    scip, lsp = runtimes
    assert entry not in default_resolver_entries({name: " OFF "}, scip_runtime=scip, lsp_runtime=lsp)

def test_host_entry_is_kept(runtimes, tmp_path):
    scip, lsp = runtimes
    entries = default_resolver_entries({"VGAR_SCIP_ENTRY": str(tmp_path / "mine.js")}, scip_runtime=scip, lsp_runtime=lsp)
    assert "VGAR_SCIP_ENTRY" not in entries and entries["VGAR_LSP_ENTRY"] == str(lsp.resolve())

def test_missing_runtime_sets_nothing(tmp_path):
    assert default_resolver_entries({}, scip_runtime=tmp_path / "no.js", lsp_runtime=tmp_path / "no2.js") == {}
```

- [ ] **Step 2: Chạy, thấy FAIL** — `ImportError: cannot import name 'default_resolver_entries'`.

- [ ] **Step 3: Cài đặt**
  - `default_resolver_entries` theo bốn test trên (đường dẫn trả về là `str(path.resolve())`).
  - `graph_server.py`, nhánh `__main__`: `os.environ.update(default_resolver_entries(os.environ))` **trước**
    `require_host_config("graph")` (để host_config kiểm luôn đường dẫn). Import module (test) không qua nhánh này.
  - `main()`: thêm vào dòng log INFO khởi động `scip=%s lsp=%s`, giá trị là `VGAR_SCIP_ENTRY` / `VGAR_LSP_ENTRY` hoặc `off`.
  - `README.md`: bảng biến môi trường thêm `VGAR_SCIP_ENTRY`, `VGAR_LSP_ENTRY` (mặc định: runtime đã ghim nếu đã cài),
    `VGAR_SCIP=off`, `VGAR_LSP=off`; mục cài đặt thêm hai lệnh
    `powershell -ExecutionPolicy Bypass -File scripts/install_scip_runtime.ps1` và `… install_lsp_runtime.ps1`, kèm câu:
    thứ tự resolver SCIP → LSP (chỉ khi SCIP lỗi) → tĩnh; thiếu runtime hoặc node thì dùng resolver tĩnh, `layers` ghi lý do.

- [ ] **Step 4: Chạy, thấy PASS** — `tests/test_layer_config.py`, rồi `tests/mcp_server/test_tv2_host_config.py tests/mcp_server/test_tv2_no_stdout.py` (nếu tên file khác, chạy `tests/mcp_server -k "host_config or stdout"`).

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/layer_config.py`, `src/vgar/mcp/servers/graph_server.py`, `README.md`, `tests/test_layer_config.py`.

---

### Task 2: LSP chỉ chạy khi SCIP không `ready`

**Files:**
- Modify: `src/vgar/graph/lsp_resolver.py` (`LspConfig`, dòng 29–45)
- Modify: `src/vgar/graph/builder.py` (`build`, dòng 237–261)
- Modify: `src/vgar/graph/layer_config.py` (`layer_configs`, `_status`, `layer_summary`)
- Create: `tests/resolver_fixture.py` (helper, không phải file test), `tests/test_resolver_chain.py`
- Test: `tests/test_layer_config.py`

**Interfaces:**
- Consumes: không có.
- Produces: `LspConfig.fallback_only: bool = False`; `layer_configs(env)` đặt `fallback_only=True` khi cả SCIP lẫn LSP được
  cấu hình; `layer_summary` có trạng thái `skipped`. `tests/resolver_fixture.py` có `needs_resolvers` (marker) và `CHAIN`
  (cây file có lời gọi `r.check()` mà resolver tĩnh không xác định chắc được); Task 3, 4, 6 import từ đây.

- [ ] **Step 1: Viết test**

`tests/resolver_fixture.py` chứa `needs_resolvers` và `CHAIN`; `tests/test_resolver_chain.py` import chúng và chứa phần còn lại:

```python
# tests/resolver_fixture.py
needs_resolvers = pytest.mark.skipif(not (SCIP_RUNTIME.exists() and LSP_RUNTIME.exists() and shutil.which("node")),
                                     reason="SCIP/LSP runtimes or node not installed")
CHAIN = {
    "shop/__init__.py": "",
    "shop/repo.py": "class Repo:\n    def check(self):\n        return 1\n",
    "shop/service.py": "from shop.repo import Repo\n\n\ndef make():\n    return Repo()\n\n\n"
                       "def run():\n    r = make()\n    return r.check()\n",
}

# tests/test_resolver_chain.py
def _layers(tmp_path, **env):   # layer_configs from absolute paths, database in tmp_path
    return layer_configs({"VGAR_GRAPH_DATABASE": str(tmp_path / "g.db"), **env})

def _build(tmp_path, layers):
    root = write_tree(tmp_path / "repo", CHAIN)    # write_tree from git_fixture
    document = PythonGraphBuilder(repo_key="t/chain", repository_revision="rev", **layers.builder_kwargs()).build(root)
    return document, layer_summary(document, layers)

def _rules(document):
    return {e["provenance"]["rule_id"] for e in document["edges"] if e["type"] == "CALLS"}

@needs_resolvers
def test_scip_ready_skips_lsp(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    assert layers.lsp.fallback_only is True
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "ready" and summary["lsp"] == {"status": "skipped", "reason": "SCIP ready"}
    assert "python.call.scip.resolve.v1" in _rules(document) and "python.call.lsp.definition.v1" not in _rules(document)
    assert document["statistics"]["resolver"]["active"] == "scip"

@needs_resolvers
def test_broken_scip_falls_back_to_lsp(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(tmp_path / "missing.js"), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["scip"]["reason"]
    assert summary["lsp"]["status"] == "ready" and document["statistics"]["resolver"]["active"] == "lsp"
    assert "python.call.lsp.definition.v1" in _rules(document)

@needs_resolvers
def test_both_broken_use_static_and_keep_may_call(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(tmp_path / "a.js"), VGAR_LSP_ENTRY=str(tmp_path / "b.js"))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["lsp"]["status"] == "failed"
    assert document["statistics"]["resolver"]["active"] == "static"
    assert any(e["type"] == "MAY_CALL" for e in document["edges"])

def test_missing_node_fails_both_and_builds_static(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME),
                     VGAR_NODE=str(tmp_path / "no-node.exe"))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["lsp"]["status"] == "failed"
    assert document["statistics"]["resolver"]["active"] == "static" and document["nodes"]
```

Trong `tests/test_layer_config.py`:

```python
@pytest.mark.parametrize("status", ["skipped", "not_needed"])
def test_lsp_with_nothing_to_do_is_skipped(status):
    document = {"statistics": {"resolver": {"requested": "scip", "status": "fallback", "reason": "x",
                                            "lsp": {"status": status, "reason": "why"}}}}
    summary = layer_summary(document, LayerConfigs(scip=object(), lsp=object()))
    assert summary["lsp"] == {"status": "skipped", "reason": "why"}

def test_only_lsp_is_not_a_fallback(tmp_path):
    assert layer_configs({"VGAR_LSP_ENTRY": str(tmp_path / "l.js")}).lsp.fallback_only is False
```

- [ ] **Step 2: Chạy, thấy FAIL** — `AttributeError: 'LspConfig' object has no attribute 'fallback_only'`; `test_scip_ready_skips_lsp` thấy LSP vẫn chạy.

- [ ] **Step 3: Cài đặt**
  - `LspConfig.fallback_only: bool = False`.
  - `layer_configs`: khi cả `scip` và `lsp` khác `None`, dựng `lsp` với `fallback_only=True` (`dataclasses.replace`).
  - `PythonGraphBuilder.build`: sau khối dựng `ScipResolver` (dòng 237–246), nếu `self.lsp_config` có `fallback_only` và
    `self.scip_resolver is not None`: ghi `self.resolver_report["lsp"] = {"status": "skipped", "reason": "SCIP ready"}`, đặt
    `self.lsp_config = None`, tính lại `self.graph_version` và cập nhật `graph_version` của mọi node/edge (cùng cách dòng
    258–260 đang làm). Nếu `fallback_only` và SCIP không `ready`: chạy khối LSP như hiện nay; sau đó chỉ đổi
    `self.resolver_report["active"] = lsp_report["active"]` (giữ `requested`/`status`/`reason` của SCIP).
  - `_status`: report `status` là `skipped` hoặc `not_needed` → `{"status": "skipped", "reason": report.get("reason")}`.

- [ ] **Step 4: Chạy, thấy PASS** — `tests/test_resolver_chain.py tests/test_layer_config.py`, rồi `tests/test_scip_enrichment.py tests/test_lsp_enrichment.py tests/test_live_build_layers.py tests/test_may_call.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/lsp_resolver.py`, `src/vgar/graph/builder.py`, `src/vgar/graph/layer_config.py`, `tests/resolver_fixture.py`, `tests/test_resolver_chain.py`, `tests/test_layer_config.py`.

---

### Task 3: `verify_patch_graph_constraints` dùng đúng resolver của graph

**Files:**
- Modify: `src/vgar/repair/patch_evidence.py` (`verify_patch`, dòng 135–216)
- Modify: `src/vgar/mcp/servers/graph_server.py` (`_verified`, dòng 399–408)
- Modify: `docs/mcp_server/contract.md` (dòng `verify_patch_graph_constraints` của bảng §3)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: `layer_configs`, `LayerConfigs`; `needs_resolvers`, `CHAIN` từ `tests/resolver_fixture.py` (Task 2).
- Produces: `verify_patch(service, diff, *, graph_version, source_roots=("src",), layers: LayerConfigs | None = None) -> dict[str, Any]`.

- [ ] **Step 1: Viết test** (cuối `tests/test_patch_checks_from_snapshot.py`, mục `# --- Batch 6: verify on SCIP/LSP graphs`)

`_build` nhận thêm `**builder_kwargs` và chuyển cho `PythonGraphBuilder`. Helper `_resolver_env(monkeypatch, tmp_path, **env)`
đặt `VGAR_GRAPH_DATABASE`, `VGAR_SCIP_ENTRY`, `VGAR_LSP_ENTRY` qua `monkeypatch.setenv` và trả `layer_configs(os.environ)`.

```python
@needs_resolvers
@pytest.mark.parametrize("active", ["scip", "lsp"])
def test_verify_passes_on_a_resolver_graph(tmp_path, monkeypatch, active):
    scip = str(SCIP_RUNTIME) if active == "scip" else str(tmp_path / "missing.js")
    layers = _resolver_env(monkeypatch, tmp_path, VGAR_SCIP_ENTRY=scip, VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    service, version, root = _build(tmp_path, {**SHOP, **CHAIN}, **layers.builder_kwargs())   # CHAIN: a call LSP must answer
    assert service._document(version)["statistics"]["resolver"]["active"] == active
    _serve(tmp_path, monkeypatch, service)
    _edit_pricing(root)
    response = verify()
    assert response["status"] == "PASS", response

@needs_resolvers
def test_verify_on_scip_graph_names_the_unsupported_constant(tmp_path, monkeypatch):
    layers = _resolver_env(monkeypatch, tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    service, version, root = _build(tmp_path, {**SHOP, "shop/order.py": ORDER}, **layers.builder_kwargs())
    _serve(tmp_path, monkeypatch, service)
    assert verify()["data"]["reasons"] == ["NO_CHANGES"]
    (root / "shop/order.py").write_text(ORDER.replace("[Status.PAID]", "[Status.PAID, Status.NEW]"), encoding="utf-8", newline="")
    data = verify()["data"]
    assert data["status"] == "NOT_RUN" and data["unsupported_changes"][0]["symbol"] == "ALLOWED"
    assert not any("BUILDER_OPTIONS_OR_SOURCE_DIFFER" in r for r in data["reasons"])

@needs_resolvers
def test_candidate_resolver_failure_is_not_run(tmp_path, monkeypatch):
    layers = _resolver_env(monkeypatch, tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    service, version, root = _build(tmp_path, **layers.builder_kwargs())
    _serve(tmp_path, monkeypatch, service)
    monkeypatch.setenv("VGAR_SCIP_ENTRY", str(tmp_path / "gone.js"))
    _edit_pricing(root)
    data = verify()["data"]
    assert data["status"] == "NOT_RUN" and data["reasons"][0].startswith("CANDIDATE_RESOLVER_UNAVAILABLE: scip: ")

@needs_resolvers
def test_verify_patch_without_layers_on_scip_graph_is_not_run(tmp_path, monkeypatch):
    layers = _resolver_env(monkeypatch, tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    service, version, root = _build(tmp_path, **layers.builder_kwargs())
    result = verify_patch(service, PRICING_FIX, graph_version=version)
    assert result["status"] == "NOT_RUN" and result["reasons"] == ["CANDIDATE_RESOLVER_UNAVAILABLE: scip: not configured"]
```

- [ ] **Step 2: Chạy, thấy FAIL** — `test_verify_passes_on_a_resolver_graph` thấy `ERROR` với `BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT`.

- [ ] **Step 3: Cài đặt**
  - `verify_patch`: `active = document["statistics"]["resolver"]["active"]` (thiếu khoá → `"static"`).
    - Chỉ tính lại và so `graph_version` khi graph **không** có mã nguồn lưu (`sources is None`), như hiện nay.
    - Resolver cho ứng viên: `active == "scip"` → `{"scip": layers.scip}`; `"lsp"` → `{"lsp": dataclasses.replace(layers.lsp, fallback_only=False)}`;
      ngược lại `{}`. Cấu hình cần mà `layers` thiếu (hoặc `layers is None`) → trả ngay `_result("NOT_RUN",
      ["CANDIDATE_RESOLVER_UNAVAILABLE: <active>: not configured"], {}, graph_version, diff)`.
    - Sau `candidate = builder.build(copy)`: nếu `candidate["statistics"]["resolver"]["active"] != active` → `_result("NOT_RUN",
      [f"CANDIDATE_RESOLVER_UNAVAILABLE: {active}: {lý do}"], …)`; lý do lấy từ `resolver["reason"]` (SCIP) hoặc
      `resolver["lsp"]["reason"]` (LSP).
    - Docstring `Args:` thêm `layers`.
  - `graph_server._verified`: truyền `layers=layer_configs(os.environ)` (import tại chỗ như `_live`).
  - `contract.md` §3, dòng `verify_patch_graph_constraints`: thêm câu "ứng viên dựng bằng đúng resolver graph đã dùng
    (SCIP/LSP/tĩnh); resolver đó không chạy được → NOT_RUN `CANDIDATE_RESOLVER_UNAVAILABLE`".

- [ ] **Step 4: Chạy, thấy PASS** — `tests/test_patch_checks_from_snapshot.py`, rồi `tests/test_tv2_patch_evidence.py tests/test_agent_loop_fixes.py tests/test_graph_tools_agent_feedback.py tests/mcp_server/test_tv2_no_stdout.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/repair/patch_evidence.py`, `src/vgar/mcp/servers/graph_server.py`, `docs/mcp_server/contract.md`, `tests/test_patch_checks_from_snapshot.py`.

---

### Task 4: Thư mục chạy SCIP/LSP cạnh database, giữ 3 lần mới nhất

**Files:**
- Modify: `src/vgar/graph/layer_config.py` (`layer_configs`; hàm mới `prune_runs`)
- Modify: `src/vgar/graph/live_build.py` (`_work`, sau khi dựng)
- Modify: `src/vgar/repair/patch_evidence.py` (`verify_patch`, sau khi dựng ứng viên)
- Test: `tests/test_layer_config.py`, `tests/test_resolver_chain.py`

**Interfaces:**
- Consumes: `verify_patch(..., layers=...)` (Task 3).
- Produces: `prune_runs(directory: Path, keep: int = 3) -> None` trong `layer_config.py`: xoá các thư mục con cũ nhất (theo
  `st_mtime`), giữ `keep` thư mục mới nhất; thư mục không tồn tại thì không làm gì.

- [ ] **Step 1: Viết test**

Trong `tests/test_layer_config.py`:

```python
def test_run_directories_sit_next_to_the_database(tmp_path):
    layers = layer_configs({"VGAR_GRAPH_DATABASE": str(tmp_path / "data" / "g.db"),
                            "VGAR_SCIP_ENTRY": str(tmp_path / "s.js"), "VGAR_LSP_ENTRY": str(tmp_path / "l.js")})
    assert Path(layers.scip.output_directory) == tmp_path / "data" / "scip-runs"
    assert Path(layers.lsp.output_directory) == tmp_path / "data" / "lsp-runs"

@pytest.mark.parametrize("database", [None, "relative/g.db"])
def test_without_an_absolute_database_the_old_directories_stay(tmp_path, database):
    env = {"VGAR_SCIP_ENTRY": str(tmp_path / "s.js"), **({"VGAR_GRAPH_DATABASE": database} if database else {})}
    assert str(layer_configs(env).scip.output_directory) == "artifacts/m1/w7-w8/scip"

def test_prune_runs_keeps_the_three_newest(tmp_path):
    for index in range(5):
        run = tmp_path / f"run{index}"; run.mkdir(); (run / "index.scip").write_bytes(b"x")
        os.utime(run, (1_000 + index, 1_000 + index))
    prune_runs(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run2", "run3", "run4"]
    prune_runs(tmp_path / "missing")   # no error
```

Trong `tests/test_resolver_chain.py`:

```python
@needs_resolvers
def test_served_builds_write_runs_next_to_the_database_only(tmp_path, monkeypatch):
    root = write_tree(tmp_path / "repo", CHAIN)
    cwd = tmp_path / "cwd"; cwd.mkdir(); monkeypatch.chdir(cwd)
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    live = LiveGraphBuilder(root, tmp_path / "g.db", layers=layers)
    for index in range(4):
        (root / "shop/repo.py").write_text(f"class Repo:\n    def check(self):\n        return {index}\n", encoding="utf-8")
        live.run()
    assert len(list((tmp_path / "scip-runs").iterdir())) == 3
    assert not (cwd / "artifacts").exists() and not (root / "artifacts").exists()
```

- [ ] **Step 2: Chạy, thấy FAIL** — `ImportError: cannot import name 'prune_runs'`; đường dẫn vẫn là `artifacts/m1/w7-w8/scip`.

- [ ] **Step 3: Cài đặt**
  - `layer_configs`: `VGAR_GRAPH_DATABASE` có và là đường dẫn tuyệt đối → `output_directory` của SCIP và LSP như Global
    Constraints (`dataclasses.replace`); ngược lại giữ nguyên (không ném lỗi).
  - `prune_runs` theo interface.
  - `LiveGraphBuilder._work`: sau khi dựng xong (cả nhánh lỗi), gọi `prune_runs` cho `output_directory` của
    `self.layers.scip` / `self.layers.lsp` khi khác `None`.
  - `verify_patch`: sau khi dựng ứng viên bằng SCIP hoặc LSP, gọi `prune_runs` cho thư mục của resolver đó.

- [ ] **Step 4: Chạy, thấy PASS** — `tests/test_layer_config.py tests/test_resolver_chain.py tests/test_live_build_layers.py tests/test_patch_checks_from_snapshot.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/layer_config.py`, `src/vgar/graph/live_build.py`, `src/vgar/repair/patch_evidence.py`, `tests/test_layer_config.py`, `tests/test_resolver_chain.py`.

---

### Task 5: `changed_files` khi phải dựng lại đầy đủ

**Files:**
- Modify: `src/vgar/graph/live_build.py` (`__init__`, `_compute` dòng 171–181, docstring `run`)
- Modify: `src/vgar/mcp/servers/graph_server.py` (docstring `build_or_update_graph`)
- Modify: `docs/mcp_server/contract.md` (dòng `build_or_update_graph` của bảng §3)
- Test: `tests/test_live_build_layers.py`

**Interfaces:**
- Consumes: không có.
- Produces: kết quả `LiveGraphBuilder.run()` có `changed_files` đúng ở mọi `mode`.

- [ ] **Step 1: Viết test** (cuối `tests/test_live_build_layers.py`; tsg trỏ tới file không tồn tại để bật nhánh có layer mà không cần tool thật)

```python
def test_full_rebuild_with_layers_lists_changed_files(tmp_path):
    root = write_tree(tmp_path / "plain", FILES)
    missing = TsgConfig(executable=tmp_path / "no-such-tsg", tree_sitter_dir=tmp_path)
    live = LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=missing))
    assert live.run()["changed_files"] == []
    (root / "pkg/mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nX = 1\n")
    edited = live.run()
    assert edited["mode"] == "cold" and edited["changed_files"] == ["pkg/mod.py"]
    (root / "pkg/new.py").write_text("Y = 2\n", encoding="utf-8")
    (root / "pkg/mod.py").unlink()
    assert live.run()["changed_files"] == ["pkg/mod.py", "pkg/new.py"]
```

- [ ] **Step 2: Chạy, thấy FAIL** — `[] == ['pkg/mod.py']`.

- [ ] **Step 3: Cài đặt**
  - `LiveGraphBuilder` giữ `self._file_hashes: dict[str, str] | None = None` (path → `content_hash` của các File node của graph
    vừa công bố).
  - Nhánh có layer trong `_compute`: `changed` = các path có hash khác, thêm hoặc mất so với `self._file_hashes` (sắp xếp);
    `[]` khi `self._file_hashes is None`. Cập nhật `self._file_hashes` sau mỗi lần dựng ở cả hai nhánh.
  - Docstring `run` và `build_or_update_graph`: khi có layer (mặc định có SCIP), mọi lần dựng là dựng lại đầy đủ (`mode`
    `cold`), `changed_files` vẫn liệt kê file đổi; `layers` cho biết resolver nào đã chạy (`ready`, `skipped`, `failed` kèm
    lý do, `off`).
  - `contract.md` §3, dòng `build_or_update_graph`: thứ tự resolver SCIP → LSP → tĩnh, ý nghĩa `layers`, `changed_files`.

- [ ] **Step 4: Chạy, thấy PASS** — `tests/test_live_build_layers.py tests/mcp_server/test_tv2_build_tool.py tests/test_agent_loop_fixes.py`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/live_build.py`, `src/vgar/mcp/servers/graph_server.py`, `docs/mcp_server/contract.md`, `tests/test_live_build_layers.py`.

---

### Task 6: Kiểm tra tích hợp, chạy lại spike, toàn bộ suite

**Files:**
- Create: `tests/mcp_server/test_tv2_resolver_default_stdio.py`
- Create (kết quả): `docs/status/tv2_scip_in_served_graph_run_2026-11-24.md`

**Interfaces:**
- Consumes: mọi thứ của Task 1–5; `needs_resolvers`, `CHAIN` từ `tests/resolver_fixture.py` (Task 2).

- [ ] **Step 1: Viết test stdio** — khởi động `python -m vgar.mcp.servers.graph_server` qua `mcp.Client` + `StdioServerParameters`
  (cách làm của `tests/mcp_server/test_core_wire.py`), env chỉ có `PYTHONPATH`, `PYTHONUTF8=1`, `VGAR_GRAPH_BACKEND=sqlite`,
  `VGAR_REPOSITORY_ROOT` (cây `CHAIN` của Task 2), `VGAR_GRAPH_DATABASE`, `VGAR_MCP_AUDIT_LOG` (không có biến SCIP/LSP), `PATH`
  của máy (để có node):

```python
@needs_resolvers
def test_server_started_by_a_host_uses_scip_by_default(tmp_path):
    data = _build_over_stdio(tmp_path)          # call_tool("build_or_update_graph", {"repo_path": root}) -> structured data
    assert data["layers"]["scip"]["status"] == "ready" and data["layers"]["lsp"]["status"] == "skipped"
    assert not (tmp_path / "repo" / "artifacts").exists() and (tmp_path / "data" / "scip-runs").is_dir()

@needs_resolvers
def test_host_can_turn_scip_off(tmp_path):
    data = _build_over_stdio(tmp_path, VGAR_SCIP="off")
    assert data["layers"]["scip"]["status"] == "off" and data["layers"]["lsp"]["status"] == "ready"
```

- [ ] **Step 2: Chạy, thấy PASS** — `tests/mcp_server/test_tv2_resolver_default_stdio.py` (Task 1–5 đã xong nên test pass ngay; nếu FAIL là lỗi tích hợp, sửa ở task tương ứng).

- [ ] **Step 3: Chạy lại spike** trong `D:\kltn\vgar-work\spikes\` (đặt `VGAR_SCIP_ENTRY`, `VGAR_LSP_ENTRY` như server mặc định):
  `scip_mcp_spike.py --scip on`, `scip_checks_spike.py on`, `replay_shopflow_session.py` (nguồn: `git archive 68c96af` của
  `D:\kltn\shopflow-clean1\shopflow`), và một lần với `VGAR_SCIP_ENTRY` trỏ tới file không tồn tại. Đạt khi: `verify` sửa thuế
  PASS; `verify` lỗi 5 NOT_RUN nêu `ALLOWED_TRANSITIONS`; replay đạt; `update` có `changed_files == ["shopflow/services/pricing.py"]`;
  thư mục `spikes` không có thư mục `artifacts` mới. Ghi bảng kết quả (thời gian dựng, `layers`, trạng thái verify, CALLS/MAY_CALL)
  vào `docs/status/tv2_scip_in_served_graph_run_2026-11-24.md`.

- [ ] **Step 4: Chạy toàn bộ suite** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`. Kỳ vọng: pass hết trừ 7 lỗi
  Docker/harness đã biết (JARVIS 4, Joern 2, `test_official_harness` 1). Test khác fail: dừng, báo TV2 kèm output.

- [ ] **Step 5: Chuẩn bị lượt OpenCode cho TV2** — trong file kết quả, ghi: `opencode.json` không cần đổi (SCIP mặc định); kiểm
  trước khi chạy là `node --version` chạy được và hai runtime đã cài; sau lượt chạy cần đo `layers`, thời gian mỗi lần dựng, trạng
  thái `verify`, file lạ trong repo, test ẩn, token (spec §5.4).

- [ ] **Step 6: Liệt kê file** — `tests/mcp_server/test_tv2_resolver_default_stdio.py`, `docs/status/tv2_scip_in_served_graph_run_2026-11-24.md`.
