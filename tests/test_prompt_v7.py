from conftest import CharacterChatTokenizer
from test_bootstrap import api


def test_v7_full_prompt_keeps_original_context_without_final_feedback(m1_case):
    task,counter = m1_case
    handoff = api('context_adapter').load_handoff(task,counter,counter.counter_label)
    p = api('prompt').build_repair_prompt(task,handoff,{},CharacterChatTokenizer(),
        api('contracts').RepairPolicy(prompt_version='m2-w78-v7'))
    assert p.version == 'm2-w78-v7' and p.input_tokens <= 6000
    assert p.metadata.get('feedback') is None
    assert [x['node_id'] for x in p.metadata['source_items']] == [x.node_id for x in handoff.context.items]
    assert all(x.snippet in p.messages[-1]['content'] for x in handoff.context.items)
