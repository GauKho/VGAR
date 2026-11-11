"""Real A3 policy over source-bound API/structural checks, with controlled tool I/O."""
import json
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair import verification as verify
from vgar.repair import verification_checks as checks
from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant, policy_hash
from vgar.repair.static_diagnostics import DiagnosticReport
from vgar.repair.workspace import inventory

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    (root / 'b.py').write_bytes(b'import a\n')
    task = SimpleNamespace(repo_key='fixture/a3', revision='base',
        allowed_source_paths=('a.py', 'b.py'), failing_selectors=('test_fix',), fallback_scope=('tests',))
    private = tmp_path / 'private'
    private.mkdir()
    lease = SimpleNamespace(path=root, private=private, before=inventory(root), assert_original=lambda: None)
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': ['test_fix']})
    monkeypatch.setattr(verify, 'run_tests', lambda *a: {
        'status': 'FAIL', 'outcomes': {'test_fix': 'FAIL'}, 'durations_ms': {}})

    def static(*args, **kwargs):
        return dict(config_hashes={}, binding={'scope': list(task.allowed_source_paths)},
            source_snapshot={p: (root / p).read_text(encoding='utf-8') for p in task.allowed_source_paths},
            **{n: dict(status='PASS', report=DiagnosticReport(tool=n, tool_version='fixture',
                execution_status='COMPLETE').model_dump(mode='json')) for n in ('syntax', 'mypy', 'ruff')})

    monkeypatch.setattr(verify, 'run_static_checks', static)
    return task, lease, tmp_path / 'artifacts'


def variant(name='A3'):
    return load_variant(ROOT / 'configs/m2/variants' / ('A3.json' if name == 'A3' else f'w10/{name}.json'))


def complete(case, baseline, policy):
    task, lease, artifacts = case
    partial = dict(status='TESTED', tests={'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}},
        collection={'status': 'PASS'}, related_collection={'status': 'NOT_RUN'})
    return verify.complete_verification(partial, task, lease, SimpleNamespace(changed_files=['a.py']),
        baseline, None, RepairPolicy(), variant=policy, artifact_root=artifacts)


@pytest.mark.parametrize(('candidate', 'want', 'api_status', 'reason'), [
    (b'def public(value):\n    return value + 1\n', 'PASS', 'PASS', None),
    (b'def public(value, required):\n    return value\n', 'FAIL', 'FAIL', 'API_BREAK'),
    (b'@framework\ndef public(value):\n    return value\n', 'ERROR', 'NOT_RUN',
     'VERIFICATION_INCOMPLETE'),
])
def test_a3_patch_scope_ignores_only_unaffected_unknowns(case, candidate, want, api_status, reason):
    task, lease, artifacts = case
    unrelated = b'class Other(ExternalBase): pass\nfrom external import exposed\n'
    (lease.path / 'a.py').write_bytes(unrelated + b'def public(value):\n    return value\n')
    policy = variant()
    baseline = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy,
                                       artifact_root=artifacts)
    assert baseline['status'] == 'PASS'
    (lease.path / 'a.py').write_bytes(unrelated + candidate)
    result = complete(case, baseline, policy)
    assert result['status'] == want
    assert result['compatibility']['api']['status'] == api_status
    assert result['variant_policy_hash'] == policy_hash(policy)
    if reason:
        assert reason in result['reasons']
    else:
        assert result['reasons'] == []
    dto = result['compatibility']['api']
    details = json.loads((artifacts / dto['details_ref']).read_bytes())['details']
    assert details['analysis_scope']['selected'] == {'a.py': ['public']}
    assert {item['symbol'] for item in details['analysis_scope']['excluded_diagnostics']} == {
        'Other', 'exposed'}


@pytest.mark.parametrize('source,want,api,structure,reason', [
    (b'def public(value):\n    return value + 1\n', 'PASS', 'PASS', 'PASS', None),
    (b'def public(value, required):\n    return value\n', 'FAIL', 'FAIL', 'PASS', 'API_BREAK'),
    (b'import b as _b\ndef public(value):\n    return value\n', 'FAIL', 'PASS', 'FAIL', 'STRUCTURAL_VIOLATION'),
    (b'import b as _b\ndef public(value, required):\n    return value\n', 'FAIL', 'FAIL', 'FAIL', 'API_BREAK'),
    (b'__all__ = expose()\ndef public(value):\n    return value\n', 'ERROR', 'NOT_RUN', 'PASS', 'VERIFICATION_INCOMPLETE'),
    (b'def public(:\n', 'ERROR', 'ERROR', 'ERROR', 'VERIFICATION_INCOMPLETE'),
])
def test_a3_applies_real_source_checks_and_publishes_details(case, source, want, api, structure, reason):
    task, lease, artifacts = case
    policy = variant()
    baseline = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy, artifact_root=artifacts)
    assert baseline['status'] == 'PASS'
    (lease.path / 'a.py').write_bytes(source)
    result = complete(case, baseline, policy)
    assert result['status'] == want
    assert result['compatibility']['api']['status'] == api
    assert result['compatibility']['structural']['status'] == structure
    assert result['variant_policy_hash'] == policy_hash(policy)
    assert result['variant_id'] == 'A3'
    assert (reason in result['reasons']) if reason else result['reasons'] == []
    for name in ('api', 'structural'):
        dto = result['compatibility'][name]
        path = artifacts / dto['details_ref']
        detail = json.loads(path.read_bytes())
        assert detail['status'] == dto['status']
        assert detail['reasons'] == dto['reasons']
        assert checks.digest(path.read_bytes()) == result['compatibility_hashes'][name]


@pytest.mark.parametrize('api,structural', list(product(['PASS', 'FAIL', 'ERROR', 'NOT_RUN'], repeat=2)))
def test_a3_all_check_status_combinations_use_required_gate(case, monkeypatch, api, structural):
    task, lease, artifacts = case
    policy = variant()
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy, artifact_root=artifacts)
    # Only control checker availability/outcomes; policy and complete_verification remain real.
    monkeypatch.setattr(checks, 'run_compatibility_checks', lambda *a, **kw: {
        'api': {'status': api}, 'structural': {'status': structural}, 'hashes': {}})
    result = complete(case, before, policy)
    states = {api, structural}
    want = 'ERROR' if states & {'ERROR', 'NOT_RUN'} else 'FAIL' if 'FAIL' in states else 'PASS'
    assert result['status'] == want
    if want == 'ERROR':
        assert 'VERIFICATION_INCOMPLETE' in result['reasons']
    if api == 'FAIL':
        assert 'API_BREAK' in result['reasons']
    if structural == 'FAIL':
        assert 'STRUCTURAL_VIOLATION' in result['reasons']


def test_a3_malformed_structural_config_cannot_accept(case, monkeypatch):
    task, lease, artifacts = case
    config = artifacts / 'config/fixture/a3.yaml'
    config.parent.mkdir(parents=True)
    config.write_text('!!python/object:unsafe {}', encoding='utf-8')
    monkeypatch.setattr(checks, 'STRUCTURAL_CONFIG_DIR', artifacts / 'config')
    policy = variant()
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy, artifact_root=artifacts)
    result = complete(case, before, policy)
    assert result['status'] == 'ERROR'
    assert result['compatibility']['structural']['status'] == 'ERROR'
    assert 'VERIFICATION_INCOMPLETE' in result['reasons']


def test_a3_cannot_reuse_a2_policy_bound_baseline(case):
    task, lease, artifacts = case
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=variant('A2'), artifact_root=artifacts)
    result = complete(case, before, variant())
    assert result['status'] == 'ERROR'
    assert result['reasons'] == ['VARIANT_POLICY_CHANGED']


@pytest.mark.parametrize('name', ['A0', 'A1', 'A2', 'A3'])
def test_direct_verification_keeps_checks_after_collection_failure(case, monkeypatch, name):
    from test_collection_failure import collection_evidence
    task, lease, artifacts = case
    policy = variant(name)
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy, artifact_root=artifacts)
    assert before['status'] == 'PASS'
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: collection_evidence())
    monkeypatch.setattr(verify, 'run_tests', lambda *a: collection_evidence())
    applied = SimpleNamespace(status='PASS', changed_files=['a.py'])
    selection = {'selected': ('tests',), 'related_selectors': ()}
    result = verify.verify_patch(task, lease, applied, before, selection, None, RepairPolicy(),
                                variant=policy, artifact_root=artifacts)
    assert result['status'] == 'FAIL'
    assert 'TEST_COLLECTION_FAILED' in result['reasons']
    assert all(name in result['static'] for name in ('syntax', 'mypy', 'ruff'))
    assert set(result['compatibility']) == {'api', 'structural'}


def test_baseline_collection_failure_is_not_qualified(case, monkeypatch):
    from test_collection_failure import collection_evidence
    task, lease, artifacts = case
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: collection_evidence())
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=variant(), artifact_root=artifacts)
    assert (before['status'], before['reason']) == ('ERROR', 'BASELINE_NOT_QUALIFIED')


@pytest.mark.parametrize('name', ['A0', 'A3'])
@pytest.mark.parametrize('missing', ['required', 'regression'])
def test_collection_failure_cannot_override_incomplete_test_run(case, monkeypatch, name, missing):
    from test_collection_failure import collection_evidence
    task, lease, artifacts = case
    policy = variant(name)
    before = verify.capture_baseline(task, lease, None, RepairPolicy(), variant=policy, artifact_root=artifacts)
    outcomes = {'test_fix': 'PASS'}
    if missing == 'required':
        outcomes = {'test_other': 'PASS'}
    else:
        before['tests']['outcomes']['test_ok'] = 'PASS'
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: collection_evidence())
    monkeypatch.setattr(verify, 'run_tests', lambda *a: {'status': 'PASS', 'outcomes': outcomes})
    result = verify.verify_patch(task, lease, SimpleNamespace(status='PASS', changed_files=['a.py']),
        before, {'selected': ('tests',), 'related_selectors': ()}, None, RepairPolicy(),
        variant=policy, artifact_root=artifacts)
    assert result['status'] == 'ERROR'
    assert 'VERIFICATION_INCOMPLETE' in result['reasons']
    assert 'static' in result and 'compatibility' in result
