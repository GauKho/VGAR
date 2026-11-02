"""M2-W11-1 contracts for static, snapshot-only public API compatibility."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from types import MappingProxyType

import pytest

from vgar.contracts.impact import ImpactReport


def test_api_remove_public_function_fails():
    assert importlib.util.find_spec('vgar.repair.api_check') is not None, 'M2-W11-1 API checker is missing'
    checker = importlib.import_module('vgar.repair.api_check')
    result = checker.check_api({'api.py': b'def public(): pass\n'}, {'api.py': b'# removed\n'})
    assert result.status == 'FAIL' and 'API_SYMBOL_REMOVED' in result.reasons


@pytest.fixture
def api():
    # Keeping this import in the fixture makes the first RED describe the missing API.
    assert importlib.util.find_spec('vgar.repair.api_check') is not None, 'M2-W11-1 API checker is missing'
    return importlib.import_module('vgar.repair.api_check')


@pytest.fixture
def report():
    """Synthetic report: no dependency on a graph, tracked database, or fixture repo."""
    return ImpactReport.model_validate({
        'repo_key': 'synthetic/api-contract',
        'repository_revision': 'baseline-revision',
        'graph_version': 'synthetic-v1',
        'graph_hash': 'sha256:' + 'a' * 64,
        'source_hash': 'sha256:' + 'b' * 64,
        'patch_hash': 'sha256:' + 'c' * 64,
        'changed': [],
        'unmapped': [],
        'risk': {'status': 'COMPLETE', 'features': [
            {'name': 'fan_out', 'available': True, 'value': 7},
            {'name': 'signature_changed', 'available': False, 'reason': 'NOT_COMPUTED'},
            {'name': 'test_coverage', 'available': False, 'reason': 'NO_CHANGED_NODES'},
        ]},
    })


def source(text):
    return {'package/api.py': text.encode('utf-8')}


def assert_signature(analysis, value):
    feature = analysis.details['signature_changed']
    assert feature['available'] is (value is not None)
    assert feature['value'] is value
    if value is None:
        assert isinstance(feature.get('reason'), str) and feature['reason']


def assert_evidence(analysis):
    assert isinstance(analysis.reasons, tuple)
    assert isinstance(analysis.details['changes'], list)
    assert isinstance(analysis.details['diagnostics'], list)
    for change in analysis.details['changes']:
        assert {'path', 'symbol', 'reason'} <= change.keys()
        assert all(isinstance(change[key], str) and change[key]
                   for key in ('path', 'symbol', 'reason'))
    # Evidence must be suitable for the existing JSON report artifacts.
    json.dumps(analysis.details, ensure_ascii=False, allow_nan=False)


@pytest.mark.parametrize(('before', 'after'), [
    ('def api(x): pass\n', 'def api(x, y): pass\n'),
    ('def api(x, y): pass\n', 'def api(x): pass\n'),
    ('def api(x, y): pass\n', 'def api(y, x): pass\n'),
    ('def api(x=1): pass\n', 'def api(x): pass\n'),
    ('def api(x, **kwargs): pass\n', 'def api(x): pass\n'),
    ('def api(*, option=1): pass\n', 'def api(): pass\n'),
    ('def api(x): pass\n', 'def api(x, /): pass\n'),
    ('def api(*, x): pass\n', 'def api(x, /): pass\n'),
    ('def api(x): pass\n', 'def api(x, *, option): pass\n'),
], ids=[
    'required-addition', 'positional-removal', 'positional-reorder', 'default-removal',
    'kwargs-removal', 'public-keyword-only-removal', 'keyword-callability-lost',
    'keyword-only-to-positional-only', 'required-keyword-only-addition',
])
def test_incompatible_signatures_fail(api, before, after):
    analysis = api.check_api(source(before), source(after))
    assert analysis.status == 'FAIL'
    assert 'API_SIGNATURE_INCOMPATIBLE' in analysis.reasons
    assert_signature(analysis, True)
    assert analysis.details['changes']
    assert_evidence(analysis)


@pytest.mark.parametrize(('before', 'after', 'changed'), [
    ('def api(x): return x\n', 'def api(x, y=None): return x\n', True),
    ('def api(x): return x\n', 'def api(x, *, y=None): return x\n', True),
    ('def api(x): return x\n', 'def api(x): return x + 1\n', False),
    ('def api(x: int) -> int: return x\n',
     'def api(x: str) -> str: return x\n', True),
    ('def api(x=1): return x\n', 'def api(x=2): return x\n', True),
    ('def api(x):\n    def nested(a): pass\n    return x\ndef _private(a): pass\n',
     'def api(x):\n    def nested(a, b): pass\n    return x\ndef _private(a, b): pass\n',
     False),
], ids=['optional-positional', 'optional-keyword', 'body-only', 'annotations',
        'default-value', 'nested-and-private'])
def test_compatible_changes_preserve_existing_calls(api, before, after, changed):
    analysis = api.check_api(source(before), source(after))
    assert analysis.status == 'PASS'
    assert 'API_SIGNATURE_INCOMPATIBLE' not in analysis.reasons
    assert_signature(analysis, changed)
    assert_evidence(analysis)


@pytest.mark.parametrize(('before', 'after', 'reason'), [
    ('def api(x): pass\n', '# removed module function\n', 'API_SYMBOL_REMOVED'),
    ('class Service:\n    def run(self): pass\n', '# removed class\n',
     'API_SYMBOL_REMOVED'),
    ('class Service:\n    def run(self, value): pass\n', 'class Service: pass\n',
     'API_SYMBOL_REMOVED'),
    ('class Service:\n    def __init__(self, value=1): pass\n',
     'class Service:\n    def __init__(self, value): pass\n',
     'API_SIGNATURE_INCOMPATIBLE'),
], ids=['module-function', 'class', 'public-method', 'constructor'])
def test_public_surface_includes_classes_methods_and_constructors(api, before, after, reason):
    analysis = api.check_api(source(before), source(after))
    assert analysis.status == 'FAIL'
    assert reason in analysis.reasons
    assert_signature(analysis, True)
    assert analysis.details['changes']
    assert_evidence(analysis)


@pytest.mark.parametrize('exported', [False, True], ids=['implicit-public', 'literal-all'])
def test_public_exports_are_selected_without_executing_code(api, exported):
    if exported:
        before = "__all__ = ['_exported']\ndef _exported(x): pass\ndef helper(x): pass\n"
        after = "__all__ = ('_exported',)\ndef _exported(x): pass\ndef helper(x, y): pass\n"
    else:
        before = 'def api(x): pass\ndef _hidden(x): pass\n'
        after = 'def api(x): pass\ndef _hidden(x, y): pass\n'
    analysis = api.check_api(source(before), source(after))
    assert analysis.status == 'PASS'
    assert_signature(analysis, False)


@pytest.mark.parametrize('exports', [
    "__all__ = discover_exports()\n",
    "__all__ = ['api']\n__all__.append('extra')\n",
    "__all__ = ['api']\n__all__ += ['extra']\n",
    "__all__ = ['api']\n__all__[0] = 'extra'\n",
], ids=['computed', 'method-mutation', 'augmented-assignment', 'item-mutation'])
def test_dynamic_exports_are_explicitly_unknown(api, exports):
    analysis = api.check_api(source('def api(x): pass\n'),
                             source(exports + 'def api(x, y): pass\n'))
    assert analysis.status == 'NOT_RUN'
    assert 'API_DYNAMIC_EXPORTS' in analysis.reasons
    assert_signature(analysis, None)
    assert_evidence(analysis)


def test_duplicate_public_bindings_are_not_silently_resolved(api):
    analysis = api.check_api(source('def api(x): pass\n'), source(
        'def api(x): pass\ndef api(x, y): pass\n'))
    assert analysis.status == 'NOT_RUN'
    assert analysis.reasons
    assert_signature(analysis, None)


def test_imported_reexports_are_not_claimed_compatible(api):
    snapshot = source("from unavailable_target import api\n__all__ = ['api']\n")
    analysis = api.check_api(snapshot, snapshot)
    assert analysis.status == 'NOT_RUN'
    assert analysis.reasons
    assert_signature(analysis, None)


@pytest.mark.parametrize('broken_side', ['baseline', 'candidate'])
def test_parse_failure_is_an_error_with_unavailable_signature(api, broken_side):
    before, after = source('def api(x): pass\n'), source('def api(x): pass\n')
    (before if broken_side == 'baseline' else after)['package/api.py'] = b'def api(:\n'
    analysis = api.check_api(before, after)
    assert analysis.status == 'ERROR'
    assert 'API_PARSE_ERROR' in analysis.reasons
    assert analysis.details['diagnostics']
    assert_signature(analysis, None)
    assert_evidence(analysis)


def test_empty_scope_is_not_a_pass(api):
    analysis = api.check_api({}, {})
    assert analysis.status == 'NOT_RUN'
    assert 'API_EMPTY_SCOPE' in analysis.reasons
    assert_signature(analysis, None)


@pytest.mark.parametrize('declaration', [
    "from exports import __all__\n",
    "from exports import names as __all__\n",
    "if configured:\n    from dependency import exposed\n",
])
def test_indirect_or_conditional_export_bindings_are_unavailable(api, declaration):
    raw = source(declaration + 'def api(x): return x\n')
    analysis = api.check_api(raw, raw)
    assert analysis.status == 'NOT_RUN'
    assert_signature(analysis, None)


@pytest.mark.parametrize(('before', 'after', 'status'), [
    ('class Service:\n    def run(self, x): return x\n',
     'class Service:\n    def run(self, x): return x + 1\n', 'PASS'),
    ('class Service: pass\n',
     'class Service:\n    def __init__(self, required): pass\n', 'FAIL'),
    ('class Service:\n    @staticmethod\n    def run(x): pass\n',
     'class Service:\n    @staticmethod\n    def run(x, required): pass\n', 'FAIL'),
    ('class Service:\n    @classmethod\n    def run(cls, x): return x\n',
     'class Service:\n    @classmethod\n    def run(cls, x, option=None): return x\n', 'PASS'),
])
def test_class_call_binding_and_implicit_constructor(api, before, after, status):
    assert api.check_api(source(before), source(after)).status == status


def test_removing_an_export_fails_even_if_implementation_remains(api):
    before = "__all__ = ['api']\ndef api(x): return x\n"
    after = "__all__ = []\ndef api(x): return x\n"
    result = api.check_api(source(before), source(after))
    assert result.status == 'FAIL' and 'API_SYMBOL_REMOVED' in result.reasons


@pytest.mark.parametrize('declaration', ['def api(x, x): pass\n', 'return 1\n', 'break\n'])
def test_compiler_rejected_syntax_is_error_without_executing_target(api, declaration):
    result = api.check_api(source('def api(x): pass\n'), source(declaration))
    assert result.status == 'ERROR' and 'API_PARSE_ERROR' in result.reasons
    assert_signature(result, None)


def test_import_overwriting_literal_all_is_unknown(api):
    snapshot = source("__all__ = ['api']\nfrom missing import __all__\ndef api(x): pass\n")
    result = api.check_api(snapshot, snapshot)
    assert result.status == 'NOT_RUN' and 'API_DYNAMIC_EXPORTS' in result.reasons
    assert_signature(result, None)


@pytest.mark.parametrize(('before', 'after'), [
    ('def _impl(x): pass\napi = _impl\n', 'def _impl(x, y): pass\napi = _impl\n'),
    ('api = lambda x: x\n', 'api = lambda x, y: x\n'),
    ('api = factory()\n', 'api = other_factory()\n'),
])
def test_assigned_callable_or_dynamic_export_is_unknown(api, before, after):
    result = api.check_api(source(before), source(after))
    assert result.status == 'NOT_RUN'
    assert_signature(result, None)


@pytest.mark.parametrize('constructor', [
    '    async def __init__(self, x): pass\n',
    '    @property\n    def __init__(self, x): pass\n',
    '    if True:\n        def __new__(cls, x): pass\n',
])
def test_unsupported_constructor_is_not_claimed_compatible(api, constructor):
    result = api.check_api(source('class C:\n    def __init__(self, x): pass\n'),
                           source('class C:\n' + constructor))
    assert result.status == 'NOT_RUN'
    assert_signature(result, None)


@pytest.mark.parametrize(('before', 'after'), [
    ('def api(x, /, **kw): pass\n', 'def api(x, **kw): pass\n'),
    ('def api(x, *args, **kw): pass\n', 'def api(x, extra=None, *args, **kw): pass\n'),
])
def test_new_keyword_collisions_with_existing_kwargs_fail(api, before, after):
    # Calls api(1, x=2) / api(1, 2, extra=3) worked before and now collide.
    result = api.check_api(source(before), source(after))
    assert result.status == 'FAIL' and 'API_SIGNATURE_INCOMPATIBLE' in result.reasons
    assert_signature(result, True)


@pytest.mark.parametrize('parse_error', [False, True], ids=['unknown-over-fail', 'error-over-unknown'])
def test_status_priority_preserves_unknown_or_error_in_mixed_scope(api, parse_error):
    before = {'known.py': b'def api(x): pass\n', 'unknown.py': b'def exported(): pass\n'}
    after = {'known.py': b'def api(x, y): pass\n',
             'unknown.py': b'__all__ = discover_exports()\ndef exported(): pass\n'}
    if parse_error:
        before['broken.py'] = b'def broken(:\n'
        after['broken.py'] = b'def broken(): pass\n'
    analysis = api.check_api(before, after)
    assert analysis.status == ('ERROR' if parse_error else 'NOT_RUN')
    assert 'API_DYNAMIC_EXPORTS' in analysis.reasons
    if parse_error:
        assert 'API_PARSE_ERROR' in analysis.reasons
    assert_signature(analysis, None)


@pytest.mark.parametrize('invalid', [
    None,
    [('api.py', b'def api(): pass\n')],
    {42: b'def api(): pass\n'},
    {'api.py': 'def api(): pass\n'},
    {'api.py': bytearray(b'def api(): pass\n')},
    {'../api.py': b'def api(): pass\n'},
    {'/api.py': b'def api(): pass\n'},
    {'package\\api.py': b'def api(): pass\n'},
], ids=['none', 'sequence', 'non-string-path', 'text-content', 'mutable-content',
        'traversal', 'absolute', 'windows-separator'])
def test_invalid_snapshot_arguments_raise_value_error_on_either_side(api, invalid):
    valid = source('def api(): pass\n')
    with pytest.raises(ValueError):
        api.check_api(invalid, valid)
    with pytest.raises(ValueError):
        api.check_api(valid, invalid)


def test_file_addition_and_removal_are_supported(api):
    added = api.check_api({}, {'new.py': b'def added(x): pass\n'})
    removed = api.check_api({'old.py': b'def removed(x): pass\n'}, {})
    assert added.status == 'PASS'
    assert_signature(added, True)
    assert removed.status == 'FAIL'
    assert 'API_SYMBOL_REMOVED' in removed.reasons
    assert_signature(removed, True)
    assert all(change['path'] == 'old.py' for change in removed.details['changes'])


def test_callers_are_detached_diagnostics_and_do_not_gate_breakage(api):
    before, after = source('def api(x): pass\n'), source('def api(x, y): pass\n')
    absent = api.check_api(before, after)
    empty = api.check_api(before, after, callers_in_repo={})
    callers = {'package.api.api': ['consumer.py:3']}
    present = api.check_api(before, after, callers_in_repo=callers)
    assert absent.details['callers_in_repo']['available'] is False
    assert empty.details['callers_in_repo']['available'] is True
    assert present.details['callers_in_repo']['available'] is True
    assert {analysis.status for analysis in (absent, empty, present)} == {'FAIL'}
    assert all('API_SIGNATURE_INCOMPATIBLE' in analysis.reasons
               for analysis in (absent, empty, present))
    diagnostic = copy.deepcopy(present.details['callers_in_repo'])
    callers['package.api.api'].append('later.py:10')
    callers['new-symbol'] = ['new.py:1']
    assert present.details['callers_in_repo'] == diagnostic


def test_evidence_is_deterministic_bound_to_raw_bytes_and_does_not_mutate_inputs(api):
    before = {'z.py': b'def z(x): return x\r\n', 'a.py': b'def a(): pass\n'}
    after = {'a.py': b'def a(option=None): pass\n', 'z.py': b'def z(x): return x + 1\r\n'}
    original = copy.deepcopy((before, after))
    first = api.check_api(MappingProxyType(before), MappingProxyType(after))
    second = api.check_api(dict(reversed(list(before.items()))),
                           dict(reversed(list(after.items()))))
    assert first.status == second.status == 'PASS'
    assert first.reasons == second.reasons
    assert first.details == second.details
    assert (before, after) == original
    expected = {
        'baseline': {path: 'sha256:' + hashlib.sha256(raw).hexdigest()
                     for path, raw in before.items()},
        'candidate': {path: 'sha256:' + hashlib.sha256(raw).hexdigest()
                      for path, raw in after.items()},
    }
    assert first.details['source_hashes'] == expected
    assert_evidence(first)


def test_crlf_and_unicode_identifiers_are_parsed_as_source(api):
    before = {'gói/api.py': 'def chào(tên):\r\n    return tên\r\n'.encode('utf-8')}
    after = {'gói/api.py': 'def chào(tên, lời="xin chào"):\r\n    return tên\r\n'.encode('utf-8')}
    analysis = api.check_api(before, after)
    assert analysis.status == 'PASS'
    assert_signature(analysis, True)
    assert_evidence(analysis)


def test_target_top_level_open_raise_import_and_defaults_are_never_executed(api, tmp_path):
    marker = tmp_path / 'target-was-executed.txt'
    target = (
        f'open({str(marker)!r}, "w").write("executed")\n'
        'raise RuntimeError("target must never execute")\n'
        'import definitely_nonexistent_target_dependency as _dependency\n'
        'def api(value=explode()): return value\n'
    )
    analysis = api.check_api(source(target), source(target))
    assert analysis.status == 'PASS'
    assert_signature(analysis, False)
    assert not marker.exists()


@pytest.mark.parametrize(('before', 'after', 'expected'), [
    ('def api(x): pass\n', 'def api(x): return x\n', False),
    ('def api(x): pass\n', 'def api(x, option=None): pass\n', True),
    ('def api(x): pass\n', 'def api(x, required): pass\n', True),
    ('def api(x): pass\n', '__all__ = discover_exports()\ndef api(x): pass\n', None),
], ids=['unchanged-signature', 'compatible-signature-change', 'breaking-change', 'unknown'])
def test_risk_enrichment_replaces_only_signature_feature_in_a_validated_detached_copy(
        api, report, before, after, expected):
    analysis = api.check_api(source(before), source(after))
    report_before = report.model_dump(mode='json')
    analysis_before = copy.deepcopy(analysis.details)
    enriched = api.with_api_risk(report, analysis)
    assert isinstance(enriched, ImpactReport) and enriched is not report
    assert ImpactReport.model_validate(enriched.model_dump()) == enriched
    original_payload = dict(report_before)
    enriched_payload = enriched.model_dump(mode='json')
    original_payload.pop('risk')
    enriched_payload.pop('risk')
    assert enriched_payload == original_payload
    original_features = {item.name: item.model_dump() for item in report.risk.features
                         if item.name != 'signature_changed'}
    features = {item.name: item.model_dump() for item in enriched.risk.features}
    assert {key: value for key, value in features.items() if key != 'signature_changed'} == original_features
    signature = features['signature_changed']
    assert signature['available'] is (expected is not None)
    assert signature['value'] is expected
    if expected is None:
        assert signature['reason'] == 'NOT_COMPUTED'
        assert 'API_DYNAMIC_EXPORTS' in analysis.reasons
    assert len([item for item in enriched.risk.features if item.name == 'signature_changed']) == 1
    assert report.model_dump(mode='json') == report_before
    assert analysis.details == analysis_before
    # Verify deep detachment across existing nested payload and feature objects.
    enriched.limits.unsupported_operations.clear()
    next(item for item in enriched.risk.features if item.name == 'fan_out').value = 99
    assert report.model_dump(mode='json') == report_before
    assert analysis.details == analysis_before


def test_risk_enrichment_creates_missing_feature_and_validates_computed_status(api, report):
    payload = report.model_dump()
    payload['risk'] = {'status': 'NOT_COMPUTED', 'features': []}
    uncomputed = ImpactReport.model_validate(payload)
    analysis = api.check_api(source('def api(): pass\n'), source('def api(): return 1\n'))
    enriched = api.with_api_risk(uncomputed, analysis)
    assert enriched.risk.status == 'COMPLETE'
    assert len(enriched.risk.features) == 1
    feature = enriched.risk.features[0]
    assert feature.name == 'signature_changed' and feature.available is True and feature.value is False
    assert ImpactReport.model_validate(enriched.model_dump()) == enriched
    assert uncomputed.risk.status == 'NOT_COMPUTED' and uncomputed.risk.features == []
