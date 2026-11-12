"""Measure one fixed patch once; derive policy verdicts without generation or arm rebinding."""
from __future__ import annotations

import copy
import base64
import json
from pathlib import Path
import shutil
import time

from vgar.repair.evidence import atomic_json, digest
from vgar.repair.executor import remaining_timeout
from vgar.repair.patch import PatchPolicy, apply_patch, parse_unified_diff
from vgar.repair.policy import VariantPolicy, policy_hash, required_checks
from vgar.repair.static_checks import collect_static_measurements
from vgar.repair.static_diagnostics import DiagnosticReport
from vgar.repair.test_runner import collect_tests, is_collection_failure, run_tests
from vgar.repair.verification import _assess_w9_static, assess_transition, expand_required
from vgar.repair.verification_checks import (
    CheckIntegrityError, assert_checks_baseline, assess_compatibility,
    capture_checks_baseline, inventory_hash, run_compatibility_checks,
)
from vgar.repair.workspace import inventory

SCHEMA = 'vgar-verifier-vector-v1'
STATIC = ('syntax', 'mypy', 'ruff')
CHECKS = ('tests', *STATIC, 'api', 'structural')


def canonical_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def seal_vector(value):
    result = copy.deepcopy(value)
    result.pop('vector_hash', None)
    result['vector_hash'] = canonical_hash(result)
    return result


def validate_vector(value):
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('Invalid neutral vector schema')
    if seal_vector(value)['vector_hash'] != value.get('vector_hash'):
        raise ValueError('Neutral vector hash mismatch')
    for half in ('baseline', 'post'):
        raw = value.get(half, {})
        if 'variant_policy_hash' in raw or 'variant_policy_hash' in raw.get('static', {}):
            raise ValueError('Raw measurement vector must be arm-neutral')
    return value


def _qualified(before, task_scope, variant):
    try:
        tests = before['tests']
        required = before['required_ids']
        static = before['static']
        return bool(before['collection']['status'] == 'PASS' and required
            and tests['status'] == 'FAIL' and any(tests['outcomes'].get(n) == 'FAIL' for n in required)
            and all(tests['outcomes'].get(n) in ('FAIL', 'PASS') for n in required)
            and not any(v == 'ERROR' for v in tests['outcomes'].values())
            and set(static['source_snapshot']) == set(task_scope)
            and all(DiagnosticReport.model_validate(static[k]['report']).execution_status in ('COMPLETE', 'UNAVAILABLE')
                    for k in required_checks(variant) & set(STATIC)))
    except (KeyError, TypeError, ValueError):
        return False


def derive_verdict(vector, variant):
    """No execution: qualification and verdict from an immutable, independently hashed vector."""
    validate_vector(vector)
    variant = VariantPolicy.model_validate(variant)
    before, post = vector.get('baseline', {}), vector.get('post', {})
    qualified = _qualified(before, vector['binding']['scope'], variant)
    reasons, status = [], 'ERROR'
    if vector.get('integrity', {}).get('status') != 'PASS':
        reasons = vector.get('integrity', {}).get('reasons', []) + ['VERIFICATION_INCOMPLETE']
    elif not qualified:
        reasons = ['BASELINE_NOT_QUALIFIED', 'VERIFICATION_INCOMPLETE']
    elif vector.get('apply', {}).get('status') != 'PASS':
        status = 'FAIL' if vector.get('apply', {}).get('status') == 'FAIL' else 'ERROR'
        reasons = ['PATCH_APPLY_FAILED' if status == 'FAIL' else 'VERIFICATION_INCOMPLETE']
    else:
        try:
            status, reasons = assess_transition(before, post['tests'])
            if post['collection']['status'] != 'PASS':
                if is_collection_failure(post['collection']) and status != 'ERROR':
                    status, reasons = 'FAIL', reasons + ['TEST_COLLECTION_FAILED']
                else:
                    status, reasons = 'ERROR', reasons + ['VERIFICATION_INCOMPLETE']
            static = copy.deepcopy(post['static'])
            status, reasons, _ = _assess_w9_static(before, static, variant, status, reasons)
            status, reasons = assess_compatibility(post.get('compatibility', {}), required_checks(variant), status, reasons)
            if static['config_hashes'] != before['static']['config_hashes']:
                status, reasons = 'ERROR', reasons + ['STATIC_CONFIG_CHANGED']
        except (KeyError, TypeError, ValueError):
            status, reasons = 'ERROR', ['VERIFICATION_INCOMPLETE']
    return dict(status=status, recommendation={'PASS': 'ACCEPT', 'FAIL': 'REVISE'}.get(status, 'REJECT'),
        reasons=list(dict.fromkeys(reasons)), baseline_qualified=qualified,
        vector_hash=vector['vector_hash'], variant_id=variant.variant_id, policy_hash=policy_hash(variant))


def _not_run(reason):
    return dict(status='NOT_RUN', reason=reason)


def collect_patch_vector(task, lease, executor, policy, raw_patch, artifact_root, *, guard=None):
    """Trusted internal collector. Public verify_once establishes admission and owns the lease."""
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    if root.resolve().is_relative_to(lease.path.resolve()):
        raise ValueError('Evaluation artifacts must be outside target source')
    guard = guard or (lambda: None)
    before_inventory = inventory(lease.path)
    vector = dict(schema=SCHEMA, task_id=task.task_id,
        binding=dict(source_inventory_hash=inventory_hash(before_inventory),
            scope=list(task.allowed_source_paths), repo_key=task.repo_key, revision=task.revision),
        integrity=dict(status='PASS', reasons=[]), baseline={}, apply=_not_run('not_applied'), post={})
    for half in ('baseline', 'post'):
        vector[half] = {k: _not_run('not_measured') for k in ('collection', 'tests', 'static', 'compatibility')}

    def measure(half):
        guard()
        half['collection'] = collect_tests(lease, task.fallback_scope, executor, policy.command_timeout)
        guard()
        # Return-value ERROR/FAIL is evidence; it does not suppress independent checks.
        half['tests'] = run_tests(lease, task.fallback_scope, executor, policy.command_timeout)
        guard()
        half['static'] = collect_static_measurements(lease, task.allowed_source_paths, policy, executor)
        guard()

    try:
        guard()
        frozen = capture_checks_baseline(task, lease, root, guard=guard)
        vector['binding']['analysis_baseline'] = frozen
        measure(vector['baseline'])
        try:
            vector['baseline']['required_ids'] = expand_required(task.failing_selectors,
                vector['baseline']['collection'].get('node_ids', []))
        except ValueError as error:
            vector['baseline']['required_ids'] = []
            vector['baseline']['qualification_detail'] = str(error)
        assert_checks_baseline(task, lease, frozen, root, guard=guard)
        self_analysis = run_compatibility_checks(task, lease,
            type('Changed', (), {'changed_files': task.allowed_source_paths})(), frozen, root, guard=guard)
        copied = {}
        for name in ('api', 'structural'):
            dto = copy.deepcopy(self_analysis[name])
            ref = f'baseline_checks/{name}.json'
            destination = root / ref
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(root / dto['details_ref'], destination)
            if digest(destination.read_bytes()) != self_analysis['hashes'][name]:
                raise CheckIntegrityError('Baseline sidecar copy hash changed')
            dto['details_ref'] = ref
            copied[name] = dto
        vector['baseline']['compatibility'] = copied
        vector['baseline']['compatibility_hashes'] = self_analysis['hashes']
        guard()
        try:
            parsed = parse_unified_diff(raw_patch, PatchPolicy(task.allowed_source_paths, task.protected_paths,
                policy.max_diff_bytes, policy.max_files, policy.max_changed_lines))
        except ValueError as error:
            vector['apply'] = dict(status='FAIL', reason='PATCH_PARSE_ERROR', message=str(error))
            return seal_vector(vector)
        applied = apply_patch(lease, parsed, executor)
        vector['apply'] = applied.model_dump(mode='json')
        if applied.status != 'PASS':
            return seal_vector(vector)
        pinned = inventory_hash(inventory(lease.path))
        if getattr(lease, 'applied_inventory_hash', pinned) != pinned:
            raise CheckIntegrityError('Applied inventory pin mismatch')
        vector['binding']['applied_inventory_hash'] = pinned
        guard()
        measure(vector['post'])
        vector['post']['compatibility'] = run_compatibility_checks(task, lease, applied, frozen, root,
            guard=guard, expected_candidate_hash=pinned)
        result = vector['post']['compatibility']
        vector['post']['compatibility_hashes'] = result.pop('hashes')
        if inventory_hash(inventory(lease.path)) != pinned:
            raise CheckIntegrityError('Candidate changed during tests/static/analysis')
        lease.assert_original()
    except Exception as error:
        # Escaping exceptions (including Docker identity/config drift) are never optional.
        vector['integrity'] = dict(status='ERROR', reasons=[
            'RUN_TIMEOUT' if isinstance(error, TimeoutError) else 'CHECK_INTEGRITY_ERROR'],
            exception=dict(type=type(error).__name__, message=str(error)))
    return seal_vector(vector)


def _empty_vector(task, reason):
    return dict(schema=SCHEMA, task_id=task.task_id,
        binding={'scope': list(task.allowed_source_paths)},
        integrity=dict(status='ERROR', reasons=[reason]),
        baseline={k: _not_run(reason) for k in ('collection', 'tests', 'static', 'compatibility')},
        apply=_not_run(reason), post={k: _not_run(reason) for k in ('collection', 'tests', 'static', 'compatibility')})


def verify_once(task, raw_patch, policy, output_root, *, admission=None, temp_root=None, pool_binding=None):
    """Own one private workspace and one fixed patch; never call a repair generator."""
    from vgar.repair.admission import prepare_admitted_workspace, validate_admission
    from vgar.repair.deadline import DeadlineExecutor, require_trusted_fixture
    from vgar.repair.workspace import create_workspace
    root = Path(output_root).resolve()
    if root.exists() or root.is_relative_to(task.source_repo.resolve()):
        raise ValueError('Fresh output outside original source required')
    deadline = time.monotonic() + policy.global_timeout
    def guard():
        return remaining_timeout(deadline)
    if policy.runtime == 'docker_admitted':
        admission = validate_admission(task, admission)
    else:
        if admission is not None:
            raise ValueError('Native fixtures cannot use Docker admission')
        require_trusted_fixture(task)
    root.mkdir(parents=True)
    vector, lease, interrupted = None, None, False
    try:
        factory = prepare_admitted_workspace if admission is not None else create_workspace
        temp = Path(temp_root) if temp_root else root.parent / '.verifier-workspaces'
        lease = (factory(task, admission, temp, deadline=deadline) if admission is not None
                 else factory(task.source_repo, temp, deadline=deadline))
        if admission is not None:
            from vgar.repair.docker_executor import DockerExecutor
            executor = DockerExecutor(lease, task, admission, deadline, policy.max_output_bytes, root / 'docker')
        else:
            executor = DeadlineExecutor(lease, deadline, policy.max_output_bytes)
        vector = collect_patch_vector(task, lease, executor, policy, raw_patch, root, guard=guard)
        vector['binding']['repair_policy_hash'] = canonical_hash(policy.model_dump(mode='json'))
        vector['binding']['admission_hash'] = admission.snapshot()['admission_hash'] if admission is not None else None
        vector['binding']['environment'] = ({k: admission.snapshot()[k] for k in (
            'expected_manifest_hash', 'expected_profile_hash', 'bundle_hashes', 'overlay_hash')}
            if admission is not None else {'runtime': policy.runtime})
        lease.assert_original()
    except BaseException as error:
        interrupted = isinstance(error, KeyboardInterrupt)
        reason = 'INTERRUPTED' if interrupted else 'RUN_TIMEOUT' if isinstance(error, TimeoutError) else 'CHECK_INTEGRITY_ERROR'
        if vector is None:
            vector = _empty_vector(task, reason)
        vector['integrity'] = dict(status='ERROR', reasons=[reason],
            exception=dict(type=type(error).__name__, message=str(error)))
    finally:
        if lease is not None:
            try:
                lease.__exit__()
            except Exception as error:
                if vector is not None:
                    vector['integrity'] = dict(status='ERROR', reasons=['WORKSPACE_CLEANUP_ERROR'], message=str(error))
                else:
                    raise
    if pool_binding is not None:
        vector['binding']['pool'] = copy.deepcopy(pool_binding)
        if (digest(raw_patch) != pool_binding['patch_hash']
                or (vector.get('apply', {}).get('status') == 'PASS' and (
                    vector['binding'].get('source_inventory_hash') != pool_binding['execution_source_hash']
                    or vector['binding'].get('applied_inventory_hash') != pool_binding['execution_candidate_hash']))):
            vector['integrity'] = dict(status='ERROR', reasons=['POOL_SOURCE_BINDING_CHANGED'])
    vector['binding']['repair_policy_hash'] = canonical_hash(policy.model_dump(mode='json'))
    vector['binding'].setdefault('repo_key', task.repo_key)
    vector['binding'].setdefault('revision', task.revision)
    if lease is not None:
        vector['binding']['original_source_inventory'] = lease.before
    vector['binding']['overlay'] = admission.snapshot()['overlay'] if admission is not None else {}
    vector = seal_vector(vector)
    atomic_json(root / 'vector.json', vector)
    if interrupted:
        raise KeyboardInterrupt()
    return vector


def confusion_metrics(rows):
    """BAD is positive. Pending vectors stay unknown; actual ERROR is nonaccept."""
    result = {k: 0 for k in ('TP', 'FP', 'FN', 'TN', 'bad_total', 'good_total',
        'bad_not_run', 'good_not_run', 'bad_errors', 'good_errors', 'bad_check_failures', 'good_check_failures')}
    for row in rows:
        if row['label'] not in ('GOOD', 'BAD'):
            raise ValueError('Unknown patch label')
        bad = row['label'] == 'BAD'
        prefix = 'bad' if bad else 'good'
        result[prefix + '_total'] += 1
        if row.get('status') in (None, 'NOT_RUN'):
            result[prefix + '_not_run'] += 1
            continue
        if row['status'] not in ('PASS', 'FAIL', 'ERROR'):
            raise ValueError('Unknown verification status')
        if row.get('recommendation') != {'PASS': 'ACCEPT', 'FAIL': 'REVISE', 'ERROR': 'REJECT'}[row['status']]:
            raise ValueError('Inconsistent status/recommendation')
        accept = row.get('recommendation') == 'ACCEPT'
        result[('FN' if bad else 'TN') if accept else ('TP' if bad else 'FP')] += 1
        if row['status'] == 'ERROR':
            result[prefix + '_errors'] += 1
        elif row['status'] == 'FAIL':
            result[prefix + '_check_failures'] += 1
    result['FAR'] = (result['FN'] / result['bad_total'] if result['bad_total'] and not result['bad_not_run'] else None)
    result['FRR'] = (result['FP'] / result['good_total'] if result['good_total'] and not result['good_not_run'] else None)
    for prefix, numerator, metric in (('bad', 'FN', 'FAR'), ('good', 'FP', 'FRR')):
        observed = result[prefix + '_total'] - result[prefix + '_not_run']
        result[prefix + '_observed'] = observed
        result['observed_' + metric] = result[numerator] / observed if observed else None
    return result


def _save_campaign(root, value):
    value.pop('campaign_hash', None)
    value['campaign_hash'] = canonical_hash(value)
    atomic_json(root / 'campaign.json', value)


def _validated_policies(variants):
    if set(variants) != {'A0', 'A1', 'A2', 'A3'}:
        raise ValueError('Exactly A0-A3 policies required')
    result, common = {}, None
    for name, value in sorted(variants.items()):
        variant = VariantPolicy.model_validate(value)
        if variant.variant_id != name:
            raise ValueError('Policy identity differs from variant key')
        variant = VariantPolicy.model_validate(variant.model_copy(update={
            'arm': variant.arm or ('bm25' if name == 'A0' else 'graph')}))
        if name in ('A2', 'A3') and variant.arm != 'graph':
            raise ValueError('Arm fairness: A2/A3 require graph')
        shared = {k: v for k, v in variant.model_dump(mode='json').items()
                  if k not in ('variant_id', 'arm', 'required_checks')}
        if common is not None and common != shared:
            raise ValueError('Arm fairness: common variant semantics differ')
        common, result[name] = shared, variant
    return result


def evaluate_pool(pool_root, output_root, task_provider, policy, variants, *, expected_pool_hash,
                  temp_root=None, runtime_provenance=None, source_roots=()):
    """One worker, one verify call per CREATED slot; persist all planned slots before execution."""
    from vgar.evaluation.repair.mutant_pool import load_pool
    pool_root, root = Path(pool_root).resolve(), Path(output_root).resolve()
    pool = load_pool(pool_root, expected_pool_hash=expected_pool_hash)
    if root.exists():
        raise ValueError('Campaign output already exists; choose a new output directory')
    if root.is_relative_to(pool_root) or pool_root.is_relative_to(root):
        raise ValueError('Fresh campaign output must not overlap frozen pool')
    variants = _validated_policies(variants)
    prepared, input_errors = {}, {}
    roots = [Path(p).resolve() for p in source_roots]
    for task_id in {s['task_id'] for s in pool['slots'] if s['status'] == 'CREATED'}:
        try:
            prepared[task_id] = task_provider(task_id)
            roots.append(Path(prepared[task_id][0].source_repo).resolve())
        except Exception as error:
            input_errors[task_id] = error
    if any(root == p or root.is_relative_to(p) or p.is_relative_to(root) for p in roots):
        raise ValueError('Campaign output/source overlap is forbidden')
    root.mkdir(parents=True)
    record = dict(schema='vgar-verifier-campaign-v1', pool_hash=pool['pool_hash'],
        repair_policy=policy.model_dump(mode='json'),
        source_roots=sorted({str(p) for p in roots}),
        runtime_provenance=copy.deepcopy(runtime_provenance or {}),
        variants={name: VariantPolicy.model_validate(v).model_dump(mode='json') for name, v in variants.items()},
        slots=[dict(slot_id=s['slot_id'], task_id=s['task_id'], operator=s['operator'], label=s['label'],
            status='NOT_RUN' if s['status'] == 'CREATED' else s['status'], reason=s['reason'],
            vector_ref=None, vector_file_hash=None) for s in pool['slots']])
    _save_campaign(root, record)
    indexed = {t['task_id']: t for t in pool['tasks']}
    for i, (slot, row) in enumerate(zip(pool['slots'], record['slots'])):
        if slot['status'] != 'CREATED':
            continue
        directory = root / 'vectors' / f'{i:03d}'
        try:
            if slot['task_id'] in input_errors:
                raise input_errors[slot['task_id']]
            task, admission = prepared[slot['task_id']]
            frozen = indexed[slot['task_id']]
            if (task.task_id != frozen['task_id'] or task.repo_key != frozen['repo'] or task.revision != frozen['base_commit']
                    or sorted(task.allowed_source_paths) != frozen['allowed_paths']
                    or sorted(task.protected_paths) != frozen['protected_paths']
                    or inventory(task.source_repo) != frozen['source_inventory']):
                raise ValueError('Task source/scope differs from sealed pool')
            patch = (pool_root / slot['patch_ref']).read_bytes()
            if digest(patch) != slot['patch_hash']:
                raise ValueError('Patch bytes changed after pool validation')
            overlay = admission.snapshot()['overlay'] if admission is not None else {}
            overlay_hashes = {p: digest(raw) for p, raw in overlay.items()}
            binding = dict(pool_hash=pool['pool_hash'], slot_id=slot['slot_id'], patch_hash=slot['patch_hash'],
                execution_source_hash=inventory_hash(frozen['source_inventory'] | overlay_hashes),
                execution_candidate_hash=inventory_hash(slot['predicted_inventory'] | overlay_hashes))
            vector = verify_once(task, patch.decode('utf-8'), policy, directory, admission=admission,
                temp_root=temp_root, pool_binding=binding)
            if not (directory / 'vector.json').is_file():
                raise ValueError('Verifier did not publish a vector')
            disk = json.loads((directory / 'vector.json').read_bytes())
            validate_vector(disk)
            if disk != vector:
                raise ValueError('Published vector differs from measured vector')
            if disk['binding'].get('pool') != binding:
                raise ValueError('Published vector has no matching pool binding')
            row.update(status='EVALUATED', reason=None)
        except KeyboardInterrupt:
            row.update(status='NOT_RUN', reason='INTERRUPTED')
            if (directory / 'vector.json').is_file():
                row.update(status='EVALUATED', reason='INTERRUPTED',
                    vector_ref=(directory / 'vector.json').relative_to(root).as_posix(),
                    vector_file_hash=digest((directory / 'vector.json').read_bytes()))
            _save_campaign(root, record)
            raise
        except Exception as error:
            row.update(status='ERROR', reason='TASK_INPUT_ERROR', detail=dict(type=type(error).__name__, message=str(error)))
            directory.mkdir(parents=True, exist_ok=True)
            # Terminal infrastructure/input errors are explicit full-scope NOT_RUN measurements,
            # never a patch exclusion or a fabricated check failure.
            minimal = type('Task', (), {'task_id': slot['task_id'], 'allowed_source_paths': indexed[slot['task_id']]['allowed_paths']})()
            vector = seal_vector(_empty_vector(minimal, 'TASK_INPUT_ERROR'))
            frozen = indexed[slot['task_id']]
            vector['binding'].update(repo_key=frozen['repo'], revision=frozen['base_commit'],
                repair_policy_hash=canonical_hash(policy.model_dump(mode='json')),
                pool=dict(pool_hash=pool['pool_hash'], slot_id=slot['slot_id'], patch_hash=slot['patch_hash']))
            vector = seal_vector(vector)
            atomic_json(directory / 'vector.json', vector)
        row.update(vector_ref=(directory / 'vector.json').relative_to(root).as_posix(),
            vector_file_hash=digest((directory / 'vector.json').read_bytes()))
        _save_campaign(root, record)
    return record


def _read_vector(root, row):
    from vgar.repair.contracts import safe_path
    ref = safe_path(row['vector_ref'])
    path = root / ref
    if not path.resolve(strict=True).is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('Vector reference escapes campaign')
    raw = path.read_bytes()
    if digest(raw) != row['vector_file_hash']:
        raise ValueError('Stored vector file hash mismatch')
    vector = json.loads(raw)
    validate_vector(vector)
    # Independently read actual saved API/structural sidecars in both halves.
    for half in ('baseline', 'post'):
        dto_map = vector.get(half, {}).get('compatibility', {})
        hashes = vector.get(half, {}).get('compatibility_hashes', {})
        for name in ('api', 'structural'):
            dto = dto_map.get(name, {})
            if not dto.get('details_ref'):
                if dto.get('status') in ('PASS', 'FAIL', 'ERROR'):
                    raise ValueError('Computed check lacks a real sidecar reference')
                continue
            details = path.parent / safe_path(dto['details_ref'])
            if not details.resolve(strict=True).is_relative_to(path.parent.resolve()) or details.is_symlink():
                raise ValueError('Check sidecar reference escapes vector')
            data = details.read_bytes()
            if digest(data) != hashes.get(name):
                raise ValueError('Stored check sidecar hash mismatch')
            detail = json.loads(data)
            if detail['status'] != dto['status'] or detail['reasons'] != dto['reasons']:
                raise ValueError('Stored check sidecar differs from DTO')
    snapshot = vector.get('binding', {}).get('analysis_baseline')
    if snapshot:
        baseline = path.parent / safe_path(snapshot['details_ref'])
        if not baseline.resolve(strict=True).is_relative_to(path.parent.resolve()) or digest(baseline.read_bytes()) != snapshot['sha256']:
            raise ValueError('Stored baseline snapshot hash/reference mismatch')
    return vector


def _validate_source_proof(vector, task, slot, record, directory):
    """Consistency against externally pinned pool, not authentication of execution."""
    from vgar.repair.contracts import safe_path
    binding = vector['binding']
    if (binding.get('scope') != task['allowed_paths'] or binding.get('repo_key') != task['repo']
            or binding.get('revision') != task['base_commit']
            or binding.get('repair_policy_hash') != canonical_hash(record['repair_policy'])):
        raise ValueError('Vector source/scope/repair policy binding mismatch')
    snapshot = binding.get('analysis_baseline')
    if snapshot is None:
        if vector['integrity']['status'] != 'ERROR':
            raise ValueError('Computed vector lacks baseline source proof')
        return
    if binding.get('original_source_inventory') != task['source_inventory']:
        raise ValueError('Original source inventory differs from frozen pool')
    overlay = binding.get('overlay', {})
    if not isinstance(overlay, dict):
        raise ValueError('Invalid overlay source proof')
    for p, raw in overlay.items():
        safe_path(p)
        if (not isinstance(raw, str) or p in task['source_inventory']
                or not any(p == q or p.startswith(q + '/') for q in task['protected_paths'])):
            raise ValueError('Overlay source proof escapes protected scope')
    if record['repair_policy']['runtime'] == 'docker_admitted':
        environment = binding.get('environment', {})
        if environment.get('overlay_hash') != canonical_hash(overlay):
            raise ValueError('Overlay source hash mismatch')
    elif overlay:
        raise ValueError('Native fixture cannot introduce an admission overlay')
    base = task['source_inventory'] | {p: digest(raw) for p, raw in overlay.items()}
    candidate = slot['predicted_inventory'] | {p: digest(raw) for p, raw in overlay.items()}
    base_hash, candidate_hash = inventory_hash(base), inventory_hash(candidate)
    if binding.get('source_inventory_hash') != base_hash:
        raise ValueError('Baseline source inventory binding mismatch')
    applied = vector['apply']['status'] == 'PASS'
    if applied and binding.get('applied_inventory_hash') != candidate_hash:
        raise ValueError('Candidate inventory binding mismatch')
    pool_binding = binding['pool']
    if pool_binding.get('execution_source_hash') != base_hash or pool_binding.get('execution_candidate_hash') != candidate_hash:
        raise ValueError('Pool execution source/candidate binding mismatch')
    old = json.loads((directory / safe_path(snapshot['details_ref'])).read_bytes())
    if (old['inventory'] != base or old['scope'] != task['allowed_paths']
            or old['repo_key'] != task['repo'] or old['revision'] != task['base_commit']):
        raise ValueError('Saved baseline source/scope proof mismatch')
    old_hashes = {p: digest(base64.b64decode(raw, validate=True)) for p, raw in old['sources'].items()}
    expected_old = {p: base[p] for p in task['allowed_paths']}
    if old_hashes != expected_old:
        raise ValueError('Saved baseline source bytes differ from pool')
    for half, inventory_map in (('baseline', base), ('post', candidate)):
        measurement = vector[half]
        raw_static = measurement.get('static', {})
        if 'source_snapshot' in raw_static:
            for p, text in raw_static['source_snapshot'].items():
                if (p not in task['allowed_paths'] or not isinstance(text, str)
                        or inventory_map[p] not in (digest(text), digest(b'\xef\xbb\xbf' + text.encode('utf-8')))):
                    raise ValueError('Static source snapshot differs from frozen candidate')
            if (raw_static.get('syntax', {}).get('report', {}).get('execution_status') != 'ERROR'
                    and set(raw_static['source_snapshot']) != set(task['allowed_paths'])):
                raise ValueError('Static source snapshot scope incomplete without ERROR')
        for name in ('api', 'structural'):
            dto = measurement.get('compatibility', {}).get(name, {})
            if not dto.get('details_ref'):
                continue
            details = json.loads((directory / safe_path(dto['details_ref'])).read_bytes())['details']
            proof = details.get('binding', {})
            changed = task['allowed_paths'] if half == 'baseline' else vector['apply'].get('changed_files', [])
            if (proof.get('baseline_inventory_hash') != base_hash
                    or proof.get('candidate_inventory_hash') != (base_hash if half == 'baseline' else candidate_hash)
                    or proof.get('scope_paths') != task['allowed_paths']
                    or proof.get('api_paths') != sorted(changed)
                    or proof.get('resolver_profile') != old['resolver_profile']
                    or proof.get('module_roots') != old['module_roots'] or proof.get('config_hash') != old['config_hash']):
                raise ValueError('Check source/candidate/scope binding mismatch')
            paths = changed if name == 'api' else task['allowed_paths']
            expected = {'baseline': {p: base[p] for p in paths},
                'candidate': {p: inventory_map[p] for p in paths}}
            if details.get('source_hashes') != expected:
                raise ValueError('Check source hashes differ from frozen candidate')


def report_campaign(pool_root, campaign_root, *, expected_pool_hash):
    from vgar.evaluation.repair.mutant_pool import OPERATORS, load_pool
    pool = load_pool(Path(pool_root), expected_pool_hash=expected_pool_hash)
    root = Path(campaign_root)
    record = json.loads((root / 'campaign.json').read_bytes())
    if (record.get('schema') != 'vgar-verifier-campaign-v1' or record.get('pool_hash') != pool['pool_hash']
            or record.get('campaign_hash') != canonical_hash({k: v for k, v in record.items() if k != 'campaign_hash'})
            or [s['slot_id'] for s in record['slots']] != [s['slot_id'] for s in pool['slots']]):
        raise ValueError('Campaign hash/population mismatch')
    policies = _validated_policies({name: VariantPolicy.model_validate_json(json.dumps(value))
                                   for name, value in record['variants'].items()})
    by_arm = {name: [] for name in policies}
    tasks = {t['task_id']: t for t in pool['tasks']}
    states = {state: 0 for state in ('EVALUATED', 'ERROR', 'NOT_RUN', 'NOT_APPLICABLE')}
    for slot, row in zip(pool['slots'], record['slots']):
        if any(row[k] != slot[k] for k in ('task_id', 'operator', 'label')) or row['status'] not in states:
            raise ValueError('Campaign slot identity/state mismatch')
        states[row['status']] += 1
        if slot['status'] != 'CREATED':
            if row['status'] != slot['status'] or row['vector_ref'] is not None or row['vector_file_hash'] is not None:
                raise ValueError('Unavailable pool slot cannot become an evaluated patch')
            continue
        if row['status'] == 'NOT_RUN':
            if row.get('vector_ref') is not None or row.get('vector_file_hash') is not None:
                raise ValueError('NOT_RUN state cannot claim an evaluated vector')
        elif row['status'] in ('EVALUATED', 'ERROR'):
            if not row.get('vector_ref') or not row.get('vector_file_hash'):
                raise ValueError('Terminal campaign state requires a stored vector')
        else:
            raise ValueError('CREATED patch has an invalid campaign state')
        vector = _read_vector(root, row) if row.get('vector_ref') else None
        if vector is not None and vector['task_id'] != slot['task_id']:
            raise ValueError('Vector task differs from pool slot')
        if vector is not None:
            if row['status'] == 'ERROR' and vector.get('integrity', {}).get('status') != 'ERROR':
                raise ValueError('ERROR row cannot claim a successful vector state')
            binding = vector['binding'].get('pool', {})
            if any(binding.get(k) != v for k, v in dict(pool_hash=pool['pool_hash'],
                    slot_id=slot['slot_id'], patch_hash=slot['patch_hash']).items()):
                raise ValueError('Stored vector pool/slot/patch binding mismatch')
            _validate_source_proof(vector, tasks[slot['task_id']], slot, record,
                                   (root / row['vector_ref']).parent)
        for name, variant in policies.items():
            result = derive_verdict(vector, variant) if vector is not None else dict(status='NOT_RUN', recommendation=None)
            by_arm[name].append(dict(label=slot['label'], operator=slot['operator'], **result))
    def metrics(rows, selected):
        result = confusion_metrics(rows)
        for label, prefix in (('BAD', 'bad'), ('GOOD', 'good')):
            slots = [s for s in selected if s['label'] == label]
            result['planned_' + prefix] = len(slots)
            result[prefix + '_not_applicable'] = sum(s['status'] == 'NOT_APPLICABLE' for s in slots)
            result[prefix + '_pool_errors'] = sum(s['status'] == 'ERROR' for s in slots)
            generated = sum(s['status'] == 'CREATED' for s in slots)
            if (len(slots) != generated + result[prefix + '_not_applicable'] + result[prefix + '_pool_errors']
                    or generated != result[prefix + '_total']
                    or generated != result[prefix + '_observed'] + result[prefix + '_not_run']):
                raise ValueError('Metric population accounting mismatch')
            result[prefix + '_observed_coverage'] = result[prefix + '_observed'] / len(slots) if slots else None
            if result[prefix + '_pool_errors']:
                result['FAR' if label == 'BAD' else 'FRR'] = None
        return result
    summary = dict(schema='vgar-verifier-tables-v1', pool_hash=pool['pool_hash'],
        campaign_hash=record['campaign_hash'], expected_slots=pool['expected_slots'], task_count=len(pool['tasks']),
        source_roots=record.get('source_roots', []),
        generated_patches=sum(s['status'] == 'CREATED' for s in pool['slots']), states=states,
        complete=states['NOT_RUN'] == 0 and not any(s['status'] == 'ERROR' for s in pool['slots']),
        variants={name: metrics(rows, pool['slots']) for name, rows in by_arm.items()},
        operators={operator: {name: metrics([r for r in rows if r['operator'] == operator],
            [s for s in pool['slots'] if s['operator'] == operator])
            for name, rows in by_arm.items()} for operator in OPERATORS})
    if summary['variants']['A0'] != summary['variants']['A1']:
        raise ValueError('A0/A1 verification semantics diverged on the same fixed vectors')
    return summary


def _observed_display_row(row):
    """Enrich legacy counters without inventing missing measurements or changing the input."""
    row = dict(row)

    def count(key):
        value = row.get(key)
        return value if type(value) is int and value >= 0 else None

    for prefix, numerator, metric in (('bad', 'FN', 'FAR'), ('good', 'FP', 'FRR')):
        total, pending = count(prefix + '_total'), count(prefix + '_not_run')
        row.setdefault(prefix + '_observed', total - pending if total is not None
                       and pending is not None and pending <= total else None)
        observed, planned, num = count(prefix + '_observed'), count('planned_' + prefix), count(numerator)
        row.setdefault('observed_' + metric, num / observed if observed and num is not None
                       and num <= observed else None)
        row.setdefault(prefix + '_observed_coverage', observed / planned if planned
                       and observed is not None and observed <= planned else None)
    return row


def render_tables(summary):
    summary = copy.deepcopy(summary)
    summary['variants'] = {name: _observed_display_row(row) for name, row in summary['variants'].items()}
    summary['operators'] = {operator: {name: _observed_display_row(row) for name, row in arms.items()}
                            for operator, arms in summary['operators'].items()}

    def cell(value):
        return 'N/A' if value is None else f'{value:.6f}' if isinstance(value, float) else str(value)

    def scope(row, prefixes):
        counts = [(row.get(p + '_observed'), row.get('planned_' + p)) for p in prefixes]
        if any(type(v) is not int or v < 0 for pair in counts for v in pair):
            return 'UNKNOWN'
        return 'PARTIAL' if any(observed < planned for observed, planned in counts) else 'FULL'

    note = ('Observed rates describe terminal generated patches only; PARTIAL results do not represent the full '
            'planned population. Coverage = observed / planned (including NOT_APPLICABLE and pool ERROR slots). '
            'ERROR is non-ACCEPT, not a proven detection. N/A means an unknown or zero denominator.')
    columns = [('Planned BAD', 'planned_bad'), ('Planned GOOD', 'planned_good'),
        ('Generated BAD', 'bad_total'), ('Generated GOOD', 'good_total'),
        ('Observed BAD', 'bad_observed'), ('Observed GOOD', 'good_observed'),
        ('TP', 'TP'), ('FP', 'FP'), ('FN', 'FN'), ('TN', 'TN'), ('FAR', 'FAR'), ('FRR', 'FRR'),
        ('Observed FAR', 'observed_FAR'), ('Observed FRR', 'observed_FRR'),
        ('BAD coverage', 'bad_observed_coverage'), ('GOOD coverage', 'good_observed_coverage'),
        ('BAD NOT_APPLICABLE', 'bad_not_applicable'), ('GOOD NOT_APPLICABLE', 'good_not_applicable'),
        ('BAD ERROR', 'bad_errors'), ('GOOD ERROR', 'good_errors'),
        ('BAD FAIL rejection', 'bad_check_failures'), ('GOOD FAIL rejection', 'good_check_failures'),
        ('BAD pending', 'bad_not_run'), ('GOOD pending', 'good_not_run'),
        ('BAD pool ERROR', 'bad_pool_errors'), ('GOOD pool ERROR', 'good_pool_errors')]
    lines = ['# V1 — Fixed patch verification (BAD = positive)', '',
        f"Expected slots: {summary['expected_slots']}; generated patches: {summary['generated_patches']}; execution complete: {summary['complete']}.", '',
        note, '', '| Arm | ' + ' | '.join(label for label, _ in columns) + ' | Observation scope |',
        '|---|' + '---:|' * len(columns) + '---|']
    for name, row in sorted(summary['variants'].items()):
        lines.append('| ' + name + ' | ' + ' | '.join(cell(row.get(key)) for _, key in columns)
                     + ' | ' + scope(row, ('bad', 'good')) + ' |')
    v2 = ['# V2 — Mutant non-ACCEPT by operator; ERROR is not a proven detection', '',
        note, '',
        '| Operator | Arm | Planned | Generated | Observed BAD | BAD coverage | NOT_APPLICABLE | Pool ERROR | FAIL rejection | ERROR/incomplete | Pending | Non-ACCEPT rate | Observed non-ACCEPT rate | Observation scope |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for operator, arms in sorted(summary['operators'].items()):
        for name, row in sorted(arms.items()):
            rate = None if row['FAR'] is None else 1 - row['FAR']
            observed_rate = None if row['observed_FAR'] is None else 1 - row['observed_FAR']
            keys = ('planned_bad', 'bad_total', 'bad_observed', 'bad_observed_coverage',
                    'bad_not_applicable', 'bad_pool_errors', 'bad_check_failures', 'bad_errors', 'bad_not_run')
            v2.append('| ' + ' | '.join([operator, name, *(cell(row.get(k)) for k in keys),
                cell(rate), cell(observed_rate), scope(row, ('bad',))]) + ' |')
    return {'V1.md': '\n'.join(lines) + '\n', 'V2.md': '\n'.join(v2) + '\n',
        'verification_pool_counts.json': json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'}
