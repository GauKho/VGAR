from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.retrieval import _words
from vgar.graph.source_evidence import SourceEvidence
from vgar.graph.source_evidence import diagnostic_lines
from concurrent.futures import ThreadPoolExecutor
import pytest
from vgar.contracts.error import GraphError


def test_source_terms_exclude_locals_nested_scopes_and_include_literal_tags(tmp_path):
    (tmp_path/'app.py').write_text('''def outer(client):
    """timeout"""
    timeout = 1
    def inner():
        return "timeout"
    return client.mode == "log"
''', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/source-terms', repository_revision='fixture').build(tmp_path)
    outer = next(n for n in graph['nodes'] if n['name']=='outer')
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    retriever.retrieve([outer['id']], 100, issue_text='outer log timeout')
    terms = retriever._source_evidence.terms[outer['id']]
    assert 'log' in terms and 'mode' in terms
    assert not terms & {'client', 'timeout', 'inner'}
    inner = next(n for n in graph['nodes'] if n['name']=='inner')
    assert evidence_terms(retriever, inner) == {'timeout'}


def evidence_terms(retriever, node):
    return retriever._source_evidence.terms[node['id']]


def test_source_scores_are_stable_across_interleaved_queries(tmp_path):
    (tmp_path/'app.py').write_text('def read(client): return client.timeout\ndef write(client): return client.retry\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/source-cache', repository_revision='fixture').build(tmp_path)
    read = next(n for n in graph['nodes'] if n['name']=='read')
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    retriever.retrieve([read['id']], 100, issue_text='timeout')
    evidence = retriever._source_evidence
    queries = [frozenset({'timeout'}), frozenset({'retry'}), frozenset(), frozenset({'timeout', 'retry'})] * 8
    expected = [evidence._score(read['id'], query) for query in queries]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = list(pool.map(lambda query:evidence.similarity(read['id'], query), queries))
    assert actual == expected
    assert actual[0] > 0 and actual[1] == actual[2] == 0
    assert evidence._similarity.cache_info().hits > 0


def test_nested_async_function_in_exception_handler_has_its_own_evidence():
    source = b'''def outer(client):
    try:
        client.read()
    except ValueError:
        async def retry():
            return client.timeout
        return retry
'''
    # SourceEvidence consumes graph locations independently of how a builder
    # obtains them; these ranges cover a nested async def in an exception arm.
    nodes = [dict(id=name, name=name, type='Function', path='app.py',
                  range=dict(start_line=line, start_col=column))
             for name, line, column in (('outer', 1, 0), ('retry', 5, 8))]
    evidence = SourceEvidence(nodes, {'app.py':source}, _words)
    assert 'timeout' in evidence.terms['retry']
    assert 'timeout' not in evidence.terms['outer']


def test_cached_evidence_does_not_accept_changed_source(tmp_path):
    source = tmp_path/'app.py'
    source.write_text('def handle(client): return client.timeout\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/source-refresh', repository_revision='fixture').build(tmp_path)
    handle = next(n for n in graph['nodes'] if n['name']=='handle')
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    retriever.retrieve([handle['id']], 100, issue_text='timeout')
    source.write_text('def handle(client): return client.retry\n', encoding='utf-8')
    with pytest.raises(GraphError):
        retriever.retrieve([handle['id']], 100, issue_text='timeout')


def test_runtime_message_finds_emitter_without_symbol_anchor(tmp_path):
    (tmp_path/'app.py').write_text('''def emit(logger, key):
    message = _("unknown configuration key cannot be loaded %r")
    logger.warning(message, key)

def other():
    """unknown configuration key cannot be loaded"""
    return "unknown configuration key cannot be loaded"
''', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/messages', repository_revision='fixture').build(tmp_path)
    emit = next(n for n in graph['nodes'] if n['name']=='emit')
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    issue = '```text\nWARNING: unknown configuration key cannot be loaded "alpha"\n```'
    retriever.retrieve([emit['id']], 100, issue_text='emit fails')
    assert not retriever._source_evidence.has_messages
    result = retriever.retrieve([], 100, issue_text=issue)
    assert retriever._source_evidence.has_messages
    assert result.candidates[0]['node_id'] == emit['id']
    assert result.candidates[0]['graph_rationale'] == ['SOURCE_DIAGNOSTIC']
    assert result.context.anchor_ids == [emit['id']]
    assert result.config['diagnostic_seed_ids'] == [emit['id']]
    assert not retriever.retrieve([], 100, issue_text='unknown configuration key cannot be loaded').candidates
    assert not retriever.retrieve([], 100, issue_text='WARNING: unrelated configuration key cannot be loaded').candidates
    (tmp_path/'app.py').write_text('def emit(): pass\n', encoding='utf-8')
    with pytest.raises(GraphError):
        retriever.retrieve([], 100, issue_text=issue)


def test_runtime_messages_remain_ambiguous_and_respect_filters(tmp_path):
    (tmp_path/'app.py').write_text('''def first():
    raise ValueError("invalid resource identifier cannot be accepted %s" % "name")
def second(logger):
    logger.error(f"invalid resource identifier cannot be accepted {1}")
def short(logger):
    logger.warning("failed request")
''', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/shared-message', repository_revision='fixture').build(tmp_path)
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    issue = 'ValueError: invalid resource identifier cannot be accepted abc'
    result = retriever.retrieve([], 100, issue_text=issue)
    seeds = result.config['diagnostic_seed_ids']
    assert len(seeds) == 2
    assert all(c['confidence'] == .5 for c in result.candidates if c['node_id'] in seeds)
    assert not retriever.retrieve([], 100, issue_text='WARNING: failed request').candidates
    assert not retriever.retrieve([], 100, issue_text=issue, include=lambda _:False).candidates
    assert diagnostic_lines('ordinary prose\nERROR: broken resource') == ('error: broken resource',)


def test_component_hint_recovers_code_outside_unrelated_anchor(tmp_path):
    component = tmp_path/'pkg'/'widget'
    component.mkdir(parents=True)
    (component/'worker.py').write_text('def handle(client): return client.timeout\ndef unrelated(client): return client.retry\n', encoding='utf-8')
    (tmp_path/'pkg'/'other.py').write_text('def helper(): pass\ndef first(): pass\ndef second(): pass\ndef third(): pass\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/component', repository_revision='fixture').build(tmp_path)
    nodes = {n['name']:n for n in graph['nodes'] if n['type']=='Function'}
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture')
    result = retriever.retrieve([nodes['helper']['id']], 100, issue_text='widget timeout')
    assert result.config['component_seed_ids'] == [nodes['handle']['id']]
    handle = next(c for c in result.candidates if c['node_id']==nodes['handle']['id'])
    assert handle['graph_rationale'] == ['SOURCE_COMPONENT']
    assert handle['confidence'] == .45 and handle['component_hints'] == ['widget']
    assert not retriever.retrieve([], 100, issue_text='pkg timeout').config['component_seed_ids']
    assert not retriever.retrieve([], 100, issue_text='wid timeout').config['component_seed_ids']
    assert not retriever.retrieve([], 100, issue_text='widget timeout', include=lambda n: '/widget/' not in n['path']).config['component_seed_ids']
    assert not retriever.retrieve([nodes['handle']['id']], 100, issue_text='widget timeout').config['component_seed_ids']


def test_component_seed_limit_and_explicit_disable(tmp_path):
    from vgar.graph.retrieval import RetrievalConfig
    directory = tmp_path/'widget'
    directory.mkdir()
    (directory/'worker.py').write_text('\n'.join(f'def handle_{i}(client): return client.timeout' for i in range(20)), encoding='utf-8')
    (tmp_path/'other.py').write_text('\n'.join(f'def other_{i}(): pass' for i in range(21)), encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/component-cap', repository_revision='fixture').build(tmp_path)
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture', config=RetrievalConfig(max_candidates=10))
    result = retriever.retrieve([], 100, issue_text='widget timeout')
    assert len(result.config['component_seed_ids']) == result.config['component_seed_limit'] == 1
    disabled = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture', config=RetrievalConfig(use_component_seeds=False))
    assert not disabled.retrieve([], 100, issue_text='widget timeout').candidates


def test_forward_annotations_are_not_executable_body_evidence(tmp_path):
    (tmp_path/'app.py').write_text('''def handle(value: "domain.Invoice") -> "Result":
    return value
def decoy(value):
    """domain Invoice Result"""
    return value
''', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/annotations', repository_revision='fixture').build(tmp_path)
    evidence = SourceEvidence(graph['nodes'], {'app.py':(tmp_path/'app.py').read_bytes()}, _words)
    handle = next(n for n in graph['nodes'] if n['name']=='handle')
    decoy = next(n for n in graph['nodes'] if n['name']=='decoy')
    assert not evidence.terms[handle['id']]
    assert not evidence.terms[decoy['id']]


def test_topic_evidence_ranks_implementation_above_reproduction_vocabulary(tmp_path):
    from vgar.graph.retrieval import RetrievalConfig
    (tmp_path/'app.py').write_text('''def execute(client):
    return client.timeout
def classes(client):
    return client.label
''', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/topic', repository_revision='fixture').build(tmp_path)
    nodes = {n['name']:n for n in graph['nodes'] if n['type']=='Function'}
    issue = 'Timeout handling\n```python\nclass Example:\n    pass\n```'
    ret = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture', config=RetrievalConfig(max_hops=0, use_topic_evidence=True))
    result = ret.retrieve([n['id'] for n in nodes.values()], 100, issue_text=issue)
    assert result.candidates[0]['node_id'] == nodes['execute']['id']
    assert 'class' not in result.config['topic_words']
    assert result.candidates[0]['topic_source_similarity'] > 0
    assert ret._similarity_cache.cache_info().hits > 0
    queries = [frozenset({'timeout'}), frozenset({'label'}), frozenset()] * 10
    expected = [ret._score_task_similarity(nodes['execute']['id'], q, q, 0, True) for q in queries]
    with ThreadPoolExecutor(max_workers=4) as pool:
        scores = list(pool.map(lambda q:ret._task_similarity(nodes['execute'], q, topic_words=q), queries))
    assert scores == expected


def test_topic_focus_can_be_disabled_and_does_not_accept_stale_source(tmp_path):
    from vgar.graph.retrieval import RetrievalConfig
    source = tmp_path/'app.py'
    source.write_text('def execute(client): return client.timeout\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/topic-control', repository_revision='fixture').build(tmp_path)
    node = next(n for n in graph['nodes'] if n['name']=='execute')
    ret = GraphContextRetriever(graph, tmp_path, count_tokens=lambda _:1, counter_label='fixture', config=RetrievalConfig(use_topic_evidence=False))
    result = ret.retrieve([node['id']], 100, issue_text='Timeout handling')
    assert result.config['topic_words'] == []
    assert result.candidates[0]['topic_source_similarity'] is None
    source.write_text('def execute(client): return client.retry\n', encoding='utf-8')
    with pytest.raises(GraphError):
        ret.retrieve([node['id']], 100, issue_text='Timeout handling')
