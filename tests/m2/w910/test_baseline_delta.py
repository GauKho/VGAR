"""Policy verdicts over real source snapshots and controlled external tool reports."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair import verification as verify
from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant
from vgar.repair.static_checks import run_static_checks

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = 'tests/test_app.py::test_required'
REGRESSION = 'tests/test_app.py::test_regression'


class FixtureExecutor:
    """Replace only subprocess output; source, parser, comparator and verifier stay real."""

    def __init__(self):
        self.rows = [{'file': 'app.py', 'line': 2, 'column': 0, 'severity': 'error',
                      'code': 'assignment', 'message': 'Existing error'}]
        self.tool_fault = False
        self.version = '2.4.0'
        self.calls = []

    def run(self, argv, cwd, timeout_seconds):
        self.calls.append(argv)
        tool = argv[2]
        version = '--version' in argv
        if version:
            raw, code = tool + ' ' + (self.version if tool == 'mypy' else '0.17.0'), 0
        elif tool == 'mypy':
            raw = '\n'.join(json.dumps(r) for r in self.rows)
            code = 1 if self.rows else 0
        else:
            raw, code = '[]', 0
        fault = self.tool_fault and tool == 'mypy' and not version
        return {'argv': list(argv), 'cwd': str(cwd), 'stdout': raw, 'stderr': '',
                'status': 'ERROR' if fault else 'FAIL' if code else 'PASS',
                'exit_code': None if fault else code, 'complete': not fault,
                'timed_out': fault, 'output_truncated': False,
                'duration_ms': 1, 'timeout_seconds': timeout_seconds}


class FixtureLease:
    def __init__(self, root):
        self.path = root / 'worktree'
        self.path.mkdir()
        self.private = root / 'private'
        self.private.mkdir()
        (self.path / 'app.py').write_text('value = 1\nold_debt = missing\n', encoding='utf-8')
        (self.path / 'protected.txt').write_text('original', encoding='utf-8')
        from vgar.repair.workspace import inventory
        self.before = inventory(self.path)

    def assert_original(self):
        # The unit lease has no external original; unexpected private edits are
        # still checked by the real inventory guard in complete_verification.
        pass


def outcomes_result(required='FAIL', regression='PASS', status=None):
    outcomes = {REQUIRED: required, REGRESSION: regression}
    return {'status': status or ('FAIL' if 'FAIL' in outcomes.values() else 'PASS'),
            'outcomes': outcomes, 'node_ids': list(outcomes), 'durations_ms': {k: 1 for k in outcomes}}


@pytest.fixture
def case(tmp_path, monkeypatch):
    task = SimpleNamespace(allowed_source_paths=('app.py',), failing_selectors=(REQUIRED,), fallback_scope=('tests',))
    lease, executor = FixtureLease(tmp_path), FixtureExecutor()
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': [REQUIRED, REGRESSION]})
    monkeypatch.setattr(verify, 'run_tests', lambda *a: outcomes_result())
    return task, lease, executor, RepairPolicy()


def variant(name='A2'):
    return load_variant(ROOT / 'configs/m2/variants' / (name + '.json'))


def baseline(case, arm='A2'):
    task, lease, executor, policy = case
    return verify.capture_baseline(task, lease, executor, policy, variant=variant(arm))


def completion(case, before, arm='A2', tests=None):
    task, lease, executor, policy = case
    partial = {'status': 'TESTED', 'tests': tests or outcomes_result(required='PASS'),
               'collection': {'status': 'PASS'}, 'related_collection': {'status': 'NOT_RUN'}}
    return verify.complete_verification(partial, task, lease,
        SimpleNamespace(status='PASS', changed_files=['app.py']), before, executor, policy, variant=variant(arm))


def test_existing_mypy_debt_qualifies_baseline_and_delta_passes(case):
    before = baseline(case)
    assert before['status'] == 'PASS'
    assert before['static']['mypy']['status'] == 'FAIL'  # Raw debt remains visible.
    result = completion(case, before)
    assert result['status'] == 'PASS'
    assert result['static']['mypy']['status'] == 'FAIL'
    assert result['policy_checks']['mypy']['status'] == 'PASS'


def test_old_error_shifted_by_inserted_line_remains_old(case):
    before = baseline(case)
    _, lease, executor, _ = case
    path = lease.path / 'app.py'
    path.write_text('# inserted\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
    executor.rows[0]['line'] = 3
    result = completion(case, before)
    assert result['status'] == 'PASS'
    assert result['policy_checks']['mypy']['delta']['persisting']


def test_baseline_survives_json_roundtrip_between_process_steps(case):
    before = json.loads(json.dumps(baseline(case)))
    assert completion(case, before)['status'] == 'PASS'


@pytest.mark.parametrize(('name', 'expected'), [('A0', 'PASS'), ('A1', 'PASS'), ('A2', 'FAIL')])
def test_new_static_error_is_required_only_for_a2(case, name, expected):
    before = baseline(case, name)
    case[2].rows.append({'file': 'app.py', 'line': 1, 'column': 0, 'severity': 'error',
                         'code': 'arg-type', 'message': 'New error'})
    result = completion(case, before, name)
    assert result['status'] == expected
    assert result['policy_checks']['mypy']['status'] == 'FAIL'
    assert result['policy_checks']['mypy']['required'] is (name == 'A2')


@pytest.mark.parametrize(('name', 'expected'), [('A0', 'PASS'), ('A1', 'PASS'), ('A2', 'ERROR')])
def test_tool_timeout_is_recorded_and_never_faked_as_check_pass(case, name, expected):
    before = baseline(case, name)
    case[2].tool_fault = True
    result = completion(case, before, name)
    assert result['status'] == expected
    assert result['policy_checks']['mypy']['status'] == 'ERROR'


def test_required_static_tool_error_blocks_baseline(case):
    case[2].tool_fault = True
    assert baseline(case)['status'] == 'ERROR'


def test_optional_static_tool_error_does_not_block_baseline(case):
    case[2].tool_fault = True
    assert baseline(case, 'A0')['status'] == 'PASS'


def test_legacy_still_requires_absolute_static_pass(case):
    task, lease, executor, policy = case
    before = verify.capture_baseline(task, lease, executor, policy)
    assert before['status'] == 'ERROR' and before['reason'] == 'BASELINE_NOT_QUALIFIED'


@pytest.mark.parametrize('change', ['config', 'scope', 'version', 'variant'])
def test_binding_drift_cannot_accept_patch(case, change):
    before = baseline(case)
    if change == 'config':
        before['static']['config_hashes']['mypy'] = 'different'
    elif change == 'scope':
        before['static']['binding']['scope_hash'] = 'different'
    elif change == 'version':
        case[2].version = '2.5.0'
    else:
        before['variant_policy_hash'] = 'different'
    assert completion(case, before)['status'] == 'ERROR'


@pytest.mark.parametrize('outcome', ['SKIP', 'NOT_RUN', 'ERROR'])
def test_incomplete_required_test_never_accepts(case, outcome):
    before = baseline(case, 'A0')
    assert completion(case, before, 'A0', outcomes_result(required=outcome))['status'] == 'ERROR'


def test_regression_failure_rejects_even_a0(case):
    before = baseline(case, 'A0')
    assert completion(case, before, 'A0', outcomes_result(required='PASS', regression='FAIL'))['status'] == 'FAIL'


def test_missing_collection_prevents_generation_readiness(case, monkeypatch):
    monkeypatch.setattr(verify, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': [REGRESSION]})
    assert baseline(case)['status'] == 'ERROR'


def test_protected_file_change_rejected_for_every_policy(case):
    before = baseline(case, 'A0')
    (case[1].path / 'protected.txt').write_text('tampered', encoding='utf-8')
    assert completion(case, before, 'A0')['status'] == 'ERROR'


def test_syntax_checks_collect_all_files_not_just_first_error(case):
    _, lease, executor, policy = case
    for name in ('one.py', 'two.py'):
        (lease.path / name).write_text('def bad(:\n', encoding='utf-8')
    executor.rows = []
    result = run_static_checks(lease, ('one.py', 'two.py'), policy, executor, variant=variant())
    assert len(result['syntax']['report']['diagnostics']) == 2


def test_unreadable_post_snapshot_is_global_error_even_for_a0(case):
    before = baseline(case, 'A0')
    (case[1].path / 'app.py').write_bytes(b'\xff')
    assert completion(case, before, 'A0')['status'] == 'ERROR'


def test_optional_tool_io_exception_is_recorded_not_raised(case, monkeypatch):
    before = baseline(case, 'A0')
    executor = case[2]
    original = executor.run

    def unavailable(argv, cwd, timeout):
        if argv[2] == 'mypy' and '--version' not in argv:
            raise OSError('Synthetic report transport failure')
        return original(argv, cwd, timeout)

    monkeypatch.setattr(executor, 'run', unavailable)
    result = completion(case, before, 'A0')
    assert result['status'] == 'PASS'
    assert result['policy_checks']['mypy']['status'] == 'ERROR'
    assert result['static']['mypy']['exception']['type'] == 'OSError'


def test_global_deadline_is_not_swallowed_as_optional_tool_failure(case, monkeypatch):
    before = baseline(case, 'A0')

    def exhausted(*args):
        raise TimeoutError('Global deadline')

    monkeypatch.setattr(case[2], 'run', exhausted)
    with pytest.raises(TimeoutError, match='Global deadline'):
        completion(case, before, 'A0')
