"""M3-W12-1: table M1 (RQ5) from `vgar solve --agent` traces and the MCP audit log.

Descriptive only (N = a handful of dev tasks); never compared statistically with the A0–A3 pipeline arms.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

INVALID_REASONS = frozenset({'HOST_REFUSED', 'INVALID_ARGUMENT', 'TOOL_ORDER_VIOLATION', 'SELECTOR_REJECTED',
                             'PATH_OUTSIDE_ROOT', 'RUN_NOT_FOUND'})
# Tools that reach an MCP server (and so its audit log); generate_patch runs inside the host.
MCP_TOOLS = {'get_task_context': 'repair', 'apply_patch': 'repair', 'run_relevant_tests': 'repair',
             'verify_patch': 'repair', 'analyze_patch_impact': 'graph'}
CLOCK_SLACK = timedelta(seconds=2)
READ_REDUNDANCY_REASON = ('the agent has no code-reading tool and traces do not record call arguments, so repeated '
                          'reads cannot be identified (spec §2.2; cut first under Appendix A)')
DESCRIPTIVE = 'Chỉ mô tả, N = {n} task, không so sánh thống kê với A0–A3.'


def _ended_at(file_name: str) -> datetime:
    """Trace file names start with the UTC end time: YYYYmmddTHHMMSS<microseconds>Z-<task>.json."""
    stamp = Path(file_name).name.split('-', 1)[0]
    return datetime.strptime(stamp, '%Y%m%dT%H%M%S%fZ').replace(tzinfo=timezone.utc)


def load_trace(path: Path) -> dict:
    trace = json.loads(Path(path).read_text(encoding='utf-8'))
    return trace | {'ended_at': _ended_at(Path(path).name), 'path': str(path)}


def percentiles(values: list[float]) -> dict:
    if not values:
        return {'n': 0, 'p50': None, 'p95': None}
    if len(values) == 1:
        return {'n': 1, 'p50': values[0], 'p95': values[0]}
    cuts = statistics.quantiles(values, n=100, method='inclusive')
    return {'n': len(values), 'p50': cuts[49], 'p95': cuts[94]}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def audit_completeness(trace: dict, audit: list[dict]) -> dict:
    """MCP calls of the trace that have an audit line of the same server/tool inside the trace's time window."""
    end = trace['ended_at']
    start = end - timedelta(milliseconds=trace.get('duration_ms') or 0)
    expected = Counter(call['tool'] for call in trace['calls']
                       if call['tool'] in MCP_TOOLS and call.get('reason') != 'HOST_REFUSED')
    available = Counter()
    for line in audit:
        payload = line.get('payload', {})
        tool = payload.get('tool')
        if line.get('event_type') != 'tool_call' or MCP_TOOLS.get(tool) != payload.get('server'):
            continue
        if start - CLOCK_SLACK <= _parse_time(line['timestamp']) <= end + CLOCK_SLACK:
            available[tool] += 1
    missing = []
    for tool in sorted(expected):
        missing += [tool] * max(expected[tool] - available[tool], 0)
    total = sum(expected.values())
    return {'expected': total, 'matched': total - len(missing), 'missing': missing}


def summarize_traces(traces: list[dict], audit: list[dict]) -> dict:
    real = [t for t in traces if t.get('mode') == 'real']
    excluded = [{'task_id': t['task_id'], 'mode': t.get('mode')} for t in traces if t.get('mode') != 'real']
    tools: dict[str, dict] = {}
    invalid = agent_calls = 0
    for trace in real:
        for call in trace['calls']:
            row = tools.setdefault(call['tool'], {'durations': [], 'calls': 0, 'invalid': 0, 'agent_calls': 0})
            row['calls'] += 1
            row['durations'].append(call['duration_ms'])
            if call.get('by') == 'agent':
                row['agent_calls'] += 1
                agent_calls += 1
                if call.get('reason') in INVALID_REASONS:
                    row['invalid'] += 1
                    invalid += 1
    turns = [m for t in real for m in t['model_calls']]
    inputs = [m['input_tokens'] for m in turns if m.get('input_tokens') is not None]
    outputs = [m['output_tokens'] for m in turns if m.get('output_tokens') is not None]
    audits = [audit_completeness(t, audit) for t in real]
    expected, matched = sum(a['expected'] for a in audits), sum(a['matched'] for a in audits)
    n = len(real)
    return {
        'n_tasks': n, 'tasks': [t['task_id'] for t in real], 'excluded': excluded,
        'tools': {tool: {'calls': row['calls'], 'calls_per_task': row['calls'] / n if n else None,
                         'latency_ms': percentiles(row['durations']),
                         'invalid': {'invalid': row['invalid'], 'agent_calls': row['agent_calls'],
                                     'rate': row['invalid'] / row['agent_calls'] if row['agent_calls'] else None}}
                  for tool, row in sorted(tools.items())},
        'model_turns': {'n': len(turns), 'latency_ms': percentiles([m['duration_ms'] for m in turns])},
        'tokens': {'input': percentiles(inputs), 'output': percentiles(outputs),
                   'missing_turns': sum(m.get('input_tokens') is None for m in turns)},
        'invalid_calls': {'invalid': invalid, 'agent_calls': agent_calls,
                          'rate': invalid / agent_calls if agent_calls else None},
        'audit': {'expected': expected, 'matched': matched,
                  'completeness': matched / expected if expected else None,
                  'missing': [{'task_id': t['task_id'], 'tools': a['missing']} for t, a in zip(real, audits) if a['missing']]},
        'read_redundancy': None, 'read_redundancy_reason': READ_REDUNDANCY_REASON,
        **_v2_fields(real),
    }


def _v2_fields(real: list[dict]) -> dict:
    """Trace v2 additions (trace spec 2026-11-03 §3.2); v1 traces contribute nothing, never a zero."""
    v2 = [t for t in real if t.get('schema') == 'vgar-agent-trace-v2']
    turns = [m for t in v2 for m in t['model_calls'] if m.get('followed') is not None]
    classes: dict[str, int] = {}
    for trace in v2:
        klass = (trace.get('failure_class') or {}).get('class')
        if klass:
            classes[klass] = classes.get(klass, 0) + 1
    return {'followed': {'followed': sum(m['followed'] for m in turns), 'turns_with_tool': len(turns)} if v2 else None,
            'classes': dict(sorted(classes.items())),
            'generators': sorted({(t.get('header') or {}).get('generator') for t in v2} - {None})}


def _ms(value) -> str:
    return 'n/a' if value is None else f'{value:.0f}'


def _rate(value) -> str:
    return 'n/a' if value is None else f'{value:.1%}'


def render_m1(summary: dict) -> str:
    lines = ['| Tool | Số call | p50 (ms) | p95 (ms) | Invalid call rate | Audit completeness | Token/lượt model |',
             '|---|---|---|---|---|---|---|']
    for tool, row in summary['tools'].items():
        audit = 'qua MCP' if tool in MCP_TOOLS else 'không qua MCP'
        lines.append(f"| `{tool}` | {row['calls']} | {_ms(row['latency_ms']['p50'])} | {_ms(row['latency_ms']['p95'])} "
                     f"| {_rate(row['invalid']['rate'])} | {audit} | — |")
    turns, tokens = summary['model_turns'], summary['tokens']
    lines.append(f"| Lượt model | {turns['n']} | {_ms(turns['latency_ms']['p50'])} | {_ms(turns['latency_ms']['p95'])} "
                 f"| — | — | vào p50 {_ms(tokens['input']['p50'])} / p95 {_ms(tokens['input']['p95'])}, "
                 f"ra p50 {_ms(tokens['output']['p50'])} / p95 {_ms(tokens['output']['p95'])} "
                 f"(thiếu {tokens['missing_turns']} lượt) |")
    audit, invalid = summary['audit'], summary['invalid_calls']
    lines += ['', DESCRIPTIVE.format(n=summary['n_tasks']),
              f"Invalid call rate (call của agent): {_rate(invalid['rate'])} ({invalid['invalid']}/{invalid['agent_calls']}). "
              f"Audit completeness: {_rate(audit['completeness'])} ({audit['matched']}/{audit['expected']} call MCP).",
              f"Read redundancy: n/a — {summary['read_redundancy_reason']}."]
    followed = summary.get('followed')
    if followed:
        lines.append(f"Agent làm theo NEXT: {followed['followed']}/{followed['turns_with_tool']} lượt (chỉ trace v2).")
    if summary.get('classes'):
        lines.append('Nhãn kết cục: ' + ', '.join(f'{k} {v}' for k, v in summary['classes'].items())
                     + f". Generator: {', '.join(summary.get('generators') or ['n/a'])}.")
    if summary['excluded']:
        lines.append('Trace bị loại (không phải mode real): '
                     + ', '.join(f"{e['task_id']} ({e['mode']})" for e in summary['excluded']) + '.')
    return '\n'.join(lines) + '\n'
