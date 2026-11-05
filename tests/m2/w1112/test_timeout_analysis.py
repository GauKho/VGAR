"""D15 synthetic batch exports: never model or campaign measurements."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts/analyze_repair_timeouts.py'


def tool():
    assert SCRIPT.is_file(), 'D15 standalone analyzer is not implemented'
    spec = importlib.util.spec_from_file_location('d15', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def population():
    return [json.loads((ROOT / f'configs/m3/w10_dev_stage{i}.json').read_text(
        encoding='utf-8'))['source']['task_ids'] for i in (1, 2)]


def export(tmp, *, stage=1, cohort='w10', exp_id=None):
    tasks = population()[stage - 1] if cohort == 'w10' else sum(population(), [])
    variants = ('A0', 'A1', 'A2') if cohort == 'w10' else ('A3',)
    exp_id = exp_id or f'synthetic-{cohort}-{stage}'
    root = tmp / exp_id
    put(root / 'experiment.json', {
        'schema': 'vgar-m3-experiment-v1', 'experiment_id': exp_id,
        'generation': 'fake', 'source': {'type': 'fixture', 'task_ids': tasks},
        'variants': [{'path': f'../policies/{v}.json',
                      'arm': 'bm25' if v == 'A0' else 'graph'} for v in variants],
    })
    for task in tasks:
        for variant in variants:
            attempt(root, task, variant)
    return root


def attempt(root, task, variant, n=1, *, state='TERMINAL', reason=None, parent=None):
    arm = 'bm25' if variant == 'A0' else 'graph'
    run_id = f'run-{n}'
    rel = f'engine/{task}__{variant}/attempt-{n}/{run_id}'
    entry = {
        'experiment_id': root.name, 'task_id': task, 'variant_id': variant,
        'arm': arm, 'attempt': n, 'parent_attempt': parent, 'state': state,
        'status': 'FAIL' if reason else 'PASS', 'reason': reason,
        'source': 'engine', 'engine_run_dir': f'/home/m3/results/{root.name}/{rel}',
        'engine_complete': state == 'TERMINAL', 'wall_ms': 10000,
    }
    ledger = put(root / f'attempts/{task}__{variant}/attempt-{n}.json', entry)
    record = {
        'kind': 'repair', 'run_id': run_id, 'task_id': task,
        'mode': 'fake', 'status': entry['status'], 'reason': reason,
        'complete': state == 'TERMINAL', 'duration_ms': 10000,
        'experiment': {'variant_id': variant, 'arm': arm},
        'policy': {'prompt_version': 'v11', 'input_cap': 6000,
                   'output_cap': 1536, 'reserved_margin': 256,
                   'generation_timeout': 900, 'global_timeout': 1800,
                   'command_timeout': 120},
        'model': {'model_id': 'synthetic', 'revision': 'pinned',
                  'dtype': 'float16', 'device_map': 'auto'},
        'source_fingerprint': {'src/test.py': 'sha256:synthetic'},
        'stages': {'prompt': {'template_hash': 'sha256:template', 'tokenizer_label': 'synthetic'},
                   'generation': {'status': 'PASS', 'complete': True,
                                  'input_tokens': 100, 'output_tokens': 30,
                                  'generation_ms': 2000, 'model_load_ms': 500,
                                  'duration_ms': 2600, 'truncated': False}},
    }
    rec = put(root / rel / 'run_record.json', record)
    return ledger, rec


def change(path, **fields):
    obj = json.loads(path.read_text(encoding='utf-8'))
    obj.update(fields)
    put(path, obj)


def row(result, task=None, variant='A0', cohort='w10'):
    return next(r for r in result['rows'] if r['cohort'] == cohort
                and r['variant'] == variant and (task is None or r['task_id'] == task))


def digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_no_data_and_full_denominators(tmp_path):
    m = tool()
    result = m.run_analysis(output_root=tmp_path / 'out')
    assert result['summary']['state'] == 'WAITING_DATA'
    assert result['exit_code'] == 2 and len(result['rows']) == 100
    assert result['summary']['expected_slots'] == {'w10': 75, 'w12': 25}
    assert all(r['generation_ms'] is None for r in result['rows'])
    assert result['summary']['recommendation']['selected_seconds'] is None


def test_partial_keeps_exclusions_missing_and_all_tasks(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0')
    change(ledger, reason='TASK_EXCLUDED', source='runner', engine_run_dir=None)
    rec.unlink()
    result = tool().run_analysis(w10=[root], output_root=tmp_path / 'out')
    assert result['summary']['state'] == 'PARTIAL'
    assert len(result['rows']) == 100
    assert row(result, task)['raw_reason'] == 'TASK_EXCLUDED'
    assert row(result, population()[1][0])['selection'] == 'INPUT_MISSING'
    assert row(result, task)['generation_ms'] is None


def test_synthetic_is_never_real_ready_and_outputs_are_deterministic(tmp_path):
    roots = [export(tmp_path, stage=i) for i in (1, 2)]
    a3 = export(tmp_path, cohort='w12')
    before = {str(r): digest(r) for r in [*roots, a3]}
    m = tool()
    result = m.run_analysis(w10=roots, w12=[a3], output_root=tmp_path / 'out1')
    m.run_analysis(w10=roots, w12=[a3], output_root=tmp_path / 'out2')
    assert result['summary']['synthetic'] is True
    assert result['summary']['state'] == 'PARTIAL'
    assert result['summary']['coverage']['w10']['selected'] == 75
    assert result['summary']['coverage']['w12']['selected'] == 25
    assert digest(tmp_path / 'out1') == digest(tmp_path / 'out2')
    assert before == {str(r): digest(r) for r in [*roots, a3]}
    assert 'SYNTHETIC' in (tmp_path / 'out1/report.md').read_text(encoding='utf-8')


def test_ready_only_real_complete_with_bindings(tmp_path):
    roots = [export(tmp_path, stage=i) for i in (1, 2)]
    a3 = export(tmp_path, cohort='w12')
    for root in [*roots, a3]:
        config = json.loads((root / 'experiment.json').read_text())
        config['generation'] = 'real'
        config['source']['type'] = 'swebench'
        put(root / 'experiment.json', config)
        for rec in root.glob('engine/*/*/*/run_record.json'):
            change(rec, mode='real')
    result = tool().run_analysis(w10=roots, w12=[a3], output_root=tmp_path / 'out')
    assert result['summary']['state'] == 'READY_FOR_REVIEW'
    assert result['exit_code'] == 0
    assert result['summary']['recommendation']['selected_seconds'] is None


@pytest.mark.parametrize('state', ['RESERVED', 'INTERRUPTED'])
def test_pending_rerun_does_not_fall_back_to_old_terminal(tmp_path, state):
    root = export(tmp_path)
    task = population()[0][0]
    attempt(root, task, 'A0', 2, state=state, parent=1)
    result = tool().analyze(w10=[root])
    selected = row(result, task)
    assert selected['selection'] == 'RERUN_PENDING'
    assert selected['generation_ms'] is None
    audit = next(a for a in result['selection_audit'] if a['task_id'] == task
                 and a['variant'] == 'A0')
    assert audit['previous_terminal'] == 1


def test_supersession_and_parent_binding(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0', 2, parent=1)
    change(rec, supersedes_run_id='run-1')
    result = tool().analyze(w10=[root])
    assert row(result, task)['attempt'] == 2
    change(rec, supersedes_run_id='run-2')
    assert row(tool().analyze(w10=[root]), task)['selection'] == 'INVALID'


@pytest.mark.parametrize('field,value', [
    ('task_id', 'wrong'), ('experiment', {'variant_id': 'A3', 'arm': 'graph'}),
    ('run_id', 'wrong'), ('kind', 'agent'), ('complete', False),
])
def test_engine_binding_is_checked(tmp_path, field, value):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0')
    change(rec, **{field: value})
    result = tool().analyze(w10=[root])
    assert row(result, task)['selection'] == 'INVALID'
    assert row(result, task)['generation_ms'] is None


@pytest.mark.parametrize('case', ['json', 'missing', 'duplicate', 'parent_cycle'])
def test_malformed_missing_duplicate_and_cycle_kept_in_ledger(tmp_path, case):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0')
    if case == 'json':
        ledger.write_text('{bad', encoding='utf-8')
    elif case == 'missing':
        rec.unlink()
    elif case == 'duplicate':
        put(ledger.with_name('attempt-01.json'), json.loads(ledger.read_text()))
    else:
        change(ledger, parent_attempt=1)
    result = tool().analyze(w10=[root])
    assert row(result, task)['selection'] == 'INVALID'
    assert len(result['rows']) == 100


@pytest.mark.parametrize('case', ['traversal', 'output_inside', 'output_parent', 'existing'])
def test_path_guards(tmp_path, case):
    root = export(tmp_path)
    out = tmp_path / 'out'
    if case == 'traversal':
        ledger, _ = attempt(root, population()[0][0], 'A0')
        change(ledger, engine_run_dir='/home/m3/../escape/run-1')
    elif case == 'output_inside':
        out = root / 'new'
    elif case == 'output_parent':
        out = tmp_path
    else:
        out.mkdir()
    with pytest.raises(ValueError):
        tool().run_analysis(w10=[root], output_root=out)


def test_symlink_or_junction_is_rejected(tmp_path):
    root = export(tmp_path)
    link = tmp_path / 'linked'
    import subprocess
    import os
    if os.name == 'nt':
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(root)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
    else:
        link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match='(?i)link|reparse'):
        tool().analyze(w10=[link])


@pytest.mark.parametrize('case,events,completed', [
    ('post_fail', [], True), ('generation', ['GENERATION_TIMEOUT'], False),
    ('global', ['RUN_TIMEOUT'], True), ('command', ['COMMAND_TIMEOUT'], True),
    ('cap', ['OUTPUT_CAP'], True), ('slow', [], True),
])
def test_timing_censoring_and_explicit_classification(tmp_path, case, events, completed):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0', reason='TEST_FAILED')
    record = json.loads(rec.read_text())
    if case == 'generation':
        record['reason'] = 'GENERATION_TIMEOUT'
        record['stages']['generation'].update(status='ERROR', timed_out=True, complete=False)
    elif case == 'global':
        record['reason'] = 'RUN_TIMEOUT'
    elif case == 'command':
        record['stages']['tests'] = {'commands': [{'argv': ['pytest'], 'timed_out': True}]}
    elif case == 'cap':
        record['stages']['generation']['truncated'] = True
    elif case == 'slow':
        record['stages']['generation']['generation_ms'] = 1000000
    put(rec, record)
    change(ledger, reason=record['reason'])
    r = row(tool().analyze(w10=[root]), task)
    assert r['events'] == events
    assert r['generation_completed'] is completed
    assert r['wall_censored'] is (case == 'global')
    assert r['generation_stage_ms'] == 2600
    assert r['model_load_ms'] == 500


@pytest.mark.parametrize('value', [True, -1, float('nan'), float('inf'), '12', None])
def test_invalid_metrics_are_unknown(tmp_path, value):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0')
    data = json.loads(rec.read_text())
    data['stages']['generation']['input_tokens'] = value
    put(rec, data)
    r = row(tool().analyze(w10=[root]), task)
    assert r['input_tokens'] is None
    assert r['availability']['input_tokens'] != 'MEASURED'


def test_zero_is_measured_and_correlations_handle_ties():
    m = tool()
    assert m.distribution([0, 0, 0]) == {'count': 3, 'min': 0, 'median': 0, 'p95': 0, 'max': 0}
    assert m.correlations([(1, 2), (2, 4)])['pearson'] is None
    assert m.correlations([(1, 2), (1, 3), (1, 4)])['spearman'] is None
    stats = m.correlations([(1, 10), (1, 10), (3, 30), (4, 40)])
    assert stats['spearman'] == pytest.approx(1)
    assert stats['pearson'] == pytest.approx(1)


def test_cohorts_require_binding_and_never_mix_variants(tmp_path):
    roots = [export(tmp_path, stage=i) for i in (1, 2)]
    m = tool()
    result = m.analyze(w10=roots)
    assert len(result['summary']['combined_w10']) == 3
    rec = next(roots[1].glob('engine/*__A0/*/*/run_record.json'))
    change(rec, model={'model_id': 'different'})
    result = m.analyze(w10=roots)
    assert not any(g['variant'] == 'A0' for g in result['summary']['combined_w10'])
    assert result['summary']['warnings']


def test_inventory_detects_input_mutation(tmp_path, monkeypatch):
    root = export(tmp_path)
    m = tool()
    original = m.verify_inputs

    def mutate(inventory):
        path = root / 'experiment.json'
        path.write_bytes(path.read_bytes() + b' ')
        return original(inventory)

    monkeypatch.setattr(m, 'verify_inputs', mutate)
    with pytest.raises(ValueError, match='(?i)changed|drift'):
        m.run_analysis(w10=[root], output_root=tmp_path / 'out')
    assert not (tmp_path / 'out/artifact_hashes.json').exists()


@pytest.mark.parametrize('case', ['status', 'reason', 'shape', 'not_complete'])
def test_terminal_consistency_errors_are_rows_not_crashes(tmp_path, case):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0')
    if case == 'status':
        change(rec, status='FAIL')
    elif case == 'reason':
        change(rec, reason='MODEL_ERROR')
    elif case == 'shape':
        change(rec, reason=['bad'])
    else:
        change(ledger, engine_complete=False)
    assert row(tool().analyze(w10=[root]), task)['selection'] == 'INVALID'


def test_unknown_and_mixed_binding_split_within_experiment(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0')
    obj = json.loads(rec.read_text())
    obj['stages']['prompt']['template_hash'] = 'changed-template'
    put(rec, obj)
    summary = tool().analyze(w10=[root])['summary']
    groups = [g for g in summary['groups'] if g['variant'] == 'A0'
              and g['experiment_id'] == root.name]
    assert len(groups) == 2
    assert summary['warnings']


def test_missing_prompt_binding_cannot_enable_pooling(tmp_path):
    roots = [export(tmp_path, stage=i) for i in (1, 2)]
    rec = next(roots[0].glob('engine/*__A0/*/*/run_record.json'))
    obj = json.loads(rec.read_text())
    obj['stages'].pop('prompt')
    put(rec, obj)
    assert not any(g['variant'] == 'A0' for g in tool().analyze(w10=roots)['summary']['combined_w10'])


def test_duplicate_stage_exports_never_inflate_resolved_denominator(tmp_path):
    first = export(tmp_path)
    second = export(tmp_path, exp_id='synthetic-copy')
    result = tool().analyze(w10=[first, second])
    assert result['summary']['coverage']['w10']['unique_resolved'] == 33
    assert any('overlap' in s.lower() for s in result['summary']['issues'])


def test_model_error_and_runner_infrastructure_keep_evidence(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0', reason='INTERNAL_ERROR')
    obj = json.loads(rec.read_text())
    obj['stages']['generation'].update(status='ERROR', complete=False)
    put(rec, obj)
    result = tool().analyze(w10=[root])
    assert 'MODEL_ERROR' in row(result, task)['events']
    change(ledger, source='runner', engine_run_dir=None, reason='RUNNER_INFRA_ERROR')
    result = tool().analyze(w10=[root])
    assert 'INFRASTRUCTURE_ERROR' in row(result, task)['events']
    assert row(result, task)['evidence_refs']


def test_numeric_zero_is_measured_not_unknown(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0')
    obj = json.loads(rec.read_text())
    obj['stages']['generation'].update(input_tokens=0, generation_ms=0, model_load_ms=0)
    put(rec, obj)
    r = row(tool().analyze(w10=[root]), task)
    assert r['input_tokens'] == 0 and r['generation_ms'] == 0
    assert r['availability']['input_tokens'] == 'MEASURED'


def test_cli_missing_data_is_exit_two_and_stdlib_only(tmp_path):
    import ast
    import subprocess
    import sys
    assert SCRIPT.exists()
    tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name.split('.')[0] in sys.stdlib_module_names for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module != '__future__':
            assert node.module.split('.')[0] in sys.stdlib_module_names
    proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--output-root', str(tmp_path / 'out')],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and 'WAITING_DATA' in proc.stdout


def test_interrupted_engine_output_root_can_bind_resumed_supersession(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, _ = attempt(root, task, 'A0', state='INTERRUPTED')
    change(ledger, engine_run_dir=None,
           engine_output_root=f'/home/m3/{root.name}/engine/{task}__A0/attempt-1')
    _, resumed = attempt(root, task, 'A0', 2, parent=1)
    change(resumed, supersedes_run_id='run-1')
    result = tool().analyze(w10=[root])
    assert row(result, task)['selection'] == 'SELECTED'
    assert row(result, task)['run_id'] == 'run-2'
    audit = next(a for a in result['selection_audit'] if a['task_id'] == task and a['variant'] == 'A0')
    assert audit['attempts'][0]['run_id'] == 'run-1'


@pytest.mark.parametrize('case', ['fallback', 'conflict'])
def test_prompt_tokens_on_generation_timeout_are_measured_with_provenance(tmp_path, case):
    root = export(tmp_path)
    task = population()[0][0]
    ledger, rec = attempt(root, task, 'A0', reason='GENERATION_TIMEOUT')
    obj = json.loads(rec.read_text())
    obj['stages']['prompt']['input_tokens'] = 6000
    obj['stages']['generation'] = {'status': 'ERROR', 'complete': True, 'timed_out': True}
    if case == 'conflict':
        obj['stages']['generation']['input_tokens'] = 100
    put(rec, obj)
    r = row(tool().analyze(w10=[root]), task)
    if case == 'fallback':
        assert r['input_tokens'] == 6000
        assert r['availability']['input_tokens'] == 'MEASURED'
        assert r['metric_refs']['input_tokens'].endswith('#/stages/prompt/input_tokens')
    else:
        assert r['input_tokens'] is None
        assert r['availability']['input_tokens'] == 'CONFLICT'
        assert r['issues']
    assert 'COMMAND_TIMEOUT' not in r['events']
    assert r['generation_completed'] is False


@pytest.mark.parametrize('case', ['invalid_number', 'unbound'])
def test_invalid_or_unbound_real_labeled_data_never_ready(tmp_path, case):
    roots = [export(tmp_path, stage=i) for i in (1, 2)]
    a3 = export(tmp_path, cohort='w12')
    for root in [*roots, a3]:
        cfg = json.loads((root / 'experiment.json').read_text())
        cfg['generation'] = 'real'
        cfg['source']['type'] = 'swebench'
        put(root / 'experiment.json', cfg)
        for rec in root.glob('engine/*/*/*/run_record.json'):
            change(rec, mode='real')
    rec = next(a3.glob('engine/*/*/*/run_record.json'))
    obj = json.loads(rec.read_text())
    if case == 'unbound':
        obj.pop('source_fingerprint')
    else:
        obj['stages']['generation'].update(input_tokens=True, generation_ms=-1)
    put(rec, obj)
    result = tool().analyze(w10=roots, w12=[a3])
    assert result['summary']['state'] == 'PARTIAL'
    assert result['exit_code'] == 2
    assert result['summary']['data_quality_issues']


def test_finite_large_measurements_produce_finite_statistics():
    assert tool().distribution([1e308, 1e308])['median'] == 1e308


def test_malformed_failure_stays_in_denominator_without_breaking_output(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    _, rec = attempt(root, task, 'A0')
    change(rec, failure={'code': None, 'cause': float('nan')})
    result = tool().run_analysis(w10=[root], output_root=tmp_path / 'out')
    assert row(result, task)['selection'] == 'INVALID'
    assert row(result, task)['issues']
    assert len(result['rows']) == 100
    assert (tmp_path / 'out/artifact_hashes.json').is_file()


def test_runner_terminal_ref_is_selected_numerically_not_lexically(tmp_path):
    root = export(tmp_path)
    task = population()[0][0]
    for n in range(2, 11):
        ledger, _ = attempt(root, task, 'A0', n, reason='TASK_EXCLUDED', parent=n - 1)
        change(ledger, source='runner', engine_run_dir=None)
    r = row(tool().analyze(w10=[root]), task)
    assert r['attempt'] == 10
    assert r['evidence_refs'][0].endswith('attempt-10.json')
