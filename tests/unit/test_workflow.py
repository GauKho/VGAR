"""vgar solve: LangGraph runs the M2 pipeline exactly once and reports its evidence."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from vgar.agents.runtime import Runtime
from vgar.agents.workflow import run_task
from vgar.models.generator import FakeGenerator

REPO = Path(__file__).resolve().parents[2]
TASK = REPO / "examples/m2/tasks/single_file_login.json"


def test_solve_fake_completes_with_m2_evidence(tmp_path):
    state = asyncio.run(run_task(task_path=TASK, runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "COMPLETED" and state["attempts"] == 1
    assert state["repair_status"] == "PASS" and state["failure_reason"] is None
    assert state["evidence"]["verification"]["patch_applied"] is True
    assert Path(state["run_record_path"]).is_file()


def test_solve_invalid_diff_fails_once_without_retry(tmp_path):
    runtime = Runtime(output_root=tmp_path / "runs", generator=FakeGenerator("not a diff"))
    state = asyncio.run(run_task(task_path=TASK, runtime=runtime))
    assert state["status"] == "FAILED" and state["attempts"] == 1
    assert state["failure_reason"] == "PATCH_PARSE_ERROR"


def test_solve_untrusted_task_fails_without_touching_source(tmp_path):
    task = json.loads(TASK.read_text(encoding="utf-8"))
    shutil.copytree(REPO / "examples/m2/snapshots/single_file_login", tmp_path / "src")
    (tmp_path / "src/auth.py").write_bytes(b"def login(value):\n    return False\n")
    before = (tmp_path / "src/auth.py").read_bytes()
    task.update(source_repo=str(tmp_path / "src"),
                bundle_directory=str(REPO / "examples/m2/handoffs/single_file_login"))
    (tmp_path / "task.json").write_text(json.dumps(task), encoding="utf-8")
    state = asyncio.run(run_task(task_path=tmp_path / "task.json", runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "FAILED" and state["failure_reason"]
    assert (tmp_path / "src/auth.py").read_bytes() == before


def test_solve_unregistered_task_id_fails_instead_of_raising(tmp_path):
    task = json.loads(TASK.read_text(encoding="utf-8"))
    task.update(task_id="my_new_task",
                source_repo=str(REPO / "examples/m2/snapshots/single_file_login"),
                bundle_directory=str(REPO / "examples/m2/handoffs/single_file_login"))
    (tmp_path / "task.json").write_text(json.dumps(task), encoding="utf-8")
    state = asyncio.run(run_task(task_path=tmp_path / "task.json", runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "FAILED" and state["repair_status"] == "ERROR"
    assert "FileNotFoundError" in state["failure_reason"]
