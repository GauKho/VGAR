from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.contracts.context import ContextPayload
from vgar.contracts.prompt_context import render_context_for_repair
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.test_selection import select_related_tests
from vgar.graph.visualization import plot_graph_tracking
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'app.py').write_text('def target(): return 1\ndef helper(): return target()\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests/test_app.py').write_text('from app import helper\ndef test_helper(): assert helper() == 1\n', encoding='utf-8')
    document = PythonGraphBuilder(repo_key='demo/w7', repository_revision='fixture').build(root)
    return root, document


def test_transitive_tests_and_explicit_fallbacks(snapshot):
    _, doc = snapshot
    target = next(n['id'] for n in doc['nodes'] if n['name'] == 'target' and n['type'] == 'Function')
    result = select_related_tests(doc, [target], failing_tests=['tests/test_other.py::test_failed'])
    assert result['selection_mode'] == 'graph'
    assert result['tests'] == ['tests/test_app.py::test_helper', 'tests/test_other.py::test_failed']
    assert result['candidates'][0]['reason'] == 'transitive_call'
    assert result['candidates'][0]['distance'] == 1
    assert result['coverage_verified'] is False
    without_links = {**doc, 'edges': [e for e in doc['edges'] if e['type'] != 'TESTS']}
    assert select_related_tests(without_links, [target], failing_tests=['tests/test_app.py'])['selection_mode'] == 'failing_tests'
    assert select_related_tests(without_links, [target], selected_tests=['tests/test_app.py'])['selection_mode'] == 'selected_tests'
    assert select_related_tests(without_links, [target])['requires_full_suite']


def test_path_selection_and_limits(snapshot):
    _, doc = snapshot
    assert select_related_tests(doc, [], changed_paths=['app.py'])['tests'] == ['tests/test_app.py::test_helper']
    for path in ['../app.py', 'C:/app.py', '/app.py']:
        with pytest.raises(Exception):
            select_related_tests(doc, [], changed_paths=[path])
    target = next(n['id'] for n in doc['nodes'] if n['name'] == 'target' and n['type'] == 'Function')
    assert not select_related_tests(doc, [target], max_hops=0)['tests']


def test_mcp_context_metadata_prompt_and_test_selection(snapshot, tmp_path, monkeypatch):
    root, doc = snapshot
    store = SQLiteGraphStore(tmp_path / 'graph.db')
    store.ingest(doc)
    service = SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label='test:characters')
    monkeypatch.setattr(graph_server, 'graph_service', service)
    monkeypatch.setattr(graph_server, '_audit_logger', AuditLogger(tmp_path / 'audit.jsonl'))
    monkeypatch.setenv('VGAR_GRAPH_DEBUG_LOG', str(tmp_path / 'debug.jsonl'))
    version = doc['graph_version']
    target = next(n['id'] for n in doc['nodes'] if n['name'] == 'target' and n['type'] == 'Function')
    response = graph_server.get_related_context([target], 1000, version, 'task', 'target fails')
    assert response['status'] == 'PASS'
    data = response['data']
    assert data['context_format'] == 'vgar.context.v1'
    payload = ContextPayload.model_validate(data['context'])
    assert 'schema_version' not in data['context']
    assert all(data['source_metadata'][item.node_id]['content_hash'] for item in payload.items)
    prompt = render_context_for_repair(payload)
    assert 'app.py' in prompt and 'app.target' in prompt and 'unified diff' in prompt
    selected = graph_server.get_related_tests([target], version)
    assert selected['status'] == 'PASS' and selected['data']['tests']
    assert graph_server.get_related_tests([target], 'stale')['status'] == 'ERROR'
    events = [json.loads(line) for line in (tmp_path / 'debug.jsonl').read_text().splitlines()]
    assert {'retrieval_start', 'retrieval_candidate', 'retrieval_complete', 'test_selection'} <= {e['event'] for e in events}
    assert all('snippet' not in event for event in events)
    (root / 'app.py').write_text('def target(): return 2\n')
    assert graph_server.get_related_context([target], 1000, version, 'task')['status'] == 'ERROR'
    assert 'retrieval_error' in (tmp_path / 'debug.jsonl').read_text()


def test_plot_has_bounded_graph_and_complete_resolver_counts(snapshot, tmp_path):
    _, doc = snapshot
    pytest.importorskip('matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure = plot_graph_tracking(doc, max_nodes=2, events=[{'event': 'resolver_fallback'}])
    assert len(figure.axes) == 2
    assert len(figure.axes[0].collections) <= 2
    assert sum(bar.get_width() for bar in figure.axes[1].patches) == doc['statistics']['callsite_count']
    figure.savefig(tmp_path / 'plot.png')
    assert (tmp_path / 'plot.png').stat().st_size > 1000
    plt.close(figure)
