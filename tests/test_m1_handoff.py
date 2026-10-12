from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys

import pytest

from vgar.contracts.context import ContextPayload
from vgar.contracts.handoff import adapt_test_hints, payload_digest, validate_context_handoff
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.handoff import create_context_handoff, write_context_handoff
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


@pytest.fixture(params=['single', 'multi', 'method'])
def handoff_case(tmp_path, request):
    root = tmp_path / 'source có khoảng trắng'
    root.mkdir()
    if request.param == 'single':
        sources = {'app.py': 'def login(value):\n    return bool(value)\n',
                   'tests/test_app.py': 'from app import login\ndef test_login(): assert login("ok")\n'}
        targets = ['app.py']
    elif request.param == 'multi':
        sources = {'app.py': 'from money import tax\ndef total(value): return tax(value)\n',
                   'money.py': 'def tax(value): return value * 1.1\n',
                   'tests/test_app.py': 'from app import total\ndef test_total(): assert total(10) == 11\n'}
        targets = ['app.py', 'money.py']
    else:
        sources = {'app.py': 'class Service:\r\n    def normalize(self, name):\r\n        """Tên người dùng."""\r\n        return name.strip()\r\n',
                   'tests/test_app.py': 'from app import Service\ndef test_normalize(): assert Service().normalize(" a ") == "a"\n'}
        targets = ['app.py']
    for path, source in sources.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.encode('utf-8'))
    doc = PythonGraphBuilder(repo_key='demo/handoff', repository_revision='approved-fixture').build(root)
    anchors = [n['id'] for n in doc['nodes'] if n['path'] in targets and n['type'] in {'Function', 'Method'}]
    store = SQLiteGraphStore(tmp_path / 'graph.db')
    store.ingest(doc)
    service = SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label='test:characters')
    response = service.get_related_context(anchors, 10000, graph_version=doc['graph_version'], task_id='handoff')
    bundle = create_context_handoff(doc, response, root, count_tokens=len, counter_label='test:characters',
                                    changed_paths=targets, failing_tests=['tests/test_app.py'])
    return root, doc, bundle, targets


def receive(root, bundle):
    manifest = bundle['manifest']
    return validate_context_handoff(bundle['context'], manifest, root,
        expected_graph_version=manifest['graph_version'], expected_repo_key='demo/handoff',
        expected_revision='approved-fixture', count_tokens=len, counter_label='test:characters')


def test_roundtrip_portable_source_and_m2_mapping(handoff_case, tmp_path):
    root, doc, bundle, targets = handoff_case
    destination = tmp_path / 'consumer clone'
    shutil.copytree(root, destination)
    validated = receive(destination, json.loads(json.dumps(bundle)))
    assert isinstance(validated, ContextPayload)
    assert {item.path for item in validated.items} >= set(targets)
    hints = adapt_test_hints(bundle['test_hints'], bundle['manifest'], destination)
    assert hints['failing_selectors'] == ('tests/test_app.py',)
    assert all(hints['test_links'][path] for path in targets)
    assert all(isinstance(values, tuple) for values in hints['test_links'].values())
    output = write_context_handoff(bundle, tmp_path / 'export')
    assert json.loads((output / 'context.json').read_text(encoding='utf-8')) == bundle['context']
    assert (output / 'context_manifest.json').is_file() and (output / 'test_links.json').is_file()
    assert '\r\n' in next(item.snippet for item in validated.items if item.path == 'app.py') or not b'\r\n' in (root / 'app.py').read_bytes()
    assert 'schema_version' not in bundle['context']
    assert bundle['manifest']['source_digest']
    with pytest.raises(FileExistsError):
        write_context_handoff(bundle, output)
    # The exported prompt must preserve source CRLF rather than double it on Windows.
    prompt_bytes = (output / 'repair-context.txt').read_bytes()
    for item in validated.items:
        assert item.snippet.encode('utf-8') in prompt_bytes


@pytest.mark.parametrize('fault', ['source_edit', 'added_file', 'missing_file', 'context_hash', 'snippet',
                                 'range', 'node', 'token_count', 'file_hash', 'snapshot', 'empty', 'missing_binding'])
def test_invalid_context_rejected_before_prompt(handoff_case, fault):
    root, doc, original, targets = handoff_case
    bundle = copy.deepcopy(original)
    context = bundle['context']
    item = context['items'][0]
    if fault == 'source_edit':
        (root / targets[0]).write_bytes((root / targets[0]).read_bytes() + b'\n# modified\n')
    elif fault == 'added_file':
        (root / 'added.py').write_text('x = 1\n')
    elif fault == 'missing_file':
        (root / targets[0]).unlink()
    elif fault == 'context_hash':
        item['relevance_score'] = .0123
    elif fault == 'snippet':
        item['snippet'] = 'pass'
    elif fault == 'range':
        item['range']['start_col'] += 1
    elif fault == 'node':
        item['node_id'] = 'unbound-node'
    elif fault == 'token_count':
        item['token_count'] += 1
        context['total_token_count'] += 1
    elif fault == 'file_hash':
        bundle['manifest']['files'][targets[0]] = 'sha256:' + '0' * 64
    elif fault == 'snapshot':
        bundle['manifest']['graph_version'] = 'different-snapshot'
    elif fault == 'empty':
        context['items'] = []
        context['total_token_count'] = 0
    else:
        del bundle['manifest']['items'][item['node_id']]
    # Even a recomputed transport hash must not bypass source/range/token binding.
    if fault != 'context_hash':
        bundle['manifest']['context_sha256'] = payload_digest(context)
    with pytest.raises(ValueError):
        receive(root, bundle)


def test_identity_counter_and_source_scope_are_explicit(handoff_case):
    root, _, bundle, _ = handoff_case
    manifest = bundle['manifest']
    for field, value in [('expected_graph_version', 'wrong'), ('expected_repo_key', 'other/repo'),
                         ('expected_revision', 'wrong'), ('counter_label', 'other-counter')]:
        kwargs = dict(expected_graph_version=manifest['graph_version'], expected_repo_key=manifest['repo_key'],
                      expected_revision=manifest['repository_revision'], count_tokens=len, counter_label='test:characters')
        kwargs[field] = value
        with pytest.raises(ValueError):
            validate_context_handoff(bundle['context'], manifest, root, **kwargs)
    (root / 'README.txt').write_text('Not part of the declared Python source inventory.')
    assert receive(root, bundle)


@pytest.mark.parametrize('selector', ['../outside.py::test_x', '--collect-only', 'missing.py::test_x',
                                    'tests/test_app.py\n--option'])
def test_invalid_test_hints_rejected(handoff_case, selector):
    root, _, original, _ = handoff_case
    bundle = copy.deepcopy(original)
    bundle['test_hints']['failing_selectors'] = [selector]
    with pytest.raises(ValueError):
        adapt_test_hints(bundle['test_hints'], bundle['manifest'], root)


def test_missing_links_keep_failing_or_selected_fallback(handoff_case):
    root, doc, bundle, targets = handoff_case
    without_links = {**doc, 'edges': [e for e in doc['edges'] if e['type'] != 'TESTS']}
    # A distinct graph is not reused as source binding: only build fresh test hints.
    from vgar.graph.handoff import create_test_hints
    hints = create_test_hints(without_links, bundle['manifest'], changed_paths=targets,
                              failing_tests=['tests/test_app.py'], selected_tests=['tests'])
    adapted = adapt_test_hints(hints, bundle['manifest'], root)
    assert adapted['failing_selectors'] == ('tests/test_app.py',)
    assert adapted['fallback_scope'] == ('tests',)
    assert not any(adapted['test_links'].values())
    assert hints['coverage_verified'] is False and hints['collection_verified'] is False


def test_token_callback_source_mutation_is_detected(handoff_case):
    root, _, bundle, targets = handoff_case
    manifest = bundle['manifest']
    def mutation_counter(text):
        (root / targets[0]).write_bytes((root / targets[0]).read_bytes() + b'\n')
        return len(text)
    with pytest.raises(ValueError):
        validate_context_handoff(bundle['context'], manifest, root,
            expected_graph_version=manifest['graph_version'], expected_repo_key=manifest['repo_key'],
            expected_revision=manifest['repository_revision'], count_tokens=mutation_counter, counter_label='test:characters')


def test_consumer_import_does_not_load_graph_mcp_or_models():
    code = '''import sys
from vgar.contracts.handoff import validate_context_handoff, adapt_test_hints
assert not any(name.startswith(('vgar.graph', 'vgar.mcp', 'torch', 'transformers', 'tree_sitter')) for name in sys.modules)
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, shell=False, timeout=15)
    assert result.returncode == 0, result.stderr
