from pathlib import Path
import pytest
from vgar.repair import contracts as m_contracts
from vgar.models.huggingface import generator_hf as m_generator_hf
from vgar.models.huggingface import hf_backend as m_hf_backend


def test_unapproved_model_is_blocked_before_worker(tmp_path):
    profile = m_contracts.ModelProfile(snapshot=tmp_path, interpreter=Path('python'), tokenizer_manifest=tmp_path / 'manifest.json')
    with pytest.raises(ValueError, match='approved'):
        m_generator_hf.HFGenerator(profile, tmp_path)


def test_greedy_kwargs_cannot_inherit_sampling():
    values = m_hf_backend.generation_kwargs(64)
    assert values['do_sample'] is False and values['max_new_tokens'] == 64
    assert 'temperature' not in values



def test_worker_runs_the_vgar_module_with_repo_src_on_path(tmp_path, monkeypatch):
    import os
    import sys
    from vgar.repair.config import REPO_ROOT
    seen = {}
    def worker(command, folder, response, timeout):
        seen.update(command=command, pythonpath=os.environ.get('PYTHONPATH'))
        return dict(status='PASS', response=dict(kind='tokenize', rendered='x', input_ids=[1]))
    monkeypatch.setattr(m_generator_hf, 'invoke_worker', worker)
    profile = m_contracts.ModelProfile(snapshot=tmp_path / m_hf_backend.REVISION, interpreter=sys.executable,
                                       tokenizer_manifest=tmp_path / 'manifest.json', approved_prototype=True)
    m_generator_hf.HFGenerator(profile, tmp_path).request('tokenize', [], m_contracts.RepairPolicy(), 5)
    assert seen['command'][1:4] == ('-B', '-m', 'vgar.models.huggingface.hf_worker')
    assert seen['pythonpath'] == str(REPO_ROOT / 'src')
