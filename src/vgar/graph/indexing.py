"""Build a repository's graph snapshot into SQLite: the database the MCP graph server reads."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def index_repo(repo: Path, db: Path) -> int:
    """Build the graph snapshot for ``repo`` into the SQLite file ``db``.

    Args:
        repo: Repository root to index; its folder name becomes the repo key.
        db: SQLite file to write; parent folders are created.

    Returns:
        Number of nodes in the built graph.
    """
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_store import SQLiteGraphStore

    doc = PythonGraphBuilder(repo_key=repo.name, repository_revision="cli").build(repo)
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteGraphStore(db).ingest(doc)
    logger.info("indexed %s: %d nodes, %d edges -> %s", repo, len(doc["nodes"]), len(doc["edges"]), db)
    return len(doc["nodes"])
