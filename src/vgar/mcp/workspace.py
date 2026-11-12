"""The repository a server works on is the folder the coding agent was opened in, unless the host config names one.

A host such as Claude Code starts stdio servers in the folder where the user ran it, so one MCP config serves every
repository. Each repository gets its own graph, outside the repository, at
``<data dir>/graphs/<folder name>-<first 8 hex of sha256(full path)>.db``: the same repository always maps to the
same graph, and two repositories with the same folder name (``app``, ``backend``) never share one.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from collections.abc import MutableMapping
from pathlib import Path

logger = logging.getLogger(__name__)

# A folder holding one of these is a repository; a home or download folder is not graphed by accident.
PROJECT_MARKERS = (".git", "pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini")
_FILE_KEYS = ("VGAR_GRAPH_DATABASE", "VGAR_MCP_AUDIT_LOG")


def data_dir() -> Path:
    """Where VGAR keeps graphs and logs: ``%LOCALAPPDATA%\\vgar`` on Windows, else ``$XDG_CACHE_HOME/vgar``."""
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "vgar"
    return Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache") / "vgar"


def default_database(repository: Path, base: Path | None = None) -> Path:
    """The graph file of ``repository``.

    Args:
        repository: Repository root.
        base: Data directory; defaults to ``data_dir()``.
    """
    root = repository.resolve()
    digest = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()[:8]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", root.name) or "repo"
    return (base or data_dir()) / "graphs" / f"{name}-{digest}.db"


def apply_workspace_defaults(server: str, environ: MutableMapping[str, str] | None = None, *,
                             cwd: Path | None = None, base: Path | None = None) -> Path | None:
    """Fill in unset repository, graph and log settings from the folder the server was started in.

    Values the host config sets are kept. Nothing is filled in when no repository is configured and the folder
    holds no project marker.

    Args:
        server: Server name (``graph``, ``execution``, ``repository``), used for the log file name.
        environ: Settings to fill in; defaults to ``os.environ``.
        cwd: Folder the server was started in; defaults to the current directory.
        base: Data directory; defaults to ``data_dir()``.

    Returns:
        The repository root in use, or None when there is none.
    """
    env = os.environ if environ is None else environ
    configured = (env.get("VGAR_REPOSITORY_ROOT") or env.get("VGAR_LEASE_ROOT") or "").strip()
    if configured:
        root = Path(configured).resolve()
    else:
        folder = (cwd or Path.cwd()).resolve()
        if not any((folder / marker).exists() for marker in PROJECT_MARKERS):
            return None
        root = folder
    base = base or data_dir()
    for key, value in (("VGAR_REPOSITORY_ROOT", str(root)), ("VGAR_LEASE_ROOT", str(root)),
                       ("VGAR_GRAPH_DATABASE", str(default_database(root, base))),
                       ("VGAR_MCP_AUDIT_LOG", str(base / "logs" / f"{server}.jsonl"))):
        current = (env.get(key) or "").strip()
        if current and key in _FILE_KEYS and not Path(current).is_absolute():
            # A relative file (e.g. from the VGAR project's .env) would be written inside the repository.
            logger.warning("%s=%s is relative to the repository being edited; using %s", key, current, value)
            current = ""
        if not current:
            env[key] = value
    return root
