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
