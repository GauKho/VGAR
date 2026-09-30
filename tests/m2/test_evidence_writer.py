from __future__ import annotations

import json
import os
from pathlib import Path

from vgar.contracts.evidence import TestRunResult as M2TestRunResult
from vgar.repair.evidence_writer import begin_run, finish_run


def test_pending_and_finished_are_one_file(tmp_path: Path) -> None:
    handle = begin_run(tmp_path, task_id="t1", source_repo=tmp_path,
                       source_hash_before="abc", worktree_id="wt-1",
                       argv=["python", "-m", "pytest"], cwd=tmp_path, timeout_seconds=10)
    pending = json.loads(handle.path.read_text(encoding="utf-8"))
    assert pending["complete"] is False
    assert pending["status"] == "NOT_RUN"
    assert pending["environment"]["PYTHONPATH"] == os.pathsep.join((str(tmp_path / "src"), str(tmp_path)))
    assert pending["environment"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    result = M2TestRunResult(status="PASS", command="python -m pytest", argv=["python", "-m", "pytest"],
                             exit_code=0, duration_ms=10, stdout="✓ UTF-8", stderr="")
    finished_path = finish_run(handle, result, source_hash_after="abc")
    record = json.loads(finished_path.read_text(encoding="utf-8"))
    assert finished_path == handle.path
    assert record["complete"] is True
    assert record["test_result"]["stdout"] == "✓ UTF-8"
    assert record["source_hash_before"] == record["source_hash_after"]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_two_runs_have_distinct_paths_and_interrupted_is_pending(tmp_path: Path) -> None:
    args = dict(task_id=None, source_repo=tmp_path, source_hash_before="x", worktree_id="wt-1",
                argv=["pytest"], cwd=tmp_path, timeout_seconds=5)
    first = begin_run(tmp_path, **args)
    second = begin_run(tmp_path, **args)
    assert first.path != second.path
    assert json.loads(first.path.read_text(encoding="utf-8"))["complete"] is False
    assert len(list(tmp_path.glob("*.json"))) == 2
