"""M3-W9-2: CLI guards. A forgotten --data-root would turn every pair into a TERMINAL ERROR."""
import importlib.util

import pytest
from m3_support import ROOT


def cli():
    spec = importlib.util.spec_from_file_location('run_repair_experiment', ROOT/'scripts/run_repair_experiment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_data_root_is_required(tmp_path, capsys):
    with pytest.raises(SystemExit) as stopped:
        cli().main(['run', '--config', str(ROOT/'configs/m3/w9_fixture_smoke.json'), '--output-root', str(tmp_path)])
    assert stopped.value.code == 2 and '--data-root' in capsys.readouterr().err
    assert not any(tmp_path.iterdir())
