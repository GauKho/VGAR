"""Logging per the build-server guide (2026-07-28): stdout carries only JSON-RPC, logs go to stderr through
``logging.getLogger(__name__)``, the level comes from ``VGAR_MCP_LOG_LEVEL`` (default WARNING, trace spec P8).

The server is driven with raw JSON-RPC over pipes so the test works on MCP SDK 1.x and 2.x alike.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from graph_fixture import real_graph_env

ROOT = Path(__file__).resolve().parents[2]


def _serve(tmp_path: Path, calls: list[tuple[str, dict]], **env: str) -> tuple[list[dict], str, int]:
    """Start graph_server over stdio, run ``calls`` after the handshake, return (responses, stderr, exit code)."""
    stderr_path = tmp_path / "stderr.log"
    full_env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1",
                "VGAR_MCP_AUDIT_LOG": str(tmp_path / "audit.jsonl"), **real_graph_env(), **env}
    if not env.get("VGAR_MCP_LOG_LEVEL"):
        full_env.pop("VGAR_MCP_LOG_LEVEL", None)
    with stderr_path.open("w", encoding="utf-8") as err:
        process = subprocess.Popen([sys.executable, "-B", "-m", "vgar.mcp.servers.graph_server"], cwd=tmp_path,
                                   env=full_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                   text=True, encoding="utf-8")
        responses = []

        def send(message: dict) -> None:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def receive(identifier: int) -> dict:
            while True:
                line = process.stdout.readline()
                if not line:
                    raise EOFError("server closed stdout")
                message = json.loads(line)  # stdout must be JSON-RPC only
                if message.get("id") == identifier:
                    return message

        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "log-test", "version": "1"}}})
            responses.append(receive(1))
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            for number, (tool, arguments) in enumerate(calls, start=2):
                send({"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
                responses.append(receive(number))
        except EOFError:
            pass
        finally:
            process.stdin.close()
            code = process.wait(timeout=120)
    return responses, stderr_path.read_text(encoding="utf-8"), code


def _envelope(response: dict) -> dict:
    return json.loads(response["result"]["content"][0]["text"])


def test_info_level_logs_each_tool_call_on_stderr_only(tmp_path):
    responses, stderr, _ = _serve(tmp_path, [("search_symbols", {"query": "login"})], VGAR_MCP_LOG_LEVEL="INFO")
    assert _envelope(responses[-1])["status"] == "PASS"
    assert "tool=search_symbols" in stderr and "status=PASS" in stderr
    assert "vgar-graph" in stderr and "backend=sqlite" in stderr


def test_default_level_has_no_per_call_info_lines(tmp_path):
    responses, stderr, _ = _serve(tmp_path, [("search_symbols", {"query": "login"})])
    assert _envelope(responses[-1])["status"] == "PASS"
    assert "tool=search_symbols" not in stderr


def test_debug_level_never_logs_diff_content(tmp_path):
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a = 1\n+SECRET_MARKER = 2\n"
    _, stderr, _ = _serve(tmp_path, [("verify_patch_graph_constraints", {"diff": diff})], VGAR_MCP_LOG_LEVEL="DEBUG")
    start = [line for line in stderr.splitlines() if "tool=verify_patch_graph_constraints" in line and "args=" in line]
    assert start and "sha256:" in start[0]
    assert "SECRET_MARKER" not in stderr


def test_missing_database_is_logged_before_exit(tmp_path):
    # No repository configured: nothing can build the graph, so the server must stop and say why.
    _, stderr, code = _serve(tmp_path, [], VGAR_GRAPH_DATABASE=str(tmp_path / "missing.db"), VGAR_REPOSITORY_ROOT="")
    assert code != 0
    assert any("ERROR" in line and "vgar.mcp.servers.graph_server" in line and "Graph database not found" in line
               for line in stderr.splitlines())


def test_configure_server_logging_is_idempotent(monkeypatch):
    from vgar.mcp.logging_setup import configure_server_logging

    package = logging.getLogger("vgar")  # restore: other tests read vgar records through caplog
    monkeypatch.setattr(package, "handlers", list(package.handlers))
    monkeypatch.setattr(package, "propagate", package.propagate)
    monkeypatch.setattr(package, "level", package.level)
    monkeypatch.setenv("VGAR_MCP_LOG_LEVEL", "debug")
    assert configure_server_logging() == "DEBUG" == configure_server_logging()
    assert len([h for h in logging.getLogger("vgar").handlers if getattr(h, "_vgar", False)]) == 1
    monkeypatch.setenv("VGAR_MCP_LOG_LEVEL", "loud")
    assert configure_server_logging() == "WARNING"


def test_server_without_a_graph_starts_and_answers_graph_not_ready(tmp_path):
    # The repository is configured, the database does not exist yet: the agent will build it (proposal §10.3).
    responses, stderr, _ = _serve(tmp_path, [("search_symbols", {"query": "login"})], VGAR_MCP_LOG_LEVEL="INFO",
                                  VGAR_GRAPH_DATABASE=str(tmp_path / "graphs" / "new.db"))
    assert len(responses) == 2, stderr[-2000:]
    envelope = _envelope(responses[-1])
    assert envelope["status"] == "ERROR" and envelope["error"]["code"] == "GRAPH_NOT_READY"
    assert "graph_version=not built" in stderr
