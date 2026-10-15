import pytest
from conftest import CharacterChatTokenizer
from test_bootstrap import api


def test_full_chat_template_count_not_snippets_only(m1_case):
    task, counter = m1_case
    context = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    prompt = api('prompt').build_repair_prompt(task, context, {}, CharacterChatTokenizer(), api('contracts').RepairPolicy())
    assert prompt.input_tokens > 40
    assert prompt.input_tokens == len(prompt.rendered.encode('utf-8'))
    assert 'auth.py' in prompt.rendered and 'Range:' in prompt.rendered
    assert prompt.version == 'm2-w78-v1'


def test_over_budget_needs_reexport(m1_case):
    task, counter = m1_case
    context = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    policy = api('contracts').RepairPolicy(input_cap=10)
    with pytest.raises(ValueError, match='budget'):
        api('prompt').build_repair_prompt(task, context, {}, CharacterChatTokenizer(), policy)

