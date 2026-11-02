"""M2-W11-2: source-bound, baseline-relative structural verification contracts.

Every graph starts with the real Python builder. Graph mutations below isolate
validation and uncertainty cases that the normal static resolver cannot emit.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from types import MappingProxyType

import pytest

from vgar.graph.builder import PythonGraphBuilder


REPO_KEY = 'demo/structural'
RESOLVER_PROFILE = 'tree-sitter+python-static-v4-external-import'


@pytest.fixture
def structural():
    assert importlib.util.find_spec('vgar.repair.structural_check') is not None, (
        'M2-W11-2 structural checker is missing')
    return importlib.import_module('vgar.repair.structural_check')


@pytest.fixture
def snapshots(tmp_path):
    """Build detached graphs and exact raw File inventories in separate roots."""
    serial = 0

    def build_pair(before, after=None):
        nonlocal serial
        serial += 1
        results = []
        for side, files in [('before', before), ('after', before if after is None else after)]:
            root = tmp_path / str(serial) / side
            root.mkdir(parents=True)
            sources = {path: raw.encode('utf-8') if isinstance(raw, str) else raw
                       for path, raw in files.items()}
            for path, raw in sources.items():
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            graph = PythonGraphBuilder(
                repo_key=REPO_KEY, repository_revision='base').build(root)
            assert {node['path'] for node in graph['nodes'] if node['type'] == 'File'} == set(sources)
            assert graph['statistics']['resolver']['profile'] == RESOLVER_PROFILE
            results.append((graph, sources))
        return results

    return build_pair


def analyze(structural, pair, **kwargs):
    (before_graph, before_sources), (after_graph, after_sources) = pair
    return structural.check_structure(
        before_graph, after_graph,
        before_sources=before_sources, after_sources=after_sources, **kwargs)


def import_edges(graph, *, path=None):
    nodes = {node['id']: node for node in graph['nodes']}
    return [edge for edge in graph['edges'] if edge['type'] == 'IMPORTS'
            and (path is None or nodes[edge['source_id']]['path'] == path)]


def import_node(graph, path):
    return next(node for node in graph['nodes'] if node['type'] == 'Import' and node['path'] == path)


def module_node(graph, name):
    return next(node for node in graph['nodes']
                if node['type'] == 'Module' and node['qualified_name'] == name)


def subcheck(result, name, status):
    item = result.details['subchecks'][name]
    assert item['status'] == status
    assert 'reasons' in item
    return item


def assert_evidence(result):
    assert result.status in {'PASS', 'FAIL', 'NOT_RUN', 'ERROR'}
    assert isinstance(result.reasons, tuple)
    assert {'cycles', 'forbidden_imports', 'layers'} <= result.details['subchecks'].keys()
    assert isinstance(result.details['diagnostics'], list)
    assert set(result.details['graph_hashes']) == {'baseline', 'candidate'}
    assert set(result.details['source_hashes']) == {'baseline', 'candidate'}
    assert 'config_hash' in result.details and 'min_confidence' in result.details
    json.dumps(result.details, ensure_ascii=False, allow_nan=False)


def assert_error(result):
    assert result.status == 'ERROR'
    assert result.reasons
    assert result.details['diagnostics']


def cycle_pair(snapshots):
    return snapshots(
        {'src/a.py': 'import b\n', 'src/b.py': 'VALUE = 1\n'},
        {'src/a.py': 'import b\n', 'src/b.py': 'import a\n'})


def forbidden_config(**extra):
    return {'repo_key': REPO_KEY,
            'forbidden_imports': [{'source': 'a', 'target': 'forbidden_lib'}], **extra}


def layer_config():
    return {'repo_key': REPO_KEY,
            'layers': {'upper': ['a'], 'lower': ['b']},
            'allowed_layer_imports': {'upper': ['upper', 'lower'], 'lower': ['lower']}}


def test_new_import_cycle_fails_with_original_edge_witness(snapshots):
    # This first substantive contract makes an absent implementation a FAIL,
    # rather than a collection/import error, in the initial RED run.
    assert importlib.util.find_spec('vgar.repair.structural_check') is not None, (
        'M2-W11-2 structural checker is missing')
    checker = importlib.import_module('vgar.repair.structural_check')
    pair = cycle_pair(snapshots)
    result = analyze(checker, pair)
    assert result.status == 'FAIL' and 'NEW_IMPORT_CYCLE' in result.reasons
    cycles = subcheck(result, 'cycles', 'FAIL')
    assert cycles['violations']
    originals = {edge['id']: edge for edge in import_edges(pair[1][0])}
    for violation in cycles['violations']:
        witness = violation['witness']
        assert witness['modules'][0] == witness['modules'][-1]
        assert set(witness['modules']) == {'src/a.py', 'src/b.py'}
        assert len(witness['edges']) == len(witness['modules']) - 1
        assert all(edge['type'] == 'IMPORTS' and edge == originals[edge['id']]
                   for edge in witness['edges'])
    assert_evidence(result)


@pytest.mark.parametrize(('before', 'after'), [
    ({'src/a.py': 'import b\n', 'src/b.py': 'import a\n'},
     {'src/a.py': 'import b\n', 'src/b.py': 'import a\n'}),
    ({'src/a.py': 'import b\n', 'src/b.py': 'import a\n'},
     {'src/a.py': 'import b\n', 'src/b.py': 'VALUE = 1\n'}),
    ({'src/a.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'},
     {'src/a.py': 'import b\n', 'src/b.py': 'VALUE = 2\n'}),
], ids=['preexisting-cycle', 'deleted-cycle', 'new-acyclic-edge'])
def test_only_new_cycle_forming_module_adjacencies_fail(structural, snapshots, before, after):
    result = analyze(structural, snapshots(before, after))
    assert result.status == 'PASS'
    assert 'NEW_IMPORT_CYCLE' not in result.reasons
    assert subcheck(result, 'cycles', 'PASS')['violations'] == []


def test_new_chord_inside_an_existing_scc_is_a_new_cycle(structural, snapshots):
    before = {'src/a.py': 'import b\n', 'src/b.py': 'import c\n', 'src/c.py': 'import a\n'}
    pair = snapshots(before, {**before, 'src/a.py': 'import b\nimport c\n'})
    result = analyze(structural, pair)
    assert result.status == 'FAIL' and 'NEW_IMPORT_CYCLE' in result.reasons
    violations = subcheck(result, 'cycles', 'FAIL')['violations']
    assert violations
    graph = pair[1][0]
    new_edge = next(edge for edge in import_edges(graph, path='src/a.py')
                    if edge['target_id'] == module_node(graph, 'c')['id'])
    assert all(new_edge in violation['witness']['edges'] for violation in violations)


def test_self_import_is_a_module_cycle_without_a_graph_self_loop(structural, snapshots):
    result = analyze(structural, snapshots({'src/a.py': 'VALUE = 1\n'}, {'src/a.py': 'import a\n'}))
    assert result.status == 'FAIL' and 'NEW_IMPORT_CYCLE' in result.reasons
    witness = subcheck(result, 'cycles', 'FAIL')['violations'][0]['witness']
    assert witness['modules'] == ['src/a.py', 'src/a.py']
    assert len(witness['edges']) == 1
    assert witness['edges'][0]['source_id'] != witness['edges'][0]['target_id']


@pytest.mark.parametrize('new_source', ['import b\nimport b as second\n', '# moved\n\nimport b\n'])
def test_new_import_ids_do_not_make_existing_module_adjacency_new(structural, snapshots, new_source):
    before = {'src/a.py': 'import b\n', 'src/b.py': 'import a\n'}
    result = analyze(structural, snapshots(before, {**before, 'src/a.py': new_source}))
    assert result.status == 'PASS'
    assert subcheck(result, 'cycles', 'PASS')['violations'] == []


def test_new_unrelated_edge_does_not_fail_because_an_old_cycle_exists(structural, snapshots):
    before = {'src/a.py': 'import b\n', 'src/b.py': 'import a\n',
              'src/c.py': 'VALUE = 1\n', 'src/d.py': 'VALUE = 2\n'}
    result = analyze(structural, snapshots(before, {**before, 'src/c.py': 'import d\n'}))
    assert result.status == 'PASS'


@pytest.mark.parametrize(('confidence', 'threshold', 'expected'), [
    (0.599, 0.60, 'PASS'), (0.60, 0.60, 'FAIL'), (0.601, 0.60, 'FAIL'),
    (0.0, 0.0, 'FAIL'), (1.0, 1.0, 'FAIL'),
])
def test_cycle_confidence_threshold_is_inclusive(structural, snapshots, confidence, threshold, expected):
    pair = cycle_pair(snapshots)
    import_edges(pair[1][0], path='src/b.py')[0]['confidence'] = confidence
    result = analyze(structural, pair, min_confidence=threshold)
    assert result.status == expected
    assert result.details['min_confidence'] == threshold
    assert ('NEW_IMPORT_CYCLE' in result.reasons) is (expected == 'FAIL')


@pytest.mark.parametrize('status', ['unresolved', 'ambiguous'])
def test_unresolved_or_ambiguous_import_nodes_are_honestly_skipped(structural, snapshots, status):
    pair = cycle_pair(snapshots)
    import_node(pair[1][0], 'src/b.py')['properties']['resolution_status'] = status
    result = analyze(structural, pair)
    assert result.status == 'PASS'
    assert subcheck(result, 'cycles', 'PASS')['violations'] == []
    assert result.details['diagnostics']


@pytest.mark.parametrize('resolution', ['unresolved', 'ambiguous'])
def test_nonresolved_import_edges_do_not_create_cycle_claims(structural, snapshots, resolution):
    pair = cycle_pair(snapshots)
    import_edges(pair[1][0], path='src/b.py')[0]['resolution'] = resolution
    result = analyze(structural, pair)
    assert result.status == 'PASS'
    assert result.details['diagnostics']


def test_exact_confidence_one_external_import_is_excluded_from_cycle_scope(structural, snapshots):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'}, {'src/a.py': 'import external_dependency\n'})
    graph = pair[1][0]
    edge = import_edges(graph)[0]
    assert edge['confidence'] == 1.0 and edge['resolution'] == 'exact'
    assert module_node(graph, 'external_dependency')['properties']['is_external'] is True
    assert import_node(graph, 'src/a.py')['properties']['resolution_status'] == 'external'
    result = analyze(structural, pair)
    assert result.status == 'PASS'
    assert subcheck(result, 'cycles', 'PASS')['violations'] == []
    assert result.details['diagnostics']


def test_ownership_uses_contains_even_when_its_confidence_is_zero(structural, snapshots):
    pair = cycle_pair(snapshots)
    for graph, _ in pair:
        for edge in graph['edges']:
            if edge['type'] == 'CONTAINS':
                edge['confidence'] = 0.0
    result = analyze(structural, pair)
    assert result.status == 'FAIL' and 'NEW_IMPORT_CYCLE' in result.reasons


@pytest.mark.parametrize('ambiguous', [False, True], ids=['missing-owner', 'ambiguous-owner'])
def test_missing_or_ambiguous_import_owner_is_error_even_below_threshold(
        structural, snapshots, ambiguous):
    pair = cycle_pair(snapshots)
    graph = pair[1][0]
    imported = import_node(graph, 'src/b.py')
    owner_edge = next(edge for edge in graph['edges']
                      if edge['type'] == 'CONTAINS' and edge['target_id'] == imported['id'])
    import_edges(graph, path='src/b.py')[0]['confidence'] = 0.0
    if ambiguous:
        extra = copy.deepcopy(owner_edge)
        extra.update(id=owner_edge['id'] + ':ambiguous-owner',
                     source_id=module_node(graph, 'a')['id'], confidence=0.0)
        graph['edges'].append(extra)
    else:
        graph['edges'].remove(owner_edge)
    assert_error(analyze(structural, pair))


def test_calls_are_not_import_adjacencies(structural, snapshots):
    pair = snapshots(
        {'src/a.py': 'def ping(): return 1\ndef pong(): return 2\n'},
        {'src/a.py': 'def ping(): return pong()\ndef pong(): return ping()\n'})
    assert len([edge for edge in pair[1][0]['edges'] if edge['type'] == 'CALLS']) == 2
    assert not import_edges(pair[1][0])
    result = analyze(structural, pair)
    assert result.status == 'PASS'
    assert subcheck(result, 'cycles', 'PASS')['violations'] == []


@pytest.mark.parametrize('invalid', [True, False, -0.01, 1.01, float('nan'), float('inf'), '0.60', None])
def test_invalid_min_confidence_is_a_programmer_error(structural, snapshots, invalid):
    with pytest.raises(ValueError):
        analyze(structural, snapshots({'src/a.py': 'VALUE = 1\n'}), min_confidence=invalid)


@pytest.mark.parametrize('invalid', [
    None, [('src/a.py', b'VALUE = 1\n')], {42: b'VALUE = 1\n'},
    {'src/a.py': 'VALUE = 1\n'}, {'src/a.py': bytearray(b'VALUE = 1\n')},
    {'../a.py': b'VALUE = 1\n'}, {'/a.py': b'VALUE = 1\n'},
    {'src\\a.py': b'VALUE = 1\n'},
])
def test_invalid_source_arguments_raise_value_error_on_either_side(structural, snapshots, invalid):
    (before, before_sources), (after, after_sources) = snapshots({'src/a.py': 'VALUE = 1\n'})
    with pytest.raises(ValueError):
        structural.check_structure(before, after, before_sources=invalid, after_sources=after_sources)
    with pytest.raises(ValueError):
        structural.check_structure(before, after, before_sources=before_sources, after_sources=invalid)


@pytest.mark.parametrize('side', [0, 1], ids=['baseline', 'candidate'])
@pytest.mark.parametrize('fault', ['missing-file', 'extra-file', 'raw-bytes', 'file-hash',
                                  'module-hash', 'module-range', 'import-hash',
                                  'range-bounds', 'range-shape', 'graph-shape'])
def test_graph_and_exact_source_binding_are_validated(structural, snapshots, side, fault):
    pair = snapshots({'src/a.py': 'import b\n', 'src/b.py': 'VALUE = 1\n'})
    graph, sources = pair[side]
    if fault == 'missing-file':
        sources.pop('src/a.py')
    elif fault == 'extra-file':
        sources['src/extra.py'] = b'VALUE = 3\n'
    elif fault == 'raw-bytes':
        sources['src/a.py'] = b'import b\r\n'
    elif fault == 'file-hash':
        next(node for node in graph['nodes'] if node['type'] == 'File')['content_hash'] = 'sha256:' + '0' * 64
    elif fault == 'module-hash':
        module_node(graph, 'a')['content_hash'] = 'sha256:' + '0' * 64
    elif fault == 'module-range':
        # Matching a partial slice is insufficient for a full-file Module.
        module = module_node(graph, 'a')
        module['range'].update(start_col=1, start_byte=1)
        module['content_hash'] = 'sha256:' + hashlib.sha256(sources['src/a.py'][1:]).hexdigest()
    elif fault == 'import-hash':
        import_node(graph, 'src/a.py')['content_hash'] = 'sha256:' + '0' * 64
    elif fault == 'range-bounds':
        import_node(graph, 'src/a.py')['range']['end_byte'] = 99999
    elif fault == 'range-shape':
        import_node(graph, 'src/a.py')['range']['start_byte'] = True
    elif fault == 'graph-shape':
        graph['edges'][0]['target_id'] = 'missing:node'
    assert_error(analyze(structural, pair))


@pytest.mark.parametrize('fault', ['missing-file-owner', 'ambiguous-file-owner',
                                  'cross-path-import', 'cross-path-function'])
def test_source_nodes_must_descend_from_one_same_path_file_even_at_zero_confidence(
        structural, snapshots, fault):
    pair = snapshots({'src/a.py': 'import b\ndef helper(): return 1\n',
                      'src/b.py': 'VALUE = 1\n'})
    graph = pair[1][0]
    if fault in {'missing-file-owner', 'ambiguous-file-owner'}:
        module = module_node(graph, 'a')
        edge = next(edge for edge in graph['edges']
                    if edge['type'] == 'CONTAINS' and edge['target_id'] == module['id'])
        if fault == 'missing-file-owner':
            graph['edges'].remove(edge)
        else:
            extra = copy.deepcopy(edge)
            other_file = next(node for node in graph['nodes']
                              if node['type'] == 'File' and node['path'] == 'src/b.py')
            extra.update(id=edge['id'] + ':other-file', source_id=other_file['id'], confidence=0.0)
            graph['edges'].append(extra)
    else:
        source_node = (import_node(graph, 'src/a.py') if fault == 'cross-path-import'
                       else next(node for node in graph['nodes'] if node['type'] == 'Function'))
        edge = next(edge for edge in graph['edges']
                    if edge['type'] == 'CONTAINS' and edge['target_id'] == source_node['id'])
        edge.update(source_id=module_node(graph, 'b')['id'], confidence=0.0)
    assert_error(analyze(structural, pair))


def test_duplicate_internal_module_names_are_error_instead_of_lost_adjacency(structural, snapshots):
    # The default src prefix policy makes both real files claim module "pkg".
    pair = snapshots({'pkg.py': 'import dependency\n', 'src/pkg.py': 'VALUE = 1\n',
                      'src/dependency.py': 'VALUE = 2\n'})
    modules = [node for node in pair[1][0]['nodes']
               if node['type'] == 'Module' and not node['properties']['is_external']]
    assert [node['properties']['module_name'] for node in modules].count('pkg') == 2
    assert_error(analyze(structural, pair))


@pytest.mark.parametrize('side', [0, 1], ids=['baseline', 'candidate'])
@pytest.mark.parametrize('profile', [None, 'tree-sitter+python-static-v3-method-aliases', 'other-resolver'])
def test_expected_resolver_profile_is_required_separately_from_graph_version(
        structural, snapshots, side, profile):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'})
    graph = pair[side][0]
    old_version = graph['graph_version']
    if profile is None:
        graph['statistics']['resolver'].pop('profile')
    else:
        graph['statistics']['resolver']['profile'] = profile
    assert graph['graph_version'] == old_version
    assert_error(analyze(structural, pair))


def test_pair_from_different_repositories_is_error(structural, snapshots):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'})
    pair[1][0]['repo_key'] = 'other/repository'
    for node in pair[1][0]['nodes']:
        node['repo_key'] = 'other/repository'
    assert_error(analyze(structural, pair))


def test_empty_source_scope_is_not_run(structural, snapshots):
    result = analyze(structural, snapshots({}))
    assert result.status == 'NOT_RUN'
    assert result.reasons
    assert_evidence(result)


def test_missing_policy_config_does_not_suppress_measured_cycles(structural, snapshots):
    result = analyze(structural, cycle_pair(snapshots))
    assert result.status == 'FAIL'
    subcheck(result, 'cycles', 'FAIL')
    subcheck(result, 'forbidden_imports', 'NOT_RUN')
    subcheck(result, 'layers', 'NOT_RUN')


@pytest.mark.parametrize(('before_import', 'after_import', 'expected'), [
    ('', 'import forbidden_lib\n', 'FAIL'),
    ('', 'import forbidden_lib.child\n', 'FAIL'),
    ('', 'from forbidden_lib import child\n', 'FAIL'),
    ('', 'import forbidden_library\n', 'PASS'),
    ('import forbidden_lib\n', 'import forbidden_lib\n', 'PASS'),
    ('import forbidden_lib\n', '', 'PASS'),
], ids=['new-external', 'target-descendant', 'from-import', 'prefix-boundary',
        'preexisting-violation', 'deleted-violation'])
def test_forbidden_import_policy_uses_lexical_targets_and_baseline_delta(
        structural, snapshots, before_import, after_import, expected):
    pair = snapshots({'src/a.py': before_import or 'VALUE = 1\n'},
                     {'src/a.py': after_import or 'VALUE = 1\n'})
    result = analyze(structural, pair, repo_config=forbidden_config())
    assert result.status == expected
    assert ('FORBIDDEN_IMPORT' in result.reasons) is (expected == 'FAIL')
    subcheck(result, 'forbidden_imports', expected)


@pytest.mark.parametrize(('path', 'expected'), [('src/a/child.py', 'FAIL'), ('src/abc.py', 'PASS')])
def test_forbidden_source_prefix_has_a_module_boundary(structural, snapshots, path, expected):
    pair = snapshots({path: 'VALUE = 1\n'}, {path: 'import forbidden_lib\n'})
    result = analyze(structural, pair, repo_config=forbidden_config())
    assert result.status == expected


@pytest.mark.parametrize('status', ['unresolved', 'ambiguous'])
def test_lexical_forbidden_rule_is_not_gated_by_import_resolution_or_confidence(
        structural, snapshots, status):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'}, {'src/a.py': 'import forbidden_lib\n'})
    import_node(pair[1][0], 'src/a.py')['properties']['resolution_status'] = status
    import_edges(pair[1][0])[0]['confidence'] = 0.0
    result = analyze(structural, pair, repo_config=forbidden_config(), min_confidence=1.0)
    assert result.status == 'FAIL' and 'FORBIDDEN_IMPORT' in result.reasons


def test_empty_forbidden_rule_list_is_a_measured_zero(structural, snapshots):
    result = analyze(structural, snapshots({'src/a.py': 'import external_lib\n'}),
                     repo_config={'repo_key': REPO_KEY, 'forbidden_imports': []})
    assert result.status == 'PASS'
    assert subcheck(result, 'forbidden_imports', 'PASS')['violations'] == []
    subcheck(result, 'layers', 'NOT_RUN')


@pytest.mark.parametrize(('before', 'after', 'expected'), [
    ({'src/a.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'},
     {'src/a.py': 'import b\n', 'src/b.py': 'VALUE = 2\n'}, 'PASS'),
    ({'src/a.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'},
     {'src/a.py': 'VALUE = 1\n', 'src/b.py': 'import a\n'}, 'FAIL'),
    ({'src/a.py': 'VALUE = 1\n', 'src/b.py': 'import a\n'},
     {'src/a.py': 'VALUE = 1\n', 'src/b.py': '# moved\nimport a\n'}, 'PASS'),
    ({'src/a.py': 'VALUE = 1\n', 'src/b.py': 'import a\n'},
     {'src/a.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'}, 'PASS'),
], ids=['allowed-direction', 'new-disallowed-direction', 'preexisting-layer-violation',
        'deleted-layer-violation'])
def test_layer_rules_are_directional_and_baseline_relative(structural, snapshots, before, after, expected):
    result = analyze(structural, snapshots(before, after), repo_config=layer_config())
    assert result.status == expected
    assert ('LAYER_VIOLATION' in result.reasons) is (expected == 'FAIL')
    subcheck(result, 'layers', expected)


def test_overlapping_layer_prefixes_use_the_longest_module_match(structural, snapshots):
    config = {'repo_key': REPO_KEY,
              'layers': {'upper': ['a', 'b'], 'lower': ['a.special']},
              'allowed_layer_imports': {'upper': ['upper', 'lower'], 'lower': ['lower']}}
    before = {'src/a/special.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'}
    result = analyze(structural, snapshots(before, {**before, 'src/a/special.py': 'import b\n'}),
                     repo_config=config)
    assert result.status == 'FAIL' and 'LAYER_VIOLATION' in result.reasons


@pytest.mark.parametrize('target', ['unclassified', 'external_dependency'])
def test_layer_rules_do_not_guess_classification_for_out_of_scope_targets(
        structural, snapshots, target):
    before = {'src/b.py': 'VALUE = 1\n', 'src/unclassified.py': 'VALUE = 2\n'}
    pair = snapshots(before, {**before, 'src/b.py': f'import {target}\n'})
    result = analyze(structural, pair, repo_config=layer_config())
    assert result.status == 'PASS'
    assert subcheck(result, 'layers', 'PASS')['violations'] == []
    assert result.details['diagnostics']


@pytest.mark.parametrize('config', [
    {}, {'repo_key': 'other/repo'}, {'repo_key': REPO_KEY, 'typo': []},
    {'repo_key': REPO_KEY, 'forbidden_imports': 'a -> b'},
    {'repo_key': REPO_KEY, 'forbidden_imports': [{'source': 'a'}]},
    {'repo_key': REPO_KEY, 'forbidden_imports': [{'source': '', 'target': 'b'}]},
    {'repo_key': REPO_KEY, 'layers': {'upper': ['a']}},
    {'repo_key': REPO_KEY, 'allowed_layer_imports': {'upper': ['upper']}},
    {'repo_key': REPO_KEY, 'layers': {'upper': ['a'], 'lower': ['a']},
     'allowed_layer_imports': {'upper': ['upper'], 'lower': ['lower']}},
    {'repo_key': REPO_KEY, 'layers': {'upper': ['a', 'a']},
     'allowed_layer_imports': {'upper': ['upper']}},
    {'repo_key': REPO_KEY, 'layers': {'upper': ['a']},
     'allowed_layer_imports': {'upper': ['missing']}},
    {'repo_key': REPO_KEY, 'layers': {'upper': ['a']},
     'allowed_layer_imports': {'missing': ['upper']}},
], ids=['missing-repo', 'wrong-repo', 'unknown-key', 'rules-not-list', 'missing-target',
        'empty-prefix', 'missing-allow-list', 'missing-layers', 'cross-layer-duplicate-prefix',
        'duplicate-prefix', 'unknown-target-layer', 'unknown-source-layer'])
def test_invalid_policy_config_is_analysis_error(structural, snapshots, config):
    result = analyze(structural, snapshots({'src/a.py': 'VALUE = 1\n'}), repo_config=config)
    assert_error(result)
    assert 'STRUCTURAL_CONFIG_ERROR' in result.reasons


def test_loader_returns_none_for_no_path_or_missing_file(structural, tmp_path):
    assert structural.load_structural_config(None) is None
    assert structural.load_structural_config(tmp_path / 'missing.yaml') is None


def test_loader_reads_a_safe_repository_policy(structural, tmp_path):
    path = tmp_path / 'structural.yaml'
    path.write_text(
        'repo_key: demo/structural\nforbidden_imports:\n'
        '  - source: a\n    target: forbidden_lib\n', encoding='utf-8')
    assert structural.load_structural_config(path) == forbidden_config()


@pytest.mark.parametrize('yaml_text', [
    'repo_key: [unterminated\n',
    '!!python/object/apply:os.system ["echo should-never-run"]\n',
    'repo_key: demo/structural\nrepo_key: other/repo\n',
    'repo_key: demo/structural\nforbidden_imports:\n'
    '  - source: a\n    source: b\n    target: forbidden_lib\n',
], ids=['malformed-yaml', 'dangerous-tag', 'duplicate-top-level-key', 'duplicate-nested-key'])
def test_loader_rejects_malformed_unsafe_or_duplicate_key_yaml(structural, tmp_path, yaml_text):
    path = tmp_path / 'invalid.yaml'
    path.write_text(yaml_text, encoding='utf-8')
    with pytest.raises(ValueError):
        structural.load_structural_config(path)


def test_evidence_is_deterministic_raw_byte_bound_and_inputs_are_immutable(structural, snapshots):
    pair = snapshots(
        {'src/z.py': b'VALUE = "caf\xc3\xa9"\r\n', 'src/a.py': b'VALUE = 1\n'},
        {'src/z.py': b'import a\r\n', 'src/a.py': b'import z\nimport forbidden_lib\n'})
    config = forbidden_config()
    original = copy.deepcopy((pair, config))
    first = structural.check_structure(
        pair[0][0], pair[1][0], before_sources=MappingProxyType(pair[0][1]),
        after_sources=MappingProxyType(pair[1][1]), repo_config=config)
    reordered = copy.deepcopy(pair)
    for graph, _ in reordered:
        graph['nodes'].reverse()
        graph['edges'].reverse()
    reordered = [(graph, dict(reversed(list(sources.items())))) for graph, sources in reordered]
    config_reordered = dict(reversed(list(config.items())))
    second = analyze(structural, reordered, repo_config=config_reordered)
    assert first.status == second.status == 'FAIL'
    assert first.reasons == second.reasons
    assert first.details == second.details
    assert (pair, config) == original
    expected = {
        side: {path: 'sha256:' + hashlib.sha256(raw).hexdigest() for path, raw in sources.items()}
        for side, (_, sources) in zip(('baseline', 'candidate'), pair)
    }
    assert first.details['source_hashes'] == expected
    assert all(value.startswith('sha256:') and len(value) == 71
               for value in first.details['graph_hashes'].values())
    assert isinstance(first.details['config_hash'], str)
    assert first.details['config_hash'].startswith('sha256:')
    assert first.details['min_confidence'] == 0.60
    assert_evidence(first)


def test_config_hash_changes_with_the_measured_policy(structural, snapshots):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'})
    first = analyze(structural, pair, repo_config=forbidden_config())
    changed = analyze(structural, pair, repo_config={
        'repo_key': REPO_KEY, 'forbidden_imports': [{'source': 'a', 'target': 'other_lib'}]})
    assert first.details['config_hash'] != changed.details['config_hash']
    assert first.details['graph_hashes'] == changed.details['graph_hashes']
    assert first.details['source_hashes'] == changed.details['source_hashes']


def test_input_code_is_never_executed(structural, snapshots, tmp_path):
    marker = tmp_path / 'executed.txt'
    code = (f'open({str(marker)!r}, "w").write("executed")\n'
            'raise RuntimeError("must not execute")\nimport forbidden_lib\n')
    pair = snapshots({'src/a.py': 'VALUE = 1\n'}, {'src/a.py': code})
    result = analyze(structural, pair, repo_config=forbidden_config())
    assert result.status == 'FAIL' and 'FORBIDDEN_IMPORT' in result.reasons
    assert not marker.exists()


@pytest.mark.parametrize('side', [0, 1], ids=['baseline', 'candidate'])
def test_wrong_import_slice_returns_error_instead_of_raising_syntax_error(structural, snapshots, side):
    pair = snapshots({'src/a.py': 'if enabled:\n    import b\nelse:\n    pass\n',
                      'src/b.py': 'VALUE = 1\n'})
    graph, sources = pair[side]
    node = import_node(graph, 'src/a.py')
    raw = sources['src/a.py']
    start = raw.index(b'else:')
    node['range'] = {'start_byte': start, 'end_byte': start + 5,
                     'start_line': 3, 'end_line': 3, 'start_col': 0, 'end_col': 5}
    node['content_hash'] = 'sha256:' + hashlib.sha256(raw[start:start + 5]).hexdigest()
    result = analyze(structural, pair)
    assert_error(result)
    assert 'STRUCTURAL_GRAPH_ERROR' in result.reasons


def test_loader_rejects_aliases_even_when_only_mapping_keys_are_shared(structural, tmp_path):
    path = tmp_path / 'key-aliases.yaml'
    path.write_text('repo_key: demo/structural\nforbidden_imports:\n'
                    '  - &s source: a\n    &t target: b\n'
                    '  - *s: b\n    *t: a\n', encoding='utf-8')
    with pytest.raises(ValueError, match='alias'):
        structural.load_structural_config(path)


@pytest.mark.parametrize('bad_config', [True, False], ids=['invalid-config', 'invalid-pair'])
def test_aborted_cycle_analysis_has_an_accurate_not_run_reason(structural, snapshots, bad_config):
    pair = snapshots({'src/a.py': 'VALUE = 1\n'})
    kwargs = {'repo_config': {'repo_key': 'other/repo'}} if bad_config else {}
    if not bad_config:
        pair[1][0]['repo_key'] = 'other/repo'
        for node in pair[1][0]['nodes']:
            node['repo_key'] = 'other/repo'
    result = analyze(structural, pair, **kwargs)
    assert_error(result)
    cycles = subcheck(result, 'cycles', 'NOT_RUN')
    assert cycles['reasons'] and 'NO_CONFIG' not in cycles['reasons']


@pytest.mark.parametrize('statement', ['from . import secret as safe_alias\n',
                                      'from pkg import secret as safe_alias\n'])
def test_forbidden_from_import_matches_member_not_local_alias(structural, snapshots, statement):
    before = {'src/pkg/__init__.py': '', 'src/pkg/reader.py': 'VALUE = 1\n',
              'src/pkg/secret.py': 'VALUE = 2\n'}
    result = analyze(structural, snapshots(before, {**before, 'src/pkg/reader.py': statement}),
                     repo_config={'repo_key': REPO_KEY,
                                  'forbidden_imports': [{'source': 'pkg.reader', 'target': 'pkg.secret'}]})
    assert result.status == 'FAIL' and 'FORBIDDEN_IMPORT' in result.reasons


def test_committed_example_policy_operates_on_its_synthetic_repository(structural, snapshots):
    from pathlib import Path
    policy = structural.load_structural_config(
        Path(__file__).resolve().parents[3] / 'configs/m2/structural/example.yaml')
    before = {'src/a.py': 'VALUE = 1\n', 'src/b.py': 'VALUE = 2\n'}
    after = {'src/a.py': 'import forbidden_lib\n', 'src/b.py': 'import a\n'}
    result = analyze(structural, snapshots(before, after), repo_config=policy)
    assert set(result.reasons) == {'FORBIDDEN_IMPORT', 'LAYER_VIOLATION'}
    assert result.status == 'FAIL'
