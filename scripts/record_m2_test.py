"""Run one pytest invocation and retain a complete JSON evidence file."""

from __future__ import annotations

import argparse
import os
import sys
import math
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.contracts.evidence import TestRunResult  # noqa: E402
from vgar.contracts.repair import FailureReason  # noqa: E402
from vgar.repair.evidence_writer import begin_run, finish_run, update_pending  # noqa: E402
from vgar.repair.test_runner import run_tests  # noqa: E402
from vgar.repair.source_preflight import snapshot_source  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selectors", nargs="+", help="Repository-relative pytest file or node IDs")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts" / "m2" / "test-runs")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--preflight-timeout-seconds", type=float, default=30)
    parser.add_argument("--task-id", default=None)
    args = parser.parse_args()
    if any(not math.isfinite(value) or value <= 0 for value in (args.timeout_seconds, args.preflight_timeout_seconds)):
        parser.error("timeouts must be positive and finite")
    before, after = "", ""
    phase = "PREFLIGHT_BEFORE"
    started = time.monotonic()
    result = None
    handle = begin_run(args.artifact_dir, task_id=args.task_id, source_repo=ROOT,
                       source_hash_before="", worktree_id="development-test",
                       argv=[sys.executable, "-m", "pytest", *args.selectors], cwd=ROOT,
                       timeout_seconds=args.timeout_seconds)
    try:
        update_pending(handle, phase=phase)
        temp_root = Path(os.getenv("VGAR_M2_TEMP_ROOT", str(ROOT.parent / "m2-temp"))).resolve()
        temp_root.mkdir(parents=True, exist_ok=True)
        for key in ("TMP", "TEMP", "TMPDIR"):
            os.environ[key] = str(temp_root)
        snapshot = snapshot_source(ROOT, args.preflight_timeout_seconds)
        before = snapshot["fingerprint"]
        update_pending(handle, source_hash_before=before, source_scope=snapshot["scope"], preflight_before=snapshot)
        phase = "PYTEST"
        update_pending(handle, phase=phase)
        result = run_tests(ROOT, tuple(args.selectors), args.timeout_seconds)
        phase = "PREFLIGHT_AFTER"
        update_pending(handle, phase=phase, pytest_result=result.model_dump(mode="json"))
        snapshot = snapshot_source(ROOT, args.preflight_timeout_seconds)
        after = snapshot["fingerprint"]
        update_pending(handle, preflight_after=snapshot)
        if before != after:
            raise RuntimeError("Input source changed during pytest")
        phase = "DONE"
        update_pending(handle, phase=phase)
    except (Exception, KeyboardInterrupt) as exc:
        trace = traceback.format_exc()
        payload = result.model_dump(mode="json") if result is not None else dict(
            command="pytest not started", argv=[sys.executable, "-m", "pytest", *args.selectors],
            exit_code=None, duration_ms=round((time.monotonic() - started) * 1000), stdout="", stderr="")
        code = "TEST_TIMEOUT" if isinstance(exc, TimeoutError) else ("WORKTREE_ERROR" if phase.startswith("PREFLIGHT") else "INTERNAL_ERROR")
        payload.update(status="ERROR", complete=False, stderr=payload["stderr"] + "\n" + trace,
                       reason=FailureReason(code=code, message=f"{phase}: {exc}"), timeout_seconds=args.timeout_seconds)
        result = TestRunResult(**payload)
    path = finish_run(handle, result, source_hash_after=after)
    print(f"M2 test: {result.status}; artifact: {path}")
    return 0 if result.status == "PASS" and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
