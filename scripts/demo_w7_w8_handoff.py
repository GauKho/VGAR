"""Three static M1 handoff demos: one file, multiple files, and missing test links.

These fixtures intentionally contain bugs. PASS means validated handoff and
expected diagnostics, not a repaired repository or successful test execution.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/w7_w8_handoff'
sys.path.insert(0, str(ROOT / 'src'))

from vgar.contracts.consumer import HandoffTarget, receive_context_handoff
from vgar.contracts.handoff import SourceScope, byte_digest, read_source_inventory
from vgar.graph.builder import IGNORED_DIRECTORY_NAMES, PythonGraphBuilder
from vgar.graph.handoff import create_context_handoff, write_context_handoff
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.token_counter import LocalTokenizerCounter


def write_json(path: Path, value: dict) -> None:
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def source_hashes(root: Path) -> dict:
    sources = read_source_inventory(root, SourceScope(excluded_directories=sorted(IGNORED_DIRECTORY_NAMES)))
    return {path: byte_digest(data) for path, data in sources.items()}


def run_case(case: dict, fixtures: Path, output: Path, *,
             count_tokens: Callable[[str], int], counter_label: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    stage = 'copy_fixture'
    record = {'task_id': case['task_id'], 'scope': 'm1_handoff_no_model_no_patch_no_test_execution',
              'resolver_profile': 'static', 'output_directory': str(output.resolve())}
    events = []
    try:
        repository = (fixtures / case['repository']).resolve()
        if not repository.is_relative_to(fixtures.resolve()) or not repository.is_dir():
            raise ValueError('Demo repository must be a directory inside the fixture package')
        before = source_hashes(repository)
        original = output / 'original-snapshot'
        shutil.copytree(repository, original, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
        stage = 'build_and_retrieve'
        repo_key, revision = 'demo/w7-w8/' + case['task_id'], 'fixture-v1'
        document = PythonGraphBuilder(repo_key=repo_key, repository_revision=revision).build(original)
        write_json(output / 'graph.json', document)
        store = SQLiteGraphStore(output / 'graph.db')
        store.ingest(document)
        service = SQLiteGraphService(store, repository_root=original,
                                     count_tokens=count_tokens, counter_label=counter_label)
        anchors = service.find_task_anchors(case['issue_text'], case['failing_tests'],
            graph_version=document['graph_version'], task_id=case['task_id'])
        response = service.get_related_context([item['node_id'] for item in anchors['anchors']], 8000,
            graph_version=document['graph_version'], task_id=case['task_id'],
            issue_text=case['issue_text'], failing_tests=case['failing_tests'])
        stage = 'export_handoff'
        bundle = create_context_handoff(document, response, original,
            count_tokens=count_tokens, counter_label=counter_label, changed_paths=case['changed_paths'],
            failing_tests=case['failing_tests'], selected_tests=case['selected_tests'])
        exported = write_context_handoff(bundle, output / 'bundle')
        # Identity is approved from this task's graph before receiving the sidecars.
        target = HandoffTarget(task_id=case['task_id'], repo_key=repo_key,
                               repository_revision=revision, graph_version=document['graph_version'])
        write_json(output / 'approved-task-target.json', target.model_dump())
        clone = output / 'consumer-snapshot'
        shutil.copytree(original, clone)
        stage = 'receive_handoff'
        received = receive_context_handoff(exported, clone, target, count_tokens=count_tokens,
            counter_label=counter_label, changed_paths=case['changed_paths'])
        (output / 'repair-context.txt').write_bytes(received['context_text'].encode('utf-8'))
        write_json(output / 'test-inputs.json', received['test_inputs'])
        report = received['test_target_report']
        write_json(output / 'test-targets.json', report)
        stage = 'check_expectations'
        paths = {item['path'] for item in received['context']['items']}
        if not set(case['expected_context_paths']) <= paths:
            raise ValueError('Expected repair files are missing from retrieved context')
        statuses = {path: detail['mapping_status'] for path, detail in report['targets'].items()}
        if statuses != case['expected_mapping_status']:
            raise ValueError(f'Unexpected mapping status: {statuses}')
        if report['fallback_required'] != case['expected_fallback_required']:
            raise ValueError('Unexpected fallback requirement')
        if (not set(case['failing_tests']) <= set(report['candidate_tests']) or
                set(report['fallback_scope']) != set(case['selected_tests'])):
            raise ValueError('Explicit failing tests or selected scope were lost')
        if any(source_hashes(path) != before for path in (repository, original, clone)):
            raise ValueError('Demo altered a source snapshot')
        record.update(status='PASS', metadata=received['metadata'], mapping_status=statuses,
            graph_selectors=report['graph_selectors'], candidate_tests=report['candidate_tests'],
            fallback_scope=report['fallback_scope'], fallback_required=report['fallback_required'],
            coverage_verified=False, collection_verified=False, source_unchanged=True)
        events.append({'event': 'handoff_validated', **received['metadata']})
        events.append({'event': 'test_target_diagnostics', 'mapping_status': statuses,
                       'fallback_required': report['fallback_required'],
                       'fallback_available': report['fallback_available'],
                       'requires_fallback_input': report['requires_fallback_input']})
    except Exception as error:
        record.update(status='ERROR', error_stage=stage, error_type=type(error).__name__, reason=str(error))
        events.append({'event': 'demo_error', 'stage': stage, 'error_type': type(error).__name__, 'reason': str(error)})
    record['duration_seconds'] = time.perf_counter() - started
    write_json(output / 'result.json', record)
    (output / 'events.jsonl').write_bytes(''.join(json.dumps(
        {'task_id': case['task_id'], **event}, ensure_ascii=False) + '\n' for event in events).encode('utf-8'))
    return record


def main() -> int:
    cases = json.loads((FIXTURES / 'cases.json').read_text(encoding='utf-8'))['cases']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer-manifest', type=Path, required=True)
    parser.add_argument('--case', choices=[case['task_id'] for case in cases], action='append')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'artifacts/m1/w7-w8/handoff-demos')
    args = parser.parse_args()
    output = args.output_root.resolve() / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    record = {'scope': 'm1_handoff_no_model_no_patch_no_test_execution', 'output_directory': str(output)}
    try:
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        selected = [case for case in cases if not args.case or case['task_id'] in args.case]
        results = [run_case(case, FIXTURES, output / case['task_id'],
                    count_tokens=counter, counter_label=counter.counter_label) for case in selected]
        record.update(status='PASS' if all(case['status'] == 'PASS' for case in results) else 'ERROR',
                      tokenizer=counter.provenance, cases=results)
    except Exception as error:
        record.update(status='ERROR', error_type=type(error).__name__, reason=str(error))
    write_json(output / 'result.json', record)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
