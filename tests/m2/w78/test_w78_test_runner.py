from vgar.repair import executor as m_executor
from vgar.repair import test_runner as m_test_runner
from vgar.repair import workspace as m_workspace


def test_collect_and_baseline_exact_node_ids(m1_case, tmp_path):
    task, _ = m1_case
    with m_workspace.create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        executor = m_executor.NativeExecutor(lease)
        collected = m_test_runner.collect_tests(lease, ('tests',), executor)
        assert collected['status'] == 'PASS'
        assert collected['node_ids'] == ['tests/test_auth.py::test_login_rejects_whitespace',
                                        'tests/test_auth.py::test_login_accepts_name']
        run = m_test_runner.run_tests(lease, ('tests',), executor, 30)
        assert run['status'] == 'FAIL'
        assert run['outcomes']['tests/test_auth.py::test_login_rejects_whitespace'] == 'FAIL'
        assert run['outcomes']['tests/test_auth.py::test_login_accepts_name'] == 'PASS'
        assert '<testcase' in run['junit_xml']


def test_zero_tests_and_all_skip_are_not_pass(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'test_empty.py').write_bytes(b'import pytest\n@pytest.mark.skip\ndef test_skip(): pass\n')
    with m_workspace.create_workspace(source, tmp_path / 'temp') as lease:
        executor = m_executor.NativeExecutor(lease)
        result = m_test_runner.run_tests(lease, ('test_empty.py',), executor, 30)
        assert result['status'] == 'ERROR'



def test_w78_run_tests_child_process_loads_plugin_without_pythonpath(m1_case, tmp_path, monkeypatch):
    monkeypatch.delenv('PYTHONPATH', raising=False)
    task, _ = m1_case
    with m_workspace.create_workspace(task.source_repo, tmp_path / 'ws') as lease:
        result = m_test_runner.collect_tests(lease, ('tests',), m_executor.NativeExecutor(lease), 60)
    assert result['status'] == 'PASS', result['command']['stderr']
    assert 'tests/test_auth.py::test_login_rejects_whitespace' in result['node_ids']
