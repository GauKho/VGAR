"""Cumulative layer profiles and their graph builds (spec 2026-11-19 §5)."""
import pytest

from baseline.profiles import BUILDS, PROFILE_ORDER, PROFILES, build_layers

TOOL_NAMES = ("VGAR_NODE", "VGAR_SCIP_ENTRY", "VGAR_LSP_ENTRY", "VGAR_TSG_EXECUTABLE", "VGAR_TSG_TREE_SITTER_DIR")


def test_every_profile_names_a_known_build_and_arm():
    from retrieval_variants import GRAPH_ARM_SPECS
    assert all(build in BUILDS and arm in GRAPH_ARM_SPECS for build, arm in PROFILES.values())
    assert PROFILE_ORDER[0] == "P0" and PROFILE_ORDER[-1] == "full"


def test_builds_add_layers_cumulatively(tmp_path):
    tools = {name: str(tmp_path / name) for name in TOOL_NAMES}
    assert not build_layers("base", tools).any_optional
    scip = build_layers("scip", tools)
    assert scip.scip and not scip.lsp and not scip.tsg
    lsp = build_layers("scip_lsp", tools)
    assert lsp.scip and lsp.lsp and not lsp.joern
    full = build_layers("full", tools)
    assert full.scip and full.lsp and full.tsg and full.joern and full.jarvis


def test_missing_tool_for_a_build_names_the_variable():
    with pytest.raises(ValueError, match="VGAR_SCIP_ENTRY"):
        build_layers("scip", {})
    with pytest.raises(ValueError, match="unknown build"):
        build_layers("nope", {})


def test_a1_arch_profile_uses_the_arch_arm_on_the_base_build():
    # §13.1 "repo graph + architecture lift" without the task trace, compared with A1 (spec 2026-11-20 §5.4).
    from baseline.profiles import BASELINE_PROFILE
    assert PROFILES["A1_arch"] == ("base", "arch_no_task_trace")
    assert BASELINE_PROFILE == {"A1_arch": "A1"}
