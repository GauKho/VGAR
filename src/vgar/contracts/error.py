from __future__ import annotations

from typing import Any


class GraphError(Exception):
    """Base error with a stable machine-readable code for the MCP boundary."""

    code = "GRAPH_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class InvalidQueryError(GraphError, ValueError):
    code = "INVALID_QUERY"


class InvalidLimitError(GraphError, ValueError):
    code = "INVALID_LIMIT"


class NodeNotFoundError(GraphError, KeyError):
    code = "NODE_NOT_FOUND"

    def __init__(self, node_id: str, *, entity: str = "node") -> None:
        super().__init__(
            f"Unknown {entity}: {node_id}",
            details={"entity": entity, "node_id": node_id},
        )


class GraphNotReadyError(GraphError, LookupError):
    code = "GRAPH_NOT_READY"

    def __init__(self, graph_version: str) -> None:
        super().__init__(
            f"Graph version is not ready: {graph_version}",
            details={"graph_version": graph_version},
        )
