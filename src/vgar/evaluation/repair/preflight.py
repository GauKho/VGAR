"""Prompt preflight: build the real repair prompt for every pair with the real tokenizer, no model, no Docker.

The baseline's failed cases are only known after running tests, so the failing selectors stand in for them.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from vgar.evaluation.repair.manifest import Experiment, plan_task
from vgar.graph.token_counter import LocalTokenizerCounter
from vgar.models.huggingface.local_chat import LocalChatTokenizer
from vgar.repair.admission import admit_task
from vgar.repair.context_adapter import load_handoff
from vgar.repair.evidence import atomic_json
from vgar.repair.prompt import build_repair_prompt
from vgar.repair.static_tools import mypy_unavailable_reason

PREFLIGHT = 'preflight.json'


def _row(plan_id, variant, cap, result, tokens=None, reason=None, detail=None, static_unavailable=None):
    return dict(task_id=plan_id, variant_id=variant.variant_id, arm=variant.arm, result=result,
                input_tokens=tokens, input_cap=cap, headroom=None if tokens is None else cap - tokens,
                reason=reason, detail=detail, baseline_estimate='failing_selectors',
                static_unavailable=static_unavailable)


def _static_unavailable(plan):
    """Check -> reason for checks the pinned environment cannot run; {} for native fixtures."""
    if not plan.admission_args:
        return {}
    profile = json.loads(Path(plan.admission_args['profile_path']).read_text(encoding='utf-8'))
    reason = mypy_unavailable_reason(profile['runtime']['python'])
    return {'mypy': reason} if reason else {}


def _check(exp, task_id, variant, data_root, counter, tokenizer):
    cap = exp.policy.input_cap
    try:
        plan = plan_task(exp, task_id, variant, data_root)
    except Exception:
        return _row(task_id, variant, cap, 'ERROR', reason='ADMISSION_REJECTED', detail=traceback.format_exc())
    if plan.skip_reason:
        return _row(task_id, variant, cap, 'ERROR', reason=plan.skip_reason, detail=plan.skip_detail)
    # Static checks this pair cannot run, frozen here from the pinned profile before any generation.
    audit = dict(static_unavailable=_static_unavailable(plan))
    # The engine baseline collects only fallback_scope, so each failing selector's file must be inside it.
    scope = plan.task.fallback_scope
    outside = [s for s in plan.task.failing_selectors
               if not any(s.split('::')[0] == p or s.startswith(p.rstrip('/') + '/') for p in scope)]
    if outside:
        return _row(task_id, variant, cap, 'ERROR', reason='SELECTOR_OUTSIDE_SCOPE',
                    detail=f'{outside} not under fallback_scope {list(scope)}', **audit)
    try:
        if exp.source_type == 'swebench':
            admit_task(plan.task, **plan.admission_args)
    except Exception:
        return _row(task_id, variant, cap, 'ERROR', reason='ADMISSION_REJECTED', detail=traceback.format_exc(), **audit)
    try:
        hashes = plan.admission_args['bundle_hashes'] if plan.admission_args else None
        handoff = load_handoff(plan.task, counter, counter.counter_label, arm=variant.arm, expected_hashes=hashes)
        uncapped = exp.policy.model_copy(update={'input_cap': 10**9})
        prompt = build_repair_prompt(plan.task, handoff, {'failed_cases': list(plan.task.failing_selectors)},
                                     tokenizer, uncapped)
    except Exception:
        return _row(task_id, variant, cap, 'ERROR', reason='PROMPT_ERROR', detail=traceback.format_exc(), **audit)
    return _row(task_id, variant, cap, 'FITS' if prompt.input_tokens <= cap else 'OVER_CAP', prompt.input_tokens, **audit)


def preflight(exp: Experiment, data_root: Path, output_root: Path) -> list[dict]:
    """One row per pair (FITS, OVER_CAP or ERROR with a reason); saved as <output_root>/<id>/preflight.json."""
    counter = LocalTokenizerCounter(exp.profile.tokenizer_manifest)
    tokenizer = LocalChatTokenizer(exp.profile.tokenizer_manifest)
    rows = [_check(exp, task_id, variant, data_root, counter, tokenizer)
            for task_id in exp.task_ids for variant in exp.variants]
    atomic_json(Path(output_root) / exp.experiment_id / PREFLIGHT, {'experiment_id': exp.experiment_id, 'rows': rows})
    return rows


def require_preflight(output_root: Path, exp: Experiment) -> None:
    if not (Path(output_root) / exp.experiment_id / PREFLIGHT).is_file():
        raise RuntimeError(f'run preflight first for experiment {exp.experiment_id}')
