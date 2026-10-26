"""M3-W9-2: experiment config, experiment identity and per-task planning (no engine calls)."""
import json
import re

import pytest
from m3_support import git, write_json


def edit(path, change):
    data = json.loads(path.read_text(encoding='utf-8'))
    change(data)
    write_json(path, data)


def test_fixture_experiment_loads_and_id_is_stable(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    first, second = load_experiment(fixture_config, tmp_path), load_experiment(fixture_config, tmp_path)
    assert first.experiment_id == second.experiment_id
    assert re.fullmatch(r'[0-9a-f]{16}', first.experiment_id)
    assert first.source_type == 'fixture' and first.task_ids == ('single_file_login',)
    assert [(v.variant_id, v.arm) for v in first.variants] == [('A0', 'bm25'), ('A1', 'graph'), ('A2', 'graph')]


def test_changed_variant_changes_experiment_id(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    before = load_experiment(fixture_config, tmp_path).experiment_id
    edit(fixture_config, lambda d: d['variants'][1].update(arm='bm25'))
    assert load_experiment(fixture_config, tmp_path).experiment_id != before


def test_experiment_id_ignores_data_root(swebench_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    config, data = swebench_config
    assert load_experiment(config, data).experiment_id == load_experiment(config, tmp_path/'elsewhere').experiment_id


def test_fake_generation_rejected_for_swebench(swebench_config):
    from vgar.evaluation.repair.manifest import load_experiment
    config, data = swebench_config
    edit(config, lambda d: d.update(generation='fake'))
    with pytest.raises(ValueError, match='fake'):
        load_experiment(config, data)


def test_null_arm_rejected(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment
    edit(fixture_config, lambda d: d['variants'][0].pop('arm'))
    with pytest.raises(ValueError, match='arm'):
        load_experiment(fixture_config, tmp_path)


def test_manifest_pin_mismatch_rejected(swebench_config):
    from vgar.evaluation.repair.manifest import load_experiment
    config, data = swebench_config
    edit(config, lambda d: d['source']['manifest'].update(sha256='sha256:' + 'b'*64))
    with pytest.raises(ValueError, match='manifest'):
        load_experiment(config, data)


def test_excluded_profile_gives_task_excluded(swebench_config):
    from vgar.evaluation.repair.manifest import load_experiment, plan_task
    config, data = swebench_config
    exp = load_experiment(config, data)
    plan = plan_task(exp, 'demo__demo-2', exp.variants[0], data)
    assert plan.skip_reason == 'TASK_EXCLUDED' and plan.skip_detail == 'PYTEST_UNAVAILABLE'
    assert plan.task is None and plan.admission_args is None


def test_missing_inputs_gives_task_input_missing(swebench_config):
    from vgar.evaluation.repair.manifest import load_experiment, plan_task
    config, data = swebench_config
    exp = load_experiment(config, data)
    (config.parent/'tasks/demo__demo-1.json').unlink()
    plan = plan_task(exp, 'demo__demo-1', exp.variants[0], data)
    assert plan.skip_reason == 'TASK_INPUT_MISSING' and 'demo__demo-1.json' in plan.skip_detail


def test_task_fields_come_from_manifest_bundle_inventory(swebench_config):
    from vgar.evaluation.repair.manifest import load_experiment, plan_task
    config, data = swebench_config
    exp = load_experiment(config, data)
    graph = plan_task(exp, 'demo__demo-1', exp.variants[1], data)
    bm25 = plan_task(exp, 'demo__demo-1', exp.variants[0], data)
    task = graph.task
    assert graph.skip_reason is None
    assert (task.issue_text, task.repo_key) == ('f is wrong', 'demo/demo')
    assert task.revision == git(data/'repositories/demo__demo-1', 'rev-parse', 'HEAD')
    assert task.graph_version == 'sha256:' + 'f'*64 and bm25.task.graph_version == 'sha256:' + 'e'*64
    assert task.allowed_source_paths == ('pkg/core.py',)
    assert task.trusted_fixture is False
    assert task.source_repo == (data/'repositories/demo__demo-1').resolve()
    args = graph.admission_args
    assert args['source_roots'] == ['pkg']
    assert args['overlay'] == {'tests/vgar_w9_repro_f.py': 'def test_f():\n    assert False\n'}
    assert args['expected_profile_hash'] == json.loads((data/'profiles/demo__demo-1.json').read_text())['profile_hash']
    assert set(args['bundle_hashes']) == {'context.json', 'context_manifest.json', 'test_links.json'}


def test_fixture_plan_uses_task_file_without_admission(fixture_config, tmp_path):
    from vgar.evaluation.repair.manifest import load_experiment, plan_task
    exp = load_experiment(fixture_config, tmp_path)
    plan = plan_task(exp, 'single_file_login', exp.variants[2], tmp_path)
    assert plan.task.trusted_fixture is True and plan.admission_args is None and plan.skip_reason is None
