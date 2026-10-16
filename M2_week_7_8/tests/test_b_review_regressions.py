"""Reproduce the pre-inference review findings without loading model weights."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_b_experiment import ready, setup_store, fail_record
from test_bootstrap import api


@pytest.mark.parametrize('field,value', [('status', 'PASS'), ('elapsed_seconds', 0)])
def test_reload_rejects_changed_terminal_outcome_or_time(tmp_path, field, value):
    module, store, _, _, _ = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        store.finish(fail_record(store, entry).path)
    state = json.loads(store.path.read_text(encoding='utf-8'))
    state['attempts'][0][field] = value
    state.update({k:v for k,v in module.b_decision(state['attempts']).items() if k != 'next'})
    api('evidence').atomic_json(store.path, state)
    with pytest.raises(ValueError, match='Historical|outcome|accounting'):
        module.BExperimentStore.open(store.directory)


def test_protected_input_changed_after_reserve_is_terminal_integrity(tmp_path):
    _, store, _, _, protected = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        protected.write_bytes(b'changed during run')
        store.finish(fail_record(store, entry).path)
    assert store.state['stop_reason'] == 'UNRESOLVED_INTEGRITY'
    assert 'PROTECTED_INPUT_CHANGED_DURING_RUN' in entry['gate_errors']


def test_protected_input_checked_before_generation(tmp_path):
    _, store, _, _, protected = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        protected.write_bytes(b'changed during preflight')
        with pytest.raises(ValueError, match='Frozen'):
            store.bind_prompt(SimpleNamespace(record={}, save=lambda: None),
                SimpleNamespace(prompt_hash='prompt', template_hash=entry['template_hash'], input_tokens=12))


@pytest.mark.parametrize('registration', ['runtime', 'prompt'])
def test_registration_can_recover_after_campaign_save_crash(tmp_path, monkeypatch, registration):
    module, store, _, proof, _ = setup_store(tmp_path)
    if registration == 'prompt':
        with store.session():
            store.register_runtime('initial', proof)
    def register():
        if registration == 'runtime':
            store.register_runtime('initial', proof)
        else:
            store.register_prompt('m2-w78-v10', 'initial prompt')
    with store.session():
        with monkeypatch.context() as patch:
            patch.setattr(store, '_save', lambda: (_ for _ in ()).throw(OSError('injected save crash')))
            with pytest.raises(OSError, match='injected'):
                register()
    store = module.BExperimentStore.open(store.directory)
    with store.session():
        register()
    assert len(store.state['runtimes' if registration == 'runtime' else 'prompts']) == 1


def test_reservation_is_saved_before_directory_creation(tmp_path, monkeypatch):
    module, store, _, _, _ = ready(tmp_path)
    original = Path.mkdir
    def fail_attempt_directory(path, *args, **kwargs):
        if path.name == '01' and path.parent.name == 'attempts':
            raise OSError('injected mkdir crash')
        return original(path, *args, **kwargs)
    with store.session(), monkeypatch.context() as patch:
        patch.setattr(Path, 'mkdir', fail_attempt_directory)
        with pytest.raises(OSError, match='injected'):
            store.reserve()
    recovered = module.BExperimentStore.open(store.directory)
    assert len(recovered.state['attempts']) == 1
    monkeypatch.setattr(module, 'process_identity', lambda pid: None)
    with recovered.session():
        assert recovered.recover_pending() == 'RECOVERED'
    assert recovered.state['attempts'][0]['status'] == 'ERROR'


def test_pipeline_shaped_integrity_error_stops_not_runtime_retry():
    result = api('b_experiment').diagnose(dict(status='ERROR', reason='FINALIZATION_ERROR',
        original_source_unchanged=False, integrity_error='Original source changed', error_detail={}))
    assert result['category'] == 'integrity' and result['action'] == 'STOP'


def test_absolute_reservation_deadline_is_not_restarted(tmp_path):
    module, store, _, _, _ = ready(tmp_path)
    with store.session():
        entry = store.reserve()
        deadline = module.reservation_deadline(entry)
        assert 0 < deadline - module.time.monotonic() <= entry['timeout_seconds']
        old = dict(entry, started_utc='2020-01-01T00:00:00+00:00')
        assert module.reservation_deadline(old) < module.time.monotonic()


def test_crlf_prompt_is_rejected_before_any_attempt_is_reserved(tmp_path):
    _, store, root, proof, _ = setup_store(tmp_path)
    (root/'prompts/repair_v10.txt').write_bytes(b'neutral\r\nformat\r\n')
    with store.session():
        store.register_runtime('initial', proof)
        with pytest.raises(ValueError, match='LF|line ending'):
            store.register_prompt('m2-w78-v10', 'unsupported CRLF')
    assert store.state['attempts'] == []


def test_expired_absolute_deadline_blocks_pipeline_generation(m1_case, tmp_path):
    from conftest import CharacterChatTokenizer
    import time
    task, counter = m1_case
    generator = SimpleNamespace(mode='fake', generate=lambda *a: pytest.fail('Expired run generated'))
    result = api('pipeline').run_repair(task, api('contracts').RepairPolicy(), generator, None,
        tmp_path/'runs', m1_counter=counter, tokenizer=CharacterChatTokenizer(),
        temp_root=tmp_path/'temp', deadline=time.monotonic()-1)
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['status'] == 'ERROR'
    assert record['stages']['generation']['status'] == 'NOT_RUN'
