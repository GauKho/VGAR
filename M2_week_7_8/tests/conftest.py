from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
VGAR = ROOT.parent
M1_RUN = VGAR / 'artifacts/m1/w7-w8/handoff-demos/20261014T072245Z-a8015356523c45cfa264244c07d252b0'
GRAPHS = {
    'single_file_login': 'sha256:e1fe94d21f10f112cd3a5e2a39f88e1fb26a760ee8ea3eaa6d3bac608d1ec371',
    'multi_file_invoice': 'sha256:1bbff47bc1ee5098b1f3d8f37dc5952faa9127224763e651c66630d838adb93e',
    'missing_links': 'sha256:ac135fa480d1f999d33e943fc36e003b76a570ba59ee5ba8cf495e76bb285c51',
}


@pytest.fixture
def m1_case(tmp_path):
    from vgar_m2_w78.bootstrap import verify_reference
    verify_reference()
    from vgar_m2_w78.contracts import RepairTask
    from vgar.graph.token_counter import LocalTokenizerCounter
    case = 'single_file_login'
    source, bundle = tmp_path / 'source', tmp_path / 'bundle'
    shutil.copytree(VGAR / 'tests/fixtures/w7_w8_handoff' / case / 'repo', source,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    shutil.copytree(M1_RUN / case / 'bundle', bundle)
    task = RepairTask(task_id=case, issue_text='auth.py login accepts whitespace-only names; trim the name before checking whether it is empty.',
        source_repo=source, bundle_directory=bundle, repo_key='demo/w7-w8/' + case,
        revision='fixture-v1', graph_version=GRAPHS[case],
        failing_selectors=('tests/test_auth.py::test_login_rejects_whitespace',),
        fallback_scope=('tests',), allowed_source_paths=('auth.py',), trusted_fixture=True)
    counter = LocalTokenizerCounter(VGAR / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
    return task, counter


class CharacterChatTokenizer:
    """Explicit unit-test tokenizer; never reported as model token usage."""
    label = 'unit-test:characters'
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        text = '\n'.join(item['role'] + ':' + item['content'] for item in messages) + '\nassistant:'
        return list(text.encode('utf-8')) if tokenize else text

