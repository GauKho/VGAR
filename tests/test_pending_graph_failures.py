"""Regressions derived from the six failed Week 6 benchmark tasks."""
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder


@pytest.mark.parametrize("bases", ["Animal, Animal", "Animal, Alias"])
def test_repeated_base_occurrences_keep_distinct_inheritance_edges(tmp_path: Path, bases):
    # Pylint analyzes invalid runtime programs too: do not execute this source.
    (tmp_path / "bad.py").write_text(
        "class Animal: pass\nfrom bad import Animal as Alias\n"
        f"class Cat({bases}): pass\n", encoding="utf-8"
    )
    document = PythonGraphBuilder(repo_key="fixture", repository_revision="base", use_jedi=False).build(tmp_path)
    edges = [edge for edge in document["edges"] if edge["type"] == "INHERITS"]
    assert len(edges) == 2
    assert len({edge["id"] for edge in edges}) == 2
    assert len({edge["target_id"] for edge in edges}) == 1
    assert [edge["properties"]["mro_position"] for edge in edges] == [1, 2]
    again = PythonGraphBuilder(repo_key="fixture", repository_revision="base", use_jedi=False).build(tmp_path)
    assert [e["id"] for e in again["edges"] if e["type"] == "INHERITS"] == [e["id"] for e in edges]
