"""Additive B evidence audit; never weakens or replaces existing assessment."""
import ast
import json
from pathlib import Path

from .evidence import digest


def audit_b_pass(path, frozen, entry):
    path = Path(path)
    record = json.loads(path.read_text(encoding='utf-8'))
    errors = []
    stages = record.get('stages', {})
    generation = stages.get('generation', {})
    diagnostic = generation.get('generation_diagnostics') or {}
    effective = diagnostic.get('effective_generation_config') or {}
    mask = diagnostic.get('attention_mask') or {}
    tokens = generation.get('input_tokens')
    if (diagnostic.get('effective_observed') is not True or diagnostic.get('status') != 'PASS'
            or effective.get('do_sample') is not False or effective.get('max_new_tokens') != 1536
            or mask.get('shape') != [1, tokens] or mask.get('binary') is not True
            or mask.get('zeros') != 0 or not generation.get('device_map')
            or not isinstance(tokens, int) or not 0 < tokens <= 6000):
        errors.append('REAL_GENERATION_DIAGNOSTICS')
    if stages.get('cleanup', {}).get('status') != 'PASS':
        errors.append('CLEANUP_INCOMPLETE')
    expected_policy = dict(frozen.get('policy', {}), prompt_version=entry.get('version'))
    if 'timeout_seconds' in entry:
        expected_policy['global_timeout'] = entry['timeout_seconds']
    if record.get('model') != frozen.get('model') or record.get('policy') != expected_policy:
        errors.append('FROZEN_MODEL_OR_POLICY_MISMATCH')
    if record.get('task') != frozen.get('task'):
        errors.append('FROZEN_TASK_MISMATCH')
    if (record.get('runtime_revision') != entry.get('runtime_revision')
            or record.get('runtime_manifest_sha256') != entry.get('runtime_manifest_sha256')
            or record.get('request_identity') != entry.get('request_identity')):
        errors.append('RUNTIME_OR_REQUEST_BINDING')
    root = Path(frozen['runtime_root'])
    for name, expected in entry.get('runtime_files', {}).items():
        relative = Path(name).relative_to(root).as_posix()
        if record.get('source_fingerprint', {}).get(relative) != expected:
            errors.append('RUNTIME_START_FINGERPRINT')
            break
    required = stages.get('baseline', {}).get('required_ids', [])
    baseline = stages.get('baseline', {}).get('tests', {}).get('outcomes', {})
    if len(required) != 2 or any(baseline.get(n) != 'FAIL' for n in required):
        errors.append('BOTH_REQUIRED_BASELINE_FAILURES')
    try:
        prompt = stages['prompt']
        if (digest((path.parent/'prompt.txt').read_bytes()) != prompt['prompt_hash']
                or prompt['prompt_hash'] != entry['prompt_hash']
                or prompt['template_hash'] != entry['template_hash']
                or generation['input_sha256'] != prompt['prompt_hash'].removeprefix('sha256:')
                or generation['raw_text'] != (path.parent/record['artifacts']['raw_output']).read_bytes().decode('utf-8')):
            errors.append('PROMPT_OR_RAW_BINDING')
        from .patch import PatchPolicy, parse_unified_diff, _bind
        task = frozen['task']
        parsed = parse_unified_diff(generation['raw_text'], PatchPolicy(tuple(task['allowed_source_paths']), tuple(task['protected_paths'])))
        predicted, _ = _bind(parsed, Path(task['source_repo']))
        def signatures(source):
            tree = ast.parse(source)
            return {n.name: (type(n).__name__, ast.dump(n.args), ast.dump(n.returns) if n.returns else None)
                    for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name, changed in predicted.items():
            if signatures((Path(task['source_repo'])/name).read_bytes()) != signatures(changed):
                errors.append('PUBLIC_SIGNATURE_CHANGED')
    except (OSError, KeyError, TypeError, ValueError, SyntaxError):
        errors.append('B_ARTIFACT_AUDIT_INCOMPLETE')
    return errors
