"""Contract tests for the graph MCP tool envelope, error codes and audit trail.

Runs the tool functions directly (no stdio) against the committed SQLite
sample graph so results are deterministic. Transport behaviour is covered by
scripts/smoke_w3_w4.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import ToolResponse
from vgar.mcp.servers import graph_server

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "mcp"
ENVELOPE_KEYS = {"status", "data", "error", "metadata"}


@pytest.fixture
def audit_path(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(path))
    monkeypatch.setattr(
        graph_server,
        "graph_service",
        SQLiteGraphService(SQLiteGraphStore(ROOT / "artifacts" / "sample_graph.db")),
    )
    return path


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _login_id() -> str:
    return graph_server.search_symbols("login", limit=10)["data"]["symbols"][0]["symbol_id"]


def test_fixtures_are_valid_envelopes():
    ok = ToolResponse.model_validate_json((FIXTURES / "tool_success.json").read_text())
    err = ToolResponse.model_validate_json((FIXTURES / "tool_error.json").read_text())
    assert ok.status == "PASS" and ok.error is None and ok.data
    assert err.status == "ERROR" and err.data is None and err.error.code == "NODE_NOT_FOUND"


def test_success_matches_fixture_shape(audit_path):
    fixture = json.loads((FIXTURES / "tool_success.json").read_text())
    live = graph_server.search_symbols("login", limit=10)

    assert set(live) == ENVELOPE_KEYS == set(fixture)
    assert set(live["data"]) == set(fixture["data"])
    assert set(live["data"]["symbols"][0]) == set(fixture["data"]["symbols"][0])
    assert set(live["metadata"]) == set(fixture["metadata"])
    assert live["status"] == "PASS" and live["error"] is None
    assert isinstance(live["metadata"]["duration_ms"], int)
    assert live["metadata"]["backend"] == "sqlite"


def test_error_matches_fixture_shape(audit_path):
    fixture = json.loads((FIXTURES / "tool_error.json").read_text())
    live = graph_server.get_callers("missing:symbol")

    assert set(live) == ENVELOPE_KEYS
    assert live["status"] == "ERROR" and live["data"] is None
    assert live["error"] == fixture["error"]
    assert set(live["metadata"]) == set(fixture["metadata"])


@pytest.mark.parametrize("tool,key", [("get_callers", "callers"), ("get_callees", "callees")])
def test_relation_tools_pass_with_data(audit_path, tool, key):
    symbol_id = _login_id()
    response = getattr(graph_server, tool)(symbol_id, depth=1)
    assert response["status"] == "PASS"
    assert response["data"]["symbol_id"] == symbol_id
    assert isinstance(response["data"][key], list)


@pytest.mark.parametrize("tool", ["get_callers", "get_callees"])
def test_unknown_symbol_is_node_not_found(audit_path, tool):
    response = getattr(graph_server, tool)("missing:symbol")
    assert response["error"]["code"] == "NODE_NOT_FOUND"
    assert response["error"]["details"]["node_id"] == "missing:symbol"


def test_empty_query_and_bad_limit_have_distinct_codes(audit_path):
    assert graph_server.search_symbols("")["error"]["code"] == "INVALID_QUERY"
    assert graph_server.search_symbols("login", limit=0)["error"]["code"] == "INVALID_LIMIT"
    assert graph_server.search_symbols("login", limit=101)["error"]["code"] == "INVALID_LIMIT"


def test_unexpected_exception_is_internal_error_without_leak(audit_path, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret path /home/x/db")

    monkeypatch.setattr(graph_server.graph_service, "search_symbols", boom)
    response = graph_server.search_symbols("login")

    assert response["status"] == "ERROR"
    assert response["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in json.dumps(response)
    assert "secret path" in _events(audit_path)[-1]["payload"]["error_message"]  # kept for operators


def test_every_call_is_audited_including_errors(audit_path):
    ok = graph_server.search_symbols("login", limit=10)
    bad = graph_server.get_callers("missing:symbol")

    first, second = [e["payload"] for e in _events(audit_path)]
    assert first["request_id"] == ok["metadata"]["request_id"]
    assert first["status"] == "PASS" and first["result_count"] >= 1
    assert isinstance(first["duration_ms"], int)

    assert second["request_id"] == bad["metadata"]["request_id"]
    assert second["status"] == "ERROR" and second["error_code"] == "NODE_NOT_FOUND"
    assert second["tool"] == "get_callers" and second["symbol_id"] == "missing:symbol"


def test_request_ids_are_unique(audit_path):
    ids = {graph_server.search_symbols("login")["metadata"]["request_id"] for _ in range(5)}
    assert len(ids) == 5


def test_resource_read_is_audited_and_errors_are_logged(audit_path):
    graph_server.repo_summary()
    with pytest.raises(KeyError):  # resources keep protocol-level errors
        graph_server.graph_node("missing:node")

    ok, bad = [e["payload"] for e in _events(audit_path)]
    assert ok["status"] == "PASS" and ok["resource"] == "vgar://repo/summary"
    assert bad["status"] == "ERROR" and bad["error_code"] == "NODE_NOT_FOUND"
    assert {"request_id", "duration_ms"} <= set(bad)


def test_demo_backend_uses_the_same_error_code(monkeypatch, tmp_path):
    from vgar.graph.demo_service import DemoGraphService

    monkeypatch.setattr(graph_server, "graph_service", DemoGraphService())
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "a.jsonl"))
    response = graph_server.get_callers("missing:symbol")
    assert response["error"]["code"] == "NODE_NOT_FOUND"


def test_coded_tool_error_keeps_its_code():
    # Legacy-server plan Task 1: C4 codes raised by servers survive the envelope mapping.
    from vgar.mcp.schemas import ROOT_NOT_LEASED, CodedToolError, error_from_exception
    error = error_from_exception(CodedToolError(ROOT_NOT_LEASED, "no lease"))
    assert (error.code, error.message) == ("ROOT_NOT_LEASED", "no lease")


def test_run_tool_marks_untrusted_text(tmp_path):
    from vgar.mcp.tooling import run_tool
    response = run_tool(server="t", tool="x", backend="b", audit=AuditLogger(tmp_path / "audit.jsonl"),
                        call=lambda: {"v": 1}, untrusted=True)
    plain = run_tool(server="t", tool="x", backend="b", audit=AuditLogger(tmp_path / "audit.jsonl"),
                     call=lambda: {"v": 1})
    assert response["metadata"]["untrusted"] is True
    assert "untrusted" not in plain["metadata"]


def test_leased_root_and_inside(tmp_path, monkeypatch):
    # S1 / S2 shared guards (security design §4.2)
    from vgar.mcp.schemas import CodedToolError
    from vgar.mcp.tooling import inside, leased_root
    monkeypatch.delenv("VGAR_TEST_ROOT", raising=False)
    with pytest.raises(CodedToolError) as missing:
        leased_root("VGAR_TEST_ROOT")
    assert missing.value.code == "ROOT_NOT_LEASED"
    monkeypatch.setenv("VGAR_TEST_ROOT", str(tmp_path))
    root = leased_root("VGAR_TEST_ROOT")
    with pytest.raises(CodedToolError) as escaped:
        inside(root, root / ".." / "x")
    assert escaped.value.code == "PATH_OUTSIDE_ROOT"
    assert inside(root, root / "a.py") == (tmp_path / "a.py").resolve()


def test_retryable_follows_the_code_table():
    # S10: retryable is derived from the code table, never trusted from the caller.
    from vgar.mcp.schemas import KNOWN_ERROR_CODES, ToolError
    assert ToolError(code="GRAPH_NOT_READY", message="x").retryable is True
    assert ToolError(code="TIMEOUT", message="x", retryable=True).retryable is False
    assert "TOOL_ERROR" not in KNOWN_ERROR_CODES
    assert [c for c, r in KNOWN_ERROR_CODES.items() if r] == ["GRAPH_NOT_READY"]


def test_unknown_coded_error_becomes_internal_error():
    from vgar.mcp.schemas import CodedToolError, error_from_exception
    error = error_from_exception(CodedToolError("MADE_UP", "secret detail"))
    assert (error.code, error.retryable) == ("INTERNAL_ERROR", False)
    assert "secret detail" not in error.message
