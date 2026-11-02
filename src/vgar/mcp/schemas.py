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

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vgar.contracts.error import GraphError
from vgar.observability.redact import redact, redact_text

ToolStatus = Literal["PASS", "FAIL", "ERROR", "NOT_RUN"]

INVALID_ARGUMENT = "INVALID_ARGUMENT"
INTERNAL_ERROR = "INTERNAL_ERROR"
# C4 security codes (docs/m3_w11_decisions.md); none of them is retryable with unchanged arguments.
ROOT_NOT_LEASED = "ROOT_NOT_LEASED"
PATH_OUTSIDE_ROOT = "PATH_OUTSIDE_ROOT"
SELECTOR_REJECTED = "SELECTOR_REJECTED"
TIMEOUT = "TIMEOUT"
# C4 repair codes: a call in the wrong run phase, or a run_dir that is not a repair run.
TOOL_ORDER_VIOLATION = "TOOL_ORDER_VIOLATION"
RUN_NOT_FOUND = "RUN_NOT_FOUND"

# S10: every error code a tool may return -> retryable (the same call, unchanged, may succeed).
# Table from C4 in docs/m3_w11_decisions.md; TOOL_ERROR (legacy repair) is deliberately absent.
KNOWN_ERROR_CODES: Mapping[str, bool] = MappingProxyType({
    INVALID_ARGUMENT: False, INTERNAL_ERROR: False,
    "INVALID_QUERY": False, "INVALID_LIMIT": False, "NODE_NOT_FOUND": False, "GRAPH_ERROR": False,
    "GRAPH_NOT_READY": True,
    PATH_OUTSIDE_ROOT: False, ROOT_NOT_LEASED: False, SELECTOR_REJECTED: False, TIMEOUT: False,
    TOOL_ORDER_VIOLATION: False, RUN_NOT_FOUND: False, "MCP_TRANSPORT_ERROR": False,
})


class CodedToolError(Exception):
    """A tool failure with a stable C4 code; the message is safe to show to the model."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False

    @model_validator(mode="after")
    def _retryable_from_code(self) -> "ToolError":
        self.retryable = KNOWN_ERROR_CODES.get(self.code, False)
        return self


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
    if isinstance(exc, (CodedToolError, GraphError)) and exc.code not in KNOWN_ERROR_CODES:
        return ToolError(code=INTERNAL_ERROR, message=f"Unexpected server error: {type(exc).__name__}")
    if isinstance(exc, CodedToolError):
        return ToolError(code=exc.code, message=redact_text(exc.message))
    if isinstance(exc, GraphError):  # must precede ValueError: some are both
        return ToolError(code=exc.code, message=redact_text(exc.message), details=redact(exc.details))
    if isinstance(exc, ValueError):
        return ToolError(code=INVALID_ARGUMENT, message=redact_text(str(exc)))
    return ToolError(
        code=INTERNAL_ERROR,
        message=f"Unexpected server error: {type(exc).__name__}",
    )
