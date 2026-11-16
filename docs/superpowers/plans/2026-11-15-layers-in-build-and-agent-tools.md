# All Layers in the Served Graph, and Agent Tools That Use Them — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `build_or_update_graph` builds with the host-configured layers and the HEAD SHA; the graph gets function→variable reader edges; impact (flags A, B) and context (one flag) can use them, all off by default, with measurement hooks for I1 and R1.

**Architecture:** a shared `layer_config.py` turns settings into the existing layer configs for both `scripts/build_graph.py` and `LiveGraphBuilder`; `variable_refs.py` finds reads/writes with `ast` and the builder links them to tree-sitter-graph nodes; Joern statements get an `effects` property; `impact.py` and `retrieval.py` gain gated behaviour; the I1 and R1 scripts take the same settings.

**Tech Stack:** Python 3.11 (`ast`, `symtable`), dulwich, existing builder/impact/retrieval, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-layers-in-build-and-agent-tools-design.md`

## Global Constraints

- Defaults unchanged: `RetrievalConfig()` hash stays `FROZEN_RANKING_HASH` (`sha256:993f02c9…`); default impact output identical on existing fixtures (`tests/test_impact.py`, `tests/test_impact_arch.py`, `tests/test_w10_impact_mcp.py` unchanged); graphs built without tree-sitter-graph/Joern identical to today.
- New layer settings are absolute paths, checked like other `VGAR_*` in `host_config.py`; unset = layer off.
- A layer that fails or is missing is recorded in `statistics.layers` with a reason; never silently dropped.
- Reader edges: `REFERENCES`, `rule_id` `python.layer1.reads.v1`, property `access` ∈ `read`/`write`/`read_write`; confidence 1.0 exact, 0.8 heuristic (imported name); only when tree-sitter-graph created the target nodes.
- Impact flags `follow_variable_readers`, `narrow_with_dataflow`; context flag `use_variable_references` (+ `variable_co_readers` = 3). All `False` by default; new relations `READS_CHANGED_VARIABLE`, `SHARES_STATE`.
- No test starts Docker or Java (JARVIS/Joern/SCIP from recorded outputs or fakes). MCP rules: no stdout, logger per module, `Args:` docstrings. The user commits; tasks end with a file list.

## Review Focus

1. A repository where tree-sitter-graph is configured but fails on one file: other files still get reader edges, `statistics.layers.tsg` says `failed`/partial with the reason, build does not abort. → Task 2 test `test_failed_layer_is_reported_and_build_continues`.
2. A global name shadowed by a local or parameter of the same name (`def f(LIMIT): return LIMIT`): no reader edge. → Task 3 test `test_shadowed_global_is_not_a_read`.
3. A module-level change that is not an assignment to a known global (an `import` line): flag A adds nothing and the report is unchanged. → Task 5 test `test_module_change_without_variable_adds_nothing`.
4. A worktree with uncommitted edits: revision is HEAD's SHA, `worktree_dirty` true, history still ends at HEAD. → Task 2 test `test_dirty_worktree_keeps_head_revision`.
5. `use_variable_references=True` on a graph without reader edges: ranking identical to off. → Task 6 test `test_flag_without_reader_edges_changes_nothing`.

---

### Task 1: `layer_config.py`, shared by `build_graph.py`; host config checks

**Files:**
- Create: `src/vgar/graph/layer_config.py`
- Modify: `scripts/build_graph.py:58-95` (use the shared constructors), `src/vgar/mcp/host_config.py` (graph server: optional absolute paths)
- Test: `tests/test_layer_config.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class LayerConfigs:
    tsg: TsgConfig | None = None; scip: ScipConfig | None = None; lsp: LspConfig | None = None
    jarvis: JarvisConfig | None = None; joern: JoernConfig | None = None
    @property
    def any_optional(self) -> bool            # True when any field is not None
    def builder_kwargs(self) -> dict          # {"tsg": ..., "scip": ..., "lsp": ..., "jarvis": ..., "joern": ...}
def scip_config(entry: Path | None, *, node: str, timeout: float, strict: bool, environment: Path | None,
                native_config: bool, import_roots: tuple[str, ...], target_only: str | None,
                python: Path | None, bundle: Path | None = None) -> ScipConfig
def lsp_config(entry: Path | None, *, node: str, total_timeout: float, request_timeout: float, max_requests: int,
               python: Path | None, import_roots: tuple[str, ...], strict: bool) -> LspConfig
def layer_configs(env: Mapping[str, str]) -> LayerConfigs
def layer_summary(document: dict, configs: LayerConfigs) -> dict[str, dict]
    # {"tsg"|"scip"|"lsp"|"jarvis"|"joern": {"status": "ready"|"off"|"failed", "reason": str|None}}
```
  Env names: `VGAR_TSG_EXECUTABLE`, `VGAR_TSG_TREE_SITTER_DIR`; `VGAR_SCIP_ENTRY`, `VGAR_NODE`, `VGAR_SCIP_ENVIRONMENT`, `VGAR_SCIP_TIMEOUT` (default 120), `VGAR_SCIP_PYTHON`; `VGAR_LSP_ENTRY`, `VGAR_LSP_PYTHON`; `VGAR_JARVIS` (`1` = on), `VGAR_JARVIS_IMAGE`, `VGAR_JARVIS_TIMEOUT` (120); `VGAR_JOERN` (`1`), `VGAR_JOERN_IMAGE`, `VGAR_JOERN_TIMEOUT` (900). Defaults for the rest as `build_graph.py` options (import roots `("src", "lib")`, shim `scripts/scip_windows_compat.cjs`).
  `layer_summary` reads `statistics.resolver` (`status`, `lsp`), `statistics.tsg`, `statistics.code_graph`, `statistics.jarvis`.

- [ ] **Step 1: Tests:** `test_unset_env_gives_no_layers`, `test_each_variable_enables_its_layer`, `test_relative_path_rejected` (ValueError), `test_scip_and_lsp_commands_match_build_graph` (same `command` tuple as the old CLI code for the same inputs), `test_layer_summary_ready_off_failed` (synthetic statistics), `test_host_config_rejects_relative_layer_path` (graph server with `VGAR_TSG_EXECUTABLE=rel` → problem listed).
- [ ] **Step 2–4:** FAIL → implement (move the SCIP/LSP construction out of `build_graph.py` unchanged; `build_graph.py` calls `scip_config`/`lsp_config`) → PASS; `pytest tests/test_layer_config.py tests/mcp_server/test_host_config.py -q`.
- [ ] **Step 5:** File list.

### Task 2: `LiveGraphBuilder` with layers, HEAD revision, layer report

**Files:**
- Modify: `src/vgar/graph/live_build.py`, `src/vgar/mcp/servers/graph_server.py:415-425` (pass `layer_configs(os.environ)`)
- Test: `tests/test_live_build_layers.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `LiveGraphBuilder(root, database, *, timeout_seconds=900, layers: LayerConfigs = LayerConfigs())`; `head_revision(root: Path) -> tuple[str, bool]` (`(sha, dirty)` via dulwich `Repo.head()` and `porcelain.status` staged+unstaged; `("cli", False)` when not a Git repo). Document `statistics` gains `revision_source` (`"git-head"`/`"none"`), `worktree_dirty`, `layers` (`layer_summary`). `run()` result gains `layers` and `revision`.

- [ ] **Step 1: Tests** (dulwich fixture repos via `tests/git_fixture.py`):
  - `test_revision_is_head_sha_in_git_repo` / `test_non_git_repo_keeps_cli`.
  - `test_dirty_worktree_keeps_head_revision` (Review Focus 4).
  - `test_layers_off_uses_incremental_path` (second `run()` reports `mode == "incremental"`).
  - `test_layers_on_uses_full_build` (`LayerConfigs(tsg=<fake config>)` with builder method monkeypatched to record kwargs; every run `mode == "cold"`, kwargs contain `tsg`).
  - `test_failed_layer_is_reported_and_build_continues` (Review Focus 1; tsg config pointing to a missing executable → `layers.tsg.status == "failed"`, graph still published).
  - `test_tool_result_carries_layers_and_revision`.
- [ ] **Step 2–4:** FAIL → implement (full build = `PythonGraphBuilder(repo_key=root.name, repository_revision=sha, **layers.builder_kwargs()).build(root)`; statistics added before `store.ingest`) → PASS; run `tests/mcp_server/test_tv2_build_tool.py tests/mcp_server/test_incremental_serving.py` too.
- [ ] **Step 5:** File list.

### Task 3: Reader edges (`variable_refs.py` + builder + schema)

**Files:**
- Create: `src/vgar/graph/variable_refs.py`
- Modify: `src/vgar/graph/builder.py` (after tree-sitter-graph nodes are added, in the same TSG step), `src/vgar/contracts/schema.py:226-250` (endpoints)
- Test: `tests/test_variable_refs.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class VariableAccess:
    function: str          # qualified name inside the module ("Class.method", nested → outer)
    kind: Literal["global", "field", "imported"]
    owner: str             # "" for module globals and imported names; class qualname for fields
    name: str              # variable name (for imported: the local name)
    access: Literal["read", "write", "read_write"]
def variable_accesses(source: bytes) -> list[VariableAccess]   # SyntaxError → []
```
  Rules: `Name` load/store resolved with `symtable` as global (module scope) and not shadowed; `self.a`/`cls.a` in a method; imported = name bound by `from m import X` at module level and used in the function. Builder maps: global → `GlobalVariable` node `(path, f"{module}.{name}")`; field → `Field` `(path, f"{module}.{owner}.{name}")`; imported → builder `_import_tables()` gives source module → its `GlobalVariable`; confidence 0.8 `heuristic`. Function node by `(path, f"{module}.{function}")`. One edge per pair; `access` merged.

- [ ] **Step 1: Tests:** `test_global_read_and_write`, `test_shadowed_global_is_not_a_read` (Review Focus 2), `test_self_field_read_write`, `test_nested_function_belongs_to_outer`, `test_imported_global_is_heuristic` (two-module fixture built with tree-sitter-graph facts recorded: use the recorded-facts mechanism of `tests/test_tsg_enrichment.py`), `test_no_edges_without_tsg_nodes` (static build: no `python.layer1.reads.v1` edge), `test_schema_accepts_reader_endpoints`, `test_demo_shop_free_shipping_read_by_shipping_fee`.
- [ ] **Step 2–4:** FAIL → implement → PASS; run `tests/test_tsg_enrichment.py tests/test_layer1_facts.py tests/test_graph_schema.py tests/test_graph_builder.py -q`.
- [ ] **Step 5:** File list.

### Task 4: Statement `effects` in G_code

**Files:**
- Modify: `src/vgar/graph/code_graph.py` (statement facts), `src/vgar/graph/builder.py:_add_code_graph` (node property)
- Test: `tests/test_code_graph.py` (extend)

**Interfaces:**
- Produces: `Statement` node `properties["effects"]`: sorted list from {`return`, `raise`, `yield`, `call`, `store_attribute`, `store_subscript`, `store_global`} computed from the statement's tree-sitter node (calls/yields/stores anywhere inside the statement, not inside nested definitions).

- [ ] **Step 1: Tests:** `test_statement_effects_kinds` (one statement per effect, plus a pure local assignment with `[]`), `test_effects_ignore_nested_definitions`.
- [ ] **Step 2–4:** FAIL → implement → PASS; run `tests/test_code_graph.py tests/test_code_graph_builder.py tests/test_joern_runner.py -q` (recorded digests may change: update only digest constants of graphs that contain `Statement` nodes, ledger the ruling).
- [ ] **Step 5:** File list.

### Task 5: Impact flags A and B

**Files:**
- Modify: `src/vgar/graph/impact.py` (`compute_impact`, `analyze_patch_impact`), `src/vgar/contracts/impact.py` (relations, two optional fields), `src/vgar/graph/sqlite_service.py:349-360` (flags from `VGAR_IMPACT_FOLLOW_VARIABLE_READERS`, `VGAR_IMPACT_NARROW_WITH_DATAFLOW` = `1`), `docs/impact_report_schema.md`
- Test: `tests/test_impact_variables.py`

**Interfaces:**
- Consumes: Task 3 edges, Task 4 effects.
- Produces: `compute_impact(..., follow_variable_readers: bool = False, narrow_with_dataflow: bool = False)`; `analyze_patch_impact(..., **limits)` passes them. Contract: `ImpactRelation` adds `'READS_CHANGED_VARIABLE'`, `'SHARES_STATE'`; `ImpactedNodes` adds `narrowed_by_dataflow: list[Text] = []`, `dataflow_fallbacks: int | None = None`, `flags: dict[str, bool] = {}` (only keys set to True appear; empty by default so default reports are byte-identical).
  A seeds: `GlobalVariable` nodes overlapping an `UnmappedChange` with reason `MODULE_LEVEL_CHANGE`; `Field` nodes inside a changed `Class` whose range overlaps the class's change spans. Readers via reverse reader edges (hop 1, `via` = variable node id), then the normal walk continues. Writers: a changed function's `write`/`read_write` edges → that variable's readers (hop 1, `SHARES_STATE`, no further walk).
  B: for a changed Function/Method with `Statement` children: changed statements = ranges overlapping its spans; influence = reverse closure over `DATA_DEPENDS_ON`/`CONTROL_DEPENDS_ON` (edge source depends on target); if no influenced statement has `effects` ∩ {return, raise, yield, call, store_attribute, store_subscript, store_global}, skip its `CALLS`/`IMPORTS`/`INHERITS` reverse walk (keep its `TESTS`) and add it to `narrowed_by_dataflow`; no statement or no G_code → normal walk, `dataflow_fallbacks += 1`.

- [ ] **Step 1: Tests:** `test_defaults_identical_to_before` (existing fixture report JSON equal), `test_global_change_reports_readers`, `test_field_change_reports_readers`, `test_writer_reports_readers_one_hop`, `test_module_change_without_variable_adds_nothing` (Review Focus 3), `test_log_only_change_is_narrowed`, `test_change_reaching_return_is_not_narrowed`, `test_no_code_graph_falls_back_and_counts`, `test_service_reads_env_flags`.
- [ ] **Step 2–4:** FAIL → implement → PASS; run `tests/test_impact.py tests/test_impact_arch.py tests/test_w10_impact_mcp.py tests/test_port_check.py -q` (must be unchanged).
- [ ] **Step 5:** File list.

### Task 6: Retrieval gating and the context flag

**Files:**
- Modify: `src/vgar/graph/retrieval.py` (`RetrievalConfig`, off-value dict used by `ranking_config_hash`, adjacency at ~`:500`, candidate seeding)
- Test: `tests/test_retrieval_variables.py`

**Interfaces:**
- Produces: `RetrievalConfig.use_variable_references: bool = False`, `variable_co_readers: int = 3`, both added to the off-value dict (rename not needed: add to `RT1_FLAG_DEFAULTS` with a comment, or a new `VARIABLE_FLAG_DEFAULTS` merged in `ranking_config_hash`). Adjacency skips edges with `provenance.rule_id == "python.layer1.reads.v1"` unless the flag is on. With the flag: per anchor function, variables it reads become candidates (rationale `READS_VARIABLE`, snippet = the variable node's range) and up to `variable_co_readers` other readers per variable (rationale `CO_READER`), hop 1, scored with existing features.

- [ ] **Step 1: Tests:** `test_default_hash_unchanged`, `test_default_ranking_identical_with_reader_edges_present` (graph with and without reader edges → same candidates), `test_flag_adds_variable_and_co_readers`, `test_flag_without_reader_edges_changes_nothing` (Review Focus 5), `test_co_reader_cap`.
- [ ] **Step 2–4:** FAIL → implement → PASS; run `tests/test_graph_retrieval.py tests/test_retrieval_rt1.py tests/test_tv2_integration_service.py -q`.
- [ ] **Step 5:** File list.

### Task 7: Measurement hooks (I1, R1) and the run guide

**Files:**
- Modify: `src/vgar/evaluation/gold_impact.py:140-175` (`evaluate_task(..., layers: LayerConfigs = LayerConfigs(), impact_flags: dict | None = None)`), `scripts/measure_patch_impact.py` (options), `scripts/run_graph_retrieval.py:58` (`load_or_build_graph(..., layers=None)`, cache key includes the layer settings), `ablation_matrix/run_r1_ablation.py` + `ablation_matrix/retrieval_variants.py` (options `--tsg-*`, `--joern`, `--use-variable-references`)
- Create: `docs/status/layers_in_build_measurement_guide.md`
- Test: `tests/test_measure_layers_options.py`

**Interfaces:**
- Consumes: Tasks 1, 5, 6.
- Produces: CLI options mirroring `build_graph.py` (`--tsg-executable`, `--tsg-tree-sitter-dir`, `--joern`, `--enable-jarvis`, `--scip-entry` …) on both scripts; I1 adds `--follow-variable-readers`, `--narrow-with-dataflow`; R1 adds `--use-variable-references` (applied to the `task_trace` arm only). Each output JSON records `layers` (`layer_summary`) and the flags.

- [ ] **Step 1: Tests:** `test_measure_patch_impact_parses_layer_and_flag_options`, `test_gold_impact_passes_layers_and_flags` (monkeypatched builder/impact record kwargs), `test_r1_options_reach_builder_and_config`, `test_cache_key_changes_with_layers`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Guide (Vietnamese): order of runs (I1 baseline default graph → I1 with tree-sitter-graph + A → I1 with + Joern + A + B → R1 `task_trace` with/without context flag), exact WSL commands, which outputs to compare, and the rule that flags stay off unless the user decides after the numbers.
- [ ] **Step 6:** Full suite `pytest tests -q` → only known failures. File list.

## Not done by this plan (user steps)

- The I1 and R1 runs themselves (WSL, checkouts, parquet, Docker for Joern).
- Adding the layer env vars and the three required `VGAR_*` paths to `~/.claude.json`.
