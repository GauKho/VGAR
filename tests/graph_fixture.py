"""Real graph fixtures for tests: build a repository with the production builder into SQLite."""
from __future__ import annotations

import os
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore

FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "vgar-arch-cases" / "multi_package"


def build_fixture_database(target_dir: Path, repo: Path = FIXTURE_REPO) -> tuple[Path, str]:
    """Build ``repo`` with the real builder into ``target_dir/graph.db``.

    Args:
        target_dir: Directory that receives the SQLite file.
        repo: Repository to build; defaults to the multi-package architecture fixture.

    Returns:
        The database path and the graph version stored in it.
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    document = PythonGraphBuilder(repo_key=f"fixture/{Path(repo).name}", repository_revision="fixture").build(repo)
    database = target_dir / "graph.db"
    SQLiteGraphStore(database).ingest(document)
    return database, document["graph_version"]


def fixture_service(target_dir: Path, repo: Path = FIXTURE_REPO) -> SQLiteGraphService:
    """A ``SQLiteGraphService`` over a freshly built real graph of ``repo``.

    Args:
        target_dir: Directory that receives the SQLite file.
        repo: Repository to build; also used as the service's repository root.
    """
    database, version = build_fixture_database(target_dir, repo)
    store = SQLiteGraphStore(database, graph_version=version)
    store.resolve_graph_version()
    return SQLiteGraphService(store, repository_root=repo)


def real_graph_env() -> dict[str, str]:
    """Environment entries that point a server subprocess at the session's real fixture graph (set by conftest)."""
    return {key: os.environ[key] for key in ("VGAR_GRAPH_BACKEND", "VGAR_GRAPH_DATABASE", "VGAR_REPOSITORY_ROOT")}
