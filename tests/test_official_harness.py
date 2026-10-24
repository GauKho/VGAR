"""W9-4 offline boundary tests. All harness reports here are SYNTHETIC."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IDS = ('astropy__astropy-13398', 'django__django-11138', 'matplotlib__matplotlib-14623')
PATCH = '--- a/café.py\n+++ b/café.py\n@@ -1 +1 @@\n-old\n+new\n'


@pytest.fixture
def api():
    from vgar.evaluation.harness import official
    return official


@pytest.fixture
def inputs(tmp_path):
    manifest = json.loads((ROOT/'configs/m1/w9_pilot_manifest.json').read_text(encoding='utf-8'))
    rows = [{**task, 'patch': PATCH, 'test_patch': 'synthetic-test-patch', 'version': '1.0',
             'FAIL_TO_PASS': '["tests/test_one.py::test_bad"]',
             'PASS_TO_PASS': '["tests/test_one.py::test_good"]'} for task in manifest['tasks']]
    return manifest, rows


def save_report(directory, instance_id=IDS[0], resolved=True, patch=PATCH):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'report.json').write_text(json.dumps({instance_id: {
        'patch_is_None': False, 'patch_exists': True, 'patch_successfully_applied': True,
        'resolved': resolved, 'tests_status': {'FAIL_TO_PASS': {'success': ['bad'], 'failure': []},
                                             'PASS_TO_PASS': {'success': ['good'], 'failure': []}}}}), encoding='utf-8')
    (directory/'patch.diff').write_bytes(patch.encode())
    (directory/'test_output.txt').write_text('SYNTHETIC, not official execution', encoding='utf-8')
    (directory/'run_instance.log').write_text('SYNTHETIC', encoding='utf-8')


def test_gold_extraction_preserves_patch_and_does_not_mutate_retrieval(api, inputs):
    manifest, rows = inputs
    before = copy.deepcopy(manifest)
    selected = api.select_gold_rows(rows, manifest, IDS)
    assert [r['instance_id'] for r in selected] == list(IDS)
    assert selected[0]['patch'].encode() == PATCH.encode()
    assert selected[0]['FAIL_TO_PASS'] == ['tests/test_one.py::test_bad']
    assert manifest == before
    assert all('patch' not in t and 'test_patch' not in t for t in manifest['tasks'])


@pytest.mark.parametrize('kind', ['duplicate', 'commit', 'query', 'repo', 'missing'])
def test_gold_source_identity_mismatch_is_rejected(api, inputs, kind):
    manifest, rows = inputs
    if kind == 'duplicate':
        rows.append(copy.deepcopy(rows[0]))
    elif kind == 'missing':
        rows.pop(0)
    else:
        rows[0][{'commit': 'base_commit', 'query': 'problem_statement', 'repo': 'repo'}[kind]] = 'wrong'
    with pytest.raises(ValueError):
        api.select_gold_rows(rows, manifest, IDS)


def test_population_cannot_be_replaced_or_reordered(api, inputs):
    manifest, rows = inputs
    for ids in (IDS[:2], IDS[::-1], (IDS[0], IDS[0], IDS[2]), (*IDS[:2], 'other__task-1')):
        with pytest.raises(ValueError):
            api.select_gold_rows(rows, manifest, ids)


def test_prepare_checks_parquet_bytes_and_records_no_gold_in_manifest(api, inputs, tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from vgar.evaluation.harness import gold_inputs
    manifest, rows = inputs
    cached = tmp_path/'test.parquet'
    pq.write_table(pa.Table.from_pylist(rows), cached)
    # Fake only the approved raw-cache identity; projection/report logic stays real.
    raw, digest = cached.read_bytes(), gold_inputs.sha256
    monkeypatch.setattr(gold_inputs, 'sha256', lambda data: gold_inputs.PARQUET_HASH if data == raw else digest(data))
    out = tmp_path/'evaluation'
    prepared = api.prepare_inputs(manifest, cached, out, IDS)
    dataset = json.loads(Path(prepared['dataset']).read_text(encoding='utf-8'))
    predictions = [json.loads(l) for l in Path(prepared['predictions']).read_text(encoding='utf-8').splitlines()]
    assert dataset[0]['patch'].encode() == predictions[0]['model_patch'].encode() == PATCH.encode()
    assert prepared['project_split'] == 'dev' and prepared['upstream_partition'] == 'test'
    cached.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash'):
        api.prepare_inputs(manifest, cached, tmp_path/'another', IDS)
    with pytest.raises(FileExistsError):
        api.prepare_inputs(manifest, Path(prepared['cached_parquet']), out, IDS)


def test_command_is_pinned_local_dataset_with_safe_argv(api, tmp_path):
    profile = api.load_profile(ROOT/'configs/m1/w9_harness_profile.json')
    profile['python'] = '/space dir/python'
    image = {'tag': 'qualified-tag'}
    command = api.build_command(profile, IDS[0], tmp_path/'dữ liệu.json', tmp_path/'predictions.jsonl', 'fresh-id', image)
    assert command[:4] == ['/space dir/python', '-B', '-m', 'swebench.harness.run_evaluation']
    assert command[command.index('--dataset_name')+1] == str(tmp_path/'dữ liệu.json')
    assert command[command.index('--instance_ids')+1] == IDS[0]
    assert command[command.index('--max_workers')+1] == '1'
    assert command[command.index('--timeout')+1] == '1800'
    assert command[command.index('--clean')+1] == 'False'
    assert command[command.index('--cache_level')+1] == 'instance'
    assert command[command.index('--split')+1] == 'test'


@pytest.mark.parametrize('resolved,expected', [(True, 'RESOLVED'), (False, 'UNRESOLVED')])
def test_report_uses_strict_per_instance_resolution(api, tmp_path, resolved, expected):
    save_report(tmp_path, resolved=resolved)
    assert api.read_report(tmp_path, IDS[0], PATCH)['status'] == expected


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'wrong_id', 'string_bool', 'int_bool', 'wrong_patch', 'no_log', 'no_apply'])
def test_invalid_or_unbound_report_never_resolves(api, tmp_path, fault):
    save_report(tmp_path)
    report = tmp_path/'report.json'
    if fault == 'missing':
        report.unlink()
    elif fault == 'corrupt':
        report.write_text('{', encoding='utf-8')
    elif fault == 'wrong_id':
        save_report(tmp_path, instance_id=IDS[1])
    elif fault in {'string_bool', 'int_bool', 'no_apply'}:
        value = json.loads(report.read_text())
        key = 'patch_successfully_applied' if fault == 'no_apply' else 'resolved'
        value[IDS[0]][key] = {'string_bool': 'true', 'int_bool': 1, 'no_apply': False}[fault]
        report.write_text(json.dumps(value))
    elif fault == 'wrong_patch':
        (tmp_path/'patch.diff').write_bytes(b'changed')
    elif fault == 'no_log':
        (tmp_path/'test_output.txt').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        api.read_report(tmp_path, IDS[0], PATCH)


def test_unqualified_profile_is_blocked_without_external_commands(api, tmp_path, monkeypatch):
    profile = api.load_profile(ROOT/'configs/m1/w9_harness_profile.json')
    def forbidden(*args, **kwargs):
        raise AssertionError('Unqualified profile must not launch subprocess')
    monkeypatch.setattr(api, 'invoke', forbidden)
    report = api.preflight(profile, tmp_path)
    assert report['ready'] is False
    assert report['blockers']


@pytest.mark.parametrize('field,value', [('harness_commit', 'f'*40), ('harness_version', 'latest'),
    ('dataset_revision', 'f'*40), ('max_workers', 2), ('test_timeout_seconds', True)])
def test_changed_pin_or_execution_policy_is_rejected(api, tmp_path, field, value):
    data = json.loads((ROOT/'configs/m1/w9_harness_profile.json').read_text())
    data[field] = value
    path = tmp_path/'profile.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        api.load_profile(path)


def test_real_command_capture_is_durable_and_records_time(api, tmp_path):
    result = api.invoke([sys.executable, '-c', 'import sys; print("actual child"); sys.stderr.write("observed")'], tmp_path, 'probe', timeout=10)
    assert result['exit_code'] == 0 and result['stdout'].strip() == 'actual child'
    assert result['stderr'] == 'observed' and result['duration_seconds'] >= 0
    assert result['started_utc'] <= result['ended_utc']
    assert json.loads((tmp_path/'probe.json').read_text())['argv'][0] == sys.executable


def test_real_owned_child_timeout_is_not_unresolved(api, tmp_path):
    result = api.invoke([sys.executable, '-c', 'import time; print("began", flush=True); time.sleep(10)'], tmp_path, 'timeout', timeout=0.2)
    assert result['status'] == 'TIMEOUT' and result['traceback']
    assert 'began' in result['stdout']


@pytest.mark.parametrize('foreign', [False, True])
def test_cleanup_only_removes_exact_owned_container(api, tmp_path, monkeypatch, foreign):
    calls = []
    removed = False
    def command(argv, directory, name, **kwargs):
        nonlocal removed
        calls.append(argv)
        if argv[:3] == ['docker', 'ps', '-aq']:
            stdout = '' if removed else 'container123\n'
        elif argv[:3] == ['docker', 'container', 'inspect']:
            stdout = json.dumps([{'Id': 'container123', 'Name': '/owned-run' if not foreign else '/someone-else', 'Image': 'sha256:'+'a'*64}])
        else:
            stdout = ''
            removed = True
        return {'exit_code': 0, 'status': 'OK', 'stdout': stdout, 'stderr': ''}
    monkeypatch.setattr(api, 'invoke', command)
    result = api.cleanup_owned('owned-run', 'sha256:'+'a'*64, tmp_path)
    assert result['status'] == ('ERROR' if foreign else 'PASS')
    assert any(c[:3] == ['docker', 'rm', '-f'] for c in calls) is (not foreign)


@pytest.fixture
def synthetic_runtime(api, inputs, tmp_path_factory, monkeypatch):
    """Mock only OS/harness/Docker subprocess boundary, never report/runner logic."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from vgar.evaluation.harness import gold_inputs
    tmp_path = tmp_path_factory.mktemp('h')
    _manifest, rows = inputs
    cached = tmp_path/'cached.parquet'
    pq.write_table(pa.Table.from_pylist(rows), cached)
    raw, digest = cached.read_bytes(), gold_inputs.sha256
    monkeypatch.setattr(gold_inputs, 'sha256', lambda data: gold_inputs.PARQUET_HASH if data == raw else digest(data))
    profile = api.load_profile(ROOT/'configs/m1/w9_harness_profile.json')
    source = tmp_path/'pinned harness source'
    source.mkdir()
    profile.update(qualification_state='READY', python=sys.executable, harness_repo=str(source),
                   dataset_parquet=str(cached), docker_host='unix:///var/run/docker.sock')
    profile['images'] = {key: {'tag': 'qualified',
        'reference': 'swebench/sweb.eval.x86_64.'+key.replace('__', '_1776_')+':qualified',
        'image_id': 'sha256:'+'a'*64, 'repo_digest': 'swebench/pinned@sha256:'+'b'*64} for key in IDS}
    path = tmp_path/'profile.json'
    path.write_text(json.dumps(profile), encoding='utf-8')
    monkeypatch.setattr(api.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(api.platform, 'machine', lambda: 'x86_64')
    state = {'outcomes': ['resolved']*3, 'head': api.HARNESS_COMMIT, 'calls': [], 'launches': 0}
    def command(argv, directory, name, **kwargs):
        state['calls'].append(list(argv))
        result = {'argv': list(argv), 'status': 'OK', 'exit_code': 0, 'stdout': '', 'stderr': '', 'traceback': None}
        if name == 'harness-head':
            result['stdout'] = state['head']
        elif name == 'harness-clean':
            result['stdout'] = state.get('dirty', '')
        elif name == 'runtime-module':
            result['stdout'] = json.dumps({'version': '4.1.0', 'module': state.get('module', str(source/'swebench/harness/run_evaluation.py'))})
        elif name == 'runtime-help':
            result['stdout'] = ' '.join(api.FLAGS)
        elif name == 'docker-info':
            result['stdout'] = json.dumps({'ID': 'synthetic-daemon', 'OSType': state.get('docker_os', 'linux'), 'Architecture': 'x86_64'})
        elif name == 'sdk-daemon':
            result['stdout'] = json.dumps({'ID': state.get('sdk_id', 'synthetic-daemon')})
        elif name.startswith('image-'):
            result['stdout'] = json.dumps([{'Id': state.get('image_id', 'sha256:'+'a'*64), 'RepoDigests': ['swebench/pinned@sha256:'+'b'*64]}])
        elif name == 'harness':
            index = state['launches'] % 3
            state['launches'] += 1
            outcome = state['outcomes'][index]
            if outcome == 'exception':
                raise OSError('SYNTHETIC launch failure')
            if outcome in {'TIMEOUT', 'INTERRUPTED'}:
                result.update(status=outcome, exit_code=-1, traceback='SYNTHETIC process interruption')
            elif outcome == 'exit_error':
                result.update(status='ERROR', exit_code=1)
            elif outcome != 'missing_report':
                key = argv[argv.index('--instance_ids')+1]
                run = argv[argv.index('--run_id')+1]
                save_report(Path(kwargs['cwd'])/'logs/run_evaluation'/run/'vgar-w9-gold'/key,
                            key, outcome == 'resolved')
                if outcome == 'test_timeout':
                    log_dir = Path(kwargs['cwd'])/'logs/run_evaluation'/run/'vgar-w9-gold'/key
                    (log_dir/'report.json').unlink()
                    (log_dir/'test_output.txt').write_text('SYNTHETIC\n\nTimeout error: 1800 seconds exceeded.')
                    (log_dir/'run_instance.log').write_text('SYNTHETIC\nEvaluationError: Test timed out after 1800 seconds.')
            if state.get('mutate_after_launch'):
                state['head'] = 'f'*40
            if state.get('delete_inputs'):
                Path(argv[argv.index('--dataset_name')+1]).unlink()
        return result
    monkeypatch.setattr(api, 'invoke', command)
    return path, profile, state


@pytest.mark.parametrize('change', ['head', 'module', 'docker_os', 'image_id', 'dirty'])
def test_qualified_profile_still_requires_observed_runtime_identity(api, synthetic_runtime, tmp_path, change):
    _, profile, state = synthetic_runtime
    state[change] = 'changed'
    assert api.preflight(profile, tmp_path/'preflight')['ready'] is False
    assert state['launches'] == 0


@pytest.mark.parametrize('outcomes,expected,count', [
    (['resolved', 'unresolved', 'missing_report'], 'UNMET', 1),
    (['resolved', 'resolved', 'exit_error'], 'QUALIFIED', 2),
    (['TIMEOUT', 'resolved', 'resolved'], 'QUALIFIED', 2),
    (['exception', 'resolved', 'resolved'], 'QUALIFIED', 2),
    (['INTERRUPTED', 'resolved', 'resolved'], 'UNMET', 0),
])
def test_campaign_preserves_every_task_and_never_infers_resolution_from_exit(api, synthetic_runtime, tmp_path, outcomes, expected, count):
    path, _, state = synthetic_runtime
    state['outcomes'] = outcomes
    result = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json',
        harness_profile=path, instance_ids=IDS, output_root=path.parent/'r')
    assert result['status'] == expected and result['resolved_count'] == count
    assert len(result['tasks']) == 3 and result['complete'] is True
    if outcomes[0] == 'INTERRUPTED':
        assert state['launches'] == 1
        assert [t['status'] for t in result['tasks']] == ['ERROR', 'NOT_RUN', 'NOT_RUN']
    else:
        assert state['launches'] == 3
    if 'missing_report' in outcomes:
        assert result['tasks'][2]['status'] == 'ERROR' and result['tasks'][2]['traceback']


def test_cli_default_builds_commands_but_does_not_launch(api, synthetic_runtime, tmp_path):
    path, _, state = synthetic_runtime
    assert api.main(['--profile', str(path), '--output-root', str(path.parent/'r')]) == 0
    assert state['launches'] == 0
    result = json.loads(next((path.parent/'r').glob('*/run_record.json')).read_text())
    assert result['status'] == 'NOT_RUN' and all(t['status'] == 'NOT_RUN' for t in result['tasks'])
    assert all(t['argv'] for t in result['tasks'])


def test_new_invocation_never_reuses_old_reports(api, synthetic_runtime, tmp_path):
    path, _, state = synthetic_runtime
    first = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    second = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    assert first['run_id'] != second['run_id'] and state['launches'] == 6
    assert len(list((path.parent/'r').glob('*/run_record.json'))) == 2
    assert {t['invocation_id'] for t in first['tasks']}.isdisjoint(t['invocation_id'] for t in second['tasks'])


def test_runtime_changed_during_execution_blocks_qualification(api, synthetic_runtime, tmp_path):
    path, _, state = synthetic_runtime
    state['mutate_after_launch'] = True
    result = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    assert result['status'] == 'ERROR'
    assert result['runtime_after']['ready'] is False


def test_docker_cli_and_sdk_must_observe_same_daemon(api, synthetic_runtime, tmp_path):
    _, profile, state = synthetic_runtime
    state['sdk_id'] = 'different-daemon'
    assert api.preflight(profile, tmp_path/'daemon')['ready'] is False
    assert state['launches'] == 0


def test_explicit_docker_endpoint_overrides_ambient_context_for_both_clients(api, synthetic_runtime, tmp_path, monkeypatch):
    _, profile, _ = synthetic_runtime
    monkeypatch.setenv('DOCKER_CONTEXT', 'wrong-context')
    monkeypatch.setenv('DOCKER_HOST', 'tcp://wrong-host:2375')
    actual = api.invoke
    observations = []
    def boundary(argv, directory, name, **kwargs):
        observations.append(kwargs.get('env'))
        return actual(argv, directory, name, **kwargs)
    monkeypatch.setattr(api, 'invoke', boundary)
    assert api.preflight(profile, tmp_path/'bound')['ready'] is True
    assert all(env and env['DOCKER_HOST'] == 'unix:///var/run/docker.sock'
               and 'DOCKER_CONTEXT' not in env for env in observations)


def test_official_test_timeout_with_process_exit_zero_is_timeout(api, synthetic_runtime):
    path, _, state = synthetic_runtime
    state['outcomes'][0] = 'test_timeout'
    report = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    assert report['tasks'][0]['status'] == 'TIMEOUT'
    assert report['tasks'][0]['reason'] == 'OFFICIAL_TEST_TIMEOUT'


def test_cleanup_failure_stops_later_launches_and_vetoes_qualification(api, synthetic_runtime, monkeypatch):
    path, _, state = synthetic_runtime
    monkeypatch.setattr(api, 'cleanup_owned', lambda *args, **kwargs: {'status': 'ERROR', 'reason': 'SYNTHETIC orphan still alive'})
    report = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    assert report['status'] == 'ERROR' and state['launches'] == 1
    assert [t['status'] for t in report['tasks']] == ['ERROR', 'NOT_RUN', 'NOT_RUN']


def test_deleted_input_finalizes_current_task_as_error(api, synthetic_runtime):
    path, _, state = synthetic_runtime
    state['delete_inputs'] = True
    report = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json', harness_profile=path,
        instance_ids=IDS, output_root=path.parent/'r')
    assert report['status'] == 'ERROR' and report['resolved_count'] == 0
    assert report['tasks'][0]['status'] == 'ERROR'
    saved = path.parent/'r'/report['run_id']/IDS[0]/'record.json'
    assert json.loads(saved.read_text())['status'] == 'ERROR'
    assert state['launches'] == 1


def test_timeout_pipe_drain_always_has_a_bound(api, tmp_path, monkeypatch):
    import io
    import subprocess
    class Child:
        pid, returncode = 123, None
        stdout, stderr = io.BytesIO(), io.BytesIO()
        def communicate(self, timeout=None):
            assert timeout is not None, 'Pipe drain must not wait without a deadline'
            raise subprocess.TimeoutExpired('SYNTHETIC child', timeout, output=b'partial', stderr=b'err')
        def terminate(self):
            pass
        def kill(self):
            self.returncode = -9
        def wait(self, timeout=None):
            assert timeout is not None
            return self.returncode
    monkeypatch.setattr(api.subprocess, 'Popen', lambda *args, **kwargs: Child())
    monkeypatch.setattr(api.os, 'killpg', lambda *args: None, raising=False)
    result = api.invoke(['synthetic-child'], tmp_path, 'bounded', timeout=0.01)
    assert result['status'] == 'TIMEOUT' and result['stdout'] == 'partial'
    assert result['output_drain_complete'] is False


def test_campaign_reads_pinned_upstream_run_evaluation_directory(api, synthetic_runtime):
    # SWE-bench 4.1.0@726c5461 constants.RUN_EVALUATION_LOG_DIR, verified on real run.
    # The subprocess double emits SYNTHETIC artifacts at the upstream directory.
    path, _, _state = synthetic_runtime
    output = path.parent/'upstream-layout'
    result = api.run_gold_validation(ROOT/'configs/m1/w9_pilot_manifest.json',
        harness_profile=path, instance_ids=IDS, output_root=output)
    assert result['status'] == 'QUALIFIED'
    assert result['resolved_count'] == 3
    for task in result['tasks']:
        expected = (output/result['run_id']/task['instance_id']/'logs/run_evaluation'
                    /task['invocation_id']/'vgar-w9-gold'/task['instance_id']/'report.json')
        assert Path(task['raw_report']) == expected
        assert expected.is_file()
