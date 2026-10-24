"""Manifest no-gold boundary and sequential export controller."""
import copy

import pytest


def test_projection_ignores_gold_and_oracle():
    from vgar.evaluation.retrieval.pilot_manifest import project_retrieval_task
    row = {'instance_id': 'astropy__astropy-13398', 'repo': 'astropy/astropy',
           'base_commit': 'a'*40, 'problem_statement': 'normalize broken',
           'patch': 'GOLD', 'FAIL_TO_PASS': ['SECRET'], 'changed_source_files': ['answer.py']}
    projected = project_retrieval_task(row)
    other = copy.deepcopy(row)
    other.update(patch='DIFFERENT GOLD', FAIL_TO_PASS=['OTHER'], changed_source_files=['gold.py'])
    assert project_retrieval_task(other) == projected
    assert set(projected) == {'instance_id', 'repo', 'base_commit', 'problem_statement', 'query_hash', 'split'}


def test_manifest_is_pinned_and_hash_bound():
    from vgar.evaluation.retrieval.pilot_manifest import (
        PILOT_IDS,
        make_manifest,
        validate_manifest,
    )
    tasks = [{'instance_id': i, 'repo': 'fixture/project', 'base_commit': 'a'*40,
              'problem_statement': 'normalize'} for i in PILOT_IDS]
    manifest = make_manifest(tasks, parquet_hash='sha256:'+'a'*64)
    validate_manifest(manifest)
    bad = copy.deepcopy(manifest)
    bad['tasks'][0]['base_commit'] = 'b'*40
    with pytest.raises(ValueError):
        validate_manifest(bad)
    bad = copy.deepcopy(manifest)
    bad['tasks'] = bad['tasks'][:-1]
    with pytest.raises(ValueError):
        validate_manifest(bad)


def test_export_task_arms_share_test_policy(tmp_path):
    from vgar.evaluation.retrieval.pilot_export import export_task
    root = tmp_path / 'repo'
    (root / 'tests').mkdir(parents=True)
    (root / 'app.py').write_text('def normalize(value):\n    return value.strip()\n', encoding='utf-8')
    (root / 'tests/test_app.py').write_text('def test_normalize(): assert True\n', encoding='utf-8')
    task = {'instance_id':'astropy__astropy-13398', 'repo':'fixture/project', 'base_commit':'a'*40,
            'problem_statement':'normalize value'}
    result = export_task(task, root, tmp_path / 'export', count_tokens=len, counter_label='fixture:characters')
    assert [a['status'] for a in result['arms']] == ['PASS', 'PASS']
    assert all(a['snippet_budget'] == 8000 for a in result['arms'])
    assert result['fallback_scope'] == ['tests/test_app.py']
    with pytest.raises(FileExistsError):
        export_task(task, root, tmp_path / 'export', count_tokens=len, counter_label='fixture:characters')


def test_both_arms_exclude_empty_named_source(tmp_path):
    from vgar.evaluation.retrieval.pilot_export import export_task
    root = tmp_path/'repo'
    root.mkdir()
    (root/'normalize.py').write_bytes(b' \n')
    (root/'app.py').write_bytes(b'def normalize(name):\n    return name.strip()\n')
    result = export_task({'instance_id':'astropy__astropy-13398', 'repo':'fixture/project',
        'base_commit':'a'*40, 'problem_statement':'normalize name'}, root, tmp_path/'output',
        count_tokens=len, counter_label='fixture:characters')
    assert all(a['status']=='PASS' for a in result['arms'])


@pytest.mark.parametrize('outcome', ['timeout', 'invalid_json', 'mixed_arms', 'bad_exit_all_pass'])
def test_controller_keeps_all_task_arm_records(tmp_path, monkeypatch, outcome):
    import importlib.util
    import json
    import subprocess
    from pathlib import Path
    from types import SimpleNamespace

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('w9_export_controller', root/'scripts/export_w9_pilot_bundles.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    manifest = json.loads((root/'configs/m1/w9_pilot_manifest.json').read_text(encoding='utf-8'))
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    tokenizer = tmp_path/'tokenizer.json'
    tokenizer.write_text((root/'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json').read_text(encoding='utf-8'), encoding='utf-8')
    monkeypatch.setattr(script.sys, 'argv', ['export', '--manifest',str(path), '--profile',str(root/'configs/m1/w9_bundle_profile.json'),
        '--tokenizer-manifest',str(tokenizer), '--output-root',str(tmp_path/'out')])
    def fake_worker(command, **kwargs):
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(command, 600)
        directory = Path(command[command.index('--directory')+1])
        directory.mkdir()
        data = '{' if outcome == 'invalid_json' else json.dumps({'source_unchanged':True,
            'task':{'arms':[{'arm':'graph','status':'PASS'}, {'arm':'bm25',
                            'status':'PASS' if outcome == 'bad_exit_all_pass' else 'ERROR','reason':'no_context'}]}})
        (directory/'worker_result.json').write_text(data, encoding='utf-8')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(script.subprocess, 'run', fake_worker)
    assert script.main() == 1
    report = json.loads(next((tmp_path/'out').glob('*/run_record.json')).read_text(encoding='utf-8'))
    assert len(report['tasks']) == 5 and sum(len(t['arms']) for t in report['tasks']) == 10
    assert report['passed_bundles'] == (10 if outcome == 'bad_exit_all_pass' else 5 if outcome == 'mixed_arms' else 0)
    assert report['status'] == 'INCOMPLETE'
    assert all(t['status']=='ERROR' for t in report['tasks'])


def test_tokenizer_identity_must_match_approved_model(tmp_path):
    import json
    from pathlib import Path

    from vgar.evaluation.retrieval.pilot_manifest import require_tokenizer_identity
    approved = Path(__file__).resolve().parents[1]/'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json'
    value = json.loads(approved.read_text(encoding='utf-8'))
    relocated = tmp_path/'manifest.json'
    value['assets_directory'] = '/different/cache/location'
    relocated.write_text(json.dumps(value), encoding='utf-8')
    require_tokenizer_identity(relocated, approved)
    value['model_id'] = 'other/valid-model'
    relocated.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError):
        require_tokenizer_identity(relocated, approved)
