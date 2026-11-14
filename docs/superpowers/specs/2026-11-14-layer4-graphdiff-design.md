# Layer 4 GraphDiff without the tangled-change step (14/11/2026)

## Sources

- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`, rows L4-1 … L4-7 (lines 139–145), GD1 (line 186), M4 (line 201)
- **[bench]** `docs/status/graphdiff_ast_vs_proposal_tools_2026-11-14.md` and `scripts/graphdiff_bench/` (68 synthetic shopflow commits, 14/11)
- **[RM-acc]** RefactoringMiner `documentation/accuracy.md#python-benchmark` (read 14/11/2026)

Plans and results of the 16-week schedule are not sources for this change.

## What the proposal asks for

| [P] line | Section | Text / requirement |
|---|---|---|
| 52 | §1 | GraphDiff: "lọc nhiễu commit history để lấy graph edits đáng tin hơn cho phân tích và evaluation" |
| 377–380 | §5.2 Layer 4 | GumTree / DAT-GumTree, RefactoringMiner, UTango-style tangled commit detector |
| 406 | §5.3 | RefactoringMiner: "tách refactor khỏi bug fix"; not "mọi ngôn ngữ/mọi refactor" |
| 682–696 | §7.2 | input: commit diff; output: validated graph edits with confidence and provenance; example fields `edit_type`, `entity`, `is_refactoring`, `is_tangled_risk`, `confidence`, `evidence` |
| 701–722 | §7.3 | [1] detect refactoring (RefactoringMiner) → [2] detect tangled changes → [3] AST diff ("GumTree / DAT-GumTree / RefactoringMiner AST diff") → [4] AST edits to graph edits → [5] score confidence |
| 727–741 | §7.4 | `confidence = w1·algorithm_agreement + w2·semantic_coherence + w3·(1 − tangle_risk) + w4·test_relevance + w5·trace_relevance` |
| 745–751 | §7.5 | no multiplicative noise formula |
| 753–760 | §7.5 | manual-label protocol: labels bug-fix / refactor / formatting / unrelated; P/R/F1; retention rate; downstream impact on retrieval/repair |
| 1436–1438 | §14 M4 | deliverables: RefactoringMiner/GumTree integration, validated graph edit format, manual-label evaluation dataset |
| 1444–1445 | §14 M4 | success: "higher precision graph edits than raw diff"; "demonstrate downstream benefit or document failure cases" |

[P] gives no weights, no threshold for "validated", and only one `edit_type` (`UPDATE_METHOD_BODY`). Every such value below is the team's choice and is marked so.

## Current state in the repository

| Plan row | Code | State |
|---|---|---|
| L4-1 commit history | `src/vgar/graph/history.py` (`read_commit_history`, dulwich, first parent from a pinned SHA, `change_counts` per path) | done |
| L4-2 refactoring detection | only in `scripts/graphdiff_bench/evaluate.py` (`ast_refactorings`, `rm_refactorings`) | bench code |
| L4-3 tangled changes | none | **out of scope here** |
| L4-4 AST diff | `src/vgar/graph/ast_diff.py` (`diff_python_ast`, `diff_python_commit`) | done, three weaknesses (below) |
| L4-5 graph edits | none | to do |
| L4-6 confidence | none | to do |
| L4-7 manual labels | none (bench labels are synthetic) | to do |
| downstream | `GraphContextRetriever` reads `change_counts` keyed by node id first, then path (`retrieval.py:305`); `ablation_matrix/run_r1_ablation.py` passes no history | to do |

`ast_diff` weaknesses measured on 14/11 with direct calls of `diff_python_ast`:
1. a docstring text edit is reported as `MODIFIED body` (a documentation edit counted as a code change);
2. a module-level constant change only sets `module_statements_changed`, with no entity;
3. a file that does not parse (Python 2 syntax, newer syntax) raises `SyntaxError` for the whole commit.

## Scope

In scope: L4-2, fixes to L4-4, L4-5, L4-6, L4-7 (tooling and protocol), and the downstream measurement of [P] line 760 on retrieval.

Out of scope:
- **L4-3 / step [2]** (UTango-style tangled detection). The official UTANGO release (`Commit-Untangling/commit-untangling`) covers C# and Java only and ships no parser; a Python port would be a GNN model, which [P] line 16 and line 1485 removed from the core. `is_tangled_risk` stays in the output with value `null`, and `w3` is 0 until a later change adds step [2].
- GumTree (see Approaches).
- An MCP tool or resource for GraphDiff: [P] §10.2–10.3 list none, and GraphDiff works on history, not on the agent's patch.
- Languages other than Python ([plan] §1.1).
- Repair downstream measurement: [P] line 760 says "retrieval/repair"; this change measures retrieval only, because retrieval is the one existing consumer of history (`recent_change_frequency`).

## Goals, non-goals, anti-goals

Goals:
1. One call turns a pinned first-parent commit window into graph edits with the six [P] §7.2 fields plus provenance.
2. RefactoringMiner is the step [1] detector when configured; without Java the pipeline still runs with the `ast` detector and says so in every edit's evidence.
3. Each edit's entity is the id of the node that `PythonGraphBuilder` builds for that symbol.
4. A labelling kit lets people label real commits with the four [P] labels, and one script turns the labels into GD1: P/R/F1, retention, against the raw-diff baseline.
5. One retrieval experiment compares no history, raw history and GraphDiff history on the R1 task set.

Non-goals: step [2]; GumTree; MCP exposure; changing retrieval defaults; graph schema changes (graph edits are output records, not graph nodes).

Anti-goals (a failure even if the code runs):
- reading any commit after the snapshot revision (history must end at the graph's own revision, as `sqlite_service._history` does today);
- reporting a GraphDiff precision from synthetic data as if it were GD1;
- tuning weights or the threshold on the evaluation labels and then reporting on the same labels;
- silently dropping a commit or file that failed (parse error, RefactoringMiner error): every failure is counted and reported.

## Approaches

| | A. `ast` + RefactoringMiner (chosen) | B. GumTree + RefactoringMiner | C. `ast` only |
|---|---|---|---|
| Step [1] | RefactoringMiner, `ast` exact-body pairs as fallback | RefactoringMiner | `ast` exact-body pairs |
| Step [3] | `ast` | GumTree (tree-sitter) | `ast` |
| Bug-fix isolation F1 on [bench] | **0.94** | 0.81 | 0.86 |
| FP from formatting on [bench] | **0** | 26 (comments, quote style) | 0 |
| Refactoring recall on [bench] | 0.94 | 0.94 | 0.59 (misses extract, inline, rename parameter/variable) |
| Mapping to graph nodes | direct (qualified name) | character offsets → enclosing symbol (extra step) | direct |
| Speed (30 real commits) | `ast` 30 s + RM 165 s once per window | 249 s + 165 s | 30 s |
| [P] fit | step [1] as listed; step [3] lists "RefactoringMiner AST diff" as an alternative, and M4 asks for "RefactoringMiner/GumTree integration" | exactly as listed | step [1] tool missing |

Decided in the conversation of 14/11: A. Reasons: the user's rule is to follow [P] unless another tool is measurably better and still logical for GraphDiff; [bench] shows A ≥ B at symbol level, and the only difference is formatting noise that `ast` cannot see by construction. [RM-acc] gives RefactoringMiner an official Python benchmark (PyRef dataset, 203 commits, 3 projects, P 0.997, R 0.998, as of 13/11/2026). `ast` is the Python standard library, not a parser written from scratch ([P] §5.1). Limits that stay true: [bench] is synthetic; GumTree with comment and quote filtering would probably tie with `ast` at symbol level (not measured); GumTree's statement-level actions are finer than `ast_diff`'s declaration/body split.

RefactoringMiner AST diff is **not** used: its command-line support for AST diff on Python was not checked. `algorithm_agreement` is computed between the two step [1] detectors instead (below).

How RefactoringMiner runs (my call, correct me): the pipeline supports two modes, chosen by configuration.
- **live**: the pipeline starts `java -classpath <home>/lib/* org.refactoringminer.RefactoringMiner -bc <repo> <start> <end> -json <file>` once for the whole window (one JVM, 0.06 s/commit amortised on [bench]). `RefactoringMiner.bat` is not used: its class path exceeds the `cmd.exe` line limit.
- **precomputed**: the pipeline reads JSON files that someone produced earlier with the same command (needed because Java tools are run by the user, and because WSL runs the heavy repositories).

## Design

### 1. Files

| File | Content |
|---|---|
| `src/vgar/graph/ast_diff.py` | L4-4 fixes (section 2) |
| `src/vgar/graph/refactorings.py` | L4-2: `Refactoring` record, `ast` detector (ported from `evaluate.py`), RefactoringMiner adapter (live and precomputed), location → symbol mapping |
| `src/vgar/graph/graphdiff.py` | L4-5 and L4-6: `GraphEdit`, raw-diff baseline, edit typing, node id mapping, confidence, `run_graphdiff(...)` |
| `scripts/graphdiff.py` | CLI: repository, revision, window size, graph JSON/DB, RefactoringMiner mode → `graph_edits.jsonl` + `summary.json` |
| `scripts/graphdiff_label_kit.py` | L4-7: sample commits, write the labelling sheet |
| `scripts/evaluate_graphdiff.py` | GD1 from a labelled sheet |
| `docs/status/graphdiff_labelling_guide.md` | instructions for annotators |
| tests | `tests/test_python_ast_diff.py` (extended), `tests/test_refactorings.py`, `tests/test_graphdiff.py`, `tests/test_evaluate_graphdiff.py` |

`pyproject.toml` extra `history` (dulwich 1.2.18) already exists and stays the only new runtime dependency. RefactoringMiner is optional and external.

### 2. L4-4 fixes in `ast_diff`

1. **Docstrings.** The first statement of a module, class or function body that is a string constant is compared on its own. A change only there gives `changed_parts = ("docstring",)`; a change in the rest gives `"body"` as today. Graph typing maps docstring-only edits to `UPDATE_DOCSTRING` (section 4), which counts as a formatting edit.
2. **Module-level names.** For each module-level `Assign`/`AnnAssign` whose targets are plain names, the diff emits a `SymbolEdit` with kind `global` and the name as symbol (`ADDED`/`REMOVED`/`MODIFIED`). `module_statements_changed` stays for every other module statement.
3. **Parse errors.** `diff_python_commit` catches `SyntaxError` per file and returns that file with `parse_error` set (message and side) and no edits; the other files of the commit still diff. `diff_python_ast` itself keeps raising, so existing callers are unchanged.

### 3. L4-2 refactoring detection

`Refactoring` record: `detector` (`refactoringminer` or `ast`), `type` as the detector names it, `family` (rename_method, rename_class, move_method, move_class, extract_method, inline_method, rename_parameter, rename_variable, other), `before` and `after` symbols (path + qualified name, either may be empty), `renames` (new short name → old short name), `description`, `tool_version`.

- **`ast` detector**: exact-body pairs of `ADDED` and `REMOVED` definitions within the commit, with members of a paired class following their class (same rules as `evaluate.py:177`).
- **RefactoringMiner adapter**: parses the `-json` output; maps each left/right location to the enclosing `ast` definition of the before/after file (the rule in `evaluate.py:215`, including members of renamed or moved classes); takes `tool_version` from the jar name of the configured home or from the precomputed folder's metadata. Lines RefactoringMiner prints on standard error about parse errors are kept per commit; a commit with such lines gets `refactoringminer_parse_warning` in its evidence ([RM-acc] notes that unparsable commits can give wrong refactorings).
- **Window alignment** (my call): `-bc` walks every commit in the range, merged branches included, while `history.py` walks first parents. The adapter keeps only RefactoringMiner results whose commit id is in the dulwich window and ignores the rest; a window commit with no RefactoringMiner result falls back to `ast` and is counted.
- **Availability**: if RefactoringMiner is not configured, fails, or has no output for a commit, that commit uses the `ast` detector and every edit of the commit records `refactoring_detector: ast` and the reason. The summary counts commits per detector.

Configuration (environment, absolute paths, like the other `VGAR_*` settings): `VGAR_REFACTORINGMINER_HOME` (unzipped release folder, contains `lib/`), `VGAR_JAVA_HOME`, `VGAR_REFACTORINGMINER_OUTPUT` (folder of precomputed JSON, one file per window or per commit). The CLI accepts the same values as options.

### 4. L4-5 graph edits

One `GraphEdit` per changed entity per commit:

| Field | Meaning |
|---|---|
| `commit_id`, `path` | commit and repository-relative path (after side, or before side for removals) |
| `edit_type` | from the table below |
| `entity` | qualified name as the graph writes it (`module.Class.method`) |
| `node_id` | `vgar:{repo_key}:python:{kind}:{path}:{qualified_name}`, the scheme of `PythonGraphBuilder`; the module name comes from the builder's own `_module_name` rule (shared, not copied), so source roots match |
| `node_type` | Function, Method, Class, Test, GlobalVariable, Module |
| `in_test_file` | the path is a test file by the builder's own test-path rule (the rule that makes `Test` nodes, `builder.py:746`); such edits stay in the output, feed `test_relevance`, and are excluded from `validated`, the labelling sheet and GD1 (my call: the four [P] labels describe production-code edits, and fix commits nearly always touch tests, which would swamp the sheet) |
| `node_in_snapshot` | whether `node_id` exists in the snapshot graph given to the run (old commits may touch symbols that no longer exist) |
| `before`, `after` | line spans |
| `is_refactoring` | true when the edit is fully explained by a detected refactoring (section 5, rule R) |
| `refactoring` | the explaining `Refactoring` (type, family, description, counterpart symbol) or null |
| `is_tangled_risk` | `null` (step [2] not implemented) |
| `confidence`, `confidence_terms` | section 5 |
| `evidence` | list of strings naming each source: `ast`, `refactoringminer <version>`, `refactoringminer unavailable: <reason>`, `test touched: <path>`, `message mentions: <token>`, `parse error: <path>` |
| `validated` | section 5 |

`edit_type` vocabulary (team's choice; [P] gives only `UPDATE_METHOD_BODY`):

| `ast` change and parts | Refactoring involved | `edit_type` |
|---|---|---|
| ADDED / REMOVED | none | `ADD_SYMBOL` / `REMOVE_SYMBOL` |
| ADDED + REMOVED pair | rename family | `RENAME_SYMBOL` (one edit, on the after node, counterpart in `refactoring`) |
| ADDED + REMOVED pair | move family | `MOVE_SYMBOL` |
| ADDED | extract family | `EXTRACT_SYMBOL` |
| REMOVED | inline family | `INLINE_SYMBOL` |
| MODIFIED declaration | none | `UPDATE_SIGNATURE` |
| MODIFIED body, function/method | none | `UPDATE_METHOD_BODY` |
| MODIFIED body, class | none | `UPDATE_CLASS_BODY` |
| MODIFIED docstring only | — | `UPDATE_DOCSTRING` |
| global ADDED/REMOVED/MODIFIED | — | `ADD_GLOBAL` / `REMOVE_GLOBAL` / `UPDATE_GLOBAL` |
| module statements changed | — | `UPDATE_MODULE_STATEMENTS` (entity = module node) |

When the snapshot has no `GlobalVariable` node (they exist only when the graph was built with tree-sitter-graph), `UPDATE_GLOBAL` keeps the global's would-be id and `node_in_snapshot` is false.

**Raw-diff baseline** ([P] line 1444: "higher precision … than raw diff"): every definition whose line span overlaps a changed text hunk (`difflib` over the before/after blobs, either side), plus the module when a hunk lies outside all definitions. Formatting-only hunks, comments and docstrings all count, because a raw diff cannot tell them apart. The run writes the baseline set next to the graph edits so that L4-7 labels both.

### 5. L4-6 confidence and validation

Terms, each in [0, 1] or `null` when it cannot be computed:

| Term | Definition |
|---|---|
| `algorithm_agreement` | RefactoringMiner ran for the commit: 1.0 if both detectors give the same verdict on whether the entity is part of a refactoring, 0.0 if they differ. RefactoringMiner did not run: `null`. |
| `semantic_coherence` | 1.0 when the edit is either fully explained by one refactoring or touched by none; 0.5 when the entity is part of a refactoring and still has changes beyond renamed references (rule R); 0.5 for `UPDATE_MODULE_STATEMENTS` (no entity-level evidence). |
| `tangle_risk` | `null` (step [2] out of scope) |
| `test_relevance` | 1.0 if the commit changes a test file that, in the snapshot graph, has a `TESTS` edge to the node or imports the node's module; 0.5 if the commit changes any test file; 0.0 otherwise. |
| `trace_relevance` | 1.0 if a token of the commit subject equals the entity's short name or one of its identifier parts (snake/camel split, length ≥ 3); 0.5 if it matches a module or path part; 0.0 otherwise. `history.py` stores only the subject today; the body may be added if needed. |

Rule R (from `evaluate.py`, "drop symbols whose change is only the renamed references"): an edit is fully explained by a refactoring when the entity is one of the refactoring's symbols, or when its before and after bodies are equal after applying the refactoring's renames.

`confidence = Σ w_i · term_i / Σ w_i` over the non-null terms, with default weights `w1 = 0.3, w2 = 0.2, w3 = 0, w4 = 0.25, w5 = 0.25` (team's choice; normalisation over available terms follows the retrieval scorer). `algorithm_agreement` is `null` (not 0) when only the `ast` detector ran, so a missing Java does not lower the score.

`validated` is the noise filter and does not depend on confidence (my call, after the builder check: with a threshold, a plain bug-fix body edit scored 0.53 with RefactoringMiner and 0.29 without, so the verdict would mostly say whether Java ran):

`validated = not is_refactoring and edit_type not in {UPDATE_DOCSTRING} and not in_test_file`

`confidence` is a ranking score reported next to it. A second flag `high_confidence = validated and confidence ≥ τ` (default `τ = 0.5`, team's choice) is reported, and GD1 shows both. Weights and τ come from a config object; they may be tuned on the L4-7 development split only (section 6).

`run_graphdiff` never drops an edit: refactoring, docstring and low-confidence edits stay in the output with `validated = false`, because [P] §7.2 asks for labelled edits and the consumer decides.

### 6. L4-7 labelling kit and GD1

Sample (team's choice, correct me): repositories of the R1 task set (the 50 SWE-bench Python dev tasks of the manifest given to `ablation_matrix/run_r1_ablation.py`), first-parent windows ending at each task's base commit (never after it). From all windows, draw commits stratified by number of changed Python files (1, 2–3, 4–10), excluding merges and commits with more than 10 Python files; target 100 commits, of which 60–70 have a subject matching fix/bug/issue/error so that bug-fix edits are well represented. Seeded and recorded so that the sample can be rebuilt.

Sheet: one row per raw-diff baseline entity (section 4), columns: commit, subject, path, entity, before/after code of the entity, link to the full commit diff, `label` (bug-fix / refactor / formatting / unrelated / unsure), `annotator`, `note`. GraphDiff's predictions are not in the sheet, so annotators are not influenced. Split by commit into development (40%) and evaluation (60%) before anyone labels.

Guide (`graphdiff_labelling_guide.md`): definitions of the four [P] labels with Python examples (docstring and comment edits are formatting; a logging or feature change unrelated to the subject is unrelated; behaviour-preserving restructuring is refactor), rule for `unsure`, and a request for two annotators on at least 20% of commits for agreement (Cohen's κ).

`evaluate_graphdiff.py` on the evaluation split:
- positives = rows labelled bug-fix; `unsure` rows reported separately and excluded;
- GraphDiff prediction = entity has a validated edit; compare with the raw-diff baseline (every row predicted positive) and with approach C (`ast` detector only);
- outputs P, R, F1, retention rate (= predicted positives / baseline rows), the confusion between predicted negatives and each noise label, counts of parse errors and of commits without RefactoringMiner, κ when double labels exist, and the exact command and versions.

Labelling itself is done by people; this change delivers the kit, the guide and the evaluator. GD1 numbers exist only after labels.

Optional check of step [1] on real Python commits: run the adapter over the PyRef oracle (`src/test/resources/oracle/python-dataset/data.json` in the RefactoringMiner repository) and compare with [RM-acc]. It needs the three oracle repositories cloned; it is not required for M4.

### 7. Downstream on retrieval ([P] line 760)

Add to the R1 runner (`ablation_matrix/run_r1_ablation.py`, run in WSL like the 11/11 R1 matrix) a history option with three values:
- `none` (today's default);
- `raw`: `read_commit_history(...).change_counts` per path;
- `graphdiff`: per node id, the number of commits in the window with at least one validated edit on that node (keys are node ids, which `retrieval.py:305` already reads before the path).

Window: 50 first-parent commits ending at the task's base commit (as `sqlite_service._history`). Arm (my call): only the R1 graph arm with `G_task` (R-A2, `task_trace`), with every retrieval setting unchanged, including the `recent_change_frequency` weight 0.1; running all arms would triple a heavy WSL run, and at weight 0.1 a null result is likely and is read as such. Report gold file and function recall@k and MRR for the three values on the same 50 tasks, with the R1 configuration otherwise unchanged. A null or negative result is reported as such ([P] line 1445: "or document failure cases").

## Tests

- `ast_diff`: docstring-only change → `("docstring",)`; docstring + code → `body`; module constant change → `global MODIFIED`; Python 2 file in a commit → `parse_error` on that file while other files diff.
- refactorings: `ast` detector on rename/move/class-rename fixtures; RefactoringMiner parser on two saved JSON outputs from [bench] (copied as small fixtures); fallback when home is unset or the process fails; parse-warning capture.
- graphdiff: each `edit_type` row; node ids equal those of `PythonGraphBuilder` on a fixture repository (built in the test); `node_in_snapshot`; raw-diff baseline includes comment-only and docstring-only hunks; each confidence term including `null` handling; weights normalisation; no edit dropped; no commit after the snapshot is read.
- evaluator: hand-made sheet with known P/R/F1, retention, `unsure` handling, κ.
- No test starts Java. A live RefactoringMiner run is a manual step documented in the guide.

## Constraints

- Windows and WSL; dulwich only (no `git` subprocess) for history, as `history.py`.
- Java tools are run by the user; the code must work from precomputed output.
- Record RefactoringMiner and Python versions in every summary; `ast` results depend on the running Python's grammar.
- Existing tests stay green; known failures listed in memory are unchanged.

## Left to the builder

- Exact `-bc` boundary semantics (whether the start commit is inclusive) and the precomputed file layout; verify on a three-commit repository.
- How to share `_module_name` with the builder without importing the whole builder (extract a small function if needed).
- Token splitting for `trace_relevance` (reuse grounding's tokenizer if it fits).
- Output file naming under `results/`.
