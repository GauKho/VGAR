"""Server logging per the MCP build-server guide (2026-07-28).

STDIO servers never write to stdout (it carries JSON-RPC); logs go to stderr, which the host captures.
Protocol logging (``notifications/message``) is deprecated in 2026-07-28 and is not used.
The level comes from ``VGAR_MCP_LOG_LEVEL`` (DEBUG, INFO, WARNING, ERROR); the default WARNING keeps
TV1's trace spec P8 (no per-request INFO lines).
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def server_log_level() -> str:
    """The level named by ``VGAR_MCP_LOG_LEVEL``; unknown or empty values fall back to WARNING."""
    value = os.getenv("VGAR_MCP_LOG_LEVEL", "").strip().upper()
    return value if value in LEVELS else "WARNING"


def configure_server_logging() -> str:
    """Send the ``vgar`` loggers to stderr at the configured level; safe to call more than once.

    Called from a server's ``main()`` only, so importing a server module (tests, tools) changes nothing.

    Returns:
        The level name in effect.
    """
    level = server_log_level()
    package = logging.getLogger("vgar")
    if not any(getattr(handler, "_vgar", False) for handler in package.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler._vgar = True  # marks the handler this function owns
        handler.setFormatter(logging.Formatter(_FORMAT))
        package.addHandler(handler)
    package.setLevel(level)
    package.propagate = False  # the SDK may configure the root logger too; avoid duplicate lines
    raw = os.getenv("VGAR_MCP_LOG_LEVEL", "").strip()
    if raw and raw.upper() not in LEVELS:
        logger.warning("Unknown VGAR_MCP_LOG_LEVEL %r; using WARNING", raw)
    return level
