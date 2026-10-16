from contextlib import nullcontext
from copy import deepcopy
import json
from types import SimpleNamespace
import sys

import pytest

from test_bootstrap import api


class Tensor:
    dtype = 'int64'
    device = 'cpu'

    def __init__(self, values):
        self.values = values
        self.shape = (len(values), len(values[0]))

    def detach(self):
        return self

    def cpu(self):
        return self

    def to(self, device):
        return self

    def tolist(self):
        return deepcopy(self.values)

    def __getitem__(self, index):
        batch, tail = index
        return SimpleNamespace(tolist=lambda: self.values[batch][tail])


class Config:
    def __init__(self, **values):
        self.__dict__.update(values)

    def to_dict(self):
        return deepcopy(vars(self))


class Decoder:
    device = 'cpu'
    hf_device_map = {'layers': 'cpu'}

    def __init__(self, fail=False):
        self.generation_config = Config(do_sample=True, max_length=20, eos_token_id=[9], pad_token_id=9)
        self.mask = Tensor([[1, 1, 0]])
        self.fail = fail

    def generate(self, input_ids, *, generation_config, do_sample, max_new_tokens, return_dict_in_generate):
        values = generation_config.to_dict()
        values.update(do_sample=do_sample, max_new_tokens=max_new_tokens,
                      max_length=input_ids.shape[-1] + max_new_tokens)
        prepared = Config(**values)
        processor = self._get_logits_processor(generation_config=prepared, model_kwargs={'attention_mask': self.mask})
        # Transformers 4.57.6 deliberately dispatches the decoder on type(self),
        # so an observer that patches only instance._sample is ineffective.
        return type(self)._sample(self, input_ids, generation_config=prepared,
                                  attention_mask=self.mask, logits_processor=processor)

    def _get_logits_processor(self, *, generation_config, model_kwargs):
        return 'unchanged-processor'

    def _sample(self, input_ids, *, generation_config, attention_mask, logits_processor):
        assert attention_mask is self.mask
        assert logits_processor == 'unchanged-processor'
        if self.fail:
            raise RuntimeError('decoder crashed')
        return Tensor([[1, 2, 3, 8, 9]])


def test_observer_captures_actual_decoder_config_and_mask_without_changing_call():
    module = api('hf_diagnostics')
    model, snapshots = Decoder(), []
    original = model._get_logits_processor
    settings = Config(do_sample=False, eos_token_id=[9], max_length=None)
    result, diagnostic = module.generate_observed(model, Tensor([[1, 2, 3]]), settings,
        dict(do_sample=False, max_new_tokens=6, return_dict_in_generate=False),
        lambda item: snapshots.append(json.loads(json.dumps(item))))
    assert result.tolist() == [[1, 2, 3, 8, 9]]
    assert diagnostic['effective_generation_config']['do_sample'] is False
    assert diagnostic['effective_generation_config']['max_length'] == 9
    assert diagnostic['effective_generation_config']['max_new_tokens'] == 6
    assert diagnostic['attention_mask']['shape'] == [1, 3]
    assert diagnostic['attention_mask']['zeros'] == 1 and diagnostic['attention_mask']['ones'] == 2
    assert diagnostic['attention_mask']['sha256'].startswith('sha256:')
    assert diagnostic['attention_mask_supplied_by_host'] is False
    assert [s['phase'] for s in snapshots] == ['before_generate', 'pre_decode', 'complete']
    assert model._get_logits_processor == original and '_get_logits_processor' not in model.__dict__
    assert settings.max_length is None and model.generation_config.do_sample is True


def test_observer_persists_configuration_before_failure_and_restores_decoder():
    model, snapshots = Decoder(fail=True), []
    with pytest.raises(RuntimeError, match='decoder crashed'):
        api('hf_diagnostics').generate_observed(model, Tensor([[1, 2, 3]]), Config(do_sample=False),
            dict(do_sample=False, max_new_tokens=6, return_dict_in_generate=False),
            lambda item: snapshots.append(deepcopy(item)))
    assert snapshots[-1]['status'] == 'ERROR' and snapshots[-1]['phase'] == 'error'
    assert snapshots[-1]['effective_generation_config']['max_length'] == 9
    assert 'RuntimeError: decoder crashed' in snapshots[-1]['exception']['traceback']
    assert '_get_logits_processor' not in model.__dict__


def test_unsupported_decoder_does_not_invent_effective_observation():
    class OtherDecoder:
        generation_config = Config(do_sample=False)

        def generate(self, inputs, **kwargs):
            return inputs
    _, diagnostic = api('hf_diagnostics').generate_observed(OtherDecoder(), Tensor([[1]]),
        Config(do_sample=False), dict(do_sample=False), lambda item: None)
    assert diagnostic['effective_observed'] is False
    assert diagnostic['effective_generation_config'] is None and diagnostic['attention_mask'] is None


def test_worker_serializes_chained_exception(tmp_path, monkeypatch):
    worker = api('hf_worker')
    def broken(request, **kwargs):
        try:
            raise ValueError('bad input')
        except ValueError as error:
            raise RuntimeError('worker failed') from error
    monkeypatch.setattr(worker, 'execute', broken)
    request, response = tmp_path/'request.json', tmp_path/'response.json'
    request.write_text('{}', encoding='utf-8')
    assert worker.main([str(request), str(response)]) == 2
    saved = json.loads(response.read_text(encoding='utf-8'))
    assert saved['status'] == 'ERROR' and saved['error_type'] == 'RuntimeError'
    assert 'ValueError: bad input' in saved['traceback'] and 'RuntimeError: worker failed' in saved['traceback']


def test_backend_wires_observer_and_writes_durable_metadata_without_weights(tmp_path, monkeypatch):
    backend = api('hf_backend')
    class Tokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, return_tensors=None):
            return Tensor([[1, 2, 3]]) if return_tensors else [1, 2, 3] if tokenize else 'rendered'

        def decode(self, ids, **kwargs):
            return 'generated'
    tokenizer, model = Tokenizer(), Decoder()
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **kw: tokenizer),
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=lambda *a, **kw: model)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True, reset_peak_memory_stats=lambda: None,
        max_memory_allocated=lambda: 123, get_device_name=lambda n: 'unit-test-double'),
        float16='float16', inference_mode=nullcontext))
    monkeypatch.setattr(backend.importlib.metadata, 'version', lambda name: 'unit-test-double')
    snapshot = tmp_path/backend.REVISION
    snapshot.mkdir()
    (snapshot/'config.json').write_text('{"max_position_embeddings": 100}', encoding='utf-8')
    request = dict(kind='generate', messages=[dict(role='user', content='neutral')], expected_input_tokens=3,
        profile=dict(snapshot=str(snapshot), approved_prototype=True, model_id=backend.MODEL, revision=backend.REVISION),
        policy=dict(input_cap=20, output_cap=6, reserved_margin=2))
    artifact = tmp_path/'generation_diagnostics.json'
    result = backend.execute(request, diagnostics_path=artifact)
    stored = json.loads(artifact.read_text(encoding='utf-8'))
    assert result['raw_text'] == 'generated' and result['output_tokens'] == 2
    assert stored == result['generation_diagnostics']
    assert stored['effective_generation_config']['max_length'] == 9
    assert stored['attention_mask']['zeros'] == 1 and stored['status'] == 'PASS'


def test_host_keeps_partial_generation_diagnostics_when_worker_fails(tmp_path, monkeypatch):
    module = api('generator_hf')
    profile = api('contracts').ModelProfile(snapshot=tmp_path/api('hf_backend').REVISION,
        interpreter=sys.executable, tokenizer_manifest=tmp_path/'manifest.json', approved_prototype=True)
    def failed_worker(command, folder, response, timeout):
        api('evidence').atomic_json(folder/'generation_diagnostics.json',
            dict(status='ERROR', effective_observed=True, effective_generation_config=dict(do_sample=False)))
        return dict(status='ERROR', reason='decoder crashed')
    monkeypatch.setattr(module, 'invoke_worker', failed_worker)
    generator = module.HFGenerator(profile, tmp_path/'workers', api('contracts').RepairPolicy())
    result = generator.request('generate', [], generator.policy, 3, 0)
    assert result['status'] == 'ERROR'
    assert result['generation_diagnostics']['effective_generation_config']['do_sample'] is False
    assert result['diagnostics_artifact']['sha256'].startswith('sha256:')
