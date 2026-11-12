"""M3-W11 day 5: every call audited including errors (S8), repository text marked untrusted (S12), graph server
has no unguarded write tool (S13/L6-2), every guarded tool returns the C4 envelope with a known code (S10)."""
from __future__ import annotations

import json
from pathlib import Path

from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import ToolResponse


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_graph_tools_mark_repository_text_untrusted(monkeypatch, tmp_path):
    # S12
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    from vgar.mcp.servers import graph_server
    monkeypatch.setattr(graph_server, "graph_service", SQLiteGraphService(SQLiteGraphStore(
        Path(__file__).parents[1] / "artifacts" / "sample_graph.db")))
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    assert graph_server.search_symbols("login", limit=5)["metadata"]["untrusted"] is True


def test_graph_server_has_no_write_tool(monkeypatch, tmp_path):
    # S13 updated by L6-2, then 12/11/2026 (proposal §10.5): the only write tool is build_or_update_graph; the host
    # asks the user before each call, and it builds nothing but the configured repository.
    import asyncio

    from vgar.mcp.servers import graph_server
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    names = {tool.name for tool in asyncio.run(graph_server.mcp.list_tools())}
    assert names == {"search_symbols", "get_callers", "get_callees", "find_task_anchors", "get_related_context",
                     "get_related_tests", "analyze_patch_impact", "build_or_update_graph", "explain_dependency_path",
                     "verify_patch_graph_constraints", "rank_patch_candidates"}
    assert not any(word in name for name in names for word in ("write", "apply", "patch_file", "delete", "save"))
    response = asyncio.run(graph_server.build_or_update_graph(str(tmp_path)))  # not VGAR_REPOSITORY_ROOT
    assert response["status"] == "ERROR" and response["error"]["code"] == "PATH_OUTSIDE_ROOT"


def test_tool_errors_carry_known_code_and_retryable(tmp_path, monkeypatch):
    # S10 (repository, execution, graph): envelope validates; error has a C4 code and retryable is a bool.
    from vgar.mcp.schemas import KNOWN_ERROR_CODES
    from vgar.mcp.servers import execution_server, graph_server, repository_server
    for module in (repository_server, execution_server, graph_server):
        monkeypatch.setattr(module, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("VGAR_LEASE_ROOT", raising=False)
    responses = [repository_server.read_file("a.py"), execution_server.run_pytest("tests"),
                 graph_server.get_callers("missing:symbol"), repository_server.health()]
    for response in responses:
        ToolResponse.model_validate(response)
        if response["status"] == "ERROR":
            assert response["error"]["code"] in KNOWN_ERROR_CODES
            assert isinstance(response["error"]["retryable"], bool)
    assert responses[-1]["status"] == "PASS"
