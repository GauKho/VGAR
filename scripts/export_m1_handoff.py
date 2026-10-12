"""Export and validate M1 context/source/test inputs for M2; no model or patch."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar.contracts.handoff import adapt_test_hints, validate_context_handoff
from vgar.graph.handoff import create_context_handoff, write_context_handoff
from vgar.graph.token_counter import LocalTokenizerCounter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--context-response', type=Path, required=True, help='get_related_context data wrapper JSON')
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--tokenizer-manifest', type=Path, required=True)
    parser.add_argument('--changed-path', action='append', default=None)
    parser.add_argument('--failing-test', action='append', default=[])
    parser.add_argument('--selected-test', action='append', default=[])
    parser.add_argument('--output-root', type=Path, default=ROOT / 'artifacts/m1/w7-w8/handoffs')
    args = parser.parse_args()
    run_id = uuid.uuid4().hex
    output = args.output_root.resolve() / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + run_id)
    try:
        document = json.loads(args.graph.read_text(encoding='utf-8'))
        response = json.loads(args.context_response.read_text(encoding='utf-8'))
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        bundle = create_context_handoff(document, response, args.repository,
            count_tokens=counter, counter_label=counter.counter_label, changed_paths=args.changed_path,
            failing_tests=args.failing_test, selected_tests=args.selected_test)
        # Exercise the consumer interface explicitly, using the approved graph input.
        context = validate_context_handoff(bundle['context'], bundle['manifest'], args.repository,
            expected_graph_version=document['graph_version'], expected_repo_key=document['repo_key'],
            expected_revision=document['repository_revision'], count_tokens=counter, counter_label=counter.counter_label)
        hints = adapt_test_hints(bundle['test_hints'], bundle['manifest'], args.repository)
        write_context_handoff(bundle, output)
        record = {'status': 'PASS', 'run_id': run_id, 'scope': 'm1_handoff_no_model_no_patch_no_test_execution',
                  'graph_version': context.graph_version, 'source_digest': bundle['manifest']['source_digest'],
                  'items': len(context.items), 'snippet_tokens': context.total_token_count,
                  'test_link_targets': len(hints['test_links']), 'failing_selectors': hints['failing_selectors'],
                  'fallback_scope': hints['fallback_scope'], 'collection_verified': False,
                  'tokenizer': counter.provenance, 'output_directory': str(output)}
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        record = {'status': 'ERROR', 'run_id': run_id, 'error_type': type(error).__name__, 'reason': str(error),
                  'scope': 'm1_handoff_no_model_no_patch_no_test_execution', 'output_directory': str(output)}
    (output / 'result.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
