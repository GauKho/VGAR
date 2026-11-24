"""Replay the get_related_context calls of OpenCode session A (big-pickle) on ShopFlow and check batch 5 (spec 2026-11-24 §5.2).

Builds the graph of ShopFlow at ``ee54b36`` in a temporary folder, replays every recorded ``find_task_anchors`` and
``get_related_context`` call in order through the real MCP tools, then verifies the bug-5 diff (ALLOWED_TRANSITIONS).
Passes when every response is at most 32 KiB, every fault function is still in the context, and verify answers NOT_RUN
naming ALLOWED_TRANSITIONS.

    python scripts/mcp_server/replay_shopflow_session.py --source <ShopFlow repo root at ee54b36> \
        --session D:/kltn/vgar-work/opencode-logs/ses_df7276b72ffetYKJMAPODVXxnI.json --out report.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

LIMIT = 32 * 1024
# Number of the get_related_context call (1..13 in session order) -> fault functions it must still contain.
EXPECTED_FAULTS = {9: ("Order.__init__",), 10: ("coupon_rate", "OrderService.place_order"), 11: ("quote_order",),
                   12: ("Notifier.order_shipped", "InventoryService.commit"), 13: ("Order.can_transition",)}
SAVED = re.compile(r"full output saved to (\S+?tool_[A-Za-z0-9]+)")


def recorded_calls(session: Path) -> tuple[list[tuple[str, dict]], str]:
    """The (tool, input) of every recorded anchor/context call, in order, and the bug-5 diff."""
    calls, bug5 = [], None
    for message in json.loads(session.read_text(encoding="utf-8"))["messages"]:
        for part in message.get("content") or []:
            if part.get("type") != "tool" or not part["name"].startswith("vgar-graph_"):
                continue
            tool = part["name"].removeprefix("vgar-graph_")
            if tool in ("find_task_anchors", "get_related_context"):
                calls.append((tool, dict(part["state"]["input"])))
            elif tool == "verify_patch_graph_constraints" and bug5 is None:
                text = "".join(p.get("text", "") for p in part["state"].get("content", []) if isinstance(p, dict))
                saved = SAVED.search(text)
                if saved and Path(saved.group(1)).exists():
                    text = Path(saved.group(1)).read_text(encoding="utf-8")
                data = (json.loads(text) if text.startswith("{") else {}).get("data") or {}
                if "API_UNSUPPORTED_DECLARATION" in data.get("reasons", []) and "ALLOWED_TRANSITIONS" in text:
                    bug5 = data["checked_diff"]["diff"]
    if bug5 is None:
        raise SystemExit("no recorded verify output for bug 5 (ALLOWED_TRANSITIONS) in the session")
    return calls, bug5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="ShopFlow repository root at ee54b36")
    parser.add_argument("--session", type=Path, required=True, help="OpenCode session export (JSON)")
    parser.add_argument("--out", type=Path, help="also write the report here")
    args = parser.parse_args()
    calls, bug5 = recorded_calls(args.session)
    folder = Path(tempfile.mkdtemp(prefix="vgar-replay-"))
    root = folder / "shopflow"   # the folder name is the repo_key: node ids in the log start with vgar:shopflow:
    shutil.copytree(args.source, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"))
    os.environ.update(VGAR_GRAPH_BACKEND="sqlite", VGAR_REPOSITORY_ROOT=str(root),
                      VGAR_GRAPH_DATABASE=str(folder / "graph.db"), VGAR_MCP_AUDIT_LOG=str(folder / "audit.jsonl"))
    os.environ.pop("VGAR_GRAPH_VERSION", None)

    import anyio
    from vgar.mcp.agent_output import compact_json
    from vgar.mcp.servers import graph_server   # imported after the environment: it reads it at import

    def call(tool: str, arguments: dict) -> tuple[dict, int]:
        result = anyio.run(graph_server.mcp.call_tool, tool, arguments)
        return result.structured_content, len(result.content[0].text.encode("utf-8"))

    built, _ = call("build_or_update_graph", {"repo_path": str(root)})
    version = built["data"]["graph_version"]
    recorded = next(arguments["graph_version"] for tool, arguments in calls if "graph_version" in arguments)
    lines = [f"Graph version rebuilt {version}, recorded {recorded} ({'same' if version == recorded else 'DIFFERENT'} code)", "",
             "| # | status | data bytes | text bytes | items | dropped | faults missing |", "|---|---|---|---|---|---|---|"]
    ok, number = True, 0
    for tool, arguments in calls:
        arguments = {**arguments, "graph_version": version}
        envelope, text_bytes = call(tool, arguments)
        if tool != "get_related_context":
            continue
        number += 1
        data = envelope.get("data") or {}
        items = (data.get("context") or {}).get("items", [])
        size = len(compact_json(data).encode("utf-8"))
        missing = [name for name in EXPECTED_FAULTS.get(number, ())
                   if not any(item["node_id"].endswith("." + name) for item in items)]
        dropped = ((data.get("diagnostics") or {}).get("response_limit") or {}).get("dropped_items", 0)
        ok &= not missing and (envelope["status"] != "PASS" or size <= LIMIT)
        lines.append(f"| {number} | {envelope['status']} | {size} | {text_bytes} | {len(items)} | {dropped} | "
                     f"{', '.join(missing) or '-'} |")
    verify, _ = call("verify_patch_graph_constraints", {"diff": bug5})
    symbols = [entry["symbol"] for entry in (verify.get("data") or {}).get("unsupported_changes", [])]
    ok &= verify["status"] == "NOT_RUN" and "ALLOWED_TRANSITIONS" in symbols
    lines += ["", f"verify (bug 5): status {verify['status']}; {(verify.get('data') or {}).get('summary')}",
              "", f"Result: {'PASS' if ok else 'FAIL'}"]
    report = "\n".join(lines) + "\n"
    sys.stdout.write(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    shutil.rmtree(folder, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
