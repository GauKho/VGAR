# M3 W7-W8 Phase 2: Agent Chooses the MCP Repair Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `vgar solve --agent` lets a LangChain agent decide which of five zero-argument repair tools to call and when to stop. Diffs always come from the V11 single-turn generator, never from the agent. Fake mode proves the regenerate-with-feedback branch ends PASS.

**Architecture:**
- A host object (`AgentRepairHost`) owns the current run, the held diff, the attempt counter and the trace. It exposes five LangChain tools. Four of them forward to the existing MCP `repair` tools with `run_dir` bound by the host. `generate_patch` runs the generator in the client.
- A failed attempt is closed (verified) and a **new run** is opened with host-built feedback (`supersedes_run_id`, `rerun_reason`, `feedback`). The server keeps "one apply per run".
- Two real generators behind `--generator`: `worker` (M2 `HFGenerator`, unchanged path) and `agent` (the agent's own in-process model with M2 settings, hash-checked against `prompt.rendered`).
- The phase-1 fixed flow (`run_task`, `workflow.py`) is not changed in behaviour.

**Tech Stack:** Python 3.11, LangChain `create_agent` + `ToolCallLimitMiddleware`, `langchain_mcp_adapters`, FastMCP, transformers (real mode only), pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-m3-w7-w8-agent-tool-choice-design.md`

## Global Constraints

- `src/vgar/agents/prompts/repair_v11.txt` (template hash `sha256:ba6d1478…`), `parse_unified_diff`, `PatchPolicy`, verification: **not edited**.
- `tests/m2/w78/test_w78_golden_v11.py` and `tests/unit/test_workflow.py` stay green after every task. `vgar repair`, fixed-flow `vgar solve` (no `--agent`), `vgar run`, `vgar chat` keep their behaviour.
- `repair_get_task_context` called **without** the new arguments must log the same `input_sha256` as today (the six existing keys only) and write the same `prompt.txt`.
- Run 1 of agent mode writes a `prompt.txt` byte-identical to `tests/fixtures/m2/golden_v11/{A,B,C}/prompt.txt`.
- Every run the agent mode opens ends with `repair_verify_patch` (agent- or host-called). A task result is PASS only if the **last** run's verify returned `recommendation == "ACCEPT"`.
- The agent never sees `run_dir`, paths, the V11 prompt or the diff text. No agent tool has a model-filled parameter.
- Limits: `MAX_ATTEMPTS = 3` generations per task, `MAX_TOOL_CALLS = 15` (ToolCallLimitMiddleware `run_limit`, `exit_behavior="end"`), `RECURSION_LIMIT = 40`.
- Trace `by` values: `"agent"` (the agent chose this tool) or `"host"` (the host made this MCP call on its own: closing a failed run, opening the next run, safety-net verify).
- Tool reply text format (the scripted fake agent parses it, the real agent reads it). Every reply is plain text, first line `STATUS: <PASS|FAIL|ERROR>`; optional lines `REASON: …`, `DETAIL: …` (one line, ≤ 300 chars), `ATTEMPT: <n> of 3`, `ATTEMPTS LEFT: <k>`, `FILES: a.py, b.py`, and a last line `NEXT: …` telling the usual next tool.
- Generation meta sent to `apply_patch` carries `generator_path` ∈ `{"fake", "worker", "agent_model"}` in addition to the keys the fixed flow already sends.
- The user runs every real-mode (GPU) command. Do not start or stop real runs.
- Tests: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider` from the repo root. Baseline 2026-10-18: 706 passed, 1 failed (known failure `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`).
- **Ruling (deviation from spec §6 table, agent row):** in real mode the agent model is always loaded from the pinned profile snapshot (`profile.snapshot`, `profile.revision`, `local_files_only=True`), for both `--generator` values. Option B needs a pinned agent model; using one loader for both keeps A and B comparable. `create_core_model` and `vgar run/chat` are untouched.

## Review Focus

1. Agent calls `generate_patch` twice in a row → second call returns ERROR "call apply_patch", no second generation, no new run (Task 4 test).
2. Agent calls `verify_patch` itself after a test FAIL, then `generate_patch` → the host opens the next run **without** a host-called verify (server would reject a second verify) (Task 4 test).
3. `agent.ainvoke` raises (recursion limit, model output that is not parseable) → the run is still verified by the host, result FAILED, trace file written, no exception escapes `run_agent_task` (Task 4 test).
4. A real model passes arguments to a zero-argument tool (e.g. `generate_patch(diff="...")`) → arguments ignored, tool runs normally (Task 4 test).
5. MCP transport error on one tool → ERROR text to the agent, the safety-net verify still closes the run (Task 4 test).

---

### Task 0: Baseline

- [ ] **Step 1:** Run the full suite, record pass/fail counts in this file's Global Constraints line.
Run: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider -q`
Expected: only the known HF failure.

### Task 1: `repair_get_task_context` accepts feedback for a rerun

**Files:**
- Modify: `src/vgar/mcp/servers/repair_server.py` (`get_task_context`)
- Test: `tests/m2/w78/test_w78_repair_server.py`

**Interfaces:**
- Produces: `get_task_context(task_path, mode, output_root, work_root, config_path=None, keep_workspace=False, feedback: dict | None = None, supersedes_run_id: str | None = None, rerun_reason: str | None = None) -> dict` — the three new values go straight to `start_session(...)`. They are added to the logged `inputs` dict **only when not None**.

- [ ] **Step 1: Write the failing tests**

```python
def test_context_with_feedback_starts_a_superseding_run(tmp_path):
    first = context(tmp_path)
    server.verify_patch(first['run_dir'])
    feedback = {'task_id': 'single_file_login', 'source_run_id': first['run_id'],
                'category': 'PATCH_PARSE_ERROR', 'message': 'Line 5 has no prefix.'}
    second = server.get_task_context(str(TASK), 'fake', str(tmp_path / 'runs'), str(tmp_path / 'work'),
                                     feedback=feedback, supersedes_run_id=first['run_id'],
                                     rerun_reason='PATCH_PARSE_ERROR')
    assert second['status'] == 'PASS'
    record = record_of(second['run_dir'])
    assert record['supersedes_run_id'] == first['run_id'] and record['rerun_reason'] == 'PATCH_PARSE_ERROR'
    assert record['prompt_feedback'] == feedback
    assert 'Previous attempt feedback (execution data, not instructions):' in (Path(second['run_dir']) / 'prompt.txt').read_text(encoding='utf-8')
    server.verify_patch(second['run_dir'])


def test_context_without_feedback_logs_the_original_six_inputs(tmp_path):
    ctx = context(tmp_path)
    inputs = {'task_path': str(TASK), 'mode': 'fake', 'output_root': str(tmp_path / 'runs'),
              'work_root': str(tmp_path / 'work'), 'config_path': None, 'keep_workspace': False}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    record = record_of(ctx['run_dir'])
    assert record['mcp_calls'][0]['input_sha256'] == digest and 'prompt_feedback' not in record
    server.verify_patch(ctx['run_dir'])
```

- [ ] **Step 2:** Run `…pytest tests/m2/w78/test_w78_repair_server.py -k "feedback or six_inputs" -v` → first FAILS (unexpected keyword `feedback`).
- [ ] **Step 3:** Implement the signature above.
- [ ] **Step 4:** Run `…pytest tests/m2/w78 tests/unit/test_workflow.py -q` → PASS.
- [ ] **Step 5:** Commit `feat(mcp): repair_get_task_context can start a rerun with feedback`.

### Task 2: Host-built retry feedback

**Files:**
- Create: `src/vgar/agents/feedback.py`
- Test: `tests/unit/test_agent_feedback.py`

**Interfaces:**
- Produces: `build_feedback(record: dict) -> dict` returning exactly `{"task_id", "source_run_id", "category", "message"}`, all non-empty strings. `task_id = record["task_id"]`, `source_run_id = record["run_id"]`, `category = record["reason"] or record["status"]`.
- `message` (host text, never agent text), first matching rule:
  1. `record["error_detail"]` present → its `message`, plus one hint line per `parser_diagnostics["invalid_body_lines"]` entry (`Line {raw_line} '{text}' has no '-', '+' or ' ' prefix.`) and one line when `expected_counts != actual_counts` (`Hunk header {hunk_header} declares old={o} new={n} but the body has old={o'} new={n'}.`).
  2. `record["stages"]["verification"]["tests"]["outcomes"]` has non-PASS entries → `Tests still failing after the patch: name1, name2.` plus `Verification reasons: …` if `stages.verification.reasons` is non-empty.
  3. Fallback: `Previous attempt ended with {status} {reason}.`
- Length is not capped here; `build_repair_prompt` already bounds it to 300 tokens.

- [ ] **Step 1: Write failing tests** — three dict-based records, one per rule:
  - `test_parse_error_feedback_names_the_unprefixed_line`: `error_detail={"message": "Invalid hunk body", "parser_diagnostics": {"invalid_body_lines": [{"raw_line": 5, "text": "    return name"}]}}`, `reason="PATCH_PARSE_ERROR"` → `category == "PATCH_PARSE_ERROR"`, `"Line 5" in message`, `"Invalid hunk body" in message`, keys == the four.
  - `test_test_failure_feedback_lists_failing_tests`: `stages.verification.tests.outcomes={"tests/test_a.py::t1": "FAIL", "tests/test_a.py::t2": "PASS"}`, `reason="TEST_FAILED"` → `"tests/test_a.py::t1" in message` and `"t2" not in message`.
  - `test_fallback_feedback_is_never_empty`: record with only `task_id, run_id, status="ERROR", reason="INTERNAL_ERROR"` → message non-empty and contains `INTERNAL_ERROR`.
- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3:** Implement `build_feedback`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(agents): host-built retry feedback from a failed run record`.

### Task 3: Fake pieces — scripted patch generator, broken diff, scripted agent

**Files:**
- Create: `src/vgar/agents/fakes.py`
- Test: `tests/unit/test_agent_fakes.py`

**Interfaces:**
- Produces:
  - `break_diff(diff: str) -> str` — drops the leading `-` of the first removed line (`-` but not `---`) so the hunk counts no longer match. Mirrors the spike failure.
  - `class ScriptedPatchGenerator` — `mode = "fake"`, `__init__(self, diffs: list[str])`, `generate(prompt, profile, timeout_seconds) -> dict` returns the next diff in the same dict shape as `FakeGenerator.generate`; after the last diff it keeps returning the last one.
  - `class ScriptedRepairAgent(BaseChatModel)` — `bind_tools` returns self. `_generate` reads the last `ToolMessage` (none → `get_task_context`) and, from its `STATUS:` / `ATTEMPTS LEFT:` lines and tool name, emits the next call:
    `get_task_context PASS → generate_patch`; `generate_patch PASS → apply_patch`; `generate_patch ERROR → verify_patch`; `apply_patch PASS → run_relevant_tests`; `run_relevant_tests PASS → verify_patch`; `apply_patch / run_relevant_tests not PASS → generate_patch if ATTEMPTS LEFT > 0 else verify_patch`; `verify_patch → final AIMessage with no tool calls` (content = the verify reply). Tool calls have `args == {}`.

- [ ] **Step 1: Write failing tests**
  - `test_break_diff_makes_every_reference_patch_unparseable` (parametrize the three `tests/fixtures/m2/reference_patches/*.diff`): `parse_unified_diff(break_diff(d), policy)` raises `ValueError`, where `policy` = `PatchPolicy` built from the task like `apply_candidate` does.
  - `test_scripted_patch_generator_returns_diffs_in_order`: `["a", "b"]` → `raw_text` `"a"`, `"b"`, `"b"`.
  - `test_scripted_agent_retries_after_apply_fail`: messages ending in `ToolMessage(name="apply_patch", content="STATUS: FAIL\nATTEMPTS LEFT: 2\n…")` → next call `generate_patch`; with `ATTEMPTS LEFT: 0` → `verify_patch`.
  - `test_scripted_agent_stops_after_verify`: last tool `verify_patch` → AIMessage without tool calls.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Use `ScriptedToolModel` in `scripts/smoke_w3_w4_agent.py` as the shape reference.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(agents): scripted fake agent and patch generator for agent mode`.

### Task 4: Agent mode host, tools, trace and `run_agent_task`

**Files:**
- Create: `src/vgar/agents/tool_agent.py`, `src/vgar/agents/prompts/repair_agent.md`
- Modify: `src/vgar/agents/nodes/mcp_repair.py` (extract the body of `generate` into `run_generation`; `generate` calls it, behaviour unchanged), `src/vgar/agents/runtime.py` (add `generator_choice: Literal["worker", "agent"] = "worker"`)
- Test: `tests/unit/test_agent_solve.py`

**Interfaces:**
- Consumes: Task 1 `get_task_context(..., feedback, supersedes_run_id, rerun_reason)`; Task 2 `build_feedback`; Task 3 `break_diff`, `ScriptedPatchGenerator`, `ScriptedRepairAgent`.
- Produces:
  - `run_generation(generator, prompt: dict, mode: str, profile, policy) -> tuple[str, dict]` in `mcp_repair.py` — (diff text, meta without `raw_text`, with `started_utc`, `duration_ms`); exceptions become `status="ERROR"` meta exactly as today.
  - `class AgentRepairHost` — `__init__(self, runtime: Runtime, task_path: Path, work_dir: Path, generator)`, `langchain_tools() -> list[BaseTool]` (names `get_task_context, generate_patch, apply_patch, run_relevant_tests, verify_patch`), `async close() -> None` (safety-net verify), attributes `trace: list[dict]`, `runs: list[dict]`, `last_verify: dict | None`.
  - `async run_agent_task(*, task_path: Path, runtime: Runtime, model: BaseChatModel | None = None) -> dict` — returns `{"status": "COMPLETED"|"FAILED", "repair_status", "recommendation", "attempts", "run_record_path", "evidence", "failure_reason", "trace_path"}`. `model=None` → `ScriptedRepairAgent()` in fake mode, pinned agent model (Task 5) in real mode.
- Generator choice inside `run_agent_task`: `runtime.generator` if set; else fake → `ScriptedPatchGenerator([break_diff(ref), ref])` with `ref` = `tests/fixtures/m2/reference_patches/<task_id>.diff`; real + `worker` → `build_generation("real", …)[0]`; real + `agent` → `AgentModelGenerator(model, profile, policy)` (Task 5). `generator_path` meta = `"fake"` / `"worker"` / `"agent_model"`.
- Host rules (spec §5): `get_task_context` once (second call → ERROR text). `generate_patch`: no run → ERROR; held unapplied diff → ERROR `call apply_patch`; current run not failed and not verified-non-ACCEPT → ERROR; current run failed → if unverified, host `repair_verify_patch` (`by="host"`), then if `attempts >= 3` → ERROR `No attempts left; call verify_patch` (no new run), else host `repair_get_task_context` with `build_feedback(record)`, `supersedes_run_id`, `rerun_reason=category`; then generate, hold diff, `attempts += 1`. A run is *failed* when apply or tests returned non-PASS, or its verify recommendation is not ACCEPT. `apply_patch` without a held diff → ERROR. `run_relevant_tests` / `verify_patch` before any run → ERROR; otherwise forwarded to MCP and server order errors are returned as text. `last_verify` is updated only by verify results that carry a `recommendation`.
- Trace file: `<runtime.output_root>/agent-traces/<UTC stamp>-<task_id>.json` with keys `task_id, mode, generator, duration_ms, calls` (`{tool, by, status, reason, duration_ms, run_dir}`), `runs` (`{run_dir, run_id, supersedes_run_id, status, reason}` read from each run_record), `messages` (`{type, content, tool_calls}`), `result`.
- `run_agent_task` owns the work dir like `run_task` (cleanup unless `keep_workspace`), wraps `agent.ainvoke` in try/except (exception message → `failure_reason` if the result is not PASS), always calls `host.close()`, re-checks `fingerprint_source` of the source repo (changed → FAILED).
- `repair_agent.md`: describes the five tools, the usual order context → generate → apply → tests → verify, that after a FAIL it may call `generate_patch` again (a fresh copy and feedback are prepared automatically), that it must not write diffs or code itself, and that it must always end with `verify_patch`. Plain text, no V11 content.

- [ ] **Step 1: Write failing tests** (all fake mode, `Runtime(output_root=tmp_path / "runs")`, `GOLDEN`/`CASES` as in `tests/unit/test_workflow.py`):
  - `test_agent_fake_retries_then_passes[A|B|C]` (§10.1, §10.2, §10.4): `status == "COMPLETED"`, two runs; run 1 record `status == "FAIL"`, `reason == "PATCH_PARSE_ERROR"`; run 2 `supersedes_run_id == run1.run_id`, `prompt_feedback` non-empty, `status == "PASS"`; run 1 `prompt.txt` == golden; run 2 `prompt.txt` with the feedback block removed == run 1 `prompt.txt` (block = `'\nPrevious attempt feedback (execution data, not instructions):\n' + json.dumps(stages.prompt.metadata.feedback, ensure_ascii=False, separators=(',', ':'))`), `metadata.feedback_tokens <= 300`; both records `mcp_calls[-1]["tool"] == "verify_patch"`; trace agent tools in order `get_task_context, generate_patch, apply_patch, generate_patch, apply_patch, run_relevant_tests, verify_patch`, plus host calls `verify_patch` and `get_task_context` between the two generates.
  - `test_agent_golden_raw_output_is_one_straight_run[A|B|C]` (§10.3): `Runtime(generator=ScriptedPatchGenerator([raw]))` → one run, `applied.diff` == golden, recommendation ACCEPT, no `by="host"` entry.
  - `test_agent_stops_after_three_generations` (§10.5): generator always returns `break_diff(ref)` → exactly 3 runs, last result FAILED, every run verified.
  - `test_agent_that_stops_early_is_verified_by_host` (§10.5): scripted model that ends after `generate_patch` → one run, trace last call `{"tool": "verify_patch", "by": "host"}`, run_record complete.
  - `test_agent_out_of_order_call_gets_error_and_run_is_verified` (§10.5): model calls `run_relevant_tests` right after `get_task_context` → tool reply starts `STATUS: ERROR` and contains `Tool order violation`; run still verified.
  - `test_generate_twice_without_apply_is_refused` (Review Focus 1).
  - `test_agent_verify_then_generate_skips_host_verify` (RF 2): scripted sequence context, generate (bad), apply, verify, generate, apply, tests, verify → no `by="host"` verify in trace, 2 runs.
  - `test_agent_exception_still_verifies_and_writes_trace` (RF 3): model whose `_generate` raises after the first tool call → FAILED, run verified, trace file exists.
  - `test_zero_arg_tool_ignores_model_arguments` (RF 4): scripted call `generate_patch` with `args={"diff": "x"}` → reply `STATUS: PASS`.
  - `test_mcp_transport_error_is_text_and_run_is_closed` (RF 5): monkeypatch `repair_apply_patch` to raise like `test_solve_tool_error_is_failed_not_raised` → reply `STATUS: ERROR`, run verified by host.
- [ ] **Step 2:** Run `…pytest tests/unit/test_agent_solve.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `run_generation` extraction; run `…pytest tests/unit/test_workflow.py -q` → PASS (no behaviour change).
- [ ] **Step 4:** Implement `tool_agent.py`, `repair_agent.md`, `Runtime.generator_choice`.
- [ ] **Step 5:** Run `…pytest tests/unit tests/m2/w78 -q` → PASS.
- [ ] **Step 6:** Commit `feat(agents): agent-chosen repair tools with host-held diff and rerun feedback`.

### Task 5: Option B — generate with the agent's own model

**Files:**
- Modify: `src/vgar/models/huggingface/hf_model.py` (`create_local_chat_model(..., revision: str | None = None, local_files_only: bool = False)` passes both to `from_pretrained`), `src/vgar/models/huggingface/local_hf_chat_model.py` (field `revision: str | None = None`)
- Create: `src/vgar/agents/agent_generator.py`
- Test: `tests/unit/test_agent_model_generator.py`

**Interfaces:**
- Produces:
  - `load_pinned_agent_model(profile: ModelProfile, max_new_tokens: int) -> LocalChatModel` — `create_local_chat_model(model_id=str(profile.snapshot), revision=profile.revision, local_files_only=True, max_new_tokens=max_new_tokens, device_map=profile.device_map, torch_dtype=profile.dtype)`; used by `run_agent_task` in real mode (`max_new_tokens = get_settings().model.max_new_tokens`).
  - `class AgentModelGenerator` — `mode = "real"`; `__init__(self, model, profile, policy)` raises `ValueError("Agent model revision <x> does not match pinned <y>")` when `model.revision != profile.revision`; `generate(prompt, profile, timeout_seconds) -> dict`:
    1. `rendered = model.tokenizer.apply_chat_template(prompt.messages, tokenize=False, add_generation_prompt=True)`; `"sha256:" + sha256(rendered)` ≠ `prompt.prompt_hash` → return `{"status": "ERROR", "mode": "real", "reason": "Agent model prompt bytes differ", "truncated": False, "raw_text": ""}` without generating.
    2. Generate on `model.llm.pipeline.model` with `hf_backend.generation_kwargs(policy.output_cap)` under `torch.inference_mode()`; truncation and `finish_reason` exactly as `hf_backend.execute`.
    3. Return `status, mode="real", generator_path="agent_model", raw_text, finish_reason, truncated, input_tokens, output_tokens, model_id, revision, generation_ms`.
  - `timeout_seconds` is not enforced (in-process); say so in the docstring.

- [ ] **Step 1: Write failing tests** with a fake model object (`SimpleNamespace(revision=…, tokenizer=FakeTokenizer, llm=SimpleNamespace(pipeline=SimpleNamespace(model=FakeHF)))`, `FakeHF.generate` records kwargs and returns input ids + `[7, eos]`; skip with `pytest.importorskip("torch")` only for the generate test):
  - `test_rendered_mismatch_returns_error_without_generating`: tokenizer renders `"other"` → `status == "ERROR"`, `FakeHF.calls == []`.
  - `test_revision_mismatch_is_a_clear_error`: `revision="main"` → `ValueError` matching `does not match pinned`.
  - `test_generation_uses_output_cap_and_greedy`: matching render → `FakeHF.calls[0]["max_new_tokens"] == 1536`, `do_sample is False`, result `generator_path == "agent_model"`, `truncated is False`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; wire `AgentModelGenerator` and `load_pinned_agent_model` into `run_agent_task` real branches.
- [ ] **Step 4:** Run `…pytest tests/unit tests/test_hf_model.py -q` → PASS except the known HF failure.
- [ ] **Step 5:** Commit `feat(agents): --generator agent reuses the agent model with M2 settings`.

### Task 6: CLI, docs, full suite, hand-off for real runs

**Files:**
- Modify: `src/vgar/cli.py` (`solve` gets `--agent` and `--generator {worker,agent}` (argparse default `None`, resolved to `worker` under `--agent`); any `--generator` without `--agent` → `parser.error("--generator requires --agent")`; `cmd_solve` calls `run_agent_task` when `--agent` and prints `[status]`, `[run]`, `[trace]`, `[reason]`), module docstring usage line, `README.md` solve section.
- Test: `tests/unit/test_agent_solve.py`

- Also add `solve --output-root PATH` (default `REPO_ROOT / "results/solve"`, the current `Runtime.output_root` default) passed to `Runtime(output_root=…)` for both flows.
- [ ] **Step 1: Failing tests** `test_cli_solve_agent_fake_exits_zero(tmp_path, capsys)`: `main(["solve", "--task", str(TASK), "--agent", "--output-root", str(tmp_path / "runs")])` → returns 0, stdout contains `[status] COMPLETED` and `[trace]`. `test_cli_generator_requires_agent`: `main(["solve", "--task", str(TASK), "--generator", "agent"])` → `SystemExit`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Full suite → no new failures vs Task 0.
- [ ] **Step 6:** Commit `feat(cli): vgar solve --agent [--generator worker|agent]`.
- [ ] **Step 7: Hand off real runs to the user** (do not run them). Commands:
  `.venv/Scripts/python.exe -m vgar.cli solve --mode real --agent --generator worker --task examples/m2/tasks/<case>.json` and the same with `--generator agent`, for `single_file_login`, `multi_file_invoice`, `missing_links`. Record per run: status, tool chain, seconds per task, memory behaviour (two model copies in A). Results go into an acceptance doc like phase 1 after the user pastes them.
