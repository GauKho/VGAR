"""Freeze the evaluation-only W10 gold/mutant pool, without model or verifier calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def main(argv=None) -> int:
    from vgar.evaluation.repair.mutant_pool import build_pool, load_w10_tasks
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet', type=Path, required=True, help='existing pinned SWE-bench parquet; never downloaded')
    parser.add_argument('--data-root', type=Path, required=True, help='M3 data root with pinned source checkouts')
    parser.add_argument('--output-root', type=Path, required=True, help='new append-only pool directory')
    parser.add_argument('--seed', type=int, choices=(0,), default=0)
    args = parser.parse_args(argv)
    try:
        tasks, provenance = load_w10_tasks(args.parquet, args.data_root)
        index = build_pool(tasks, args.output_root, seed=args.seed, provenance=provenance)
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2
    counts = {name: sum(s['status'] == name for s in index['slots']) for name in ('CREATED', 'NOT_APPLICABLE', 'ERROR')}
    print(json.dumps({'pool_hash': index['pool_hash'], 'tasks': len(index['tasks']),
        'expected_slots': index['expected_slots'], 'actual': counts, 'ready': index['ready']}, sort_keys=True))
    return 0 if index['ready'] else 2


if __name__ == '__main__':
    sys.exit(main())
