"""M2-W11-2: baseline-relative IMPORTS cycles and host-owned architecture rules.

The caller supplies complete source bytes for each graph File inventory. This
module validates and reads snapshots only; it never builds graphs, applies a
patch, imports target modules or runs commands. Graph coverage is static module
imports, not runtime import completeness. Evidence publication belongs to W11-3.
"""
from __future__ import annotations

import ast
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from vgar.contracts.schema import SOURCE_BACKED_NODE_TYPES, validate_graph_document
from vgar.graph.builder import RESOLVER_PROFILE
from vgar.repair.check_result import CheckAnalysis
from vgar.repair.contracts import safe_path
from vgar.repair.structural_config import load_structural_config, validate_structural_config

__all__ = ['check_structure', 'load_structural_config']


def _hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _bytes_hash(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _sources(value) -> dict[str, bytes]:
    if not isinstance(value, Mapping):
        raise ValueError('Source snapshot must map normalized Python paths to immutable bytes')
    result = {}
    for path, raw in value.items():
        path = safe_path(path)
        if not path.endswith('.py') or type(raw) is not bytes:
            raise ValueError('Source snapshot requires Python paths and immutable bytes')
        result[path] = raw
    return dict(sorted(result.items()))


def _prefix_matches(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + '.')


def _normalized_import(owner, properties) -> str:
    imported, level = properties['imported_module'], properties['level']
    if level == 0:
        return imported
    parts = owner['properties']['module_name'].split('.')
    if not owner['properties']['is_package']:
        parts.pop()
    ascend = level - 1
    if ascend:
        parts = parts[:-ascend] if ascend <= len(parts) else []
    parts.extend(part for part in imported.lstrip('.').split('.') if part)
    return '.'.join(parts)


@dataclass
class _Import:
    node: dict
    owner: dict
    targets: tuple[str, ...]
    edges: list[dict]
    containment: list[dict]


@dataclass
class _Snapshot:
    graph: dict
    graph_hash: str
    modules: dict[str, dict]
    imports: list[_Import]
    pairs: dict[tuple[str, str], list[dict]]


def _validate_range(node, raw):
    bounds = node['range']
    start, end = bounds['start_byte'], bounds['end_byte']
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(raw):
        raise ValueError('Source node byte range is outside its bound file: ' + node['id'])
    for label, offset in (('start', start), ('end', end)):
        head = raw[:offset]
        actual = (head.count(b'\n') + 1, len(head.rsplit(b'\n', 1)[-1]))
        if actual != (bounds[label + '_line'], bounds[label + '_col']):
            raise ValueError('Source coordinates differ from byte offsets: ' + node['id'])
    if node.get('content_hash') != _bytes_hash(raw[start:end]):
        raise ValueError('Source node hash differs from supplied snapshot: ' + node['id'])
    if node['type'] in ('File', 'Module') and (start != 0 or end != len(raw)):
        raise ValueError('File/internal Module must bind the entire file: ' + node['id'])
    return raw[start:end]


def _snapshot(value, sources, threshold, side, diagnostics) -> _Snapshot:
    if not isinstance(value, Mapping):
        raise ValueError('Graph document must be a mapping')
    # JSON detachment rejects nonfinite/opaque metadata and protects caller objects.
    graph = json.loads(json.dumps(dict(value), ensure_ascii=False, allow_nan=False))
    validate_graph_document(graph)
    if (not isinstance(graph.get('repo_key'), str) or not graph['repo_key'].strip()
            or not isinstance(graph.get('repository_revision'), str) or not graph['repository_revision'].strip()):
        raise ValueError('Graph requires repository identity and revision')
    if graph.get('statistics', {}).get('resolver', {}).get('profile') != RESOLVER_PROFILE:
        raise ValueError('Graph requires current post-B10 resolver profile; rebuild snapshot')
    nodes = {n['id']: n for n in graph['nodes']}
    files = [n for n in nodes.values() if n['type'] == 'File']
    if len({n['path'] for n in files}) != len(files) or {n['path'] for n in files} != set(sources):
        raise ValueError('Exact Python File inventory differs from supplied source snapshot')
    parents = defaultdict(list)
    outgoing = defaultdict(list)
    for edge in graph['edges']:
        if edge['provenance']['source_revision'] != graph['repository_revision']:
            raise ValueError('Edge provenance revision differs from graph snapshot')
        if edge['type'] == 'CONTAINS':
            parents[edge['target_id']].append(edge)
        elif edge['type'] == 'IMPORTS':
            if edge.get('resolution') not in ('exact', 'static', 'heuristic', 'unresolved', 'ambiguous'):
                raise ValueError('IMPORTS edge has unsupported/missing resolution')
            outgoing[edge['source_id']].append(edge)
    repository = next(n for n in nodes.values() if n['type'] == 'Repository')
    chains = {}

    def ancestry(node):
        if node['id'] in chains:
            return chains[node['id']]
        current, chain, module, visited = node, [], None, set()
        while current['type'] != 'File':
            if current['id'] in visited:
                raise ValueError('Containment cycle in source ownership')
            visited.add(current['id'])
            if current['type'] == 'Module':
                if module is not None:
                    raise ValueError('Multiple Modules in source ownership chain')
                module = current
            links = sorted(parents[current['id']], key=lambda e: e['id'])
            if len({e['source_id'] for e in links}) != 1:
                raise ValueError('Source node has missing/ambiguous containment owner: ' + node['id'])
            chain.extend(links)
            current = nodes[links[0]['source_id']]
            if current.get('path') != node['path']:
                raise ValueError('Containment source/File paths disagree: ' + node['id'])
        roots = parents[current['id']]
        if {edge['source_id'] for edge in roots} != {repository['id']}:
            raise ValueError('File is not uniquely contained by repository')
        if node['type'] != 'File' and module is None:
            raise ValueError('Source node has no owning Module')
        chains[node['id']] = (module, chain)
        return module, chain

    modules, module_names, slices = {}, set(), {}
    for node in sorted(nodes.values(), key=lambda n: n['id']):
        if node['repo_key'] != graph['repo_key']:
            raise ValueError('Node repository differs from graph identity')
        if node['type'] == 'Module':
            external = node['properties'].get('is_external')
            if type(external) is not bool:
                raise ValueError('Module requires explicit is_external boolean')
            if external:
                if node.get('path') is not None or node.get('range') is not None:
                    raise ValueError('External Module cannot claim source ownership')
                continue
            name = node['properties'].get('module_name')
            if (not isinstance(name, str) or not name or node['qualified_name'] != name
                    or type(node['properties'].get('is_package')) is not bool):
                raise ValueError('Internal Module metadata is incomplete')
            if name in module_names or node['path'] in modules:
                raise ValueError('Ambiguous/duplicate internal module name or path; rebuild/repair graph scope')
            module_names.add(name)
            modules[node['path']] = node
        if node['type'] in SOURCE_BACKED_NODE_TYPES or node['type'] == 'Module':
            path = safe_path(node['path'])
            if path not in sources:
                raise ValueError('Source node is outside the exact File inventory')
            if node['type'] == 'File' and node['properties'].get('parse_status') != 'parsed':
                raise ValueError('Partial/failed file parse cannot establish structural completeness')
            slices[node['id']] = _validate_range(node, sources[path])
            ancestry(node)
    if set(modules) != set(sources):
        raise ValueError('Each source File needs exactly one internal Module')
    imports, pairs = [], defaultdict(list)
    for node in sorted(nodes.values(), key=lambda n: n['id']):
        if node['type'] != 'Import':
            continue
        owner, chain = ancestry(node)
        props = node['properties']
        raw_tree = ast.parse(slices[node['id']].decode('utf-8'))
        statement = raw_tree.body[0] if len(raw_tree.body) == 1 else None
        if isinstance(statement, ast.Import):
            declarations = {(a.name, None, a.asname, 0) for a in statement.names}
        elif isinstance(statement, ast.ImportFrom):
            declarations = {('.' * statement.level + (statement.module or ''), a.name, a.asname, statement.level)
                            for a in statement.names}
        else:
            raise ValueError('Import node bytes are not one Python import declaration')
        actual = tuple(props.get(k) for k in ('imported_module', 'imported_name', 'alias', 'level'))
        if (actual not in declarations or type(actual[3]) is not int
                or props.get('resolution_status') not in ('resolved', 'external', 'unresolved', 'ambiguous')):
            raise ValueError('Import metadata differs from its bound source declaration')
        base = _normalized_import(owner, props)
        lexical = {base} if base else set()
        if props['imported_name'] and props['imported_name'] != '*':
            lexical.add('.'.join(p for p in (base, props['imported_name']) if p))
        edges = sorted(outgoing[node['id']], key=lambda e: e['id'])
        if len({edge['target_id'] for edge in edges}) > 1:
            raise ValueError('Import has ambiguous graph targets')
        record = _Import(node, owner, tuple(sorted(lexical)), edges, chain)
        imports.append(record)
        if not edges:
            diagnostics.append({'side': side, 'import_id': node['id'], 'reason': 'NO_RESOLVED_IMPORT_EDGE'})
        for edge in edges:
            target = nodes[edge['target_id']]
            reason = None
            if props['resolution_status'] != 'resolved':
                reason = 'IMPORT_NOT_INTERNALLY_RESOLVED'
            elif target['properties']['is_external']:
                reason = 'EXTERNAL_IMPORT_TARGET'
            elif edge['resolution'] in ('unresolved', 'ambiguous'):
                reason = 'UNRESOLVED_IMPORT_EDGE'
            elif edge['confidence'] < threshold:
                reason = 'BELOW_CONFIDENCE_THRESHOLD'
            elif target['properties']['module_name'] != base:
                raise ValueError('Resolved import target differs from normalized source module')
            if reason:
                diagnostics.append({'side': side, 'import_id': node['id'], 'edge_id': edge['id'], 'reason': reason})
            else:
                pairs[(owner['path'], target['path'])].append(edge)
    for values in pairs.values():
        values.sort(key=lambda e: (-e['confidence'], e['id']))
    graph['nodes'].sort(key=lambda n: n['id'])
    graph['edges'].sort(key=lambda e: e['id'])
    return _Snapshot(graph, _hash(graph), modules, imports, dict(pairs))


def _path(adjacency, start, end):
    queue, previous = deque([start]), {start: None}
    while queue:
        node = queue.popleft()
        if node == end:
            result = []
            while node is not None:
                result.append(node)
                node = previous[node]
            return list(reversed(result))
        for target in sorted(adjacency.get(node, ())):
            if target not in previous:
                previous[target] = node
                queue.append(target)
    return None


def _result(violations, code, **metadata):
    return {'status': 'FAIL' if violations else 'PASS', 'reasons': [code] if violations else [],
            'violations': violations, **metadata}


def _cycles(before, after):
    adjacency = defaultdict(set)
    for source, target in after.pairs:
        adjacency[source].add(target)
    violations = []
    added = sorted(set(after.pairs) - set(before.pairs))
    for source, target in added:
        back = _path(adjacency, target, source)
        if back is None:
            continue
        modules = [source, *back]
        edges = [after.pairs[pair][0] for pair in zip(modules, modules[1:])]
        violations.append({'new_adjacency': {'source': source, 'target': target},
                           'witness': {'modules': modules, 'edges': edges}})
    return _result(violations, 'NEW_IMPORT_CYCLE', baseline_adjacencies=len(before.pairs),
                   candidate_adjacencies=len(after.pairs), new_adjacencies=len(added))


def _forbidden(snapshot, rules):
    violations = {}
    for record in snapshot.imports:
        owner_name = record.owner['properties']['module_name']
        for rule in rules:
            if not _prefix_matches(owner_name, rule['source']):
                continue
            for target in record.targets:
                if _prefix_matches(target, rule['target']):
                    key = (record.owner['path'], target, rule['source'], rule['target'])
                    violations.setdefault(key, {'source': record.owner['path'], 'source_module': owner_name,
                        'target': target, 'rule': dict(rule), 'import_id': record.node['id'],
                        'edges': record.edges, 'containment_edges': record.containment})
    return violations


def _layer(name, layers):
    matches = [(len(prefix), prefix, label) for label, prefixes in layers.items()
               for prefix in prefixes if _prefix_matches(name, prefix)]
    return max(matches)[2] if matches else None


def _layers(snapshot, policy, side, diagnostics):
    violations = {}
    for source, target in sorted(snapshot.pairs):
        a, b = snapshot.modules[source], snapshot.modules[target]
        source_layer = _layer(a['properties']['module_name'], policy['layers'])
        target_layer = _layer(b['properties']['module_name'], policy['layers'])
        if source_layer is None or target_layer is None:
            diagnostics.append({'side': side, 'source': source, 'target': target, 'reason': 'OUTSIDE_LAYER_POLICY_SCOPE'})
        elif target_layer not in policy['allowed_layer_imports'][source_layer]:
            violations[(source, target)] = {'source': source, 'target': target,
                'source_layer': source_layer, 'target_layer': target_layer, 'edges': snapshot.pairs[(source, target)]}
    return violations


def _delta(before, after, code):
    return _result([after[key] for key in sorted(set(after) - set(before))], code,
                   baseline_violation_count=len(before), candidate_violation_count=len(after))


def check_structure(before_graph: Mapping[str, Any], after_graph: Mapping[str, Any], *,
                    before_sources: Mapping[str, bytes], after_sources: Mapping[str, bytes],
                    repo_config: Mapping[str, Any] | None = None, min_confidence: float = 0.60) -> CheckAnalysis:
    """Compare static structural changes; missing config does not disable cycle checks.

    Invalid call arguments raise ValueError. Invalid graph/source binding or
    policy returns ERROR evidence; never a computed PASS. The result is internal
    CheckAnalysis, not a published verification verdict or evidence DTO.
    """
    if (isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float))
            or not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1):
        raise ValueError('min_confidence must be a finite number within [0,1]')
    sources = {'baseline': _sources(before_sources), 'candidate': _sources(after_sources)}
    def not_run(reason):
        return {'status': 'NOT_RUN', 'reasons': [reason], 'violations': []}

    details = {'scope': 'static-module-imports', 'min_confidence': float(min_confidence),
        'graph_hashes': {'baseline': None, 'candidate': None},
        'source_hashes': {side: {p: _bytes_hash(raw) for p, raw in files.items()} for side, files in sources.items()},
        'config_hash': None, 'subchecks': {name: not_run('NOT_EVALUATED' if name == 'cycles' else 'NO_CONFIG')
                                          for name in ('cycles', 'forbidden_imports', 'layers')},
        'diagnostics': [], 'coverage': {'cycle_scope': 'resolved internal module IMPORTS above threshold',
            'limitations': ['function/class-local and dynamic imports are not represented by this builder',
                           'from-package imports resolve the base package, not an inferred submodule']}}
    snapshots = {}
    for side, graph in (('baseline', before_graph), ('candidate', after_graph)):
        try:
            snap = _snapshot(graph, sources[side], min_confidence, side, details['diagnostics'])
            snapshots[side] = snap
            details['graph_hashes'][side] = snap.graph_hash
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError, UnicodeError, SyntaxError) as error:
            details['diagnostics'].append({'side': side, 'reason': 'STRUCTURAL_GRAPH_ERROR', 'message': str(error)})
    if len(snapshots) != 2:
        for item in details['subchecks'].values():
            item['reasons'] = ['INVALID_SNAPSHOT']
        return CheckAnalysis('ERROR', ('STRUCTURAL_GRAPH_ERROR',), details)
    before, after = snapshots['baseline'], snapshots['candidate']
    if before.graph['repo_key'] != after.graph['repo_key']:
        details['diagnostics'].append({'reason': 'STRUCTURAL_GRAPH_ERROR', 'message': 'Snapshot repositories differ'})
        details['subchecks'] = {name: not_run('INVALID_PAIR') for name in details['subchecks']}
        return CheckAnalysis('ERROR', ('STRUCTURAL_GRAPH_ERROR',), details)
    try:
        policy = None if repo_config is None else validate_structural_config(repo_config, repo_key=before.graph['repo_key'])
    except (ValueError, TypeError) as error:
        details['diagnostics'].append({'reason': 'STRUCTURAL_CONFIG_ERROR', 'message': str(error)})
        details['subchecks'] = {name: not_run('INVALID_CONFIG') for name in details['subchecks']}
        return CheckAnalysis('ERROR', ('STRUCTURAL_CONFIG_ERROR',), details)
    details['config_hash'] = _hash(policy) if policy is not None else None
    if not sources['baseline'] and not sources['candidate']:
        for item in details['subchecks'].values():
            item['reasons'] = ['EMPTY_SCOPE']
        return CheckAnalysis('NOT_RUN', ('STRUCTURAL_EMPTY_SCOPE',), details)
    checks = details['subchecks']
    checks['cycles'] = _cycles(before, after)
    if policy is not None and 'forbidden_imports' in policy:
        checks['forbidden_imports'] = _delta(_forbidden(before, policy['forbidden_imports']),
            _forbidden(after, policy['forbidden_imports']), 'FORBIDDEN_IMPORT')
    if policy is not None and 'layers' in policy:
        checks['layers'] = _delta(_layers(before, policy, 'baseline', details['diagnostics']),
            _layers(after, policy, 'candidate', details['diagnostics']), 'LAYER_VIOLATION')
    details['diagnostics'].sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    reasons = tuple(sorted({reason for c in checks.values() if c['status'] == 'FAIL' for reason in c['reasons']}))
    return CheckAnalysis('FAIL' if reasons else 'PASS', reasons, details)
