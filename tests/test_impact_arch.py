"""IM-1: impact through G_arch. Spec: docs/superpowers/specs/2026-11-09-tv2-im-1-impact-design.md"""
from __future__ import annotations

import difflib
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vgar.contracts.impact import ImpactedNode, ImpactReport, PortCheck
from vgar.contracts.schema import G_ARCH_EDGE_TYPES
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.impact import analyze_patch_impact, diff_to_nodes
from vgar.repair.patch import PatchPolicy


def _component(**overrides: Any) -> dict[str, Any]:
    return {"node_id": "c", "qualified_name": "core", "path": None, "kind": "Component", "hops": 0,
            "relation": "LIFT", "via": "f", **overrides}


def _lost(port_id: str = "p", path: str = "a.py", consumers: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"path": path, "port_id": port_id, "qualified_name": "a.f", "export": "public_name",
            "owner_component_id": "c", "consumers": list(consumers), "api_reason": None}


def _report(items: tuple[dict[str, Any], ...] = (), **extra: Any) -> ImpactReport:
    data: dict[str, Any] = {"repo_key": "demo/project", "repository_revision": "r", "graph_version": "v",
                            "graph_hash": "sha256:" + "a" * 64, "source_hash": "sha256:" + "b" * 64,
                            "patch_hash": "sha256:" + "c" * 64, "changed": [], "unmapped": [], **extra}
    if items:
        data["impacted"] = {"status": "COMPLETE", "items": list(items), "max_hops": 2, "max_nodes": 200, "min_confidence": 0.6,
                            "traversed": sorted({item["relation"] for item in items})}
    return ImpactReport.model_validate(data)


def test_component_may_have_no_path() -> None:
    assert ImpactedNode.model_validate(_component()).path is None


def test_port_requires_path() -> None:
    with pytest.raises(ValidationError):
        ImpactedNode.model_validate(_component(kind="Port", relation="EXPOSES_PORT"))


def test_hops_zero_only_for_architecture() -> None:
    with pytest.raises(ValidationError):
        ImpactedNode.model_validate(_component(kind="Function", path="a.py", relation="CALLS"))


def test_non_null_path_still_validated() -> None:
    with pytest.raises(ValidationError):
        ImpactedNode.model_validate(_component(kind="Port", relation="EXPOSES_PORT", path="../x.py"))


def test_canonical_json_sorts_null_path() -> None:
    report = _report((_component(hops=1, relation="DEPENDS_ON"),
                      _component(node_id="g", kind="Function", path="a.py", hops=1, relation="CALLS")))
    assert ImpactReport.model_validate_json(report.canonical_json()) == report


def test_port_check_defaults_not_computed() -> None:
    check = _report().port_check
    assert check.status == "NOT_COMPUTED" and check.lost == check.removed_api == check.unchecked == []


@pytest.mark.parametrize("data", [
    pytest.param({"status": "NOT_COMPUTED", "lost": [_lost()]}, id="not-computed-with-lost"),
    pytest.param({"status": "COMPLETE", "unchecked": [{"path": "a.py", "reason": "AFTER_PARSE_FAILED"}]}, id="complete-with-unchecked"),
    pytest.param({"status": "PARTIAL"}, id="partial-without-unchecked"),
])
def test_port_check_consistency(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PortCheck.model_validate(data)


def test_canonical_json_sorts_port_check() -> None:
    first = _report(port_check={"status": "COMPLETE", "lost": [_lost("p1", consumers=("y", "x")), _lost("p2")]})
    second = _report(port_check={"status": "COMPLETE", "lost": [_lost("p2"), _lost("p1", consumers=("x", "y"))]})
    assert first.canonical_json() == second.canonical_json()


# ---- which node an insertion belongs to (spec 4.6) ------------------------------------------------------------------

def _lines(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=\n)", text) if part]


def _diff(path: str, old: str, new: str) -> str:
    out = []
    for line in difflib.unified_diff(_lines(old), _lines(new), fromfile=f"a/{path}", tofile=f"b/{path}", n=3):
        out.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return "".join(out)


def _build_repo(root: Path, files: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(text.encode("utf-8"))
    return PythonGraphBuilder(repo_key="t/arch", repository_revision="rev", **kwargs).build(root)


def _policy(doc: dict[str, Any]) -> PatchPolicy:
    return PatchPolicy(tuple(sorted(n["path"] for n in doc["nodes"] if n["type"] == "File")), ())


def _map(root: Path, doc: dict[str, Any], path: str, old: str, new: str) -> ImpactReport:
    return diff_to_nodes(_diff(path, old, new), doc, root, patch_policy=_policy(doc))


def _insert(text: str, after_line: int, added: str) -> str:
    lines = _lines(text)
    return "".join(lines[:after_line] + [added] + lines[after_line:])


def _changed_by_insert(root: Path, source: str, after_line: int, added: str) -> tuple[set[str], list[str]]:
    doc = _build_repo(root, {"a.py": source})
    report = _map(root, doc, "a.py", source, _insert(source, after_line, added))
    names = {n["id"]: n["qualified_name"] for n in doc["nodes"]}
    return {names[c.node_id] for c in report.changed}, [u.reason for u in report.unmapped]


TWO_FUNCTIONS = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
TWO_METHODS = "class C:\n    def a(self):\n        return 1\n\n    def b(self):\n        return 2\n"


def test_insert_after_last_statement_maps_function(tmp_path: Path) -> None:
    assert _changed_by_insert(tmp_path, TWO_FUNCTIONS, 2, "    x = 1\n") == ({"a.f"}, [])


def test_insert_after_comment_and_blank_maps_function(tmp_path: Path) -> None:
    source = "def f():\n    return 1\n    # note\n\n\ndef g():\n    return 2\n"
    assert _changed_by_insert(tmp_path, source, 4, "    x = 1\n") == ({"a.f"}, [])


def test_insert_at_def_indent_is_not_function(tmp_path: Path) -> None:
    assert _changed_by_insert(tmp_path, TWO_FUNCTIONS, 2, "x = 1\n") == (set(), ["NO_BASELINE_SYMBOL_AT_INSERTION"])


def test_insert_after_code_between_is_not_function(tmp_path: Path) -> None:
    source = "def f():\n    return 1\n\ny = 2\n\n\ndef g():\n    return 2\n"
    assert _changed_by_insert(tmp_path, source, 4, "    z = 1\n") == (set(), ["NO_BASELINE_SYMBOL_AT_INSERTION"])


def test_insert_end_of_inner_method_maps_method(tmp_path: Path) -> None:
    assert _changed_by_insert(tmp_path, TWO_METHODS, 3, "        x = 1\n") == ({"a.C.a"}, [])


def test_insert_at_class_body_indent_maps_class(tmp_path: Path) -> None:
    assert _changed_by_insert(tmp_path, TWO_METHODS, 3, "    x = 1\n") == ({"a.C"}, [])


def test_insert_at_end_of_crlf_file_maps_function(tmp_path: Path) -> None:
    source = TWO_FUNCTIONS.replace("\n", "\r\n")
    assert _changed_by_insert(tmp_path, source, 2, "    x = 1\r\n") == ({"a.f"}, [])


def test_insert_in_tab_indented_function_maps_function(tmp_path: Path) -> None:
    source = TWO_FUNCTIONS.replace("    ", "\t")
    assert _changed_by_insert(tmp_path, source, 2, "\tx = 1\n") == ({"a.f"}, [])


# ---- walking G_arch (spec 4.2-4.5) ----------------------------------------------------------------------------------

CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"
ARCH_NODES = {"Component", "Port", "Service", "DeploymentUnit"}
OVERRIDE_EDIT = ("storage/sql.py", "return discount(item)", "return discount(item) + 0")


def _case(tmp_path: Path, name: str = "boundary_cases") -> tuple[Path, dict[str, Any]]:
    root = shutil.copytree(CASES / name, tmp_path / "repo")
    return root, PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(root)


def _edit(root: Path, doc: dict[str, Any], path: str, old: str, new: str, **limits: Any) -> ImpactReport:
    text = (root / path).read_bytes().decode("utf-8")
    assert old in text
    return analyze_patch_impact(_diff(path, text, text.replace(old, new, 1)), doc, root, patch_policy=_policy(doc), **limits)


def _items(report: ImpactReport) -> dict[tuple[str, str], tuple[int, str]]:
    return {(item.qualified_name, item.kind): (item.hops, item.relation) for item in report.impacted.items}


def _strip_arch(doc: dict[str, Any]) -> dict[str, Any]:
    return {**doc, "nodes": [n for n in doc["nodes"] if n["type"] not in ARCH_NODES],
            "edges": [e for e in doc["edges"] if e["type"] not in G_ARCH_EDGE_TYPES]}


def _features(report: ImpactReport) -> dict[str, Any]:
    return {feature.name: feature for feature in report.risk.features}


def test_boundary_override_answer(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    items = _items(_edit(root, doc, *OVERRIDE_EDIT))
    assert items["storage.sql.SqlStore.save", "Port"] == (0, "EXPOSES_PORT")
    assert items["storage", "Component"] == (0, "LIFT")
    assert items["storage.base.BaseStore.save", "Method"] == (1, "INHERITS")
    assert items["storage.base.BaseStore.save", "Port"] == (1, "EXPOSES_PORT")
    for name in ("api", "services", "plugins"):
        assert items[name, "Component"] == (1, "DEPENDS_ON")
    assert items["services.orders.save_with", "Function"] == (2, "CALLS")


def test_private_function_has_component_no_port(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, doc, "services/pricing.py", "return 2", "return 3")
    assert _items(report)["services", "Component"] == (0, "LIFT")
    assert not [item for item in report.impacted.items if item.kind == "Port" and item.hops == 0]


def test_consumer_via_port(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    assert _items(_edit(root, doc, "storage/sql.py", "return value", "return value + 0"))["services", "Component"] == (1, "CONSUMES_PORT")


def test_depends_on_stops_after_one_step(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    items = _items(_edit(root, doc, "services/pricing.py", "return value - 1", "return value - 2"))
    assert ("api", "Component") in items and ("storage", "Component") in items
    assert ("plugins", "Component") not in items  # plugins depends on storage, two DEPENDS_ON steps away


def test_edge_below_confidence_not_followed(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    for edge in doc["edges"]:
        if edge["type"] == "DEPENDS_ON":
            edge["confidence"] = 0.3
    assert "DEPENDS_ON" not in {item.relation for item in _edit(root, doc, *OVERRIDE_EDIT).impacted.items}


def test_init_does_not_walk_to_base(tmp_path: Path) -> None:
    source = "class Base:\n    def __init__(self):\n        self.x = 1\n\n\nclass Child(Base):\n    def __init__(self):\n        self.x = 2\n"
    doc = _build_repo(tmp_path, {"a.py": source})
    assert ("a.Base.__init__", "Method") not in _items(_edit(tmp_path, doc, "a.py", "self.x = 2", "self.x = 3"))


def test_multiple_inheritance_and_empty_middle(tmp_path: Path) -> None:
    source = ("class A:\n    def run(self):\n        return 1\n\n\nclass Mid(A):\n    pass\n\n\n"
              "class B:\n    def run(self):\n        return 2\n\n\nclass C(Mid, B):\n    def run(self):\n        return 3\n")
    doc = _build_repo(tmp_path, {"a.py": source})
    items = _items(_edit(tmp_path, doc, "a.py", "return 3", "return 4"))
    assert items["a.A.run", "Method"] == (1, "INHERITS") and items["a.B.run", "Method"] == (1, "INHERITS")


def test_inherits_cycle_terminates(tmp_path: Path) -> None:
    source = "class A:\n    pass\n\n\nclass B(A):\n    pass\n\n\nclass C(B):\n    def run(self):\n        return 3\n"
    doc = _build_repo(tmp_path, {"a.py": source})
    ids = {n["qualified_name"]: n["id"] for n in doc["nodes"] if n["type"] == "Class"}
    template = next(e for e in doc["edges"] if e["type"] == "INHERITS")
    doc["edges"].append({**template, "id": "cycle", "source_id": ids["a.A"], "target_id": ids["a.B"]})
    assert _edit(tmp_path, doc, "a.py", "return 3", "return 4").impacted.status == "COMPLETE"


def test_small_max_nodes_keeps_component(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, doc, *OVERRIDE_EDIT, max_nodes=2)
    assert report.impacted.status == "PARTIAL" and ("storage", "Component") in _items(report)


def test_max_hops_one(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, doc, *OVERRIDE_EDIT, max_hops=1)
    assert {item.hops for item in report.impacted.items} == {0, 1}
    assert ("services.orders.save_with", "Function") not in _items(report)


def test_no_component_graph_is_unchanged(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, _strip_arch(doc), *OVERRIDE_EDIT)
    assert report.impacted.traversed == ["CALLS", "IMPORTS", "INHERITS", "TESTS"]
    assert not {item.kind for item in report.impacted.items} & {"Port", "Component"}
    items = _items(report)
    assert ("storage.base.BaseStore.save", "Method") not in items and ("services.orders.save_with", "Function") not in items
    features = _features(report)
    for name in ("public_ports_changed", "components_affected"):
        assert (features[name].available, features[name].reason) == (False, "NOT_COMPUTED")


def test_risk_features_architecture(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    features = _features(_edit(root, doc, *OVERRIDE_EDIT))
    assert features["public_ports_changed"].value == 1 and features["components_affected"].value == 4
    assert features["ports_lost"].value == 0  # the body changed, every Port is still there
    for name in ("dependency_cycle_introduced", "covering_tests_pass"):
        assert features[name].available is False


def test_impacted_callers_ignores_base_method(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, doc, *OVERRIDE_EDIT)
    assert ("storage.base.BaseStore.save", "Method") in _items(report)
    assert _features(report)["impacted_callers"].value == 1  # save_with only; the base method is not a caller
