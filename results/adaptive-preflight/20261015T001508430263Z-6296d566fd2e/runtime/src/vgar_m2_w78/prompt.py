from dataclasses import dataclass, field
import json
from pathlib import Path

from .evidence import digest

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class PromptArtifact:
    messages: list[dict]
    rendered: str
    input_tokens: int
    template_hash: str
    prompt_hash: str
    version: str
    tokenizer_label: str
    metadata: dict = field(default_factory=dict)


def template_path(version: str) -> Path:
    files = {f'm2-w78-v{n}': f'repair_v{n}.txt' for n in (1, 2, 3, 4)}
    if version not in files:
        raise ValueError('Unsupported prompt version: ' + str(version))
    return ROOT / 'prompts' / files[version]


def build_repair_prompt(task, handoff, baseline, tokenizer, policy) -> PromptArtifact:
    handoff.assert_unchanged()
    template = template_path(policy.prompt_version).read_text(encoding='utf-8')
    context, metadata = handoff.context_text, {}
    if policy.prompt_version in ('m2-w78-v3', 'm2-w78-v4'):
        from .context_presentation import present_context
        context, metadata = present_context(handoff)
    policy_text = json.dumps({'allowed_source_paths': task.allowed_source_paths,
                              'protected_paths': task.protected_paths})
    # Baseline is host-produced execution evidence, never a developer/gold patch.
    failure_text = json.dumps(baseline.get('failed_cases', []), ensure_ascii=False)
    messages = [dict(role='system', content=template + '\nHost path policy: ' + policy_text),
                dict(role='user', content='Issue:\n' + task.issue_text + '\nBaseline failed cases:\n' +
                     failure_text + '\nRepository context:\n' + context)]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if not isinstance(rendered, str) or len(ids) > policy.input_cap:
        raise ValueError('Full prompt exceeds input budget; re-export smaller context')
    return PromptArtifact(messages, rendered, len(ids), digest(template), digest(rendered),
                          policy.prompt_version, getattr(tokenizer, 'label', 'explicit-backend-tokenizer'), metadata)

