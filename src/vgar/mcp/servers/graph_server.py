from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger


mcp = FastMCP("vgar-graph")
graph_service = create_graph_service()
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))

def _audit(event_type: str, payload: dict[str, Any]) -> None:
    _audit_logger.write(event_type, {"server": "graph", "backend": graph_service.backend_name, **payload})


@mcp.tool()
def search_symbols(query: str, limit: int = 20) -> dict[str, Any]:
    """Search repository symbols in the configured graph backend."""
    result = graph_service.search_symbols(query=query, limit=limit)
    response = {
        "status": "OK", "query": result.query,
        "symbols": [symbol.model_dump() for symbol in result.symbols],
        "limit": limit, "metadata": {"backend": graph_service.backend_name},
    }
    _audit("tool_call", {"tool": "search_symbols", "query": query, "limit": limit, "result_count": len(result.symbols)})
    return response


@mcp.tool()
def get_callers(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callers of a symbol. depth is reserved for W5-W6 traversal."""
    result = graph_service.get_callers(symbol_id)
    response = {
        "status": "OK", "symbol_id": symbol_id, "depth": depth,
        "callers": [symbol.model_dump() for symbol in result.symbols],
        "metadata": {"backend": graph_service.backend_name},
    }
    _audit("tool_call", {"tool": "get_callers", "symbol_id": symbol_id, "depth": depth, "result_count": len(result.symbols)})
    return response


@mcp.tool()
def get_callees(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callees of a symbol. depth is reserved for W5-W6 traversal."""
    result = graph_service.get_callees(symbol_id)
    response = {
        "status": "OK", "symbol_id": symbol_id, "depth": depth,
        "callees": [symbol.model_dump() for symbol in result.symbols],
        "metadata": {"backend": graph_service.backend_name},
    }
    _audit("tool_call", {"tool": "get_callees", "symbol_id": symbol_id, "depth": depth, "result_count": len(result.symbols)})
    return response


@mcp.resource("vgar://repo/summary")
def repo_summary() -> str:
    result = graph_service.get_repository_summary()
    _audit("resource_read", {"resource": "vgar://repo/summary"})
    return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/node/{node_id}")
def graph_node(node_id: str) -> str:
    result = graph_service.get_node(node_id)
    _audit("resource_read", {"resource": "vgar://graph/node/{node_id}", "node_id": node_id})
    return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/subgraph/{node_id}")
def graph_subgraph(node_id: str) -> str:
    result = graph_service.get_subgraph(node_id, depth=2)
    _audit("resource_read", {
        "resource": "vgar://graph/subgraph/{node_id}", "node_id": node_id,
        "depth": 2, "node_count": len(result.nodes), "edge_count": len(result.edges),
    })
    return result.model_dump_json(indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
