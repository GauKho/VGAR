"""Run an MCP tool/resource body with the shared envelope and audit trail."""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.context import current_context
from vgar.mcp.proposal.locking import no_links
from vgar.mcp.proposal.security import scrub_secrets
from vgar.mcp.schemas import (
    INTERNAL_ERROR,
    PATH_OUTSIDE_ROOT,
    ROOT_NOT_LEASED,
    CodedToolError,
    ToolMetadata,
    ToolResponse,
    error_from_exception,
)

logger = logging.getLogger(__name__)

# Server-set limits (security design §4.4); no tool accepts these as arguments.
READ_FILE_MAX_BYTES = 64 * 1024
PYTEST_TIMEOUT_SECONDS = 120
PYTEST_OUTPUT_CAP = 12_000
_ASYNC_STARTED = ContextVar("mcp_async_started", default=None)


def leased_root(env_name: str) -> Path:
    """The root the host leased to this server through ``env_name``; never chosen by the model."""
    value = os.environ.get(env_name)
    try:
        root = no_links(Path(value)).resolve() if value else None
    except ValueError:
        raise CodedToolError(PATH_OUTSIDE_ROOT, "Lease root is a linked/reparse path") from None
    if root is None or not root.is_dir():
        raise CodedToolError(ROOT_NOT_LEASED, f"No leased root: {env_name} is not set to a directory")
    return root


def inside(root: Path, candidate: Path) -> Path:
    """``candidate`` resolved (symlinks, ``..``) and guaranteed to stay under ``root``."""
    try:
        no_links(root)
        target = no_links(Path(candidate)).resolve()
    except ValueError:
        raise CodedToolError(PATH_OUTSIDE_ROOT, "Path is linked or leaves the lease") from None
    if target != root and root not in target.parents:
        raise CodedToolError(PATH_OUTSIDE_ROOT, "Path is outside the leased root")
    return target


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _error_audit_fields(exc: BaseException, code: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"error_code": code}
    if code == INTERNAL_ERROR:  # keep the real message out of the response only
        fields["error_message"] = f"{type(exc).__name__}: {exc}"
    else:  # the redacted message the caller already got (X2b 03/11: INVALID_ARGUMENT left no reason)
        fields["error_message"] = error_from_exception(exc).message[:240]
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
    untrusted: bool = False,
) -> dict[str, Any]:
    """Execute `call`, always return a ToolResponse dict, always write one audit line.

    `audit_fields` are the call arguments to log; `summarize(data)` adds result
    counts on success. Errors are logged too, with their error_code.
    """
    context = current_context()
    request_id = context.request_id if context else uuid.uuid4().hex
    started = _ASYNC_STARTED.get() or time.perf_counter()
    # audit_fields are already safe to log (hashes, sizes, names; never diff content or secrets).
    logger.debug("tool=%s server=%s request_id=%s args=%s", tool, server, request_id, audit_fields or {})
    data: dict[str, Any] | None = None
    error = None
    interrupted = None
    extra: dict[str, Any] = {}
    try:
        data = call()
        extra = summarize(data) if summarize else {}
    except Exception as exc:  # noqa: BLE001 - boundary: nothing may escape raw
        error = error_from_exception(exc)
        extra = _error_audit_fields(exc, error.code)
        if error.code == INTERNAL_ERROR:
            logger.exception("tool=%s server=%s request_id=%s raised unexpectedly", tool, server, request_id)
    except BaseException as exc:  # noqa: BLE001 - cancellation is audited then re-raised unchanged
        interrupted = exc
        error = error_from_exception(RuntimeError("Request interrupted"))
        extra = {"error_code": INTERNAL_ERROR, "interrupted": True}

    duration_ms = _elapsed_ms(started)
    status = "ERROR" if error else "PASS"
    fields = {
            "server": server,
            "backend": backend,
            "tool": tool,
            "request_id": request_id,
            "status": status,
            "duration_ms": duration_ms,
            **(audit_fields or {}),
            **extra,
        }
    try:
        audit.write("tool_call", fields)
    except (OSError,ValueError,TypeError):
        # An operation may already have happened, but missing evidence can never be PASS.
        error = error_from_exception(RuntimeError("Audit persistence failed"))
        data = None
        status = "ERROR"
    logger.info("tool=%s server=%s status=%s duration_ms=%d request_id=%s%s", tool, server, status, duration_ms,
                request_id, f" error_code={extra['error_code']}" if "error_code" in extra else "")
    if interrupted is not None:
        raise interrupted
    response = ToolResponse(
        status=status,
        data=data,
        error=error,
        metadata=ToolMetadata(
            duration_ms=duration_ms,
            request_id=request_id,
            backend=backend,
            tool=tool,
            **({"untrusted": True} if untrusted else {}),
        ),
    )
    if context:
        value=response.model_dump(mode="json")
        value["metadata"].update(run_id=context.run_id,task_id=context.task_id,snapshot_hash=context.snapshot_hash)
        return scrub_secrets(value,context.secrets)
    return response.model_dump(mode="json")


async def run_tool_async(*, call, **kwargs):
    """Same terminal envelope/audit for async handlers, including SDK cancellation."""
    token=_ASYNC_STARTED.set(time.perf_counter())
    try:
        try:
            data=await call()
        except BaseException as error:  # noqa: BLE001 - async boundary; cancellation re-raised by run_tool
            def failed(exc=error):
                raise exc
            return run_tool(call=failed,**kwargs)
        return run_tool(call=lambda:data,**kwargs)
    finally:
        _ASYNC_STARTED.reset(token)


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
    except BaseException as exc:
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
