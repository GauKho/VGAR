from __future__ import annotations

import os
import sys
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from vgar.config.settings import SECRET_KEYS, Settings, get_settings
from vgar.observability.instrumentation import current_run_id

SERVER_NAMES = ("graph", "repository", "execution")


def _child_env(settings: Settings) -> dict[str, str]:
    """Parent env minus secrets, with VGAR_* derived from the Settings object."""
    env = {k: v for k, v in os.environ.items() if k not in SECRET_KEYS}
    env.update(settings.to_env())
    return env


def create_mcp_client(settings: Settings | None = None) -> MultiServerMCPClient:
    settings = settings or get_settings()
    env = _child_env(settings)
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
        for name in SERVER_NAMES
    }

    return MultiServerMCPClient(
        connections,
        tool_name_prefix=True,
        handle_tool_errors=True,
    )
