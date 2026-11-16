"""Impact flags (spec 2026-11-15 §3): A follows reader edges, B narrows with Joern dataflow; both off by default."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_code_graph_builder import READY
from test_code_graph_builder import SOURCE as FLOW_SOURCE
from test_variable_refs import APP_FACTS, OTHER_FACTS
from test_variable_refs import OTHER as OTHER_SOURCE
from test_variable_refs import SOURCE as APP_SOURCE

from vgar.graph import joern_runner, tsg_extractor
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.impact import analyze_patch_impact
from vgar.graph.joern_runner import JoernConfig
from vgar.graph.tsg_extractor import TsgConfig
from vgar.repair.patch import PatchPolicy


def _diff(path: str, old: str, new: str, line: int) -> str:
    return f"--- a/{path}\n+++ b/{path}\n@@ -{line} +{line} @@\n-{old}\n+{new}\n"


@pytest.fixture
def app(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(APP_SOURCE, encoding="utf-8")
    (root / "src" / "other.py").write_text(OTHER_SOURCE, encoding="utf-8")
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file",
                        lambda config, r, path: {"src/app.py": APP_FACTS, "src/other.py": OTHER_FACTS}[path])
    tsg = TsgConfig(executable=tmp_path / "tsg", tree_sitter_dir=tmp_path)
    document = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev", tsg=tsg).build(root)
    return root, document


def _impact(root, document, diff, **flags):
    policy = PatchPolicy(("src/app.py", "src/other.py"), ())
    return analyze_patch_impact(diff, document, root, patch_policy=policy, **flags)


def _items(report) -> set[tuple[str, str]]:
    return {(item.qualified_name, item.relation) for item in report.impacted.items}


LIMIT_DIFF = _diff("src/app.py", "LIMIT = 10", "LIMIT = 11", 1)


def test_defaults_identical_to_before(app):
    root, document = app
    off = _impact(root, document, LIMIT_DIFF)
    assert "extensions" not in json.loads(off.canonical_json())["impacted"]
    assert not any(relation in {"READS_CHANGED_VARIABLE", "SHARES_STATE"} for _, relation in _items(off))


def test_global_change_reports_readers(app):
    root, document = app
    report = _impact(root, document, LIMIT_DIFF, follow_variable_readers=True)
    readers = {name for name, relation in _items(report) if relation == "READS_CHANGED_VARIABLE"}
    assert readers == {"app.Cart.add", "app.bump", "app.outer", "other.use"}
    extensions = json.loads(report.canonical_json())["impacted"]["extensions"]
    assert extensions["flags"] == {"follow_variable_readers": True}
    assert extensions["variable_seeds"] == ["vgar:t/repo:python:globalvariable:src/app.py:app.LIMIT"]


def test_field_change_reports_readers(app):
    root, document = app
    report = _impact(root, document, _diff("src/app.py", "    size = 0", "    size = 1", 3), follow_variable_readers=True)
    assert ("app.Cart.add", "READS_CHANGED_VARIABLE") in _items(report)


def test_writer_reports_readers_one_hop(app):
    root, document = app
    diff = _diff("src/app.py", "    LIMIT = LIMIT + 1", "    LIMIT = LIMIT + 2", 11)
    report = _impact(root, document, diff, follow_variable_readers=True)
    shared = {name for name, relation in _items(report) if relation == "SHARES_STATE"}
    assert shared == {"app.Cart.add", "app.outer", "other.use"}
    assert all(item.hops == 1 for item in report.impacted.items if item.relation == "SHARES_STATE")


def test_module_change_without_variable_adds_nothing(app):
    root, document = app
    diff = "--- a/src/other.py\n+++ b/src/other.py\n@@ -1 +1 @@\n-from app import LIMIT\n+from app import LIMIT  # noqa\n"
    off, on = _impact(root, document, diff), _impact(root, document, diff, follow_variable_readers=True)
    assert [u.reason for u in on.unmapped] == ["MODULE_LEVEL_CHANGE"]
    assert _items(on) == _items(off)
    assert json.loads(on.canonical_json())["impacted"]["extensions"]["variable_seeds"] == []


# --- B: dataflow narrowing, with the recorded Joern run of tests/fixtures/joern/flow_cases.py ------------

@pytest.fixture
def flow(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "flow_cases.py").write_bytes(FLOW_SOURCE + b"\n\ndef caller():\n    return checked(1)\n")
    monkeypatch.setattr(joern_runner, "run_joern", lambda r, files, config: READY)
    document = PythonGraphBuilder(repo_key="demo/flow", repository_revision="base", source_roots=(".",),
                                  joern=JoernConfig()).build(root)
    return root, document


def _flow_impact(root, document, diff, **flags):
    return analyze_patch_impact(diff, document, root, patch_policy=PatchPolicy(("flow_cases.py",), ()), **flags)


RESULT_LINE = next(n for n, text in enumerate(FLOW_SOURCE.decode().splitlines(), 1) if text == "    result = value + 1")
RESULT_DIFF = _diff("flow_cases.py", "    result = value + 1", "    result = value + 2", RESULT_LINE)


def test_change_reaching_return_is_not_narrowed(flow):
    root, document = flow
    report = _flow_impact(root, document, RESULT_DIFF, narrow_with_dataflow=True)
    assert any(name.endswith(".caller") for name, relation in _items(report) if relation == "CALLS")
    assert json.loads(report.canonical_json())["impacted"]["extensions"]["narrowed_by_dataflow"] == []


def test_change_that_reaches_no_effect_is_narrowed(flow):
    root, document = flow
    # Cut the return's dependence on `result`: the changed statement then reaches nothing that leaves the function.
    changed = next(n["id"] for n in document["nodes"] if n["type"] == "Statement" and n["id"].endswith(".checked::expression#1"))
    document = dict(document, edges=[e for e in document["edges"]
                                     if not (e["type"] == "DATA_DEPENDS_ON" and e["target_id"] == changed)])
    report = _flow_impact(root, document, RESULT_DIFF, narrow_with_dataflow=True)
    assert not any(name.endswith(".caller") for name, _ in _items(report))
    extensions = json.loads(report.canonical_json())["impacted"]["extensions"]
    assert extensions["narrowed_by_dataflow"] and extensions["narrowed_by_dataflow"][0].endswith(".checked")


def test_no_code_graph_falls_back_and_counts(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "flow_cases.py").write_bytes(FLOW_SOURCE + b"\n\ndef caller():\n    return checked(1)\n")
    document = PythonGraphBuilder(repo_key="demo/flow", repository_revision="base", source_roots=(".",)).build(root)
    report = _flow_impact(root, document, RESULT_DIFF, narrow_with_dataflow=True)
    assert any(name.endswith(".caller") for name, _ in _items(report))
    assert json.loads(report.canonical_json())["impacted"]["extensions"]["dataflow_fallbacks"] == 1


def test_service_reads_env_flags(monkeypatch):
    from vgar.graph.sqlite_service import impact_flags_from_env

    monkeypatch.setenv("VGAR_IMPACT_FOLLOW_VARIABLE_READERS", "1")
    monkeypatch.delenv("VGAR_IMPACT_NARROW_WITH_DATAFLOW", raising=False)
    assert impact_flags_from_env() == {"follow_variable_readers": True, "narrow_with_dataflow": False}


def test_flow_fixture_source_has_result_line():
    assert RESULT_LINE > 0 and Path  # guard for the line lookup above


# --- final review fixes ------------------------------------------------------------------------------

SHARED = "LIMIT = 1\ndef bump():\n    global LIMIT\n    LIMIT = 2\ndef outer():\n    return LIMIT\ndef go():\n    return outer()\n"


def test_flag_a_only_adds_to_the_default_walk(tmp_path, monkeypatch):
    from vgar.graph.tsg_extractor import TsgFileFacts

    def fact(type_, name, line, end_line, end_col):
        return {"type": type_, "name": name, "line": line, "col": 0, "end_line": end_line, "end_col": end_col}

    facts = TsgFileFacts(nodes={0: {"type": "Discard"}, 1: fact("GlobalVariable", "LIMIT", 1, 1, 9),
                                2: fact("Function", "bump", 2, 4, 13), 3: fact("Function", "outer", 5, 6, 16),
                                4: fact("Function", "go", 7, 8, 18)},
                         edges=[(0, 2, "HAS_METHOD"), (0, 3, "HAS_METHOD"), (0, 4, "HAS_METHOD")])
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "x.py").write_text(SHARED, encoding="utf-8")
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, r, path: facts)
    document = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev",
                                  tsg=TsgConfig(executable=tmp_path / "tsg", tree_sitter_dir=tmp_path)).build(root)
    diff = ("--- a/src/x.py\n+++ b/src/x.py\n@@ -4 +4 @@\n-    LIMIT = 2\n+    LIMIT = 3\n"
            "@@ -6 +6 @@\n-    return LIMIT\n+    return LIMIT + 0\n")
    policy = PatchPolicy(("src/x.py",), ())
    off = analyze_patch_impact(diff, document, root, patch_policy=policy)
    on = analyze_patch_impact(diff, document, root, patch_policy=policy, follow_variable_readers=True)
    assert {i.node_id for i in off.impacted.items} <= {i.node_id for i in on.impacted.items}
    assert any(i.qualified_name == "x.go" for i in on.impacted.items)


def test_insertion_is_not_narrowed(flow):
    root, document = flow
    diff = (f"--- a/flow_cases.py\n+++ b/flow_cases.py\n@@ -{RESULT_LINE},0 +{RESULT_LINE + 1} @@\n"
            "+    notify(result)\n")
    report = _flow_impact(root, document, diff, narrow_with_dataflow=True)
    extensions = json.loads(report.canonical_json())["impacted"]["extensions"]
    assert extensions["narrowed_by_dataflow"] == [] and extensions["dataflow_fallbacks"] == 1
    assert any(name.endswith(".caller") for name, _ in _items(report))


def test_statements_without_effects_key_fall_back(flow):
    root, document = flow
    changed = next(n["id"] for n in document["nodes"] if n["type"] == "Statement" and n["id"].endswith(".checked::expression#1"))
    nodes = [dict(n, properties={k: v for k, v in n["properties"].items() if k != "effects"})
             if n["type"] == "Statement" else n for n in document["nodes"]]
    edges = [e for e in document["edges"] if not (e["type"] == "DATA_DEPENDS_ON" and e["target_id"] == changed)]
    report = _flow_impact(root, dict(document, nodes=nodes, edges=edges), RESULT_DIFF, narrow_with_dataflow=True)
    extensions = json.loads(report.canonical_json())["impacted"]["extensions"]
    assert extensions["narrowed_by_dataflow"] == [] and extensions["dataflow_fallbacks"] == 1


# --- minor fixes 1 (15/11) ---------------------------------------------------------------------------

def test_reader_edges_respect_min_confidence(app):
    root, document = app
    policy = PatchPolicy(("src/app.py", "src/other.py"), ())
    strict = analyze_patch_impact(LIMIT_DIFF, document, root, patch_policy=policy, follow_variable_readers=True,
                                  min_confidence=0.9)
    readers = {i.qualified_name for i in strict.impacted.items if i.relation == "READS_CHANGED_VARIABLE"}
    assert "other.use" not in readers and "app.bump" in readers  # the imported read is heuristic (0.8)


def test_unsupported_references_note_when_flag_a_on(app):
    root, document = app
    off = {u.relation for u in _impact(root, document, LIMIT_DIFF).impacted.unsupported}
    on = {u.relation for u in _impact(root, document, LIMIT_DIFF, follow_variable_readers=True).impacted.unsupported}
    assert "REFERENCES" in off
    assert "REFERENCES" not in on and "REFERENCES (except python.layer1.reads.v1)" in on


def test_narrowed_function_adds_no_depends_on(tmp_path, monkeypatch):
    # user.py calls looped (not checked): its component DEPENDS_ON flow_cases only. Once B narrows checked, that
    # dependent component must go too (narrowed seeds do not feed seed_components).
    root = tmp_path / "repo"
    root.mkdir()
    (root / "flow_cases.py").write_bytes(FLOW_SOURCE)
    (root / "user.py").write_text("from flow_cases import looped\n\n\ndef use():\n    return looped([])\n",
                                  encoding="utf-8")
    monkeypatch.setattr(joern_runner, "run_joern", lambda r, files, config: READY)
    document = PythonGraphBuilder(repo_key="demo/flow", repository_revision="base", source_roots=(".",),
                                  joern=JoernConfig()).build(root)
    policy = PatchPolicy(("flow_cases.py", "user.py"), ())
    plain = analyze_patch_impact(RESULT_DIFF, document, root, patch_policy=policy)
    assert ("user", "DEPENDS_ON") in _items(plain)
    changed = next(n["id"] for n in document["nodes"] if n["type"] == "Statement" and n["id"].endswith(".checked::expression#1"))
    document = dict(document, edges=[e for e in document["edges"]
                                     if not (e["type"] == "DATA_DEPENDS_ON" and e["target_id"] == changed)])
    report = analyze_patch_impact(RESULT_DIFF, document, root, patch_policy=policy, narrow_with_dataflow=True)
    assert json.loads(report.canonical_json())["impacted"]["extensions"]["narrowed_by_dataflow"]
    assert not any(relation == "DEPENDS_ON" for _, relation in _items(report))
