"""Shapes of VGAR tool output sent to agents (spec 2026-11-24)."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_CONTEXT_FORMAT = "vgar.context.agent.v1"
# Hosts cut tool output near 50 KB (OpenCode); the batch-5 simulation kept every fault function under 32 KiB (§4.2).
RESPONSE_LIMIT_BYTES = 32 * 1024


def compact_json(value: Any) -> str:
    """JSON without indentation or spaces, non-ASCII characters kept.

    Args:
        value: JSON-serializable value.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _short_name(node_id: str) -> str:
    # The qualified name ends a code node id; a renamed duplicate adds "@definition:<row>:<col>".
    return node_id.split("@definition:", 1)[0].rsplit(":", 1)[-1]


def _why(entry: str) -> str:
    relation, colon, rest = entry.partition(":")
    source, arrow, target = rest.partition("->")
    if not colon or not arrow:   # TASK_ANCHOR, SOURCE_COMPONENT, TRACE_COMPONENT
        return entry
    return f"{relation} {_short_name(source)} -> {_short_name(target)}"


def _item(item: dict[str, Any]) -> dict[str, Any]:
    return {"node_id": item["node_id"], "path": item["path"],
            "lines": [item["range"]["start_line"], item["range"]["end_line"]],
            "score": round(item["relevance_score"], 3), "distance": item["graph_distance"],
            "why": [_why(entry) for entry in item["graph_rationale"]], "snippet": item["snippet"]}


def agent_context(data: dict[str, Any], limit_bytes: int = RESPONSE_LIMIT_BYTES) -> dict[str, Any]:
    """get_related_context as sent to the agent: compact items, no source_metadata, at most ``limit_bytes`` (§4.2).

    Args:
        data: Service result whose diagnostics the tool already replaced (not modified).
        limit_bytes: Limit on the compact JSON of the result; the lowest-ranked items are dropped first, the top one never.
    """
    items = data["context"]["items"]
    shaped = [_item(item) for item in items]
    out = {key: value for key, value in data.items() if key != "source_metadata"}
    out["context_format"] = AGENT_CONTEXT_FORMAT
    out["context"] = {**data["context"], "items": shaped}
    out["diagnostics"] = dict(out["diagnostics"])
    keep = len(shaped)
    # Measured with response_limit included, so the diagnostics never push the result over the limit.
    while keep > 1 and len(compact_json(out).encode("utf-8")) > limit_bytes:
        keep -= 1
        dropped = len(shaped) - keep
        out["context"] = {**data["context"], "items": shaped[:keep], "truncated": True,
                          "total_token_count": sum(item["token_count"] for item in items[:keep])}
        out["diagnostics"]["response_limit"] = {
            "limit_bytes": limit_bytes, "dropped_items": dropped, "over_limit": False,
            "hint": f"the response is kept under 32 KiB, so the {dropped} lowest-ranked items were dropped; "
                    "call again with fewer anchor_ids, or read the files, if you need them"}
    if shaped and len(compact_json(out).encode("utf-8")) > limit_bytes:   # the top item alone is too large
        out["diagnostics"]["response_limit"] = {
            "limit_bytes": limit_bytes, "dropped_items": len(shaped) - keep, "over_limit": True,
            "hint": "the top-ranked item alone is larger than 32 KiB; it is returned whole"}
    return out


def verify_view(result: dict[str, Any], details: bool) -> dict[str, Any]:
    """What verify_patch_graph_constraints sends: a summary by default, the full result with ``details`` (§4.3).

    Args:
        result: verify_patch result with ``checked_diff`` (never modified: it may be cached).
        details: True returns every check's details and the checked diff.
    """
    checks = result.get("checks") or {}
    api = checks.get("api", {}).get("details")
    unsupported = []
    for item in api.get("diagnostics", []) if isinstance(api, dict) else []:
        entry = {"symbol": item.get("symbol"), "path": item["path"], "reason": item["reason"]}
        if entry not in unsupported:   # one entry per symbol, not one per baseline/candidate side
            unsupported.append(entry)
    summary = _verify_sentence(result, checks, unsupported)
    if details:
        return {**result, "summary": summary}
    counts: dict[str, int] = {}
    for check in checks.values():
        if isinstance(check.get("details"), dict):
            for item in check["details"].get("diagnostics", []):
                counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return {"status": result["status"], "reasons": result["reasons"], "graph_version": result["graph_version"],
            "diff_sha256": result["diff_sha256"], "summary": summary,
            "checks": {name: {"status": check.get("status"), "reasons": list(check.get("reasons", ()))}
                       for name, check in checks.items()},
            "unsupported_changes": unsupported, "diagnostic_counts": counts,
            "checked_diff": {key: value for key, value in result["checked_diff"].items() if key != "diff"}}


def _verify_sentence(result: dict[str, Any], checks: dict[str, Any], unsupported: list[dict[str, Any]]) -> str:
    checked = result["checked_diff"]
    if result["status"] == "PASS":
        passed = ", ".join(name for name, check in checks.items() if check.get("status") == "PASS")
        sentence = f"Change verified: {passed} PASS on {', '.join(checked['files'])}"
    else:
        parts = []
        for name, check in checks.items():
            status, reasons = check.get("status"), list(check.get("reasons", ()))
            if status not in ("FAIL", "ERROR") and not (status == "NOT_RUN" and reasons):
                continue
            labels = reasons
            if name == "api" and unsupported:
                labels = [f"{u['reason']}: {u['symbol']} in {u['path']}" if u["symbol"] else f"{u['reason']} in {u['path']}"
                          for u in unsupported]
            parts.append(f"{name} {status}" + (f" ({', '.join(labels)})" if labels else ""))
        sentence = "Change NOT verified: " + ("; ".join(parts) or ", ".join(
            reason for reason in result["reasons"] if not reason.startswith("NOT_CHECKED: ")))
    if checked["not_checked"]:
        sentence += f"; not checked: {', '.join(checked['not_checked'])}"
    return sentence
