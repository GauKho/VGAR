"""M2-W12-2: verify fixed patches once on admitted Docker tasks, or regenerate V1/V2.

No generation, model loading, retrieval tuning or target-image replacement.
Real run belongs to M3's sequential window after GPU and dry-runs.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def _runtime(configs, data_root):
    from vgar.evaluation.repair.mutant_pool import W10_IDS
    from vgar.evaluation.repair.fairness import check_arm_fairness
    from vgar.evaluation.repair.manifest import load_experiment, plan_task, resolve
    from vgar.repair.admission import admit_task
    from vgar.repair.evidence import digest
    experiments = [load_experiment(p, data_root) for p in configs]
    if tuple(t for e in experiments for t in e.task_ids) != W10_IDS:
        raise ValueError('Runtime configs must retain the exact ordered 11+14 W10 population')
    check_arm_fairness(experiments)
    if any(e.policy.runtime != 'docker_admitted' for e in experiments):
        raise ValueError('Real pool requires admitted Docker; no native fallback')
    indexed = {task: exp for exp in experiments for task in exp.task_ids}
    ignored = {task: reason for exp in experiments
        for task, reason in exp.raw['source'].get('excluded', {}).items()
        if isinstance(reason, str) and reason.startswith('OVER_CAP before running (D18/D25):')}

    def provider(task_id):
        exp = indexed[task_id]
        # Fixed-patch verification has no prompt or retrieval budget. Preserve all
        # 25 IDs; environment/profile/admission still independently qualify them.
        raw = copy.deepcopy(exp.raw)
        excluded = raw['source'].get('excluded', {})
        raw['source']['excluded'] = {t: reason for t, reason in excluded.items() if t not in ignored}
        exp = replace(exp, raw=raw)
        candidates = [v for v in exp.variants if v.arm == 'graph' and v.variant_id in ('A2', 'A3')]
        if not candidates:
            raise ValueError('Runtime needs a pinned graph bundle for fixed-source admission')
        plan = plan_task(exp, task_id, candidates[0], data_root)
        if plan.skip_reason:
            raise ValueError(plan.skip_reason + ': ' + str(plan.skip_detail))
        return plan.task, admit_task(plan.task, **plan.admission_args)

    return experiments[0].policy, provider, dict(
        runtime_config_hashes={str(p): digest(p.read_bytes()) for p in configs},
        source_roots=[str(resolve(e.raw['source']['checkouts'].format(task_id=t), e.base, data_root).resolve())
            for e in experiments if 'checkouts' in e.raw['source'] for t in e.task_ids],
        ignored_generation_exclusions=ignored,
        eligibility='fixed patch has no generation/prompt budget; other exclusions and admission remain enforced')


def main(argv=None):
    from vgar.evaluation.repair.mutant_pool import load_pool
    from vgar.evaluation.repair.verifier_eval import evaluate_pool, render_tables, report_campaign
    from vgar.repair.policy import load_variant
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'report'))
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--expected-pool-hash', required=True)
    parser.add_argument('--output-root', type=Path, required=True, help='fresh campaign directory for run; stored directory for report')
    parser.add_argument('--table-root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--config', type=Path, action='append', help='ordered W10 stage1+stage2 runtime configs; run only')
    parser.add_argument('--temp-root', type=Path)
    args = parser.parse_args(argv)
    try:
        pool = load_pool(args.pool, expected_pool_hash=args.expected_pool_hash)
        if args.command == 'run':
            if pool['provenance'].get('kind') != 'pinned_w10' or args.data_root is None:
                raise ValueError('Real run requires pinned W10 pool and explicit --data-root')
            configs = args.config or [ROOT / 'configs/m3/w10_dev_stage1.json', ROOT / 'configs/m3/w10_dev_stage2.json']
            policy, provider, runtime_provenance = _runtime(configs, args.data_root)
            variants = {name: load_variant(ROOT / 'configs/m2/variants' /
                ('A3.json' if name == 'A3' else f'w10/{name}.json')) for name in ('A0', 'A1', 'A2', 'A3')}
            evaluate_pool(args.pool, args.output_root, provider, policy, variants,
                expected_pool_hash=args.expected_pool_hash, temp_root=args.temp_root,
                runtime_provenance=runtime_provenance, source_roots=runtime_provenance['source_roots'])
        summary = report_campaign(args.pool, args.output_root, expected_pool_hash=args.expected_pool_hash)
        tables = render_tables(summary)
        table_root = args.table_root.resolve()
        if table_root == args.pool.resolve() or table_root.is_relative_to(args.pool.resolve()):
            raise ValueError('Table output cannot overwrite frozen pool')
        if any(table_root == p or table_root.is_relative_to(p) or p.is_relative_to(table_root)
               for p in (Path(value).resolve() for value in summary['source_roots'])):
            raise ValueError('Table output/source overlap is forbidden')
        table_root.mkdir(parents=True, exist_ok=True)
        for name, content in tables.items():
            (table_root / name).write_text(content, encoding='utf-8', newline='\n')
        print(json.dumps(dict(expected_slots=summary['expected_slots'], generated=summary['generated_patches'],
            states=summary['states'], execution_complete=summary['complete']), sort_keys=True))
        return 0 if summary['complete'] else 2
    except KeyboardInterrupt:
        print('Interrupted: campaign ledger and incomplete vectors retained.', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
