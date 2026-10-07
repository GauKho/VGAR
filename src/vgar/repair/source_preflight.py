"""Bounded source fingerprint worker: no model loading or child execution."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from vgar.source_scope import SourceScope
from vgar.repair.workspace import fingerprint_source


def snapshot_source(root: Path, timeout_seconds: float) -> dict:
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("preflight timeout must be positive and finite")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    argv = [sys.executable, "-B", "-m", "vgar.repair.source_preflight", str(root)]
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, env=environment, capture_output=True, text=True, encoding="utf-8",
                                   timeout=timeout_seconds, shell=False)
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills/waits for this single worker. Worker never spawns children.
        raise TimeoutError(f"Source preflight exceeded {timeout_seconds} seconds") from error
    if completed.returncode != 0:
        raise RuntimeError(f"Source preflight exited {completed.returncode}: {completed.stderr}")
    payload = json.loads(completed.stdout)
    payload.update(duration_seconds=time.monotonic() - started, argv=argv,
                   stdout=completed.stdout, stderr=completed.stderr, exit_code=completed.returncode)
    return payload


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve(strict=True)
    scope = SourceScope.for_repository(root)
    print(json.dumps({"fingerprint": fingerprint_source(root, scope=scope), "scope": scope.metadata()}))
