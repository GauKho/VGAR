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


def test_context_path_listing_names_only_allowed_paths_shown_in_context(m1_case):
    task, counter = m1_case
    unshown = tuple(f'unshown/module_{i:02}.py' for i in range(40))
    task = task.model_copy(update={'allowed_source_paths': ('auth.py', 'unshown/other.py', *unshown)})
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    policy = m_contracts.RepairPolicy(input_cap=100_000)
    full = m_prompt.build_repair_prompt(task, context, {}, CharacterChatTokenizer(), policy)
    listed = m_prompt.build_repair_prompt(task, context, {}, CharacterChatTokenizer(), policy,
                                          path_listing='context')
    assert '- unshown/other.py' in full.rendered and 'path_listing' not in full.metadata
    assert '- auth.py' in listed.rendered and '- unshown/other.py' not in listed.rendered
    assert 'not listed' in listed.rendered and listed.input_tokens < full.input_tokens
    assert listed.metadata['path_listing'] == {'mode': 'context', 'listed': 1, 'allowed': 42}


def test_over_budget_needs_reexport(m1_case):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    policy = m_contracts.RepairPolicy(input_cap=10)
    with pytest.raises(ValueError, match='budget'):
        m_prompt.build_repair_prompt(task, context, {}, CharacterChatTokenizer(), policy)

