"""M3-W9-2: classifying engine records, pre-handle failures, and one real native fixture run."""
import json


def classify(record):
    from vgar.evaluation.repair.launch import classify_record
    return classify_record(record, 'run-dir')


def test_classify_pass_record():
    result = classify({'status': 'PASS', 'reason': None, 'complete': True, 'stages': {}})
    assert (result.status, result.source, result.engine_complete, result.interrupted) == ('PASS', 'engine', True, False)
    assert result.engine_run_dir == 'run-dir'


def test_classify_keyboard_interrupt_anywhere():
    nested = {'status': 'ERROR', 'reason': 'INTERNAL_ERROR', 'complete': True,
              'stages': {'generation': {'error_detail': {'type': 'KeyboardInterrupt'}}}}
    top = {'status': 'ERROR', 'reason': 'INTERNAL_ERROR', 'complete': True, 'stages': {},
           'error_detail': {'type': 'KeyboardInterrupt', 'stage': 'generation'}}
    assert classify(nested).interrupted and classify(top).interrupted
    assert classify(top).stage == 'generation'


def test_classify_without_timeouts():
    result = classify({'status': 'FAIL', 'reason': 'TEST_FAILED', 'complete': True, 'stages': {}})
    assert result.timed_out is False and result.command_timed_out is False


def test_missing_run_record_is_infra_error(tmp_path):
    from vgar.evaluation.repair.launch import read_engine_record
    result = read_engine_record(tmp_path/'run-1'/'run_record.json')
    assert (result.status, result.reason, result.source) == ('ERROR', 'RUNNER_INFRA_ERROR', 'runner')


def test_admission_error_is_admission_rejected(swebench_config, monkeypatch, tmp_path):
    from vgar.evaluation.repair import launch as module
    from vgar.evaluation.repair.manifest import load_experiment, plan_task
    config, data = swebench_config
    exp = load_experiment(config, data)
    plan = plan_task(exp, 'demo__demo-1', exp.variants[0], data)

    def reject(*args, **kwargs):
        raise ValueError('hash mismatch')
    monkeypatch.setattr(module, 'admit_task', reject)
    monkeypatch.setattr(module, '_generation', lambda *a: (None, None, None))
    result = module.make_launch(exp, tmp_path)(plan, tmp_path/'engine', None, None)
    assert (result.status, result.reason, result.source) == ('ERROR', 'ADMISSION_REJECTED', 'runner')
    assert 'hash mismatch' in result.detail


def test_fixture_smoke_end_to_end(fixture_config, tmp_path):
    from vgar.evaluation.repair.launch import make_launch
    from vgar.evaluation.repair.manifest import load_experiment
    from vgar.evaluation.repair.runner import read_attempts, run_experiment
    exp = load_experiment(fixture_config, tmp_path)
    out = tmp_path/'out'
    assert run_experiment(exp, tmp_path, out, make_launch(exp, out)) == 0
    ledger = read_attempts(out/exp.experiment_id)
    assert len(ledger) == 3
    for (task_id, variant), [record] in ledger.items():
        assert record['state'] == 'TERMINAL' and record['source'] == 'engine'
        engine = json.loads((tmp_path/record['engine_run_dir']/'run_record.json').read_text(encoding='utf-8'))
        assert engine['experiment']['variant_id'] == variant and engine['experiment']['arm'] == record['arm']
    assert ledger[('single_file_login', 'A0')][0]['status'] == 'PASS'


def test_command_timeout_alone_is_not_a_run_timeout():
    record = {'status': 'ERROR', 'reason': 'VERIFICATION_INCOMPLETE', 'complete': True,
              'stages': {'baseline': {'tests': {'command': {'timed_out': True}}}}}
    result = classify(record)
    assert result.timed_out is False and result.command_timed_out is True


def test_global_deadline_error_is_a_run_timeout():
    record = {'status': 'ERROR', 'reason': 'INTERNAL_ERROR', 'complete': True, 'stages': {},
              'error_detail': {'type': 'TimeoutError', 'message': 'Global run deadline exhausted', 'stage': 'tests'}}
    assert classify(record).timed_out is True
