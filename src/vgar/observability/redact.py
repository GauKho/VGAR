"""Shared secret redactor (D6/S6): one place that knows what a secret looks like.

Used by instrumentation, phase logs, the MCP audit log and tool error messages.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Token shapes recognised on their own, wherever they appear.
_TOKEN_RES = (
    re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+"
)


def redact_text(text: str) -> str:
    for pattern in _TOKEN_RES:
        text = pattern.sub(REDACTED, text)
    text = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    return _KEY_VALUE_RE.sub(rf"\1={REDACTED}", text)


def redact(value: Any) -> Any:
    """Return a copy of `value` with every string inside it redacted."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    return value
