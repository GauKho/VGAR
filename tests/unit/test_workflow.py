"""vgar solve: LangGraph runs the M2 pipeline exactly once and reports its evidence."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

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
    assert state["status"] == "FAILED"
    assert state["failure_reason"].startswith("INTERNAL_ERROR: ")
    assert "approved fixtures" in state["failure_reason"]
    assert (tmp_path / "src/auth.py").read_bytes() == before


def test_solve_unregistered_task_id_fails_instead_of_raising(tmp_path):
    task = json.loads(TASK.read_text(encoding="utf-8"))
    task.update(task_id="my_new_task",
                source_repo=str(REPO / "examples/m2/snapshots/single_file_login"),
                bundle_directory=str(REPO / "examples/m2/handoffs/single_file_login"))
    (tmp_path / "task.json").write_text(json.dumps(task), encoding="utf-8")
    state = asyncio.run(run_task(task_path=tmp_path / "task.json", runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "FAILED" and state["repair_status"] == "ERROR"
    assert state["recommendation"] == "REJECT"
    assert "approved fixtures" in state["failure_reason"]


GOLDEN = REPO / "tests/fixtures/m2/golden_v11"
TOOLS = ["get_task_context", "apply_patch", "run_relevant_tests", "verify_patch"]


def record_of(state):
    return json.loads(Path(state["run_record_path"]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("letter,case", [("A", "single_file_login"), ("B", "multi_file_invoice"), ("C", "missing_links")])
def test_solve_through_mcp_reproduces_golden(letter, case, tmp_path):
    raw = (GOLDEN / letter / "raw_model_output.txt").read_text(encoding="utf-8")
    state = asyncio.run(run_task(task_path=REPO / f"examples/m2/tasks/{case}.json",
                                 runtime=Runtime(output_root=tmp_path / "runs", generator=FakeGenerator(raw))))
    run_dir = Path(state["run_record_path"]).parent
    assert (run_dir / "prompt.txt").read_bytes() == (GOLDEN / letter / "prompt.txt").read_bytes()
    assert (run_dir / "applied.diff").read_bytes() == (GOLDEN / letter / "applied.diff").read_bytes()
    record = record_of(state)
    assert [c["tool"] for c in record["mcp_calls"]] == TOOLS and record["mcp_scope"] == "repair_server"
    assert state["recommendation"] == "ACCEPT" and state["status"] == "COMPLETED"


class BrokenGenerator:
    mode = "fake"

    def generate(self, prompt, profile, timeout_seconds):
        raise RuntimeError("boom")


def test_solve_generator_error_rejects_and_cleans_up(tmp_path):
    state = asyncio.run(run_task(task_path=TASK, runtime=Runtime(output_root=tmp_path / "runs", generator=BrokenGenerator())))
    assert state["status"] == "FAILED" and state["recommendation"] == "REJECT"
    record = record_of(state)
    assert [c["tool"] for c in record["mcp_calls"]] == ["get_task_context", "apply_patch", "verify_patch"]
    assert record["stages"]["cleanup"]["status"] == "PASS" and record["complete"] is True


def test_solve_tool_error_is_failed_not_raised(tmp_path, monkeypatch):
    original = Runtime.repair_tools

    class Exploding:
        async def ainvoke(self, args):
            raise RuntimeError("transport down")

    async def patched(self):
        tools = dict(await original(self))
        tools["repair_apply_patch"] = Exploding()
        return tools

    monkeypatch.setattr(Runtime, "repair_tools", patched)
    state = asyncio.run(run_task(task_path=TASK, runtime=Runtime(output_root=tmp_path / "runs")))
    assert state["status"] == "FAILED" and state["failure_reason"]
    assert [c["tool"] for c in record_of(state)["mcp_calls"]] == ["get_task_context", "verify_patch"]


def test_solve_keep_keeps_the_private_worktree(tmp_path):
    state = asyncio.run(run_task(task_path=TASK, runtime=Runtime(output_root=tmp_path / "runs", keep_workspace=True)))
    try:
        worktree = Path(record_of(state)["stages"]["workspace"]["path"])
        assert state["status"] == "COMPLETED" and worktree.is_dir()
        assert (worktree / "auth.py").is_file()
    finally:
        shutil.rmtree(state["work_dir"], ignore_errors=True)
