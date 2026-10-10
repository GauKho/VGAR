"""Pair a finished BM25 run with a finished Graph run -> results/retrieval/<cmp>/ (result.json + REPORT.md).

  python scripts/compare_graph_vs_bm25.py . results/retrieval/<bm25_run> results/retrieval/<graph_run>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.evaluation.retrieval.compare import compare_runs
from vgar.evaluation.retrieval.report import write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("bm25_run", type=Path)
    parser.add_argument("graph_run", type=Path)
    parser.add_argument("--bm25-cap", type=int, default=100, help="BM25 rank re-scored on its top-N chunks (Graph keeps <=100 nodes)")
    parser.add_argument("--seed", type=int, default=0, help="bootstrap seed for the 95%% CI")
    parser.add_argument("--no-report", action="store_true", help="Write raw JSON results only")
    args = parser.parse_args()
    directory, report = compare_runs(args.bm25_run, args.graph_run, args.root / "results" / "retrieval", cap=args.bm25_cap, seed=args.seed)
    print(directory if args.no_report else write_report(args.bm25_run, comparison=directory, destination=directory / "REPORT.md"))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
