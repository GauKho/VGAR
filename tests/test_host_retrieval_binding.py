"""Host-owned graph snapshots must bind their actual disposable source.

Regression catches inheriting another repository's source/version or leaving
source_root unset. Real index/copy/store/retriever; no model or mock context.
"""
from dataclasses import replace

import pytest

from vgar.agents.nodes.prepare import prepare_workspace
from vgar.agents.runtime import Runtime
from vgar.cli import sandbox
from vgar.config.settings import Settings
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


@pytest.mark.parametrize('host', ['cli', 'workflow'])
@pytest.mark.parametrize('foreign_binding', [False, True])
def test_host_created_snapshot_retrieves_its_own_source(tmp_path, host, foreign_binding):
    repo = tmp_path / 'repo'
    (repo / 'src').mkdir(parents=True)
    raw = b'def answer():\n    return 0\n'
    (repo / 'src/demo.py').write_bytes(raw)
    other = tmp_path / 'other'
    (other / 'src').mkdir(parents=True)
    (other / 'src/demo.py').write_bytes(b'def answer():\n    return 99\n')
    original = Settings()
    manifest = tmp_path / 'not-loaded-tokenizer-manifest.json'
    original = replace(original, graph=replace(original.graph,
        source_root=other if foreign_binding else None,
        version='foreign-graph-version' if foreign_binding else None,
        tokenizer_manifest=manifest, allow_fallback_counter=False))

    def exercise(bound, workspace):
        # Reopen exactly as the graph consumer does, without a builder in memory.
        store = SQLiteGraphStore(bound.graph.database, graph_version=bound.graph.version)
        service = SQLiteGraphService(store, source_root=bound.graph.source_root,
            count_tokens=lambda text: len(text.split()), counter_label='fixture-words')
        task = service.find_task_anchors('demo.answer returns the wrong value')
        result = service.get_related_context(task['anchor_ids'], 1000, task['task_handle'])
        assert result.context.items and result.context.total_token_count <= 1000
        assert result.context.graph_version == store.get_graph_document()['graph_version']
        assert any('return 0' in item.snippet for item in result.context.items)
        assert all('return 99' not in item.snippet for item in result.context.items)
        assert bound.graph.source_root == workspace
        assert bound.workspace_root == workspace and workspace != repo
        assert bound.graph.tokenizer_manifest == manifest
        assert bound.graph.allow_fallback_counter is False

    if host == 'cli':
        with sandbox(repo, original) as (bound, lease):
            exercise(bound, lease.path)
    else:
        runtime = Runtime(settings=original)
        state = prepare_workspace({'repo_path': str(repo), 'work_dir': str(tmp_path / 'work'),
                                   'failing_tests': ['tests']}, runtime)
        from pathlib import Path
        exercise(runtime.sandboxed, Path(state['workspace_path']))
    assert (repo / 'src/demo.py').read_bytes() == raw
    assert original.graph.source_root == (other if foreign_binding else None)
    assert original.graph.version == ('foreign-graph-version' if foreign_binding else None)
