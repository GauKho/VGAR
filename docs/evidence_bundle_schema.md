# M2 EvidenceBundle contract (W3–W4)

Python definitions: `vgar.contracts.repair` and `vgar.contracts.evidence`. Both use Pydantic 2 and reject unknown fields. No `schema_version` field is present. M1 `graph_version` is a graph snapshot identifier, not an M2 schema number.

## Public objects

| Object | Required fields | Meaning |
|---|---|---|
| `FailureReason` | `code`, `message` | Stable reason code and human-readable detail. |
| `PatchApplyResult` | `status`, `patch_applied`, `worktree_id` | Reserved patch boundary; no patch engine is implemented at W3–W4. `changed_files` defaults empty, `error` null. |
| `TestRunResult` | `status`, `command`, `argv`, `exit_code`, `duration_ms`, `stdout`, `stderr` | One pytest process result. Optional JUnit cases/counts, timeout, byte counts, completion and truncation flags. |
| `CheckResult` | `status` | Defaults to `NOT_RUN`; used for future verification tiers. |
| `VerificationResult` | `patch_applied`, `tests` | Test result plus typecheck/lint/API/structural checks and reasons. |
| `EvidenceBundle` | `run_id`, `source_repo`, `source_hash_before`, `source_hash_after`, `worktree_id`, `verification` | Correlates source integrity and verification. `task_id`, artifact path and metadata are optional. |

The saved JSON additionally contains `run_id`, UTC timestamps, source/cwd/workspace identifiers, actual command/argv, Python and pytest versions, selected non-secret environment settings, timeout, `status`, record-level `complete`, full `test_result`, and `evidence_bundle` for baseline runs. The JUnit XML is embedded as parsed case data and removed. `test_result.complete=false` on timeout/output interruption; record-level `complete=true` means the JSON was finalized even if the test did not finish. A crash before finalization leaves record-level `complete=false` and `status=NOT_RUN`.

## Example baseline fragment

```json
{
  "run_id": "unique-uuid",
  "task_id": "sample-auth-baseline",
  "source_hash_before": "sha256-hex",
  "source_hash_after": "sha256-hex",
  "verification": {
    "patch_applied": false,
    "tests": {
      "status": "PASS",
      "command": "python -m pytest tests/test_auth.py",
      "argv": ["python", "-m", "pytest", "tests/test_auth.py"],
      "exit_code": 0,
      "duration_ms": 1000,
      "stdout": "1 passed",
      "stderr": ""
    },
    "typecheck": {"status": "NOT_RUN", "reason": null},
    "lint": {"status": "NOT_RUN", "reason": null},
    "api_check": {"status": "NOT_RUN", "reason": null},
    "structural_check": {"status": "NOT_RUN", "reason": null},
    "reasons": []
  }
}
```

The example is illustrative, not a saved run. For exact serialized output, inspect a generated JSON in `artifacts/m2/test-runs/`. Share the Pydantic JSON schema and sample artifact with M3 before adding MCP tools or changing shared names.
