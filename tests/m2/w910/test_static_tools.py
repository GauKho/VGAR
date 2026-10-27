"""Pinned static-tool bundle for SWE-bench images, and mypy UNAVAILABLE on old testbeds."""
import json
import sys

import pytest
import test_admission as admission_cases
import test_baseline_delta as delta_cases
from test_docker_admission import make_executor

from vgar.repair import static_tools

admitted_case = admission_cases.admitted_case
case = delta_cases.case
UNSUPPORTED = {'mypy': 'TESTBED_PYTHON_UNSUPPORTED'}


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root = tmp_path / 'static-tools'
    root.mkdir()
    lock = static_tools.lock()
    (root / 'manifest.json').write_text(json.dumps({k: lock[k] for k in ('python', 'mypy', 'ruff')}))
    monkeypatch.setenv('VGAR_STATIC_TOOLS', str(root))
    return root


@pytest.mark.parametrize(('version', 'reason'), [
    ('3.6.13', 'TESTBED_PYTHON_UNSUPPORTED'), ('3.7.0', None), ('3.9.20', None), ('3.10.15', None)])
def test_mypy_availability_follows_pinned_testbed_python(version, reason):
    assert static_tools.mypy_unavailable_reason(version) == reason


def test_missing_bundle_is_an_os_error_so_static_evidence_records_error(tmp_path, monkeypatch):
    monkeypatch.setenv('VGAR_STATIC_TOOLS', str(tmp_path / 'absent'))
    with pytest.raises(OSError):
        static_tools.load_bundle()


def test_bundle_with_other_versions_than_the_lock_is_rejected(bundle):
    (bundle / 'manifest.json').write_text(json.dumps({'python': '3.11.17', 'mypy': '9.9.9', 'ruff': '0.17.0'}))
    with pytest.raises(ValueError, match='lock'):
        static_tools.load_bundle()


def static_argv(e, name):
    config = static_tools.CONFIG_DIR / ('static/mypy.ini' if name == 'mypy' else 'static/ruff.toml')
    targets = tuple(e.task.allowed_source_paths)
    if name == 'mypy':
        return (sys.executable, '-m', 'mypy', '--config-file', str(config), '--no-incremental',
                '--cache-dir', str(e.lease.private / 'mypy-cache'), '--output', 'json',
                '--no-error-summary', *targets)
    return (sys.executable, '-m', 'ruff', 'check', '--config', str(config), '--no-cache', '--no-fix',
            '--output-format', 'json', *targets)


def test_static_commands_run_from_the_bundle_against_the_testbed(admitted_case, tmp_path, bundle):
    e = make_executor(admitted_case, tmp_path)
    try:
        mypy, _ = e.map_command(static_argv(e, 'mypy'))
        assert mypy[:3] == ['/vgar/tools/py/bin/python3', '-m', 'mypy']
        assert mypy[3:7] == ['--python-executable', '/opt/miniconda3/envs/testbed/bin/python',
                             '--python-version', '3.10']
        assert '/vgar/mypy.ini' in mypy and '/vgar/mypy-cache' in mypy
        ruff, _ = e.map_command(static_argv(e, 'ruff'))
        assert ruff[:2] == ['/vgar/tools/bin/ruff', 'check'] and '/vgar/ruff.toml' in ruff
        assert e.map_command((sys.executable, '-m', 'ruff', '--version'))[0] == ['/vgar/tools/bin/ruff', '--version']
        assert e.map_command((sys.executable, '-m', 'mypy', '--version'))[0] == [
            '/vgar/tools/py/bin/python3', '-m', 'mypy', '--version']
    finally:
        e.lease.__exit__()


def test_testbed_below_minimum_marks_mypy_unavailable(admitted_case, tmp_path):
    e = make_executor(admitted_case, tmp_path)
    try:
        assert e.unavailable_checks == {}
        e.profile = dict(e.profile, runtime=dict(e.profile['runtime'], python='3.6.13'))
        assert e.unavailable_checks == UNSUPPORTED
    finally:
        e.lease.__exit__()


def copies(e, monkeypatch, operation):
    calls = []

    def checked(args, directory, deadline):
        calls.append(list(args))
        return {'stdout': ''}

    monkeypatch.setattr(e, '_identity', lambda d: None)
    monkeypatch.setattr(e, '_checked', checked)
    monkeypatch.setattr(e, '_cli', lambda *a: {'complete': False, 'exit_code': None})
    monkeypatch.setattr(e, '_cleanup', lambda *a: {'status': 'PASS'})
    e.execute_operation(operation, 60)
    return [c for c in calls if c[0] == 'cp']


def test_bundle_is_copied_only_for_static_commands(admitted_case, tmp_path, bundle, monkeypatch):
    e = make_executor(admitted_case, tmp_path)
    try:
        static = copies(e, monkeypatch, {'kind': 'command', 'argv': ['/vgar/tools/bin/ruff', 'check']})
        assert static[-1] == ['cp', str(bundle), e.name + ':/vgar/tools']
        syntax = copies(e, monkeypatch, {'kind': 'syntax', 'targets': ['xarray/core.py']})
        assert all(':/vgar/tools' not in c[-1] for c in syntax)
    finally:
        e.lease.__exit__()


def test_container_absolute_paths_map_to_scope(tmp_path):
    # Ruff prints /testbed/<path> inside the container; cwd is the host lease.
    from test_static_diagnostics import command

    from vgar.repair.static_diagnostics import parse_tool_report
    rows = [{'filename': '/testbed/pkg/debt.py', 'location': {'row': 2, 'column': 1},
             'code': 'F821', 'message': 'Undefined name in /testbed/pkg/debt.py'}]
    parsed = parse_tool_report('ruff', command(tmp_path, 'ruff', rows=rows, target_cwd='/testbed'), '0.17.0')
    assert parsed.execution_status == 'COMPLETE', parsed.reason
    assert parsed.diagnostics[0].path == 'pkg/debt.py'
    assert parsed.diagnostics[0].message == 'Undefined name in pkg/debt.py'


def test_docker_results_carry_the_container_cwd(admitted_case, tmp_path, monkeypatch):
    e = make_executor(admitted_case, tmp_path)
    try:
        monkeypatch.setattr(e, '_identity', lambda d: None)
        monkeypatch.setattr(e, '_checked', lambda *a: {'stdout': ''})
        monkeypatch.setattr(e, '_cli', lambda *a: {'complete': False, 'exit_code': None})
        monkeypatch.setattr(e, '_cleanup', lambda *a: {'status': 'PASS'})
        assert e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)['target_cwd'] == '/testbed'
    finally:
        e.lease.__exit__()


def test_probe_resets_quietly_so_git_progress_never_reaches_tool_stderr(tmp_path, monkeypatch):
    from vgar.repair import docker_probe
    calls = []
    monkeypatch.setattr(docker_probe.subprocess, 'check_call', lambda argv, **k: calls.append(argv))
    monkeypatch.setattr(docker_probe, 'base_identity', lambda root: (_ for _ in ()).throw(RuntimeError('stop')))
    runtime = docker_probe.run({'root': str(tmp_path), 'runtime': None, 'base_commit': 'abc'})['runtime']
    docker_probe.run({'root': str(tmp_path), 'runtime': runtime, 'base_commit': 'abc'})
    reset = next(c for c in calls if 'reset' in c)
    assert '-q' in reset


def test_unavailable_mypy_is_not_run_and_still_qualifies_a2_baseline(case):
    case[2].unavailable_checks = UNSUPPORTED
    before = delta_cases.baseline(case)
    assert before['status'] == 'PASS'
    assert before['static']['mypy']['status'] == 'UNAVAILABLE'
    assert before['static']['mypy']['report']['execution_status'] == 'UNAVAILABLE'
    assert not any(argv[2] == 'mypy' for argv in case[2].calls)


def test_unavailable_mypy_is_never_reported_as_pass(case):
    case[2].unavailable_checks = UNSUPPORTED
    before = delta_cases.baseline(case)
    result = delta_cases.completion(case, before)
    assert result['status'] == 'PASS'
    assert result['policy_checks']['mypy']['status'] == 'UNAVAILABLE'
    assert result['policy_checks']['ruff']['status'] == 'PASS'


def test_ruff_stays_required_when_mypy_is_unavailable(case, monkeypatch):
    case[2].unavailable_checks = UNSUPPORTED
    before = delta_cases.baseline(case)
    run = case[2].run

    def new_lint_error(argv, cwd, timeout_seconds):
        result = run(argv, cwd, timeout_seconds)
        if argv[2] == 'ruff' and '--version' not in argv:
            result.update(stdout=json.dumps([{'filename': 'app.py', 'location': {'row': 1, 'column': 1},
                                              'code': 'F821', 'message': 'Undefined name'}]),
                          exit_code=1, status='FAIL')
        return result

    monkeypatch.setattr(case[2], 'run', new_lint_error)
    result = delta_cases.completion(case, before)
    assert result['status'] == 'FAIL' and 'LINT_FAILED' in result['reasons']


def test_availability_change_between_baseline_and_post_is_an_error(case):
    before = delta_cases.baseline(case)
    case[2].unavailable_checks = UNSUPPORTED
    result = delta_cases.completion(case, before)
    assert result['status'] == 'ERROR'
    assert result['policy_checks']['mypy']['status'] == 'ERROR'
