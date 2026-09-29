from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
)

from vgar.config import load_mcp_config


def _resolve_server_config(
    server: dict[str, Any],
) -> dict[str, Any]:
    transport = server.get(
        "transport",
        "stdio",
    )

    if transport != "stdio":
        return server

    command = server.get("command")

    if command == "python":
        command = sys.executable

    return {
        **server,
        "command": command,
    }


def create_mcp_client() -> MultiServerMCPClient:
    config = load_mcp_config()

    raw_servers = config.get("servers", {})

    if not raw_servers:
        raise RuntimeError(
            "No MCP servers configured."
        )

    connections = {
        name: _resolve_server_config(server)
        for name, server in raw_servers.items()
    }

    client_config = config.get(
        "client",
        {},
    )

    return MultiServerMCPClient(
        connections,
        tool_name_prefix=bool(
            client_config.get(
                "tool_name_prefix",
                True,
            )
        ),
        handle_tool_errors=bool(
            client_config.get(
                "handle_tool_errors",
                True,
            )
        ),
    )