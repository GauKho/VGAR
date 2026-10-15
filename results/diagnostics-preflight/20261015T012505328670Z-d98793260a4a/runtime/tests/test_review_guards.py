import time
from types import SimpleNamespace

import pytest
from test_bootstrap import api
from test_pipeline import FIX


def test_public_bundle_uses_assessed_tests_not_raw_exit_zero(m1_case, tmp_path):
    task, _ = m1_case
    run = api('evidence').begin_run(tmp_path / 'runs', 'repair', task_id=task.task_id, mode='fake')
    run.record['stages']['baseline'] = {'required_ids': ['required'], 'tests': {'outcomes': {'required': 'FAIL', 'regression': 'PASS'}}}
    command = dict(command='pytest', argv=['pytest'], timed_out=False, exit_code=0, duration_ms=1,
        stdout='', stderr='', complete=True, output_truncated=False, stdout_bytes=0, stderr_bytes=0, timeout_seconds=1)
    verification = {'status': 'ERROR', 'reasons': ['VERIFICATION_INCOMPLETE'],
        'tests': {'status': 'PASS', 'command': command, 'outcomes': {'required': 'SKIP', 'regression': 'PASS'}, 'durations_ms': {}}}
    lease = SimpleNamespace(before=api('workspace').inventory(task.source_repo), worktree_id='test-worktree')
    bundle = api('pipeline')._project_bundle(run, task, lease, None, verification)
    assert bundle.verification.tests.status == 'ERROR'
    assert bundle.verification.reasons[0].code == 'VERIFICATION_INCOMPLETE'
    assert bundle.metadata['raw_pytest_status'] == 'PASS'


def test_applied_diff_export_failure_is_error(m1_case, tmp_path):
    task, _ = m1_case
    with api('workspace').create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        native = api('executor').NativeExecutor(lease)
        class ExportFailure:
            def run(self, argv, cwd, timeout):
                if argv[:2] == ('git', 'diff'):
                    return dict(status='ERROR', complete=False, stdout='', stderr='injected export failure')
                return native.run(argv, cwd, timeout)
        patch = api('patch').parse_unified_diff(FIX, api('patch').PatchPolicy(task.allowed_source_paths, task.protected_paths))
        result = api('patch').apply_patch(lease, patch, ExportFailure())
        assert result.status == 'ERROR'
        assert lease.patch_evidence[-1]['stderr'] == 'injected export failure'


def test_expired_workspace_budget_stops_before_git(m1_case, tmp_path):
    task, _ = m1_case
    with pytest.raises(TimeoutError, match='deadline'):
        api('workspace').create_workspace(task.source_repo, tmp_path / 'temp', deadline=time.monotonic()-1)


def test_reference_subprocess_is_bounded(tmp_path, monkeypatch):
    bootstrap = api('bootstrap')
    calls = []
    def checked(command, **kwargs):
        calls.append(kwargs)
        return 'wrong-revision'
    monkeypatch.setattr(bootstrap.subprocess, 'check_output', checked)
    with pytest.raises(ValueError, match='HEAD'):
        bootstrap.verify_reference(deadline=time.monotonic()+10)
    assert 0 < calls[0]['timeout'] <= 10


def test_tokenizer_obeys_global_deadline_before_launch():
    generator = SimpleNamespace(profile=SimpleNamespace(model_id='test', revision='test'))
    tokenizer = api('generator_hf').HFChatTokenizer(generator, api('contracts').RepairPolicy())
    tokenizer.deadline = time.monotonic()-1
    with pytest.raises(TimeoutError, match='deadline'):
        tokenizer.apply_chat_template([], tokenize=False, add_generation_prompt=True)


@pytest.mark.parametrize('tool', ['mypy', 'ruff'])
def test_missing_required_static_tool_cannot_pass(m1_case, tmp_path, tool):
    task, _ = m1_case
    with api('workspace').create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        native = api('executor').NativeExecutor(lease)
        class MissingTool:
            def run(self, argv, cwd, timeout):
                if len(argv)>2 and argv[2] == tool:
                    return dict(status='FAIL', complete=True, exit_code=1, stderr='No module named ' + tool)
                return native.run(argv, cwd, timeout)
        baseline = api('verification').capture_baseline(task, lease, MissingTool(), api('contracts').RepairPolicy())
        assert baseline['status'] == 'ERROR'
        assert baseline['static'][tool]['status'] != 'PASS'
