from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vgar.agents.runtime import Runtime, index_repo
from vgar.agents.state import VGARState
from vgar.repair.workspace import create_workspace


def prepare_workspace(state: VGARState, runtime: Runtime) -> dict:
    """Index the source repo and copy it to a disposable workspace.

    Must run before any MCP client exists: the graph server reads its database
    path from the environment it is spawned with.
    """
    if not state.get("failing_tests"):
        raise ValueError("failing_tests (pytest selectors) is required to verify a patch")
    work_dir = state.get("work_dir")
    if not work_dir:
        raise ValueError("work_dir is required")

    repo = Path(state["repo_path"]).resolve(strict=True)
    work = Path(work_dir)
    db = work / "graph.db"

    node_count = index_repo(repo, db)
    lease = create_workspace(repo, work / "ws")

    base = runtime.base_settings()
    runtime.sandboxed = replace(
        base, graph=replace(base.graph, backend="sqlite", database=db,
                            source_root=lease.path, version=None),
        workspace_root=lease.path,
    )

    return {
        "graph_db": str(db),
        "graph_node_count": node_count,
        "workspace_path": str(lease.path),
        "worktree_id": lease.worktree_id,
        "source_hash_before": lease.source_hash_before,
    }
