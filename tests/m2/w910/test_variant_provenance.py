"""Opt-in profile, persisted binding and real fake-repair integration."""
import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
DEBT_FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,3 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n+unused: int = "debt"\n'


def test_profile_binds_explicit_arm_and_derives_hash_without_mutating_input(experiment_input):
    from vgar.repair.experiment import RepairExperiment
    from vgar.repair.policy import policy_hash
    before = copy.deepcopy(experiment_input)
    profile = RepairExperiment.model_validate(experiment_input)
    assert profile.variant_policy.arm == 'bm25'
    assert profile.policy_hash == policy_hash(profile.variant_policy)
    assert experiment_input == before
    assert profile.snapshot()['variant_id'] == 'A0'
    assert profile.snapshot()['policy_hash'] == profile.policy_hash


@pytest.mark.parametrize('fault', ['bad_arm', 'mismatched_arm', 'variant', 'hash_override', 'missing_arm', 'bad_hashes'])
def test_profile_rejects_invalid_input(experiment_input, fault):
    from vgar.repair.experiment import RepairExperiment
    if fault == 'bad_arm':
        experiment_input['arm'] = 'A0'
    elif fault == 'mismatched_arm':
        experiment_input['variant_policy']['arm'] = 'graph'
    elif fault == 'variant':
        experiment_input['variant_policy']['variant_id'] = 'A9'
    elif fault == 'hash_override':
        experiment_input['policy_hash'] = 'sha256:'+'a'*64
    elif fault == 'missing_arm':
        experiment_input.pop('arm')
    else:
        experiment_input['expected_hashes'] = {'context.json': 'sha256:'+'a'*64}
    with pytest.raises(ValueError):
        RepairExperiment.model_validate(experiment_input)


def test_start_stores_pending_profile_and_keeps_configs_unchanged(w9_case, experiment_input, tmp_path):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session
    task, _, _ = w9_case
    path = ROOT/'configs/m2/variants/A0.json'
    before = path.read_bytes()
    session = start_session(task, RepairPolicy(), 'fake', tmp_path/'runs', experiment=experiment_input)
    saved = json.loads((session.run.directory/'session.json').read_text())
    record = json.loads(session.run.path.read_text())
    assert saved['experiment'] == record['experiment']
    assert record['experiment']['variant_id'] == 'A0' and record['experiment']['arm'] == 'bm25'
    assert record['complete'] is False
    assert RepairSession.load(session.run.directory).experiment.policy_hash == record['experiment']['policy_hash']
    assert path.read_bytes() == before and json.loads(before)['arm'] is None


@pytest.mark.parametrize('fault', ['hash', 'arm', 'missing_state', 'missing_record', 'policy', 'null_state'])
def test_reload_rejects_inconsistent_profile_before_any_write(w9_case, experiment_input, tmp_path, fault):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session
    session = start_session(w9_case[0], RepairPolicy(), 'fake', tmp_path/'runs', experiment=experiment_input)
    state_path = session.run.directory/'session.json'
    state, record = json.loads(state_path.read_text()), json.loads(session.run.path.read_text())
    if fault == 'hash':
        state['experiment']['policy_hash'] = 'sha256:'+'f'*64
    elif fault == 'arm':
        state['experiment']['arm'] = 'graph'
    elif fault == 'missing_state':
        state.pop('experiment')
    elif fault == 'null_state':
        state['experiment'] = None
    elif fault == 'missing_record':
        record.pop('experiment')
    else:
        state['experiment']['variant_policy']['required_checks'] = ['tests', 'ruff']
    state_path.write_text(json.dumps(state), encoding='utf-8')
    session.run.path.write_text(json.dumps(record), encoding='utf-8')
    before = state_path.read_bytes(), session.run.path.read_bytes()
    with pytest.raises(ValueError):
        RepairSession.load(session.run.directory)
    assert (state_path.read_bytes(), session.run.path.read_bytes()) == before


def test_legacy_has_no_experiment_keys_and_still_loads(w9_case, tmp_path):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session
    session = start_session(w9_case[0], RepairPolicy(), 'fake', tmp_path/'runs')
    assert 'experiment' not in session.state and 'experiment' not in session.run.record
    assert RepairSession.load(session.run.directory).experiment is None


def test_deleting_both_pending_experiments_cannot_downgrade_to_legacy(w9_case, experiment_input, tmp_path):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session
    session = start_session(w9_case[0], RepairPolicy(), 'fake', tmp_path/'runs', experiment=experiment_input)
    state_path = session.run.directory/'session.json'
    state, record = json.loads(state_path.read_text()), json.loads(session.run.path.read_text())
    state.pop('experiment')
    record.pop('experiment')
    state_path.write_text(json.dumps(state), encoding='utf-8')
    session.run.path.write_text(json.dumps(record), encoding='utf-8')
    before = state_path.read_bytes(), session.run.path.read_bytes()
    with pytest.raises(ValueError):
        RepairSession.load(session.run.directory)
    assert (state_path.read_bytes(), session.run.path.read_bytes()) == before


@pytest.mark.parametrize('fault', ['both_experiments', 'record_hash_changed', 'record_hash_missing', 'state_hash_missing'])
def test_prepared_baseline_binding_is_required_before_reload_write(w9_case, experiment_input, tmp_path, fault):
    from vgar.repair import session as steps
    from vgar.repair.contracts import RepairPolicy
    task, count, tokenizer = w9_case
    session = steps.start_session(task, RepairPolicy(), 'fake', tmp_path/'runs',
        temp_root=tmp_path/'temp', experiment=experiment_input)
    assert steps.prepare(session, count, tokenizer) is not None
    state_path = session.run.directory/'session.json'
    state, record = json.loads(state_path.read_text()), json.loads(session.run.path.read_text())
    if fault == 'both_experiments':
        state.pop('experiment')
        record.pop('experiment')
    elif fault == 'record_hash_changed':
        record['stages']['baseline']['variant_policy_hash'] = 'sha256:'+'a'*64
    elif fault == 'record_hash_missing':
        record['stages']['baseline'].pop('variant_policy_hash')
    else:
        state['baseline'].pop('variant_policy_hash')
    state_path.write_text(json.dumps(state), encoding='utf-8')
    session.run.path.write_text(json.dumps(record), encoding='utf-8')
    before = state_path.read_bytes(), session.run.path.read_bytes()
    try:
        with pytest.raises(ValueError):
            steps.RepairSession.load(session.run.directory)
        assert (state_path.read_bytes(), session.run.path.read_bytes()) == before
    finally:
        # Only the original verified in-memory owner is allowed to clean this test lease.
        steps.finish(session)


@pytest.mark.parametrize('variant_id,arm,want', [('A0', 'bm25', 'PASS'), ('A1', 'graph', 'PASS'), ('A2', 'graph', 'FAIL')])
def test_real_pipeline_applies_effective_policy_and_preserves_raw_static(w9_case, tmp_path, variant_id, arm, want):
    from vgar.models.generator import FakeGenerator
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.evidence import digest
    from vgar.repair.pipeline import run_repair
    task, count, tokenizer = w9_case
    definition = json.loads((ROOT/f'configs/m2/variants/{variant_id}.json').read_text())
    run = run_repair(task, RepairPolicy(), FakeGenerator(DEBT_FIX), None, tmp_path/'runs',
        m1_counter=count, tokenizer=tokenizer, temp_root=tmp_path/'temp',
        experiment={'variant_policy': definition, 'arm': arm})
    record = json.loads(run.path.read_text())
    assert record['status'] == want, record.get('error_detail')
    assert record['stages']['verification']['static']['mypy']['status'] == 'FAIL'
    assert record['stages']['baseline']['variant_policy_hash'] == record['experiment']['policy_hash']
    assert record['original_source_unchanged'] is True
    bundle = json.loads((run.directory/'evidence_bundle.json').read_text())
    assert bundle['metadata']['experiment'] == record['experiment']
    assert bundle['metadata']['canonical_sha256'] == digest(run.path.read_bytes())
    assert record['experiment']['bundle_hashes'] == record['stages']['context']['hashes']
    assert bundle['recommendation'] == ('ACCEPT' if want == 'PASS' else 'REVISE')


def test_context_error_retains_valid_profile_without_creating_workspace(w9_case, experiment_input, tmp_path):
    from vgar.models.generator import FakeGenerator
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.pipeline import run_repair
    experiment_input['expected_hashes'] = {name: 'sha256:'+'a'*64 for name in
        ('context.json', 'context_manifest.json', 'test_links.json')}
    task, count, tokenizer = w9_case
    run = run_repair(task, RepairPolicy(), FakeGenerator(FIX), None, tmp_path/'runs',
        m1_counter=count, tokenizer=tokenizer, temp_root=tmp_path/'work', experiment=experiment_input)
    assert run.record['status'] == 'ERROR'
    assert run.record['experiment']['variant_id'] == 'A0'
    assert run.record['stages']['workspace']['status'] == 'NOT_RUN'
    assert run.record['stages']['generation']['status'] == 'NOT_RUN'


def test_early_baseline_error_without_policy_hash_remains_loadable(w9_case, experiment_input, tmp_path):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session
    task, _, _ = w9_case
    session = start_session(task, RepairPolicy(), 'fake', tmp_path/'runs', experiment=experiment_input)
    session.run.stage('baseline', {'status': 'ERROR', 'complete': False, 'reason': 'interrupted before capture'})
    session.state['outcome'] = ['ERROR', 'INTERNAL_ERROR']
    session.save()
    loaded = RepairSession.load(session.run.directory)
    assert loaded.experiment.policy_hash == session.experiment.policy_hash
    assert loaded.state['baseline'] is None
