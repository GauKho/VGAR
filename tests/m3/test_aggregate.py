"""M3-W10-2: deterministic A0-A2 table and diagnostic funnel from stored records only (spec §5.9)."""
import json

import pytest
from m3_support import write_json

GOLD_ONE = '--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n'
GOLD_TWO = ('--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n'
            '--- a/pkg/b.py\n+++ b/pkg/b.py\n@@ -1 +1 @@\n-b = 1\n+b = 2\n')
GOLD = {'demo__demo-1': GOLD_ONE, 'demo__demo-2': GOLD_TWO}
APPLIED = 'diff --git a/pkg/core.py b/pkg/core.py\n--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 3\n'


def stages(**given):
    from vgar.repair.session import STAGES
    return {name: given.get(name, {'status': 'NOT_RUN'}) for name in STAGES}


GEN = {'status': 'PASS', 'input_tokens': 4000, 'output_tokens': 300, 'generation_ms': 60000, 'model_load_ms': 9000}
BASE = {'status': 'PASS', 'static': {'mypy': {'report': {'execution_status': 'COMPLETE'}}}}


def engine_record(status, reason, **given):
    return {'run_id': 'r', 'status': status, 'reason': reason, 'complete': True, 'stages': stages(**given)}


def write_pair(exp_dir, task_id, variant, *, state='TERMINAL', record=None, applied=None, runner=None, attempt=1):
    run_dir = exp_dir/'engine'/f'{task_id}__{variant}'/f'attempt-{attempt}'/'run'
    attempt_record = {'experiment_id': exp_dir.name, 'task_id': task_id, 'variant_id': variant,
                      'arm': {'A0': 'bm25'}.get(variant, 'graph'), 'attempt': attempt, 'state': state,
                      'status': None, 'reason': None, 'stage': None, 'engine_run_dir': None, 'wall_ms': 120000}
    if record is not None:
        write_json(run_dir/'run_record.json', record)
        if applied:
            (run_dir/'applied.diff').write_text(applied, encoding='utf-8')
        attempt_record.update(status=record['status'], reason=record['reason'], engine_run_dir=str(run_dir))
    if runner is not None:
        attempt_record.update(status='ERROR', reason=runner, stage='plan',
                              failure={'stage': 'plan', 'code': runner, 'cause': None, 'evidence_ref': None})
    write_json(exp_dir/'attempts'/f'{task_id}__{variant}'/f'attempt-{attempt}.json', attempt_record)


@pytest.fixture
def stored(swebench_config, tmp_path):
    """demo-1: A0 strict-fails but applies after normalization and fails its tests; A1 is accepted;
    A2 was only interrupted. demo-2 (two-file gold) is excluded for every arm."""
    from vgar.evaluation.repair.manifest import load_experiment
    path, data = swebench_config
    exp = load_experiment(path, data)
    exp_dir = tmp_path/'out'/exp.experiment_id
    parse_ok = {'status': 'PASS', 'patch_normalization': {'mode': 'normalized', 'strict_parse_ok': False,
                                                          'strict_apply_ok': False}}
    write_pair(exp_dir, 'demo__demo-1', 'A0', applied=APPLIED, record=engine_record(
        'FAIL', 'TEST_FAILED', generation=GEN, baseline=BASE, parse_patch=parse_ok, apply={'status': 'PASS'},
        verification={'status': 'FAIL', 'policy_checks': {'tests': {'status': 'FAIL'}}, 'reasons': ['TEST_FAILED']}))
    write_pair(exp_dir, 'demo__demo-1', 'A1', applied=APPLIED, record=engine_record(
        'PASS', None, generation=GEN, baseline=BASE, parse_patch=dict(parse_ok, patch_normalization=dict(
            parse_ok['patch_normalization'], strict_parse_ok=True, strict_apply_ok=True)), apply={'status': 'PASS'},
        verification={'status': 'PASS', 'policy_checks': {'tests': {'status': 'PASS'}}}))
    write_pair(exp_dir, 'demo__demo-1', 'A2', state='INTERRUPTED')
    for variant in ('A0', 'A1', 'A2'):
        write_pair(exp_dir, 'demo__demo-2', variant, runner='TASK_EXCLUDED')
    grades = write_json(tmp_path/'grades.json', {'grades': [
        {'experiment_id': exp.experiment_id, 'task_id': 'demo__demo-1', 'variant_id': 'A0', 'run_id': 'r', 'harness_status': 'RESOLVED'},
        {'experiment_id': exp.experiment_id, 'task_id': 'demo__demo-1', 'variant_id': 'A1', 'run_id': 'r', 'harness_status': 'RESOLVED'}]})
    return path, data, tmp_path/'out', grades


def run(stored, **kwargs):
    from vgar.evaluation.repair.aggregate import aggregate
    path, data, out, grades = stored
    return aggregate([path], data, out, [grades], GOLD, **kwargs)


def funnel(summary, variant):
    return {k: v['count'] for k, v in summary['variants'][variant]['funnel'].items()}


def test_denominator_includes_excluded_and_not_run(stored):
    summary, _ = run(stored)
    assert {v: s['N'] for v, s in summary['variants'].items()} == {'A0': 2, 'A1': 2, 'A2': 2}
    rows = {(r['task_id'], r['variant_id']): r for r in summary['rows']}
    assert rows[('demo__demo-1', 'A2')]['status'] == 'NOT_RUN'  # Review Focus 5: interrupted only, still counted
    assert rows[('demo__demo-2', 'A0')]['failure'] == {'stage': 'plan', 'code': 'TASK_EXCLUDED'}
    assert summary['variants']['A0']['funnel']['F8']['rate'] == 0.0


def test_funnel_counts(stored):
    summary, _ = run(stored)
    assert funnel(summary, 'A0') == {'F1': 1, 'F2': 0, 'F3': 1, 'F4': 1, 'F5': 0, 'F6': 0, 'F7': 0, 'F8': 0}
    assert funnel(summary, 'A1') == {'F1': 1, 'F2': 1, 'F3': 1, 'F4': 1, 'F5': 0, 'F6': 1, 'F7': 1, 'F8': 1}
    assert funnel(summary, 'A2') == dict.fromkeys(('F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8'), 0)
    assert summary['variants']['A1']['funnel']['F8']['rate'] == 0.5
    assert summary['variants']['A0']['F5_unavailable'] == 1  # no pinned graph for demo-1


def test_false_accept_and_reject(stored):
    summary, _ = run(stored)
    assert summary['variants']['A0']['false_reject'] == 1 and summary['variants']['A0']['false_accept'] == 0
    path, data, out, grades = stored
    payload = json.loads(grades.read_text())
    payload['grades'][1]['harness_status'] = 'UNRESOLVED'
    grades.write_text(json.dumps(payload))
    summary, _ = run(stored)
    assert summary['variants']['A1']['false_accept'] == 1 and funnel(summary, 'A1')['F8'] == 0


def test_legacy_record_without_failure_gets_stage(stored):
    summary, _ = run(stored)
    row = next(r for r in summary['rows'] if (r['task_id'], r['variant_id']) == ('demo__demo-1', 'A0'))
    assert row['failure'] == {'stage': 'verification', 'code': 'TEST_FAILED'}
    assert row['harness_status'] == 'RESOLVED'


def test_subgroups_cost_and_failure_codes(stored):
    summary, _ = run(stored)
    a0 = summary['variants']['A0']
    assert a0['subgroups']['multi_file']['N'] == 1 and a0['subgroups']['single_file']['N'] == 1
    assert a0['subgroups']['mypy_COMPLETE']['N'] == 1
    assert a0['failure_codes'] == {'TASK_EXCLUDED': 1, 'TEST_FAILED': 1}
    assert a0['cost']['input_tokens'] == {'mean': 4000.0, 'n': 1}
    assert a0['cost']['wall_ms']['n'] == 2  # runner wall time exists even for the excluded task
    row = next(r for r in summary['rows'] if (r['task_id'], r['variant_id']) == ('demo__demo-2', 'A0'))
    assert row['cost']['input_tokens'] is None and row['cost_missing']['input_tokens'] == 'generation_not_reached'


def test_byte_identical_rerun(stored, tmp_path):
    from vgar.evaluation.repair.aggregate import write_outputs
    first, second = tmp_path/'agg1', tmp_path/'agg2'
    write_outputs(*run(stored), first)
    write_outputs(*run(stored), second)
    for name in ('aggregate.json', 'aggregate.md'):
        assert (first/name).read_bytes() == (second/name).read_bytes()
    assert str(tmp_path) not in (first/'aggregate.json').read_text()  # no absolute paths in the table
    assert '| A1 |' in (first/'aggregate.md').read_text()


def test_cross_experiment_fairness_enforced(stored, tmp_path):
    from vgar.evaluation.repair.aggregate import aggregate
    from m3_support import ROOT
    path, data, out, grades = stored
    demo = json.loads((ROOT/'configs/m2/demo.json').read_text())
    demo['policy']['input_cap'] = 5000
    demo['model']['tokenizer_manifest'] = str((ROOT/'configs/m2'/demo['model']['tokenizer_manifest']).resolve())
    demo['model']['interpreter'] = str((ROOT/'configs/m2'/demo['model']['interpreter']).resolve())
    other_config = json.loads(path.read_text())
    other_config['repair_config'] = str(write_json(tmp_path/'demo_5000.json', demo))
    other = write_json(tmp_path/'other.json', other_config)
    with pytest.raises(ValueError, match='Arm fairness violation'):
        aggregate([path, other], data, out, [grades], GOLD)


def test_cli_aggregate_writes_table(stored, tmp_path, monkeypatch):
    import importlib.util
    from m3_support import ROOT
    from vgar.evaluation.repair import aggregate as module
    spec = importlib.util.spec_from_file_location('run_cli', ROOT/'scripts/run_repair_experiment.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(module, 'load_gold', lambda parquet, task_ids: GOLD)  # parquet IO boundary only
    path, data, out, grades = stored
    target = tmp_path/'agg'
    assert cli.main(['aggregate', '--config', str(path), '--data-root', str(data), '--output-root', str(out),
                     '--grades', str(grades), '--parquet', str(tmp_path/'unused.parquet'), '--out', str(target)]) == 0
    assert json.loads((target/'aggregate.json').read_text())['variants']['A1']['funnel']['F8']['count'] == 1
    with pytest.raises(SystemExit):
        cli.main(['status', '--config', str(path), '--config', str(path), '--data-root', str(data)])


def test_legacy_runner_attempt_without_failure_keeps_stage_and_code(stored):
    path, data, out, grades = stored
    from vgar.evaluation.repair.manifest import load_experiment
    attempt = out/load_experiment(path, data).experiment_id/'attempts/demo__demo-2__A0/attempt-1.json'
    legacy = json.loads(attempt.read_text())
    legacy.pop('failure')  # W9 runner attempts predate the failure field
    attempt.write_text(json.dumps(legacy))
    summary, _ = run(stored)
    row = next(r for r in summary['rows'] if (r['task_id'], r['variant_id']) == ('demo__demo-2', 'A0'))
    assert row['failure'] == {'stage': 'plan', 'code': 'TASK_EXCLUDED'}


def test_grade_of_another_run_is_not_applied(stored):
    path, data, out, grades = stored
    payload = json.loads(grades.read_text())
    payload['grades'][1]['run_id'] = 'earlier-attempt'
    grades.write_text(json.dumps(payload))
    summary, _ = run(stored)
    row = next(r for r in summary['rows'] if (r['task_id'], r['variant_id']) == ('demo__demo-1', 'A1'))
    assert row['harness_status'] == 'NOT_GRADED' and funnel(summary, 'A1')['F8'] == 0
