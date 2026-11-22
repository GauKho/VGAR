"""T2 loop and scoring with a scripted model (spec 2026-11-19 §8)."""
import anyio

from baseline.nav.run_nav import nav_table, run_task, score_nav
from baseline.nav.tools import ToolResult

SOURCES = {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n",
           "pkg/b.py": "from pkg.a import f\n\n\ndef g():\n    return f()\n", "pkg/c.py": "X = 1\n"}
PATCH = ("diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -2 +2 @@\n-    return 1\n+    return 2\n"
         "diff --git a/pkg/b.py b/pkg/b.py\n--- a/pkg/b.py\n+++ b/pkg/b.py\n@@ -5 +5 @@\n-    return f()\n"
         "+    return f() + 1\n")
ROW = {"instance_id": "o__r-1", "problem_statement": "g is wrong", "patch": PATCH}
ANSWER = '{"files": ["pkg/b.py", "pkg/a.py"], "functions": ["pkg/b.py::pkg.b.g", "pkg/a.py::f"]}'


class FakeModel:
    def __init__(self, replies, prompt=100):
        self.replies, self.prompt = list(replies), prompt

    def prompt_tokens(self, messages, tools):
        return self.prompt

    def generate(self, messages, tools, max_new_tokens=1024):
        return self.replies.pop(0), {"prompt_tokens": self.prompt, "completion_tokens": 10, "seconds": 0.5}


def _tools():
    async def graph_call(**arguments):
        return ToolResult("graph says pkg/a.py", [("pkg/a.py", 1, 2)])
    return {"read_file": lambda path, start=1, end=None: ToolResult("4: def g():", [("pkg/b.py", 4, 5)]),
            "get_callers": graph_call}


def _run(replies, **limits):
    return anyio.run(lambda: run_task(FakeModel(replies), _tools(), [], ROW, **limits))


def test_loop_calls_tools_then_scores_the_final_answer():
    result = _run(['<tool_call>{"name": "read_file", "arguments": {"path": "pkg/b.py"}}</tool_call>',
                   '<tool_call>{"name": "get_callers", "arguments": {"symbol_id": "x"}}</tool_call>', ANSWER])
    assert result["status"] == "OK" and [c["name"] for c in result["tool_calls"]] == ["read_file", "get_callers"]
    metrics = score_nav(result, ROW, SOURCES)
    assert metrics["function_recall@5"] == 1.0 and metrics["file_recall@1"] == 0.5
    assert metrics["seen_frontier_recall"] == 1.0 and metrics["seen_all_gold_files"] == 1
    assert metrics["non_gold_files_read"] == 0 and metrics["tool_calls"] == 2


def test_unknown_tool_and_bad_json_are_reported_not_fatal():
    result = _run(['<tool_call>{"name": "rm", "arguments": {}}</tool_call><tool_call>{bad</tool_call>', ANSWER])
    assert result["status"] == "OK" and all(call["error"] for call in result["tool_calls"])


def test_no_final_answer_after_max_calls_keeps_the_task():
    call = '<tool_call>{"name": "read_file", "arguments": {"path": "pkg/c.py"}}</tool_call>'
    result = _run([call, call, "still thinking"], max_calls=2)
    assert result["status"] == "NO_ANSWER"
    metrics = score_nav(result, ROW, SOURCES)
    assert metrics["function_recall@5"] == 0.0 and metrics["status"] == "NO_ANSWER"


def test_full_context_stops_the_loop():
    result = anyio.run(lambda: run_task(FakeModel([ANSWER], prompt=20000), _tools(), [], ROW, max_context_tokens=16000))
    assert result["status"] == "CONTEXT_FULL" and result["answer"] is None


def test_nav_table_lists_each_arm(tmp_path):
    import json
    for arm, recall in (("base", 0.0), ("graph_v0", 1.0)):
        (tmp_path / arm).mkdir()
        (tmp_path / arm / "t.json").write_text(json.dumps({"status": "OK", "metrics": {
            "function_recall@5": recall, "status": "OK", "tool_calls": 3}}), encoding="utf-8")
    (tmp_path / "audit").mkdir()   # the MCP audit logs live next to the arms and are not an arm
    table = nav_table(tmp_path)
    assert "| audit |" not in table
    assert "| graph_v0 | 1 |" in table and "1.000" in table
    # answer ranking at @1, 3, 5, 10, 20 in one table, navigation and cost in a second
    assert table.count("| arm | n | status |") == 2
    for k in (1, 3, 5, 10, 20):
        assert f"file_recall@{k}" in table and f"function_recall@{k}" in table
    assert "tool_calls" in table


def test_graph_v1_arm_is_known_and_graph_conf_is_gone():
    from baseline.nav.run_nav import ARMS, PROPOSAL_ARMS
    assert ARMS["graph_v1"] == "base" and "graph_v1" in PROPOSAL_ARMS and "graph_conf" not in ARMS


def test_graph_v1_b3000_is_graph_v1_with_a_3000_token_context_budget():
    from baseline.nav.run_nav import ARM_CONTEXT_BUDGET, ARMS, PROPOSAL_ARMS
    assert ARMS["graph_v1_b3000"] == "base" and "graph_v1_b3000" in PROPOSAL_ARMS
    assert ARM_CONTEXT_BUDGET["graph_v1_b3000"] == 3000 and "graph_v1" not in ARM_CONTEXT_BUDGET


def test_graph_v1_n100_is_graph_v1_with_a_100_candidate_server_limit():
    from baseline.nav.run_nav import (
        ARM_CONTEXT_BUDGET,
        ARM_SERVER_ENV,
        ARMS,
        PROPOSAL_ARMS,
    )
    assert ARMS["graph_v1_n100"] == "base" and "graph_v1_n100" in PROPOSAL_ARMS
    assert ARM_SERVER_ENV == {"graph_v1_n100": {"VGAR_RETRIEVAL_MAX_CANDIDATES": "100"}}
    assert "graph_v1_n100" not in ARM_CONTEXT_BUDGET


def test_each_layer_build_has_a_free_tool_arm_and_a_proposal_arm():
    from baseline.nav.run_nav import ARMS, PROPOSAL_ARMS
    for build in ("scip", "scip_lsp", "full"):
        assert ARMS[f"graph_v0_{build}"] == build and f"graph_v0_{build}" not in PROPOSAL_ARMS
        assert ARMS[f"graph_v1_{build}"] == build and f"graph_v1_{build}" in PROPOSAL_ARMS


def test_run_task_uses_the_given_prompt():
    seen = []

    class Recording(FakeModel):
        def generate(self, messages, tools, max_new_tokens=1024):
            seen.append([dict(message) for message in messages])
            return super().generate(messages, tools, max_new_tokens)

    anyio.run(lambda: run_task(Recording([ANSWER]), _tools(), [], ROW, prompt=("SYSTEM TEXT", "USER TEXT")))
    assert seen[0][:2] == [{"role": "system", "content": "SYSTEM TEXT"}, {"role": "user", "content": "USER TEXT"}]


def test_a_task_that_cannot_be_prepared_is_recorded_and_the_run_goes_on(tmp_path, monkeypatch):
    import json

    import baseline.nav.model as model_module
    import baseline.run_offline as offline
    from baseline.nav.run_nav import main

    monkeypatch.setattr(model_module, "QwenModel", lambda *args, **kwargs: FakeModel([ANSWER]))
    tried = []

    def prepare(root, row):
        tried.append(row["instance_id"])
        raise OSError("archive download failed")

    monkeypatch.setattr(offline, "prepare_task", prepare)
    (tmp_path / "p.diff").write_text(PATCH, encoding="utf-8")
    ids = ["astropy__astropy-13033", "django__django-10914"]
    manifest = {"split": "dev", "tasks": [{"instance_id": i, "split": "dev", "repo": "o/r", "base_commit": "a" * 40,
                                           "problem_statement": "g is wrong", "gold_patch_path": "p.diff"} for i in ids]}
    (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert main([str(tmp_path), str(tmp_path / "m.json"), "--out", str(tmp_path / "out"), "--arms", "base"]) == 0
    assert tried == ids
    for instance_id in ids:
        saved = json.loads((tmp_path / "out" / "base" / f"{instance_id}.json").read_text(encoding="utf-8"))
        assert saved["status"] == "ERROR" and "archive download failed" in saved["reason"]
        assert saved["metrics"]["status"] == "ERROR"


def _result(answer, calls=(), spans=()):
    return {"status": "OK", "answer": answer, "tool_calls": list(calls), "spans": list(spans),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "seconds": 0.0}}


def test_dotted_function_names_without_a_path_are_scored():
    answer = {"files": [], "functions": ["pkg.a.f", "pkg.b.g"]}
    assert score_nav(_result(answer), ROW, SOURCES)["function_recall@5"] == 1.0


def test_path_with_a_single_colon_is_read_like_path_double_colon():
    """graph_v1 answers copy the context's ``path:qualname`` shape (nav_v3: 9 of 62 answers)."""
    answer = {"files": [], "functions": ["pkg/b.py:pkg.b.g", "pkg/a.py:f"]}
    assert score_nav(_result(answer), ROW, SOURCES)["function_recall@5"] == 1.0


def test_only_read_file_calls_count_as_files_read():
    calls = [{"name": "grep", "arguments": {"pattern": "x"}, "seconds": 0.1},
             {"name": "read_file", "arguments": {"path": "pkg/c.py"}, "seconds": 0.1},
             {"name": "read_file", "arguments": {"path": "./pkg/a.py", "start": 1}, "seconds": 0.1}]
    spans = [("pkg/c.py", 1, 1), ("pkg/__init__.py", 1, 1), ("pkg/x.py", 3, 3)]   # grep hits are not reads
    metrics = score_nav(_result({"files": [], "functions": []}, calls, spans), ROW, SOURCES)
    assert metrics["non_gold_files_read"] == 1 and metrics["files_read"] == 2


def test_rescore_reads_again_an_answer_the_old_parser_missed(tmp_path, monkeypatch):
    import json

    import baseline.run_offline as offline
    from baseline.nav.run_nav import main

    monkeypatch.setattr(offline, "prepare_task", lambda root, row: (dict(SOURCES), tmp_path))
    (tmp_path / "p.diff").write_text(PATCH, encoding="utf-8")
    instance = "astropy__astropy-13033"
    manifest = {"split": "dev", "tasks": [{"instance_id": instance, "split": "dev", "repo": "o/r", "base_commit": "a" * 40,
                                           "problem_statement": "g is wrong", "gold_patch_path": "p.diff"}]}
    (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
    saved = tmp_path / "out" / "base" / f"{instance}.json"
    saved.parent.mkdir(parents=True)
    missed = _result(None) | {"status": "BAD_ANSWER", "ended_by": "answer", "turns": ['Uses f"{x}" here.\n' + ANSWER]}
    saved.write_text(json.dumps(missed), encoding="utf-8")
    assert main([str(tmp_path), str(tmp_path / "m.json"), "--out", str(tmp_path / "out"), "--arms", "base",
                 "--rescore"]) == 0
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["status"] == "OK" and data["answer"]["files"] == ["pkg/b.py", "pkg/a.py"]
    assert data["metrics"]["status"] == "OK" and data["metrics"]["function_recall@5"] == 1.0


def test_rescore_updates_saved_metrics_without_loading_the_model(tmp_path, monkeypatch):
    import json

    import baseline.nav.model as model_module
    import baseline.run_offline as offline
    from baseline.nav.run_nav import main

    def no_model(*args, **kwargs):
        raise AssertionError("the model must not load when rescoring")

    monkeypatch.setattr(model_module, "QwenModel", no_model)
    monkeypatch.setattr(offline, "prepare_task", lambda root, row: (dict(SOURCES), tmp_path))
    (tmp_path / "p.diff").write_text(PATCH, encoding="utf-8")
    instance = "astropy__astropy-13033"
    manifest = {"split": "dev", "tasks": [{"instance_id": instance, "split": "dev", "repo": "o/r", "base_commit": "a" * 40,
                                           "problem_statement": "g is wrong", "gold_patch_path": "p.diff"}]}
    (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
    saved = tmp_path / "out" / "base" / f"{instance}.json"
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps(_result({"files": [], "functions": ["pkg.a.f"]}) | {"metrics": {"stale": 1}}),
                     encoding="utf-8")
    assert main([str(tmp_path), str(tmp_path / "m.json"), "--out", str(tmp_path / "out"), "--arms", "base",
                 "--rescore"]) == 0
    metrics = json.loads(saved.read_text(encoding="utf-8"))["metrics"]
    assert "stale" not in metrics and metrics["function_recall@5"] == 0.5


def test_near_the_context_limit_the_model_is_asked_to_answer():
    result = anyio.run(lambda: run_task(FakeModel([ANSWER], prompt=15000), _tools(), [], ROW, max_context_tokens=16000))
    assert result["status"] == "OK" and result["ended_by"] == "context_limit" and result["answer"]["files"]


def test_a_task_past_its_time_limit_stops_with_timeout():
    result = anyio.run(lambda: run_task(FakeModel([ANSWER]), _tools(), [], ROW, max_seconds=0))
    assert result["status"] == "TIMEOUT" and result["ended_by"] == "time_limit"


def test_each_tool_call_logs_what_the_model_saw_and_the_raw_server_answer():
    raw = {"status": "PASS", "data": {"diagnostics": {"candidates": [{"node_id": "n", "relevance_score": 0.7}]}}}

    async def graph_call(**arguments):
        return ToolResult("rendered context", [("pkg/a.py", 1, 2)], raw=raw)

    tools = {"get_related_context": graph_call,
             "read_file": lambda path, start=1, end=None: ToolResult("4: def g():", [("pkg/b.py", 4, 5)])}
    replies = ['<tool_call>{"name": "get_related_context", "arguments": {"anchor_ids": ["n"]}}</tool_call>',
               '<tool_call>{"name": "read_file", "arguments": {"path": "pkg/b.py"}}</tool_call>', ANSWER]
    result = anyio.run(lambda: run_task(FakeModel(replies), tools, [], ROW))
    context, read = result["tool_calls"]
    assert context["result"] == "rendered context" and context["raw"] == raw
    assert read["result"] == "4: def g():" and "raw" not in read


def test_the_loop_keeps_the_longer_cap_of_related_context():
    long_context = "x" * (1800 * 4)   # 1800 tokens: above the 1500 default, below the 2000 context cap

    async def graph_call(**arguments):
        return ToolResult(long_context, [])

    replies = ['<tool_call>{"name": "get_related_context", "arguments": {"anchor_ids": ["n"]}}</tool_call>', ANSWER]
    result = anyio.run(lambda: run_task(FakeModel(replies), {"get_related_context": graph_call}, [], ROW))
    assert result["tool_calls"][0]["result"] == long_context   # not cut again to 1500


def test_a_larger_context_cap_keeps_a_larger_related_context():
    long_context = "x" * (3500 * 4)   # a 3000-token budget plus item headers

    async def graph_call(**arguments):
        return ToolResult(long_context, [])

    replies = ['<tool_call>{"name": "get_related_context", "arguments": {"anchor_ids": ["n"]}}</tool_call>', ANSWER]
    result = anyio.run(lambda: run_task(FakeModel(replies), {"get_related_context": graph_call}, [], ROW,
                                        context_cap=4000))
    assert result["tool_calls"][0]["result"] == long_context


def test_resume_reruns_errored_tasks_but_keeps_finished_ones(tmp_path, monkeypatch):
    import json

    import baseline.nav.model as model_module
    import baseline.run_offline as offline
    from baseline.nav.run_nav import main

    monkeypatch.setattr(model_module, "QwenModel", lambda *args, **kwargs: FakeModel([ANSWER, ANSWER]))
    monkeypatch.setattr(offline, "prepare_task", lambda root, row: (dict(SOURCES), tmp_path))
    (tmp_path / "p.diff").write_text(PATCH, encoding="utf-8")
    ids = ["astropy__astropy-13033", "django__django-10914"]
    manifest = {"split": "dev", "tasks": [{"instance_id": i, "split": "dev", "repo": "o/r", "base_commit": "a" * 40,
                                           "problem_statement": "g is wrong", "gold_patch_path": "p.diff"} for i in ids]}
    (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "out" / "base"
    out.mkdir(parents=True)
    (out / f"{ids[0]}.json").write_text(json.dumps({"status": "ERROR", "reason": "CUDA error: out of memory"}))
    (out / f"{ids[1]}.json").write_text(json.dumps({"status": "OK", "sentinel": True}))
    assert main([str(tmp_path), str(tmp_path / "m.json"), "--out", str(tmp_path / "out"), "--arms", "base",
                 "--resume"]) == 0
    assert json.loads((out / f"{ids[0]}.json").read_text())["status"] == "OK"     # errored run done again
    assert json.loads((out / f"{ids[1]}.json").read_text()).get("sentinel")       # finished run kept
