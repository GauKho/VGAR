"""V15/V16: neutral measurements, exact policy semantics and honest FAR/FRR."""
import copy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant
from vgar.repair.static_diagnostics import DiagnosticReport
from vgar.repair.workspace import inventory

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def api():
    assert importlib.util.find_spec('vgar.evaluation.repair.verifier_eval'), 'verify-once evaluator missing'
    return importlib.import_module('vgar.evaluation.repair.verifier_eval')


def policy(name):
    return load_variant(ROOT / 'configs/m2/variants' / ('A3.json' if name == 'A3' else f'w10/{name}.json'))


def static(state='COMPLETE'):
    return dict(config_hashes={'mypy': 'm', 'ruff': 'r'}, binding={'scope': ['a.py']},
        source_snapshot={'a.py': 'value = 1\n'}, **{name: dict(status='PASS', report=DiagnosticReport(
            tool=name, tool_version='fixture', execution_status=state).model_dump(mode='json'))
            for name in ('syntax', 'mypy', 'ruff')})


def raw_vector(api):
    return api.seal_vector(dict(schema='vgar-verifier-vector-v1', task_id='fixture',
        binding={'source_inventory_hash': 'source', 'scope': ['a.py']},
        integrity={'status': 'PASS', 'reasons': []},
        baseline={'collection': {'status': 'PASS', 'node_ids': ['test_fix']},
            'tests': {'status': 'FAIL', 'outcomes': {'test_fix': 'FAIL'}},
            'required_ids': ['test_fix'], 'static': static()},
        apply={'status': 'PASS', 'changed_files': ['a.py']},
        post={'collection': {'status': 'PASS'},
            'tests': {'status': 'PASS', 'outcomes': {'test_fix': 'PASS'}},
            'static': static(), 'compatibility': {n: {'status': 'PASS'} for n in ('api', 'structural')}}))


@pytest.mark.parametrize('name', ['A0', 'A1', 'A2', 'A3'])
def test_neutral_vector_accepts_and_is_not_rebound_or_mutated(api, name):
    vector = raw_vector(api)
    original = copy.deepcopy(vector)
    result = api.derive_verdict(vector, policy(name))
    assert (result['status'], result['recommendation']) == ('PASS', 'ACCEPT')
    assert result['vector_hash'] == vector['vector_hash']
    assert result['policy_hash'].startswith('sha256:')
    assert vector == original


@pytest.mark.parametrize('state,want,reason', [('FAIL', 'FAIL', 'API_BREAK'),
    ('NOT_RUN', 'ERROR', 'VERIFICATION_INCOMPLETE'), ('ERROR', 'ERROR', 'VERIFICATION_INCOMPLETE')])
def test_api_required_only_for_a3(api, state, want, reason):
    vector = raw_vector(api)
    vector['post']['compatibility']['api']['status'] = state
    vector = api.seal_vector(vector)
    assert api.derive_verdict(vector, policy('A3'))['status'] == want
    assert reason in api.derive_verdict(vector, policy('A3'))['reasons']
    for name in ('A0', 'A1', 'A2'):
        assert api.derive_verdict(vector, policy(name))['recommendation'] == 'ACCEPT'


@pytest.mark.parametrize('outcome', ['SKIP', 'NOT_RUN', 'ERROR'])
def test_skip_mutant_rejected(api, outcome):
    vector = raw_vector(api)
    vector['post']['tests']['outcomes']['test_fix'] = outcome
    vector = api.seal_vector(vector)
    for name in ('A0', 'A1', 'A2', 'A3'):
        result = api.derive_verdict(vector, policy(name))
        assert result['status'] == 'ERROR'
        assert 'VERIFICATION_INCOMPLETE' in result['reasons']


def test_baseline_qualification_is_per_arm_not_a3_bound(api):
    vector = raw_vector(api)
    vector['baseline']['static']['mypy']['report']['execution_status'] = 'ERROR'
    vector['baseline']['static']['mypy']['status'] = 'ERROR'
    vector = api.seal_vector(vector)
    a0 = api.derive_verdict(vector, policy('A0'))
    a2 = api.derive_verdict(vector, policy('A2'))
    assert a0['baseline_qualified'] is True
    assert a2['baseline_qualified'] is False
    assert a2['recommendation'] == 'REJECT'
    assert vector['baseline'].get('variant_policy_hash') is None


@pytest.mark.parametrize('name', ['A0', 'A1', 'A2', 'A3'])
def test_integrity_failure_cannot_be_optional(api, name):
    vector = raw_vector(api)
    vector['integrity'] = {'status': 'ERROR', 'reasons': ['CHECK_INTEGRITY_ERROR']}
    vector = api.seal_vector(vector)
    assert api.derive_verdict(vector, policy(name))['status'] == 'ERROR'


def test_tampered_vector_rejected(api):
    vector = raw_vector(api)
    vector['post']['tests']['status'] = 'FAIL'
    with pytest.raises(ValueError, match='hash'):
        api.derive_verdict(vector, policy('A0'))


def test_structured_static_measurements_have_no_arm_binding(tmp_path):
    from vgar.repair import static_checks
    assert hasattr(static_checks, 'collect_static_measurements'), 'neutral static measurement entrypoint missing'
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_text('value = 1\n', encoding='utf-8')
    lease = SimpleNamespace(path=root, private=tmp_path / 'private')

    class Executor:
        def run(self, argv, cwd, timeout):
            tool = argv[2]
            return dict(complete=True, exit_code=0, status='PASS', stderr='',
                stdout=(tool + ' 1.0') if '--version' in argv else '',
                timed_out=False, output_truncated=False)

    result = static_checks.collect_static_measurements(lease, ('a.py',), RepairPolicy(), Executor())
    assert 'variant_policy_hash' not in result
    assert all('report' in result[name] for name in ('syntax', 'mypy', 'ruff'))


@pytest.fixture
def collector_case(tmp_path, monkeypatch, api):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    private = tmp_path / 'private'
    private.mkdir()
    task = SimpleNamespace(task_id='fixture', repo_key='fixture/neutral', revision='base',
        allowed_source_paths=('a.py',), protected_paths=('tests',),
        failing_selectors=('test_fix',), fallback_scope=('tests',))
    lease = SimpleNamespace(path=root, private=private, before=inventory(root), assert_original=lambda: None)
    calls = []
    monkeypatch.setattr(api, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': ['test_fix']})

    def tests(*args):
        calls.append('tests')
        return {'status': 'ERROR', 'outcomes': {'test_fix': 'ERROR'}}

    monkeypatch.setattr(api, 'run_tests', tests)
    monkeypatch.setattr(api, 'collect_static_measurements', lambda *a: (calls.append('static') or static()))
    monkeypatch.setattr(api, 'apply_patch', lambda *a: SimpleNamespace(status='PASS', changed_files=['a.py'],
        model_dump=lambda **kw: {'status': 'PASS', 'changed_files': ['a.py']}))
    return task, lease, calls, tmp_path / 'artifacts'


def test_collector_keeps_independent_checks_after_test_error(api, collector_case):
    task, lease, calls, out = collector_case
    patch = '--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n def public(value):\n-    return value\n+    return value + 1\n'
    vector = api.collect_patch_vector(task, lease, None, RepairPolicy(), patch, out)
    assert calls == ['tests', 'static', 'tests', 'static']
    assert vector['baseline']['tests']['status'] == vector['post']['tests']['status'] == 'ERROR'
    assert vector['post']['compatibility']['api']['status'] == 'PASS'
    assert vector['post']['compatibility']['structural']['status'] == 'PASS'
    assert (out / 'baseline_checks/api.json').is_file()
    assert (out / 'checks/api.json').is_file()


def test_v1_metrics_bad_is_positive_and_errors_are_separate(api):
    rows = [dict(label='GOOD', operator='gold', recommendation='ACCEPT', status='PASS'),
        dict(label='GOOD', operator='gold', recommendation='REJECT', status='ERROR'),
        dict(label='BAD', operator='condition_flip', recommendation='ACCEPT', status='PASS'),
        dict(label='BAD', operator='signature_change', recommendation='REVISE', status='FAIL'),
        dict(label='BAD', operator='import_cycle', recommendation='REJECT', status='ERROR')]
    result = api.confusion_metrics(rows)
    assert {k: result[k] for k in ('TP', 'FP', 'FN', 'TN')} == {'TP': 2, 'FP': 1, 'FN': 1, 'TN': 1}
    assert result['FAR'] == pytest.approx(1 / 3)
    assert result['FRR'] == 0.5
    assert result['bad_errors'] == 1 and result['bad_check_failures'] == 1
    assert api.confusion_metrics([])['FAR'] is None


def test_not_run_is_unknown_not_a_successful_rejection(api):
    result = api.confusion_metrics([dict(label='BAD', operator='condition_flip', status='NOT_RUN', recommendation=None)])
    assert result['FAR'] is None
    assert result['bad_not_run'] == 1
    assert result['TP'] == result['FN'] == 0


@pytest.mark.parametrize('name', ['A0', 'A1', 'A2', 'A3'])
@pytest.mark.parametrize('scenario', ['pass', 'test_error', 'skip', 'api_not_run',
    'structural_fail', 'unavailable', 'baseline_tool_error', 'baseline_collection_error'])
def test_derived_arm_verdict_matches_direct_verify(api, tmp_path, monkeypatch, name, scenario):
    from vgar.repair import verification as direct
    from vgar.repair import verification_checks
    from vgar.repair import static_checks
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'def public(value):\n    return value\n')
    private = tmp_path / 'private'
    private.mkdir()
    task = SimpleNamespace(task_id='fixture', repo_key='fixture/v16', revision='base',
        allowed_source_paths=('a.py',), protected_paths=('tests',),
        failing_selectors=('test_fix',), fallback_scope=('tests',))
    lease = SimpleNamespace(path=root, private=private, before=inventory(root), assert_original=lambda: None)
    before_static = static()
    after_static = static()
    if scenario == 'unavailable':
        for half in (before_static, after_static):
            for tool in ('mypy', 'ruff'):
                half[tool]['status'] = 'UNAVAILABLE'
                half[tool]['report'].update(execution_status='UNAVAILABLE', tool_version='', reason='pinned_profile')
    if scenario == 'baseline_tool_error':
        before_static['mypy']['report']['execution_status'] = 'ERROR'
    collection = {'status': 'ERROR' if scenario == 'baseline_collection_error' else 'PASS', 'node_ids': ['test_fix']}
    tests_before = {'status': 'FAIL', 'outcomes': {'test_fix': 'FAIL'}}
    post_outcome = {'test_error': 'ERROR', 'skip': 'SKIP'}.get(scenario, 'PASS')
    tests_after = {'status': 'ERROR' if post_outcome == 'ERROR' else 'PASS', 'outcomes': {'test_fix': post_outcome}}
    compatibility = {'api': {'status': 'NOT_RUN' if scenario == 'api_not_run' else 'PASS'},
        'structural': {'status': 'FAIL' if scenario == 'structural_fail' else 'PASS'}, 'hashes': {}}
    calls = iter([before_static, after_static])
    monkeypatch.setattr(direct, 'collect_tests', lambda *a: copy.deepcopy(collection))
    monkeypatch.setattr(direct, 'run_tests', lambda *a: copy.deepcopy(tests_before))
    monkeypatch.setattr(direct, 'run_static_checks', lambda *a, **kw: copy.deepcopy(next(calls)))
    monkeypatch.setattr(verification_checks, 'run_compatibility_checks', lambda *a, **kw: copy.deepcopy(compatibility))
    variant = policy(name)
    before = direct.capture_baseline(task, lease, None, RepairPolicy(), variant=variant,
        artifact_root=tmp_path / 'direct')
    if before['status'] != 'PASS':
        expected = 'ERROR'
    else:
        partial = dict(status='TESTED', tests=tests_after, collection={'status': 'PASS'},
            related_collection={'status': 'NOT_RUN'})
        expected = direct.complete_verification(partial, task, lease,
            SimpleNamespace(changed_files=['a.py']), before, None, RepairPolicy(),
            variant=variant, artifact_root=tmp_path / 'direct')['status']
    vector = raw_vector(api)
    vector.update(baseline={'collection': collection, 'tests': tests_before, 'static': before_static,
        'required_ids': ['test_fix']}, post={'collection': {'status': 'PASS'}, 'tests': tests_after,
        'static': after_static, 'compatibility': compatibility})
    assert api.derive_verdict(api.seal_vector(vector), variant)['status'] == expected
    # The collector's structured path is still a distinct neutral interface.
    assert callable(static_checks.collect_static_measurements)


def test_invalid_patch_is_check_rejection_not_infrastructure_error(api, collector_case):
    task, lease, calls, root = collector_case
    vector = api.collect_patch_vector(task, lease, None, RepairPolicy(), 'not a diff', root)
    assert vector['integrity']['status'] == 'PASS'
    assert vector['apply']['status'] == 'FAIL'
    assert vector['post']['tests']['status'] == 'NOT_RUN'


def test_v1_rejects_inconsistent_terminal_status_and_recommendation(api):
    with pytest.raises(ValueError, match='recommendation'):
        api.confusion_metrics([dict(label='BAD', status='ERROR', recommendation='ACCEPT')])
