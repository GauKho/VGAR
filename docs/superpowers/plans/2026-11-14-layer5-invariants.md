# Layer 5 Semantic Invariants (L5-1, L5-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `run_relevant_tests` learns likely invariants on the baseline test run and checks the candidate run, filling `semantic_invariant_preserved`, with Daikon as the core when configured and Python code for exceptions, `None`, noise filtering, node ids and a no-Java fallback.

**Architecture:** a pytest plugin traces calls into workspace modules during the two test runs EV-3 already makes and writes JSONL outside the workspace; `invariants.py` selects samples from baseline-passing tests, runs Daikon (`daikon.py`) or the Python templates, adds the exception supplement and the noise filter, and returns a `semantic_invariants` record that EV-3 stores and the ranking provider reads.

**Tech Stack:** Python 3.11 stdlib (`sys.settrace`), pytest, optional Daikon 5.9.0 + JDK 21 (user-run), existing EV-3 provider.

**Spec:** `docs/superpowers/specs/2026-11-14-layer5-invariants-design.md`

## Global Constraints

- Learn only on baseline samples from tests that **passed** on the baseline; check only candidate samples from **the same tests**.
- Traces never go inside the workspace; EV-3's inventory hash checks stay unchanged.
- Trace limits: 1,000 samples per program point, 50 MB per run; beyond that `TRACE_TRUNCATED`.
- Daikon only when `VGAR_DAIKON_JAR` and `VGAR_JAVA_HOME` are set (absolute paths); otherwise, or on Daikon failure/timeout, `python-fallback` with the reason.
- Invariants are off by default (constructor argument); with Docker admission the record is `NOT_RUN` / `TRACE_OUTPUT_UNAVAILABLE` (the Docker executor only accepts its fixed pytest argv and copies only `nodeids.json`/`junit.xml`).
- Noise filter list is fixed (spec §3); not tuned on the W10 pool.
- Every `NOT_RUN`/`ERROR` carries a reason; every record names the engine (`daikon 5.9.0` / `python-fallback`) and Python version; limitation `LIKELY_INVARIANTS_NOT_PROOF` always present.
- No test starts Java. MCP rules: no stdout in library code, `logger = logging.getLogger(__name__)`, docstrings with `Args:`.
- The user commits; tasks end with a file list, no `git commit`.

## Review Focus

1. A traced value whose type differs between baseline and candidate (int vs float in `round_vnd`): Daikon trace still parses (`nonsensical`), result is a violation or PASS, never `ERROR`. → Task 3 test `test_candidate_with_other_type_uses_baseline_declarations`.
2. A test that errors during setup/collection in the candidate (no samples for it): its baseline points become `unexercised_points`, not violations. → Task 2 test `test_missing_candidate_samples_are_unexercised`.
3. Recursive or very hot functions (thousands of calls): trace stops at 1,000 samples per point, run completes, record says `TRACE_TRUNCATED`. → Task 1 test `test_samples_capped_per_point`.
4. Objects with unhashable/odd fields (`__slots__`, properties that raise, huge strings): tracer never raises into the test. → Task 1 test `test_tracer_survives_odd_objects`.
5. Evidence byte limit with many violations: violations list is cut, `violations_total` kept, status unchanged. → Task 4 test `test_violation_list_capped_under_byte_limit`.

---

### Task 1: Trace plugin

**Files:**
- Create: `src/vgar/repair/invariant_trace_plugin.py`
- Test: `tests/test_invariant_trace_plugin.py`

**Interfaces:**
- Produces: pytest option `--vgar-trace-dir=<abs path>`; writes `<dir>/trace.jsonl` (one record per line) and `<dir>/trace_meta.json` `{"records": int, "truncated": bool, "python": str}`.
  Record: `{"ppt": "<module>.<qualname>(<arg names>)", "path": "<workspace-relative .py>", "qualname": str, "kind": "enter"|"exit"|"raise", "nonce": int, "test": "<pytest nodeid>", "vars": {name: value}, "exception": "<class name>"}` (`exception` only on `raise`).
  Values: primitives as is; object → `{"__object__": cls, "__id__": crc32(cls + sorted primitive fields)+1}` plus `name.field` primitives (one level); container → `name.__len__`; `self` → `this`.

- [ ] **Step 1: Tests** (each runs `python -m pytest -p vgar.repair.invariant_trace_plugin --vgar-trace-dir=<tmp>/trace` in a tmp mini repo via `subprocess`):
  - `test_records_enter_exit_and_raise` (function returning, function raising `ValueError` → `raise` record with `"exception": "ValueError"`).
  - `test_object_fields_and_stable_ids` (dataclass return gives `return.field`; same values in two runs → same `__id__`).
  - `test_test_files_and_generated_code_not_traced` (no ppt from `tests/` or `<string>`).
  - `test_nothing_written_in_workspace` (workspace file listing identical before/after).
  - `test_samples_capped_per_point` (function called 1,500 times → 1,000 exit records, meta `truncated` true).
  - `test_tracer_survives_odd_objects` (object with a raising property and `__slots__`; tests still pass).
  - `test_records_carry_test_nodeid`.
- [ ] **Step 2:** `pytest tests/test_invariant_trace_plugin.py -q` → FAIL (plugin missing).
- [ ] **Step 3: Implement** from `scripts/invariant_spike/tracer.py` (port, not import): `pytest_addoption`, `pytest_runtest_call` sets `sys.settrace`, `pytest_runtest_teardown` clears it, `pytest_sessionfinish` writes files. Traced frame: `co_filename` resolves under `Path.cwd()`, relative path not a test path (`name.startswith("test_") or "/tests/" in "/"+path`, same rule as the builder), not starting with `<`. Field reads wrapped in `try/except Exception` (skip field). Stdlib only. Byte cap counts serialized lengths.
- [ ] **Step 4:** tests PASS.
- [ ] **Step 5:** File list: the two files.

### Task 2: Samples, Python templates, exception supplement, noise filter, node ids

**Files:**
- Create: `src/vgar/repair/invariants.py`
- Test: `tests/test_invariants.py`

**Interfaces:**
- Consumes: Task 1 record format.
- Produces:

```python
NOISE_PATTERNS: tuple[str, ...]  # regexes: r"is a power of 2", r"\*\*2", r"is boolean", r"% \S+ == 0",
                                  # r"(__len__|_size)\b", r"has only one value"
def load_trace(folder: Path) -> tuple[list[dict], dict]               # records, meta
def select_samples(records: list[dict], tests: set[str]) -> dict[str, list[dict]]
    # key "<ppt>:::ENTER" / "<ppt>:::EXIT"; primitives only; only records whose "test" is in tests
def learn_python(points: dict[str, list[dict]]) -> list[dict]          # spike templates
def check_python(invariants: list[dict], points: dict[str, list[dict]]) -> list[dict]  # violations
def describe(invariant: dict) -> str
def exception_violations(base: list[dict], cand: list[dict], tests: set[str]) -> list[dict]
def is_noise(text: str) -> bool
def node_id_for(record: dict, repo_key: str, source_roots: tuple[str, ...], repository_name: str) -> str
    # vgar:{repo_key}:python:{function|method|class}:{path}:{module_name_for(path)}.{qualname}
```
  Violation dict: `{"program_point": str, "node_id": str, "invariant": str, "test": str}`.

- [ ] **Step 1: Tests:**
  - `test_select_samples_keeps_only_given_tests` (records from failing test excluded).
  - `test_learn_and_check_templates` (constant, one_of ≤3, range, nonneg, cmp, linear; < 2 samples → none; binary needs ≥ 3) — values from the spike unit cases.
  - `test_missing_candidate_samples_are_unexercised` (via `check_python` returning nothing for absent points; points listed by a helper `point_sets(base, cand) -> (new, unexercised)` also in `invariants.py`).
  - `test_new_exception_class_is_violation` and `test_stopped_raising_is_violation` (per (point, test)).
  - `test_noise_patterns` (`"quantity is a power of 2"` noise; `"return.total one of {...}"` not).
  - `test_node_id_matches_builder_scheme` (`src/shop/cart.py`, qualname `Cart.add` → `vgar:fx:python:method:src/shop/cart.py:shop.cart.Cart.add`; top-level → `function`).
  - `test_demo_shop_rule_gold_fix_zero_violations` (uses `tests/fixtures/vgar-demo-shop`, runs plugin on base and gold-fix copies: learn on baseline-passing tests → 0 violations on gold fix; ≥ 1 on mutant M5 `product.name.upper()`).
- [ ] **Step 2:** FAIL. **Step 3:** implement (port `learn`/`holds`/`describe` from `scripts/invariant_spike/spike.py`; `module_name_for` from `vgar.graph.builder`). **Step 4:** PASS.
- [ ] **Step 5:** File list.

### Task 3: Daikon writer, runner and parser

**Files:**
- Create: `src/vgar/repair/daikon.py`
- Create: `tests/fixtures/invariants/daikon_5_9_0/` (`base_invariants.txt`, `check_R1.txt`, `check_M5.txt`, `check_M7.txt` copied from `%TEMP%\vgar-daikon-spike\a\`; R1 has 0 violations, M5 1, M7 10 incl. `power of 2`)
- Test: `tests/test_daikon_format.py`

**Interfaces:**
- Consumes: Task 1 records; `is_noise` (Task 2).
- Produces:

```python
@dataclass(frozen=True)
class DaikonConfig:
    jar: Path | None = None; java_home: Path | None = None
    @classmethod
    def from_env(cls) -> "DaikonConfig"            # VGAR_DAIKON_JAR, VGAR_JAVA_HOME; relative → ValueError
    @property
    def configured(self) -> bool
def declarations(records: list[dict]) -> tuple[dict, dict]               # (enter, exit) types per ppt
def write_dtrace(records: list[dict], path: Path, decls: tuple[dict, dict]) -> None
def parse_invariants(text: str) -> list[str]                            # "<ppt>:::ENTER|EXIT  <inv>"
def parse_violations(text: str) -> list[str]                            # EXIT/EXITn merged, deduped
def run_daikon(config: DaikonConfig, base: Path, cand: Path, work: Path, deadline: float
               ) -> tuple[list[str], list[str], str]                    # learned, violated, version
    # raises DaikonUnavailable(reason) on timeout/non-zero exit/missing jar
```
  Encoding (from the spike): `x_is_none` int flags for variables `None` at least once in the baseline; stable hashcodes; candidate written with baseline declarations, other-type values `nonsensical`; `\_` for spaces in ppt names; dotted names keep dots only when the parent is declared, else `_`/`_size`.

- [ ] **Step 1: Tests:** `test_candidate_with_other_type_uses_baseline_declarations`, `test_is_none_flags_declared`, `test_parse_invariants_counts_fixture` (58 lines), `test_parse_violations_merges_exit_duplicates` (M7 fixture → 10 unique before noise filter, 6 after `is_noise`), `test_run_daikon_unconfigured_raises`, `test_run_daikon_nonzero_exit_raises` (monkeypatched `subprocess.run`), `test_relative_env_path_rejected`.
- [ ] **Step 2–4:** FAIL → implement (port `write_daikon`/`daikon_types`/`_prepare` from the spike; commands `java -cp <jar> daikon.Daikon --no_text_output -o base.inv.gz base.dtrace`, `daikon.PrintInvariants base.inv.gz`, `daikon.tools.InvariantChecker --verbose base.inv.gz cand.dtrace`; version from the first output line `Daikon version X`) → PASS.
- [ ] **Step 5:** File list.

### Task 4: `compute_semantic_invariants` and EV-3 integration

**Files:**
- Modify: `src/vgar/repair/invariants.py` (add the orchestrator)
- Modify: `src/vgar/mcp/proposal/diff_tests_provider.py`
- Test: `tests/mcp_server/test_tv3_invariants.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:

```python
class InvariantExecutor:                     # like ContractExecutor
    def __init__(self, executor, trace_dir: Path)
    def run(self, argv, cwd, timeout_seconds)  # appends -p vgar.repair.invariant_trace_plugin --vgar-trace-dir=<dir> to pytest argv
@dataclass(frozen=True)
class InvariantSettings:
    daikon: DaikonConfig = DaikonConfig(); repo_key: str = ""; source_roots: tuple[str, ...] = ("src",)
def compute_semantic_invariants(base_dir: Path, cand_dir: Path, baseline_outcomes: dict[str, str],
                                settings: InvariantSettings, deadline: float) -> dict
```
  Order inside `compute_semantic_invariants`: passing tests = baseline outcomes `PASS`; select samples on both sides; Daikon when configured (learned/violated text), else `learn_python`/`check_python`; **always** add `exception_violations`; drop texts where `is_noise` (count them); attach `node_id` per violation.
  Record keys (spec §3): `status, reasons, engine, learned, filtered_noise, violations, violations_total, new_points, unexercised_points, limitations, python_version, daikon_version`.
  `DiffTestsProvider(..., invariants: InvariantSettings | None = None)`: when set and runtime native, the baseline run uses `InvariantExecutor(executor, lease.private / "invariants" / "baseline")`, the candidate run `.../"candidate"` (stack inside `ContractExecutor` when both are set); after `assess_transition`, `state["semantic_invariants"] = compute_semantic_invariants(...)`; with Docker admission → `{"status": "NOT_RUN", "reasons": ["TRACE_OUTPUT_UNAVAILABLE"], ...}`; when the baseline is not qualified or the patch did not apply → `NOT_RUN` with that reason. `invariants` goes into `_profile_hash`.

- [ ] **Step 1: Tests** (reuse the `job` fixture style of `tests/mcp_server/test_tv3_diff_tests.py`, `single_file_login`):
  - `test_invariants_off_by_default_record_unchanged` (no `semantic_invariants` key).
  - `test_fix_passes_and_regression_fails_invariants` (fix → status `PASS` or `FAIL` listed with engine `python-fallback`; the BAD diff `return False` → `FAIL` with a violation whose `node_id` contains `auth.py`).
  - `test_workspace_inventory_unchanged_with_tracing` (EV-3 status as without invariants).
  - `test_docker_admission_gives_trace_output_unavailable` (unit on the helper that builds the record for a non-native runtime).
  - `test_violation_list_capped_under_byte_limit` (synthetic 10,000 violations → list cut, `violations_total` 10,000).
  - `test_daikon_failure_falls_back_with_reason` (config pointing to a missing jar → engine `python-fallback`, reason starts `daikon unavailable`).
- [ ] **Step 2–4:** FAIL → implement → PASS. Run `pytest tests/mcp_server/test_tv3_diff_tests.py -q` too (unchanged behaviour).
- [ ] **Step 5:** File list.

### Task 5: Ranking provider and demo-shop measurement

**Files:**
- Modify: `src/vgar/mcp/proposal/ranking_provider.py:190-202`
- Create: `docs/status/l5_invariants_run_2026-11-14.md`
- Test: `tests/mcp_server/test_tv3_ranking.py` (extend), `tests/test_invariants_demo_shop.py`

**Interfaces:**
- Consumes: EV-3 record field `semantic_invariants` (Task 4).
- Produces: `semantic_invariant_preserved` = `PASS` iff invariants `PASS` and (no contract or contract PASS); `FAIL` if either `FAIL`; else unchanged `NOT_RUN`.

- [ ] **Step 1: Tests:** `test_ranking_reads_semantic_invariants` (PASS/FAIL/NOT_RUN table incl. contract combinations). `test_demo_shop_variants` (parametrized over the 14 spike variants, edits copied from `scripts/invariant_spike/spike.py` VARIANTS, applied to copies of `tests/fixtures/vgar-demo-shop`; calls plugin + `compute_semantic_invariants` with python-fallback): base, gold fix, R1–R4 → `PASS`; M3, M4, M5, M6, M7 → `FAIL`; M1, M2, M8 → `PASS` (marked known misses in the test ids).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Write `docs/status/l5_invariants_run_2026-11-14.md` (Vietnamese): demo-shop table (python-fallback measured in CI; Daikon numbers from the spike run, with the command to re-run `scripts/invariant_spike/spike.py daikon`), what is not measured (W10 pool: blocked under Docker admission by `TRACE_OUTPUT_UNAVAILABLE`, needs a Docker copy-out change), and how to enable (`InvariantSettings`, env vars).
- [ ] **Step 6:** Full suite `pytest tests -q` → only known failures. File list.

## Not done by this plan

- Docker trace copy-out (the W10 measurement depends on it); a follow-up spec.
- L5-3 `coverage_count`, EV-1 weights, the static EV-2 baseline resource.
