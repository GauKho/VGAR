# M3 W7-W8 MCP Repair Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `vgar solve` runs retrieve → generate → patch → test → verify as a fixed LangGraph flow in which every repair step is a real call to a new MCP server `repair`, and each run's `run_record.json` logs those calls.

**Architecture:**
- `run_repair` is split into persisted step functions in `src/vgar/repair/session.py`. The state of each step lives in the run directory, so every step can run in a fresh process.
- `vgar repair` composes these steps in-process.
- A FastMCP server `repair_server.py` exposes four of them as tools.
- The `solve` graph calls those tools through `langchain_mcp_adapters`. Only the model generation runs in the client.

**Tech Stack:** Python 3.11, pydantic 2, FastMCP (`mcp`), `langchain_mcp_adapters` `MultiServerMCPClient`, LangGraph, pytest.

**Spec:** `docs/superpowers/specs/2026-10-17-m3-w7-w8-mcp-repair-loop-design.md`

## Global Constraints

- Prompt V11, `parse_unified_diff`, `PatchPolicy` and `apply_patch` behave as before. `tests/m2/w78/test_w78_golden_v11.py` must stay green after every task.
- `vgar repair` keeps the same CLI and outcome:
  - status, reason, evidence bundle and recommendation;
  - artifacts `prompt.txt`, `raw_model_output.txt`, `candidate.diff`, `transport.diff`, `applied.diff`;
  - stage names `context, workspace, baseline, prompt, generation, parse_patch, apply, selection, verification` (+ `cleanup`), and the keys inside each stage;
  - the order of commands.
- Static checks are still skipped when test collection fails.
- One pipeline implementation. `run_repair` and the MCP tools call the same step functions.
- Tools write only inside the run's private worktree.
- Every tool works on a task only after `require_trusted_fixture`.
- Every tool is wrapped with `instrument_mcp_tool`, and its child env comes from `_child_env`.
- The default MCP servers of `vgar run`/`vgar chat` (`SERVER_NAMES = ("graph", "repository", "execution")`) do not change. `solve` connects only to `repair`.
- `run_record.mcp_scope` is `"repair_server"` for runs started by the MCP tool and `"standalone_not_executed"` for `vgar repair`.
- Each `mcp_calls` entry is `{tool, input_sha256, started_utc, duration_ms, status}` and is recorded server-side.
- Tool call order inside a run is strict: `get_task_context → apply_patch (once) → run_relevant_tests (optional) → verify_patch`. A violation raises `ValueError('Tool order violation: ...')`.
- **Deviation from spec §6 (ruling):** the V11 prompt is built **inside `repair_get_task_context`**, not by the client.
  - Building it client-side would require the client to re-read the M1 bundle itself, so retrieve would no longer go through MCP.
  - The tool returns the full `PromptArtifact` fields, and the client generates from them.
  - `prompt.txt` stays byte-identical because the same `build_repair_prompt` and tokenizer run.
- **Deviation from spec §5 table (ruling):** after `get_task_context`, the tools are keyed by the absolute `run_dir` instead of `run_id`. A run id alone does not locate the run on disk without also knowing `output_root`. `run_id` is still returned and recorded.
- Baseline at 2026-10-17: 681 passed, 1 failed (`tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`). Run tests with `.venv/Scripts/python.exe -m pytest -p no:cacheprovider` from the repo root.

## Review Focus

1. **A tool called with a `run_dir` that does not exist or is not a run directory** must return a clear error, not a traceback, and must touch nothing. Test: Task 3 `test_tool_rejects_unknown_run_dir`.
2. **`repair_verify_patch` called twice for the same run** must refuse the second call, because the run is already finished, and must leave the record unchanged. Test: Task 3 `test_verify_twice_is_rejected`.
3. **A deadline that expires between two tool calls**: the next step stops with `VERIFICATION_INCOMPLETE`/`INTERNAL_ERROR`, and verify still cleans up. Test: Task 2 `test_expired_deadline_between_steps_still_finishes_cleanly`.
4. **The model output is empty or truncated**: apply records the generation as ERROR, applies no patch, and verify gives `REJECT`. Test: Task 4 `test_solve_generator_error_rejects_and_cleans_up`.
5. **The MCP server process cannot start or returns a non-JSON error**: `solve` ends FAILED with a reason, and if a `run_dir` exists verify is still attempted. Test: Task 4 `test_solve_tool_error_is_failed_not_raised`.

---

### Task 1: Split `verify_patch` into a test half and a completion half

**Files:**
- Modify: `src/vgar/repair/verification.py`
- Test: `tests/m2/w78/test_w78_verification.py`

**Interfaces:**
- Produces:
  - `run_patch_tests(task, lease, apply_result, baseline, selection, executor, policy) -> dict`. This is the first half of today's `verify_patch`: the `apply_result`/`baseline` guard, related collection, selected collection with its early ERROR return, and `run_tests`. It returns a dict with keys `status` (`'TESTED'` when it continues normally), `tests`, `collection`, `related_collection`, `related_fallback_reason`, or the early-return dict exactly as today.
  - `complete_verification(partial, task, lease, apply_result, baseline, executor, policy) -> dict`. This is the second half: static checks, `assess_transition`, the static config hash compare, `assert_original` and the inventory check. If `partial` is an early-return dict, it is returned unchanged.
  - `verify_patch(...)` keeps its signature and returns `complete_verification(run_patch_tests(...), ...)`.

- [ ] **Step 1: Write the failing test** `test_verify_patch_equals_tests_then_completion(m1_case, tmp_path)`. On a worktree with `FIX` applied (same setup as `test_w78_verification.py`), assert that `complete_verification(run_patch_tests(...), ...)` has the same `status`, `reasons` and `tests['outcomes']` as `verify_patch(...)` on a second identical worktree. Also assert that the order of the executor's commands is `pytest --collect-only, pytest, mypy, ruff` in both.
- [ ] **Step 2: Run it.** Run `.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/m2/w78/test_w78_verification.py -q`. Expected: ImportError for `run_patch_tests`.
- [ ] **Step 3: Implement** the split in `verification.py` by moving code without changing it.
- [ ] **Step 4: Run the tests.** Run `tests/m2/w78 -q`. Expected: all pass, including golden.
- [ ] **Step 5: Commit** with `refactor(repair): split verify_patch into test and completion halves`.

### Task 2: Persisted repair session; `run_repair` composed from steps

**Files:**
- Create: `src/vgar/repair/session.py`
- Modify: `src/vgar/repair/evidence.py`, `src/vgar/repair/pipeline.py`
- Test: `tests/m2/w78/test_w78_session.py`

**Interfaces:**
- Consumes: Task 1 `run_patch_tests`, `complete_verification`.
- Produces:
  - `vgar.repair.evidence.load_run(directory: Path) -> RunHandle`. It reloads `run_record.json` and sets `start` so that `finish()` computes `duration_ms` from `started_utc`.
  - `vgar.repair.session`:
    - `class RepairSession`
      - Attributes: `run: RunHandle`, `state: dict`.
      - `state` is persisted to `<run_dir>/session.json` with keys `task`, `policy`, `profile`, `mode`, `deadline_utc` (epoch seconds), `phase`, `outcome`, `lease`, `baseline`, `applied`, `selection`, `verification`, `keep_workspace`.
      - `@classmethod load(run_dir: Path) -> RepairSession`. Raises `ValueError('Not a repair run directory: ...')` if `session.json` is missing.
      - `save() -> None`.
      - Properties `phase: str`, one of `started | prepared | generated | applied | tested | finished`, and `outcome: tuple[str, str] | None`.
    - `start_session(task, policy, mode, output_root, *, profile=None, temp_root=None, keep_workspace=False, supersedes_run_id=None, rerun_reason=None, feedback=None, deadline=None, mcp_scope='standalone_not_executed') -> RepairSession`. This is the current `begin_run` + stage init + `source_fingerprint` block. `deadline` is a monotonic value as today and is stored as `deadline_utc`.
    - `prepare(session, m1_counter, tokenizer) -> PromptArtifact | None`. Runs trusted check → context → workspace → baseline → prompt and writes `prompt.txt`. Returns `None` once `outcome` is set.
    - `record_generation(session, generated: dict, *, started_utc: str, duration_ms: int) -> str | None`. Writes the `generation` stage and `raw_model_output.txt`. Applies today's rules: status not PASS → `('ERROR', 'INTERNAL_ERROR')`; truncated → `('ERROR', 'VERIFICATION_INCOMPLETE')`. Returns the raw text or `None`.
    - `apply_candidate(session, raw: str) -> PatchApplyResult | None`. Runs `parse_patch`, `candidate.diff`, `apply`, `transport.diff` and `applied.diff`.
    - `run_selected_tests(session, m1_counter) -> dict | None`. Runs `selection` plus the first half of verification (`run_patch_tests`), stored as the `verification` stage.
    - `finish(session, m1_counter) -> RunHandle`. Completes verification if tests ran, then integrity check, bundle, lease cleanup and `run.finish`, exactly today's `finally` block. Sets phase `finished`. Raises `ValueError('Run already finished')` if called again.
  - Every step except `finish` is a no-op returning `None` when `session.outcome` is set. Exceptions map exactly as today's `except` branches: `parse_patch` + `ValueError` → `FAIL PATCH_PARSE_ERROR`; `workspace` → `ERROR WORKTREE_ERROR`; otherwise `ERROR INTERNAL_ERROR` with `error_detail`. A `StopRun` maps to its own status and code.
  - The lease is persisted as `{path, private, temp_root, source_repo, before, worktree_id, keep}` and rebuilt as `WorkspaceLease`.
  - The handoff is re-loaded with `load_handoff(task, m1_counter, m1_counter.counter_label)` in any step that needs it.
  - The executor deadline in a loaded session is `time.monotonic() + (deadline_utc - time.time())`.
  - `run_repair(...)` keeps its exact signature. Its body becomes `start_session → prepare → (time generator.generate) → record_generation → apply_candidate → run_selected_tests → finish`.

- [ ] **Step 1: Write the failing tests** in `test_w78_session.py`:
  - `test_steps_survive_reload_between_each_step(m1_case, tmp_path)`. Call each step on `RepairSession.load(run_dir)` loaded fresh from disk, with `FakeGenerator(FIX)` timing done in the test. Assert the final record has `status == 'PASS'`, every stage name above is present with `status` set, `evidence_bundle.json` has `recommendation == 'ACCEPT'`, and the worktree `private` dir no longer exists.
  - `test_finish_twice_raises(m1_case, tmp_path)`.
  - `test_expired_deadline_between_steps_still_finishes_cleanly(m1_case, tmp_path)`. After `prepare`, rewrite `deadline_utc` in `session.json` to `time.time() - 1`, then call `apply_candidate`, then `finish`. Assert `status == 'ERROR'`, the private dir is removed, and `record['complete'] is True`.
  - `test_load_rejects_non_run_dir(tmp_path)`: `pytest.raises(ValueError, match='Not a repair run directory')`.
- [ ] **Step 2: Run them.** Run `tests/m2/w78/test_w78_session.py -q`. Expected: ImportError.
- [ ] **Step 3: Implement** `load_run` and `session.py` by moving the bodies from `run_repair`. Reduce `run_repair` to the composition above.
- [ ] **Step 4: Run the tests.** Run `tests/m2/w78 tests/unit -q`. Expected: all pass, including golden, pipeline, finalization, review guards and evidence bundle tests.
- [ ] **Step 5: Commit** with `refactor(repair): persisted repair session steps; run_repair composes them`.

### Task 3: MCP server `repair`

**Files:**
- Create: `src/vgar/mcp/servers/repair_server.py`
- Modify: `src/vgar/mcp/client.py` (add a `servers` parameter)
- Test: `tests/m2/w78/test_w78_repair_server.py`

**Interfaces:**
- Consumes: Task 2 session API, plus `build_generation`, `load_task` and `load_config`.
- Produces:
  - `create_mcp_client(settings=None, servers: tuple[str, ...] = SERVER_NAMES) -> MultiServerMCPClient`.
  - The FastMCP server `vgar-repair` exposes these tools. Each tool function is also importable for direct tests, and all return JSON dicts:
    - `get_task_context(task_path: str, mode: str, output_root: str, work_root: str, config_path: str | None = None) -> dict`
      - Starts the run with `mcp_scope='repair_server'`.
      - On success returns `{status: 'PASS', run_dir, run_id, worktree_id, prompt: {messages, rendered, input_tokens, template_hash, prompt_hash, version, tokenizer_label, metadata}, failed_cases, context}`.
      - On failure it calls `finish` itself and returns `{status: 'ERROR', run_dir, reason, detail, recommendation: 'REJECT', run_record_path}`.
    - `apply_patch(run_dir: str, diff: str, generation: dict | None = None) -> dict`
      - `generation` is the client's generator result, without `raw_text`, plus `started_utc` and `duration_ms`.
      - If `generation` is `None`, it is recorded as `{'status': 'PASS', 'mode': 'tool_input'}`.
      - Calls `record_generation`, then `apply_candidate`.
      - Returns `{status, changed_files, reason}`.
    - `run_relevant_tests(run_dir: str) -> dict` → `{status, failing_tests, relevant_tests}`. The groups come from `_test_groups` over the partial verification.
    - `verify_patch(run_dir: str) -> dict` → `{status, reason, detail, recommendation, evidence, run_record_path}`. `evidence` is the bundle dict, or `{}` if there is none.
  - A server helper `_call(tool, run_dir, inputs, fn)`:
    - checks the phase order;
    - times the call;
    - appends `{tool, input_sha256: sha256 of json.dumps(inputs, sort_keys=True), started_utc, duration_ms, status}` to `run.record['mcp_calls']`;
    - saves.
    - A failed call returns `{status: 'ERROR', reason: 'TOOL_ERROR', detail}`. This applies to order violations and to an unknown `run_dir`.

- [ ] **Step 1: Write the failing tests**:
  - `test_tools_in_order_pass_and_log_four_calls(tmp_path)`: call the tool functions directly on `examples/m2/tasks/single_file_login.json` with `mode='fake'`, using the reference patch text as `diff`. Assert `verify_patch` returns `recommendation == 'ACCEPT'`, `[c['tool'] for c in record['mcp_calls']] == ['get_task_context', 'apply_patch', 'run_relevant_tests', 'verify_patch']`, and `record['mcp_scope'] == 'repair_server'`.
  - `test_apply_before_context_is_rejected` and `test_tests_before_apply_is_rejected`.
  - `test_verify_twice_is_rejected`.
  - `test_tool_rejects_unknown_run_dir(tmp_path)`.
  - `test_untrusted_task_context_returns_reject_and_cleans_up(tmp_path)`. Use the modified-snapshot task from `tests/unit/test_workflow.py`. Assert `status == 'ERROR'`, `recommendation == 'REJECT'`, `'approved fixtures' in detail`, the record is complete, and nothing is left under `work_root`.
  - `test_server_lists_four_repair_tools()`: `asyncio.run(create_mcp_client(servers=('repair',)).get_tools())` gives exactly `{'repair_get_task_context', 'repair_apply_patch', 'repair_run_relevant_tests', 'repair_verify_patch'}`.
- [ ] **Step 2: Run them.** Expected: ImportError.
- [ ] **Step 3: Implement** the server, following the pattern of `execution_server.py`: `mcp = FastMCP("vgar-repair")`, `@mcp.tool()` + `@instrument_mcp_tool(name)`, and `main()` runs stdio. Add the `servers` parameter to the client.
- [ ] **Step 4: Run the tests.** Run `tests/m2/w78 tests/test_mcp_client.py tests/test_settings.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(mcp): repair server exposing get_task_context/apply_patch/run_relevant_tests/verify_patch`.

### Task 4: `vgar solve` calls the repair tools

**Files:**
- Create: `src/vgar/agents/nodes/mcp_repair.py` (nodes `retrieve`, `generate`, `apply`, `test`, `verify`)
- Delete: `src/vgar/agents/nodes/repair_run.py`
- Modify: `src/vgar/agents/workflow.py`, `routes.py`, `runtime.py`, `state.py`, `nodes/__init__.py`, `src/vgar/cli.py` (solve output), `docs/mcp_tool_contract.md`, `README.md` (sections 3.2, 7.0 and 10.2)
- Test: `tests/unit/test_workflow.py`

**Interfaces:**
- Consumes: Task 3 tools and `create_mcp_client(servers=('repair',))`; `parse_mcp_json_result`; `build_generation`; `PromptArtifact`.
- Produces:
  - `Runtime` keeps its fields and adds `async def repair_tools(self) -> dict[str, BaseTool]`, which builds the client once per runtime.
  - New state keys: `run_dir`, `prompt`, `diff`, `generation`, `apply_status`, `recommendation`.
  - Graph: `START → initialize → retrieve → (generate | failed) → apply → (test | verify) → verify → (finalize | failed) → END`.
    - `route_after_retrieve`: `generate` if `run_dir` is set and status is PASS.
    - `route_after_apply`: `test` if `apply_status == 'PASS'`, else `verify`.
    - `route_after_verify`: `finalize` if `recommendation == 'ACCEPT'`, else `failed`.
  - `generate`:
    - uses `runtime.generator`, or the generator from `build_generation(runtime.mode, task, policy, profile, runtime.output_root)`;
    - calls `generator.generate(PromptArtifact(**state['prompt']), profile if mode == 'real' else None, policy.generation_timeout)`, timed;
    - turns any exception into `{'status': 'ERROR', 'reason': f'{type(e).__name__}: {e}'}`.
  - Every tool node:
    - wraps `parse_mcp_json_result(await tool.ainvoke(args))`;
    - turns any exception or ERROR result into `failure_reason`;
    - routes to `verify` when `run_dir` is known.
  - `failure_reason` is `None` on ACCEPT. Otherwise it is `reason`, plus `: {detail}` when the status is ERROR and there is a detail.
  - `cmd_solve` output is unchanged: `[status]`, `[run]`, `[reason]`.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_workflow.py`. Keep the existing four tests with these adjustments:
  - `test_solve_unregistered_task_id_fails_instead_of_raising` now asserts `state['recommendation'] == 'REJECT'` and `'approved fixtures' in state['failure_reason']`. The trusted-fixture gate in `repair_get_task_context` now fires before any reference patch is read.
  - Add:
    - `test_solve_through_mcp_reproduces_golden(letter, case)`, parametrized A/B/C, with `Runtime(generator=FakeGenerator(<golden raw_model_output.txt>))`. Assert that the run's `prompt.txt` and `applied.diff` bytes equal `tests/fixtures/m2/golden_v11/<letter>/`, that `mcp_calls` tools are the four in order, and that `state['recommendation'] == 'ACCEPT'`.
    - `test_solve_generator_error_rejects_and_cleans_up`: a generator whose `generate` raises `RuntimeError('boom')`. Assert FAILED, `recommendation == 'REJECT'`, `mcp_calls` tools are `['get_task_context', 'apply_patch', 'verify_patch']`, and `work_dir` contains no worktree after the run.
    - `test_solve_tool_error_is_failed_not_raised`: monkeypatch `Runtime.repair_tools` so that `repair_apply_patch.ainvoke` raises. Assert FAILED with a reason, and that `verify_patch` was still called.
- [ ] **Step 2: Run them.** Run `tests/unit -q`. Expected: failures on the new tests.
- [ ] **Step 3: Implement** the nodes, routes, runtime and state. Delete `repair_run.py`. Add a "repair server" section to `docs/mcp_tool_contract.md` listing the 4 tools, their inputs and outputs and the order rule. Update README sections 3.2, 7.0 and 10.2 to say that `solve` goes through the MCP `repair` server.
- [ ] **Step 4: Run the tests.** Run `tests/unit tests/m2/w78 -q` first, then the full suite. Expected: all pass except the baseline `test_hf_model` failure. `scripts/smoke_workflow.py` must print the new graph.
- [ ] **Step 5: Commit** with `feat(agents): vgar solve calls the MCP repair tools in a fixed flow`.

### Task 5: Acceptance

- [ ] **Step 1: Run fake `solve` on each case.** For each of `single_file_login`, `multi_file_invoice` and `missing_links`, run `.venv/Scripts/python.exe -m vgar.cli solve --task examples/m2/tasks/<case>.json`. Expected: `[status] COMPLETED` each time, and each run record has 4 `mcp_calls`.
- [ ] **Step 2: Run real `solve` on each case.** Run `... solve --task ... --mode real` for the 3 cases, one at a time. Record status, tokens and duration, and compare the run's `prompt.txt`, `raw_model_output.txt` and `applied.diff` with `golden_v11`. If a case is not PASS, investigate once and report to the user. Do not change the prompt or parser.
- [ ] **Step 3: Update the ledger and memory.** README section 2.3 gets one row with the real `solve` result. Commit with `docs: record M3 W7-W8 MCP solve acceptance`.
