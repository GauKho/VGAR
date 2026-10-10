from pathlib import Path
import copy

import pytest

from vgar.contracts.error import GraphError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_bytes(b'def login():\r\n    return "caf\xc3\xa9"\r\n')
    document = PythonGraphBuilder(repo_key="demo/w5", repository_revision="fixture").build(repo)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    service = SQLiteGraphService(store, repository_root=repo, count_tokens=len, counter_label="test:characters")
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    return repo, store, document


def test_sqlite_roundtrip_keeps_unicode_byte_ranges(snapshot):
    repo, store, document = snapshot
    assert store.load_document(document["graph_version"]) == document
    restored = SQLiteGraphService(store, repository_root=repo, count_tokens=len, counter_label="test:characters")
    found = restored.find_task_anchors("login fails", graph_version=document["graph_version"], task_id="one")
    result = restored.get_related_context([found["anchors"][0]["node_id"]], 100,
                                         graph_version=document["graph_version"], task_id="one", issue_text="login fails")
    assert '"café"' in result["context"]["items"][0]["snippet"]
    assert result["overlay_id"] == found["overlay_id"]


def test_tools_are_stateless_and_enforce_budget_and_version(snapshot):
    repo, store, document = snapshot
    version = document["graph_version"]
    before = copy.deepcopy(store.load_document(version))
    found = graph_server.find_task_anchors("login fails", version, "one")
    assert found["status"] == "PASS"
    assert found["data"]["trace_nodes"][0]["type"] == "Issue"
    anchors = [anchor["node_id"] for anchor in found["data"]["anchors"]]
    context = graph_server.get_related_context(anchors, 100, version, "one", "login fails")
    assert context["status"] == "PASS"
    packed = context["data"]["context"]
    assert packed["items"] and packed["total_token_count"] <= 100
    tight = graph_server.get_related_context(anchors, 1, version, "two", "login fails")
    assert tight["data"]["context"]["items"] == []
    assert tight["data"]["overlay_id"] != context["data"]["overlay_id"]
    assert graph_server.find_task_anchors("login", "missing", "one")["error"]["code"] == "GRAPH_NOT_READY"
    assert graph_server.get_related_context(["missing"], 100, version, "one")["error"]["code"] == "NODE_NOT_FOUND"
    assert store.load_document(version) == before
    (repo / "app.py").write_text("def login(): return 2\n", encoding="utf-8")
    assert graph_server.get_related_context(anchors, 100, version, "one")["status"] == "ERROR"


def test_legacy_snapshot_requires_rebuild_for_retrieval(snapshot):
    _, store, document = snapshot
    with store._connect() as connection:
        connection.execute("UPDATE nodes SET range_json = NULL")
    assert store.search_symbols("login", 20)
    with pytest.raises(GraphError, match="rebuild"):
        store.load_document(document["graph_version"])
