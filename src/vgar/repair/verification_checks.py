"""Source-bound supplemental API/structural evidence; no target code execution.

The static graph covers the task's frozen allowed production paths, not tests or
an inferred repository architecture. Unknown analysis is never a measured PASS.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from vgar.contracts.evidence import AnalysisCheckResult
from vgar.graph.builder import PythonGraphBuilder, RESOLVER_PROFILE
from vgar.repair.api_check import check_api
from vgar.repair.check_result import CheckAnalysis
from vgar.repair.config import CONFIG_DIR
from vgar.repair.contracts import safe_path
from vgar.repair.evidence import atomic_json, digest
from vgar.repair.structural_check import check_structure
from vgar.repair.structural_config import load_structural_config
from vgar.repair.workspace import inventory

STRUCTURAL_CONFIG_DIR = CONFIG_DIR / 'structural'


class CheckIntegrityError(ValueError):
    """Binding/source drift must fail the run, including recorded-only policies."""


class _NoTrace:
    def emit(self, *args, **kwargs):
        pass


class _ScopedBuilder(PythonGraphBuilder):
    def __init__(self, paths, **kwargs):
        super().__init__(trace=_NoTrace(), **kwargs)
        self.paths = paths

    def _discover_python_files(self, root):
        return [root / p for p in self.paths]


def _guard(guard):
    if guard is not None:
        guard()


def inventory_hash(value):
    return digest(json.dumps(value, sort_keys=True))


def _root(lease, artifact_root):
    root = Path(artifact_root) if artifact_root is not None else lease.private / 'verification'
    if root.resolve().is_relative_to(lease.path.resolve()):
        raise CheckIntegrityError('Evidence must be outside target source')
    return root


def _artifact(root, ref):
    safe_path(ref)
    path = root / ref
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise CheckIntegrityError('Evidence reference escapes artifact root')
    return path


def _config(repo_key):
    if not repo_key:
        return None, None, None, 'SOURCE_IDENTITY_MISSING'
    path = STRUCTURAL_CONFIG_DIR / safe_path(repo_key + '.yaml')
    before = digest(path.read_bytes()) if path.is_file() else None
    try:
        value, error = load_structural_config(path), None
    except (ValueError, OSError) as exc:
        value, error = None, str(exc)
    after = digest(path.read_bytes()) if path.is_file() else None
    if before != after:
        raise CheckIntegrityError('Structural configuration changed during read')
    return str(path), before, value, error


def _snapshot(task, lease, guard):
    _guard(guard)
    lease.assert_original()
    before = inventory(lease.path)
    paths = tuple(sorted(safe_path(p) for p in task.allowed_source_paths if p.endswith('.py')))
    sources = {}
    for path in paths:
        _guard(guard)
        if path not in before:  # deleted files are absent, never reconstructed
            continue
        actual = lease.path / path
        if actual.is_symlink() or not actual.resolve().is_relative_to(lease.path.resolve()):
            raise CheckIntegrityError('Source link/escape in analysis scope')
        sources[path] = actual.read_bytes()
        if digest(sources[path]) != before[path]:
            raise CheckIntegrityError('Source changed while snapshotting')
    graph, error = None, None
    if getattr(task, 'repo_key', None) and getattr(task, 'revision', None):
        try:
            graph = _ScopedBuilder(tuple(sources), repo_key=task.repo_key,
                repository_revision=task.revision).build(lease.path)
        except (ValueError, OSError, SyntaxError, UnicodeError) as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
    else:
        error = {'message': 'SOURCE_IDENTITY_MISSING'}
    _guard(guard)
    lease.assert_original()
    if before != inventory(lease.path):
        raise CheckIntegrityError('Source changed during graph analysis')
    return sources, graph, error, before


def capture_checks_baseline(task, lease, artifact_root=None, *, guard=None):
    root = _root(lease, artifact_root)
    sources, graph, error, bound_inventory = _snapshot(task, lease, guard)
    config_path, config_hash, config, config_error = _config(getattr(task, 'repo_key', None))
    value = dict(sources={p: base64.b64encode(raw).decode('ascii') for p, raw in sources.items()},
        graph=graph, graph_error=error, inventory=bound_inventory,
        repo_key=getattr(task, 'repo_key', None), revision=getattr(task, 'revision', None),
        scope=list(task.allowed_source_paths), resolver_profile=RESOLVER_PROFILE,
        module_roots=['src'], config_path=config_path, config_hash=config_hash,
        config=config, config_error=config_error)
    _guard(guard)
    ref = 'checks/baseline.json'
    path = _artifact(root, ref)
    atomic_json(path, value)
    return dict(details_ref=ref, sha256=digest(path.read_bytes()), artifact_root=str(root.resolve()))


def _load_baseline(task, lease, baseline, root):
    if str(root.resolve()) != baseline['artifact_root']:
        raise CheckIntegrityError('Analysis artifact root changed')
    path = _artifact(root, baseline['details_ref'])
    raw = path.read_bytes()
    if digest(raw) != baseline['sha256']:
        raise CheckIntegrityError('Baseline analysis snapshot hash changed')
    old = json.loads(raw)
    if (old['scope'] != list(task.allowed_source_paths) or old['resolver_profile'] != RESOLVER_PROFILE
            or old['repo_key'] != getattr(task, 'repo_key', None)
            or old['revision'] != getattr(task, 'revision', None) or old['module_roots'] != ['src']):
        raise CheckIntegrityError('Analysis source/profile binding changed')
    config_path, config_hash, _, _ = _config(getattr(task, 'repo_key', None))
    if config_path != old['config_path'] or config_hash != old['config_hash']:
        raise CheckIntegrityError('Structural configuration binding changed')
    lease.assert_original()
    return old


def assert_checks_baseline(task, lease, baseline, artifact_root=None, *, guard=None):
    """No target execution may alter the frozen preapply bytes."""
    _guard(guard)
    old = _load_baseline(task, lease, baseline, _root(lease, artifact_root))
    if old['inventory'] != inventory(lease.path):
        raise CheckIntegrityError('Frozen baseline source changed before apply')
    _guard(guard)


def _publish(root, name, analysis):
    ref = f'checks/{name}.json'
    path = _artifact(root, ref)
    atomic_json(path, dict(status=analysis.status, reasons=list(analysis.reasons), details=analysis.details))
    return AnalysisCheckResult(status=analysis.status, reasons=list(analysis.reasons), details_ref=ref).model_dump(), digest(path.read_bytes())


def run_compatibility_checks(task, lease, applied, baseline, artifact_root=None, *, guard=None,
                             expected_candidate_hash=None):
    root = _root(lease, artifact_root)
    _guard(guard)
    old = _load_baseline(task, lease, baseline, root)
    sources, graph, graph_error, after_inventory = _snapshot(task, lease, guard)
    pinned = expected_candidate_hash or getattr(lease, 'applied_inventory_hash', None)
    if pinned is not None and inventory_hash(after_inventory) != pinned:
        raise CheckIntegrityError('Candidate source differs from pinned applied bytes')
    changed = set(applied.changed_files)
    if not changed <= set(task.allowed_source_paths):
        raise CheckIntegrityError('Applied paths outside frozen source scope')
    unexpected = [p for p in set(old['inventory']) | set(after_inventory)
                  if old['inventory'].get(p) != after_inventory.get(p) and p not in changed]
    if unexpected:
        raise CheckIntegrityError('Protected source changed: ' + ', '.join(sorted(unexpected)))
    before_sources = {p: base64.b64decode(raw, validate=True) for p, raw in old['sources'].items()}
    api = check_api({p: raw for p, raw in before_sources.items() if p in changed},
                    {p: raw for p, raw in sources.items() if p in changed}, changed_only=True)
    _guard(guard)
    hashes = dict(baseline={p: digest(raw) for p, raw in before_sources.items()},
                  candidate={p: digest(raw) for p, raw in sources.items()})
    binding = dict(scope_paths=list(task.allowed_source_paths), api_paths=sorted(changed),
        resolver_profile=RESOLVER_PROFILE, module_roots=['src'], config_hash=old['config_hash'],
        baseline_inventory_hash=inventory_hash(old['inventory']),
        candidate_inventory_hash=inventory_hash(after_inventory), candidate_binding_available=pinned is not None)
    api.details['binding'] = binding.copy()
    if old['config_error']:
        structure = CheckAnalysis('ERROR', ('STRUCTURAL_CONFIG_ERROR',),
            dict(source_hashes=hashes, error=old['config_error']))
    elif old['graph'] is None or graph is None:
        structure = CheckAnalysis('ERROR', ('STRUCTURAL_GRAPH_ERROR',),
            dict(source_hashes=hashes, baseline_error=old['graph_error'], candidate_error=graph_error))
    else:
        structure = check_structure(old['graph'], graph, before_sources=before_sources,
                                    after_sources=sources, repo_config=old['config'], min_confidence=0.60)
    structure.details['binding'] = binding.copy()
    _guard(guard)
    # Detect config/source mutations even when the checker itself returns ERROR.
    _load_baseline(task, lease, baseline, root)
    if inventory(lease.path) != after_inventory:
        raise CheckIntegrityError('Source changed during compatibility checks')
    result, hashes_out = {}, {}
    for name, analysis in (('api', api), ('structural', structure)):
        result[name], hashes_out[name] = _publish(root, name, analysis)
    return dict(result, hashes=hashes_out)


def assess_compatibility(checks, required, status, reasons):
    """Shared required-check semantics, independent of future A3 configuration."""
    reasons = list(reasons)
    for name, code in (('api', 'API_BREAK'), ('structural', 'STRUCTURAL_VIOLATION')):
        if name not in required:
            continue
        state = checks.get(name, {}).get('status', 'NOT_RUN')
        if state in ('NOT_RUN', 'ERROR'):
            status = 'ERROR'
            reasons.append('VERIFICATION_INCOMPLETE')
        elif state == 'FAIL':
            status = 'ERROR' if status == 'ERROR' else 'FAIL'
            reasons.append(code)
        elif state != 'PASS':
            raise ValueError('Invalid compatibility check status')
    return status, list(dict.fromkeys(reasons))


def project_compatibility(verification, artifact_root):
    root = Path(artifact_root)
    checks = verification.get('compatibility')
    projected = {}
    for name in ('api', 'structural'):
        if checks is None:
            dto, _ = _publish(root, name, CheckAnalysis('NOT_RUN', ('VERIFICATION_NOT_COMPLETED',),
                dict(coverage='NONE', reason=verification.get('reason') or verification.get('status')
                     or 'Verification did not complete')))
        else:
            dto = checks[name]
            parsed = AnalysisCheckResult.model_validate(dto)
            if parsed.details_ref is None:
                raise CheckIntegrityError('Computed check lacks details_ref')
            path = _artifact(root, parsed.details_ref)
            raw = path.read_bytes()
            if digest(raw) != verification.get('compatibility_hashes', {}).get(name):
                raise CheckIntegrityError('Check details hash changed')
            detail = json.loads(raw)
            if detail['status'] != parsed.status or detail['reasons'] != parsed.reasons:
                raise CheckIntegrityError('Check DTO differs from details artifact')
        projected[name + '_check'] = AnalysisCheckResult.model_validate(dto)
    return projected
