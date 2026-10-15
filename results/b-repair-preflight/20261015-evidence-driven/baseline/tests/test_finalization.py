import json
import pytest
from conftest import CharacterChatTokenizer
from test_bootstrap import api
from test_pipeline import FIX


def repair(m1_case, tmp_path):
    task, counter = m1_case
    return api('pipeline').run_repair(task, api('contracts').RepairPolicy(),
        api('generator').FakeGenerator(FIX), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')


@pytest.mark.parametrize('fault', ['bundle', 'cleanup'])
def test_terminal_record_never_passes_when_finalization_fails(m1_case, tmp_path, monkeypatch, fault):
    def broken(*args):
        raise OSError('injected ' + fault + ' failure')
    if fault == 'bundle':
        monkeypatch.setattr(api('pipeline'), '_project_bundle', broken)
    else:
        monkeypatch.setattr(api('workspace'), '_remove_owned', broken)
    result = repair(m1_case, tmp_path)
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['status'] == 'ERROR' and record['complete']
    assert record['reason'] == 'FINALIZATION_ERROR'
    assert fault in record['finalization_errors'][0]['message']


def test_bundle_hash_points_to_terminal_canonical_record(m1_case, tmp_path):
    result = repair(m1_case, tmp_path)
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['artifacts']['bundle'] == 'evidence_bundle.json'
    bundle = json.loads((result.directory / record['artifacts']['bundle']).read_text(encoding='utf-8'))
    assert bundle['metadata']['canonical_sha256'] == api('evidence').digest(result.path.read_bytes())


def test_regression_disappearing_or_skipping_is_incomplete():
    baseline = {'required_ids': ['fix'], 'tests': {'outcomes': {'fix': 'FAIL', 'regression': 'PASS'}}}
    for state in (None, 'SKIP', 'XFAIL', 'XPASS', 'ERROR'):
        post = {'status': 'PASS', 'outcomes': {'fix': 'PASS', 'regression': state}}
        status, reasons = api('verification').assess_transition(baseline, post)
        assert status == 'ERROR' and 'VERIFICATION_INCOMPLETE' in reasons
