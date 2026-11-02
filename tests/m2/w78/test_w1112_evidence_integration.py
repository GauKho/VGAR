"""Real trusted-fixture execution through the three existing entry points."""
import json
from pathlib import Path

import pytest

from vgar.models.generator import FakeGenerator
from vgar.repair import pipeline, session
from vgar.repair.contracts import RepairPolicy
from vgar.repair.executor import utc_now
from w78_support import CharacterChatTokenizer

PATCH = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


def assert_checks(directory, expected='PASS'):
    bundle = json.loads((directory / 'evidence_bundle.json').read_bytes())
    for name in ('api_check', 'structural_check'):
        check = bundle['verification'][name]
        assert check['status'] == expected
        sidecar = json.loads((directory / check['details_ref']).read_bytes())
        assert sidecar['status'] == expected
        if expected == 'PASS':
            assert sidecar['details']['source_hashes']['baseline']
            assert sidecar['details']['source_hashes']['candidate']
    return bundle


def test_batch_publishes_details_that_survive_workspace_cleanup(m1_case, tmp_path):
    task, counter = m1_case
    run = pipeline.run_repair(task, RepairPolicy(), FakeGenerator(PATCH), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    assert run.record['status'] == 'PASS'
    bundle = assert_checks(run.directory)
    assert bundle['recommendation'] == 'ACCEPT'
    baseline = run.record['stages']['baseline']['compatibility_snapshot']
    assert (run.directory / baseline['details_ref']).is_file()
    assert b'value.strip()' not in (task.source_repo / 'auth.py').read_bytes()


def test_persisted_session_and_MCP_share_results(m1_case, tmp_path, monkeypatch):
    from vgar.mcp.servers import repair_server
    monkeypatch.setenv('VGAR_RUN_ROOT', str(tmp_path))
    task, counter = m1_case
    state = session.start_session(task, RepairPolicy(), 'fake', tmp_path / 'runs', temp_root=tmp_path / 'temp')
    directory = state.run.directory
    def reload():
        return session.RepairSession.load(directory)
    prompt = session.prepare(reload(), counter, CharacterChatTokenizer())
    assert prompt is not None
    raw = session.record_generation(reload(), FakeGenerator(PATCH).generate(prompt, None, 30),
                                    started_utc=utc_now(), duration_ms=1)
    assert session.apply_candidate(reload(), raw).status == 'PASS'
    assert reload().lease().applied_inventory_hash == reload().run.record['stages']['apply']['source_inventory_hash']
    assert session.run_selected_tests(reload(), counter) is not None
    response = repair_server.verify_patch(str(directory))
    assert response['status'] == 'PASS'
    assert response['data']['recommendation'] == 'ACCEPT'
    bundle = assert_checks(directory)
    assert response['data']['evidence']['verification']['api_check'] == bundle['verification']['api_check']
    assert reload().phase == 'finished'
    assert not Path(reload().state['lease']['private']).exists()


@pytest.mark.parametrize('raw', ['not a patch'])
def test_aborted_run_publishes_explicit_not_run_details(m1_case, tmp_path, raw):
    task, counter = m1_case
    run = pipeline.run_repair(task, RepairPolicy(), FakeGenerator(raw), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    assert run.record['status'] == 'FAIL'
    assert_checks(run.directory, 'NOT_RUN')


def test_preapply_source_drift_is_rejected_and_apply_pin_survives_reload(m1_case, tmp_path):
    task, counter = m1_case
    state = session.start_session(task, RepairPolicy(), 'fake', tmp_path / 'runs', temp_root=tmp_path / 'temp')
    prompt = session.prepare(state, counter, CharacterChatTokenizer())
    raw = session.record_generation(state, FakeGenerator(PATCH).generate(prompt, None, 30),
                                    started_utc=utc_now(), duration_ms=1)
    path = state.lease().path / 'auth.py'
    path.write_bytes(path.read_bytes() + b'\n# modified after baseline\n')
    later = session.RepairSession.load(state.run.directory)
    assert session.apply_candidate(later, raw) is None
    run = session.finish(later)
    assert run.record['status'] == 'ERROR'
    assert_checks(run.directory, 'NOT_RUN')
