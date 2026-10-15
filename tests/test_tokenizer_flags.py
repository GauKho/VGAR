"""Tokenizer flag must survive host caching and the real worker request boundary."""
from types import SimpleNamespace
import sys

import pytest

from test_bootstrap import api


def test_host_tokenizer_distinguishes_generation_flag_and_keeps_cache(tmp_path):
    module = api('generator_hf')

    class TokenizeWorker:
        profile = SimpleNamespace(model_id='unit-test', revision='pinned')
        def request(self, kind, messages, policy, timeout, expected_input_tokens=None, **kwargs):
            flag = kwargs.get('add_generation_prompt', True)
            assert kind == 'tokenize'
            return {'status': 'PASS', 'response': {'rendered': 'base+assistant' if flag else 'base',
                                                 'input_ids': [1, 2] if flag else [1]}}

    tokenizer = module.HFChatTokenizer(TokenizeWorker(), api('contracts').RepairPolicy())
    messages = [dict(role='user', content='neutral')]
    assert tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True) == [1, 2]
    assert tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False) == [1]
    assert tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False) == 'base'
    assert tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) == 'base+assistant'
    assert len(tokenizer.cache) == 2


@pytest.mark.parametrize('flag', [True, False])
def test_backend_tokenize_honors_flag_without_loading_model(tmp_path, monkeypatch, flag):
    backend = api('hf_backend')

    class Tokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            return ([1, 2] if add_generation_prompt else [1]) if tokenize else ('base+assistant' if add_generation_prompt else 'base')

    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **kw: Tokenizer())))
    # Backend imports both Auto classes but must never load weights for tokenize.
    sys.modules['transformers'].AutoModelForCausalLM = SimpleNamespace(
        from_pretrained=lambda *a, **kw: pytest.fail('Tokenize loaded model'))
    result = backend.execute(dict(kind='tokenize', messages=[], add_generation_prompt=flag,
        profile=dict(snapshot=str(tmp_path/backend.REVISION), approved_prototype=True,
                     model_id=backend.MODEL, revision=backend.REVISION), policy=dict(input_cap=30)))
    assert result['input_ids'] == ([1, 2] if flag else [1])
    assert result['rendered'] == ('base+assistant' if flag else 'base')


def test_request_carries_tokenizer_flag_to_worker(tmp_path, monkeypatch):
    module = api('generator_hf')
    profile = api('contracts').ModelProfile(snapshot=tmp_path/api('hf_backend').REVISION,
        interpreter=sys.executable, tokenizer_manifest=tmp_path/'manifest.json', approved_prototype=True)

    def worker(command, folder, response, timeout):
        import json
        request = json.loads((folder/'request.json').read_text(encoding='utf-8'))
        assert request['add_generation_prompt'] is False
        return dict(status='PASS', response=dict(kind='tokenize', rendered='base', input_ids=[1]))

    monkeypatch.setattr(module, 'invoke_worker', worker)
    generator = module.HFGenerator(profile, tmp_path/'workers', api('contracts').RepairPolicy())
    assert generator.request('tokenize', [], generator.policy, 2, add_generation_prompt=False)['status'] == 'PASS'
