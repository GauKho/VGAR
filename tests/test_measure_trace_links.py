"""TR-1: the trace link measurement script.

Spec: docs/superpowers/specs/2026-11-10-tv2-tr-1-trace-links-design.md
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from itertools import count
from pathlib import Path
from typing import Any

import pytest

from vgar.evaluation.retrieval.dataset import split_of

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_trace_links.py"
_spec = importlib.util.spec_from_file_location("measure_trace_links", SCRIPT)
assert _spec is not None and _spec.loader is not None
measure_trace_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure_trace_links)


def _task_id(split: str = "dev", skip: int = 0) -> str:
    ids = (f"a__b-{number}" for number in count() if split_of(f"a__b-{number}") == split)
    for _ in range(skip):
        next(ids)
    return next(ids)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _checkout(root: Path, instance_id: str) -> str:
    repo = root / instance_id
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "m.py").write_text("def alpha_one():\n    return 1\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    return _git(repo, "rev-parse", "HEAD")


def _task(instance_id: str, commit: str, split: str = "dev", **extra: Any) -> dict[str, Any]:
    return {"instance_id": instance_id, "repo": "a/b", "base_commit": commit, "problem_statement": "`alpha_one` fails",
            "changed_source_files": ["pkg/m.py"], "split": split, **extra}


def _manifest(*tasks: dict[str, Any], split: str = "dev") -> dict[str, Any]:
    return {"split": split, "tasks": list(tasks)}


def test_measure_dev_task(tmp_path: Path) -> None:
    instance_id = _task_id()
    result = measure_trace_links.measure(_manifest(_task(instance_id, _checkout(tmp_path, instance_id))), tmp_path)
    assert result["skipped"] == [] and [row["task_id"] for row in result["tasks"]] == [instance_id]
    assert result["tasks"][0]["gold_files"] == 1 and result["summary"]["all"]["n"] == 1


def test_empty_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nonempty"):
        measure_trace_links.measure(_manifest(), tmp_path)


def test_duplicate_tasks_are_refused(tmp_path: Path) -> None:
    task = _task(_task_id(), "0" * 40)
    with pytest.raises(ValueError, match="Duplicate"):
        measure_trace_links.measure(_manifest(task, task), tmp_path)


def test_refuses_heldout_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="heldout"):
        measure_trace_links.measure(_manifest(_task(_task_id("heldout"), "0" * 40, "heldout"), split="heldout"), tmp_path)


def test_refuses_heldout_task_in_dev_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="heldout"):
        measure_trace_links.measure(_manifest(_task(_task_id("heldout"), "0" * 40)), tmp_path)


def test_allow_heldout_still_needs_the_freeze(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        measure_trace_links.measure(_manifest(_task(_task_id("heldout"), "0" * 40, "heldout"), split="heldout"), tmp_path, allow_heldout=True)


def test_head_mismatch_is_skipped(tmp_path: Path) -> None:
    instance_id = _task_id()
    _checkout(tmp_path, instance_id)
    result = measure_trace_links.measure(_manifest(_task(instance_id, "0" * 40)), tmp_path)
    assert result["tasks"] == [] and result["skipped"] == [{"instance_id": instance_id, "reason": "head_mismatch"}]


def test_missing_checkout_is_skipped_and_the_run_continues(tmp_path: Path) -> None:
    missing, present = _task_id(), _task_id(skip=1)
    commit = _checkout(tmp_path, present)
    result = measure_trace_links.measure(_manifest(_task(missing, commit), _task(present, commit)), tmp_path)
    assert result["skipped"] == [{"instance_id": missing, "reason": "missing_checkout"}]
    assert [row["task_id"] for row in result["tasks"]] == [present]


def test_failing_tests_are_never_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original = measure_trace_links.TaskOverlayBuilder.build

    def spy(self: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(measure_trace_links.TaskOverlayBuilder, "build", spy)
    instance_id = _task_id()
    commit = _checkout(tmp_path, instance_id)
    measure_trace_links.measure(_manifest(_task(instance_id, commit, FAIL_TO_PASS=["tests/test_x.py::test_y"])), tmp_path)
    assert calls == [((instance_id, "`alpha_one` fails"), {})]


def test_main_writes_json(tmp_path: Path) -> None:
    instance_id = _task_id()
    repositories = tmp_path / "repos"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest(_task(instance_id, _checkout(repositories, instance_id)))), encoding="utf-8")
    output = tmp_path / "out" / "trace.json"
    code = measure_trace_links.main(["--manifest", str(manifest), "--repositories", str(repositories), "--output", str(output)])
    assert code == 0 and json.loads(output.read_text(encoding="utf-8"))["tasks"][0]["task_id"] == instance_id
