import json
from types import SimpleNamespace

import pytest

from conftest import CharacterChatTokenizer
from test_bootstrap import api


def test_b_acceptance_rejects_missing_provenance_and_real_diagnostics(tmp_path):
    path = tmp_path/'run_record.json'
    api('evidence').atomic_json(path, dict(status='PASS', mode='real', stages={}))
    errors = api('b_acceptance').audit_b_pass(path, {'model': {}, 'task': {}, 'policy': {}, 'runtime_root': str(tmp_path)}, {})
    assert 'REAL_GENERATION_DIAGNOSTICS' in errors and 'CLEANUP_INCOMPLETE' in errors


def test_pipeline_guard_runs_before_any_generation(m1_case, tmp_path):
    task, counter = m1_case
    def reject(run, prompt):
        raise ValueError('Duplicate unchanged real generation is forbidden')
    generator = SimpleNamespace(mode='fake', generate=lambda *a: pytest.fail('Generation passed rejected guard'))
    result = api('pipeline').run_repair(task, api('contracts').RepairPolicy(), generator, None,
        tmp_path/'runs', m1_counter=counter, tokenizer=CharacterChatTokenizer(),
        temp_root=tmp_path/'temp', before_generation=reject)
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['status'] == 'ERROR'
    assert record['stages']['generation']['status'] == 'NOT_RUN'
    assert 'Duplicate' in record['error_detail']['message']
