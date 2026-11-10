"""Compare each RT-1 config run with the default run (paired bootstrap per task).

Reads ``<out>/<NAME>/`` folders written by ``run_rt1_ablation.py`` and prints,
for every config and metric, the mean delta against ``default`` with its CI95.

Usage:
    python scripts/compare_rt1_ablation.py <out> [--arm graph] [--json report.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.compare import compare_graph_runs

METRICS = ("file_recall@5", "function_recall@5", "file_mrr", "function_mrr",
           "packed_gold_file_in_context", "packed_gold_function_in_context")


def compare_all(out: Path, arm: str = "graph") -> dict[str, dict[str, dict]]:
    """Paired comparison of every config folder in ``out`` against ``out/default``.

    Args:
        out: Folder holding one run folder per config, including ``default``.
        arm: Graph arm to compare (``graph`` or ``graph_f2p``).
    """
    report: dict[str, dict[str, dict]] = {}
    for run in sorted(path for path in out.iterdir() if (path / "result.json").exists() and path.name != "default"):
        report[run.name] = {}
        for metric in METRICS:
            result = compare_graph_runs(out / "default", run, arm=arm, metric=metric)
            report[run.name][metric] = {key: result[key] for key in ("n", "mean_delta", "ci95", "wins", "losses")}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--arm", default="graph", choices=("graph", "graph_f2p"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = compare_all(args.out, args.arm)
    for name, metrics in report.items():
        for metric, value in metrics.items():
            low, high = value["ci95"] if value["ci95"] else (None, None)
            print(f"{name:14} {metric:32} n={value['n']:2} delta={value['mean_delta']:+.4f} "
                  f"ci95=[{low:+.4f}, {high:+.4f}] wins={value['wins']} losses={value['losses']}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
