"""Pinned W9 dev pilot and the explicit no-gold producer boundary."""
from __future__ import annotations

import json
from pathlib import Path

from vgar.contracts.handoff import payload_digest
from vgar.evaluation.retrieval.dataset import require_split, split_of, validate_task
from vgar.evaluation.retrieval.evidence import sha256

DATASET_REVISION = 'c104f840cc67f8b6eec6f759ebc8b2693d585d4a'
PILOT_IDS = ('astropy__astropy-13398', 'django__django-11138', 'matplotlib__matplotlib-14623',
             'pydata__xarray-3305', 'pylint-dev__pylint-4551')


def project_retrieval_task(row: dict) -> dict:
    validate_task(row)
    return {k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')} | {
        'query_hash': sha256(row['problem_statement']), 'split': split_of(row['instance_id'])}


def make_manifest(rows: list[dict], *, parquet_hash: str) -> dict:
    result = {'dataset_id': 'princeton-nlp/SWE-bench_Verified', 'dataset_revision': DATASET_REVISION,
              'split': 'dev', 'selection_policy': 'repo_round_robin_then_instance_id_v1:multi-file',
              'query_policy': 'problem_statement_only_no_hints_or_gold', 'parquet_hash': parquet_hash,
              'tasks': [project_retrieval_task(row) for row in rows]}
    result['manifest_hash'] = payload_digest(result)
    validate_manifest(result)
    return result


def validate_manifest(manifest: dict, *, expected_hash: str | None = None) -> None:
    body = {k: v for k, v in manifest.items() if k != 'manifest_hash'}
    if payload_digest(body) != manifest.get('manifest_hash'):
        raise ValueError('Pilot manifest hash mismatch')
    if expected_hash is not None and manifest['manifest_hash'] != expected_hash:
        raise ValueError('Pilot manifest differs from the approved generated input')
    if manifest.get('dataset_revision') != DATASET_REVISION or manifest.get('dataset_id') != 'princeton-nlp/SWE-bench_Verified':
        raise ValueError('Pilot dataset differs from approved snapshot')
    require_split(manifest)
    if tuple(row['instance_id'] for row in manifest['tasks']) != PILOT_IDS:
        raise ValueError('Pilot task population/order differs from approved five tasks')
    for row in manifest['tasks']:
        if row != project_retrieval_task(row):
            raise ValueError('Retrieval task contains unapproved fields or wrong query hash')


def require_tokenizer_identity(path: Path, reference: Path) -> None:
    """Permit relocation, never a different model/revision/asset bundle."""
    def identity(location):
        data = json.loads(Path(location).read_text(encoding='utf-8'))
        return {k: data[k] for k in ('model_id', 'revision', 'counting_policy', 'weights_downloaded')} | {
            'files': sorted((f['name'], f['size'], f['sha256']) for f in data['files'])}
    if identity(path) != identity(reference):
        raise ValueError('Tokenizer identity differs from approved Qwen3 snapshot')
