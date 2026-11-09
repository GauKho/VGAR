"""Read-only mapping from exact baseline diff blocks to source graph symbols, then reverse impact."""
from __future__ import annotations

import hashlib
import os
import stat
from collections import defaultdict
from pathlib import Path

from vgar.contracts.impact import (
    ChangeSpan,
    ImpactReport,
    MappingLimits,
    canonical_hash,
)
from vgar.contracts.schema import validate_graph_document
from vgar.repair.contracts import safe_path
from vgar.repair.api_check import check_api, with_api_risk
from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff

_SYMBOLS = {'Function', 'Method', 'Class'}


def _digest(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def _linked(path: Path) -> bool:
    attrs = getattr(path.lstat(), 'st_file_attributes', 0)
    return path.is_symlink() or bool(attrs & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _snapshot(document: dict, root: Path) -> dict[str, bytes]:
    from vgar.graph.builder import IGNORED_DIRECTORY_NAMES
    if not root.is_dir() or _linked(root):
        raise ValueError('Source root is missing or linked')
    sources = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRECTORY_NAMES)
        for name in dirs + [f for f in files if f.endswith('.py')]:
            if _linked(Path(directory) / name):
                raise ValueError('Source inventory uses filesystem links')
        for name in sorted(files):
            if name.endswith('.py'):
                path = Path(directory) / name
                relative = safe_path(path.relative_to(root).as_posix())
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Source path escapes repository')
                sources[relative] = path.read_bytes()
    file_nodes = [n for n in document['nodes'] if n['type'] == 'File']
    paths = [safe_path(n['path']) for n in file_nodes]
    if len(paths) != len(set(paths)) or set(paths) != set(sources):
        raise ValueError('Source inventory differs from graph snapshot')
    for node in document['nodes']:
        if node['repo_key'] != document['repo_key']:
            raise ValueError('Graph node repository differs from document')
        if not node.get('path') or not node.get('range'):
            continue
        path = safe_path(node['path'])
        if path not in sources:
            raise ValueError('Graph source node is outside inventory')
        data, bounds = sources[path], node['range']
        start, end = bounds['start_byte'], bounds['end_byte']
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(data):
            raise ValueError('Invalid graph byte range')
        for label, offset in (('start', start), ('end', end)):
            head = data[:offset]
            actual = (head.count(b'\n') + 1, len(head.rsplit(b'\n', 1)[-1]))
            if actual != (bounds[label + '_line'], bounds[label + '_col']):
                raise ValueError('Graph source coordinates differ from byte range')
        if _digest(data[start:end]) != node.get('content_hash'):
            raise ValueError('Graph source hash differs from baseline')
        if node['type'] == 'File' and (start != 0 or end != len(data)):
            raise ValueError('File node must bind all baseline bytes')
        if node['type'] in _SYMBOLS:
            if start == end:
                raise ValueError('Baseline symbol range must be nonempty')
            try:
                data[:start].decode('utf-8')
                data[:end].decode('utf-8')
            except UnicodeDecodeError as error:
                raise ValueError('Symbol range is not a UTF-8 boundary') from error
    return sources


def _blocks(hunk: dict, hunk_index: int):
    old = hunk['old'] - bool(hunk['oc'])
    new = hunk['new'] - bool(hunk['nc'])
    body, i = hunk['body'], 0
    while i < len(body):
        if body[i][0] == ' ':
            old, new, i = old + 1, new + 1, i + 1
            continue
        old_begin, new_begin = old, new
        while i < len(body) and body[i][0] != ' ':
            old += body[i][0] == '-'
            new += body[i][0] == '+'
            i += 1
        oc, nc = old - old_begin, new - new_begin
        yield ChangeSpan(hunk_index=hunk_index, old_start=old_begin + bool(oc),
                         old_count=oc, new_start=new_begin + bool(nc), new_count=nc)


def _smallest(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []
    size = min(n['range']['end_byte'] - n['range']['start_byte'] for n in candidates)
    return [n for n in candidates if n['range']['end_byte'] - n['range']['start_byte'] == size]


def _inserted_text(hunk: dict, span: ChangeSpan) -> str | None:
    """First non-blank line added by this block."""
    line = hunk['new'] - bool(hunk['nc'])
    for sign, content, _ in hunk['body']:
        if sign in ' +':
            line += 1
            if sign == '+' and span.new_start <= line < span.new_start + span.new_count and content.strip():
                return content
    return None


def _trailing_symbols(nodes: list[dict], data: bytes, point: int, indent: int) -> list[dict]:
    """Innermost symbols that a block inserted at `point` extends: only blank or comment lines
    separate them from it, and it is indented deeper than they are."""
    found = []
    for node in sorted((n for n in nodes if n['range']['end_byte'] <= point), key=lambda n: -n['range']['end_byte']):
        gap = data[node['range']['end_byte']:point].splitlines()
        if not all(not line.strip() or line.strip().startswith(b'#') for line in gap):
            break  # any earlier symbol has this same code in its gap
        if indent > node['range']['start_col']:
            found.append(node)
    return _smallest(found)


def diff_to_nodes(raw_diff: str, document: dict, source_repo: Path, *,
                  patch_policy: PatchPolicy) -> ImpactReport:
    """Validate snapshot and hunks without writing source, then map changed blocks.

    A block can support several symbols and an unmapped reason simultaneously.
    Full block coordinates are retained in every supporting record.
    """
    return _map_patch(raw_diff, document, source_repo, patch_policy=patch_policy)[0]


def _map_patch(raw_diff: str, document: dict, source_repo: Path, *,
               patch_policy: PatchPolicy) -> tuple[ImpactReport, dict[str, bytes], dict[str, bytes]]:
    """diff_to_nodes plus the baseline and predicted bytes of every patched file (same snapshot)."""
    validate_graph_document(document)
    root = Path(source_repo).absolute()
    sources = _snapshot(document, root)
    graph_hash = canonical_hash(document)
    parsed = parse_unified_diff(raw_diff, patch_policy)
    if not set(parsed.files) <= set(sources):
        raise ValueError('Patch must modify existing files in graph source inventory')
    predicted, _ = _bind(parsed, root)  # Pure read/prediction: validates exact source, offsets and EOF markers.
    changed, unmapped = {}, []
    for path, hunks in parsed.files.items():
        nodes = [n for n in document['nodes'] if n['type'] in _SYMBOLS and n['path'] == path]
        lines = sources[path].splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        for index, hunk in enumerate(hunks, 1):
            for span in _blocks(hunk, index):
                matches, reasons = {}, set()
                if span.old_count:
                    for line in range(span.old_start - 1, span.old_start - 1 + span.old_count):
                        candidates = _smallest([n for n in nodes if
                            n['range']['start_byte'] < offsets[line + 1]
                            and offsets[line] < n['range']['end_byte']])
                        if len(candidates) == 1:
                            matches[candidates[0]['id']] = candidates[0]
                        else:
                            reasons.add('AMBIGUOUS_BASELINE_SYMBOL' if candidates else 'MODULE_LEVEL_CHANGE')
                    basis = 'baseline_changed_lines'
                else:
                    point = offsets[span.old_start]
                    text = _inserted_text(hunk, span)
                    candidates = (text is not None
                                  and _trailing_symbols(nodes, sources[path], point, len(text) - len(text.lstrip(' \t')))
                                  or _smallest([n for n in nodes if
                                                n['range']['start_byte'] < point < n['range']['end_byte']]))
                    if len(candidates) == 1:
                        matches[candidates[0]['id']] = candidates[0]
                    else:
                        reasons.add('AMBIGUOUS_BASELINE_SYMBOL' if candidates else 'NO_BASELINE_SYMBOL_AT_INSERTION')
                    basis = 'insertion_in_existing_scope'
                for node_id, node in matches.items():
                    entry = changed.setdefault(node_id, {'node_id': node_id, 'path': path, 'kind': node['type'],
                        'source_range': {k: node['range'][k] for k in ('start_line', 'start_col', 'end_line', 'end_col')},
                        'basis': basis, 'spans': []})
                    if basis == 'baseline_changed_lines':
                        entry['basis'] = basis
                    if span not in entry['spans']:
                        entry['spans'].append(span)
                for reason in sorted(reasons):
                    unmapped.append({'path': path, 'span': span, 'reason': reason})
    if sources != _snapshot(document, root) or canonical_hash(document) != graph_hash:
        raise ValueError('Source or graph changed during mapping')
    report = ImpactReport(repo_key=document['repo_key'], repository_revision=document['repository_revision'],
        graph_version=document['graph_version'], graph_hash=graph_hash,
        source_hash=canonical_hash({p: _digest(b) for p, b in sorted(sources.items())}),
        patch_hash=_digest(raw_diff.encode('utf-8')), changed=list(changed.values()), unmapped=unmapped,
        limits=MappingLimits(max_diff_bytes=patch_policy.max_bytes, max_files=patch_policy.max_files,
                             max_changed_lines=patch_policy.max_changed_lines))
    return report, {path: sources[path] for path in parsed.files}, predicted


def _python_only(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: data for path, data in files.items() if path.endswith('.py')}


# Walk order; a node reached by several relations keeps the first one found.
_RELATIONS = ('CALLS', 'IMPORTS', 'INHERITS', 'TESTS')
_ARCH_RELATIONS = ('LIFT', 'EXPOSES_PORT', 'CONSUMES_PORT', 'DEPENDS_ON')
_CALLERS = {'Function', 'Method', 'Test'}
_LIFTED = {'Function', 'Method', 'Class', 'Module'}  # Tests belong to no Component
_ARCH_KINDS = ('Port', 'Component')
_CONSTRUCTORS = ('__init__', '__new__')  # building a base object never runs the subclass constructor


def _public(qualified_name: str) -> bool:
    return all(not part.startswith('_') or (part.startswith('__') and part.endswith('__'))
               for part in qualified_name.split('.'))


def compute_impact(report: ImpactReport, document: dict, *, max_hops: int = 2, max_nodes: int = 200,
                   min_confidence: float = 0.6) -> ImpactReport:
    """Fill `impacted` and `risk` by walking CALLS/IMPORTS/INHERITS/TESTS backwards from the changed nodes,
    plus their Ports and Components when the graph has G_arch (spec IM-1 §4).

    Only edges present in the graph with confidence >= min_confidence are followed; nothing is inferred.
    Relations the walk cannot see (REFERENCES, call sites with no resolved target) are listed as unsupported.
    """
    if type(max_hops) is not int or not 1 <= max_hops <= 5:
        raise ValueError('max_hops must be within [1, 5]')
    if type(max_nodes) is not int or not 1 <= max_nodes <= 1000:
        raise ValueError('max_nodes must be within [1, 1000]')
    if isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float)) or not 0 <= min_confidence <= 1:
        raise ValueError('min_confidence must be within [0, 1]')
    validate_graph_document(document)
    if canonical_hash(document) != report.graph_hash:
        raise ValueError('Impact graph differs from the mapped graph snapshot')
    nodes = {n['id']: n for n in document['nodes']}
    parent, incoming, resolved, bases = {}, defaultdict(lambda: defaultdict(list)), set(), defaultdict(list)
    for edge in document['edges']:
        if edge['type'] == 'CONTAINS':
            parent[edge['target_id']] = edge['source_id']
        elif edge['type'] in (*_RELATIONS, 'CONSUMES_PORT', 'DEPENDS_ON') and edge['confidence'] >= min_confidence:
            incoming[edge['target_id']][edge['type']].append(edge['source_id'])
            if edge['type'] == 'CALLS':
                resolved.add(edge['source_id'])
            elif edge['type'] == 'INHERITS':
                bases[edge['source_id']].append(edge['target_id'])
    method_of = {(parent[n['id']], n['name']): n['id'] for n in document['nodes'] if n['type'] == 'Method' and n['id'] in parent}
    port_of = {n['properties']['symbol_id']: n['id'] for n in document['nodes'] if n['type'] == 'Port'}
    component_of = {path: n['id'] for n in document['nodes'] if n['type'] == 'Component' for path in n['properties']['files']}
    has_arch = any(n['type'] == 'Component' for n in document['nodes'])
    seeds = sorted(c.node_id for c in report.changed)
    # DEPENDS_ON spans whole packages: one step from the changed code, or it reports most of the repo (spec §4.3).
    seed_components = {component_of[nodes[s]['path']] for s in seeds if nodes[s]['path'] in component_of}
    port_sources = set(seeds)  # the changed nodes and the base methods they override

    def module_of(node_id):
        while node_id is not None and nodes[node_id]['type'] != 'Module':
            node_id = parent.get(node_id)
        return node_id

    def callers(node_id):
        return sorted({parent[cs] for cs in incoming[node_id]['CALLS']
                       if cs in parent and nodes[parent[cs]]['type'] in _CALLERS})

    def overridden(method_id):
        """The nearest definition of this method on each branch of its ancestors (spec §4.4)."""
        name = nodes[method_id]['name']
        if name in _CONSTRUCTORS or method_id not in parent:
            return []
        found, visited, stack = set(), {parent[method_id]}, list(bases[parent[method_id]])
        while stack:
            owner = stack.pop()
            if owner in visited:
                continue
            visited.add(owner)
            base = method_of.get((owner, name))
            if base is None:
                stack.extend(bases[owner])
            else:
                found.add(base)
        return sorted(found)

    def lift(node_id):
        """Architecture nodes of a node; reaching them costs no hop."""
        node = nodes[node_id]
        if node_id in port_sources and node_id in port_of:
            yield 'EXPOSES_PORT', port_of[node_id]
        if node['type'] in _LIFTED and node['path'] in component_of:
            yield 'LIFT', component_of[node['path']]

    def neighbours(node_id):
        node = nodes[node_id]
        if node['type'] == 'Port':
            yield from (('CONSUMES_PORT', component) for component in sorted(set(incoming[node_id]['CONSUMES_PORT'])))
            return
        if node['type'] == 'Component':
            if node_id in seed_components:
                yield from (('DEPENDS_ON', component) for component in sorted(set(incoming[node_id]['DEPENDS_ON'])))
            return
        yield from (('CALLS', caller) for caller in callers(node_id))
        module = module_of(node_id)
        if module is not None:
            importers = {module_of(imp) for imp in incoming[module]['IMPORTS']}
            yield from (('IMPORTS', m) for m in sorted(importers - {None, module}))
        owner = parent.get(node_id) if node['type'] == 'Method' else node_id if node['type'] == 'Class' else None
        if owner is not None and nodes[owner]['type'] == 'Class':
            yield from (('INHERITS', sub) for sub in sorted(set(incoming[owner]['INHERITS'])))
        yield from (('TESTS', test) for test in sorted(set(incoming[node_id]['TESTS'])))
        if has_arch and node_id in seeds and node['type'] == 'Method':
            for base in overridden(node_id):
                port_sources.add(base)
                yield 'INHERITS', base

    seen, items = set(seeds), []

    def visit(sources, step, hops):
        """Record what `step` reaches from `sources`. The flag says max_nodes cut the walk short."""
        reached = []
        for source in sources:
            for relation, target in step(source):
                if target in seen:
                    continue
                if len(items) == max_nodes:
                    return reached, True
                seen.add(target)
                reached.append(target)
                items.append({'node_id': target, 'qualified_name': nodes[target]['qualified_name'],
                              'path': nodes[target]['path'], 'kind': nodes[target]['type'],
                              'hops': hops, 'relation': relation, 'via': source})
        return reached, False

    level, truncated = seeds, False
    for hops in range(max_hops + 1):
        lifted, truncated = visit(level, lift, hops)
        if truncated or hops == max_hops:
            break
        # Stable sort: architecture nodes first so max_nodes cannot cut them, symbols keep discovery order.
        level, truncated = visit(sorted(level + lifted, key=lambda i: nodes[i]['type'] not in _ARCH_KINDS), neighbours, hops + 1)
        if truncated:
            break
    unresolved = sum(n['type'] == 'CallSite' and n['id'] not in resolved for n in document['nodes'])
    impacted = {'status': 'PARTIAL' if truncated else 'COMPLETE', 'items': items, 'max_hops': max_hops,
                'max_nodes': max_nodes, 'min_confidence': float(min_confidence),
                'traversed': [*_RELATIONS, *(_ARCH_RELATIONS if has_arch else ())],
                'unsupported': [{'relation': 'REFERENCES', 'reason': 'NOT_TRAVERSED'},
                                {'relation': 'CALLS', 'reason': 'UNRESOLVED_CALL_SITES', 'count': unresolved}]}

    def unavailable(names, reason):
        return [{'name': name, 'available': False, 'reason': reason} for name in names]

    names = ('public_symbol_changed', 'fan_in', 'impacted_callers', 'impacted_tests')
    arch_names = ('public_ports_changed', 'components_affected')
    if seeds:
        values = (any(_public(nodes[s]['qualified_name']) for s in seeds),
                  max(len(callers(s)) for s in seeds),
                  sum(item['kind'] in ('Function', 'Method') and item['relation'] == 'CALLS' for item in items),
                  sum(item['kind'] == 'Test' for item in items))
        features = [{'name': n, 'available': True, 'value': v} for n, v in zip(names, values)]
        # Default only: analyze_patch_impact overwrites it with the API check result (M2-W11-1, H3).
        features += unavailable(('signature_changed',), 'NOT_COMPUTED')
    else:
        features = unavailable((*names, 'signature_changed'), 'NO_CHANGED_NODES')
    if not has_arch:
        features += unavailable(arch_names, 'NOT_COMPUTED')
    elif seeds:
        arch_values = (sum(s in port_of for s in seeds), sum(item['kind'] == 'Component' for item in items))
        features += [{'name': n, 'available': True, 'value': v} for n, v in zip(arch_names, arch_values)]
    else:
        features += unavailable(arch_names, 'NO_CHANGED_NODES')
    # Cycle detection needs a whole-repo G' and test results need a run; analyze_patch_impact fills ports_lost.
    features += unavailable(('dependency_cycle_introduced', 'covering_tests_pass', 'ports_lost'), 'NOT_COMPUTED')
    return ImpactReport.model_validate({**report.model_dump(), 'impacted': impacted,
                                        'risk': {'status': 'COMPLETE', 'features': features}})


def analyze_patch_impact(raw_diff: str, document: dict, source_repo: Path, *, patch_policy: PatchPolicy,
                         **limits) -> ImpactReport:
    """diff_to_nodes, then compute_impact on the same graph snapshot; signature risk and lost Ports from the patched bytes."""
    from vgar.graph.port_check import check_lost_ports
    mapped, before, after = _map_patch(raw_diff, document, source_repo, patch_policy=patch_policy)
    report = compute_impact(mapped, document, **limits)
    if not _python_only(after):
        return report
    analysis = check_api(_python_only(before), _python_only(after))
    data = with_api_risk(report, analysis).model_dump(mode='python')
    check = check_lost_ports(document, _python_only(after), analysis)
    data['port_check'] = check.model_dump(mode='python')
    if check.status == 'COMPLETE':
        data['risk']['features'] = [f for f in data['risk']['features'] if f['name'] != 'ports_lost'] + [
            {'name': 'ports_lost', 'available': True, 'value': len(check.lost)}]
    return ImpactReport.model_validate(data)
