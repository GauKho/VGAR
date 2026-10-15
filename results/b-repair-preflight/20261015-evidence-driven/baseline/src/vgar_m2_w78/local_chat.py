"""Full pinned Qwen chat template/counting for offline mode, without Torch."""
import json
from pathlib import Path

from .bootstrap import verify_reference


class LocalChatTokenizer:
    def __init__(self, manifest_path):
        verify_reference()
        from vgar.graph.token_counter import LocalTokenizerCounter
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        from jinja2 import ext
        self.counter = LocalTokenizerCounter(manifest_path)
        manifest_path = Path(manifest_path).resolve()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        directory = (manifest_path.parent / manifest['assets_directory']).resolve()
        self.config = json.loads((directory / 'tokenizer_config.json').read_text(encoding='utf-8'))
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                                   extensions=[ext.loopcontrols])
        def raise_exception(message):
            raise ValueError(message)
        environment.globals['raise_exception'] = raise_exception
        environment.filters['tojson'] = lambda value, **kwargs: json.dumps(value, ensure_ascii=False, **kwargs)
        self.template = environment.from_string(self.config['chat_template'])
        self.label = self.counter.counter_label + ':full-chat-template'

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        rendered = self.template.render(messages=messages, add_generation_prompt=add_generation_prompt,
            bos_token=self.config.get('bos_token'), eos_token=self.config.get('eos_token'), tools=None)
        # Only len(ids) is consumed by prompt builder; native counter encodes the full text.
        return range(self.counter(rendered)) if tokenize else rendered

