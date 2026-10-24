"""W9 integration inputs: existing admitted W78 fixture, no new admission."""
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def w9_case(tmp_path):
    from vgar.graph.token_counter import LocalTokenizerCounter
    from vgar.models.huggingface.local_chat import LocalChatTokenizer
    from vgar.repair.config import load_task
    task = load_task(ROOT/'examples/m2/tasks/single_file_login.json')
    source, bundle = tmp_path/'source', tmp_path/'bundle'
    shutil.copytree(task.source_repo, source, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    shutil.copytree(task.bundle_directory, bundle)
    task = task.model_copy(update={'source_repo': source, 'bundle_directory': bundle})
    manifest = ROOT/'artifacts/m2/w5-w6/tokenizer_manifest.json'
    return task, LocalTokenizerCounter(manifest), LocalChatTokenizer(manifest)


@pytest.fixture
def experiment_input():
    data = json.loads((ROOT/'configs/m2/variants/A0.json').read_text(encoding='utf-8'))
    return {'variant_policy': data, 'arm': 'bm25'}
