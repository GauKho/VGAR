"""Catch task/config paths resolved against the CWD, and a non-V11 default policy."""
from pathlib import Path

from vgar.repair.config import CONFIG_DIR, REPO_ROOT, load_config, load_task
from vgar.repair.contracts import RepairPolicy
from w78_support import REPO


def test_repo_root_is_this_repository():
    assert REPO_ROOT == REPO


def test_load_task_resolves_paths_relative_to_task_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = load_task(REPO / "examples/m2/tasks/single_file_login.json")
    assert task.source_repo == (REPO / "examples/m2/snapshots/single_file_login").resolve()
    assert task.bundle_directory == (REPO / "examples/m2/handoffs/single_file_login").resolve()


def test_load_config_expands_user_home_in_model_paths():
    policy, profile = load_config(CONFIG_DIR / "demo.json")
    assert policy.prompt_version == "m2-w78-v11"
    assert profile.snapshot.is_relative_to(Path.home())
    assert profile.interpreter == (REPO / ".venv/Scripts/python.exe").resolve()


def test_repair_policy_defaults_to_v11():
    assert RepairPolicy().prompt_version == "m2-w78-v11"
