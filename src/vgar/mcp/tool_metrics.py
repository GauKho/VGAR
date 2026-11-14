"""Per-call metrics of MCP tools: tokens in and out, processing time, and the format of arguments and results.

Only what crosses a tool is visible here (proposal §13.2: context token cost, average tool latency, tool calls
per task); the model's own tokens are counted by the host. Tokens are UTF-8 bytes / 4, the same counter as the
retrieval evaluation, so they are tool-side measures, not the model's tokens. Records never hold argument or result content, only
types and sizes. Written as one JSON line per call to ``VGAR_MCP_METRICS_LOG`` (default: next to
``VGAR_MCP_AUDIT_LOG`` as ``<audit name>.metrics.jsonl``; no file when neither is set) and logged at INFO on stderr.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from vgar.graph.token_counter import FALLBACK_COUNTER_LABEL, bytes_div4_counter

logger = logging.getLogger(__name__)
_write_lock = threading.Lock()


def describe(value: Any) -> str:
    """Type and size of a value, never its content.

    Args:
        value: Any argument or result field.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return type(value).__name__
    if isinstance(value, str):
        return f"str {len(value.encode('utf-8'))}B"
    if isinstance(value, (list, tuple)):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    return type(value).__name__


def token_count(text: str) -> tuple[int, str]:
    """Tokens of ``text`` as UTF-8 bytes / 4, the counter of the retrieval evaluation (not the model's tokenizer).

    Args:
        text: Serialized tool arguments or result.

    Returns:
        The count and the label ``FALLBACK:utf8_bytes_ceil_div4``.
    """
    return bytes_div4_counter(text), FALLBACK_COUNTER_LABEL


def _server_of(module: str) -> str:
    if module == "__main__":
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        module = spec.name if spec is not None else module
    name = module.rsplit(".", 1)[-1]
    return name.removesuffix("_server")


def _metrics_path() -> Path | None:
    explicit = os.getenv("VGAR_MCP_METRICS_LOG", "").strip()
    if explicit:
        return Path(explicit)
    audit = os.getenv("VGAR_MCP_AUDIT_LOG", "").strip()
    if audit:
        path = Path(audit)
        return path.with_name(path.stem + ".metrics.jsonl")
    return None


def _shape(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"type": describe(result)}
    data = result.get("data")
    shape: dict[str, Any] = {"status": result.get("status")}
    shape["data"] = {key: describe(value) for key, value in data.items()} if isinstance(data, dict) else describe(data)
    if isinstance(result.get("error"), dict):
        shape["error_code"] = result["error"].get("code")
    return shape


def observe(tool: str, module: str, arguments: dict[str, Any], result: Any, started: float,
            error: BaseException | None = None) -> None:
    """Record one tool call; never raises (metrics must not break a tool).

    Args:
        tool: Tool name.
        module: Module that defines the tool (gives the server name).
        arguments: The call's keyword arguments (positional ones keyed by position).
        result: The tool's return value, or None when it raised.
        started: ``time.perf_counter()`` taken before the call.
        error: The exception the tool raised, if any.
    """
    try:
        duration_ms = round((time.perf_counter() - started) * 1000)
        input_text = json.dumps(arguments, ensure_ascii=False, default=str, sort_keys=True)
        output_text = "" if result is None else json.dumps(result, ensure_ascii=False, default=str)
        input_tokens, method = token_count(input_text)
        output_tokens, _ = token_count(output_text)
        metadata = result.get("metadata") if isinstance(result, dict) else None
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool, "server": _server_of(module),
            "request_id": metadata.get("request_id") if isinstance(metadata, dict) else None,
            "status": "EXCEPTION" if error is not None else (result.get("status") if isinstance(result, dict) else "OK"),
            "duration_ms": duration_ms, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "token_method": method, "input_bytes": len(input_text.encode("utf-8")),
            "output_bytes": len(output_text.encode("utf-8")),
            "args": {key: describe(value) for key, value in arguments.items()}, "result": _shape(result),
        }
        if error is not None:
            record["exception"] = type(error).__name__
        logger.info("metrics tool=%s server=%s status=%s duration_ms=%d input_tokens=%d output_tokens=%d "
                    "token_method=%s args=%s result=%s", tool, record["server"], record["status"], duration_ms,
                    input_tokens, output_tokens, method, json.dumps(record["args"]), json.dumps(record["result"]))
        path = _metrics_path()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with _write_lock, path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - observability must never fail the call
        logger.debug("tool metrics failed for %s", tool, exc_info=True)
