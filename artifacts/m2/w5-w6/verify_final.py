"""One-off receipt check for the approved M2 W5-6 execution, not a product runner."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, source_fingerprint, utc_now, write_json

bm_dir, graph_dir, cmp_dir = [ROOT / arg for arg in sys.argv[1:4]]
bm, graph, cmp = [json.loads((p / 'result.json').read_text(encoding='utf-8'))
                  for p in (bm_dir, graph_dir, cmp_dir)]
manifest_path = ROOT / 'data/manifests/verified-c104f840cc67-dev-25.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
expected = {row['instance_id'] for row in manifest['tasks']}
assert len(expected) == 25
current = source_fingerprint(ROOT)
for run, directory in ((bm, bm_dir), (graph, graph_dir)):
    assert run['complete'] is True
    assert run['source']['digest'] == current['digest'], 'Source/profile changed; do not mix runs'
    assert run['config']['manifest_hash'] == sha256(manifest_path.read_bytes())
    assert {row['instance_id'] for row in run['task_results']} == expected
    assert len(run['task_results']) == 25
    assert run['config']['counter_is_fallback'] is False
    assert run['config']['budget_tokens'] == 8000
    for row in run['task_results']:
        artifact = directory / 'tasks' / (row['instance_id'] + '.json')
        if row['status'] == 'SUCCEEDED':
            assert sha256(artifact.read_bytes()) == row['artifact_hash']
assert cmp['complete'] and cmp['status'] == 'COMPARED'
assert cmp['bm25_run_hash'] == sha256((bm_dir / 'result.json').read_bytes())
assert cmp['graph_run_hash'] == sha256((graph_dir / 'result.json').read_bytes())
assert (cmp_dir / 'REPORT.md').is_file()
assert cmp['paired_tasks'] >= 20, 'Approved >=20 pairs gate not met'
assert set(cmp['per_task']['bm25']) == set(cmp['per_task']['graph'])
for metric, value in cmp['paired']['graph'].items():
    assert value['n'] <= cmp['paired_tasks']
assert (ROOT / 'artifacts/m2/w5-w6/native_handoff_final/result.json').is_file()
directory, receipt = new_run(ROOT / 'artifacts/m2/w5-w6/final-verification', 'm2-w56-acceptance')
receipt.update(status='PASS', complete=True, ended_utc=utc_now(), source=current,
    manifest_hash=sha256(manifest_path.read_bytes()), source_head='73814b8f89666c71b1911e42e98b8ecc7f6e3e99',
    runs={'bm25': str(bm_dir.relative_to(ROOT)), 'graph': str(graph_dir.relative_to(ROOT)),
          'comparison': str(cmp_dir.relative_to(ROOT))},
    attempted=25, paired_tasks=cmp['paired_tasks'], skipped=cmp['skipped'],
    counts={label: {'succeeded': sum(t['status'] == 'SUCCEEDED' for t in r['task_results']),
                   'failed': sum(t['status'] != 'SUCCEEDED' for t in r['task_results'])}
            for label, r in (('bm25', bm), ('graph', graph))},
    m2_test_hashes={str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in sorted((ROOT/'tests/m2').glob('*.py'))},
    owner_signoff='PENDING_M1_OWNER_REVIEW', exit_code=0)
write_json(directory / 'result.json', receipt)
print(json.dumps({'receipt': str(directory / 'result.json'), 'status': receipt['status'],
                  'counts': receipt['counts'], 'paired_tasks': receipt['paired_tasks'],
                  'owner_signoff': receipt['owner_signoff']}, ensure_ascii=False))
