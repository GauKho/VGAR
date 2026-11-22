"""Cumulative layer profiles (spec 2026-11-19 §5): profile -> (graph build, retrieval arm of R1).

The builds use ``vgar.graph.layer_config.layer_configs``, the function the served graph uses, so a build here is
configured exactly as the MCP server would configure it from the same host variables.
"""
from __future__ import annotations

from collections.abc import Mapping

import baseline._paths  # noqa: F401
from vgar.graph.layer_config import LayerConfigs, layer_configs

BUILDS = ("base", "scip", "scip_lsp", "full")
PROFILES: dict[str, tuple[str, str]] = {
    "P0": ("base", "ast_no_task_trace"),      # §13.1 AST-only graph
    "A1": ("base", "no_task_trace"),          # §13.3 A1 repo graph
    "A1_arch": ("base", "arch_no_task_trace"),   # §13.1 repo graph + architecture lift, no task trace
    "A2": ("base", "task_trace"),             # + task trace (the served default)
    "A3": ("base", "a3"),                     # + architecture
    "A3_scip": ("scip", "a3"),
    "A3_scip_lsp": ("scip_lsp", "a3"),
    "full": ("full", "a3"),                   # + tree-sitter-graph, Joern, JARVIS
}
PROFILE_ORDER = tuple(PROFILES)
# Profiles compared with a named profile instead of the previous one (the A1 -> A2 step stays the G_task step).
BASELINE_PROFILE = {"A1_arch": "A1"}

_REQUIRED = {"base": (), "scip": ("VGAR_SCIP_ENTRY",), "scip_lsp": ("VGAR_SCIP_ENTRY", "VGAR_LSP_ENTRY"),
             "full": ("VGAR_SCIP_ENTRY", "VGAR_LSP_ENTRY", "VGAR_TSG_EXECUTABLE", "VGAR_TSG_TREE_SITTER_DIR")}
_PASS_THROUGH = ("VGAR_NODE", "VGAR_SCIP_TIMEOUT")


def build_env(build: str, tools: Mapping[str, str]) -> dict[str, str]:
    """Host variables of one build; raises ValueError naming a missing tool variable."""
    if build not in _REQUIRED:
        raise ValueError(f"unknown build {build!r}; expected one of {BUILDS}")
    if build == "base":
        return {}
    missing = [name for name in _REQUIRED[build] if not (tools.get(name) or "").strip()]
    if missing:
        raise ValueError(f"build {build!r} needs {', '.join(missing)}")
    env = {name: tools[name] for name in _REQUIRED[build]}
    env.update({name: tools[name] for name in _PASS_THROUGH if tools.get(name)})
    if build == "full":
        env.update(VGAR_JOERN="1", VGAR_JARVIS="1")
    return env


def build_layers(build: str, tools: Mapping[str, str]) -> LayerConfigs:
    """``LayerConfigs`` of one build."""
    return layer_configs(build_env(build, tools))
