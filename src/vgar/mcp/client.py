import sys

from langchain_mcp_adapters.client import MultiServerMCPClient


def create_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "graph": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [
                    "-m",
                    "vgar.mcp.servers.graph_server",
                ],
            },
        },
        tool_name_prefix=True,
        handle_tool_errors=True,
    )