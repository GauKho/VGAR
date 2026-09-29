import asyncio

from vgar.mcp.client import create_mcp_client


async def main() -> None:
    client = create_mcp_client()

    print("Loading MCP tools...")

    tools = await client.get_tools()

    print()
    print("Discovered tools:")

    for tool in tools:
        print(
            f" - {tool.name}"
        )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    expected_tools = {
        "graph_search_symbols",
        "graph_get_callers",
        "graph_get_callees",
    }

    missing = (
        expected_tools
        - set(tools_by_name)
    )

    if missing:
        raise RuntimeError(
            f"Missing MCP tools: {missing}"
        )

    print()
    print("===== SEARCH SYMBOLS =====")

    search_result = await tools_by_name[
        "graph_search_symbols"
    ].ainvoke(
        {
            "query": "login",
            "limit": 10,
        }
    )

    print(search_result)

    print()
    print("===== GET CALLERS =====")

    callers_result = await tools_by_name[
        "graph_get_callers"
    ].ainvoke(
        {
            "symbol_id":
                "function:auth.login",
        }
    )

    print(callers_result)

    print()
    print("===== GET CALLEES =====")

    callees_result = await tools_by_name[
        "graph_get_callees"
    ].ainvoke(
        {
            "symbol_id":
                "function:web.login_handler",
        }
    )

    print(callees_result)

    print()
    print("M3 STAGE 1: PASS")


if __name__ == "__main__":
    asyncio.run(main())