"""The source bytes a graph snapshot was built from: read at build time, materialized for patch checks (spec 2026-11-22)."""
from __future__ import annotations

import hashlib
import logging
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

NO_SOURCE_COPY_HINT = ("this graph stores no copy of its source: rebuild it with build_or_update_graph to check edited "
                       "files without stashing")


def read_graph_sources(root: Path, document: Mapping[str, Any]) -> dict[str, bytes]:
    """Bytes of every File node of ``document``, read from ``root`` and checked against the node's content hash.

    Args:
        root: Repository the document was just built from.
        document: Graph document whose File nodes name the files.

    Returns:
        The bytes keyed by repository-relative path.
    """
    sources = {}
    for node in document["nodes"]:
        if node["type"] != "File":
            continue
        content = (Path(root) / node["path"]).read_bytes()
        if "sha256:" + hashlib.sha256(content).hexdigest() != node["content_hash"]:
            raise ValueError(f"file changed during the build: {node['path']}; call build_or_update_graph again")
        sources[node["path"]] = content
    return sources


def materialize_snapshot(sources: Mapping[str, bytes], target: Path, *, worktree: Path | None = None) -> Path:
    """Write the graph's source into ``target``: alone, or over a copy of the working tree's other files.

    Args:
        sources: Stored bytes of the snapshot's files, keyed by repository-relative path.
        target: Folder to create; must not exist yet.
        worktree: Repository whose non-graph files (configuration, data, ignored folders) the copy keeps; the
            ``.py`` files the builder sees are replaced by exactly the snapshot's.

    Returns:
        ``target``.
    """
    from vgar.graph.builder import discover_python_files

    target = Path(target)
    if worktree is None:
        target.mkdir(parents=True)
    else:
        shutil.copytree(worktree, target, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for path in discover_python_files(target):
            if path.relative_to(target).as_posix() not in sources:
                path.unlink()
    for relative, content in sources.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return target


def worktree_changes(sources: Mapping[str, bytes], root: Path) -> list[str]:
    """Python files of the working tree that differ from the graph's stored source: edited, added or missing.

    Args:
        sources: Stored source of the graph, keyed by repository-relative path.
        root: Working tree to compare with.

    Returns:
        Sorted repository-relative POSIX paths.
    """
    from vgar.graph.builder import discover_python_files

    current = {path.relative_to(root).as_posix(): path for path in discover_python_files(root)}
    changed = {relative for relative, path in current.items()
               if relative not in sources or path.read_bytes() != sources[relative]}
    return sorted(changed | (set(sources) - set(current)))
