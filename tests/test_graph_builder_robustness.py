from __future__ import annotations

from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder


def _build(root: Path) -> dict:
    return PythonGraphBuilder(
        repo_key="t/repo",
        repository_revision="rev",
        source_roots=("src",),
        use_jedi=False,
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
    paths = {n["path"] for n in document["nodes"] if n["path"]}
    assert paths == {"src/pkg/good.py"}  # no partial nodes from the failed file


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