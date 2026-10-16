"""Fetch missing immutable source archives, independently of graph/ranking/model code."""
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.dataset import read_repository_sources
from vgar.evaluation.retrieval.evidence import sha256, write_json, utc_now

manifest_path = ROOT / 'data/manifests/verified-c104f840cc67-dev-25.json'
manifest = json.loads(manifest_path.read_bytes())
missing_ids = set(json.loads((ROOT / 'artifacts/m2/w5-w6/source_cache_receipt.json').read_bytes())['missing'])
results = []
for task in manifest['tasks']:
    if task['instance_id'] not in missing_ids:
        continue
    sources, provenance = read_repository_sources(task, ROOT / 'data/repositories', network=True)
    results.append({'instance_id': task['instance_id'], 'status': 'VERIFIED',
                    'source_file_count': len(sources), 'provenance': provenance})
    write_json(ROOT / 'artifacts/m2/w5-w6/source_fetch_progress.json',
               {'manifest_hash': sha256(manifest_path.read_bytes()), 'ended_utc': utc_now(),
                'results': results, 'complete': len(results) == len(missing_ids)})
    print(f"Verified source {task['instance_id']}: {len(sources)} Python files", flush=True)
    del sources
    gc.collect()
print(json.dumps({'verified_downloads': len(results), 'weights_downloaded': False,
                  'benchmark_tests_executed': False}))
