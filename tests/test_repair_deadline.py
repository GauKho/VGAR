"""vgar.repair.deadline guards the execution server's native test runs (run_relevant_tests via diff_tests_provider)."""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pytest

from vgar.repair.config import load_task
from vgar.repair.deadline import DeadlineExecutor, require_trusted_fixture
from vgar.repair.executor import GLOBAL_DEADLINE

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "examples/m2/tasks/single_file_login.json"


def test_approved_fixture_is_trusted():
    require_trusted_fixture(load_task(TASK))


def test_tampered_fixture_is_refused(tmp_path):
    task = load_task(TASK)
    copy = tmp_path / "repo"
    shutil.copytree(task.source_repo, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    victim = next(p for p in sorted(copy.rglob("*.py")) if "__pycache__" not in p.parts)
    victim.write_text(victim.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="byte-verified approved fixtures"):
        require_trusted_fixture(task.model_copy(update={"source_repo": copy}))


def test_untrusted_task_is_refused():
    task = load_task(TASK)
    with pytest.raises(ValueError, match="byte-verified approved fixtures"):
        require_trusted_fixture(task.model_copy(update={"trusted_fixture": False}))


def test_deadline_executor_stops_once_the_deadline_has_passed(tmp_path):
    executor = DeadlineExecutor(None, time.monotonic() - 1, 1024)
    with pytest.raises(TimeoutError, match=GLOBAL_DEADLINE):
        executor.run((sys.executable, "-m", "pytest"), tmp_path, 30)
