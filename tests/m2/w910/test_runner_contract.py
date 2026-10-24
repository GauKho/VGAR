"""Direct/session/MCP boundary evidence, not an implementation of M3 runner."""
import json
from pathlib import Path

from vgar.repair.evidence import digest

ROOT = Path(__file__).resolve().parents[3]
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def test_w9_reload_between_all_steps_retains_profile_and_canonical_binding(w9_case, experiment_input, tmp_path):
    from vgar.models.generator import FakeGenerator
    from vgar.repair import session as steps
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.executor import utc_now
    task, count, tokenizer = w9_case
    session = steps.start_session(task, RepairPolicy(), 'fake', tmp_path/'runs',
        temp_root=tmp_path/'temp', experiment=experiment_input)
    directory = session.run.directory
    def reload():
        return steps.RepairSession.load(directory)
    prompt = steps.prepare(reload(), count, tokenizer)
    assert prompt is not None
    snapshot = read(directory/'run_record.json')['experiment']
    assert snapshot['bundle_hashes'] is not None
    generated = FakeGenerator(FIX).generate(prompt, None, 30)
    raw = steps.record_generation(reload(), generated, started_utc=utc_now(), duration_ms=1)
    assert steps.apply_candidate(reload(), raw).status == 'PASS'
    assert steps.run_selected_tests(reload(), count)['status'] == 'TESTED'
    run = steps.finish(reload())
    assert run.record['status'] == 'PASS'
    assert run.record['experiment'] == snapshot
    bundle = read(directory/'evidence_bundle.json')
    assert bundle['metadata']['experiment'] == snapshot
    assert bundle['metadata']['canonical_sha256'] == digest(run.path.read_bytes())
    assert reload().phase == 'finished'
    assert not Path(read(directory/'session.json')['lease']['private']).exists()


def test_bundle_drift_is_error_and_owned_workspace_is_cleaned(w9_case, experiment_input, tmp_path):
    from vgar.repair import session as steps
    from vgar.repair.contracts import RepairPolicy
    task, count, tokenizer = w9_case
    session = steps.start_session(task, RepairPolicy(), 'fake', tmp_path/'runs',
        temp_root=tmp_path/'temp', experiment=experiment_input)
    assert steps.prepare(session, count, tokenizer) is not None
    assert steps.apply_candidate(session, FIX).status == 'PASS'
    path = task.bundle_directory/'context.json'
    path.write_bytes(path.read_bytes()+b'\n')
    assert steps.run_selected_tests(session, count) is None
    run = steps.finish(session)
    assert run.record['status'] == 'ERROR'
    assert 'expected bundle hashes' in run.record['error_detail']['message']
    assert run.record['original_source_unchanged'] is True
    assert not Path(session.state['lease']['private']).exists()


def test_mcp_optional_experiment_survives_fresh_session_tools(tmp_path, experiment_input):
    from vgar.mcp.servers import repair_server as server
    result = server.get_task_context(str(ROOT/'examples/m2/tasks/single_file_login.json'), 'fake',
        str(tmp_path/'runs'), str(tmp_path/'work'), experiment=experiment_input)
    assert result['status'] == 'PASS', result
    directory = Path(result['run_dir'])
    snapshot = read(directory/'run_record.json')['experiment']
    assert server.apply_patch(str(directory), FIX)['status'] == 'PASS'
    assert server.run_relevant_tests(str(directory))['status'] == 'PASS'
    final = server.verify_patch(str(directory))
    assert final['recommendation'] == 'ACCEPT', final
    assert final['evidence']['metadata']['experiment'] == snapshot
    record = read(directory/'run_record.json')
    assert record['experiment'] == snapshot
    assert [call['tool'] for call in record['mcp_calls']] == [
        'get_task_context', 'apply_patch', 'run_relevant_tests', 'verify_patch']
    assert final['evidence']['metadata']['canonical_sha256'] == digest((directory/'run_record.json').read_bytes())


def test_different_arm_contexts_can_share_template_without_same_prompt(w9_case, tmp_path):
    from vgar.evaluation.retrieval.bm25_handoff import create_bm25_handoff
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.handoff import write_context_handoff
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.prompt import build_repair_prompt
    task = load_task(ROOT/'tests/fixtures/w9_bundle/task.json')
    graph = load_handoff(task, len, 'fixture-only:characters', arm='graph')
    document = PythonGraphBuilder(repo_key=task.repo_key, repository_revision=task.revision).build(task.source_repo)
    exported = create_bm25_handoff(document, task.source_repo, issue_text=task.issue_text,
        count_tokens=len, counter_label='fixture-only:characters', selected_tests=('tests',))
    output = write_context_handoff(exported, tmp_path/'bm25')
    lexical = load_handoff(task.model_copy(update={'bundle_directory': output}), len, 'fixture-only:characters', arm='bm25')
    tokenizer = w9_case[2]
    first = build_repair_prompt(task, graph, {}, tokenizer, RepairPolicy())
    second = build_repair_prompt(task, lexical, {}, tokenizer, RepairPolicy())
    assert first.template_hash == second.template_hash
    assert first.prompt_hash != second.prompt_hash
