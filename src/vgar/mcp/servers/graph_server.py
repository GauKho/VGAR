from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.graph.demo_service import DemoGraphService


mcp = FastMCP("vgar-graph")
graph_service = DemoGraphService()


@mcp.tool()
def search_symbols(
    query: str,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search repository symbols.

    Search the deterministic demo graph.
    """
    result = graph_service.search_symbols(
        query=query,
        limit=limit,
    )

    return {
        "status": "OK",
        "query": result.query,
        "symbols": [
            symbol.model_dump()
            for symbol in result.symbols
        ],
        "limit": limit,
        "metadata": {
            "backend": "demo",
        },
    }


@mcp.tool()
def get_callers(
    symbol_id: str,
    depth: int = 1,
) -> dict[str, Any]:
    """
    Return callers of a symbol.
    """
    result = graph_service.get_callers(symbol_id)

    return {
        "status": "OK",
        "symbol_id": symbol_id,
        "depth": depth,
        "callers": [
            symbol.model_dump()
            for symbol in result.symbols
        ],
        "metadata": {
            "backend": "demo",
        },
    }


@mcp.tool()
def get_callees(
    symbol_id: str,
    depth: int = 1,
) -> dict[str, Any]:
    """
    Return callees of a symbol.
    """
    result = graph_service.get_callees(symbol_id)

    return {
        "status": "OK",
        "symbol_id": symbol_id,
        "depth": depth,
        "callees": [
            symbol.model_dump()
            for symbol in result.symbols
        ],
        "metadata": {
            "backend": "demo",
        },
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
