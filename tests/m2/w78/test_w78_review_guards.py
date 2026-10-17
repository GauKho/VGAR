import time
from types import SimpleNamespace

import pytest
from vgar.repair import contracts as m_contracts
from vgar.repair import evidence as m_evidence
from vgar.repair import executor as m_executor
from vgar.models.huggingface import generator_hf as m_generator_hf
from vgar.repair import patch as m_patch
from vgar.repair import pipeline as m_pipeline
from vgar.repair import verification as m_verification
from vgar.repair import workspace as m_workspace
from test_w78_pipeline import FIX


def test_public_bundle_uses_assessed_tests_not_raw_exit_zero(m1_case, tmp_path):
    task, _ = m1_case
    run = m_evidence.begin_run(tmp_path / 'runs', 'repair', task_id=task.task_id, mode='fake')
    run.record['stages']['baseline'] = {'required_ids': ['required'], 'tests': {'outcomes': {'required': 'FAIL', 'regression': 'PASS'}}}
    command = dict(command='pytest', argv=['pytest'], timed_out=False, exit_code=0, duration_ms=1,
        stdout='', stderr='', complete=True, output_truncated=False, stdout_bytes=0, stderr_bytes=0, timeout_seconds=1)
    verification = {'status': 'ERROR', 'reasons': ['VERIFICATION_INCOMPLETE'],
        'tests': {'status': 'PASS', 'command': command, 'outcomes': {'required': 'SKIP', 'regression': 'PASS'}, 'durations_ms': {}}}
    lease = SimpleNamespace(before=m_workspace.inventory(task.source_repo), worktree_id='test-worktree')
    bundle = m_pipeline._project_bundle(run, task, lease, None, verification)
    assert bundle.verification.tests.status == 'ERROR'
    assert bundle.verification.reasons[0].code == 'VERIFICATION_INCOMPLETE'
    assert bundle.metadata['raw_pytest_status'] == 'PASS'


def test_applied_diff_export_failure_is_error(m1_case, tmp_path):
    task, _ = m1_case
    with m_workspace.create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        native = m_executor.NativeExecutor(lease)
        class ExportFailure:
            def run(self, argv, cwd, timeout):
                if argv[:2] == ('git', 'diff'):
                    return dict(status='ERROR', complete=False, stdout='', stderr='injected export failure')
                return native.run(argv, cwd, timeout)
        patch = m_patch.parse_unified_diff(FIX, m_patch.PatchPolicy(task.allowed_source_paths, task.protected_paths))
        result = m_patch.apply_patch(lease, patch, ExportFailure())
        assert result.status == 'ERROR'
        assert lease.patch_evidence[-1]['stderr'] == 'injected export failure'


def test_expired_workspace_budget_stops_before_git(m1_case, tmp_path):
    task, _ = m1_case
    with pytest.raises(TimeoutError, match='deadline'):
        m_workspace.create_workspace(task.source_repo, tmp_path / 'temp', deadline=time.monotonic()-1)



def test_tokenizer_obeys_global_deadline_before_launch():
    generator = SimpleNamespace(profile=SimpleNamespace(model_id='test', revision='test'))
    tokenizer = m_generator_hf.HFChatTokenizer(generator, m_contracts.RepairPolicy())
    tokenizer.deadline = time.monotonic()-1
    with pytest.raises(TimeoutError, match='deadline'):
        tokenizer.apply_chat_template([], tokenize=False, add_generation_prompt=True)


@pytest.mark.parametrize('tool', ['mypy', 'ruff'])
def test_missing_required_static_tool_cannot_pass(m1_case, tmp_path, tool):
    task, _ = m1_case
    with m_workspace.create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        native = m_executor.NativeExecutor(lease)
        class MissingTool:
            def run(self, argv, cwd, timeout):
                if len(argv)>2 and argv[2] == tool:
                    return dict(status='FAIL', complete=True, exit_code=1, stderr='No module named ' + tool)
                return native.run(argv, cwd, timeout)
        baseline = m_verification.capture_baseline(task, lease, MissingTool(), m_contracts.RepairPolicy())
        assert baseline['status'] == 'ERROR'
        assert baseline['static'][tool]['status'] != 'PASS'
