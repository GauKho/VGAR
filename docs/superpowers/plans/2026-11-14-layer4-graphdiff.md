# Layer 4 GraphDiff (without UTango) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a pinned first-parent commit window into validated graph edits (L4-2, L4-4 fixes, L4-5, L4-6), ship the L4-7 labelling kit and GD1 evaluator, and add the GraphDiff history option to the R1 retrieval runner.

**Architecture:** `ast_diff` (fixed) gives symbol edits per file; `refactorings.py` gives step [1] refactorings from RefactoringMiner JSON (live or precomputed) with the `ast` exact-body detector as fallback; `graphdiff.py` maps both onto `PythonGraphBuilder` node ids, types each edit, scores confidence and the `validated` flag, and computes the raw-diff baseline. Scripts wrap it (CLI, label kit, evaluator); the R1 runner gets `--history {none,raw,graphdiff}`.

**Tech Stack:** Python 3.11, stdlib `ast`/`difflib`, dulwich 1.2.18 (extra `history`), optional RefactoringMiner 3.2.0 (Java, run by the user), pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-layer4-graphdiff-design.md` (read it; section numbers below refer to it).

## Global Constraints

- L4-3 / step [2] is out of scope: `is_tangled_risk` is always `null`, `tangle_risk` is `null`, `w3 = 0`.
- No GumTree, no MCP tool/resource, no graph schema change, no change to retrieval defaults, Python only.
- History via dulwich only (no `git` subprocess); never read a commit after the snapshot revision.
- No test starts Java. Code must work from precomputed RefactoringMiner JSON.
- Never drop a commit, file or edit silently: parse errors and RefactoringMiner failures are counted in the summary and named in `evidence`.
- Default weights `w1=0.3, w2=0.2, w3=0, w4=0.25, w5=0.25`, `τ=0.5`, held in a config object.
- `validated = not is_refactoring and edit_type != "UPDATE_DOCSTRING" and not in_test_file`.
- Every summary records RefactoringMiner version (or `null`) and `sys.version`.
- Env settings are absolute paths: `VGAR_REFACTORINGMINER_HOME`, `VGAR_JAVA_HOME`, `VGAR_REFACTORINGMINER_OUTPUT`.
- MCP build rules (memory): no stdout in library code, `logger = logging.getLogger(__name__)` per module, docstrings with `Args:`.
- The user commits; no task runs `git commit`. Each task ends with its file list.
- Existing tests stay green (known failures unchanged).

## Review Focus

1. A commit that deletes or adds a whole `.py` file: every definition is `REMOVE_SYMBOL`/`ADD_SYMBOL`, the raw baseline covers it, no crash on `before=None`. → Task 3 test `test_whole_file_added_and_removed`.
2. A file that is not UTF-8 / not parseable on one side only: the file gets `parse_error`, the commit's other files still give edits, the raw baseline still lists the file's module (text diff with `errors="replace"`). → Task 1 test + Task 3 test `test_raw_baseline_on_unparsable_file`.
3. RefactoringMiner JSON with Windows backslash paths or a location in a file the window commit did not change: the path is normalised; locations outside changed files are ignored, not mapped to `<module>`. → Task 2 test `test_rm_paths_normalised_and_foreign_files_ignored`.
4. Duplicate qualified names (two `def f` in one module, setter/deleter accessors): the edit maps to the first builder node (`node_id` without `@definition` suffix) and `node_in_snapshot` is computed on that id. → Task 3 test `test_duplicate_definition_maps_to_first_node`.
5. A window shorter than requested (repository root commit reached): the run reports the actual commit count, no error. → Task 4 test `test_window_stops_at_root_commit`.

---

### Task 1: L4-4 fixes in `ast_diff`

**Files:**
- Modify: `src/vgar/graph/ast_diff.py`
- Test: `tests/test_python_ast_diff.py` (extend)

**Interfaces:**
- Produces:
  - `SymbolEdit.changed_parts` may now contain `"docstring"`; `DefinitionSpan.kind` may be `"global"` (start/end of the first assignment of the name on that side).
  - `PythonFileDiff.parse_error: ParseError | None = None` with `@dataclass(frozen=True) class ParseError: side: Literal["before","after"]; message: str`; when set, `ast_diff = PythonAstDiff((), False)`.
  - `diff_python_ast` unchanged signature, still raises `SyntaxError`.
  - New helper used by Task 2/3: `read_python_blobs(repo_root, commit) -> dict[str, tuple[bytes | None, bytes | None]]` keyed by after path (before path for removals), regular `.py` blobs only. `diff_python_commit` uses it.

- [ ] **Step 1: Write failing tests**

```python
def test_docstring_only_change_is_its_own_part():
    before = b'def f():\n    """Old."""\n    return 1\n'
    edit, = diff_python_ast(before, before.replace(b"Old.", b"New.")).edits
    assert (edit.symbol, edit.change, edit.changed_parts) == ("f", "MODIFIED", ("docstring",))

def test_docstring_and_code_change_is_body():
    before = b'class C:\n    """Old."""\n    x = 1\n'
    edit, = diff_python_ast(before, b'class C:\n    """New."""\n    x = 2\n').edits
    assert edit.changed_parts == ("body",)

def test_module_docstring_change_is_not_module_statement():
    result = diff_python_ast(b'"""A."""\nimport os\n', b'"""B."""\nimport os\n')
    assert result.edits == () and not result.module_statements_changed  # module docstring: no entity, not a code change

def test_module_constant_change_is_a_global_edit():
    result = diff_python_ast(b"LIMIT = 1\nimport os\n", b"LIMIT = 2\nNEW: int = 3\nimport os\n")
    assert [(e.symbol, e.change, e.before[0].kind if e.before else e.after[0].kind) for e in result.edits] == \
        [("LIMIT", "MODIFIED", "global"), ("NEW", "ADDED", "global")]
    assert not result.module_statements_changed

def test_tuple_or_attribute_targets_stay_module_statements():
    result = diff_python_ast(b"a, b = 1, 2\n", b"a, b = 1, 3\n")
    assert result.edits == () and result.module_statements_changed

def test_parse_error_in_one_file_keeps_other_files(tmp_path):  # dulwich repo with py2 file + good file
    ...  # build with the helper used in tests/test_commit_history.py; commit {"old.py": b"print 'x'\n", "good.py": change}
    diffs = {d.after.path: d for d in diff_python_commit(repo, commit)}
    assert diffs["old.py"].parse_error.side == "after" and diffs["old.py"].ast_diff.edits == ()
    assert diffs["good.py"].parse_error is None and diffs["good.py"].ast_diff.edits
```

- [ ] **Step 2:** `pytest tests/test_python_ast_diff.py -q` → new tests FAIL.
- [ ] **Step 3: Implement.** Docstring = first body statement that is `Expr(Constant(str))`; split it off before computing `body` for functions and classes (class `_statements`/`_order` skip it too) and compare it separately → `"docstring"` part only when the rest is equal; if both differ the part is `"body"` only. Module docstring is dropped from module statements (no entity; spec gives no module docstring edit type — note this in the docstring). Globals: module-level `Assign` with all targets `ast.Name`, and `AnnAssign` with `Name` target; collect per name the list of `ast.dump(node)` (dump of value+annotation, without positions), compare lists like definitions; remove these statements from module `_statements`/`_order`. Parse errors: in `diff_python_commit`, `try: diff_python_ast(...) except SyntaxError as exc:` → decide side by parsing each blob alone; `ValueError` from null bytes is treated the same.
- [ ] **Step 4:** `pytest tests/test_python_ast_diff.py tests/test_commit_history.py -q` → PASS (old tests unchanged).
- [ ] **Step 5:** File list: `src/vgar/graph/ast_diff.py`, `tests/test_python_ast_diff.py`.

### Task 2: L4-2 refactoring detection (`refactorings.py`)

**Files:**
- Create: `src/vgar/graph/refactorings.py`
- Create: `tests/fixtures/graphdiff/rm/` (two RM JSON outputs copied from `%TEMP%/vgar-graphdiff-bench/out/rm/` — one rename_method, one move_class — trimmed to the needed fields; plus a 3-line `stderr.txt` with a parse warning)
- Test: `tests/test_refactorings.py`

**Interfaces:**
- Consumes: `read_python_blobs`, `CommitChange` (Task 1, `history.py`).
- Produces:

```python
@dataclass(frozen=True)
class SymbolRef: path: str; name: str          # name = ast qualified name without module ("Class.method")

@dataclass(frozen=True)
class Refactoring:
    detector: Literal["refactoringminer", "ast"]
    type: str; family: str                      # families of spec §3; "other" for unknown types
    before: tuple[SymbolRef, ...]; after: tuple[SymbolRef, ...]
    involved: frozenset[SymbolRef]              # before+after plus members of renamed/moved classes
    renames: Mapping[str, str]                  # new short name -> old short name
    description: str; tool_version: str | None

@dataclass(frozen=True)
class CommitRefactorings:
    commit_id: str
    detector: Literal["refactoringminer", "ast"]
    refactorings: tuple[Refactoring, ...]
    ast_refactorings: tuple[Refactoring, ...]   # always computed (needed for algorithm_agreement)
    fallback_reason: str | None                 # "not configured" | "process failed: ..." | "no output for commit"
    parse_warnings: tuple[str, ...]

@dataclass(frozen=True)
class RefactoringMinerConfig:
    home: Path | None = None; java_home: Path | None = None; output: Path | None = None
    timeout_seconds: int = 3600
    @classmethod
    def from_env(cls) -> "RefactoringMinerConfig"   # reads the three VGAR_* vars; relative path -> ValueError

def ast_refactorings(blobs: Mapping[str, tuple[bytes | None, bytes | None]]) -> tuple[Refactoring, ...]
def parse_refactoringminer_json(data: dict, blobs_by_commit: Mapping[str, Mapping[str, tuple[bytes|None, bytes|None]]],
                                tool_version: str | None) -> dict[str, tuple[Refactoring, ...]]
def detect_refactorings(repo_root: Path, history: CommitHistory, blobs_by_commit: ..., config: RefactoringMinerConfig
                        ) -> dict[str, CommitRefactorings]
```

- [ ] **Step 1: Write failing tests**
  - `test_ast_detector_rename_function` (same file, exact body, new name → family `rename_method`, `renames == {"new": "old"}`).
  - `test_ast_detector_move_function_across_files` → `move_method`.
  - `test_ast_detector_class_rename_carries_members` → one Refactoring (`rename_class`), `involved` contains `C.m` on both sides, no separate method refactoring.
  - `test_rm_json_rename_method_fixture` and `test_rm_json_move_class_fixture`: parse fixtures with blobs from the matching bench files (inline the two small before/after sources in the test) → expected family, before/after SymbolRef.
  - `test_rm_paths_normalised_and_foreign_files_ignored` (Review Focus 3).
  - `test_window_alignment_drops_non_window_commits_and_counts_missing`: RM JSON lists commits X (not in window) and A; window has A, B → result keys A, B; B has `detector == "ast"`, `fallback_reason == "no output for commit"`.
  - `test_fallback_when_not_configured` → every commit `detector == "ast"`, reason `"not configured"`.
  - `test_fallback_when_process_fails` (monkeypatch `subprocess.run` to return code 1) → reason starts with `"process failed"`.
  - `test_parse_warning_captured` (stderr fixture line naming commit A) → `parse_warnings` on A only.
  - `test_relative_env_path_rejected`.
- [ ] **Step 2:** `pytest tests/test_refactorings.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement.** Port `ast_refactorings`, `family_of` (FAMILIES table) and the location rule of `rm_refactorings` from `scripts/graphdiff_bench/evaluate.py:155-255`, working on `blobs` instead of the bench `Commit`; RM old/new name choice by description order as in `evaluate.py:244`. Live mode: `[java_home/bin/java(.exe), "-classpath", str(home/"lib"/"*"), "org.refactoringminer.RefactoringMiner", "-bc", repo, start, end, "-json", out_file]` once per window, `start` = first parent of the oldest window commit (verify inclusivity on a three-commit repository in a manual check and write the finding in the module docstring; if the oldest commit is the root, use `-c` per commit for it). Precomputed layout: `<output>/<end_commit>.json` (whole window) or `<output>/<commit>.json` (one commit), optional `<output>/metadata.json` `{"tool_version": ...}` and `<output>/<name>.stderr.txt`. Version from jar name `RefactoringMiner-*.jar` in `home/lib`. Parse warnings: stderr lines containing a window commit id. Log, never print.
- [ ] **Step 4:** `pytest tests/test_refactorings.py -q` → PASS.
- [ ] **Step 5:** File list: `src/vgar/graph/refactorings.py`, `tests/test_refactorings.py`, `tests/fixtures/graphdiff/rm/*`.

### Task 3: L4-5 graph edits, node ids and raw-diff baseline

**Files:**
- Modify: `src/vgar/graph/builder.py` (extract `_module_name` body to module-level `module_name_for(relative_path: str, source_roots: tuple[str, ...], repository_name: str) -> str`; the method calls it — no behaviour change; `_is_test_path` stays the shared test rule, called as `PythonGraphBuilder._is_test_path`)
- Create: `src/vgar/graph/graphdiff.py`
- Test: `tests/test_graphdiff.py`

**Interfaces:**
- Consumes: Task 1 (`PythonFileDiff`, `read_python_blobs`), Task 2 (`CommitRefactorings`, `Refactoring`).
- Produces:

```python
@dataclass(frozen=True)
class SnapshotIndex:                      # built once from the graph document
    repo_key: str; revision: str; source_roots: tuple[str, ...]; repository_name: str
    by_symbol: Mapping[tuple[str, str], tuple[str, str]]   # (path, graph qualified_name) -> (node_id, type); first node wins
    node_ids: frozenset[str]
    tests_of: Mapping[str, frozenset[str]]                 # node_id -> paths of test files with TESTS edge to it
    test_imports: Mapping[str, frozenset[str]]             # module qualified name -> test file paths importing it
    @classmethod
    def from_document(cls, document: dict, *, source_roots=("src",), repository_name: str) -> "SnapshotIndex"

@dataclass
class GraphEdit:  # fields exactly as spec §4 table, plus `high_confidence: bool`; to_json() -> dict
    ...

def type_commit_edits(commit: CommitChange, files: tuple[PythonFileDiff, ...], refs: CommitRefactorings,
                      blobs: Mapping[str, tuple[bytes|None, bytes|None]], index: SnapshotIndex) -> list[GraphEdit]
    # confidence fields left at defaults here; Task 4 fills them
def raw_diff_entities(commit: CommitChange, blobs: ..., index: SnapshotIndex) -> list[dict]
    # each: {"commit_id","path","entity","node_id","in_test_file"}
```

Node id rule: graph qualified name = `module_name_for(path, ...) + "." + ast_symbol` (module itself: just the module name). Kind: `class` for class, `test` when the short name starts with `test_`, parent is module or class and `_is_test_path(path)`, else `method` if the parent is a class else `function`; `globalvariable` for globals; `module` for module statements. Look up `(path, qualified_name)` in `index.by_symbol` first (exact builder id, handles accessors/duplicates); otherwise build `vgar:{repo_key}:python:{kind}:{path}:{qualified_name}` and `node_in_snapshot=False`. `node_type` from the index when found, else from kind.

- [ ] **Step 1: Write failing tests** (fixture repo built in `tmp_path` with dulwich; graph built with `PythonGraphBuilder(repo_key="fx", repository_revision=<head>, source_roots=("src",)).build(root)`):
  - one test per row of the spec §4 `edit_type` table: `test_edit_type_add_remove`, `..._rename`, `..._move`, `..._extract` (RM fixture with extract family on an ADDED symbol), `..._inline`, `..._signature`, `..._method_body`, `..._class_body`, `..._docstring`, `..._global`, `..._module_statements`.
  - `test_rename_is_one_edit_on_after_node_with_counterpart`.
  - `test_node_ids_equal_builder_ids` (every edit with `node_in_snapshot` True has `node_id in {n["id"] for n in document["nodes"]}`; an edit on a symbol present at head maps to True).
  - `test_symbol_removed_before_snapshot_is_not_in_snapshot`.
  - `test_in_test_file_uses_builder_rule` (`tests/test_x.py` and `pkg/tests/helpers.py` → True).
  - `test_whole_file_added_and_removed` (Review Focus 1).
  - `test_duplicate_definition_maps_to_first_node` (Review Focus 4).
  - `test_raw_baseline_includes_comment_and_docstring_hunks` (comment-only edit in a function → entity listed; hunk outside definitions → module listed).
  - `test_raw_baseline_on_unparsable_file` (Review Focus 2).
  - `test_module_name_for_matches_builder` (`src/pkg/__init__.py` → `pkg`, root `__init__.py` → repository name).
- [ ] **Step 2:** `pytest tests/test_graphdiff.py -q` → FAIL.
- [ ] **Step 3: Implement.** Rule R for `is_refactoring`: the edit's `(path, ast_symbol)` is in some `refactoring.involved` on its side, or (MODIFIED with both sides) its after segment with `renames` applied (word-boundary replace, `evaluate.py:rename_tokens`) parses to the same `ast.dump` as the before segment. The refactoring that explains it goes in `refactoring` (`{"type","family","description","counterpart"}`). Pairing for RENAME/MOVE: the ADDED edit whose SymbolRef is in a rename/move refactoring's `after` becomes the single edit; the matching REMOVED edit is not emitted separately (counterpart recorded). EXTRACT on ADDED / INLINE on REMOVED only when the symbol is in that refactoring's after / before. Rename/move/extract/inline edits have `is_refactoring=True`. Raw baseline: `difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes()` non-equal hunks; map hunk lines to innermost definition span on the matching side (spans from `ast` when parseable; module only when not).
- [ ] **Step 4:** `pytest tests/test_graphdiff.py tests/test_python_ast_diff.py -q` and the builder suite `pytest tests -q -k builder` → PASS.
- [ ] **Step 5:** File list: `src/vgar/graph/builder.py`, `src/vgar/graph/graphdiff.py`, `tests/test_graphdiff.py`.

### Task 4: L4-6 confidence, validation and `run_graphdiff`

**Files:**
- Modify: `src/vgar/graph/graphdiff.py`
- Test: `tests/test_graphdiff.py` (extend)

**Interfaces:**
- Consumes: Tasks 1–3, `read_commit_history`.
- Produces:

```python
@dataclass(frozen=True)
class ConfidenceConfig:
    weights: Mapping[str, float] = {"algorithm_agreement": 0.3, "semantic_coherence": 0.2, "tangle_risk": 0.0,
                                    "test_relevance": 0.25, "trace_relevance": 0.25}   # via field(default_factory)
    threshold: float = 0.5

@dataclass(frozen=True)
class GraphDiffResult:
    edits: tuple[GraphEdit, ...]; raw_baseline: tuple[dict, ...]; summary: dict

def score_edit(edit: GraphEdit, commit: CommitChange, refs: CommitRefactorings, index: SnapshotIndex,
               config: ConfidenceConfig) -> None   # fills confidence_terms, confidence, validated, high_confidence
def run_graphdiff(repo_root: Path, document: dict, *, max_commits: int, source_roots=("src",),
                  rm_config: RefactoringMinerConfig | None = None, config: ConfidenceConfig | None = None
                  ) -> GraphDiffResult
```

`run_graphdiff` reads the window with `revision=document["repository_revision"]` (never later), and `summary` holds: `revision`, `history_label`, `commits_requested`, `commits_read`, `commits_per_detector`, `refactoringminer_fallbacks` (reason → count), `parse_errors` (list of `{commit, path, side, message}`), `edits_total`, `edits_validated`, `edits_high_confidence`, `raw_baseline_entities` (production code only), `weights`, `threshold`, `refactoringminer_version`, `python_version`.

- [ ] **Step 1: Write failing tests**
  - `test_algorithm_agreement_null_without_rm_and_scored_with_rm` (same verdict → 1.0, different → 0.0).
  - `test_semantic_coherence_values` (pure refactoring 1.0; untouched 1.0; refactoring + extra change 0.5; module statements 0.5).
  - `test_test_relevance_levels` (TESTS edge / import → 1.0; other test file in commit → 0.5; none → 0.0).
  - `test_trace_relevance_levels` (subject "Fix apply_discount rounding" → 1.0 on `apply_discount` and on `Cart.apply_discount`; subject naming only the module part → 0.5; else 0.0; tokens <3 chars ignored). Use `vgar.evaluation.retrieval.bm25.tokenize` for splitting.
  - `test_confidence_normalises_over_non_null_terms` (agreement null, coherence 1, test 0, trace 1 → (0.2+0.25)/(0.2+0.25+0.25) ≈ 0.6429).
  - `test_validated_and_high_confidence_rule` (refactoring/docstring/test-file edits not validated; validated with confidence 0.4 → `high_confidence` False).
  - `test_no_edit_dropped` (edit count == count of ast symbol edits after rename pairing, including refactoring and docstring edits).
  - `test_history_ends_at_snapshot_revision` (repo with a commit after the graph revision; its changes never appear).
  - `test_window_stops_at_root_commit` (Review Focus 5).
  - `test_is_tangled_risk_always_null`.
  - `test_summary_counts_parse_errors_and_fallbacks`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement** per spec §5 table and formulas (no extra terms).
- [ ] **Step 4:** `pytest tests/test_graphdiff.py -q` → PASS.
- [ ] **Step 5:** File list: `src/vgar/graph/graphdiff.py`, `tests/test_graphdiff.py`.

### Task 5: CLI `scripts/graphdiff.py`

**Files:**
- Create: `scripts/graphdiff.py`
- Test: `tests/test_graphdiff_cli.py`

**Interfaces:**
- Consumes: `run_graphdiff`, `RefactoringMinerConfig`.
- Produces: `main(argv) -> int`; options `repo` (path), `--graph PATH` (graph JSON, or SQLite DB read with the existing loader used by `sqlite_service`), `--build` (build the graph at `--revision` from a dulwich-exported tree instead; optional, skip if the existing scripts already provide a build helper — reuse it), `--max-commits N` (default 50), `--source-root` (repeatable, default `src`), `--rm-home`, `--java-home`, `--rm-output` (override env), `--out DIR` (default `results/graphdiff/<repo_name>-<revision[:12]>/`). Writes `graph_edits.jsonl`, `raw_baseline.jsonl`, `summary.json`. Output under `results/` (already git-ignored? check `.gitignore`; if not, keep the default but mention it).

- [ ] **Step 1:** `test_cli_writes_three_files` on the Task 3 fixture repo (graph JSON written by the test) → files exist, `summary.json["commits_read"] > 0`, one JSON object per line.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (argparse, logging to stderr; final one-line JSON summary on stdout is fine for a script). **Step 4:** PASS.
- [ ] **Step 5:** File list: `scripts/graphdiff.py`, `tests/test_graphdiff_cli.py`.

### Task 6: L4-7 labelling kit and guide

**Files:**
- Create: `scripts/graphdiff_label_kit.py`
- Create: `docs/status/graphdiff_labelling_guide.md`
- Test: `tests/test_graphdiff_label_kit.py`

**Interfaces:**
- Consumes: `read_commit_history`, `read_python_blobs`, `raw_diff_entities`, `SnapshotIndex`.
- Produces: `sample_commits(windows: Mapping[str, CommitHistory], *, target=100, fix_share=(0.6, 0.7), seed=0) -> list[dict]` and `write_sheet(rows, path: Path) -> None` (CSV, UTF-8 with BOM for Excel, columns exactly: `row_id, split, repo, commit, subject, path, entity, node_id, before_code, after_code, diff_link, label, annotator, note`). CLI: `--manifest` (R1 manifest), `--git-root DIR` (local clones `DIR/<owner>__<name>`, full history; the R1 runner works on archives without history, so clones are a user step documented in the guide), `--window 50`, `--seed`, `--out DIR` → `sheet.csv`, `sample.json` (seed, manifest hash, commit list, split per commit, skipped repos with reason). The sheet never contains GraphDiff predictions.

Rules: commits from first-parent windows ending at each task's `base_commit`; exclude merges (`len(parent_ids) > 1`) and commits with >10 changed `.py` files or 0; strata 1 / 2–3 / 4–10 by changed `.py` count; fix subject = regex `\b(fix|bug|issue|error)` (case-insensitive) with 60–70% of the target; rows = raw baseline entities with `in_test_file False`; split by commit, seeded, 40% `dev` / 60% `eval`; `diff_link` = `https://github.com/<repo>/commit/<sha>`.

- [ ] **Step 1: Tests:** `test_sample_is_seeded_and_reproducible`, `test_sample_excludes_merges_and_large_commits`, `test_fix_share_within_bounds` (synthetic windows with 300 commits), `test_split_is_by_commit_and_40_60` (±1 commit), `test_sheet_has_no_prediction_columns`, `test_missing_clone_is_reported_not_silent`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Guide** (`graphdiff_labelling_guide.md`, Vietnamese like other status docs): the four [P] labels with one Python example each (docstring/comment → formatting; logging or feature unrelated to the subject → unrelated; behaviour-preserving restructure → refactor), `unsure` rule, double labels on ≥20% of commits for Cohen's κ, how to clone the repositories in WSL, the exact commands for kit → `scripts/graphdiff.py` → evaluator, and the manual live RefactoringMiner command (`java -classpath "<home>/lib/*" org.refactoringminer.RefactoringMiner -bc <repo> <start> <end> -json <file>`). Note GD1 numbers exist only after labelling; bench numbers are synthetic and are not GD1.
- [ ] **Step 6:** File list: `scripts/graphdiff_label_kit.py`, `docs/status/graphdiff_labelling_guide.md`, `tests/test_graphdiff_label_kit.py`.

### Task 7: GD1 evaluator `scripts/evaluate_graphdiff.py`

**Files:**
- Create: `scripts/evaluate_graphdiff.py`
- Test: `tests/test_evaluate_graphdiff.py`

**Interfaces:**
- Consumes: labelled `sheet.csv` (Task 6), `graph_edits.jsonl` from a normal run and from an `ast`-only run (approach C: same CLI without RM settings) per repo/revision.
- Produces: `evaluate(rows: list[dict], predictions: Mapping[str, set[tuple[str, str]]], *, split="eval") -> dict` where `predictions` maps arm name (`graphdiff`, `graphdiff_high_confidence`, `ast_only`, `raw_baseline`) to the set of `(commit, node_id)` predicted positive. Report per arm: P, R, F1, retention (= predicted positives / baseline rows), predicted-negative counts by noise label, plus `unsure` count, parse errors and commits without RefactoringMiner (from the runs' `summary.json`), Cohen's κ over double-labelled rows (rows sharing `row_id` with two annotators), the command line and versions. CLI writes `gd1.json` and `gd1.md`. Refuses `--split dev` output named as GD1 (prints "development split, not GD1" in the report title).

- [ ] **Step 1: Tests:** hand-made 10-row sheet with known answers: `test_prf_and_retention_known_values` (e.g. 4 bug-fix, prediction hits 3 of 4 with 1 FP → P 0.75, R 0.75, F1 0.75, retention 0.4), `test_raw_baseline_has_recall_one`, `test_unsure_rows_excluded_and_counted`, `test_kappa_on_double_labels` (known κ for a 2×2 table, e.g. agree 8/10 with marginals 5/5 → κ = 0.6), `test_only_eval_split_by_default`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** File list: `scripts/evaluate_graphdiff.py`, `tests/test_evaluate_graphdiff.py`.

### Task 8: Downstream on retrieval (R1 runner `--history`)

**Files:**
- Modify: `ablation_matrix/retrieval_variants.py` (`variant_outputs(..., change_counts: Mapping[str, float] | None = None, history_label: str | None = None)` passed to `GraphContextRetriever`)
- Modify: `ablation_matrix/run_r1_ablation.py`
- Test: `tests/test_r1_history_option.py`

**Interfaces:**
- Consumes: `read_commit_history`, `run_graphdiff`.
- Produces: options `--history {none,raw,graphdiff}` (default `none`, so existing runs are unchanged), `--git-root DIR` (required unless `none`), `--history-commits 50`. With `raw`/`graphdiff` only the `task_trace` arm runs (`arms=("task_trace",)`, text arms skipped) and each task JSON records `history: {mode, label, commits_read, keys}`; a task whose clone is missing or lacks `base_commit` is `FAILED` with `error_class` `HistoryUnavailable` (counted, not silent). `graphdiff` counts = per node id, number of window commits with ≥1 `validated` edit on it; label `graphdiff:v1:<history_label>`. Separate `--out` folders per mode; `summarize` works unchanged. Add a pair-free helper `compare_history_runs(none_dir, raw_dir, graphdiff_dir) -> dict` (file/function recall@k and MRR means, paired deltas vs `none` with `_bootstrap`) and a `compare-history` subcommand or separate small function invoked by `python ablation_matrix/run_r1_ablation.py --compare-history A B C`.

- [ ] **Step 1: Tests:** `test_history_none_keeps_default_arms` (parse args only), `test_graphdiff_counts_are_validated_commits_per_node` (unit on a fake `GraphDiffResult`), `test_missing_clone_marks_task_failed`, `test_compare_history_runs_known_deltas` (three tmp dirs with two hand-written task JSONs each).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Full suite `pytest tests -q` → only the known failures from memory.
- [ ] **Step 6:** The real run is a user step in WSL (heavy repositories; Java for RM is optional — without it the `ast` detector runs and the summary says so). Write the commands into `docs/status/graphdiff_labelling_guide.md` § downstream.
- [ ] **Step 7:** File list: `ablation_matrix/retrieval_variants.py`, `ablation_matrix/run_r1_ablation.py`, `tests/test_r1_history_option.py`, guide.

## Not done by this plan (user / people steps)

- Cloning the R1 repositories with full history (WSL), labelling the sheet, live RefactoringMiner runs, the real R1 history run. GD1 numbers appear only after these.
