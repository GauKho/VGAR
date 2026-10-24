"""W9-1 schema contract only; no mapping or runtime impact calculation."""
import copy
import importlib
import json

import pytest
from pydantic import ValidationError


@pytest.fixture
def api():
    return importlib.import_module('vgar.contracts.impact')


def example():
    span = {'hunk_index': 1, 'old_start': 2, 'old_count': 1, 'new_start': 2, 'new_count': 1}
    return {'repo_key': 'demo/project', 'repository_revision': 'fixture-v1', 'graph_version': 'snapshot-1',
            'graph_hash': 'sha256:' + 'a'*64, 'source_hash': 'sha256:' + 'b'*64,
            'patch_hash': 'sha256:' + 'c'*64,
            'changed': [{'node_id': 'opaque:fn', 'path': 'app.py', 'kind': 'Function',
                         'source_range': {'start_line': 1, 'start_col': 0, 'end_line': 4, 'end_col': 0},
                         'basis': 'baseline_changed_lines', 'spans': [span]}], 'unmapped': []}


def test_schema_roundtrip_and_not_computed(api):
    report = api.ImpactReport.model_validate(example())
    assert report.impacted.status == report.risk.status == 'NOT_COMPUTED'
    assert report.impacted.items == report.risk.features == []
    assert api.ImpactReport.model_validate_json(report.canonical_json()) == report
    assert 'schema_version' not in report.model_dump()


@pytest.mark.parametrize('kind,counts', [('modify', (1, 1)), ('add', (0, 2)), ('delete', (2, 0))])
def test_schema_change_operations(api, kind, counts):
    data = example()
    data['changed'][0]['spans'][0].update(old_count=counts[0], new_count=counts[1])
    assert api.ImpactReport.model_validate(data).changed[0].spans[0].old_count == counts[0]


@pytest.mark.parametrize('path', ['../x.py', '/x.py', 'C:/x.py', 'a\\x.py', './x.py', '.git/x.py', 'a//b.py', 'x\n.py'])
def test_schema_rejects_unsafe_paths(api, path):
    data = example()
    data['changed'][0]['path'] = path
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


@pytest.mark.parametrize('field,value', [('graph_hash', 'a'*64), ('source_hash', 'sha256:'+'G'*64),
                                       ('patch_hash', None), ('repo_key', ' '), ('graph_version', '')])
def test_schema_identity_validation(api, field, value):
    data = example()
    data[field] = value
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


@pytest.mark.parametrize('field,value', [('old_count', True), ('new_count', False), ('hunk_index', 0),
                                       ('old_count', -1), ('new_start', '2'), ('old_count', 1.5)])
def test_schema_strict_coordinates(api, field, value):
    data = example()
    data['changed'][0]['spans'][0][field] = value
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


@pytest.mark.parametrize('fault', ['range', 'range_bool', 'empty_change', 'zero_start', 'extra',
                                 'nested_extra', 'duplicate_node', 'duplicate_span', 'partial',
                                 'truncated', 'computed', 'risk_value'])
def test_schema_rejects_inconsistent_data(api, fault):
    data = example()
    node = data['changed'][0]
    if fault == 'range':
        node['source_range']['end_line'] = 0
    elif fault == 'range_bool':
        node['source_range']['start_col'] = False
    elif fault == 'empty_change':
        node['spans'][0].update(old_count=0, new_count=0)
    elif fault == 'zero_start':
        node['spans'][0]['old_start'] = 0
    elif fault == 'extra':
        data['schema_version'] = 'v1'
    elif fault == 'nested_extra':
        node['confidence'] = 1
    elif fault == 'duplicate_node':
        data['changed'].append(copy.deepcopy(node))
    elif fault == 'duplicate_span':
        node['spans'] *= 2
    elif fault == 'partial':
        data['limits'] = {'status': 'PARTIAL'}
    elif fault == 'truncated':
        data['limits'] = {'truncated': True}
    elif fault == 'computed':
        data['impacted'] = {'status': 'COMPLETE', 'items': []}
    else:
        data['risk'] = {'status': 'NOT_COMPUTED', 'features': [{'name': 'api', 'available': True, 'value': 0}]}
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


def test_schema_unmapped_addition_and_partial_are_explicit(api):
    data = example()
    data['unmapped'] = [{'path': 'app.py', 'span': {'hunk_index': 2, 'old_start': 5, 'old_count': 0,
                          'new_start': 5, 'new_count': 2}, 'reason': 'NO_BASELINE_SYMBOL_AT_INSERTION'}]
    data['limits'] = {'status': 'PARTIAL', 'truncated': True, 'reasons': ['mapping_limit']}
    report = api.ImpactReport.model_validate(data)
    assert report.unmapped[0].span.old_count == 0
    assert report.limits.status == 'PARTIAL'


def test_schema_canonical_order_and_hash_definition(api):
    data = example()
    other = copy.deepcopy(data['changed'][0])
    other['node_id'] = 'opaque:other'
    other['path'] = 'z.py'
    data['changed'].append(other)
    first = api.ImpactReport.model_validate(data)
    data['changed'].reverse()
    second = api.ImpactReport.model_validate(data)
    assert first.canonical_json() == second.canonical_json()
    assert first.changed[0].node_id == 'opaque:fn'  # Serialization must not mutate input order.
    assert api.canonical_hash({'b': 2, 'a': 1}) == api.canonical_hash({'a': 1, 'b': 2})
    assert api.canonical_hash({'a': 2}) != api.canonical_hash({'a': 1})
    with pytest.raises(ValueError):
        api.canonical_hash({'x': float('nan')})


def test_schema_document_example(api):
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / 'docs/impact_report_schema.md').read_text(encoding='utf-8')
    payload = json.loads(text.split('```json\n', 1)[1].split('\n```', 1)[0])
    assert api.ImpactReport.model_validate(payload).unmapped


@pytest.mark.parametrize('value', [0, 0.0, 1, 'false'])
def test_schema_risk_availability_is_strict_boolean(api, value):
    data = example()
    data['risk'] = {'features': [{'name': 'api', 'available': value}]}
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


@pytest.mark.parametrize('end_line,end_col', [(1, 0), (1, -1)])
def test_schema_rejects_empty_or_negative_range(api, end_line, end_col):
    data = example()
    data['changed'][0]['source_range'].update(end_line=end_line, end_col=end_col)
    with pytest.raises(ValidationError):
        api.ImpactReport.model_validate(data)


def test_schema_zero_count_boundary_before_first_line(api):
    data = example()
    data['changed'][0]['spans'][0].update(old_start=0, old_count=0, new_start=1, new_count=1)
    assert api.ImpactReport.model_validate(data).changed[0].spans[0].old_start == 0


@pytest.fixture
def mapping_case(tmp_path):
    import shutil
    from pathlib import Path

    from vgar.graph.builder import PythonGraphBuilder
    root = tmp_path / 'repo'
    shutil.copytree(Path(__file__).parent / 'fixtures/m1_w9_impact', root)
    document = PythonGraphBuilder(repo_key='demo/impact', repository_revision='fixture-v1').build(root)
    return root, document


def map_diff(root, document, raw):
    import os
    from pathlib import Path

    from vgar.graph.impact import diff_to_nodes
    from vgar.repair.patch import PatchPolicy
    policy = PatchPolicy(('app.py', 'other.py'), ('tests',))
    output = os.environ.get('M1_W9_MAPPING_EVIDENCE')
    directory = None
    if output:
        import uuid
        directory = Path(output) / uuid.uuid4().hex
        directory.mkdir(parents=True)
        (directory / 'input.diff').write_bytes(raw.encode('utf-8'))
        (directory / 'graph.json').write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    try:
        report = diff_to_nodes(raw, document, root, patch_policy=policy)
    except Exception as error:
        if directory:
            import traceback
            (directory / 'exception.json').write_text(json.dumps({'type': type(error).__name__,
                'message': str(error), 'traceback': traceback.format_exc()}), encoding='utf-8')
        raise
    if directory:
        (directory / 'mapping.json').write_text(report.canonical_json(), encoding='utf-8')
    return report


def patch(body, path='app.py'):
    return f'--- a/{path}\n+++ b/{path}\n' + body


def test_diff_to_nodes_modify_and_read_only(mapping_case):
    root, document = mapping_case
    before = {p.name: p.read_bytes() for p in root.glob('*.py')}
    original = copy.deepcopy(document)
    report = map_diff(root, document, patch('@@ -4,5 +4,5 @@\n def first(value):\n-    return value + 1\n+    return value + 3\n \n \n def second(value):\n'))
    expected = next(n['id'] for n in document['nodes'] if n['type'] == 'Function' and n['name'] == 'first')
    assert len(report.changed) == 1 and report.changed[0].node_id == expected
    assert report.changed[0].spans[0].old_start == 5
    assert not report.unmapped and report.impacted.status == 'NOT_COMPUTED'
    assert document == original and before == {p.name: p.read_bytes() for p in root.glob('*.py')}


@pytest.mark.parametrize('body,mapped', [
    ('@@ -4,0 +5 @@\n+    value = abs(value)\n', True),
    ('@@ -9,0 +10,2 @@\n+def third():\n+    return 3\n', False),
    ('@@ -0,0 +1 @@\n+FLAG2 = 1\n', False)])
def test_diff_to_nodes_add(mapping_case, body, mapped):
    root, document = mapping_case
    report = map_diff(root, document, patch(body))
    assert bool(report.changed) is mapped
    if mapped:
        assert report.changed[0].basis == 'insertion_in_existing_scope'
    else:
        assert report.unmapped[0].reason == 'NO_BASELINE_SYMBOL_AT_INSERTION'


def test_diff_to_nodes_delete(mapping_case):
    root, document = mapping_case
    report = map_diff(root, document, patch('@@ -8,2 +7,0 @@\n-def second(value):\n-    return value * 2\n'))
    expected = next(n['id'] for n in document['nodes'] if n['type'] == 'Function' and n['name'] == 'second')
    assert len(report.changed) == 1 and report.changed[0].node_id == expected
    assert report.changed[0].spans[0].new_count == 0


def test_diff_to_nodes_multifile_multihunk_and_unmapped(mapping_case):
    root, document = mapping_case
    raw = patch('@@ -1 +1 @@\n-FLAG = True\n+FLAG = False\n@@ -5 +5 @@\n-    return value + 1\n+    return value + 4\n')
    raw += patch('@@ -2 +2 @@\n-    return "old"\n+    return "new"\n', 'other.py')
    report = map_diff(root, document, raw)
    assert {n.path for n in report.changed} == {'app.py', 'other.py'}
    assert report.unmapped[0].reason == 'MODULE_LEVEL_CHANGE'
    assert next(n for n in report.changed if n.path == 'app.py').spans[0].hunk_index == 2


def test_diff_to_nodes_partial_block_is_not_dropped(mapping_case):
    root, document = mapping_case
    report = map_diff(root, document, patch('@@ -3,3 +3 @@\n-\n-def first(value):\n-    return value + 1\n+FLAG3 = 1\n'))
    assert report.changed and report.unmapped


@pytest.mark.parametrize('fault', ['source', 'extra_file', 'missing_file', 'hash', 'range', 'repo',
                                  'context', 'new_offset', 'protected', 'malformed', 'rename'])
def test_diff_to_nodes_rejects_invalid_input(mapping_case, fault):
    root, document = mapping_case
    raw = patch('@@ -5 +5 @@\n-    return value + 1\n+    return value + 3\n')
    if fault == 'source':
        (root / 'app.py').write_bytes(b'wrong\n')
    elif fault == 'extra_file':
        (root / 'extra.py').write_bytes(b'x=1\n')
    elif fault == 'missing_file':
        (root / 'other.py').unlink()
    elif fault == 'hash':
        next(n for n in document['nodes'] if n['type'] == 'Function')['content_hash'] = 'sha256:'+'0'*64
    elif fault == 'range':
        next(n for n in document['nodes'] if n['type'] == 'Function')['range']['start_col'] += 1
    elif fault == 'repo':
        document['repo_key'] = 'different/repo'
    elif fault == 'context':
        raw = raw.replace('return value + 1', 'return value + 2')
    elif fault == 'new_offset':
        raw = raw.replace('+5 @@', '+6 @@')
    elif fault == 'protected':
        raw = raw.replace('app.py', 'tests/test_x.py')
    elif fault == 'malformed':
        raw = raw.replace('-5 +5', '-5,2 +5')
    else:
        raw = raw.replace('+++ b/app.py', '+++ b/new.py')
    with pytest.raises(ValueError):
        map_diff(root, document, raw)


@pytest.mark.parametrize('newline,final', [('\n', True), ('\r\n', True), ('\n', False)])
def test_diff_to_nodes_ranges_nested_utf8_decorators(mapping_case, newline, final):
    from vgar.graph.builder import PythonGraphBuilder
    root, _ = mapping_case
    source = '@wrap\ndef outer():\n    def inner():\n        return "tên"\n    return inner()'
    if final:
        source += '\n'
    (root / 'app.py').write_bytes(source.replace('\n', newline).encode('utf-8'))
    document = PythonGraphBuilder(repo_key='demo/impact', repository_revision='fixture-v1').build(root)
    report = map_diff(root, document, patch('@@ -4 +4 @@\n-        return "tên"\n+        return "mới"\n'))
    expected = next(n['id'] for n in document['nodes'] if n['type'] == 'Function' and n['name'] == 'inner')
    assert len(report.changed) == 1 and report.changed[0].node_id == expected


def test_diff_to_nodes_ambiguous(mapping_case):
    root, document = mapping_case
    original = next(n for n in document['nodes'] if n['type'] == 'Function')
    twin = copy.deepcopy(original)
    twin['id'] += ':ambiguous'
    document['nodes'].append(twin)
    report = map_diff(root, document, patch('@@ -5 +5 @@\n-    return value + 1\n+    return value + 3\n'))
    assert not report.changed
    assert report.unmapped[0].reason == 'AMBIGUOUS_BASELINE_SYMBOL'


def test_diff_to_nodes_combines_insert_and_replace(mapping_case):
    root, document = mapping_case
    raw = patch('@@ -4,0 +5 @@\n+    value = abs(value)\n@@ -5 +6 @@\n-    return value + 1\n+    return value + 3\n')
    report = map_diff(root, document, raw)
    assert len(report.changed) == 1 and len(report.changed[0].spans) == 2
    assert report.changed[0].basis == 'baseline_changed_lines'
    assert report.patch_hash == 'sha256:' + __import__('hashlib').sha256(raw.encode('utf-8')).hexdigest()


def test_diff_to_nodes_modified_eof_without_final_newline(mapping_case):
    from vgar.graph.builder import PythonGraphBuilder
    root, _ = mapping_case
    (root / 'other.py').write_bytes(b'def label():\n    return "old"')
    document = PythonGraphBuilder(repo_key='demo/impact', repository_revision='fixture-v1').build(root)
    raw = patch('@@ -2 +2 @@\n-    return "old"\n\\ No newline at end of file\n+    return "new"\n\\ No newline at end of file\n', 'other.py')
    assert map_diff(root, document, raw).changed[0].path == 'other.py'


def test_diff_to_nodes_detects_mid_operation_source_change(mapping_case, monkeypatch):
    from vgar.graph import impact
    root, document = mapping_case
    original = impact._blocks
    def changing_blocks(*args):
        yield from original(*args)
        (root / 'other.py').write_bytes(b'CHANGED=1\n')
    monkeypatch.setattr(impact, '_blocks', changing_blocks)
    with pytest.raises(ValueError):
        map_diff(root, document, patch('@@ -5 +5 @@\n-    return value + 1\n+    return value + 3\n'))


def test_diff_to_nodes_link_is_rejected(mapping_case):
    root, document = mapping_case
    try:
        (root / 'alias.py').symlink_to(root / 'app.py')
    except OSError:
        pytest.skip('Creating a symlink requires Windows developer mode/privilege')
    with pytest.raises(ValueError, match='link'):
        map_diff(root, document, patch('@@ -5 +5 @@\n-    return value + 1\n+    return value + 3\n'))


@pytest.mark.parametrize('fault', ['empty', 'boolean_column'])
def test_diff_to_nodes_rejects_invalid_untouched_symbol(mapping_case, fault):
    import hashlib
    root, document = mapping_case
    node = next(n for n in document['nodes'] if n['type'] == 'Function' and n['path'] == 'other.py')
    if fault == 'empty':
        node['range'].update(end_byte=node['range']['start_byte'],
                             end_line=node['range']['start_line'], end_col=node['range']['start_col'])
        node['content_hash'] = 'sha256:' + hashlib.sha256(b'').hexdigest()
    else:
        node['range']['start_col'] = False
    with pytest.raises(ValueError):
        map_diff(root, document, patch('@@ -5 +5 @@\n-    return value + 1\n+    return value + 3\n'))


def test_diff_to_nodes_decorator_outside_symbol_remains_unmapped(mapping_case):
    from vgar.graph.builder import PythonGraphBuilder
    root, _ = mapping_case
    (root / 'app.py').write_bytes(b'@old\ndef first():\n    return 1\n')
    document = PythonGraphBuilder(repo_key='demo/impact', repository_revision='fixture-v1').build(root)
    report = map_diff(root, document, patch('@@ -1 +1 @@\n-@old\n+@new\n'))
    assert not report.changed and report.unmapped[0].reason == 'MODULE_LEVEL_CHANGE'
