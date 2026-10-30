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
        'variants': [{'path': str(p), 'arm': W10[v]} for v, p in paths.items()]})


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
