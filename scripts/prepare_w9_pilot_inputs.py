"""Prepare pinned cached inputs and full Git checkouts, without running target code."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.contracts.handoff import byte_digest
from vgar.evaluation.retrieval.dataset import select_tasks
from vgar.evaluation.harness.test_cmds import load_test_cmds, lookup
from vgar.evaluation.retrieval.pilot_manifest import DATASET_REVISION, PILOT_IDS, W10_SELECTION, make_manifest

W10_MANIFEST = ROOT/'configs/m1/w10_dev_manifest.json'


def locked_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError('Existing pinned input differs: '+str(path))
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def build_w10_manifest(rows, *, parquet_hash, count, table):
    """W10 dev population: pilot tasks removed, single- and multi-file, every (repo, version) has a pinned runner."""
    rows = [r for r in rows if r['instance_id'] not in PILOT_IDS]
    selected, _ = select_tasks(rows, count, split='dev', min_source_files=1)
    missing = []
    for row in selected:
        try:
            lookup(table, row['repo'], row['version'])
        except ValueError as error:
            missing.append(str(error))
    if missing:
        raise ValueError('W10 population has tasks without a pinned test command: ' + '; '.join(missing))
    return make_manifest(selected, parquet_hash=parquet_hash, selection_policy=W10_SELECTION)


def main():
    import pyarrow.parquet as pq
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-cache', type=Path, required=True)
    parser.add_argument('--tokenizer-cache', type=Path, required=True)
    parser.add_argument('--sources-root', type=Path, default=ROOT / 'data/w9/repositories')
    parser.add_argument('--prepare-sources', action='store_true')
    parser.add_argument('--population', choices=('w9-pilot', 'w10-dev'), default='w9-pilot')
    parser.add_argument('--count', type=int, default=50, help='w10-dev candidate count (locked)')
    parser.add_argument('--limit', type=int, help='prepare sources for the first N manifest tasks only')
    args = parser.parse_args()
    metadata = json.loads((args.dataset_cache/'hf_metadata.json').read_text(encoding='utf-8'))
    if metadata['sha'] != DATASET_REVISION or metadata['id'] != 'princeton-nlp/SWE-bench_Verified':
        raise ValueError('Wrong dataset snapshot metadata')
    parquet = args.dataset_cache/'test-00000-of-00001.parquet'
    # Compare against the already pinned download hash, not just a directory label.
    expected = 'sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
    actual = byte_digest(parquet.read_bytes())
    if actual != expected:
        raise ValueError('Cached Parquet differs from recorded download hash')
    rows = [r for batch in pq.ParquetFile(parquet).iter_batches(batch_size=64) for r in batch.to_pylist()]
    if args.population == 'w10-dev':
        manifest = build_w10_manifest(rows, parquet_hash=actual, count=args.count, table=load_test_cmds())
        locked_json(W10_MANIFEST, manifest)
    else:
        selected, _ = select_tasks(rows, 5, split='dev', min_source_files=2)
        manifest = make_manifest(selected, parquet_hash=actual)
        locked_json(ROOT/'configs/m1/w9_pilot_manifest.json', manifest)
    original = ROOT/'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json'
    tokenizer_manifest = json.loads(original.read_text(encoding='utf-8'))
    assets = (original.parent/tokenizer_manifest['assets_directory']).resolve()
    assets.mkdir(parents=True, exist_ok=True)
    for entry in tokenizer_manifest['files']:
        raw = (args.tokenizer_cache/entry['name']).read_bytes()
        if byte_digest(raw) != 'sha256:'+entry['sha256'] or len(raw) != entry['size']:
            raise ValueError('Cached tokenizer asset mismatch')
        destination = assets/entry['name']
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError('Existing tokenizer asset differs')
        if not destination.exists():
            shutil.copyfile(args.tokenizer_cache/entry['name'], destination)
    from vgar.graph.token_counter import LocalTokenizerCounter
    counter = LocalTokenizerCounter(original)
    print('INPUTS READY', manifest['manifest_hash'], counter.counter_label, flush=True)
    if not args.prepare_sources:
        return
    for task in manifest['tasks'][:args.limit]:
        started = time.perf_counter()
        directory = args.sources_root/task['instance_id']
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory = directory.resolve()
        git = ['git', '-c', 'safe.directory='+str(directory), '-c', 'core.autocrlf=false',
               '-c', 'core.longpaths=true', '-C', str(directory)]
        print('SOURCE START', task['instance_id'], flush=True)
        commands = []
        def run(argv, commands=commands):
            proc = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=False)
            commands.append({'argv':argv, 'stdout':proc.stdout, 'stderr':proc.stderr, 'exit_code':proc.returncode})
            if proc.returncode:
                raise RuntimeError(proc.stderr)
            return proc.stdout.strip()
        try:
            if not (directory/'.git').is_dir():
                if directory.exists() and any(directory.iterdir()):
                    raise ValueError('Refuse nonempty source directory without Git')
                run(['git', 'init', str(directory)])
            probe = subprocess.run(git+['rev-parse', '--verify', 'HEAD'], capture_output=True, check=False)
            if probe.returncode:
                if any(p.name != '.git' for p in directory.iterdir()):
                    raise ValueError('Refuse incomplete checkout containing source files')
                run(git+['fetch', '--depth=1', 'https://github.com/'+task['repo']+'.git', task['base_commit']])
                run(git+['checkout', '--detach', task['base_commit']])
            head = run(git+['rev-parse', 'HEAD'])
            if head != task['base_commit'] or run(git+['status', '--porcelain', '--untracked-files=all']):
                raise ValueError('Source commit/clean status mismatch')
            print('SOURCE READY', task['instance_id'], head, round(time.perf_counter()-started, 2), flush=True)
        finally:
            log = directory.parent/(task['instance_id']+'-prepare-'+str(time.time_ns())+'.json')
            log.write_text(json.dumps({'task':task, 'commands':commands,
                'duration_seconds':time.perf_counter()-started}, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
