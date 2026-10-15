from pathlib import Path
import pytest
from test_bootstrap import api


def test_unapproved_model_is_blocked_before_worker(tmp_path):
    profile = api('contracts').ModelProfile(snapshot=tmp_path, interpreter=Path('python'), tokenizer_manifest=tmp_path / 'manifest.json')
    with pytest.raises(ValueError, match='approved'):
        api('generator_hf').HFGenerator(profile, tmp_path)


def test_greedy_kwargs_cannot_inherit_sampling():
    values = api('hf_backend').generation_kwargs(64)
    assert values['do_sample'] is False and values['max_new_tokens'] == 64
    assert 'temperature' not in values

