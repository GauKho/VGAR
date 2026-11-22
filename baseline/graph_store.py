"""One SQLite graph per (task, build), shared by the offline tier (T1) and the LLM tier (T2) (spec 2026-11-19 §7).

The graph is built the way R1 builds it (``run_graph_retrieval.load_or_build_graph``), then stored with
``SQLiteGraphStore``; the MCP graph server can serve the same file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import baseline._paths  # noqa: F401

# isort: split
import run_graph_retrieval as runner

from vgar.graph.layer_config import LayerConfigs, layer_summary
from vgar.graph.sqlite_store import SQLiteGraphStore


def graph_db_path(graphs_dir: Path, build: str, instance_id: str) -> Path:
    return Path(graphs_dir) / build / f"{instance_id}.db"


def load_or_build(root: Path, row: dict, tree: Path, *, build: str, layers: LayerConfigs, graphs_dir: Path,
                  builder_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The task's graph for one build: read from SQLite when built by this builder, otherwise built and stored.

    Args:
        root: Evaluation root (R1 layout).
        row: Manifest task (``instance_id``, ``repo``, ``base_commit``).
        tree: Extracted Python tree of the task.
        build: Build name (``baseline.profiles.BUILDS``).
        layers: Optional layers of the build.
        graphs_dir: Directory of the SQLite graphs.
        builder_hash: Fingerprint of the vgar source tree; another value forces a rebuild.
    """
    db = graph_db_path(graphs_dir, build, row["instance_id"])
    meta_path = db.with_suffix(".meta.json")
    if db.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["builder_hash"] == builder_hash:
            store = SQLiteGraphStore(db, graph_version=meta["graph_version"])
            return store.load_document(meta["graph_version"]), meta | {"db": db, "from_cache": True}
    # A killed build leaves SQLite side files; a stale -journal would be rolled into the next database of this name.
    for stale in (db, meta_path, *(db.with_name(db.name + suffix) for suffix in ("-journal", "-wal", "-shm"))):
        stale.unlink(missing_ok=True)
    document, built = runner.load_or_build_graph(root, row, tree, rebuild=True, builder_hash=builder_hash,
                                                 cache=False, layers=layers)
    db.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteGraphStore(db)
    store.initialize()
    store.ingest(document)
    meta = {"build": build, "graph_version": document["graph_version"], "build_seconds": built["build_seconds"],
            "builder_hash": builder_hash,
            "layer_status": layer_summary(document, layers) if layers.any_optional else {}}
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return document, meta | {"db": db, "from_cache": False}
