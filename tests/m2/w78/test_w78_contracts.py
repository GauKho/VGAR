"""Catch missing task identity, unsafe selectors, and policy bypass."""
import pytest
from vgar.repair import contracts as m_contracts


def task_data(tmp_path):
    return dict(task_id='unit-task', issue_text='Fix trim.', source_repo=tmp_path,
        repo_key='demo/unit', revision='fixture-v1', graph_version='graph',
        bundle_directory=tmp_path, failing_selectors=('tests/test_x.py::test_x',),
        fallback_scope=('tests',), allowed_source_paths=('app.py',), protected_paths=('tests',))


@pytest.mark.parametrize('key', ['task_id', 'issue_text', 'repo_key', 'revision', 'graph_version'])
def test_missing_identity_or_issue_rejected(tmp_path, key):
    data = task_data(tmp_path)
    data[key] = ' '
    with pytest.raises(ValueError):
        m_contracts.RepairTask(**data)


def test_config_does_not_accept_shell_command(tmp_path):
    with pytest.raises(ValueError):
        m_contracts.RepairTask(**task_data(tmp_path), command='echo secret')


@pytest.mark.parametrize('path', ['../app.py', 'C:/app.py', '/app.py', 'src\\app.py', '.git/a'])
def test_path_policy_rejects_escape(path):
    with pytest.raises(ValueError):
        m_contracts.safe_path(path)

