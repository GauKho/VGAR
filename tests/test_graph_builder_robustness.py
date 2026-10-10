from __future__ import annotations

from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder


def _build(root: Path) -> dict:
    return PythonGraphBuilder(
        repo_key="t/repo",
        repository_revision="rev",
        source_roots=("src",),

    ).build(root)


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ids(document: dict, node_type: str) -> list[str]:
    return [n["id"] for n in document["nodes"] if n["type"] == node_type]


def test_overload_stubs_are_skipped_and_implementation_kept(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/pkg/mod.py",
        "import typing as t\n"
        "from typing import overload\n\n"
        "@overload\ndef f(a: int) -> int: ...\n"
        "@t.overload\ndef f(a: str) -> str: ...\n"
        "def f(a):\n    return a\n",
    )
    document = _build(tmp_path)
    functions = [n for n in document["nodes"] if n["type"] == "Function"]
    assert len(functions) == 1
    assert functions[0]["range"]["start_line"] == 8
    assert document["statistics"]["skipped_overload_count"] == 2


def test_property_setter_gets_distinct_stable_id(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/pkg/mod.py",
        "class A:\n"
        "    @property\n    def x(self):\n        return 1\n"
        "    @x.setter\n    def x(self, value):\n        pass\n",
    )
    document = _build(tmp_path)
    methods = _ids(document, "Method")
    assert len(methods) == 2 and len(set(methods)) == 2
    assert methods[0].endswith(":pkg.mod.A.x")  # first definition keeps plain id
    assert document["statistics"]["renamed_duplicate_count"] == 1


def test_failing_file_is_isolated_and_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "src/pkg/good.py", "def ok():\n    return 1\n")
    _write(tmp_path, "src/pkg/bad.py", "def boom():\n    return ok()\n")

    original = PythonGraphBuilder._extract_call

    def flaky(self, node, source, module, *args, **kwargs):  # type: ignore[no-untyped-def]
        if module.path.endswith("bad.py"):
            raise RuntimeError("synthetic failure")
        return original(self, node, source, module, *args, **kwargs)

    monkeypatch.setattr(PythonGraphBuilder, "_extract_call", flaky)
    document = _build(tmp_path)

    stats = document["statistics"]
    assert stats["failed_file_count"] == 1
    assert stats["failed_files"][0]["path"] == "src/pkg/bad.py"
    assert stats["failed_files"][0]["error_type"] == "RuntimeError"
    paths = {n["path"] for n in document["nodes"] if n["path"] and n["type"] != "File"}
    assert paths == {"src/pkg/good.py"}  # no partial symbols from the failed file


def test_helpers_nested_in_tests_do_not_break_contract(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/lib.py", "def work():\n    return 1\n")
    _write(
        tmp_path,
        "tests/test_lib.py",
        "from pkg.lib import work\n\n"
        "def test_it():\n"
        "    def helper():\n        return work()\n"
        "    helper()\n",
    )
    document = _build(tmp_path)  # validate_graph_document runs inside build()
    assert len(_ids(document, "Test")) == 1


def test_test_named_function_outside_test_file_is_not_a_test(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/app.py", "class App:\n    def test_client(self):\n        return 1\n")
    document = _build(tmp_path)
    assert _ids(document, "Test") == []
    assert len(_ids(document, "Method")) == 1


def test_orphaned_class_from_failed_module_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "src/pkg/good.py", "class Base: pass\n")
    _write(tmp_path, "src/pkg/bad.py", "class Derived(Base): pass\n")

    original = PythonGraphBuilder._extract_class

    def flaky(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        module = args[2] if len(args) > 2 else kwargs.get("module")
        if module and module.path.endswith("bad.py"):
            raise RuntimeError("synthetic parse failure in bad.py")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PythonGraphBuilder, "_extract_class", flaky)
    document = _build(tmp_path)

    assert document["statistics"]["failed_file_count"] == 1
    assert any("bad.py" in f["path"] for f in document["statistics"]["failed_files"])
    paths = {n["path"] for n in document["nodes"] if n.get("path") and n["type"] != "File"}
    assert paths == {"src/pkg/good.py"}
    classes = [n for n in document["nodes"] if n["type"] == "Class"]
    class_names = {n["name"] for n in classes}
    assert "Base" in class_names
    assert "Derived" not in class_names


def test_orphaned_call_from_failed_module_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        tmp_path, "src/pkg/good.py",
        "def target():\n    return 1\n\ndef caller():\n    return target()\n",
    )
    _write(tmp_path, "src/pkg/bad.py", "def bad_caller():\n    return target()\n")

    original = PythonGraphBuilder._extract_call

    def flaky(self, node, source, module, *args, **kwargs):  # type: ignore[no-untyped-def]
        if module.path.endswith("bad.py"):
            raise RuntimeError("synthetic parse failure in bad.py")
        return original(self, node, source, module, *args, **kwargs)

    monkeypatch.setattr(PythonGraphBuilder, "_extract_call", flaky)
    document = _build(tmp_path)

    assert document["statistics"]["failed_file_count"] == 1
    paths = {n["path"] for n in document["nodes"] if n.get("path") and n["type"] != "File"}
    assert paths == {"src/pkg/good.py"}
    call_edges = [e for e in document["edges"] if e["type"] == "CALLS"]
    assert len(call_edges) >= 1


def test_dotted_decorator_is_not_a_property_setter(tmp_path):
    _write(tmp_path, "src/app.py", "@api.route('/login')\ndef login(): return 1\n")
    document = _build(tmp_path)
    function = next(n for n in document["nodes"] if n["type"] == "Function")
    assert function["id"].endswith(":app.login")
    assert document["statistics"]["renamed_duplicate_count"] == 0


def test_commented_overloads_and_duplicate_definitions_keep_source_ranges(tmp_path):
    _write(tmp_path, "src/app.py",
           "from typing import overload\n@overload  # typing stub\ndef f(a: int): ...\n"
           "def f(a): return 1\ndef f(a): return 2\n")
    document = _build(tmp_path)
    functions = [n for n in document["nodes"] if n["type"] == "Function"]
    assert len(functions) == 2
    assert len({n["id"] for n in functions}) == 2
    assert document["statistics"]["skipped_overload_count"] == 1
    assert document["statistics"]["failed_file_count"] == 0


def test_failed_file_keeps_inventory_without_leaking_recorded_symbols(tmp_path, monkeypatch):
    _write(tmp_path, "src/bad.py", "class Broken:\n    def run(self): return target()\n")
    _write(tmp_path, "src/good.py", "def target(): return 1\ndef caller(): return target()\n")
    original = PythonGraphBuilder._extract_call
    def fail_after_record(self, node, source, module, *args, **kwargs):
        original(self, node, source, module, *args, **kwargs)
        if module.path.endswith('bad.py'):
            raise RuntimeError("after call was recorded")
    monkeypatch.setattr(PythonGraphBuilder, '_extract_call', fail_after_record)
    builder = PythonGraphBuilder(repo_key='t/repo', repository_revision='rev')
    document = builder.build(tmp_path)
    assert not any('Broken' in key for key in builder.symbols_by_qualified_name)
    assert all(call.path == 'src/good.py' for call in builder.calls)
    failed = next(n for n in document['nodes'] if n['type'] == 'File' and n['path'] == 'src/bad.py')
    assert failed['properties']['parse_status'] == 'failed'
    from vgar.graph.retrieval import GraphContextRetriever
    anchor = next(n['id'] for n in document['nodes'] if n['name'] == 'caller')
    result = GraphContextRetriever(document, tmp_path, count_tokens=len, counter_label='test:chars').retrieve([anchor], 1000)
    assert result.context.items


def test_typed_receiver_reassignment_and_union_are_not_guessed(tmp_path):
    _write(tmp_path, 'src/app.py',
           'class Worker:\n    def execute(self): pass\n'
           'def changed(worker: Worker):\n    worker = unknown\n    worker.execute()\n'
           'def union(worker: Worker | None):\n    worker.execute()\n')
    document = _build(tmp_path)
    assert not [e for e in document['edges'] if e['type'] == 'CALLS']


def test_shadowing_external_base_does_not_create_inheritance_self_loop(tmp_path):
    _write(tmp_path, 'src/app.py', 'from external.parsers import Parser\nclass Parser(Parser):\n    pass\n')
    document = _build(tmp_path)
    assert document['statistics']['failed_file_count'] == 0
    assert all(e['source_id'] != e['target_id'] for e in document['edges'])
    assert not [e for e in document['edges'] if e['type'] == 'INHERITS']


def test_shadowing_internal_base_uses_imported_class(tmp_path):
    _write(tmp_path, 'src/base.py', 'class Parser: pass\n')
    _write(tmp_path, 'src/app.py', 'from base import Parser\nclass Parser(Parser): pass\n')
    document = _build(tmp_path)
    nodes = {n['id']: n for n in document['nodes']}
    edge = next(e for e in document['edges'] if e['type'] == 'INHERITS')
    assert nodes[edge['source_id']]['qualified_name'] == 'app.Parser'
    assert nodes[edge['target_id']]['qualified_name'] == 'base.Parser'


def test_scope_indexing_failure_is_rolled_back(tmp_path, monkeypatch):
    _write(tmp_path, 'src/a_bad.py', 'class Broken: pass\n')
    _write(tmp_path, 'src/b_good.py', 'def work(): return 1\n')
    original = PythonGraphBuilder._index_scopes
    def fail_after_index(self, source, module):
        original(self, source, module)
        if module.path.endswith('a_bad.py'):
            raise RuntimeError('scope index failure')
    monkeypatch.setattr(PythonGraphBuilder, '_index_scopes', fail_after_index)
    builder = PythonGraphBuilder(repo_key='t/repo', repository_revision='rev')
    document = builder.build(tmp_path)
    assert document['statistics']['failed_file_count'] == 1
    assert not any('a_bad' in key for key in builder.scope_tables)
    assert not any('a_bad' in key for key in builder.typed_parameters)


def test_duplicate_base_example_preserves_occurrences_without_duplicate_edges(tmp_path):
    _write(tmp_path, 'src/example.py',
           'class Animal: pass\nclass Cat(Animal, Animal): pass\n')
    document = _build(tmp_path)
    edges = [edge for edge in document['edges'] if edge['type'] == 'INHERITS']
    assert len(edges) == 1
    assert document['statistics']['failed_file_count'] == 0
    assert edges[0]['properties']['base_occurrences'] == [
        {'base_expression': 'Animal', 'mro_position': 1},
        {'base_expression': 'Animal', 'mro_position': 2},
    ]
