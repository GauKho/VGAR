"""L2-2: MAY_CALL edges for calls that could not be resolved (proposal lines 551-567)."""
from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from vgar.contracts.schema import (
    PROFILE_FULL_VGAR_MCP,
    PROFILE_LEGACY_W10,
    GraphValidationError,
    project_legacy_w10,
    validate_graph_document,
)
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.incremental import IncrementalGraphBuilder, affected_node_count
from vgar.graph.sqlite_store import SQLiteGraphStore


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def _build(root: Path) -> dict:
    return PythonGraphBuilder(repo_key="t/repo", repository_revision="rev").build(root)


def _document_with_may_call(tmp_path: Path, mutate: Callable[[dict, dict], None]) -> dict:
    document = _build(_write(tmp_path, {"src/a.py": "def g():\n    return 1\n\ndef f():\n    return g()\n"}))
    edge = copy.deepcopy(next(e for e in document["edges"] if e["type"] == "CALLS"))
    edge.update(id="may-call-1", type="MAY_CALL", confidence=0.3, resolution="heuristic")
    edge["provenance"]["evidence"] = ["name_match"]
    mutate(edge, document)
    document["edges"].append(edge)
    return document


def test_valid_may_call_passes(tmp_path: Path) -> None:
    validate_graph_document(_document_with_may_call(tmp_path, lambda edge, document: None))


def _set_evidence(value):
    return lambda edge, document: edge["provenance"].update(evidence=value)


def _target_module(edge: dict, document: dict) -> None:
    edge["target_id"] = next(n["id"] for n in document["nodes"] if n["type"] == "Module")


@pytest.mark.parametrize(("mutate", "message"), [
    (_set_evidence([]), "provenance.evidence"),
    (lambda edge, document: edge["provenance"].pop("evidence"), "provenance.evidence"),
    (_set_evidence([""]), "provenance.evidence"),
    (lambda edge, document: edge.update(confidence=0.51), "at most 0.50"),
    (_target_module, "invalid endpoints for MAY_CALL"),
], ids=["empty", "missing", "blank", "over_cap", "wrong_endpoint"])
def test_invalid_may_call_rejected(tmp_path: Path, mutate, message: str) -> None:
    with pytest.raises(GraphValidationError, match=message):
        validate_graph_document(_document_with_may_call(tmp_path, mutate))


REPOS = ("class UserRepo:\n    def check(self): ...\n\nclass OrderRepo:\n    def check(self): ...\n\n"
         "class CacheRepo:\n    def check(self): ...\n")
SERVICE = ("class Service:\n    def __init__(self, repo):\n        self.repo = repo\n\n"
           "    def run(self):\n        return self.repo.check()\n")
SIX_REPOS = "".join(f"class R{i}:\n    def check(self): ...\n\n" for i in range(6))
NAME_ONLY = ("name_match", "unresolved_type")
ALL3 = [(f"repos.{cls}.check", 0.3, NAME_ONLY) for cls in ("CacheRepo", "OrderRepo", "UserRepo")]


def _may_call_edges(document: dict) -> list[dict]:
    return [e for e in document["edges"] if e["type"] == "MAY_CALL"]


def _may_calls(document: dict) -> list[tuple]:
    nodes = {n["id"]: n for n in document["nodes"]}
    return sorted((nodes[e["target_id"]]["qualified_name"], e["confidence"], tuple(e["provenance"]["evidence"]))
                  for e in _may_call_edges(document))


def test_three_candidates(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    assert _may_calls(document) == ALL3
    edge = _may_call_edges(document)[0]
    assert edge["resolution"] == "heuristic"
    assert edge["provenance"]["source_tool"] == "vgar-builder-heuristic"
    assert edge["provenance"]["rule_id"] == "python.call.may_call.name.v1"
    assert edge["properties"] == {"match_kind": "name", "candidate_count": 3}
    source = next(n for n in document["nodes"] if n["id"] == edge["source_id"])
    assert source["type"] == "CallSite"
    assert (source["properties"]["resolution_status"], source["properties"]["candidate_count"]) == ("unresolved", 0)
    assert document["statistics"]["may_call"] == {"rule_version": "may-call-v1", "edge_count": 3, "callsite_count": 1,
                                                  "skipped_over_cap": 0, "by_match_kind": {"name": 3}}


def test_external_library_skipped(tmp_path: Path) -> None:
    app = "import numpy as np\n\ndef f():\n    return np.check()\n"
    assert _may_calls(_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": app}))) == []


def test_internal_alias_kept(tmp_path: Path) -> None:
    app = "import repos as r\n\ndef f():\n    return r.check()\n"
    document = _build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": app}))
    assert _may_calls(document) == [(name, 0.5, ("name_match", "import_path", "unresolved_type"))
                                    for name, _, _ in ALL3]


def test_bare_call_skipped(tmp_path: Path) -> None:
    app = "def f():\n    return check()\n"
    assert _may_calls(_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": app}))) == []


def test_more_than_five_candidates_drops_call(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/repos.py": SIX_REPOS, "src/app.py": SERVICE}))
    assert _may_calls(document) == []
    assert document["statistics"]["may_call"]["skipped_over_cap"] == 1
    assert document["statistics"]["may_call"]["by_match_kind"] == {}


def test_parameter_receiver(tmp_path: Path) -> None:
    app = "def f(repo):\n    return repo.check()\n"
    assert _may_calls(_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": app}))) == ALL3


def test_class_call_targets_init(tmp_path: Path) -> None:
    files = {"src/models.py": "class Foo:\n    def __init__(self): ...\n\nclass Bar:\n    pass\n",
             "src/app.py": "def f(x):\n    x.Foo()\n    x.Bar()\n"}
    assert _may_calls(_build(_write(tmp_path, files))) == [("models.Foo.__init__", 0.3, NAME_ONLY)]


def test_import_path_coherence(tmp_path: Path) -> None:
    files = {"src/lib.py": "class Lib:\n    def ping(self): ...\n",
             "src/other.py": "class Other:\n    def ping(self): ...\n",
             "src/app.py": ("from lib import Lib\n\nclass Local:\n    def ping(self): ...\n\n"
                            "def f(x):\n    return x.ping()\n")}
    assert _may_calls(_build(_write(tmp_path, files))) == [
        ("app.Local.ping", 0.5, ("name_match", "same_module_scope", "unresolved_type")),
        ("lib.Lib.ping", 0.5, ("name_match", "import_path", "unresolved_type")),
        ("other.Other.ping", 0.3, NAME_ONLY),
    ]


def test_existing_graph_unchanged(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE})
    default = _build(root)
    builder = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev")
    builder._emit_may_call = False
    off = builder.build(root)
    assert _may_call_edges(off) == []
    assert default["nodes"] == off["nodes"]
    assert [e for e in default["edges"] if e["type"] != "MAY_CALL"] == off["edges"]
    assert default["graph_version"] == off["graph_version"]
    assert default["statistics"]["unresolved_call_count"] == off["statistics"]["unresolved_call_count"]


def test_duplicate_definitions_are_separate_candidates(tmp_path: Path) -> None:
    files = {"src/d.py": "class A:\n    if X:\n        def ping(self): ...\n    else:\n        def ping(self): ...\n",
             "src/app.py": "def f(x):\n    x.ping()\n"}
    edges = _may_call_edges(_build(_write(tmp_path, files)))
    assert len(edges) == 2 and len({e["target_id"] for e in edges}) == 2


def test_unusual_callee_text(tmp_path: Path) -> None:
    files = {"src/d.py": "class A:\n    def ping(self): ...\n",
             "src/app.py": "def f(a, b):\n    a[0].ping()\n    b(a.ping)()\n    a().ping()\n"}
    document = _build(_write(tmp_path, files))
    nodes = {n["id"]: n for n in document["nodes"]}
    assert sorted(nodes[e["source_id"]]["properties"]["callee_text"] for e in _may_call_edges(document)) == [
        "a().ping", "a[0].ping"]


def test_call_to_enclosing_method_is_valid(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/a.py": "class A:\n    def ping(self, o):\n        return o.ping()\n"}))
    assert [name for name, _, _ in _may_calls(document)] == ["a.A.ping"]


def test_namespace_package_is_internal(tmp_path: Path) -> None:
    files = {"src/ns/mod.py": "class A:\n    def ping(self): ...\n", "src/app.py": "import ns\n\ndef f():\n    return ns.ping()\n"}
    assert _may_calls(_build(_write(tmp_path, files))) == [("ns.mod.A.ping", 0.3, NAME_ONLY)]


def test_function_local_import_known_limit(tmp_path: Path) -> None:
    # The builder records module-level imports only (builder.py, _walk_scope), so this library call still gets a candidate.
    files = {"src/d.py": "class A:\n    def ping(self): ...\n",
             "src/app.py": "def f():\n    import numpy as np\n    return np.ping()\n"}
    assert len(_may_calls(_build(_write(tmp_path, files)))) == 1


class _FakeScip:
    def __init__(self, builder: PythonGraphBuilder, status: str, name: str = "check", empty: bool = False) -> None:
        self.builder, self.status, self.name, self.empty = builder, status, name, empty

    def resolve(self, path: str, line: int, column: int) -> tuple[str, list[str]]:
        return self.status, [] if self.empty else sorted(n["id"] for n in self.builder.nodes if n["name"] == self.name)


class _FakeLsp(dict):
    def __init__(self, builder: PythonGraphBuilder) -> None:
        super().__init__()
        self.builder = builder

    def get(self, node_id, default=None):
        return "ambiguous", sorted(n["id"] for n in self.builder.nodes if n["name"] == "check")


@pytest.fixture
def _scip_build(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(PythonGraphBuilder, "_link_chain_references", lambda self: None)

    def build(root: Path, status: str, **fake) -> dict:
        builder = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev")
        builder.scip_resolver = _FakeScip(builder, status, **fake)
        builder.resolver_report.update(tool="scip-python", tool_version="0.6.6")
        return builder.build(root)

    return build


def test_scip_ambiguous(tmp_path: Path, _scip_build) -> None:
    document = _scip_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE}), "ambiguous")
    assert _may_calls(document) == [(name, 0.42, ("scip_ambiguous",)) for name, _, _ in ALL3]
    provenance = _may_call_edges(document)[0]["provenance"]
    assert (provenance["source_tool"], provenance["source_tool_version"]) == ("scip-python", "0.6.6")
    assert provenance["rule_id"] == "python.call.may_call.scip_ambiguous.v1"
    assert document["statistics"]["may_call"]["by_match_kind"] == {"scip_ambiguous": 3}


def test_scip_ambiguous_imported(tmp_path: Path, _scip_build) -> None:
    document = _scip_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": "import repos\n\n" + SERVICE}), "ambiguous")
    assert _may_calls(document) == [(name, 0.5, ("scip_ambiguous", "import_path")) for name, _, _ in ALL3]


def test_lsp_ambiguous(tmp_path: Path) -> None:
    builder = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev")
    builder.lsp_results = _FakeLsp(builder)
    builder.resolver_report["lsp"] = {"server_info": {"name": "pyright", "version": "1.1.0"}}
    document = builder.build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    assert _may_calls(document) == [(name, 0.42, ("lsp_ambiguous",)) for name, _, _ in ALL3]
    provenance = _may_call_edges(document)[0]["provenance"]
    assert (provenance["source_tool"], provenance["source_tool_version"]) == ("pyright", "1.1.0")
    assert provenance["rule_id"] == "python.call.may_call.lsp_ambiguous.v1"


@pytest.mark.parametrize("status", ["external_or_non_callable", "local_non_callable"])
def test_scip_external_no_edge(tmp_path: Path, _scip_build, status: str) -> None:
    assert _may_calls(_scip_build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE}), status)) == []


def test_ambiguous_empty_no_name_fallback(tmp_path: Path, _scip_build) -> None:
    root = _write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE})
    assert _may_calls(_scip_build(root, "ambiguous", empty=True)) == []


def test_ambiguous_over_cap(tmp_path: Path, _scip_build) -> None:
    document = _scip_build(_write(tmp_path, {"src/repos.py": SIX_REPOS, "src/app.py": SERVICE}), "ambiguous")
    assert _may_calls(document) == []
    assert document["statistics"]["may_call"]["skipped_over_cap"] == 1


def test_ambiguous_class_maps_to_init(tmp_path: Path, _scip_build) -> None:
    files = {"src/models.py": "class Foo:\n    def __init__(self): ...\n", "src/app.py": "def f(x):\n    x.Foo()\n"}
    assert _may_calls(_scip_build(_write(tmp_path, files), "ambiguous", name="Foo")) == [
        ("models.Foo.__init__", 0.42, ("scip_ambiguous",))]


def test_get_subgraph_excludes_may_call(tmp_path: Path) -> None:
    document = _build(_write(tmp_path / "repo", {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    nodes, edges = store.get_subgraph(_may_call_edges(document)[0]["source_id"], depth=2, limit=1000)
    assert all(edge.edge_type != "MAY_CALL" for edge in edges)
    assert "repos.UserRepo.check" not in {node.qualified_name for node in nodes}


def test_sqlite_round_trip(tmp_path: Path) -> None:
    document = _build(_write(tmp_path / "repo", {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    loaded = store.load_document(document["graph_version"])
    validate_graph_document(loaded)
    assert _may_calls(loaded) == _may_calls(document)


def _normalized(document: dict) -> str:
    document = json.loads(json.dumps(document))
    document["statistics"].pop("build_time_ms", None)
    return json.dumps(document, sort_keys=True)


def test_incremental_updates_candidates_across_files(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE})
    builder = IncrementalGraphBuilder("t/repo", "rev")
    builder.build(root)
    _write(root, {"src/extra.py": "class Extra:\n    def check(self): ...\n"})
    updated, _ = builder.update(root)
    assert "extra.Extra.check" in {name for name, _, _ in _may_calls(updated)}
    assert _normalized(updated) == _normalized(_build(root))


def test_affected_node_count_ignores_may_call(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE})
    previous = _build(root)
    _write(root, {"src/extra.py": "class Extra:\n    def check(self): ...\n"})
    current = _build(root)

    def without_may_call(document: dict) -> dict:
        return {**document, "edges": [e for e in document["edges"] if e["type"] != "MAY_CALL"]}

    assert affected_node_count(previous, current) == affected_node_count(without_may_call(previous), without_may_call(current))


FIVE_REPOS = "".join(f"class R{i}:\n    def check(self): ...\n\n" for i in range(5))
PING = "class A:\n    def ping(self): ...\n    def join(self): ...\n    def format(self): ...\n    def get(self): ...\n    def exists(self): ...\n"


def test_exactly_five_candidates_keeps_edges(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/repos.py": FIVE_REPOS, "src/app.py": SERVICE}))
    assert len(_may_calls(document)) == 5
    assert document["statistics"]["may_call"]["skipped_over_cap"] == 0


def test_imported_symbol_from_library_skipped(tmp_path: Path) -> None:
    app = "from numpy import linalg\n\ndef f():\n    return linalg.ping()\n"
    assert _may_calls(_build(_write(tmp_path, {"src/d.py": PING, "src/app.py": app}))) == []


def test_from_package_import_module_counts_as_imported(tmp_path: Path) -> None:
    files = {"src/pkg/__init__.py": "", "src/pkg/mod.py": "class A:\n    def ping(self): ...\n",
             "src/app.py": "from pkg import mod\n\ndef f(x):\n    return x.ping()\n"}
    assert _may_calls(_build(_write(tmp_path, files))) == [("pkg.mod.A.ping", 0.5, ("name_match", "import_path", "unresolved_type"))]


def test_relative_import_is_internal(tmp_path: Path) -> None:
    files = {"src/pkg/__init__.py": "", "src/pkg/b.py": "class A:\n    def ping(self): ...\n",
             "src/pkg/a.py": "from . import b as bb\n\ndef f():\n    return bb.ping()\n"}
    assert [name for name, _, _ in _may_calls(_build(_write(tmp_path, files)))] == ["pkg.b.A.ping"]


@pytest.mark.parametrize("call", [
    '", ".join(p)', '"{}".format(1)', '{}.get("k")', "[1].ping()", 'f"{p}".ping()', 'b"x".ping()', "str.join(',', p)", "object.ping(p)",
], ids=["str_join", "str_format", "dict", "list", "fstring", "bytes", "builtin_str", "builtin_object"])
def test_literal_and_builtin_receivers_skipped(tmp_path: Path, call: str) -> None:
    app = f"def f(p):\n    return {call}\n"
    assert _may_calls(_build(_write(tmp_path, {"src/d.py": PING, "src/app.py": app}))) == []


@pytest.mark.parametrize("app", [
    "from pathlib import Path\n\ndef f(x):\n    return Path(x).exists()\n",
    "import numpy as np\n\ndef f():\n    return (np).ping()\n",
    "import numpy as np\n\ndef f():\n    return np\\n        .ping()\n",
], ids=["constructor", "parenthesized", "line_continuation"])
def test_library_root_recognised_through_syntax(tmp_path: Path, app: str) -> None:
    assert _may_calls(_build(_write(tmp_path, {"src/d.py": PING, "src/app.py": app}))) == []


def test_parameter_shadowing_builtin_is_kept(tmp_path: Path) -> None:
    app = "def f(str):\n    return str.ping()\n"
    assert [name for name, _, _ in _may_calls(_build(_write(tmp_path, {"src/d.py": PING, "src/app.py": app})))] == ["d.A.ping"]


def test_super_call_excludes_own_class(tmp_path: Path) -> None:
    source = "class B:\n    def get(self): ...\n\nclass C(B):\n    def get(self):\n        return super().get()\n"
    assert [name for name, _, _ in _may_calls(_build(_write(tmp_path, {"src/a.py": source})))] == ["a.B.get"]


def test_legacy_profile_rejects_new_types(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    validate_graph_document(document)
    with pytest.raises(GraphValidationError, match="not allowed in profile legacy_w10"):
        validate_graph_document(document, profile=PROFILE_LEGACY_W10)


def test_unknown_profile_rejected(tmp_path: Path) -> None:
    document = _build(_write(tmp_path, {"src/a.py": "def f():\n    return 1\n"}))
    with pytest.raises(ValueError, match="unknown schema profile"):
        validate_graph_document(document, profile="other")


def test_legacy_projection_matches_graph_without_new_facts(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/repos.py": REPOS, "src/app.py": SERVICE})
    full = _build(root)
    builder = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev")
    builder._emit_may_call = False
    builder._lift_architecture = lambda: None  # G_arch is a new fact too; this test compares against the graph without them.
    without = builder.build(root)
    legacy = project_legacy_w10(full)
    validate_graph_document(legacy, profile=PROFILE_LEGACY_W10)
    assert legacy["graph_version"] == full["statistics"]["legacy_graph_version"] != full["graph_version"]
    assert {n["graph_version"] for n in [*legacy["nodes"], *legacy["edges"]]} == {legacy["graph_version"]}

    def strip(items: list[dict]) -> list[dict]:
        return [{k: v for k, v in item.items() if k != "graph_version"} for item in items]

    assert strip(legacy["nodes"]) == strip(without["nodes"]) and strip(legacy["edges"]) == strip(without["edges"])
    statistics = legacy["statistics"]
    assert statistics["schema_profile"] == PROFILE_LEGACY_W10 and "may_call" not in statistics
    assert statistics["edge_count"] == len(legacy["edges"]) and "MAY_CALL" not in statistics["edge_counts_by_type"]
    assert full["statistics"]["schema_profile"] == PROFILE_FULL_VGAR_MCP and len(full["edges"]) > len(legacy["edges"])


def test_full_graph_version_depends_on_resolver_profile_but_legacy_does_not(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, {"src/a.py": "def f():\n    return 1\n"})
    before = _build(root)
    monkeypatch.setattr("vgar.graph.builder.RESOLVER_PROFILE", "another-profile")
    after = _build(root)
    assert before["graph_version"] != after["graph_version"]
    assert before["statistics"]["legacy_graph_version"] == after["statistics"]["legacy_graph_version"]


def test_graph_version_still_tracks_source_content(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/a.py": "def f():\n    return 1\n"})
    first = _build(root)
    _write(root, {"src/a.py": "def f():\n    return 2\n"})
    assert first["graph_version"] != _build(root)["graph_version"]


def test_ingest_same_version_is_idempotent(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    document = _build(_write(tmp_path / "repo", {"src/repos.py": REPOS, "src/app.py": SERVICE}))
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    with caplog.at_level("WARNING"):
        store.ingest(document)
    assert "already exists" in caplog.text
    assert _may_calls(store.load_document(document["graph_version"])) == _may_calls(document)


def test_ingest_over_unfinished_build_still_fails(tmp_path: Path) -> None:
    document = _build(_write(tmp_path / "repo", {"src/a.py": "def f():\n    return 1\n"}))
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    with sqlite3.connect(tmp_path / "graph.db") as connection:
        connection.execute("UPDATE graph_metadata SET status = 'building'")
    with pytest.raises(ValueError, match="not ready"):
        store.ingest(document)
