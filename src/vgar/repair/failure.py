"""Structured terminal failure {stage, code, cause, evidence_ref}, derived only from the run record."""

CAUSE_LIMIT = 500


def _cause(record, stage):
    detail = record.get('error_detail') or {}
    entry = record.get('stages', {}).get(stage) or {}
    error = entry.get('error') if isinstance(entry.get('error'), dict) else {}
    for value in (detail.get('message'), error.get('message'), entry.get('reason'),
                  ', '.join(entry.get('reasons') or []) or None):
        if value:
            return str(value)[:CAUSE_LIMIT]
    return None


def _stage(record):
    from vgar.repair.session import STAGES  # lazy: session imports this module
    detail = record.get('error_detail') or {}
    if detail.get('stage'):
        return detail['stage']
    if record.get('reason') == 'FINALIZATION_ERROR' or record.get('integrity_error'):
        return 'finalization'
    stages = record.get('stages', {})
    statuses = [(name, (stages.get(name) or {}).get('status', 'NOT_RUN')) for name in STAGES]
    failed = [name for name, status in statuses if status in ('FAIL', 'ERROR')]
    if failed:
        return failed[0]
    reached = [name for name, status in statuses if status != 'NOT_RUN']
    return reached[-1] if reached else STAGES[0]


def failure_of(record):
    """None for PASS; otherwise where the run stopped, its outcome code and a bounded cause."""
    if record.get('status') == 'PASS':
        return None
    stage = _stage(record)
    return {'stage': stage, 'code': record.get('reason') or 'INTERNAL_ERROR', 'cause': _cause(record, stage),
            'evidence_ref': 'run_record.json#stages/' + stage}
