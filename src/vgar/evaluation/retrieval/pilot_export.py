"""One task's paired W9 exports; consumers run independently on exact source."""
from __future__ import annotations

import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from vgar.contracts.handoff import byte_digest
from vgar.evaluation.retrieval.bm25_handoff import (
    create_bm25_handoff,
    response_for,
    test_scope,
    usable_node_ids,
)
from vgar.evaluation.retrieval.pilot_manifest import project_retrieval_task
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.handoff import create_context_handoff, write_context_handoff
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder
from vgar.repair.context_adapter import load_handoff


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)


def export_task(task, source_repo, output, *, count_tokens, counter_label, budget_tokens=8000) -> dict:
    """budget_tokens is shared by both arms; 8000 is the retrieval-evaluation budget, repair uses a smaller one."""
    task = project_retrieval_task(task)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    clock = time.perf_counter()
    started = datetime.now(UTC).isoformat()
    build_start = time.perf_counter()
    document = PythonGraphBuilder(repo_key=task['repo'], repository_revision=task['base_commit']).build(source_repo)
    write_json(output / 'graph.json', document)
    build_seconds = time.perf_counter()-build_start
    fallback, arms = test_scope(document), []
    source_digest = None
    for arm in ('graph', 'bm25'):
        arm_clock = time.perf_counter()
        try:
            if arm == 'bm25':
                bundle = create_bm25_handoff(document, source_repo, issue_text=task['problem_statement'],
                    count_tokens=count_tokens, counter_label=counter_label, selected_tests=fallback,
                    budget_tokens=budget_tokens)
                diagnostics = bundle.pop('retrieval_diagnostics')
            else:
                overlay = TaskOverlayBuilder(document).build(task['instance_id'], task['problem_statement'], [])
                retriever = GraphContextRetriever(document, source_repo, count_tokens=count_tokens, counter_label=counter_label)
                usable = usable_node_ids(document, retriever._verify_snapshot())
                anchors = [a.node_id for a in overlay.grounding.anchors]
                result = retriever.retrieve(anchors, budget_tokens, issue_text=task['problem_statement'], overlay=overlay,
                                            include=lambda node, usable=usable: node['id'] in usable)
                diagnostics = {'candidates':result.candidates, 'omissions':result.omissions,
                               'config':result.config, 'traversal_limited':result.traversal_limited}
                bundle = create_context_handoff(document, response_for(document, result.context, counter_label),
                    source_repo, count_tokens=count_tokens, counter_label=counter_label,
                    selected_tests=fallback, test_hint_policy='issue-only')
            directory = write_context_handoff(bundle, output / arm)
            target = SimpleNamespace(task_id=task['instance_id'], source_repo=Path(source_repo), bundle_directory=directory,
                repo_key=task['repo'], revision=task['base_commit'], graph_version=document['graph_version'])
            received = load_handoff(target, count_tokens, counter_label)
            received.assert_unchanged()
            if source_digest is not None and received.metadata['source_digest'] != source_digest:
                raise ValueError('Arms differ in source inventory')
            source_digest = received.metadata['source_digest']
            write_json(output / f'{arm}-retrieval.json', diagnostics)
            record = {'arm':arm, 'status':'PASS', 'bundle_directory':str(directory.resolve()),
                **received.metadata, 'bundle_hashes':{n:byte_digest((directory/n).read_bytes())
                 for n in ('context.json','context_manifest.json','test_links.json')}}
        except Exception as error:  # noqa: BLE001 -- preserve per-arm errors at the export boundary
            record = {'arm':arm, 'status':'ERROR', 'error_type':type(error).__name__,
                      'reason':str(error), 'traceback':traceback.format_exc()}
        record['duration_seconds'] = time.perf_counter()-arm_clock
        arms.append(record)
        write_json(output / f'{arm}-validation.json', record)
    report = {'task':task, 'resolver_profile':'static', 'shared_build_seconds':build_seconds,
        'fallback_scope':fallback, 'arms':arms, 'started_utc':started,
        'ended_utc':datetime.now(UTC).isoformat(), 'duration_seconds':time.perf_counter()-clock}
    write_json(output / 'export_record.json', report)
    return report
