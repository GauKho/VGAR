"""M3-W11-1 security S4/S5 through the real MCP tool path (execution_server -> pytest_runner -> run_bounded).

Design: docs/superpowers/specs/2026-11-01-m3-w11-security-design.md
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

import pytest

from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import execution_server


def _alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except ImportError:
        pass
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def lease(tmp_path, monkeypatch):
    root = tmp_path / "lease"
    (root / "tests").mkdir(parents=True)
    monkeypatch.setenv("VGAR_LEASE_ROOT", str(root))
    monkeypatch.setenv("VGAR_ALLOWED_SELECTORS", json.dumps(["tests"]))
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    return root


def test_timeout_kills_grandchild(lease, monkeypatch):
    # S4: the whole process tree dies on timeout, not only the pytest parent.
    pid_file = lease / "grandchild.pid"
    (lease / "tests" / "test_hang.py").write_text(
        "import subprocess, sys, time\n"
        "def test_hang():\n"
        f"    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"    open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "    time.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(execution_server, "PYTEST_TIMEOUT_SECONDS", 4)

    response = execution_server.run_pytest("tests/test_hang.py")

    assert response["status"] == "ERROR" and response["error"]["code"] == "TIMEOUT"
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _alive(pid)


def test_output_is_capped_while_running(lease, monkeypatch):
    # S5: the cap stops a flooding test early instead of truncating after it finishes.
    (lease / "tests" / "test_flood.py").write_text(
        "import sys, time\n"
        "def test_flood(capsys):\n"
        "    with capsys.disabled():  # bypass pytest's own capture so the bytes reach the process stdout\n"
        "        for _ in range(50_000):\n"
        "            sys.stdout.write('x' * 1024 + '\\n')\n"
        "            sys.stdout.flush()\n"
        "    time.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(execution_server, "PYTEST_OUTPUT_CAP", 100_000)
    started = time.monotonic()

    response = execution_server.run_pytest("tests/test_flood.py::test_flood")

    assert time.monotonic() - started < 20
    data = response["data"]
    assert data["truncated"] is True
    assert len(data["stdout"]) <= 100_000


# ------------------------------------------------------- Task 8: repair_server run root (S1, S2)
REPO = Path(__file__).resolve().parents[1]
TASK = REPO / "examples/m2/tasks/single_file_login.json"
REF = (REPO / "tests/fixtures/m2/reference_patches/single_file_login.diff").read_text(encoding="utf-8")


def _open_run(root: Path) -> str:
    from vgar.mcp.servers import repair_server
    result = repair_server.get_task_context(str(TASK), "fake", str(root / "runs"), str(root / "work"))
    assert result["status"] == "PASS", result
    return result["run_dir"]


def test_repair_rejects_run_dir_outside_run_root(tmp_path, monkeypatch):
    from vgar.mcp.servers import repair_server
    run_a = tmp_path / "a"
    run_a.mkdir()
    monkeypatch.setenv("VGAR_RUN_ROOT", str(run_a))
    run_dir = _open_run(run_a)
    before = (Path(run_dir) / "session.json").read_bytes()
    (tmp_path / "b").mkdir()
    monkeypatch.setenv("VGAR_RUN_ROOT", str(tmp_path / "b"))

    result = repair_server.apply_patch(run_dir, REF)

    assert result["status"] == "ERROR" and result["reason"] == "PATH_OUTSIDE_ROOT"
    assert (Path(run_dir) / "session.json").read_bytes() == before


def test_repair_without_run_root_is_root_not_leased(tmp_path, monkeypatch):
    from vgar.mcp.servers import repair_server
    monkeypatch.delenv("VGAR_RUN_ROOT", raising=False)
    result = repair_server.get_task_context(str(TASK), "fake", str(tmp_path / "runs"), str(tmp_path / "work"))
    assert result["status"] == "ERROR" and result["reason"] == "ROOT_NOT_LEASED"
    assert repair_server.verify_patch(str(tmp_path / "runs" / "x"))["reason"] == "ROOT_NOT_LEASED"


def test_runtime_repair_tools_lease_output_root(tmp_path, monkeypatch):
    import asyncio
    import vgar.mcp.client as client_module
    from vgar.agents.runtime import Runtime
    seen = {}

    class FakeClient:
        async def get_tools(self):
            return []

    def fake_client(settings=None, servers=None, extra_env=None):
        seen.update(servers=servers, extra_env=extra_env)
        return FakeClient()

    monkeypatch.setattr(client_module, "create_mcp_client", fake_client)
    runtime = Runtime(output_root=tmp_path / "runs")
    asyncio.run(runtime.repair_tools())
    assert seen["servers"] == ("repair",)
    assert seen["extra_env"]["VGAR_RUN_ROOT"] == str(tmp_path / "runs")


# ------------------------------------------------------------- Task 9: PUBLIC_TOOLS (S9)
def test_unknown_tool_is_refused():
    from types import SimpleNamespace
    from vgar.mcp.registry import validate_public_tools
    with pytest.raises(RuntimeError, match="repository_apply_patch"):
        validate_public_tools([SimpleNamespace(name="repository_read_file"), SimpleNamespace(name="repository_apply_patch")])


def test_all_current_tools_are_public():
    import asyncio
    from vgar.mcp.registry import PUBLIC_TOOLS
    from vgar.mcp.servers import graph_server, repair_server, repository_server
    servers = {"graph": graph_server, "repository": repository_server, "execution": execution_server,
               "repair": repair_server}
    names = {f"{prefix}_{tool.name}" for prefix, module in servers.items()
             for tool in asyncio.run(module.mcp.list_tools())}
    assert names <= PUBLIC_TOOLS
