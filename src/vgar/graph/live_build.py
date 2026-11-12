"""Build, then incrementally update, the graph of one repository on behalf of the MCP graph server.

Proposal §10.3 (``build_or_update_graph``), §11 (incremental update after each edit), plan L6-6. The first call
builds cold; later calls re-extract only changed files through ``IncrementalGraphBuilder`` and publish a new
snapshot to the server's SQLite database, where read tools pick it up on their next call.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from vgar.contracts.error import GraphNotReadyError
from vgar.graph.incremental import IncrementalGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore

logger = logging.getLogger(__name__)


class _Job:
    """One build or update, run to completion by its own thread even when the caller stops waiting."""

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: dict[str, Any] | None = None
        self.error: BaseException | None = None


class LiveGraphBuilder:
    """One repository, one database, one builder cache for the life of the server process."""

    def __init__(self, repository_root: Path, database: Path, *, timeout_seconds: float = 900) -> None:
        """Bind the builder to a repository and its graph database.

        Args:
            repository_root: Repository the graph is built from; its folder name is the repo key, as in `vgar index`.
            database: SQLite file the graph server reads.
            timeout_seconds: How long one call waits for the build or update before answering TIMEOUT.
        """
        self.root = Path(repository_root).resolve()
        self.database = Path(database)
        self.timeout_seconds = timeout_seconds
        self._incremental: IncrementalGraphBuilder | None = None
        self._guard = threading.Lock()
        self._job: _Job | None = None

    def run(self) -> dict[str, Any]:
        """Build the graph cold, or update it incrementally, and publish it as the only snapshot of this repository.

        A call that times out leaves its job running; the next call waits for that job and returns its result
        instead of starting another build.

        Returns:
            ``graph_version``, ``previous_graph_version``, ``mode`` (``cold`` or ``incremental``),
            ``changed_files``, ``nodes``, ``edges``, ``duration_ms`` and ``unchanged``.
        """
        with self._guard:
            if self._job is None:
                self._job = _Job()
                threading.Thread(target=self._work, args=(self._job,), name="vgar-graph-build", daemon=True).start()
            job = self._job
        if not job.done.wait(self.timeout_seconds):
            from vgar.mcp.schemas import TIMEOUT, CodedToolError
            raise CodedToolError(TIMEOUT, f"Graph build still running after {self.timeout_seconds}s; call again to "
                                          "wait for it, or build ahead of time with `vgar index`")
        with self._guard:
            if self._job is job:
                self._job = None
        if job.error is not None:
            raise job.error
        return dict(job.result)

    def _work(self, job: _Job) -> None:
        started = time.monotonic()
        try:
            store = SQLiteGraphStore(self.database)
            try:
                previous = store.resolve_graph_version()
            except GraphNotReadyError:
                previous = None
            cold = self._incremental is None or previous is None
            builder, document, changed = self._compute(None if cold else self._incremental)
            self._incremental = builder
            version = str(document["graph_version"])
            if version != previous:
                store.ingest(document)
                # The published snapshot is the only one of this repository: reverting an edit cannot leave an
                # older row "latest", and the database does not grow with every edit.
                store.prune_other_versions(version, str(document["repo_key"]))
            job.result = {"graph_version": version, "previous_graph_version": previous,
                          "mode": "cold" if cold else "incremental", "changed_files": changed,
                          "nodes": len(document["nodes"]), "edges": len(document["edges"]),
                          "duration_ms": round((time.monotonic() - started) * 1000), "unchanged": version == previous}
            logger.info("graph %s: version=%s changed_files=%d nodes=%d duration_ms=%d", job.result["mode"], version,
                        len(changed), job.result["nodes"], job.result["duration_ms"])
        except BaseException as error:  # noqa: BLE001 - handed to the waiting caller
            self._incremental = None
            job.error = error
        finally:
            job.done.set()

    def _compute(self, incremental: IncrementalGraphBuilder | None) -> tuple[IncrementalGraphBuilder, dict[str, Any], list[str]]:
        if incremental is None:
            builder = IncrementalGraphBuilder(repo_key=self.root.name, repository_revision="cli")
            return builder, builder.build(self.root), []
        document, summary = incremental.update(self.root)
        changed = sorted({*summary.changed_files, *summary.added_files, *summary.deleted_files})
        return incremental, document, changed
