"""Run one pytest invocation and retain a complete JSON evidence file."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.contracts.evidence import TestRunResult  # noqa: E402
from vgar.contracts.repair import FailureReason  # noqa: E402
from vgar.repair.evidence_writer import begin_run, finish_run  # noqa: E402
from vgar.repair.test_runner import run_tests  # noqa: E402
from vgar.repair.workspace import fingerprint_source  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selectors", nargs="+", help="Repository-relative pytest file or node IDs")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts" / "m2" / "test-runs")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--task-id", default=None)
    args = parser.parse_args()
    temp_root = Path(os.getenv("VGAR_M2_TEMP_ROOT", str(ROOT.parent / "m2-temp"))).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    for key in ("TMP", "TEMP", "TMPDIR"):
        os.environ[key] = str(temp_root)
    before = fingerprint_source(ROOT)
    handle = begin_run(args.artifact_dir, task_id=args.task_id, source_repo=ROOT,
                       source_hash_before=before, worktree_id="development-test",
                       argv=[sys.executable, "-m", "pytest", *args.selectors], cwd=ROOT,
                       timeout_seconds=args.timeout_seconds)
    try:
        result = run_tests(ROOT, tuple(args.selectors), args.timeout_seconds)
    except Exception as exc:
        result = TestRunResult(status="ERROR", command="pytest invocation failed",
                               argv=[sys.executable, "-m", "pytest", *args.selectors],
                               exit_code=None, duration_ms=0, stdout="", stderr=str(exc),
                               reason=FailureReason(code="INTERNAL_ERROR", message=str(exc)))
    after = fingerprint_source(ROOT)
    path = finish_run(handle, result, source_hash_after=after)
    print(f"M2 test: {result.status}; artifact: {path}")
    return 0 if result.status == "PASS" and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
