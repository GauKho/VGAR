"""Record a disposable pre-patch baseline for a Python repository."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.repair.baseline import run_baseline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_repo", type=Path)
    parser.add_argument("selectors", nargs="+", help="Repository-relative pytest file/node IDs")
    parser.add_argument("--task-id", default="baseline")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts" / "m2" / "test-runs")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    temp_root = Path(os.getenv("VGAR_M2_TEMP_ROOT", str(ROOT.parent / "m2-temp"))).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    for key in ("TMP", "TEMP", "TMPDIR"):
        os.environ[key] = str(temp_root)
    bundle = run_baseline(args.source_repo, tuple(args.selectors), args.artifact_dir, args.task_id,
                          temp_root=temp_root, timeout_seconds=args.timeout_seconds)
    status = bundle.verification.tests.status
    print(f"M2 baseline: {status}; source_unchanged: {bundle.source_hash_before == bundle.source_hash_after}")
    print(f"Evidence: {bundle.artifact_path}")
    return 0 if status == "PASS" and bundle.source_hash_before == bundle.source_hash_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
