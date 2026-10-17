import shutil

import pytest

from w78_support import EXAMPLES, GRAPHS, REPO


@pytest.fixture
def m1_case(tmp_path):
    from vgar.graph.token_counter import LocalTokenizerCounter
    from vgar.repair.contracts import RepairTask
    case = 'single_file_login'
    source, bundle = tmp_path / 'source', tmp_path / 'bundle'
    shutil.copytree(EXAMPLES / 'snapshots' / case, source,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    shutil.copytree(EXAMPLES / 'handoffs' / case, bundle)
    task = RepairTask(task_id=case, issue_text='auth.py login accepts whitespace-only names; trim the name before checking whether it is empty.',
        source_repo=source, bundle_directory=bundle, repo_key='demo/w7-w8/' + case,
        revision='fixture-v1', graph_version=GRAPHS[case],
        failing_selectors=('tests/test_auth.py::test_login_rejects_whitespace',),
        fallback_scope=('tests',), allowed_source_paths=('auth.py',), trusted_fixture=True)
    counter = LocalTokenizerCounter(REPO / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
    return task, counter
