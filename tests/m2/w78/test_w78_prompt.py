import pytest
from w78_support import CharacterChatTokenizer
from vgar.repair import context_adapter as m_context_adapter
from vgar.repair import contracts as m_contracts
from vgar.repair import prompt as m_prompt


def test_full_chat_template_count_not_snippets_only(m1_case):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    prompt = m_prompt.build_repair_prompt(task, context, {}, CharacterChatTokenizer(), m_contracts.RepairPolicy())
    assert prompt.input_tokens > 40
    assert prompt.input_tokens == len(prompt.rendered.encode('utf-8'))
    assert 'Path: auth.py' in prompt.rendered and '--- BEGIN SOURCE ---' in prompt.rendered
    assert prompt.version == 'm2-w78-v11'


def test_over_budget_needs_reexport(m1_case):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    policy = m_contracts.RepairPolicy(input_cap=10)
    with pytest.raises(ValueError, match='budget'):
        m_prompt.build_repair_prompt(task, context, {}, CharacterChatTokenizer(), policy)

