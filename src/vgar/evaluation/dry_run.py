"""M1-W12-2 dry-run of the full held-out chain on 2 dev tasks (spec §4): export -> config -> runner -> harness.

The gate "harness ổn định" passes when two consecutive runs each have zero infrastructure errors (spec §4.5).
Model outcomes (bad patch, unresolved, verifier reject) are results, not infrastructure errors.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, NamedTuple

from vgar.evaluation.retrieval.dataset import require_split, split_of  # noqa: F401  (split_of used by tests)
from vgar.graph.retrieval import RetrievalConfig, ranking_config_hash

ROOT = Path(__file__).resolve().parents[3]
FROZEN_RANKING_HASH = 'sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a'  # tests/test_graph_retrieval.py
DRY_RUN_TASKS = ('astropy__astropy-13033', 'django__django-10914')  # first 2 of w10_dev_stage1.json, RUNNABLE in W10
INFRA_REASONS = frozenset({'INTERNAL_ERROR', 'WORKTREE_ERROR', 'FINALIZATION_ERROR', 'RUNNER_INFRA_ERROR',
                           'ADMISSION_REJECTED'})
BUNDLE_ROOT = 'w12/bundles/repair'
_RUN_DIRECTORY = re.compile(r'^RUN DIRECTORY: (.+)$', re.MULTILINE)


class Step(NamedTuple):
    name: str
    argv: list[str]


@dataclass(frozen=True)
class Context:
    template: Path
    data_root: Path
    out: Path
    arms: tuple[str, ...]
    manifest: Path
    parquet: Path
    python: str
    variants_dir: Path = ROOT / 'configs/m2/variants'
    profile: Path = ROOT / 'configs/m1/w9_bundle_profile_repair.json'
    tokenizer_manifest: Path = ROOT / 'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json'
    export_run: str = '<EXPORT_RUN>'
    experiment_id: str = '<EXPERIMENT_ID>'
    grades: str = '<GRADES_JSON>'

    @property
    def config(self) -> Path:
        return self.out / 'w12_dry_run.json'


def check_preconditions(manifest: dict, arms: list[str], variants_dir: Path) -> None:
    require_split(manifest, allowed=('dev',))
    current = ranking_config_hash(RetrievalConfig())
    if current != FROZEN_RANKING_HASH:
        raise ValueError(f'Ranking config {current} differs from the frozen hash {FROZEN_RANKING_HASH}')
    first = tuple(t['instance_id'] for t in manifest['tasks'][:len(DRY_RUN_TASKS)])
    if first != DRY_RUN_TASKS:
        raise ValueError(f'Dry-run tasks {DRY_RUN_TASKS} must be the first manifest tasks (export uses --limit), got {first}')
    for arm in arms:
        if not (Path(variants_dir) / f'{arm}.json').is_file():
            raise ValueError(f'{arm}.json is missing in {variants_dir}; pass --arms without {arm} '
                             '(the gate is then INCOMPLETE_A3_MISSING)')


def _script(name: str) -> str:
    return str(ROOT / 'scripts' / name)


def build_steps(ctx: Context) -> list[Step]:
    """Commands in run order; placeholders stand for values known only after an earlier step."""
    data = str(ctx.data_root)
    runner = [ctx.python, _script('run_repair_experiment.py')]
    common = ['--config', str(ctx.config), '--data-root', data, '--output-root', str(ctx.out / 'runs')]
    variants = ','.join(f"{arm}:{'bm25' if arm == 'A0' else 'graph'}" for arm in ctx.arms)
    return [
        Step('export_bundles', [ctx.python, _script('export_w9_pilot_bundles.py'), '--manifest', str(ctx.manifest),
                                '--approved-manifest', str(ctx.manifest), '--profile', str(ctx.profile),
                                '--tokenizer-manifest', str(ctx.tokenizer_manifest),
                                '--sources-root', str(ctx.data_root / 'repositories'),
                                '--output-root', str(ctx.data_root / BUNDLE_ROOT), '--limit', str(len(DRY_RUN_TASKS))]),
        Step('derive_config', [ctx.python, _script('derive_experiment_config.py'), '--template', str(ctx.template),
                               '--data-root', data, '--tasks', ','.join(DRY_RUN_TASKS),
                               '--bundle-dir', f'@data/{BUNDLE_ROOT}/{ctx.export_run}', '--variants', variants,
                               '--out', str(ctx.config)]),
        Step('preflight', runner + ['preflight'] + common),
        Step('run', runner + ['run'] + common),
        Step('grade', [ctx.python, _script('grade_repair_candidates.py'),
                       '--experiment-dir', str(ctx.out / 'runs' / ctx.experiment_id), '--manifest', str(ctx.manifest),
                       '--approved-manifest', str(ctx.manifest), '--dataset-parquet', str(ctx.parquet),
                       '--output-root', str(ctx.out / 'grades'), '--execute']),
        Step('aggregate', runner + ['aggregate'] + common + ['--grades', ctx.grades, '--parquet', str(ctx.parquet),
                                                             '--out', str(ctx.out / 'aggregate')]),
    ]


def infra_errors(steps: list[dict], attempts: dict, grades: dict | None) -> list[dict]:
    errors = [{'kind': 'step_exit', 'step': s['name'], 'exit_code': s['exit_code']}
              for s in steps if s['exit_code'] != 0]
    for (task, variant), items in sorted(attempts.items()):
        last = items[-1]
        if last.get('state') != 'TERMINAL':
            errors.append({'kind': 'attempt_not_terminal', 'task': task, 'variant': variant, 'state': last.get('state')})
        elif last.get('status') == 'ERROR' and last.get('reason') in INFRA_REASONS:
            errors.append({'kind': 'runner_infra_reason', 'task': task, 'variant': variant, 'reason': last['reason']})
    if grades is not None:
        if grades.get('status') in ('BLOCKED', 'ERROR'):
            errors.append({'kind': 'grade_blocked', 'status': grades['status']})
        errors += [{'kind': 'grade_error', 'task': g.get('task_id'), 'variant': g.get('variant_id')}
                   for g in grades.get('grades', []) if g.get('harness_status') == 'ERROR']
    return errors


def gate(infra: list[dict], arms) -> str:
    if infra:
        return 'FAIL'
    return 'PASS' if 'A3' in arms else 'INCOMPLETE_A3_MISSING'


def heldout_commands(steps: list[Step], dev_manifest: Path) -> str:
    """Shell template for the protocol; never executed by this module."""
    lines = ['# Chỉ để chép vào protocol. Không chạy trước khi có tag `protocol-freeze`.', '', '```bash']
    for step in steps:
        argv = [a for i, a in enumerate(step.argv) if a != '--limit' and (i == 0 or step.argv[i - 1] != '--limit')]
        text = ' '.join(argv).replace(str(dev_manifest), '<HELDOUT_MANIFEST>')
        text = text.replace(','.join(DRY_RUN_TASKS), '<ALL_HELDOUT_TASKS>')
        lines += [f'# {step.name}', text, '']
    return '\n'.join(lines + ['```']) + '\n'


def _sha(path: Path) -> str | None:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _git_commit() -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _model_revision(ctx: Context) -> str | None:
    try:
        from vgar.evaluation.repair.manifest import load_experiment
        profile = load_experiment(ctx.config, ctx.data_root).profile
        return f'{profile.model_id}@{profile.revision}'
    except Exception:  # noqa: BLE001 -- best effort; the runner record carries the full identity
        return None


def _outcomes(ctx: Context) -> tuple[dict, dict | None]:
    from vgar.evaluation.repair.runner import read_attempts
    exp_dir = ctx.out / 'runs' / ctx.experiment_id
    attempts = read_attempts(exp_dir) if exp_dir.is_dir() else {}
    found = sorted((ctx.out / 'grades').glob('*/grades.json'))
    grades = json.loads(found[-1].read_text(encoding='utf-8')) if found else None
    return attempts, grades


def run_chain(ctx: Context, *, runner: Callable = subprocess.run) -> dict:
    """Run the chain once, stopping at the first failing step; dry_run.json is always written."""
    ctx.out.mkdir(parents=True, exist_ok=True)
    (ctx.out / 'logs').mkdir(exist_ok=True)
    manifest = json.loads(Path(ctx.manifest).read_text(encoding='utf-8'))
    record = {'git_commit': _git_commit(), 'started': _now(), 'tasks': list(DRY_RUN_TASKS), 'arms': list(ctx.arms),
              'hashes': {'ranking': ranking_config_hash(RetrievalConfig()), 'manifest': manifest.get('manifest_hash'),
                         'variants': {a: _sha(Path(ctx.variants_dir) / f'{a}.json') for a in ctx.arms}},
              'steps': [], 'infra_errors': [], 'gate': 'FAIL', 'experiment_id': None}
    (ctx.out / 'heldout_commands.md').write_text(heldout_commands(build_steps(ctx), ctx.manifest), encoding='utf-8')
    try:
        try:
            check_preconditions(manifest, list(ctx.arms), ctx.variants_dir)
        except ValueError as error:
            record['precondition_error'] = str(error)
            return record
        current = ctx
        for index in range(len(build_steps(ctx))):
            step = build_steps(current)[index]
            started, clock = _now(), time.perf_counter()
            done = runner(step.argv, capture_output=True, text=True)
            log = ctx.out / 'logs' / f'{step.name}.log'
            log.write_text(f'$ {" ".join(step.argv)}\n{done.stdout or ""}\n{done.stderr or ""}', encoding='utf-8')
            record['steps'].append({'name': step.name, 'argv': step.argv, 'started': started, 'finished': _now(),
                                    'seconds': time.perf_counter() - clock, 'exit_code': done.returncode,
                                    'log': str(log)})
            if done.returncode != 0:
                break
            if step.name == 'export_bundles':
                found = _RUN_DIRECTORY.search(done.stdout or '')
                if not found:
                    record['steps'][-1]['exit_code'] = 'NO_RUN_DIRECTORY'
                    break
                current = Context(**{**current.__dict__, 'export_run': Path(found.group(1).strip()).name})
            elif step.name == 'derive_config':
                current = Context(**{**current.__dict__, 'experiment_id': (done.stdout or '').split()[-1]})
                record['experiment_id'] = current.experiment_id
                record['hashes']['config'] = _sha(ctx.config)
                record['hashes']['model_revision'] = _model_revision(ctx)
            elif step.name == 'grade':
                found = sorted((ctx.out / 'grades').glob('*/grades.json'))
                current = Context(**{**current.__dict__, 'grades': str(found[-1]) if found else '<GRADES_JSON>'})
        attempts, grades = _outcomes(current)
        record['infra_errors'] = infra_errors(record['steps'], attempts, grades)
        record['gate'] = gate(record['infra_errors'], ctx.arms)
        return record
    finally:
        record['finished'] = _now()
        (ctx.out / 'dry_run.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
