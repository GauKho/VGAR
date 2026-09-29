from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("vgar-execution")


@mcp.tool()
def health() -> dict[str, Any]:
    """
    Execution MCP health check.

    Real pytest/type/lint verification tools arrive
    during repair/verification milestones.
    """
    return {
        "status": "OK",
        "server": "execution",
        "phase": "infrastructure",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()