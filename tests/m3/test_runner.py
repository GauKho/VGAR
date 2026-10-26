"""M3-W9-2: attempt ledger, experiment lock and resume, with an injected launch (no engine)."""
import json
import subprocess
import sys

import pytest
from m3_support import ROOT, write_json


class FakeLaunch:
    """Scripted launch: results[i] is returned (or raised) on the i-th call; default PASS."""

    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def __call__(self, plan, out_dir, supersedes_run_id, rerun_reason):
        from vgar.evaluation.repair.runner import LaunchResult
        self.calls.append((plan.task_id, plan.variant.variant_id, supersedes_run_id, rerun_reason))
        result = self.results.pop(0) if self.results else 'PASS'
        if isinstance(result, BaseException):
            raise result
        if isinstance(result, str):
            return LaunchResult(result, None, None, 'engine', str(out_dir/'run-1'), True)
        return result


def load(config, data):
    from vgar.evaluation.repair.manifest import load_experiment
    return load_experiment(config, data)


def attempts(out, exp, task, variant):
    folder = out/exp.experiment_id/'attempts'/f'{task}__{variant}'
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('attempt-*.json'))]


def run(exp, data, out, launch, **kwargs):
    from vgar.evaluation.repair.runner import run_experiment
    return run_experiment(exp, data, out, launch, **kwargs)


def test_runs_every_task_variant_once_in_manifest_order(fixture_config, tmp_path):
    exp, launch = load(fixture_config, tmp_path), FakeLaunch()
    assert run(exp, tmp_path, tmp_path/'out', launch) == 0
    assert [c[1] for c in launch.calls] == ['A0', 'A1', 'A2']
    for variant in ('A0', 'A1', 'A2'):
        [record] = attempts(tmp_path/'out', exp, 'single_file_login', variant)
        assert record['state'] == 'TERMINAL' and record['status'] == 'PASS' and record['attempt'] == 1
        assert record['experiment_id'] == exp.experiment_id and record['task_id'] == 'single_file_login'
        assert record['variant_id'] == variant and record['source'] == 'engine'
    assert json.loads((tmp_path/'out'/exp.experiment_id/'experiment.json').read_text())['experiment_id'] == exp.experiment_id


def test_terminal_pairs_are_skipped_on_second_run(fixture_config, tmp_path):
    exp, launch = load(fixture_config, tmp_path), FakeLaunch()
    run(exp, tmp_path, tmp_path/'out', launch)
    run(exp, tmp_path, tmp_path/'out', launch)
    assert len(launch.calls) == 3


def test_fail_and_error_are_terminal_and_not_retried(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch('FAIL', 'ERROR', 'PASS'))
    again = FakeLaunch()
    run(exp, tmp_path, tmp_path/'out', again)
    assert again.calls == []
    assert attempts(tmp_path/'out', exp, 'single_file_login', 'A1')[0]['status'] == 'ERROR'


def reserve(out, exp, variant, *, with_run):
    pair = out/exp.experiment_id/'attempts'/f'single_file_login__{variant}'
    engine = out/exp.experiment_id/'engine'/f'single_file_login__{variant}'/'attempt-1'
    engine.mkdir(parents=True)
    if with_run:
        write_json(engine/'run-x'/'run_record.json', {'run_id': 'run-x', 'complete': False})
    write_json(pair/'attempt-1.json', {'experiment_id': exp.experiment_id, 'task_id': 'single_file_login',
                                        'variant_id': variant, 'attempt': 1, 'state': 'RESERVED',
                                        'engine_output_root': str(engine)})


def test_reserved_becomes_interrupted_and_reruns_with_parent(fixture_config, tmp_path):
    exp, launch = load(fixture_config, tmp_path), FakeLaunch()
    reserve(tmp_path/'out', exp, 'A0', with_run=True)
    run(exp, tmp_path, tmp_path/'out', launch)
    first, second = attempts(tmp_path/'out', exp, 'single_file_login', 'A0')
    assert first['state'] == 'INTERRUPTED'
    assert second['state'] == 'TERMINAL' and second['parent_attempt'] == 1 and second['rerun_reason'] == 'interrupted'
    assert launch.calls[0] == ('single_file_login', 'A0', 'run-x', 'interrupted')


def test_reserved_without_run_dir_reruns_without_supersede(fixture_config, tmp_path):
    exp, launch = load(fixture_config, tmp_path), FakeLaunch()
    reserve(tmp_path/'out', exp, 'A0', with_run=False)
    run(exp, tmp_path, tmp_path/'out', launch)
    assert launch.calls[0] == ('single_file_login', 'A0', None, 'interrupted')


def test_keyboard_interrupt_in_launch_marks_interrupted(fixture_config, tmp_path):
    from vgar.evaluation.repair.runner import ExperimentLock
    exp, launch = load(fixture_config, tmp_path), FakeLaunch('PASS', KeyboardInterrupt())
    assert run(exp, tmp_path, tmp_path/'out', launch) == 130
    assert len(launch.calls) == 2
    [record] = attempts(tmp_path/'out', exp, 'single_file_login', 'A1')
    assert record['state'] == 'INTERRUPTED'
    assert attempts(tmp_path/'out', exp, 'single_file_login', 'A2') == []
    with ExperimentLock(tmp_path/'out'/exp.experiment_id/'runner.lock'):
        pass


def test_engine_reported_interrupt_stops_loop(fixture_config, tmp_path):
    from vgar.evaluation.repair.runner import LaunchResult
    exp = load(fixture_config, tmp_path)
    interrupted = LaunchResult('ERROR', 'INTERNAL_ERROR', 'generation', 'engine', 'x', True, interrupted=True)
    launch = FakeLaunch(interrupted)
    assert run(exp, tmp_path, tmp_path/'out', launch) == 130
    [record] = attempts(tmp_path/'out', exp, 'single_file_login', 'A0')
    assert record['state'] == 'INTERRUPTED' and len(launch.calls) == 1


def test_launch_exception_becomes_runner_error(fixture_config, tmp_path):
    exp, launch = load(fixture_config, tmp_path), FakeLaunch(RuntimeError('boom'))
    assert run(exp, tmp_path, tmp_path/'out', launch) == 0
    [record] = attempts(tmp_path/'out', exp, 'single_file_login', 'A0')
    assert (record['state'], record['status'], record['reason'], record['source']) == \
        ('TERMINAL', 'ERROR', 'RUNNER_INFRA_ERROR', 'runner')
    assert 'boom' in record['detail'] and len(launch.calls) == 3


def test_skip_plans_are_recorded_without_launch(swebench_config):
    config, data = swebench_config
    exp, launch = load(config, data), FakeLaunch()
    run(exp, data, data/'out', launch)
    assert {c[0] for c in launch.calls} == {'demo__demo-1'}
    for variant in ('A0', 'A1', 'A2'):
        [record] = attempts(data/'out', exp, 'demo__demo-2', variant)
        assert (record['state'], record['status'], record['reason']) == ('TERMINAL', 'ERROR', 'TASK_EXCLUDED')
        assert record['detail'] == 'PYTEST_UNAVAILABLE' and record['source'] == 'runner'


def test_plan_error_becomes_admission_rejected(swebench_config):
    config, data = swebench_config
    exp = load(config, data)
    (data/'repositories/demo__demo-1/pkg/core.py').write_bytes(b'changed\n')
    run(exp, data, data/'out', FakeLaunch())
    [record] = attempts(data/'out', exp, 'demo__demo-1', 'A0')
    assert (record['status'], record['reason'], record['stage']) == ('ERROR', 'ADMISSION_REJECTED', 'plan')


def test_rerun_flag_keeps_old_attempt(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch())
    folder = tmp_path/'out'/exp.experiment_id/'attempts'/'single_file_login__A1'
    before = (folder/'attempt-1.json').read_bytes()
    launch = FakeLaunch()
    run(exp, tmp_path, tmp_path/'out', launch, rerun=('single_file_login', 'A1'), rerun_reason='env fixed')
    assert launch.calls == [('single_file_login', 'A1', None, 'env fixed')]
    assert (folder/'attempt-1.json').read_bytes() == before
    second = attempts(tmp_path/'out', exp, 'single_file_login', 'A1')[1]
    assert second['parent_attempt'] == 1 and second['rerun_reason'] == 'env fixed'


def test_rerun_requires_reason(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    with pytest.raises(ValueError, match='reason'):
        run(exp, tmp_path, tmp_path/'out', FakeLaunch(), rerun=('single_file_login', 'A1'))


def test_rerun_requires_terminal_pair(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    with pytest.raises(ValueError, match='TERMINAL'):
        run(exp, tmp_path, tmp_path/'out', FakeLaunch(), rerun=('single_file_login', 'A1'), rerun_reason='x')


def test_second_runner_is_locked_out(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    lock = tmp_path/'out'/exp.experiment_id/'runner.lock'
    lock.parent.mkdir(parents=True)
    holder = subprocess.Popen(
        [sys.executable, '-c', ('import sys; from pathlib import Path; '
         'from vgar.evaluation.repair.runner import ExperimentLock\n'
         f'with ExperimentLock(Path({str(lock)!r})):\n    print("locked", flush=True); sys.stdin.read()')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=ROOT,
        env={**__import__('os').environ, 'PYTHONPATH': str(ROOT/'src')})
    try:
        assert holder.stdout.readline().strip() == 'locked'
        with pytest.raises(RuntimeError, match='locked'):
            run(exp, tmp_path, tmp_path/'out', FakeLaunch())
    finally:
        holder.communicate('')


class FakeSampler:
    def start(self):
        pass

    def stop(self):
        return 2048


def test_wall_ms_and_gpu_fields(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch(), sampler_factory=FakeSampler)
    [record] = attempts(tmp_path/'out', exp, 'single_file_login', 'A0')
    assert record['gpu_peak_mib'] == 2048 and record['gpu_peak_scope'] == 'device' and record['wall_ms'] >= 0
    run(exp, tmp_path, tmp_path/'other', FakeLaunch())
    [plain] = attempts(tmp_path/'other', exp, 'single_file_login', 'A0')
    assert plain['gpu_peak_mib'] is None


def test_summary_table_has_one_row_per_pair_and_marks_timeouts(fixture_config, tmp_path):
    from vgar.evaluation.repair.runner import LaunchResult, summary_table
    exp = load(fixture_config, tmp_path)
    timed = LaunchResult('ERROR', 'VERIFICATION_INCOMPLETE', None, 'engine', 'x', True, timed_out=True)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch('PASS', timed), sampler_factory=FakeSampler)
    lines = summary_table(tmp_path/'out'/exp.experiment_id, exp).splitlines()
    rows = [line for line in lines if line.startswith('| single_file_login')]
    assert len(rows) == 3
    assert '| A0 | TERMINAL | PASS |' in rows[0] and '| 2048 |' in rows[0]
    assert '≥ 30.0' in rows[1] and 'VERIFICATION_INCOMPLETE' in rows[1]
    assert '| A2 | TERMINAL | PASS |' in rows[2]
