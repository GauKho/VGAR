from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("vgar-repository")


@mcp.tool()
def health() -> dict[str, Any]:
    """
    Repository MCP health check.

    Real repository tools arrive in W7-W8.
    """
    return {
        "status": "OK",
        "server": "repository",
        "phase": "infrastructure",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()