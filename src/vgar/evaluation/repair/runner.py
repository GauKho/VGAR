"""Sequential task x variant runner: one attempt record per engine call, resumable under an OS lock.

Layout under <output_root>/<experiment_id>/: runner.lock, experiment.json,
attempts/<task>__<variant>/attempt-<n>.json, engine/<task>__<variant>/attempt-<n>/<run_id>/.
A pair with a TERMINAL attempt is never relaunched except by an explicit rerun with a reason.
"""
from __future__ import annotations

import json
import os
import platform
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from vgar.evaluation.repair.manifest import Experiment, TaskPlan, plan_task
from vgar.repair.evidence import atomic_json

INTERRUPTED_EXIT = 130


@dataclass
class LaunchResult:
    status: Literal['PASS', 'FAIL', 'ERROR']
    reason: str | None
    stage: str | None
    source: Literal['engine', 'runner']
    engine_run_dir: str | None
    engine_complete: bool | None
    interrupted: bool = False
    timed_out: bool = False
    detail: str | None = None
    command_timed_out: bool = False


Launch = Callable[[TaskPlan, Path, 'str | None', 'str | None'], LaunchResult]


class ExperimentLock:
    """Exclusive OS lock held for the runner's lifetime; the OS releases it if the process dies."""

    def __init__(self, path: Path):
        self.path, self.handle = Path(path), None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, 'a+')
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            raise RuntimeError('experiment is locked by another runner: ' + str(self.path)) from None
        return self

    def __exit__(self, *exc):
        if os.name == 'nt':
            import msvcrt
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        self.handle.close()
        return False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pair(task_id: str, variant_id: str) -> str:
    return f'{task_id}__{variant_id}'


def read_attempts(exp_dir: Path) -> dict[tuple[str, str], list[dict]]:
    found = {}
    for path in Path(exp_dir).glob('attempts/*/attempt-*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        found.setdefault((record['task_id'], record['variant_id']), []).append(record)
    return {key: sorted(items, key=lambda r: r['attempt']) for key, items in found.items()}


def _attempt_path(exp_dir: Path, record: dict) -> Path:
    return exp_dir / 'attempts' / _pair(record['task_id'], record['variant_id']) / f"attempt-{record['attempt']}.json"


def _interrupted_run_id(record: dict) -> str | None:
    root = record.get('engine_output_root')
    runs = sorted(Path(root).glob('*/run_record.json')) if root else []
    return json.loads(runs[-1].read_text(encoding='utf-8')).get('run_id') if runs else None


def _attempt(exp, data_root, exp_dir, launch, sampler_factory, plan_variant, number, parent, rerun_reason):
    """Run one attempt; returns True when the run was interrupted."""
    task_id, variant = plan_variant
    engine_root = exp_dir / 'engine' / _pair(task_id, variant.variant_id) / f'attempt-{number}'
    record = dict(experiment_id=exp.experiment_id, task_id=task_id, variant_id=variant.variant_id, arm=variant.arm,
                  attempt=number, parent_attempt=parent and parent['attempt'], rerun_reason=rerun_reason,
                  state='RESERVED', status=None, reason=None, stage=None, source=None, engine_run_dir=None,
                  engine_complete=None, engine_output_root=str(engine_root), timed_out=False, command_timed_out=False,
                  detail=None,
                  started_utc=_now(), ended_utc=None, wall_ms=None, gpu_peak_mib=None, gpu_peak_scope=None,
                  host=platform.node())
    path = _attempt_path(exp_dir, record)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, record)
    supersedes = _interrupted_run_id(parent) if parent and rerun_reason == 'interrupted' else None
    sampler = sampler_factory() if sampler_factory else None
    start, result = time.monotonic(), None
    try:
        if sampler:
            sampler.start()
        try:
            plan = plan_task(exp, task_id, variant, data_root)
        except Exception:
            result = LaunchResult('ERROR', 'ADMISSION_REJECTED', 'plan', 'runner', None, None,
                                  detail=traceback.format_exc())
        else:
            if plan.skip_reason:
                result = LaunchResult('ERROR', plan.skip_reason, 'plan', 'runner', None, None, detail=plan.skip_detail)
            else:
                engine_root.mkdir(parents=True, exist_ok=True)
                try:
                    result = launch(plan, engine_root, supersedes, rerun_reason)
                except Exception:
                    result = LaunchResult('ERROR', 'RUNNER_INFRA_ERROR', 'launch', 'runner', None, None,
                                          detail=traceback.format_exc())
    except KeyboardInterrupt:
        result = None
    finally:
        peak = sampler.stop() if sampler else None
    record.update(ended_utc=_now(), wall_ms=round((time.monotonic() - start) * 1000), gpu_peak_mib=peak,
                  gpu_peak_scope='device' if peak is not None else None)
    if result is not None:
        record.update({k: v for k, v in asdict(result).items() if k != 'interrupted'})
    interrupted = result is None or result.interrupted
    record['state'] = 'INTERRUPTED' if interrupted else 'TERMINAL'
    atomic_json(path, record)
    return interrupted


def run_experiment(exp: Experiment, data_root: Path, output_root: Path, launch: Launch, *,
                   rerun: tuple[str, str] | None = None, rerun_reason: str | None = None,
                   sampler_factory=None) -> int:
    """Run every task x variant pair without a TERMINAL attempt; returns 0, or 130 when interrupted."""
    if rerun and not rerun_reason:
        raise ValueError('--rerun requires a reason')
    exp_dir = Path(output_root) / exp.experiment_id
    with ExperimentLock(exp_dir / 'runner.lock'):
        if not (exp_dir / 'experiment.json').exists():
            atomic_json(exp_dir / 'experiment.json', exp.raw | {'experiment_id': exp.experiment_id})
        ledger = read_attempts(exp_dir)
        for items in ledger.values():
            if items[-1]['state'] == 'RESERVED':
                items[-1].update(state='INTERRUPTED', ended_utc=_now())
                atomic_json(_attempt_path(exp_dir, items[-1]), items[-1])
        if rerun and not any(a['state'] == 'TERMINAL' for a in ledger.get(rerun, [])):
            raise ValueError('--rerun target has no TERMINAL attempt: ' + ':'.join(rerun))
        for task_id in exp.task_ids:
            for variant in exp.variants:
                key = (task_id, variant.variant_id)
                items = ledger.get(key, [])
                parent, reason = None, None
                if key == rerun:
                    parent, reason = items[-1], rerun_reason
                elif any(a['state'] == 'TERMINAL' for a in items):
                    continue
                elif items:
                    parent, reason = items[-1], 'interrupted'
                if _attempt(exp, data_root, exp_dir, launch, sampler_factory, (task_id, variant),
                            len(items) + 1, parent, reason):
                    return INTERRUPTED_EXIT
    return 0


def summary_table(exp_dir: Path, exp: Experiment) -> str:
    """Markdown status of every pair, latest attempt; a timed-out wall time is a lower bound, not a measurement."""
    ledger = read_attempts(exp_dir)
    limit = exp.policy.global_timeout / 60
    lines = [f'Experiment `{exp.experiment_id}`', '',
             '| task | variant | state | status | reason | attempts | wall (min) | VRAM peak (MiB, device) |',
             '|---|---|---|---|---|---|---|---|']
    for task_id in exp.task_ids:
        for variant in exp.variants:
            items = ledger.get((task_id, variant.variant_id), [])
            last = items[-1] if items else {}
            wall = last.get('wall_ms')
            minutes = f'≥ {limit:.1f}' if last.get('timed_out') else ('' if wall is None else f'{wall / 60000:.1f}')
            peak = last.get('gpu_peak_mib')
            lines.append(f"| {task_id} | {variant.variant_id} | {last.get('state', 'NOT_RUN')} | "
                         f"{last.get('status') or ''} | {last.get('reason') or ''} | {len(items)} | {minutes} | "
                         f"{'' if peak is None else peak} |")
    return '\n'.join(lines)
