search_symbols(query)
get_callers(symbol_id, depth)
get_callees(symbol_id, depth)

## Repair server (`vgar.mcp.servers.repair_server`, M3 W7-W8)

Client prefix `repair_`. Used by `vgar solve`, which connects only to this server
(`create_mcp_client(servers=("repair",))`); `vgar run`/`chat` keep the three servers above.

```
get_task_context(task_path, mode, output_root, work_root, config_path=None)
    -> {status, run_dir, run_id, worktree_id, prompt{messages, rendered, input_tokens, template_hash,
        prompt_hash, version, tokenizer_label, metadata}, failed_cases, context}
    on failure -> {status: ERROR, run_dir, reason, detail, recommendation: REJECT, run_record_path}
apply_patch(run_dir, diff, generation=None)  -> {status, reason, changed_files}
run_relevant_tests(run_dir)                  -> {status, failing_tests, relevant_tests}
verify_patch(run_dir)                        -> {status, reason, detail, recommendation, evidence, run_dir, run_record_path}
```

- Order per run is strict: `get_task_context -> apply_patch (once) -> run_relevant_tests (optional) -> verify_patch`.
  Out-of-order calls, a second `verify_patch` and an unknown `run_dir` return
  `{status: ERROR, reason: TOOL_ERROR, detail}` and change nothing.
- `verify_patch` is the single finalizer once a run exists: it cleans the private worktree and
  publishes `evidence_bundle.json` (`recommendation` ACCEPT / REVISE / REJECT).
- State lives in the run directory (`session.json` next to `run_record.json`), so each call may be a
  fresh server process. Only tasks in `configs/m2/trusted_fixtures.json` run; writes stay inside the
  run's private worktree under `work_root`.
- Every accepted call is appended to `run_record.mcp_calls` as
  `{tool, input_sha256, started_utc, duration_ms, status}`; `run_record.mcp_scope` is `repair_server`.
