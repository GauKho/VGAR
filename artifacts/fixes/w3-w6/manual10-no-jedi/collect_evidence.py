"""Read-only evidence cards for the ten cases chosen before dev25 completed.

This collector is NOT a manual review. The authored Vietnamese review records
the actual interpretation; automated integrity checks are reported separately.
No repository code is imported/executed, no gold is sent to a retrieval worker.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, write_json, utc_now
from vgar.evaluation.retrieval.chunks import decode_source, physical_lines, entities
from vgar.evaluation.retrieval.graph_arm import verify_python_tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph-run', required=True, type=Path)
    parser.add_argument('--bm25-run', required=True, type=Path)
    args = parser.parse_args()
    directory, result = new_run(Path(__file__).parent / 'evidence', 'manual-audit-input-checks')
    result.update(status='RUNNING', complete=False, reviews=[], inference='NOT_RUN',
                  review_author='Codex; manual interpretation in separate authored report',
                  manual_review_completed=False, graph_run=str(args.graph_run.resolve()),
                  bm25_run=str(args.bm25_run.resolve()))
    write_json(directory / 'result.json', result)
    started = time.perf_counter()
    try:
        manifest_path = ROOT / 'data/manifests/verified-c104f840cc67-dev-25.json'
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        runs = {name: json.loads((path / 'result.json').read_bytes()) for name, path in
                [('graph', args.graph_run), ('bm25', args.bm25_run)]}
        assert runs['graph']['config']['graph']['use_jedi'] is False
        assert runs['graph']['config']['counter_is_fallback'] is False
        succeeded = {row['instance_id'] for row in runs['graph']['task_results'] if row['status'] == 'SUCCEEDED'}
        chosen = [row for row in manifest['tasks'] if row['instance_id'] in succeeded][:10]
        assert len(chosen) == 10, 'Need ten completed graph task artifacts; do not synthesize missing contexts'
        result.update(manifest_hash=sha256(manifest_bytes), selection_policy=
                      'First 10 SUCCEEDED graph tasks in manifest order, declared before reading paired deltas; selection does not use accuracy. Failed tasks stay in the benchmark denominator and are reported separately.',
                      selected_ids=[row['instance_id'] for row in chosen],
                      selected_repositories=sorted({row['repo'] for row in chosen}),
                      graph_run_complete_at_collection=runs['graph']['complete'],
                      graph_failures_at_collection=[row for row in runs['graph']['task_results'] if row['status'] != 'SUCCEEDED'])
        for row in chosen:
            iid = row['instance_id']
            g_path = args.graph_run / 'tasks' / (iid + '.json')
            b_path = args.bm25_run / 'tasks' / (iid + '.json')
            g_raw, b_raw = g_path.read_bytes(), b_path.read_bytes()
            g, b = json.loads(g_raw), json.loads(b_raw)
            for kind, raw in [('graph', g_raw), ('bm25', b_raw)]:
                summary = next(r for r in runs[kind]['task_results'] if r['instance_id'] == iid)
                assert summary['status'] == 'SUCCEEDED'
                assert sha256(raw) == summary['artifact_hash']
            for key in ('query_hash', 'patch_hash', 'corpus_hash', 'base_commit', 'repository', 'gold'):
                assert g[key] == b[key], (iid, key)
            assert g['inference'] == 'NOT_RUN'
            assert g['query_hash'] == row['query_hash']
            patch_path = ROOT / row['gold_patch_path']
            patch_raw = patch_path.read_bytes()
            # The existing evaluator binds patch *text* read with universal
            # newlines; source tree/task artifact guards bind exact raw bytes.
            patch = patch_path.read_text(encoding='utf-8')
            assert sha256(patch) == row['patch_hash']
            tree = Path(g['source_tree']['path'])
            tree_meta = verify_python_tree(tree)
            assert tree_meta['tree_hash'] == g['source_tree']['tree_hash']
            assert tree_meta['commit'] == row['base_commit'] and tree_meta['repo'] == row['repo']
            card = dict(instance_id=iid, repository=row['repo'], base_commit=row['base_commit'],
                        issue=row['problem_statement'], developer_patch=patch,
                        patch_text_hash=sha256(patch), patch_checkout_raw_hash=sha256(patch_raw),
                        gold=g['gold'], graph_task_path=str(g_path.resolve()),
                        bm25_task_path=str(b_path.resolve()), graph_task_hash=sha256(g_raw),
                        bm25_task_hash=sha256(b_raw), source_provenance=g['source_provenance'],
                        source_tree=g['source_tree'], inference='NOT_RUN',
                        graph_arms={}, bm25_metrics=b['metrics'], gold_base_definitions=[])
            for arm in ('graph', 'graph_f2p'):
                value = g['arms'][arm]
                file5, function5, seen_files, seen_functions = [], [], set(), set()
                for item in value['ranked']:
                    if item['path'] not in seen_files:
                        seen_files.add(item['path'])
                        if len(file5) < 5:
                            file5.append(item)
                    if item['function_id'] and item['function_id'] not in seen_functions:
                        seen_functions.add(item['function_id'])
                        if len(function5) < 5:
                            function5.append(item)
                selected = {item['item_id']: item for item in [*value['ranked'][:5], *file5, *function5]}
                verified = {}
                for item in selected.values():
                    raw = (tree / item['path']).read_bytes()
                    lines = physical_lines(decode_source(raw), keepends=True)
                    start, end = item['lines']
                    snippet = ''.join(lines[start - 1:end])
                    assert sha256(snippet) == item['snippet_sha256'], (iid, item['item_id'])
                    verified[item['item_id']] = dict(item, verified_source_sha256=sha256(raw), snippet=snippet)
                assert value['metrics']['context_tokens'] <= 8000
                card['graph_arms'][arm] = dict(metrics=value['metrics'],
                    top5_items=[verified[item['item_id']] for item in value['ranked'][:5]],
                    top5_files=[verified[item['item_id']] for item in file5],
                    top5_functions=[verified[item['item_id']] for item in function5],
                    anchors=value['anchors'], unmapped=value['unmapped'], excluded=value['excluded'],
                    diagnostics=value['diagnostics'], packed=value['scoring']['packed'])
            for fid in g['gold']['gold_functions']:
                path, symbol = fid.split('::', 1)
                raw = (tree / path).read_bytes()
                source = decode_source(raw)
                definition = next(d for d in entities(path, source) if d['parent_id'] == fid)
                lines = physical_lines(source, keepends=True)
                start, end = definition['start_line'], definition['end_line']
                card['gold_base_definitions'].append(dict(definition, source_sha256=sha256(raw),
                    excerpt=''.join(lines[start - 1:min(end, start + 11)])))
            for path in g['gold']['unretrievable_files']:
                assert not (tree / path).exists()
            card.update(technical_integrity_status='PASS', manual_status='PENDING_INTERPRETATION',
                        duration_seconds=g['duration_seconds'], peak_rss_bytes=g['peak_rss_bytes'])
            result['reviews'].append(card)
            write_json(directory / 'result.json', result)
            print(iid + ': integrity PASS; manual interpretation separate', flush=True)
        result.update(status='PASS', exit_code=0)
    except Exception as exc:
        result.update(status='ERROR', exit_code=1, error_class=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc())
    finally:
        result.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        write_json(directory / 'result.json', result)
    print('evidence: ' + str(directory), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
