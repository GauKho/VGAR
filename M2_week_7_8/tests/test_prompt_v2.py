from conftest import CharacterChatTokenizer
from test_bootstrap import api


def test_v2_format_contract_is_versioned_without_fixture_solution(m1_case):
    task, counter = m1_case
    policy = api('contracts').RepairPolicy(prompt_version='m2-w78-v2')
    handoff = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    prompt = api('prompt').build_repair_prompt(task, handoff, {}, CharacterChatTokenizer(), policy)
    assert prompt.version == 'm2-w78-v2'
    assert 'SEARCH/REPLACE' in prompt.messages[0]['content']
    assert '--- a/example.py' in prompt.messages[0]['content']
    assert 'value.strip()' not in prompt.messages[0]['content']

