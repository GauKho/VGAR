"""Validate an exported M1 bundle for M2 without building a graph or calling a model."""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar.contracts.consumer import HandoffTarget, receive_context_handoff
from vgar.graph.token_counter import LocalTokenizerCounter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--repository', type=Path, required=True, help='Original source snapshot, before patch')
    parser.add_argument('--task-config', type=Path, required=True, help='Approved HandoffTarget JSON, independent of bundle')
    parser.add_argument('--tokenizer-manifest', type=Path, required=True)
    parser.add_argument('--changed-path', action='append', help='Actual diff path (POSIX, relative); repeat per file')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'artifacts/m1/w7-w8/consumer-runs')
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    run_id = uuid.uuid4().hex
    output = args.output_root.resolve() / (started.strftime('%Y%m%dT%H%M%SZ') + '-' + run_id)
    record = {
        'run_id': run_id, 'started_utc': started.isoformat(),
        'scope': 'm1_consumer_no_model_no_patch_no_test_execution',
        'bundle_directory': str(args.bundle.resolve()), 'repository': str(args.repository.resolve()),
        'output_directory': str(output),
    }
    stage = 'load_task_config'
    events = []
    try:
        output.mkdir(parents=True, exist_ok=False)
        target = HandoffTarget.model_validate_json(args.task_config.read_text(encoding='utf-8'))
        record['approved_target'] = target.model_dump()
        stage = 'load_tokenizer'
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        stage = 'receive_handoff'
        received = receive_context_handoff(args.bundle, args.repository, target,
            count_tokens=counter, counter_label=counter.counter_label, changed_paths=args.changed_path)
        events.append({'event': 'handoff_validated', 'task_id': target.task_id, **received['metadata']})
        stage = 'write_consumer_outputs'
        # Write bytes to preserve exact UTF-8/CRLF slices on Windows.
        (output / 'repair-context.txt').write_bytes(received['context_text'].encode('utf-8'))
        (output / 'test-inputs.json').write_text(
            json.dumps(received['test_inputs'], indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        diagnostics = received['test_inputs']['diagnostics']
        summary = {
            'limited_targets': diagnostics['limited_targets'],
            'unlinked_targets': diagnostics['unlinked_targets'],
            'fallback_reasons': {key: detail['fallback_reason']
                                 for key, detail in diagnostics['link_details'].items()},
            'test_link_targets': len(received['test_inputs']['test_links']),
            'coverage_verified': False, 'collection_verified': False,
        }
        events.append({'event': 'test_hint_diagnostics', **summary})
        record.update(status='PASS', metadata=received['metadata'], tokenizer=counter.provenance,
                      test_diagnostics=summary)
        if 'test_target_report' in received:
            report = received['test_target_report']
            (output / 'test-targets.json').write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            changed_summary = {
                'mapping_status': {path: item['mapping_status'] for path, item in report['targets'].items()},
                'fallback_required': report['fallback_required'],
                'fallback_available': report['fallback_available'],
                'requires_fallback_input': report['requires_fallback_input'],
                'coverage_verified': False, 'collection_verified': False,
            }
            events.append({'event': 'test_target_diagnostics', **changed_summary})
            record['test_target_diagnostics'] = changed_summary
    except Exception as error:
        # Pydantic's default string can include the rejected source payload.
        reason = (json.dumps(error.errors(include_input=False, include_context=False, include_url=False),
                             ensure_ascii=False) if isinstance(error, ValidationError) else str(error))
        record.update(status='ERROR', error_stage=stage, error_type=type(error).__name__, reason=reason)
        events.append({'event': 'consumer_error', 'stage': stage,
                       'error_type': type(error).__name__, 'reason': reason})
    record.update(ended_utc=datetime.now(timezone.utc).isoformat(), duration_seconds=time.perf_counter() - clock)
    if output.is_dir():
        (output / 'events.jsonl').write_text(''.join(json.dumps({'run_id': run_id, **event}, ensure_ascii=False)
                                                    + '\n' for event in events), encoding='utf-8')
        (output / 'result.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
