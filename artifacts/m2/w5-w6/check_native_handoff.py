"""M1 real static producer -> M2 source/range/counter/mapping proof, no inference."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder
from vgar.graph.token_counter import LocalTokenizerCounter
from vgar.evaluation.retrieval.evidence import sha256, write_json
from vgar.evaluation.retrieval.gold_labels import extract_gold
from vgar.evaluation.retrieval.scoring import CorpusIndex, graph_rank, make_include, score_record

source = ROOT / 'artifacts/m2/w5-w6/handoff_fixture'
destination = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'artifacts/m2/w5-w6/native_handoff')
if destination.exists():
    raise ValueError('Keep the existing proof; use a new output for another invocation')
counter = LocalTokenizerCounter(ROOT / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
sources = {p.relative_to(source).as_posix(): p.read_text(encoding='utf-8') for p in sorted(source.rglob('*.py'))}
source_hashes = {p.relative_to(source).as_posix(): sha256(p.read_bytes()) for p in sorted(source.rglob('*.py'))}
document = PythonGraphBuilder(repo_key='m2-handoff-fixture', repository_revision='m2-w56-fixture-v1').build(source)
issue = 'Repair src/auth.py normalize_token: trim whitespace while preserving authenticate in src/service.py.'
overlay = TaskOverlayBuilder(document).build('m2-handoff-proof', issue)
anchors = [a.node_id for a in overlay.grounding.anchors]
retriever = GraphContextRetriever(document, source, count_tokens=counter, counter_label=counter.counter_label)
corpus = CorpusIndex(sources)
output = retriever.retrieve(anchors, 8000, issue_text=issue, overlay=overlay, include=make_include(corpus))
context = output.context.model_dump(mode='json')
if not context['items']:
    raise AssertionError('Actual M1 context is empty')
for item in context['items']:
    lines = (source / item['path']).read_bytes().splitlines(keepends=True)
    span = item['range']
    start = sum(map(len, lines[:span['start_line'] - 1])) + span['start_col']
    end = sum(map(len, lines[:span['end_line'] - 1])) + span['end_col']
    raw = (source / item['path']).read_bytes()
    assert raw[start:end].decode('utf-8') == item['snippet']
    assert counter(item['snippet']) == item['token_count']
assert sum(item['token_count'] for item in context['items']) == context['total_token_count'] <= 8000
rank = graph_rank('m2-handoff-proof', output.candidates, retriever.nodes, sources, corpus)
before = rank.rank_hash
# Developer labels are introduced only after M1 retrieval and M2 ranking finish.
patch = '--- a/src/auth.py\n+++ b/src/auth.py\n@@ -3,1 +3,1 @@\n-    return token\n+    return token.strip()\n'
gold = extract_gold(patch, sources)
assert gold['gold_functions'] == ['src/auth.py::auth.normalize_token']
scored = score_record(rank, gold, budget_tokens=8000, counter=counter, counter_label=counter.counter_label)
assert rank.rank_hash == scored['rank_hash'] == before
assert any(item.function_id == 'src/auth.py::auth.normalize_token' for item in rank.items)
assert source_hashes == {p.relative_to(source).as_posix(): sha256(p.read_bytes()) for p in sorted(source.rglob('*.py'))}
write_json(destination / 'context.json', context)
write_json(destination / 'graph.json', document)
proof = {'status': 'PASS', 'context_origin': 'actual-M1-static-producer', 'source_hashes': source_hashes,
         'source_unchanged': True, 'counter': counter.provenance, 'counter_label': counter.counter_label,
         'issue': issue, 'anchor_ids': anchors, 'rank': rank.to_json(include_snippets=True), 'gold': gold,
         'scoring': scored, 'checks': ['UTF-8-byte-source-slice', 'exclusive-range', 'token-accounting',
                                      'canonical-function-mapping', 'gold-after-rank-freeze', 'source-unchanged'],
         'owner_signoff': 'PENDING_M1_OWNER_REVIEW'}
write_json(destination / 'result.json', proof)
print(json.dumps({'status': 'PASS', 'context_items': len(context['items']),
                  'snippet_tokens': context['total_token_count'], 'unmapped': len(rank.unmapped),
                  'proof': str(destination / 'result.json'), 'owner_signoff': proof['owner_signoff']}))
