"""T2 paired report: graph_v0 vs base per task (bootstrap CI95 of the mean difference), all and multi-file tasks.

  PYTHONPATH=src python baseline/nav/nav_paired.py ~/rt1/results/nav_k20 [--arms base,graph_v0]
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import baseline._paths  # noqa: F401  (puts ablation_matrix on sys.path)

# isort: split
from compare_runs import ci95

KS = (1, 3, 5, 10, 20)
KEYS = (*(f"file_recall@{k}" for k in KS), *(f"function_recall@{k}" for k in KS), "file_mrr", "function_mrr",
        "file_all_gold@20", "seen_frontier_recall", "seen_all_gold_files", "files_read", "non_gold_files_read",
        "tool_calls", "completion_tokens")


def _table(results: dict[tuple[str, str], Any], ids: list[str], title: str, arms: tuple[str, str]) -> str:
    before, after = arms
    lines = [f"#### {title} (n={len(ids)})", "",
             f"| metric | {before} | {after} | delta [CI95] | {after} higher/lower |", "|---|---|---|---|---|"]
    for key in KEYS:
        pairs = [(results[(before, i)]["metrics"].get(key), results[(after, i)]["metrics"].get(key)) for i in ids]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if not pairs:
            continue
        deltas = [b - a for a, b in pairs]
        low, high = ci95(deltas)
        lines.append(f"| {key} | {statistics.fmean(a for a, _ in pairs):.3f} | "
                     f"{statistics.fmean(b for _, b in pairs):.3f} | {statistics.fmean(deltas):+.3f} "
                     f"[{low:+.3f}; {high:+.3f}] | {sum(d > 0 for d in deltas)}/{sum(d < 0 for d in deltas)} |")
    return "\n".join(lines)


def report(run_dir: Path, arms: tuple[str, str] = ("base", "graph_v0")) -> str:
    """Markdown: status counts, paired tables (all tasks, multi-file tasks), answer length, tool use, time per task."""
    results = {}
    for arm in arms:
        for path in sorted(Path(run_dir, arm).glob("*.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            results[(arm, result["instance_id"])] = result
    ids = sorted({i for _, i in results if all((arm, i) in results for arm in arms)})
    multi = [i for i in ids if results[(arms[0], i)]["metrics"].get("cross_file")]
    parts = [f"Run: {run_dir}",
             f"Status: {dict(collections.Counter((arm, r['status']) for (arm, _), r in results.items()))}", "",
             _table(results, ids, "All paired tasks", arms), "",
             _table(results, multi, "Multi-file tasks (>= 2 gold files)", arms), ""]
    for arm in arms:
        answers = [r["answer"] for (a, _), r in results.items() if a == arm and r.get("answer")]
        if answers:
            files, functions = [len(x["files"]) for x in answers], [len(x["functions"]) for x in answers]
            parts.append(f"Answer length {arm}: files median {statistics.median(files)} max {max(files)}; "
                         f"functions median {statistics.median(functions)} max {max(functions)}")
        calls = collections.Counter(c["name"] for (a, _), r in results.items() if a == arm for c in r.get("tool_calls", []))
        seconds = [r["usage"]["seconds"] for (a, _), r in results.items() if a == arm and r.get("usage")]
        line = f"Tool use {arm}: {dict(calls.most_common())}"
        if seconds:
            line += f"; mean seconds/task {statistics.fmean(seconds):.0f}"
        parts.append(line)
    parts.append(f"No answer: {sorted((a, i, r['status']) for (a, i), r in results.items() if not r.get('answer'))}")
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--arms", default="base,graph_v0", help="the two arms to pair: before,after")
    args = parser.parse_args(argv)
    arms = tuple(args.arms.split(","))
    if len(arms) != 2:
        parser.error("--arms needs exactly two arms")
    print(report(args.run_dir.expanduser(), arms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
