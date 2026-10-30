"""W9 variant policy: validate config and bind its semantics to a stable hash."""
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = ROOT / 'configs/m2/variants'
ALL_CHECKS = ['tests', 'syntax', 'mypy', 'ruff']


def module():
    # Import inside tests so the initial missing implementation is a test failure,
    # not a collection/environment failure.
    return importlib.import_module('vgar.repair.policy')


def write_policy(tmp_path, **updates):
    data = {'variant_id': 'A0', 'arm': None, 'required_checks': ['tests'],
            'recorded_checks': ALL_CHECKS, 'static_mode': 'baseline_delta',
            'diagnostic_identity_version': 'm2-static-delta-v1'}
    data.update(updates)
    path = tmp_path / 'variant.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


@pytest.mark.parametrize(('variant', 'expected'), [
    ('A0', frozenset({'tests'})),
    ('A1', frozenset({'tests'})),
    ('A2', frozenset({'tests', 'syntax', 'mypy', 'ruff'})),
])
def test_exact_required_checks(variant, expected):
    api = module()
    policy = api.load_variant(VARIANTS / (variant + '.json'))
    assert policy.variant_id == variant
    assert api.required_checks(policy) == expected
    assert frozenset(policy.recorded_checks) == frozenset(ALL_CHECKS)
    assert policy.arm is None  # Mapping has not been approved by M1/M3.


@pytest.mark.parametrize('variant', ['A3', 'a0', '', 'unknown'])
def test_unknown_variant_rejected(tmp_path, variant):
    api = module()
    with pytest.raises(ValueError):
        api.load_variant(write_policy(tmp_path, variant_id=variant))


@pytest.mark.parametrize(('variant', 'required'), [
    ('A0', ['tests', 'ruff']), ('A1', []), ('A1', ['syntax']),
    ('A2', ['tests']), ('A2', ['tests', 'syntax', 'mypy']),
])
def test_variant_cannot_weaken_or_strengthen_required_gate(tmp_path, variant, required):
    api = module()
    with pytest.raises(ValueError):
        api.load_variant(write_policy(tmp_path, variant_id=variant, required_checks=required))


@pytest.mark.parametrize('updates', [
    {'required_checks': ['tests', 'tests']},
    {'recorded_checks': ['tests', 'syntax', 'mypy', 'mypy']},
    {'recorded_checks': ['tests']},
    {'required_checks': 'tests'},
    {'recorded_checks': ['tests', 'syntax', 'mypy', 'shell']},
    {'arm': 'automatic'},
    {'static_mode': 'absolute_pass'},
    {'diagnostic_identity_version': 'unknown'},
    {'command': 'echo forbidden'},
    {'policy_hash': 'sha256:self-declared'},
])
def test_invalid_or_ambiguous_policy_rejected(tmp_path, updates):
    api = module()
    with pytest.raises(ValueError):
        api.load_variant(write_policy(tmp_path, **updates))


def test_missing_variant_does_not_default_to_a0(tmp_path):
    api = module()
    path = write_policy(tmp_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    del data['variant_id']
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        api.load_variant(path)


def test_malformed_json_rejected(tmp_path):
    api = module()
    path = tmp_path / 'bad.json'
    path.write_text('{', encoding='utf-8')
    with pytest.raises(ValueError):
        api.load_variant(path)


def test_policy_hash_stable_across_json_key_order(tmp_path):
    api = module()
    path = write_policy(tmp_path)
    first = api.load_variant(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    # Both keys and set-like check order may vary without changing semantics.
    data['recorded_checks'].reverse()
    path.write_text(json.dumps(dict(reversed(list(data.items()))), indent=4), encoding='utf-8')
    assert api.policy_hash(first) == api.policy_hash(api.load_variant(path))
    digest = api.policy_hash(first)
    assert digest.startswith('sha256:') and len(bytes.fromhex(digest[7:])) == 32


def test_effective_policy_change_changes_hash(tmp_path):
    api = module()
    pending = api.load_variant(write_policy(tmp_path))
    explicit_bm25 = api.load_variant(write_policy(tmp_path, arm='bm25'))
    explicit_graph = api.load_variant(write_policy(tmp_path, arm='graph'))
    a2 = api.load_variant(write_policy(tmp_path, variant_id='A2', required_checks=ALL_CHECKS))
    assert len({api.policy_hash(p) for p in (pending, explicit_bm25, explicit_graph, a2)}) == 4


def test_loaded_policy_independent_of_later_file_edits(tmp_path):
    api = module()
    path = write_policy(tmp_path)
    policy = api.load_variant(path)
    before = api.policy_hash(policy)
    path.write_text('{}', encoding='utf-8')
    assert api.policy_hash(policy) == before
    with pytest.raises(ValueError):
        policy.variant_id = 'A2'


def test_w78_default_runtime_and_budget_unchanged():
    from vgar.repair.contracts import RepairPolicy
    policy = RepairPolicy()
    assert policy.runtime == 'native_trusted_fixtures'
    assert policy.prompt_version == 'm2-w78-v11'
    assert (policy.input_cap, policy.output_cap, policy.reserved_margin) == (6000, 1536, 256)


W9_HASHES = {'A0': 'sha256:bca5f7b7f208f217ce72373305e8325922ed6a43ebe378305920bc50ebfacbbf',
             'A1': 'sha256:2b29abdb298d364685edf0236556cb648eb61d7cb5160d2380783a3a894bef00',
             'A2': 'sha256:2f7c85d1124c77b5f5c67160e8acc644e64cf638d9bdcc10bbab4eb768be55ca'}


@pytest.mark.parametrize('variant', ['A0', 'A1', 'A2'])
def test_w9_variant_hashes_unchanged(variant):
    policy = module().load_variant(VARIANTS / f'{variant}.json')
    assert policy.patch_mode == 'strict' and policy.path_listing == 'all'
    assert 'patch_mode' not in policy.model_dump(mode='json') and 'path_listing' not in policy.model_dump(mode='json')
    assert module().policy_hash(policy) == W9_HASHES[variant]


@pytest.mark.parametrize('variant', ['A0', 'A1', 'A2'])
def test_w10_variants_are_normalized_and_hash_differs(variant):
    policy = module().load_variant(VARIANTS / 'w10' / f'{variant}.json')
    assert policy.patch_mode == 'normalized'
    assert policy.model_dump(mode='json')['patch_mode'] == 'normalized'
    assert policy.model_dump(mode='json')['path_listing'] == 'context'
    assert module().policy_hash(policy) != W9_HASHES[variant]
    w9 = json.loads((VARIANTS / f'{variant}.json').read_text(encoding='utf-8'))
    assert json.loads((VARIANTS / 'w10' / f'{variant}.json').read_text(encoding='utf-8')) == w9 | {
        'patch_mode': 'normalized', 'path_listing': 'context'}


def test_unknown_path_listing_rejected(tmp_path):
    with pytest.raises(Exception):
        module().load_variant(write_policy(tmp_path, path_listing='some'))


def test_unknown_patch_mode_rejected(tmp_path):
    with pytest.raises(Exception):
        module().load_variant(write_policy(tmp_path, patch_mode='fuzzy'))
