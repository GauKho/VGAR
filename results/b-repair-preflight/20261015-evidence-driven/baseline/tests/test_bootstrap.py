"""Catch accepting modified shared source or importing another VGAR checkout."""
import importlib
import sys
from pathlib import Path

import pytest


def api(module):
    try:
        return importlib.import_module('vgar_m2_w78.' + module)
    except ModuleNotFoundError:
        pytest.fail('Planned M2 API not implemented: ' + module)


def test_contract_import_origin_is_pinned():
    result = api('bootstrap').verify_reference()
    assert result['head'] == 'b8e2461635b81d1ae790445efea5c9757d91700a'
    assert Path(result['root']).name == 'VGAR'
    from vgar.contracts.consumer import HandoffTarget
    assert tuple(HandoffTarget.model_fields) == ('task_id', 'repo_key', 'repository_revision', 'graph_version')
    assert not any(name.startswith(('torch', 'transformers', 'vgar.mcp')) for name in sys.modules)


def test_shared_boundary_hash_change_rejected(tmp_path):
    module = api('bootstrap')
    root = tmp_path / 'reference'
    file = root / 'src/vgar/contracts/context.py'
    file.parent.mkdir(parents=True)
    file.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'):
        module.verify_hashes(root, {'src/vgar/contracts/context.py': '0' * 64})


def test_unrelated_documented_dirty_diff_preserved():
    result = api('bootstrap').verify_reference()
    assert 'src/vgar/evaluation/retrieval/scoring.py' in result['dirty_paths']

