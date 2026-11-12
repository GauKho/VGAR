import time

import pytest
from vgar.repair import contracts as m_contracts
from vgar.repair import executor as m_executor
from vgar.repair import patch as m_patch
from vgar.repair import verification as m_verification
from vgar.repair import workspace as m_workspace

# The reference fix the removed test_w78_pipeline.py exported.
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


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
