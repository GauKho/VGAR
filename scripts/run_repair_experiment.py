"""Run or inspect a repair experiment (task x variant) on the M2 engine.

  preflight build the real prompt for every pair (no model, no Docker); required before run
  run      every pair without a TERMINAL attempt; Ctrl+C stops after recording INTERRUPTED (exit 130)
  status   Markdown table of the latest attempt per pair
  aggregate  A0-A2 table + diagnostic funnel from stored records (repeat --config for stage 1 + stage 2)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar.evaluation.repair import aggregate as aggregate_module
from vgar.evaluation.repair.fairness import check_arm_fairness
from vgar.evaluation.repair.gpu import GpuPeakSampler
from vgar.evaluation.repair.launch import make_launch
from vgar.evaluation.repair.manifest import load_experiment
from vgar.evaluation.repair.preflight import preflight, require_preflight
from vgar.evaluation.repair.runner import run_experiment, summary_table


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('preflight', 'run', 'status', 'aggregate'))
    parser.add_argument('--config', type=Path, action='append', required=True,
                        help='repeat only for aggregate (stage 1 + stage 2 experiments)')
    parser.add_argument('--data-root', type=Path, required=True,
                        help='root for @data/ paths in the config (checkouts, bundles, profiles); no default on purpose')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/m3')
    parser.add_argument('--rerun', metavar='TASK:VARIANT', help='relaunch one TERMINAL pair as a new attempt')
    parser.add_argument('--reason', help='required with --rerun')
    parser.add_argument('--grades', type=Path, action='append', default=[], help='aggregate: grades.json from the harness')
    parser.add_argument('--parquet', type=Path, help='aggregate: pinned dataset parquet (gold patches, read after runs)')
    parser.add_argument('--out', type=Path, help='aggregate: directory for aggregate.json and aggregate.md')
    args = parser.parse_args(argv)
    if args.command == 'aggregate':
        if not args.parquet or not args.out:
            parser.error('aggregate requires --parquet and --out')
        experiments = [load_experiment(c, args.data_root) for c in args.config]
        gold = aggregate_module.load_gold(args.parquet, [t for e in experiments for t in e.task_ids])
        summary, markdown = aggregate_module.aggregate(args.config, args.data_root, args.output_root, args.grades, gold)
        aggregate_module.write_outputs(summary, markdown, args.out)
        print(markdown)
        return 0
    if len(args.config) != 1:
        parser.error(args.command + ' takes exactly one --config')
    exp = load_experiment(args.config[0], args.data_root)
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
    try:
        check_arm_fairness([exp])  # refused before any attempt record or experiment directory exists
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    require_preflight(args.output_root, exp)
    rerun = tuple(args.rerun.rsplit(':', 1)) if args.rerun else None
    return run_experiment(exp, args.data_root, args.output_root, make_launch(exp, args.output_root),
                          rerun=rerun, rerun_reason=args.reason,
                          sampler_factory=GpuPeakSampler if exp.generation == 'real' else None)


if __name__ == '__main__':
    sys.exit(main())
