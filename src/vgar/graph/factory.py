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

    if backend == "snapshot":
        from vgar.graph.storage_capabilities import SnapshotGraphStore, legacy_profile

        snapshot_manifest = os.getenv("VGAR_GRAPH_SNAPSHOT_MANIFEST", "").strip()
        graph_version = os.getenv("VGAR_GRAPH_VERSION", "").strip()
        resolver_hash = os.getenv("VGAR_GRAPH_RESOLVER_HASH", "").strip()
        profile_hash = os.getenv("VGAR_GRAPH_PROFILE_HASH", "").strip()
        if not all((snapshot_manifest, graph_version, resolver_hash, profile_hash)):
            raise RuntimeError("Snapshot backend requires explicit manifest, version, resolver hash and profile hash")
        store = SnapshotGraphStore(snapshot_manifest, graph_version=graph_version,
                                   profiles=(legacy_profile(resolver_hash=resolver_hash, profile_hash=profile_hash),))
    elif backend == "sqlite":
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
    else:
        raise RuntimeError(
            f"Unsupported VGAR_GRAPH_BACKEND: {backend!r}; "
            "expected 'demo', 'sqlite' or 'snapshot'"
        )

    if backend in {"sqlite", "snapshot"}:
        manifest = os.getenv("VGAR_TOKENIZER_MANIFEST", "").strip()
        counter = None
        if manifest:
            from vgar.graph.token_counter import LocalTokenizerCounter
            counter = LocalTokenizerCounter(manifest)
        return SQLiteGraphService(store, repository_root=os.getenv("VGAR_REPOSITORY_ROOT", "").strip() or None,
                                  count_tokens=counter, counter_label=counter.counter_label if counter else "")
