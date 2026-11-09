"""V10/V11 and source-bound supplemental checks through the shared verifier."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair import verification as verify
from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant, policy_hash
from vgar.repair.workspace import inventory

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def checks():
    assert importlib.util.find_spec('vgar.repair.verification_checks'), 'W11-3 collector missing'
    return importlib.import_module('vgar.repair.verification_checks')


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    (root / 'b.py').write_bytes(b'import a\n')
    (root / 'tests').mkdir()
    (root / 'tests/test_protected.py').write_bytes(b'# protected\n')
    task = SimpleNamespace(repo_key='fixture/evidence', revision='base',
        allowed_source_paths=('a.py', 'b.py'), failing_selectors=('test_fix',), fallback_scope=('tests',))
    lease = SimpleNamespace(path=root, private=tmp_path / 'private', before=inventory(root),
                            assert_original=lambda: None)
    lease.private.mkdir()
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': ['test_fix']})
    monkeypatch.setattr(verify, 'run_tests', lambda *a: {
        'status': 'FAIL', 'outcomes': {'test_fix': 'FAIL'}, 'durations_ms': {}})
    monkeypatch.setattr(verify, 'run_static_checks', lambda *a, **kw: {
        **{n: {'status': 'PASS'} for n in ('syntax', 'mypy', 'ruff')}, 'config_hashes': {}})
    return task, lease, tmp_path / 'artifacts'


def test_baseline_is_persisted_before_apply_and_checks_have_real_details(checks, case):
    task, lease, artifacts = case
    original = inventory(lease.path)
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    assert inventory(lease.path) == original
    json.dumps(baseline)  # usable by a fresh persisted session
    (lease.path / 'a.py').write_bytes(b'import b as _b\ndef public(value, required):\n    return value\n')
    applied = SimpleNamespace(changed_files=['a.py'])
    result = checks.run_compatibility_checks(task, lease, applied, baseline, artifacts)
    assert result['api']['status'] == result['structural']['status'] == 'FAIL'
    assert 'API_SIGNATURE_INCOMPATIBLE' in result['api']['reasons']
    assert 'NEW_IMPORT_CYCLE' in result['structural']['reasons']
    for name in ('api', 'structural'):
        dto = result[name]
        detail = json.loads((artifacts / dto['details_ref']).read_bytes())
        assert detail['status'] == dto['status']
        assert detail['details']['source_hashes']['baseline']
        assert detail['details']['source_hashes']['candidate']
    assert 'tests/test_protected.py' not in json.loads(
        (artifacts / baseline['details_ref']).read_bytes())['sources']


@pytest.mark.parametrize('name', ['api', 'structural'])
@pytest.mark.parametrize('state,expected', [('NOT_RUN', 'ERROR'), ('ERROR', 'ERROR'), ('FAIL', 'FAIL'), ('PASS', 'PASS')])
def test_not_run_never_counts_as_pass_in_A3(checks, name, state, expected):
    # Exercise future required-check semantics without enabling A3 policy/config.
    records = {n: {'status': 'PASS', 'reasons': [], 'details_ref': None} for n in ('api', 'structural')}
    records[name]['status'] = state
    status, reasons = checks.assess_compatibility(records, {'api', 'structural'}, 'PASS', [])
    assert status == expected
    assert reasons == ([] if state == 'PASS' else [
        ('API_BREAK' if name == 'api' else 'STRUCTURAL_VIOLATION') if state == 'FAIL'
        else 'VERIFICATION_INCOMPLETE'])


def test_optional_fail_error_not_run_do_not_change_old_verdict(checks):
    for status in ('FAIL', 'ERROR', 'NOT_RUN'):
        records = {n: {'status': status} for n in ('api', 'structural')}
        assert checks.assess_compatibility(records, set(), 'PASS', []) == ('PASS', [])


def test_collector_scopes_api_to_changed_symbols_and_publishes_exclusions(checks, case):
    task, lease, artifacts = case
    old = b'from external import exposed\ndef public(value):\n    return value\n'
    (lease.path / 'a.py').write_bytes(old)
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    (lease.path / 'a.py').write_bytes(old.replace(b'return value', b'return value + 1'))
    result = checks.run_compatibility_checks(task, lease, SimpleNamespace(changed_files=['a.py']),
                                            baseline, artifacts)
    assert result['api']['status'] == 'PASS'
    sidecar = json.loads((artifacts / result['api']['details_ref']).read_bytes())
    assert sidecar['details']['analysis_scope']['selected'] == {'a.py': ['public']}
    excluded = sidecar['details']['analysis_scope']['excluded_diagnostics']
    assert {item['symbol'] for item in excluded} == {'exposed'}


def test_shared_capture_and_completion_publish_real_supplemental_results(case):
    task, lease, artifacts = case
    policy = RepairPolicy()
    baseline = verify.capture_baseline(task, lease, None, policy, artifact_root=artifacts)
    assert baseline['status'] == 'PASS'
    assert 'compatibility_snapshot' in baseline
    (lease.path / 'a.py').write_bytes(b'def public(value, required):\n    return value\n')
    partial = dict(status='TESTED', tests={'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}},
                   collection={'status': 'PASS'}, related_collection={'status': 'NOT_RUN'})
    result = verify.complete_verification(partial, task, lease,
        SimpleNamespace(changed_files=['a.py']), baseline, None, policy, artifact_root=artifacts)
    assert result['status'] == 'PASS'  # supplemental failure cannot reject legacy policy
    assert result['compatibility']['api']['status'] == 'FAIL'
    assert result['compatibility']['structural']['status'] == 'PASS'
    assert result['compatibility']['structural']['details_ref']


@pytest.mark.parametrize('arm', ['A0', 'A1', 'A2'])
def test_A0_A2_record_break_without_rejection(case, monkeypatch, arm):
    from vgar.repair.static_diagnostics import DiagnosticReport
    task, lease, artifacts = case
    def static(*args, **kwargs):
        return dict(config_hashes={}, binding={'scope': list(task.allowed_source_paths)},
            source_snapshot={p: (lease.path / p).read_text(encoding='utf-8') for p in task.allowed_source_paths},
            **{n: dict(status='PASS', report=DiagnosticReport(tool=n, tool_version='fixture',
                execution_status='COMPLETE').model_dump(mode='json')) for n in ('syntax', 'mypy', 'ruff')})
    monkeypatch.setattr(verify, 'run_static_checks', static)
    policy = RepairPolicy()
    variant = load_variant(ROOT / 'configs/m2/variants/w10' / (arm + '.json'))
    baseline = verify.capture_baseline(task, lease, None, policy, variant=variant, artifact_root=artifacts)
    (lease.path / 'a.py').write_bytes(b'import b as _b\ndef public(value, required):\n    return value\n')
    partial = dict(status='TESTED', tests={'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}},
                   collection={'status': 'PASS'}, related_collection={'status': 'NOT_RUN'})
    result = verify.complete_verification(partial, task, lease, SimpleNamespace(changed_files=['a.py']),
        baseline, None, policy, variant=variant, artifact_root=artifacts)
    assert result['status'] == 'PASS'
    assert result['reasons'] == []
    assert result['compatibility']['api']['status'] == 'FAIL'
    assert result['compatibility']['structural']['status'] == 'FAIL'
    assert result['variant_policy_hash'] == policy_hash(variant)


def test_compatibility_integrity_error_rejects_legacy_policy(case):
    task, lease, artifacts = case
    baseline = verify.capture_baseline(task, lease, None, RepairPolicy(), artifact_root=artifacts)
    (artifacts / baseline['compatibility_snapshot']['details_ref']).write_bytes(b'{}')
    partial = dict(status='TESTED', tests={'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}},
                   collection={'status': 'PASS'}, related_collection={'status': 'NOT_RUN'})
    result = verify.complete_verification(partial, task, lease, SimpleNamespace(changed_files=[]),
        baseline, None, RepairPolicy(), artifact_root=artifacts)
    assert result['status'] == 'ERROR'
    assert result['reason'] == 'CHECK_INTEGRITY_ERROR'
    assert 'compatibility' not in result


def test_source_mutation_during_builder_is_not_a_checker_failure(checks, case, monkeypatch):
    task, lease, artifacts = case
    original = checks._ScopedBuilder.build
    def corrupt(builder, root):
        graph = original(builder, root)
        (root / 'a.py').write_bytes(b'# changed during analysis\n')
        return graph
    monkeypatch.setattr(checks._ScopedBuilder, 'build', corrupt)
    with pytest.raises(checks.CheckIntegrityError, match='Source changed'):
        checks.capture_checks_baseline(task, lease, artifacts)


def test_malformed_config_remains_supplemental_error(checks, case, monkeypatch):
    task, lease, artifacts = case
    config_dir = artifacts / 'config'
    path = config_dir / 'fixture/evidence.yaml'
    path.parent.mkdir(parents=True)
    path.write_text('!!python/object:unsafe {}', encoding='utf-8')
    monkeypatch.setattr(checks, 'STRUCTURAL_CONFIG_DIR', config_dir)
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    result = checks.run_compatibility_checks(task, lease, SimpleNamespace(changed_files=['a.py']), baseline, artifacts)
    assert result['structural']['status'] == 'ERROR'
    assert result['structural']['reasons'] == ['STRUCTURAL_CONFIG_ERROR']


def test_baseline_tests_cannot_mutate_frozen_source(checks, case, monkeypatch):
    task, lease, artifacts = case
    def mutate(*args):
        (lease.path / 'a.py').write_bytes(b'def public(value, required):\n    return value\n')
        return {'status': 'FAIL', 'outcomes': {'test_fix': 'FAIL'}, 'durations_ms': {}}
    monkeypatch.setattr(verify, 'run_tests', mutate)
    with pytest.raises(checks.CheckIntegrityError):
        verify.capture_baseline(task, lease, None, RepairPolicy(), artifact_root=artifacts)


def test_selected_tests_cannot_replace_an_already_changed_candidate(case, monkeypatch):
    task, lease, artifacts = case
    policy = RepairPolicy()
    before = (lease.path / 'a.py').read_bytes()
    baseline = verify.capture_baseline(task, lease, None, policy, artifact_root=artifacts)
    (lease.path / 'a.py').write_bytes(b'def public(value, required):\n    return value\n')
    from vgar.repair.verification_checks import inventory_hash
    lease.applied_inventory_hash = inventory_hash(inventory(lease.path))  # pinned by real apply_patch
    def mutate(*args):
        (lease.path / 'a.py').write_bytes(before)
        return {'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}, 'durations_ms': {}}
    monkeypatch.setattr(verify, 'run_tests', mutate)
    applied = SimpleNamespace(status='PASS', changed_files=['a.py'])
    partial = verify.run_patch_tests(task, lease, applied, baseline,
        {'related_selectors': (), 'selected': ('tests',)}, None, policy)
    result = verify.complete_verification(partial, task, lease, applied, baseline, None, policy, artifact_root=artifacts)
    assert result['status'] == 'ERROR'
    assert result.get('reason') == 'CHECK_INTEGRITY_ERROR'
    assert 'compatibility' not in result


@pytest.mark.parametrize('tamper', ['snapshot', 'config', 'profile', 'protected_source'])
def test_integrity_failures_are_not_optional(checks, case, monkeypatch, tamper):
    task, lease, artifacts = case
    config_dir = artifacts / 'config'
    config_dir.mkdir(parents=True)
    monkeypatch.setattr(checks, 'STRUCTURAL_CONFIG_DIR', config_dir)
    config = config_dir / 'fixture/evidence.yaml'
    config.parent.mkdir()
    config.write_text('repo_key: fixture/evidence\n', encoding='utf-8')
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    if tamper == 'snapshot':
        (artifacts / baseline['details_ref']).write_bytes(b'{}')
    elif tamper == 'config':
        config.write_text('repo_key: changed\n', encoding='utf-8')
    elif tamper == 'profile':
        monkeypatch.setattr(checks, 'RESOLVER_PROFILE', 'drift')
    else:
        (lease.path / 'tests/test_protected.py').write_bytes(b'changed\n')
    with pytest.raises(checks.CheckIntegrityError):
        checks.run_compatibility_checks(task, lease, SimpleNamespace(changed_files=[]), baseline, artifacts)


def test_global_deadline_propagates(checks, case):
    task, lease, artifacts = case
    def expired():
        raise TimeoutError('GLOBAL_DEADLINE_EXCEEDED')
    with pytest.raises(TimeoutError):
        checks.capture_checks_baseline(task, lease, artifacts, guard=expired)
    assert not artifacts.exists()


def test_unknown_is_evidence_not_pass_and_empty_changes_are_measured(checks, case):
    task, lease, artifacts = case
    (lease.path / 'a.py').write_bytes(b'__all__ = build_exports()\n')
    lease.before = inventory(lease.path)
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    result = checks.run_compatibility_checks(task, lease, SimpleNamespace(changed_files=['a.py']), baseline, artifacts)
    assert result['api']['status'] == 'NOT_RUN'
    assert result['structural']['status'] == 'PASS'


def test_unrelated_dynamic_export_does_not_hide_analyzed_change(checks, case):
    task, lease, artifacts = case
    (lease.path / 'b.py').write_bytes(b'__all__ = build_exports()\n')
    lease.before = inventory(lease.path)
    baseline = checks.capture_checks_baseline(task, lease, artifacts)
    (lease.path / 'a.py').write_bytes(b'def public(value):\n    return 42\n')
    result = checks.run_compatibility_checks(task, lease, SimpleNamespace(changed_files=['a.py']), baseline, artifacts)
    assert result['api']['status'] == 'PASS'


def test_projection_checks_sidecar_hash_and_aborted_details_exist(checks, tmp_path):
    projected = checks.project_compatibility({}, tmp_path)
    for name in ('api_check', 'structural_check'):
        dto = projected[name]
        assert dto.status == 'NOT_RUN'
        assert dto.reasons == ['VERIFICATION_NOT_COMPLETED']
        assert (tmp_path / dto.details_ref).is_file()
    verification = {'compatibility': {n: projected[n + '_check'].model_dump() for n in ('api', 'structural')},
                    'compatibility_hashes': {}}
    with pytest.raises(checks.CheckIntegrityError):
        checks.project_compatibility(verification, tmp_path)


@pytest.mark.parametrize('folder,expected', [('', [
    'bca5f7b7f208f217ce72373305e8325922ed6a43ebe378305920bc50ebfacbbf',
    '2b29abdb298d364685edf0236556cb648eb61d7cb5160d2380783a3a894bef00',
    '2f7c85d1124c77b5f5c67160e8acc644e64cf638d9bdcc10bbab4eb768be55ca']), ('w10', [
    '30ed3355d3176c9deeb5d9d8dd0196ef7a35f90e560fed6b753a298fb6812942',
    'f4dae9841f6cd45cc1b3a83a09eaff9a7ccf7f3bfb33739b9de8f8dfdd6bee19',
    '2c2b8e4745679b13543ac1fa44ba8ece7445beb45221d27a2bbf30ba2f0c3b93'])])
def test_policy_hash_A0_A2_unchanged(folder, expected):
    for name, sha in zip(('A0', 'A1', 'A2'), expected):
        policy = load_variant(ROOT / 'configs/m2/variants' / folder / (name + '.json'))
        assert policy_hash(policy) == 'sha256:' + sha
        assert set(policy.recorded_checks) == {'tests', 'syntax', 'mypy', 'ruff'}
        assert not {'api', 'structural'} & set(policy.required_checks)


@pytest.mark.parametrize('folder,arm,hashes', [
    ('', 'bm25', ['959008d2592357341bfbef587861d870b94c5d46384211df78d737f68b6f428a',
        '2d1fb8f56648306f9374aa450af0824eb631e6f5180ec9ce54190e90daa4d0f7',
        'ab1443e50d21ca81b8bb66ae6e4f4d3bb54dcd425e53230b1be2d99835055cce']),
    ('', 'graph', ['460af6cd5e962587b52dfc58c8171b1c1ba0d414fa8f9b152c32f363c2ebd408',
        '9a9e38442739a1bd7fd44c7d9488b486e93fad8fc14f2ec6456065411175f278',
        '5fff1fb8e0e2804a1550051218761fd2c58efdf3627a60b74119bf7cc7da8bc5']),
    ('w10', 'bm25', ['7d24081d7000eb846ee32633554b38b11093a78a8f305b0ea7d7d7674d2b645e',
        '0b9d83436728468b11645f40146f3f9eac8a0d9b616fd527c31ec98aad42637e',
        'a7846861affc88c21b1b03116d5e10fe08f4bad79d45f7592ea6195dd0304d5e']),
    ('w10', 'graph', ['3c5a55cac1be05da5a4a677c62e23f96e163eac882d261fbcfd533d58376c2e9',
        'c724417ace497a3011c8ae2c6fbe016bfa9b742897ad78bd9ad6b9f5817dcc07',
        '18a1e37f27526717334fab4aac7a468bbe1054ee4af1a63de7e584438aa7cb1f']),
])
def test_bound_arm_hashes_unchanged(folder, arm, hashes):
    for name, sha in zip(('A0', 'A1', 'A2'), hashes):
        policy = load_variant(ROOT / 'configs/m2/variants' / folder / (name + '.json'))
        assert policy_hash(policy.model_copy(update={'arm': arm})) == 'sha256:' + sha
