"""S15 / D20: `vgar solve --agent` on an admitted SWE-bench task (no Docker here; admission is stubbed)."""
import asyncio
import json

import pytest


class StubAdmission:
    def __init__(self, task):
        from vgar.repair.admission import canonical_hash
        self.value = {'task_hash': canonical_hash(task.model_dump(mode='json')), 'admission_hash': 'sha256:' + 'a'*64}

    def snapshot(self):
        return dict(self.value)


@pytest.fixture
def admitted(swebench_config, monkeypatch, tmp_path):
    from vgar.agents import admitted as module
    seen = {}

    def admit(task, **kwargs):
        seen.update(kwargs)
        return StubAdmission(task)

    monkeypatch.setattr(module, 'admit_task', admit)
    config, data = swebench_config
    return module, config, data, seen


def test_prepare_writes_task_whose_hash_matches_the_admission(admitted, tmp_path):
    from vgar.repair.admission import canonical_hash
    from vgar.repair.config import load_task
    module, config, data, seen = admitted
    prepared = module.prepare_admitted_task(config, 'demo__demo-1', 'A2', data, tmp_path/'tasks')
    reloaded = load_task(prepared.task_path)
    assert canonical_hash(reloaded.model_dump(mode='json')) == prepared.run_args['admission']['task_hash']
    assert reloaded.trusted_fixture is False and reloaded.task_id == 'demo__demo-1'
    assert prepared.run_args['experiment']['arm'] == 'graph' and 'variant_policy' in prepared.run_args['experiment']
    assert seen['docker_host'] == 'unix:///var/run/docker.sock'


def test_prepare_refuses_a_task_the_runner_would_skip(admitted, tmp_path):
    module, config, data, _ = admitted
    with pytest.raises(ValueError, match='TASK_EXCLUDED'):
        module.prepare_admitted_task(config, 'demo__demo-2', 'A2', data, tmp_path/'tasks')
    with pytest.raises(ValueError, match='Unknown variant'):
        module.prepare_admitted_task(config, 'demo__demo-1', 'A9', data, tmp_path/'tasks')


def test_repair_server_forwards_admission_to_the_session(tmp_path, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import repair_server
    from vgar.repair import session
    seen = {}

    def spy(*args, **kwargs):
        seen.update(kwargs)
        raise RuntimeError('stop after start_session')

    monkeypatch.setattr(session, 'start_session', spy)
    monkeypatch.setattr(repair_server, '_audit_logger', AuditLogger(tmp_path/'audit.jsonl'))
    monkeypatch.setenv('VGAR_RUN_ROOT', str(tmp_path))
    from m3_support import ROOT
    repair_server.get_task_context(str(ROOT/'examples/m2/tasks/single_file_login.json'), 'fake',
                                   str(tmp_path/'runs'), str(tmp_path/'work'), admission={'admission_hash': 'x'})
    assert seen['admission'] == {'admission_hash': 'x'}


def test_agent_host_opens_every_run_with_the_admission(tmp_path, monkeypatch):
    from m3_support import ROOT
    from vgar.agents import tool_agent
    from vgar.agents.runtime import Runtime
    calls = []

    async def fake_call(runtime, tool, args):
        calls.append((tool, args))
        return {'status': 'ERROR', 'reason': 'ROOT_NOT_LEASED', 'detail': 'stub'}

    monkeypatch.setattr(tool_agent, '_call', fake_call)
    run_args = {'experiment': {'arm': 'graph'}, 'admission': {'admission_hash': 'x'}}
    host = tool_agent.AgentRepairHost(Runtime(output_root=tmp_path/'runs'), ROOT/'examples/m2/tasks/single_file_login.json',
                                      tmp_path/'work', None, run_args=run_args)
    asyncio.run(host._open_run('agent'))
    asyncio.run(host._open_run('agent', feedback={'message': 'retry'}))
    assert [args['admission'] for _, args in calls] == [{'admission_hash': 'x'}] * 2
    assert calls[1][1]['experiment'] == {'arm': 'graph'} and calls[1][1]['feedback'] == {'message': 'retry'}


def test_cli_solve_agent_takes_experiment_task_and_requires_a_scripted_patch_in_fake_mode(capsys):
    from vgar import cli
    p = cli.parser()
    args = p.parse_args(['solve', '--agent', '--experiment', 'e.json', '--task-id', 't', '--variant', 'A2'])
    assert (str(args.experiment), args.task_id, args.variant, args.task) == ('e.json', 't', 'A2', None)
    with pytest.raises(SystemExit):
        cli.main(['solve', '--agent', '--experiment', 'e.json', '--task-id', 't', '--variant', 'A2', '--mode', 'fake'])
    assert '--scripted-patch' in capsys.readouterr().err
