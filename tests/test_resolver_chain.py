"""Resolver order SCIP -> LSP (only when SCIP is not ready) -> static -> MAY_CALL (spec 2026-11-24 §4.2)."""
from __future__ import annotations

from git_fixture import write_tree
from resolver_fixture import CHAIN, needs_resolvers

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.layer_config import LSP_RUNTIME, SCIP_RUNTIME, layer_configs, layer_summary


def _layers(tmp_path, **env):
    return layer_configs({"VGAR_GRAPH_DATABASE": str(tmp_path / "g.db"), **env})


def _tree(tmp_path):
    return write_tree(tmp_path / "repo", {path: text.encode() for path, text in CHAIN.items()})


def _build(tmp_path, layers):
    document = PythonGraphBuilder(repo_key="t/chain", repository_revision="rev",
                                  **layers.builder_kwargs()).build(_tree(tmp_path))
    return document, layer_summary(document, layers)


def _rules(document):
    return {e["provenance"]["rule_id"] for e in document["edges"] if e["type"] == "CALLS"}


@needs_resolvers
def test_scip_ready_skips_lsp(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    assert layers.lsp.fallback_only is True
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "ready" and summary["lsp"] == {"status": "skipped", "reason": "SCIP ready"}
    assert "python.call.scip.resolve.v1" in _rules(document) and "python.call.lsp.definition.v1" not in _rules(document)
    assert document["statistics"]["resolver"]["active"] == "scip"


@needs_resolvers
def test_broken_scip_falls_back_to_lsp(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(tmp_path / "missing.js"), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["scip"]["reason"]
    assert summary["lsp"]["status"] == "ready" and document["statistics"]["resolver"]["active"] == "lsp"
    assert "python.call.lsp.definition.v1" in _rules(document)


@needs_resolvers
def test_both_broken_use_static_and_keep_may_call(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(tmp_path / "a.js"), VGAR_LSP_ENTRY=str(tmp_path / "b.js"))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["lsp"]["status"] == "failed"
    assert document["statistics"]["resolver"]["active"] == "static"
    assert any(e["type"] == "MAY_CALL" for e in document["edges"])


def test_missing_node_fails_both_and_builds_static(tmp_path):
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME),
                     VGAR_NODE=str(tmp_path / "no-node.exe"))
    document, summary = _build(tmp_path, layers)
    assert summary["scip"]["status"] == "failed" and summary["lsp"]["status"] == "failed"
    assert document["statistics"]["resolver"]["active"] == "static" and document["nodes"]


@needs_resolvers
def test_served_builds_write_runs_next_to_the_database_only(tmp_path, monkeypatch):
    from vgar.graph.live_build import LiveGraphBuilder
    root = _tree(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    layers = _layers(tmp_path, VGAR_SCIP_ENTRY=str(SCIP_RUNTIME), VGAR_LSP_ENTRY=str(LSP_RUNTIME))
    live = LiveGraphBuilder(root, tmp_path / "g.db", layers=layers)
    for index in range(4):
        (root / "shop/repo.py").write_text(f"class Repo:\n    def check(self):\n        return {index}\n", encoding="utf-8")
        live.run()
    assert len(list((tmp_path / "scip-runs").iterdir())) == 3
    assert not (cwd / "artifacts").exists() and not (root / "artifacts").exists()
