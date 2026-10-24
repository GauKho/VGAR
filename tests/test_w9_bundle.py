"""W9 shared handoff: real producer/consumer, no inference or fixture execution."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT/'tests/fixtures/w9_bundle'
ORIGINAL = ROOT/'tests/fixtures/w7_w8_handoff/single_file_login/repo'


@pytest.fixture
def recipe():
    path = ROOT/'scripts/build_w9_bundle_fixture.py'
    assert path.is_file(), 'M1-W9-6 recipe not implemented'
    spec = importlib.util.spec_from_file_location('w9_fixture_recipe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def built(recipe, tmp_path):
    output = tmp_path/'fixture'
    recipe.build_fixture(output)
    return output


def inventory(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_default_cli_creates_a_consumer_validated_fixture(tmp_path):
    output = tmp_path/'CLI bundle có khoảng trắng'
    command = [sys.executable, '-B', str(ROOT/'scripts/build_w9_bundle_fixture.py'), '--output-root', str(output)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'PASS' and report['mode'] == 'build'
    assert report['counter_label'] == 'fixture-only:characters'
    assert (output/'bundle/context_manifest.json').is_file()


def test_real_consumer_receives_source_bound_unrepaired_fixture(recipe, built):
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    task = load_task(built/'task.json')
    handoff = load_handoff(task, len, 'fixture-only:characters')
    assert task.task_id == 'w9-single-file-login'
    assert task.source_repo == built/'repo'
    assert task.bundle_directory == built/'bundle'
    assert task.allowed_source_paths == ('auth.py',)
    assert task.trusted_fixture is False
    assert (built/'repo/auth.py').read_bytes().replace(b'\r\n', b'\n') == b'def login(value):\n    return bool(value)\n'
    assert any(i.path == 'auth.py' and 'return bool(value)' in i.snippet for i in handoff.context.items)
    for item in handoff.context.items:
        assert item.snippet.encode('utf-8') in (task.source_repo/item.path).read_bytes()
        assert item.token_count == len(item.snippet)
    assert handoff.inputs['failing_selectors'] == ('tests/test_auth.py::test_login_rejects_whitespace',)
    assert handoff.inputs['fallback_scope'] == ('tests',)
    assert not handoff.metadata['coverage_verified']
    assert not handoff.metadata['collection_verified']
    assert not handoff.inputs['diagnostics']['collection_verified']
    assert recipe.load_fixture(built).task == task


def test_rebuild_preserves_original_bytes_and_is_deterministic(recipe, tmp_path):
    before = inventory(ORIGINAL)
    first, second = tmp_path/'one', tmp_path/'two'
    recipe.build_fixture(first)
    recipe.build_fixture(second)
    assert inventory(first) == inventory(second)
    assert inventory(ORIGINAL) == before
    expected_source = inventory(CANONICAL/'repo') if CANONICAL.exists() else before
    assert inventory(first/'repo') == expected_source
    assert set(inventory(first)) == {
        '.gitattributes', 'README.md', 'task.json', 'fixture_profile.json', 'repo/auth.py', 'repo/pytest.ini',
        'repo/tests/test_auth.py', 'bundle/context.json', 'bundle/context_manifest.json',
        'bundle/test_links.json', 'bundle/repair-context.txt',
    }


def test_relocated_unicode_space_paths_validate(recipe, built, tmp_path):
    relocated = tmp_path/'bàn giao có khoảng trắng'
    shutil.copytree(built, relocated)
    value = recipe.load_fixture(relocated)
    assert value.task.source_repo == relocated/'repo'
    assert value.task.bundle_directory == relocated/'bundle'
    profile = json.loads((relocated/'fixture_profile.json').read_text(encoding='utf-8'))
    assert profile['counter_label'] == 'fixture-only:characters'
    assert profile['counter_mode'] == 'fixture-only'
    data = json.loads((relocated/'task.json').read_text(encoding='utf-8'))
    assert data['source_repo'] == 'repo' and data['bundle_directory'] == 'bundle'
    assert all(not Path(p).is_absolute() for p in profile['files'])
    serialized = (relocated/'fixture_profile.json').read_text(encoding='utf-8')
    assert str(built) not in serialized and str(ROOT) not in serialized
    assert 'started_utc' not in profile and 'fixture_profile.json' not in profile['files']


@pytest.mark.parametrize('field', ['task_id', 'repo_key', 'revision', 'graph_version'])
def test_task_identity_tamper_is_rejected_before_consumer(recipe, built, field):
    path = built/'task.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data[field] = 'wrong'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        recipe.load_fixture(built)


@pytest.mark.parametrize('field', ['repo_key', 'revision', 'graph_version'])
def test_existing_consumer_rejects_independent_wrong_target(recipe, built, field):
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    task = load_task(built/'task.json').model_copy(update={field: 'wrong'})
    with pytest.raises(ValueError):
        load_handoff(task, len, 'fixture-only:characters')


@pytest.mark.parametrize('fault', ['source', 'added_source', 'missing_source', 'sidecar', 'missing_sidecar',
                                  'snippet', 'range', 'counts', 'counter', 'profile_counter'])
def test_invalid_fixture_inputs_are_rejected(recipe, built, fault):
    if fault == 'source':
        (built/'repo/auth.py').write_bytes(b'def login(value): return True\n')
    elif fault == 'added_source':
        (built/'repo/extra.py').write_bytes(b'x=1\n')
    elif fault == 'missing_source':
        (built/'repo/auth.py').unlink()
    elif fault == 'missing_sidecar':
        (built/'bundle/test_links.json').unlink()
    else:
        path = built/('fixture_profile.json' if fault == 'profile_counter' else 'bundle/context_manifest.json'
                     if fault == 'counter' else 'bundle/context.json')
        data = json.loads(path.read_text(encoding='utf-8'))
        if fault == 'sidecar':
            data['total_token_count'] += 1
        elif fault == 'snippet':
            data['items'][0]['snippet'] = 'return False'
        elif fault == 'range':
            data['items'][0]['range']['start_col'] += 1
        elif fault == 'counts':
            data['items'][0]['token_count'] += 1
        else:
            data['counter_label'] = 'wrong-counter'
        path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises((ValueError, FileNotFoundError)):
        recipe.load_fixture(built)


def test_consumer_rejects_wrong_counter_without_fixture_hash_helper(recipe, built):
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    task = load_task(built/'task.json')
    with pytest.raises(ValueError):
        load_handoff(task, len, 'wrong-counter')
    with pytest.raises(ValueError):
        load_handoff(task, lambda text: len(text)+1, 'fixture-only:characters')


def test_missing_graph_links_retain_explicit_failing_and_fallback_inputs(recipe, built):
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    path = built/'bundle/test_links.json'
    hints = json.loads(path.read_text(encoding='utf-8'))
    for key in hints['test_links']:
        hints['test_links'][key] = []
        hints['link_details'][key]['candidates'] = []
        hints['link_details'][key]['fallback_reason'] = 'W9_FIXTURE_NO_LINKS'
    path.write_text(json.dumps(hints), encoding='utf-8')
    received = load_handoff(load_task(built/'task.json'), len, 'fixture-only:characters')
    assert all(not values for values in received.inputs['test_links'].values())
    assert received.inputs['failing_selectors'] == ('tests/test_auth.py::test_login_rejects_whitespace',)
    assert received.inputs['fallback_scope'] == ('tests',)
    assert not received.metadata['collection_verified']


def test_fixture_does_not_gain_native_execution_admission(recipe, built):
    from vgar.repair.pipeline import require_trusted_fixture
    with pytest.raises(ValueError, match='Native execution only allowed'):
        require_trusted_fixture(recipe.load_fixture(built).task)


@pytest.fixture
def local_tokenizer(tmp_path):
    # Tiny synthetic assets exercise the REAL verified loader; not Qwen assets/results.
    import tokenizers
    assets = tmp_path/'tokenizer-assets'
    assets.mkdir()
    tokenizer = tokenizers.Tokenizer(tokenizers.models.WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
    raw = {'tokenizer.json': tokenizer.to_str().encode('utf-8'), 'tokenizer_config.json': b'{}',
           'vocab.json': b'{"[UNK]":0}', 'merges.txt': b'#version: 0.2\n'}
    for name, data in raw.items():
        (assets/name).write_bytes(data)
    manifest = {'model_id': 'fixture/unit-tokenizer', 'revision': 'a'*40,
        'weights_downloaded': False, 'assets_directory': 'tokenizer-assets',
        'counting_policy': 'encode-each-snippet:add_special_tokens=false:sum-item-counts',
        'files': [{'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(raw.items())]}
    path = tmp_path/'local-tokenizer.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return path


def test_verified_tokenizer_mode_roundtrip_and_determinism(recipe, local_tokenizer, tmp_path):
    first, second = tmp_path/'tokens-first', tmp_path/'tokens-second'
    recipe.build_fixture(first, tokenizer_manifest=local_tokenizer)
    recipe.build_fixture(second, tokenizer_manifest=local_tokenizer)
    assert inventory(first) == inventory(second)
    received = recipe.load_fixture(first, tokenizer_manifest=local_tokenizer)
    assert received.metadata['counter_label'].startswith('local-hf:fixture/unit-tokenizer@')
    assert all(item.token_count == 1 for item in received.context.items)
    assert received.context.total_token_count == len(received.context.items)
    with pytest.raises(ValueError):
        recipe.load_fixture(first)


def test_changed_tokenizer_asset_is_rejected_without_output(recipe, local_tokenizer, tmp_path):
    (tmp_path/'tokenizer-assets/tokenizer.json').write_bytes(b'{}')
    output = tmp_path/'refused'
    with pytest.raises(ValueError):
        recipe.build_fixture(output, tokenizer_manifest=local_tokenizer)
    assert not output.exists()


def test_different_tokenizer_identity_cannot_load_an_existing_bundle(recipe, local_tokenizer, tmp_path):
    output = tmp_path/'tokens-output'
    recipe.build_fixture(output, tokenizer_manifest=local_tokenizer)
    data = json.loads(local_tokenizer.read_text(encoding='utf-8'))
    data['revision'] = 'b'*40
    local_tokenizer.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        recipe.load_fixture(output, tokenizer_manifest=local_tokenizer)


def test_post_validation_sidecar_edit_is_detected(recipe, built):
    value = recipe.load_fixture(built)
    (built/'bundle/context.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='changed'):
        value.assert_unchanged()


def test_rehashed_tampered_snippet_is_rejected_by_real_consumer(recipe, built):
    from vgar.contracts.handoff import payload_digest
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    context_path, manifest_path = built/'bundle/context.json', built/'bundle/context_manifest.json'
    context = json.loads(context_path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    context['items'][0]['snippet'] = 'x'*len(context['items'][0]['snippet'])
    manifest['context_sha256'] = payload_digest(context)
    context_path.write_text(json.dumps(context), encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        load_handoff(load_task(built/'task.json'), len, 'fixture-only:characters')


@pytest.mark.parametrize('kind', ['exists', 'source', 'source_parent', 'source_child', 'canonical', 'canonical_parent', 'canonical_child'])
def test_output_guards_preserve_existing_and_protected_inputs(recipe, tmp_path, kind):
    source_before = inventory(ORIGINAL)
    if kind == 'canonical' and not CANONICAL.exists():
        pytest.skip('Canonical creation is allowed once; overwrite tested after bootstrap')
    if kind == 'exists':
        target = tmp_path/'exists'
        target.mkdir()
        (target/'keep.txt').write_text('keep', encoding='utf-8')
    else:
        target = {'source': ORIGINAL, 'source_parent': ORIGINAL.parent, 'source_child': ORIGINAL/'new',
                  'canonical': CANONICAL, 'canonical_parent': CANONICAL.parent,
                  'canonical_child': CANONICAL/'new'}[kind]
    with pytest.raises((ValueError, FileExistsError)):
        recipe.build_fixture(target)
    assert inventory(ORIGINAL) == source_before
    if kind == 'exists':
        assert (target/'keep.txt').read_text() == 'keep'


def test_missing_tokenizer_never_falls_back_or_creates_output(recipe, tmp_path):
    target = tmp_path/'not-created'
    with pytest.raises((ValueError, FileNotFoundError)):
        recipe.build_fixture(target, tokenizer_manifest=tmp_path/'missing.json')
    assert not target.exists()


def test_fixture_counter_rejects_supplying_tokenizer_profile(recipe, built, tmp_path):
    with pytest.raises(ValueError):
        recipe.load_fixture(built, tokenizer_manifest=tmp_path/'not-needed.json')


def test_recipe_cli_validates_without_writing_fixture(recipe, built):
    before = inventory(built)
    command = [sys.executable, '-B', str(ROOT/'scripts/build_w9_bundle_fixture.py'), '--validate-root', str(built)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'PASS' and report['mode'] == 'validate'
    assert report['counter_label'] == 'fixture-only:characters'
    assert inventory(built) == before


def test_checked_in_fixture_validates_and_matches_recipe(recipe, tmp_path):
    assert CANONICAL.is_dir(), 'Canonical W9 fixture not generated yet'
    handoff = recipe.load_fixture(CANONICAL)
    assert handoff.metadata['task_id'] == 'w9-single-file-login'
    regenerated = tmp_path/'regenerated'
    recipe.build_fixture(regenerated)
    assert inventory(CANONICAL) == inventory(regenerated)
