import pytest
from test_bootstrap import api


def test_baseline_to_repair_and_static_evidence(m1_case, tmp_path):
    task, _ = m1_case
    with api('workspace').create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        executor = api('executor').NativeExecutor(lease)
        policy = api('contracts').RepairPolicy()
        baseline = api('verification').capture_baseline(task, lease, executor, policy)
        assert baseline['status'] == 'PASS' and baseline['tests']['status'] == 'FAIL'
        assert baseline['static']['mypy']['status'] == 'PASS'
        raw = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
        applied = api('patch').apply_patch(lease, api('patch').parse_unified_diff(raw,
            api('patch').PatchPolicy(task.allowed_source_paths, task.protected_paths)), executor)
        assert applied.status == 'PASS'
        selection = {'selected': ('tests',), 'related_selectors': (), 'required_selectors': task.failing_selectors}
        result = api('verification').verify_patch(task, lease, applied, baseline, selection, executor, policy)
        assert result['status'] == 'PASS'
        assert result['tests']['status'] == 'PASS' and result['static']['ruff']['status'] == 'PASS'


@pytest.mark.parametrize('fault', ['missing', 'skip', 'xfail', 'regression'])
def test_required_or_regression_cannot_hide_behind_exit_zero(fault):
    before = {'required_ids': ['test.py::test_fix'], 'tests': {'outcomes': {'test.py::test_fix': 'FAIL', 'test.py::test_ok': 'PASS'}}}
    post = {'status': 'PASS', 'outcomes': {'test.py::test_fix': 'PASS', 'test.py::test_ok': 'PASS'}}
    if fault == 'missing':
        post['outcomes'].pop('test.py::test_fix')
    elif fault in ('skip', 'xfail'):
        post['outcomes']['test.py::test_fix'] = fault.upper()
    else:
        post['outcomes']['test.py::test_ok'] = 'FAIL'
    status, reasons = api('verification').assess_transition(before, post)
    assert status == ('FAIL' if fault == 'regression' else 'ERROR')
    assert reasons

