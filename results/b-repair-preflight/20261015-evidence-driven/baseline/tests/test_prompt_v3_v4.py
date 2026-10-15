import json
import re
from types import SimpleNamespace

import pytest
from conftest import CharacterChatTokenizer, ROOT
from test_bootstrap import api


@pytest.mark.parametrize('source,snippet,start,end,want', [
    (b'def f():\n    return 1\n', 'def f():\n    return 1\n', (1,0),(3,0),(2,2,2)),
    (b'def f():\r\n    return 1\r\n', 'def f():\r\n    return 1\r\n', (1,0),(3,0),(2,2,2)),
    (b'a=1\n\nb=2\n', 'a=1\n\nb=2\n', (1,0),(4,0),(3,3,3)),
    (b'value=1', 'value=1', (1,0),(1,7),(1,1,1)),
    ('αβ\nx\n'.encode(), 'β', (1,2),(1,4),(1,2,1)),
    (b'class C:\n    def run(self):\n        return 1\n', '    def run(self):\n        return 1\n', (2,0),(4,0),(2,3,3)),
    (b'', '', (1,0),(1,0),(0,0,None)),
])
def test_metadata_counts_actual_lines_not_exclusive_endpoint(source, snippet, start, end, want):
    item = SimpleNamespace(node_id='node:sample', path='sample.py', symbol='sample', snippet=snippet,
        range=SimpleNamespace(start_line=start[0],start_col=start[1],end_line=end[0],end_col=end[1]))
    metadata = api('context_presentation').describe_item(item, source)
    assert (metadata['snippet_line_count'], metadata['source_line_count'], metadata['last_covered_line']) == want
    assert metadata['end_exclusive'] == list(end)


@pytest.mark.parametrize('version', ['m2-w78-v3','m2-w78-v4'])
def test_new_prompt_preserves_every_source_item_and_keeps_original_m1_text(m1_case, version):
    task, counter = m1_case
    h = api('context_adapter').load_handoff(task,counter,counter.counter_label)
    p = api('prompt').build_repair_prompt(task,h,{},CharacterChatTokenizer(),api('contracts').RepairPolicy(prompt_version=version))
    assert p.metadata['original_m1_context'] == h.context_text
    assert [i['node_id'] for i in p.metadata['source_items']] == [i.node_id for i in h.context.items]
    for item in h.context.items:
        assert item.snippet in p.messages[-1]['content']
    auth = next(i for i in p.metadata['source_items'] if i['path']=='auth.py')
    assert auth['snippet_line_count'] == 2 and auth['source_line_count'] == 2
    assert 'Snippet_line_count: 2' in p.rendered
    assert p.input_tokens == len(p.rendered.encode())


@pytest.mark.parametrize('version',['m2-w78-v1','m2-w78-v2'])
def test_legacy_messages_are_identical_to_original_assembly(m1_case, version):
    task,counter=m1_case
    h=api('context_adapter').load_handoff(task,counter,counter.counter_label)
    policy=api('contracts').RepairPolicy(prompt_version=version)
    original=(ROOT/'prompts'/('repair_v1.txt' if version.endswith('v1') else 'repair_v2.txt')).read_text(encoding='utf-8')
    expected=[{'role':'system','content':original+'\nHost path policy: '+json.dumps({'allowed_source_paths':task.allowed_source_paths,'protected_paths':task.protected_paths})},
              {'role':'user','content':'Issue:\n'+task.issue_text+'\nBaseline failed cases:\n[]\nRepository context:\n'+h.context_text}]
    prompt=api('prompt').build_repair_prompt(task,h,{},CharacterChatTokenizer(),policy)
    assert prompt.messages == expected


def test_source_changed_after_handoff_blocks_v3_before_model(m1_case):
    task,counter=m1_case
    h=api('context_adapter').load_handoff(task,counter,counter.counter_label)
    (task.source_repo/'auth.py').write_bytes(b'def login(value): return True\n')
    with pytest.raises(ValueError,match='source|Source'):
        api('prompt').build_repair_prompt(task,h,{},CharacterChatTokenizer(),api('contracts').RepairPolicy(prompt_version='m2-w78-v3'))


@pytest.mark.parametrize('version',['m2-w78-v3','m2-w78-v4'])
def test_neutral_format_examples_are_accepted_by_strict_parser(version):
    policy=api('contracts').RepairPolicy(prompt_version=version)
    template=api('prompt').template_path(policy.prompt_version).read_text(encoding='utf-8')
    examples=re.findall(r'BEGIN FORMAT DIFF\n(.*?)\nEND FORMAT DIFF',template,re.S)
    assert len(examples)==(1 if version.endswith('v3') else 2)
    for raw in examples:
        parsed=api('patch').parse_unified_diff(raw+'\n',api('patch').PatchPolicy(('example.py','lower_bound.py','frame.py'),('tests',)))
        assert parsed.files
    assert '.strip()' not in template and 'tax_percent' not in template and 'discount_percent' not in template


def test_unknown_version_cannot_fall_back_to_v1(m1_case):
    task,counter=m1_case
    h=api('context_adapter').load_handoff(task,counter,counter.counter_label)
    invalid=api('contracts').RepairPolicy().model_copy(update={'prompt_version':'wrong'})
    with pytest.raises(ValueError,match='version'):
        api('prompt').build_repair_prompt(task,h,{},CharacterChatTokenizer(),invalid)


def test_v3_full_prompt_over_budget_blocks_generation(m1_case):
    task,counter=m1_case
    h=api('context_adapter').load_handoff(task,counter,counter.counter_label)
    with pytest.raises(ValueError,match='budget'):
        api('prompt').build_repair_prompt(task,h,{},CharacterChatTokenizer(),api('contracts').RepairPolicy(prompt_version='m2-w78-v3',input_cap=20))


def test_historical_raw_v2_remains_rejected():
    raw=(ROOT/'results/repair/20261014T091104527173Z-8e59e14c75c7/raw_model_output.txt').read_text(encoding='utf-8')
    with pytest.raises(ValueError,match='hunk'):
        api('patch').parse_unified_diff(raw,api('patch').PatchPolicy(('auth.py',),('tests',)))
