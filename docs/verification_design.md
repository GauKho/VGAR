# M2 W3–W4: baseline verification design

This milestone provides a disposable repository copy, a bounded pytest invocation, and durable pre-patch evidence. It does **not** apply a patch, select relevant tests, invoke a model, enforce graph/API rules, or expose a new MCP tool. Those belong to later milestones. M1 graph and M3 MCP code are unchanged.

## Execution sequence

1. Resolve the input repository and enumerate files. Ignore `.git`, virtual environments, caches, `artifacts`, `logs`, and `.vgar`; reject symlinks/junctions and over-limit files. Compute SHA-256 over ordered relative paths and file bytes.
2. Copy the input into a uniquely named workspace under `VGAR_M2_TEMP_ROOT` (or the configured D-drive parent). The workspace is separate from the source and deleted when the lease exits.
3. Write a unique pending JSON evidence record before starting pytest.
4. Launch only `sys.executable -m pytest` with a fixed argument prefix, validated repository-relative selectors, `shell=False`, workspace cwd, workspace-local `src` import path, timeout, and output-size guard. User-supplied shell flags and traversal paths are rejected.
5. Capture complete stdout/stderr, exit code, duration and a temporary JUnit XML report. Parse per-case outcomes into the JSON record; remove the temporary XML. Kill the process tree on timeout. Test assertion failures are `FAIL`; timeout, bad invocation or unavailable pytest are `ERROR`.
6. Re-hash the original source, assemble `EvidenceBundle`, atomically finalize the same JSON file, then delete the disposable workspace. If finalization fails, the pending record remains visibly incomplete.

Defaults: 16 MiB per input file, 256 MiB total input, 8 MiB maximum per stdout/stderr stream, 120 seconds for a baseline test. The output guard stops execution and marks `ERROR`/`VERIFICATION_INCOMPLETE`; it preserves the bytes captured up to termination. `output_truncated=true` denotes a breached output limit; a fast process may exit before the polling loop stops it, so the stored byte count can exceed the limit without data being dropped. Adjust source-size limits only after review if a larger benchmark repository is later in scope.

## Status and failure semantics

`PASS` means pytest exited zero and its output was complete. `FAIL` means pytest returned assertion failures with JUnit failure cases. `ERROR` means the verification process itself was incomplete or failed to execute reliably. `NOT_RUN` means a tier did not execute; it is never treated as passed. A baseline has `patch_applied=false`; `typecheck`, `lint`, `api_check`, and `structural_check` are all `NOT_RUN`. The baseline is evidence of the starting state, **not** proof that a patch fixes the task.

Current reason codes follow the W2 draft: `PATCH_PARSE_ERROR`, `PATCH_APPLY_FAILED`, `WORKTREE_ERROR`, `TEST_TIMEOUT`, `TEST_FAILED`, `TYPECHECK_FAILED`, `LINT_FAILED`, `API_BREAK`, `STRUCTURAL_VIOLATION`, `VERIFICATION_INCOMPLETE`, `INTERNAL_ERROR`. W3–W4 emits primarily test/worktree/internal reasons. Shared field names remain subject to M3 review before a protocol freeze.

## Safety and limitations

The source hash is checked before/after; edits are limited to the copy. The runner strips common secret-bearing environment variables and does not pass a shell command. However, arbitrary repository tests can still execute code and access host resources. This is a **disposable workspace**, not an OS/container security sandbox. Run untrusted benchmark repositories in Docker at the later integration milestone. Review raw stdout/stderr for secrets before committing evidence artifacts. The runner does not install dependencies; the selected Python interpreter must have pytest and the target project's dependencies available.

On Windows, set `VGAR_M2_TEMP_ROOT` to a writable D-drive directory if the default temporary folder causes permission errors. Every invocation writes a distinct JSON under `artifacts/m2/test-runs/`; interrupted executions retain a `complete=false` record.
