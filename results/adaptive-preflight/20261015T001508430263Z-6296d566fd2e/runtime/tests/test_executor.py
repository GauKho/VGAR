"""Catch running outside an owned workspace, leaking secrets, or ignoring limits."""
import sys
import time

import pytest
from test_bootstrap import api


def test_executor_requires_owned_cwd(tmp_path):
    with pytest.raises(ValueError, match='owned'):
        api('executor').NativeExecutor().run((sys.executable, '-m', 'pytest'), tmp_path, 2)


def test_command_timeout_and_output_cap(tmp_path):
    run = api('executor').run_bounded
    timeout = run((sys.executable, '-c', 'import time; time.sleep(10)'), tmp_path, .2)
    assert timeout['status'] == 'ERROR' and timeout['timed_out']
    cap = run((sys.executable, '-c', 'print("x"*100000)'), tmp_path, 5, output_cap=1024)
    assert cap['status'] == 'ERROR' and cap['output_truncated']
    assert len(cap['stdout'].encode('utf-8')) <= 1024


def test_command_environment_removes_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('SOME_API_KEY', 'never-forward-this')
    result = api('executor').run_bounded((sys.executable, '-c',
        'import os; print(os.environ.get("SOME_API_KEY", "ABSENT"))'), tmp_path, 5)
    assert result['stdout'].strip() == 'ABSENT'
    assert result['exit_code'] == 0
    assert result['duration_ms'] >= 0 and result['ended_utc'] >= result['started_utc']


def test_descendant_cannot_survive_completed_parent(tmp_path):
    marker = tmp_path / 'child-survived.txt'
    child = f'import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text("bad")'
    parent = f'import subprocess, sys; subprocess.Popen([sys.executable, "-c", {child!r}]); print("parent done")'
    result = api('executor').run_bounded((sys.executable, '-c', parent), tmp_path, 5)
    assert result['status'] == 'PASS', result
    time.sleep(1.3)
    assert not marker.exists(), 'Child escaped owned job after its parent exited'

