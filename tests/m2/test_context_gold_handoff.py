"""M2 consumer boundaries: same source/query must also mean the same developer labels."""
from __future__ import annotations

import json

import pytest

from vgar.evaluation.retrieval.compare import compare_runs
from vgar.evaluation.retrieval.evaluation import evaluate_task
from vgar.evaluation.retrieval.evidence import sha256, write_json
from vgar.evaluation.retrieval.graph_arm import evaluate_graph_task
from vgar.evaluation.retrieval.metrics import aggregate_metrics
from vgar.evaluation.retrieval.scoring import CorpusIndex, graph_rank, score_record


SOURCES = {'src/auth.py': 'def validate(token):\n    return token == "old"\n',
           'src/client.py': 'def login(token):\n    return validate(token)\n'}
PATCH = '--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1,2 +1,2 @@\n def validate(token):\n-    return token == "old"\n+    return token == "valid"\n'
TASK = {'instance_id': 'auth-1', 'repo': 'example/auth', 'base_commit': 'a' * 40,
        'problem_statement': 'validate token correctly', 'patch': PATCH}
WORDS = lambda text: len(text.split())
NODES = {'auth.validate': {'id': 'auth.validate', 'type': 'Function', 'path': 'src/auth.py',
                         'qualified_name': 'auth.validate', 'range': {'start_line': 1, 'end_line': 2}}}
OUTPUT = {'candidates': [{'node_id': 'auth.validate', 'relevance_score': 1.0}],
          'anchors': [{'node_id': 'auth.validate', 'symbol': 'auth.validate'}], 'seconds': 0.1}


def comparison_inputs(tmp_path, *, other_patch):
    """Real evaluator artifacts with independently different developer fixes."""
    bm = evaluate_task(TASK, SOURCES, counter=WORDS, counter_label='test:words')
    gr = evaluate_graph_task(dict(TASK, patch=other_patch), SOURCES, CorpusIndex(SOURCES), NODES,
                             {'graph': OUTPUT, 'graph_f2p': OUTPUT}, budget_tokens=8000,
                             counter=WORDS, counter_label='test:words')
    config = {'manifest_hash': 'test:same-input-manifest', 'budget_tokens': 8000,
              'counter_label': 'test:words', 'counter_is_fallback': False,
              'scoring_version': 'retrieval-scoring-v1',
              'snippet_policy': {'max_snippet_lines': 80, 'header': True,
                                 'overlap': 'skip_if_overlaps_different_group'}}
    for label, task in (('bm25', bm), ('graph', gr)):
        directory = tmp_path / label
        task_path = directory / 'tasks/auth-1.json'
        write_json(task_path, task)
        row = {'instance_id': 'auth-1', 'status': 'SUCCEEDED', 'graph_build_seconds': 0.1,
               'artifact_hash': sha256(task_path.read_bytes())}
        if label == 'bm25':
            row['metrics'] = task['metrics']
            summary = aggregate_metrics([row])
        else:
            row['arms'] = {arm: {'metrics': data['metrics']} for arm, data in task['arms'].items()}
            summary = {}
        write_json(directory / 'result.json', {'run_id': label, 'complete': True,
                   'dataset_id': 'test:verified', 'dataset_revision': 'test:pinned',
                   'config': config, 'task_results': [row], 'summary': summary})
    return tmp_path / 'bm25', tmp_path / 'graph'


def test_compare_rejects_patch_hash_mismatch(tmp_path):
    bm, gr = comparison_inputs(tmp_path, other_patch=PATCH.replace('"valid"', '"different"'))
    with pytest.raises(ValueError, match='patch_hash'):
        compare_runs(bm, gr, tmp_path / 'comparison')


def test_compare_accepts_same_patch_identity(tmp_path):
    bm, gr = comparison_inputs(tmp_path, other_patch=PATCH)
    _, report = compare_runs(bm, gr, tmp_path / 'comparison')
    assert report['status'] == 'COMPARED'
    assert report['paired_tasks'] == 1
    assert report['paired']['graph']['function_recall@5']['n'] == 1


@pytest.mark.parametrize('key', ['query_hash', 'corpus_hash', 'base_commit'])
def test_compare_rejects_task_identity_mismatch(tmp_path, key):
    bm, gr = comparison_inputs(tmp_path, other_patch=PATCH)
    task_path = gr / 'tasks/auth-1.json'
    task = json.loads(task_path.read_text(encoding='utf-8'))
    task[key] = 'different-identity'
    write_json(task_path, task)
    run = json.loads((gr / 'result.json').read_text(encoding='utf-8'))
    run['task_results'][0]['artifact_hash'] = sha256(task_path.read_bytes())
    write_json(gr / 'result.json', run)
    with pytest.raises(ValueError, match=key):
        compare_runs(bm, gr, tmp_path / 'comparison')


@pytest.mark.parametrize('key,value', [('budget_tokens', 4000), ('counter_label', 'test:other'),
                                      ('scoring_version', 'other'), ('manifest_hash', 'other')])
def test_compare_rejects_profile_mismatch(tmp_path, key, value):
    bm, gr = comparison_inputs(tmp_path, other_patch=PATCH)
    run = json.loads((gr / 'result.json').read_text(encoding='utf-8'))
    run['config'][key] = value
    write_json(gr / 'result.json', run)
    with pytest.raises(ValueError, match=key):
        compare_runs(bm, gr, tmp_path / 'comparison')


def test_single_definition_outside_range_is_not_a_function_hit():
    # A producer can name the right symbol but point at unrelated/out-of-bounds lines.
    nodes = {'auth.validate': dict(NODES['auth.validate'], range={'start_line': 99, 'end_line': 100})}
    record = graph_rank('auth-1', OUTPUT['candidates'], nodes, SOURCES, CorpusIndex(SOURCES))
    assert record.items == []
    assert record.unmapped[0]['reason'] == 'INVALID_SOURCE_RANGE'
    gold = {'gold_files': ['src/auth.py'], 'gold_functions': ['src/auth.py::auth.validate'],
            'function_labels_complete': True}
    scored = score_record(record, gold, budget_tokens=8000, counter=WORDS, counter_label='test:words')
    assert scored['rank']['metrics']['function_recall@5'] == 0.0


def test_same_symbol_in_other_path_cannot_resolve_to_wrong_function():
    sources = {'src/auth.py': 'def validate(token):\n    return True\n',
               'src/other.py': 'def validate(token):\n    return False\n'}
    corpus = CorpusIndex(sources)
    assert corpus.resolve_function('src/auth.py', 'auth.validate', 1, 2) == ('src/auth.py::auth.validate', None)
    assert corpus.resolve_function('src/other.py', 'other.validate', 1, 2) == ('src/other.py::other.validate', None)
    assert corpus.resolve_function('src/auth.py', 'other.validate', 1, 2) == (None, 'NO_FUNCTION_MATCH')


def test_end_exclusive_next_line_does_not_add_unrelated_code():
    sources = dict(SOURCES)
    sources['src/auth.py'] += 'def unrelated():\n    return 42\n'
    nodes = {'auth.validate': dict(NODES['auth.validate'],
                                 range={'start_line': 1, 'start_col': 0, 'end_line': 3, 'end_col': 0})}
    record = graph_rank('auth-1', OUTPUT['candidates'], nodes, sources, CorpusIndex(sources))
    assert record.items[0].snippet == 'def validate(token):\n    return token == "old"\n'
    assert record.items[0].function_id == 'src/auth.py::auth.validate'


@pytest.mark.parametrize('span', [None, {}, {'start_line': 1},
    {'start_line': 1, 'start_col': 0, 'end_line': 1, 'end_col': 0},
    {'start_line': 1, 'start_col': 99, 'end_line': 2, 'end_col': 0},
    {'start_line': 1, 'start_col': -1, 'end_line': 2, 'end_col': 0},
    {'start_line': 2, 'start_col': 0, 'end_line': 1, 'end_col': 0},
    {'start_line': True, 'end_line': 2},
    {'start_line': 1, 'start_col': 0, 'end_line': 2},
    {'start_line': 'bad', 'end_line': 2}])
def test_malformed_source_range_is_diagnostic_not_a_function_hit(span):
    nodes = {'auth.validate': dict(NODES['auth.validate'], range=span)}
    record = graph_rank('auth-1', OUTPUT['candidates'], nodes, SOURCES, CorpusIndex(SOURCES))
    assert record.items == []
    assert record.unmapped == [{'item_id': 'auth.validate', 'scope': 'item',
                               'reason': 'INVALID_SOURCE_RANGE', 'path': 'src/auth.py'}]


def test_utf8_column_inside_multibyte_character_is_not_source_bound():
    sources = dict(SOURCES, **{'src/auth.py': 'def validate(token):\n    return "é"\n'})
    nodes = {'auth.validate': dict(NODES['auth.validate'],
        range={'start_line': 1, 'start_col': 0, 'end_line': 2, 'end_col': 13})}
    record = graph_rank('auth-1', OUTPUT['candidates'], nodes, sources, CorpusIndex(sources))
    assert record.items == []
    assert record.unmapped[0]['reason'] == 'INVALID_SOURCE_RANGE'


def test_valid_native_utf8_end_and_crlf_keep_function_mapping():
    sources = dict(SOURCES, **{'src/auth.py': 'def validate(token):\r\n    return "é"\r\n'})
    nodes = {'auth.validate': dict(NODES['auth.validate'],
        range={'start_line': 1, 'start_col': 0, 'end_line': 2, 'end_col': 15})}
    record = graph_rank('auth-1', OUTPUT['candidates'], nodes, sources, CorpusIndex(sources))
    assert record.items[0].function_id == 'src/auth.py::auth.validate'
    assert record.unmapped == []
