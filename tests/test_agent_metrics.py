"""M3-W12-1: bảng M1 from `solve --agent` traces (latency, tokens, invalid calls, audit completeness)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.evaluation.agent_metrics import audit_completeness, load_trace, percentiles, render_m1, summarize_traces

ROOT = Path(__file__).resolve().parents[1]
ENDED = '20261104T100000000000Z'   # trace window: [09:59:00, 10:00:00] with duration_ms=60000


def _call(tool, by='agent', status='PASS', reason=None, duration_ms=10):
    return {'tool': tool, 'by': by, 'status': status, 'reason': reason, 'duration_ms': duration_ms, 'run_dir': None}


def _turn(turn, input_tokens, output_tokens, duration_ms=1000):
    return {'turn': turn, 'status': 'PASS', 'duration_ms': duration_ms, 'input_tokens': input_tokens,
            'output_tokens': output_tokens, 'tool_calls': []}


def _trace_body(task, calls=(), model_calls=(), duration_ms=60000, mode='real'):
    return {'task_id': task, 'mode': mode, 'duration_ms': duration_ms, 'calls': list(calls),
            'model_calls': list(model_calls), 'runs': [], 'messages': [], 'result': {}}


def _trace(task, calls, model_calls, ended=ENDED, duration_ms=60000, mode='real', tmp=None):
    from vgar.evaluation import agent_metrics
    body = _trace_body(task, calls, model_calls, duration_ms, mode)
    return body | {'ended_at': agent_metrics._ended_at(f'{ended}-{task}.json')}


def _audit(tool, at, server=None):
    from vgar.evaluation.agent_metrics import MCP_TOOLS
    return {'timestamp': at, 'event_type': 'tool_call',
            'payload': {'server': server or MCP_TOOLS[tool], 'tool': tool, 'status': 'PASS', 'duration_ms': 5}}


def test_percentiles_inclusive_and_single_sample():
    assert percentiles([10, 20, 30, 40]) == {'n': 4, 'p50': 25.0, 'p95': 38.5}
    assert percentiles([7]) == {'n': 1, 'p50': 7, 'p95': 7}
    assert percentiles([]) == {'n': 0, 'p50': None, 'p95': None}


def test_invalid_rate_counts_agent_calls_only():
    calls = [_call('apply_patch', reason='HOST_REFUSED'), _call('verify_patch'),
             _call('verify_patch', by='host', reason='TOOL_ORDER_VIOLATION'),
             _call('apply_patch', status='FAIL', reason='PATCH_APPLY_FAILED')]
    summary = summarize_traces([_trace('t1', calls, [])], [])
    assert summary['invalid_calls'] == {'invalid': 1, 'agent_calls': 3, 'rate': 1 / 3}


def test_audit_completeness_matches_mcp_calls_in_window():
    calls = [_call('get_task_context'), _call('generate_patch'), _call('apply_patch'), _call('analyze_patch_impact')]
    audit = [_audit('get_task_context', '2026-11-04T09:59:30+00:00'), _audit('apply_patch', '2026-11-04T09:59:40+00:00')]
    assert audit_completeness(_trace('t1', calls, []), audit) == {
        'expected': 3, 'matched': 2, 'missing': ['analyze_patch_impact']}


def test_host_refused_calls_are_not_expected_in_audit():
    calls = [_call('apply_patch', reason='HOST_REFUSED')]
    assert audit_completeness(_trace('t1', calls, []), [])['expected'] == 0


def test_audit_outside_trace_window_is_ignored():
    audit = [_audit('apply_patch', '2026-11-04T08:00:00+00:00')]
    assert audit_completeness(_trace('t1', [_call('apply_patch')], []), audit)['matched'] == 0


def test_audit_line_counts_once():
    audit = [_audit('apply_patch', '2026-11-04T09:59:40+00:00')]
    result = audit_completeness(_trace('t1', [_call('apply_patch'), _call('apply_patch')], []), audit)
    assert result == {'expected': 2, 'matched': 1, 'missing': ['apply_patch']}


def test_missing_tokens_are_counted_not_zeroed():
    turns = [_turn(1, 100, 10), _turn(2, None, None), _turn(3, 300, 30)]
    summary = summarize_traces([_trace('t1', [], turns)], [])
    assert summary['tokens']['input'] == {'n': 2, 'p50': 200.0, 'p95': 290.0}
    assert summary['tokens']['missing_turns'] == 1


def test_fake_traces_are_excluded_and_listed():
    summary = summarize_traces([_trace('t1', [_call('apply_patch')], []), _trace('t2', [], [], mode='fake')], [])
    assert summary['n_tasks'] == 1 and summary['excluded'] == [{'task_id': 't2', 'mode': 'fake'}]


def test_per_tool_latency_and_counts():
    calls = [_call('apply_patch', duration_ms=100), _call('apply_patch', duration_ms=300),
             _call('verify_patch', duration_ms=50)]
    summary = summarize_traces([_trace('t1', calls, [])], [])
    assert summary['tools']['apply_patch']['latency_ms'] == {'n': 2, 'p50': 200.0, 'p95': 290.0}
    assert summary['tools']['apply_patch']['calls'] == 2 and summary['tools']['verify_patch']['calls'] == 1


def test_render_m1_is_pure_and_states_descriptive_only():
    summary = summarize_traces([_trace('t1', [_call('apply_patch')], [_turn(1, 100, 10)])], [])
    markdown = render_m1(summary)
    assert markdown.splitlines()[0].startswith(
        '| Tool | Số call | p50 (ms) | p95 (ms) | Invalid call rate | Audit completeness')
    assert 'Chỉ mô tả, N = 1 task, không so sánh thống kê với A0–A3.' in markdown
    assert 'Read redundancy: n/a' in markdown
    assert render_m1(json.loads(json.dumps(summary, default=str))) == markdown


def test_load_trace_reads_end_time_from_file_name(tmp_path):
    path = tmp_path / f'{ENDED}-t1.json'
    path.write_text(json.dumps(_trace_body('t1')), encoding='utf-8')
    trace = load_trace(path)
    assert trace['task_id'] == 't1' and trace['ended_at'].isoformat() == '2026-11-04T10:00:00+00:00'


# ---- CLI (Task 2) ----

def test_cli_writes_json_and_markdown(tmp_path):
    traces = tmp_path / 'run/agent-traces'
    traces.mkdir(parents=True)
    (traces / f'{ENDED}-t1.json').write_text(json.dumps(_trace_body('t1', [_call('apply_patch')])), encoding='utf-8')
    audit = tmp_path / 'mcp_audit.jsonl'
    audit.write_text(json.dumps(_audit('apply_patch', '2026-11-04T09:59:40+00:00')) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, 'scripts/aggregate_agent_traces.py', '--traces', str(tmp_path / 'run'),
                    '--audit', str(audit), '--out', str(tmp_path / 'out')], check=True, cwd=ROOT)
    data = json.loads((tmp_path / 'out/m1.json').read_text(encoding='utf-8'))
    assert data['summary']['n_tasks'] == 1 and data['summary']['audit']['completeness'] == 1.0
    assert (tmp_path / 'out/m1.md').read_text(encoding='utf-8').startswith('| Tool')


def test_cli_missing_audit_is_recorded(tmp_path):
    traces = tmp_path / 'run'
    traces.mkdir()
    (traces / f'{ENDED}-t1.json').write_text(json.dumps(_trace_body('t1', [_call('apply_patch')])), encoding='utf-8')
    subprocess.run([sys.executable, 'scripts/aggregate_agent_traces.py', '--traces', str(traces),
                    '--audit', str(tmp_path / 'none.jsonl'), '--out', str(tmp_path / 'out')], check=True, cwd=ROOT)
    data = json.loads((tmp_path / 'out/m1.json').read_text(encoding='utf-8'))
    assert data['audit_file_missing'] is True and data['summary']['audit']['completeness'] == 0.0


def test_cli_reads_existing_real_traces_if_present(tmp_path):
    source = ROOT / 'results/agent-impact-real'
    if not source.exists():
        pytest.skip('no local agent traces')
    subprocess.run([sys.executable, 'scripts/aggregate_agent_traces.py', '--traces', str(source),
                    '--audit', str(tmp_path / 'none.jsonl'), '--out', str(tmp_path / 'out')], check=True, cwd=ROOT)
    assert json.loads((tmp_path / 'out/m1.json').read_text(encoding='utf-8'))['summary']['n_tasks'] >= 1


# ---- trace v2 (trace spec 2026-11-03 §3.2, plan Task 7) ----------------------------------------------------
def _v2(task, followed, klass, generator='agent_model'):
    turns = [dict(_turn(i + 1, 100, 10), tool_calls=['x'], followed=f) for i, f in enumerate(followed)]
    return _trace('t', [_call('verify_patch')], turns) | {
        'task_id': task, 'schema': 'vgar-agent-trace-v2', 'failure_class': {'class': klass, 'code': None},
        'header': {'generator': generator}}


def test_v1_trace_gives_the_same_m1_table_as_before():
    v1 = [_trace('t1', [_call('apply_patch')], [_turn(1, 100, 10)])]
    summary = summarize_traces(v1, [])
    assert summary['followed'] is None and summary['classes'] == {} and summary['generators'] == []
    table = render_m1(summary).split('\n\n')[0]
    assert 'Agent làm theo NEXT' not in render_m1(summary)
    assert table.splitlines()[2].startswith('| `apply_patch` | 1 |')


def test_v2_trace_adds_followed_and_classes():
    summary = summarize_traces([_v2('a', [True, True, True, False], 'MODEL'),
                                _v2('b', [True, True, True, True], 'VERIFIED')], [])
    assert summary['followed'] == {'followed': 7, 'turns_with_tool': 8}
    assert summary['classes'] == {'MODEL': 1, 'VERIFIED': 1} and summary['generators'] == ['agent_model']
    markdown = render_m1(summary)
    assert 'Agent làm theo NEXT: 7/8 lượt (chỉ trace v2).' in markdown
    assert 'Nhãn kết cục: MODEL 1, VERIFIED 1. Generator: agent_model.' in markdown
