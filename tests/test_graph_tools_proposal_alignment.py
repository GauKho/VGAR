"""Graph tool outputs follow the proposal (spec 2026-11-20 §5.1-5.2): callers/callees carry edge confidence and
provenance (§6.4); get_related_context ranks against the task bound by find_task_anchors and the tool returns only
the packed context (§9.2), the full diagnostics going to the audit log."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server

REPO = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": ("from shop.pricing import round_vnd\n\n\n"
                         "def total(lines):\n    first = round_vnd(lines[0])\n    return first + round_vnd(sum(lines))\n"),
    "shop/report.py": "from shop.checkout import total\n\n\ndef daily(lines):\n    return total(lines)\n",
}
ISSUE = "total() is wrong: round_vnd drops the cents of a checkout total"


def _service(tmp_path: Path) -> tuple[SQLiteGraphService, dict]:
    root = tmp_path / "repo"
    for path, text in REPO.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/tools", repository_revision="rev").build(root)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    return SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test"), document


def _id(document: dict, qualified_name: str) -> str:
    return next(node["id"] for node in document["nodes"] if node["qualified_name"] == qualified_name)


def _best_call_confidence(document: dict, caller: str, callee: str) -> float:
    sites = {edge["target_id"] for edge in document["edges"] if edge["type"] == "CONTAINS" and edge["source_id"] == caller}
    return max(edge["confidence"] for edge in document["edges"]
               if edge["type"] == "CALLS" and edge["source_id"] in sites and edge["target_id"] == callee)


def test_callers_carry_confidence_resolution_and_tool_of_their_best_call_edge(tmp_path):
    service, document = _service(tmp_path)
    callee, caller = _id(document, "shop.pricing.round_vnd"), _id(document, "shop.checkout.total")
    [up] = [symbol for symbol in service.get_callers(callee).symbols if symbol.symbol_id == caller]
    assert up.confidence == _best_call_confidence(document, caller, callee)
    assert up.resolution and up.source_tool
    [down] = [symbol for symbol in service.get_callees(caller).symbols if symbol.symbol_id == callee]
    assert down.confidence == up.confidence


def test_depth_two_traversal_keeps_confidence(tmp_path):
    service, document = _service(tmp_path)
    result = service.traverse(_id(document, "shop.pricing.round_vnd"), "callers", 2)
    assert {symbol["hop"] for symbol in result["symbols"]} == {1, 2}
    assert all(symbol["confidence"] is not None for symbol in result["symbols"])


def test_related_context_ranks_against_the_task_bound_by_find_task_anchors(tmp_path):
    service, document = _service(tmp_path)
    version, anchor = document["graph_version"], _id(document, "shop.checkout.total")
    full = service.get_related_context([anchor], 2000, graph_version=version, task_id="full", issue_text=ISSUE)
    service.find_task_anchors(ISSUE, None, graph_version=version, task_id="bound")
    short = service.get_related_context([anchor], 2000, graph_version=version, task_id="bound", issue_text="total")
    assert short["diagnostics"]["candidates"] == full["diagnostics"]["candidates"]
    assert [item["node_id"] for item in short["context"]["items"]] == [item["node_id"] for item in full["context"]["items"]]


def test_related_context_without_a_bound_task_uses_the_given_issue_text(tmp_path):
    service, document = _service(tmp_path)
    version, anchor = document["graph_version"], _id(document, "shop.checkout.total")
    given = service.get_related_context([anchor], 2000, graph_version=version, task_id="x", issue_text=ISSUE)
    other = service.get_related_context([anchor], 2000, graph_version=version, task_id="y", issue_text="total")
    assert given["diagnostics"]["candidates"] != other["diagnostics"]["candidates"]


@pytest.fixture
def server(tmp_path, monkeypatch) -> tuple[dict, Path]:
    service, document = _service(tmp_path)
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(audit))
    monkeypatch.setattr(graph_server, "graph_service", service)
    return document, audit


def _related(document: dict) -> dict:
    return graph_server.get_related_context(anchor_ids=[_id(document, "shop.checkout.total")],
                                            graph_version=document["graph_version"], task_id="t",
                                            budget_tokens=2000, issue_text=ISSUE)


def test_related_context_result_keeps_only_budget_and_traversal_flag(server):
    document, _ = server
    response = _related(document)
    assert response["status"] == "PASS"
    assert set(response["data"]["diagnostics"]) == {"budget", "traversal_limited"}


def test_related_context_audit_line_holds_the_full_diagnostics(server):
    document, audit = server
    _related(document)
    payload = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()][-1]["payload"]
    assert payload["diagnostics"]["candidates"] and "config" in payload["diagnostics"]


def test_get_callers_tool_shows_edge_confidence(server):
    document, _ = server
    response = graph_server.get_callers(_id(document, "shop.pricing.round_vnd"))
    assert response["status"] == "PASS"
    assert all(caller["confidence"] is not None for caller in response["data"]["callers"])


def test_audit_diagnostics_stay_under_the_audit_line_cap_on_a_large_neighbourhood():
    """6,000 candidates of ~1 KB (N on a big repo) once made audit.write refuse the line and the tool fail."""
    candidate = {"node_id": "n" * 120, "graph_rationale": ["CALLS:" + "x" * 200] * 3, "features": {"f": "y" * 300}}
    diagnostics = {"candidates": [candidate] * 6000, "omissions": [{"node_id": "o" * 100, "reason": "token_budget"}] * 900,
                   "config": {"max_candidates": 6000}, "traversal_limited": False}
    kept = graph_server._audit_diagnostics(diagnostics)
    assert len(json.dumps(kept)) < 65536
    assert kept["candidates"] == diagnostics["candidates"][:graph_server.AUDIT_LIST_ITEMS]
    assert kept["candidate_count"] == 6000 and kept["omission_count"] == 900 and kept["config"] == diagnostics["config"]


def test_host_can_set_the_candidate_limit_of_related_context(server, monkeypatch):
    document, audit = server
    monkeypatch.setenv("VGAR_RETRIEVAL_MAX_CANDIDATES", "7")
    assert _related(document)["status"] == "PASS"
    payload = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()][-1]["payload"]
    assert payload["diagnostics"]["config"]["max_candidates"] == 7


def test_without_the_host_setting_related_context_keeps_the_default_limit(server, monkeypatch):
    from vgar.graph.retrieval import RESOURCE_LIMIT_CANDIDATES
    document, audit = server
    monkeypatch.delenv("VGAR_RETRIEVAL_MAX_CANDIDATES", raising=False)
    _related(document)
    payload = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()][-1]["payload"]
    assert payload["diagnostics"]["config"]["max_candidates"] == RESOURCE_LIMIT_CANDIDATES
