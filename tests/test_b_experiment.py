"""Durable B-only experiment gates; simulated records never count as real repair."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_bootstrap import api


def setup_store(tmp_path):
    module = api('b_experiment')
    runtime = tmp_path/'project'
    (runtime/'src').mkdir(parents=True)
    (runtime/'src/runtime.py').write_bytes(b'value = 1\n')
    (runtime/'prompts').mkdir()
    for n in (10, 11):
        (runtime/'prompts'/f'repair_v{n}.txt').write_bytes(f'neutral version {n}\n'.encode())
    protected = tmp_path/'protected.py'
    protected.write_bytes(b'protected\n')
    snapshot = dict(task_id='multi_file_invoice', runtime_root=str(runtime),
        task={'task_id': 'multi_file_invoice'}, model={}, policy={},
        files={str(protected): api('evidence').digest(protected.read_bytes())})
    store = module.BExperimentStore.create(tmp_path/'experiment', snapshot)
    proof = tmp_path/'tests.json'
    fp = module.runtime_fingerprint(runtime)
    api('evidence').atomic_json(proof, dict(status='PASS', complete=True, mode='offline',
        runtime_before=fp, runtime_after=fp,
        stages={'pytest': {'status': 'PASS', 'complete': True, 'exit_code': 0, 'argv': ['python', '-m', 'pytest', 'tests']}}))
    return module, store, runtime, proof, protected


def ready(tmp_path):
    module, store, root, proof, protected = setup_store(tmp_path)
    with store.session():
        store.register_runtime('initial qualified runtime', proof)
        store.register_prompt('m2-w78-v10', 'approved neutral prompt')
    return module, store, root, proof, protected


def fail_record(store, entry, *, reason='PATCH_PARSE_ERROR', status='FAIL'):
    run = api('evidence').begin_run(Path(entry['run_root']), 'unit-test-double', mode='real',
        task_id='multi_file_invoice', campaign_id=store.state['campaign_id'], attempt_id=entry['attempt_id'],
        runtime_revision=entry['runtime_revision'], policy={'prompt_version': entry['version']})
    run.finish(status, reason=reason, error_detail={'message': 'unit-test failure'},
        stages={'parse_patch': {'status': 'ERROR'}})
    return run


def test_b_store_has_durable_cap_and_requires_new_revision(tmp_path):
    module, store, _, _, _ = ready(tmp_path)
    for index in range(8):
        with store.session():
            if index:
                version = 'm2-w78-v' + str(10 + index)
                path = Path(store.frozen['runtime_root'])/'prompts'/f'repair_v{10+index}.txt'
                if not path.exists():
                    path.write_text('neutral-' + str(index), encoding='utf-8')
                store.register_prompt(version, 'different instruction hypothesis', trigger=store.state['attempts'][-1]['record'])
            entry = store.reserve()
            store.finish(fail_record(store, entry).path)
        store = module.BExperimentStore.open(store.directory)
    assert len(store.state['attempts']) == 8
    with store.session(), pytest.raises(RuntimeError, match='budget|terminal'):
        store.reserve()


def test_b_runtime_changes_are_explicit_and_archived(tmp_path):
    module, store, root, proof, _ = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        store.finish(fail_record(store, entry, status='ERROR', reason='INTERNAL_ERROR').path)
    (root/'src/runtime.py').write_bytes(b'value = 2\n')
    with store.session(), pytest.raises(ValueError, match='runtime|Runtime'):
        store.reserve()
    fp = module.runtime_fingerprint(root)
    data = json.loads(proof.read_text(encoding='utf-8'))
    data.update(runtime_before=fp, runtime_after=fp)
    api('evidence').atomic_json(proof, data)
    with store.session():
        store.register_runtime('fix proven local runtime bug', proof, trigger=store.state['attempts'][-1]['record'])
        new = store.reserve()
        assert new['version'] == entry['version'] and new['runtime_revision'] != entry['runtime_revision']
        store.finish(fail_record(store, new).path)
    assert len(module.BExperimentStore.open(store.directory).state['runtimes']) == 2


def test_b_protected_change_and_prompt_tamper_fail_closed(tmp_path):
    _, store, root, _, protected = ready(tmp_path)
    protected.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Frozen|protected'):
        type(store).open(store.directory)
    protected.write_bytes(b'protected\n')
    (root/'prompts/repair_v10.txt').write_bytes(b'tampered')
    with store.session(), pytest.raises(ValueError, match='prompt|Prompt'):
        store.reserve()


def test_b_pending_owner_is_not_restarted_and_dead_recovery_consumes_slot(tmp_path, monkeypatch):
    module, store, _, _, _ = ready(tmp_path)
    with store.session():
        store.reserve()
        assert store.recover_pending() == 'LIVE'
        with pytest.raises(RuntimeError, match='Pending'):
            store.reserve()
    monkeypatch.setattr(module, 'process_identity', lambda pid: None)
    with store.session():
        assert store.recover_pending() == 'RECOVERED'
    assert store.state['attempts'][0]['status'] == 'ERROR'
    assert len(store.state['attempts']) == 1 and store.state['attempts'][0]['complete']


def test_b_duplicate_generation_is_blocked_before_second_generation(tmp_path):
    _, store, _, _, _ = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        store.bind_prompt(SimpleNamespace(record={}, save=lambda: None),
            SimpleNamespace(prompt_hash='same-input', template_hash=entry['template_hash'], input_tokens=12))
        store.finish(fail_record(store, entry).path)
        # Same prompt/runtime but changing feedback would be allowed only if
        # rendered input is actually different; identical input is rejected.
        second = store.reserve()
        with pytest.raises(ValueError, match='Duplicate'):
            store.bind_prompt(SimpleNamespace(record={}, save=lambda: None),
                SimpleNamespace(prompt_hash='same-input', template_hash=second['template_hash'], input_tokens=12))


@pytest.mark.parametrize('reason,want', [('PATCH_PARSE_ERROR','candidate'), ('PATCH_APPLY_FAILED','candidate'),
    ('TEST_FAILED','candidate'), ('INTERNAL_ERROR','runtime'), ('FINALIZATION_ERROR','runtime')])
def test_b_diagnosis_separates_candidate_and_runtime(reason, want):
    assert api('b_experiment').diagnose(dict(status='FAIL' if want == 'candidate' else 'ERROR',
        reason=reason, stages={}))['category'] == want


@pytest.mark.parametrize('gate,want', [('REAL_GENERATION_DIAGNOSTICS','runtime'),
    ('PUBLIC_SIGNATURE_CHANGED','candidate'), ('RUNTIME_CHANGED_DURING_RUN','integrity')])
def test_b_additive_gates_route_to_actual_cause_not_automatic_hard_stop(gate, want):
    assert api('b_experiment').diagnose_assessment({'status':'PASS','reason':None}, [gate])['category'] == want


def test_b_rejects_other_task_and_exhausted_time(tmp_path):
    module, store, _, _, _ = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        store.finish(fail_record(store, entry).path)
    # Use the same total-budget function the runner consumes, with a literal
    # elapsed boundary to test the refusal before any new model launch.
    assert module.b_decision([{'complete': True, 'status': 'FAIL', 'elapsed_seconds': 14400}])['complete']
    snapshot = dict(store.frozen, task_id='missing_links')
    with pytest.raises(ValueError, match='B|multi_file_invoice'):
        module.BExperimentStore.create(tmp_path/'not-b', snapshot)
