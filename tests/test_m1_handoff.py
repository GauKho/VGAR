from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.contracts.context import ContextPayload
from vgar.contracts.consumer import HandoffTarget, diagnose_changed_paths, receive_context_handoff
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
    assert all(not adapted['test_links'][path] for path in targets)
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
from vgar.contracts.consumer import HandoffTarget, receive_context_handoff
assert not any(name.startswith(('vgar.graph', 'vgar.mcp', 'torch', 'transformers', 'tree_sitter')) for name in sys.modules)
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, shell=False, timeout=15)
    assert result.returncode == 0, result.stderr


def approved_target(document):
    # Identity comes from the task's producer snapshot, not a received manifest.
    return dict(task_id='handoff-task', repo_key='demo/handoff',
                repository_revision='approved-fixture', graph_version=document['graph_version'])


def test_consumer_receives_clone_and_regenerates_prompt(handoff_case, tmp_path):
    root, document, bundle, _ = handoff_case
    destination = tmp_path / 'M2 clone có khoảng trắng'
    shutil.copytree(root, destination)
    exported = write_context_handoff(bundle, tmp_path / 'bundle')
    (exported / 'repair-context.txt').write_text('UNTRUSTED PRODUCER PROMPT', encoding='utf-8')
    received = receive_context_handoff(exported, destination, approved_target(document),
                                       count_tokens=len, counter_label='test:characters')
    assert received['context'] == bundle['context']
    assert 'UNTRUSTED PRODUCER PROMPT' not in received['context_text']
    for item in bundle['context']['items']:
        assert item['snippet'] in received['context_text']
        assert item['path'] in received['context_text']
        assert item['symbol'] in received['context_text']
    assert received['metadata']['token_budget_unit'] == 'snippets-only'
    assert received['metadata']['collection_verified'] is False


@pytest.mark.parametrize('field', ['repo_key', 'repository_revision', 'graph_version'])
def test_consumer_rejects_independent_target_mismatch(handoff_case, tmp_path, field):
    root, document, bundle, _ = handoff_case
    exported = write_context_handoff(bundle, tmp_path / 'bundle')
    target = {**approved_target(document), field: 'wrong-target'}
    with pytest.raises(ValueError, match='identity'):
        receive_context_handoff(exported, root, target, count_tokens=len, counter_label='test:characters')


@pytest.mark.parametrize('identity', ['', '   ', 123])
def test_consumer_target_does_not_default_identity(identity):
    with pytest.raises(ValueError):
        HandoffTarget.model_validate(dict(task_id='task', repo_key=identity,
            repository_revision='revision', graph_version='graph'))


def test_adapter_preserves_limits_without_losing_failing_tests(handoff_case):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    hints['link_details'][targets[0]].update(truncated=True, traversal_limited=True)
    adapted = adapt_test_hints(hints, bundle['manifest'], root)
    diagnostics = adapted['diagnostics']
    assert targets[0] in diagnostics['limited_targets']
    assert diagnostics['link_details'][targets[0]] == hints['link_details'][targets[0]]
    assert adapted['failing_selectors'] == ('tests/test_app.py',)
    assert diagnostics['coverage_verified'] is False
    assert diagnostics['collection_verified'] is False
    # Consumer mutations must not change the source hint object.
    diagnostics['link_details'][targets[0]]['candidates'].clear()
    assert hints['link_details'][targets[0]]['candidates']


@pytest.mark.parametrize('field,value', [('truncated', 'false'), ('traversal_limited', 0),
                                       ('fallback_reason', False), ('candidates', {})])
def test_adapter_rejects_ambiguous_limit_metadata(handoff_case, field, value):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    hints['link_details'][targets[0]][field] = value
    with pytest.raises(ValueError):
        adapt_test_hints(hints, bundle['manifest'], root)


def test_consumer_missing_links_retains_selected_scope(handoff_case, tmp_path):
    root, document, bundle, targets = handoff_case
    from vgar.graph.handoff import create_test_hints
    without_links = {**document, 'edges': [e for e in document['edges'] if e['type'] != 'TESTS']}
    bundle = copy.deepcopy(bundle)
    bundle['test_hints'] = create_test_hints(without_links, bundle['manifest'], changed_paths=targets,
                                            failing_tests=['tests/test_app.py'], selected_tests=['tests'])
    exported = write_context_handoff(bundle, tmp_path / 'bundle')
    inputs = receive_context_handoff(exported, root, approved_target(document),
        count_tokens=len, counter_label='test:characters')['test_inputs']
    assert inputs['failing_selectors'] == ('tests/test_app.py',)
    assert inputs['fallback_scope'] == ('tests',)
    assert set(targets) <= set(inputs['diagnostics']['unlinked_targets'])
    assert all(inputs['diagnostics']['link_details'][path]['fallback_reason'] == 'no_graph_test_links'
               for path in targets)


@pytest.fixture
def consumer_cli_case(handoff_case, tmp_path):
    from tokenizers import Tokenizer, models, pre_tokenizers
    from vgar.graph.token_counter import COUNTING_POLICY, LocalTokenizerCounter
    from vgar.contracts.handoff import byte_digest
    root, document, original, _ = handoff_case
    assets = tmp_path / 'tokenizer-assets'
    assets.mkdir()
    native = Tokenizer(models.WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
    native.pre_tokenizer = pre_tokenizers.Whitespace()
    (assets / 'tokenizer.json').write_text(native.to_str(), encoding='utf-8')
    for name in ('tokenizer_config.json', 'vocab.json', 'merges.txt'):
        (assets / name).write_text('{}', encoding='utf-8')
    manifest = tmp_path / 'tokenizer-manifest.json'
    manifest.write_text(json.dumps(dict(model_id='fixture/tokenizer', revision='a' * 40,
        assets_directory=assets.name, counting_policy=COUNTING_POLICY, weights_downloaded=False,
        files=[dict(name=f.name, size=f.stat().st_size, sha256=byte_digest(f.read_bytes()).removeprefix('sha256:'))
               for f in assets.iterdir()])), encoding='utf-8')
    counter = LocalTokenizerCounter(manifest)
    bundle = copy.deepcopy(original)
    for item in bundle['context']['items']:
        item['token_count'] = counter(item['snippet'])
    bundle['context']['total_token_count'] = sum(item['token_count'] for item in bundle['context']['items'])
    bundle['manifest']['counter_label'] = counter.counter_label
    bundle['manifest']['context_sha256'] = payload_digest(bundle['context'])
    exported = write_context_handoff(bundle, tmp_path / 'exported')
    destination = tmp_path / 'consumer clone'
    shutil.copytree(root, destination)
    config = tmp_path / 'approved-task.json'
    config.write_text(json.dumps(approved_target(document)), encoding='utf-8')
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/consume_m1_handoff.py'),
        '--bundle', str(exported), '--repository', str(destination), '--task-config', str(config),
        '--tokenizer-manifest', str(manifest), '--output-root', str(tmp_path / 'consumer-outputs')]
    return command, bundle, exported, destination, config, assets


def run_consumer_cli(command):
    completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', shell=False, timeout=20)
    assert completed.stdout, completed.stderr
    record = json.loads(completed.stdout)
    output = Path(record['output_directory'])
    assert json.loads((output / 'result.json').read_text(encoding='utf-8')) == record
    return completed.returncode, record, output


def test_consumer_cli_preserves_snippets_and_separates_invocations(consumer_cli_case):
    command, bundle, exported, destination, _, _ = consumer_cli_case
    before = {f.relative_to(destination): f.read_bytes() for f in destination.rglob('*.py')}
    (exported / 'repair-context.txt').write_bytes(b'UNTRUSTED PROMPT')
    code, record, output = run_consumer_cli(command)
    assert code == 0 and record['status'] == 'PASS'
    assert record['metadata']['collection_verified'] is False
    assert record['scope'] == 'm1_consumer_no_model_no_patch_no_test_execution'
    rendered = (output / 'repair-context.txt').read_bytes()
    assert b'UNTRUSTED PROMPT' not in rendered
    for item in bundle['context']['items']:
        assert item['snippet'].encode('utf-8') in rendered
    assert before == {f.relative_to(destination): f.read_bytes() for f in destination.rglob('*.py')}
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [e['event'] for e in events] == ['handoff_validated', 'test_hint_diagnostics']
    assert all(e['run_id'] == record['run_id'] for e in events)
    assert '"snippet":' not in json.dumps(events)
    code, _, second = run_consumer_cli(command)
    assert code == 0 and second != output


@pytest.mark.parametrize('fault', ['identity', 'source', 'tokenizer', 'missing_bundle_file', 'hint_flags', 'payload_shape'])
def test_consumer_cli_rejects_invalid_input_before_prompt(consumer_cli_case, fault):
    command, bundle, exported, destination, config, assets = consumer_cli_case
    if fault == 'identity':
        target = json.loads(config.read_text(encoding='utf-8'))
        target['graph_version'] = 'other-snapshot'
        config.write_text(json.dumps(target), encoding='utf-8')
    elif fault == 'source':
        source = destination / 'app.py'
        source.write_bytes(source.read_bytes() + b'\n# changed snapshot\n')
    elif fault == 'tokenizer':
        (assets / 'vocab.json').write_bytes(b'[]')
    elif fault == 'missing_bundle_file':
        (exported / 'test_links.json').unlink()
    elif fault == 'hint_flags':
        hints = copy.deepcopy(bundle['test_hints'])
        next(iter(hints['link_details'].values()))['truncated'] = 'false'
        (exported / 'test_links.json').write_text(json.dumps(hints), encoding='utf-8')
    else:
        payload = copy.deepcopy(bundle['context'])
        payload['total_token_count'] = -1
        (exported / 'context.json').write_text(json.dumps(payload), encoding='utf-8')
    code, record, output = run_consumer_cli(command)
    assert code == 2 and record['status'] == 'ERROR'
    assert record['error_stage'] in {'load_tokenizer', 'receive_handoff'}
    assert not (output / 'repair-context.txt').exists()
    assert not (output / 'test-inputs.json').exists()
    assert 'consumer_error' in (output / 'events.jsonl').read_text(encoding='utf-8')
    if fault == 'payload_shape':
        assert 'input_value' not in record['reason']
        assert all(item['snippet'] not in record['reason'] for item in bundle['context']['items'])


def test_changed_files_keep_graph_candidates_and_all_explicit_inputs(handoff_case):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    hints['failing_selectors'] = ['tests/test_app.py::test_other', 'tests/test_app.py']
    hints['fallback_scope'] = ['tests']
    report = diagnose_changed_paths(hints, bundle['manifest'], root, targets + targets)
    assert report['changed_paths'] == tuple(sorted(targets))
    assert all(detail['mapping_status'] == 'linked' for detail in report['targets'].values())
    assert report['graph_selectors']
    assert set(hints['failing_selectors']) <= set(report['candidate_tests'])
    assert report['fallback_scope'] == ('tests',)
    assert report['fallback_required'] is False
    assert report['collection_verified'] is False and report['coverage_verified'] is False


@pytest.mark.parametrize('mapping', ['missing_mapping', 'partial_mapping', 'unlinked'])
def test_changed_file_mapping_gaps_are_not_hidden_by_symbol_hints(handoff_case, mapping):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    path = targets[0]
    symbols = {key for key, binding in bundle['manifest']['items'].items() if binding['path'] == path}
    remove = {path} | (symbols if mapping == 'missing_mapping' else set())
    if mapping == 'unlinked':
        remove = set()
        hints['test_links'][path] = []
    for key in remove:
        hints['test_links'].pop(key, None)
        hints['link_details'].pop(key, None)
    report = diagnose_changed_paths(hints, bundle['manifest'], root, targets)
    assert report['targets'][path]['mapping_status'] == mapping
    assert report['fallback_required'] and report['fallback_available']
    assert report['requires_fallback_input'] is False
    assert 'tests/test_app.py' in report['candidate_tests']
    if mapping == 'partial_mapping':
        expected = {value for key in symbols for value in hints['test_links'].get(key, [])}
        assert set(report['targets'][path]['selectors']) == expected
    if len(targets) > 1:
        assert report['targets'][targets[1]]['mapping_status'] == 'linked'


@pytest.mark.parametrize('flag,reason', [('truncated', 'links_truncated'),
                                       ('traversal_limited', 'traversal_limited')])
def test_changed_file_limit_flags_require_fallback_without_dropping_candidates(handoff_case, flag, reason):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    hints['link_details'][targets[0]][flag] = True
    report = diagnose_changed_paths(hints, bundle['manifest'], root, targets)
    assert report['targets'][targets[0]]['mapping_status'] == 'linked'
    assert reason in report['targets'][targets[0]]['fallback_reasons']
    assert report['fallback_required']
    assert report['graph_selectors'] and report['failing_selectors']


def test_new_or_out_of_scope_changed_paths_report_missing_fallback_input(handoff_case):
    root, _, bundle, targets = handoff_case
    hints = copy.deepcopy(bundle['test_hints'])
    hints['failing_selectors'] = []
    hints['fallback_scope'] = []
    report = diagnose_changed_paths(hints, bundle['manifest'], root, targets + ['new.py', 'config.toml'])
    assert report['targets'][targets[0]]['mapping_status'] == 'linked'
    for path in ('new.py', 'config.toml'):
        assert report['targets'][path]['mapping_status'] == 'outside_source_scope'
    assert report['fallback_required'] and report['requires_fallback_input']
    assert not report['fallback_available']
    assert not (root / 'new.py').exists()


@pytest.mark.parametrize('paths', ['app.py', ['../app.py'], [r'src\app.py'],
                                 ['app.py::test_x'], [123], ['/app.py']])
def test_changed_paths_reject_non_file_or_ambiguous_input(handoff_case, paths):
    root, _, bundle, _ = handoff_case
    with pytest.raises(ValueError):
        diagnose_changed_paths(bundle['test_hints'], bundle['manifest'], root, paths)


def test_post_patch_diagnostics_use_original_snapshot_only(handoff_case):
    root, _, bundle, targets = handoff_case
    (root / targets[0]).unlink()
    with pytest.raises(ValueError, match='snapshot'):
        diagnose_changed_paths(bundle['test_hints'], bundle['manifest'], root, targets)


def test_consumer_cli_reports_actual_changed_paths(consumer_cli_case):
    command, bundle, _, _, _, _ = consumer_cli_case
    paths = sorted({item['path'] for item in bundle['context']['items']})
    paths.append('new.py')
    arguments = [value for path in paths for value in ('--changed-path', path)]
    code, record, output = run_consumer_cli(command + arguments)
    assert code == 0 and record['status'] == 'PASS'
    report = json.loads((output / 'test-targets.json').read_text(encoding='utf-8'))
    assert report['targets']['new.py']['mapping_status'] == 'outside_source_scope'
    assert report['fallback_required'] and report['failing_selectors']
    assert record['test_target_diagnostics']['fallback_required']
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert events[-1]['event'] == 'test_target_diagnostics'
    assert '"snippet":' not in json.dumps(events)


def test_consumer_cli_invalid_changed_path_produces_no_prompt(consumer_cli_case):
    command, _, _, _, _, _ = consumer_cli_case
    code, record, output = run_consumer_cli(command + ['--changed-path', '../escape.py'])
    assert code == 2 and record['error_stage'] == 'receive_handoff'
    assert not (output / 'repair-context.txt').exists()
