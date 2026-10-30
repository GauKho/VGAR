"""Grade every applied repair candidate of one or more experiments with the pinned official harness.

Defaults to preflight (writes predictions, launches nothing); --execute runs run_evaluation per candidate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from vgar.evaluation.harness.candidates import grade_candidates  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-dir', type=Path, action='append', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--approved-manifest', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=ROOT/'configs/m1/w10_harness_profile.json')
    parser.add_argument('--output-root', type=Path, default=ROOT/'results/m1/w10/grades')
    parser.add_argument('--dataset-parquet', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    result = grade_candidates(args.manifest, args.profile, args.experiment_dir, args.output_root,
                              approved_manifest=args.approved_manifest, execute=args.execute,
                              dataset_parquet=args.dataset_parquet)
    print('RESULT:', result['status'], Path(result['directory'])/'grades.json',
          {s: sum(g['harness_status'] == s for g in result['grades']) for s in ('RESOLVED', 'UNRESOLVED', 'ERROR', 'NOT_RUN')})
    return 0 if result['status'] in ('COMPLETE', 'NOT_RUN') else 1


if __name__ == '__main__':
    raise SystemExit(main())
