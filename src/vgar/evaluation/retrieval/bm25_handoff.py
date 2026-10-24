"""W9 lexical node-range baseline. Graph edges never enter BM25 scoring."""
from __future__ import annotations

from vgar.contracts.context import ContextItem, ContextPayload, SourceRange
from vgar.contracts.prompt_context import CONTEXT_FORMAT
from vgar.evaluation.retrieval.bm25 import BM25
from vgar.evaluation.retrieval.chunks import is_source
from vgar.graph.handoff import create_context_handoff
from vgar.graph.retrieval import GraphContextRetriever


def production_node(node: dict) -> bool:
    return (node['type'] in {'Function', 'Method', 'Class', 'File', 'Module'}
            and bool(node.get('path')) and bool(node.get('range'))
            and is_source(node['path']))


def test_scope(document: dict) -> list[str]:
    return sorted({n['path'] for n in document['nodes'] if n['type'] == 'File'
                   and n['properties'].get('is_test_file')})


def usable_node_ids(document: dict, sources: dict) -> set[str]:
    """Identical empty/whitespace source exclusion for both retrieval arms."""
    return {n['id'] for n in document['nodes'] if production_node(n)
            and sources[n['path']][n['range']['start_byte']:n['range']['end_byte']].strip()}


def response_for(document: dict, context: ContextPayload, counter_label: str) -> dict:
    nodes = {n['id']: n for n in document['nodes']}
    return {'graph_version': document['graph_version'], 'repository_revision': document['repository_revision'],
            'context_format': CONTEXT_FORMAT, 'counter_label': counter_label,
            'context': context.model_dump(mode='json'),
            'source_metadata': {i.node_id: {'content_hash': nodes[i.node_id]['content_hash'],
                                          'range_encoding': 'utf-8-bytes'} for i in context.items}}


def create_bm25_handoff(document, source_repo, *, issue_text, count_tokens, counter_label,
                        budget_tokens=8000, failing_tests=(), selected_tests=()) -> dict:
    if type(budget_tokens) is not int or budget_tokens <= 0:
        raise ValueError('Invalid snippet budget')
    if not isinstance(issue_text, str) or not issue_text.strip() or failing_tests:
        raise ValueError('W9 requires issue-only retrieval')
    retriever = GraphContextRetriever(document, source_repo, count_tokens=count_tokens, counter_label=counter_label)
    sources = retriever._verify_snapshot()
    usable = usable_node_ids(document, sources)
    corpus = []
    for node in document['nodes']:
        if node['id'] in usable:
            snippet = retriever._snippet(node, sources[node['path']])
            corpus.append({'chunk_id': node['id'], 'text': node['path']+' '+node['qualified_name']+'\n'+snippet,
                           'node': node, 'snippet': snippet})
    ranked = BM25(corpus).search(issue_text)
    items, occupied, omissions, ranks = [], [], [], []
    total = 0
    for row in ranked:
        node, snippet = row['node'], row['snippet']
        bounds = node['range']
        ranks.append({'node_id': node['id'], 'score': row['score']})
        if any(p == node['path'] and bounds['start_byte'] < end and start < bounds['end_byte']
               for p, start, end in occupied):
            omissions.append({'node_id': node['id'], 'reason': 'overlap'})
            continue
        cost = count_tokens(snippet)
        if type(cost) is not int or cost < 0:
            raise ValueError('Counter must return a nonnegative integer')
        if total + cost > budget_tokens:
            omissions.append({'node_id': node['id'], 'reason': 'token_budget'})
            continue
        items.append(ContextItem(node_id=node['id'], path=node['path'], symbol=node['qualified_name'],
            range=SourceRange(**{k: bounds[k] for k in SourceRange.model_fields}), snippet=snippet,
            relevance_score=row['score']/(1+row['score']), graph_distance=0,
            graph_rationale=['LEXICAL_BM25_NO_GRAPH_TRAVERSAL'], confidence=1.0, token_count=cost))
        total += cost
        occupied.append((node['path'], bounds['start_byte'], bounds['end_byte']))
    if not items:
        raise ValueError('BM25 produced no source context within budget')
    context = ContextPayload(graph_version=document['graph_version'], anchor_ids=[], items=items,
        total_token_count=total, token_budget=budget_tokens,
        truncated=any(r['reason'] == 'token_budget' for r in omissions))
    bundle = create_context_handoff(document, response_for(document, context, counter_label), source_repo,
        count_tokens=count_tokens, counter_label=counter_label, selected_tests=list(selected_tests or test_scope(document)),
        test_hint_policy='issue-only')
    bundle['retrieval_diagnostics'] = {'profile':'w9-bm25-node-ranges', 'k1':1.2, 'b':0.75,
        'excluded_empty_source_nodes':sum(production_node(n) and n['id'] not in usable for n in document['nodes']),
        'ranked':ranks, 'omissions':omissions, 'confidence_meaning':'exact-source-binding-not-relevance-probability'}
    return bundle
