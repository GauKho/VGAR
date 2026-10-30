import copy
import pytest
from vgar.repair import context_adapter as m_context_adapter
from vgar.repair import test_selection as m_test_selection


def test_failing_inputs_union_and_original_snapshot(m1_case):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    selection = m_test_selection.select_relevant_tests(('auth.py',), context, task)
    assert 'tests/test_auth.py::test_login_rejects_whitespace' in selection['required_selectors']
    assert selection['report']['targets']['auth.py']['mapping_status'] == 'linked'
    assert selection['selected'] == ('tests',)


@pytest.mark.parametrize('mapping', ['missing_mapping', 'partial_mapping', 'unlinked'])
def test_mapping_gaps_require_approved_fallback(m1_case, mapping):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    hints = copy.deepcopy(context.hints)
    symbols = {key for key, binding in context.manifest['items'].items() if binding['path'] == 'auth.py'}
    if mapping == 'unlinked':
        hints['test_links']['auth.py'] = []
    else:
        for key in {'auth.py'} | (symbols if mapping == 'missing_mapping' else set()):
            hints['test_links'].pop(key, None)
            hints['link_details'].pop(key, None)
    context.hints = hints
    result = m_test_selection.select_relevant_tests(('auth.py',), context, task)
    assert result['report']['targets']['auth.py']['mapping_status'] == mapping
    assert result['fallback_required'] and result['selected'] == ('tests',)


def test_admitted_task_runs_only_its_own_scope(m1_case):
    """Docker admission executes only task.fallback_scope (W10 D15); bundle hints are recorded, not run."""
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    assert list(context.hints['fallback_scope']) == ['tests']  # the bundle hints the whole test tree
    task = task.model_copy(update={'fallback_scope': ('tests/test_auth.py',)})
    result = m_test_selection.select_relevant_tests(('auth.py',), context, task, admitted=True)
    assert result['selected'] == result['fallback_scope'] == ('tests/test_auth.py',)
    assert list(result['report']['fallback_scope']) == ['tests']
    widened = m_test_selection.select_relevant_tests(('auth.py',), context, task)
    assert set(widened['selected']) > {'tests/test_auth.py'}  # native fixtures keep the approved hint scope


def test_limited_links_and_missing_scope_is_incomplete(m1_case):
    task, counter = m1_case
    context = m_context_adapter.load_handoff(task, counter, counter.counter_label)
    context.hints['link_details']['auth.py']['traversal_limited'] = True
    context.hints['fallback_scope'] = []
    task = task.model_copy(update={'fallback_scope': ()})
    with pytest.raises(ValueError, match='fallback'):
        m_test_selection.select_relevant_tests(('auth.py',), context, task)

