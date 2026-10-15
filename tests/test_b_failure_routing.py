"""Real attempt-01 showed command metadata must not masquerade as timeout."""
from test_bootstrap import api


def test_parse_failure_with_command_timeout_metadata_is_candidate():
    record = dict(status='FAIL', reason='PATCH_PARSE_ERROR', error_detail={
        'type':'ValueError','message':'Expected file headers; extra text/operations are not allowed'},
        stages={'baseline':{'command':{'timeout_seconds':120,'timed_out':False}}})
    assert api('b_experiment').diagnose(record)['category'] == 'candidate'


def test_worker_prompt_hash_mismatch_keeps_integrity_precedence():
    record = dict(status='ERROR', reason='GENERATION_ERROR', stages={
        'generation':{'error_detail':{'message':'input hash mismatch'}}})
    assert api('b_experiment').diagnose(record)['category'] == 'integrity'
