# Đợt 3: kiểm patch trên code của graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Các tool kiểm patch chạy trên đúng code mà graph đã dựng (lưu trong database), và không cần agent truyền diff.

**Architecture:** Khi dựng graph, lưu byte từng file `.py` vào bảng `sources` (khóa ngoại cascade theo version). Mỗi lần
kiểm, dựng code đó ra thư mục tạm và đưa thư mục này làm gốc cho các hàm hiện có (`impact`, `patch._bind`, `verify_patch`,
`run_patch_tests` không đổi thuật toán). Khi `diff` trống, server sinh diff kiểu `git diff` giữa code đã lưu và thư mục làm
việc, theo đúng ngữ nghĩa của `parse_unified_diff` + `_bind` (bỏ qua CRLF/LF, giữ dấu không-newline-cuối-file).

**Tech Stack:** Python 3.11, SQLite (`sqlite3`), `difflib`, MCP SDK 2.2 (FastMCP), pytest.

**Spec:** `docs/superpowers/specs/2026-11-22-tv2-patch-checks-from-snapshot-design.md` (đã duyệt 22/11/2026).

## Global Constraints

- Không `git commit`: TV2 tự commit. Bước cuối mỗi task là liệt kê file đã đổi.
- Chạy test bằng `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <đường dẫn>` trong `D:\kltn\vgar_mcp_mvp_demo`.
- Luật server MCP: không in ra stdout; `logger = logging.getLogger(__name__)`; hàm public có docstring với mục `Args:`.
- Không đổi: contract của TV1 (`DiffRequest`, `core_tools`, `storage_capabilities`, `graph_jobs`), `ImpactReport`,
  `src/vgar/graph/impact.py`, `src/vgar/repair/patch.py`, `rank_patch_candidates`.
- Giới hạn diff lấy từ giá trị mặc định của `PatchPolicy` (`max_files`, `max_changed_lines`), không viết lại số.
- Chuỗi cố định (chép đúng):
  - `NO_SOURCE_COPY_HINT = "this graph stores no copy of its source: rebuild it with build_or_update_graph to check edited files without stashing"`
  - mục `not_checked`: `"new file: <path>"`, `"deleted file: <path>"`, `"line endings only: <path>"`, `"not UTF-8: <path>"`
  - lý do `verify`/test: `"NO_CHANGES"`, `"NOT_CHECKED: " + <mục not_checked>`
  - lỗi dựng graph: `"file changed during the build: <path>; call build_or_update_graph again"`
- `checked_diff = {"source": "worktree" | "argument", "files": [...], "sha256": "sha256:<hex>", "diff": <chuỗi nếu ≤ 8192 byte UTF-8, ngược lại None>, "not_checked": [...]}`, thêm ở tầng tool.

## Review Focus

- Thư mục builder bỏ qua (`.venv`, `build`, `node_modules`…) có file `.py`: dựng code gốc không được xoá chúng (test ở Task 3).
- File `.py` không phải UTF-8 trong repo: sinh diff không được hỏng, mà liệt kê `not UTF-8` (test ở Task 5).
- Đường dẫn có dấu cách: diff sinh ra vẫn áp lại được (test ở Task 5).
- Sửa quá 5 file / 500 dòng mà không dựng lại graph: lỗi phải chỉ cách làm (test ở Task 6).
- Kết quả `verify` lưu trong cache bị sửa trực tiếp khi thêm `checked_diff`/`NOT_CHECKED`, làm rò sang lần gọi sau (test ở Task 6).

---

### Task 1: Bảng `sources` trong store

**Files:**
- Modify: `src/vgar/graph/sqlite_store.py` (`initialize` dòng 82–153, `ingest` dòng 155)
- Create: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Produces:
  - `SQLiteGraphStore.ingest(document: Mapping[str, Any], sources: Mapping[str, bytes] | None = None) -> None`: ghi `sources` trong cùng transaction với node/edge.
  - `SQLiteGraphStore.put_sources(graph_version: str, sources: Mapping[str, bytes]) -> None`: thay toàn bộ dòng của version; `ValueError` (nêu path) nếu tập key khác tập path của File node, hoặc `sha256(content)` khác `content_hash` của File node.
  - `SQLiteGraphStore.get_sources(graph_version: str) -> dict[str, bytes]`: `{}` khi không có dòng nào.

- [ ] **Step 1: Viết test (đầu file test mới)**

```python
SHOP = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
}

def _write(root, files): ...            # ghi chuỗi (str) hoặc byte, tạo thư mục cha; trả root
def _doc(tmp_path, files=SHOP):          # (root, document) dựng bằng PythonGraphBuilder(repo_key="t/snap", repository_revision="rev")
def _files(root, document):              # {File node path: byte trên đĩa}

def test_ingest_keeps_the_sources_of_its_version(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(document, sources=_files(root, document))
    assert store.get_sources(document["graph_version"]) == {p: t.encode() for p, t in SHOP.items()}

def test_ingest_without_sources_stores_none(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db"); store.ingest(document)
    assert store.get_sources(document["graph_version"]) == {}

def test_put_sources_rejects_bytes_that_differ_from_the_graph(tmp_path):
    root, document = _doc(tmp_path); store = SQLiteGraphStore(tmp_path / "g.db"); store.ingest(document)
    sources = {**_files(root, document), "shop/pricing.py": b"x = 1\n"}
    with pytest.raises(ValueError, match="shop/pricing.py"):
        store.put_sources(document["graph_version"], sources)

def test_put_sources_rejects_a_missing_file(tmp_path):
    # như trên, nhưng xoá "shop/checkout.py" khỏi sources -> ValueError match "shop/checkout.py"

def test_pruning_a_version_removes_its_sources(tmp_path):
    root, first = _doc(tmp_path); store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(first, sources=_files(root, first))
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8")
    second = PythonGraphBuilder(repo_key="t/snap", repository_revision="rev").build(root)
    store.ingest(second, sources=_files(root, second))
    store.prune_other_versions(second["graph_version"], "t/snap")
    assert store.get_sources(first["graph_version"]) == {}
    assert store.get_sources(second["graph_version"])["shop/pricing.py"] == b"def round_vnd(amount):\n    return 0\n"
```

- [ ] **Step 2: Chạy, thấy FAIL** — `pytest tests/test_patch_checks_from_snapshot.py` → `TypeError: ingest() got an unexpected keyword argument 'sources'`.

- [ ] **Step 3: Cài đặt** — trong `initialize`, thêm vào `executescript`:
  `CREATE TABLE IF NOT EXISTS sources (graph_version TEXT NOT NULL, path TEXT NOT NULL, content BLOB NOT NULL, PRIMARY KEY (graph_version, path), FOREIGN KEY (graph_version) REFERENCES graph_metadata(graph_version) ON DELETE CASCADE);`
  `ingest` và `put_sources` dùng chung một hàm ghi trong transaction, kiểm key/hash theo các File node.

- [ ] **Step 4: Chạy, thấy PASS** — file test mới, rồi `pytest tests/test_sqlite_graph_service.py tests/test_live_build_layers.py tests -k "store or prune"`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/sqlite_store.py`, `tests/test_patch_checks_from_snapshot.py`.

---

### Task 2: Ghi `sources` khi dựng graph

**Files:**
- Create: `src/vgar/graph/snapshot_sources.py`
- Modify: `src/vgar/graph/live_build.py` (`_work`, quanh dòng 149–154), `src/vgar/graph/indexing.py` (`index_repo`)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: Task 1 (`ingest(..., sources=)`, `put_sources`, `get_sources`).
- Produces: `read_graph_sources(root: Path, document: Mapping[str, Any]) -> dict[str, bytes]` — đọc file của mọi File node; byte có `sha256` khác `content_hash` → `ValueError("file changed during the build: <path>; call build_or_update_graph again")`.

- [ ] **Step 1: Viết test**

```python
def test_read_graph_sources_rejects_a_file_changed_after_the_build(tmp_path):
    root, document = _doc(tmp_path)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed during the build: shop/pricing.py"):
        read_graph_sources(root, document)

def test_live_build_stores_the_source_of_every_file(tmp_path):
    root = _write(tmp_path / "repo", SHOP)
    version = LiveGraphBuilder(root, tmp_path / "g.db").run()["graph_version"]
    assert SQLiteGraphStore(tmp_path / "g.db").get_sources(version) == {p: t.encode() for p, t in SHOP.items()}

def test_live_build_backfills_the_sources_of_an_unchanged_older_graph(tmp_path):
    root = _write(tmp_path / "repo", SHOP); db = tmp_path / "g.db"
    builder = LiveGraphBuilder(root, db); version = builder.run()["graph_version"]
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM sources")           # a graph built before this change
    assert builder.run()["unchanged"] is True
    assert SQLiteGraphStore(db).get_sources(version)["shop/pricing.py"] == SHOP["shop/pricing.py"].encode()

def test_vgar_index_stores_the_sources(tmp_path):
    root = _write(tmp_path / "repo", SHOP); index_repo(root, tmp_path / "g.db")
    store = SQLiteGraphStore(tmp_path / "g.db")
    assert set(store.get_sources(store.resolve_graph_version())) == set(SHOP)
```

- [ ] **Step 2: Chạy, thấy FAIL** — `ImportError: read_graph_sources`.

- [ ] **Step 3: Cài đặt** — `read_graph_sources` trong module mới. `_work`: khi `version != previous` thì
  `store.ingest(document, sources=read_graph_sources(self.root, document))`; khi không đổi mà
  `store.get_sources(version) == {}` thì `store.put_sources(version, read_graph_sources(self.root, document))`.
  `index_repo`: `ingest(doc, sources=read_graph_sources(repo, doc))`.

- [ ] **Step 4: Chạy, thấy PASS** — file test, rồi `pytest tests/test_live_build_layers.py tests/test_tv2_live_build.py tests -k "live_build or index"`.

- [ ] **Step 5: Liệt kê file** — `src/vgar/graph/snapshot_sources.py`, `live_build.py`, `indexing.py`, file test.

---

### Task 3: `analyze_patch_impact` dùng code đã lưu

**Files:**
- Modify: `src/vgar/graph/snapshot_sources.py`, `src/vgar/graph/sqlite_service.py` (`analyze_patch_impact` dòng 391–403, thêm `snapshot_sources`)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: Task 1–2.
- Produces:
  - `NO_SOURCE_COPY_HINT: str` (chuỗi ở Global Constraints) trong `snapshot_sources.py`.
  - `materialize_snapshot(sources: Mapping[str, bytes], target: Path, *, worktree: Path | None = None) -> Path`: không có `worktree` thì chỉ ghi các file trong `sources`; có `worktree` thì `copytree(worktree, target, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))`, xoá mọi file `discover_python_files(target)` không có trong `sources`, rồi ghi toàn bộ `sources` (tạo thư mục cha). Trả `target`.
  - `SQLiteGraphService.snapshot_sources(graph_version: str) -> dict[str, bytes] | None`: `None` khi store không có dòng nào; thiếu file hoặc lệch hash với File node của `_document(graph_version)` → `ValueError("stored source of <path> does not match graph <version>: rebuild the graph")`.

- [ ] **Step 1: Viết test** (thêm helper `_build(tmp_path, files=SHOP, *, with_sources=True) -> (service, version, root)`: ghi repo, dựng document, `ingest(document, sources=read_graph_sources(...) if with_sources else None)`, `SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test")`; và `_edit_pricing(root)` ghi `return round(amount, -3)`; `PRICING_FIX` = diff một hunk như trong `tests/test_graph_tools_agent_feedback.py`)

```python
def test_patch_impact_checks_a_diff_on_the_graph_code_while_the_file_is_edited(tmp_path):
    service, version, root = _build(tmp_path); _edit_pricing(root)
    changed = service.analyze_patch_impact(PRICING_FIX, graph_version=version)["changed"]
    assert [item["path"] for item in changed] == ["shop/pricing.py"]

def test_graph_without_a_source_copy_keeps_the_old_check_and_hints_a_rebuild(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False); _edit_pricing(root)
    with pytest.raises(ValueError) as error:
        service.analyze_patch_impact(PRICING_FIX, graph_version=version)
    assert "shop/pricing.py" in str(error.value) and "build_or_update_graph" in str(error.value)

def test_a_tampered_source_copy_is_refused(tmp_path):
    service, version, _ = _build(tmp_path)
    with sqlite3.connect(tmp_path / "graph.db") as connection:
        connection.execute("UPDATE sources SET content = ? WHERE path = ?", (b"x = 1\n", "shop/pricing.py"))
    with pytest.raises(ValueError, match="shop/pricing.py"):
        service.snapshot_sources(version)

def test_materialized_snapshot_holds_the_graph_code_and_the_other_worktree_files(tmp_path):
    sources = {"pkg/a.py": b"A = 1\n", "pkg/gone.py": b"G = 1\n"}
    worktree = _write(tmp_path / "wt", {"pkg/a.py": "A = 2\n", "scratch.py": "x = 1\n", "data.json": "{}",
                                        ".venv/lib/site.py": "s = 1\n"})
    target = materialize_snapshot(sources, tmp_path / "copy", worktree=worktree)
    assert (target / "pkg/a.py").read_bytes() == b"A = 1\n" and (target / "pkg/gone.py").read_bytes() == b"G = 1\n"
    assert not (target / "scratch.py").exists() and (target / "data.json").read_text() == "{}"
    assert (target / ".venv/lib/site.py").exists()          # folders the builder ignores are left alone
```

- [ ] **Step 2: Chạy, thấy FAIL** — test đầu báo lỗi lệch file (đợt 2) thay vì trả `changed`; các test khác `ImportError`/`AttributeError`.

- [ ] **Step 3: Cài đặt** — `analyze_patch_impact`: có `sources` thì dựng `materialize_snapshot(sources, <TemporaryDirectory>/"snapshot")` (không `worktree`) và truyền thư mục đó làm `source_repo`; không có thì: `drift = source_drift(document, self.repository_root)`, nếu có thì `raise ValueError(f"{drift} {NO_SOURCE_COPY_HINT}")`, còn lại như cũ.

- [ ] **Step 4: Chạy, thấy PASS** — file test, rồi `pytest tests/test_graph_tools_agent_feedback.py tests -k "impact"`.

- [ ] **Step 5: Liệt kê file** — `snapshot_sources.py`, `sqlite_service.py`, file test.

---

### Task 4: `verify_patch` và `run_patch_tests` dùng code đã lưu

**Files:**
- Modify: `src/vgar/repair/patch_evidence.py` (`verify_patch` dòng 64–150, `run_patch_tests` dòng 154–260)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: Task 3 (`service.snapshot_sources`, `materialize_snapshot`, `NO_SOURCE_COPY_HINT`).
- Produces: không có hàm mới; hành vi: khi có `sources`, bản sao kiểm = `materialize_snapshot(sources, folder / "repo", worktree=root)`.

- [ ] **Step 1: Viết test** (helper `_build_from(tmp_path, repo)`: chép fixture vào `tmp_path/"repo"` bỏ `__pycache__`, dựng có `sources`; `_apply_in_place(root, diff)`: ghi byte `_bind(parse_unified_diff(diff, PatchPolicy(("auth.py",), ())), root)` vào file, giống agent sửa tại chỗ; `LOGIN_REPO`, `REF`, `FAILING` lấy như `tests/test_tv2_patch_evidence.py`)

```python
def test_verify_passes_a_diff_while_the_file_is_edited(tmp_path):
    service, version, root = _build(tmp_path); _edit_pricing(root)
    assert verify_patch(service, PRICING_FIX, graph_version=version)["status"] == "PASS"

def test_verify_ignores_a_scratch_file_added_after_the_build(tmp_path):
    service, version, root = _build(tmp_path); _edit_pricing(root)
    (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    assert verify_patch(service, PRICING_FIX, graph_version=version)["status"] == "PASS"

def test_verify_without_a_source_copy_hints_a_rebuild(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False); _edit_pricing(root)
    reason = verify_patch(service, PRICING_FIX, graph_version=version)["reasons"][0]
    assert reason.startswith("SOURCE_DIFFERS_FROM_SNAPSHOT") and "build_or_update_graph" in reason

def test_patch_tests_run_on_the_graph_code_while_the_fix_is_in_the_worktree(tmp_path):
    service, version, root = _build_from(tmp_path, LOGIN_REPO); _apply_in_place(root, REF)
    result = run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING)
    assert result["status"] == "PASS"
    assert result["baseline"][FAILING[0]] == "FAIL" and result["candidate"][FAILING[0]] == "PASS"
```

- [ ] **Step 2: Chạy, thấy FAIL** — `verify` trả `ERROR`/`SOURCE_DIFFERS_FROM_SNAPSHOT`; `run_patch_tests` trả `PATCH_DOES_NOT_APPLY`.

- [ ] **Step 3: Cài đặt** — `verify_patch`: có `sources` thì dựng bản sao bằng `materialize_snapshot(..., worktree=root)`, không thì `copytree` như cũ; lý do lệch file (nhánh cũ) thêm `NO_SOURCE_COPY_HINT`; gọi `impact.analyze_patch_impact` với bản sao **trước** khi ghi byte ứng viên vào nó (bản sao còn nguyên là code gốc). `run_patch_tests`: có `sources` thì dựng bản sao trước, dùng nó cho bước impact và cho pytest; không thì như cũ.

- [ ] **Step 4: Chạy, thấy PASS** — file test, rồi `pytest tests/test_tv2_patch_evidence.py tests/test_graph_tools_agent_feedback.py tests -k "verify or patch_tests or evidence"`.

- [ ] **Step 5: Liệt kê file** — `patch_evidence.py`, file test.

---

### Task 5: Sinh diff từ thư mục làm việc

**Files:**
- Create: `src/vgar/repair/worktree_diff.py`
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class WorktreeDiff:
      diff: str                     # unified diff kiểu git; "" khi không có gì để kiểm
      files: tuple[str, ...]        # path có trong diff, đã sắp xếp
      not_checked: tuple[str, ...]  # các mục ở Global Constraints, đã sắp xếp
      changed_lines: int            # số dòng '+'/'-' trong thân hunk

  def worktree_diff(sources: Mapping[str, bytes], root: Path) -> WorktreeDiff
  ```

- [ ] **Step 1: Viết test** (helper `_round_trip(tmp_path, stored, worktree) -> dict[str, bytes]`: ghi `stored` vào `base/`, `worktree` vào `wt/`; `wd = worktree_diff(stored, wt)`; trả `_bind(parse_unified_diff(wd.diff, PatchPolicy(tuple(stored), ())), base)[0]`)

```python
@pytest.mark.parametrize("old, new", [
    (b"a\nb\nc\n", b"a\nB\nc\n"),           # edit a middle line
    (b"a\nb", b"a\nb\nc\n"),                # file without final newline grows
    (b"a\nb\n", b"a\nb"),                   # final newline removed
    (b"a\r\nb\r\n", b"a\r\nX\r\n"),         # CRLF on both sides
])
def test_worktree_diff_applies_back_to_the_worktree_bytes(tmp_path, old, new):
    assert _round_trip(tmp_path, {"m.py": old}, {"m.py": new}) == {"m.py": new}

def test_worktree_diff_handles_paths_with_spaces(tmp_path):
    assert _round_trip(tmp_path, {"my pkg/m.py": b"a\n"}, {"my pkg/m.py": b"b\n"}) == {"my pkg/m.py": b"b\n"}

def test_worktree_diff_counts_changed_lines(tmp_path):
    root = _write(tmp_path / "wt", {"m.py": b"a\nB\n"})
    assert worktree_diff({"m.py": b"a\nb\n"}, root).changed_lines == 2

def test_line_endings_alone_are_not_a_change(tmp_path):
    wd = worktree_diff({"m.py": b"a\nb\n"}, _write(tmp_path / "wt", {"m.py": b"a\r\nb\r\n"}))
    assert wd.diff == "" and wd.not_checked == ("line endings only: m.py",)

def test_new_deleted_and_non_utf8_files_are_listed_not_diffed(tmp_path):
    root = _write(tmp_path / "wt", {"a.py": b"A\n", "new.py": b"N\n", "bin.py": b"\xff\n"})
    wd = worktree_diff({"a.py": b"A\n", "gone.py": b"G\n", "bin.py": b"x\n"}, root)
    assert wd.diff == "" and wd.files == ()
    assert wd.not_checked == ("deleted file: gone.py", "new file: new.py", "not UTF-8: bin.py")

def test_no_change_gives_an_empty_diff(tmp_path):
    wd = worktree_diff({"a.py": b"A\n"}, _write(tmp_path / "wt", {"a.py": b"A\n"}))
    assert (wd.diff, wd.files, wd.not_checked, wd.changed_lines) == ("", (), (), 0)
```

- [ ] **Step 2: Chạy, thấy FAIL** — `ImportError: worktree_diff`.

- [ ] **Step 3: Cài đặt** — file hiện tại = `discover_python_files(root)` (path posix tương đối). Với mỗi path có ở cả hai bên mà byte khác:

  ```python
  def _tokens(text: str) -> list[str]:
      lines = text.splitlines(keepends=True)
      tokens = [line.rstrip("\r\n") for line in lines]
      if lines and not lines[-1].endswith(("\n", "\r")):
          tokens[-1] += "\0"            # a missing final newline is a real change; line endings are not
      return tokens
  ```

  Token bằng nhau → `line endings only`. Khác → `difflib.unified_diff(old, new, f"a/{p}", f"b/{p}", n=3, lineterm="")`, thêm dòng `diff --git a/{p} b/{p}` ở đầu; mỗi dòng thân có token kết thúc bằng `"\0"`: bỏ `"\0"` và thêm dòng `\ No newline at end of file` ngay sau. Path có khoảng trắng: dùng `json.dumps` cho tên `a/…`, `b/…` ở cả ba dòng header (như `patch._bind`). Giải mã UTF-8 lỗi → `not UTF-8`. File chỉ có ở thư mục làm việc → `new file`; chỉ có trong `sources` → `deleted file`.

- [ ] **Step 4: Chạy, thấy PASS** — file test.

- [ ] **Step 5: Liệt kê file** — `src/vgar/repair/worktree_diff.py`, file test.

---

### Task 6: Tool không cần `diff`

**Files:**
- Modify: `src/vgar/repair/patch_evidence.py` (thêm `resolve_diff`), `src/vgar/mcp/servers/graph_server.py` (`analyze_patch_impact`, `verify_patch_graph_constraints`, docstring), `src/vgar/mcp/servers/execution_server.py` (`run_relevant_tests`)
- Test: `tests/test_patch_checks_from_snapshot.py`

**Interfaces:**
- Consumes: Task 3 (`snapshot_sources`, `NO_SOURCE_COPY_HINT`), Task 5 (`worktree_diff`).
- Produces:
  - `resolve_diff(service: Any, graph_version: str, diff: str) -> tuple[str, dict[str, Any]]` → `(diff sẽ kiểm, checked_diff)`. `diff` khác rỗng: `source="argument"`, `files` = các path sau `+++ b/`, `not_checked=[]`. `diff` rỗng: không có `sources` → `ValueError(f"no diff given and {NO_SOURCE_COPY_HINT}, or pass the diff")`; vượt `PatchPolicy` mặc định → `ValueError("the working tree differs from graph <v> in <n> files / <m> changed lines (limit <max_files> files, <max_changed_lines> lines): check and rebuild the graph after each fix")`; còn lại `source="worktree"` từ `worktree_diff`. Không có thay đổi: trả `("", checked_diff)`.
  - Tool: `analyze_patch_impact(graph_version: str, diff: str = "", max_hops: int = 2, max_nodes: int = 200)`, `verify_patch_graph_constraints(diff: str = "")`, `run_relevant_tests(diff: str = "")`.

- [ ] **Step 1: Viết test** (fixture `served(tmp_path, monkeypatch) -> (version, root)`: `_build` có `sources`; đặt `graph_server.graph_service`, `graph_server._audit_logger` (`AuditLogger(tmp_path/"a.jsonl")`), `graph_server._verify_cache = {}`; `verify = lambda: anyio.run(graph_server.verify_patch_graph_constraints)`)

```python
def test_analyze_without_a_diff_checks_the_worktree_changes(served):
    version, root = served; _edit_pricing(root)
    data = graph_server.analyze_patch_impact(graph_version=version)["data"]
    assert [item["path"] for item in data["changed"]] == ["shop/pricing.py"]
    assert data["checked_diff"]["source"] == "worktree" and data["checked_diff"]["files"] == ["shop/pricing.py"]

def test_verify_without_a_diff_passes_and_lists_a_scratch_file(served):
    version, root = served; _edit_pricing(root); (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    data = verify()["data"]
    assert data["status"] == "PASS" and data["checked_diff"]["not_checked"] == ["new file: scratch.py"]
    assert "NOT_CHECKED: new file: scratch.py" in data["reasons"]

def test_verify_without_changes_is_not_run(served):
    data = verify()["data"]
    assert data["status"] == "NOT_RUN" and data["reasons"] == ["NO_CHANGES"]

def test_analyze_without_changes_says_check_before_rebuilding(served):
    response = graph_server.analyze_patch_impact(graph_version=served[0])
    assert response["status"] == "ERROR" and "before rebuilding" in response["error"]["message"]

def test_verify_follows_new_edits_between_calls(served):
    version, root = served; _edit_pricing(root); first = verify()["data"]["status"]
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return (\n", encoding="utf-8")
    second = verify()["data"]
    assert first == "PASS" and second["status"] == "FAIL" and "CANDIDATE_SYNTAX_ERROR" in second["reasons"]

def test_not_checked_entries_do_not_leak_between_calls(served):
    version, root = served; _edit_pricing(root); (root / "a_scratch.py").write_text("x = 1\n", encoding="utf-8")
    verify(); (root / "a_scratch.py").unlink()
    data = verify()["data"]
    assert data["checked_diff"]["not_checked"] == [] and not any(r.startswith("NOT_CHECKED") for r in data["reasons"])

def test_graph_without_a_source_copy_needs_a_diff(tmp_path, monkeypatch):
    # như fixture served nhưng _build(..., with_sources=False); _edit_pricing(root)
    response = anyio.run(graph_server.verify_patch_graph_constraints)
    assert response["status"] == "ERROR" and "build_or_update_graph" in response["error"]["message"]

def test_too_many_changed_files_ask_to_rebuild_after_each_fix(tmp_path, monkeypatch):
    # repo 6 module m0.py..m5.py ("X = 0\n"), dựng có sources, đặt graph_service; sửa cả 6 thành "X = 1\n"
    response = graph_server.analyze_patch_impact(graph_version=version)
    assert response["status"] == "ERROR" and "rebuild the graph after each fix" in response["error"]["message"]

def test_a_host_provider_still_requires_a_diff(served, monkeypatch):
    monkeypatch.setattr(graph_server, "_has_provider", lambda capability: True)
    response = verify()
    assert response["status"] == "ERROR" and "diff is required" in json.dumps(response)

def test_run_relevant_tests_without_a_diff(tmp_path, monkeypatch):
    service, version, root = _build_from(tmp_path, LOGIN_REPO); _apply_in_place(root, REF)
    monkeypatch.setattr(execution_server, "_graph_service", service)
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "x.jsonl"))
    data = anyio.run(execution_server.run_relevant_tests)["data"]
    assert data["candidate"][FAILING[0]] == "PASS" and data["checked_diff"]["files"] == ["auth.py"]
```

- [ ] **Step 2: Chạy, thấy FAIL** — `TypeError: missing required argument 'diff'`.

- [ ] **Step 3: Cài đặt**
  - `resolve_diff` theo Interfaces, đặt trong `patch_evidence.py`.
  - `analyze_patch_impact` (graph_server): trong `call()`, `checked, meta = resolve_diff(graph_service, graph_version, diff)`; `checked == ""` → `ValueError(f"no change between the working tree and graph {graph_version}; if you just rebuilt the graph, the change is already in it: check before rebuilding")`; kết quả service thêm `data["checked_diff"] = meta`.
  - Audit (cả ba tool): hash của diff tự tính chỉ có sau khi chạy, nên thêm `checked_sha256 = checked_diff["sha256"]` và `diff_source = checked_diff["source"]` vào hàm tóm tắt (đối số `summarize` của `_tool` / `run_tool_async`); trường trước khi chạy giữ hash của tham số như hiện nay.
  - `verify_patch_graph_constraints`: nhánh provider, `diff` rỗng → lỗi `INVALID_ARGUMENT` "diff is required with the host's verification provider" (dựng lỗi trong lambda tạo request, giống khi `DiffRequest` không hợp lệ). Nhánh mặc định: version = `graph_service.get_repository_summary().graph_version`; `resolve_diff`; không thay đổi → `{"status": "NOT_RUN", "checks": {}, "reasons": ["NO_CHANGES"], "graph_version": version, "diff_sha256": diff_sha256(""), "checked_diff": meta}`; có thay đổi → **bản sao** `dict(_verified(checked))`, nối `reasons` với `"NOT_CHECKED: " + mục`, thêm `checked_diff`. Không sửa object trong cache.
  - `run_relevant_tests`: cùng mẫu, provider = `core_tools.registry.get("tests")`, record `NOT_RUN`/`NO_CHANGES` theo khóa của `run_patch_tests`.
  - Docstring ba tool: `diff` tuỳ chọn, mặc định là thay đổi của thư mục làm việc so với graph; kết quả có `checked_diff`; gọi trước khi `build_or_update_graph`.

- [ ] **Step 4: Chạy, thấy PASS** — file test, rồi `pytest tests/mcp_server tests/test_graph_tools_agent_feedback.py tests/test_tv2_patch_evidence.py tests/test_graph_tools_proposal_alignment.py`.

- [ ] **Step 5: Liệt kê file** — `patch_evidence.py`, `graph_server.py`, `execution_server.py`, file test.

---

### Task 7: Tài liệu, artifact, kiểm tra toàn bộ

**Files:**
- Modify: `README.md` (mục "Working session" bước 4), `repair_agent/shopflow_opencode_scenario.md`, `artifacts/sample_graph.db`, `docs/superpowers/specs/2026-11-22-tv2-patch-checks-from-snapshot-design.md` (trạng thái)

- [ ] **Step 1: README bước 4** — thay bằng: "4. It checks its change with `analyze_patch_impact`, `verify_patch_graph_constraints`, `run_relevant_tests` and `rank_patch_candidates` **before** rebuilding the graph. Leave `diff` empty: the server diffs the working tree against the source the graph was built from (stored in the database) and returns what it checked in `checked_diff`, including files it could not check (new, deleted, line endings only). A diff given explicitly is applied to that same source. A graph built before this change has no stored source: rebuild it once. A change may touch at most 5 files and 500 changed lines; rebuild the graph after each checked fix."

- [ ] **Step 2: Kịch bản** — viết lại `repair_agent/shopflow_opencode_scenario.md` cho repo `D:\kltn\shopflow-clean\shopflow` theo bản đã gửi ngày 22/11 (Bước 0 cài MCP + `git config core.autocrlf false`, đặc tả nghiệp vụ trong prompt, 14 mô tả lỗi B01–B17, chấm bằng `hidden_tests`), với bước 3 mục 5–6 đổi thành: "5. Gọi analyze_patch_impact và verify_patch_graph_constraints, KHÔNG truyền diff; báo nguyên văn kết quả, kể cả `checked_diff.not_checked`. Nếu tool báo lỗi thì coi như CHƯA kiểm. 6. Gọi build_or_update_graph (commit là tuỳ chọn)."

- [ ] **Step 3: Artifact** — `.venv/Scripts/python.exe -c "from vgar.graph.sqlite_store import SQLiteGraphStore; SQLiteGraphStore('artifacts/sample_graph.db').initialize()"`; kiểm `git diff --stat -- artifacts/sample_graph.db` có thay đổi và `pytest tests/mcp_server` PASS.

- [ ] **Step 4: Toàn bộ bộ test** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --ignore=.claude`. Kỳ vọng: chỉ còn 7 FAIL có sẵn (`test_jarvis_runner.py` ×4 và `test_joern_runner.py` ×2 cần Docker, `test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`).

- [ ] **Step 5: Kiểm bằng tool thật trên bản sao ShopFlow** — `git archive HEAD` của `D:\kltn\shopflow-clean\shopflow` vào thư mục tạm, `git init`, `git config core.autocrlf true`, commit; trỏ `VGAR_REPOSITORY_ROOT`/`VGAR_GRAPH_DATABASE` vào đó; gọi `build_or_update_graph`; sửa `shopflow/services/pricing.py` tại chỗ và thêm `scratch.py`; `analyze_patch_impact(graph_version)` không diff → `changed` có `quote_order`; `verify_patch_graph_constraints()` → `PASS`, `not_checked == ["new file: scratch.py"]`; chạy `git stash` rồi `git stash pop` (git ghi lại CRLF) → `verify` vẫn `PASS`. Xoá thư mục tạm.

- [ ] **Step 6: Liệt kê file và lệnh commit cho TV2** — mọi file của Task 1–7, kèm một lệnh `git add -- …` và `git commit -m "feat(mcp): patch checks run on the graph's stored source; diff optional, computed from the working tree (TV2, OpenCode ShopFlow runs 22/11)"`.
