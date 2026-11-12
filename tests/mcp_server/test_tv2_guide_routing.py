"""Guide-style routing: tools and resources use graph_service when no host provider is registered (spec §7.2)."""
from __future__ import annotations

import pytest

from graph_fixture import fixture_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


@pytest.fixture
def served(tmp_path, monkeypatch):
    service = fixture_service(tmp_path / "graph")
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    version = service.get_repository_summary().graph_version
    ids = {node["qualified_name"]: node["id"] for node in service._document(version)["nodes"]
           if node["type"] in {"Function", "Method", "Class", "Test"}}
    return service, ids


def test_get_callers_depth_two_runs_without_a_provider(served):
    _, ids = served
    response = graph_server.get_callers(ids["app.parser.normalize"], depth=2)
    assert response["status"] == "PASS", response
    hops = {item["symbol_id"]: item["hop"] for item in response["data"]["callers"]}
    assert hops[ids["tests.test_service.test_login"]] == 2


def test_get_callees_depth_two_lists_may_call(served):
    _, ids = served
    response = graph_server.get_callees(ids["app.service.login"], depth=2)
    assert response["status"] == "PASS", response
    assert [item["symbol_id"] for item in response["data"]["may_call"]] == [ids["db.store.Store.put"]]


def test_get_callers_depth_one_is_unchanged(served):
    _, ids = served
    response = graph_server.get_callers(ids["app.parser.normalize"])
    assert response["status"] == "PASS" and "may_call" not in response["data"]


def test_explain_dependency_path_runs_without_a_provider(served):
    _, ids = served
    response = graph_server.explain_dependency_path(ids["app.service.login"], ids["db.store.save_user"])
    assert response["status"] == "PASS", response
    assert response["data"]["found"] is True


def test_unknown_symbol_is_a_coded_error(served):
    response = graph_server.get_callers("missing:symbol", depth=2)
    assert response["status"] == "ERROR" and response["error"]["code"] == "NODE_NOT_FOUND"


def test_registered_traversal_provider_still_wins(served, monkeypatch):
    calls = []
    monkeypatch.setattr(graph_server, "_has_provider", lambda capability: True)
    monkeypatch.setattr(graph_server.core_tools, "respond", lambda *a, **k: calls.append(a[0]) or {"status": "PASS"})
    _, ids = served
    graph_server.get_callers(ids["app.parser.normalize"], depth=2)
    graph_server.explain_dependency_path(ids["app.service.login"], ids["db.store.save_user"])
    assert calls == ["get_callers", "explain_dependency_path"]


def test_resources_are_served_without_a_context(served):
    import json
    service, _ = served
    assert json.loads(graph_server._read_resource("vgar://repo/schema")) == service.get_schema()
    component = json.loads(graph_server._read_resource("vgar://component/app"))
    assert component["component"] == "app" and component["dependencies"] == ["db"]
    assert json.loads(graph_server._read_resource("vgar://evidence/baseline"))["tests"] == "NOT_RUN"


def test_task_resource_after_find_task_anchors(served):
    import json
    service, _ = served
    version = service.get_repository_summary().graph_version
    graph_server.find_task_anchors("app/service.py login fails", version, "t1")
    assert json.loads(graph_server._read_resource("vgar://task/t1"))["task_id"] == "t1"
