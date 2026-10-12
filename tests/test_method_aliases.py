from __future__ import annotations

import hashlib
import json

import pytest

from vgar.graph.builder import PythonGraphBuilder, discover_python_files
from vgar.graph.grounding import TaskAnchorFinder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.scip_resolver import ScipConfig, source_fingerprint
from test_scip_enrichment import field, occurrence


def build(root, code, scip=None):
    (root / 'app.py').write_text(code, encoding='utf-8')
    return PythonGraphBuilder(repo_key='demo/aliases', repository_revision='test', scip=scip).build(root)


CODE = '''class Service:
    def implementation(self):
        return 1
    execute = implementation
    perform = execute
    def caller(self):
        return self.perform()
'''


def test_class_aliases_link_static_calls_and_ground_to_original_range(tmp_path):
    document = build(tmp_path, CODE)
    nodes = {n['id']: n for n in document['nodes']}
    implementation = next(n for n in nodes.values() if n['name']=='implementation')
    assert [a['name'] for a in implementation['properties']['symbol_aliases']] == ['execute', 'perform']
    assert implementation['range']['start_line'] == 2
    call = next(e for e in document['edges'] if e['type']=='CALLS')
    assert call['target_id'] == implementation['id']
    for query in ('Service.execute()', '`app.Service.perform`', '```python\nitem.execute()\n```'):
        anchors = TaskAnchorFinder(document).find_task_anchors(query).anchors
        assert implementation['id'] in [a.node_id for a in anchors]
    retriever = GraphContextRetriever(document, tmp_path, count_tokens=lambda text: len(text.split()), counter_label='words')
    assert retriever._task_similarity(implementation, {'execute'}) > retriever._task_similarity(implementation, {'unrelated'})
    result = retriever.retrieve([implementation['id']], 200)
    assert any(item.symbol == implementation['qualified_name'] and item.range.start_line == 2 for item in result.context.items)


@pytest.mark.parametrize('rewrite', [
    '    execute = external\n',
    '    del execute\n',
    '    if condition:\n        execute = external\n',
    '    from external import execute\n',
    '    for execute in values:\n        pass\n',
    '    try:\n        risky()\n    except Exception as execute:\n        pass\n',
    '    match value:\n        case {"x": execute}:\n            pass\n',
    '    exec("execute = external")\n',
])
def test_rebound_or_dynamic_class_alias_is_not_exported(tmp_path, rewrite):
    code = 'class Service:\n    def implementation(self): return 1\n    execute = implementation\n'+rewrite
    document = build(tmp_path, code)
    assert not any(a['name']=='execute' for n in document['nodes'] for a in n['properties'].get('symbol_aliases', []))
    assert not TaskAnchorFinder(document).find_task_anchors('Service.execute()').anchors


def test_copy_before_target_rebind_retains_original_implementation(tmp_path):
    document = build(tmp_path, 'class Service:\n    def implementation(self): return 1\n    execute = implementation\n    implementation = external\n')
    implementation = next(n for n in document['nodes'] if n['name']=='implementation')
    assert [a['name'] for a in implementation['properties']['symbol_aliases']] == ['execute']


def test_global_property_and_conditional_values_are_not_method_aliases(tmp_path):
    document = build(tmp_path, '''def external(): return 1
class Service:
    @property
    def value(self): return 1
    read = value
    execute = external
    if condition:
        def implementation(self): return 1
    perform = implementation
''')
    assert not any(n['properties'].get('symbol_aliases') for n in document['nodes'])


def test_scip_alias_assignment_definition_maps_to_implementation(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    code = 'class Service:\n    def implementation(self): return 1\n    execute = implementation\n    def caller(self):\n        return self.execute()\n'
    (root / 'app.py').write_text(code, encoding='utf-8')
    destination = tmp_path / 'bundle'
    destination.mkdir()
    symbols = [occurrence('Service.execute', [2, 4, 11], 1), occurrence('Service.execute', [4, 20, 27])]
    data = field(1, field(2, field(1, 'test-scip')+field(2, '1'))+field(3, root.as_uri()))
    data += field(2, field(1, 'app.py')+field(6, 2)+b''.join(field(2, o) for o in symbols))
    (destination / 'index.scip').write_bytes(data)
    (destination / 'manifest.json').write_text(json.dumps({'sources': source_fingerprint(root, discover_python_files(root)), 'index_sha256': hashlib.sha256(data).hexdigest()}), encoding='utf-8')
    document = build(root, code, ScipConfig(bundle=destination / 'manifest.json', strict=True))
    call = next(e for e in document['edges'] if e['type']=='CALLS')
    assert call['properties']['binding_kind'] == 'scip'
    assert next(n for n in document['nodes'] if n['id']==call['target_id'])['name'] == 'implementation'
