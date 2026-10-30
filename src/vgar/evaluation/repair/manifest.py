"""Experiment config: identity, variants and per-task RepairTask planning; never runs the engine.

Paths starting with '@data/' resolve against --data-root (machine-specific); others against the config file.
The experiment ID hashes pins and contents only, so the same experiment keeps its ID on another machine.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vgar.evaluation.harness.task_env import validate_profile
from vgar.repair.admission import base_inventory
from vgar.repair.config import load_config, load_task
from vgar.repair.contracts import ModelProfile, RepairPolicy, RepairTask
from vgar.repair.evidence import digest
from vgar.repair.policy import VariantPolicy, load_variant, policy_hash
from vgar.repair.prompt import template_path

SCHEMA = 'vgar-m3-experiment-v1'
_TEST_DIRS = ('test', 'tests', 'testing')


@dataclass(frozen=True)
class Variant:
    variant_id: str
    arm: Literal['bm25', 'graph']
    policy: dict


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    source_type: Literal['swebench', 'fixture']
    generation: Literal['real', 'fake']
    policy: RepairPolicy
    profile: ModelProfile
    variants: tuple[Variant, ...]
    task_ids: tuple[str, ...]
    raw: dict
    base: Path
    task_sources: dict


@dataclass(frozen=True)
class TaskPlan:
    task_id: str
    variant: Variant
    task: RepairTask | None
    admission_args: dict | None
    skip_reason: str | None
    skip_detail: str | None


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def resolve(value: str, base: Path, data_root: Path) -> Path:
    if value.startswith('@data/'):
        return Path(data_root) / value.removeprefix('@data/')
    return base / value


def _read_inputs(path: Path) -> dict | None:
    if not path.is_file():
        return None
    inputs = json.loads(path.read_text(encoding='utf-8'))
    inputs['overlay'] = {dest: (path.parent / name).read_text(encoding='utf-8')
                         for dest, name in inputs.get('overlay', {}).items()}
    return inputs


def load_experiment(path: Path, data_root: Path) -> Experiment:
    path = Path(path).resolve()
    base = path.parent
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema') != SCHEMA:
        raise ValueError('Unsupported experiment schema: ' + str(raw.get('schema')))
    source, generation = raw['source'], raw['generation']
    if source['type'] not in ('swebench', 'fixture') or generation not in ('real', 'fake'):
        raise ValueError('Unknown source type or generation mode')
    if source['type'] == 'swebench' and generation == 'fake':
        raise ValueError('fake generation is not allowed for SWE-bench tasks (no reference patch may be used)')
    policy, profile = load_config(resolve(raw['repair_config'], base, data_root))
    variants, variant_ids = [], []
    for item in raw['variants']:
        if item.get('arm') not in ('bm25', 'graph'):
            raise ValueError('Each variant needs an explicit arm: bm25 or graph')
        loaded = load_variant(resolve(item['path'], base, data_root))
        bound = VariantPolicy.model_validate(loaded.model_dump() | {'arm': item['arm']})
        variants.append(Variant(loaded.variant_id, item['arm'],
                                json.loads(resolve(item['path'], base, data_root).read_text(encoding='utf-8'))))
        variant_ids.append([loaded.variant_id, item['arm'], policy_hash(bound)])
    identity = {'schema': SCHEMA, 'generation': generation, 'policy': policy.model_dump(mode='json'),
                'model': {'model_id': profile.model_id, 'revision': profile.revision,
                          'tokenizer_manifest': digest(profile.tokenizer_manifest.read_bytes()),
                          'template': digest(template_path(policy.prompt_version).read_bytes())},
                'variants': variant_ids}
    if source['type'] == 'swebench':
        manifest = json.loads(resolve(source['manifest']['path'], base, data_root).read_text(encoding='utf-8'))
        if manifest.get('manifest_hash') != source['manifest']['sha256']:
            raise ValueError('Pilot manifest differs from the pinned manifest hash')
        task_sources = {row['instance_id']: row for row in manifest['tasks']}
        if 'task_ids' in source:
            # W10 stages run an ordered, locked subset of one manifest; absent key keeps W9 identities unchanged.
            ids = source['task_ids']
            if not ids or len(set(ids)) != len(ids) or any(i not in task_sources for i in ids):
                raise ValueError('source.task_ids must be distinct tasks of the pinned manifest')
            task_sources = {i: task_sources[i] for i in ids}
            identity['task_ids'] = list(ids)
        profile_pin = source.get('bundle_profile')
        if profile_pin and digest(resolve(profile_pin['path'], base, data_root).read_bytes()) != profile_pin['sha256']:
            raise ValueError('Pinned bundle profile hash mismatch')
        for task_id, pin in sorted(source.get('graph_documents', {}).items()):
            if digest(resolve(pin['path'], base, data_root).read_bytes()) != pin['sha256']:
                raise ValueError(f'Pinned graph document hash mismatch for {task_id}')
        inputs_dir = resolve(source['task_inputs'], base, data_root)
        identity['source'] = {
            'manifest': source['manifest']['sha256'],
            'profiles': {t: p['sha256'] for t, p in sorted(source['profiles'].items())},
            'bundles': {t: {a: b['hashes'] for a, b in sorted(arms.items())}
                        for t, arms in sorted(source['bundles'].items())},
            'task_inputs': {t: _read_inputs(inputs_dir / f'{t}.json') for t in task_sources}}
        for key in ('bundle_profile', 'graph_documents'):
            if key in source:
                identity['source'][key] = source[key]['sha256'] if key == 'bundle_profile' else {
                    t: p['sha256'] for t, p in sorted(source[key].items())}
        if 'excluded' in source:
            # W10 D25: tasks excluded before running (e.g. OVER_CAP in any arm), skipped in every arm with the reason.
            excluded = source['excluded']
            if (not isinstance(excluded, dict) or any(t not in task_sources for t in excluded)
                    or any(not isinstance(r, str) or not r.strip() for r in excluded.values())):
                raise ValueError('source.excluded must map tasks of this experiment to a non-empty reason')
            identity['source']['excluded'] = dict(sorted(excluded.items()))
    else:
        task_sources = {}
        for task_file in source['tasks']:
            task_path = resolve(task_file, base, data_root)
            task_sources[load_task(task_path).task_id] = task_path
        identity['source'] = {'fixture_tasks': [digest(Path(p).read_bytes()) for p in task_sources.values()]}
    experiment_id = digest(_canonical(identity)).removeprefix('sha256:')[:16]
    return Experiment(experiment_id, source['type'], generation, policy, profile, tuple(variants),
                      tuple(task_sources), raw, base, task_sources)


def load_graph(exp: Experiment, task_id: str, data_root: Path) -> dict | None:
    """The hash-pinned baseline graph of one task, checked against the manifest repo/base; None when not pinned."""
    pin = exp.raw['source'].get('graph_documents', {}).get(task_id)
    if pin is None:
        return None
    raw = resolve(pin['path'], exp.base, data_root).read_bytes()
    if digest(raw) != pin['sha256']:
        raise ValueError(f'Pinned graph document hash mismatch for {task_id}')
    document = json.loads(raw)
    row = exp.task_sources[task_id]
    for field, expected in (('repo_key', row['repo']), ('repository_revision', row['base_commit'])):
        if document.get(field) != expected:
            raise ValueError(f'Graph document {field} differs from the manifest task {task_id}')
    return document


def production_paths(files, roots) -> tuple[str, ...]:
    """Same production scope rule as repair.admission: .py under roots, outside test dirs/files."""
    return tuple(sorted(
        p for p in files
        if p.endswith('.py') and any(p.startswith(r + '/') for r in roots)
        and not any(s.lower() in _TEST_DIRS for s in p.split('/')[:-1])
        and not Path(p).name.startswith(('test_', 'conftest'))))


def _skip(task_id, variant, reason, detail):
    return TaskPlan(task_id, variant, None, None, reason, detail)


def plan_task(exp: Experiment, task_id: str, variant: Variant, data_root: Path) -> TaskPlan:
    if exp.source_type == 'fixture':
        return TaskPlan(task_id, variant, load_task(exp.task_sources[task_id]), None, None, None)
    source, row = exp.raw['source'], exp.task_sources[task_id]
    if task_id in source.get('excluded', {}):
        return _skip(task_id, variant, 'TASK_EXCLUDED', source['excluded'][task_id])
    where = lambda value: resolve(value, exp.base, data_root)
    pin = source['profiles'].get(task_id)
    if pin is None or not where(pin['path']).is_file():
        return _skip(task_id, variant, 'TASK_INPUT_MISSING', 'environment profile: ' + str(pin and where(pin['path'])))
    profile = validate_profile(json.loads(where(pin['path']).read_text(encoding='utf-8')), expected_task=row)
    if profile['status'] != 'COLLECTED':
        return _skip(task_id, variant, 'TASK_EXCLUDED', profile['reason'])
    inputs_path = where(source['task_inputs']) / f'{task_id}.json'
    inputs = _read_inputs(inputs_path)
    if inputs is None:
        return _skip(task_id, variant, 'TASK_INPUT_MISSING', 'task inputs: ' + str(inputs_path))
    bundle = source['bundles'].get(task_id, {}).get(variant.arm)
    context_manifest = bundle and where(bundle['path']) / 'context_manifest.json'
    if not bundle or not context_manifest.is_file():
        return _skip(task_id, variant, 'TASK_INPUT_MISSING', f'{variant.arm} bundle for {task_id}')
    checkout = where(source['checkouts'].format(task_id=task_id)).resolve()
    files = base_inventory(checkout, row['base_commit'])
    task = RepairTask(
        task_id=task_id, issue_text=row['problem_statement'], source_repo=checkout, repo_key=row['repo'],
        revision=row['base_commit'],
        graph_version=json.loads(context_manifest.read_text(encoding='utf-8'))['graph_version'],
        bundle_directory=context_manifest.parent.resolve(), failing_selectors=tuple(inputs['failing_selectors']),
        fallback_scope=tuple(inputs['fallback_scope']),
        allowed_source_paths=production_paths(files, inputs['source_roots']),
        protected_paths=tuple(inputs['protected_paths']), trusted_fixture=False)
    admission_args = dict(
        manifest_path=where(source['manifest']['path']).resolve(), profile_path=where(pin['path']).resolve(),
        expected_manifest_hash=source['manifest']['sha256'], expected_profile_hash=pin['sha256'],
        bundle_hashes=bundle['hashes'], source_roots=inputs['source_roots'], overlay=inputs['overlay'],
        docker_host=source['docker_host'])
    return TaskPlan(task_id, variant, task, admission_args, None, None)
