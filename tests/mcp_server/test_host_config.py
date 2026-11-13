"""The servers work only on what the host configuration declares (proposal §10.5: only allowlisted repositories)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.mcp.host_config import check_host_config

ROOT = Path(__file__).resolve().parents[2]


def full(tmp_path: Path, **extra: str) -> dict[str, str]:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return {"VGAR_REPOSITORY_ROOT": str(repo), "VGAR_LEASE_ROOT": str(repo),
            "VGAR_GRAPH_DATABASE": str(tmp_path / "g.db"), "VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl"), **extra}


def test_full_configuration_has_no_problems(tmp_path):
    for server in ("graph", "execution", "repository"):
        assert check_host_config(server, full(tmp_path)) == []


def test_graph_names_every_missing_variable():
    names = {problem.split()[0] for problem in check_host_config("graph", {})}
    assert names == {"VGAR_REPOSITORY_ROOT", "VGAR_GRAPH_DATABASE", "VGAR_MCP_AUDIT_LOG"}


def test_dotenv_relative_values_are_rejected(tmp_path):
    env = full(tmp_path, VGAR_GRAPH_DATABASE="artifacts/sample_graph.db", VGAR_MCP_AUDIT_LOG="logs/mcp_audit.jsonl")
    problems = check_host_config("graph", env)
    assert "VGAR_GRAPH_DATABASE=artifacts/sample_graph.db is not an absolute path" in problems
    assert "VGAR_MCP_AUDIT_LOG=logs/mcp_audit.jsonl is not an absolute path" in problems


def test_root_must_be_an_existing_directory(tmp_path):
    missing = tmp_path / "missing"
    problems = check_host_config("graph", full(tmp_path, VGAR_REPOSITORY_ROOT=str(missing)))
    assert problems == [f"VGAR_REPOSITORY_ROOT={missing} is not an existing directory"]


def test_forward_slash_windows_paths_are_absolute(tmp_path):
    env = {key: value.replace("\\", "/") for key, value in full(tmp_path).items()}
    assert check_host_config("graph", env) == []


def test_spaces_around_a_value_are_rejected_because_the_servers_use_it_unstripped(tmp_path):
    log = f" {tmp_path / 'a.jsonl'}"
    assert check_host_config("repository", full(tmp_path, VGAR_MCP_AUDIT_LOG=log)) == [
        f"VGAR_MCP_AUDIT_LOG={log!r} has spaces around it"]


def test_execution_from_a_template_with_only_the_lease_root_starts(tmp_path):
    env = full(tmp_path)
    for name in ("VGAR_REPOSITORY_ROOT", "VGAR_GRAPH_DATABASE"):
        env.pop(name)
    assert check_host_config("execution", env) == []


def test_execution_needs_at_least_one_root(tmp_path):
    env = {"VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl")}
    assert check_host_config("execution", env) == ["VGAR_REPOSITORY_ROOT is not set (or set VGAR_LEASE_ROOT)"]


@pytest.mark.skipif(os.name != "nt", reason="drive-relative paths exist only on Windows")
def test_drive_relative_path_is_not_absolute(tmp_path):
    problems = check_host_config("graph", full(tmp_path, VGAR_GRAPH_DATABASE="D:graph.db"))
    assert problems == ["VGAR_GRAPH_DATABASE=D:graph.db is not an absolute path"]


def test_snapshot_backend_needs_no_repository_or_database(tmp_path):
    env = {"VGAR_GRAPH_BACKEND": "snapshot", "VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl")}
    assert check_host_config("graph", env) == []


def test_execution_lease_root_is_optional_but_checked_when_set(tmp_path):
    env = full(tmp_path)
    env.pop("VGAR_LEASE_ROOT")
    assert check_host_config("execution", env) == []
    assert check_host_config("execution", {**env, "VGAR_LEASE_ROOT": "repo"}) == [
        "VGAR_LEASE_ROOT=repo is not an absolute path"]


def test_repository_requires_lease_root(tmp_path):
    env = full(tmp_path)
    env.pop("VGAR_LEASE_ROOT")
    assert [problem.split()[0] for problem in check_host_config("repository", env)] == ["VGAR_LEASE_ROOT"]


def _start(module: str, cwd: Path, **env: str) -> subprocess.CompletedProcess[str]:
    base = {"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    return subprocess.run([sys.executable, "-B", "-m", f"vgar.mcp.servers.{module}"], cwd=cwd, env={**base, **env},
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=120)


def test_server_process_without_configuration_exits_naming_the_variable(tmp_path):
    result = _start("repository_server", tmp_path)
    assert result.returncode == 2
    assert "VGAR_LEASE_ROOT is not set" in result.stderr
    assert "VGAR_MCP_AUDIT_LOG is not set" in result.stderr
    assert result.stdout == ""


def test_graph_server_with_relative_database_exits_before_opening_it(tmp_path):
    result = _start("graph_server", tmp_path, **full(tmp_path, VGAR_GRAPH_DATABASE="artifacts/sample_graph.db"))
    assert result.returncode == 2
    assert "VGAR_GRAPH_DATABASE=artifacts/sample_graph.db is not an absolute path" in result.stderr
    assert "Graph database not found" not in result.stderr
    assert not (tmp_path / "artifacts").exists()
    assert result.stdout == ""
