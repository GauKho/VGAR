"""Structured failure {stage, code, cause, evidence_ref} on every terminal non-PASS record (spec §5.5)."""
import pytest


def failure_of(record):
    from vgar.repair.failure import failure_of
    return failure_of(record)


def stages(**statuses):
    from vgar.repair.session import STAGES
    return {name: dict(statuses.get(name, {'status': 'NOT_RUN'})) for name in STAGES}


def test_pass_has_no_failure():
    assert failure_of({'status': 'PASS', 'reason': None, 'stages': stages()}) is None


def test_parse_error_uses_error_detail_stage():
    record = {'status': 'FAIL', 'reason': 'PATCH_PARSE_ERROR', 'stages': stages(parse_patch={'status': 'ERROR'}),
              'error_detail': {'stage': 'parse_patch', 'message': 'Hunk counts exceeded'}}
    assert failure_of(record) == {'stage': 'parse_patch', 'code': 'PATCH_PARSE_ERROR', 'cause': 'Hunk counts exceeded',
                                  'evidence_ref': 'run_record.json#stages/parse_patch'}


def test_apply_failure_without_error_detail_points_at_apply():
    record = {'status': 'FAIL', 'reason': 'PATCH_APPLY_FAILED', 'stages': stages(
        generation={'status': 'PASS'}, parse_patch={'status': 'PASS'},
        apply={'status': 'FAIL', 'error': {'code': 'PATCH_APPLY_FAILED', 'message': 'Original hunk context/removal mismatch'}})}
    failure = failure_of(record)
    assert (failure['stage'], failure['code'], failure['cause']) == (
        'apply', 'PATCH_APPLY_FAILED', 'Original hunk context/removal mismatch')


def test_baseline_not_qualified():
    record = {'status': 'ERROR', 'reason': 'VERIFICATION_INCOMPLETE', 'stages': stages(
        context={'status': 'PASS'}, workspace={'status': 'PASS'}, baseline={'status': 'ERROR', 'reason': 'BASELINE_NOT_QUALIFIED'})}
    assert failure_of(record)['stage'] == 'baseline' and failure_of(record)['cause'] == 'BASELINE_NOT_QUALIFIED'


def test_no_op_normalization_failure():
    record = {'status': 'FAIL', 'reason': 'NO_OP', 'stages': stages(
        generation={'status': 'PASS'}, parse_patch={'status': 'FAIL', 'error': {'code': 'NO_OP', 'message': 'all no-op'}})}
    assert failure_of(record) == {'stage': 'parse_patch', 'code': 'NO_OP', 'cause': 'all no-op',
                                  'evidence_ref': 'run_record.json#stages/parse_patch'}


def test_truncated_generation_points_at_last_reached_stage():
    record = {'status': 'ERROR', 'reason': 'VERIFICATION_INCOMPLETE', 'stages': stages(
        context={'status': 'PASS'}, prompt={'status': 'PASS'}, generation={'status': 'PASS', 'truncated': True})}
    assert failure_of(record)['stage'] == 'generation'


def test_test_failure_lists_reasons_as_cause():
    record = {'status': 'FAIL', 'reason': 'TEST_FAILED', 'stages': stages(
        apply={'status': 'PASS'}, verification={'status': 'FAIL', 'reasons': ['TEST_FAILED', 'tests/t.py::test_a']})}
    assert failure_of(record)['cause'] == 'TEST_FAILED, tests/t.py::test_a'


def test_long_cause_is_bounded():
    record = {'status': 'FAIL', 'reason': 'PATCH_PARSE_ERROR', 'stages': stages(),
              'error_detail': {'stage': 'parse_patch', 'message': 'x'*2000}}
    assert len(failure_of(record)['cause']) == 500


def test_classify_record_uses_derived_stage_for_legacy_records():
    from vgar.evaluation.repair.launch import classify_record
    record = {'status': 'FAIL', 'reason': 'PATCH_APPLY_FAILED', 'complete': True,
              'stages': stages(apply={'status': 'FAIL', 'error': {'message': 'mismatch'}})}
    result = classify_record(record, 'run-dir')
    assert result.stage == 'apply' and result.failure['code'] == 'PATCH_APPLY_FAILED'


def test_pipeline_record_carries_failure(w9_case, tmp_path):
    import json
    from pathlib import Path
    from vgar.models.generator import FakeGenerator
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.pipeline import run_repair
    task, count, tokenizer = w9_case
    root = Path(__file__).resolve().parents[3]
    definition = json.loads((root/'configs/m2/variants/A0.json').read_text())
    raw = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def logout(value):\n-    return None\n+    return 0\n'
    handle = run_repair(task, RepairPolicy(), FakeGenerator(raw), None, tmp_path/'runs', m1_counter=count,
                        tokenizer=tokenizer, temp_root=tmp_path/'temp', experiment={'variant_policy': definition, 'arm': 'bm25'})
    record = json.loads(handle.path.read_text())
    assert record['status'] == 'FAIL' and record['failure']['stage'] == 'apply'
    assert record['failure']['code'] == record['reason'] == 'PATCH_APPLY_FAILED'


class _TimedOutGenerator:
    mode = 'fake'

    def generate(self, prompt, profile, timeout_seconds):
        from vgar.repair.executor import GLOBAL_DEADLINE
        raise TimeoutError(GLOBAL_DEADLINE)


class _BrokenGenerator(_TimedOutGenerator):
    def generate(self, prompt, profile, timeout_seconds):
        raise TimeoutError('some other timeout')


def _run(w9_case, tmp_path, generator, **kwargs):
    import json
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.pipeline import run_repair
    task, count, tokenizer = w9_case
    handle = run_repair(task, RepairPolicy(), generator, None, tmp_path/'runs', m1_counter=count,
                        tokenizer=tokenizer, temp_root=tmp_path/'temp', **kwargs)
    return json.loads(handle.path.read_text())


def test_global_deadline_during_generation_is_run_timeout(w9_case, tmp_path):
    record = _run(w9_case, tmp_path, _TimedOutGenerator())
    assert (record['status'], record['reason']) == ('ERROR', 'RUN_TIMEOUT')
    assert record['failure']['stage'] == 'generation' and record['failure']['code'] == 'RUN_TIMEOUT'


def test_global_deadline_before_first_stage_is_run_timeout(w9_case, tmp_path):
    import time
    record = _run(w9_case, tmp_path, _TimedOutGenerator(), deadline=time.monotonic() - 1)
    assert (record['status'], record['reason']) == ('ERROR', 'RUN_TIMEOUT')
    assert record['failure']['stage'] == 'context'


class _FailedGenerator(_TimedOutGenerator):
    def __init__(self, **extra):
        self.extra = extra

    def generate(self, prompt, profile, timeout_seconds):
        return dict(status='ERROR', mode='fake', reason='Worker failed or response missing', **self.extra)


@pytest.mark.parametrize('extra,code', [({'timed_out': True}, 'GENERATION_TIMEOUT'),
                                        ({'timed_out': False}, 'INTERNAL_ERROR'), ({}, 'INTERNAL_ERROR')])
def test_failed_generation_code_depends_on_worker_timeout(w9_case, tmp_path, extra, code):
    record = _run(w9_case, tmp_path, _FailedGenerator(**extra))
    assert (record['status'], record['reason']) == ('ERROR', code)
    assert record['failure']['stage'] == 'generation'


def test_other_timeout_stays_internal_error(w9_case, tmp_path):
    record = _run(w9_case, tmp_path, _BrokenGenerator())
    assert (record['status'], record['reason']) == ('ERROR', 'INTERNAL_ERROR')


@pytest.mark.parametrize('detail,cause', [(None, None), ('Traceback\n  ...\nValueError: bad', 'ValueError: bad')])
def test_runner_failure_for_runner_side_outcome(detail, cause):
    from vgar.evaluation.repair.runner import LaunchResult, runner_failure
    result = LaunchResult('ERROR', 'TASK_EXCLUDED', 'plan', 'runner', None, None, detail=detail)
    assert runner_failure(result) == {'stage': 'plan', 'code': 'TASK_EXCLUDED', 'cause': cause, 'evidence_ref': None}
