"""Summarize MCP tool metrics (one JSON line per call) into a per-tool table: calls, errors, latency, tokens.

Proposal §13.2 MCP usability: tool calls per task, average tool latency, context token cost. Works for any host
(Claude Code, OpenCode, Claude Desktop): it reads only the metrics the VGAR servers write.

    python scripts/summarize_mcp_metrics.py --metrics D:/kltn/vgar-logs/graph.metrics.jsonl [--metrics ...] --out results/mcp_metrics
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _percentile(values: list[int], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 1)


def summarize(records: list[dict]) -> dict:
    """Per-tool and total figures from metrics records.

    Args:
        records: Parsed metrics lines.
    """
    tools: dict[str, dict] = {}
    for record in records:
        tools.setdefault(record["tool"], []).append(record)
    table = {}
    for name, rows in sorted(tools.items()):
        durations = [int(r["duration_ms"]) for r in rows]
        table[name] = {
            "server": rows[0].get("server"), "calls": len(rows),
            "errors": sum(r.get("status") not in ("PASS", "OK") for r in rows),
            "mean_ms": round(statistics.fmean(durations), 1), "p50_ms": _percentile(durations, 0.5),
            "p95_ms": _percentile(durations, 0.95), "max_ms": max(durations),
            "input_tokens": sum(int(r.get("input_tokens", 0)) for r in rows),
            "output_tokens": sum(int(r.get("output_tokens", 0)) for r in rows),
        }
    methods = sorted({r.get("token_method", "") for r in records})
    return {"total_calls": len(records), "total_output_tokens": sum(t["output_tokens"] for t in table.values()),
            "total_input_tokens": sum(t["input_tokens"] for t in table.values()),
            "token_methods": methods, "tools": table}


def render(summary: dict) -> str:
    """Markdown table of a summary.

    Args:
        summary: Result of ``summarize``.
    """
    lines = ["| tool | server | calls | errors | mean ms | p50 ms | p95 ms | max ms | input tokens | output tokens |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, t in summary["tools"].items():
        lines.append(f"| {name} | {t['server']} | {t['calls']} | {t['errors']} | {t['mean_ms']} | {t['p50_ms']} | "
                     f"{t['p95_ms']} | {t['max_ms']} | {t['input_tokens']} | {t['output_tokens']} |")
    lines += ["", f"Total calls: {summary['total_calls']}; input tokens {summary['total_input_tokens']}, output "
                  f"tokens {summary['total_output_tokens']} (method: {', '.join(summary['token_methods'])})."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metrics", type=Path, action="append", required=True, help="metrics JSONL file (repeatable)")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    args = parser.parse_args()
    records = [json.loads(line) for path in args.metrics for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    if not records:
        parser.error("no metrics records found")
    summary = summarize(records)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "mcp_metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.out / "mcp_metrics.md").write_text(render(summary), encoding="utf-8")
    print(f"{summary['total_calls']} calls, {len(summary['tools'])} tools -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
