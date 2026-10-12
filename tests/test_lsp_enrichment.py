from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.lsp_resolver import DefinitionMapper, LspConfig
from vgar.graph.scip_resolver import ScipConfig, current_fingerprint
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.test_selection import select_related_tests
from vgar.observability.graph_trace import GraphTrace
from test_scip_enrichment import bundle


SERVER = Path(__file__).parent / 'fixtures/lsp/server.py'


def fixture(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root/'app.py').write_text('class Worker:\n    def execute(self): return 1\n\ndef invoke():\n    "🚀"; worker.execute()\n    worker = None\n', encoding='utf-8')
    return root


def build(root, tmp_path, mode='config', **options):
    config = LspConfig(command=(sys.executable, str(SERVER), mode, str(root/'app.py')),
                       output_directory=tmp_path/'logs', **options)
    return PythonGraphBuilder(repo_key='demo/lsp', repository_revision='fixture', lsp=config,
                              trace=GraphTrace(tmp_path/'trace.jsonl')).build(root)


@pytest.mark.parametrize('mode', ['config', 'unicode', 'link'])
def test_live_protocol_maps_calls_and_uses_utf16_without_stdout_logs(tmp_path, mode):
    root = fixture(tmp_path)
    document = build(root, tmp_path, mode, strict=True)
    edge = next(e for e in document['edges'] if e['type']=='CALLS')
    assert edge['properties']['binding_kind'] == 'lsp'
    assert edge['target_id'].endswith('app.Worker.execute')
    assert edge['provenance']['source_tool'] == 'fixture-lsp'
    assert document['statistics']['resolver']['lsp_call_count'] == 1
    assert document['statistics']['resolver']['lsp']['status'] == 'ready'
    assert all(n['graph_version'] == document['graph_version'] for n in [*document['nodes'], *document['edges']])
    trace = (tmp_path/'trace.jsonl').read_text(encoding='utf-8')
    assert 'lsp_call_result' in trace and 'publishDiagnostics' not in trace
    assert '"text"' not in trace
    again = build(root, tmp_path, mode, strict=True)
    assert document['graph_version'] == again['graph_version']


@pytest.mark.parametrize('mode,status', [('ambiguous', 'ambiguous'), ('external', 'external_or_non_callable'),
                                       ('non_callable', 'external_or_non_callable')])
def test_uncertain_lsp_bindings_never_create_internal_calls(tmp_path, mode, status):
    root = fixture(tmp_path)
    graph = build(root, tmp_path, mode)
    assert not any(e['type']=='CALLS' for e in graph['edges'])
    call = next(n for n in graph['nodes'] if n['type']=='CallSite')
    assert call['properties']['resolution_status'] == 'unresolved'
    assert call['properties']['resolution_reason'] == status


@pytest.mark.parametrize('mode', ['exit', 'malformed', 'timeout', 'query_timeout', 'invalid_range', 'encoding'])
def test_transport_failure_has_bounded_fallback_and_strict_mode(tmp_path, mode):
    root = fixture(tmp_path)
    started = time.monotonic()
    graph = build(root, tmp_path, mode, initialize_timeout=.2, request_timeout=.2, total_timeout=2)
    assert time.monotonic()-started < 8
    assert graph['statistics']['resolver']['lsp']['status'] == 'fallback'
    assert graph['statistics']['resolver']['lsp']['reason']
    assert not any(e['type']=='CALLS' for e in graph['edges'])
    with pytest.raises((OSError, ValueError, RuntimeError)):
        build(root, tmp_path, mode, initialize_timeout=.2, request_timeout=.2, total_timeout=2, strict=True)


def test_missing_runtime_static_fallback_and_query_cap(tmp_path):
    root = fixture(tmp_path)
    (root/'app.py').write_text((root/'app.py').read_text(encoding='utf-8')+'    worker.execute()\n', encoding='utf-8')
    missing = PythonGraphBuilder(repo_key='demo/missing', repository_revision='fixture',
                                 lsp=LspConfig(command=(str(tmp_path/'missing.exe'),))).build(root)
    assert missing['statistics']['resolver']['lsp']['error_type'] == 'FileNotFoundError'
    graph = build(root, tmp_path, max_requests=1)
    report = graph['statistics']['resolver']['lsp']
    assert report['request_count'] == report['resolved_count'] == 1
    assert report['status'] == 'partial' and report['unqueried_call_count'] == 1
    assert len([e for e in graph['edges'] if e['type']=='CALLS']) == 1


def test_empty_result_keeps_static_fallback_but_authoritative_external_blocks_it(tmp_path):
    root = fixture(tmp_path)
    (root/'app.py').write_text('def invoke(): return helper()\n', encoding='utf-8')
    (root/'other.py').write_text('def helper(): pass\n', encoding='utf-8')
    graph = build(root, tmp_path, 'empty')
    call = next(n for n in graph['nodes'] if n['type']=='CallSite')
    edge = next(e for e in graph['edges'] if e['type']=='CALLS')
    assert edge['properties']['binding_kind'] == 'heuristic'
    assert call['properties']['lsp_fallback_reason'] == 'no_definition'
    blocked = build(root, tmp_path, 'external')
    assert not any(e['type']=='CALLS' for e in blocked['edges'])


def test_source_change_is_fatal_even_with_fallback_enabled(tmp_path):
    root = fixture(tmp_path)
    with pytest.raises(ValueError, match='changed during LSP'):
        build(root, tmp_path, 'mutate')


@pytest.mark.parametrize('external', [True, False])
def test_lsp_does_not_override_scip_resolved_or_external_binding(tmp_path, external):
    root = tmp_path/'repo'
    root.mkdir()
    manifest = bundle(root, tmp_path/'bundle', external=external)
    graph = PythonGraphBuilder(repo_key='demo/authority', repository_revision='fixture',
        scip=ScipConfig(bundle=manifest, strict=True),
        lsp=LspConfig(command=(str(tmp_path/'missing.exe'),), strict=True)).build(root)
    assert graph['statistics']['resolver']['lsp']['status'] == 'not_needed'
    calls = [e for e in graph['edges'] if e['type']=='CALLS']
    assert len(calls) == (0 if external else 1)
    assert all(e['properties']['binding_kind']=='scip' for e in calls)


def test_partial_timeout_retains_verified_result_and_marks_remaining_site(tmp_path):
    root = fixture(tmp_path)
    (root/'app.py').write_text((root/'app.py').read_text(encoding='utf-8')+'    worker.execute()\n', encoding='utf-8')
    graph = build(root, tmp_path, 'partial_timeout', request_timeout=.2)
    report = graph['statistics']['resolver']['lsp']
    assert report['status'] == 'partial' and report['resolved_count'] == 1
    assert report['unqueried_call_count'] == 1
    assert len([e for e in graph['edges'] if e['type']=='CALLS']) == 1
    calls = [n for n in graph['nodes'] if n['type']=='CallSite']
    assert any(n['properties'].get('lsp_fallback_reason')=='server_failure' for n in calls)


def test_lsp_links_feed_existing_context_and_test_selection(tmp_path):
    root = fixture(tmp_path)
    (root/'tests').mkdir()
    # This fixture server responds within the opened document. Give the test
    # file the same declaration locations so the target can be checked exactly.
    (root/'tests/test_worker.py').write_text('class Worker:\n    def execute(self): return 1\n\ndef test_execute():\n    worker.execute()\n', encoding='utf-8')
    graph = build(root, tmp_path)
    target = next(n for n in graph['nodes'] if n['type']=='Method' and n['path'].startswith('tests/'))
    payload = GraphContextRetriever(graph, root, count_tokens=lambda text:len(text.split()), counter_label='fixture').retrieve([target['id']], 100)
    assert payload.context.graph_version == graph['graph_version']
    assert target['id'] in {item.node_id for item in payload.context.items}
    selected = select_related_tests(graph, symbol_ids=[target['id']])
    assert selected['tests'] == ['tests/test_worker.py::test_execute']
    assert selected['candidates'][0]['confidence'] == .95


def test_mapping_handles_encoded_drive_and_percent_once_and_checks_snapshot(tmp_path):
    root = tmp_path/'repo %20'
    root.mkdir()
    path = root/'app %20.py'
    path.write_text('def execute(): pass\n', encoding='utf-8')
    graph = PythonGraphBuilder(repo_key='demo/uri', repository_revision='fixture').build(root)
    mapper = DefinitionMapper(root, graph['nodes'], current_fingerprint(root))
    uri = path.as_uri()
    # Pyright encodes the drive colon, while preserving the file URI scheme.
    if len(uri)>9 and uri[9]==':':
        uri = uri[:9]+'%3A'+uri[10:]
    location = {'uri': uri, 'range': {'start': {'line': 0, 'character': 4}, 'end': {'line': 0, 'character': 11}}}
    assert mapper.map([location])[0] == 'resolved'
    location['uri'] = 'untitled:app.py'
    assert mapper.map([location])[0] == 'external_or_non_callable'
    path.write_text('def changed(): pass\n', encoding='utf-8')
    fresh = DefinitionMapper(root, [], mapper.fingerprints)
    with pytest.raises(ValueError, match='snapshot changed'):
        fresh.lines(path.name)


@pytest.mark.parametrize('options', [{'max_requests':0}, {'request_timeout':float('nan')},
                                    {'total_timeout':True}, {'command':'server'}, {'max_requests':1.5}])
def test_invalid_lsp_limits_are_rejected(options):
    with pytest.raises(ValueError):
        LspConfig(**options)
