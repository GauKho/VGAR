"""Reuse only hash/provenance-verified archives; never overwrite another experiment."""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import sha256, write_json

manifest = json.loads((ROOT / 'data/manifests/verified-c104f840cc67-dev-25.json').read_text(encoding='utf-8'))
previous = ROOT.parent / 'M2_week_5_6/data/repositories/archives'
target = ROOT / 'data/repositories/archives'
reused, missing = [], []
for task in manifest['tasks']:
    name = task['repo'].replace('/', '__') + '-' + task['base_commit'] + '.tar.gz'
    archive = previous / name
    sidecar = archive.with_suffix('.json')
    if not archive.exists() or not sidecar.exists():
        missing.append(task['instance_id'])
        continue
    meta = json.loads(sidecar.read_text(encoding='utf-8'))
    url = f"https://codeload.github.com/{task['repo']}/tar.gz/{task['base_commit']}"
    if meta['url'] != url or meta['base_commit'] != task['base_commit'] or meta['archive_hash'] != sha256(archive.read_bytes()):
        raise ValueError('Historical archive provenance mismatch: ' + name)
    target.mkdir(parents=True, exist_ok=True)
    for item in (archive, sidecar):
        destination = target / item.name
        if destination.exists():
            if sha256(destination.read_bytes()) != sha256(item.read_bytes()):
                raise ValueError('Existing cache differs: ' + item.name)
        else:
            shutil.copy2(item, destination)
    reused.append({'instance_id': task['instance_id'], 'archive_hash': meta['archive_hash'],
                   'from': str(archive), 'to': str(target / name)})
receipt = ROOT / 'artifacts/m2/w5-w6/source_cache_receipt.json'
if receipt.exists():
    raise ValueError('Do not overwrite an existing source cache receipt')
write_json(receipt, {'manifest_sha256': sha256((ROOT / 'data/manifests/verified-c104f840cc67-dev-25.json').read_bytes()),
                     'reused': reused, 'missing': missing,
                     'historical_metrics_reused': False})
print(json.dumps({'reused_archives': len(reused), 'missing_ids': missing, 'receipt': str(receipt)}))
