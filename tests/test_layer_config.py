"""Layer settings shared by scripts/build_graph.py and the served build (spec 2026-11-15 §1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vgar.graph.layer_config import (
    LayerConfigs,
    layer_configs,
    layer_summary,
    lsp_config,
    scip_config,
)
from vgar.mcp.host_config import check_host_config

ROOT = Path(__file__).resolve().parents[1]


def test_unset_env_gives_no_layers():
    configs = layer_configs({})
    assert configs == LayerConfigs() and not configs.any_optional
    assert configs.builder_kwargs() == {"tsg": None, "scip": None, "lsp": None, "jarvis": None, "joern": None}


def test_each_variable_enables_its_layer(tmp_path):
    tool = tmp_path / "tool"
    tool.write_text("", encoding="utf-8")
    env = {"VGAR_TSG_EXECUTABLE": str(tool), "VGAR_TSG_TREE_SITTER_DIR": str(tmp_path),
           "VGAR_SCIP_ENTRY": str(tool), "VGAR_NODE": str(tool), "VGAR_LSP_ENTRY": str(tool),
           "VGAR_JARVIS": "1", "VGAR_JARVIS_TIMEOUT": "30", "VGAR_JOERN": "1", "VGAR_JOERN_TIMEOUT": "60"}
    configs = layer_configs(env)
    assert configs.tsg.executable == tool and configs.tsg.tree_sitter_dir == tmp_path
    assert configs.scip.command[0] == str(tool.resolve()) and configs.scip.command[-1] == str(tool.resolve())
    assert configs.lsp.command == (str(tool.resolve()), str(tool.resolve()), "--stdio")
    assert configs.jarvis.timeout_seconds == 30 and configs.joern.timeout_seconds == 60
    assert configs.any_optional


def test_relative_path_rejected():
    with pytest.raises(ValueError):
        layer_configs({"VGAR_SCIP_ENTRY": "relative/index.js"})
    with pytest.raises(ValueError):
        layer_configs({"VGAR_TSG_EXECUTABLE": "tsg", "VGAR_TSG_TREE_SITTER_DIR": "/abs"})


def test_tsg_needs_both_variables(tmp_path):
    with pytest.raises(ValueError):
        layer_configs({"VGAR_TSG_EXECUTABLE": str(tmp_path / "tsg")})


def test_scip_and_lsp_commands_match_build_graph(tmp_path):
    entry, node = tmp_path / "index.js", tmp_path / "node.exe"
    shim = (ROOT / "scripts" / "scip_windows_compat.cjs").resolve()
    scip = scip_config(entry, node=str(node), timeout=120, strict=False, environment=None, native_config=False,
                       import_roots=("src", "lib"), target_only=None, python=None)
    assert scip.command == (str(node.resolve()), "-r", str(shim), str(entry.resolve()))
    assert scip.import_roots == ("src", "lib") and scip.configure_imports is True
    lsp = lsp_config(entry, node=str(node), total_timeout=30, request_timeout=5, max_requests=200, python=None,
                     import_roots=("src", "lib"), strict=False)
    assert lsp.command == (str(node.resolve()), str(entry.resolve()), "--stdio") and lsp.max_requests == 200


def test_layer_summary_ready_off_failed():
    document = {"statistics": {"resolver": {"requested": "scip", "status": "fallback", "reason": "timeout"},
                               "tsg": {"status": "ready", "reason": None},
                               "code_graph": {"status": "failed", "reason": "docker missing"}}}
    configs = LayerConfigs(tsg=object(), scip=object(), joern=object())
    summary = layer_summary(document, configs)
    assert summary["tsg"] == {"status": "ready", "reason": None}
    assert summary["scip"] == {"status": "failed", "reason": "timeout"}
    assert summary["joern"] == {"status": "failed", "reason": "docker missing"}
    assert summary["jarvis"] == {"status": "off", "reason": None} and summary["lsp"]["status"] == "off"


def test_host_config_rejects_relative_layer_path(tmp_path):
    db = tmp_path / "g.db"
    db.write_bytes(b"")
    env = {"VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl"), "VGAR_REPOSITORY_ROOT": str(tmp_path),
           "VGAR_GRAPH_DATABASE": str(db), "VGAR_TSG_EXECUTABLE": "tsg"}
    problems = check_host_config("graph", env)
    assert any(problem.startswith("VGAR_TSG_EXECUTABLE") for problem in problems)
    del env["VGAR_TSG_EXECUTABLE"]
    assert check_host_config("graph", env) == []



def test_partial_with_every_file_failed_is_failed():
    document = {"statistics": {"tsg": {"status": "partial", "reason": None, "file_count": 2,
                                       "failed_files": [{"path": "a.py"}, {"path": "b.py"}]}}}
    assert layer_summary(document, LayerConfigs(tsg=object()))["tsg"]["status"] == "failed"
    document["statistics"]["tsg"]["failed_files"] = [{"path": "a.py"}]
    assert layer_summary(document, LayerConfigs(tsg=object()))["tsg"]["status"] == "ready"


def _graph_env(tmp_path):
    db = tmp_path / "g.db"
    db.write_bytes(b"")
    return {"VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl"), "VGAR_REPOSITORY_ROOT": str(tmp_path),
            "VGAR_GRAPH_DATABASE": str(db)}


def test_host_config_rejects_half_tsg_pair(tmp_path):
    env = dict(_graph_env(tmp_path), VGAR_TSG_EXECUTABLE=str(tmp_path / "tsg"))
    assert any("VGAR_TSG_EXECUTABLE" in p and "VGAR_TSG_TREE_SITTER_DIR" in p for p in check_host_config("graph", env))


def test_host_config_rejects_non_numeric_timeout(tmp_path):
    env = dict(_graph_env(tmp_path), VGAR_JOERN="1", VGAR_JOERN_TIMEOUT="abc")
    assert any(p.startswith("VGAR_JOERN_TIMEOUT") for p in check_host_config("graph", env))
