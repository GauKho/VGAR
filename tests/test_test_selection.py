from __future__ import annotations

import copy
import random

import pytest

from vgar.contracts.consumer import diagnose_changed_paths
from vgar.contracts.error import InvalidQueryError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.handoff import create_context_handoff
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.test_selection import select_related_tests


def build(tmp_path, sources):
    root = tmp_path / 'repository'
    root.mkdir()
    for relative, content in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8'))
    return root, PythonGraphBuilder(repo_key='demo/test-quality', repository_revision='fixture-v1').build(root)


def node_id(document, name, kind='Function'):
    return next(node['id'] for node in document['nodes'] if node['name'] == name and node['type'] == kind)


@pytest.mark.parametrize('query', ['path', 'symbol'])
def test_changed_test_file_or_test_symbol_selects_itself(tmp_path, query):
    _, doc = build(tmp_path, {
        'app.py': 'def target(): return 1\n',
        'tests/test_app.py': 'from app import target\ndef test_target(): assert target() == 1\n'
                             'class TestService:\n    def test_method(self): assert target() == 1\n',
    })
    ids = [] if query == 'path' else [node_id(doc, 'test_target', 'Test'), node_id(doc, 'test_method', 'Test')]
    paths = ['tests/test_app.py'] if query == 'path' else []
    selected = select_related_tests(doc, ids, changed_paths=paths)
    assert selected['tests'] == ['tests/test_app.py::TestService::test_method', 'tests/test_app.py::test_target']
    assert {item['reason'] for item in selected['candidates']} == {'changed_test' if query == 'path' else 'test_target'}
    assert not selected['coverage_verified'] and not selected['traversal_limited']


def test_equal_distance_evidence_uses_strongest_test_link_before_limit(tmp_path):
    _, doc = build(tmp_path, {
        'lib.py': 'def a_weak(): return 1\ndef m_other(): return 1\ndef z_strong(): return 1\n',
        'tests/test_app.py': 'import lib\nfrom lib import z_strong\n'
                             'def test_shared(): assert a_weak() + z_strong() == 2\n'
                             'def test_other(): assert lib.m_other() == 1\n',
    })
    ids = [node_id(doc, name) for name in ('a_weak', 'm_other', 'z_strong')]
    selected = select_related_tests(doc, ids, limit=1, failing_tests=['tests/test_app.py::test_other'])
    assert selected['candidates'][0]['selector'] == 'tests/test_app.py::test_shared'
    assert selected['candidates'][0]['confidence'] == pytest.approx(.95)
    assert set(selected['tests']) == {'tests/test_app.py::test_other', 'tests/test_app.py::test_shared'}
    assert selected['truncated'] and selected['fallback_reason'] == 'test_candidates_truncated'
    reordered = copy.deepcopy(doc)
    random.Random(42).shuffle(reordered['edges'])
    random.Random(17).shuffle(reordered['nodes'])
    assert select_related_tests(reordered, list(reversed(ids)), limit=1,
        failing_tests=['tests/test_app.py::test_other']) == selected


def test_equal_hop_routes_use_stronger_path_to_shared_caller(tmp_path):
    _, doc = build(tmp_path, {
        'app.py': 'def target(): return 1\n',
        'wrappers.py': 'from app import target as explicit_target\n'
                       'def a_weak(): return target()\n'
                       'def z_strong(): return explicit_target()\n'
                       'def shared(): return a_weak() + z_strong()\n',
        'tests/test_app.py': 'from wrappers import shared\ndef test_shared(): assert shared() == 2\n',
    })
    selected = select_related_tests(doc, [node_id(doc, 'target')])
    assert selected['tests'] == ['tests/test_app.py::test_shared']
    candidate = selected['candidates'][0]
    assert candidate['distance'] == 2 and candidate['confidence'] == pytest.approx(.95)
    assert candidate['via'] == [node_id(doc, name) for name in ('target', 'z_strong', 'shared')]
    assert not selected['traversal_limited']


def test_shorter_route_has_priority_over_stronger_longer_route(tmp_path):
    _, doc = build(tmp_path, {
        'app.py': 'def a_weak(): return 1\ndef z_strong(): return 1\ndef helper(): return z_strong()\n',
        'tests/test_app.py': 'from app import helper\ndef test_mixed(): assert a_weak() + helper() == 2\n',
    })
    selected = select_related_tests(doc, [node_id(doc, 'a_weak'), node_id(doc, 'z_strong')])
    candidate = selected['candidates'][0]
    assert candidate['distance'] == 0 and candidate['confidence'] == pytest.approx(.6)
    assert candidate['reason'] == 'direct_call'


@pytest.fixture
def deep_chain(tmp_path):
    return build(tmp_path, {
        'core.py': 'def target(): return 1\n',
        'chain.py': 'from core import target\ndef one(): return target()\n'
                    'def two(): return one()\ndef three(): return two()\n',
        'tests/test_app.py': 'from core import target\nfrom chain import three\n'
                             'def test_direct(): assert target() == 1\n'
                             'def test_deep(): assert three() == 1\n',
    })


def test_hop_limit_reports_omitted_callers_without_discarding_known_tests(deep_chain):
    _, doc = deep_chain
    selected = select_related_tests(doc, [node_id(doc, 'target')])
    assert selected['tests'] == ['tests/test_app.py::test_direct']
    assert selected['traversal_limited']
    assert selected['fallback_reason'] == 'test_traversal_limited'
    expanded = select_related_tests(doc, [node_id(doc, 'target')], max_hops=3)
    assert expanded['tests'] == ['tests/test_app.py::test_deep', 'tests/test_app.py::test_direct']
    assert not expanded['traversal_limited'] and expanded['fallback_reason'] is None


def test_real_hop_limit_flows_through_handoff_to_consumer_fallback(deep_chain, tmp_path):
    root, doc = deep_chain
    store = SQLiteGraphStore(tmp_path / 'graph.db')
    store.ingest(doc)
    service = SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label='test:characters')
    response = service.get_related_context([node_id(doc, 'target')], 10000,
        graph_version=doc['graph_version'], task_id='bounded-handoff')
    bundle = create_context_handoff(doc, response, root, count_tokens=len, counter_label='test:characters',
        changed_paths=['core.py'], failing_tests=['tests/test_app.py::test_deep'], selected_tests=['tests'])
    report = diagnose_changed_paths(bundle['test_hints'], bundle['manifest'], root, ['core.py'])
    assert report['targets']['core.py']['mapping_status'] == 'linked'
    assert report['targets']['core.py']['traversal_limited']
    assert report['fallback_required'] and report['fallback_available']
    assert set(report['candidate_tests']) == {'tests/test_app.py::test_direct', 'tests/test_app.py::test_deep'}
    assert report['fallback_scope'] == ('tests',)


def test_cycles_and_already_reachable_callers_do_not_trigger_false_limits(tmp_path):
    _, doc = build(tmp_path, {
        'app.py': 'def target(): return helper()\ndef helper(): return target()\n',
        'tests/test_app.py': 'from app import target\ndef test_target(): assert target()\n',
    })
    selected = select_related_tests(doc, [node_id(doc, 'target')], max_hops=1)
    assert selected['tests'] == ['tests/test_app.py::test_target']
    assert not selected['traversal_limited']


@pytest.mark.parametrize('field', ['changed_paths', 'failing_tests', 'selected_tests'])
@pytest.mark.parametrize('value', [False, '', {}, ()])
def test_falsy_non_list_input_is_not_silently_accepted(tmp_path, field, value):
    _, doc = build(tmp_path, {'app.py': 'def target(): return 1\n'})
    with pytest.raises(InvalidQueryError):
        select_related_tests(doc, [], **{field: value})
