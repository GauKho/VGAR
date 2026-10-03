"""Single response envelope for every VGAR MCP tool.

    {"status": "PASS" | "FAIL" | "ERROR" | "NOT_RUN",
     "data":   {...} | null,
     "error":  {"code": str, "message": str, "details": {...}} | null,
     "metadata": {"duration_ms": int, "request_id": str, ...}}

Rules:
- status PASS  -> data is set,  error is null.
- status ERROR -> data is null, error is set (the tool could not answer).
- FAIL / NOT_RUN are reserved for verification-style tools (M2); graph query
  tools only ever return PASS or ERROR.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vgar.contracts.error import GraphError

ToolStatus = Literal["PASS", "FAIL", "ERROR", "NOT_RUN"]

INVALID_ARGUMENT = "INVALID_ARGUMENT"
INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolMetadata(BaseModel):
    # Extra keys (backend, tool, ...) are allowed; these two are mandatory.
    model_config = ConfigDict(extra="allow")

    duration_ms: int = Field(ge=0)
    request_id: str = Field(min_length=1)


class ToolResponse(BaseModel):
    status: ToolStatus
    data: dict[str, Any] | None = None
    error: ToolError | None = None
    metadata: ToolMetadata


def error_from_exception(exc: BaseException) -> ToolError:
    """Map an exception to a stable, machine-readable error.

    GraphError subclasses keep their own code (NODE_NOT_FOUND, INVALID_QUERY...).
    Plain ValueError from argument validation becomes INVALID_ARGUMENT.
    Anything else is INTERNAL_ERROR with only the exception type exposed; the
    full message goes to the audit log, not to the model.
    """
    if isinstance(exc, GraphError):  # must precede ValueError: some are both
        return ToolError(code=exc.code, message=exc.message, details=exc.details)
    if isinstance(exc, ValueError):
        return ToolError(code=INVALID_ARGUMENT, message=str(exc))
    return ToolError(
        code=INTERNAL_ERROR,
        message=f"Unexpected server error: {type(exc).__name__}",
    )
