"""Catch wrong source coordinates, mutable templates and leaked retry feedback."""
import json
import re

import pytest

from conftest import CharacterChatTokenizer
from test_bootstrap import api

V5 = 'm2-w78-v5'


def test_v5_neutral_examples_bind_to_absolute_lines_without_editing_files(tmp_path):
    text = api('prompt').template_path(V5).read_text(encoding='utf-8')
    examples = re.findall(r'BEGIN FORMAT DIFF\n(.*?)END FORMAT DIFF', text, re.S)
    assert len(examples) == 1
    originals = {
        'origin_a.py': b'MARKER = 0\n\ndef magnitude(n):\n    return n\n',
        'origin_b.py': b'MARKER = 0\n\n\n\n\ndef doubled(n):\n    return n\n',
    }
    for name, data in originals.items():
        (tmp_path / name).write_bytes(data)
    module = api('patch')
    patch = module.parse_unified_diff(examples[0], module.PatchPolicy(tuple(originals), ()))
    predicted, _ = module._bind(patch, tmp_path)
    assert patch.files['origin_a.py'][0]['old'] == 3
    assert patch.files['origin_b.py'][0]['old'] == 6
    assert predicted['origin_a.py'] == b'MARKER = 0\n\ndef magnitude(n):\n    return abs(n)\n'
    assert predicted['origin_b.py'] == b'MARKER = 0\n\n\n\n\ndef doubled(n):\n    return n + n\n'
    assert all((tmp_path / n).read_bytes() == b for n, b in originals.items())


def test_v5_preserves_source_and_validates_feedback_case_and_budget(m1_case):
    task, counter = m1_case
    h = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    policy = api('contracts').RepairPolicy(prompt_version=V5)
    feedback = dict(task_id=task.task_id, source_run_id='prior-run', category='PATCH_APPLY_FAILED', message='Wrong absolute line')
    tokenizer = CharacterChatTokenizer()
    p = api('prompt').build_repair_prompt(task, h, {}, tokenizer, policy, feedback=feedback)
    assert p.version == V5 and p.metadata['feedback']['source_run_id'] == 'prior-run'
    assert p.metadata['feedback_tokens'] <= 300
    assert all(item.snippet in p.messages[-1]['content'] for item in h.context.items)
    assert 'First_shown_original_file_line: 1' in p.messages[-1]['content']
    with pytest.raises(ValueError, match='case|task'):
        api('prompt').build_repair_prompt(task, h, {}, tokenizer, policy,
            feedback=dict(feedback, task_id='different-case'))
    long = api('prompt').build_repair_prompt(task, h, {}, tokenizer, policy,
        feedback=dict(feedback, message='x' * 1000))
    assert long.metadata['feedback_tokens'] <= 300
    assert long.metadata['feedback_truncated'] is True


def test_clean_final_prompt_does_not_carry_previous_feedback(m1_case):
    task, counter = m1_case
    h = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    p = api('prompt').build_repair_prompt(task, h, {}, CharacterChatTokenizer(),
        api('contracts').RepairPolicy(prompt_version=V5))
    assert p.metadata.get('feedback') is None
    assert 'Previous attempt feedback' not in p.messages[-1]['content']


def test_registered_prompt_versions_cannot_be_missing_or_escape_root():
    for version in ('m2-w78-v99', '../repair_v5.txt', 'm2-w78-v05'):
        with pytest.raises(ValueError):
            api('prompt').template_path(version)


def test_registered_version_payload_is_internal_not_new_public_schema(m1_case):
    task, _ = m1_case
    policy = api('contracts').RepairPolicy(prompt_version=V5)
    assert policy.model_dump()['prompt_version'] == V5
    assert 'schema_version' not in json.loads(task.model_dump_json())
