search_symbols(query)
get_callers(symbol_id, depth)
get_callees(symbol_id, depth)

## Repair server (`vgar.mcp.servers.repair_server`, M3 W7-W8)

Client prefix `repair_`. Used by `vgar solve`, which connects only to this server
(`create_mcp_client(servers=("repair",))`). `vgar chat --task` connects graph, repository, execution and repair;
`vgar run --repo` connects graph, repository and execution (no edit tool).

Every tool returns the shared C4 envelope `{status, data, error, metadata}` (M3-W11-3). `status` is `PASS`
when the tool answered and `ERROR` when it could not. The engine's own answer is inside `data`, with the
engine status as `data.verdict` (`PASS` / `FAIL` / `ERROR`); a failed or incomplete repair is
`status: PASS, data.verdict: FAIL|ERROR`, not a tool error.

```
get_task_context(task_path, mode, output_root, work_root, config_path=None, ..., experiment=None, admission=None)
    -> data {verdict, run_dir, run_id, worktree_id, prompt{messages, rendered, input_tokens, template_hash,
             prompt_hash, version, tokenizer_label, metadata}, failed_cases, context}
    run started but not prepared -> data {verdict: ERROR, run_dir, reason, detail, recommendation: REJECT, ...}
apply_patch(run_dir, diff, generation=None)  -> data {verdict, reason, changed_files}
run_relevant_tests(run_dir)                  -> data {verdict, failing_tests, relevant_tests}
verify_patch(run_dir)                        -> data {verdict, reason, detail, recommendation, evidence, run_dir, run_record_path}
```

- Order per run is strict: `get_task_context -> apply_patch (once) -> run_relevant_tests (optional) -> verify_patch`.
  Out-of-order calls and a second `verify_patch` return `error.code = TOOL_ORDER_VIOLATION`; a `run_dir` that is
  not a repair run returns `RUN_NOT_FOUND`; a `run_dir` or `output_root` outside `VGAR_RUN_ROOT` returns
  `PATH_OUTSIDE_ROOT` / `ROOT_NOT_LEASED`. None of them changes the run. Any other failure is `INTERNAL_ERROR`
  (exception type only; the full message is in the audit line).
- `metadata.request_id` equals the `request_id` of the call's `tool_call` audit line, which carries
  `input_sha256` and `verdict`, never the diff text.
- `admission` (S15): the host's admission snapshot for a SWE-bench task (`vgar.agents.admitted`); the engine
  re-validates it. Agents never see this tool's arguments (`solve --agent` binds them, `chat` hides the tool).
- Agent hosts (`solve`, `solve --agent`, `chat`'s host calls) read the envelope through
  `vgar.agents.nodes.mcp_repair._call`, which flattens it to `{status: <verdict>, ...data}` or
  `{status: ERROR, reason: <error.code>, detail}`; a dead server or lost connection is `MCP_TRANSPORT_ERROR`.
- `verify_patch` is the single finalizer once a run exists: it cleans the private worktree and
  publishes `evidence_bundle.json` (`recommendation` ACCEPT / REVISE / REJECT).
- State lives in the run directory (`session.json` next to `run_record.json`), so each call may be a
  fresh server process. Only tasks in `configs/m2/trusted_fixtures.json` run; writes stay inside the
  run's private worktree under `work_root`.
- Every accepted call is appended to `run_record.mcp_calls` as
  `{tool, input_sha256, started_utc, duration_ms, status}`; `run_record.mcp_scope` is `repair_server`.

## Repository and execution servers (M3-W11-2, D7; security S1-S5)

Both servers are read-only/run-only and rooted by the host, never by the model.

```
repository_read_file(path)   -> data {path, content, truncated, size_bytes}; metadata.untrusted = true
execution_run_pytest(selector) -> data {selector, verdict: PASS|FAIL, exit_code, stdout, stderr, truncated}
```

- Root: environment variable `VGAR_LEASE_ROOT`, set by the host through
  `create_mcp_client(..., extra_env=...)`. `vgar run`: the disposable sandbox copy. `vgar chat`: the private
  worktree of the repair run the host opened. Paths are resolved (symlinks, `..`) and must stay inside it.
- Selectors: environment variable `VGAR_ALLOWED_SELECTORS` (JSON list). A selector is allowed if it equals an
  entry or starts with `<entry>/` or `<entry>::`, contains no whitespace, does not start with `-`, has no `..`
  and its path stays in the root. argv is fixed: `python -m pytest -q -p no:cacheprovider <selector>`, no shell.
- Limits (server constants in `vgar.mcp.tooling`): `READ_FILE_MAX_BYTES = 65536`, `PYTEST_TIMEOUT_SECONDS = 120`,
  `PYTEST_OUTPUT_CAP = 12000`. No tool takes them as arguments.
- Runner (C6): `vgar.mcp.pytest_runner.run_selector` wraps M2's `run_bounded`, which kills the whole process
  tree on timeout (Windows job object, POSIX process group) and stops the child once output passes the cap.
- Error codes (C4, none retryable with unchanged arguments): `ROOT_NOT_LEASED`, `PATH_OUTSIDE_ROOT`,
  `SELECTOR_REJECTED`, `TIMEOUT`, `INVALID_ARGUMENT` (for example a non-UTF-8 file), `INTERNAL_ERROR`.
- `error.retryable` (S10, every envelope tool): derived from `vgar.mcp.schemas.KNOWN_ERROR_CODES`, never set by
  the tool. Only `GRAPH_NOT_READY` is `true`; every other code, `TIMEOUT` included, is `false`. A code outside
  the table is returned as `INTERNAL_ERROR`. `TOOL_ERROR` was removed with the C4 envelope.
- Removed in W11: `repository_apply_patch` and every `repo_path` / `timeout_seconds` parameter.

