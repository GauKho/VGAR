"""Copy approved M1 snapshots/bundles once; never overwrite modified inputs."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.evidence import atomic_json, begin_run, digest
from vgar_m2_w78.workspace import inventory
from vgar_m2_w78.diagnostics import exception_details

GRAPHS = {
    'single_file_login': 'sha256:e1fe94d21f10f112cd3a5e2a39f88e1fb26a760ee8ea3eaa6d3bac608d1ec371',
    'multi_file_invoice': 'sha256:1bbff47bc1ee5098b1f3d8f37dc5952faa9127224763e651c66630d838adb93e',
    'missing_links': 'sha256:ac135fa480d1f999d33e943fc36e003b76a570ba59ee5ba8cf495e76bb285c51',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'examples')
    args = parser.parse_args()
    run = begin_run(ROOT / 'results/setup', 'prepare-inputs', mode='offline')
    try:
        reference = Path(verify_reference()['root'])
        archived = reference / 'artifacts/m1/w7-w8/handoff-demos/20261014T072245Z-a8015356523c45cfa264244c07d252b0'
        cases = json.loads((reference / 'tests/fixtures/w7_w8_handoff/cases.json').read_text(encoding='utf-8'))['cases']
        registry = json.loads((ROOT / 'config/trusted_fixtures.json').read_text(encoding='utf-8'))
        for case in cases:
            name = case['task_id']
            source = reference / 'tests/fixtures/w7_w8_handoff' / case['repository']
            destination = args.destination / 'snapshots' / name
            if not destination.exists():
                shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            if inventory(destination) != {p:'sha256:'+h for p,h in registry[name]['files'].items()}:
                raise ValueError('Existing/source fixture differs; do not overwrite: ' + name)
            bundle = args.destination / 'handoffs' / name
            if not bundle.exists():
                shutil.copytree(archived / name / 'bundle', bundle)
            for file in ('context.json', 'context_manifest.json', 'test_links.json'):
                if (bundle / file).read_bytes() != (archived / name / 'bundle' / file).read_bytes():
                    raise ValueError('Existing handoff differs; do not overwrite')
            task = dict(task_id=name, issue_text=case['issue_text'], source_repo='../snapshots/'+name,
                bundle_directory='../handoffs/'+name, repo_key='demo/w7-w8/'+name, revision='fixture-v1',
                graph_version=GRAPHS[name], failing_selectors=case['failing_tests'], fallback_scope=case['selected_tests'],
                allowed_source_paths=registry[name]['allowed'], protected_paths=['tests', 'pytest.ini'], trusted_fixture=True)
            task_path = args.destination / 'tasks' / (name+'.json')
            if task_path.exists() and json.loads(task_path.read_text(encoding='utf-8')) != task:
                raise ValueError('Existing task config differs; do not overwrite')
            if not task_path.exists():
                atomic_json(task_path, task)
            run.stage(name, dict(status='PASS', graph_version=GRAPHS[name], source_hashes=inventory(destination),
                task_sha256=digest(task_path.read_bytes()), bundle_hashes={f:digest((bundle/f).read_bytes()) for f in ('context.json','context_manifest.json','test_links.json')}))
        run.finish('PASS', reference_revision='b8e2461635b81d1ae790445efea5c9757d91700a',
                   source_m1_run='20261014T072245Z-a8015356523c45cfa264244c07d252b0')
        atomic_json(args.destination / 'inputs_receipt.json', run.record)
    except Exception as error:
        run.finish('ERROR', reason=str(error), **exception_details(error))
    print(run.path)
    return 0 if run.record['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())

