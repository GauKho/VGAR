"""T2 audit uses sealed synthetic vectors; no benchmark run or target execution."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.evaluation.repair import verifier_eval as api
from vgar.evaluation.repair.mutant_pool import PoolTask, build_pool
from vgar.repair.contracts import RepairPolicy
from vgar.repair.evidence import digest
from vgar.repair.policy import load_variant
from vgar.repair.static_diagnostics import DiagnosticReport, parse_tool_report, scope_digest
from vgar.repair.workspace import create_workspace, inventory

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'def first(value):\n    return value\n\ndef second(value):\n    return value\n'
PATCH = '--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,4 @@\n+# header\n def first(value):\n     return value\n \n'


@pytest.fixture
def audit_module():
    path = ROOT / 'scripts/audit_mypy_deltas.py'
    assert path.is_file(), 'T2 audit CLI missing'
    spec = importlib.util.spec_from_file_location('t2_mypy_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit_case(tmp_path, monkeypatch, request):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.py').write_bytes(SOURCE.encode('utf-8'))
    tasks = [PoolTask('fixture', 'fixture/audit', 'base', source, PATCH, ('a.py',), fixture=True)]
    if getattr(request, 'param', False):
        tasks.append(PoolTask('missing', 'fixture/audit', 'base', tmp_path / 'missing', '', (),
                              fixture=True, unavailable_reason='SOURCE_MISSING'))
    pool = tmp_path / 'pool'
    index = build_pool(tasks, pool)
    task = SimpleNamespace(task_id='fixture', repo_key='fixture/audit', revision='base', source_repo=source,
        allowed_source_paths=('a.py',), protected_paths=('tests', 'pytest.ini'),
        failing_selectors=('test_fix',), fallback_scope=('tests',))
    policies = {n: load_variant(ROOT / 'configs/m2/variants' / ('A3.json' if n == 'A3' else f'w10/{n}.json'))
                for n in ('A0', 'A1', 'A2', 'A3')}

    def static(lease, *args):
        text = (lease.path / 'a.py').read_bytes().decode('utf-8')
        binding = dict(scope=['a.py'], scope_hash=scope_digest(['a.py']), interpreter_ref='synthetic-python')
        context = dict(binding, config_hash='synthetic-mypy-config')
        diagnostic = dict(file='a.py', line=3 if text.startswith('# header') else 2,
                          column=4, code='return-value', severity='error', message='Synthetic existing debt')
        command = dict(cwd=str(lease.path), stdout=json.dumps(diagnostic), stderr='', complete=True,
                       exit_code=1, status='FAIL', timed_out=False, output_truncated=False,
                       diagnostic_context=context)
        command['report'] = parse_tool_report('mypy', command, '2.4.0').model_dump(mode='json')
        result = dict(binding=binding, config_hashes={'mypy': 'synthetic-mypy-config', 'ruff': 'r'},
                      source_snapshot={'a.py': text}, mypy=command)
        for tool in ('syntax', 'ruff'):
            result[tool] = dict(status='PASS', report=DiagnosticReport(tool=tool, tool_version='fixture',
                execution_status='COMPLETE', **binding).model_dump(mode='json'))
        return result

    monkeypatch.setattr(api, 'collect_static_measurements', static)
    monkeypatch.setattr(api, 'collect_tests', lambda *a: {'status': 'PASS', 'node_ids': ['test_fix']})
    monkeypatch.setattr(api, 'run_tests', lambda lease, *a: {'status': 'PASS' if (
        lease.path / 'a.py').read_text(encoding='utf-8').startswith('# header') else 'FAIL',
        'outcomes': {'test_fix': 'PASS' if (lease.path / 'a.py').read_text(encoding='utf-8').startswith('# header') else 'FAIL'}})

    def apply(lease, *args):
        (lease.path / 'a.py').write_bytes(('# header\n' + SOURCE).encode('utf-8'))
        return SimpleNamespace(status='PASS', changed_files=['a.py'], model_dump=lambda **k:
                               {'status': 'PASS', 'changed_files': ['a.py']})

    monkeypatch.setattr(api, 'apply_patch', apply)

    def once(task, patch, policy, out, **kwargs):
        if patch != PATCH:
            vector = api._empty_vector(task, 'SYNTHETIC_MUTANT_NOT_EXECUTED')
        else:
            with create_workspace(source, tmp_path / 'leases') as lease:
                vector = api.collect_patch_vector(task, lease, None, policy, patch, out)
                assert vector['integrity']['status'] == 'PASS', vector
                vector['binding'].update(original_source_inventory=inventory(source), overlay={})
        vector['binding'].update(repo_key=task.repo_key, revision=task.revision,
            repair_policy_hash=api.canonical_hash(policy.model_dump(mode='json')), pool=kwargs['pool_binding'])
        vector = api.seal_vector(vector)
        out.mkdir(parents=True, exist_ok=True)
        api.atomic_json(out / 'vector.json', vector)
        return vector

    monkeypatch.setattr(api, 'verify_once', once)
    campaign = tmp_path / 'campaign'
    record = api.evaluate_pool(pool, campaign, lambda task_id: (task, None), RepairPolicy(), policies,
                               expected_pool_hash=index['pool_hash'])
    return pool, campaign, index, record


def invoke(module, case, output):
    pool, campaign, index, _ = case
    return module.main(['--pool', str(pool), '--campaign', str(campaign),
                        '--expected-pool-hash', index['pool_hash'], '--output-root', str(output)])


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_audit_recovers_mapping_from_neutral_vector_without_saved_delta(audit_module, audit_case, tmp_path):
    pool, campaign, _, record = audit_case
    before = tree_bytes(pool), tree_bytes(campaign)
    assert invoke(audit_module, audit_case, tmp_path / 'out1') == 0
    assert invoke(audit_module, audit_case, tmp_path / 'out2') == 0
    data = json.loads((tmp_path / 'out1/audit.json').read_bytes())
    assert data['status'] == 'READY_FOR_REVIEW' and data['synthetic'] is True
    assert len(data['rows']) == 1
    row = data['rows'][0]
    assert row['classification'] == 'FALSE_REJECT_CONFIRMED'
    assert row['old_delta']['status'] == 'FAIL' and row['new_delta']['status'] == 'PASS'
    assert len(row['diagnostics']) == 1 and row['diagnostics'][0]['category'] == 'MAPPING_RECOVERED'
    assert row['diagnostics'][0]['mapping']['before_line'] == 2
    assert row['diagnostics'][0]['mapping']['after_line'] == 3
    assert row['diagnostics'][0]['mapping']['kind'] == 'UNCHANGED_DECLARATION'
    assert len(data['unverified_reported_task_ids']) == 10
    assert tree_bytes(tmp_path / 'out1') == tree_bytes(tmp_path / 'out2')
    assert before == (tree_bytes(pool), tree_bytes(campaign))
    gold = next(r for r in record['slots'] if r['operator'] == 'gold')
    vector = json.loads((campaign / gold['vector_ref']).read_bytes())
    assert 'delta' not in vector['post']['static']['mypy']


@pytest.mark.parametrize('fault', ['missing_vector', 'missing_snapshot', 'config_drift', 'tool_error',
    'raw_report_mismatch', 'sidecar_corrupt', 'source_drift', 'wrong_task', 'pending', 'escape'])
def test_audit_preserves_incomplete_gold_in_ledger(audit_module, audit_case, tmp_path, fault):
    _, campaign, _, record = audit_case
    row = next(r for r in record['slots'] if r['operator'] == 'gold')
    path = campaign / row['vector_ref']
    vector = json.loads(path.read_bytes())
    post = vector['post']['static']
    if fault == 'missing_vector':
        path.unlink()
    elif fault == 'sidecar_corrupt':
        ref = vector['post']['compatibility']['api']['details_ref']
        (path.parent / ref).write_bytes(b'{}')
    elif fault == 'pending':
        row.update(status='NOT_RUN', vector_ref=None, vector_file_hash=None)
    else:
        if fault == 'missing_snapshot':
            del post['source_snapshot']
        elif fault == 'config_drift':
            post['mypy']['diagnostic_context']['config_hash'] = 'other-config'
            post['config_hashes']['mypy'] = 'other-config'
            post['mypy']['report'] = parse_tool_report('mypy', post['mypy'], '2.4.0').model_dump(mode='json')
        elif fault == 'tool_error':
            post['mypy']['complete'] = False
            post['mypy']['report'] = parse_tool_report('mypy', post['mypy'], '2.4.0').model_dump(mode='json')
        elif fault == 'raw_report_mismatch':
            post['mypy']['stdout'] = '{}'
        elif fault == 'source_drift':
            post['source_snapshot']['a.py'] = 'changed = True\n'
        elif fault == 'wrong_task':
            vector['task_id'] = 'different'
        elif fault == 'escape':
            vector['post']['compatibility']['api']['details_ref'] = '../outside.json'
        api.atomic_json(path, api.seal_vector(vector))
        row['vector_file_hash'] = digest(path.read_bytes())
    api._save_campaign(campaign, record)
    before = tree_bytes(campaign)
    assert invoke(audit_module, audit_case, tmp_path / 'out') == 2
    data = json.loads((tmp_path / 'out/audit.json').read_bytes())
    assert data['status'] == 'PARTIAL' and len(data['rows']) == 1
    assert data['rows'][0]['classification'] != 'FALSE_REJECT_CONFIRMED'
    assert data['rows'][0]['reason']
    expected = {'missing_vector': 'FileNotFoundError', 'missing_snapshot': 'source_snapshot',
        'config_drift': 'STATIC_BINDING_CHANGED', 'tool_error': 'Mypy tool incomplete',
        'raw_report_mismatch': 'differs from raw', 'sidecar_corrupt': 'sidecar hash mismatch',
        'source_drift': 'source snapshot differs', 'wrong_task': 'Vector task differs',
        'pending': 'NOT_RUN', 'escape': 'Path escapes'}
    assert expected[fault] in data['rows'][0]['reason']
    assert tree_bytes(campaign) == before


@pytest.mark.parametrize('audit_case', [True], indirect=True)
def test_audit_keeps_unavailable_pool_gold_and_does_not_replace_it(audit_module, audit_case, tmp_path):
    assert invoke(audit_module, audit_case, tmp_path / 'out') == 2
    rows = json.loads((tmp_path / 'out/audit.json').read_bytes())['rows']
    assert len(rows) == 2 and [r['task_id'] for r in rows] == ['fixture', 'missing']
    assert rows[0]['classification'] == 'FALSE_REJECT_CONFIRMED'
    assert rows[1]['reason'] == 'SOURCE_MISSING'


@pytest.mark.parametrize('output_kind', ['exists', 'pool', 'campaign'])
def test_audit_rejects_existing_or_overlapping_output(audit_module, audit_case, tmp_path, output_kind):
    pool, campaign, _, _ = audit_case
    out = tmp_path / 'out'
    if output_kind == 'exists':
        out.mkdir()
        (out / 'sentinel').write_bytes(b'keep')
    else:
        out = (pool if output_kind == 'pool' else campaign) / 'new-audit'
    before = tree_bytes(tmp_path)
    assert invoke(audit_module, audit_case, out) == 2
    assert tree_bytes(tmp_path) == before


def test_audit_records_missing_export_without_fake_measurement(audit_module, audit_case, tmp_path):
    pool, _, index, record = audit_case
    case = pool, tmp_path / 'missing-export', index, record
    assert invoke(audit_module, case, tmp_path / 'out') == 2
    data = json.loads((tmp_path / 'out/audit.json').read_bytes())
    assert data['status'] == 'PARTIAL' and len(data['rows']) == 1
    assert data['rows'][0]['classification'] == 'MISSING_EVIDENCE'


@pytest.mark.parametrize('change,want', [('line', 'UNRESOLVED'), ('code', 'INTRODUCED_BY_RULE'),
                                       ('column', 'INTRODUCED_BY_RULE')])
def test_audit_does_not_waive_new_or_unresolved_diagnostics(audit_module, audit_case, tmp_path, change, want):
    _, campaign, _, record = audit_case
    row = next(r for r in record['slots'] if r['operator'] == 'gold')
    path = campaign / row['vector_ref']
    vector = json.loads(path.read_bytes())
    command = vector['post']['static']['mypy']
    diagnostic = json.loads(command['stdout'])
    diagnostic[change] = {'line': 6, 'code': 'arg-type', 'column': 5}[change]
    command['stdout'] = json.dumps(diagnostic)
    command['report'] = parse_tool_report('mypy', command, '2.4.0').model_dump(mode='json')
    api.atomic_json(path, api.seal_vector(vector))
    row['vector_file_hash'] = digest(path.read_bytes())
    api._save_campaign(campaign, record)
    assert invoke(audit_module, audit_case, tmp_path / 'out') == 0
    item = json.loads((tmp_path / 'out/audit.json').read_bytes())['rows'][0]
    assert item['classification'] == want and item['new_delta']['status'] == 'FAIL'
    assert len(item['new_delta']['introduced']) == 1


def test_audit_rejects_reparse_point_metadata_before_reading_sidecar(audit_module, audit_case, tmp_path, monkeypatch):
    import stat
    _, campaign, _, record = audit_case
    row = next(r for r in record['slots'] if r['operator'] == 'gold')
    path = campaign / row['vector_ref']
    vector = json.loads(path.read_bytes())
    sidecar = path.parent / vector['post']['compatibility']['api']['details_ref']
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == sidecar:
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', lstat)
    assert invoke(audit_module, audit_case, tmp_path / 'out') == 2
    item = json.loads((tmp_path / 'out/audit.json').read_bytes())['rows'][0]
    assert 'link/reparse' in item['reason']


def test_audit_detects_input_drift_after_validation(audit_module, audit_case, tmp_path, monkeypatch):
    _, campaign, _, _ = audit_case
    original = audit_module.compare_diagnostics
    calls = []

    def compare(*args):
        result = original(*args)
        if not calls:
            calls.append(True)
            path = campaign / 'campaign.json'
            path.write_bytes(path.read_bytes() + b' ')
        return result

    monkeypatch.setattr(audit_module, 'compare_diagnostics', compare)
    assert invoke(audit_module, audit_case, tmp_path / 'out') == 2
    data = json.loads((tmp_path / 'out/audit.json').read_bytes())
    assert data['input_unchanged'] is False
    assert data['rows'][0]['classification'] == 'MISSING_EVIDENCE'


def test_input_inventory_preserves_first_hash_on_repeated_read(audit_module, tmp_path):
    pool, campaign = tmp_path / 'pool', tmp_path / 'campaign'
    pool.mkdir()
    campaign.mkdir()
    path = pool / 'pool.json'
    path.write_bytes(b'{}')
    inputs = audit_module._Inputs(pool, campaign)
    inputs.read('pool', 'pool.json')
    path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match='changed'):
        inputs.read('pool', 'pool.json')
    assert inputs.unchanged() is False
