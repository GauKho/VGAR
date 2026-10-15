"""Optional HF implementation, imported only inside a confined real worker."""
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
from .evidence import atomic_json
from .hf_diagnostics import generate_observed

MODEL = 'Qwen/Qwen3-4B-Instruct-2507'
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'


def generation_kwargs(cap):
    return {'do_sample': False, 'max_new_tokens': cap, 'return_dict_in_generate': False}


def execute(request, *, diagnostics_path=None):
    profile, policy = request['profile'], request['policy']
    snapshot = Path(profile['snapshot']).resolve()
    if not profile['approved_prototype'] or profile['model_id'] != MODEL or profile['revision'] != REVISION or snapshot.name != REVISION:
        raise ValueError('Unapproved/non-pinned prototype profile')
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), revision=REVISION, local_files_only=True)
    messages = request['messages']
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if len(ids) > policy['input_cap']:
        raise ValueError('Full prompt exceeds model input budget')
    if request['kind'] == 'tokenize':
        return dict(status='PASS', kind='tokenize', rendered=rendered, input_ids=ids,
                    model_id=MODEL, revision=REVISION)
    if request.get('expected_input_tokens') != len(ids):
        raise ValueError('Host and worker prompt token counts disagree')
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('Approved local profile requires CUDA; no CPU/model fallback')
    config = json.loads((snapshot / 'config.json').read_text(encoding='utf-8'))
    if config['max_position_embeddings'] < policy['input_cap'] + policy['output_cap'] + policy['reserved_margin']:
        raise ValueError('Model context window insufficient for frozen caps')
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    model = AutoModelForCausalLM.from_pretrained(str(snapshot), revision=REVISION,
        local_files_only=True, device_map='auto', torch_dtype=torch.float16)
    load_ms = round((time.monotonic()-start)*1000)
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                          return_tensors='pt').to(model.device)
    if inputs.shape[-1] != len(ids):
        raise ValueError('Tokenization changed before inference')
    settings = deepcopy(model.generation_config)
    settings.do_sample, settings.max_length = False, None
    settings.temperature, settings.top_p, settings.top_k = 1.0, 1.0, 50
    start = time.monotonic()
    with torch.inference_mode():
        output, diagnostics = generate_observed(model, inputs, settings, generation_kwargs(policy['output_cap']),
            lambda value: atomic_json(Path(diagnostics_path), value) if diagnostics_path is not None else None)
    generated = output[0, inputs.shape[-1]:].tolist()
    eos = settings.eos_token_id
    eos = [eos] if isinstance(eos, int) else eos or []
    truncated = len(generated) >= policy['output_cap'] and (not generated or generated[-1] not in eos)
    return dict(status='PASS', kind='generate', mode='real', raw_text=tokenizer.decode(generated, skip_special_tokens=True),
        input_tokens=len(ids), output_tokens=len(generated), truncated=truncated,
        finish_reason='length' if truncated else 'eos', revision=REVISION, tokenizer_revision=REVISION,
        model_id=MODEL, input_sha256=hashlib.sha256(rendered.encode('utf-8')).hexdigest(),
        model_load_ms=load_ms, generation_ms=round((time.monotonic()-start)*1000),
        generation_diagnostics=diagnostics,
        device_map={str(k): str(v) for k, v in getattr(model, 'hf_device_map', {}).items()},
        cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(), gpu=torch.cuda.get_device_name(0),
        versions={n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'tokenizers', 'accelerate')},
        api_cost_usd=0.0, scope='trusted_fixture_prototype_not_qwen32b_benchmark')

