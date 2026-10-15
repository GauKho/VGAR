"""Bound a host-chosen worker and validate its durable response."""
import json
from pathlib import Path

from .executor import run_bounded


def invoke_worker(command, cwd, response_path: Path, timeout_seconds):
    if response_path.exists():
        return dict(status='ERROR', reason='Worker response path already exists')
    evidence = run_bounded(tuple(command), cwd, timeout_seconds)
    result = dict(status='ERROR', command=evidence, reason='Worker failed or response missing')
    if evidence['status'] != 'PASS' or not response_path.is_file():
        return result
    try:
        response = json.loads(response_path.read_text(encoding='utf-8'))
        if response.get('status') != 'PASS' or response.get('kind') not in ('tokenize', 'generate'):
            raise ValueError('Unsuccessful/malformed worker response')
        required = ('rendered', 'input_ids') if response['kind'] == 'tokenize' else ('raw_text', 'input_tokens', 'output_tokens', 'truncated', 'finish_reason')
        if any(key not in response for key in required):
            raise ValueError('Incomplete worker response')
        return dict(status='PASS', command=evidence, response=response)
    except (ValueError, OSError) as error:
        result['reason'] = str(error)
        return result

