from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder, discover_python_files
from vgar.graph.scip_resolver import ScipConfig, ScipResolver, source_fingerprint
from vgar.graph.scip_wire import read_index
from vgar.observability.graph_trace import GraphTrace
from vgar.graph.scip_profile import auxiliary_fingerprint, local_profile, runtime_fingerprint
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
from vgar.graph.test_selection import select_related_tests


def varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode()
    return varint((number << 3) | 2) + varint(len(value)) + value


def occurrence(symbol, bounds, roles=0, *, typed=False):
    location = field(8, b''.join(field(i + 1, v) for i, v in enumerate(bounds))) if typed else field(1, b''.join(varint(v) for v in bounds))
    return location + field(2, symbol) + field(3, roles)


def bundle(root, destination, *, external=False, unicode=False, encoding=2, typed=False):
    destination.mkdir()
    prefix = '    "🚀"; ' if unicode else '    '
    (root / 'app.py').write_text('class Worker:\n    def execute(self):\n        return 1\n\ndef run():\n' + prefix + 'worker.execute()\n', encoding='utf-8')
    column = len(prefix.encode('utf-16-le')) // 2 if encoding == 2 else len(prefix.encode('utf-8')) if encoding == 1 else len(prefix)
    symbols = [occurrence('worker.execute', [1, 8, 15], 1, typed=typed),
               occurrence('external.execute' if external else 'worker.execute', [5, column + 7, column + 14], typed=typed)]
    metadata = field(2, field(1, 'test-scip') + field(2, '1')) + field(3, root.as_uri())
    doc = field(1, 'app.py') + field(6, encoding) + b''.join(field(2, value) for value in symbols)
    data = field(1, metadata) + field(2, doc)
    (destination / 'index.scip').write_bytes(data)
    manifest = {'sources': source_fingerprint(root, discover_python_files(root)), 'index_sha256': hashlib.sha256(data).hexdigest()}
    (destination / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return destination / 'manifest.json'


def build(root, config, trace=None):
    return PythonGraphBuilder(repo_key='demo/scip', repository_revision='test', scip=config, trace=trace).build(root)


@pytest.mark.parametrize('declared_subset', [True, False])
def test_subset_index_root_is_rebased_only_for_the_declared_target(tmp_path, declared_subset):
    root = tmp_path/'repo'
    subset = root/'src'
    subset.mkdir(parents=True)
    manifest = bundle(subset, tmp_path/'bundle')
    info = json.loads(manifest.read_text(encoding='utf-8'))
    info['sources'] = source_fingerprint(root, discover_python_files(root))
    if declared_subset:
        info['target_only'] = 'src'
    manifest.write_text(json.dumps(info), encoding='utf-8')
    if not declared_subset:
        with pytest.raises(ValueError, match='another repository root'):
            build(root, ScipConfig(bundle=manifest, strict=True))
        return
    graph = build(root, ScipConfig(bundle=manifest, strict=True))
    edge = next(e for e in graph['edges'] if e['type']=='CALLS')
    assert edge['properties']['binding_kind'] == 'scip'
    assert ':src/app.py:' in edge['target_id']
    report = graph['statistics']['resolver']
    assert report['indexed_root_uri'] == subset.as_uri()
    assert report['target_only'] == 'src'


@pytest.mark.parametrize('path', ['../app.py', '/app.py', 'C:/app.py'])
def test_subset_document_cannot_escape_the_verified_root(tmp_path, path):
    root = tmp_path/'repo'
    subset = root/'src'
    subset.mkdir(parents=True)
    manifest = bundle(subset, tmp_path/'bundle')
    index_path = manifest.parent/'index.scip'
    raw = index_path.read_bytes() + field(2, field(1, path) + field(6, 2))
    index_path.write_bytes(raw)
    info = json.loads(manifest.read_text(encoding='utf-8'))
    info.update(sources=source_fingerprint(root, discover_python_files(root)), target_only='src',
                index_sha256=hashlib.sha256(raw).hexdigest())
    manifest.write_text(json.dumps(info), encoding='utf-8')
    with pytest.raises(ValueError, match='Unsafe SCIP subset'):
        build(root, ScipConfig(bundle=manifest, strict=True))


@pytest.mark.parametrize('encoding,typed', [(1, False), (2, False), (3, False), (2, True)])
def test_scip_links_untyped_receiver_and_unicode_columns(tmp_path, encoding, typed):
    root = tmp_path / 'repo'
    root.mkdir()
    manifest = bundle(root, tmp_path / 'bundle', unicode=True, encoding=encoding, typed=typed)
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    edge = next(e for e in document['edges'] if e['type'] == 'CALLS')
    assert edge['properties']['binding_kind'] == 'scip'
    assert edge['provenance']['source_tool'] == 'test-scip'
    assert edge['confidence'] == .98
    assert document['statistics']['resolver']['active'] == 'scip'
    static = build(root, None)
    assert not any(e['type'] == 'CALLS' for e in static['edges'])
    assert static['graph_version'] != document['graph_version']


def test_scip_external_binding_does_not_use_internal_name_guess(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    manifest = bundle(root, tmp_path / 'bundle', external=True)
    document = build(root, ScipConfig(bundle=manifest))
    assert not any(e['type'] == 'CALLS' for e in document['edges'])
    call = next(n for n in document['nodes'] if n['type'] == 'CallSite')
    assert call['properties']['resolution_reason'] == 'external_or_non_callable'


@pytest.mark.parametrize('codec,text', [('latin-1', 'caf\u00e9'), ('cp1251', '\u043f\u0440\u0438\u0432\u0435\u0442')])
def test_non_utf8_document_is_isolated_without_losing_valid_scip_calls(tmp_path, codec, text):
    root = tmp_path/'repo'
    root.mkdir()
    manifest_path = bundle(root, tmp_path/'bundle')
    bad = root/'fixture.py'
    original = (f'# coding: {codec}\n# {text}\ndef other(): return 0\n').encode(codec)
    bad.write_bytes(original)
    index_path = manifest_path.parent/'index.scip'
    # Unsupported document deliberately reuses the good symbol's definition:
    # its occurrences must not contaminate the verified UTF-8 mapping.
    extra = field(1, 'fixture.py') + field(6, 2) + field(2, occurrence('worker.execute', [2, 4, 9], 1))
    data = index_path.read_bytes() + field(2, extra)
    index_path.write_bytes(data)
    manifest = json.loads(manifest_path.read_text())
    manifest.update(sources=source_fingerprint(root, discover_python_files(root)), index_sha256=hashlib.sha256(data).hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    log = tmp_path/'debug.jsonl'
    document = build(root, ScipConfig(bundle=manifest_path, strict=True), GraphTrace(log))
    calls = [e for e in document['edges'] if e['type']=='CALLS']
    assert len(calls)==1 and calls[0]['properties']['binding_kind']=='scip'
    report = document['statistics']['resolver']
    assert report['active']=='scip'
    assert report['definition_mapping']['usable_document_count']==1
    assert report['definition_mapping']['skipped_documents']==[{'path':'fixture.py','reason':'source_encoding_not_utf8'}]
    events = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert any(e['event']=='resolver_document_skipped' and e['path']=='fixture.py' for e in events)
    assert bad.read_bytes()==original
    run = next(n for n in document['nodes'] if n['name']=='run')
    result = GraphContextRetriever(document, root, count_tokens=lambda _:1, counter_label='fixture').retrieve([run['id']], 100)
    assert any(item.symbol=='app.Worker.execute' for item in result.context.items)


def test_unsupported_encoding_does_not_hide_a_stale_snapshot(tmp_path):
    (tmp_path/'fixture.py').write_bytes(b'# coding: latin-1\n# caf\xe9\n')
    index = dict(documents=[dict(path='fixture.py', encoding=2, occurrences=[])], source_fingerprint={'fixture.py':'stale'})
    with pytest.raises(ValueError, match='Source changed'):
        ScipResolver(index, tmp_path, [])


@pytest.mark.parametrize('rebound', [False, True])
def test_classmethod_parameter_has_conservative_fallback(tmp_path, rebound):
    root = tmp_path / 'repo'
    root.mkdir()
    code = 'class Factory:\n    @classmethod\n    def create(cls):\n'
    if rebound:
        code += '        cls = other\n'
    code += '        return cls()\n'
    (root / 'app.py').write_text(code, encoding='utf-8')
    directory = tmp_path / 'bundle'
    directory.mkdir()
    symbols = [occurrence('parameter.cls', [2, 15, 18], 1), occurrence('parameter.cls', [4 if rebound else 3, 15, 18])]
    data = field(1, field(2, field(1, 'test-scip') + field(2, '1')) + field(3, root.as_uri()))
    data += field(2, field(1, 'app.py') + field(6, 2) + b''.join(field(2, item) for item in symbols))
    (directory / 'index.scip').write_bytes(data)
    manifest = {'sources': source_fingerprint(root, discover_python_files(root)), 'index_sha256': hashlib.sha256(data).hexdigest()}
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    document = build(root, ScipConfig(bundle=directory / 'manifest.json', strict=True))
    calls = [edge for edge in document['edges'] if edge['type'] == 'CALLS']
    assert bool(calls) is not rebound
    if calls:
        assert calls[0]['properties']['binding_kind'] == 'classmethod_constructor'
        assert calls[0]['confidence'] == .8


@pytest.mark.parametrize('fault', ['stale_source', 'index_checksum', 'missing_index'])
def test_invalid_bundle_falls_back_or_fails_strictly(tmp_path, fault):
    root = tmp_path / 'repo'
    root.mkdir()
    manifest = bundle(root, tmp_path / 'bundle')
    if fault == 'stale_source':
        with (root / 'app.py').open('a') as stream:
            stream.write('\n# changed\n')
    elif fault == 'index_checksum':
        with (manifest.parent / 'index.scip').open('ab') as stream:
            stream.write(b'\x00')
    else:
        (manifest.parent / 'index.scip').unlink()
    document = build(root, ScipConfig(bundle=manifest))
    assert document['statistics']['resolver']['status'] == 'fallback'
    with pytest.raises((ValueError, OSError)):
        build(root, ScipConfig(bundle=manifest, strict=True))


def test_indexer_timeout_and_missing_command_are_recorded(tmp_path, capsys):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'app.py').write_text('def f(): return 1\n')
    log = tmp_path / 'debug.jsonl'
    config = ScipConfig(command=(sys.executable, '-c', 'import time; time.sleep(30)'),
                        timeout_seconds=.2, output_directory=tmp_path / 'indexes')
    document = build(root, config, GraphTrace(log))
    assert document['statistics']['resolver']['error_type'] == 'TimeoutError'
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(event['event'] == 'resolver_fallback' for event in events)
    assert capsys.readouterr().out == ''
    assert build(root, ScipConfig())['statistics']['resolver']['error_type'] == 'FileNotFoundError'


@pytest.mark.parametrize('data', [b'\x00', b'\x12\x80', b'\x12\x04x', b'\x0b'])
def test_malformed_protobuf_is_rejected(data):
    with pytest.raises(ValueError):
        read_index(data)


def test_debug_failure_does_not_break_graph(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'app.py').write_text('def f(): pass\n')
    blocked = tmp_path / 'file'
    blocked.write_text('not a directory')
    document = build(root, None, GraphTrace(blocked / 'debug.jsonl'))
    assert document['nodes']


def test_same_named_local_variable_is_not_a_function_definition(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'app.py').write_text('def execute():\n    execute = callback\n    return execute()\n', encoding='utf-8')
    directory = tmp_path / 'bundle'
    directory.mkdir()
    symbols = [occurrence('function.execute', [0, 4, 11], 1),
               occurrence('local 1', [1, 4, 11], 1), occurrence('local 1', [2, 11, 18])]
    data = field(1, field(2, field(1, 'test-scip') + field(2, '1')) + field(3, root.as_uri()))
    data += field(2, field(1, 'app.py') + field(6, 2) + b''.join(field(2, item) for item in symbols))
    (directory / 'index.scip').write_bytes(data)
    manifest = {'sources': source_fingerprint(root, discover_python_files(root)), 'index_sha256': hashlib.sha256(data).hexdigest()}
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    document = build(root, ScipConfig(bundle=directory / 'manifest.json', strict=True))
    assert not any(e['type'] == 'CALLS' for e in document['edges'])
    call = next(n for n in document['nodes'] if n['type'] == 'CallSite')
    assert call['properties']['resolution_reason'] == 'local_non_callable'


def chain_bundle(tmp_path, *, mutation='', annotation=False, outer_status=None, overrides=1, setter_edit=None):
    root = tmp_path / 'repo'
    root.mkdir()
    code = 'class Processor:\n    def execute(self): return 1\n'
    code += ''.join(f'class Variant{i}(Processor):\n    def execute(self): return 2\n' for i in range(overrides))
    code += 'class Box:\n'
    if annotation:
        code += '    def get_processor(self) -> Processor:\n        return Processor()\n'
    else:
        code += ('    def get_processor(self):\n        return self.value\n'
                 '    def set_processor(self, item):\n'
                 '        if not isinstance(item, Processor):\n            raise TypeError()\n'
                 '        self.value = item\n')
    code += mutation
    code += 'def test_run():\n    box.get_processor().execute()\n'
    if setter_edit:
        code = code.replace(*setter_edit)
    (root / 'test_app.py').write_text(code, encoding='utf-8')
    lines = code.splitlines()
    declaration = next(i for i, line in enumerate(lines) if 'def get_processor' in line)
    call_line = len(lines) - 1
    getter_start = lines[declaration].index('get_processor')
    inner_start = lines[call_line].index('get_processor')
    occurrences = [occurrence('Box.get_processor', [declaration, getter_start, getter_start + len('get_processor')], 1),
                   occurrence('Box.get_processor', [call_line, inner_start, inner_start + len('get_processor')])]
    if outer_status:
        start = lines[call_line].index('execute')
        occurrences.append(occurrence('external.execute', [call_line, start, start + len('execute')]))
    directory = tmp_path / 'bundle'
    directory.mkdir()
    data = field(1, field(2, field(1, 'test-scip') + field(2, '1')) + field(3, root.as_uri()))
    data += field(2, field(1, 'test_app.py') + field(6, 2) + b''.join(field(2, o) for o in occurrences))
    (directory / 'index.scip').write_bytes(data)
    manifest = {'sources': source_fingerprint(root, discover_python_files(root)), 'index_sha256': hashlib.sha256(data).hexdigest()}
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    return root, directory / 'manifest.json'


@pytest.mark.parametrize('annotation', [False, True])
def test_chain_return_contract_keeps_possible_overrides_as_references(tmp_path, annotation):
    root, manifest = chain_bundle(tmp_path, annotation=annotation)
    log = tmp_path / 'debug.jsonl'
    document = build(root, ScipConfig(bundle=manifest, strict=True), GraphTrace(log))
    nodes = {n['id']: n for n in document['nodes']}
    outer = next(n for n in document['nodes'] if n['type'] == 'CallSite' and n['name'] == 'box.get_processor().execute')
    refs = [e for e in document['edges'] if e['source_id'] == outer['id'] and e['type'] == 'REFERENCES']
    assert {nodes[e['target_id']]['qualified_name'] for e in refs} == {'test_app.Processor.execute', 'test_app.Variant0.execute'}
    assert outer['properties']['resolution_status'] == 'unresolved'
    assert outer['properties']['candidate_count'] == 0
    assert outer['properties']['reference_candidate_count'] == 2
    assert not any(e['source_id'] == outer['id'] and e['type'] == 'CALLS' for e in document['edges'])
    assert all(e['properties']['runtime_dispatch_verified'] is False for e in refs)
    expected = 'return_annotation' if annotation else 'guarded_field'
    assert all(e['properties']['evidence']['kind'] == expected for e in refs)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(e['event'] == 'call_reference_hint' for e in events)
    test = next(n for n in document['nodes'] if n['type'] == 'Test')
    retriever = GraphContextRetriever(document, root, count_tokens=lambda s: len(s.split()), counter_label='test', config=RetrievalConfig(max_hops=1))
    result = retriever.retrieve([test['id']], 1000)
    candidate = next(c for c in result.candidates if c['symbol'] == 'test_app.Processor.execute')
    assert candidate['graph_distance'] == 1
    assert any(r.startswith('MEMBER_REFERENCE:') for r in candidate['graph_rationale'])
    selected = select_related_tests(document, [refs[0]['target_id']], failing_tests=['tests/test_app.py::test_fail'])
    assert selected['selection_mode'] == 'failing_tests'
    assert selected['tests'] == ['tests/test_app.py::test_fail']


@pytest.mark.parametrize('mutation', [
    '    def replace(self, item):\n        self.value = item\n',
    '    def replace(self):\n        del self.value\n',
    '    def replace(self):\n        self.value = object()\n',
])
def test_chain_guard_contract_rejects_other_field_writes(tmp_path, mutation):
    root, manifest = chain_bundle(tmp_path, mutation=mutation)
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    assert not any(e['type'] == 'REFERENCES' for e in document['edges'])


def test_chain_hint_never_overrides_authoritative_external_binding(tmp_path):
    root, manifest = chain_bundle(tmp_path, outer_status='external')
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    assert not any(e['type'] == 'REFERENCES' for e in document['edges'])


def test_chain_hints_reject_truncated_override_families(tmp_path):
    root, manifest = chain_bundle(tmp_path, overrides=17)
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    assert not any(e['type'] == 'REFERENCES' for e in document['edges'])
    assert document['statistics']['resolver']['chain_reference_statuses']['return_contract_candidate_limit'] == 1


@pytest.mark.parametrize('setter_edit', [
    ('set_processor(self, item)', 'set_processor(self, item, Processor)'),
    ('        self.value = item', '        item = object()\n        self.value = item'),
    ('class Processor:', 'isinstance = custom_check\nclass Processor:'),
    ('    def set_processor(self, item):', '    @staticmethod\n    def set_processor(self, item):'),
])
def test_chain_contract_rejects_shadowed_guards_and_reassigned_parameter(tmp_path, setter_edit):
    root, manifest = chain_bundle(tmp_path, setter_edit=setter_edit)
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    assert not any(e['type'] == 'REFERENCES' for e in document['edges'])


def test_reference_snippet_reservation_is_bounded_and_does_not_change_rank(tmp_path):
    root, manifest = chain_bundle(tmp_path)
    document = build(root, ScipConfig(bundle=manifest, strict=True))
    nodes = {n['qualified_name']: n for n in document['nodes']}
    test = nodes['test_app.test_run']['id']
    base = nodes['test_app.Processor.execute']['id']
    history = {test: 100, nodes['test_app.Box.get_processor']['id']: 50,
               nodes['test_app.Variant0.execute']['id']: 25}
    weights = {name: float(name == 'recent_change_frequency') for name in RetrievalConfig().weights}
    def retrieve(fraction):
        retriever = GraphContextRetriever(document, root,
            count_tokens=lambda s: 2 if s.startswith('def test_run') else 4 if s.startswith('def get_processor') else 3,
            counter_label='synthetic-budget', change_counts=history, history_label='synthetic ordering',
            config=RetrievalConfig(max_hops=1, weights=weights, reference_budget_fraction=fraction))
        return retriever.retrieve([test], 7, include=lambda n: n['type'] in {'Function', 'Method', 'Test'})
    ordinary, reserved = retrieve(0), retrieve(0.5)
    assert base not in {i.node_id for i in ordinary.context.items}
    assert base in {i.node_id for i in reserved.context.items}
    assert [c['node_id'] for c in ordinary.candidates] == [c['node_id'] for c in reserved.candidates]
    assert reserved.config['reference_reserved_tokens'] == 3
    assert reserved.context.total_token_count == 5
    assert reserved.context.total_token_count <= reserved.context.token_budget


def test_managed_profile_is_local_keeps_settings_and_cleans_on_exception(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'lib').mkdir()
    original = b'[tool.pyright]\npythonVersion = "3.10"\nextraPaths = ["custom"]\n'
    (tmp_path / 'pyproject.toml').write_bytes(original)
    with pytest.raises(RuntimeError):
        with local_profile(tmp_path) as profile:
            config = json.loads((tmp_path / 'scip-pyrightconfig.json').read_text())
            assert config['extraPaths'] == ['custom', 'src', 'lib']
            assert config['pythonVersion'] == '3.10'
            assert profile['mode'] == 'managed_local'
            raise RuntimeError('simulated indexer failure')
    assert not (tmp_path / 'scip-pyrightconfig.json').exists()
    assert (tmp_path / 'pyproject.toml').read_bytes() == original


def test_existing_jsonc_config_is_not_overwritten(tmp_path):
    config = tmp_path / 'pyrightconfig.json'
    data = b'{ // project settings\n "extraPaths": ["custom"]\n}'
    config.write_bytes(data)
    with local_profile(tmp_path) as profile:
        assert profile['mode'] == 'existing_json'
        assert not (tmp_path / 'scip-pyrightconfig.json').exists()
    assert config.read_bytes() == data


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/absolute', 'src\\bad'])
def test_unsafe_import_root_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        with local_profile(tmp_path, roots=(path,)):
            pass


def test_stub_and_config_change_invalidate_bundle(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    manifest = bundle(root, tmp_path / 'bundle')
    (root / 'app.pyi').write_text('class Worker: ...\n')
    with pytest.raises(ValueError, match='config/stub'):
        build(root, ScipConfig(bundle=manifest, strict=True))


def test_profile_detects_concurrent_edit_and_retains_modified_file(tmp_path):
    with pytest.raises(ValueError, match='changed'):
        with local_profile(tmp_path):
            (tmp_path / 'scip-pyrightconfig.json').write_text('{"extraPaths": ["user"]}')
    assert json.loads((tmp_path / 'scip-pyrightconfig.json').read_text())['extraPaths'] == ['user']


def test_runtime_hash_includes_actual_dist_bundle(tmp_path):
    entry = tmp_path / 'index.js'
    entry.write_text('require("./dist/scip-python");')
    (tmp_path / 'dist').mkdir()
    bundle_path = tmp_path / 'dist/scip-python.js'
    bundle_path.write_text('version1')
    (tmp_path / 'package.json').write_text('{}')
    first = runtime_fingerprint((str(entry),))
    bundle_path.write_text('version2')
    second = runtime_fingerprint((str(entry),))
    assert first[str(entry)] == second[str(entry)]
    assert first[str(bundle_path)] != second[str(bundle_path)]


def test_indexer_python_path_matches_inventory_interpreter(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'app.py').write_text('def f(): return 1\n')
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node required to verify the actual indexer subprocess lookup')
    code = "console.log(require('child_process').execFileSync('python', ['-c', 'import sys;print(sys.prefix)'], {encoding: 'utf8'}).trim())"
    config = ScipConfig(command=(node, '-e', code), output_directory=tmp_path / 'index')
    document = build(root, config)
    report = document['statistics']['resolver']
    output = Path(report['log_directory']) / 'stdout.log'
    assert Path(output.read_text().strip()) == Path(sys.prefix)
    assert Path(report['python_executable']) == Path(sys.executable).absolute()
    assert not (root / 'scip-pyrightconfig.json').exists()
