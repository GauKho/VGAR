"""M1-W10-2: reverse-edge and node-by-line queries on the SQLite graph store."""
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore

FIXTURE = Path(__file__).parent / 'fixtures/m1_w10_impact'


@pytest.fixture
def store(tmp_path):
    document = PythonGraphBuilder(repo_key='demo/w10', repository_revision='fixture-v1').build(FIXTURE)
    store = SQLiteGraphStore(tmp_path / 'graph.db')
    store.ingest(document)
    ids = {n['qualified_name']: n['id'] for n in document['nodes']
           if n['type'] in ('Module', 'Class', 'Function', 'Method', 'Test')}
    return store, ids


def test_reverse_edges_by_type_and_confidence(store):
    store, ids = store
    calls = store.get_reverse_edges([ids['pkg.core.helper']], ('CALLS',))
    assert len(calls) == 4 and {e.edge_type for e in calls} == {'CALLS'}
    assert all(e.target_id == ids['pkg.core.helper'] for e in calls)
    assert [e.edge_id for e in calls] == sorted(e.edge_id for e in calls)
    both = store.get_reverse_edges([ids['pkg.core.helper'], ids['pkg.core.Base']], ('TESTS', 'INHERITS'))
    assert {(e.edge_type, e.source_id) for e in both} == {('TESTS', ids['tests.test_core.test_helper']),
                                                         ('INHERITS', ids['pkg.core.Child'])}
    assert store.get_reverse_edges([ids['pkg.core.Base']], ('INHERITS',), min_confidence=0.95) == []
    assert store.get_reverse_edges([], ('CALLS',)) == []


@pytest.mark.parametrize('types', [(), ('CALL',), ('CALLS', 'NOPE')])
def test_reverse_edges_rejects_unknown_types(store, types):
    store, ids = store
    with pytest.raises(ValueError):
        store.get_reverse_edges([ids['pkg.core.helper']], types)


def test_find_nodes_at_returns_innermost_first(store):
    store, ids = store
    assert [n.node_id for n in store.find_nodes_at('pkg/core.py', 3)] == [ids['pkg.core.Base.run'], ids['pkg.core.Base']]
    assert [n.node_id for n in store.find_nodes_at('pkg/core.py', 11)] == [ids['pkg.core.helper']]
    assert store.find_nodes_at('pkg/core.py', 12) == []  # blank line after the exclusive end
    assert store.find_nodes_at('missing.py', 1) == []
    with pytest.raises(ValueError):
        store.find_nodes_at('pkg/core.py', 0)


def test_service_exposes_contract_shapes(store):
    store, ids = store
    service = SQLiteGraphService(store)
    edges = service.get_reverse_edges([ids['pkg.core.helper']], ['TESTS'])
    assert [e.source_id for e in edges] == [ids['tests.test_core.test_helper']]
    nodes = service.find_nodes_at('pkg/api.py', 5)
    assert [n.repo.node_id for n in nodes] == [ids['pkg.api.use']] and nodes[0].repo.start_line == 4
