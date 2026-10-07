from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from vgar.contracts.error import GraphError
from vgar.evaluation.retrieval.scoring import CorpusIndex, graph_rank
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever


def write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def builder() -> PythonGraphBuilder:
    return PythonGraphBuilder(repo_key="test/bindings", repository_revision="fixture", use_jedi=False)


def retrieve(document: dict, root: Path, name: str):
    anchor = next(n["id"] for n in document["nodes"] if n["name"] == name and n["type"] == "Function")
    return GraphContextRetriever(document, root, count_tokens=lambda text: len(text.split()),
                                 counter_label="test-whitespace").retrieve([anchor], 1000)


def fail_after_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    original = PythonGraphBuilder._walk_scope

    def fail(self, node, source, module, **kwargs):
        result = original(self, node, source, module, **kwargs)
        if module.path == "bad.py" and kwargs["parent_type"] == "Module":
            raise RuntimeError("induced post-extraction failure")
        return result

    monkeypatch.setattr(PythonGraphBuilder, "_walk_scope", fail)


def failed_graph(root: Path, monkeypatch: pytest.MonkeyPatch):
    write(root, "bad.py", "from typing import overload\nclass Bad: pass\n"
          "@overload\ndef broken(a: int): ...\n"
          "def broken(a):\n    return broken(a)\n")
    write(root, "good.py", "def ok():\n    return 1\n")
    fail_after_extraction(monkeypatch)
    instance = builder()
    return instance, instance.build(root)


def test_failed_file_rollback_removes_all_auxiliary_state(tmp_path, monkeypatch):
    instance, document = failed_graph(tmp_path, monkeypatch)
    ids = {n["id"] for n in document["nodes"]}
    assert all(value in ids for value in instance.symbols_by_qualified_name.values())
    assert all(c.node_id in ids for c in instance.calls + instance.classes)
    assert not any(name == "bad" or name.startswith("bad.") for name in instance.scope_tables)
    assert not any(name == "bad" or name.startswith("bad.") for name in instance.scope_parents)
    assert "bad" not in instance.modules
    assert document["statistics"]["skipped_overload_count"] == 0
    assert document["statistics"]["failed_file_count"] == 1


def test_good_source_can_be_retrieved_after_failed_file(tmp_path, monkeypatch):
    _, document = failed_graph(tmp_path, monkeypatch)
    before = copy.deepcopy(document)
    assert retrieve(document, tmp_path, "ok").context.items
    assert document == before
    assert set(document["statistics"]["source_inventory"]) == {"bad.py", "good.py"}
    assert not any(n.get("path") == "bad.py" for n in document["nodes"])


@pytest.mark.parametrize("change", ["modify_failed", "delete_failed", "add_source", "modify_good"])
def test_inventory_still_checks_failed_and_good_source(tmp_path, monkeypatch, change):
    _, document = failed_graph(tmp_path, monkeypatch)
    if change == "delete_failed":
        (tmp_path / "bad.py").unlink()
    elif change == "add_source":
        write(tmp_path, "added.py", "pass\n")
    else:
        write(tmp_path, "bad.py" if change == "modify_failed" else "good.py", "# modified\npass\n")
    with pytest.raises(GraphError, match="snapshot"):
        retrieve(document, tmp_path, "ok")


@pytest.mark.parametrize("inventory", [{}, {"good.py": "invalid"}, {"../outside.py": "sha256:" + "0" * 64}])
def test_malformed_inventory_cannot_weaken_file_hashes(tmp_path, inventory):
    write(tmp_path, "good.py", "def ok(): return 1\n")
    document = builder().build(tmp_path)
    document["statistics"]["source_inventory"] = inventory
    with pytest.raises(GraphError):
        retrieve(document, tmp_path, "ok")


def test_legacy_graph_without_inventory_remains_source_verified(tmp_path):
    write(tmp_path, "good.py", "def ok(): return 1\n")
    document = builder().build(tmp_path)
    document["statistics"].pop("source_inventory", None)
    assert retrieve(document, tmp_path, "ok").context.items
    write(tmp_path, "good.py", "def ok(): return 2\n")
    with pytest.raises(GraphError):
        retrieve(document, tmp_path, "ok")


@pytest.mark.parametrize("order", ["base.py", "zbase.py"])
def test_imported_base_uses_binding_before_class_assignment(tmp_path, order):
    write(tmp_path, order, "class A: pass\n")
    base = order[:-3]
    write(tmp_path, "derived.py", f"from {base} import A\nclass A(A): pass\n")
    document = builder().build(tmp_path)
    classes = {n["qualified_name"]: n["id"] for n in document["nodes"] if n["type"] == "Class"}
    inherits = [e for e in document["edges"] if e["type"] == "INHERITS"]
    assert [(e["source_id"], e["target_id"]) for e in inherits] == [(classes["derived.A"], classes[f"{base}.A"])]


def test_redefined_class_can_inherit_previous_occurrence(tmp_path):
    write(tmp_path, "local.py", "class A: pass\nclass A(A): pass\n")
    document = builder().build(tmp_path)
    classes = [n for n in document["nodes"] if n["type"] == "Class"]
    assert len(classes) == 2
    assert classes[0]["id"] != classes[1]["id"]
    assert [(e["source_id"], e["target_id"]) for e in document["edges"] if e["type"] == "INHERITS"] == [
        (classes[1]["id"], classes[0]["id"])]


@pytest.mark.parametrize("source", ["class A(A): pass\n", "class A(factory()): pass\n"])
def test_unbound_or_dynamic_base_is_unresolved_not_self_loop(tmp_path, source):
    write(tmp_path, "dynamic.py", source)
    document = builder().build(tmp_path)
    assert not any(e["type"] == "INHERITS" for e in document["edges"])
    assert document["statistics"]["unresolved_base_count"] == 1


@pytest.mark.parametrize("decorator, expected", [
    ("@value.setter", True), ("@obj.value.setter", True),
    ("@app.get('/login')", False), ("@pytest.mark.parametrize('x', [1])", False),
    ("@value.deleter", False), ("@something.setter()", False),
])
def test_only_property_setter_attribute_matches(decorator, expected):
    assert PythonGraphBuilder._is_setter_decorator([decorator]) is expected


def test_conditional_duplicate_and_nested_definitions_map_to_m2_occurrences(tmp_path):
    source = ("if FLAG:\n    def choose():\n        return 1\n"
              "else:\n    def choose():\n        return 2\n"
              "try:\n    class C:\n        def run(self):\n            return 1\n"
              "except Exception:\n    class C:\n        def run(self):\n            return 2\n"
              "def outer():\n    if FLAG:\n        def inner():\n            return 1\n"
              "    else:\n        def inner():\n            return 2\n    return inner()\n")
    write(tmp_path, "conditional.py", source)
    document = builder().build(tmp_path)
    assert document["statistics"]["failed_file_count"] == 0
    functions = [n for n in document["nodes"] if n["type"] in {"Function", "Method"}]
    assert len(functions) == 7
    assert len({n["id"] for n in functions}) == 7
    repeated = builder().build(tmp_path)
    assert [n["id"] for n in document["nodes"]] == [n["id"] for n in repeated["nodes"]]
    record = graph_rank("task", [{"node_id": n["id"]} for n in functions],
                        {n["id"]: n for n in document["nodes"]},
                        {"conditional.py": source}, CorpusIndex({"conditional.py": source}))
    assert record.unmapped == []
    assert len({item.function_id for item in record.items}) == 7
    assert next(n for n in functions if n["qualified_name"] == "conditional.choose")["id"].endswith(":conditional.choose")


def test_duplicate_scopes_do_not_share_local_binding_tables(tmp_path):
    write(tmp_path, "bindings.py", "def target(): return 1\n"
          "def caller(target):\n    return target()\n"
          "def caller():\n    return target()\n")
    document = builder().build(tmp_path)
    calls = sorted([n for n in document["nodes"] if n["type"] == "CallSite"], key=lambda n: n["range"]["start_line"])
    assert len(calls) == 2
    linked = {e["source_id"] for e in document["edges"] if e["type"] == "CALLS"}
    assert calls[0]["id"] not in linked
    assert calls[1]["id"] in linked


def test_file_hash_in_inventory_is_raw_not_snippet_hash(tmp_path):
    source = "# prefix\r\ndef ok(): return 1\r\n"
    (tmp_path / "good.py").write_bytes(source.encode())
    document = builder().build(tmp_path)
    assert document["statistics"]["source_inventory"]["good.py"] == "sha256:" + hashlib.sha256(source.encode()).hexdigest()


@pytest.mark.parametrize("source, count", [
    ("if X:\n    def f(): pass\nelif Y:\n    def f(): pass\nelse:\n    def f(): pass\n", 3),
    ("try:\n    def f(): pass\nexcept Exception:\n    def f(): pass\nelse:\n    def f(): pass\nfinally:\n    def f(): pass\n", 4),
    ("for x in y:\n    def f(): pass\nelse:\n    def f(): pass\n", 2),
    ("while x:\n    def f(): pass\nelse:\n    def f(): pass\n", 2),
    ("with lock:\n    def f(): pass\n", 1),
    ("match x:\n    case 1:\n        def f(): pass\n    case _:\n        def f(): pass\n", 2),
])
def test_compound_statement_blocks_are_discovered(tmp_path, source, count):
    write(tmp_path, "compound.py", source)
    document = builder().build(tmp_path)
    assert document["statistics"]["failed_file_count"] == 0
    assert len([n for n in document["nodes"] if n["type"] == "Function"]) == count


def test_scope_indexing_failure_is_also_transactional(tmp_path, monkeypatch):
    write(tmp_path, "bad.py", "def broken(): pass\n")
    write(tmp_path, "good.py", "def ok(): pass\n")
    original = PythonGraphBuilder._index_scopes

    def fail(self, source, module):
        original(self, source, module)
        if module.path == "bad.py":
            raise RuntimeError("induced scope index failure")

    monkeypatch.setattr(PythonGraphBuilder, "_index_scopes", fail)
    instance = builder()
    document = instance.build(tmp_path)
    assert document["statistics"]["failed_file_count"] == 1
    assert retrieve(document, tmp_path, "ok").context.items
    assert not any(key[0].startswith("bad") for key in instance.scope_locations)


def test_duplicate_definition_calls_remain_ambiguous_without_execution_proof(tmp_path):
    write(tmp_path, "ambiguous.py", "if FLAG:\n    def f(): return 1\nelse:\n    def f(): return 2\n"
          "def caller(): return f()\n")
    document = builder().build(tmp_path)
    assert len([n for n in document["nodes"] if n["type"] == "Function"]) == 3
    assert not any(e["type"] == "CALLS" for e in document["edges"])


def test_later_import_rebinds_earlier_class_before_inheritance(tmp_path):
    write(tmp_path, "base.py", "class A: pass\n")
    write(tmp_path, "derived.py", "class A: pass\nfrom base import A\nclass B(A): pass\n")
    document = builder().build(tmp_path)
    classes = {n["qualified_name"]: n["id"] for n in document["nodes"] if n["type"] == "Class"}
    assert [(e["source_id"], e["target_id"]) for e in document["edges"] if e["type"] == "INHERITS"] == [
        (classes["derived.B"], classes["base.A"])]
