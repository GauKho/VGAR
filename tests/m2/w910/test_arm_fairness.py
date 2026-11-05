"""Arms of one experiment, and experiments of one table, may differ only in arm and required checks (spec §5.7)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests/m3'))
from m3_support import VARIANTS, write_json  # noqa: E402

W10 = {'A0': 'bm25', 'A1': 'graph', 'A2': 'graph'}


def config(tmp_path, name='config.json', variant_paths=None, repair_config=None):
    examples = ROOT/'examples/m2'
    paths = variant_paths or {v: VARIANTS/'w10'/f'{v}.json' for v in W10}
    return write_json(tmp_path/name, {
        'schema': 'vgar-m3-experiment-v1',
        'source': {'type': 'fixture', 'tasks': [str(examples/'tasks/single_file_login.json')]},
        'repair_config': str(repair_config or ROOT/'configs/m2/demo.json'), 'generation': 'fake',
        'variants': [{'path': str(p), 'arm': (W10 | {'A3': 'graph'})[v]} for v, p in paths.items()]})


def load(path):
    from vgar.evaluation.repair.manifest import load_experiment
    return load_experiment(path, ROOT)


def check(*experiments):
    from vgar.evaluation.repair.fairness import check_arm_fairness
    check_arm_fairness(list(experiments))


def test_only_arm_and_checks_may_differ(tmp_path):
    check(load(config(tmp_path)))


def test_patch_mode_mismatch_rejected(tmp_path):
    paths = {v: VARIANTS/'w10'/f'{v}.json' for v in W10} | {'A1': VARIANTS/'A1.json'}
    with pytest.raises(ValueError, match='patch_mode'):
        check(load(config(tmp_path, variant_paths=paths)))


def test_cross_experiment_input_cap_mismatch(tmp_path):
    demo = json.loads((ROOT/'configs/m2/demo.json').read_text(encoding='utf-8'))
    demo['policy']['input_cap'] = 5000
    for field in ('snapshot', 'tokenizer_manifest', 'interpreter'):
        demo['model'][field] = str((ROOT/'configs/m2'/demo['model'][field]).resolve()) if not Path(
            demo['model'][field]).expanduser().is_absolute() else demo['model'][field]
    other = write_json(tmp_path/'demo_5000.json', demo)
    first = load(config(tmp_path))
    second = load(config(tmp_path, name='other.json', repair_config=other))
    check(first)
    check(second)
    with pytest.raises(ValueError, match='policy'):
        check(first, second)


def test_cross_experiment_same_config_passes(tmp_path):
    check(load(config(tmp_path)), load(config(tmp_path, name='again.json')))


def test_refused_run_writes_nothing(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location('run_cli', ROOT/'scripts/run_repair_experiment.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    paths = {v: VARIANTS/'w10'/f'{v}.json' for v in W10} | {'A1': VARIANTS/'A1.json'}
    path = config(tmp_path, variant_paths=paths)
    out = tmp_path/'out'
    assert cli.main(['run', '--config', str(path), '--data-root', str(ROOT), '--output-root', str(out)]) == 2
    assert not out.exists() or not any(out.iterdir())
    assert 'Arm fairness violation' in capsys.readouterr().err


def a3_paths():
    return {'A2': VARIANTS / 'w10/A2.json', 'A3': VARIANTS / 'A3.json'}


def test_A3_differs_from_A2_only_in_required_checks(tmp_path):
    exp = load(config(tmp_path, variant_paths=a3_paths()))
    check(exp)
    assert [(v.variant_id, v.arm) for v in exp.variants] == [('A2', 'graph'), ('A3', 'graph')]
    check(load(config(tmp_path, name='a2.json', variant_paths={'A2': a3_paths()['A2']})),
          load(config(tmp_path, name='a3.json', variant_paths={'A3': a3_paths()['A3']})))


@pytest.mark.parametrize('field,value', [('patch_mode', 'strict'), ('path_listing', 'all')])
def test_a3_shared_policy_drift_is_rejected_before_any_attempt(tmp_path, capsys, field, value):
    import importlib.util
    spec = importlib.util.spec_from_file_location('a3_run_cli', ROOT / 'scripts/run_repair_experiment.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    changed = json.loads((VARIANTS / 'A3.json').read_bytes()) | {field: value}
    paths = a3_paths() | {'A3': write_json(tmp_path / 'changed_a3.json', changed)}
    path = config(tmp_path, variant_paths=paths)
    output = tmp_path / 'out'
    assert cli.main(['run', '--config', str(path), '--data-root', str(ROOT), '--output-root', str(output)]) == 2
    assert not output.exists() or not any(output.iterdir())
    assert field in capsys.readouterr().err


@pytest.mark.parametrize('changed_variant', ['A2', 'A3'])
def test_a3_comparison_cannot_change_graph_arm(tmp_path, changed_variant):
    path = config(tmp_path, variant_paths=a3_paths())
    raw = json.loads(path.read_bytes())
    raw['variants'][0 if changed_variant == 'A2' else 1]['arm'] = 'bm25'
    write_json(path, raw)
    with pytest.raises(ValueError, match='(Arm fairness|A3).*graph'):
        check(load(path))


def test_a3_cross_experiment_cannot_compare_bm25_a2(tmp_path):
    first = config(tmp_path, name='a2.json', variant_paths={'A2': a3_paths()['A2']})
    raw = json.loads(first.read_bytes())
    raw['variants'][0]['arm'] = 'bm25'
    write_json(first, raw)
    second = config(tmp_path, name='a3.json', variant_paths={'A3': a3_paths()['A3']})
    with pytest.raises(ValueError, match='Arm fairness.*graph'):
        check(load(first), load(second))


@pytest.mark.parametrize('field,value', [('input_cap', 5000), ('output_cap', 1024),
    ('generation_timeout', 899), ('global_timeout', 1799), ('prompt_version', 'm2-w78-v12')])
def test_a3_cannot_change_common_prompt_budget_or_deadline(tmp_path, monkeypatch, field, value):
    from dataclasses import replace
    if field == 'prompt_version':
        from vgar.evaluation.repair import fairness
        original = fairness.template_path
        other = tmp_path / 'other-template.txt'
        other.write_text('Different registered fixture prompt', encoding='utf-8')
        monkeypatch.setattr(fairness, 'template_path', lambda version: other if version == value else original(version))
    first = load(config(tmp_path, variant_paths={'A2': a3_paths()['A2']}))
    second = load(config(tmp_path, name='a3.json', variant_paths={'A3': a3_paths()['A3']}))
    second = replace(second, policy=second.policy.model_copy(update={field: value}))
    with pytest.raises(ValueError, match='Arm fairness'):
        check(first, second)


@pytest.mark.parametrize('field', ['model_id', 'revision', 'tokenizer_manifest'])
def test_a3_cannot_change_model_or_tokenizer(tmp_path, field):
    from dataclasses import replace
    first = load(config(tmp_path, variant_paths={'A2': a3_paths()['A2']}))
    second = load(config(tmp_path, name='a3.json', variant_paths={'A3': a3_paths()['A3']}))
    value = 'different-pin'
    if field == 'tokenizer_manifest':
        value = tmp_path / 'different-tokenizer.json'
        value.write_bytes(second.profile.tokenizer_manifest.read_bytes() + b'\n')
    second = replace(second, profile=second.profile.model_copy(update={field: value}))
    with pytest.raises(ValueError, match='Arm fairness'):
        check(first, second)
