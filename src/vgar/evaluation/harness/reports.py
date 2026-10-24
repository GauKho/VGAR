"""Read the upstream 4.1.0 report shape, not a replacement grading algorithm."""
import json
from pathlib import Path

from vgar.evaluation.retrieval.evidence import sha256


def read_report(directory: Path, instance_id: str, expected_patch: str) -> dict:
    names = ('report.json', 'patch.diff', 'test_output.txt', 'run_instance.log')
    for name in names[1:]:
        if not (directory/name).is_file() or (directory/name).is_symlink():
            raise FileNotFoundError(f'Missing/untrusted harness artifact: {name}')
    if (directory/'patch.diff').read_bytes() != expected_patch.encode('utf-8'):
        raise ValueError('Harness patch artifact differs from expected gold bytes')
    if not (directory/'report.json').exists():
        output = (directory/'test_output.txt').read_text(encoding='utf-8')
        log = (directory/'run_instance.log').read_text(encoding='utf-8')
        # Pinned run_evaluation catches this EvaluationError and can exit0 without report.json.
        if output.rstrip().endswith('Timeout error: 1800 seconds exceeded.') and (
                'EvaluationError' in log and 'Test timed out after 1800 seconds.' in log):
            return {'status': 'TIMEOUT', 'resolved': None, 'reason': 'OFFICIAL_TEST_TIMEOUT',
                    'raw_report': None, 'artifacts': {n: sha256((directory/n).read_bytes()) for n in names[1:]}}
        raise FileNotFoundError('Official report.json missing without confirmed timeout evidence')
    if (directory/'report.json').is_symlink():
        raise ValueError('Untrusted symlink report artifact')
    raw = json.loads((directory/'report.json').read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or set(raw) != {instance_id} or not isinstance(raw[instance_id], dict):
        raise ValueError('Harness report identity/shape mismatch')
    data = raw[instance_id]
    flags = ('patch_is_None', 'patch_exists', 'patch_successfully_applied', 'resolved')
    if any(type(data.get(k)) is not bool for k in flags):
        raise ValueError('Harness report flags must be strict booleans')
    if data['patch_is_None'] or not data['patch_exists'] or not data['patch_successfully_applied']:
        raise ValueError('Harness patch was not applied; this is not ordinary unresolved grading')
    return {'status': 'RESOLVED' if data['resolved'] else 'UNRESOLVED',
            'resolved': data['resolved'], 'raw_report': str(directory/'report.json'),
            'artifacts': {name: sha256((directory/name).read_bytes()) for name in names}}
