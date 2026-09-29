from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.graph.demo_service import DemoGraphService
from vgar.mcp.audit import write_audit


mcp = FastMCP("vgar-graph")

graph_service = DemoGraphService()


@mcp.tool()
def search_symbols(
    query: str,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search repository symbols by name,
    qualified identifier, or file path.

    Use this tool when the exact symbol_id
    is not known yet.
    """

    args = {
        "query": query,
        "limit": limit,
    }

    try:
        result = graph_service.search_symbols(
            query=query,
            limit=limit,
        )

        write_audit(
            tool="search_symbols",
            arguments=args,
            status="ok",
        )

        return result.model_dump()

    except Exception:
        write_audit(
            tool="search_symbols",
            arguments=args,
            status="error",
        )

        raise


@mcp.tool()
def get_callers(
    symbol_id: str,
) -> dict[str, Any]:
    """
    Return repository symbols that call
    the exact symbol identified by symbol_id.

    Use search_symbols first when the exact
    symbol_id is unknown.
    """

    args = {
        "symbol_id": symbol_id,
    }

    try:
        result = graph_service.get_callers(
            symbol_id
        )

        write_audit(
            tool="get_callers",
            arguments=args,
            status="ok",
        )

        return result.model_dump()

    except Exception:
        write_audit(
            tool="get_callers",
            arguments=args,
            status="error",
        )

        raise


@mcp.tool()
def get_callees(
    symbol_id: str,
) -> dict[str, Any]:
    """
    Return repository symbols called by
    the exact symbol identified by symbol_id.
    """

    args = {
        "symbol_id": symbol_id,
    }

    try:
        result = graph_service.get_callees(
            symbol_id
        )

        write_audit(
            tool="get_callees",
            arguments=args,
            status="ok",
        )

        return result.model_dump()

    except Exception:
        write_audit(
            tool="get_callees",
            arguments=args,
            status="error",
        )

        raise


if __name__ == "__main__":
    mcp.run(transport="stdio")