"""M3-W10-3 real-model check: does Qwen choose analyze_patch_impact in the agent's retry loop?

The first patch of every task is a valid wrong patch (applies, tests still fail), later patches are the
reference, so each task reaches the retry decision and only the agent's tool choice is measured.
Loads the pinned agent model once and runs the tasks one after another (GPU; the user runs it).

  python scripts/check_agent_impact_real.py [--tasks single_file_login,multi_file_invoice,missing_links]
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

TASKS = ('single_file_login', 'multi_file_invoice', 'missing_links')
IMPACT_LINE = 'Static graph impact of the previous patch'


def summarize(trace: dict) -> dict:
    """One row per task trace: did the agent call the impact tool, and did the retry feedback carry it."""
    impact = [call for call in trace['calls'] if call['tool'] == 'analyze_patch_impact' and call['by'] == 'agent']
    records = [json.loads((Path(run['run_dir']) / 'run_record.json').read_text(encoding='utf-8')) for run in trace['runs']]
    feedback = [(record.get('prompt_feedback') or {}).get('message', '') for record in records[1:]]
    return {'task': trace['task_id'], 'impact_called': bool(impact),
            'impact_status': next((c['status'] for c in impact if c['status'] == 'PASS'), impact[0]['status'] if impact else None),
            'feedback_has_impact': any(IMPACT_LINE in message for message in feedback),
            'recommendation': trace['result']['recommendation'],
            'tool_calls': sum(call['by'] == 'agent' for call in trace['calls']),
            'duration_ms': trace['duration_ms'], 'trace_path': trace.get('trace_path')}


def gate(rows: list[dict]) -> bool:
    return any(r['impact_called'] and r['impact_status'] == 'PASS' and r['feedback_has_impact'] for r in rows)


async def run(tasks: list[str], out: Path) -> list[dict]:
    from vgar.agents.fakes import ScriptedPatchGenerator
    from vgar.agents.runtime import Runtime
    from vgar.agents.tool_agent import default_agent_model, run_agent_task
    from vgar.repair.config import load_config

    runtime = Runtime(mode='real', output_root=out / 'runs')
    model = default_agent_model(runtime, load_config(runtime.config_path)[1])
    rows = []
    for task in tasks:
        wrong = (ROOT / f'tests/fixtures/m2/wrong_patches/{task}.diff').read_text(encoding='utf-8')
        ref = (ROOT / f'tests/fixtures/m2/reference_patches/{task}.diff').read_text(encoding='utf-8')
        task_runtime = Runtime(mode='real', output_root=out / 'runs', generator=ScriptedPatchGenerator([wrong, ref]))
        result = await run_agent_task(task_path=ROOT / f'examples/m2/tasks/{task}.json', runtime=task_runtime, model=model)
        trace = json.loads(Path(result['trace_path']).read_text(encoding='utf-8'))
        rows.append(summarize({**trace, 'trace_path': result['trace_path']}))
        print(json.dumps(rows[-1]), flush=True)
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tasks', default=','.join(TASKS))
    parser.add_argument('--out', type=Path, default=ROOT / 'results/agent-impact-real')
    args = parser.parse_args(argv)
    out = args.out / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rows = asyncio.run(run(args.tasks.split(','), out))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print('| task | impact_called | impact_status | feedback_has_impact | recommendation | tool_calls | seconds |')
    print('|---|---|---|---|---|---|---|')
    for r in rows:
        print(f"| {r['task']} | {r['impact_called']} | {r['impact_status']} | {r['feedback_has_impact']} | "
              f"{r['recommendation']} | {r['tool_calls']} | {r['duration_ms'] / 1000:.0f} |")
    print(f"summary: {out / 'summary.json'}")
    print(f"GATE: {'PASS' if gate(rows) else 'FAIL'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
