from __future__ import annotations

import json
from pathlib import Path

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


def _sample_service() -> SQLiteGraphService:
    database = Path(__file__).parents[1] / "artifacts" / "sample_graph.db"
    return SQLiteGraphService(SQLiteGraphStore(database))


def test_repository_summary_reads_real_sqlite_graph():
    summary = _sample_service().get_repository_summary()
    assert summary.node_count > 0
    assert summary.edge_count > 0
    assert summary.node_counts_by_type.get("Function", 0) > 0


def test_graph_node_contract_is_repo_wrapped():
    service = _sample_service()
    search = service.search_symbols("login", limit=10)
    assert search.symbols

    anchor = search.symbols[0].symbol_id
    node = service.get_node(anchor)
    payload = node.model_dump()

    assert set(payload) == {"repo"}
    assert payload["repo"]["node_id"] == anchor
    assert payload["repo"]["type"] == "Function"
    assert payload["repo"]["path"] == "src/auth/service.py"
    assert payload["repo"]["start_line"] is not None
    assert payload["repo"]["end_line"] is not None
    assert 0.0 <= payload["repo"]["confidence"] <= 1.0
    assert payload["repo"]["provenance"] == "tree-sitter"


def test_get_node_and_subgraph_from_real_sqlite_graph():
    service = _sample_service()
    search = service.search_symbols("login", limit=10)
    assert search.symbols
    anchor = search.symbols[0].symbol_id

    node = service.get_node(anchor)
    assert node.repo.node_id == anchor

    subgraph = service.get_subgraph(anchor, depth=2)
    assert any(item.repo.node_id == anchor for item in subgraph.nodes)
    assert len(subgraph.nodes) >= 1

    serialized = json.loads(subgraph.model_dump_json())
    assert all(set(item) == {"repo"} for item in serialized["nodes"])


def _read_resource(uri: str) -> str:
    import asyncio
    from vgar.mcp.servers import graph_server
    contents = list(asyncio.run(graph_server.mcp.read_resource(uri)))
    return contents[0].content


def test_node_resource_roundtrip_encoded_id(monkeypatch, tmp_path):
    # S11 (B02): ids contain "/" and ":", so clients percent-encode them in the
    # URI; the resource must decode exactly once and find the node.
    from urllib.parse import quote
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import graph_server
    service = _sample_service()
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    node_id = service.search_symbols("login", limit=1).symbols[0].symbol_id
    assert "/" in node_id and ":" in node_id

    node = json.loads(_read_resource(f"vgar://graph/node/{quote(node_id, safe='')}"))
    subgraph = json.loads(_read_resource(f"vgar://graph/subgraph/{quote(node_id, safe='')}"))

    assert node["repo"]["node_id"] == node_id
    assert any(item["repo"]["node_id"] == node_id for item in subgraph["nodes"])


def test_node_resource_decodes_id_only_once(monkeypatch, tmp_path):
    # S11b: an id that itself contains an escape-looking sequence must reach
    # the service after exactly one decode, not two.
    from urllib.parse import quote
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import graph_server
    seen = []
    service = _sample_service()
    real_get_node = service.get_node
    monkeypatch.setattr(service, "get_node", lambda node_id: seen.append(node_id) or real_get_node(
        service.search_symbols("login", limit=1).symbols[0].symbol_id))
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    raw_id = "vgar:x:python:function:a%2Fb.py:f"

    _read_resource(f"vgar://graph/node/{quote(raw_id, safe='')}")

    assert seen == [raw_id]
