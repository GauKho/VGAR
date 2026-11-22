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
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.incremental import IncrementalGraphBuilder
from vgar.graph.layer_config import LayerConfigs, layer_summary
from vgar.graph.snapshot_sources import read_graph_sources
from vgar.graph.sqlite_store import SQLiteGraphStore

logger = logging.getLogger(__name__)


class _Job:
    """One build or update, run to completion by its own thread even when the caller stops waiting."""

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: dict[str, Any] | None = None
        self.error: BaseException | None = None


def head_revision(root: Path, *, check_dirty: bool = True) -> tuple[str, bool]:
    """The repository's HEAD commit and whether tracked files differ from it; ``("cli", False)`` outside Git.

    The check never writes ``.git/index``: refreshing its stat cache belongs to the user's own Git.

    Args:
        root: Repository root.
        check_dirty: Compare tracked files with HEAD (reads every file whose stat drifted); ``False`` returns
            ``(sha, False)`` from HEAD alone.
    """
    try:
        from dulwich import porcelain
        from dulwich.errors import NotGitRepository
        from dulwich.repo import Repo
    except ImportError:
        return "cli", False
    try:
        with Repo(str(root)) as repo:
            sha = repo.head().decode("ascii")
            if not check_dirty:
                return sha, False
            status = porcelain.status(repo, untracked_files="no", optional_locks=False)
    except (NotGitRepository, KeyError, OSError):
        return "cli", False
    except Exception:  # noqa: BLE001 - corrupt index or object data: build without history, never fail the build
        logger.warning("Cannot read the Git HEAD of %s; using revision 'cli'", root, exc_info=True)
        return "cli", False
    dirty = any(status.staged.values()) or bool(status.unstaged)
    return sha, dirty


def enclosing_git_root(root: Path) -> Path | None:
    """The nearest parent folder holding ``.git`` when ``root`` itself has none; history then is not read.

    Args:
        root: Repository root.
    """
    if (root / ".git").exists():
        return None
    return next((parent for parent in root.parents if (parent / ".git").exists()), None)


class LiveGraphBuilder:
    """One repository, one database, one builder cache for the life of the server process."""

    def __init__(self, repository_root: Path, database: Path, *, timeout_seconds: float = 900,
                 layers: LayerConfigs | None = None) -> None:
        """Bind the builder to a repository and its graph database.

        Args:
            repository_root: Repository the graph is built from; its folder name is the repo key, as in `vgar index`.
            database: SQLite file the graph server reads.
            timeout_seconds: How long one call waits for the build or update before answering TIMEOUT.
            layers: Optional layers configured by the host; when any is on, every call is a full build
                (incremental updates support the static resolver only).
        """
        self.root = Path(repository_root).resolve()
        self.database = Path(database)
        self.timeout_seconds = timeout_seconds
        self.layers = layers or LayerConfigs()
        self._incremental: IncrementalGraphBuilder | None = None
        self._revision: str | None = None
        self._dirty = False
        self._guard = threading.Lock()
        self._job: _Job | None = None
        self._enclosing_git = enclosing_git_root(self.root)
        if self._enclosing_git is not None:
            logger.warning("%s has no .git but %s does; revision and history stay off. Set VGAR_REPOSITORY_ROOT "
                           "to the folder holding .git to use them", self.root, self._enclosing_git)

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
            revision, _ = head_revision(self.root, check_dirty=False)
            # A new HEAD starts a new snapshot lineage: the cached builder carries the old revision.
            cold = self._incremental is None or previous is None or revision != self._revision
            builder, document, changed = self._compute(None if cold else self._incremental, revision)
            # Full comparison with HEAD only on a cold build; an update is dirty once any graphed file changed
            # since HEAD was read (a revert to HEAD stays dirty until HEAD moves: the safe side).
            dirty = head_revision(self.root)[1] if cold else self._dirty or bool(changed)
            self._incremental, self._revision, self._dirty = builder, revision, dirty
            layers = layer_summary(document, self.layers)
            source = "git-head" if revision != "cli" else "parent-repo-not-supported" if self._enclosing_git else "none"
            document["statistics"].update(revision_source=source,
                                          worktree_dirty=dirty, layers=layers)
            version = str(document["graph_version"])
            if version != previous:
                store.ingest(document, sources=read_graph_sources(self.root, document))
                # The published snapshot is the only one of this repository: reverting an edit cannot leave an
                # older row "latest", and the database does not grow with every edit.
                store.prune_other_versions(version, str(document["repo_key"]))
            elif not store.get_sources(version):   # a graph stored before source copies existed
                store.put_sources(version, read_graph_sources(self.root, document))
            job.result = {"graph_version": version, "previous_graph_version": previous,
                          "mode": "cold" if cold else "incremental", "changed_files": changed,
                          "nodes": len(document["nodes"]), "edges": len(document["edges"]),
                          "duration_ms": round((time.monotonic() - started) * 1000), "unchanged": version == previous,
                          "revision": revision, "worktree_dirty": dirty, "layers": layers}
            logger.info("graph %s: version=%s changed_files=%d nodes=%d duration_ms=%d", job.result["mode"], version,
                        len(changed), job.result["nodes"], job.result["duration_ms"])
        except BaseException as error:  # noqa: BLE001 - handed to the waiting caller
            self._incremental = None
            job.error = error
        finally:
            job.done.set()

    def _compute(self, incremental: IncrementalGraphBuilder | None, revision: str
                 ) -> tuple[IncrementalGraphBuilder | None, dict[str, Any], list[str]]:
        if self.layers.any_optional:
            builder = PythonGraphBuilder(repo_key=self.root.name, repository_revision=revision,
                                         **self.layers.builder_kwargs())
            return None, builder.build(self.root), []
        if incremental is None:
            builder = IncrementalGraphBuilder(repo_key=self.root.name, repository_revision=revision)
            return builder, builder.build(self.root), []
        document, summary = incremental.update(self.root)
        changed = sorted({*summary.changed_files, *summary.added_files, *summary.deleted_files})
        return incremental, document, changed
