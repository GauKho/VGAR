"""Every repair step must work on a session re-loaded from disk (as a fresh MCP server process would)."""
import json
import time

import pytest

from vgar.models.generator import FakeGenerator
from vgar.repair import session as m_session
from vgar.repair.contracts import RepairPolicy
from vgar.repair.executor import utc_now
from w78_support import CharacterChatTokenizer

FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
STAGES = ('context', 'workspace', 'baseline', 'prompt', 'generation', 'parse_patch', 'apply', 'selection', 'verification')


def started(task, tmp_path):
    return m_session.start_session(task, RepairPolicy(), 'fake', tmp_path / 'runs', temp_root=tmp_path / 'temp')


def reload(session):
    return m_session.RepairSession.load(session.run.directory)


def test_steps_survive_reload_between_each_step(m1_case, tmp_path):
    task, counter = m1_case
    run_dir = started(task, tmp_path).run.directory
    prompt = m_session.prepare(m_session.RepairSession.load(run_dir), counter, CharacterChatTokenizer())
    assert prompt is not None
    generated = FakeGenerator(FIX).generate(prompt, None, 30)
    raw = m_session.record_generation(m_session.RepairSession.load(run_dir), generated,
                                      started_utc=utc_now(), duration_ms=1)
    assert raw == FIX
    assert m_session.apply_candidate(m_session.RepairSession.load(run_dir), raw).status == 'PASS'
    assert m_session.run_selected_tests(m_session.RepairSession.load(run_dir), counter) is not None
    session = m_session.RepairSession.load(run_dir)
    private = session.state['lease']['private']
    run = m_session.finish(session, counter)
    record = json.loads(run.path.read_text(encoding='utf-8'))
    assert record['status'] == 'PASS' and record['complete'] is True
    assert all(record['stages'][name]['complete'] is True for name in STAGES)
    assert record['stages']['verification']['tests']['status'] == 'PASS'
    assert record['stages']['verification']['static']['ruff']['status'] == 'PASS'
    bundle = json.loads((run.directory / 'evidence_bundle.json').read_text(encoding='utf-8'))
    assert bundle['recommendation'] == 'ACCEPT'
    assert not __import__('pathlib').Path(private).exists()
    assert m_session.RepairSession.load(run_dir).phase == 'finished'


def test_finish_twice_raises(m1_case, tmp_path):
    task, counter = m1_case
    session = started(task, tmp_path)
    m_session.finish(session, counter)
    with pytest.raises(ValueError, match='Run already finished'):
        m_session.finish(m_session.RepairSession.load(session.run.directory), counter)


def test_expired_deadline_between_steps_still_finishes_cleanly(m1_case, tmp_path):
    task, counter = m1_case
    session = started(task, tmp_path)
    prompt = m_session.prepare(session, counter, CharacterChatTokenizer())
    assert prompt is not None
    state_path = session.run.directory / 'session.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state['deadline_utc'] = time.time() - 1
    state_path.write_text(json.dumps(state), encoding='utf-8')
    later = m_session.RepairSession.load(session.run.directory)
    private = later.state['lease']['private']
    assert m_session.record_generation(later, FakeGenerator(FIX).generate(prompt, None, 30),
                                       started_utc=utc_now(), duration_ms=1) is None
    run = m_session.finish(m_session.RepairSession.load(session.run.directory), counter)
    record = json.loads(run.path.read_text(encoding='utf-8'))
    assert record['status'] == 'ERROR' and record['complete'] is True
    assert not __import__('pathlib').Path(private).exists()


def test_load_rejects_non_run_dir(tmp_path):
    with pytest.raises(ValueError, match='Not a repair run directory'):
        m_session.RepairSession.load(tmp_path)
