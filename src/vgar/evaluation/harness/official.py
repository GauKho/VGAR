"""Pinned official gold qualification. CLI defaults to preflight, never execution."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from vgar.evaluation.harness.gold_inputs import (
    GOLD_IDS,
    ROOT,
    prepare_inputs,
    select_gold_rows,  # noqa: F401 -- evaluation helper re-export
    write_json,
)
from vgar.evaluation.harness.reports import read_report
from vgar.evaluation.retrieval.evidence import sha256
from vgar.evaluation.retrieval.pilot_manifest import DATASET_REVISION

HARNESS_COMMIT = '726c5461e2ef52d83cf1ea2107870a8bb3328d57'
MODEL_LABEL = 'vgar-w9-gold'
FLAGS = ('--dataset_name', '--predictions_path', '--instance_ids', '--max_workers', '--timeout',
         '--run_id', '--namespace', '--instance_image_tag', '--cache_level', '--clean', '--force_rebuild', '--split')


def utc_now():
    return datetime.now(UTC).isoformat()


def invoke(argv, directory, name, *, timeout=30, cwd=None, env=None):
    """Capture an owned subprocess; terminate only the process we launched."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    record = {'argv': list(argv), 'cwd': str(cwd or directory), 'started_utc': utc_now(),
              'timeout_seconds': timeout, 'status': 'ERROR', 'exit_code': None,
              'stdout': '', 'stderr': '', 'traceback': None, 'output_drain_complete': True}
    start, child = time.perf_counter(), None
    stdout, stderr = b'', b''
    try:
        child = subprocess.Popen(argv, cwd=cwd or directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env, start_new_session=os.name == 'posix')
        record['pid'] = child.pid
        stdout, stderr = child.communicate(timeout=timeout)
        record.update(exit_code=child.returncode, status='OK' if child.returncode == 0 else 'ERROR')
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        record.update(status='TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'INTERRUPTED',
                      traceback=traceback.format_exc())
        if child is not None:
            def stop_owned(force):
                try:
                    if os.name == 'posix':
                        # New session was created by this Popen; never target a shared process group.
                        os.killpg(child.pid, signal.SIGKILL if force else signal.SIGTERM)
                    elif force:
                        child.kill()
                    else:
                        child.terminate()
                except ProcessLookupError:
                    pass
                except OSError:
                    record.setdefault('termination_errors', []).append(traceback.format_exc())
            stop_owned(False)
            try:
                stdout, stderr = child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stop_owned(True)
                try:
                    stdout, stderr = child.communicate(timeout=5)
                except subprocess.TimeoutExpired as drain_error:
                    stdout, stderr = drain_error.output or b'', drain_error.stderr or b''
                    record['output_drain_complete'] = False
                    for pipe in (child.stdout, child.stderr):
                        if pipe is not None:
                            pipe.close()
                    try:
                        child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        record['termination_errors'] = [traceback.format_exc()]
            record['exit_code'] = child.returncode
    except OSError:
        record['traceback'] = traceback.format_exc()
    record.update(process_terminated=child is None or child.returncode is not None,
                  stdout=stdout.decode('utf-8', 'replace'), stderr=stderr.decode('utf-8', 'replace'),
                  ended_utc=utc_now(), duration_seconds=time.perf_counter()-start)
    for suffix in ('stdout', 'stderr'):
        with (directory/f'{name}.{suffix}.log').open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(record[suffix])
    write_json(directory/f'{name}.json', record)
    return record


def load_profile(path):
    profile = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(profile, dict):
        raise TypeError('Harness profile must be an object')
    exact = {'harness_version': '4.1.0', 'harness_commit': HARNESS_COMMIT,
             'dataset_revision': DATASET_REVISION, 'max_workers': 1,
             'test_timeout_seconds': 1800, 'process_timeout_seconds': 3600}
    if any(type(profile.get(k)) is not type(v) or profile[k] != v for k, v in exact.items()):
        raise ValueError('Harness pin or execution policy mismatch')
    if profile.get('qualification_state') not in {'UNQUALIFIED', 'READY'} or not isinstance(profile.get('images'), dict):
        raise ValueError('Invalid harness qualification profile')
    for key in ('python', 'harness_repo', 'dataset_parquet'):
        if profile.get(key) is not None and (not isinstance(profile[key], str) or not profile[key]):
            raise ValueError('Invalid runtime/input path')
        if profile.get(key) and not Path(profile[key]).is_absolute():
            profile[key] = str((Path(path).resolve().parent/profile[key]).resolve())
    return profile


def build_command(profile, instance_id, dataset, predictions, run_id, image):
    return [profile['python'], '-B', '-m', 'swebench.harness.run_evaluation',
            '--dataset_name', str(dataset), '--predictions_path', str(predictions),
            '--instance_ids', instance_id, '--split', 'test', '--max_workers', '1',
            '--timeout', '1800', '--run_id', run_id, '--namespace', 'swebench',
            '--instance_image_tag', image['tag'], '--cache_level', 'instance',
            '--clean', 'False', '--force_rebuild', 'False']


def docker_environment(profile):
    environment = os.environ.copy()
    environment.pop('DOCKER_CONTEXT', None)
    environment['DOCKER_HOST'] = profile['docker_host']
    return environment


def preflight(profile, directory, instance_ids=GOLD_IDS):
    blockers = []
    if platform.system() != 'Linux' or platform.machine().lower() not in {'x86_64', 'amd64'}:
        blockers.append('Requires qualified Linux x86_64 harness host, not Windows native')
    if profile['qualification_state'] != 'READY':
        blockers.append('Harness runtime profile is UNQUALIFIED')
    if not profile.get('python') or not profile.get('harness_repo'):
        blockers.append('Separate harness interpreter/source checkout not provisioned')
    if not isinstance(profile.get('docker_host'), str) or not re.fullmatch(
            r'(unix:///[^\s\x00]+|tcp://[A-Za-z0-9.\-:\[\]]+)', profile.get('docker_host') or ''):
        blockers.append('Explicit qualified Docker endpoint required; ambient CLI context is not sufficient')
    if (set(profile['images']) != set(GOLD_IDS) if tuple(instance_ids) == GOLD_IDS
            else not set(instance_ids) <= set(profile['images'])):
        blockers.append('All pinned instance image identities are required')
    if blockers:
        return {'ready': False, 'blockers': blockers, 'checks': []}
    checks = []
    environment = docker_environment(profile)
    def checked(argv, name, *, cwd=None):
        result = invoke(argv, directory, name, timeout=30, cwd=cwd, env=environment)
        checks.append(result)
        if result['status'] != 'OK':
            raise ValueError('Preflight command failed: '+name)
        return result['stdout']
    try:
        source = Path(profile['harness_repo']).resolve()
        git = ['git', '-c', 'safe.directory='+str(source), '-C', str(source)]
        if checked(git+['rev-parse', 'HEAD'], 'harness-head').strip() != HARNESS_COMMIT:
            raise ValueError('Harness source commit mismatch')
        if checked(git+['status', '--porcelain', '--untracked-files=all'], 'harness-clean').strip():
            raise ValueError('Harness source checkout is dirty')
        probe = ('import json,swebench; import swebench.harness.run_evaluation as m; '
                 'print(json.dumps({"version":swebench.__version__,"module":m.__file__}))')
        identity = json.loads(checked([profile['python'], '-B', '-c', probe], 'runtime-module'))
        if identity['version'] != '4.1.0' or Path(identity['module']).resolve() != source/'swebench/harness/run_evaluation.py':
            raise ValueError('Installed harness module differs from pinned checkout')
        help_text = checked([profile['python'], '-B', '-m', 'swebench.harness.run_evaluation', '--help'], 'runtime-help')
        if any(flag not in help_text for flag in FLAGS):
            raise ValueError('Pinned harness CLI capabilities mismatch')
        docker = json.loads(checked(['docker', 'info', '--format', '{{json .}}'], 'docker-info'))
        if docker['OSType'] != 'linux' or docker['Architecture'] not in {'x86_64', 'amd64'}:
            raise ValueError('Docker server must be Linux x86_64')
        sdk_probe = ('import docker,json; c=docker.from_env(); '
                     'print(json.dumps({"ID":c.info()["ID"]})); c.close()')
        sdk = json.loads(checked([profile['python'], '-B', '-c', sdk_probe], 'sdk-daemon'))
        if not isinstance(docker.get('ID'), str) or not docker['ID'] or sdk.get('ID') != docker['ID']:
            raise ValueError('Docker CLI and harness SDK address different daemons')
        for index, instance_id in enumerate(instance_ids):
            image = profile['images'][instance_id]
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', image['tag']):
                raise ValueError('Invalid image tag')
            expected = f"swebench/sweb.eval.x86_64.{instance_id.lower()}:{image['tag']}".replace('__', '_1776_')
            if image['reference'] != expected or not re.fullmatch(r'sha256:[0-9a-f]{64}', image['image_id']):
                raise ValueError('Image reference/identity mismatch')
            observed = json.loads(checked(['docker', 'image', 'inspect', expected], f'image-{index}'))
            if len(observed) != 1 or observed[0]['Id'] != image['image_id']:
                raise ValueError('Qualified image identity differs from Docker image')
            if image.get('repo_digest') not in (observed[0].get('RepoDigests') or []):
                raise ValueError('Qualified image digest missing or changed')
    except Exception:  # noqa: BLE001 -- report all external runtime/JSON failures with full traceback
        blockers.append(traceback.format_exc())
    return {'ready': not blockers, 'blockers': blockers, 'checks': checks,
            'docker_host': profile['docker_host']}


def _containers(name, directory, label, *, env=None):
    result = invoke(['docker', 'ps', '-aq', '--filter', 'name=^/'+re.escape(name)+'$'], directory, label, env=env)
    if result['status'] != 'OK':
        raise ValueError('Cannot establish container ownership/absence')
    return result['stdout'].split()


def cleanup_owned(name, image_id, directory, *, env=None):
    """Call only after reserving a fresh absent container name before launch."""
    try:
        ids = _containers(name, directory, 'cleanup-list', env=env)
        if not ids:
            return {'status': 'PASS', 'detail': 'No owned container remains'}
        if len(ids) != 1:
            raise ValueError('Ambiguous container ownership')
        result = invoke(['docker', 'container', 'inspect', ids[0]], directory, 'cleanup-inspect', env=env)
        if result['status'] != 'OK':
            raise ValueError('Cannot verify owned container')
        observed = json.loads(result['stdout'])
        if len(observed) != 1 or observed[0]['Name'] != '/'+name or observed[0]['Image'] != image_id:
            raise ValueError('Foreign container identity; refusing cleanup')
        result = invoke(['docker', 'rm', '-f', ids[0]], directory, 'cleanup-remove', env=env)
        if result['status'] != 'OK':
            raise ValueError('Owned container removal failed')
        if _containers(name, directory, 'cleanup-final', env=env):
            raise ValueError('Owned container still exists')
        return {'status': 'PASS', 'removed': ids[0]}
    except Exception:  # noqa: BLE001 -- resource cleanup must return diagnostic evidence, not lose task record
        return {'status': 'ERROR', 'traceback': traceback.format_exc()}


def input_integrity(prepared):
    try:
        if any(sha256(Path(prepared[key]).read_bytes()) != prepared[key+'_hash']
               for key in ('dataset', 'predictions')):
            raise ValueError('Evaluation inputs changed during harness execution')
        return {'ready': True, 'blockers': []}
    except (ValueError, OSError):
        return {'ready': False, 'blockers': [traceback.format_exc()]}


def _campaign(pilot_manifest, harness_profile, instance_ids, output_root, *, execute, dataset_parquet=None):
    output_root = Path(output_root).resolve()
    if output_root.is_relative_to(ROOT) and not output_root.is_relative_to(ROOT/'results'):
        raise ValueError('Evaluation gold outputs inside repository must be under ignored results/')
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:12]
    directory = output_root/run_id
    directory.mkdir(parents=True, exist_ok=False)
    print('RUN DIRECTORY:', directory, flush=True)
    clock = time.perf_counter()
    report = {'run_id': run_id, 'mode': 'execute' if execute else 'preflight', 'complete': False,
        'status': 'BLOCKED', 'started_utc': utc_now(), 'interpreter': sys.executable,
        'tasks': [{'instance_id': i, 'status': 'NOT_RUN'} for i in GOLD_IDS],
        'scope': 'official-gold-qualification-not-model-repair', 'resolved_count': 0}
    write_json(directory/'reservation.json', report)
    try:
        profile = load_profile(harness_profile)
        if dataset_parquet is not None:
            profile['dataset_parquet'] = str(Path(dataset_parquet).resolve())
        manifest = json.loads(Path(pilot_manifest).read_text(encoding='utf-8'))
        if tuple(instance_ids) != GOLD_IDS:
            raise ValueError('Qualification population differs from fixed first three pilot tasks')
        write_json(directory/'profile.json', profile)
        report['profile_hash'] = sha256((directory/'profile.json').read_bytes())
        report['manifest_hash'] = sha256(Path(pilot_manifest).read_bytes())
        readiness = preflight(profile, directory/'preflight')
        write_json(directory/'preflight.json', readiness)
        report['preflight'] = readiness
        if profile.get('dataset_parquet'):
            prepared = prepare_inputs(manifest, Path(profile['dataset_parquet']), directory/'inputs', instance_ids)
            report['inputs'] = prepared
        else:
            report['input_blocker'] = 'Pinned cached Parquet not configured'
        if readiness['ready'] and 'inputs' in report:
            environment = docker_environment(profile)
            rows = {r['instance_id']: r for r in json.loads(Path(prepared['dataset']).read_text(encoding='utf-8'))}
            for index, task in enumerate(report['tasks']):
                instance_id = task['instance_id']
                image = profile['images'][instance_id]
                invocation_id = 'vgw9-'+uuid.uuid4().hex
                task_dir = directory/instance_id
                task_dir.mkdir()
                command = build_command(profile, instance_id, prepared['dataset'], prepared['predictions'], invocation_id, image)
                task.update(argv=command, invocation_id=invocation_id, image=image, started_utc=utc_now())
                if not execute:
                    task.update(status='NOT_RUN', reason='Preflight only; --execute was not supplied')
                    write_json(task_dir/'record.json', task)
                    continue
                started = time.perf_counter()
                name = f'sweb.eval.{instance_id.lower()}.{invocation_id}'
                reserved = False
                try:
                    if _containers(name, task_dir, 'ownership-before', env=environment):
                        raise ValueError('Fresh invocation container already exists; refusing reuse')
                    reserved = True
                    result = invoke(command, task_dir, 'harness', timeout=3600, cwd=task_dir, env=environment)
                    task['process'] = result
                    if result['status'] in {'TIMEOUT', 'INTERRUPTED'}:
                        task.update(status='TIMEOUT' if result['status'] == 'TIMEOUT' else 'ERROR', reason=result['status'])
                    elif result['status'] != 'OK':
                        task.update(status='ERROR', reason='Harness subprocess failed')
                    else:
                        raw_dir = task_dir/'logs/run_evaluation'/invocation_id/MODEL_LABEL/instance_id
                        task.update(read_report(raw_dir, instance_id, rows[instance_id]['patch']))
                except Exception:  # noqa: BLE001 -- terminal evidence at external harness boundary
                    task.update(status='ERROR', traceback=traceback.format_exc())
                finally:
                    task['cleanup'] = cleanup_owned(name, image['image_id'], task_dir, env=environment) if reserved else {
                        'status': 'NOT_RUN', 'reason': 'No ownership reservation; never remove foreign resources'}
                    if task['cleanup']['status'] == 'ERROR':
                        task['grading_status_before_cleanup'] = task['status']
                        task['status'] = 'ERROR'
                    after = preflight(profile, task_dir/'runtime-after')
                    task['runtime_after'] = report['runtime_after'] = after
                    task['input_integrity'] = input_integrity(prepared)
                    if not task['input_integrity']['ready']:
                        after['ready'] = False
                        after['blockers'].extend(task['input_integrity']['blockers'])
                    if not after['ready']:
                        task['status'] = 'ERROR'
                    task.update(ended_utc=utc_now(), duration_seconds=time.perf_counter()-started)
                    write_json(task_dir/'record.json', task)
                resource_error = task['cleanup']['status'] == 'ERROR' or (
                    task.get('process', {}).get('process_terminated') is False
                    or task.get('process', {}).get('output_drain_complete') is False)
                if resource_error:
                    report['resource_error'] = True
                    for remaining in report['tasks'][index+1:]:
                        remaining['reason'] = 'Stopped after cleanup/process recovery failed'
                    break
                if not after['ready']:
                    for remaining in report['tasks'][index+1:]:
                        remaining['reason'] = 'Stopped after runtime/input integrity mismatch'
                    break
                if task.get('process', {}).get('status') == 'INTERRUPTED':
                    for remaining in report['tasks'][index+1:]:
                        remaining['reason'] = 'Stopped after owned subprocess interruption'
                    break
            report['resolved_count'] = sum(t['status'] == 'RESOLVED' for t in report['tasks'])
            report['status'] = ('QUALIFIED' if report['resolved_count'] >= 2 else 'UNMET') if execute else 'NOT_RUN'
            if execute and (report.get('resource_error') or not report.get('runtime_after', {}).get('ready', True)):
                report['status'] = 'ERROR'
    except Exception:  # noqa: BLE001 -- always preserve a terminal record for preparation/runtime exceptions
        report.update(status='ERROR', traceback=traceback.format_exc())
    except KeyboardInterrupt:
        report.update(status='ERROR', reason='Interrupted outside subprocess', traceback=traceback.format_exc())
    report.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter()-clock,
                  build_pull_test_seconds=None, timing_note='Not separately observed; see upstream raw logs')
    write_json(directory/'run_record.json', report)
    print('RESULT:', directory/'run_record.json', report['status'], flush=True)
    return report


def run_gold_validation(pilot_manifest: Path, *, harness_profile: Path,
                        instance_ids: tuple[str, ...], output_root: Path) -> dict:
    return _campaign(pilot_manifest, harness_profile, instance_ids, output_root, execute=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/m1/w9_pilot_manifest.json')
    parser.add_argument('--profile', type=Path, default=ROOT/'configs/m1/w9_harness_profile.json')
    parser.add_argument('--output-root', type=Path, default=ROOT/'results/m1/w9/m1-w9-4/runs')
    parser.add_argument('--dataset-parquet', type=Path)
    parser.add_argument('--execute', action='store_true', help='Explicitly run qualified official harness, never install/pull/setup')
    args = parser.parse_args(argv)
    result = _campaign(args.manifest, args.profile, GOLD_IDS, args.output_root,
                       execute=args.execute, dataset_parquet=args.dataset_parquet)
    return 0 if result['status'] in {'QUALIFIED', 'NOT_RUN'} else 2 if result['status'] == 'BLOCKED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
