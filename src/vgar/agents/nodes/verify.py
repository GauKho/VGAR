from __future__ import annotations

from pathlib import Path

from vgar.agents.runtime import Runtime
from vgar.agents.state import VGARState
from vgar.repair.test_runner import run_tests
from vgar.repair.workspace import fingerprint_source

_TAIL = 2000


def _not_run() -> dict:
    return {"status": "NOT_RUN"}


def verify(state: VGARState, runtime: Runtime) -> dict:
    """Independent evidence: never trusts what the agent says about its own patch."""
    workspace = Path(state["workspace_path"])
    modified = fingerprint_source(workspace) != state["source_hash_before"]

    try:
        run = run_tests(workspace, tuple(state["failing_tests"]), runtime.test_timeout)
    except ValueError as exc:  # invalid selector etc.
        tests = {"status": "ERROR", "reason_code": "VERIFICATION_INCOMPLETE", "message": str(exc)}
        failure_class = "VERIFICATION_INCOMPLETE"
    else:
        tests = {
            "status": run.status,
            "exit_code": run.exit_code,
            "duration_ms": run.duration_ms,
            "counts": run.case_counts,
            "failed_cases": [c.name for c in run.cases if c.status in ("FAIL", "ERROR")],
            "output_tail": (run.stdout + run.stderr)[-_TAIL:],
            "reason_code": run.reason.code if run.reason else None,
        }
        failure_class = run.reason.code if run.reason else None

    passed = tests["status"] == "PASS" and modified
    if tests["status"] == "PASS" and not modified:
        failure_class = "NO_PATCH"  # tests already passed without any change

    reasons = [] if passed else [failure_class or "TEST_FAILED"]
    evidence = {
        "patch_applied": modified,
        "tests": tests,
        "typecheck": _not_run(),
        "lint": _not_run(),
        "api_check": _not_run(),
        "structural_check": _not_run(),
        "reasons": reasons,
        "passed": passed,
    }
    return {
        "evidence": evidence,
        "last_failure_class": None if passed else (failure_class or "TEST_FAILED"),
    }
