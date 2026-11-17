# G1 Labelled Call Edges and Name Uses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A kit that samples 150 call sites and 150 non-call name uses from the 12 dev repositories into a blind labelling sheet, and an evaluator that reports call edge P/R and name-use P/R of the graph against the locked labels, with a 30-item user agreement check.

**Architecture:** All logic lives in one library module `src/vgar/evaluation/g1_labels.py` (enumeration with `ast`/`symtable`, candidate table, sampling, sheets, lock, label parsing, matching, metrics, agreement). Two thin scripts wrap it: `scripts/g1_label_kit.py` (checkouts → sheets, `--lock`) and `scripts/g1_evaluate.py` (lock check → agreement/settlement → graphs per configuration → report). The kit never builds a graph.

**Tech Stack:** Python 3.11 stdlib (`ast`, `symtable`, `csv`, `hashlib`, `random`), existing R1 helpers (`read_repository_sources`, `extract_python_tree`, `is_source`, `decode_source`), `PythonGraphBuilder`, `layer_config`.

**Spec:** `docs/superpowers/specs/2026-11-16-g1-labelled-edges-design.md`

## Global Constraints

- Sample sizes: 150 calls, 150 name uses; sampling seed 0; agreement subset 15 calls + 15 name uses, seed 1.
- Even allocation by repository: `total // 12` each, remainder to the repositories with the most eligible items.
- Bootstrap: 2,000 resamples, seed 7, 95 % interval (same as R1).
- Task per repository: first task of each repository in manifest order, manifest `~/rt1/data/manifests/w10-dev-50-gold.json`.
- Production files only: `is_source(path)` and not `conftest.py`, `setup.py`.
- Candidates come from the definition table only, sorted by qualified name; the kit builds no graph.
- Label grammar: candidate numbers separated by `;`, or `external`, `builtin`, `unknown`, `other:<qualified name>`.
- Name-use graph edges: `REFERENCES` with `rule_id == "python.layer1.reads.v1"`.
- Every report string calls the labels "labels assigned by Claude"; never "hand labels".
- No change to `src/vgar/graph/`, resolvers or retrieval.
- The user commits; tasks end by listing the files, never by running `git commit` (memory rule).

## Review Focus

1. A source file that `ast` cannot parse (Python 2 syntax, encoding errors) → skipped and counted in `manifest.json` `unparsed_files`, never a crash. Test in Task 1.
2. A file with a non-UTF-8 coding cookie → decoded with `decode_source`; `col` is the byte offset in the raw file, as tree-sitter (and so the graph's `CallSite`) counts it. Test in Task 1.
3. Label typos (`"1, 3"`, `" External "`, a number above the candidate count, empty cell) → whitespace/case normalised; invalid or empty labels make `--lock` refuse and list the item ids. Test in Task 2.
4. A repository with fewer eligible items than its quota → takes all, the deficit goes to the others by the same remainder rule, totals stay 150. Test in Task 2.
5. Two definitions with the same name in one file (property getter/setter, redefinition) → two candidates with different lines; mapping to graph nodes picks the node whose range contains that line. Test in Task 3.

---

### Task 1: Enumerate items and build the candidate table

**Files:**
- Create: `src/vgar/evaluation/g1_labels.py`
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Definition: kind: str` (`"function" | "method" | "class" | "global" | "field"`), `qualified_name: str`, `name: str`, `path: str`, `line: int` (def line, or first assignment line), `lines: tuple[int, ...]` (all assignment lines for global/field; `(line,)` otherwise)
  - `@dataclass(frozen=True) class Item: kind: str` (`"call" | "name"`), `repo: str`, `task_id: str`, `path: str`, `line: int`, `col: int` (0-based UTF-8 byte offset), `name: str`, `code: str` (the source line, stripped of the newline), `enclosing: str` (qualified name of the enclosing def, or the module name), `candidates: tuple[Definition, ...]` (sorted by `qualified_name`, then `line`)
  - `production_files(tree: Path) -> list[str]` (POSIX relative paths, sorted)
  - `scan_repository(tree: Path, *, repo: str, task_id: str, source_roots: tuple[str, ...] = ("src",)) -> tuple[list[Item], dict]` → eligible items (those with ≥1 candidate) of both kinds, and stats `{"files": n, "unparsed_files": [paths], "calls_total": n, "calls_eligible": n, "names_total": n, "names_eligible": n}`
- Qualified names: `module_name_for(path, source_roots, tree.name)` (from `vgar.graph.builder`) + nested class/def names; field = `<class qname>.<attr>`; global = `<module>.<name>`.

- [ ] **Step 1: Write the failing tests**

Fixture helper `_repo(tmp_path, files: dict[str, str]) -> Path` writes files under `tmp_path / "repo"`. Tests:

```python
def test_call_and_name_items_at_ast_positions(tmp_path):
    root = _repo(tmp_path, {"pkg/mod.py": "LIMIT = 3\n\ndef helper(x):\n    return x\n\nclass Box:\n    def __init__(self):\n        self.size = LIMIT\n    def grow(self):\n        return helper(self.size)\n"})
    items, stats = scan_repository(root, repo="o/r", task_id="t")
    calls = [(i.name, i.line, i.col) for i in items if i.kind == "call"]
    names = sorted((i.name, i.line) for i in items if i.kind == "name")
    assert calls == [("helper", 10, 15)]
    assert names == [("LIMIT", 8), ("size", 10)]   # self.size on line 8 is a store, so it is not an item
    assert stats["calls_eligible"] == 1

def test_locals_parameters_and_call_func_are_not_name_items(tmp_path):
    root = _repo(tmp_path, {"m.py": "def f(a):\n    b = a\n    return g(b)\n\ndef g(x):\n    return x\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    assert [i.name for i in items if i.kind == "name"] == []

def test_alias_uses_original_name_for_candidates(tmp_path):
    root = _repo(tmp_path, {"a.py": "def real():\n    return 1\n", "b.py": "from a import real as r\n\ndef use():\n    return r()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call"]
    assert [c.qualified_name for c in call.candidates] == ["a.real"]

def test_candidates_cover_every_same_name_definition_sorted(tmp_path):
    root = _repo(tmp_path, {"x.py": "class A:\n    def run(self):\n        pass\n", "y.py": "class B:\n    def run(self):\n        pass\n\ndef go(o):\n    o.run()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call"]
    assert [c.qualified_name for c in call.candidates] == ["x.A.run", "y.B.run"]

def test_unparsable_file_is_skipped_and_counted(tmp_path):
    root = _repo(tmp_path, {"ok.py": "def f():\n    return f()\n", "py2.py": "print 'x'\n"})
    items, stats = scan_repository(root, repo="o/r", task_id="t")
    assert stats["unparsed_files"] == ["py2.py"] and len(items) == 1

def test_latin1_file_keeps_byte_columns(tmp_path):
    src = "# -*- coding: latin-1 -*-\ndef f():\n    s = 'é'; return f()\n".encode("latin-1")
    root = tmp_path / "repo"; root.mkdir(); (root / "l.py").write_bytes(src)
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = items
    assert call.line == 3 and call.col == len("    s = 'é'; return ".encode("latin-1"))   # raw-file bytes, as tree-sitter sees them

def test_production_files_skip_tests_conftest_and_setup(tmp_path):
    root = _repo(tmp_path, {"pkg/a.py": "", "tests/test_a.py": "", "conftest.py": "", "setup.py": "", "docs/conf.py": ""})
    assert production_files(root) == ["pkg/a.py"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q`
Expected: FAIL with `ImportError: cannot import name 'scan_repository'`

- [ ] **Step 3: Implement `Definition`, `Item`, `production_files`, `scan_repository` in `src/vgar/evaluation/g1_labels.py`**

- Read bytes, decode with `vgar.evaluation.retrieval.chunks.decode_source`, parse with `ast.parse`; on `SyntaxError`/`ValueError`/`UnicodeDecodeError` append the path to `unparsed_files` and continue.
- `col` must equal the graph's `CallSite` `range.start_col`, which is a byte offset in the **raw file bytes** (the builder passes `read_bytes()` to tree-sitter, `builder.py:389`). CPython's `col_offset` is in UTF-8 bytes of the decoded line, so convert: `char_col = len(line.encode("utf-8")[:col_offset].decode("utf-8"))`, then `col = len(line[:char_col].encode(file_encoding))` with the encoding `tokenize.detect_encoding` found. For UTF-8 files this is the identity. State the convention in the module docstring.
- Locals: for each function, `symtable` symbols with `is_parameter()` or `is_assigned()` and not `is_global()`/`is_declared_global()`/`is_nonlocal()` are local; Name items only when `isinstance(ctx, ast.Load)`, not the `func` of a Call, inside a function body, not local.
- Attribute items: every `ast.Attribute` in Load context inside a function body that is not the `func` of a Call.
- Definitions pass first over all files, then items; alias map per module from `ImportFrom`/`Import` with `asname`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q`
Expected: 7 passed

- [ ] **Step 5: Hand-off** — no commit (the user commits). Files: `src/vgar/evaluation/g1_labels.py`, `tests/test_g1_labels.py`.

---

### Task 2: Sampling, sheets, agreement subset, label grammar and lock

**Files:**
- Modify: `src/vgar/evaluation/g1_labels.py`
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Consumes: `Item`, `Definition` (Task 1).
- Produces:
  - `allocate(eligible: dict[str, int], total: int) -> dict[str, int]` — per-repository quota
  - `sample_items(items: list[Item], kind: str, total: int, seed: int) -> list[Item]` — allocated, uniform within repository (`random.Random(f"{seed}:{repo}:{kind}")`), then shuffled with `random.Random(seed)`
  - `SHEET_COLUMNS = ("item_id", "repo", "task_id", "path", "line", "col", "code", "candidates", "label", "note")`
  - `write_sheet(path: Path, items: list[Item], prefix: str) -> list[str]` — ids `C001…`/`N001…` in list order; `candidates` cell `1) qname — path:line; 2) …`; returns ids
  - `write_items_md(path: Path, rows: list[tuple[str, Item]], tree_of: dict[str, Path]) -> None` — 3 lines before/after, item line marked `>>`
  - `agreement_ids(call_ids: list[str], name_ids: list[str], k: int = 15, seed: int = 1) -> list[str]`
  - `write_agreement_sheet(path: Path, main_rows: dict[str, dict], ids: list[str], seed: int = 1) -> None` — same columns, `label`/`note` empty, own shuffled order
  - `@dataclass(frozen=True) class Label: cls: str` (`"in_repo" | "external" | "builtin" | "unknown"`), `targets: tuple[Definition | str, ...]` (Definitions for numbers, the qname string for `other:`)
  - `parse_label(text: str, candidates: tuple[Definition, ...]) -> Label` — raises `ValueError` for empty or invalid
  - `read_sheet(path: Path) -> dict[str, dict]` — rows by `item_id`
  - `sha256_file(path: Path) -> str`
  - `lock(out: Path, items_by_id: dict[str, Item]) -> None` — validates every label with `parse_label`, raises `ValueError(f"invalid labels: {ids}")`, then appends `{"sheet", "sha256", "at"}` per sheet to `manifest.json["locks"]`
  - `check_lock(out: Path, sheet: str) -> None` — raises `ValueError` if the sheet has no lock or its hash differs from the latest lock

- [ ] **Step 1: Write the failing tests**

```python
def test_allocate_even_with_remainder_to_largest():
    q = allocate({f"r{i:02d}": 100 + i for i in range(12)}, 150)
    assert sum(q.values()) == 150 and sorted(q.values()) == [12] * 6 + [13] * 6
    assert all(q[f"r{i:02d}"] == 13 for i in range(6, 12))

def test_allocate_redistributes_short_repository():
    q = allocate({"small": 3, **{f"r{i:02d}": 500 for i in range(11)}}, 150)
    assert q["small"] == 3 and sum(q.values()) == 150

def test_sample_is_deterministic_and_respects_quota(tmp_path):
    items = [_item(repo=f"r{i % 3}", line=n) for n, i in enumerate(range(90))]
    a = sample_items(items, "call", 30, seed=0); b = sample_items(items, "call", 30, seed=0)
    assert a == b and Counter(i.repo for i in a) == {"r0": 10, "r1": 10, "r2": 10}

def test_parse_label_grammar():
    cands = (_defn("a.f", 1), _defn("b.f", 2), _defn("c.f", 3))
    assert parse_label(" 1 ; 3 ", cands).targets == (cands[0], cands[2])
    assert parse_label(" External ", cands).cls == "external"
    assert parse_label("other:pkg.mod.g", cands) == Label("in_repo", ("pkg.mod.g",))
    for bad in ("", "4", "1, 3", "maybe"):
        with pytest.raises(ValueError):
            parse_label(bad, cands)

def test_lock_refuses_invalid_and_detects_edits(tmp_path):
    out, items = _kit_out(tmp_path)          # writes calls.csv/name_uses.csv/manifest.json with two items
    _fill(out / "calls.csv", {"C001": "1", "C002": ""})
    with pytest.raises(ValueError, match="C002"):
        lock(out, items)
    _fill(out / "calls.csv", {"C002": "builtin"}); _fill(out / "name_uses.csv", {"N001": "unknown", "N002": "1"})
    lock(out, items); check_lock(out, "calls.csv")
    _fill(out / "calls.csv", {"C001": "unknown"})
    with pytest.raises(ValueError):
        check_lock(out, "calls.csv")

def test_agreement_sheet_hides_claude_labels(tmp_path):
    out, items = _kit_out(tmp_path); _fill(out / "calls.csv", {"C001": "1"})
    ids = agreement_ids(["C001", "C002"], ["N001", "N002"], k=1, seed=1)
    write_agreement_sheet(out / "agreement_user.csv", {**read_sheet(out / "calls.csv"), **read_sheet(out / "name_uses.csv")}, ids)
    rows = read_sheet(out / "agreement_user.csv")
    assert sorted(rows) == sorted(ids) and all(r["label"] == "" for r in rows.values())
    assert agreement_ids(["C001", "C002"], ["N001", "N002"], k=1, seed=1) == ids
```

`_item`, `_defn`, `_kit_out`, `_fill` are small helpers in the test file (`_kit_out` calls `write_sheet` for two calls and two names, each with two candidates, and writes `manifest.json` `{"locks": []}`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q -k "allocate or sample or parse_label or lock or agreement_sheet"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement the Task 2 interfaces in `src/vgar/evaluation/g1_labels.py`**

`allocate`: start with `total // n` capped at each repository's eligible count, then hand out the remaining units one at a time to repositories ordered by (eligible − quota descending, name), skipping full ones. Label normalisation: `text.strip().lower()` for keywords; numbers split on `;` with surrounding spaces stripped; a comma anywhere is invalid.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q`
Expected: 13 passed

- [ ] **Step 5: Hand-off** — no commit. Files: `src/vgar/evaluation/g1_labels.py`, `tests/test_g1_labels.py`.

---

### Task 3: Matching to the graph, metrics and agreement statistics

**Files:**
- Modify: `src/vgar/evaluation/g1_labels.py`
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Consumes: `Item`, `Definition`, `Label` (Tasks 1–2).
- Produces:
  - `READS_RULE = "python.layer1.reads.v1"`
  - `class GraphIndex: __init__(self, document: dict)`; `node_for(self, target: Definition | str) -> str | None` (callables: same path and name, type in `{Function, Method, Class}`, range contains `target.line`, innermost; variables: type in `{GlobalVariable, Field}`, same path and name, `target.lines` ∩ (`properties.assignment_lines` or `[range.start_line]`) non-empty; `str` → node with that `qualified_name`); `call_targets(self, item: Item) -> tuple[bool, set[str], set[str]]` (CallSite found at `path`/`line`/`col` from `range.start_line`/`start_col`; `CALLS` targets; `CALLS ∪ MAY_CALL` targets); `name_targets(self, item: Item) -> set[str]` (innermost Function/Method containing the line; its `REFERENCES` edges with `READS_RULE` whose target `name == item.name`)
  - `@dataclass class Scored: item_id: str, kind: str, repo: str, label: Label, truth: set[str], predicted: set[str], status: str` (`"no_callsite" | "no_edge" | "right" | "wrong" | "partial"`), `unmapped: int`
  - `score_item(index: GraphIndex, item_id: str, item: Item, label: Label, *, may_call: bool = False) -> Scored` — unmapped true targets enter `truth` as `"unmapped:<qname>"`
  - `micro_pr(rows: list[Scored]) -> dict` → `{"precision", "recall", "tp", "fp", "fn", "n", "precision_ci95", "recall_ci95"}` (bootstrap over rows, 2,000, seed 7; `None` when a denominator is 0)
  - `agreement(claude: dict[str, Label], user: dict[str, Label]) -> dict` → `{"n", "raw", "kappa", "target_equal_in_repo", "disagreements": [ids]}`; equal = same `cls` and, for `in_repo`, same target set; kappa on `cls`, `None` when expected agreement is 1

- [ ] **Step 1: Write the failing tests**

Build documents by hand with a helper `_doc(nodes, edges)` (only the fields the index reads: `id`, `type`, `name`, `qualified_name`, `path`, `range`, `properties`; edges `type`, `source_id`, `target_id`, `provenance.rule_id`).

```python
def test_callsite_matched_by_position_and_may_call_separate():
    idx = GraphIndex(_doc_call())          # CallSite at m.py 10:15, CALLS -> f, MAY_CALL -> g
    found, calls, both = idx.call_targets(_item(kind="call", path="m.py", line=10, col=15))
    assert found and calls == {"F"} and both == {"F", "G"}
    assert idx.call_targets(_item(kind="call", path="m.py", line=10, col=16))[0] is False

def test_same_name_definitions_map_by_line():
    idx = GraphIndex(_doc_property())      # two Method nodes "x" in c.py, ranges 3-4 and 6-7
    assert idx.node_for(_defn("c.C.x", 3, kind="method", path="c.py")) == "X_GET"
    assert idx.node_for(_defn("c.C.x", 6, kind="method", path="c.py")) == "X_SET"

def test_name_targets_use_reads_rule_and_name():
    idx = GraphIndex(_doc_reads())         # function F reads Field size (READS_RULE) and global LIMIT (other rule)
    assert idx.name_targets(_item(kind="name", path="m.py", line=8, name="size")) == {"FIELD_SIZE"}
    assert idx.name_targets(_item(kind="name", path="m.py", line=8, name="LIMIT")) == set()

def test_micro_pr_hand_computed():
    rows = [_scored({"A"}, {"A"}), _scored({"A", "B"}, {"A"}), _scored(set(), {"C"}), _scored({"D"}, set())]
    r = micro_pr(rows)
    assert (r["tp"], r["fp"], r["fn"]) == (2, 1, 2)
    assert r["precision"] == pytest.approx(2 / 3) and r["recall"] == pytest.approx(2 / 4)

def test_unmapped_target_counts_as_miss():
    s = score_item(GraphIndex(_doc_call()), "C001", _item(kind="call", path="m.py", line=10, col=15),
                   Label("in_repo", ("nowhere.h",)))
    assert s.unmapped == 1 and "unmapped:nowhere.h" in s.truth and s.status == "wrong"

def test_agreement_raw_and_kappa():
    c = {"1": Label("in_repo", (_defn("a.f", 1),)), "2": Label("external", ()), "3": Label("builtin", ()), "4": Label("in_repo", (_defn("a.g", 2),))}
    u = {"1": Label("in_repo", (_defn("a.f", 1),)), "2": Label("external", ()), "3": Label("external", ()), "4": Label("in_repo", (_defn("a.h", 3),))}
    a = agreement(c, u)
    assert a["raw"] == 0.5 and a["disagreements"] == ["3", "4"]
    assert a["kappa"] == pytest.approx((0.75 - 0.375) / (1 - 0.375))   # on cls: 3/4 observed, expected 0.375
    assert agreement({"1": Label("unknown", ())}, {"1": Label("unknown", ())})["kappa"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q -k "callsite or same_name or name_targets or micro_pr or unmapped or agreement_raw"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement the Task 3 interfaces in `src/vgar/evaluation/g1_labels.py`**

`status`: `no_callsite` (calls only, CallSite not found); `no_edge` (predicted empty, truth non-empty); `right` (predicted == truth, non-empty); `partial` (overlap but not equal); `wrong` (no overlap, predicted non-empty, or truth empty with predicted non-empty).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q`
Expected: 19 passed

- [ ] **Step 5: Hand-off** — no commit. Files: `src/vgar/evaluation/g1_labels.py`, `tests/test_g1_labels.py`.

---

### Task 4: Label kit script and labelling guide

**Files:**
- Create: `scripts/g1_label_kit.py`
- Create: `docs/status/g1_labelling_guide.md`
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Consumes: `scan_repository`, `sample_items`, `write_sheet`, `write_items_md`, `agreement_ids`, `write_agreement_sheet`, `lock`, `sha256_file` (Tasks 1–2); `read_repository_sources(row, cache_root, network=True)` (`vgar.evaluation.retrieval.dataset`), `extract_python_tree(archive_path, repo, commit, destination)` (`vgar.evaluation.retrieval.graph_arm`).
- Produces:
  - CLI: `python scripts/g1_label_kit.py --root ~/rt1 --manifest <gold manifest> --out <dir> [--calls 150] [--names 150] [--seed 0] [--offline]`; `python scripts/g1_label_kit.py --out <dir> --lock`
  - `select_tasks(rows: list[dict]) -> list[dict]` — first task per `repo` in manifest order
  - `<out>/manifest.json`: `{"manifest", "manifest_hash", "seed", "tasks": [{"task_id", "repo", "base_commit", "archive", "archive_sha256", "tree"}], "stats": {repo: scan stats}, "sheets": {"calls.csv": sha256, "name_uses.csv": sha256, "agreement_user.csv": sha256}, "agreement_ids": [...], "locks": []}`
  - `<out>/items.json`: every sampled `Item` (dataclass → dict) by `item_id`, read back by the evaluator and by `--lock`

- [ ] **Step 1: Write the failing test**

```python
def test_select_tasks_first_per_repository():
    rows = [{"repo": "a/x", "instance_id": "1"}, {"repo": "b/y", "instance_id": "2"}, {"repo": "a/x", "instance_id": "3"}]
    assert [r["instance_id"] for r in kit.select_tasks(rows)] == ["1", "2"]

def test_kit_writes_sheets_from_local_trees(tmp_path, monkeypatch):
    # Two fake repositories already extracted; read_repository_sources/extract_python_tree are monkeypatched to return them.
    out = _run_kit(tmp_path, monkeypatch, calls=4, names=2)
    assert {p.name for p in out.iterdir()} >= {"calls.csv", "name_uses.csv", "items.md", "items.json", "agreement_user.csv", "manifest.json"}
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(read_sheet(out / "calls.csv")) == 4 and manifest["locks"] == [] and "graph" not in (out / "items.md").read_text(encoding="utf-8").lower()
```

`kit` is loaded with `importlib` from `scripts/g1_label_kit.py` (same helper `_load` as `tests/test_measure_layers_options.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q -k "select_tasks or kit_writes"`
Expected: FAIL (`FileNotFoundError` for the script)

- [ ] **Step 3: Implement `scripts/g1_label_kit.py`**

Trees go to `<root>/data/repositories/trees/<owner>__<name>-<base_commit>` (same as R1). `--lock` reads `items.json`, rebuilds `Item`s, calls `lock(out, items)`, prints the hashes. With the default sizes and the dev manifest, print per repository: eligible calls/names and sampled counts.

- [ ] **Step 4: Write `docs/status/g1_labelling_guide.md` (Vietnamese)**

Content: purpose (G1, proposal dòng 1342–1343), who labels (Claude; the user labels `agreement_user.csv` blind), the label grammar, and the rules of the spec "Labelling rules" section with one example each (polymorphic call, `C(...)` → class, `super().m()`, decorated function, attribute set in several methods, `external`/`builtin`, `unknown` for `getattr`/assignment aliases), and the lock/settlement procedure with the exact commands of Tasks 4–5.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q`
Expected: 21 passed

- [ ] **Step 6: Hand-off** — no commit. Files: `scripts/g1_label_kit.py`, `docs/status/g1_labelling_guide.md`, `tests/test_g1_labels.py`.

---

### Task 5: Evaluator script and report

**Files:**
- Create: `scripts/g1_evaluate.py`
- Test: `tests/test_g1_labels.py`

**Interfaces:**
- Consumes: `check_lock`, `read_sheet`, `parse_label`, `agreement`, `GraphIndex`, `score_item`, `micro_pr` (Tasks 2–3); `PythonGraphBuilder(repo_key=..., repository_revision=..., **LayerConfigs(...).builder_kwargs())`; `add_layer_options`, `layers_from_args`, `layer_summary`, `scip_config` (`vgar.graph.layer_config`).
- Produces:
  - CLI: `python scripts/g1_evaluate.py --kit <dir> --out <dir> [--tsg-executable P --tsg-tree-sitter-dir P] [--enable-jarvis] [--scip-entry P --scip-node node]`
  - Configurations: `static` (always); `tsg` (when tsg options given); `tsg_jarvis` (tsg + `--enable-jarvis`); `scip_tsg` (tsg + `--scip-entry`, built with `scip_config(entry, node=..., timeout=600, strict=False, environment=None, native_config=False, import_roots=(), target_only=None, python=None)`). Configurations not run are listed with the reason.
  - Flow, in order: (1) `check_lock` for both sheets, else exit 2; (2) archive hashes in `manifest.json` equal `sha256_file` of the archives, else exit 2; (3) if `agreement_user.csv` has any label: compute `agreement`; if disagreements exist and `<kit>/settlement.csv` (`item_id`, `final_label`) does not cover all of them, write `<kit>/disagreements.csv` (`item_id`, `code`, `candidates`, `claude_label`, `user_label`, `final_label` empty) and exit 3 with a message; (4) final labels = Claude's with settlement overrides; (5) build each configuration per repository (tree from manifest), score items, write `<out>/g1_report.json` and `<out>/g1_report.md`.
  - Report content per configuration: calls `CALLS` and `CALLS ∪ MAY_CALL` (`micro_pr`), name uses all and "expressible" (items whose true targets are all `global`/`field` Definitions), status counts, items labelled `external`/`builtin` with a graph target, unmapped true targets, per-repository TP/FP/FN, `graph_version` and `layer_summary` per repository; agreement block, with the SHA-256 of `settlement.csv` and the list of items whose label it changed (this is the recorded history of post-lock label changes the spec asks for; the locked sheets themselves are never edited); the sentence "Labels assigned by Claude; 30 items also labelled blind by the user." at the top of `g1_report.md`.

- [ ] **Step 1: Write the failing tests**

```python
def test_evaluator_refuses_unlocked_or_edited_sheets(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch)
    _fill(kit_dir / "calls.csv", {"C001": "unknown"})
    assert ev.main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 2

def test_evaluator_stops_for_unsettled_disagreements(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="disagree")
    assert ev.main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 3
    assert (kit_dir / "disagreements.csv").exists()

def test_evaluator_static_report_on_fixture(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="agree")
    assert ev.main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 0
    report = json.loads((tmp_path / "o" / "g1_report.json").read_text(encoding="utf-8"))
    assert report["configurations"]["static"]["calls"]["calls_only"]["n"] == 2
    assert report["configurations"]["tsg"]["status"] == "not run: no --tsg-executable"
    assert (tmp_path / "o" / "g1_report.md").read_text(encoding="utf-8").startswith("# G1") and "Labels assigned by Claude" in (tmp_path / "o" / "g1_report.md").read_text(encoding="utf-8")
```

`_locked_kit` runs the kit (Task 4 test helper) on a one-repository fixture with two calls whose targets the static resolver can resolve, fills Claude's labels, optionally fills `agreement_user.csv`, and locks.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py -q -k evaluator`
Expected: FAIL (`FileNotFoundError` for the script)

- [ ] **Step 3: Implement `scripts/g1_evaluate.py` with `main(argv: list[str] | None = None) -> int`**

- [ ] **Step 4: Run tests to verify they pass, then the related suites**

Run: `.venv/Scripts/python.exe -m pytest tests/test_g1_labels.py tests/test_measure_layers_options.py -q`
Expected: all passed (24 in `test_g1_labels.py`)

- [ ] **Step 5: Real kit run (WSL, archives cached in `~/rt1`)**

Run (after `rsync` of the repo to `~/vgar-rt1`):
`cd ~/vgar-rt1 && ~/.vgar-wsl/bin/python scripts/g1_label_kit.py --root ~/rt1 --manifest ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/g1`
Expected: 12 tasks, 150 rows in `calls.csv` and in `name_uses.csv`, 30 rows in `agreement_user.csv`, `unparsed_files` listed per repository.

- [ ] **Step 6: Hand-off** — no commit. Files: `scripts/g1_evaluate.py`, `tests/test_g1_labels.py`. Next (outside this plan): Claude labels `~/rt1/g1` in batches of ~50, `--lock`, user labels `agreement_user.csv`, then the evaluator.
