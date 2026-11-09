"""Real SDK2 abrupt-close and process-tree timeout checks; no target/model code."""
import ctypes
import json
import os
import sys
from pathlib import Path

import anyio
import pytest

from vgar.repair.executor import run_bounded


def test_stdio_abnormal_server_exit_is_not_success(tmp_path):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    from mcp.shared.exceptions import MCPError
    script = tmp_path / "crash.py"
    script.write_text("raise SystemExit(7)\n", encoding="utf-8")

    async def run():
        with anyio.fail_after(10), pytest.raises(ExceptionGroup) as caught:
            async with Client(StdioServerParameters(command=sys.executable, args=["-B", str(script)]), mode="legacy"):
                pytest.fail("A crashed server cannot establish a session")
        errors = list(caught.value.exceptions)
        while any(isinstance(e, BaseExceptionGroup) for e in errors):
            errors = [leaf for error in errors for leaf in (error.exceptions if isinstance(error, BaseExceptionGroup) else [error])]
        assert errors and all(isinstance(e, MCPError) and "Connection closed" in str(e) for e in errors)

    anyio.run(run)


def alive(pid):
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file() and stat.read_text().split()[2] == "Z":
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_bounded_worker_timeout_reaps_descendant_tree(tmp_path):
    marker = tmp_path / "pids.json"
    code = """
import json,os,pathlib,subprocess,sys,threading
child=subprocess.Popen([sys.executable,'-B','-c','import threading; threading.Event().wait(60)'])
pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))
threading.Event().wait(60)
"""
    result = run_bounded((sys.executable, "-B", "-c", code, str(marker)), tmp_path, 3)
    assert result["timed_out"] and not result["complete"]
    assert result["status"] == "ERROR"
    assert marker.is_file(), "Worker did not reach the deterministic PID receipt before timeout"
    assert not any(alive(pid) for pid in json.loads(marker.read_text()))
