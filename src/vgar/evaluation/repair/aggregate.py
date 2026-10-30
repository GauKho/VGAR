"""A0-A2 table and diagnostic funnel (spec §5.9) from stored records, harness grades and gold patches.

Gold patches are read here, after runs finished, and nowhere on the generator side. The denominator is
always the whole population: excluded, errored and never-run pairs stay in N. Output is byte-stable.
"""
from __future__ import annotations

import json
from pathlib import Path

from vgar.evaluation.repair.fairness import check_arm_fairness
from vgar.evaluation.repair.manifest import Experiment, load_experiment, load_graph, resolve
from vgar.evaluation.repair.runner import read_attempts
from vgar.evaluation.retrieval.dataset import changed_source_files
from vgar.repair.failure import failure_of

STEPS = ('F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8')
COST = ('input_tokens', 'output_tokens', 'generation_ms', 'model_load_ms')


def load_gold(parquet: Path, task_ids) -> dict:
    """Gold patches for evaluation only, from the pinned parquet."""
    import pyarrow.parquet as pq
    from vgar.evaluation.harness.gold_inputs import PARQUET_HASH
    from vgar.repair.evidence import digest
    raw = Path(parquet).read_bytes()
    if digest(raw) != PARQUET_HASH:
        raise ValueError('Parquet differs from the pinned snapshot')
    wanted = set(task_ids)
    return {r['instance_id']: r['patch'] for r in pq.read_table(parquet, columns=['instance_id', 'patch']).to_pylist()
            if r['instance_id'] in wanted}


def _latest(items):
    terminal = [a for a in items if a['state'] == 'TERMINAL']
    return terminal[-1] if terminal else None


def _nodes(raw_diff, document, source_repo):
    from vgar.graph.impact import diff_to_nodes
    from vgar.repair.patch import PatchPolicy
    paths = tuple(sorted({n['path'] for n in document['nodes'] if n.get('path')}))
    policy = PatchPolicy(allowed_paths=paths, protected_paths=(), max_files=1000, max_changed_lines=100000)
    report = diff_to_nodes(raw_diff, document, source_repo, patch_policy=policy)
    return {n.node_id for n in report.changed if n.kind in ('Function', 'Method')}


def _function_hit(exp, task_id, data_root, applied, gold):
    try:
        document = load_graph(exp, task_id, data_root)
        if document is None:
            return 'unavailable'
        checkout = resolve(exp.raw['source']['checkouts'].format(task_id=task_id), exp.base, data_root)
        return bool(_nodes(applied, document, checkout) & _nodes(gold, document, checkout))
    except (ValueError, OSError):
        return 'unavailable'


def _row(exp: Experiment, task_id, variant, attempt, data_root, grades, gold):
    row = {'experiment_id': exp.experiment_id, 'task_id': task_id, 'variant_id': variant.variant_id,
           'arm': variant.arm, 'status': 'NOT_RUN', 'failure': None, 'harness_status': 'NOT_GRADED',
           'multi_file': len(changed_source_files(gold)) >= 2, 'mypy': None, **dict.fromkeys(STEPS, False)}
    record = None
    if attempt is not None:
        row['status'] = attempt['status']
        if attempt.get('engine_run_dir') and (Path(attempt['engine_run_dir'])/'run_record.json').is_file():
            record = json.loads((Path(attempt['engine_run_dir'])/'run_record.json').read_text(encoding='utf-8'))
        failure = attempt.get('failure') or (failure_of(record) if record else None)
        if failure is None and attempt['status'] != 'PASS':  # W9 runner-side attempt (plan/admission/launch)
            failure = {'stage': attempt.get('stage'), 'code': attempt.get('reason')}
        row['failure'] = failure and {'stage': failure['stage'], 'code': failure['code']}
    # Keyed by run_id too: a grade of an earlier attempt never transfers to a rerun.
    row['harness_status'] = grades.get((exp.experiment_id, task_id, variant.variant_id, (record or {}).get('run_id')),
                                       'NOT_GRADED')
    stages = (record or {}).get('stages', {})
    generation = stages.get('generation') or {}
    row['cost'], row['cost_missing'] = {}, {}
    for field in COST:
        value = generation.get(field)
        row['cost'][field] = value
        if value is None:
            row['cost_missing'][field] = ('generation_not_reached' if generation.get('status', 'NOT_RUN') == 'NOT_RUN'
                                          else 'field_absent')
    row['cost']['wall_ms'] = attempt.get('wall_ms') if attempt else None
    if row['cost']['wall_ms'] is None:
        row['cost_missing']['wall_ms'] = 'no_terminal_attempt'
    row['cost']['generation_count'] = int(generation.get('status', 'NOT_RUN') != 'NOT_RUN')
    if record is None:
        return row
    row['mypy'] = ((stages.get('baseline') or {}).get('static') or {}).get('mypy', {}).get('report', {}).get('execution_status')
    normalization = (stages.get('parse_patch') or {}).get('patch_normalization')
    row['F1'] = generation.get('status') == 'PASS'
    row['F3'] = (stages.get('apply') or {}).get('status') == 'PASS'
    row['F2'] = normalization['strict_apply_ok'] is True if normalization else row['F3']
    applied_path = Path(attempt['engine_run_dir'])/'applied.diff'
    if row['F3'] and applied_path.is_file():
        applied = applied_path.read_text(encoding='utf-8')
        row['F4'] = bool(set(changed_source_files(applied)) & set(changed_source_files(gold)))
        row['F5'] = _function_hit(exp, task_id, data_root, applied, gold)
    row['F6'] = (((stages.get('verification') or {}).get('policy_checks') or {}).get('tests') or {}).get('status') == 'PASS'
    row['F7'] = record.get('status') == 'PASS'
    row['F8'] = row['F7'] and row['harness_status'] == 'RESOLVED'
    return row


def pair_rows(exp: Experiment, exp_dir: Path, data_root: Path, grades: dict, gold: dict) -> list[dict]:
    ledger = read_attempts(exp_dir)
    return [_row(exp, task_id, variant, _latest(ledger.get((task_id, variant.variant_id), [])), data_root, grades,
                 gold[task_id])
            for task_id in exp.task_ids for variant in exp.variants]


def _counts(rows):
    n = len(rows)
    return {'N': n, 'funnel': {s: {'count': sum(r[s] is True for r in rows),
                                   'rate': round(sum(r[s] is True for r in rows) / n, 4) if n else None} for s in STEPS}}


def summarize(rows: list[dict]) -> dict:
    variants = {}
    for variant_id in sorted({r['variant_id'] for r in rows}):
        group = [r for r in rows if r['variant_id'] == variant_id]
        codes = {}
        for r in group:
            code = (r['failure'] or {}).get('code') or ('NOT_RUN' if r['status'] == 'NOT_RUN' else None)
            if code:
                codes[code] = codes.get(code, 0) + 1
        cost = {}
        for field in (*COST, 'wall_ms', 'generation_count'):
            values = [r['cost'][field] for r in group if r['cost'][field] is not None]
            cost[field] = {'mean': round(sum(values) / len(values), 2) if values else None, 'n': len(values)}
        subgroups = {'multi_file': _counts([r for r in group if r['multi_file']]),
                     'single_file': _counts([r for r in group if not r['multi_file']])}
        for status in sorted({r['mypy'] for r in group if r['mypy']}):
            subgroups['mypy_' + status] = _counts([r for r in group if r['mypy'] == status])
        variants[variant_id] = {
            'arm': group[0]['arm'], **_counts(group),
            'F5_unavailable': sum(r['F5'] == 'unavailable' for r in group),
            'false_reject': sum(r['harness_status'] == 'RESOLVED' and r['status'] != 'PASS' for r in group),
            'false_accept': sum(r['status'] == 'PASS' and r['harness_status'] == 'UNRESOLVED' for r in group),
            'failure_codes': dict(sorted(codes.items())), 'cost': cost, 'subgroups': subgroups}
    return {'experiments': sorted({r['experiment_id'] for r in rows}), 'variants': variants, 'rows': rows}


def _cell(entry):
    return f"{entry['count']} ({entry['rate']:.0%})" if entry['rate'] is not None else '0'


def render_markdown(summary: dict) -> str:
    lines = ['# A0-A2 dev funnel', '', 'Experiments: ' + ', '.join(f'`{e}`' for e in summary['experiments']), '',
             '| variant | arm | N | ' + ' | '.join(STEPS) + ' | F5 unavailable | false reject | false accept |',
             '|---|---|---|' + '---|' * (len(STEPS) + 3)]
    for variant_id, v in summary['variants'].items():
        lines.append(f"| {variant_id} | {v['arm']} | {v['N']} | " + ' | '.join(_cell(v['funnel'][s]) for s in STEPS)
                     + f" | {v['F5_unavailable']} | {v['false_reject']} | {v['false_accept']} |")
    lines += ['', '| variant | subgroup | N | F3 | F4 | F8 |', '|---|---|---|---|---|---|']
    for variant_id, v in summary['variants'].items():
        for name, group in v['subgroups'].items():
            lines.append(f"| {variant_id} | {name} | {group['N']} | " + ' | '.join(
                _cell(group['funnel'][s]) for s in ('F3', 'F4', 'F8')) + ' |')
    lines += ['', '| variant | failure code | count |', '|---|---|---|']
    for variant_id, v in summary['variants'].items():
        lines += [f'| {variant_id} | {code} | {count} |' for code, count in v['failure_codes'].items()]
    lines += ['', '| variant | ' + ' | '.join(f'{f} (mean, n)' for f in (*COST, 'wall_ms')) + ' |',
              '|---|' + '---|' * (len(COST) + 1)]
    for variant_id, v in summary['variants'].items():
        lines.append(f'| {variant_id} | ' + ' | '.join(f"{v['cost'][f]['mean']}, {v['cost'][f]['n']}"
                                                       for f in (*COST, 'wall_ms')) + ' |')
    return '\n'.join(lines) + '\n'


def aggregate(configs, data_root: Path, output_root: Path, grade_files, gold: dict) -> tuple[dict, str]:
    experiments = [load_experiment(Path(c), data_root) for c in configs]
    check_arm_fairness(experiments)
    grades = {}
    for path in grade_files:
        for g in json.loads(Path(path).read_text(encoding='utf-8'))['grades']:
            grades[(g['experiment_id'], g['task_id'], g['variant_id'], g['run_id'])] = g['harness_status']
    rows = sorted((row for exp in experiments
                   for row in pair_rows(exp, Path(output_root)/exp.experiment_id, data_root, grades, gold)),
                  key=lambda r: (r['task_id'], r['variant_id'], r['experiment_id']))
    summary = summarize(rows)
    return summary, render_markdown(summary)


def write_outputs(summary: dict, markdown: str, out: Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'aggregate.json').write_text(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8', newline='\n')
    (out/'aggregate.md').write_text(markdown, encoding='utf-8', newline='\n')
