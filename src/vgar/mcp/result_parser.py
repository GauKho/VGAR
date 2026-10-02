from __future__ import annotations

import json
from typing import Any


def parse_mcp_json_result(result: Any) -> dict[str, Any]:
    """Normalize a direct LangChain MCP tool invocation into one JSON object.

    `langchain-mcp-adapters` can expose a FastMCP structured response either as
    a dict, a JSON string, or a list of MCP text content blocks.  This helper is
    intentionally transport-only: it does not change M1's graph JSON schema.
    """

    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        decoded = json.loads(result)
        if not isinstance(decoded, dict):
            raise TypeError("Expected MCP JSON object")
        return decoded

    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)

            if not isinstance(text, str):
                continue

            decoded = json.loads(text)
            if not isinstance(decoded, dict):
                raise TypeError(
                    "Expected MCP text content to contain a JSON object"
                )
            return decoded

    raise TypeError(
        f"Unsupported MCP result type: {type(result).__name__}: {result!r}"
    )
