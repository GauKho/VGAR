"""`vgar solve --agent` on an admitted SWE-bench task (S15, D20).

The host plans and admits the task exactly like the M3 runner (`plan_task` -> `admit_task`), writes the planned
task to a JSON file the repair server can load, and opens every run with the variant's experiment policy and
the admission snapshot. The engine re-validates the snapshot, so the model never chooses or sees either.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgar.evaluation.repair.manifest import load_experiment, plan_task, resolve
from vgar.repair.admission import admit_task


@dataclass(frozen=True)
class AdmittedTask:
    task_path: Path
    config_path: Path  # the experiment's repair config (policy + model profile)
    run_args: dict[str, Any]  # experiment + admission, passed to every repair_get_task_context


def prepare_admitted_task(experiment_path: Path, task_id: str, variant_id: str, data_root: Path,
                          task_dir: Path) -> AdmittedTask:
    exp = load_experiment(Path(experiment_path), Path(data_root))
    variant = next((v for v in exp.variants if v.variant_id == variant_id), None)
    if variant is None:
        raise ValueError(f'Unknown variant {variant_id!r}; experiment has {[v.variant_id for v in exp.variants]}')
    plan = plan_task(exp, task_id, variant, Path(data_root))
    if plan.skip_reason:
        raise ValueError(f'{task_id} cannot run: {plan.skip_reason} ({plan.skip_detail})')
    admission = admit_task(plan.task, **plan.admission_args)
    task_path = Path(task_dir) / f'{task_id}.json'
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(json.dumps(plan.task.model_dump(mode='json'), indent=2), encoding='utf-8')
    return AdmittedTask(task_path=task_path, config_path=resolve(exp.raw['repair_config'], exp.base, Path(data_root)),
                        run_args={'experiment': {'variant_policy': variant.policy, 'arm': variant.arm},
                                  'admission': admission.snapshot()})
