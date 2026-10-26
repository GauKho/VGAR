"""W9-5 contracts and actual tiny-repository collection, without Docker."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def api():
    return importlib.import_module('vgar.evaluation.harness.task_env')


@pytest.fixture
def task():
    return {'instance_id': 'astropy__astropy-13398', 'repo': 'astropy/astropy', 'base_commit': 'a'*40}


@pytest.fixture
def image(task):
    repo = 'swebench/sweb.eval.x86_64.'+task['instance_id'].replace('__', '_1776_')
    return {'reference': repo+'@sha256:'+'b'*64, 'image_id': 'sha256:'+'c'*64}


@pytest.fixture
def probe():
    source = {'head': 'a'*40, 'clean': True, 'inventory_hash': 'sha256:'+'d'*64, 'inventory_count': 1}
    return {'protocol': 'vgar-pytest-collection-v1', 'status': 'COLLECTED', 'reason': None,
            'source_before': source, 'source_after': dict(source),
            'runtime': {'python': '3.11.0', 'pytest': '8.0.0', 'executable': '/opt/miniconda3/envs/testbed/bin/python'},
            'collection': {'exit_code': 0, 'node_ids': ['tests/test_demo.py::test_bad'], 'errors': []}}


def make_profile(task, image, probe):
    return api().build_profile(task, image, ['tests/test_demo.py'], probe, daemon_id='synthetic-daemon')


def test_profile_roundtrip_minimum_contract(task, image, probe):
    profile = make_profile(task, image, probe)
    assert profile['task_id'] == task['instance_id']
    assert profile['base_commit'] == task['base_commit']
    assert profile['env_ref'] == 'docker://'+image['reference']
    assert profile['test_command'] == ['/opt/miniconda3/envs/testbed/bin/python', '-m', 'pytest',
                                       '-q', '-p', 'no:cacheprovider', 'tests/test_demo.py']
    assert '--collect-only' in profile['collection_command']
    assert profile['visibility'] == 'base_only_no_oracle'
    assert api().validate_profile(json.loads(json.dumps(profile)), expected_task=task) == profile


@pytest.mark.parametrize('field,value', [
    ('env_ref', 'docker://swebench/image:latest'), ('base_commit', 'f'*40),
    ('task_id', 'other'), ('test_command', ['sh', '-c', 'evil']),
    ('scope', ['../escape.py']), ('visibility', 'gold'), ('extra', True),
])
def test_profile_rejects_tampering_even_after_rehash(task, image, probe, field, value):
    profile = make_profile(task, image, probe)
    profile[field] = value
    profile['profile_hash'] = api().canonical_hash({k: v for k, v in profile.items() if k != 'profile_hash'})
    with pytest.raises(ValueError):
        api().validate_profile(profile, expected_task=task)


@pytest.mark.parametrize('change', ['head', 'dirty', 'inventory', 'empty', 'exit', 'errors'])
def test_collection_cannot_be_falsely_qualified(task, image, probe, change):
    if change == 'head':
        probe['source_after']['head'] = 'f'*40
    elif change == 'dirty':
        probe['source_after']['clean'] = False
    elif change == 'inventory':
        probe['source_after']['inventory_hash'] = 'sha256:'+'e'*64
    elif change == 'empty':
        probe['collection']['node_ids'] = []
    elif change == 'exit':
        probe['collection']['exit_code'] = 2
    else:
        probe['collection']['errors'] = ['collection failed']
    with pytest.raises(ValueError):
        make_profile(task, image, probe)


def test_exclusion_keeps_reason_and_is_never_collected(task, image, probe):
    probe.update(status='EXCLUDED', reason='PYTEST_UNAVAILABLE')
    probe['collection'].update(exit_code=None, node_ids=[])
    probe['runtime']['pytest'] = None
    profile = make_profile(task, image, probe)
    assert profile['status'] == 'EXCLUDED' and profile['reason'] == 'PYTEST_UNAVAILABLE'
    assert not profile['collection']['node_ids']


@pytest.mark.parametrize('scope', [['/tmp/test.py'], ['tests/../test.py'], ['-q.py'], ['x.py::test'], ['x.py', 'x.py'], []])
def test_scope_is_fixed_unique_relative_python_paths(scope):
    with pytest.raises(ValueError):
        api().normalize_scope(scope)


def run_real_probe(tmp_path, content, scope=None, extra_files=None):
    api()  # Missing implementation must fail before producing a false green.
    repo = tmp_path/'repo'
    repo.mkdir()
    (repo/'test_demo.py').write_text(content, encoding='utf-8')
    for name, value in (extra_files or {}).items():
        target = repo/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')
    for args in [('init', '-q'), ('add', '.'), ('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'base')]:
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
    head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    config = tmp_path/'config.json'
    config.write_text(json.dumps({'source_root': str(repo), 'base_commit': head, 'scope': scope or ['test_demo.py']}))
    result = tmp_path/'result.json'
    environment = os.environ.copy()
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    process = subprocess.run([sys.executable, '-B', str(ROOT/'src/vgar/evaluation/harness/collection_probe.py'),
                              str(config), str(result)], capture_output=True, text=True, env=environment)
    assert process.returncode == 0, process.stdout+process.stderr
    return json.loads(result.read_text()), repo


def test_real_probe_collects_but_does_not_execute_failing_test(tmp_path):
    result, _ = run_real_probe(tmp_path, 'def test_bad():\n    assert False, "must not execute"\n')
    assert result['status'] == 'COLLECTED'
    assert result['collection']['node_ids'] == ['test_demo.py::test_bad']
    assert result['source_before'] == result['source_after']


def test_real_probe_empty_collection_is_excluded(tmp_path):
    result, _ = run_real_probe(tmp_path, 'value = 1\n')
    assert result['status'] == 'EXCLUDED' and result['reason'] == 'EMPTY_COLLECTION'


def test_real_probe_collection_error_is_preserved(tmp_path):
    result, _ = run_real_probe(tmp_path, 'raise RuntimeError("base import failed")\n')
    assert result['status'] == 'EXCLUDED' and result['reason'] == 'COLLECTION_FAILED'
    assert result['collection']['errors'] and result['collection']['exit_code'] != 0


def test_real_probe_detects_test_import_mutating_tracked_source(tmp_path):
    result, _ = run_real_probe(tmp_path,
        'from pathlib import Path\nPath(__file__).write_text("changed")\ndef test_one(): pass\n')
    assert result['status'] == 'ERROR' and result['reason'] == 'SOURCE_DRIFT'
@pytest.fixture
def docker_boundary(monkeypatch, tmp_path, task, image, probe):
    module = api()
    state = {'calls': [], 'daemon': 'synthetic-daemon', 'image_id': image['image_id'],
             'probe': probe, 'cleanup': 'PASS'}

    def invoke(argv, directory, name, **kwargs):
        state['calls'].append(list(argv))
        stdout = ''
        if name == 'base-object':
            stdout = state.get('base_object', 'commit')+'\n'
        elif name == 'base-toplevel':
            stdout = '/testbed\n'
        elif name == 'base-head-before':
            stdout = 'f'*40+'\n'
        elif name == 'base-head-after':
            stdout = task['base_commit']+'\n'
        elif name == 'ownership-before':
            stdout = state.get('foreign', '')
        elif name == 'container-create':
            stdout = 'owned-container-id\n'
        elif name == 'container-inspect':
            stdout = json.dumps([{'Id': 'owned-container-id', 'Name': '/'+state['name'],
                                  'Image': state['image_id']}])
        elif name == 'container-start':
            pass
        elif name == 'copy-result':
            Path(argv[-1]).write_text(json.dumps(state['probe']))
        if name == 'container-create':
            state['name'] = argv[argv.index('--name')+1]
        return {'argv': list(argv), 'status': 'OK', 'exit_code': 0, 'stdout': stdout,
                'stderr': '', 'process_terminated': True, 'output_drain_complete': True}

    monkeypatch.setattr(module, 'invoke', invoke)
    monkeypatch.setattr(module, 'capture_collection', lambda argv, directory, **kwargs: invoke(argv, directory, 'collection', **kwargs))
    monkeypatch.setattr(module, 'observe_daemon', lambda *_args: state['daemon'])
    monkeypatch.setattr(module, 'observe_image', lambda *_args: state['image_id'])
    monkeypatch.setattr(module, 'cleanup_owned', lambda *_args, **_kw: {'status': state['cleanup']})
    return module, state


def test_owned_container_collects_fixed_command_and_publishes_profile(docker_boundary, task, image, tmp_path):
    module, state = docker_boundary
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    assert result['status'] == 'COLLECTED' and result['cleanup']['status'] == 'PASS'
    profile = json.loads(Path(result['profile']).read_text())
    assert module.validate_profile(profile, expected_task=task)['status'] == 'COLLECTED'
    create = next(c for c in state['calls'] if c[:2] == ['docker', 'create'])
    assert create[create.index('--network')+1] == 'none'
    assert image['image_id'] in create and not any(x in create for x in ('-v', '--volume', '--privileged'))
    assert any(c[:2] == ['docker', 'exec'] and module.PYTHON in c for c in state['calls'])


@pytest.mark.parametrize('change', ['daemon', 'image_id', 'foreign'])
def test_identity_or_ownership_mismatch_prevents_create(docker_boundary, task, image, tmp_path, change):
    module, state = docker_boundary
    state[change] = 'foreign'
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    assert result['status'] == 'ERROR'
    assert not any(c[:2] == ['docker', 'create'] for c in state['calls'])


def test_cleanup_failure_vetoes_collected_profile(docker_boundary, task, image, tmp_path):
    module, state = docker_boundary
    state['cleanup'] = 'ERROR'
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    assert result['status'] == 'ERROR' and result['cleanup']['status'] == 'ERROR'
    assert result.get('profile') is None


def test_source_drift_cannot_be_relabelled_as_environment_exclusion(docker_boundary, task, image, tmp_path):
    module, state = docker_boundary
    state['probe'].update(status='ERROR', reason='SOURCE_DRIFT')
    state['probe']['source_after']['head'] = 'f'*40
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    assert result['status'] == 'ERROR' and result.get('profile') is None


def test_cli_help_does_not_connect_docker(capsys):
    with pytest.raises(SystemExit) as exit_info:
        api().main(['--help'])
    assert exit_info.value.code == 0
    assert '--execute' in capsys.readouterr().out


def test_runtime_rejects_mutable_image_pin(tmp_path):
    module = api()
    config = json.loads((ROOT/'configs/m1/w9_task_env_profile.json').read_text())
    config['qualification_state'] = 'PINNED'
    config['images'] = {key: {'reference': 'swebench/image:latest', 'image_id': None} for key in module.PILOT_IDS}
    path = tmp_path/'runtime.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        module.load_runtime(path)
@pytest.mark.parametrize('change', ['protocol', 'runtime_executable', 'unavailable_but_collected', 'empty_but_collected'])
def test_profile_rejects_inconsistent_probe_semantics(task, image, probe, change):
    if change == 'protocol':
        probe['protocol'] = 'different'
    elif change == 'runtime_executable':
        probe['runtime']['executable'] = '/foreign/python'
    else:
        probe.update(status='EXCLUDED', reason='PYTEST_UNAVAILABLE' if change == 'unavailable_but_collected' else 'EMPTY_COLLECTION')
    with pytest.raises(ValueError):
        make_profile(task, image, probe)


@pytest.fixture
def prepared_runtime(monkeypatch, tmp_path):
    module = api()
    manifest = ROOT/'configs/m1/w9_pilot_manifest.json'
    config = json.loads((ROOT/'configs/m1/w9_task_env_profile.json').read_text())
    config['qualification_state'] = 'PINNED'
    config['images'] = {key: {'reference': 'swebench/sweb.eval.x86_64.'+key.replace('__', '_1776_')+'@sha256:'+'b'*64,
                               'image_id': 'sha256:'+'c'*64} for key in module.PILOT_IDS}
    path = tmp_path/'runtime.json'
    path.write_text(json.dumps(config))
    state = {'launches': [], 'outcomes': ['COLLECTED']*5}
    monkeypatch.setattr(module, 'load_scopes', lambda *_args: ({key: ['test_demo.py'] for key in module.PILOT_IDS}, {}))
    monkeypatch.setattr(module, 'resource_gate', lambda *_args: {})
    monkeypatch.setattr(module, 'observe_daemon', lambda *_args: 'daemon')
    monkeypatch.setattr(module, 'observe_image', lambda *_args: 'sha256:'+'c'*64)
    monkeypatch.setattr(module, 'invoke', lambda argv, *_args, **_kw: {'status': 'OK', 'exit_code': 0, 'stdout': '{"ID":"daemon"}'})

    def qualify(task, *_args, **_kwargs):
        index = len(state['launches'])
        state['launches'].append(task['instance_id'])
        status = state['outcomes'][index]
        return {'task_id': task['instance_id'], 'status': status, 'reason': 'COLLECTION_FAILED' if status == 'EXCLUDED' else None}

    monkeypatch.setattr(module, 'qualify_task', qualify)
    return module, manifest, path, state


def test_preflight_does_not_launch_collection(prepared_runtime, tmp_path):
    module, manifest, runtime, state = prepared_runtime
    result = module.prepare(manifest, runtime, tmp_path/'bundles', tmp_path/'out')
    assert result['complete'] and result['status'] == 'NOT_RUN' and result['ready']
    assert len(result['tasks']) == 5 and not state['launches']


def test_all_five_tasks_keep_collection_exclusions(prepared_runtime, tmp_path):
    module, manifest, runtime, state = prepared_runtime
    state['outcomes'] = ['COLLECTED', 'EXCLUDED', 'COLLECTED', 'EXCLUDED', 'COLLECTED']
    result = module.prepare(manifest, runtime, tmp_path/'bundles', tmp_path/'out', execute=True)
    assert result['status'] == 'COMPLETE' and result['collected_count'] == 3 and result['excluded_count'] == 2
    assert state['launches'] == list(module.PILOT_IDS)
    assert [t['task_id'] for t in result['tasks']] == list(module.PILOT_IDS)


def test_global_infrastructure_error_stops_and_keeps_remaining_tasks(prepared_runtime, tmp_path):
    module, manifest, runtime, state = prepared_runtime
    state['outcomes'][0] = 'ERROR'
    result = module.prepare(manifest, runtime, tmp_path/'bundles', tmp_path/'out', execute=True)
    assert result['status'] == 'ERROR' and len(state['launches']) == 1
    assert [t['status'] for t in result['tasks']] == ['ERROR']+['NOT_RUN']*4

def test_collection_capture_bounds_output_and_preserves_raw_evidence(tmp_path):
    directory = tmp_path/'bounded'
    directory.mkdir()
    result = api().capture_collection([sys.executable, '-c', 'print("x"*4096)'], directory,
                                      env=os.environ.copy(), timeout=10, output_cap=256)
    assert result['status'] == 'ERROR' and result['output_truncated']
    assert len(result['stdout'].encode()) <= 256
    assert (directory/'collection.json').is_file()


def test_collection_capture_timeout_is_not_success(tmp_path):
    directory = tmp_path/'bounded'
    directory.mkdir()
    result = api().capture_collection([sys.executable, '-c', 'import time;time.sleep(10)'], directory,
                                      env=os.environ.copy(), timeout=0.1)
    assert result['status'] == 'TIMEOUT' and result['timed_out']

def test_project_default_scope_uses_repo_pytest_discovery_not_data_fixtures(tmp_path):
    result, _ = run_real_probe(tmp_path, 'raise RuntimeError("not a configured test file")\n',
        scope=['@pytest-default'], extra_files={
            'pytest.ini': '[pytest]\npython_files = check_*.py\n',
            'check_custom.py': 'def test_one(): assert False\n',
            'data/test_bad_fixture.py': 'def invalid syntax\n'})
    assert result['status'] == 'COLLECTED'
    assert result['collection']['node_ids'] == ['check_custom.py::test_one']
    assert api().command(['@pytest-default']) == [api().PYTHON, '-m', 'pytest', '-q', '-p', 'no:cacheprovider']


def test_owned_container_is_prepared_at_exact_base_before_probe(docker_boundary, task, image, tmp_path):
    module, state = docker_boundary
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    reset = ['docker', 'exec', 'owned-container-id', 'git', '-C', '/testbed', 'reset', '--hard', task['base_commit']]
    assert reset in state['calls']
    probe_index = next(i for i, c in enumerate(state['calls']) if c[:2] == ['docker', 'exec'] and module.PYTHON in c)
    assert state['calls'].index(reset) < probe_index
    assert result['base_preparation']['head_after'] == task['base_commit']
    assert result['status'] == 'COLLECTED'


def test_missing_base_commit_never_runs_probe_or_publishes_profile(docker_boundary, task, image, tmp_path):
    module, state = docker_boundary
    state['base_object'] = 'blob'
    result = module.qualify_task(task, image, ['tests/test_demo.py'], tmp_path/'job',
                                 docker_host='unix:///var/run/docker.sock', daemon_id='synthetic-daemon')
    assert result['status'] == 'ERROR' and result['profile'] is None
    assert not any(module.PYTHON in c for c in state['calls'])
    assert result['cleanup']['status'] == 'PASS'
