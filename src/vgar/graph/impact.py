"""Read-only mapping from exact baseline diff blocks to source graph symbols."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from vgar.contracts.impact import (
    ChangeSpan,
    ImpactReport,
    MappingLimits,
    canonical_hash,
)
from vgar.contracts.schema import validate_graph_document
from vgar.repair.contracts import safe_path
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


def diff_to_nodes(raw_diff: str, document: dict, source_repo: Path, *,
                  patch_policy: PatchPolicy) -> ImpactReport:
    """Validate snapshot and hunks without writing source, then map changed blocks.

    A block can support several symbols and an unmapped reason simultaneously.
    Full block coordinates are retained in every supporting record.
    """
    validate_graph_document(document)
    root = Path(source_repo).absolute()
    sources = _snapshot(document, root)
    graph_hash = canonical_hash(document)
    parsed = parse_unified_diff(raw_diff, patch_policy)
    if not set(parsed.files) <= set(sources):
        raise ValueError('Patch must modify existing files in graph source inventory')
    _bind(parsed, root)  # Pure read/prediction: validates exact source, offsets and EOF markers.
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
                    candidates = _smallest([n for n in nodes if
                        n['range']['start_byte'] < point < n['range']['end_byte']])
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
    return ImpactReport(repo_key=document['repo_key'], repository_revision=document['repository_revision'],
        graph_version=document['graph_version'], graph_hash=graph_hash,
        source_hash=canonical_hash({p: _digest(b) for p, b in sorted(sources.items())}),
        patch_hash=_digest(raw_diff.encode('utf-8')), changed=list(changed.values()), unmapped=unmapped,
        limits=MappingLimits(max_diff_bytes=patch_policy.max_bytes, max_files=patch_policy.max_files,
                             max_changed_lines=patch_policy.max_changed_lines))
