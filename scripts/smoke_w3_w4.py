from __future__ import annotations

import asyncio
import json
import os

from vgar.mcp import create_mcp_client
from vgar.mcp.registry import W3_W4_REQUIRED_GRAPH_TOOLS, validate_required_tools

import json
from typing import Any


def parse_mcp_result(result: Any) -> dict:
    """Normalize LangChain/MCP tool output into a Python dict."""

    # MCP/LangChain may already return a dictionary.
    if isinstance(result, dict):
        return result

    # Older/simple adapters may return raw JSON text.
    if isinstance(result, str):
        return json.loads(result)

    # Current langchain-mcp-adapters may return MCP content blocks.
    if isinstance(result, list):
        for block in result:
            # Common dict representation:
            # {"type": "text", "text": "..."}
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    return json.loads(text)

            # Some MCP versions expose TextContent objects.
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return json.loads(text)

    raise TypeError(
        f"Unsupported MCP result type: {type(result).__name__}: {result!r}"
    )

async def main() -> None:
    client = create_mcp_client()
    tools = await client.get_tools()
    validate_required_tools(tools, W3_W4_REQUIRED_GRAPH_TOOLS)
    by_name = {tool.name: tool for tool in tools}

    search = await by_name["graph_search_symbols"].ainvoke({"query": "login", "limit": 10})
    print("graph_search_symbols:")
    print(search)

    payload = parse_mcp_result(search)
    symbols = payload.get("symbols", [])
    if not symbols:
        raise RuntimeError("W3-W4 smoke failed: no symbol matching 'login'")

    symbol_id = symbols[0]["symbol_id"]
    callers = await by_name["graph_get_callers"].ainvoke({"symbol_id": symbol_id, "depth": 1})
    callees = await by_name["graph_get_callees"].ainvoke({"symbol_id": symbol_id, "depth": 1})
    print("graph_get_callers:")
    print(callers)
    print("graph_get_callees:")
    print(callees)
    print("W3-W4 MCP tool smoke PASS")


if __name__ == "__main__":
    asyncio.run(main())
