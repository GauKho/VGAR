from __future__ import annotations

import os
from pathlib import Path

from vgar.graph.port import GraphService
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.token_counter import FALLBACK_COUNTER_LABEL, bytes_div4_counter

_BUILD_HINT = "build a real graph with `vgar index <repo> --db <file>.db` and set VGAR_GRAPH_DATABASE"


def create_graph_service() -> GraphService:
    """Create the graph backend from the environment; only real graphs are served.

    ``VGAR_GRAPH_BACKEND`` is ``sqlite`` (default) or ``snapshot``. A missing graph
    fails at startup instead of falling back to placeholder data.
    """

    backend = os.getenv("VGAR_GRAPH_BACKEND", "sqlite").strip().lower() or "sqlite"
    if backend == "demo":
        raise RuntimeError(f"Backend 'demo' was removed; {_BUILD_HINT}")

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
            raise RuntimeError(f"VGAR_GRAPH_DATABASE is required when VGAR_GRAPH_BACKEND=sqlite; {_BUILD_HINT}")
        database = Path(database_value)
        repository_root = os.getenv("VGAR_REPOSITORY_ROOT", "").strip()
        # A configured repository lets the agent build the first graph itself through
        # build_or_update_graph (proposal §10.3, §11); read tools answer GRAPH_NOT_READY until then.
        buildable = bool(repository_root) and Path(repository_root).is_dir()
        if not database.is_file() and not buildable:
            raise RuntimeError(f"Graph database not found: {database}; {_BUILD_HINT}")
        if not database.is_file():
            database.parent.mkdir(parents=True, exist_ok=True)

        graph_version = os.getenv("VGAR_GRAPH_VERSION", "").strip() or None
        store = SQLiteGraphStore(database, graph_version=graph_version)
        if not buildable:
            store.resolve_graph_version()
    else:
        raise RuntimeError(f"Unsupported VGAR_GRAPH_BACKEND: {backend!r}; expected 'sqlite' or 'snapshot'")

    # One counter, UTF-8 bytes / 4, the same as the retrieval evaluation: the proposal names no tokenizer.
    return SQLiteGraphService(store, repository_root=os.getenv("VGAR_REPOSITORY_ROOT", "").strip() or None,
                              count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL)
