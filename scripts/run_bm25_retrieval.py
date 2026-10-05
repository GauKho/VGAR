"""M2: BM25 retrieval run (rank + packed scoring from one rank). Counter is injected here, not imported by evaluation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.evaluation.retrieval.evaluation import DEFAULT_BUDGET_TOKENS, evaluate_manifest
from vgar.evaluation.retrieval.report import write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the BM25 arm and write REPORT.md")
    parser.add_argument("root", type=Path, help="Project root containing data/ and results/")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--allow-heldout", action="store_true", help="FINAL evaluation only; never use while tuning")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tokenizer-manifest", type=Path, help="M1 LocalTokenizerCounter manifest (official counter)")
    group.add_argument("--allow-fallback-counter", action="store_true", help="bytes/4; dev only, flagged in the report")
    args = parser.parse_args()
    counter = label = None
    if args.tokenizer_manifest:
        from vgar.graph.token_counter import LocalTokenizerCounter
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        label = counter.counter_label
    directory, record = evaluate_manifest(args.root, args.manifest, limit=args.limit, budget_tokens=args.budget_tokens,
                                          offline=args.offline, resume=args.resume, counter=counter, counter_label=label,
                                          allow_heldout=args.allow_heldout)
    print(write_report(directory))
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())