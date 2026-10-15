"""Structural controller tests; simulated records NEVER count as real repairs."""
import json
from pathlib import Path

import pytest

from test_bootstrap import api
from test_acceptance_campaign import simulated_record

A, B, C = 'single_file_login', 'multi_file_invoice', 'missing_links'
V5, V6 = 'm2-w78-v5', 'm2-w78-v6'


def entry(case=B, status='PASS', version=V5, phase='tuning_B'):
    return dict(task_id=case, status=status, version=version, phase=phase, complete=True)


def test_retry_needs_new_revision_and_clean_final_requires_all_three():
    step = api('adaptive_campaign').adaptive_step
    assert step([])['next']['require_new_prompt'] is True
    history = [entry(status='FAIL')]
    assert step(history)['next']['task_id'] == B
    with pytest.raises(ValueError, match='revision|version'):
        step(history + [entry()])
    history += [entry(version=V6), entry(C, version=V6, phase='tuning_C')]
    assert step(history)['next'] == dict(task_id=A, phase='final', version=V6, require_new_prompt=False)
    history += [entry(case, version=V6, phase='final') for case in (A, B, C)]
    assert step(history)['status'] == 'PASS'
    assert step(history)['final_version'] == V6
    with pytest.raises(ValueError):
        step(history + [entry(C, version=V6, phase='final')])


def test_four_b_failures_move_to_c_with_new_revision_not_fifth_b():
    step = api('adaptive_campaign').adaptive_step
    history = [entry(status='FAIL', version=f'm2-w78-v{5+i}') for i in range(4)]
    assert step(history)['next']['task_id'] == C
    assert step(history)['next']['require_new_prompt'] is True
    with pytest.raises(ValueError):
        step(history + [entry(version='m2-w78-v9')])
    history += [entry(C, version='m2-w78-v9', phase='tuning_C')]
    assert step(history)['status'] == 'FAIL' and step(history)['next'] is None


def test_eleven_slots_are_separate_quotas_and_final_never_adapts():
    step = api('adaptive_campaign').adaptive_step
    history = [entry(status='FAIL' if i < 3 else 'PASS', version=f'm2-w78-v{5+i}') for i in range(4)]
    history += [entry(C, status='FAIL' if i < 3 else 'PASS', version=f'm2-w78-v{8+i}', phase='tuning_C') for i in range(4)]
    history += [entry(A, status='FAIL', version='m2-w78-v11', phase='final')]
    assert step(history)['next']['task_id'] == B
    with pytest.raises(ValueError, match='version|revision'):
        step(history + [entry(B, version='m2-w78-v12', phase='final')])
    history += [entry(case, version='m2-w78-v11', phase='final') for case in (B, C)]
    assert len(history) == 11 and step(history)['status'] == 'FAIL'


def test_runtime_error_and_c_exhaustion_stop_not_prompt_retry():
    step = api('adaptive_campaign').adaptive_step
    assert step([entry(status='ERROR')])['status'] == 'ERROR'
    history = [entry()] + [entry(C, 'FAIL', f'm2-w78-v{5+i}', 'tuning_C') for i in range(4)]
    assert step(history)['next'] is None and step(history)['status'] == 'FAIL'


@pytest.fixture
def store(tmp_path, monkeypatch):
    prompt = api('prompt')
    monkeypatch.setattr(prompt, 'ROOT', tmp_path)
    (tmp_path / 'prompts').mkdir()
    (tmp_path / 'prompts/repair_v5.txt').write_text('Generic instructions, no fixture solution.\n', encoding='utf-8')
    return api('adaptive_campaign').AdaptiveCampaignStore.create(tmp_path / 'campaign', {'files': {}})


def finish_simulated(store, attempt, status='PASS', *, finish=True):
    evidence = api('evidence')
    path = simulated_record(Path(attempt['run_root']) / 'simulated', attempt['task_id'], attempt['version'],
        store.state['campaign_id'], attempt['attempt_id'], status=status)
    record = json.loads(path.read_text(encoding='utf-8'))
    record.update(adaptive_phase=attempt['phase'], prompt_feedback=attempt['feedback'])
    record['stages']['prompt']['template_hash'] = store.state['revisions'][attempt['version']]['template_hash']
    evidence.atomic_json(path, record)
    bundle_path = path.parent / 'evidence_bundle.json'
    bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
    bundle['metadata']['canonical_sha256'] = evidence.digest(path.read_bytes())
    evidence.atomic_json(bundle_path, bundle)
    if finish:
        store.finish(path)
    return path


def test_revision_reservation_resume_and_terminal_gate_tamper(store):
    module = api('adaptive_campaign')
    with store.session():
        with pytest.raises(RuntimeError, match='prompt|revision'):
            store.reserve()
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        attempt = store.reserve()
        with pytest.raises(RuntimeError, match='Pending|pending'):
            store.reserve()
        path = finish_simulated(store, attempt)
    resumed = module.AdaptiveCampaignStore.open(store.directory)
    assert resumed.decision()['next']['task_id'] == C
    ledger = json.loads(store.path.read_text(encoding='utf-8'))
    ledger['attempts'][0]['status'] = 'FAIL'
    api('evidence').atomic_json(store.path, ledger)
    with pytest.raises(ValueError, match='canonical|ledger'):
        module.AdaptiveCampaignStore.open(store.directory)
    assert path.exists()


def test_prompt_file_tamper_blocks_resume(store):
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
    api('prompt').template_path(V5).write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='prompt|revision|changed'):
        api('adaptive_campaign').AdaptiveCampaignStore.open(store.directory)


def test_pending_owner_live_does_not_retry_and_dead_owner_consumes_slot(store, monkeypatch):
    module = api('adaptive_campaign')
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        attempt = store.reserve()
    resumed = module.AdaptiveCampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.recover_pending() == 'LIVE'
        assert resumed.next_action()['action'] == 'PENDING'
    monkeypatch.setattr(module, 'process_identity', lambda pid: None)
    with resumed.session():
        assert resumed.recover_pending() == 'RECOVERED'
        assert resumed.decision()['status'] == 'ERROR'
        assert len(resumed.state['attempts']) == 1
        with pytest.raises(RuntimeError):
            resumed.reserve()
    assert attempt['number'] == 1


def test_concurrent_owner_and_changed_runtime_block(store):
    other = api('adaptive_campaign').AdaptiveCampaignStore.open(store.directory)
    with store.session():
        with pytest.raises(RuntimeError, match='owner|locked'):
            with other.session():
                pass


def test_failure_requires_fresh_registered_revision_and_feedback_is_same_case(store):
    module = api('adaptive_campaign')
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        first = store.reserve()
        path = finish_simulated(store, first, 'FAIL')
        with pytest.raises(RuntimeError, match='prompt|revision'):
            store.reserve()
        next_file = api('prompt').ROOT / 'prompts/repair_v6.txt'
        next_file.write_text('Revised generic hunk instructions.\n', encoding='utf-8')
        store.register(V6, 'Observed apply failure', 'Fix absolute vs local numbering')
        second = store.reserve()
        assert second['feedback']['task_id'] == B
        assert second['feedback']['source_run_id'] == 'simulated'
        assert second['version'] == V6
        finish_simulated(store, second)
        third = store.reserve()
        assert third['task_id'] == C and third['feedback'] is None
    assert path.exists() and module is not None


def test_interrupted_registration_is_reconciled_without_deleting_or_counting_attempt(store, monkeypatch):
    module = api('adaptive_campaign')
    write = module.atomic_json
    def fail_ledger(path, data):
        if Path(path) == store.path:
            raise OSError('injected interruption after registration file')
        return write(path, data)
    with store.session():
        monkeypatch.setattr(module, 'atomic_json', fail_ledger)
        with pytest.raises(OSError):
            store.register(V5, 'Initial approved design', 'Absolute source coordinates')
    monkeypatch.setattr(module, 'atomic_json', write)
    resumed = module.AdaptiveCampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.recover_pending() == 'RECOVERED_REGISTRATION'
        assert list(resumed.state['revisions']) == [V5]
        assert resumed.reserve()['number'] == 1


def test_attempt_is_durable_before_directory_setup_and_interruption_consumes_slot(store, monkeypatch):
    module = api('adaptive_campaign')
    mkdir = Path.mkdir
    def fail_attempt_directory(path, *args, **kwargs):
        if path == store.directory / 'attempts/01':
            raise OSError('injected interruption before attempt directory')
        return mkdir(path, *args, **kwargs)
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        monkeypatch.setattr(Path, 'mkdir', fail_attempt_directory)
        with pytest.raises(OSError):
            store.reserve()
    ledger = json.loads(store.path.read_text(encoding='utf-8'))
    assert len(ledger['attempts']) == 1 and not ledger['attempts'][0]['complete']
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    monkeypatch.setattr(module, 'process_identity', lambda pid: None)
    resumed = module.AdaptiveCampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.recover_pending() == 'RECOVERED'
        assert resumed.state['status'] == 'ERROR'
        assert len(resumed.state['attempts']) == 1


def test_renamed_identical_parent_template_does_not_register_or_consume_attempt(store):
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        finish_simulated(store, store.reserve(), 'FAIL')
        (api('prompt').ROOT / 'prompts/repair_v6.txt').write_bytes(api('prompt').template_path(V5).read_bytes())
        with pytest.raises(ValueError, match='identical|unchanged'):
            store.register(V6, 'Only renamed', 'Claimed improvement')
        assert list(store.state['revisions']) == [V5]
        assert len(store.state['attempts']) == 1


def test_cli_recovered_terminal_pass_returns_pass_without_reserving_or_generating(store, monkeypatch):
    import importlib.util
    script_path = Path(__file__).resolve().parents[1] / 'scripts/run_adaptive_acceptance.py'
    spec = importlib.util.spec_from_file_location('adaptive_cli_recovery', script_path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    with store.session():
        store.register(V5, 'Initial approved design', 'Absolute source coordinates')
        for _ in range(4):
            finish_simulated(store, store.reserve())
        last = store.reserve()
        finish_simulated(store, last, finish=False)
    monkeypatch.setattr(api('adaptive_campaign'), 'process_identity', lambda pid: None)
    assert script.run_next(store) == 0
    assert store.state['status'] == 'PASS' and len(store.state['attempts']) == 5
    assert not list(store.directory.rglob('model-workers'))
