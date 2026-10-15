"""V10 gives editable full-line coordinates without changing M1 bytes/legacy views."""
import re
from types import SimpleNamespace

import pytest

from conftest import CharacterChatTokenizer, ROOT
from test_bootstrap import api


def test_v10_labels_source_permissions_without_changing_snippets(m1_case):
    task, counter = m1_case
    handoff = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    prompt = api('prompt').build_repair_prompt(task, handoff, {}, CharacterChatTokenizer(),
        api('contracts').RepairPolicy(prompt_version='m2-w78-v10'))
    assert prompt.metadata['presentation_version'] == 'source-lines-v10'
    assert [m['node_id'] for m in prompt.metadata['source_items']] == [i.node_id for i in handoff.context.items]
    for item, meta in zip(handoff.context.items, prompt.metadata['source_items']):
        assert item.snippet in prompt.messages[1]['content']
        if item.path == 'auth.py':
            assert meta['edit_permission'] == 'allowed'
            assert (meta['patch_old_start'], meta['patch_old_count']) == (1, 2)
            assert meta['source_has_final_newline'] is True
        else:
            assert meta['edit_permission'] == 'read-only' and meta['patch_old_start'] is None
    assert 'Patch_old_count: 2' in prompt.rendered and 'Edit_permission: read-only' in prompt.rendered
    assert 'Host path policy: {' not in prompt.messages[0]['content']
    assert prompt.metadata['original_m1_context'] == handoff.context_text


def test_v10_rejects_partial_production_line_before_generation(tmp_path):
    module = api('context_presentation')
    source = tmp_path/'app.py'
    source.write_bytes(b'value = 123\n')
    item = SimpleNamespace(node_id='node:partial', path='app.py', symbol='value', snippet='123',
        relevance_score=1.0, confidence=1.0,
        range=SimpleNamespace(start_line=1, start_col=8, end_line=1, end_col=11))
    handoff = SimpleNamespace(assert_unchanged=lambda: None, context_text='original',
        context=SimpleNamespace(graph_version='g', items=[item]),
        task=SimpleNamespace(source_repo=tmp_path, allowed_source_paths=('app.py',), protected_paths=('tests',)),
        manifest={'files': {'app.py': api('evidence').digest(source.read_bytes())}})
    with pytest.raises(ValueError, match='complete source lines'):
        module.present_context(handoff, absolute_lines=True, patch_contract=True)


@pytest.mark.parametrize('eol', [b'\n', b'\r\n'])
def test_v10_neutral_two_file_replacement_passes_current_parser_and_git(tmp_path, eol):
    template = api('prompt').template_path('m2-w78-v10').read_text(encoding='utf-8')
    example, = re.findall(r'BEGIN FORMAT DIFF\n(.*?)END FORMAT DIFF', template, re.S)
    left = b'MARKER = 0\n\ndef twice(x):\n    return x\n'.replace(b'\n', eol)
    right = b'MARKER = 0\n\n\n\n\ndef frame(value):\n    kept = value\n    return kept\n'.replace(b'\n', eol)
    source = tmp_path/'source'
    source.mkdir()
    (source/'neutral_left.py').write_bytes(left)
    (source/'neutral_right.py').write_bytes(right)
    module = api('patch')
    parsed = module.parse_unified_diff(example, module.PatchPolicy(('neutral_left.py', 'neutral_right.py'), ('tests',)))
    assert [(v[0]['old'], v[0]['oc']) for v in parsed.files.values()] == [(3, 2), (6, 3)]
    assert all(row[0] in '+-' for v in parsed.files.values() for row in v[0]['body'])
    with api('workspace').create_workspace(source, tmp_path/'private') as lease:
        result = module.apply_patch(lease, parsed, api('executor').NativeExecutor(lease))
        assert result.status == 'PASS'
        assert (lease.path/'neutral_left.py').read_bytes() == left.replace(b'return x', b'return x + x')
        assert (lease.path/'neutral_right.py').read_bytes() == right.replace(b'return kept', b"return '<' + kept + '>'")
    assert (source/'neutral_left.py').read_bytes() == left


@pytest.mark.parametrize('version', range(1, 10))
def test_previous_versions_keep_baseline_messages(m1_case, version):
    task, counter = m1_case
    handoff = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    policy = api('contracts').RepairPolicy(prompt_version=f'm2-w78-v{version}')
    baseline = ROOT/'results/b-repair-preflight/20261015-evidence-driven/baseline'
    namespace = {'__file__': str(baseline/'src/vgar_m2_w78/prompt.py'), '__package__': 'vgar_m2_w78'}
    exec(compile((baseline/'src/vgar_m2_w78/prompt.py').read_bytes(), 'baseline-prompt.py', 'exec'), namespace)
    # Baseline present_context's defaults must remain the legacy presentation.
    expected = namespace['build_repair_prompt'](task, handoff, {}, CharacterChatTokenizer(), policy)
    actual = api('prompt').build_repair_prompt(task, handoff, {}, CharacterChatTokenizer(), policy)
    assert actual.messages == expected.messages and actual.prompt_hash == expected.prompt_hash


def test_v10_budget_is_checked_for_full_chat(m1_case):
    task, counter = m1_case
    handoff = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    with pytest.raises(ValueError, match='budget'):
        api('prompt').build_repair_prompt(task, handoff, {}, CharacterChatTokenizer(),
            api('contracts').RepairPolicy(prompt_version='m2-w78-v10', input_cap=10))
