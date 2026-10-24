"""Pinned base-only task environment profiles for W9-5; no M2 admission bridge."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

# Docker/process boundary is shared with the already-qualified W9-4 wrapper.
import argparse
import os
import platform
import shutil
import traceback
import uuid

from vgar.evaluation.harness.gold_inputs import ROOT, write_json
from vgar.evaluation.harness.official import cleanup_owned, invoke, utc_now
from vgar.evaluation.retrieval.pilot_manifest import PILOT_IDS, validate_manifest
from vgar.repair.executor import run_bounded


PYTHON = '/opt/miniconda3/envs/testbed/bin/python'
SCHEMA = 'vgar-task-env-v1'
PROTOCOL = 'vgar-pytest-collection-v1'


def canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def normalize_scope(scope):
    if scope == ['@pytest-default'] or scope == ('@pytest-default',):
        return ['@pytest-default']
    if not isinstance(scope, (list, tuple)) or not scope or any(not isinstance(p, str) for p in scope):
        raise ValueError('Nonempty test path scope required')
    if len(scope) != len(set(scope)):
        raise ValueError('Duplicate test path')
    for value in scope:
        path = PurePosixPath(value)
        if (not value or path.is_absolute() or value.startswith('-') or '\\' in value or ':' in value
                or '\0' in value or any(p in ('', '.', '..', '.git') for p in value.split('/'))
                or not value.endswith('.py')):
            raise ValueError('Test path must be a safe relative Python file')
    return sorted(scope)


def command(scope, *, collect=False):
    return [PYTHON, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            *(['--collect-only'] if collect else []),
            *([] if normalize_scope(scope) == ['@pytest-default'] else normalize_scope(scope))]


def build_profile(task, image, scope, probe, *, daemon_id):
    if probe.get('protocol') != PROTOCOL:
        raise ValueError('Unexpected probe protocol')
    scope = normalize_scope(scope)
    result = {'schema_version': SCHEMA, 'task_id': task['instance_id'], 'repo': task['repo'],
        'base_commit': task['base_commit'], 'env_ref': 'docker://'+image['reference'],
        'image_id': image['image_id'], 'daemon_id': daemon_id, 'cwd': '/testbed', 'python': PYTHON,
        'scope': scope, 'scope_hash': canonical_hash(scope), 'test_command': command(scope),
        'collection_command': command(scope, collect=True), 'visibility': 'base_only_no_oracle',
        'probe_protocol': PROTOCOL, 'status': probe['status'], 'reason': probe['reason'],
        'source_before': copy.deepcopy(probe['source_before']), 'source_after': copy.deepcopy(probe['source_after']),
        'runtime': copy.deepcopy(probe['runtime']), 'collection': copy.deepcopy(probe['collection'])}
    result['profile_hash'] = canonical_hash(result)
    return validate_profile(result, expected_task=task)


def validate_profile(profile, *, expected_task=None):
    fields = {'schema_version', 'task_id', 'repo', 'base_commit', 'env_ref', 'image_id', 'daemon_id',
        'cwd', 'python', 'scope', 'scope_hash', 'test_command', 'collection_command', 'visibility',
        'probe_protocol', 'status', 'reason', 'source_before', 'source_after', 'runtime', 'collection', 'profile_hash'}
    if not isinstance(profile, dict) or set(profile) != fields:
        raise ValueError('Unexpected task environment profile fields')
    p = profile
    if p['profile_hash'] != canonical_hash({k: v for k, v in p.items() if k != 'profile_hash'}):
        raise ValueError('Profile hash mismatch')
    if p['schema_version'] != SCHEMA or p['probe_protocol'] != PROTOCOL or p['visibility'] != 'base_only_no_oracle':
        raise ValueError('Unsupported profile/report/visibility protocol')
    if not isinstance(p['task_id'], str) or not re.fullmatch(r'[a-z0-9_-]+', p['task_id']):
        raise ValueError('Invalid task ID')
    if not re.fullmatch(r'[0-9a-f]{40}', p['base_commit'] or ''):
        raise ValueError('Invalid base commit')
    repo = 'swebench/sweb.eval.x86_64.'+p['task_id'].replace('__', '_1776_')
    if not re.fullmatch(re.escape('docker://'+repo+'@sha256:')+r'[0-9a-f]{64}', p['env_ref'] or ''):
        raise ValueError('Immutable official image reference required')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', p['image_id'] or '') or not p['daemon_id']:
        raise ValueError('Observed image/daemon identity required')
    if p['cwd'] != '/testbed' or p['python'] != PYTHON:
        raise ValueError('Unexpected target interpreter or cwd')
    scope = normalize_scope(p['scope'])
    if scope != p['scope'] or p['scope_hash'] != canonical_hash(scope):
        raise ValueError('Collection scope hash/order mismatch')
    if p['test_command'] != command(scope) or p['collection_command'] != command(scope, collect=True):
        raise ValueError('Fixed pytest argv mismatch')
    if expected_task is not None and any(p[k] != expected_task[v] for k, v in
            (('task_id', 'instance_id'), ('repo', 'repo'), ('base_commit', 'base_commit'))):
        raise ValueError('Profile differs from expected manifest task')
    before, after = p['source_before'], p['source_after']
    if not isinstance(before, dict) or before != after or before.get('head') != p['base_commit'] or before.get('clean') is not True:
        raise ValueError('Base source identity/drift mismatch')
    if (type(before.get('inventory_count')) is not int or before['inventory_count'] < 1
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', before.get('inventory_hash') or '')):
        raise ValueError('Missing tracked Python inventory identity')
    runtime = p['runtime']
    if (not isinstance(runtime, dict) or set(runtime) != {'python', 'pytest', 'executable'}
            or not isinstance(runtime['python'], str) or runtime['executable'] != PYTHON):
        raise ValueError('Unexpected target runtime identity')
    c = p['collection']
    if not isinstance(c, dict) or set(c) != {'exit_code', 'node_ids', 'errors'}:
        raise ValueError('Invalid collection report')
    if (not isinstance(c['node_ids'], list) or any(not isinstance(n, str) or not n for n in c['node_ids'])
            or len(c['node_ids']) != len(set(c['node_ids'])) or not isinstance(c['errors'], list)):
        raise ValueError('Invalid collected node identities')
    if p['status'] == 'COLLECTED':
        if not isinstance(runtime['pytest'], str) or type(c['exit_code']) is not int or c['exit_code'] != 0 or not c['node_ids'] or c['errors'] or p['reason'] is not None:
            raise ValueError('Cannot qualify empty/failed collection')
    elif p['status'] == 'EXCLUDED':
        if p['reason'] == 'PYTEST_UNAVAILABLE':
            valid = runtime['pytest'] is None and c['exit_code'] is None and not c['node_ids']
        elif p['reason'] == 'EMPTY_COLLECTION':
            valid = isinstance(runtime['pytest'], str) and type(c['exit_code']) is int and c['exit_code'] in (0, 5) and not c['node_ids'] and not c['errors']
        elif p['reason'] == 'COLLECTION_FAILED':
            valid = isinstance(runtime['pytest'], str) and type(c['exit_code']) is int and (c['exit_code'] != 0 or bool(c['errors']))
        else:
            valid = False
        if not valid:
            raise ValueError('Concrete consistent collection exclusion reason required')
    else:
        raise ValueError('Infrastructure/source error cannot become qualified profile')
    return copy.deepcopy(p)

BUNDLE_RUN = '20261023T071017Z-4ab71bbef7a0'


def docker_environment(host):
    if not isinstance(host, str) or not re.fullmatch(r'unix:///[^\s\x00]+', host):
        raise ValueError('Explicit Linux Unix socket required')
    env = os.environ.copy()
    env.pop('DOCKER_CONTEXT', None)
    env['DOCKER_HOST'] = host
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def checked(argv, directory, name, *, env, timeout=60):
    result = invoke(argv, directory, name, env=env, timeout=timeout)
    if (result['status'] != 'OK' or result.get('process_terminated') is False
            or result.get('output_drain_complete') is False):
        raise RuntimeError('Command incomplete: '+name+'; '+result.get('stderr', '')[-1000:])
    return result


def observe_daemon(directory, env):
    info = json.loads(checked(['docker', 'info', '--format', '{{json .}}'], directory, 'daemon', env=env)['stdout'])
    if (info.get('OSType') != 'linux' or info.get('Architecture') not in ('amd64', 'x86_64')
            or not isinstance(info.get('ID'), str) or not info['ID']):
        raise ValueError('Expected Linux amd64 daemon with identity')
    return info['ID']


def observe_image(image, directory, env):
    rows = json.loads(checked(['docker', 'image', 'inspect', image['reference']], directory, 'image', env=env)['stdout'])
    if len(rows) != 1 or image['reference'] not in (rows[0].get('RepoDigests') or []):
        raise ValueError('Image digest identity mismatch')
    row = rows[0]
    if row.get('Os') != 'linux' or row.get('Architecture') != 'amd64':
        raise ValueError('Expected Linux amd64 image')
    if image.get('image_id') is not None and image['image_id'] != row['Id']:
        raise ValueError('Pinned image ID changed')
    return row['Id']


def capture_collection(argv, directory, *, env, timeout, output_cap=8*1024*1024):
    result = run_bounded(tuple(argv), Path(directory), timeout, output_cap=output_cap, environment=env)
    result['status'] = ('TIMEOUT' if result['timed_out'] else
                        'OK' if result['complete'] and result['exit_code'] == 0 else 'ERROR')
    result.update(process_terminated=True, output_drain_complete=True)
    for name in ('stdout', 'stderr'):
        with (Path(directory)/('collection.'+name+'.log')).open('x', encoding='utf-8') as stream:
            stream.write(result[name])
    write_json(Path(directory)/'collection.json', result)
    return result


def qualify_task(task, image, scope, directory, *, docker_host, daemon_id, timeout=300):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    env = docker_environment(docker_host)
    name = 'vgar-w95-'+uuid.uuid4().hex
    report = {'task_id': task['instance_id'], 'base_commit': task['base_commit'], 'status': 'ERROR',
        'reason': None, 'profile': None, 'started_utc': utc_now(), 'container_name': name,
        'image': image, 'daemon_id': daemon_id, 'scope': normalize_scope(scope)}
    reserved = False
    candidate = None
    try:
        if observe_daemon(directory/'before', env) != daemon_id:
            raise ValueError('Daemon identity changed')
        actual = observe_image(image, directory/'before', env)
        if actual != image['image_id']:
            raise ValueError('Image identity changed')
        absent = checked(['docker', 'ps', '-aq', '--filter', 'name=^/'+name+'$'], directory, 'ownership-before', env=env)
        if absent['stdout'].strip():
            raise ValueError('Fresh container name already exists')
        reserved = True
        create = checked(['docker', 'create', '--name', name, '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--label', 'vgar.task=M1-W9-5',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', '/bin/sleep', image['image_id'], '900'],
            directory, 'container-create', env=env)
        cid = create['stdout'].strip()
        report['container_id'] = cid
        checked(['docker', 'start', cid], directory, 'container-start', env=env)
        identity = json.loads(checked(['docker', 'container', 'inspect', cid], directory, 'container-inspect', env=env)['stdout'])
        if len(identity) != 1 or identity[0]['Name'] != '/'+name or identity[0]['Image'] != image['image_id']:
            raise ValueError('Owned container identity mismatch')
        if not re.fullmatch(r'[0-9a-f]{40}', task['base_commit']):
            raise ValueError('Expected immutable base commit before repository preparation')
        git_prefix = ['docker', 'exec', cid, 'git', '-C', '/testbed']
        toplevel = checked(git_prefix+['rev-parse', '--show-toplevel'], directory, 'base-toplevel', env=env)['stdout'].strip()
        if toplevel != '/testbed':
            raise ValueError('Owned repository root mismatch')
        kind = checked(git_prefix+['cat-file', '-t', task['base_commit']], directory, 'base-object', env=env)['stdout'].strip()
        if kind != 'commit':
            raise ValueError('Expected base commit object unavailable')
        before_head = checked(git_prefix+['rev-parse', 'HEAD'], directory, 'base-head-before', env=env)['stdout'].strip()
        # Only the fresh, identity-verified container's /testbed is mutated.
        # Official images may start at a generated SWE-bench setup commit.
        checked(git_prefix+['reset', '--hard', task['base_commit']], directory, 'base-reset', env=env)
        after_head = checked(git_prefix+['rev-parse', 'HEAD'], directory, 'base-head-after', env=env)['stdout'].strip()
        if after_head != task['base_commit']:
            raise ValueError('Base checkout did not reach expected commit')
        report['base_preparation'] = {'repository_root': toplevel, 'head_before': before_head, 'head_after': after_head}
        config = directory/'probe-input.json'
        write_json(config, {'source_root': '/testbed', 'base_commit': task['base_commit'], 'scope': report['scope']})
        probe_source = Path(__file__).with_name('collection_probe.py')
        report['probe_source_hash'] = 'sha256:'+hashlib.sha256(probe_source.read_bytes()).hexdigest()
        remote = '/tmp/'+name
        checked(['docker', 'cp', str(probe_source.resolve()), cid+':'+remote+'.py'], directory, 'copy-probe', env=env)
        checked(['docker', 'cp', str(config.resolve()), cid+':'+remote+'.input.json'], directory, 'copy-input', env=env)
        process = capture_collection(['docker', 'exec', '--workdir', '/testbed', cid, PYTHON, '-B', remote+'.py',
                          remote+'.input.json', remote+'.result.json'], directory, env=env, timeout=timeout)
        report['process'] = process
        if process['status'] != 'OK' or process.get('process_terminated') is False or process.get('output_drain_complete') is False:
            raise RuntimeError('Collection process incomplete: '+process['status'])
        result_path = directory/'probe-result.json'
        checked(['docker', 'cp', cid+':'+remote+'.result.json', str(result_path.resolve())], directory, 'copy-result', env=env)
        if not result_path.is_file() or result_path.is_symlink():
            raise ValueError('Untrusted/missing probe result')
        probe = json.loads(result_path.read_text(encoding='utf-8'))
        report['probe'] = probe
        if probe['protocol'] != PROTOCOL:
            raise ValueError('Unexpected collection protocol')
        candidate = build_profile(task, image, report['scope'], probe, daemon_id=daemon_id)
        report.update(status=candidate['status'], reason=candidate['reason'])
    except BaseException:
        report.update(status='ERROR', reason='ENVIRONMENT_QUALIFICATION_ERROR', traceback=traceback.format_exc())
    finally:
        report['cleanup'] = cleanup_owned(name, image['image_id'], directory/'cleanup', env=env) if reserved else {
            'status': 'NOT_RUN', 'reason': 'No reservation; never remove foreign container'}
        if reserved and report['cleanup']['status'] != 'PASS':
            report.update(status='ERROR', reason='CLEANUP_FAILED')
        try:
            report['runtime_after'] = {'daemon_id': observe_daemon(directory/'after', env),
                                       'image_id': observe_image(image, directory/'after', env)}
            if report['runtime_after'] != {'daemon_id': daemon_id, 'image_id': image['image_id']}:
                raise ValueError('Runtime changed during qualification')
        except BaseException:
            report.update(status='ERROR', reason='RUNTIME_DRIFT', runtime_traceback=traceback.format_exc())
        if report['status'] in ('COLLECTED', 'EXCLUDED') and candidate is not None:
            profile = directory/'task_env.json'
            write_json(profile, candidate)
            report.update(profile=str(profile.resolve()), profile_hash=candidate['profile_hash'])
        report['ended_utc'] = utc_now()
        write_json(directory/'record.json', report)
    return report


def load_runtime(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    fields = {'schema_version', 'qualification_state', 'docker_host', 'sdk_python', 'collection_timeout_seconds', 'images'}
    if (set(config) != fields or config['schema_version'] != SCHEMA
            or config['qualification_state'] not in ('UNQUALIFIED', 'PINNED')
            or type(config['collection_timeout_seconds']) is not int or config['collection_timeout_seconds'] != 300
            or set(config['images']) != set(PILOT_IDS)):
        raise ValueError('Runtime schema/population/timeout mismatch')
    docker_environment(config['docker_host'])
    if not isinstance(config['sdk_python'], str) or not PurePosixPath(config['sdk_python']).is_absolute():
        raise ValueError('Separate SDK interpreter required')
    for key, value in config['images'].items():
        if not isinstance(value, dict) or set(value) != {'reference', 'image_id'}:
            raise ValueError('Invalid image specification')
        if config['qualification_state'] == 'UNQUALIFIED' and value['reference'] is None:
            continue
        expected = 'swebench/sweb.eval.x86_64.'+key.replace('__', '_1776_')+'@sha256:'
        if not isinstance(value['reference'], str) or not re.fullmatch(re.escape(expected)+r'[0-9a-f]{64}', value['reference']):
            raise ValueError('Immutable official image pin required')
        if value['image_id'] is not None and not re.fullmatch(r'sha256:[0-9a-f]{64}', value['image_id']):
            raise ValueError('Invalid image ID')
    return config


def load_scopes(bundle_root, tasks):
    scopes, bindings = {}, {}
    for task in tasks:
        key = task['instance_id']
        values = []
        bindings[key] = {}
        for arm in ('graph', 'bm25'):
            path = Path(bundle_root)/key/arm/'test_links.json'
            raw = path.read_bytes()
            value = json.loads(raw)
            if value['repository_revision'] != task['base_commit'] or value['failing_selectors']:
                raise ValueError('Test hints differ from base-only manifest')
            values.append(normalize_scope(value['fallback_scope']))
            bindings[key][arm] = 'sha256:'+hashlib.sha256(raw).hexdigest()
        if values[0] != values[1]:
            raise ValueError('Paired collection scopes differ')
        # Preserve paired hint binding; pytest itself chooses tests using base repo config.
        # Retrieval fallback files also contain intentionally invalid test-data fixtures.
        scopes[key] = ['@pytest-default']
    return scopes, bindings


def resource_gate(directory):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('Collection controller requires Linux amd64')
    script = ('$ErrorActionPreference="Stop"; $o=Get-CimInstance Win32_OperatingSystem; '
              '@{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json')
    result = checked(['powershell.exe', '-NoProfile', '-Command', script], directory, 'windows-memory', env=os.environ.copy())
    host = json.loads(result['stdout'])['available_memory_bytes']
    text = Path('/proc/meminfo').read_text()
    linux = int(re.search(r'^MemAvailable:\s+(\d+)', text, re.M)[1])*1024
    state = {'windows_available_bytes': host, 'linux_available_bytes': linux,
             'c_free_bytes': shutil.disk_usage('/mnt/c').free, 'd_free_bytes': shutil.disk_usage('/mnt/d').free}
    write_json(Path(directory)/'resources.json', state)
    if host < 4*1024**3 or linux < 4*1024**3 or state['c_free_bytes'] < 10*1024**3 or state['d_free_bytes'] < 20*1024**3:
        raise ValueError('RAM/disk resource gate not met')
    return state


def prepare(manifest_path, runtime_path, bundle_root, output_root, *, execute=False, prepare_images=False):
    run_id = 'w95-'+uuid.uuid4().hex
    directory = Path(output_root).resolve()/run_id
    directory.mkdir(parents=True, exist_ok=False)
    report = {'run_id': run_id, 'started_utc': utc_now(), 'complete': False, 'status': 'BLOCKED',
              'mode': 'execute' if execute else 'preflight',
              'tasks': [{'task_id': key, 'status': 'NOT_RUN'} for key in PILOT_IDS]}
    print('RUN DIRECTORY:', directory, flush=True)
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        approved = json.loads((ROOT/'configs/m1/w9_pilot_manifest.json').read_text(encoding='utf-8'))
        validate_manifest(manifest, expected_hash=approved['manifest_hash'])
        config = load_runtime(runtime_path)
        write_json(directory/'runtime-input.json', config)
        report['manifest_hash'] = canonical_hash(manifest)
        scopes, bindings = load_scopes(bundle_root, manifest['tasks'])
        report['scope_bindings'] = bindings
        if config['qualification_state'] != 'PINNED':
            report['reason'] = 'Runtime profile is UNQUALIFIED'
        else:
            env = docker_environment(config['docker_host'])
            resource_gate(directory/'initial-resources')
            daemon = observe_daemon(directory/'initial-daemon', env)
            sdk = checked([config['sdk_python'], '-B', '-c',
                'import docker,json; c=docker.from_env(); print(json.dumps({"ID":c.info()["ID"]})); c.close()'],
                directory, 'sdk-daemon', env=env)
            if json.loads(sdk['stdout'])['ID'] != daemon:
                raise ValueError('CLI/SDK daemon identity mismatch')
            report['daemon_id'] = daemon
            frozen = copy.deepcopy(config['images'])
            for index, task in enumerate(manifest['tasks']):
                image = frozen[task['instance_id']]
                if prepare_images:
                    resource_gate(directory/('image-resources-'+str(index)))
                    present = invoke(['docker', 'image', 'inspect', image['reference']], directory, 'cached-image-'+str(index), env=env)
                    if present['status'] != 'OK':
                        if 'No such image' not in present['stderr']:
                            raise ValueError('Cannot establish cache absence; refusing pull')
                        checked(['docker', 'pull', '--platform', 'linux/amd64', image['reference']],
                                directory, 'pull-image-'+str(index), env=env, timeout=2400)
                image['image_id'] = observe_image(image, directory/('frozen-image-'+str(index)), env)
            write_json(directory/'frozen-images.json', frozen)
            report['ready'] = True
            report['status'] = 'NOT_RUN'
            if execute:
                for index, task in enumerate(manifest['tasks']):
                    resource_gate(directory/('collection-resources-'+str(index)))
                    outcome = qualify_task(task, frozen[task['instance_id']], scopes[task['instance_id']],
                        directory/task['instance_id'], docker_host=config['docker_host'], daemon_id=daemon,
                        timeout=config['collection_timeout_seconds'])
                    report['tasks'][index] = outcome
                    if outcome['status'] == 'ERROR':
                        report.update(status='ERROR', reason='Stopped after identity/process/cleanup failure')
                        break
                else:
                    report['status'] = 'COMPLETE'
            report['collected_count'] = sum(t['status'] == 'COLLECTED' for t in report['tasks'])
            report['excluded_count'] = sum(t['status'] == 'EXCLUDED' for t in report['tasks'])
    except BaseException:
        report.update(status='ERROR', traceback=traceback.format_exc())
    report.update(complete=True, ended_utc=utc_now())
    write_json(directory/'run_record.json', report)
    print('RESULT:', report['status'], directory/'run_record.json', flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/m1/w9_pilot_manifest.json')
    parser.add_argument('--runtime', type=Path, default=ROOT/'configs/m1/w9_task_env_profile.json')
    parser.add_argument('--bundle-root', type=Path, default=ROOT/'artifacts/m1/w9/bundles'/BUNDLE_RUN)
    parser.add_argument('--output-root', type=Path, default=ROOT/'results/m1/w9/m1-w9-5/runs')
    parser.add_argument('--prepare-images', action='store_true', help='Explicitly pull only pre-pinned missing digests')
    parser.add_argument('--execute', action='store_true', help='Explicit base-only collection; no test execution or repair')
    args = parser.parse_args(argv)
    result = prepare(args.manifest, args.runtime, args.bundle_root, args.output_root,
                     execute=args.execute, prepare_images=args.prepare_images)
    return 0 if result['status'] in ('COMPLETE', 'NOT_RUN') else 2 if result['status'] == 'BLOCKED' else 1