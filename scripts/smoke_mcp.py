from __future__ import annotations

import asyncio
import traceback

from vgar.mcp import create_mcp_client


async def main() -> None:
    print("Creating MCP client...")

    client = create_mcp_client()

    print("Loading MCP tools...")

    try:
        tools = await client.get_tools()

    except BaseException as exc:
        print()
        print("MCP TOOL LOADING FAILED")
        print("=" * 60)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print("Check each configured MCP server with:")
        print(
            "  python -m "
            "vgar.mcp.servers.graph_server"
        )
        print(
            "  python -m "
            "vgar.mcp.servers.repository_server"
        )
        print(
            "  python -m "
            "vgar.mcp.servers.execution_server"
        )

        print()
        print("Full traceback:")
        traceback.print_exception(exc)

        raise SystemExit(1) from exc

    print()
    print(
        f"Loaded {len(tools)} MCP tools:"
    )

    for tool in tools:
        print(
            f"  - {tool.name}"
        )


if __name__ == "__main__":
    asyncio.run(main())