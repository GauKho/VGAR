"""Single source of configuration for VGAR.

Precedence (high -> low):  real environment  >  .env  >  defaults below.
Covers the graph backend and the audit log; the MCP servers read their own VGAR_* variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_env(dotenv_path: Path | None = None) -> None:
    """Load .env without overriding variables that are already set."""
    load_dotenv(dotenv_path or PROJECT_ROOT / ".env", override=False)


# --------------------------------------------------------------------- parsers
def _raw(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None  # "" == unset


def _str(name: str, default: str) -> str:
    return _raw(name) or default


def _path(name: str, default: str) -> Path:
    path = Path(_str(name, default)).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


# -------------------------------------------------------------------- sections
@dataclass(frozen=True)
class GraphSettings:
    backend: str = "sqlite"  # sqlite | snapshot
    database: Path | None = None
    version: str | None = None


@dataclass(frozen=True)
class Settings:
    graph: GraphSettings = field(default_factory=GraphSettings)
    audit_log: Path = PROJECT_ROOT / "logs" / "mcp_audit.jsonl"


def _build() -> Settings:
    database = _raw("VGAR_GRAPH_DATABASE")
    return Settings(
        graph=GraphSettings(
            backend=_str("VGAR_GRAPH_BACKEND", "sqlite").lower(),
            database=_path("VGAR_GRAPH_DATABASE", database) if database else None,
            version=_raw("VGAR_GRAPH_VERSION"),
        ),
        audit_log=_path("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env()
    return _build()


def reload_settings() -> Settings:
    """Drop the cache (tests / after changing os.environ at runtime)."""
    get_settings.cache_clear()
    return get_settings()
