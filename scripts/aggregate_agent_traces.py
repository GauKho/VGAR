"""M3-W12-1: bảng M1 (RQ5) từ trace `vgar solve --agent` + audit MCP -> <out>/m1.json + <out>/m1.md.

  python scripts/aggregate_agent_traces.py --traces results/m3/w12/agent/<ts> \
      --audit results/m3/w12/agent/<ts>/mcp_audit.jsonl --out results/m3/w12/agent/<ts>/m1

Chỉ mô tả (N nhỏ), không so sánh thống kê với A0–A3. Runbook: docs/m3_w12_agent_runbook.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.agent_metrics import load_trace, render_m1, summarize_traces  # noqa: E402
from vgar.evaluation.incremental_bench import environment_info  # noqa: E402

TRACE_NAME = re.compile(r"^\d{8}T\d{12}Z-.+\.json$")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--traces", type=Path, required=True, help="directory searched recursively for agent traces")
    parser.add_argument("--audit", type=Path, required=True, help="MCP audit log (VGAR_MCP_AUDIT_LOG) of the same runs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = sorted(p for p in args.traces.rglob("*.json") if TRACE_NAME.match(p.name))
    if not paths:
        parser.error(f"no agent trace found under {args.traces}")
    traces = [load_trace(p) for p in paths]
    missing = not args.audit.is_file()
    audit = [] if missing else [json.loads(line) for line in args.audit.read_text(encoding="utf-8").splitlines()
                                if line.strip()]
    summary = summarize_traces(traces, audit)
    record = {"traces": [str(p) for p in paths], "audit": str(args.audit), "audit_file_missing": missing,
              "environment": environment_info(ROOT), "summary": summary}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "m1.json").write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n",
                                      encoding="utf-8")
    (args.out / "m1.md").write_text(render_m1(summary), encoding="utf-8")
    print(args.out / "m1.json")
    print(args.out / "m1.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
