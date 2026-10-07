"""Run an MCP tool/resource body with the shared envelope and audit trail."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import (
    INTERNAL_ERROR,
    ToolMetadata,
    ToolResponse,
    ToolError,
    error_from_exception,
)


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _error_audit_fields(exc: BaseException, code: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"error_code": code}
    if code == INTERNAL_ERROR:  # keep the real message out of the response only
        fields["error_message"] = f"{type(exc).__name__}: {exc}"
    return fields


def run_tool(
    *,
    server: str,
    tool: str,
    backend: str,
    audit: AuditLogger,
    call: Callable[[], dict[str, Any]],
    audit_fields: dict[str, Any] | None = None,
    summarize: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    verification: bool = False,
    metadata_fields: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute `call`, always return a ToolResponse dict, always write one audit line.

    `audit_fields` are the call arguments to log; `summarize(data)` adds result
    counts on success. Errors are logged too, with their error_code.
    """
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    data: dict[str, Any] | None = None
    error = None
    status = "PASS"
    response_metadata = {}
    try:
        data = call()
        response_metadata = metadata_fields() if metadata_fields else {}
        extra = summarize(data) if summarize else {}
        if verification:
            status = data.get("status")
            if status not in {"PASS", "FAIL", "ERROR", "NOT_RUN"}:
                raise ValueError("Verification tool returned an invalid status")
            reason = data.get("reason")
            if status in {"FAIL", "ERROR"} and reason:
                error = ToolError(code=reason["code"], message=reason["message"], details={})
                extra["error_code"] = error.code
            if status == "ERROR":
                if error is None:
                    raise ValueError("Verification ERROR requires a reason")
                error.details = data
                data = None
    except Exception as exc:  # noqa: BLE001 - boundary: nothing may escape raw
        data = None
        status = "ERROR"
        error = error_from_exception(exc)
        response_metadata = {}
        extra = _error_audit_fields(exc, error.code)

    duration_ms = _elapsed_ms(started)
    audit.write(
        "tool_call",
        {
            "server": server,
            "backend": backend,
            "tool": tool,
            "request_id": request_id,
            "status": status,
            "duration_ms": duration_ms,
            **(audit_fields or {}),
            **extra,
        },
    )
    response = ToolResponse(
        status=status,
        data=data,
        error=error,
        metadata=ToolMetadata(
            duration_ms=duration_ms,
            request_id=request_id,
            backend=backend,
            tool=tool,
            **response_metadata,
        ),
    )
    return response.model_dump(mode="json")


@contextmanager
def audit_resource(
    *,
    server: str,
    resource: str,
    backend: str,
    audit: AuditLogger,
    fields: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Audit a resource read (timing + status). Errors are logged then re-raised.

    Resources return raw documents, not the tool envelope, so failures stay
    protocol-level errors; the yielded dict lets the caller add result counts.
    """
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    result_fields: dict[str, Any] = {}
    try:
        yield result_fields
    except Exception as exc:
        audit.write(
            "resource_read",
            {
                "server": server,
                "backend": backend,
                "resource": resource,
                "request_id": request_id,
                "status": "ERROR",
                "duration_ms": _elapsed_ms(started),
                **(fields or {}),
                **_error_audit_fields(exc, error_from_exception(exc).code),
            },
        )
        raise
    audit.write(
        "resource_read",
        {
            "server": server,
            "backend": backend,
            "resource": resource,
            "request_id": request_id,
            "status": "PASS",
            "duration_ms": _elapsed_ms(started),
            **(fields or {}),
            **result_fields,
        },
    )
