"""W9 lexical source-node baseline, using actual producer and M2 consumer."""
import copy
from types import SimpleNamespace

import pytest


@pytest.fixture
def case(tmp_path):
    from vgar.graph.builder import PythonGraphBuilder
    root = tmp_path / 'repo'
    (root / 'tests').mkdir(parents=True)
    (root / 'app.py').write_bytes(b'def normalize(name):\r\n    return name.strip()\r\n')
    (root / 'tests/test_app.py').write_text('def test_normalize(): assert True\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='fixture/project', repository_revision='a'*40).build(root)
    return root, graph, tmp_path


def counter(text):
    return len(text.encode('utf-8'))


def make_bundle(case, **kwargs):
    from vgar.evaluation.retrieval.bm25_handoff import create_bm25_handoff
    root, graph, _ = case
    return create_bm25_handoff(graph, root, issue_text='normalize name',
        count_tokens=counter, counter_label='fixture:bytes-not-model', **kwargs)


def receive(case, bundle):
    from vgar.graph.handoff import write_context_handoff
    from vgar.repair.context_adapter import load_handoff
    root, graph, tmp = case
    directory = write_context_handoff(bundle, tmp / 'bundle')
    task = SimpleNamespace(task_id='fixture-task', source_repo=root, bundle_directory=directory,
                           repo_key=graph['repo_key'], revision=graph['repository_revision'],
                           graph_version=graph['graph_version'])
    return load_handoff(task, counter, 'fixture:bytes-not-model'), task


def test_exact_source_packing_and_real_consumer(case):
    bundle = make_bundle(case)
    received, _ = receive(case, bundle)
    assert received.context.items
    assert received.context.token_budget == 8000
    assert not received.context.anchor_ids
    assert all(not i.path.startswith('tests/') for i in received.context.items)
    assert all(i.graph_rationale == ['LEXICAL_BM25_NO_GRAPH_TRAVERSAL'] for i in received.context.items)
    assert all(i.snippet.encode('utf-8') in (case[0] / i.path).read_bytes() for i in received.context.items)
    assert received.inputs['failing_selectors'] == ()
    assert received.inputs['fallback_scope'] == ('tests/test_app.py',)
    assert all(not selectors for selectors in received.inputs['test_links'].values())
    assert not received.metadata['collection_verified']


def test_deterministic_no_overlap_and_budget(case):
    first = make_bundle(case, budget_tokens=80)
    assert first == make_bundle(case, budget_tokens=80)
    assert first['context']['total_token_count'] <= 80
    spans = list(first['manifest']['items'].values())
    for i, left in enumerate(spans):
        for right in spans[i+1:]:
            assert left['path'] != right['path'] or left['end_byte'] <= right['start_byte'] or right['end_byte'] <= left['start_byte']


@pytest.mark.parametrize('fault', ['zero_hits', 'budget', 'source', 'counter'])
def test_invalid_producer_inputs(case, fault):
    from vgar.contracts.error import GraphError
    from vgar.evaluation.retrieval.bm25_handoff import create_bm25_handoff
    root, graph, _ = case
    query, budget, counting = 'normalize', 8000, counter
    if fault == 'zero_hits':
        query = 'zzzxxyynotpresent'
    elif fault == 'budget':
        budget = 1
    elif fault == 'source':
        (root / 'app.py').write_bytes(b'changed=1\n')
    else:
        counting = lambda text: True
    with pytest.raises((ValueError, GraphError)):
        create_bm25_handoff(graph, root, issue_text=query, count_tokens=counting,
                            counter_label='fixture:bytes-not-model', budget_tokens=budget)


@pytest.mark.parametrize('fault', ['source', 'bundle', 'identity', 'counter'])
def test_consumer_and_bundle_integrity(case, fault):
    from vgar.repair.context_adapter import load_handoff
    received, task = receive(case, make_bundle(case))
    if fault == 'source':
        (case[0] / 'app.py').write_bytes(b'changed=2\n')
    elif fault == 'bundle':
        (task.bundle_directory / 'context.json').write_text('{}', encoding='utf-8')
        with pytest.raises(ValueError):
            received.assert_unchanged()
        return
    elif fault == 'identity':
        task.revision = 'b'*40
    with pytest.raises(ValueError):
        load_handoff(task, counter, 'different-counter' if fault == 'counter' else 'fixture:bytes-not-model')


def test_utf8_source_is_not_transcoded(case):
    from vgar.graph.builder import PythonGraphBuilder
    root, _, tmp = case
    (root / 'app.py').write_bytes('def normalize(name):\n    return "tên" + name\n'.encode())
    graph = PythonGraphBuilder(repo_key='fixture/project', repository_revision='a'*40).build(root)
    bundle = make_bundle((root, graph, tmp))
    assert any('tên' in i['snippet'] for i in bundle['context']['items'])


def test_edges_cannot_influence_bm25_ranking(case):
    bundle = make_bundle(case)
    root, graph, tmp = case
    graph = copy.deepcopy(graph)
    graph['edges'] = []
    second = make_bundle((root, graph, tmp))
    assert bundle['context'] == second['context']


@pytest.mark.parametrize('raw', [b'', b' \r\n'])
def test_named_empty_modules_cannot_enter_context(case, raw):
    from vgar.graph.builder import PythonGraphBuilder
    root, _, tmp = case
    (root / 'normalize.py').write_bytes(raw)
    graph = PythonGraphBuilder(repo_key='fixture/project', repository_revision='a'*40).build(root)
    bundle = make_bundle((root, graph, tmp))
    received, _ = receive((root, graph, tmp), bundle)
    assert all(i.snippet.strip() for i in received.context.items)
    assert all(i.path != 'normalize.py' for i in received.context.items)
