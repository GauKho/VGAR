"""Context flag use_variable_references (spec 2026-11-15 §4): off keeps the frozen ranking; on adds read variables and co-readers."""
from __future__ import annotations

import pytest
from test_graph_retrieval import FROZEN_RANKING_HASH
from test_variable_refs import APP_FACTS, OTHER_FACTS
from test_variable_refs import OTHER as OTHER_SOURCE
from test_variable_refs import SOURCE as APP_SOURCE

from vgar.graph import tsg_extractor
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import (
    GraphContextRetriever,
    RetrievalConfig,
    ranking_config_hash,
)
from vgar.graph.tsg_extractor import TsgConfig

ADD = "vgar:t/repo:python:method:src/app.py:app.Cart.add"


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(APP_SOURCE, encoding="utf-8")
    (root / "src" / "other.py").write_text(OTHER_SOURCE, encoding="utf-8")
    return root


def _with_reader_edges(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file",
                        lambda config, r, path: {"src/app.py": APP_FACTS, "src/other.py": OTHER_FACTS}[path])
    tsg = TsgConfig(executable=tmp_path / "tsg", tree_sitter_dir=tmp_path)
    return root, PythonGraphBuilder(repo_key="t/repo", repository_revision="rev", tsg=tsg).build(root)


def _without_reader_edges(document):
    return dict(document, edges=[e for e in document["edges"] if e["provenance"]["rule_id"] != "python.layer1.reads.v1"])


def _candidates(root, document, **flags):
    retriever = GraphContextRetriever(document, root, count_tokens=lambda text: len(text) // 4, counter_label="test",
                                      config=RetrievalConfig(**flags))
    result = retriever.retrieve([ADD], 12000)
    return {c["node_id"]: tuple(c["graph_rationale"]) for c in result.candidates}


def test_default_hash_unchanged():
    assert ranking_config_hash(RetrievalConfig()) == FROZEN_RANKING_HASH
    assert ranking_config_hash(RetrievalConfig(use_variable_references=False, variable_co_readers=3)) == FROZEN_RANKING_HASH
    assert ranking_config_hash(RetrievalConfig(use_variable_references=True)) != FROZEN_RANKING_HASH


def test_default_ranking_identical_with_reader_edges_present(tmp_path, monkeypatch):
    root, document = _with_reader_edges(tmp_path, monkeypatch)
    assert _candidates(root, document) == _candidates(root, _without_reader_edges(document))


def test_flag_adds_variable_and_co_readers(tmp_path, monkeypatch):
    root, document = _with_reader_edges(tmp_path, monkeypatch)
    on = _candidates(root, document, use_variable_references=True)
    limit = "vgar:t/repo:python:globalvariable:src/app.py:app.LIMIT"
    assert on[limit][0] == "READS_VARIABLE"
    co_readers = {node_id for node_id, rationale in on.items() if rationale and rationale[0] == "CO_READER"}
    assert {"vgar:t/repo:python:function:src/app.py:app.bump",
            "vgar:t/repo:python:function:src/other.py:other.use"} & co_readers


def test_flag_without_reader_edges_changes_nothing(tmp_path, monkeypatch):
    root, document = _with_reader_edges(tmp_path, monkeypatch)
    plain = _without_reader_edges(document)
    assert _candidates(root, plain, use_variable_references=True) == _candidates(root, plain)


def test_co_reader_cap(tmp_path, monkeypatch):
    root, document = _with_reader_edges(tmp_path, monkeypatch)
    on = _candidates(root, document, use_variable_references=True, variable_co_readers=1)
    per_variable = {}
    for rationale in on.values():
        if rationale and rationale[0] == "CO_READER":
            per_variable[rationale[1]] = per_variable.get(rationale[1], 0) + 1
    assert per_variable and all(count <= 1 for count in per_variable.values())


def test_invalid_co_reader_count_rejected():
    from vgar.contracts.error import InvalidLimitError

    with pytest.raises(InvalidLimitError):
        RetrievalConfig(variable_co_readers=-1)
