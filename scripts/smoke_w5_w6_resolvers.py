"""Check static/SCIP/LSP graph construction with installed, real runtimes."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.lsp_resolver import LspConfig
from vgar.graph.scip_resolver import ScipConfig, current_fingerprint
from vgar.graph.scip_profile import auxiliary_fingerprint
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.observability.graph_trace import GraphTrace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default=shutil.which('node') or 'node')
    parser.add_argument('--lsp-entry', type=Path, default=ROOT/'artifacts/m1/w5-w6/lsp-runtime/node_modules/pyright/langserver.index.js')
    parser.add_argument('--scip-entry', type=Path, default=ROOT/'artifacts/m1/w7-w8/scip-runtime/node_modules/@sourcegraph/scip-python/index.js')
    args = parser.parse_args()
    output = ROOT/'artifacts/m1/w5-w6/resolver-smoke'/uuid.uuid4().hex
    root = output/'repo'
    (root/'src').mkdir(parents=True)
    (root/'tests').mkdir()
    (root/'src/worker.py').write_text('''class Worker:
    def execute(self):
        return 1

def create_worker():
    return Worker()
''', encoding='utf-8')
    (root/'src/app.py').write_text('''from worker import create_worker

def invoke():
    worker = create_worker()
    "🚀"; return worker.execute()
''', encoding='utf-8')
    (root/'tests/test_worker.py').write_text('''from worker import create_worker

def test_execute():
    worker = create_worker()
    assert worker.execute() == 1
''', encoding='utf-8')
    node = str(Path(shutil.which(args.node) or args.node).resolve())
    lsp = LspConfig(command=(node, str(args.lsp_entry.resolve()), '--stdio'), strict=True,
                    output_directory=output/'lsp')
    scip = ScipConfig(command=(node, '-r', str(ROOT/'scripts/scip_windows_compat.cjs'), str(args.scip_entry.resolve())),
                      strict=True, output_directory=output/'scip')
    before = current_fingerprint(root), auxiliary_fingerprint(root)
    record = {'scope': 'W5-W6 resolver integration; controlled fixture, no repair benchmark', 'variants': {}}
    for label, options in [('static', {}), ('scip', {'scip': scip}), ('lsp', {'lsp': lsp}),
                            ('scip-lsp', {'scip': scip, 'lsp': lsp}),
                            ('scip-lsp-subset', {'scip': replace(scip, target_only='src'), 'lsp': lsp})]:
        graph = PythonGraphBuilder(repo_key='demo/w5-w6-resolvers', repository_revision='fixture',
            trace=GraphTrace(output/f'{label}.trace.jsonl'), **options).build(root)
        (output/f'{label}.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        store = SQLiteGraphStore(output/f'{label}.db')
        store.ingest(graph)
        loaded = store.load_document(graph['graph_version'])
        assert len(loaded['edges']) == len(graph['edges'])
        calls = [e for e in graph['edges'] if e['type']=='CALLS']
        targets = {n['id'] for n in graph['nodes'] if n['type']=='Method' and n['name']=='execute'}
        execute_calls = [e for e in calls if e['target_id'] in targets]
        links = [e for e in graph['edges'] if e['type']=='TESTS' and e['target_id'] in targets]
        if label == 'static':
            assert not execute_calls
        else:
            assert len(execute_calls) == 2 and len(links) == 1
        if label == 'scip-lsp-subset':
            assert graph['statistics']['resolver']['active'] == 'scip'
            assert graph['statistics']['resolver']['lsp_call_count'] == 1
        record['variants'][label] = {'graph_version':graph['graph_version'],
            'call_count':len(calls), 'execute_call_count':len(execute_calls), 'execute_test_links':len(links),
            'unresolved_call_count':graph['statistics']['unresolved_call_count'], 'resolver':graph['statistics']['resolver']}
        print(label, json.dumps({k:v for k,v in record['variants'][label].items() if k not in {'resolver','graph_version'}}), flush=True)
        assert before == (current_fingerprint(root), auxiliary_fingerprint(root))
    # Exercise hybrid fallback with an actually unavailable SCIP command. LSP
    # should still resolve missing calls; this run is explicitly not strict.
    recovery = PythonGraphBuilder(repo_key='demo/w5-w6-resolvers', repository_revision='fixture',
        scip=ScipConfig(command=(str(output/'missing.exe'),), output_directory=output/'missing-scip'),
        lsp=lsp, trace=GraphTrace(output/'recovery.trace.jsonl')).build(root)
    assert recovery['statistics']['resolver']['status'] == 'fallback'
    assert recovery['statistics']['resolver']['lsp_call_count'] == 2
    record['scip_failure_lsp_recovery'] = recovery['statistics']['resolver']
    record['sources_unchanged'] = before == (current_fingerprint(root), auxiliary_fingerprint(root))
    record['complete'] = True
    (output/'result.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print('PASS', output, flush=True)


if __name__ == '__main__':
    main()
