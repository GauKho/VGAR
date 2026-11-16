# All layers in the served graph, and agent tools that use them (15/11/2026)

## Sources

- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`: §4.3 `G_repo` (lines 205–238), §9.2 context, §9.3 impact (lines 996–1023), §10.3 tools, §11 incremental
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`
- Run reports used as evidence (numbers below are copied from them):
  `tv2_layer1_run_2026-11-08.md`, `tv2_l2_1_jarvis_run_2026-11-10.md`, `tv2_l3_1_g_code_run_2026-11-09.md`,
  `tv2_r1_retrieval_ablation_2026-11-11.md`, `tv2_rt_1_retrieval_run_2026-11-10.md`, `tv2_im_1_impact_run_2026-11-09.md`,
  `w11_w12_post_merge_status_2026-11-04.md` (I1 status)

Plans and results of the 16-week schedule are not sources for this change.

## Problem

The MCP graph server serves the graph that `build_or_update_graph` builds. That path
(`graph_server._live` → `LiveGraphBuilder` → `IncrementalGraphBuilder(repo_key, "cli")` → `PythonGraphBuilder.build`)
passes no layer configuration, and the builder reads none from the environment. The served graph has L1 base
facts, the static resolver, `MAY_CALL` and `G_arch` only. tree-sitter-graph, SCIP, LSP, JARVIS and Joern exist
and are tested, but only scripts use them. The revision is the literal `"cli"`, so history (L4) cannot be read.

Even when present, the extra data is not used by the agent's tools: `retrieval.py`, `impact.py` and
`sqlite_service.py` never mention `GlobalVariable`, `Field`, `ConfigEntry`, `CONFIGURES` or any `G_code` edge.
And the graph has **no edge from a function to a global variable or field it reads**: `Field` and
`GlobalVariable` nodes have only `CONTAINS` from their owner (`builder.py:1750–1770`); `Identifier` nodes are
parameters.

## Evidence from the runs

| Layer | Measured | Consequence for this design |
|---|---|---|
| L2 JARVIS | `CALLS` recall on the labelled fixture 0.237 → 0.441 at precision 1.000; real repos +5–20 % `CALLS`, 1–34 s (Docker) | include in the served build |
| L2 SCIP | xarray: 15,250 calls resolved by SCIP, 29 left to the static resolver | include in the served build |
| L1 tree-sitter-graph | xarray edges 54k → 96k, build 8.8 → 31.7 s (×3.6); `ConfigEntry` rare (xarray: 3), no `Route` | worth it only with a tool that reads it; `CONFIGURES` has little to offer on SWE-bench repositories |
| L3 Joern | xarray build 9.1 → 52.1 s (×5.7), edges ×3; 100 % of functions matched; dataflow check 96.1 % | data quality allows a narrowing use; cost demands a measured benefit |
| Retrieval R1, 50 tasks | function R@5: A2 0.338 vs file-neighbor 0.471; contains-only graph 0.248 > A1 with `CALLS`/`IMPORTS` 0.207; component dependents: no change; `MAY_CALL` 0.5: 0.338 → 0.363 | more traversal edges dilute function ranking: any new retrieval signal is a flag, off by default, kept only if R1 improves; no dataflow in retrieval |
| Impact | accuracy never measured: the I1 table (does the impact region of the gold patch reach the FAIL_TO_PASS tests, against diff-only) has a script and 22 passing tests but no run | measure I1 first; every impact change is a flag compared against that baseline |

## Scope

1. **Build:** the served build uses the layers the host configures (tree-sitter-graph, SCIP, LSP, JARVIS, Joern) and a real revision.
2. **Reader edges:** new `REFERENCES` edges from a function, method or test to the `GlobalVariable` / `Field` it reads or writes (only when tree-sitter-graph made those nodes).
3. **Impact:** two flags, off by default: follow reader edges (A), narrow propagation with Joern dataflow (B).
4. **Context:** one flag, off by default: variables the anchors read, and the other functions that read them.
5. **Measurement:** I1 baseline, then each impact flag; R1 for the context flag.

Out of scope: dataflow in retrieval (evidence against, ×5.7 build cost); `CONFIGURES` in impact or retrieval (no data on the target repositories); LSP inside incremental updates; new MCP tools; changing defaults without a measured gain.

## Goals, non-goals, anti-goals

Goals:
1. With the host's layer settings, `build_or_update_graph` produces the same graph as `scripts/build_graph.py` with the matching options, and says which layers ran.
2. A patch that changes a module constant or a class attribute reports the functions that read it (flag A).
3. A patch whose change cannot leave its function reports a smaller impact region (flag B), without losing FAIL_TO_PASS reach on I1.
4. Each new signal has a measured result (gain, null or loss) written down.

Non-goals: new edge semantics beyond read/write of named variables; interprocedural dataflow; aliasing (`x = obj; x.attr`).

Anti-goals (a failure even if the code runs):
- the default retrieval ranking or the default impact report changes (frozen `RetrievalConfig()` hash `sha256:993f02c9…`; impact default output identical on existing fixtures);
- a layer that failed or is not installed silently disappears (it must be recorded with a reason);
- tuning a flag on the evaluation tasks it is reported on;
- the build tool exceeding its timeout without a clear error.

## Approaches

| | A only | **A + B, flags off by default, I1 first (chosen)** | Rewrite impact/retrieval as CPG queries |
|---|---|---|---|
| Impact | reader edges | reader edges + dataflow narrowing | new engine |
| Context | reader edges | reader edges (no dataflow) | new engine |
| Needs | tree-sitter-graph | + Joern (Docker) for B | everything |
| Risk | low | medium: Joern slow, B unmeasured | high: invalidates R1, IM-1 results |

Decided on 15/11 from the run evidence above: impact gets A and B, context gets A only, every signal behind a flag measured against an I1/R1 baseline. The CPG rewrite is dropped because it discards measured results.

## Design

### 1. Build with configured layers

- `src/vgar/graph/layer_config.py` (new): one function `layer_configs(env) -> LayerConfigs` turning settings into the existing `TsgConfig`, `ScipConfig`, `LspConfig`, `JarvisConfig`, `JoernConfig` (or `None`), with the same meaning as the matching `scripts/build_graph.py` options. `build_graph.py` and the live build both use it (no copied mapping).
- Settings (environment of the graph server, absolute paths, checked by `host_config.py` like the other `VGAR_*`):
  `VGAR_TSG_EXECUTABLE`, `VGAR_TSG_TREE_SITTER_DIR` (existing); `VGAR_SCIP_ENTRY` (+ optional `VGAR_NODE`, `VGAR_SCIP_ENVIRONMENT`, `VGAR_SCIP_TIMEOUT`); `VGAR_LSP_ENTRY` (+ optional `VGAR_LSP_PYTHON`); `VGAR_JARVIS=1` (+ optional image, timeout); `VGAR_JOERN=1` (+ optional image, timeout). Unset means the layer is off.
- `LiveGraphBuilder`: when any of these layers is on, every build and update is a **full** `PythonGraphBuilder` build with the configs (incremental supports the static resolver only); otherwise the current incremental path is unchanged.
- **Revision:** the repository's `HEAD` commit SHA read with dulwich; when the root is not a Git repository, keep `"cli"`. Record `statistics.revision_source` (`git-head` / `none`, or `parent-repo-not-supported` with a warning when a parent folder holds `.git`: history paths would be relative to that parent, so it stays off) and whether tracked files differ from `HEAD` (`statistics.worktree_dirty`; full dulwich status only on a cold build and never writing `.git/index`, an incremental update is dirty once any graphed file changed, so a revert to `HEAD` stays dirty until `HEAD` moves), because history ends at the commit, not at the working tree.
- **Layer report:** `statistics.layers = {name: {"status": "ready" | "off" | "failed", "reason": str | None, "seconds": float}}`. A layer whose tool fails is `failed` with its reason and the build continues without it (the builder already falls back for SCIP/LSP; JARVIS/Joern report status). `build_or_update_graph` returns this map.
- Timeout: `VGAR_GRAPH_BUILD_TIMEOUT_SECONDS` (default 900) unchanged; a timeout is reported as today.

### 2. Reader edges (L1, needs tree-sitter-graph nodes)

`REFERENCES` from `Function` / `Method` / `Test` to `GlobalVariable` / `Field`, `rule_id` `python.layer1.reads.v1`, property `access: "read" | "write" | "read_write"`, confidence 1.0 (`resolution: exact`) or 0.8 (`heuristic`, imported name):
- **global:** a `Name` in the function body whose scope (the builder's `symtable` data) is global, and the module has a `GlobalVariable` of that name → edge to it; a name imported with `from m import X` that resolves (the builder's import table) to a module of the repository with `GlobalVariable` `X` → edge to that node (heuristic);
- **field:** `self.<a>` / `cls.<a>` in a method of class `C` where `C` has `Field` `<a>` → edge to it; inherited fields and other receivers are out of scope.
- One edge per (function, variable), `access` merged. Nested functions belong to their outer function (as in the AST diff).
- Schema: add these endpoints to `REFERENCES` as "proposed, pending team review" ([P] §4.3 `REFERENCES: Entity -> Entity`), like the existing `ConfigEntry` and `Route` additions.
- **Isolation:** retrieval already walks every `REFERENCES` edge (`retrieval.py:500`); edges with this `rule_id` are skipped there unless the context flag (§4) is on, so the default ranking does not change.

### 3. Impact flags (`compute_impact`, `analyze_patch_impact`)

Both off by default; they enter the impact report's config record and the report lists which were on.

- **A `follow_variable_readers`:** when a touched node is a `GlobalVariable` or `Field` (the diff hits its assignment), the functions with a reader edge to it become impacted at hop 1 with relation `READS_CHANGED_VARIABLE`, and the usual reverse walk continues from them within `max_hops`. A touched function that **writes** a variable also impacts that variable's readers (relation `SHARES_STATE`), one hop only.
- **B `narrow_with_dataflow`** (needs `G_code` for the touched function): changed statements = statements of the touched function overlapping the diff's changed lines. Influence = statements reachable from them by following `DATA_DEPENDS_ON` and `CONTROL_DEPENDS_ON` backwards (statements that depend on a changed one), plus the changed ones. If no influenced statement is a `return`/`yield`/`raise`, contains a call site, or stores to an attribute, subscript, global or nonlocal name, the change cannot leave the function: callers are not added; the function itself and its `TESTS` stay. Functions without `G_code`, or any doubt (no statement matched), fall back to the normal walk and are counted (`dataflow_fallbacks`).

[P] §9.3 lists `CALLS`/`IMPORTS` reverse, `TESTS`, `DEPENDS_ON` and ports; A and B are team extensions, reported as such.

### 4. Context flag (`RetrievalConfig.use_variable_references`, off)

When on: for each anchor function, the variables it reads (reader edges) enter as candidates with the assignment's snippet and rationale `READS_VARIABLE`, and up to `variable_co_readers` (default 3) other functions reading the same variable enter with rationale `CO_READER`, at hop 1, scored with the existing features. Off means the edges are invisible to retrieval (§2) and `ranking_config_hash` keeps its frozen value (the RT-1 rule: off values are left out of the hash).

### 5. Measurement

1. **I1 baseline (first, before any impact change):** `scripts/measure_patch_impact.py` on the 25 dev tasks with the current default graph (user runs it in WSL, as R1). Report F2P reach and region size, graph vs diff-only.
2. **I1 with A:** graphs built with tree-sitter-graph (reader edges), `follow_variable_readers=True`.
3. **I1 with A + B:** graphs also with Joern, `narrow_with_dataflow=True`. Report region size change and F2P reach change against 1 and 2, paired per task; Joern coverage and `dataflow_fallbacks`.
4. **R1 with the context flag:** the `task_trace` arm with `use_variable_references` on vs off, the 50 tasks, with tree-sitter-graph graphs.
Both measurement scripts build their own graphs (`evaluation/gold_impact.py` with `PythonGraphBuilder(repo_key=task_id, repository_revision='base')`; the R1 runner through `run_graph_retrieval.load_or_build_graph`). They get the same layer settings (`layer_configs`, as CLI options mirroring `build_graph.py`) and, for I1, the impact flags as options; each output records the layers and flags used.

5. Tier-1 tests on fixtures: `vgar-demo-shop` (`FREE_SHIPPING_FROM` read by `shipping_fee`; `VAT_PERCENT` read by `vat`; a log-only change in a function narrows under B) and the Joern `flow_cases` fixture (recorded output, no Docker in CI).

A flag becomes default only if the user decides so after its measurement; this change ships them off.

## Tests

- `layer_configs`: each variable → config; unset → off; relative path rejected; `build_graph.py` and live build produce equal graphs for the same settings (static + tree-sitter-graph with recorded facts).
- live build: revision is the HEAD SHA in a dulwich fixture repo, `"cli"` outside Git, `worktree_dirty`; `statistics.layers` for ready/off/failed; full build when a layer is on, incremental otherwise.
- reader edges: global read/write, imported global (heuristic), `self.attr` read/write, nested function, no edge without tree-sitter-graph nodes, schema accepts the new endpoints.
- impact: defaults identical on existing fixtures (`test_impact.py` unchanged); A adds readers; writer → readers one hop; B narrows a log-only change, keeps a change that reaches `return`, falls back without `G_code`.
- retrieval: default hash unchanged and default ranking identical with reader edges present; flag adds `READS_VARIABLE` / `CO_READER` candidates.
- No test starts Docker or Java; Joern/JARVIS paths use recorded outputs.

## Constraints

- Windows and WSL; Docker for JARVIS/Joern and Java tools are run by the user.
- MCP rules: no stdout in library code, logger per module, docstrings with `Args:`.
- Existing tests stay green; known failures unchanged. The user commits.

## Left to the builder

- Exact SCIP/LSP setting names for optional extras, matching `build_graph.py` option names.
- How `symtable` distinguishes `global x` writes from module-level reads in nested scopes (follow the builder's existing scope tables).
- Statement kinds that count as "leaving the function": `StatementFact.kind` is the tree-sitter type without `_statement` (`return`, `raise`, `expression`, `global`, …), so calls, `yield` and attribute/subscript stores inside `expression` statements are found from the statement's own source range (call sites it contains, assignment targets), not from the kind alone.
- Whether `worktree_dirty` needs the index or only blob comparison (dulwich).
