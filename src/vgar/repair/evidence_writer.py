"""Atomic, one-file-per-invocation M2 test evidence."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from vgar.contracts.evidence import EvidenceBundle, TestRunResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.stem}-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class RunHandle:
    path: Path
    run_id: str


def begin_run(artifact_dir: Path, *, task_id: str | None, source_repo: Path,
              source_hash_before: str, worktree_id: str, argv: list[str], cwd: Path,
              timeout_seconds: float) -> RunHandle:
    root = Path(artifact_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    path = root / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{run_id}.json"
    try:
        pytest_version = version("pytest")
    except PackageNotFoundError:
        pytest_version = None
    record: dict[str, Any] = {
        "run_id": run_id, "task_id": task_id, "started_utc": _utc_now(), "ended_utc": None,
        "source_repo": str(Path(source_repo).resolve()), "source_hash_before": source_hash_before,
        "source_hash_after": None, "worktree_id": worktree_id, "cwd": str(Path(cwd).resolve()),
        "argv": argv, "timeout_seconds": timeout_seconds, "python_executable": sys.executable,
        "python_version": sys.version.split()[0], "pytest_version": pytest_version,
        "environment": {
            "PYTHONPATH": os.pathsep.join((str(Path(cwd).resolve() / "src"), str(Path(cwd).resolve()))),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        "status": "NOT_RUN", "complete": False, "test_result": None,
    }
    _atomic_json(path, record)
    return RunHandle(path=path, run_id=run_id)


def finish_run(handle: RunHandle, result: TestRunResult, *, source_hash_after: str,
               bundle: EvidenceBundle | None = None) -> Path:
    record = json.loads(handle.path.read_text(encoding="utf-8"))
    if record.get("run_id") != handle.run_id or record.get("complete"):
        raise ValueError("Evidence handle mismatch or record already finalized")
    record.update({"ended_utc": _utc_now(), "source_hash_after": source_hash_after,
                   "argv": result.argv, "command": result.command,
                   "status": result.status, "complete": True, "test_result": result.model_dump(mode="json")})
    if bundle is not None:
        if bundle.run_id != handle.run_id:
            raise ValueError("Bundle run_id does not match evidence handle")
        record["evidence_bundle"] = bundle.model_dump(mode="json")
    _atomic_json(handle.path, record)
    return handle.path
