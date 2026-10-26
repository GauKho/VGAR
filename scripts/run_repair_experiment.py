"""Run or inspect a repair experiment (task x variant) on the M2 engine.

  preflight build the real prompt for every pair (no model, no Docker); required before run
  run      every pair without a TERMINAL attempt; Ctrl+C stops after recording INTERRUPTED (exit 130)
  status   Markdown table of the latest attempt per pair
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar.evaluation.repair.gpu import GpuPeakSampler
from vgar.evaluation.repair.launch import make_launch
from vgar.evaluation.repair.manifest import load_experiment
from vgar.evaluation.repair.preflight import preflight, require_preflight
from vgar.evaluation.repair.runner import run_experiment, summary_table


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('preflight', 'run', 'status'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True,
                        help='root for @data/ paths in the config (checkouts, bundles, profiles); no default on purpose')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/m3')
    parser.add_argument('--rerun', metavar='TASK:VARIANT', help='relaunch one TERMINAL pair as a new attempt')
    parser.add_argument('--reason', help='required with --rerun')
    args = parser.parse_args(argv)
    exp = load_experiment(args.config, args.data_root)
    if args.command == 'status':
        print(summary_table(args.output_root / exp.experiment_id, exp))
        return 0
    if args.command == 'preflight':
        rows = preflight(exp, args.data_root, args.output_root)
        print('| task | variant | arm | result | input tokens | cap | headroom | reason |')
        print('|---|---|---|---|---|---|---|---|')
        for r in rows:
            print(f"| {r['task_id']} | {r['variant_id']} | {r['arm']} | {r['result']} | {r['input_tokens'] or ''} | "
                  f"{r['input_cap']} | {'' if r['headroom'] is None else r['headroom']} | {r['reason'] or ''} |")
        return 0
    require_preflight(args.output_root, exp)
    rerun = tuple(args.rerun.rsplit(':', 1)) if args.rerun else None
    return run_experiment(exp, args.data_root, args.output_root, make_launch(exp, args.output_root),
                          rerun=rerun, rerun_reason=args.reason,
                          sampler_factory=GpuPeakSampler if exp.generation == 'real' else None)


if __name__ == '__main__':
    sys.exit(main())
