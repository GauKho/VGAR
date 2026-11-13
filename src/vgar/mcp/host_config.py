"""Check, when a host starts a server, that its configuration declares everything the server works on.

Proposal §10.5: "path jail: chỉ truy cập repo được allowlist". The repository and every file a server writes come
from the host configuration (``env``), as absolute paths. ``import vgar`` loads the VGAR project's ``.env`` without
overriding the host, so an undeclared variable would silently take a relative value there, resolved against the
repository being edited; such values are refused here.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

Server = Literal["graph", "execution", "repository"]
_HINT = "declare these in the host configuration (env), with absolute paths (proposal §10.5: only allowlisted repositories)"


def _value(environ: Mapping[str, str], name: str) -> str:
    return (environ.get(name) or "").strip()


def _absolute(environ: Mapping[str, str], name: str, *, directory: bool = False, required: bool = True) -> list[str]:
    raw, value = environ.get(name) or "", _value(environ, name)
    if not value:
        return [f"{name} is not set"] if required else []
    if raw != value:  # the servers read these values unstripped (Path(os.getenv(...)), leased_root)
        return [f"{name}={raw!r} has spaces around it"]
    if not Path(value).is_absolute():
        return [f"{name}={value} is not an absolute path"]
    if directory and not Path(value).is_dir():
        return [f"{name}={value} is not an existing directory"]
    return []


def check_host_config(server: Server, environ: Mapping[str, str] | None = None) -> list[str]:
    """Problems with the host configuration of ``server``, each starting with the variable name.

    Args:
        server: ``graph``, ``execution`` or ``repository``.
        environ: Settings to check; defaults to ``os.environ``.

    Returns:
        One message per problem; empty when the configuration is complete.
    """
    env = os.environ if environ is None else environ
    problems = _absolute(env, "VGAR_MCP_AUDIT_LOG")
    if server == "repository":
        return problems + _absolute(env, "VGAR_LEASE_ROOT", directory=True)
    if server == "graph":
        if (_value(env, "VGAR_GRAPH_BACKEND").lower() or "sqlite") != "sqlite":
            return problems  # a snapshot is read-only and names no repository
        return problems + _absolute(env, "VGAR_REPOSITORY_ROOT", directory=True) + _absolute(env, "VGAR_GRAPH_DATABASE")
    # execution: run_pytest works in VGAR_LEASE_ROOT, run_relevant_tests in VGAR_REPOSITORY_ROOT with its graph
    if not _value(env, "VGAR_REPOSITORY_ROOT") and not _value(env, "VGAR_LEASE_ROOT"):
        return problems + ["VGAR_REPOSITORY_ROOT is not set (or set VGAR_LEASE_ROOT)"]
    problems += _absolute(env, "VGAR_LEASE_ROOT", directory=True, required=False)
    if _value(env, "VGAR_REPOSITORY_ROOT"):
        problems += _absolute(env, "VGAR_REPOSITORY_ROOT", directory=True) + _absolute(env, "VGAR_GRAPH_DATABASE")
    return problems


def require_host_config(server: Server) -> None:
    """Stop the process, naming each problem on stderr, when the host configuration of ``server`` is incomplete.

    Args:
        server: ``graph``, ``execution`` or ``repository``.
    """
    problems = check_host_config(server)
    if not problems:
        return
    from vgar.mcp.logging_setup import configure_server_logging

    configure_server_logging()
    for problem in problems:
        logger.error("vgar-%s cannot start: %s", server, problem)
    logger.error("vgar-%s: %s", server, _HINT)
    raise SystemExit(2)
