"""Low-overhead JSONL instrumentation for VGAR workflow nodes and MCP tools.

Logs go to stderr (safe for MCP stdio transport). Payloads are summarized and
bounded; source text, patch text, prompts and command output are never emitted.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
import os
import re
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Mapping
from typing import Any, Callable

_SECRET_KEY = re.compile(r"(secret|password|token|api[_-]?key|authorization|credential)", re.I)
_PRIVATE_TEXT_KEY = re.compile(
    r"(content|old_text|new_text|prompt|messages|stdout|stderr|output_tail|diff|patch|issue_text)",
    re.I,
)
_MAX_DEPTH = 4
_MAX_ITEMS = 24
_MAX_STRING = 240
_BEARER_RE = re.compile(r"(?i)\\bBearer\\s+[A-Za-z0-9._~+/=-]+")
_KEY_VALUE_RE = re.compile(r"(?i)(api[_-]?key|access[_-]?token|password|secret)\\s*[:=]\\s*[^\\s,;]+")
_CURRENT_RUN_ID: ContextVar[str | None] = ContextVar("vgar_trace_run_id", default=None)


def current_run_id() -> str | None:
    return _CURRENT_RUN_ID.get() or os.getenv("VGAR_TRACE_RUN_ID")


@contextmanager
def trace_run(run_id: str):
    token = _CURRENT_RUN_ID.set(run_id)
    try:
        yield
    finally:
        _CURRENT_RUN_ID.reset(token)


def _redact_text(value: str) -> str:
    value = _BEARER_RE.sub("Bearer [REDACTED]", value)
    return _KEY_VALUE_RE.sub(r"\\1=[REDACTED]", value)


def _text_summary(value: str) -> dict[str, Any]:
    raw = value.encode("utf-8", errors="replace")
    return {"type": "str", "length": len(value), "sha256_12": hashlib.sha256(raw).hexdigest()[:12]}


def summarize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Summarize contracts without dumping source, prompts, patch text, or secrets."""
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        value = _redact_text(value)
        if _PRIVATE_TEXT_KEY.search(key):
            return _text_summary(value)
        if len(value) > _MAX_STRING:
            return {"type": "str", "length": len(value), "preview": value[:_MAX_STRING] + "…"}
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= _MAX_DEPTH:
        return {"type": type(value).__name__}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= _MAX_ITEMS:
                result["_truncated_keys"] = len(value) - _MAX_ITEMS
                break
            name = str(k)
            if name in {"agent_messages"} or name == "messages":
                result[name] = {"type": type(v).__name__, "count": len(v) if hasattr(v, "__len__") else None}
            else:
                result[name] = summarize(v, key=name, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return {
            "type": type(value).__name__,
            "count": len(items),
            "items": [summarize(item, depth=depth + 1) for item in items[:_MAX_ITEMS]],
            **({"truncated_items": len(items) - _MAX_ITEMS} if len(items) > _MAX_ITEMS else {}),
        }
    if hasattr(value, "model_dump"):
        try:
            return summarize(value.model_dump(mode="json"), key=key, depth=depth + 1)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {"type": type(value).__name__}
    return {"type": type(value).__name__}


def emit(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
        "event": event,
        "run_id": current_run_id(),
        **{k: summarize(v, key=k) for k, v in fields.items()},
    }
    try:
        print("[VGAR_TRACE] " + json.dumps(payload, ensure_ascii=False, default=str), file=sys.stderr, flush=True)
    except Exception:
        # Observability must never change task behavior.
        pass


def _state_summary(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if args and isinstance(args[0], Mapping):
        return summarize(args[0])
    # Positional strings have no parameter names, so hash them rather than risk
    # accidentally logging old_text/new_text, source contents, or credentials.
    safe_args = [
        _text_summary(_redact_text(value)) if isinstance(value, str) else summarize(value)
        for value in args
    ]
    return {"args": safe_args, "kwargs": summarize(kwargs)}


def instrument_node(name: str) -> Callable:
    """Decorate a real workflow node, recording its actual input/output contract."""
    def decorate(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                emit("NODE_START", node=name, input=_state_summary(args, kwargs))
                try:
                    output = await fn(*args, **kwargs)
                except Exception as exc:
                    emit("NODE_ERROR", node=name, duration_ms=round((time.perf_counter()-started)*1000),
                         exception=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()[-4000:])
                    raise
                emit("NODE_OUTPUT", node=name, output=output)
                emit("NODE_END", node=name, duration_ms=round((time.perf_counter()-started)*1000), status="OK")
                return output
            return async_wrapper
        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            emit("NODE_START", node=name, input=_state_summary(args, kwargs))
            try:
                output = fn(*args, **kwargs)
            except Exception as exc:
                emit("NODE_ERROR", node=name, duration_ms=round((time.perf_counter()-started)*1000),
                     exception=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()[-4000:])
                raise
            emit("NODE_OUTPUT", node=name, output=output)
            emit("NODE_END", node=name, duration_ms=round((time.perf_counter()-started)*1000), status="OK")
            return output
        return sync_wrapper
    return decorate


def instrument_mcp_tool(name: str) -> Callable:
    """Decorate MCP tool implementations without changing their return values."""
    def decorate(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                emit("MCP_TOOL_START", tool=name, input=_state_summary(args, kwargs))
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    emit("MCP_TOOL_ERROR", tool=name, duration_ms=round((time.perf_counter()-started)*1000),
                         exception=type(exc).__name__, message=str(exc))
                    raise
                emit("MCP_TOOL_OUTPUT", tool=name, output=result)
                emit("MCP_TOOL_END", tool=name, duration_ms=round((time.perf_counter()-started)*1000), status="OK")
                return result
            return async_wrapper
        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            emit("MCP_TOOL_START", tool=name, input=_state_summary(args, kwargs))
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                emit("MCP_TOOL_ERROR", tool=name, duration_ms=round((time.perf_counter()-started)*1000),
                     exception=type(exc).__name__, message=str(exc))
                raise
            emit("MCP_TOOL_OUTPUT", tool=name, output=result)
            emit("MCP_TOOL_END", tool=name, duration_ms=round((time.perf_counter()-started)*1000), status="OK")
            return result
        return sync_wrapper
    return decorate

