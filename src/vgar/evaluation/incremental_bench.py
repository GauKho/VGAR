"""U1 benchmark (M1-W12-1): cold build vs warm incremental update, checked against a full rebuild.

Every measurement runs on a copy of the repository; the source checkout is never modified.
Parsing is O(changed files); linking stays O(N), so the speedup comes from not re-parsing unchanged files.
"""
from __future__ import annotations

import json
import platform
import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from vgar.graph.builder import RESOLVER_PROFILE, PythonGraphBuilder
from vgar.graph.incremental import IncrementalGraphBuilder

SCENARIOS = ('body_edit', 'add_delete_file', 'public_signature')
MAX_REPEATS = 30
COLD_RUNS = 3
ADDED_FILE = '_vgar_bench_added.py'
_REVISION = 'bench'


def normalized(document: dict) -> str:
    document = json.loads(json.dumps(document))
    document['statistics'].pop('build_time_ms', None)
    return json.dumps(document, sort_keys=True)


def _under(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root.rstrip('/') + '/') for root in roots)


def pick_target(document: dict, source_roots: tuple[str, ...]) -> dict:
    """Public Function/Method in the file with most of them; first by (path, start_line)."""
    nodes = [n for n in document['nodes'] if n['type'] in ('Function', 'Method')
             and n.get('properties', {}).get('visibility') == 'public' and _under(n['path'], source_roots)]
    if not nodes:
        raise ValueError('No public function or method under the source roots')
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node['path']] = counts.get(node['path'], 0) + 1
    path = min(counts, key=lambda p: (-counts[p], p))
    node = min((n for n in nodes if n['path'] == path), key=lambda n: n['range']['start_line'])
    return {'path': path, 'qualified_name': node['qualified_name'], 'start_line': node['range']['start_line']}


def _header_end(lines: list[str], start: int) -> int:
    """Index of the line that closes the def header (ends with ':'), starting at 0-based start."""
    for index in range(start, len(lines)):
        if lines[index].split('#', 1)[0].rstrip().endswith(':'):
            return index
    raise ValueError('Function header not found')


def apply_scenario(root: Path, scenario: str, target: dict, step: int) -> None:
    """Change the copy in place; add_delete_file adds the module on even steps and deletes it on odd ones."""
    path = root / target['path']
    if scenario == 'add_delete_file':
        added = path.parent / ADDED_FILE
        if step % 2:
            added.unlink()
            return
        module, name = target['qualified_name'].rsplit('.', 1)
        added.write_text(f'from {module} import {name}\n\n\ndef _vgar_bench_added():\n    return {name}\n',
                         encoding='utf-8')
        return
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    end = _header_end(lines, target['start_line'] - 1)
    if scenario == 'body_edit':
        body = next((line for line in lines[end + 1:] if line.strip()), '    pass\n')
        indent = body[:len(body) - len(body.lstrip())]
        lines.insert(end + 1, indent + '_ = 0\n')
    elif scenario == 'public_signature':
        line = lines[end]
        head = line.split('->', 1)[0]
        close = head.rfind(')')
        if close < 0:
            raise ValueError('Signature closing parenthesis not found')
        before = line[:close].rstrip()
        extra = '_vgar_bench=None' if before.endswith('(') else ', _vgar_bench=None'
        lines[end] = line[:close] + extra + line[close:]
    else:
        raise ValueError(f'Unknown scenario {scenario!r}')
    path.write_text(''.join(lines), encoding='utf-8')


def _restore(baseline: Path, work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(baseline, work)


def run_bench(repo: Path, source_roots: tuple[str, ...], *, repeats: int, workdir: Path) -> dict:
    if not 1 <= repeats <= MAX_REPEATS:
        raise ValueError(f'repeats must be between 1 and {MAX_REPEATS}')
    repo, workdir = Path(repo), Path(workdir)
    baseline, work = workdir / 'baseline', workdir / 'work'
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo, baseline, ignore=shutil.ignore_patterns('.git'))
    # Graphs are built like the retrieval/bundle graphs (builder default roots, scripts/run_graph_retrieval.py);
    # source_roots only choose the edited target, as task source_roots only bound patchable files.
    options = {'repo_key': repo.name, 'repository_revision': _REVISION}
    target = pick_target(PythonGraphBuilder(**options).build(baseline), tuple(source_roots))

    _restore(baseline, work)
    cold = []
    for _ in range(COLD_RUNS):
        started = time.perf_counter()
        IncrementalGraphBuilder(options['repo_key'], _REVISION).build(work)
        cold.append(time.perf_counter() - started)

    scenarios = {}
    for scenario in SCENARIOS:
        row: dict[str, Any] = {'cold_seconds': cold, 'warm_seconds': [], 'affected_nodes': [], 'timings': []}
        for step in range(repeats):
            _restore(baseline, work)
            if scenario == 'add_delete_file' and step % 2:
                apply_scenario(work, scenario, target, step - 1)   # odd steps measure the deletion
            builder = IncrementalGraphBuilder(options['repo_key'], _REVISION)
            builder.build(work)
            apply_scenario(work, scenario, target, step)
            document, summary = builder.update(work)
            row['warm_seconds'].append(summary.total_seconds)
            row['affected_nodes'].append(summary.affected_node_count)
            row['timings'].append({'extract': summary.extract_seconds, 'validate': summary.validate_seconds,
                                   'total': summary.total_seconds})
            if step == 0:
                row['files_changed'] = len(summary.changed_files) + len(summary.added_files) + len(summary.deleted_files)
                row['cache_hit'] = summary.cache_hits / summary.total_files if summary.total_files else 0.0
                row['match'] = normalized(document) == normalized(PythonGraphBuilder(**options).build(work))
        scenarios[scenario] = row
    return {'repo': str(repo), 'source_roots': list(source_roots), 'resolver_profile': RESOLVER_PROFILE,
            'repeats': repeats, 'target': target, 'scenarios': scenarios}


def environment_info(vgar_root: Path) -> dict:
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=vgar_root, capture_output=True, text=True,
                                check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {'git_commit': commit, 'os': platform.platform(), 'cpu': platform.processor() or platform.machine(),
            'python': platform.python_version()}


def _percentiles(values: list[float]) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    cuts = statistics.quantiles(values, n=100, method='inclusive')
    return cuts[49], cuts[94]


def render_u1(result: dict) -> str:
    lines = ['| Kịch bản | Cold build (s) | Warm update p50/p95 (s) | Speedup | File đổi | Node bị ảnh hưởng '
             '| Cache hit | Trùng full rebuild |', '|---|---|---|---|---|---|---|---|']
    for name, row in result['scenarios'].items():
        cold = statistics.median(row['cold_seconds'])
        p50, p95 = _percentiles(row['warm_seconds'])
        speedup = f'{cold / p50:.1f}×' if p50 else 'n/a'
        lines.append(f"| {name} | {cold:.3f} | {p50:.3f} / {p95:.3f} | {speedup} | {row['files_changed']} "
                     f"| {statistics.median(row['affected_nodes']):g} | {row['cache_hit']:.1%} "
                     f"| {'có' if row['match'] else '**không**'} |")
    env = result.get('environment', {})
    lines += ['', 'Ghi chú: phần parse là O(Δ), phần link vẫn O(N); speedup đến từ việc không parse lại file không đổi.',
              '', f"Repo `{result['repo']}`, source roots `{','.join(result['source_roots'])}`, "
              f"đích `{result['target']['qualified_name']}` ({result['target']['path']}), "
              f"{result['repeats']} lần lặp warm, {COLD_RUNS} lần cold, resolver `{result['resolver_profile']}`, "
              f"commit `{env.get('git_commit')}`, máy `{env.get('os')}` / `{env.get('cpu')}`, Python {env.get('python')}."]
    return '\n'.join(lines) + '\n'
