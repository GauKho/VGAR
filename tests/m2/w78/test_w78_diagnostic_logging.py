import json
import sys

import pytest

from w78_support import CharacterChatTokenizer
from vgar.repair import static_checks as m_checks
from vgar.repair import contracts as m_contracts
from vgar.repair import diagnostics as m_diagnostics
from vgar.repair import executor as m_executor
from vgar.models import generator as m_generator
from vgar.models.huggingface import model_worker as m_model_worker
from vgar.repair import patch as m_patch
from vgar.repair import pipeline as m_pipeline
from vgar.repair import test_runner as m_test_runner


BASE = '--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n def answer():\n-    return 1\n+    return 2\n'


@pytest.mark.parametrize('raw,line,expected,actual,complete', [
    (BASE, 5, {'old': 1, 'new': 1}, {'old': 2, 'new': 2}, True),
    (BASE.replace('-1,1 +1,1', '-1,3 +1,3'), 7, {'old': 3, 'new': 3}, {'old': 2, 'new': 2}, True),
    (BASE.replace(' def answer()', 'def answer()'), 4, {'old': 1, 'new': 1}, {'old': 1, 'new': 1}, False),
    ('```diff\n' + BASE + '```\n', 6, {'old': 1, 'new': 1}, {'old': 2, 'new': 2}, True),
])
def test_parser_reports_raw_location_and_complete_hunk_counts(raw, line, expected, actual, complete):
    module = m_patch
    with pytest.raises(ValueError) as caught:
        module.parse_unified_diff(raw, module.PatchPolicy(('app.py',), ('tests',)))
    d = caught.value.parser_diagnostics
    assert d['raw_line'] == line and d['path'] == 'app.py' and d['hunk_index'] == 1
    assert d['expected_counts'] == expected and d['actual_counts'] == actual
    assert d['counts_complete'] is complete
    if not complete:
        assert d['invalid_body_lines'][0]['raw_line'] == 4


def test_unapproved_path_reports_header_not_a_nonexistent_hunk():
    module = m_patch
    with pytest.raises(ValueError, match='Protected or unapproved path') as caught:
        module.parse_unified_diff(BASE.replace('app.py', 'tests/test_app.py'), module.PatchPolicy(('app.py',), ('tests',)))
    d = caught.value.parser_diagnostics
    assert d['raw_line'] == 1 and d['path'] == 'tests/test_app.py'
    assert d['hunk_index'] is None and d['expected_counts'] is None


@pytest.mark.parametrize('removed,added', [('-- old', '++ new'), ('-- a/name', '++ b/name')])
def test_valid_header_like_body_is_not_mistaken_for_file_headers(removed, added):
    raw = ('--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-' + removed +
           '\n+' + added + '\n context\ntrailing junk\n')
    module = m_patch
    with pytest.raises(ValueError) as caught:
        module.parse_unified_diff(raw, module.PatchPolicy(('app.py',), ()))
    d = caught.value.parser_diagnostics
    assert d['raw_line'] == 7 and d['actual_counts'] == {'old': 2, 'new': 2}
    assert d['counts_complete'] is True


@pytest.mark.parametrize('raw,line', [
    ('--- a/app.py\n+++ wrong\n', 2),
    ('--- a/app.py\n+++ b/app.py\nNOT A HUNK\n', 3),
])
def test_header_and_missing_hunk_errors_point_to_offending_raw_line(raw, line):
    module = m_patch
    with pytest.raises(ValueError) as caught:
        module.parse_unified_diff(raw, module.PatchPolicy(('app.py',), ()))
    assert caught.value.parser_diagnostics['raw_line'] == line


def test_quoted_header_syntax_exception_keeps_type_and_gets_location():
    module = m_patch
    with pytest.raises(SyntaxError) as caught:
        module.parse_unified_diff('--- "a/app.py\n+++ b/app.py\n', module.PatchPolicy(('app.py',), ()))
    assert caught.value.parser_diagnostics['raw_line'] == 1


def test_pipeline_persists_parser_diagnostics_and_traceback(m1_case, tmp_path):
    task, counter = m1_case
    run = m_pipeline.run_repair(task, m_contracts.RepairPolicy(),
        m_generator.FakeGenerator('not a diff'), None, tmp_path/'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path/'temp')
    r = json.loads(run.path.read_text(encoding='utf-8'))
    assert r['status'] == 'FAIL' and r['reason'] == 'PATCH_PARSE_ERROR'
    error = r['error_detail']
    assert error['parser_diagnostics']['raw_line'] == 1
    assert 'Traceback (most recent call last)' in error['traceback']
    assert 'parse_unified_diff' in error['traceback'] and 'ValueError:' in error['traceback']
    assert r['stages']['parse_patch']['traceback'] == error['traceback'] or 'parse_unified_diff' in r['stages']['parse_patch']['traceback']
    assert r['stages']['apply']['status'] == 'NOT_RUN' and r['original_source_unchanged']


def test_command_launch_exception_preserves_traceback(tmp_path):
    result = m_executor.run_bounded((str(tmp_path/'missing-python.exe'),), tmp_path, 2)
    assert result['status'] == 'ERROR' and not result['complete']
    assert 'FileNotFoundError' in result['traceback'] and 'run_bounded' in result['traceback']


def test_chained_exception_logs_frames_without_locals():
    secret_local = 'do-not-log-locals'
    try:
        try:
            raise ValueError('inner')
        except ValueError as error:
            raise RuntimeError('outer') from error
    except RuntimeError as error:
        result = m_diagnostics.exception_details(error)
    assert 'ValueError: inner' in result['traceback'] and 'RuntimeError: outer' in result['traceback']
    assert secret_local not in result['traceback']
    assert result['type'] == 'RuntimeError' and result['message'] == 'outer'


def test_cli_config_error_has_traceback(tmp_path):
    import subprocess
    result = subprocess.run([sys.executable, '-m', 'vgar.cli', 'repair', '--mode', 'fake',
        '--task', str(tmp_path/'missing-task.json'), '--output-root', str(tmp_path/'runs')],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    saved = json.loads(next((tmp_path/'runs').glob('*/run_record.json')).read_text(encoding='utf-8'))
    assert 'FileNotFoundError' in saved['traceback'] and saved['status'] == 'ERROR'


def test_worker_error_response_keeps_its_original_traceback(tmp_path):
    response = tmp_path/'response.json'
    code = ("import json, traceback; from pathlib import Path\n"
            "try:\n    raise RuntimeError('worker exploded')\n"
            "except RuntimeError:\n    " +
            f"Path({str(response)!r}).write_text(json.dumps(dict(status='ERROR', reason='worker exploded', "
            "traceback=traceback.format_exc())), encoding='utf-8')\n"
            "raise SystemExit(2)")
    result = m_model_worker.invoke_worker((sys.executable, '-c', code), tmp_path, response, 10)
    assert result['status'] == 'ERROR' and result['command']['exit_code'] == 2
    assert 'RuntimeError: worker exploded' in result['response']['traceback']


def test_syntax_failure_retains_traceback(tmp_path):
    from types import SimpleNamespace
    (tmp_path/'app.py').write_text('def broken(:', encoding='utf-8')
    lease = SimpleNamespace(path=tmp_path, private=tmp_path)
    executor = SimpleNamespace(run=lambda *args: dict(status='PASS'))
    result = m_checks.run_static_checks(lease, ('app.py',), m_contracts.RepairPolicy(), executor)
    assert result['syntax']['status'] == 'FAIL'
    assert 'SyntaxError' in result['syntax']['exception']['traceback']


def test_missing_pytest_artifact_retains_traceback(tmp_path):
    from types import SimpleNamespace
    lease = SimpleNamespace(path=tmp_path, private=tmp_path)
    executor = SimpleNamespace(run=lambda *args: dict(status='ERROR', complete=False, exit_code=2))
    result = m_test_runner.collect_tests(lease, ('tests',), executor)
    assert result['status'] == 'ERROR' and result['reason'] == 'VERIFICATION_INCOMPLETE'
    assert 'FileNotFoundError' in result['exception']['traceback']
