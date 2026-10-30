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


IMPACT_ITEMS, IMPACT_CHARS = 5, 400


def impact_message(impact: Any) -> str | None:
    """One bounded line from an ImpactReport; static graph evidence, never a test result."""
    from vgar.contracts.impact import ImpactReport
    report = impact if isinstance(impact, ImpactReport) else ImpactReport.model_validate(impact)
    if report.impacted.status == "NOT_COMPUTED":
        return None
    spans = sorted({f"{n.path}:{n.source_range.start_line}-{n.source_range.end_line}" for n in report.changed})
    changed = ", ".join(spans[:3]) + (f", +{len(spans) - 3} more" if len(spans) > 3 else "") or "no mapped symbol"
    items = sorted(report.impacted.items, key=lambda i: (i.hops, i.kind != "Test", i.qualified_name))
    tests = sum(item.kind == "Test" for item in items)
    partial = " (partial)" if report.impacted.status == "PARTIAL" else ""
    line = (f"Static graph impact of the previous patch{partial}: changed {changed}; "
            f"{len(items)} dependent node(s), {tests} test(s)")
    if items:
        shown = [f"{item.qualified_name} ({item.relation.lower()})" for item in items[:IMPACT_ITEMS]]
        extra = len(items) - IMPACT_ITEMS
        line += ": " + ", ".join(shown) + (f", +{extra} more" if extra > 0 else "")
    return line[:IMPACT_CHARS]


def build_feedback(record: dict[str, Any], impact: Any = None) -> dict[str, str]:
    """Four-key feedback dict for start_session(feedback=...); build_repair_prompt bounds its length.

    `impact` (ImpactReport or its JSON object) adds one bounded line after the failure text, so the
    prompt's budget truncation drops it before the failure itself.
    """
    status, reason = record["status"], record.get("reason")
    if record.get("error_detail"):
        message = _parse_message(record["error_detail"])
    else:
        verification = (record.get("stages") or {}).get("verification") or {}
        message = _test_message(verification) or f"Previous attempt ended with {status} {reason}."
    impact_line = impact_message(impact) if impact is not None else None
    if impact_line:
        message += "\n" + impact_line
    return {"task_id": record["task_id"], "source_run_id": record["run_id"],
            "category": reason or status, "message": message}
