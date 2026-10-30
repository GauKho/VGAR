"""Engine adapter: admission + run_repair for one attempt, and classification of the canonical run record.

KeyboardInterrupt is deliberately not caught here; the runner records it as INTERRUPTED.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from vgar.evaluation.repair.manifest import Experiment, TaskPlan
from vgar.evaluation.repair.runner import Launch, LaunchResult
from vgar.repair.admission import admit_task
from vgar.repair.failure import failure_of
from vgar.repair.pipeline import build_generation, run_repair

# Message of the engine's TimeoutError when the global run deadline is used up (repair/executor.py, pipeline.py).
GLOBAL_DEADLINE = 'Global run deadline exhausted'


def _found(value, predicate) -> bool:
    if isinstance(value, dict):
        return predicate(value) or any(_found(v, predicate) for v in value.values())
    if isinstance(value, list):
        return any(_found(v, predicate) for v in value)
    return False


def classify_record(record: dict, run_dir: str) -> LaunchResult:
    """Read terminal evidence; Ctrl+C and timeouts can sit in any stage, so search them all.

    timed_out means the run hit the global deadline (its wall time is only a lower bound);
    command_timed_out means some single command hit command_timeout, which says nothing about wall time.
    """
    detail = record.get('error_detail') or {}
    interrupted = _found(record, lambda d: d.get('type') == 'KeyboardInterrupt' or d.get('error_type') == 'KeyboardInterrupt')
    timed_out = _found(record, lambda d: GLOBAL_DEADLINE in str(d.get('message', '')))
    command_timed_out = _found(record.get('stages', {}), lambda d: d.get('timed_out') is True)
    # Records written before W10 have no 'failure'; derive it the same way the engine does.
    failure = record.get('failure') or failure_of(record)
    return LaunchResult(record.get('status') or 'ERROR', record.get('reason'), (failure or {}).get('stage'), 'engine',
                        run_dir, record.get('complete'), interrupted=interrupted, timed_out=timed_out,
                        detail=detail.get('message'), command_timed_out=command_timed_out, failure=failure)


def read_engine_record(path: Path) -> LaunchResult:
    try:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return LaunchResult('ERROR', 'RUNNER_INFRA_ERROR', 'record', 'runner', str(Path(path).parent), None,
                            detail=traceback.format_exc())
    return classify_record(record, str(Path(path).parent))


def _generation(exp: Experiment, plan: TaskPlan, out_dir: Path):
    return build_generation(exp.generation, plan.task, exp.policy, exp.profile, out_dir)


def make_launch(exp: Experiment, output_root: Path) -> Launch:
    """Real generation shares one worker-backed generator; fake builds one per task from its reference patch."""
    shared = {}

    def launch(plan: TaskPlan, out_dir: Path, supersedes_run_id: str | None, rerun_reason: str | None) -> LaunchResult:
        if exp.generation == 'real':
            if 'real' not in shared:
                shared['real'] = _generation(exp, plan, Path(output_root) / exp.experiment_id)
            generator, tokenizer, counter = shared['real']
        else:
            generator, tokenizer, counter = _generation(exp, plan, out_dir)
        admission = None
        if exp.source_type == 'swebench':
            try:
                admission = admit_task(plan.task, **plan.admission_args)
            except Exception:
                return LaunchResult('ERROR', 'ADMISSION_REJECTED', 'admission', 'runner', None, None,
                                    detail=traceback.format_exc())
        handle = run_repair(
            plan.task, exp.policy, generator, None, out_dir, m1_counter=counter, tokenizer=tokenizer,
            profile=exp.profile if exp.generation == 'real' else None, temp_root=Path(out_dir) / '.workspaces',
            supersedes_run_id=supersedes_run_id, rerun_reason=rerun_reason,
            experiment={'variant_policy': plan.variant.policy, 'arm': plan.variant.arm}, admission=admission)
        return read_engine_record(handle.path)

    return launch
