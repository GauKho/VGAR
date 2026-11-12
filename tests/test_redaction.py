"""D6 / B12 (M3-W11, day 3): one shared redactor; secrets never reach audit, logs or tool errors (S6);
MCP child processes get an allow-listed environment (S7)."""
from __future__ import annotations

import json

import pytest

from vgar.mcp.audit import AuditLogger
from vgar.mcp.tooling import run_tool
from vgar.observability.redact import redact, redact_text

HF = "hf_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
SECRETS = [f"Authorization: Bearer {HF}", f"api_key={HF}", f"password: hunter2-{HF[:8]}", HF,
           "sk-" + "x" * 40, "ghp_" + "y" * 36]


@pytest.mark.parametrize("text", SECRETS)
def test_redact_text_removes_every_secret_shape(text):
    out = redact_text(f"before {text} after")
    assert "before" in out and "after" in out and "[REDACTED]" in out
    for fragment in (HF, "x" * 40, "y" * 36, "hunter2"):
        assert fragment not in out


def test_redact_walks_nested_values():
    value = {"note": f"token={HF}", "items": [f"Bearer {HF}", 3], "plain": "ok"}
    assert HF not in json.dumps(redact(value)) and redact(value)["plain"] == "ok"


def test_instrumentation_summary_uses_the_shared_redactor():
    # B12: the old regex was written as a raw string with doubled backslashes and never matched.
    from vgar.observability.instrumentation import summarize
    assert HF not in json.dumps(summarize({"detail": f"Authorization: Bearer {HF}"}))


def test_secret_never_reaches_audit_or_tool_error(tmp_path):
    # S6
    audit = tmp_path / "audit.jsonl"

    def leak():
        raise ValueError(f"could not open with api_key={HF}")

    response = run_tool(server="t", tool="x", backend="b", audit=AuditLogger(audit), call=leak,
                        audit_fields={"query": f"Bearer {HF}"})

    assert response["status"] == "ERROR"
    assert HF not in json.dumps(response)
    assert HF not in audit.read_text(encoding="utf-8")


@pytest.mark.parametrize("key", ["input_tokens", "output_tokens", "feedback_tokens", "total_token_count",
                                 "token_budget", "token_budget_unit", "tokenizer_label"])
def test_token_counts_are_not_redacted(key):
    # 03/11: the secret-key regex matched "token" and hid token counts in every MCP trace line.
    from vgar.observability.instrumentation import summarize
    assert summarize({key: 4886})[key] == 4886


@pytest.mark.parametrize("key", ["token", "access_token", "api_key", "authorization", "password", "HF_TOKEN"])
def test_secret_keys_stay_redacted(key):
    from vgar.observability.instrumentation import summarize
    assert summarize({key: "abc"})[key] == "[REDACTED]"
