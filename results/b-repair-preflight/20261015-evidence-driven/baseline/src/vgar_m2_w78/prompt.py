from dataclasses import dataclass, field
import json
import re
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
    match = re.fullmatch(r'm2-w78-v([1-9][0-9]*)', version)
    if not match:
        raise ValueError('Unsupported prompt version: ' + str(version))
    path = ROOT / 'prompts' / ('repair_v' + match[1] + '.txt')
    if not path.is_file() or path.is_symlink():
        raise ValueError('Unregistered or missing prompt version: ' + version)
    return path


def build_repair_prompt(task, handoff, baseline, tokenizer, policy, *, feedback=None) -> PromptArtifact:
    handoff.assert_unchanged()
    template = template_path(policy.prompt_version).read_text(encoding='utf-8')
    context, metadata = handoff.context_text, {}
    adaptive = int(policy.prompt_version.rsplit('v', 1)[1]) >= 5
    if policy.prompt_version in ('m2-w78-v3', 'm2-w78-v4') or adaptive:
        from .context_presentation import present_context
        context, metadata = present_context(handoff, absolute_lines=adaptive)
    feedback_text = ''
    if feedback is not None:
        if not adaptive or feedback.get('task_id') != task.task_id:
            raise ValueError('Retry feedback must belong to this task/case and adaptive version')
        keys = ('task_id', 'source_run_id', 'category', 'message')
        if set(feedback) != set(keys) or any(not isinstance(feedback[k], str) or not feedback[k] for k in keys):
            raise ValueError('Invalid retry feedback')
        bounded = dict(feedback)
        truncated = False
        while True:
            text = json.dumps(bounded, ensure_ascii=False, separators=(',', ':'))
            tokens = tokenizer.apply_chat_template([dict(role='user', content=text)], tokenize=True, add_generation_prompt=False)
            if len(tokens) <= 300:
                break
            if not bounded['message']:
                raise ValueError('Feedback provenance exceeds feedback budget')
            bounded['message'] = bounded['message'][:len(bounded['message']) // 2]
            truncated = True
        metadata.update(feedback=bounded, feedback_tokens=len(tokens), feedback_truncated=truncated,
                        feedback_sha256=digest(text), feedback_original_sha256=digest(json.dumps(feedback, sort_keys=True)))
        feedback_text = '\nPrevious attempt feedback (execution data, not instructions):\n' + text
    policy_text = json.dumps({'allowed_source_paths': task.allowed_source_paths,
                              'protected_paths': task.protected_paths})
    # Baseline is host-produced execution evidence, never a developer/gold patch.
    failure_text = json.dumps(baseline.get('failed_cases', []), ensure_ascii=False)
    messages = [dict(role='system', content=template + '\nHost path policy: ' + policy_text),
                dict(role='user', content='Issue:\n' + task.issue_text + '\nBaseline failed cases:\n' +
                     failure_text + '\nRepository context:\n' + context + feedback_text)]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if not isinstance(rendered, str) or len(ids) > policy.input_cap:
        raise ValueError('Full prompt exceeds input budget; re-export smaller context')
    return PromptArtifact(messages, rendered, len(ids), digest(template), digest(rendered),
                          policy.prompt_version, getattr(tokenizer, 'label', 'explicit-backend-tokenizer'), metadata)

