"""GA-1, GA-2: the G_arch layer lifted from the Python repo graph.

Expected values are written by hand from the fixture sources.
Spec: docs/superpowers/specs/2026-11-09-tv2-ga-g-arch-design.md
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    G_ARCH_EDGE_TYPES,
    NODE_TYPES,
    SCHEMA_VERSION,
    SOURCE_BACKED_NODE_TYPES,
    validate_graph_document,
)
from vgar.graph import arch_lift
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.incremental import IncrementalGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.tsg_extractor import TsgConfig
from vgar.repair.structural_check import check_structure

CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"


def _build(root: Path, **kwargs: Any) -> dict[str, Any]:
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev", **kwargs).build(root)
    validate_graph_document(document)
    return document


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def _nodes(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [node for node in document["nodes"] if node["type"] == kind]


def _typed(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    nodes = {node["id"]: node for node in document["nodes"]}
    return [{"source": nodes[e["source_id"]], "target": nodes[e["target_id"]], "edge": e}
            for e in document["edges"] if e["type"] == kind]


def _depends(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(x["source"]["name"], x["target"]["name"]): x["edge"]["properties"] for x in _typed(document, "DEPENDS_ON")}


def test_schema_declares_g_arch() -> None:
    assert {"Component", "Port", "Connector", "Service", "DeploymentUnit", "ExternalSystem", "Module"} <= NODE_TYPES
    assert not {"Port", "Component"} & SOURCE_BACKED_NODE_TYPES  # source-backed nodes need a CONTAINS owner; these have none
    assert ("Component", "Component") in EDGE_ENDPOINTS["DEPENDS_ON"]
    assert EDGE_ENDPOINTS["EXPOSES_PORT"] == EDGE_ENDPOINTS["CONSUMES_PORT"] == {("Component", "Port")}
    assert EDGE_ENDPOINTS["COMMUNICATES_WITH"] == {("Service", "Service")}
    assert EDGE_ENDPOINTS["CONTAINS_COMPONENT"] == {("Module", "Component")}
    assert EDGE_ENDPOINTS["DEPLOYS_TO"] == {("Component", "DeploymentUnit")}
    assert EDGE_ENDPOINTS["CONFIGURES"] == {("ConfigEntry", "Component"), ("ConfigEntry", "Service")}
    assert SCHEMA_VERSION.startswith("vgar-schema-full-")
    assert G_ARCH_EDGE_TYPES == {"DEPENDS_ON", "EXPOSES_PORT", "CONSUMES_PORT", "COMMUNICATES_WITH",
                                 "CONTAINS_COMPONENT", "DEPLOYS_TO", "CONFIGURES"}


def test_multi_package_components() -> None:
    document = _build(CASES / "multi_package")
    components = {node["name"]: node for node in _nodes(document, "Component")}
    assert set(components) == {"app", "db"}
    assert components["app"]["id"] == "vgar:t/arch:python:component:app"
    assert components["app"]["path"] is None and components["app"]["qualified_name"] == "app"
    assert components["app"]["properties"]["kind"] == "package"
    assert components["app"]["properties"]["files"] == ["app/__init__.py", "app/parser.py", "app/service.py"]
    assert components["app"]["properties"]["tests"] == ["tests/test_service.py"]
    assert components["db"]["properties"]["tests"] == []
    app = components["app"]["properties"]
    assert (app["internal_dependency_weight"], app["external_dependency_weight"], app["entity_count"]) == (5, 7, 5)
    assert app["cohesion"] == 0.416667 and app["coupling"] == 1.4
    db = components["db"]["properties"]
    assert (db["internal_dependency_weight"], db["external_dependency_weight"], db["entity_count"]) == (1, 7, 6)
    assert db["cohesion"] == 0.125 and db["coupling"] == 1.166667


def test_multi_package_depends_on() -> None:
    document = _build(CASES / "multi_package")
    assert _depends(document) == {("app", "db"): {"weight": 4, "call_count": 2, "import_count": 2},
                                  ("db", "app"): {"weight": 3, "call_count": 1, "import_count": 2}}
    edges = {(x["source"]["name"], x["target"]["name"]): x["edge"] for x in _typed(document, "DEPENDS_ON")}
    assert edges[("app", "db")]["confidence"] == 0.975 and edges[("db", "app")]["confidence"] == 0.9833
    assert edges[("app", "db")]["resolution"] == "heuristic"
    assert edges[("app", "db")]["provenance"]["source_tool"] == "vgar-arch-lift"
    assert edges[("app", "db")]["provenance"]["rule_id"] == "python.arch.depends_on.v1"
    evidence = edges[("app", "db")]["provenance"]["evidence"]
    assert 0 < len(evidence) <= 5 and evidence == sorted(evidence)


def test_contains_component_uses_existing_module_node() -> None:
    document = _build(CASES / "multi_package")
    pairs = {(x["source"]["qualified_name"], x["source"]["type"], x["target"]["name"], x["edge"]["confidence"])
             for x in _typed(document, "CONTAINS_COMPONENT")}
    assert pairs == {("app", "Module", "app", 1.0), ("db", "Module", "db", 1.0)}


def test_files_outside_packages_are_unassigned() -> None:
    report = _build(CASES / "multi_package")["statistics"]["arch"]
    assert report["mode"] == "package" and report["component_count"] == 2
    assert report["unassigned_source_files"] == 1


def test_single_package_uses_module_mode() -> None:
    document = _build(CASES / "single_package")
    assert {node["id"].rsplit(":", 1)[1] for node in _nodes(document, "Component")} == {"shop/a", "shop/b"}
    assert {node["properties"]["kind"] for node in _nodes(document, "Component")} == {"module"}
    assert _depends(document) == {("b", "a"): {"weight": 2, "call_count": 1, "import_count": 1}}
    assert document["statistics"]["arch"]["mode"] == "module"
    pairs = {(x["source"]["qualified_name"], x["target"]["qualified_name"]) for x in _typed(document, "CONTAINS_COMPONENT")}
    assert pairs == {("shop.a", "shop.a"), ("shop.b", "shop.b")}


def test_flat_scripts_use_module_mode() -> None:
    document = _build(CASES / "flat_scripts")
    assert {node["name"] for node in _nodes(document, "Component")} == {"a", "b"}
    assert _depends(document) == {("b", "a"): {"weight": 2, "call_count": 1, "import_count": 1}}


def test_init_with_definitions_stays_a_component_in_module_mode(tmp_path: Path) -> None:
    _write(tmp_path, {"pkg/__init__.py": "def helper():\n    return 1\n", "pkg/x.py": "def x():\n    return 1\n"})
    keys = {node["id"].rsplit(":", 1)[1] for node in _nodes(_build(tmp_path), "Component")}
    assert keys == {"pkg/__init__", "pkg/x"}


def test_empty_repo_has_no_components(tmp_path: Path) -> None:
    document = _build(tmp_path)
    assert _nodes(document, "Component") == []
    assert document["statistics"]["arch"]["mode"] == "module"
    assert document["statistics"]["arch"]["component_count"] == 0


def test_root_init_is_not_a_package() -> None:
    # Called on lift directly: the builder cannot produce a valid Module for a root __init__.py today.
    def module(path: str, name: str) -> dict[str, Any]:
        return {"id": path, "type": "Module", "repo_key": "t/arch", "path": path, "qualified_name": name,
                "properties": {"is_external": False}}

    nodes = [module("__init__.py", "root"), module("x/__init__.py", "x"), module("y/__init__.py", "y")]
    result = arch_lift.lift("t/arch", nodes, [], is_test=lambda path: False)
    assert result.report["mode"] == "package"
    assert {node["id"].rsplit(":", 1)[1] for node in result.nodes} == {"x", "y"}


def test_lift_is_deterministic() -> None:
    first, second = _build(CASES / "multi_package"), _build(CASES / "multi_package")
    assert [n["id"] for n in first["nodes"]] == [n["id"] for n in second["nodes"]]
    assert [e["id"] for e in first["edges"]] == [e["id"] for e in second["edges"]]


def test_ports() -> None:
    ports = {node["qualified_name"]: node for node in _nodes(_build(CASES / "multi_package"), "Port")}
    assert set(ports) == {"app.parser.normalize", "app.service.login", "app.service._audit",
                          "db.store.Store.put", "db.store.load_user", "db.store.save_user"}
    audit = ports["app.service._audit"]
    assert audit["properties"]["export"] == "dunder_all" and audit["properties"]["kind"] == "function"
    assert audit["path"] == "app/service.py" and audit["properties"]["routes"] == []
    assert audit["properties"]["signature"] == "def _audit(user)"
    assert audit["id"] == "vgar:t/arch:python:port:app/service.py:app.service._audit"
    assert ports["app.service.login"]["properties"]["export"] == "public_name"
    assert ports["db.store.Store.put"]["properties"]["kind"] == "method"


def test_port_points_at_its_symbol_and_owner() -> None:
    document = _build(CASES / "multi_package")
    nodes = {node["id"]: node for node in document["nodes"]}
    port = next(node for node in _nodes(document, "Port") if node["name"] == "login")
    symbol = nodes[port["properties"]["symbol_id"]]
    assert (symbol["type"], symbol["qualified_name"]) == ("Function", "app.service.login")
    assert port["range"] == symbol["range"] and port["content_hash"] == symbol["content_hash"]
    assert nodes[port["properties"]["owner_component_id"]]["name"] == "app"
    assert document["statistics"]["arch"]["port_count"] == 6


def test_exposes_and_consumes() -> None:
    document = _build(CASES / "multi_package")
    exposes = _typed(document, "EXPOSES_PORT")
    assert len(exposes) == 6 and {x["edge"]["confidence"] for x in exposes} == {1.0}
    assert {x["edge"]["resolution"] for x in exposes} == {"exact"}
    consumes = {(x["source"]["name"], x["target"]["qualified_name"]): x["edge"] for x in _typed(document, "CONSUMES_PORT")}
    assert set(consumes) == {("app", "db.store.load_user"), ("app", "db.store.save_user"), ("db", "app.parser.normalize")}
    assert consumes[("app", "db.store.load_user")]["properties"] == {"call_count": 1}
    assert consumes[("app", "db.store.load_user")]["confidence"] == 0.95
    assert consumes[("app", "db.store.load_user")]["resolution"] == "heuristic"


def test_read_dunder_all() -> None:
    assert arch_lift.read_dunder_all(b'__all__ = ["a", "b"]\n') == {"a", "b"}
    assert arch_lift.read_dunder_all(b'__all__ = ("a",)\n') == {"a"}
    assert arch_lift.read_dunder_all(b'__all__ = ["a"] + x\n') == frozenset()
    assert arch_lift.read_dunder_all(b'__all__ = [name]\n') == frozenset()
    assert arch_lift.read_dunder_all(b'def f(:\n__all__ = ["a"]\n') == frozenset()


def test_duplicate_definitions_get_two_ports(tmp_path: Path) -> None:
    _write(tmp_path, {"x/__init__.py": "", "y/__init__.py": "",
                      "x/m.py": "import sys\nif sys.argv:\n    def f():\n        return 1\nelse:\n    def f():\n        return 2\n"})
    ports = [node for node in _nodes(_build(tmp_path), "Port") if node["name"] == "f"]
    assert len(ports) == 2 and len({node["id"] for node in ports}) == 2


def test_broken_file_with_dunder_all_builds(tmp_path: Path) -> None:
    _write(tmp_path, {"x/__init__.py": "", "y/__init__.py": "",
                      "x/m.py": "__all__ = ['_g']\ndef _g():\n    return 1\ndef broken(:\n"})
    document = _build(tmp_path)
    assert all(node["name"] != "_g" for node in _nodes(document, "Port"))


@pytest.mark.skipif(TsgConfig.from_env() is None, reason="needs VGAR_TSG_EXECUTABLE and VGAR_TSG_TREE_SITTER_DIR")
def test_route_handler_and_configures_with_real_cli() -> None:
    document = _build(CASES / "web_app", tsg=TsgConfig.from_env())
    assert document["statistics"]["tsg"]["status"] == "ready"
    port = next(node for node in _nodes(document, "Port") if node["name"] == "_items")
    assert port["properties"]["export"] == "route" and port["properties"]["routes"] == ["GET /items"]
    edges = {x["target"]["name"]: x["edge"] for x in _typed(document, "CONFIGURES")}
    assert {name: edge["properties"]["reader_count"] for name, edge in edges.items()} == {"web": 1, "core": 2}
    assert {edge["confidence"] for edge in edges.values()} == {0.8}
    assert {edge["resolution"] for edge in edges.values()} == {"heuristic"}


def test_deployment_units_and_deploys_to() -> None:
    document = _build(CASES / "multi_package")
    assert {node["path"] for node in _nodes(document, "DeploymentUnit")} == {"Dockerfile", "deploy/Dockerfile.worker"}
    unit = next(node for node in _nodes(document, "DeploymentUnit") if node["path"] == "Dockerfile")
    assert unit["id"] == "vgar:t/arch:deployment_unit:Dockerfile"
    edges = _typed(document, "DEPLOYS_TO")
    assert [(x["source"]["name"], x["target"]["path"]) for x in edges] == [("app", "Dockerfile")]
    assert edges[0]["edge"]["confidence"] == 0.6 and edges[0]["edge"]["resolution"] == "heuristic"


def test_services_and_communicates() -> None:
    document = _build(CASES / "multi_package")
    services = {node["name"]: node for node in _nodes(document, "Service")}
    assert set(services) == {"api", "db"}
    assert services["db"]["id"] == "vgar:t/arch:service:docker-compose.yml:db"
    assert services["db"]["properties"] == {"image": "postgres:16", "build_context": None, "compose_file": "docker-compose.yml"}
    assert services["api"]["properties"]["build_context"] == "."
    edges = _typed(document, "COMMUNICATES_WITH")
    assert [(x["source"]["name"], x["target"]["name"]) for x in edges] == [("api", "db")]
    assert edges[0]["edge"]["confidence"] == 0.7 and edges[0]["edge"]["resolution"] == "heuristic"


def test_broken_compose_is_reported_not_fatal() -> None:
    deployment = _build(CASES / "multi_package")["statistics"]["arch"]["deployment"]
    assert (deployment["dockerfiles"], deployment["compose_files"]) == (2, 2)
    assert [error["path"] for error in deployment["errors"]] == ["broken/compose.yaml"]


def test_parse_copy_sources() -> None:
    assert arch_lift.parse_copy_sources("COPY a b /d\n") == ["a", "b"]
    assert arch_lift.parse_copy_sources('COPY ["a b", "/d"]\n') == ["a b"]
    assert arch_lift.parse_copy_sources("COPY --chown=1:1 a/ /d\n") == ["a"]
    assert arch_lift.parse_copy_sources("COPY a \\\n  b /d\n") == ["a", "b"]
    assert arch_lift.parse_copy_sources("COPY --from=x a /d\nADD c /d\n") == ["c"]
    assert arch_lift.parse_copy_sources("COPY ../a *.py /d\nADD http://x/y /d\n") == []
    assert arch_lift.parse_copy_sources("copy . /d\n") == ["."]
    assert arch_lift.parse_copy_sources("RUN COPY a /d\n# COPY b /d\n") == []


def test_copy_dot_deploys_every_component(tmp_path: Path) -> None:
    _write(tmp_path, {"x/__init__.py": "", "y/__init__.py": "", "Dockerfile": "FROM a\nCOPY . /srv\n"})
    assert {x["source"]["name"] for x in _typed(_build(tmp_path), "DEPLOYS_TO")} == {"x", "y"}


def test_module_mode_deploys_by_file(tmp_path: Path) -> None:
    _write(tmp_path, {"a.py": "def f():\n    return 1\n", "b.py": "def g():\n    return 1\n", "Dockerfile": "FROM a\nCOPY a.py /srv/\n"})
    assert [x["source"]["name"] for x in _typed(_build(tmp_path), "DEPLOYS_TO")] == ["a"]


def test_compose_bad_references_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, {"compose.yaml": "services:\n  api:\n    depends_on: [ghost, api]\n  web:\n    depends_on:\n      ghost:\n        condition: x\n"})
    document = _build(tmp_path)
    assert {node["name"] for node in _nodes(document, "Service")} == {"api", "web"}
    assert _typed(document, "COMMUNICATES_WITH") == []


def test_compose_services_not_a_mapping(tmp_path: Path) -> None:
    _write(tmp_path, {"compose.yml": "services: [a]\n"})
    document = _build(tmp_path)
    assert _nodes(document, "Service") == []
    assert [error["path"] for error in document["statistics"]["arch"]["deployment"]["errors"]] == ["compose.yml"]


def test_non_utf8_dockerfile_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, {"x/__init__.py": "", "y/__init__.py": ""})
    (tmp_path / "Dockerfile").write_bytes(b"FROM a\nCOPY . /srv \xff\n")
    document = _build(tmp_path)
    assert [node["path"] for node in _nodes(document, "DeploymentUnit")] == ["Dockerfile"]
    assert _typed(document, "DEPLOYS_TO") == []
    assert [error["path"] for error in document["statistics"]["arch"]["deployment"]["errors"]] == ["Dockerfile"]


def test_dockerfile_change_changes_graph_version(tmp_path: Path) -> None:
    _write(tmp_path, {"x.py": "def f():\n    return 1\n", "Dockerfile": "FROM a\n"})
    before = _build(tmp_path)["graph_version"]
    (tmp_path / "Dockerfile").write_text("FROM b\n", encoding="utf-8")
    assert _build(tmp_path)["graph_version"] != before


def test_signals_report() -> None:
    signals = _build(CASES / "multi_package")["statistics"]["arch"]["signals"]
    assert signals == {"package_path": "used", "density": "used", "class_ownership": "used", "naming": "used",
                       "route_config": "absent", "co_change": "unavailable", "deployment": "used", "test_grouping": "used"}


def test_signals_absent_on_empty_repo(tmp_path: Path) -> None:
    signals = _build(tmp_path)["statistics"]["arch"]["signals"]
    assert signals == {"package_path": "absent", "density": "absent", "class_ownership": "absent", "naming": "absent",
                       "route_config": "absent", "co_change": "unavailable", "deployment": "absent", "test_grouping": "absent"}


def test_lift_only_adds(monkeypatch: pytest.MonkeyPatch) -> None:
    with_arch = _build(CASES / "multi_package")
    monkeypatch.setattr(arch_lift, "lift", lambda *args, **kwargs: arch_lift.LiftResult())
    without = _build(CASES / "multi_package")
    arch_types = {"Component", "Port", "Service", "DeploymentUnit"}
    assert [node for node in with_arch["nodes"] if node["type"] not in arch_types] == without["nodes"]
    assert [edge for edge in with_arch["edges"] if edge["type"] not in G_ARCH_EDGE_TYPES] == without["edges"]


def test_may_call_does_not_change_weight() -> None:
    document = _build(CASES / "multi_package")
    assert any(edge["type"] == "MAY_CALL" for edge in document["edges"])
    db = next(node for node in _nodes(document, "Component") if node["name"] == "db")
    assert db["properties"]["internal_dependency_weight"] == 1


def _sorted_items(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return sorted(document["nodes"], key=lambda n: n["id"]), sorted(document["edges"], key=lambda e: e["id"])


def test_incremental_equals_rebuild(tmp_path: Path) -> None:
    root = shutil.copytree(CASES / "multi_package", tmp_path / "r")
    builder = IncrementalGraphBuilder("t/arch", "rev")
    builder.build(root)
    target = root / "db" / "store.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n\ndef extra():\n    return normalize('x')\n", encoding="utf-8")
    updated, _ = builder.update(root)
    fresh = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(root)
    assert _sorted_items(updated) == _sorted_items(fresh)
    assert updated["statistics"]["arch"] == fresh["statistics"]["arch"]
    assert any(node["qualified_name"] == "db.store.extra" for node in _nodes(updated, "Port"))


def test_subgraph_query_ignores_g_arch_edges(tmp_path: Path) -> None:
    document = _build(CASES / "multi_package")
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.initialize()
    store.ingest(document)
    module = next(node for node in _nodes(document, "Module") if node["qualified_name"] == "app")
    _, edges = store.get_subgraph(module["id"], depth=2)
    assert edges and not {edge.edge_type for edge in edges} & G_ARCH_EDGE_TYPES


def test_structural_check_accepts_graph_with_g_arch() -> None:
    root = CASES / "multi_package"
    document = _build(root)
    sources = {node["path"]: (root / node["path"]).read_bytes() for node in _nodes(document, "File")}
    result = check_structure(document, document, before_sources=sources, after_sources=sources)
    assert result.status != "ERROR", result.details["diagnostics"]


def test_compose_invalid_date_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, {"compose.yml": "services:\n  api:\n    image: 2001-13-45\n"})
    document = _build(tmp_path)
    assert [error["path"] for error in document["statistics"]["arch"]["deployment"]["errors"]] == ["compose.yml"]


def test_compose_non_string_fields_are_not_stored(tmp_path: Path) -> None:
    _write(tmp_path, {"compose.yml": "services:\n  api:\n    image: 2001-01-01\n    build: 5\n"})
    document = _build(tmp_path)
    properties = _nodes(document, "Service")[0]["properties"]
    assert properties["image"] is None and properties["build_context"] is None
    json.dumps(document)


def test_unreadable_deployment_file_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, {"x.py": "def f():\n    return 1\n", "Dockerfile": "FROM a\n"})
    real = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.name == "Dockerfile":
            raise PermissionError("denied")
        return real(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    document = _build(tmp_path)
    assert _nodes(document, "DeploymentUnit") == []
    deployment = document["statistics"]["arch"]["deployment"]
    assert deployment["dockerfiles"] == 1 and [error["path"] for error in deployment["errors"]] == ["Dockerfile"]


# boundary_cases: every expected value below is written by hand; the call answers are the '# expect:' comments.
BOUNDARY_PORTS = {
    "api.handlers.create_order", "api.handlers.hook_order", "api.handlers.dispatch", "api.handlers.late", "api.handlers.dynamic",
    "services.orders.place_order", "services.orders.save_with", "services.orders.run_hook",
    "services.pricing.discount", "services.pricing._internal", "services.pricing.format_total", "services.pricing.outer",
    "storage.base.BaseStore.save", "storage.base.BaseStore.flush", "storage.sql.SqlStore.save", "storage.sql.connect",
    "storage.sql.format_total", "storage.memory.MemoryStore.save", "storage.memory.snapshot",
    "plugins.registry.Plugin.run", "plugins.registry.Worker.process",
}
BOUNDARY_TRUE_PAIRS = {("api", "services"), ("api", "storage"), ("api", "plugins"), ("services", "storage"),
                       ("storage", "services"), ("plugins", "storage")}
BOUNDARY_TRUE_CONSUMES = {
    ("api", "services.orders.place_order"), ("api", "services.orders.run_hook"), ("api", "services.pricing.discount"),
    ("api", "services.pricing._internal"), ("api", "storage.sql.connect"), ("api", "plugins.registry.Worker.process"),
    ("services", "storage.sql.format_total"), ("services", "storage.sql.SqlStore.save"),
    ("services", "storage.memory.MemoryStore.save"), ("services", "storage.memory.snapshot"),
    ("storage", "services.pricing.discount"), ("plugins", "storage.base.BaseStore.flush"),
}


def test_boundary_expected_calls_match_runtime(tmp_path: Path) -> None:
    root = shutil.copytree(CASES / "boundary_cases", tmp_path / "r")
    tool = Path(__file__).parent / "fixtures" / "vgar-callgraph-cases" / "tools" / "verify_expect.py"
    result = subprocess.run([sys.executable, "-I", str(tool), str(root), str(root)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout
    assert "20 annotated calls, 0 mismatches" in result.stdout


def test_boundary_components_and_ports() -> None:
    document = _build(CASES / "boundary_cases")
    components = {node["name"]: node["properties"]["files"] for node in _nodes(document, "Component")}
    assert components == {
        "api": ["api/__init__.py", "api/handlers.py"],
        "services": ["services/__init__.py", "services/orders.py", "services/pricing.py"],
        "storage": ["storage/__init__.py", "storage/base.py", "storage/memory.py", "storage/sql.py"],
        "plugins": ["plugins/__init__.py", "plugins/registry.py"],
    }
    assert document["statistics"]["arch"]["unassigned_source_files"] == 1  # run_all.py
    assert {node["qualified_name"] for node in _nodes(document, "Port")} == BOUNDARY_PORTS


def test_boundary_depends_on_static() -> None:
    document = _build(CASES / "boundary_cases")
    assert _depends(document) == {
        ("api", "services"): {"weight": 12, "call_count": 6, "import_count": 6},
        ("api", "storage"): {"weight": 1, "call_count": 0, "import_count": 1},
        ("services", "storage"): {"weight": 6, "call_count": 3, "import_count": 3},
        ("storage", "services"): {"weight": 2, "call_count": 1, "import_count": 1},
        ("plugins", "storage"): {"weight": 1, "call_count": 0, "import_count": 1},
    }
    # Known limit: api only reaches plugins through a duck-typed call, which is a MAY_CALL and is not counted.
    assert BOUNDARY_TRUE_PAIRS - set(_depends(document)) == {("api", "plugins")}


def test_boundary_consumes_port_static() -> None:
    document = _build(CASES / "boundary_cases")
    found = {(x["source"]["name"], x["target"]["qualified_name"]) for x in _typed(document, "CONSUMES_PORT")}
    # Known limits of static resolution: duck typing, lazy import, inherited self-call, callback, subclass dispatch.
    assert BOUNDARY_TRUE_CONSUMES - found == {
        ("api", "plugins.registry.Worker.process"), ("api", "storage.sql.connect"), ("plugins", "storage.base.BaseStore.flush"),
        ("services", "storage.memory.snapshot"), ("services", "storage.sql.SqlStore.save"), ("services", "storage.memory.MemoryStore.save"),
    }
    # A call through a parameter typed BaseStore binds to the base method, which never runs.
    assert found - BOUNDARY_TRUE_CONSUMES == {("services", "storage.base.BaseStore.save")}


def test_boundary_private_function_is_counted_but_not_a_port() -> None:
    document = _build(CASES / "boundary_cases")
    calls = _depends(document)[("api", "services")]["call_count"]
    assert calls == 6 and "services.pricing._secret" not in {node["qualified_name"] for node in _nodes(document, "Port")}
