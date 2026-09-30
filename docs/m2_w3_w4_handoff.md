# M2 W3–W4 handoff — 2026-09-30

## Delivered

- `vgar.contracts.repair`: `FailureReason`, `PatchApplyResult`, shared `PASS/FAIL/ERROR/NOT_RUN` vocabulary.
- `vgar.contracts.evidence`: `TestRunResult`, per-case details, `CheckResult`, `VerificationResult`, `EvidenceBundle`.
- `vgar.repair.workspace`: bounded disposable source copy, path/symlink policy, source SHA-256, cleanup.
- `vgar.repair.test_runner`: shell-free pytest, workspace-local imports, JUnit parsing, timeout/output guard and Windows process-tree termination through Job Objects.
- `vgar.repair.evidence_writer`: unique pending/final JSON per invocation, atomic replacement and visible incomplete record on interruption.
- `vgar.repair.baseline`: source → copy → pytest → evidence → cleanup. No patch is applied.
- `scripts/record_m2_test.py` and `scripts/run_m2_baseline.py` for development test evidence and baseline capture.

The M1 graph backend and M3 MCP server/tool surface were not changed. In particular, `execution_server.py` still exposes only its existing health behavior. The old `vgar_mcp_mvp` project was not changed.

## Verification evidence

- Candidate full suite: `M2_week_3+4/VGAR_candidate/artifacts/m2/test-runs/20260930T093128297312Z-db4b79d60f4f406280761ec8626ed9ab.json` — 59 passed, 1 skipped; source hash unchanged.
- Integrated final full suite: `VGAR/artifacts/m2/test-runs/20260930T094850907502Z-8ffe7c74094140dbb4c5447070a935c9.json` — 60 passed, 1 skipped; source hash unchanged.
- Integrated clean baseline: `VGAR/artifacts/m2/test-runs/20260930T094926633646Z-bca59c6e5ce64062a3ee9ac5a4c2cc20.json` — PASS; source hash unchanged.
- Deliberately failing baseline: `M2_week_3+4/VGAR_candidate/artifacts/m2/test-runs/20260930T091531141463Z-7507513c8e7d4a1ea31c8d3b387a5366.json` — expected FAIL, `TEST_FAILED`, source hash unchanged.
- `M2_week_3+4/artifacts/input-manifest.json`: 107 original non-generated files; zero conflicts before transfer.
- `M2_week_3+4/artifacts/transfer-manifest.json`: before/after SHA-256 for 24 transferred files. Original modified files were also copied to `M2_week_3+4/artifacts/pre-transfer/`.

The one skipped test tries to create a Windows symlink; that operation is unavailable in this local environment. The path/symlink rejection logic remains in the workspace code. Earlier full-suite failures were due to an omitted `sample_graph.db` fixture in the isolated copy and an interpreter without Jedi; the final suite ran using an already installed Python 3.11 environment containing Jedi 0.20.0. No package was installed into or source file changed in the frozen project.

## Contract handoff to M3

Import `run_baseline` from `vgar.repair.baseline` for pre-patch evidence. `EvidenceBundle.model_dump(mode="json")` is the transport-friendly object; the exact fields are documented in `docs/evidence_bundle_schema.md`. M3 should review shared field names and the failure taxonomy before adding MCP execution tools. There is no `schema_version` field.

## Explicitly deferred

Patch parsing/application, LLM repair loop, graph-guided relevant-test selection, typecheck/lint/API/structural execution, full graph impact verification, SWE-bench harness grading and security isolation for untrusted repositories. Current `NOT_RUN` tiers must not be reported as passes. The disposable file copy protects the source from accidental edits; it does not sandbox untrusted code from the host OS.
