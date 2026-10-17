"""Catch running outside an owned workspace, leaking secrets, or ignoring limits."""
import sys
import time

import pytest
from vgar.repair import executor as m_executor


def test_executor_requires_owned_cwd(tmp_path):
    with pytest.raises(ValueError, match='owned'):
        m_executor.NativeExecutor().run((sys.executable, '-m', 'pytest'), tmp_path, 2)


def test_command_timeout_and_output_cap(tmp_path):
    run = m_executor.run_bounded
    timeout = run((sys.executable, '-c', 'import time; time.sleep(10)'), tmp_path, .2)
    assert timeout['status'] == 'ERROR' and timeout['timed_out']
    cap = run((sys.executable, '-c', 'print("x"*100000)'), tmp_path, 5, output_cap=1024)
    assert cap['status'] == 'ERROR' and cap['output_truncated']
    assert len(cap['stdout'].encode('utf-8')) <= 1024


def test_command_environment_removes_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('SOME_API_KEY', 'never-forward-this')
    result = m_executor.run_bounded((sys.executable, '-c',
        'import os; print(os.environ.get("SOME_API_KEY", "ABSENT"))'), tmp_path, 5)
    assert result['stdout'].strip() == 'ABSENT'
    assert result['exit_code'] == 0
    assert result['duration_ms'] >= 0 and result['ended_utc'] >= result['started_utc']


def test_descendant_cannot_survive_completed_parent(tmp_path):
    marker = tmp_path / 'child-survived.txt'
    child = f'import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text("bad")'
    parent = f'import subprocess, sys; subprocess.Popen([sys.executable, "-c", {child!r}]); print("parent done")'
    result = m_executor.run_bounded((sys.executable, '-c', parent), tmp_path, 5)
    assert result['status'] == 'PASS', result
    time.sleep(1.3)
    assert not marker.exists(), 'Child escaped owned job after its parent exited'




def test_child_does_not_inherit_stdin(tmp_path):
    # An MCP stdio server's stdin is a pipe that stays open; a child inheriting it hung on Windows
    # (git init timed out inside repair_get_task_context). Children must get an empty stdin.
    import os
    read_end, write_end = os.pipe()
    saved = os.dup(0)
    os.dup2(read_end, 0)
    try:
        result = m_executor.run_bounded((sys.executable, '-c', 'import sys; print(repr(sys.stdin.read()))'), tmp_path, 5)
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_end, write_end):
            os.close(fd)
    assert result['status'] == 'PASS', result
    assert result['stdout'].strip() == "''"
