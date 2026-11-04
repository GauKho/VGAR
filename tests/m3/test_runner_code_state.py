"""Trace spec 2026-11-03 §6.2 (plan Task 8): each runner attempt records the VGAR code it ran on (E6) and an
outcome class (E3); `status` shows both."""
import json

from test_runner import FakeLaunch, attempts, load, run


def test_attempt_records_code_state_and_class(fixture_config, tmp_path):
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch('PASS', 'FAIL', 'PASS'))
    [record] = attempts(tmp_path/'out', exp, 'single_file_login', 'A0')
    assert len(record['code']['head']) == 40 and isinstance(record['code']['dirty'], list)
    assert record['failure_class'] == 'VERIFIED'


def test_admission_rejected_is_protocol(swebench_config):
    config, data = swebench_config
    exp = load(config, data)
    (data/'repositories/demo__demo-1/pkg/core.py').write_bytes(b'changed\n')
    run(exp, data, data/'out', FakeLaunch())
    [record] = attempts(data/'out', exp, 'demo__demo-1', 'A0')
    assert record['failure_class'] == 'PROTOCOL'


def test_summary_table_shows_class_and_code(fixture_config, tmp_path):
    from vgar.evaluation.repair.runner import summary_table
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch())
    lines = summary_table(tmp_path/'out'/exp.experiment_id, exp).splitlines()
    assert lines[2].endswith('| class | code |')
    row = next(line for line in lines if line.startswith('| single_file_login | A0'))
    assert '| VERIFIED |' in row


def test_old_attempt_without_code_still_renders(fixture_config, tmp_path):
    from vgar.evaluation.repair.runner import summary_table
    exp = load(fixture_config, tmp_path)
    run(exp, tmp_path, tmp_path/'out', FakeLaunch())
    for path in (tmp_path/'out'/exp.experiment_id/'attempts').glob('*/attempt-*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        record.pop('code'), record.pop('failure_class')
        path.write_text(json.dumps(record), encoding='utf-8')
    row = next(line for line in summary_table(tmp_path/'out'/exp.experiment_id, exp).splitlines()
               if line.startswith('| single_file_login | A0'))
    assert row.endswith('|  |  |')


def test_runner_attempt_class_reads_the_engine_record(tmp_path):
    """X2b 03/11: a VERIFICATION_INCOMPLETE attempt is classed by the cause in the engine's run_record.json."""
    from vgar.evaluation.repair.runner import _outcome
    truncated = {"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
                 "stages": {"generation": {"status": "PASS", "truncated": True, "output_tokens": 1536}}}
    (tmp_path / "run_record.json").write_text(json.dumps(truncated), encoding="utf-8")
    record = {"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE", "engine_run_dir": str(tmp_path)}
    assert _outcome(record) == "MODEL"
    assert _outcome({"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE", "engine_run_dir": None}) == "UNCLASSIFIED"
