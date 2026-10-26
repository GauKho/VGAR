"""M3-W9-2c: build the real prompt for every pair without calling a model; run refuses without it."""
import json

import pytest
from m3_support import ROOT, write_json


def test_fixture_preflight_fits(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    from vgar.evaluation.repair.preflight import preflight
    exp = load_experiment(fixture_config, tmp_path)
    rows = preflight(exp, tmp_path, tmp_path/'out')
    assert [(r['variant_id'], r['result']) for r in rows] == [('A0', 'FITS'), ('A1', 'FITS'), ('A2', 'FITS')]
    for row in rows:
        assert row['input_tokens'] > 0 and row['headroom'] == row['input_cap'] - row['input_tokens']
        assert row['baseline_estimate'] == 'failing_selectors'
    saved = json.loads((tmp_path/'out'/exp.experiment_id/'preflight.json').read_text(encoding='utf-8'))
    assert saved['experiment_id'] == exp.experiment_id and saved['rows'] == rows


def test_over_cap_reported_not_raised(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    from vgar.evaluation.repair.preflight import preflight
    demo = json.loads((ROOT/'configs/m2/demo.json').read_text(encoding='utf-8'))
    demo['policy']['input_cap'] = 50
    for field in ('snapshot', 'interpreter', 'tokenizer_manifest'):
        demo['model'][field] = str((ROOT/'configs/m2'/demo['model'][field]).resolve())
    small = write_json(tmp_path/'small.json', demo)
    config = json.loads(fixture_config.read_text(encoding='utf-8'))
    config['repair_config'] = str(small)
    write_json(fixture_config, config)
    rows = preflight(load_experiment(fixture_config, tmp_path), tmp_path, tmp_path/'out')
    assert {r['result'] for r in rows} == {'OVER_CAP'}
    assert all(r['input_tokens'] > 50 and r['headroom'] < 0 for r in rows)


def test_skipped_tasks_reported_as_error(swebench_config, monkeypatch):
    from vgar.evaluation.repair import preflight as module
    from vgar.evaluation.repair.manifest import load_experiment
    config, data = swebench_config
    monkeypatch.setattr(module, 'admit_task', lambda *a, **k: (_ for _ in ()).throw(ValueError('no docker image')))
    rows = module.preflight(load_experiment(config, data), data, data/'out')
    excluded = [r for r in rows if r['task_id'] == 'demo__demo-2']
    assert {(r['result'], r['reason']) for r in excluded} == {('ERROR', 'TASK_EXCLUDED')}
    rejected = [r for r in rows if r['task_id'] == 'demo__demo-1']
    assert {(r['result'], r['reason']) for r in rejected} == {('ERROR', 'ADMISSION_REJECTED')}
    assert 'no docker image' in rejected[0]['detail']


def test_failing_selector_outside_fallback_scope_is_error(fixture_config, tmp_path, monkeypatch):
    # The engine's baseline collects only fallback_scope, then requires every failing selector in it.
    import dataclasses
    from vgar.evaluation.repair import preflight as module
    from vgar.evaluation.repair.manifest import load_experiment
    real = module.plan_task

    def narrowed(*args):
        plan = real(*args)
        return dataclasses.replace(plan, task=plan.task.model_copy(update={'fallback_scope': ('tests/other.py',)}))

    monkeypatch.setattr(module, 'plan_task', narrowed)
    rows = module.preflight(load_experiment(fixture_config, tmp_path), tmp_path, tmp_path/'out')
    assert {(r['result'], r['reason']) for r in rows} == {('ERROR', 'SELECTOR_OUTSIDE_SCOPE')}
    assert 'tests/test_auth.py::test_login_rejects_whitespace' in rows[0]['detail']


def test_run_refuses_without_preflight(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    from vgar.evaluation.repair.preflight import preflight, require_preflight
    exp = load_experiment(fixture_config, tmp_path)
    with pytest.raises(RuntimeError, match='preflight'):
        require_preflight(tmp_path/'out', exp)
    preflight(exp, tmp_path, tmp_path/'out')
    require_preflight(tmp_path/'out', exp)
