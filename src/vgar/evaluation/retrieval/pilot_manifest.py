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
W10_SELECTION = 'repo_round_robin_then_instance_id_v1:min1-excluding-w9-pilot'


def project_retrieval_task(row: dict, *, with_version: bool = False) -> dict:
    validate_task(row)
    # version picks the pinned upstream test command; it is not gold or oracle data.
    keys = ('instance_id', 'repo', 'base_commit', 'problem_statement') + (('version',) if with_version else ())
    return {k: row[k] for k in keys} | {
        'query_hash': sha256(row['problem_statement']), 'split': split_of(row['instance_id'])}


def make_manifest(rows: list[dict], *, parquet_hash: str,
                  selection_policy: str = 'repo_round_robin_then_instance_id_v1:multi-file') -> dict:
    with_version = selection_policy == W10_SELECTION
    result = {'dataset_id': 'princeton-nlp/SWE-bench_Verified', 'dataset_revision': DATASET_REVISION,
              'split': 'dev', 'selection_policy': selection_policy,
              'query_policy': 'problem_statement_only_no_hints_or_gold', 'parquet_hash': parquet_hash,
              'tasks': [project_retrieval_task(row, with_version=with_version) for row in rows]}
    result['manifest_hash'] = payload_digest(result)
    validate_manifest(result, expected_ids=None if with_version else PILOT_IDS)
    return result


def validate_manifest(manifest: dict, *, expected_hash: str | None = None,
                      expected_ids: tuple[str, ...] | None = PILOT_IDS) -> None:
    body = {k: v for k, v in manifest.items() if k != 'manifest_hash'}
    if payload_digest(body) != manifest.get('manifest_hash'):
        raise ValueError('Pilot manifest hash mismatch')
    if expected_hash is not None and manifest['manifest_hash'] != expected_hash:
        raise ValueError('Pilot manifest differs from the approved generated input')
    if manifest.get('dataset_revision') != DATASET_REVISION or manifest.get('dataset_id') != 'princeton-nlp/SWE-bench_Verified':
        raise ValueError('Pilot dataset differs from approved snapshot')
    require_split(manifest)
    if expected_ids is not None and tuple(row['instance_id'] for row in manifest['tasks']) != expected_ids:
        raise ValueError('Pilot task population/order differs from approved five tasks')
    with_version = manifest.get('selection_policy') == W10_SELECTION
    for row in manifest['tasks']:
        if row != project_retrieval_task(row, with_version=with_version):
            raise ValueError('Retrieval task contains unapproved fields or wrong query hash')


def require_tokenizer_identity(path: Path, reference: Path) -> None:
    """Permit relocation, never a different model/revision/asset bundle."""
    def identity(location):
        data = json.loads(Path(location).read_text(encoding='utf-8'))
        return {k: data[k] for k in ('model_id', 'revision', 'counting_policy', 'weights_downloaded')} | {
            'files': sorted((f['name'], f['size'], f['sha256']) for f in data['files'])}
    if identity(path) != identity(reference):
        raise ValueError('Tokenizer identity differs from approved Qwen3 snapshot')
