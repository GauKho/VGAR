"""M1 W11 tune-step verdict (E3): compare two finished graph retrieval runs on the same manifest.

  python scripts/compare_tune_steps.py results/retrieval/<previous> results/retrieval/<candidate>

Prints JSON with verdict ACCEPT/REJECT; the rule lives in vgar.evaluation.retrieval.compare.compare_graph_runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.compare import compare_graph_runs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("previous", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--arm", default="graph")
    parser.add_argument("--metric", default="file_recall@5")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = compare_graph_runs(args.previous, args.candidate, arm=args.arm, metric=args.metric, seed=args.seed)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
