"""Parsing Qwen's replies: <tool_call> blocks and the final JSON answer (spec 2026-11-19 §8)."""
import json

from baseline.nav.model import parse_final, parse_tool_calls


def test_tool_calls_are_read_from_every_block():
    text = ('Let me look.\n<tool_call>\n{"name": "grep", "arguments": {"pattern": "def g"}}\n</tool_call>\n'
            '<tool_call>{"name": "list_dir", "arguments": {}}</tool_call>')
    assert parse_tool_calls(text) == [{"name": "grep", "arguments": {"pattern": "def g"}},
                                      {"name": "list_dir", "arguments": {}}]


def test_broken_tool_call_json_becomes_an_error_entry():
    calls = parse_tool_calls('<tool_call>{"name": "grep", "arguments": {</tool_call>')
    assert len(calls) == 1 and "error" in calls[0]


def test_final_answer_in_a_fenced_block_is_trimmed_to_20_files_and_20_functions():
    files, functions = [f"f{i}.py" for i in range(25)], [f"f{i}.py::m.g" for i in range(25)]
    text = "Done.\n```json\n" + json.dumps({"files": files, "functions": functions}) + "\n```"
    assert parse_final(text) == {"files": files[:20], "functions": functions[:20]}


def test_an_answer_after_prose_with_braces_is_still_found():
    # pytest-7205 in T2: the explanation printed f"{param!r}" before the JSON, so the first-{ to last-} span failed
    text = ('The parameter is shown with f"{param!r}" in {setuponly}.\n\n'
            '{"files": ["src/_pytest/setuponly.py"], "functions": []}')
    assert parse_final(text) == {"files": ["src/_pytest/setuponly.py"], "functions": []}


def test_no_answer_or_a_tool_call_is_not_a_final_answer():
    assert parse_final("I am not sure.") is None
    assert parse_final('<tool_call>{"name": "grep", "arguments": {"pattern": "files"}}</tool_call>') is None
    assert parse_final('{"files": "a.py"}') == {"files": ["a.py"], "functions": []}
