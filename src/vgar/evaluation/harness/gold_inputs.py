"""Pinned gold data boundary. Never feed this module's outputs to retrieval."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from vgar.evaluation.retrieval.evidence import sha256
from vgar.evaluation.retrieval.pilot_manifest import PILOT_IDS, validate_manifest

ROOT = Path(__file__).resolve().parents[4]
GOLD_IDS = PILOT_IDS[:3]
PARQUET_HASH = 'sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'


def write_json(path: Path, data) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)


def select_gold_rows(rows, manifest, instance_ids):
    approved = json.loads((ROOT/'configs/m1/w9_pilot_manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest, expected_hash=approved['manifest_hash'])
    if tuple(instance_ids) != GOLD_IDS:
        raise ValueError('Gold qualification requires the fixed first three pilot IDs in order')
    indexed = {}
    for row in rows:
        key = row['instance_id']
        if key in indexed:
            raise ValueError('Duplicate dataset instance')
        indexed[key] = row
    selected = []
    for task in manifest['tasks'][:3]:
        row = copy.deepcopy(indexed.get(task['instance_id']))
        if row is None or any(row.get(k) != task[k] for k in ('repo', 'base_commit', 'problem_statement')):
            raise ValueError('Cached task identity differs from pilot manifest')
        if sha256(row['problem_statement']) != task['query_hash']:
            raise ValueError('Cached query hash mismatch')
        if not isinstance(row.get('patch'), str) or not row['patch'].strip():
            raise ValueError('Missing gold patch')
        if not isinstance(row.get('test_patch'), str) or not isinstance(row.get('version'), str) or not row['version']:
            raise ValueError('Missing harness test patch or repository version')
        for key in ('FAIL_TO_PASS', 'PASS_TO_PASS'):
            value = json.loads(row[key]) if isinstance(row.get(key), str) else row.get(key)
            if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
                raise ValueError('Invalid harness test metadata')
            row[key] = value
        if not row['FAIL_TO_PASS']:
            raise ValueError('Gold qualification needs nonempty FAIL_TO_PASS')
        selected.append(row)
    return selected


def prepare_inputs(manifest, cached_parquet: Path, directory: Path, instance_ids):
    if directory.exists():
        raise FileExistsError(directory)
    raw = Path(cached_parquet).read_bytes()
    if sha256(raw) != PARQUET_HASH or manifest.get('parquet_hash') != PARQUET_HASH:
        raise ValueError('Cached Parquet hash differs from approved snapshot')
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = select_gold_rows(pq.read_table(pa.BufferReader(raw)).to_pylist(), manifest, instance_ids)
    directory.mkdir(parents=True, exist_ok=False)
    dataset, predictions = directory/'dataset.json', directory/'predictions.jsonl'
    write_json(dataset, rows)
    with predictions.open('x', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps({'instance_id': row['instance_id'], 'model_name_or_path': 'vgar-w9-gold',
                                     'model_patch': row['patch']}, ensure_ascii=False)+'\n')
    result = {'dataset': str(dataset.resolve()), 'predictions': str(predictions.resolve()),
        'cached_parquet': str(Path(cached_parquet).resolve()), 'parquet_hash': sha256(raw),
        'dataset_hash': sha256(dataset.read_bytes()), 'predictions_hash': sha256(predictions.read_bytes()),
        'project_split': 'dev', 'upstream_partition': 'test', 'manifest_hash': manifest['manifest_hash'],
        'tasks': [{'instance_id': r['instance_id'], 'base_commit': r['base_commit'],
                   'patch_hash': sha256(r['patch']), 'test_patch_hash': sha256(r['test_patch'])} for r in rows]}
    write_json(directory/'inputs.json', result)
    return result
