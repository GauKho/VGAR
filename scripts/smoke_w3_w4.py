from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path


# W3-W4 is the M1 integration checkpoint, so this smoke test intentionally
# exercises the real SQLite backend by default. Production/backend selection
# remains configurable through create_graph_service().
_REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("VGAR_GRAPH_BACKEND", "sqlite")
os.environ.setdefault(
    "VGAR_GRAPH_DATABASE",
    str((_REPO_ROOT / "artifacts" / "sample_graph.db").resolve()),
)

from vgar.mcp import create_mcp_client  # noqa: E402
from vgar.mcp.registry import W3_W4_REQUIRED_GRAPH_TOOLS, validate_required_tools  # noqa: E402



from vgar.mcp.result_parser import parse_mcp_json_result  # noqa: E402


async def main(query: str) -> None:
    expected_backend = os.environ["VGAR_GRAPH_BACKEND"].strip().lower()
    client = create_mcp_client()
    tools = await client.get_tools()
    validate_required_tools(tools, W3_W4_REQUIRED_GRAPH_TOOLS)
    by_name = {tool.name: tool for tool in tools}

    search_raw = await by_name["graph_search_symbols"].ainvoke(
        {"query": query, "limit": 10}
    )
    search = parse_mcp_json_result(search_raw)
    print("graph_search_symbols:")
    print(json.dumps(search, indent=2, ensure_ascii=False))

    backend = search.get("metadata", {}).get("backend")
    if backend != expected_backend:
        raise RuntimeError(
            "W3-W4 smoke used the wrong graph backend: "
            f"expected={expected_backend!r}, actual={backend!r}"
        )

    symbols = search.get("symbols", [])
    if not symbols:
        raise RuntimeError(f"W3-W4 smoke failed: no symbol matching {query!r}")

    symbol_id = symbols[0]["symbol_id"]
    callers = parse_mcp_json_result(
        await by_name["graph_get_callers"].ainvoke(
            {"symbol_id": symbol_id, "depth": 1}
        )
    )
    callees = parse_mcp_json_result(
        await by_name["graph_get_callees"].ainvoke(
            {"symbol_id": symbol_id, "depth": 1}
        )
    )

    if callers.get("metadata", {}).get("backend") != expected_backend:
        raise RuntimeError("graph_get_callers did not use the expected backend")
    if callees.get("metadata", {}).get("backend") != expected_backend:
        raise RuntimeError("graph_get_callees did not use the expected backend")

    print("graph_get_callers:")
    print(json.dumps(callers, indent=2, ensure_ascii=False))
    print("graph_get_callees:")
    print(json.dumps(callees, indent=2, ensure_ascii=False))
    print(f"W3-W4 MCP tool smoke PASS (backend={expected_backend})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoke-test W3-W4 graph MCP tools through langchain-mcp-adapters."
    )
    parser.add_argument(
        "--query",
        default=os.getenv("VGAR_W3_W4_QUERY", "login"),
        help="Symbol query expected to exist in the configured graph database.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.query))
