"""Produce M1 context/source/test sidecars without changing shared ContextPayload."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from vgar.contracts.context import ContextPayload, SourceRange
from vgar.contracts.handoff import (
    ContextManifest,
    ItemBinding,
    SourceScope,
    TestHints,
    adapt_test_hints,
    byte_digest,
    payload_digest,
    validate_context_handoff,
)
from vgar.contracts.prompt_context import CONTEXT_FORMAT, render_context_for_repair
from vgar.graph.builder import IGNORED_DIRECTORY_NAMES
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.test_selection import select_related_tests


def create_test_hints(document: dict, manifest: ContextManifest | dict, *, changed_paths: list[str],
                      symbol_ids: list[str] | None = None, failing_tests: list[str] | None = None,
                      selected_tests: list[str] | None = None) -> dict:
    sidecar = ContextManifest.model_validate(manifest.model_dump() if isinstance(manifest, ContextManifest) else manifest)
    if (document['graph_version'], document['repo_key'], document['repository_revision']) != (
            sidecar.graph_version, sidecar.repo_key, sidecar.repository_revision):
        raise ValueError('Test graph differs from context snapshot')
    requested_symbols = list(sidecar.items) if symbol_ids is None else symbol_ids
    if any(node_id not in sidecar.items for node_id in requested_symbols):
        raise ValueError('Use packed node IDs or changed_paths for test-link targets')
    if any(path not in sidecar.files for path in changed_paths):
        raise ValueError('Changed paths must belong to the declared source inventory')
    links, details = {}, {}
    for key in sorted(set(changed_paths + requested_symbols)):
        selection = select_related_tests(document, [key] if key in sidecar.items else [],
                                         changed_paths=[] if key in sidecar.items else [key])
        links[key] = selection['tests']
        details[key] = {name: selection[name] for name in ('candidates', 'truncated', 'traversal_limited', 'fallback_reason')}
    return TestHints(graph_version=sidecar.graph_version, repo_key=sidecar.repo_key,
                     repository_revision=sidecar.repository_revision, source_digest=sidecar.source_digest,
                     test_links=links, link_details=details, failing_selectors=failing_tests or [],
                     fallback_scope=selected_tests or []).model_dump(mode='json')


def create_context_handoff(document: dict, response: dict, source_repo: str | Path, *,
                            count_tokens: Callable[[str], int], counter_label: str,
                            changed_paths: list[str] | None = None, failing_tests: list[str] | None = None,
                            selected_tests: list[str] | None = None,
                            test_hint_policy: str = 'graph') -> dict:
    """Consume get_related_context's data wrapper, bind exact bytes, validate export."""
    if (response.get('graph_version'), response.get('repository_revision'), response.get('context_format'),
            response.get('counter_label')) != (document['graph_version'], document['repository_revision'],
                                              CONTEXT_FORMAT, counter_label):
        raise ValueError('Retrieval wrapper identity/format/counter differs from source graph')
    context = ContextPayload.model_validate(response['context'])
    retriever = GraphContextRetriever(document, source_repo, count_tokens=count_tokens, counter_label=counter_label)
    sources = retriever._verify_snapshot()
    bindings = {}
    if any(node_id not in retriever.nodes for node_id in context.anchor_ids):
        raise ValueError('Context anchor is outside the graph snapshot')
    for item in context.items:
        node = retriever.nodes.get(item.node_id)
        if node is None or (node['path'], node['qualified_name']) != (item.path, item.symbol):
            raise ValueError('Context node/path/symbol differs from the source graph')
        bounds = node['range']
        if item.range.model_dump() != {name: bounds[name] for name in SourceRange.model_fields}:
            raise ValueError('Context range differs from the source graph')
        metadata = response.get('source_metadata', {}).get(item.node_id)
        if metadata != {'content_hash': node['content_hash'], 'range_encoding': 'utf-8-bytes'}:
            raise ValueError('Retrieval source metadata differs from the graph')
        snippet = retriever._snippet(node, sources[item.path])
        if item.snippet != snippet:
            raise ValueError('Context snippet differs from the source graph')
        bindings[item.node_id] = ItemBinding(path=item.path, symbol=item.symbol, range=item.range,
            start_byte=bounds['start_byte'], end_byte=bounds['end_byte'], snippet_sha256=byte_digest(snippet.encode('utf-8')))
    files = {path: byte_digest(data) for path, data in sources.items()}
    manifest = ContextManifest(graph_version=document['graph_version'], repo_key=document['repo_key'],
        repository_revision=document['repository_revision'], context_sha256=payload_digest(context.model_dump(mode='json')),
        source_digest=payload_digest(files), files=files,
        source_scope=SourceScope(excluded_directories=sorted(IGNORED_DIRECTORY_NAMES)), items=bindings,
        counter_label=counter_label)
    validated = validate_context_handoff(context, manifest, source_repo, expected_graph_version=document['graph_version'],
        expected_repo_key=document['repo_key'], expected_revision=document['repository_revision'],
        count_tokens=count_tokens, counter_label=counter_label)
    paths = sorted({item.path for item in context.items}) if changed_paths is None else changed_paths
    if test_hint_policy == 'graph':
        hints = create_test_hints(document, manifest, changed_paths=paths,
                                  failing_tests=failing_tests, selected_tests=selected_tests)
    elif test_hint_policy == 'issue-only':
        if failing_tests:
            raise ValueError('Issue-only export does not admit failing-test oracle inputs')
        targets = sorted(set(paths) | set(bindings))
        hints = TestHints(graph_version=manifest.graph_version, repo_key=manifest.repo_key,
            repository_revision=manifest.repository_revision, source_digest=manifest.source_digest,
            test_links={target: [] for target in targets},
            link_details={target: {'candidates': [], 'truncated': False, 'traversal_limited': False,
                          'fallback_reason': 'W9_ISSUE_ONLY_NO_TEST_ORACLE'} for target in targets},
            failing_selectors=[], fallback_scope=selected_tests or []).model_dump(mode='json')
    else:
        raise ValueError('Unknown test hint policy')
    adapt_test_hints(hints, manifest, source_repo)
    return {'context': validated.model_dump(mode='json'), 'manifest': manifest.model_dump(mode='json'), 'test_hints': hints}


def write_context_handoff(bundle: dict, output_directory: str | Path) -> Path:
    """Write to a new output directory; never overwrite an earlier handoff."""
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name, key in (('context.json', 'context'), ('context_manifest.json', 'manifest'), ('test_links.json', 'test_hints')):
        (output / name).write_bytes((json.dumps(bundle[key], indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
    (output / 'repair-context.txt').write_bytes(render_context_for_repair(bundle['context']).encode('utf-8'))
    return output
