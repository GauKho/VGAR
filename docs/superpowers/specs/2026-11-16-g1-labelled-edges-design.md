# G1: hand-labelled call edges and name uses on real repositories (16/11/2026)

## Sources

- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`: §13.2 Graph quality (lines 1341–1347:
  "symbol resolution precision/recall", "call edge precision/recall"), §6.2 step 3 symbol resolution (lines 476–478),
  §8.3 conditions (lines 835–841: "graph edge recall đủ cao", "graph edge precision không quá thấp")
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`: week 2 day 2 TV2 (G1), result G1 (§5),
  §7 conditions, O7 ("proposal không nêu cỡ mẫu cạnh gán nhãn tay"), A.3 [rq] row "Graph quality: Cạnh gán nhãn tay"
- Decisions in the conversation of 16/11 (user): 150 call sites + 150 name uses; labelling form C (blind, with
  same-name candidates); "symbol resolution" means option B (non-call name uses). The user first chose to label
  alone, then asked Claude to label. The agreement check below is Claude's proposal; the user has not yet answered
  its size (30 items).

## Problem

G1 has trace link P/R (TR-1) and incremental update correctness (U1). Call edge P/R exists only on the
hand-written fixture repository (`tests/fixtures/vgar-callgraph-cases`, `# expect:` checked by running); symbol
resolution P/R has never been measured. [rq] asks for hand-labelled edges, and the team needs both numbers for
the first two §8.3 conditions.

What the graph records today (checked on `vgar-demo-shop`, 16/11):

| Relation | Graph representation | Who decides the target |
|---|---|---|
| call | `CallSite → Function/Method/Class`: `CALLS` (`python.call.static.resolve.v1`, or SCIP/LSP/JARVIS when on), `MAY_CALL` (`python.call.may_call.name.v1`, heuristic) | resolver |
| import | `Import → Module` (`python.import.resolve.v1`); the imported name is a property, never an edge | table lookup, exact by construction |
| name read | `Function/Method → GlobalVariable/Field` (`REFERENCES`, `python.layer1.reads.v1`), only with tree-sitter-graph | Layer 1 facts |

The graph keeps no per-occurrence link from a name to its definition. Option B therefore measures what the graph
can express for non-call name uses (reads of globals and fields) and counts everything it cannot express
(callbacks, classes used in `isinstance` or annotations, module-level aliases) as a miss.

## Goals

1. A labelling kit that samples 150 call sites and 150 non-call name uses from the dev repositories and writes a
   sheet the labeller fills in without seeing the graph's answer.
1a. The labeller is **Claude** (a model), not a human. Every report and slide calls these labels "labels assigned
   by Claude", never "hand labels". To make them citable, the user labels a blind random subset of 30 items
   (15 calls + 15 name uses) independently; the report gives raw agreement and Cohen's kappa, and the user settles
   every disagreement. Final labels = Claude's, with the user's decision on each disagreement.
2. An evaluator that builds the graph for the same checkouts, matches every labelled item to the graph and reports
   call edge P/R and name-use ("symbol resolution") P/R with 95 % bootstrap intervals.
3. A labelling guide in Vietnamese so the labels are consistent and the method can be cited.

## Non-goals

- No change to the graph builder, resolvers or retrieval. Mistakes the labels reveal are reported, not fixed here.
- No component boundary quality (needs architecture labels and a sample-size decision, [plan] O7) and no import P/R
  (option A was not chosen).
- No second full labelling: only the 30-item agreement subset is labelled twice.
- No development/evaluation split: nothing is tuned on these labels.

## Anti-goals (would make the result unusable even if the code works)

- The sheet reveals the graph's target (directly, by ordering, or by marking a candidate).
- Items are sampled from the graph's own edges or filtered by whether the graph resolved them (biases recall).
- Candidates come from graph edges instead of the repository's definition table.

## Approaches considered

| | Form | Trade-off |
|---|---|---|
| A | Fully blind: code only, labeller searches the repository | unbiased, slowest; 300 items likely exceed 8 hours |
| B | Show the graph's target, mark right/wrong, add misses | fastest; anchoring raises both P and R; easy for a committee to attack |
| **C (chosen)** | Blind, with every repository definition of the same name listed as candidates (file:line), taken from the definition table, not from graph edges | almost as fast as B, unbiased like A |

## Design

### Task and checkout selection

- Manifest `~/rt1/data/manifests/w10-dev-50-gold.json` (the R1 dev set). One task per repository: the first task of
  each of the 12 repositories in manifest order. Checkout = that task's `base_commit`, read with the R1 helpers
  (`read_repository_sources`, `extract_python_tree`), so the archive and tree are the ones R1 used.
- Production code only: files R1 treats as source (`is_source`), no tests, no `conftest.py`, no `setup.py`/`docs/`.

### Enumerating items (independent of the graph)

Items are enumerated with Python's `ast` and `symtable` on the checkout, never from graph nodes.

- **Call item:** every `ast.Call` inside a function or method body, or at module/class level.
- **Name-use item:** every `ast.Name` or `ast.Attribute` in load context that is **not** the `func` of an
  `ast.Call`, inside a function or method body, and whose name is not a local or parameter of the enclosing
  function according to `symtable` (attributes are always kept: `self.x`, `obj.field`, `module.CONST`).
- **Candidate set:** every definition in the checkout whose simple name equals the item's name: functions,
  methods, classes, module-level assignments (globals) and class/instance attributes (`self.x = …` in any method
  and class-body assignments). If the name is an import alias in the enclosing module (`from a import b as c`),
  candidates are looked up under the original name `b`. Each candidate is shown as `qualified name — path:line`.
- **Eligible items:** those with at least one candidate. A true in-repository target must share the simple name
  (or the aliased original), so dropping items without candidates loses no in-repository target. Aliasing through
  assignment (`f = obj.method; f()`), `getattr` with a string and similar dynamic forms are the exception; the guide
  tells the labeller to mark them `unknown` when no candidate fits.

### Sampling

- Seeded (`--seed 0`) and stratified **evenly by repository**: 150 / 12 → 12 or 13 items per repository for each
  kind (the remainder goes to the repositories with the most eligible items). Within a repository: uniform over
  eligible items. Even allocation keeps one large repository (sympy, django) from dominating; the report gives
  both the pooled result and per-repository counts.
- Uniform within the repository, not stratified by resolution status, so P and R are unbiased estimates for the
  repository's eligible population.

### The sheet

One CSV per kind (`calls.csv`, `name_uses.csv`), UTF-8, plus `items.md` that shows each item with context, because
code does not read well inside a CSV cell.

| Column | Content |
|---|---|
| `item_id` | `C001…C150` / `N001…N150`, in a shuffled order (not grouped by repository) |
| `repo`, `task_id`, `path`, `line`, `col` | location |
| `code` | the item's source line |
| `candidates` | numbered list `1) qname — path:line; 2) …`, sorted by qualified name (never by graph confidence) |
| `label` | filled by the labeller: candidate numbers separated by `;` (several allowed for polymorphic calls), or one of `external`, `builtin`, `unknown`, `other:<qualified name>` |
| `note` | free text |

`items.md` repeats each item with 7 lines of context (3 before, 3 after, item line marked) and the candidate list.
The kit also writes `manifest.json`: tasks, base commits, archive hashes, seed, item enumeration counts per
repository (eligible / sampled), and a hash of each sheet as written (to detect edits to fixed columns).

### Who labels, and the lock

- Claude labels all 300 items from `items.md` (code and candidates only). No graph is built before the labels are
  locked, so Claude never sees the graph's answer.
- Lock: when the sheets are complete, `g1_label_kit.py --lock` writes the SHA-256 of each filled sheet into
  `manifest.json`. `g1_evaluate.py` refuses a sheet whose hash differs from the locked one, and the graph is built
  only after the lock. Changing a label after the lock needs a new lock entry recorded in the manifest (history is
  appended, never overwritten), used only for the user's settling of disagreements.
- Agreement subset: the kit draws 15 calls + 15 name uses at random (seed 1, independent of the sampling seed) and
  writes `agreement_user.csv` with the same columns and an empty `label`, in a different shuffled order. Claude's
  labels for these items are not in that file. The user fills it in blind, then the evaluator compares item by item:
  two labels agree when their sets of chosen candidates are equal (`external`/`builtin`/`unknown` compare as their
  class). Reported: raw agreement, Cohen's kappa on the label class (in-repo / external / builtin / unknown) and,
  for in-repo items, whether the target sets are equal. A listing of every disagreement goes to the user, who writes
  the final label; those final labels replace Claude's for those items before the graph is evaluated.
- Anything else (sampling, enumeration, candidates) is identical to the user-labelled design above.

### Labelling rules (guide summary; full text in the guide)

- Label the target the code reaches at run time for normal inputs. Polymorphic call on a base type: list every
  in-repository override that a caller in this repository can reach; if this cannot be decided from the code, label
  the declared method and write `polymorphic` in `note`.
- Class instantiation `C(...)`: the class (as the graph does), not `__init__`.
- `super().m()`: the method in the nearest base that defines `m`.
- Decorated functions: the decorated definition.
- Name use of an attribute set in several places (`self.x` assigned in `__init__` and in `reset`): the attribute
  candidate(s), not the assignment lines.
- Anything outside the checkout: `external` (third party) or `builtin` (Python builtins and standard library).

### Matching the graph (evaluator)

The evaluator builds the graph per configuration from the same tree and matches:

- **Call item → CallSite:** the `CallSite` node in the same file whose range starts at the item's `line:col`
  (the call expression start; `ast` `col_offset` and tree-sitter columns are both 0-based UTF-8 byte offsets on a
  1-based line). No CallSite at that position counts as "graph has no call site" (all true targets missed).
- **Graph targets of a call:** `CALLS` targets (set G), and separately `CALLS ∪ MAY_CALL` (set G′).
- **Enclosing node:** the innermost graph `Function`/`Method` node whose range contains the item (a nested `def`
  the graph does not model is attributed to the function the graph uses for that line, as the builder does).
- **Name-use item → graph targets:** the `REFERENCES` edges whose source is the enclosing Function/Method node and
  whose `rule_id` is `python.layer1.reads.v1`, restricted to targets with the item's simple name (an enclosing
  function reads many names; the restriction keeps only the edges that could be this item).
- **True targets T:** the labelled candidates mapped to graph node ids by qualified name and path. `other:<qname>`
  is mapped the same way. `external`, `builtin`, `unknown` give T = ∅.

### Metrics

Micro-averaged over items, per kind and configuration:

- precision = Σ|G ∩ T| / Σ|G|, recall = Σ|G ∩ T| / Σ|T| (items with T = ∅ count only in precision: any graph target
  there is a false positive).
- For calls: P/R for `CALLS` and for `CALLS ∪ MAY_CALL`; count of items labelled `external`/`builtin` that the graph
  linked to a repository node.
- 95 % interval by bootstrap over items (2,000 resamples, seed 7, same as R1).
- Per-repository table of TP/FP/FN (not P/R per repository: 12–13 items are too few).
- Item counts by label class (in-repo, external, builtin, unknown) and by graph status (no call site, no edge,
  edge right, edge wrong).

### Configurations evaluated

| Configuration | Calls | Name uses |
|---|---|---|
| `static` (the served default) | yes | — (no reads without Layer 1) |
| `static + tsg` | yes | yes (main name-use number) |
| `static + tsg + jarvis` | yes | yes |
| `scip + tsg` | yes, only if the SCIP runtime is installed where the evaluator runs; otherwise recorded as not run | yes |

Graphs are built with `cache=False`; the report records `graph_version` per repository and configuration, and the
evaluator refuses a sheet whose `manifest.json` tasks or archive hashes differ from the checkouts it built.

### Files

| Path | Role |
|---|---|
| `scripts/g1_label_kit.py` | enumerate, sample, write `calls.csv`, `name_uses.csv`, `items.md`, `agreement_user.csv`, `manifest.json` into `--out`; `--lock` records sheet hashes |
| `scripts/g1_evaluate.py` | read the filled sheets, build graphs per configuration, write `g1_report.json` and `g1_report.md` |
| `src/vgar/evaluation/g1_labels.py` | enumeration, candidate table, sampling, matching and metrics (testable without the network) |
| `docs/status/g1_labelling_guide.md` | labelling guide (Vietnamese) |
| `tests/test_g1_labels.py` | tests below |

### Tests (on small in-repository fixtures; no network, no Docker)

- Enumeration: calls and name uses found at the right `line:col`; locals and parameters excluded; the call's
  `func` is not a name-use item; alias lookup uses the original name.
- Candidates come from definitions only: a fixture where the graph has a wrong `CALLS` edge still shows every
  same-name definition, sorted by qualified name.
- The sheet contains no graph target (no graph is built by the kit at all).
- Sampling: deterministic for a seed; even allocation with the stated remainder rule.
- Matching: CallSite found by position; missing CallSite counted as a miss; `MAY_CALL` only in G′.
- Metrics: hand-computed P/R on a tiny labelled fixture, including T = ∅ items and multi-target labels.
- Evaluator refuses a sheet whose manifest does not match the checkout, and a sheet whose hash differs from the lock.
- Agreement: subset is reproducible for its seed, disjoint columns hide Claude's labels, and raw agreement and
  Cohen's kappa match a hand-computed example (including a class with no items).

### Cost

Labelling: Claude labels 300 items in several sessions of about 50 items (reading `items.md`); the user spends
about 1 hour on the 30-item agreement subset and the disagreement list. Kit: minutes (archives are cached in
`~/rt1`).
Evaluator: one graph per repository and configuration on 12 repositories; with JARVIS (Docker) the R1 full-layer
run suggests tens of minutes in total.

## Limitations to state in the report

- **Update 16/11:** the user asked Claude to fill the 30-item agreement sheet too, so the agreement figures measure Claude's self-consistency across two passes, not agreement with a human. The report must say so. The user still settles every disagreement.

- The labels are assigned by a model, not by a human; 30 of 300 items (10 %) were also labelled by the user blind.
  Agreement on a 30-item subset has a wide interval; the report gives it with its sample size and does not claim
  more. Disagreements are settled by the user, so the final labels on that subset are human-checked and the
  other 270 are model-assigned.
- The labeller (Claude) and the code under test are not independent in one respect: both were written with the same
  kind of model. The lock only prevents label-by-graph-answer leakage, not shared blind spots.
- Name uses that the graph has no edge type for (callbacks, `isinstance`, annotations) lower recall by design;
  the report splits recall into "expressible by the graph (globals and fields)" and "all name uses".
- Even allocation weights small repositories more than their share of code; the pooled number is per-item, not
  per-line of code.
- 12 tasks, one revision per repository; dev set only.

## Left to the builder

- Exact column order and `items.md` layout, within the content above.
- How qualified names of candidates are computed (reuse the builder's naming so they map to graph node ids).
