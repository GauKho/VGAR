"""Frozen pool controller keeps every slot and produces deterministic V1/V2."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.evaluation.repair import verifier_eval as api
from vgar.evaluation.repair.mutant_pool import PoolTask, build_pool, load_pool
from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant

ROOT = Path(__file__).resolve().parents[3]
GOLD = '--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n def public(value):\n-    return value\n+    return value + 1\n'


@pytest.fixture
def pool(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    root = tmp_path / 'pool'
    index = build_pool([PoolTask('fixture', 'fixture/repo', 'base', source, GOLD, ('a.py',), fixture=True)], root)
    task = SimpleNamespace(task_id='fixture', repo_key='fixture/repo', revision='base', source_repo=source,
        allowed_source_paths=('a.py',), protected_paths=('tests', 'pytest.ini'))
    return root, index, task


def variants():
    return {n: load_variant(ROOT / 'configs/m2/variants' / ('A3.json' if n == 'A3' else f'w10/{n}.json'))
            for n in ('A0', 'A1', 'A2', 'A3')}


def error_vector(task):
    result = api._empty_vector(task, 'FIXTURE_INFRA_ERROR')
    result['binding'].update(repo_key=task.repo_key, revision=task.revision,
                            repair_policy_hash=api.canonical_hash(RepairPolicy().model_dump(mode='json')))
    return api.seal_vector(result)


def test_controller_verifies_each_created_patch_once_and_keeps_all_slots(pool, tmp_path, monkeypatch):
    root, index, task = pool
    calls = []
    def once(task, patch, policy, out, **kwargs):
        calls.append(patch)
        out.mkdir(parents=True)
        vector = error_vector(task)
        vector['binding']['pool'] = kwargs['pool_binding']
        vector = api.seal_vector(vector)
        api.atomic_json(out / 'vector.json', vector)
        return vector
    monkeypatch.setattr(api, 'verify_once', once)
    run = api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), variants(),
                            expected_pool_hash=index['pool_hash'])
    assert len(run['slots']) == 6
    assert len(calls) == sum(s['status'] == 'CREATED' for s in index['slots'])
    assert sum(s['status'] == 'NOT_APPLICABLE' for s in run['slots']) == sum(
        s['status'] == 'NOT_APPLICABLE' for s in index['slots'])
    summary = api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])
    assert summary['expected_slots'] == 6
    assert summary['complete'] is True  # terminal ERROR still an evaluated outcome
    assert summary['variants']['A0'] == summary['variants']['A1']
    assert summary['variants']['A3']['good_errors'] == 1
    first = api.render_tables(summary)
    assert first == api.render_tables(api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash']))
    assert 'N/A' in first['V2.md']


def test_interruption_preserves_remaining_not_run_and_incomplete_rates(pool, tmp_path, monkeypatch):
    root, index, task = pool
    def interrupt(*a, **kw):
        raise KeyboardInterrupt()
    monkeypatch.setattr(api, 'verify_once', interrupt)
    with pytest.raises(KeyboardInterrupt):
        api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), variants(),
                          expected_pool_hash=index['pool_hash'])
    run = json.loads((tmp_path / 'run/campaign.json').read_bytes())
    assert len(run['slots']) == 6
    assert any(row['status'] == 'NOT_RUN' for row in run['slots'])
    summary = api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])
    assert summary['complete'] is False
    assert summary['variants']['A3']['FAR'] is None


def test_missing_task_input_is_explicit_error_not_exclusion(pool, tmp_path):
    root, index, task = pool
    def missing(task_id):
        raise FileNotFoundError('task profile missing')
    run = api.evaluate_pool(root, tmp_path / 'run', missing, RepairPolicy(), variants(),
                            expected_pool_hash=index['pool_hash'])
    assert all(row['status'] in ('ERROR', 'NOT_APPLICABLE') for row in run['slots'])
    assert any(row['reason'] == 'TASK_INPUT_ERROR' for row in run['slots'])


def test_consumer_rejects_tampered_stored_vector(pool, tmp_path, monkeypatch):
    root, index, task = pool
    def once(task, patch, policy, out, **kwargs):
        out.mkdir(parents=True)
        vector = error_vector(task)
        api.atomic_json(out / 'vector.json', vector)
        return vector
    monkeypatch.setattr(api, 'verify_once', once)
    api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), variants(),
                      expected_pool_hash=index['pool_hash'])
    vector_path = next((tmp_path / 'run/vectors').rglob('vector.json'))
    vector_path.write_bytes(b'{}')
    with pytest.raises(ValueError, match='hash'):
        api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])


def test_real_population_fixture_keeps_150_slots_when_no_operator_applies(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'a.py').write_bytes(b'value = 1\n')
    patch = '--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    tasks = [PoolTask(f'fixture-{i}', 'fixture/repo', 'base', source, patch, ('a.py',), fixture=True) for i in range(25)]
    result = build_pool(tasks, tmp_path / 'pool')
    assert len(result['slots']) == result['expected_slots'] == 150
    assert len(load_pool(tmp_path / 'pool')['tasks']) == 25


def test_controller_refuses_shared_policy_drift_before_output(pool, tmp_path):
    root, index, task = pool
    policies = variants()
    policies['A3'] = policies['A3'].model_copy(update={'patch_mode': 'strict'})
    with pytest.raises(ValueError, match='fairness'):
        api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), policies,
                          expected_pool_hash=index['pool_hash'])
    assert not (tmp_path / 'run').exists()


def test_report_rejects_vector_substitution_between_slots(pool, tmp_path, monkeypatch):
    root, index, task = pool
    def once(task, patch, policy, out, **kwargs):
        out.mkdir(parents=True)
        vector = error_vector(task)
        vector['binding']['pool'] = kwargs['pool_binding']
        vector = api.seal_vector(vector)
        api.atomic_json(out / 'vector.json', vector)
        return vector
    monkeypatch.setattr(api, 'verify_once', once)
    run = api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), variants(),
                            expected_pool_hash=index['pool_hash'])
    rows = [r for r in run['slots'] if r['vector_ref']]
    first = tmp_path / 'run' / rows[0]['vector_ref']
    second = tmp_path / 'run' / rows[1]['vector_ref']
    second.write_bytes(first.read_bytes())
    rows[1]['vector_file_hash'] = api.digest(second.read_bytes())
    api._save_campaign(tmp_path / 'run', run)
    with pytest.raises(ValueError, match='binding'):
        api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])


def test_report_cli_twice_is_byte_identical(pool, tmp_path):
    root, index, task = pool
    def missing(task_id):
        raise FileNotFoundError('fixture missing profile')
    api.evaluate_pool(root, tmp_path / 'run', missing, RepairPolicy(), variants(), expected_pool_hash=index['pool_hash'])
    spec = importlib.util.spec_from_file_location('pool_eval_cli', ROOT / 'scripts/evaluate_mutant_pool.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    args = ['report', '--pool', str(root), '--expected-pool-hash', index['pool_hash'],
        '--output-root', str(tmp_path / 'run'), '--table-root', str(tmp_path / 'tables')]
    assert cli.main(args) == 0
    first = {p.name: p.read_bytes() for p in (tmp_path / 'tables').iterdir()}
    assert cli.main(args) == 0
    assert first == {p.name: p.read_bytes() for p in (tmp_path / 'tables').iterdir()}


def test_runtime_planner_only_ignores_known_generation_exclusion_and_keeps_proof(tmp_path, monkeypatch):
    from vgar.evaluation.repair import manifest, fairness
    from vgar.repair import admission
    spec = importlib.util.spec_from_file_location('runtime_cli', ROOT / 'scripts/evaluate_mutant_pool.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    from vgar.evaluation.repair.mutant_pool import W10_IDS
    from dataclasses import dataclass
    @dataclass
    class Experiment:
        task_ids: tuple
        policy: object
        variants: tuple
        raw: dict
    raw = {'source': {'excluded': {W10_IDS[0]: 'OVER_CAP before running (D18/D25): A2 > cap',
        W10_IDS[1]: 'SOURCE_POLICY_UNSUPPORTED'}}}
    exp = Experiment(W10_IDS, RepairPolicy(runtime='docker_admitted'),
        (SimpleNamespace(arm='graph', variant_id='A2'),), raw)
    config = tmp_path / 'runtime.json'
    config.write_bytes(b'{}')
    monkeypatch.setattr(manifest, 'load_experiment', lambda *a: exp)
    monkeypatch.setattr(fairness, 'check_arm_fairness', lambda *a: None)
    seen = []
    def plan(loaded, task_id, *a):
        seen.append(loaded.raw['source'].get('excluded', {}))
        return SimpleNamespace(skip_reason=None, task=task_id, admission_args={})
    monkeypatch.setattr(manifest, 'plan_task', plan)
    monkeypatch.setattr(admission, 'admit_task', lambda task, **kw: task)
    result = cli._runtime([config], tmp_path)
    result[1](W10_IDS[0])
    assert seen == [{W10_IDS[1]: 'SOURCE_POLICY_UNSUPPORTED'}]
    assert len(result) == 3
    assert result[2]['ignored_generation_exclusions'] == {W10_IDS[0]: raw['source']['excluded'][W10_IDS[0]]}
    assert len(raw['source']['excluded']) == 2


def test_campaign_rejects_source_output_overlap_before_creating_files(pool):
    root, index, task = pool
    before = api.inventory(task.source_repo)
    with pytest.raises(ValueError, match='overlap'):
        api.evaluate_pool(root, task.source_repo / 'new-campaign', lambda task_id: (task, None),
            RepairPolicy(), variants(), expected_pool_hash=index['pool_hash'])
    assert api.inventory(task.source_repo) == before
    assert not (task.source_repo / 'new-campaign').exists()


def test_evaluated_row_requires_vector_and_error_row_cannot_accept(pool, tmp_path, monkeypatch):
    root, index, task = pool
    def once(task, patch, policy, out, **kwargs):
        out.mkdir(parents=True)
        vector = error_vector(task)
        vector['binding']['pool'] = kwargs['pool_binding']
        vector = api.seal_vector(vector)
        api.atomic_json(out / 'vector.json', vector)
        return vector
    monkeypatch.setattr(api, 'verify_once', once)
    run = api.evaluate_pool(root, tmp_path / 'run', lambda task_id: (task, None), RepairPolicy(), variants(),
                            expected_pool_hash=index['pool_hash'])
    row = next(r for r in run['slots'] if r['status'] == 'EVALUATED')
    row['vector_ref'] = row['vector_file_hash'] = None
    api._save_campaign(tmp_path / 'run', run)
    with pytest.raises(ValueError, match='vector'):
        api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])


def test_pool_input_errors_leave_rates_na_and_explicit_planned_counts(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    tasks = [PoolTask('ready', 'fixture/repo', 'base', source, GOLD, ('a.py',), fixture=True),
        PoolTask('missing', 'fixture/repo', 'base', tmp_path / 'missing', '', (), fixture=True, unavailable_reason='SOURCE_MISSING')]
    root = tmp_path / 'pool'
    index = build_pool(tasks, root)
    def missing(task_id):
        raise FileNotFoundError('profile unavailable')
    api.evaluate_pool(root, tmp_path / 'run', missing, RepairPolicy(), variants(), expected_pool_hash=index['pool_hash'])
    summary = api.report_campaign(root, tmp_path / 'run', expected_pool_hash=index['pool_hash'])
    assert summary['complete'] is False
    for name in variants():
        row = summary['variants'][name]
        assert row['FAR'] is row['FRR'] is None
        assert row['planned_good'] == 2 and row['planned_bad'] == 10
        assert row['good_pool_errors'] == 1 and row['bad_pool_errors'] == 5


def test_table_output_cannot_modify_known_original_source(pool, tmp_path):
    root, index, task = pool
    def missing(task_id):
        raise FileNotFoundError('profile unavailable')
    api.evaluate_pool(root, tmp_path / 'run', missing, RepairPolicy(), variants(),
        expected_pool_hash=index['pool_hash'], source_roots=[task.source_repo])
    spec = importlib.util.spec_from_file_location('table_guard_cli', ROOT / 'scripts/evaluate_mutant_pool.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    before = api.inventory(task.source_repo)
    assert cli.main(['report', '--pool', str(root), '--expected-pool-hash', index['pool_hash'],
        '--output-root', str(tmp_path / 'run'), '--table-root', str(task.source_repo / 'tables')]) == 2
    assert api.inventory(task.source_repo) == before
