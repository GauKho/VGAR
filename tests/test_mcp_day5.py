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


def test_repair_unexpected_exception_is_internal_error_envelope(tmp_path, monkeypatch):
    # S8 + C4: an unexpected failure is audited with its real message and returned as INTERNAL_ERROR, message hidden.
    from vgar.mcp.servers import repair_server
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(repair_server, "_audit_logger", AuditLogger(audit), raising=False)

    def boom(*_args):
        raise RuntimeError("boom-secret-detail")

    monkeypatch.setattr(repair_server, "_load", boom)
    response = repair_server.verify_patch("r")
    ToolResponse.model_validate(response)
    assert response["status"] == "ERROR" and response["error"]["code"] == "INTERNAL_ERROR"
    assert "boom-secret-detail" not in json.dumps(response)
    [entry] = _lines(audit)
    assert (entry["payload"]["status"], entry["payload"]["error_code"]) == ("ERROR", "INTERNAL_ERROR")
    assert entry["payload"]["request_id"] == response["metadata"]["request_id"]


# ------------------------------------------------- C4: repair_server on the shared envelope (M3-W11-3)
REPO = Path(__file__).resolve().parents[1]
TASK = REPO / "examples/m2/tasks/single_file_login.json"
REF = (REPO / "tests/fixtures/m2/reference_patches/single_file_login.diff").read_text(encoding="utf-8")


@pytest.fixture
def repair(tmp_path, monkeypatch):
    from vgar.mcp.servers import repair_server
    monkeypatch.setattr(repair_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"), raising=False)
    monkeypatch.setenv("VGAR_RUN_ROOT", str(tmp_path))
    return repair_server


def _open(repair, tmp_path):
    return repair.get_task_context(str(TASK), "fake", str(tmp_path / "runs"), str(tmp_path / "work"))


def test_repair_tools_return_envelope_with_engine_verdict_in_data(repair, tmp_path):
    opened = _open(repair, tmp_path)
    run_dir = opened["data"]["run_dir"]
    responses = [opened, repair.apply_patch(run_dir, REF), repair.run_relevant_tests(run_dir),
                 repair.verify_patch(run_dir)]
    for response in responses:
        ToolResponse.model_validate(response)
        assert response["status"] == "PASS" and response["error"] is None
        assert response["data"]["verdict"] == "PASS" and "status" not in response["data"]
    assert responses[-1]["data"]["recommendation"] == "ACCEPT"
    audit_ids = [e["payload"]["request_id"] for e in _lines(tmp_path / "audit.jsonl") if e["event_type"] == "tool_call"]
    assert audit_ids == [r["metadata"]["request_id"] for r in responses]


def test_repair_engine_rejection_is_a_verdict_not_a_tool_error(repair, tmp_path):
    run_dir = _open(repair, tmp_path)["data"]["run_dir"]
    response = repair.verify_patch(run_dir)  # nothing applied: the engine answers, the tool did not fail
    assert response["status"] == "PASS"
    assert (response["data"]["verdict"], response["data"]["reason"]) == ("ERROR", "VERIFICATION_INCOMPLETE")
    assert response["data"]["recommendation"] == "REJECT"


def test_repair_tool_errors_use_c4_codes(repair, tmp_path, monkeypatch):
    from vgar.mcp.schemas import KNOWN_ERROR_CODES
    run_dir = _open(repair, tmp_path)["data"]["run_dir"]
    repair.apply_patch(run_dir, REF)
    (tmp_path / "not-a-run").mkdir()
    errors = {"twice": repair.apply_patch(run_dir, REF),
              "missing": repair.verify_patch(str(tmp_path / "not-a-run"))}
    monkeypatch.delenv("VGAR_RUN_ROOT")
    errors["unleased"] = repair.run_relevant_tests(run_dir)
    for response in errors.values():
        ToolResponse.model_validate(response)
        assert response["status"] == "ERROR" and response["data"] is None
        assert response["error"]["code"] in KNOWN_ERROR_CODES and response["error"]["retryable"] is False
    assert {name: r["error"]["code"] for name, r in errors.items()} == {
        "twice": "TOOL_ORDER_VIOLATION", "missing": "RUN_NOT_FOUND", "unleased": "ROOT_NOT_LEASED"}


def test_client_unwraps_repair_envelope_for_agent_hosts():
    from vgar.agents.nodes.mcp_repair import _unwrap
    verdict = {"status": "PASS", "data": {"verdict": "FAIL", "reason": "TEST_FAILED", "recommendation": "REJECT"},
               "error": None, "metadata": {"duration_ms": 1, "request_id": "r"}}
    assert _unwrap(verdict) == {"status": "FAIL", "reason": "TEST_FAILED", "recommendation": "REJECT"}
    error = {"status": "ERROR", "data": None, "metadata": {"duration_ms": 1, "request_id": "r"},
             "error": {"code": "TOOL_ORDER_VIOLATION", "message": "needs phase prepared", "details": {},
                       "retryable": False}}
    assert _unwrap(error) == {"status": "ERROR", "reason": "TOOL_ORDER_VIOLATION", "detail": "needs phase prepared"}


def test_client_transport_failure_is_mcp_transport_error():
    import asyncio
    from vgar.agents.nodes.mcp_repair import _call

    class Down:
        async def repair_tools(self):
            raise RuntimeError("server died")

    result = asyncio.run(_call(Down(), "repair_verify_patch", {"run_dir": "x"}))
    assert result["status"] == "ERROR" and result["reason"] == "MCP_TRANSPORT_ERROR"


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
