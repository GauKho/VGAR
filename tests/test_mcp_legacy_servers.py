"""M3-W11-2 legacy servers (D7): host-leased root, allow-listed selectors, no write tool.

Design: docs/superpowers/specs/2026-11-01-m3-w11-legacy-servers-design.md
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import TIMEOUT, CodedToolError
from vgar.mcp.servers import execution_server, repository_server


@pytest.fixture
def lease(tmp_path, monkeypatch):
    root = tmp_path / "lease"
    (root / "tests").mkdir(parents=True)
    (root / "auth.py").write_text("def login(name):\n    return bool(name)\n", encoding="utf-8")
    (root / "tests" / "test_auth.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setenv("VGAR_LEASE_ROOT", str(root))
    for module in (repository_server, execution_server):
        monkeypatch.setattr(module, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"), raising=False)
    return root


def _code(response: dict) -> str | None:
    return (response.get("error") or {}).get("code")


# ------------------------------------------------------------------ repository_server.read_file
def test_read_file_without_lease_is_root_not_leased(lease, monkeypatch):
    monkeypatch.delenv("VGAR_LEASE_ROOT")
    response = repository_server.read_file("auth.py")
    assert response["status"] == "ERROR" and _code(response) == "ROOT_NOT_LEASED"


def test_read_file_reads_inside_the_lease(lease):
    response = repository_server.read_file("auth.py")
    assert response["status"] == "PASS"
    assert response["data"]["content"].startswith("def login") and response["data"]["truncated"] is False


def test_read_file_rejects_parent_escape(lease):
    assert _code(repository_server.read_file("../outside.txt")) == "PATH_OUTSIDE_ROOT"


def test_read_file_rejects_symlink_escape(lease):
    # Review Focus 1
    try:
        os.symlink(lease.parent / "outside.txt", lease / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert _code(repository_server.read_file("link.txt")) == "PATH_OUTSIDE_ROOT"


def test_read_file_truncates_at_server_cap(lease):
    # S16
    (lease / "big.py").write_text("x" * (repository_server.READ_FILE_MAX_BYTES + 6 * 1024), encoding="utf-8")
    data = repository_server.read_file("big.py")["data"]
    assert data["truncated"] is True
    assert len(data["content"].encode("utf-8")) == repository_server.READ_FILE_MAX_BYTES


def test_read_file_marks_content_untrusted(lease):
    # S12
    assert repository_server.read_file("auth.py")["metadata"]["untrusted"] is True


def test_read_file_binary_is_invalid_argument(lease):
    # Review Focus 3
    (lease / "blob.bin").write_bytes(b"\xff\xfe\x00\x81")
    assert _code(repository_server.read_file("blob.bin")) == "INVALID_ARGUMENT"


def test_repository_server_has_no_write_tool():
    # S14 (part)
    names = {tool.name for tool in asyncio.run(repository_server.mcp.list_tools())}
    assert names == {"health", "read_file"}


# --------------------------------------------------------------- execution_server.run_pytest
@pytest.fixture
def counted_runner(monkeypatch):
    from vgar.mcp import pytest_runner
    calls = []

    def fake(root, selector, *, timeout_seconds, output_cap):
        calls.append({"root": root, "selector": selector, "timeout_seconds": timeout_seconds})
        return {"exit_code": 0, "stdout": "1 passed", "stderr": "", "truncated": False}

    monkeypatch.setattr(pytest_runner, "run_selector", fake)
    return calls


def _allow(monkeypatch, *selectors: str) -> None:
    monkeypatch.setenv("VGAR_ALLOWED_SELECTORS", json.dumps(list(selectors)))


def test_run_pytest_rejects_selector_outside_allow_list(lease, monkeypatch, counted_runner):
    # S3
    _allow(monkeypatch, "tests/test_auth.py::test_ok")
    assert _code(execution_server.run_pytest("tests/test_other.py")) == "SELECTOR_REJECTED"
    assert counted_runner == []


def test_run_pytest_rejects_selector_tricks(lease, monkeypatch, counted_runner):
    # Review Focus 2
    _allow(monkeypatch, "tests")
    for selector in ("-k x", "tests/test_auth.py::test_ok --pdb", "tests/../x.py", "tests/a.py\n-x", ""):
        assert _code(execution_server.run_pytest(selector)) == "SELECTOR_REJECTED", selector
    assert counted_runner == []


def test_run_pytest_accepts_scope_prefix(lease, monkeypatch, counted_runner):
    _allow(monkeypatch, "tests")
    response = execution_server.run_pytest("tests/test_auth.py::test_ok")
    assert response["status"] == "PASS" and response["data"]["verdict"] == "PASS"
    assert len(counted_runner) == 1
    assert counted_runner[0]["timeout_seconds"] == execution_server.PYTEST_TIMEOUT_SECONDS
    assert Path(counted_runner[0]["root"]).resolve() == lease.resolve()


def test_run_pytest_without_lease_is_root_not_leased(lease, monkeypatch, counted_runner):
    monkeypatch.delenv("VGAR_LEASE_ROOT")
    _allow(monkeypatch, "tests")
    assert _code(execution_server.run_pytest("tests/test_auth.py")) == "ROOT_NOT_LEASED"
    assert counted_runner == []


def test_run_pytest_timeout_is_coded(lease, monkeypatch):
    from vgar.mcp import pytest_runner

    def slow(root, selector, *, timeout_seconds, output_cap):
        raise CodedToolError(TIMEOUT, f"pytest exceeded {timeout_seconds}s")

    monkeypatch.setattr(pytest_runner, "run_selector", slow)
    _allow(monkeypatch, "tests")
    assert _code(execution_server.run_pytest("tests/test_auth.py")) == "TIMEOUT"


def test_run_pytest_runs_real_pytest_in_lease(lease, monkeypatch):
    _allow(monkeypatch, "tests/test_auth.py::test_ok")
    data = execution_server.run_pytest("tests/test_auth.py::test_ok")["data"]
    assert data["verdict"] == "PASS" and data["exit_code"] == 0


def test_execution_server_tools():
    # S14 (part)
    tools = {tool.name: tool for tool in asyncio.run(execution_server.mcp.list_tools())}
    assert set(tools) == {"health", "run_pytest", "run_relevant_tests"}
    assert set(_schema(tools["run_pytest"])["properties"]) == {"selector"}
    assert set(_schema(tools["run_relevant_tests"])["properties"]) == {"diff"}


def _schema(tool) -> dict:
    """Tool input schema on MCP SDK 2 (``input_schema``) and SDK 1 (``inputSchema``)."""
    return getattr(tool, "input_schema", None) or tool.inputSchema


# ------------------------------------------------------------------- Task 4: tool surface + plumbing
def test_no_tool_accepts_root_or_timeout_or_writes():
    # S9 / S14; repair_server (the only writer) was removed: the attached coding agent edits code itself.
    for module in (repository_server, execution_server):
        for tool in asyncio.run(module.mcp.list_tools()):
            fields = set(_schema(tool).get("properties", {}))
            assert not fields & {"repo_path", "timeout_seconds"}, (module.__name__, tool.name)
            assert "patch" not in tool.name and "write" not in tool.name, tool.name
