"""I1 (M1-X2, RQ3): does the graph impact region of a gold patch reach the FAIL_TO_PASS tests?

Compared with a diff-only baseline (files in the diff + test files named after them). Dev split only.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import NamedTuple

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.impact import analyze_patch_impact
from vgar.repair.patch import PatchPolicy


class TestKey(NamedTuple):
    path: str | None    # file path (pytest), module path without '.py' (Django), or None (bare name)
    cls: str | None
    name: str


TestKey.__test__ = False  # not a pytest test class

_DJANGO = re.compile(r'^(\w+) \(([\w.]+)\.(\w+)\)$')
_PARAMS = re.compile(r'\[.*\]$')


def parse_f2p(raw: str) -> TestKey | None:
    """pytest node id, Django 'name (module.Class)', or a bare test name; None when unrecognised."""
    if '::' in raw:
        parts = raw.split('::')
        if not parts[0].endswith('.py'):
            return None
        return TestKey(parts[0], '.'.join(parts[1:-1]) or None, _PARAMS.sub('', parts[-1]))
    django = _DJANGO.match(raw)
    if django:
        name, module, cls = django.groups()
        return TestKey(module.replace('.', '/'), cls, name)
    if raw.isidentifier():
        return TestKey(None, None, raw)
    return None


def _node_class(node: dict) -> str | None:
    """Class part of a Test node: qualified_name minus its name and the module prefix taken from its path."""
    path = node['path'][:-3] if node['path'].endswith('.py') else node['path']
    segments = path.split('/')
    if segments[-1] == '__init__':
        segments = segments[:-1]
    parts = node['qualified_name'].split('.')[:-1]
    for k in range(min(len(parts), len(segments)), -1, -1):
        if parts[:k] == segments[len(segments) - k:]:
            return '.'.join(parts[k:]) or None
    return '.'.join(parts) or None


def _path_matches(key: TestKey, node_path: str, test_patch_files: set[str]) -> bool:
    if key.path is None:
        return node_path in test_patch_files
    if key.path.endswith('.py'):
        return node_path == key.path
    return any(node_path == key.path + tail or node_path.endswith('/' + key.path + tail)
               for tail in ('.py', '/__init__.py'))


def match_tests(keys: list[TestKey], test_nodes: list[dict], test_patch_files: set[str]) -> dict[int, set[str]]:
    """Index of each key -> ids of the Test nodes it names; unmatched keys are absent."""
    matched: dict[int, set[str]] = {}
    for index, key in enumerate(keys):
        ids = {node['id'] for node in test_nodes
               if node.get('name', node['qualified_name'].rsplit('.', 1)[-1]) == key.name
               and _path_matches(key, node['path'], test_patch_files)
               and (key.path is None or _node_class(node) == key.cls)}
        if ids:
            matched[index] = ids
    return matched


# ---- patches --------------------------------------------------------------------------------------------------------

_GIT_LINES = ('diff --git ', 'index ', 'new file mode', 'deleted file mode', 'old mode', 'new mode')


def _sections(raw: str) -> list[tuple[str, str]]:
    """(path, text from its '--- ' header) for every file of a unified diff, in order."""
    lines = raw.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines)
              if line.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ ')]
    sections = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        while end > start + 2 and lines[end - 1].startswith(_GIT_LINES):
            end -= 1
        old, new = lines[start][4:].strip(), lines[start + 1][4:].strip()
        path = old.removeprefix('a/') if new == '/dev/null' else new.removeprefix('b/')
        sections.append((path, ''.join(lines[start:end])))
    return sections


def patch_files(raw: str) -> list[str]:
    return [path for path, _ in _sections(raw)]


def filter_patch(raw_diff: str, keep: set[str]) -> tuple[str, list[str]]:
    """Diff restricted to files in keep (headers from '--- '), and the dropped file paths in order."""
    kept, dropped = [], []
    for path, text in _sections(raw_diff):
        if path in keep:
            kept.append(text)
        else:
            dropped.append(path)
    return ''.join(kept), dropped


def _under(path: str, roots) -> bool:
    return any(path == root or path.startswith(root.rstrip('/') + '/') for root in roots)


def diff_only_tests(changed_paths: list[str], test_nodes: list[dict]) -> set[str]:
    """Baseline: every test in a file named test_<module>.py or <module>_test.py for a changed module."""
    names = set()
    for path in changed_paths:
        stem = Path(path).stem
        names.update({f'test_{stem}.py', f'{stem}_test.py'})
    return {node['id'] for node in test_nodes if Path(node['path']).name in names}


# ---- one task -------------------------------------------------------------------------------------------------------

def _list(value) -> list[str]:
    return json.loads(value) if isinstance(value, str) else list(value)


def _method(region: set[str], matched: dict[int, set[str]], nodes_by_id: dict, region_nodes: int,
            test_patch_files: set[str]) -> dict:
    return {'f2p_hit': sum(1 for ids in matched.values() if ids & region), 'region_tests': len(region),
            'region_nodes': region_nodes,
            'test_patch_files_hit': len({nodes_by_id[i]['path'] for i in region} & test_patch_files)}


def evaluate_task(task_id: str, checkout: Path, task_roots: list[str], row: dict) -> dict:
    """Graph impact and diff-only regions of the gold patch on the baseline checkout.

    The graph is built like the retrieval/bundle graphs (builder default roots); task_roots only bound which gold
    files count as source changes. F2P tests absent from the baseline (added by test_patch) are not measurable.
    """
    out: dict = {'task_id': task_id}
    try:
        document = PythonGraphBuilder(repo_key=task_id, repository_revision='base').build(checkout)
        files = {n['path'] for n in document['nodes'] if n['type'] == 'File'}
        keep = {p for p in files if _under(p, task_roots)}
        diff, dropped = filter_patch(row['patch'], keep)
        out['dropped_files'] = dropped
        test_patch_files = set(patch_files(row['test_patch']))
        raw_f2p = _list(row['FAIL_TO_PASS'])
        test_nodes = [n for n in document['nodes'] if n['type'] == 'Test']
        parsed = [(i, parse_f2p(raw)) for i, raw in enumerate(raw_f2p)]
        indices = [i for i, key in parsed if key]
        found = match_tests([key for _, key in parsed if key], test_nodes, test_patch_files)
        matched = {indices[k]: ids for k, ids in found.items()}
        out.update(f2p_total=len(raw_f2p), f2p_measurable=len(matched), f2p_unmatched=len(raw_f2p) - len(matched),
                   test_patch_files=len(test_patch_files))
        if not diff:
            return out | {'status': 'NO_SOURCE_CHANGE'}
        changed = patch_files(diff)
        policy = PatchPolicy(tuple(sorted(keep)), (), max_bytes=len(diff.encode('utf-8')) + 1,
                             max_files=len(changed), max_changed_lines=len(diff.splitlines()))
        report = analyze_patch_impact(diff, document, checkout, patch_policy=policy)
        nodes_by_id = {n['id']: n for n in test_nodes}
        graph_region = {item.node_id for item in report.impacted.items if item.kind == 'Test'}
        diff_region = diff_only_tests(changed, test_nodes)
        out['graph'] = _method(graph_region, matched, nodes_by_id, len(report.impacted.items), test_patch_files)
        out['diff_only'] = _method(diff_region, matched, nodes_by_id, len(changed) + len(diff_region),
                                   test_patch_files)
        out['changed_files'] = changed
        out['impact_status'] = report.impacted.status
        return out | {'status': 'OK'}
    except Exception as error:  # noqa: BLE001 -- every task stays in the denominator with its reason
        return out | {'status': 'ERROR', 'reason': f'{type(error).__name__}: {error}'}


# ---- table ----------------------------------------------------------------------------------------------------------

METHODS = (('diff_only', 'Chỉ dùng diff (file trong diff và test cùng tên)'),
           ('graph', 'Graph impact (`analyze_patch_impact`, gold patch)'))


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r['status'] == 'OK']
    measured = [r for r in ok if r['f2p_measurable'] > 0]
    summary = {'n_tasks': len(rows), 'n_ok': len(ok), 'n_measured': len(measured),
               'n_error': sum(r['status'] == 'ERROR' for r in rows),
               'n_excluded': sum(r['status'] == 'EXCLUDED' for r in rows),
               'n_no_source_change': sum(r['status'] == 'NO_SOURCE_CHANGE' for r in rows),
               'n_no_measurable_f2p': len(ok) - len(measured),
               'f2p_total': sum(r.get('f2p_total', 0) for r in ok),
               'f2p_measurable': sum(r['f2p_measurable'] for r in ok)}
    files = sum(r['test_patch_files'] for r in ok)
    for key, _ in METHODS:
        hits = sum(r[key]['f2p_hit'] for r in measured)
        summary[key] = {
            'recall_micro': hits / summary['f2p_measurable'] if summary['f2p_measurable'] else None,
            'recall_macro': (statistics.mean(r[key]['f2p_hit'] / r['f2p_measurable'] for r in measured)
                             if measured else None),
            'median_region_tests': statistics.median(r[key]['region_tests'] for r in ok) if ok else None,
            'median_region_nodes': statistics.median(r[key]['region_nodes'] for r in ok) if ok else None,
            'test_patch_file_recall': sum(r[key]['test_patch_files_hit'] for r in ok) / files if files else None}
    return summary


def _pct(value) -> str:
    return 'n/a' if value is None else f'{value:.1%}'


def _num(value) -> str:
    return 'n/a' if value is None else f'{value:g}'


def render_i1(summary: dict) -> str:
    lines = ['| Phương pháp | N task | F2P đo được | Recall F2P trong vùng | Median số test trong vùng '
             '| Median số node trong vùng | Recall file test của test_patch |', '|---|---|---|---|---|---|---|']
    for key, label in METHODS:
        m = summary[key]
        lines.append(f"| {label} | {summary['n_measured']} | {summary['f2p_measurable']}/{summary['f2p_total']} "
                     f"| {_pct(m['recall_micro'])} (macro {_pct(m['recall_macro'])}) | {_num(m['median_region_tests'])} "
                     f"| {_num(m['median_region_nodes'])} | {_pct(m['test_patch_file_recall'])} |")
    lines += ['', f"N = {summary['n_tasks']} task trong mẫu số: {summary['n_ok']} đo được, "
              f"{summary['n_no_measurable_f2p']} không có F2P nào có ở baseline, {summary['n_no_source_change']} gold "
              f"không sửa source, {summary['n_excluded']} bị loại, {summary['n_error']} lỗi. Recall tính trên F2P có ở "
              "baseline (spec §3.4); F2P do test_patch thêm vào thì không phương pháp nào thấy được."]
    return '\n'.join(lines) + '\n'
