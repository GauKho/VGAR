from test_bootstrap import api


def test_collect_and_baseline_exact_node_ids(m1_case, tmp_path):
    task, _ = m1_case
    with api('workspace').create_workspace(task.source_repo, tmp_path / 'temp') as lease:
        executor = api('executor').NativeExecutor(lease)
        collected = api('test_runner').collect_tests(lease, ('tests',), executor)
        assert collected['status'] == 'PASS'
        assert collected['node_ids'] == ['tests/test_auth.py::test_login_rejects_whitespace',
                                        'tests/test_auth.py::test_login_accepts_name']
        run = api('test_runner').run_tests(lease, ('tests',), executor, 30)
        assert run['status'] == 'FAIL'
        assert run['outcomes']['tests/test_auth.py::test_login_rejects_whitespace'] == 'FAIL'
        assert run['outcomes']['tests/test_auth.py::test_login_accepts_name'] == 'PASS'
        assert '<testcase' in run['junit_xml']


def test_zero_tests_and_all_skip_are_not_pass(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'test_empty.py').write_bytes(b'import pytest\n@pytest.mark.skip\ndef test_skip(): pass\n')
    with api('workspace').create_workspace(source, tmp_path / 'temp') as lease:
        executor = api('executor').NativeExecutor(lease)
        result = api('test_runner').run_tests(lease, ('test_empty.py',), executor, 30)
        assert result['status'] == 'ERROR'

