"""Verification job only: no launches, no product-code changes, no record rewriting."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.b_experiment import BExperimentStore, runtime_fingerprint
from vgar_m2_w78.campaign import assess_record, verify_frozen_files
from vgar_m2_w78.config import load_config
from vgar_m2_w78.contracts import RepairTask
from vgar_m2_w78.evidence import atomic_json, begin_run, digest
from vgar_m2_w78.patch import PatchPolicy, parse_unified_diff, _bind
from vgar_m2_w78.pipeline import require_trusted_fixture

FINAL = ROOT/'results/final_acceptance/2026-10-15-v11-r002'
CASE_IDS = dict(A='single_file_login', B='multi_file_invoice', C='missing_links')


def preflight():
    verify_reference()
    prior = BExperimentStore.open(ROOT/'results/b_repair/2026-10-15-evidence-driven-b')
    runtime = prior.revision('runtimes', 'r002')
    assert runtime_fingerprint(ROOT) == runtime['files'], 'Core runtime differs from r002'
    proof = json.loads(Path(runtime['test_record']).read_text(encoding='utf-8'))
    assert proof['status'] == 'PASS' and proof['complete']
    assert proof['runtime_before'] == proof['runtime_after'] == runtime['files']
    policy, profile = load_config(FINAL/'final_profile.json')
    assert profile.model_dump(mode='json') == prior.frozen['model']
    assert policy.model_dump() == dict(prior.frozen['policy'], prompt_version='m2-w78-v11')
    assert digest((ROOT/'prompts/repair_v11.txt').read_bytes()) == prior.revision('prompts','m2-w78-v11')['template_hash']
    files = dict(prior.frozen['files'], **runtime['files'])
    for path in (FINAL/'final_profile.json', Path(__file__)):
        files[str(path.resolve())] = digest(path.read_bytes())
    snapshot = dict(files=files, runtime_files=runtime['files'], model=profile.model_dump(mode='json'),
        policy=policy.model_dump(), template_hash=prior.revision('prompts','m2-w78-v11')['template_hash'],
        scope='Final A/B/C, same core r002/template V11; no feedback or new production code')
    path = FINAL/'frozen_final.json'
    if path.exists():
        assert json.loads(path.read_text(encoding='utf-8')) == snapshot, 'Frozen final input changed'
    else:
        atomic_json(path, snapshot)
    verify_frozen_files(snapshot)
    return snapshot


def signatures(data):
    return {n.name: (type(n).__name__, ast.dump(n.args), ast.dump(n.returns) if n.returns else None)
            for n in ast.parse(data).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def audit_case(letter, frozen):
    paths = list((FINAL/letter).glob('*/run_record.json'))
    assert len(paths) == 1, f'{letter}: expected exactly one fresh canonical record'
    path = paths[0]
    record = json.loads(path.read_text(encoding='utf-8'))
    assessment = assess_record(path)
    assert assessment['status'] == 'PASS' and not assessment['gate_errors'], assessment
    assert record['task_id'] == CASE_IDS[letter]
    assert record['policy'] == frozen['policy'] and record['model'] == frozen['model']
    assert record.get('prompt_feedback') is None
    stages = record['stages']
    prompt, generation = stages['prompt'], stages['generation']
    assert prompt['template_hash'] == frozen['template_hash'] and prompt['version'] == 'm2-w78-v11'
    assert prompt.get('metadata', {}).get('feedback') is None
    assert digest((path.parent/'prompt.txt').read_bytes()) == prompt['prompt_hash']
    assert generation['input_sha256'] == prompt['prompt_hash'].removeprefix('sha256:')
    raw = (path.parent/record['artifacts']['raw_output']).read_bytes()
    assert raw == (path.parent/record['artifacts']['candidate']).read_bytes()
    assert raw.decode('utf-8') == generation['raw_text']
    diag = generation['generation_diagnostics']
    assert diag['status'] == 'PASS' and diag['effective_observed'] is True
    assert diag['effective_generation_config']['do_sample'] is False
    assert diag['effective_generation_config']['max_new_tokens'] == 1536
    assert generation['input_tokens'] == prompt['input_tokens'] <= 6000
    assert diag['attention_mask']['shape'] == [1, generation['input_tokens']]
    assert diag['attention_mask']['binary'] is True and diag['attention_mask']['zeros'] == 0
    assert generation['device_map'] and stages['cleanup']['status'] == 'PASS'
    for name, expected in frozen['runtime_files'].items():
        assert record['source_fingerprint'][Path(name).relative_to(ROOT).as_posix()] == expected
    task = RepairTask.model_validate(record['task'])
    require_trusted_fixture(task)
    expected_task = json.loads((ROOT/'examples/tasks'/f'{task.task_id}.json').read_text(encoding='utf-8'))
    for key in ('source_repo','bundle_directory'):
        expected_task[key] = str((ROOT/'examples/tasks'/expected_task[key]).resolve())
    assert RepairTask.model_validate(expected_task).model_dump(mode='json') == record['task']
    required = stages['baseline']['required_ids']
    assert len(required) == (2 if letter == 'B' else 1)
    assert all(stages['baseline']['tests']['outcomes'][n] == 'FAIL' for n in required)
    parsed = parse_unified_diff(raw.decode('utf-8'), PatchPolicy(task.allowed_source_paths, task.protected_paths))
    changed, _ = _bind(parsed, task.source_repo)
    assert all(signatures((task.source_repo/name).read_bytes()) == signatures(data) for name,data in changed.items())
    return dict(**assessment, task_id=task.task_id, prompt_version='m2-w78-v11', runtime_revision='r002',
        feedback=None, input_tokens=generation['input_tokens'], output_tokens=generation['output_tokens'],
        duration_ms=record['duration_ms'], generation_ms=generation['duration_ms'],
        changed_files=stages['apply']['changed_files'], original_source_unchanged=record['original_source_unchanged'])


run = begin_run(FINAL/'audits', 'final-v11-r002-audit', mode='offline')
try:
    frozen = preflight()
    run.stage('preflight', dict(status='PASS', protected_files=len(frozen['files']), runtime_revision='r002'))
    selected = sys.argv[1:]
    if selected == ['preflight']:
        run.finish('PASS', scope='Preflight only, no real repair acceptance')
    else:
        letters = selected or list(CASE_IDS)
        for letter in letters:
            assert letter in CASE_IDS
            run.stage(letter, audit_case(letter, frozen))
        verify_frozen_files(frozen)
        run.finish('PASS', scope='3/3 final acceptance' if letters == list(CASE_IDS) else 'Partial case audit')
except BaseException as error:
    from vgar_m2_w78.diagnostics import exception_details
    run.finish('ERROR', **exception_details(error))
    print(run.path, flush=True)
    raise
print(run.path, flush=True)
