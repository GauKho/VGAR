"""Catch overwriting prior runs, incomplete records, and losing command output."""
import json
import subprocess
import sys
from pathlib import Path

from test_bootstrap import api


def test_pending_and_terminal_records_are_unique(tmp_path):
    evidence = api('evidence')
    a = evidence.begin_run(tmp_path, 'test', task_id='one', mode='fake')
    b = evidence.begin_run(tmp_path, 'test', task_id='one', mode='fake')
    assert a.directory != b.directory
    assert json.loads(a.path.read_text(encoding='utf-8'))['complete'] is False
    a.finish('FAIL', reason='EXPECTED_RED')
    result = json.loads(a.path.read_text(encoding='utf-8'))
    assert result['complete'] and result['status'] == 'FAIL'
    assert result['duration_ms'] >= 0


def test_test_recorder_keeps_exact_exit_and_logs(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/record_tests.py'
    assert script.is_file(), 'Test recorder not implemented'
    completed = subprocess.run([sys.executable, '-B', str(script), 'tests/test_contracts.py',
        '--output-root', str(tmp_path), '--timeout-seconds', '60'], capture_output=True, text=True, timeout=70)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    path = Path(completed.stdout.strip().splitlines()[-1])
    record = json.loads(path.read_text(encoding='utf-8'))
    assert record['stages']['pytest']['exit_code'] == 0
    assert 'passed' in record['stages']['pytest']['stdout']
    assert record['status'] == 'PASS' and record['complete']

