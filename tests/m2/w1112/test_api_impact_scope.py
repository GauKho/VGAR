"""T1: patch-scoped API analysis must not erase affected unknowns or breaks."""
from __future__ import annotations

import copy

import pytest

from vgar.repair.api_check import check_api


def sources(text):
    return {'api.py': text.encode('utf-8')}


@pytest.mark.parametrize('unrelated', [
    '@framework\ndef decorated(x): return x\n',
    'class Inherited(Base): pass\n',
    'if configured:\n    def conditional(x): pass\n',
    'from external import exposed\n',
    'def repeated(x): pass\ndef repeated(x): pass\n',
], ids=['decorator', 'inherited-constructor', 'conditional', 'reexport', 'duplicate'])
@pytest.mark.parametrize(('new', 'status', 'signature'), [
    ('def api(x): return x + 1\n', 'PASS', False),
    ('def api(x, required): return x\n', 'FAIL', True),
])
def test_unrelated_unknown_does_not_mask_changed_public_symbol(unrelated, new, status, signature):
    before = sources(unrelated + 'def api(x): return x\n')
    after = sources(unrelated + new)
    original = copy.deepcopy((before, after))
    assert check_api(before, after).status == 'NOT_RUN'  # legacy default unchanged
    result = check_api(before, after, changed_only=True)
    assert result.status == status
    assert result.details['signature_changed'] == {'available': True, 'value': signature}
    scope = result.details['analysis_scope']
    assert scope['mode'] == 'changed-public-symbols'
    assert scope['selected'] == {'api.py': ['api']}
    assert scope['excluded_diagnostics']
    assert result.details['diagnostics'] == []
    assert (before, after) == original


@pytest.mark.parametrize('body', [
    '    def run(self, x): return x + 1\n',
    '    def run(self, x, required): return x\n',
])
def test_changed_method_does_not_require_resolving_unchanged_inherited_constructor(body):
    before = sources('class Service(Base):\n    def run(self, x): return x\n')
    result = check_api(before, sources('class Service(Base):\n' + body), changed_only=True)
    assert result.status == ('FAIL' if 'required' in body else 'PASS')
    assert result.details['analysis_scope']['selected'] == {'api.py': ['Service.run']}


@pytest.mark.parametrize(('old', 'new', 'reason'), [
    ('@framework\ndef api(x): return x\n', '@framework\ndef api(x, y): return x\n',
     'API_UNSUPPORTED_DECLARATION'),
    ('class C(Base): pass\n', 'class C(OtherBase): pass\n', 'API_INHERITED_CONSTRUCTOR'),
    ('from a import api\n', 'from b import api\n', 'API_UNSUPPORTED_EXPORT'),
    ('def api(x): pass\n', 'def api(x): pass\ndef api(x, y): pass\n', 'API_AMBIGUOUS_BINDING'),
    ('def _impl(x): pass\napi = _impl\n', 'def _impl(x, y): pass\napi = _impl\n',
     'API_UNSUPPORTED_DECLARATION'),
    ('class C:\n    @framework\n    def run(self, x): pass\n',
     'class C:\n    @framework\n    def run(self, x, y): pass\n', 'API_UNSUPPORTED_DECLARATION'),
    ('@framework\nclass C:\n    def run(self, x): pass\n',
     '@framework\nclass C:\n    def run(self, x, y): pass\n', 'API_UNSUPPORTED_DECLARATION'),
    ('__all__ = discover()\ndef api(x): pass\n',
     '__all__ = discover()\ndef api(x, y): pass\n', 'API_DYNAMIC_EXPORTS'),
], ids=['decorated', 'base', 'import', 'duplicate', 'private-alias', 'decorated-method',
        'decorated-class', 'dynamic-all'])
def test_affected_unknown_stays_not_run(old, new, reason):
    result = check_api(sources(old), sources(new), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert reason in result.reasons
    assert result.details['signature_changed']['available'] is False


def test_alias_dependencies_are_transitive():
    before = 'def _impl(x): pass\n_middle = _impl\napi = _middle\n'
    after = before.replace('_impl(x)', '_impl(x, y)')
    result = check_api(sources(before), sources(after), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert 'api' in result.details['analysis_scope']['selected']['api.py']


@pytest.mark.parametrize(('old', 'new', 'status', 'reason'), [
    ("__all__ = ['api']\ndef api(x): pass\n", "__all__ = []\ndef api(x): pass\n",
     'FAIL', 'API_SYMBOL_REMOVED'),
    ('def api(x): pass\n', '# removed\n', 'FAIL', 'API_SYMBOL_REMOVED'),
    ('class C:\n    def run(self, x): pass\n', 'class C: pass\n', 'FAIL', 'API_SYMBOL_REMOVED'),
    ('class C:\n    def __init__(self, x=1): pass\n',
     'class C:\n    def __init__(self, x): pass\n', 'FAIL', 'API_SIGNATURE_INCOMPATIBLE'),
    ('def api(x): pass\n', 'def api(:\n', 'ERROR', 'API_PARSE_ERROR'),
])
def test_scoping_preserves_removals_constructors_exports_and_parse_errors(old, new, status, reason):
    result = check_api(sources(old), sources(new), changed_only=True)
    assert result.status == status and reason in result.reasons


def test_line_moves_comments_and_private_body_changes_do_not_expand_public_scope():
    before = sources('from external import api\ndef _private(x): return x\n')
    after = sources('# inserted\nfrom external import api\ndef _private(x): return x + 1\n')
    result = check_api(before, after, changed_only=True)
    assert result.status == 'PASS'
    assert result.details['analysis_scope']['selected'] == {'api.py': []}
    assert result.details['signature_changed']['value'] is False


def test_scoped_analysis_is_deterministic_and_does_not_hide_empty_input():
    before = {'z.py': b'from ext import public\n', 'a.py': b'def api(x): pass\n'}
    after = dict(before, **{'a.py': b'def api(x, y): pass\n'})
    first = check_api(before, after, changed_only=True)
    second = check_api(dict(reversed(list(before.items()))), after, changed_only=True)
    assert first.details == second.details and first.reasons == second.reasons
    assert check_api({}, {}, changed_only=True).status == 'NOT_RUN'


@pytest.mark.parametrize(('old', 'new'), [
    ('class C:\n    @framework\n    def other(self): pass\n    def run(self, x): pass\n',
     'class C:\n    @framework\n    def other(self): pass\n    def run(self, x, y): pass\n'),
    ('class C(Base):\n    @framework\n    def other(self): pass\n    def run(self, x): pass\n',
     'class C(Base):\n    @framework\n    def other(self): pass\n    def run(self, x, y): pass\n'),
])
def test_unsupported_sibling_method_does_not_mask_a_method_break(old, new):
    result = check_api(sources(old), sources(new), changed_only=True)
    assert result.status == 'FAIL'
    assert 'API_SIGNATURE_INCOMPATIBLE' in result.reasons
    assert result.details['analysis_scope']['selected'] == {'api.py': ['C.run']}


@pytest.mark.parametrize(('old', 'new', 'status'), [
    ('', '@framework\ndef api(x): pass\n', 'NOT_RUN'),
    ('@framework\ndef api(x): pass\n', '', 'NOT_RUN'),
    ('', 'def api(x): pass\n', 'PASS'),
    ('def api(x): pass\n', '', 'FAIL'),
])
def test_added_and_deleted_files_cannot_drop_unsupported_public_symbols(old, new, status):
    result = check_api(sources(old) if old else {}, sources(new) if new else {}, changed_only=True)
    assert result.status == status


@pytest.mark.parametrize(('old', 'new'), [
    ('_default = 1\n@framework\ndef api(x=_default): pass\n',
     '_default = 2\n@framework\ndef api(x=_default): pass\n'),
    ('class _Base: pass\nclass C(_Base): pass\n',
     'class _Base:\n    def __init__(self, required): pass\nclass C(_Base): pass\n'),
    ('class C:\n    def _impl(self, x): pass\n    api = _impl\n',
     'class C:\n    def _impl(self, x, y): pass\n    api = _impl\n'),
    ('class C:\n    class Nested: pass\n',
     'class C:\n    class Nested(Base): pass\n'),
])
def test_affected_unsupported_dependencies_and_nested_class_are_not_measured_zero(old, new):
    result = check_api(sources(old), sources(new), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert result.details['signature_changed']['value'] is None


def test_unchanged_dynamic_exports_remain_unknown_without_a_safe_membership_proof():
    raw = sources('__all__ = discover()\ndef api(x): pass\n')
    result = check_api(raw, raw, changed_only=True)
    assert result.status == 'NOT_RUN' and 'API_DYNAMIC_EXPORTS' in result.reasons


def test_changed_only_rejects_non_boolean_option():
    with pytest.raises(ValueError, match='changed_only'):
        check_api({}, {}, changed_only=1)


def test_public_class_alias_observes_a_changed_method_in_private_class():
    before = 'class _Impl:\n    def api(self, x): pass\nPublic = _Impl\n'
    after = before.replace('api(self, x)', 'api(self, x, y)')
    result = check_api(sources(before), sources(after), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert 'API_UNSUPPORTED_DECLARATION' in result.reasons
    assert result.details['analysis_scope']['selected'] == {'api.py': ['Public']}


@pytest.mark.parametrize('same_block', [False, True])
def test_private_conditional_change_does_not_select_unchanged_conditional_api(same_block):
    before = ('if configured:\n    def conditional(x): pass\n'
              + ('    _private = 1\n' if same_block else 'if flag:\n    _private = 1\n'))
    after = before.replace('_private = 1', '_private = 2')
    result = check_api(sources(before), sources(after), changed_only=True)
    assert result.status == 'PASS'
    assert result.details['analysis_scope']['selected'] == {'api.py': []}


@pytest.mark.parametrize('declaration', [
    '@framework\ndef api(x): return x\n',
    '@framework\ndef api():\n    x = 3\n    return x\n',
    '@framework\ndef api():\n    def nested(x): return x\n    return nested(3)\n',
])
def test_lexical_locals_do_not_depend_on_module_binding(declaration):
    result = check_api(sources('x = 1\n' + declaration), sources('x = 2\n' + declaration),
                       changed_only=True)
    assert result.status == 'PASS'
    assert result.details['analysis_scope']['selected'] == {'api.py': ['x']}


def test_changed_conditional_guard_and_global_dependency_remain_unknown():
    before = 'if configured:\n    def conditional(x): pass\n'
    result = check_api(sources(before), sources(before.replace('configured', 'different')),
                       changed_only=True)
    assert result.status == 'NOT_RUN'
    before = 'x = 1\n@framework\ndef api(): return x\n'
    result = check_api(sources(before), sources(before.replace('x = 1', 'x = 2')), changed_only=True)
    assert result.status == 'NOT_RUN'


def test_conditional_constructor_guard_is_an_affected_class_dependency():
    before = '_flag = True\nclass C:\n    if _flag:\n        def __init__(self, required): pass\n'
    result = check_api(sources(before), sources(before.replace('True', 'False')), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert 'C' in result.details['analysis_scope']['selected']['api.py']


def test_conditional_method_global_is_not_shadowed_by_class_attribute():
    before = 'x = 1\nclass C:\n    x = 3\n    if flag:\n        def api(self): return x\n'
    result = check_api(sources(before), sources(before.replace('x = 1', 'x = 2')), changed_only=True)
    assert result.status == 'NOT_RUN'
    assert 'C.api' in result.details['analysis_scope']['selected']['api.py']
