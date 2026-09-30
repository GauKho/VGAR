from __future__ import annotations

import os
from pathlib import Path

from vgar.graph.demo_service import DemoGraphService
from vgar.graph.port import GraphService
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


def create_graph_service() -> GraphService:
    """Create a graph backend without coupling the MCP server to storage."""

    backend = os.getenv("VGAR_GRAPH_BACKEND", "demo").strip().lower()
    if backend == "demo":
        return DemoGraphService()

    if backend == "sqlite":
        database_value = os.getenv("VGAR_GRAPH_DATABASE", "").strip()
        if not database_value:
            raise RuntimeError(
                "VGAR_GRAPH_DATABASE is required when "
                "VGAR_GRAPH_BACKEND=sqlite"
            )

        graph_version = os.getenv("VGAR_GRAPH_VERSION", "").strip() or None
        store = SQLiteGraphStore(
            Path(database_value),
            graph_version=graph_version,
        )
        store.resolve_graph_version()
        return SQLiteGraphService(store)

    raise RuntimeError(
        f"Unsupported VGAR_GRAPH_BACKEND: {backend!r}; "
        "expected 'demo' or 'sqlite'"
    )
