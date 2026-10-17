"""The MCP repair server: four tools in a strict order, each call logged in run_record.mcp_calls."""
import asyncio
import json
import shutil
from pathlib import Path

from vgar.mcp.servers import repair_server as server
from w78_support import REPO

TASK = REPO / 'examples/m2/tasks/single_file_login.json'
PATCH = (REPO / 'tests/fixtures/m2/reference_patches/single_file_login.diff').read_text(encoding='utf-8')


def context(tmp_path, task=TASK):
    return server.get_task_context(str(task), 'fake', str(tmp_path / 'runs'), str(tmp_path / 'work'))


def worktrees(tmp_path):
    """Private worktrees left under work_root (M2 keeps only .cleanup-records there)."""
    return sorted((tmp_path / 'work').glob('m2-w78-*'))


def record_of(run_dir):
    return json.loads((Path(run_dir) / 'run_record.json').read_text(encoding='utf-8'))


def test_tools_in_order_pass_and_log_four_calls(tmp_path):
    ctx = context(tmp_path)
    assert ctx['status'] == 'PASS' and ctx['prompt']['version'] == 'm2-w78-v11'
    assert ctx['failed_cases'] == ['tests/test_auth.py::test_login_rejects_whitespace']
    assert server.apply_patch(ctx['run_dir'], PATCH)['status'] == 'PASS'
    tested = server.run_relevant_tests(ctx['run_dir'])
    assert tested['status'] == 'PASS' and tested['failing_tests']['status'] == 'PASS'
    verified = server.verify_patch(ctx['run_dir'])
    assert verified['recommendation'] == 'ACCEPT' and verified['evidence']['recommendation'] == 'ACCEPT'
    record = record_of(ctx['run_dir'])
    assert [c['tool'] for c in record['mcp_calls']] == ['get_task_context', 'apply_patch', 'run_relevant_tests', 'verify_patch']
    assert all(set(c) == {'tool', 'input_sha256', 'started_utc', 'duration_ms', 'status'} for c in record['mcp_calls'])
    assert record['mcp_scope'] == 'repair_server' and record['status'] == 'PASS'
    assert worktrees(tmp_path) == []


def test_apply_twice_is_rejected(tmp_path):
    ctx = context(tmp_path)
    server.apply_patch(ctx['run_dir'], PATCH)
    again = server.apply_patch(ctx['run_dir'], PATCH)
    assert again['status'] == 'ERROR' and 'Tool order violation' in again['detail']
    server.verify_patch(ctx['run_dir'])


def test_tests_before_apply_is_rejected(tmp_path):
    ctx = context(tmp_path)
    early = server.run_relevant_tests(ctx['run_dir'])
    assert early['status'] == 'ERROR' and 'Tool order violation' in early['detail']
    assert server.verify_patch(ctx['run_dir'])['recommendation'] == 'REJECT'


def test_verify_twice_is_rejected(tmp_path):
    ctx = context(tmp_path)
    server.apply_patch(ctx['run_dir'], PATCH)
    server.verify_patch(ctx['run_dir'])
    before = (Path(ctx['run_dir']) / 'run_record.json').read_bytes()
    again = server.verify_patch(ctx['run_dir'])
    assert again['status'] == 'ERROR' and 'Tool order violation' in again['detail']
    assert (Path(ctx['run_dir']) / 'run_record.json').read_bytes() == before


def test_tool_rejects_unknown_run_dir(tmp_path):
    (tmp_path / 'not-a-run').mkdir()
    for result in (server.apply_patch(str(tmp_path / 'not-a-run'), PATCH),
                   server.run_relevant_tests(str(tmp_path / 'nope')), server.verify_patch(str(tmp_path / 'nope'))):
        assert result['status'] == 'ERROR' and result['reason'] == 'TOOL_ERROR'
        assert 'Not a repair run directory' in result['detail']
    assert list((tmp_path / 'not-a-run').iterdir()) == []


def test_untrusted_task_context_returns_reject_and_cleans_up(tmp_path):
    task = json.loads(TASK.read_text(encoding='utf-8'))
    shutil.copytree(REPO / 'examples/m2/snapshots/single_file_login', tmp_path / 'src')
    (tmp_path / 'src/auth.py').write_bytes(b'def login(value):\n    return False\n')
    task.update(source_repo=str(tmp_path / 'src'), bundle_directory=str(REPO / 'examples/m2/handoffs/single_file_login'))
    (tmp_path / 'task.json').write_text(json.dumps(task), encoding='utf-8')
    ctx = context(tmp_path, tmp_path / 'task.json')
    assert ctx['status'] == 'ERROR' and ctx['recommendation'] == 'REJECT'
    assert 'approved fixtures' in ctx['detail']
    record = record_of(ctx['run_dir'])
    assert record['complete'] is True and [c['tool'] for c in record['mcp_calls']] == ['get_task_context']
    assert worktrees(tmp_path) == []


def test_server_lists_four_repair_tools():
    from vgar.mcp.client import create_mcp_client
    tools = asyncio.run(create_mcp_client(servers=('repair',)).get_tools())
    assert {t.name for t in tools} == {'repair_get_task_context', 'repair_apply_patch',
                                       'repair_run_relevant_tests', 'repair_verify_patch'}


def test_verify_cleans_up_even_if_tokenizer_setup_would_fail(tmp_path, monkeypatch):
    ctx = context(tmp_path)
    server.apply_patch(ctx['run_dir'], PATCH)
    assert server.run_relevant_tests(ctx['run_dir'])['status'] == 'PASS'

    def broken(session):
        raise RuntimeError('tokenizer manifest missing')
    monkeypatch.setattr(server, '_tooling', broken, raising=False)
    verified = server.verify_patch(ctx['run_dir'])
    assert verified['recommendation'] == 'ACCEPT'
    assert record_of(ctx['run_dir'])['complete'] is True
    assert worktrees(tmp_path) == []
