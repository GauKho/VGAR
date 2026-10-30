"""Sequential, bounded paired W9 exports. No LLM, target pytest, or harness."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.contracts.handoff import byte_digest, payload_digest
from vgar.evaluation.retrieval.pilot_export import export_task, write_json
from vgar.evaluation.retrieval.pilot_manifest import (
    require_tokenizer_identity,
    validate_manifest,
)
from vgar.graph.token_counter import LocalTokenizerCounter

# Retrieval evaluation profile (8000) and the M3 repair profile (smaller budget, D5 in docs/m3_w9_decisions.md).
APPROVED_PROFILES = (ROOT/'configs/m1/w9_bundle_profile.json', ROOT/'configs/m1/w9_bundle_profile_repair.json')


def profile_budget(profile):
    budget = profile.get('budget_tokens')
    if type(budget) is not int or budget <= 0:
        raise ValueError('Profile snippet budget must be a positive integer')
    return budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--tokenizer-manifest', type=Path, required=True)
    parser.add_argument('--sources-root', type=Path, default=ROOT/'data/w9/repositories')
    parser.add_argument('--output-root', type=Path, default=ROOT/'artifacts/m1/w9/bundles')
    parser.add_argument('--worker', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--directory', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--approved-manifest', type=Path, default=ROOT/'configs/m1/w9_pilot_manifest.json')
    parser.add_argument('--limit', type=int, help='export only the first N manifest tasks')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    approved_manifest = json.loads(args.approved_manifest.read_text(encoding='utf-8'))
    pilot = args.approved_manifest.resolve() == (ROOT/'configs/m1/w9_pilot_manifest.json').resolve()
    validate_manifest(manifest, expected_hash=approved_manifest['manifest_hash'],
                      **({} if pilot else {'expected_ids': None}))
    tasks = manifest['tasks'][:args.limit]
    require_tokenizer_identity(args.tokenizer_manifest, ROOT/'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json')
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    approved = [json.loads(p.read_text(encoding='utf-8')) for p in APPROVED_PROFILES if p.is_file()]
    if profile not in approved:
        raise ValueError('Profile differs from implementation pinned W9 profile')
    if args.worker is not None:
        task = tasks[args.worker]
        source = (args.sources_root/task['instance_id']).resolve()
        git = ['git', '-c', 'safe.directory='+str(source), '-C', str(source)]
        def check_source():
            head = subprocess.check_output(git+['rev-parse','HEAD']).decode().strip()
            dirty = subprocess.check_output(git+['status','--porcelain','--untracked-files=all'])
            if head != task['base_commit'] or dirty.strip():
                raise ValueError('Full source checkout commit/integrity mismatch')
        check_source()
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        result = export_task(task, source, args.directory, count_tokens=counter, counter_label=counter.counter_label,
                             budget_tokens=profile_budget(profile))
        check_source()
        write_json(args.directory/'worker_result.json', {'task':result, 'tokenizer':counter.provenance,
            'source_head':task['base_commit'], 'source_unchanged':True})
        return 0 if all(a['status']=='PASS' for a in result['arms']) else 1
    run = args.output_root.resolve()/(datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12])
    run.mkdir(parents=True, exist_ok=False)
    print('RUN DIRECTORY:', run, flush=True)
    write_json(run/'pilot_manifest.json', manifest)
    write_json(run/'profile.json', profile)
    records = []
    clock = time.perf_counter()
    started = datetime.now(UTC).isoformat()
    for index, task in enumerate(tasks):
        directory = run/task['instance_id']
        command = [sys.executable,'-B',str(Path(__file__).resolve()),'--manifest',str(args.manifest.resolve()),
            '--profile',str(args.profile.resolve()),'--tokenizer-manifest',str(args.tokenizer_manifest.resolve()),
            '--sources-root',str(args.sources_root.resolve()),'--worker',str(index),'--directory',str(directory),
            '--approved-manifest',str(args.approved_manifest.resolve()),
            *(['--limit',str(args.limit)] if args.limit is not None else [])]
        task_start, task_clock = datetime.now(UTC).isoformat(), time.perf_counter()
        print('START', task['instance_id'], flush=True)
        timed_out, error = False, None
        try:
            with (run/(task['instance_id']+'.stdout.log')).open('wb') as out, (run/(task['instance_id']+'.stderr.log')).open('wb') as err:
                completed = subprocess.run(command, stdout=out, stderr=err, timeout=600, check=False)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out, exit_code, error = True, None, 'TASK_EXPORT_TIMEOUT'
        except OSError:
            exit_code, error = None, traceback.format_exc()
        worker_path = directory/'worker_result.json'
        try:
            worker = json.loads(worker_path.read_text(encoding='utf-8')) if worker_path.exists() else None
            if worker is not None and (worker.get('source_unchanged') is not True
                    or [a['arm'] for a in worker['task']['arms']] != ['graph','bm25']):
                raise ValueError('Incomplete worker source/arm record')
        except (ValueError, OSError, KeyError, TypeError):
            worker, error = None, traceback.format_exc()
        success = exit_code == 0 and worker is not None and all(a['status']=='PASS' for a in worker['task']['arms'])
        arms = worker['task']['arms'] if worker else [{'arm':a, 'status':'ERROR',
            'reason':error or 'WORKER_FAILED: see stderr log'} for a in ('graph','bm25')]
        if worker is None:
            for arm in arms:
                if arm['status'] == 'PASS':
                    arm.update(status='ERROR', reason='Worker did not finalize source integrity')
        record = {'task_id':task['instance_id'], 'argv':command, 'status':'PASS' if success else 'ERROR',
            'arms':arms, 'timed_out':timed_out, 'exit_code':exit_code, 'error':error,
            'started_utc':task_start, 'ended_utc':datetime.now(UTC).isoformat(),
            'duration_seconds':time.perf_counter()-task_clock}
        records.append(record)
        write_json(run/(task['instance_id']+'.json'), record)
        print('END', task['instance_id'], record['status'], round(record['duration_seconds'],2), flush=True)
    passed = sum(a['status']=='PASS' for r in records for a in r['arms'])
    accepted = sum(len(r['arms']) for r in records if r['status']=='PASS')
    expected = 2*len(tasks)
    success = passed == expected and accepted == expected
    report = {'scope':'w9_dual_arm_export_no_generation_no_collection', 'complete':True,
        'status':'PASS' if success else 'INCOMPLETE', 'passed_bundles':passed,
        'accepted_bundles':accepted, 'expected_bundles':expected,
        'tasks':records, 'manifest_hash':manifest['manifest_hash'], 'profile_hash':payload_digest(profile),
        'tokenizer_manifest_hash':byte_digest(args.tokenizer_manifest.read_bytes()),
        'started_utc':started, 'ended_utc':datetime.now(UTC).isoformat(),
        'duration_seconds':time.perf_counter()-clock, 'output_directory':str(run)}
    write_json(run/'run_record.json', report)
    print('RESULT:', run/'run_record.json', f'{passed}/{expected}', flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
