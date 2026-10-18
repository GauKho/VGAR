"""Fake pieces of agent mode: a broken first diff, a scripted generator and a scripted tool-calling agent."""
from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from vgar.agents.fakes import ScriptedPatchGenerator, ScriptedRepairAgent, break_diff
from vgar.repair.config import CONFIG_DIR, load_config, load_task
from vgar.repair.patch import PatchPolicy, parse_unified_diff

REPO = Path(__file__).resolve().parents[2]
CASES = ["single_file_login", "multi_file_invoice", "missing_links"]


@pytest.mark.parametrize("case", CASES)
def test_break_diff_makes_every_reference_patch_unparseable(case):
    diff = (REPO / f"tests/fixtures/m2/reference_patches/{case}.diff").read_text(encoding="utf-8")
    task = load_task(REPO / f"examples/m2/tasks/{case}.json")
    policy = load_config(CONFIG_DIR / "demo.json")[0]
    pp = PatchPolicy(task.allowed_source_paths, task.protected_paths, policy.max_diff_bytes,
                     policy.max_files, policy.max_changed_lines)
    parse_unified_diff(diff, pp)  # the reference itself parses
    with pytest.raises(ValueError):
        parse_unified_diff(break_diff(diff), pp)


def test_scripted_patch_generator_returns_diffs_in_order():
    generator = ScriptedPatchGenerator(["a", "b"])
    prompt = type("Prompt", (), {"input_tokens": 3})()
    assert [generator.generate(prompt, None, 1)["raw_text"] for _ in range(3)] == ["a", "b", "b"]
    assert generator.mode == "fake"


def next_call(messages):
    reply = ScriptedRepairAgent().invoke(messages)
    return reply.tool_calls[0] if reply.tool_calls else None


def tool_reply(name, content):
    return [HumanMessage("fix it"), AIMessage("", tool_calls=[{"name": name, "args": {}, "id": "c1"}]),
            ToolMessage(content, name=name, tool_call_id="c1")]


def test_scripted_agent_starts_with_context():
    call = next_call([HumanMessage("fix it")])
    assert call["name"] == "get_task_context" and call["args"] == {}


def test_scripted_agent_retries_after_apply_fail():
    retry = next_call(tool_reply("apply_patch", "STATUS: FAIL\nREASON: PATCH_PARSE_ERROR\nATTEMPTS LEFT: 2\nNEXT: x"))
    assert retry["name"] == "generate_patch"
    give_up = next_call(tool_reply("apply_patch", "STATUS: FAIL\nREASON: PATCH_PARSE_ERROR\nATTEMPTS LEFT: 0\nNEXT: x"))
    assert give_up["name"] == "verify_patch"


def test_scripted_agent_follows_the_usual_order():
    assert next_call(tool_reply("get_task_context", "STATUS: PASS"))["name"] == "generate_patch"
    assert next_call(tool_reply("generate_patch", "STATUS: PASS\nATTEMPT: 1 of 3"))["name"] == "apply_patch"
    assert next_call(tool_reply("generate_patch", "STATUS: ERROR"))["name"] == "verify_patch"
    assert next_call(tool_reply("apply_patch", "STATUS: PASS"))["name"] == "run_relevant_tests"
    assert next_call(tool_reply("run_relevant_tests", "STATUS: PASS"))["name"] == "verify_patch"


def test_scripted_agent_stops_after_verify():
    reply = ScriptedRepairAgent().invoke(tool_reply("verify_patch", "STATUS: PASS\nRECOMMENDATION: ACCEPT"))
    assert not reply.tool_calls and "ACCEPT" in reply.content
