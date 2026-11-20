"""T2 tools: file tools for every arm, graph tools over the MCP server (spec 2026-11-19 §8)."""
import anyio

from baseline.nav.tools import FileTools, GraphTools, cap_tokens
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore


def _tree(tmp_path):
    tree = tmp_path / "tree"
    (tree / "pkg").mkdir(parents=True)
    (tree / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tree / "pkg" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tree / "pkg" / "b.py").write_text("from pkg.a import f\n\n\ndef g():\n    return f()\n", encoding="utf-8")
    return tree


def test_read_file_refuses_paths_outside_the_tree(tmp_path):
    tools = FileTools(_tree(tmp_path))
    (tmp_path / "secret.py").write_text("token = 1\n", encoding="utf-8")
    outside = tools.read_file("../secret.py")
    assert "refused" in outside.text and outside.spans == []
    assert tools.read_file(str(tmp_path / "secret.py")).spans == []


def test_read_file_and_grep_record_what_they_showed(tmp_path):
    tools = FileTools(_tree(tmp_path))
    shown = tools.read_file("pkg/b.py", 4, 5)
    assert shown.spans == [("pkg/b.py", 4, 5)] and "return f()" in shown.text
    found = tools.grep(r"def g")
    assert "pkg/b.py:4" in found.text and ("pkg/b.py", 4, 4) in found.spans
    assert "bad pattern" in tools.grep("(").text
    assert "pkg/" in tools.list_dir(".").text
    assert {schema["function"]["name"] for schema in tools.schemas()} == {"grep", "read_file", "list_dir"}


def test_cap_tokens_marks_truncation():
    assert cap_tokens("x" * 10000, 100).endswith("[truncated]") and cap_tokens("short") == "short"


def test_graph_tools_prebind_version_and_task(tmp_path):
    tree = _tree(tmp_path)
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    db = tmp_path / "g.db"
    store = SQLiteGraphStore(db)
    store.initialize()
    store.ingest(document)

    async def scenario():
        async with GraphTools(tree, db, document["graph_version"], "o__r-1", tmp_path / "audit.jsonl") as tools:
            schemas = tools.schemas()
            names = {schema["function"]["name"] for schema in schemas}
            props = [schema["function"]["parameters"].get("properties", {}) for schema in schemas]
            found = await tools.call("search_symbols", {"query": "f"})
            unknown = await tools.call("delete_everything", {})
            return names, props, found, unknown

    names, props, found, unknown = anyio.run(scenario)
    assert names == set(GraphTools.TOOLS)
    assert all("graph_version" not in p and "task_id" not in p for p in props)
    assert "pkg/a.py" in found.text and "unknown tool" in unknown.text
    assert "request_id" not in found.text   # the server envelope's metadata is not shown to the model


def test_graph_conf_adds_edge_confidence_and_sorts_callers(tmp_path):
    import json
    import sqlite3

    tree = _tree(tmp_path)
    (tree / "pkg" / "c.py").write_text("from pkg.a import f\n\n\ndef h():\n    return f()\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    db = tmp_path / "g.db"
    store = SQLiteGraphStore(db)
    store.initialize()
    store.ingest(document)
    with sqlite3.connect(db) as connection:   # g's call weaker than h's, so the order must flip
        connection.execute("UPDATE edges SET confidence = CASE WHEN source_id LIKE '%pkg.b.g%' THEN 0.7 ELSE 0.9 END "
                           "WHERE type = 'CALLS'")
    f_id = "vgar:o__r:python:function:pkg/a.py:pkg.a.f"

    async def callers(with_confidence):
        async with GraphTools(tree, db, document["graph_version"], "o__r-1", tmp_path / "a.jsonl",
                              with_confidence=with_confidence) as tools:
            return json.loads((await tools.call("get_callers", {"symbol_id": f_id})).text)["data"]["callers"]

    plain = anyio.run(callers, False)
    rich = anyio.run(callers, True)
    assert all("edge_confidence" not in item for item in plain)
    assert [item["name"] for item in rich] == ["h", "g"] and [item["edge_confidence"] for item in rich] == [0.9, 0.7]
    assert rich[0]["edge_source_tool"] == "vgar-python-graph-builder"


def test_a_graph_call_past_the_timeout_disables_graph_tools_for_the_task(tmp_path):
    from types import SimpleNamespace

    class SlowSession:
        def __init__(self):
            self.calls = 0

        async def call_tool(self, name, arguments, read_timeout_seconds=None):
            self.calls += 1
            raise TimeoutError(f"no reply within {read_timeout_seconds} s")

    tools = GraphTools(tmp_path, tmp_path / "g.db", "v", "t", tmp_path / "a.jsonl", timeout_seconds=300)
    tools._session = SlowSession()
    tools._tools = {"get_callers": SimpleNamespace(input_schema={"properties": {"symbol_id": {}}}, description="")}
    first = anyio.run(tools.call, "get_callers", {"symbol_id": "x"})
    second = anyio.run(tools.call, "get_callers", {"symbol_id": "y"})
    assert "timed out" in first.text and "300" in first.text
    assert "unavailable" in second.text and tools._session.calls == 1


def test_related_context_fits_the_tool_result_cap(tmp_path):

    tree = _tree(tmp_path)
    body = "".join(f"    value_{i} = compute_value({i}, 'padding text to make the function long')\n" for i in range(40))
    (tree / "pkg" / "big.py").write_text(
        "".join(f"def big_{n}():\n{body}    return value_0\n\n\n" for n in range(12)), encoding="utf-8")
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    db = tmp_path / "g.db"
    store = SQLiteGraphStore(db)
    store.initialize()
    store.ingest(document)
    anchors = [n["id"] for n in document["nodes"] if n["type"] == "Function" and n["path"] == "pkg/big.py"]

    async def scenario():
        async with GraphTools(tree, db, document["graph_version"], "o__r-1", tmp_path / "a.jsonl") as tools:
            return await tools.call("get_related_context", {"anchor_ids": anchors, "issue_text": "big value"})

    result = anyio.run(scenario)
    assert "[truncated]" not in result.text and "--- BEGIN SOURCE" in result.text   # compact text, not escaped JSON
    assert "diagnostics" not in result.text and "content_hash" not in result.text
    assert result.spans   # it still records the code it showed
    candidate = result.raw["data"]["diagnostics"]["candidates"][0]   # the full server answer is kept for the log
    assert {"features", "relevance_score", "graph_rationale"} <= set(candidate)


def test_task_anchors_are_shown_compactly_without_overlay_internals(tmp_path):
    import json

    tree = _tree(tmp_path)
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    db = tmp_path / "g.db"
    store = SQLiteGraphStore(db)
    store.initialize()
    store.ingest(document)

    async def scenario():
        async with GraphTools(tree, db, document["graph_version"], "o__r-1", tmp_path / "a.jsonl") as tools:
            return await tools.call("find_task_anchors", {"issue_text": "g returns the wrong value from f in pkg/b.py"})

    shown = json.loads(anyio.run(scenario).text)
    assert "trace_edges" not in json.dumps(shown) and shown["anchor_count"] >= len(shown["anchors"]) > 0
    first = shown["anchors"][0]
    assert set(first) == {"node_id", "path", "symbol", "score", "evidence"} and isinstance(first["evidence"], list)
    assert [a["score"] for a in shown["anchors"]] == sorted((a["score"] for a in shown["anchors"]), reverse=True)


def test_a_catastrophic_grep_pattern_times_out_instead_of_hanging(tmp_path):
    import time

    tree = _tree(tmp_path)
    (tree / "pkg" / "slow.py").write_text("x = '" + "a" * 40 + "b'\n", encoding="utf-8")
    tools = FileTools(tree, grep_timeout=2)
    started = time.perf_counter()
    result = tools.grep(r"(a+)+$")
    assert "timed out" in result.text and time.perf_counter() - started < 20
    assert "pkg/b.py:4" in tools.grep(r"def g").text   # the next call still works
