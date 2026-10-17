"""Catch overwriting prior runs, incomplete records, and losing command output."""
import json

from vgar.repair import evidence as m_evidence


def test_pending_and_terminal_records_are_unique(tmp_path):
    evidence = m_evidence
    a = evidence.begin_run(tmp_path, 'test', task_id='one', mode='fake')
    b = evidence.begin_run(tmp_path, 'test', task_id='one', mode='fake')
    assert a.directory != b.directory
    assert json.loads(a.path.read_text(encoding='utf-8'))['complete'] is False
    a.finish('FAIL', reason='EXPECTED_RED')
    result = json.loads(a.path.read_text(encoding='utf-8'))
    assert result['complete'] and result['status'] == 'FAIL'
    assert result['duration_ms'] >= 0

