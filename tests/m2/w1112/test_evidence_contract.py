"""C1 evidence payloads: modern checks and normalization of W7-W10 placeholders."""
from __future__ import annotations

import copy
import importlib

import pytest


@pytest.fixture
def evidence():
    module = importlib.import_module('vgar.contracts.evidence')
    assert hasattr(module, 'AnalysisCheckResult'), 'C1 analysis-check DTO is missing'
    return module


def test_analysis_check_roundtrip_preserves_detailed_reasons_and_ref(evidence):
    payload = {'status': 'FAIL', 'reasons': ['API_SYMBOL_REMOVED', 'API_SIGNATURE_INCOMPATIBLE'],
               'details_ref': 'checks/api.json'}
    dto = evidence.AnalysisCheckResult.model_validate(payload)
    assert dto.model_dump(mode='json') == payload
    assert evidence.AnalysisCheckResult.model_validate_json(dto.model_dump_json()) == dto


@pytest.mark.parametrize('status', ['PASS', 'FAIL', 'NOT_RUN', 'ERROR'])
def test_analysis_check_status_remains_distinct(evidence, status):
    assert evidence.AnalysisCheckResult(status=status).status == status


@pytest.mark.parametrize('legacy,expected', [
    ({}, {'status': 'NOT_RUN', 'reasons': [], 'details_ref': None}),
    ({'status': 'NOT_RUN', 'reason': None},
     {'status': 'NOT_RUN', 'reasons': [], 'details_ref': None}),
    ({'status': 'FAIL', 'reason': {'code': 'API_BREAK', 'message': 'legacy placeholder'}},
     {'status': 'FAIL', 'reasons': ['API_BREAK'], 'details_ref': None}),
    ({'status': 'ERROR', 'reason': {'code': 'VERIFICATION_INCOMPLETE', 'message': 'legacy'}},
     {'status': 'ERROR', 'reasons': ['VERIFICATION_INCOMPLETE'], 'details_ref': None}),
])
def test_legacy_placeholder_normalizes_without_mutating_input(evidence, legacy, expected):
    original = copy.deepcopy(legacy)
    assert evidence.AnalysisCheckResult.model_validate(legacy).model_dump(mode='json') == expected
    assert legacy == original


def test_legacy_check_model_can_be_read_as_analysis_check(evidence):
    old = evidence.CheckResult(status='FAIL', reason={'code': 'STRUCTURAL_VIOLATION', 'message': 'old'})
    assert evidence.AnalysisCheckResult.model_validate(old).model_dump(mode='json') == {
        'status': 'FAIL', 'reasons': ['STRUCTURAL_VIOLATION'], 'details_ref': None}


@pytest.mark.parametrize('payload', [
    {'status': 'UNAVAILABLE'}, {'status': 'COMPLETE'}, {'status': True},
    {'reasons': ['']}, {'reasons': ['api_break']}, {'reasons': ['API BREAK']},
    {'reasons': ['API-BREAK']}, {'reasons': [' API_BREAK']}, {'reasons': [2]},
    {'reasons': 'API_BREAK'}, {'reasons': None}, {'unexpected': 'value'},
    {'reason': 'API_BREAK'}, {'reason': {'code': 'API_BREAK'}},
    {'reason': {'code': 'MADE_UP_LEGACY_CODE', 'message': 'old'}},
    {'reason': {'code': 'API_BREAK', 'message': 'old'}, 'reasons': ['API_SYMBOL_REMOVED']},
])
def test_malformed_analysis_payload_is_rejected(evidence, payload):
    with pytest.raises(ValueError):
        evidence.AnalysisCheckResult.model_validate(payload)


@pytest.mark.parametrize('ref', ['', ' ', '/tmp/api.json', 'C:/api.json', '../api.json',
                                  'checks/../api.json', './api.json', 'checks//api.json',
                                  'checks\\api.json', 'https://example/api.json',
                                  'file:api.json', 'checks/./api.json', 'api.json\x00'])
def test_details_ref_cannot_escape_artifact_root(evidence, ref):
    with pytest.raises(ValueError):
        evidence.AnalysisCheckResult(status='ERROR', details_ref=ref)


def test_verification_reads_legacy_checks_and_serializes_c1(evidence):
    payload = {
        'tests': {'status': 'NOT_RUN', 'command': '', 'argv': [], 'exit_code': None,
                  'duration_ms': 0, 'stdout': '', 'stderr': ''},
        'api_check': {'status': 'NOT_RUN', 'reason': None},
        'structural_check': {'status': 'FAIL', 'reason': {
            'code': 'STRUCTURAL_VIOLATION', 'message': 'placeholder'}},
        'typecheck': {'status': 'FAIL', 'reason': {'code': 'TYPECHECK_FAILED', 'message': 'unchanged'}},
    }
    dto = evidence.VerificationResult.model_validate(payload)
    serialized = dto.model_dump(mode='json')
    assert serialized['api_check'] == {'status': 'NOT_RUN', 'reasons': [], 'details_ref': None}
    assert serialized['structural_check'] == {
        'status': 'FAIL', 'reasons': ['STRUCTURAL_VIOLATION'], 'details_ref': None}
    assert serialized['typecheck'] == payload['typecheck']
    assert serialized['lint'] == {'status': 'NOT_RUN', 'reason': None}
    assert evidence.VerificationResult.model_validate_json(dto.model_dump_json()) == dto


def test_analysis_defaults_do_not_share_mutable_reason_lists(evidence):
    first, second = evidence.AnalysisCheckResult(), evidence.AnalysisCheckResult()
    first.reasons.append('NOT_COMPUTED')
    assert second.reasons == []
