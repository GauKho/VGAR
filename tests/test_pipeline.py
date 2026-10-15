import json
from conftest import CharacterChatTokenizer
from test_bootstrap import api

FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


def test_one_pass_real_checks_with_explicit_fake_generation(m1_case, tmp_path):
    task, counter = m1_case
    result = api('pipeline').run_repair(task, api('contracts').RepairPolicy(),
        api('generator').FakeGenerator(FIX), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['status'] == 'PASS' and record['mode'] == 'fake'
    assert record['original_source_unchanged']
    assert record['stages']['verification']['tests']['outcomes']['tests/test_auth.py::test_login_rejects_whitespace'] == 'PASS'
    assert (result.directory / 'evidence_bundle.json').is_file()
    assert (result.directory / 'applied.diff').is_file()
    assert b'return bool(value)' in (task.source_repo / 'auth.py').read_bytes()


def test_invalid_diff_is_fail_with_late_checks_not_run(m1_case, tmp_path):
    task, counter = m1_case
    result = api('pipeline').run_repair(task, api('contracts').RepairPolicy(),
        api('generator').FakeGenerator('not a diff'), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    record = json.loads(result.path.read_text(encoding='utf-8'))
    assert record['status'] == 'FAIL' and record['reason'] == 'PATCH_PARSE_ERROR'
    assert record['stages']['verification']['status'] == 'NOT_RUN'
    assert not (result.directory / 'applied.diff').exists()

