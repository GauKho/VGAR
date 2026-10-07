"""Single source of configuration for VGAR.

Precedence (high -> low):  real environment  >  .env  >  defaults below.
Nothing else in the code base should call os.getenv for VGAR_* / HF_* keys.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Never forwarded to MCP child processes (the execution server runs pytest on
# untrusted repositories, so secrets must not be in its environment).
SECRET_KEYS = frozenset({"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_API_KEY"})


def load_env(dotenv_path: Path | None = None) -> None:
    """Load .env without overriding variables that are already set."""
    load_dotenv(dotenv_path or PROJECT_ROOT / ".env", override=False)


# --------------------------------------------------------------------- parsers
def _raw(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None  # "" == unset


def _str(name: str, default: str) -> str:
    return _raw(name) or default


def _int(name: str, default: int) -> int:
    value = _raw(name)
    try:
        return default if value is None else int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _float(name: str, default: float) -> float:
    value = _raw(name)
    try:
        return default if value is None else float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _path(name: str, default: str) -> Path:
    path = Path(_str(name, default)).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


# -------------------------------------------------------------------- sections
@dataclass(frozen=True)
class ModelSettings:
    provider: str = "huggingface"
    model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    temperature: float = 0.0
    max_new_tokens: int = 512
    device_map: str = "auto"
    torch_dtype: str = "auto"


@dataclass(frozen=True)
class AgentSettings:
    max_iterations: int = 5
    max_tool_calls: int = 30
    recursion_limit: int = 50
    token_budget: int = 8000


@dataclass(frozen=True)
class GraphSettings:
    backend: str = "demo"  # demo | sqlite
    database: Path | None = None
    version: str | None = None
    source_root: Path | None = None
    tokenizer_manifest: Path | None = None
    allow_fallback_counter: bool = False


@dataclass(frozen=True)
class Settings:
    model: ModelSettings = field(default_factory=ModelSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    graph: GraphSettings = field(default_factory=GraphSettings)
    audit_log: Path = PROJECT_ROOT / "logs" / "mcp_audit.jsonl"
    workspace_root: Path | None = None

    def to_env(self) -> dict[str, str]:
        """Variables the MCP servers read (graph/factory.py, graph_server.py)."""
        src = str(PROJECT_ROOT / "src")
        pythonpath = os.pathsep.join(p for p in (src, os.environ.get("PYTHONPATH", "")) if p)
        return {
            "VGAR_GRAPH_BACKEND": self.graph.backend,
            "VGAR_GRAPH_DATABASE": str(self.graph.database or ""),
            "VGAR_GRAPH_VERSION": self.graph.version or "",
            "VGAR_GRAPH_SOURCE_ROOT": str(self.graph.source_root or ""),
            "VGAR_TOKENIZER_MANIFEST": str(self.graph.tokenizer_manifest or ""),
            "VGAR_ALLOW_FALLBACK_COUNTER": "1" if self.graph.allow_fallback_counter else "0",
            "VGAR_MCP_AUDIT_LOG": str(self.audit_log),
            "VGAR_WORKSPACE_ROOT": str(self.workspace_root or ""),
            "PYTHONPATH": pythonpath,
        }


def _build() -> Settings:
    database = _raw("VGAR_GRAPH_DATABASE")
    workspace = _raw("VGAR_WORKSPACE_ROOT")
    source_root = _raw("VGAR_GRAPH_SOURCE_ROOT")
    tokenizer = _raw("VGAR_TOKENIZER_MANIFEST")
    return Settings(
        model=ModelSettings(
            provider=_str("VGAR_MODEL_PROVIDER", "huggingface").lower(),
            model_id=_str("HF_MODEL_ID", ModelSettings.model_id),
            temperature=_float("VGAR_TEMPERATURE", 0.0),
            max_new_tokens=_int("MAX_NEW_TOKENS", 512),
            device_map=_str("VGAR_DEVICE_MAP", "auto"),
            torch_dtype=_str("VGAR_TORCH_DTYPE", "auto"),
        ),
        agent=AgentSettings(
            max_iterations=_int("MAX_ITERATIONS", 5),
            max_tool_calls=_int("VGAR_MAX_TOOL_CALLS", 30),
            recursion_limit=_int("VGAR_RECURSION_LIMIT", 50),
            token_budget=_int("VGAR_TOKEN_BUDGET", 8000),
        ),
        graph=GraphSettings(
            backend=_str("VGAR_GRAPH_BACKEND", "demo").lower(),
            database=_path("VGAR_GRAPH_DATABASE", database) if database else None,
            version=_raw("VGAR_GRAPH_VERSION"),
            source_root=_path("VGAR_GRAPH_SOURCE_ROOT", source_root) if source_root else None,
            tokenizer_manifest=_path("VGAR_TOKENIZER_MANIFEST", tokenizer) if tokenizer else None,
            allow_fallback_counter=_str("VGAR_ALLOW_FALLBACK_COUNTER", "0") == "1",
        ),
        audit_log=_path("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl"),
        workspace_root=_path("VGAR_WORKSPACE_ROOT", workspace) if workspace else None,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env()
    return _build()


def reload_settings() -> Settings:
    """Drop the cache (tests / after changing os.environ at runtime)."""
    get_settings.cache_clear()
    return get_settings()
