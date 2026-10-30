"""Diagnostic parsing and multiset deltas; fixtures are synthetic, not benchmark results."""
import importlib
import json
from pathlib import Path

import pytest

from vgar.repair.evidence import digest

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures/m2_w9/diagnostics'


def api():
    return importlib.import_module('vgar.repair.static_diagnostics')


def command(tmp_path, tool='mypy', rows=None, **updates):
    if rows is None:
        raw = (FIXTURES / ('mypy.jsonl' if tool == 'mypy' else 'ruff.json')).read_text(encoding='utf-8')
    else:
        raw = ('\n'.join(json.dumps(r) for r in rows) if tool == 'mypy' else json.dumps(rows))
    scope = ['pkg/debt.py']
    result = {'cwd': str(tmp_path), 'status': 'FAIL', 'exit_code': 1,
              'stdout': raw, 'stderr': '', 'complete': True, 'timed_out': False,
              'output_truncated': False, 'diagnostic_context': {
                  'scope': scope, 'scope_hash': digest(json.dumps(scope, separators=(',', ':'))),
                  'config_hash': 'sha256:config', 'interpreter_ref': 'python-profile-test'}}
    result.update(updates)
    return result


def row(line=2, code='return-value', message='Old error', column=0):
    return {'file': 'pkg/debt.py', 'line': line, 'column': column,
            'message': message, 'code': code, 'severity': 'error'}


def report(tmp_path, rows, version='2.4.0'):
    return api().parse_tool_report('mypy', command(tmp_path, rows=rows,
        status='FAIL' if rows else 'PASS', exit_code=1 if rows else 0), version)


@pytest.mark.parametrize(('tool', 'version'), [('mypy', '2.4.0'), ('ruff', '0.17.0')])
def test_json_diagnostics_are_complete_not_tool_crashes(tmp_path, tool, version):
    parsed = api().parse_tool_report(tool, command(tmp_path, tool), version)
    assert parsed.execution_status == 'COMPLETE'
    assert len(parsed.diagnostics) == 1
    diagnostic = parsed.diagnostics[0]
    assert (diagnostic.path, diagnostic.line, diagnostic.column) == ('pkg/debt.py', 2, 12)
    assert diagnostic.code == ('return-value' if tool == 'mypy' else 'F821')


@pytest.mark.parametrize('updates', [
    {'stdout': 'not JSON'}, {'complete': False}, {'timed_out': True},
    {'output_truncated': True}, {'exit_code': 2}, {'stderr': 'internal tool error'},
    {'status': 'ERROR'}, {'stdout': '', 'exit_code': 1},
])
def test_incomplete_or_invalid_output_never_becomes_empty_pass(tmp_path, updates):
    parsed = api().parse_tool_report('mypy', command(tmp_path, **updates), '2.4.0')
    assert parsed.execution_status == 'ERROR'
    assert parsed.reason


NOQA_WARNINGS = (
    'warning: Invalid `# noqa` directive on django/template/base.py:58: expected a comma-separated list of '
    'codes (e.g., `# noqa: F401, F841`).\n'
    'warning: Invalid `# noqa` directive on sphinx/transforms/i18n.py:126: expected `:` followed by a '
    'comma-separated list of codes (e.g., `# noqa: F401, F841`).\n')


def test_ruff_invalid_noqa_warnings_in_repository_source_are_benign(tmp_path):
    # Seen on django-10914 / sphinx-10673 baselines (W10 stage 1): old-style noqa comments in the repo.
    parsed = api().parse_tool_report('ruff', command(tmp_path, 'ruff', stderr=NOQA_WARNINGS), '0.17.0')
    assert parsed.execution_status == 'COMPLETE' and len(parsed.diagnostics) == 1


@pytest.mark.parametrize(('tool', 'version', 'stderr'), [
    ('ruff', '0.17.0', NOQA_WARNINGS + 'error: Failed to parse pkg/debt.py\n'),
    ('ruff', '0.17.0', 'warning: something else\n'),
    ('mypy', '2.4.0', NOQA_WARNINGS)])
def test_other_stderr_still_requires_diagnosis(tmp_path, tool, version, stderr):
    parsed = api().parse_tool_report(tool, command(tmp_path, tool, stderr=stderr), version)
    assert parsed.execution_status == 'ERROR'


@pytest.mark.parametrize('filename', ['../escape.py', '/outside.py', 'pkg/other.py'])
def test_out_of_scope_diagnostic_is_not_silently_discarded(tmp_path, filename):
    item = row()
    item['file'] = filename
    parsed = api().parse_tool_report('mypy', command(tmp_path, rows=[item]), '2.4.0')
    assert parsed.execution_status == 'ERROR'


def test_unicode_absolute_path_and_crlf_are_normalized(tmp_path):
    item = row(message='Tên biến không hợp lệ\r\nχ')
    item['file'] = str(tmp_path / 'pkg/debt.py')
    parsed = api().parse_tool_report('mypy', command(tmp_path, rows=[item]), '2.4.0')
    assert parsed.execution_status == 'COMPLETE'
    assert parsed.diagnostics[0].path == 'pkg/debt.py'
    assert parsed.diagnostics[0].message == 'Tên biến không hợp lệ\nχ'


def test_moved_old_error_not_introduced(tmp_path):
    delta = api().compare_diagnostics(report(tmp_path, [row()]), report(tmp_path, [row(line=3)]),
                                     {'pkg/debt.py': {2: 3}})
    assert delta.complete and delta.status == 'PASS'
    assert len(delta.persisting) == 1 and not delta.introduced


def test_same_error_count_can_still_introduce_a_new_error(tmp_path):
    delta = api().compare_diagnostics(report(tmp_path, [row()]),
        report(tmp_path, [row(code='arg-type', message='Different error')]), {'pkg/debt.py': {2: 2}})
    assert delta.status == 'FAIL'
    assert len(delta.introduced) == len(delta.resolved) == 1


def test_duplicate_diagnostics_are_compared_as_multiset(tmp_path):
    delta = api().compare_diagnostics(report(tmp_path, [row()]), report(tmp_path, [row(), row()]),
                                     {'pkg/debt.py': {2: 2}})
    assert delta.status == 'FAIL' and len(delta.introduced) == 1 and len(delta.persisting) == 1


def test_unmapped_old_error_is_conservatively_recorded(tmp_path):
    delta = api().compare_diagnostics(report(tmp_path, [row()]), report(tmp_path, [row()]),
                                     {'pkg/debt.py': {}})
    assert delta.status == 'FAIL' and delta.unmatched and delta.introduced


@pytest.mark.parametrize('field', ['tool_version', 'config_hash', 'scope_hash', 'interpreter_ref'])
def test_binding_drift_blocks_comparison(tmp_path, field):
    before = report(tmp_path, [row()])
    after = before.model_copy(update={field: 'changed'})
    delta = api().compare_diagnostics(before, after, {'pkg/debt.py': {2: 2}})
    assert not delta.complete and delta.status == 'ERROR'


def test_failed_baseline_report_is_incomplete_not_zero_debt(tmp_path):
    before = api().parse_tool_report('mypy', command(tmp_path, stdout='broken'), '2.4.0')
    delta = api().compare_diagnostics(before, report(tmp_path, []), {})
    assert not delta.complete and delta.status == 'ERROR'


def test_line_map_keeps_unique_unchanged_lines_and_rejects_repeated_anchors():
    line_map = api().build_line_map({'a.py': 'x = 1\nreturn bad\n'},
                                   {'a.py': '# inserted\nx = 1\nreturn bad\n'})
    assert line_map['a.py'] == {1: 2, 2: 3}
    ambiguous = api().build_line_map({'a.py': 'return bad\nreturn bad\n'},
                                    {'a.py': '# inserted\nreturn bad\nreturn bad\n'})
    assert ambiguous['a.py'] == {}


def test_malformed_row_does_not_drop_earlier_valid_diagnostic(tmp_path):
    parsed = api().parse_tool_report('mypy', command(tmp_path, rows=[row(), {'file': 'pkg/debt.py'}]), '2.4.0')
    assert parsed.execution_status == 'ERROR'
    assert len(parsed.diagnostics) == 1


def test_mypy_unknown_column_sentinel_is_column_one(tmp_path):
    # Real mypy 2.4 output (matplotlib backend_ps.py str-bytes-safe) uses -1 for "no column".
    parsed = api().parse_tool_report('mypy', command(tmp_path, rows=[row(column=-1)]), '2.4.0')
    assert parsed.execution_status == 'COMPLETE', parsed.reason
    assert parsed.diagnostics[0].column == 1


@pytest.mark.parametrize('column', [True, False, -2, 0.5, 1.0, '0', None])
def test_invalid_mypy_column_is_not_normalized_into_valid_diagnostic(tmp_path, column):
    parsed = api().parse_tool_report(
        'mypy', command(tmp_path, rows=[row(), row(column=column)]), '2.4.0')
    assert parsed.execution_status == 'ERROR'
    assert parsed.reason
    assert len(parsed.diagnostics) == 1
    assert parsed.diagnostics[0].column == 1


@pytest.mark.parametrize(('column', 'expected'), [(0, 1), (11, 12)])
def test_integer_mypy_column_is_normalized_once(tmp_path, column, expected):
    parsed = api().parse_tool_report('mypy', command(tmp_path, rows=[row(column=column)]), '2.4.0')
    assert parsed.execution_status == 'COMPLETE'
    assert len(parsed.diagnostics) == 1
    assert parsed.diagnostics[0].column == expected
