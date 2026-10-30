"""Grade repair candidates (the engine's applied.diff) with the pinned official harness, one invocation each."""
from __future__ import annotations

import json
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from vgar.evaluation.harness import gold_inputs, official
from vgar.evaluation.harness.gold_inputs import PARQUET_HASH, ROOT, select_rows, write_json
from vgar.evaluation.harness.reports import read_report
from vgar.evaluation.retrieval.evidence import sha256


def collect_candidates(exp_dir: Path) -> list[dict]:
    """Latest TERMINAL attempt per pair whose engine run applied a patch; the graded diff is applied.diff."""
    from vgar.evaluation.repair.runner import read_attempts
    exp_dir = Path(exp_dir)
    found = []
    for (task_id, variant_id), items in sorted(read_attempts(exp_dir).items()):
        # Same choice as aggregate: the newest TERMINAL attempt (a later interrupted rerun does not hide it).
        terminal = [a for a in items if a['state'] == 'TERMINAL']
        record = terminal[-1] if terminal else None
        if record is None or not record.get('engine_run_dir'):
            continue
        run_dir = Path(record['engine_run_dir'])
        run = json.loads((run_dir/'run_record.json').read_text(encoding='utf-8'))
        if run['stages'].get('apply', {}).get('status') != 'PASS' or not (run_dir/'applied.diff').is_file():
            continue
        patch = (run_dir/'applied.diff').read_bytes().decode('utf-8')
        found.append({'experiment_id': exp_dir.name, 'task_id': task_id, 'variant_id': variant_id,
                      'arm': record.get('arm'), 'run_id': run['run_id'], 'model_patch': patch,
                      'patch_sha256': sha256(patch)})
    return found


def _label(candidate):
    return 'vgar-w10-' + candidate['variant_id']


def grade_candidates(manifest_path, harness_profile, exp_dirs, output_root, *, approved_manifest, execute,
                     dataset_parquet=None) -> dict:
    output_root = Path(output_root).resolve()
    if output_root.is_relative_to(ROOT) and not output_root.is_relative_to(ROOT/'results'):
        raise ValueError('Harness outputs inside repository must be under ignored results/')
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:12]
    directory = output_root/run_id
    directory.mkdir(parents=True, exist_ok=False)
    candidates = sorted((c for e in exp_dirs for c in collect_candidates(e)),
                        key=lambda c: (c['experiment_id'], c['task_id'], c['variant_id']))
    report = {'run_id': run_id, 'directory': str(directory), 'mode': 'execute' if execute else 'preflight',
              'status': 'BLOCKED', 'grades': [], 'scope': 'official-harness-grading-of-applied-candidates'}
    try:
        profile = official.load_profile(harness_profile)
        if dataset_parquet is not None:
            profile['dataset_parquet'] = str(Path(dataset_parquet).resolve())
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        ids = sorted({c['task_id'] for c in candidates})
        if not candidates:
            report['status'] = 'COMPLETE'
            return report
        readiness = official.preflight(profile, directory/'preflight', instance_ids=ids)
        report['preflight'] = readiness
        raw = Path(profile['dataset_parquet']).read_bytes()
        if gold_inputs.sha256(raw) != PARQUET_HASH or manifest.get('parquet_hash') != PARQUET_HASH:
            raise ValueError('Cached Parquet hash differs from approved snapshot')
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows = select_rows(pq.read_table(pa.BufferReader(raw)).to_pylist(), manifest, ids,
                           approved_manifest=approved_manifest)
        dataset = directory/'dataset.json'
        write_json(dataset, rows)
        for index, candidate in enumerate(candidates):
            task_dir = directory/f'{index:03d}-{candidate["task_id"]}-{candidate["variant_id"]}'
            task_dir.mkdir()
            predictions = task_dir/'predictions.jsonl'
            predictions.write_text(json.dumps({'instance_id': candidate['task_id'], 'model_name_or_path': _label(candidate),
                                               'model_patch': candidate['model_patch']}, ensure_ascii=False)+'\n',
                                   encoding='utf-8', newline='\n')
            report['grades'].append({k: candidate[k] for k in ('experiment_id', 'task_id', 'variant_id', 'run_id', 'patch_sha256')}
                                    | {'predictions': str(predictions), 'harness_status': 'NOT_RUN', 'report_ref': None})
        if not readiness['ready'] or not execute:
            report['status'] = 'NOT_RUN' if readiness['ready'] else 'BLOCKED'
            return report
        environment = official.docker_environment(profile)
        for index, (candidate, grade) in enumerate(zip(candidates, report['grades'])):
            if not _grade_one(profile, environment, candidate, grade, Path(grade['predictions']).parent, dataset):
                for remaining in report['grades'][index+1:]:
                    remaining['reason'] = 'Stopped after cleanup/process/runtime failure'
                break
        report['status'] = 'COMPLETE' if all(g['harness_status'] != 'NOT_RUN' for g in report['grades']) else 'ERROR'
    except Exception:  # noqa: BLE001 -- always keep a terminal grading record
        report.update(status='ERROR', traceback=traceback.format_exc())
    finally:
        write_json(directory/'grades.json', report)
    return report


def _grade_one(profile, environment, candidate, grade, task_dir, dataset) -> bool:
    """One official invocation; returns False when later invocations must not run."""
    instance_id, image = candidate['task_id'], profile['images'][candidate['task_id']]
    invocation_id = 'vgw10-'+uuid.uuid4().hex
    command = official.build_command(profile, instance_id, dataset, task_dir/'predictions.jsonl', invocation_id, image)
    name = f'sweb.eval.{instance_id.lower()}.{invocation_id}'
    started, reserved, process = time.perf_counter(), False, {}
    try:
        if official._containers(name, task_dir, 'ownership-before', env=environment):
            raise ValueError('Fresh invocation container already exists; refusing reuse')
        reserved = True
        process = official.invoke(command, task_dir, 'harness', timeout=3600, cwd=task_dir, env=environment)
        if process['status'] != 'OK':
            grade.update(harness_status='ERROR', reason='Harness subprocess '+process['status'])
        else:
            raw_dir = task_dir/'logs/run_evaluation'/invocation_id/_label(candidate)/instance_id
            result = read_report(raw_dir, instance_id, candidate['model_patch'])
            grade.update(harness_status=result['status'] if result['status'] in ('RESOLVED', 'UNRESOLVED') else 'ERROR',
                         reason=result.get('reason'), report_ref=result.get('raw_report'))
    except Exception:  # noqa: BLE001 -- external harness boundary
        grade.update(harness_status='ERROR', traceback=traceback.format_exc())
    finally:
        grade['cleanup'] = official.cleanup_owned(name, image['image_id'], task_dir, env=environment) if reserved else {
            'status': 'NOT_RUN', 'reason': 'No ownership reservation'}
        grade['duration_seconds'] = time.perf_counter()-started
    return (grade['cleanup']['status'] != 'ERROR' and process.get('status') != 'INTERRUPTED'
            and process.get('process_terminated') is not False and process.get('output_drain_complete') is not False)
