"""L1-3: Route, Schema and IMPLEMENTS facts derived from the builder's own data (tree-sitter-graph on)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vgar.contracts.schema import validate_graph_document
from vgar.graph import tsg_extractor
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.tsg_extractor import TsgConfig, TsgFileFacts

LAYER1_TYPES = {"Route", "Schema"}


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def _build(root: Path, tsg: TsgConfig | None) -> dict:
    return PythonGraphBuilder(repo_key="t/repo", repository_revision="rev", tsg=tsg).build(root)


@pytest.fixture
def _build_ready(monkeypatch: pytest.MonkeyPatch):
    """Build with a 'ready' tree-sitter-graph that emits no facts of its own."""
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, root, path: TsgFileFacts())

    def build(root: Path) -> dict:
        document = _build(root, TsgConfig(executable=Path("tsg"), tree_sitter_dir=Path(".")))
        assert document["statistics"]["tsg"]["status"] == "ready"
        validate_graph_document(document)
        return document

    return build


def _edges(document: dict, kind: str) -> list[tuple[dict, dict, dict]]:
    nodes = {n["id"]: n for n in document["nodes"]}
    return [(nodes[e["source_id"]], nodes[e["target_id"]], e) for e in document["edges"] if e["type"] == kind]


API_SOURCE = (
    "@app.post('/pay')\n"
    "def pay(): ...\n"
    "@app.get('/items')\n"
    "@app.get('/items')\n"
    "def items(): ...\n"
    "@router.route('/legacy', methods=['GET', 'POST'])\n"
    "def legacy(): ...\n"
    "@app.get(PATH)\n"
    "def dyn(): ...\n"
    "@cache.get\n"
    "def cached(): ...\n"
)


def test_routes_from_decorators(tmp_path: Path, _build_ready) -> None:
    document = _build_ready(_write(tmp_path, {"src/api.py": API_SOURCE}))
    routes = {n["name"]: n for n in document["nodes"] if n["type"] == "Route"}
    assert sorted(routes) == ["GET /items", "GET,POST /legacy", "POST /pay"]
    legacy = routes["GET,POST /legacy"]
    handler = next(n for n in document["nodes"] if n["qualified_name"] == "api.legacy")
    assert legacy["properties"] == {"methods": ["GET", "POST"], "route_path": "/legacy",
                                    "decorator": "@router.route('/legacy', methods=['GET', 'POST'])",
                                    "receiver": "router"}
    assert legacy["range"] == handler["range"]
    assert legacy["qualified_name"] == "api.legacy::<route:GET,POST /legacy>"
    references = _edges(document, "REFERENCES")
    contains = _edges(document, "CONTAINS")
    for route in routes.values():
        targets = [(target, edge) for source, target, edge in references if source["id"] == route["id"]]
        assert len(targets) == 1
        target, edge = targets[0]
        assert target["type"] == "Function" and edge["confidence"] == 0.8
        assert edge["provenance"]["rule_id"] == "python.layer1.route.v1"
        assert [s["type"] for s, t, _ in contains if t["id"] == route["id"]] == ["Module"]
    assert document["statistics"]["tsg"]["added"]["Route"] == 3


def test_routes_of_duplicate_handlers_get_distinct_ids(tmp_path: Path, _build_ready) -> None:
    source = "if X:\n    @app.get('/a')\n    def h(): ...\nelse:\n    @app.get('/a')\n    def h(): ...\n"
    document = _build_ready(_write(tmp_path, {"src/dup_api.py": source}))
    routes = sorted((n for n in document["nodes"] if n["type"] == "Route"), key=lambda n: n["range"]["start_line"])
    assert [n["qualified_name"] for n in routes] == ["dup_api.h::<route:GET /a>"] * 2
    assert routes[0]["id"] != routes[1]["id"]
    assert routes[1]["id"].endswith("@definition:6:4")
    handlers = {target["id"] for source_node, target, _ in _edges(document, "REFERENCES")
                if source_node["type"] == "Route"}
    assert len(handlers) == 2


MODELS_SOURCE = (
    "from dataclasses import dataclass as dc\n"
    "import dataclasses\n"
    "import typing as t\n"
    "from pydantic import BaseModel\n"
    "@dc(frozen=True)\n"
    "class A: ...\n"
    "@dataclasses.dataclass\n"
    "class B: ...\n"
    "class C(BaseModel): ...\n"
    "class D(C): ...\n"
    "class E(t.TypedDict): ...\n"
    "if X:\n"
    "    class A2(BaseModel): ...\n"
    "else:\n"
    "    class A2(BaseModel): ...\n"
)
SCHEMA_FILES = {
    "src/models.py": MODELS_SOURCE,
    "src/sub.py": "from models import C\nclass H(C): ...\n",
    # Look-alikes without the real import are not schemas.
    "src/fake.py": "class BaseModel: ...\nclass F(BaseModel): ...\n@dataclass\nclass G: ...\n",
}


def test_schemas_require_resolved_imports(tmp_path: Path, _build_ready) -> None:
    document = _build_ready(_write(tmp_path, SCHEMA_FILES))
    schemas = [(source, target, edge) for source, target, edge in _edges(document, "REFERENCES")
               if source["type"] == "Schema"]
    assert sorted((target["name"], source["properties"]["schema_kind"], source["properties"]["evidence"],
                   edge["confidence"]) for source, target, edge in schemas) == sorted([
        ("A", "dataclass", "decorator", 1.0), ("B", "dataclass", "decorator", 1.0),
        ("C", "pydantic", "base", 1.0), ("D", "pydantic", "inherited", 0.9), ("E", "typed_dict", "base", 1.0),
        ("A2", "pydantic", "base", 1.0), ("A2", "pydantic", "base", 1.0), ("H", "pydantic", "inherited", 0.9)])
    assert all(target["type"] == "Class" for _, target, _ in schemas)
    assert len({source["id"] for source, _, _ in schemas}) == len(schemas)
    a2 = sorted((source for source, target, _ in schemas if target["name"] == "A2"),
                key=lambda node: node["range"]["start_line"])
    assert a2[1]["id"].endswith("@definition:15:4")
    for source, target, _ in schemas:
        assert source["qualified_name"] == f"{target['qualified_name']}::<schema>"
        assert (source["range"], source["content_hash"]) == (target["range"], target["content_hash"])
    contains = {target["id"]: source["type"] for source, target, _ in _edges(document, "CONTAINS")}
    assert all(contains[source["id"]] == "Module" for source, _, _ in schemas)
    assert document["statistics"]["tsg"]["added"]["Schema"] == 8


IFACES_SOURCE = (
    "from abc import ABC, ABCMeta\n"
    "from typing import Protocol, TypeVar\n"
    "class Repo(ABC): ...\n"
    "class Meta(metaclass=ABCMeta): ...\n"
    "class Reader(Protocol): ...\n"
    "class SubReader(Reader, Protocol): ...\n"
    "class SqlRepo(Repo): ...\n"
    "class Both(Meta, Reader): ...\n"
    "class Child(SqlRepo): ...\n"
    "class Plain: ...\n"
    "T = TypeVar('T')\n"
    "class GenReader(Protocol[T]): ...\n"
    "class GenImpl(GenReader): ...\n"
)


def test_implements_edges(tmp_path: Path, _build_ready) -> None:
    document = _build_ready(_write(tmp_path, {"src/ifaces.py": IFACES_SOURCE}))
    implements = _edges(document, "IMPLEMENTS")
    assert {(s["name"], t["name"], e["properties"]["interface_kind"]) for s, t, e in implements} == {
        ("SqlRepo", "Repo", "abc"), ("Both", "Meta", "abc"), ("Both", "Reader", "protocol"),
        ("GenImpl", "GenReader", "protocol")}
    assert len(implements) == 4
    inherits = {(s["id"], t["id"]): e for s, t, e in _edges(document, "INHERITS")}
    for source, target, edge in implements:
        assert edge["confidence"] == inherits[(source["id"], target["id"])]["confidence"]
        assert edge["provenance"]["rule_id"] == "python.layer1.implements.v1"
    assert document["statistics"]["tsg"]["added"]["IMPLEMENTS"] == 4


def test_layer1_facts_absent_without_tsg_and_on_fallback(tmp_path: Path) -> None:
    root = _write(tmp_path / "repo", {"src/api.py": API_SOURCE, "src/ifaces.py": IFACES_SOURCE, **SCHEMA_FILES})
    plain = _build(root, None)
    fallback = _build(root, TsgConfig(executable=tmp_path / "missing-tsg.exe", tree_sitter_dir=tmp_path))
    assert fallback["statistics"]["tsg"]["status"] == "fallback"
    for document in (plain, fallback):
        assert not LAYER1_TYPES & {n["type"] for n in document["nodes"]}
        assert not {e["type"] for e in document["edges"]} & {"IMPLEMENTS"}
    assert len(fallback["nodes"]) == len(plain["nodes"]) and len(fallback["edges"]) == len(plain["edges"])


def test_all_layer1_types_round_trip_through_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fake tree-sitter-graph facts of the L1-2/L1-3 samples (tests/ is on sys.path under pytest).
    from test_tsg_enrichment import CFG_FACTS, CFG_SOURCE, FAKE_FACTS, OTHER_FACTS, OTHER_SOURCE, SOURCE

    from vgar.graph.sqlite_store import SQLiteGraphStore

    facts = {"src/app.py": FAKE_FACTS, "src/cfg.py": CFG_FACTS, "src/other.py": OTHER_FACTS}
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, root, path: facts.get(path, TsgFileFacts()))
    root = _write(tmp_path / "repo", {"src/app.py": SOURCE, "src/cfg.py": CFG_SOURCE, "src/other.py": OTHER_SOURCE,
                                      "src/api.py": API_SOURCE, "src/ifaces.py": IFACES_SOURCE, **SCHEMA_FILES})
    document = _build(root, TsgConfig(executable=Path("tsg"), tree_sitter_dir=Path(".")))
    validate_graph_document(document)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    loaded = store.load_document(document["graph_version"])
    validate_graph_document(loaded)

    def summary(graph: dict) -> tuple:
        nodes = {n["id"]: n for n in graph["nodes"]}
        new_nodes = sorted((n["type"], n["qualified_name"]) for n in nodes.values()
                           if n["type"] in {"Identifier", "ConfigEntry", "Route", "Schema"})
        implements = sorted((nodes[e["source_id"]]["qualified_name"], nodes[e["target_id"]]["qualified_name"],
                             e["properties"]["interface_kind"]) for e in graph["edges"] if e["type"] == "IMPLEMENTS")
        return new_nodes, implements

    expected = summary(document)
    assert {kind for kind, _ in expected[0]} == {"Identifier", "ConfigEntry", "Route", "Schema"}
    assert len(expected[1]) == 4
    assert summary(loaded) == expected
