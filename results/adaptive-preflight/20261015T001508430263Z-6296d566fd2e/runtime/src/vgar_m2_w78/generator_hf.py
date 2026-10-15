"""Host-chosen pinned profile, bounded worker, no eager Torch in core."""
import json
import os
from pathlib import Path
import uuid

from .bootstrap import ROOT, remaining_timeout
from .evidence import atomic_json
from .model_worker import invoke_worker


class HFGenerator:
    mode = 'real'
    def __init__(self, profile, worker_root, policy=None):
        if not profile.approved_prototype:
            raise ValueError('Real profile must be approved')
        if profile.snapshot.name != profile.revision or not profile.interpreter.is_file():
            raise ValueError('Pinned snapshot/interpreter missing')
        self.profile, self.worker_root, self.policy = profile, Path(worker_root), policy

    def request(self, kind, messages, policy, timeout, expected_input_tokens=None):
        folder = self.worker_root.resolve() / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=False)
        request, response = folder / 'request.json', folder / 'response.json'
        atomic_json(request, dict(kind=kind, messages=messages, profile=self.profile.model_dump(mode='json'),
                                 policy=policy.model_dump(), expected_input_tokens=expected_input_tokens))
        # Environment only points to the tool package, not an untrusted target.
        old = {key: os.environ.get(key) for key in ('PYTHONPATH', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')}
        os.environ.update(PYTHONPATH=str(ROOT / 'src'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        try:
            result = invoke_worker((str(self.profile.interpreter), '-B', '-m', 'vgar_m2_w78.hf_worker',
                                    str(request), str(response)), folder, response, timeout)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        atomic_json(folder / 'command.json', result)
        return result

    def generate(self, prompt, profile, timeout_seconds):
        result = self.request('generate', prompt.messages, self.policy, timeout_seconds, prompt.input_tokens)
        if result['status'] != 'PASS':
            return dict(status='ERROR', mode='real', reason=result.get('reason'), worker=result)
        response = result['response']
        if response['input_sha256'] != prompt.prompt_hash.removeprefix('sha256:'):
            return dict(status='ERROR', mode='real', reason='Worker prompt bytes differ', worker=result)
        return dict(response, worker=result)


class HFChatTokenizer:
    def __init__(self, generator, policy, timeout=120):
        self.generator, self.policy, self.timeout = generator, policy, timeout
        self.cache = {}
        self.deadline = None
        self.label = generator.profile.model_id + '@' + generator.profile.revision

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        timeout = remaining_timeout(self.deadline, self.timeout)
        key = json.dumps(messages, sort_keys=True)
        if key not in self.cache:
            result = self.generator.request('tokenize', messages, self.policy, timeout)
            if result['status'] != 'PASS':
                raise ValueError('Tokenizer worker failed: ' + str(result.get('reason')))
            self.cache[key] = result['response']
        return self.cache[key]['input_ids'] if tokenize else self.cache[key]['rendered']

