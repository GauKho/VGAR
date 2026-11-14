# Layer 5 semantic invariants: Daikon core with Python supplements (L5-1, L5-2) (14/11/2026)

## Sources

- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`, rows L5-1, L5-2 (lines 146–147), EV-1/EV-3 (lines 149, 151)
- **[spike]** `scripts/invariant_spike/` and `%TEMP%\vgar-daikon-spike\report.md` (14/11, vgar-demo-shop, 14 variants, Daikon 5.9.0 vs a Python miner)
- **[daikon]** Daikon user and developer manuals, version 5.9.0 (official release 1/9/2026; 5.9.1 is development)

Plans and results of the 16-week schedule are not sources for this change.

## What the proposal asks for

| [P] line | Section | Text / requirement |
|---|---|---|
| 87 | RQ4 | "Schema, structural invariant, semantic invariant và tests có giảm patch rủi ro/overfitting không?" |
| 382–383 | §5.2 Layer 5 | "Invariant and runtime evidence: Daikon-style dynamic invariant detection" |
| 410 | §5.3 | Daikon-style: "dynamic likely invariants", "semantic evidence từ test traces", not "proof tuyệt đối" |
| 900–925 | §8.5 | evidence field `semantic_invariant_preserved`, weight `w_sem` in `score(patch)`; "Không claim patch đúng tuyệt đối" |
| 1242–1261 | §12.4 | likely invariants from test traces before the patch; after it: "invariant còn đúng không? có invariant mới đáng ngờ không? có test nào exercise path này không?" |
| 1299–1305 | §13.1 | verification baselines: tests only → … → "tests + graph + semantic invariants" |
| 1332–1334 | §13.2 | false accept rate, overfitting detection rate |

[P] gives no invariant templates, no rule for when a broken invariant fails a patch, and no threshold. Every such value below is the team's choice and is marked so.

## Current state in the repository

| Place | State |
|---|---|
| `run_relevant_tests` → `DiffTestsProvider` (`src/vgar/mcp/proposal/diff_tests_provider.py`, EV-3) | runs `task.fallback_scope` on the baseline, applies the patch, runs it again, in a host workspace (native) or admitted Docker. Checks that tests do not change the workspace inventory. |
| `ContractExecutor` (`src/vgar/repair/semantic_contract.py`) | wraps the executor and adds `-p <plugin>` to every pytest call: the pattern this change reuses |
| `ranking_provider.py:190` | sets `semantic_invariant_preserved` only from a hand-written semantic contract (input/output examples) |
| `verification_provider.py` (EV-2, static) | limitation `RUNTIME_INVARIANTS_NOT_MEASURED`; baseline resource reports `semantic_invariants: NOT_RUN` |
| `repair/patch_evidence.py:238` | `semantic_invariant_preserved` is `NOT_RUN` |

No invariant is inferred anywhere today.

## What the spike showed

On vgar-demo-shop (10 passing tests plus 1 failing test, 4 behaviour-preserving refactors, 8 mutants, the gold fix):
- Daikon 5.9.0 and the Python miner caught the same mutants: 3 the tests also catch, 2 the tests miss (product name upper-cased, a default coupon applied silently), and both missed 3 mutants whose changed values no test exercises. Neither raised a violation on any refactor.
- **Daikon has no Python front end.** A Python tracer must write Daikon's `.decls`/`.dtrace` format. Three encoding rules were needed: object hashcodes stable across runs, one set of declarations (the baseline's) for every trace that is checked, and an explicit `x_is_none` variable because Daikon ignores `null` strings.
- Daikon adds conditional invariants (`is_eligible` returns true ⇔ `subtotal == 900000`) and statistical justification. It ignores exceptional exits (5 in the baseline) and prints some templates that mean nothing for Python (`is a power of 2`, `x == x**2`).
- **Rule that removed false alarms on the gold fix:** learning and checking only on tests that passed on the baseline took the gold fix from 9–13 violations to 0 and kept every mutant detection (measured with the Python miner).

Limits: 11 tests, deterministic code, one small repository; most invariants are "one of {…}". The false-alarm rate on a large repository is not measured.

## Scope

In scope: L5-1 (trace while tests run, infer invariants) and L5-2 (check the candidate against the baseline invariants), inside `run_relevant_tests`; the result feeds `semantic_invariant_preserved`; a measurement on the demo-shop variants and a protocol for the W10 mutant pool.

Out of scope: L5-3 (`coverage_count`); EV-1 weights; the static EV-2 provider and its baseline resource; a new MCP tool (the result travels in the existing EV-3 evidence); languages other than Python; a full Daikon front end (only the variables below).

## Goals, non-goals, anti-goals

Goals:
1. One `run_relevant_tests` call learns invariants on the baseline run and checks the candidate run, with no extra test execution.
2. Daikon is the inference core when configured; Python code adds what Daikon cannot see (exceptions, `None`), removes templates that mean nothing for Python, maps program points to graph node ids, and runs alone when Java is missing, saying so.
3. `semantic_invariant_preserved` becomes PASS/FAIL from measured evidence, with the violated invariants listed.
4. A measurement answers RQ4's question for invariants: does "tests + invariants" catch mutants that "tests only" accepts, and how many correct patches does it reject?

Non-goals: proving correctness; generating tests or inputs; tracing third-party or test code; tuning `w_sem`.

Anti-goals (a failure even if the code runs):
- calling a violation a proof of a bug (it is evidence; wording in the record says "likely invariant");
- learning from the candidate run, or from tests that failed on the baseline;
- writing traces inside the workspace (the EV-3 inventory check must stay unchanged and pass);
- `NOT_RUN` or `ERROR` without a reason code;
- choosing the noise filter or the rule on the W10 evaluation pool.

## Approaches

| | A. Daikon only | B. Python miner only | **C. Daikon core + Python supplements (chosen)** |
|---|---|---|---|
| Inference | Daikon | Python templates | Daikon; Python templates only as fallback |
| Exceptional exits | ignored | yes | yes (Python) |
| `None` values | needs `x_is_none` | native | `x_is_none` for Daikon, native in Python |
| Conditional invariants, statistical justification | yes | no | yes |
| Java needed | yes | no | optional (fallback without it) |
| [P] fit | Daikon-style, literal tool | Daikon-style | Daikon-style, literal tool when Java exists |

Decided in the conversation of 14/11: C. Reasons: the spike shows A and B equal on detection and complementary on gaps; C follows the tool [P] names when it can run and keeps working without Java, the same shape as GraphDiff (RefactoringMiner primary, `ast` fallback).

## Design

### 1. Files

| File | Content |
|---|---|
| `src/vgar/repair/invariant_trace_plugin.py` | pytest plugin (stdlib only): traces calls into the repository's non-test modules, writes JSONL to a folder given by environment variable |
| `src/vgar/repair/invariants.py` | records, Python templates (fallback), exception and `None` supplements, noise filter, the learn/check rule, program point → node id, result record |
| `src/vgar/repair/daikon.py` | `.dtrace` writer with fixed declarations, Daikon runner (`daikon.Daikon`, `daikon.PrintInvariants`, `daikon.tools.InvariantChecker`), output parser, configuration |
| `src/vgar/repair/invariant_executor.py` (or inside `invariants.py`) | `InvariantExecutor`: like `ContractExecutor`, adds `-p vgar.repair.invariant_trace_plugin` and the trace folder to every pytest call |
| `diff_tests_provider.py` | wraps the executor when invariants are enabled; after both runs, calls learn/check; adds `semantic_invariants` to the EV-3 record. Enabled by a constructor argument set from the host configuration, **off by default** (my call: existing EV-3 behaviour and evidence stay unchanged unless the host opts in) |
| `ranking_provider.py` | reads `semantic_invariants` into `semantic_invariant_preserved` |
| tests | `tests/test_invariant_trace_plugin.py`, `tests/test_invariants.py`, `tests/test_daikon_format.py`, `tests/mcp_server/test_tv3_invariants.py`; the demo-shop variants of [spike] become a fixture |

### 2. L5-1 tracing

- **What is traced (team's choice):** calls whose code file is inside the workspace, not under a test path (builder's `_is_test_path` rule), not generated (`<string>` file names, e.g. dataclass methods). Entry: parameters; normal exit: parameters (entry values) and `return`; exceptional exit: parameters and the exception's class name.
- **Values:** `int`, `float`, `bool`, `str`, `None` as they are; an object gives one hashcode variable (stable: hash of its class and primitive field values) and its primitive fields as `x.field` (one level); a container gives `x.__len__`; anything else is dropped. Each record carries the pytest node id of the running test.
- **Limits (team's choice):** at most 1,000 samples per program point and 50 MB of trace per run; beyond that, sampling stops for that point and the record says `TRACE_TRUNCATED`.
- **Where traces go:** a folder outside the workspace, given to the plugin by environment variable; EV-3's inventory hash check stays as it is.
- The plugin uses `sys.settrace` (Python 3.11 in this repository). It must not import anything outside the standard library, because it runs in the task's own interpreter.

### 3. L5-2 learn and check

**Rule (team's choice, from [spike]):** invariants are learned on baseline samples recorded during tests that **passed** on the baseline, and checked on candidate samples recorded during **the same tests**. Behaviour on paths of tests that failed on the baseline is expected to change and is not checked.

- **Daikon core** (when `VGAR_DAIKON_JAR` and `VGAR_JAVA_HOME` are set, absolute paths): write the baseline samples as one `.dtrace` with declarations; write the candidate samples with the **baseline's** declarations (a value of another type becomes `nonsensical`); run `daikon.Daikon` → `.inv.gz`, `daikon.PrintInvariants` (for the evidence list) and `daikon.tools.InvariantChecker --verbose` on the candidate trace. Merge `EXIT` and `EXITn` duplicates.
- **Python supplements (always):**
  - exceptions: per (program point, test), the set of exception classes raised in baseline samples; in the candidate, a class not in the baseline set for that point, or a (point, test) that raised on the baseline and no longer raises, is a violation;
  - `None`: the `x_is_none` variables for Daikon; in the fallback, `None` is an ordinary value;
  - noise filter: drop invariants whose text matches a fixed list (initially `is a power of 2`, `== x**2`, `is boolean` on an integer, `x % y == 0`, comparisons with a `__len__` or `_size` variable, `has only one value` on a hashcode). The list is fixed from the demo-shop spike and recorded in the result; it is not tuned on the W10 pool.
- Daikon runs inside the EV-3 request deadline (my call); on timeout or a non-zero exit the run uses the Python fallback and records the reason.
- **Python fallback** (Java not configured or Daikon fails): the [spike] templates: constant, one of ≤ 3 values, bounds, `x >= 0`, `==`/`<`/`<=` between numbers of one point, `y = a·x + b` (≥ 3 distinct x); a point with < 2 samples gets no invariant, binary templates need ≥ 3 samples.

**Result record** `semantic_invariants` in the EV-3 evidence:

| Field | Meaning |
|---|---|
| `status` | `PASS` (no violation), `FAIL` (≥ 1 violation), `NOT_RUN` (reason: no baseline-passing test, invariants disabled, trace empty), `ERROR` (reason: tracer or Daikon failure) |
| `engine` | `daikon 5.9.0` or `python-fallback` with the reason Daikon did not run |
| `learned`, `filtered_noise` | counts |
| `violations` | list of `{program_point, node_id, invariant, test}` (capped by the EV-3 byte limit) |
| `new_points`, `unexercised_points` | candidate-only and baseline-only program points (reported, not violations) |
| `limitations` | e.g. `LIKELY_INVARIANTS_NOT_PROOF`, `TRACE_TRUNCATED` |

`node_id` uses the graph's scheme (`vgar:{repo_key}:python:{kind}:{path}:{module.qualname}`) and the builder's module-name rule (`module_name_for`), so a violation points at a graph node.

**`semantic_invariant_preserved`** (ranking provider): `PASS` when `semantic_invariants.status` is PASS and a semantic contract, if present, also passes; `FAIL` when either fails; otherwise `NOT_RUN`.

### 4. Measurement

1. **Demo-shop (tier 1, CI):** the 14 [spike] variants as a fixture; expected: 0 violations on base, gold fix and refactors; violations on M3–M7; none on M1, M2, M8 (recorded as known misses). Runs with the Python fallback; a test with recorded Daikon output checks the parser.
2. **W10 mutant pool (tier 3, the user runs it, Docker and Java):** for each gold patch and mutant, EV-3 with invariants on. Report against "tests only": mutants that pass the tests but fail invariants (false accepts avoided), gold patches that fail invariants (false rejects added), counts per engine, and runtime overhead. A null or negative result is reported as such.

## Tests

- plugin: entry/exit/raise records; object flattening, stable hashcodes, `__len__`; test files and `<string>` frames not traced; nothing written in the workspace; truncation.
- `.dtrace`: declarations reused for a candidate with another type (`nonsensical`); `x_is_none`; parser on saved Daikon 5.9.0 output from [spike] (copied as small fixtures); `EXIT`/`EXIT1` merge.
- rule: samples from baseline-failing tests excluded on both sides; gold fix of demo-shop gives 0 violations.
- supplements: new exception class → violation; noise filter drops the listed templates and counts them.
- fallback: Daikon not configured or failing → `python-fallback` with reason.
- EV-3: workspace inventory unchanged; `semantic_invariants` present; ranking maps PASS/FAIL/NOT_RUN.
- No test starts Java.

## Constraints

- Windows and WSL; the Docker runtime runs the task's own Python, so the plugin is stdlib-only and must work on the Python versions of the W10 images.
- Java tools are run by the user during development; in production the server starts Daikon only when configured.
- Every record states the engine and Daikon version; Python version recorded.
- Existing tests stay green; known failures unchanged.

## Left to the builder

- How the trace folder reaches the plugin in the Docker runtime (a mount outside the workspace); if the admitted Docker policy cannot provide one, Docker runs report `NOT_RUN` with `TRACE_OUTPUT_UNAVAILABLE` and the measurement says so.
- Whether Daikon's own configuration can disable the noisy templates (preferred over filtering text, when it exists in 5.9.0).
- The lowest Python version the plugin must support (check the W10 images).
- Daikon command options for speed (e.g. omitting `PrintInvariants` when the evidence list is not needed).
- How the W10 measurement runs: extend `scripts/evaluate_mutant_pool.py` with invariants on if its verification goes through `DiffTestsProvider`; otherwise add a small runner that calls the same learn/check code on its baseline and candidate test runs.
- `co_qualname` exists only from Python 3.11; on older interpreters use the enclosing class found from the frame, or `co_name`, and record which.
