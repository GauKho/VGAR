from __future__ import annotations

import os
import sys
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from vgar.config.settings import Settings, get_settings
from vgar.observability.instrumentation import current_run_id

SERVER_NAMES = ("graph", "repository", "execution")

# S7: MCP children get only what they need; anything else (tokens, keys) stays in the parent.
_CHILD_ENV_ALLOW = frozenset({
    # POSIX / Windows system
    "PATH", "PATHEXT", "HOME", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "TMP", "TEMP", "TMPDIR", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "USERPROFILE",
    "USERNAME", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "COMMONPROGRAMFILES", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    # Python / venv / conda
    "PYTHONPATH", "PYTHONHOME", "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE",
    "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "CONDA_EXE",
    # Hugging Face cache / offline flags, GPU selection
    "HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "CUDA_VISIBLE_DEVICES",
})


def _child_env(settings: Settings) -> dict[str, str]:
    """Allow-listed parent env plus every VGAR_*, with VGAR_* derived from the Settings object."""
    env = {k: v for k, v in os.environ.items()
           if k.upper() in _CHILD_ENV_ALLOW or k.upper().startswith("VGAR_")}
    env.update(settings.to_env())
    return env


def create_mcp_client(settings: Settings | None = None, servers: tuple[str, ...] = SERVER_NAMES,
                      extra_env: dict[str, str] | None = None) -> MultiServerMCPClient:
    settings = settings or get_settings()
    env = _child_env(settings)
    env.update(extra_env or {})
    # Bind MCP subprocess logs to the workflow invocation that created the agent.
    run_id = current_run_id()
    if run_id:
        env["VGAR_TRACE_RUN_ID"] = run_id

    connections = {
        name: {
            "transport": "stdio",
            "command": sys.executable,  # same interpreter/venv as the caller
            "args": ["-m", f"vgar.mcp.servers.{name}_server"],
            "env": env,
        }
        for name in servers
    }

    return MultiServerMCPClient(
        connections,
        tool_name_prefix=True,
        handle_tool_errors=True,
    )
