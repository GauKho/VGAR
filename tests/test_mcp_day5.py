"""M3-W11 day 5: every call audited including errors (S8), repository text marked untrusted (S12), graph server
has no write tool (S13), every guarded tool returns the C4 envelope with a known code (S10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import ToolResponse


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_repair_errors_are_audited(tmp_path, monkeypatch):
    # S8: repair_server writes one audit line per call, failures included.
    from vgar.mcp.servers import repair_server
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(repair_server, "_audit_logger", AuditLogger(audit), raising=False)
    monkeypatch.setenv("VGAR_RUN_ROOT", str(tmp_path))
    repair_server.verify_patch(str(tmp_path / "missing-run"))
    monkeypatch.delenv("VGAR_RUN_ROOT")
    repair_server.apply_patch(str(tmp_path / "missing-run"), "diff")
    entries = [e for e in _lines(audit) if e["event_type"] == "tool_call"]
    assert [(e["payload"]["tool"], e["payload"]["status"]) for e in entries] == [
        ("verify_patch", "ERROR"), ("apply_patch", "ERROR")]
    assert entries[1]["payload"]["error_code"] == "ROOT_NOT_LEASED"


def test_graph_tools_mark_repository_text_untrusted(monkeypatch, tmp_path):
    # S12
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    from vgar.mcp.servers import graph_server
    monkeypatch.setattr(graph_server, "graph_service", SQLiteGraphService(SQLiteGraphStore(
        Path(__file__).parents[1] / "artifacts" / "sample_graph.db")))
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    assert graph_server.search_symbols("login", limit=5)["metadata"]["untrusted"] is True


def test_graph_server_has_no_write_tool():
    # S13
    import asyncio
    from vgar.mcp.servers import graph_server
    names = {tool.name for tool in asyncio.run(graph_server.mcp.list_tools())}
    assert names == {"search_symbols", "get_callers", "get_callees", "find_task_anchors", "get_related_context",
                     "get_related_tests", "analyze_patch_impact"}
    assert not any(word in name for name in names for word in ("write", "apply", "patch_file", "delete", "save"))


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


def test_repair_unexpected_exception_is_audited_and_reraised(tmp_path, monkeypatch):
    # S8: a failure outside the _tool_error path is still audited, then propagates unchanged.
    from vgar.mcp.servers import repair_server
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(repair_server, "_audit_logger", AuditLogger(audit), raising=False)

    def boom(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(repair_server, "_load", boom)
    monkeypatch.setattr(repair_server, "_tool_error", lambda error: (_ for _ in ()).throw(error))
    with pytest.raises(RuntimeError):
        repair_server.verify_patch("r")
    [entry] = _lines(audit)
    assert (entry["payload"]["status"], entry["payload"]["error_code"]) == ("ERROR", "INTERNAL_ERROR")


def test_repair_audit_hashes_inputs_not_raw_text(tmp_path, monkeypatch):
    # S8 + S6: the audit line carries an input hash, never the diff itself.
    from vgar.mcp.servers import repair_server
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(repair_server, "_audit_logger", AuditLogger(audit), raising=False)
    monkeypatch.delenv("VGAR_RUN_ROOT", raising=False)
    repair_server.apply_patch("r", "diff --git a/x b/x\n+SENTINEL_TEXT")
    [entry] = _lines(audit)
    assert "SENTINEL_TEXT" not in audit.read_text(encoding="utf-8")
    assert len(entry["payload"]["input_sha256"]) == 64 and entry["payload"]["server"] == "repair"
