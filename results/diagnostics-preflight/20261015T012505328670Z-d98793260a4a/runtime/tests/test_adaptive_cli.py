import json
import subprocess
import sys

import pytest

from conftest import ROOT
from test_bootstrap import api


def test_status_missing_campaign_does_not_create_it_or_launch_model(tmp_path):
    directory = tmp_path / 'missing'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_adaptive_acceptance.py'),
        '--status', '--campaign', str(directory)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'NOT_RUN'
    assert not directory.exists()


def test_running_without_explicit_init_does_not_create_campaign(tmp_path):
    directory = tmp_path / 'missing'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_adaptive_acceptance.py'),
        '--run-next', '--campaign', str(directory)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert not directory.exists()


def test_historical_archive_must_match_original_frozen_code_mapping(tmp_path):
    evidence = api('evidence')
    old = tmp_path / 'old.py'
    old.write_bytes(b'old-runtime')
    frozen = tmp_path / 'frozen_inputs.json'
    evidence.atomic_json(frozen, dict(files={str(tmp_path / 'current.py'): evidence.digest(b'different-runtime')}))
    manifest = tmp_path / 'manifest.json'
    evidence.atomic_json(manifest, dict(files={str(tmp_path / 'current.py'): dict(archive=str(old), sha256=evidence.digest(old.read_bytes()))},
        historical={str(frozen): evidence.digest(frozen.read_bytes())}, protected_external={}))
    with pytest.raises(ValueError, match='frozen|Frozen'):
        api('adaptive_campaign').audit_archive(manifest)


def test_changed_frozen_runtime_is_not_treated_as_prompt_tuning(tmp_path):
    file = tmp_path / 'runtime.py'
    file.write_bytes(b'original')
    evidence = api('evidence')
    module = api('adaptive_campaign')
    store = module.AdaptiveCampaignStore.create(tmp_path / 'campaign', dict(files={str(file): evidence.digest(file.read_bytes())}))
    file.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        module.AdaptiveCampaignStore.open(store.directory)
