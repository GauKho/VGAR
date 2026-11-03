"""M1-W12-2 dry-run orchestrator: preconditions, infra-error classification, gate, held-out command template."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.evaluation import dry_run
from vgar.evaluation.dry_run import (
    DRY_RUN_TASKS,
    build_steps,
    check_preconditions,
    gate,
    heldout_commands,
    infra_errors,
    run_chain,
)

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ROOT / 'configs/m2/variants'


def _manifest(split='dev', ids=DRY_RUN_TASKS):
    return {'split': split, 'tasks': [{'instance_id': i, 'split': dry_run.split_of(i)} for i in ids]}


def _context(tmp_path, arms=('A0', 'A1', 'A2')):
    return dry_run.Context(template=tmp_path / 'template.json', data_root=tmp_path / 'data', out=tmp_path / 'out',
                           arms=tuple(arms), manifest=tmp_path / 'manifest.json', parquet=tmp_path / 'x.parquet',
                           python='python', variants_dir=VARIANTS)


def test_preconditions_reject_heldout_manifest():
    with pytest.raises(ValueError, match='allowed'):
        check_preconditions(_manifest(split='heldout'), ['A0'], VARIANTS)


def test_preconditions_reject_unfrozen_ranking(monkeypatch):
    monkeypatch.setattr(dry_run, 'ranking_config_hash', lambda config: 'sha256:' + '0' * 64)
    with pytest.raises(ValueError, match='frozen'):
        check_preconditions(_manifest(), ['A0'], VARIANTS)


def test_preconditions_require_dry_run_tasks_first_in_manifest():
    with pytest.raises(ValueError, match='first'):
        check_preconditions(_manifest(ids=('django__django-10914', 'astropy__astropy-13033')), ['A0'], VARIANTS)


def test_missing_variant_without_arms_flag_stops(tmp_path):
    for arm in ('A0', 'A1', 'A2'):
        (tmp_path / f'{arm}.json').write_bytes((VARIANTS / f'{arm}.json').read_bytes())
    with pytest.raises(ValueError, match='A3.json'):
        check_preconditions(_manifest(), ['A0', 'A1', 'A2', 'A3'], tmp_path)


def test_infra_errors_counts_infra_not_model_outcomes():
    attempts = {('t', 'A1'): [{'state': 'TERMINAL', 'status': 'ERROR', 'reason': 'PATCH_PARSE_ERROR'}],
                ('t', 'A2'): [{'state': 'TERMINAL', 'status': 'ERROR', 'reason': 'WORKTREE_ERROR'}],
                ('t', 'A0'): [{'state': 'RUNNING', 'status': None, 'reason': None}]}
    grades = {'status': 'COMPLETE', 'grades': [{'task_id': 't', 'variant_id': 'A1', 'harness_status': 'ERROR'},
                                               {'task_id': 't', 'variant_id': 'A2', 'harness_status': 'UNRESOLVED'}]}
    kinds = sorted(e['kind'] for e in infra_errors([{'name': 'run', 'exit_code': 0}], attempts, grades))
    assert kinds == ['attempt_not_terminal', 'grade_error', 'runner_infra_reason']


def test_infra_errors_counts_step_exit_and_blocked_grading():
    kinds = sorted(e['kind'] for e in infra_errors([{'name': 'grade', 'exit_code': 1}], {}, {'status': 'BLOCKED',
                                                                                         'grades': []}))
    assert kinds == ['grade_blocked', 'step_exit']


def test_gate():
    assert gate([], ['A0', 'A1', 'A2', 'A3']) == 'PASS'
    assert gate([], ['A0', 'A1', 'A2']) == 'INCOMPLETE_A3_MISSING'
    assert gate([{'kind': 'step_exit'}], ['A0', 'A1', 'A2', 'A3']) == 'FAIL'
    assert gate([{'kind': 'step_exit'}], ['A0', 'A1', 'A2']) == 'FAIL'


def test_build_steps_order_and_commands(tmp_path):
    steps = build_steps(_context(tmp_path))
    assert [s.name for s in steps] == ['export_bundles', 'derive_config', 'preflight', 'run', 'grade', 'aggregate']
    derive = ' '.join(steps[1].argv)
    assert '--tasks ' + ','.join(DRY_RUN_TASKS) in derive and '--variants A0:bm25,A1:graph,A2:graph' in derive
    assert '--limit 2' in ' '.join(steps[0].argv) and '--execute' in steps[4].argv


def test_heldout_commands_have_placeholder_and_no_limit(tmp_path):
    text = heldout_commands(build_steps(_context(tmp_path)), tmp_path / 'manifest.json')
    assert '<HELDOUT_MANIFEST>' in text and '<ALL_HELDOUT_TASKS>' in text
    assert '--limit' not in text and str(tmp_path / 'manifest.json') not in text
    assert 'protocol-freeze' in text.splitlines()[0]


class _Completed:
    def __init__(self, returncode, stdout=''):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ''


def _prepare(tmp_path):
    context = _context(tmp_path)
    context.manifest.write_text(json.dumps(_manifest() | {'manifest_hash': 'sha256:' + 'a' * 64}), encoding='utf-8')
    return context


def test_failed_step_still_writes_record(tmp_path):
    def fake_runner(argv, **kwargs):
        joined = ' '.join(map(str, argv))
        if 'export_w9_pilot_bundles.py' in joined:
            return _Completed(0, 'RUN DIRECTORY: /data/w12/bundles/repair/20261104T000000Z-abc\n')
        if 'derive_experiment_config.py' in joined:
            return _Completed(0, f'{tmp_path}/out/w12_dry_run.json 0123456789abcdef\n')
        return _Completed(1 if 'grade_repair_candidates.py' in joined else 0)
    record = run_chain(_prepare(tmp_path), runner=fake_runner)
    assert [s['name'] for s in record['steps']] == ['export_bundles', 'derive_config', 'preflight', 'run', 'grade']
    assert record['gate'] == 'FAIL' and record['steps'][-1]['exit_code'] == 1
    assert record['experiment_id'] == '0123456789abcdef'
    assert '@data/w12/bundles/repair/20261104T000000Z-abc' in ' '.join(record['steps'][1]['argv'])
    saved = json.loads((tmp_path / 'out/dry_run.json').read_text(encoding='utf-8'))
    assert saved['gate'] == 'FAIL' and (tmp_path / 'out/heldout_commands.md').exists()
    assert (tmp_path / 'out/logs/grade.log').exists()


def test_precondition_failure_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(dry_run, 'ranking_config_hash', lambda config: 'sha256:' + '0' * 64)
    calls = []
    record = run_chain(_prepare(tmp_path), runner=lambda argv, **kw: calls.append(argv))
    assert calls == [] and record['gate'] == 'FAIL' and 'frozen' in record['precondition_error']
    assert json.loads((tmp_path / 'out/dry_run.json').read_text(encoding='utf-8'))['steps'] == []


def test_cli_help_runs():
    assert subprocess.run([sys.executable, 'scripts/dry_run_heldout_chain.py', '--help'], cwd=ROOT,
                          capture_output=True).returncode == 0
