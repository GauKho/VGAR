"""Retry feedback for the next V11 prompt, built by the host from a failed run record (never agent text)."""
from __future__ import annotations

from typing import Any


def _parse_message(detail: dict[str, Any]) -> str:
    lines = [detail.get("message") or "Patch could not be parsed."]
    diagnostics = detail.get("parser_diagnostics") or {}
    for entry in diagnostics.get("invalid_body_lines") or []:
        lines.append(f"Line {entry['raw_line']} '{entry['text']}' has no '-', '+' or ' ' prefix.")
    expected, actual = diagnostics.get("expected_counts"), diagnostics.get("actual_counts")
    if expected and actual and expected != actual:
        lines.append(f"Hunk header {diagnostics.get('hunk_header')} declares old={expected['old']} "
                     f"new={expected['new']} but the body has old={actual['old']} new={actual['new']}.")
    return "\n".join(lines)


def _test_message(verification: dict[str, Any]) -> str | None:
    outcomes = (verification.get("tests") or {}).get("outcomes") or {}
    failing = [name for name, outcome in outcomes.items() if outcome != "PASS"]
    if not failing:
        return None
    message = f"Tests still failing after the patch: {', '.join(failing)}."
    if verification.get("reasons"):
        message += f"\nVerification reasons: {', '.join(verification['reasons'])}."
    return message


def build_feedback(record: dict[str, Any]) -> dict[str, str]:
    """Four-key feedback dict for start_session(feedback=...); build_repair_prompt bounds its length."""
    status, reason = record["status"], record.get("reason")
    if record.get("error_detail"):
        message = _parse_message(record["error_detail"])
    else:
        verification = (record.get("stages") or {}).get("verification") or {}
        message = _test_message(verification) or f"Previous attempt ended with {status} {reason}."
    return {"task_id": record["task_id"], "source_run_id": record["run_id"],
            "category": reason or status, "message": message}
