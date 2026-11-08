"""L1-1: tree-sitter-graph as an optional extra fact source merged into the builder's graph."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from vgar.contracts.schema import validate_graph_document
from vgar.graph import tsg_extractor
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.tsg_extractor import TsgConfig, TsgFileFacts, parse_graph

SOURCE = (
    "LIMIT = 10\n"
    "class Cart:\n"
    "    size: int\n"
    "    def add(self, sku):\n"
    "        self.items = check(sku)\n"
    "def check(sku):\n"
    "    return len(sku)\n"
    'TOTAL = check("ab")\n'
)

# What python.tsg emits for SOURCE (rows/cols 1-based lines, 0-based byte columns), checked
# against the real CLI by test_real_cli_emits_the_same_facts.
FAKE_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: {"type": "GlobalVariable", "name": "LIMIT", "line": 1, "col": 0, "end_line": 1, "end_col": 10},
        2: {"type": "Class", "name": "Cart", "line": 2, "col": 0, "end_line": 5, "end_col": 31},
        3: {"type": "Field", "name": "size", "line": 3, "col": 4, "end_line": 3, "end_col": 13},
        4: {"type": "Method", "name": "add", "line": 4, "col": 4, "end_line": 5, "end_col": 31},
        5: {"type": "Field", "name": "items", "line": 5, "col": 8, "end_line": 5, "end_col": 31},
        6: {"type": "CallSite", "name": "check", "line": 5, "col": 21, "end_line": 5, "end_col": 31},
        7: {"type": "Function", "name": "check", "line": 6, "col": 0, "end_line": 7, "end_col": 19},
        8: {"type": "CallSite", "name": "len", "line": 7, "col": 11, "end_line": 7, "end_col": 19},
        9: {"type": "GlobalVariable", "name": "TOTAL", "line": 8, "col": 0, "end_line": 8, "end_col": 19},
        # Module-level call: owned by Discard, not extracted by the builder either.
        10: {"type": "CallSite", "name": "check", "line": 8, "col": 8, "end_line": 8, "end_col": 19},
        # Def parameters (L1-2); `self` is dropped by the merge, not by the rules.
        11: {"type": "Identifier", "name": "self", "kind": "normal", "line": 4, "col": 12, "end_line": 4,
             "end_col": 16},
        12: {"type": "Identifier", "name": "sku", "kind": "normal", "line": 4, "col": 18, "end_line": 4,
             "end_col": 21},
        13: {"type": "Identifier", "name": "sku", "kind": "normal", "line": 6, "col": 10, "end_line": 6,
             "end_col": 13},
    },
    edges=[(2, 4, "HAS_METHOD"), (0, 7, "HAS_METHOD"), (2, 3, "CONTAINS"), (2, 5, "CONTAINS"),
           (4, 6, "HAS_CALLSITE"), (7, 8, "HAS_CALLSITE"), (0, 10, "HAS_CALLSITE"),
           (4, 11, "CONTAINS"), (4, 12, "CONTAINS"), (7, 13, "CONTAINS")],
)


def _canonical(facts: TsgFileFacts) -> tuple:
    """Facts without the CLI's node numbering."""
    key = {i: tuple(sorted(n.items())) for i, n in facts.nodes.items()}
    return sorted(key.values()), sorted((key[s], key[d], label) for s, d, label in facts.edges)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "app.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def _build(root: Path, tsg: TsgConfig | None) -> dict:
    return PythonGraphBuilder(repo_key="t/repo", repository_revision="rev", tsg=tsg).build(root)


def _facts_summary(document: dict) -> dict:
    nodes = {n["id"]: n for n in document["nodes"]}

    def edges(kind: str) -> list[tuple[str, str]]:
        return sorted((nodes[e["source_id"]]["qualified_name"], nodes[e["target_id"]]["qualified_name"])
                      for e in document["edges"]
                      if e["type"] == kind and e["provenance"]["source_tool"] == "tree-sitter-graph")

    return {
        "Field": sorted(n["qualified_name"] for n in nodes.values() if n["type"] == "Field"),
        "GlobalVariable": sorted(n["qualified_name"] for n in nodes.values() if n["type"] == "GlobalVariable"),
        "Identifier": sorted(n["qualified_name"] for n in nodes.values() if n["type"] == "Identifier"),
        "HAS_METHOD": edges("HAS_METHOD"),
        "HAS_CALLSITE": edges("HAS_CALLSITE"),
        "CONTAINS": edges("CONTAINS"),
    }


EXPECTED = {
    "Field": ["app.Cart.items", "app.Cart.size"],
    "GlobalVariable": ["app.LIMIT", "app.TOTAL"],
    "Identifier": ["app.Cart.add::<param:sku>", "app.check::<param:sku>"],
    "HAS_METHOD": [("app.Cart", "app.Cart.add")],
    "HAS_CALLSITE": [("app.Cart.add", "app.Cart.add::<call:1>"), ("app.check", "app.check::<call:1>")],
    "CONTAINS": [("app", "app.LIMIT"), ("app", "app.TOTAL"), ("app.Cart", "app.Cart.items"),
                 ("app.Cart", "app.Cart.size"), ("app.Cart.add", "app.Cart.add::<param:sku>"),
                 ("app.check", "app.check::<param:sku>")],
}

needs_cli = pytest.mark.skipif(
    not (os.getenv("VGAR_TSG_EXECUTABLE") and os.getenv("VGAR_TSG_TREE_SITTER_DIR")),
    reason="needs a tree-sitter-graph CLI and a tree-sitter-python v0.23.6 grammar")


def _fake_cli(monkeypatch: pytest.MonkeyPatch, facts_by_path: dict[str, TsgFileFacts]) -> TsgConfig:
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, root, path: facts_by_path[path])
    return TsgConfig(executable=Path("tsg"), tree_sitter_dir=Path("."))


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(text.encode("utf-8"))
    return root


def test_parse_graph_unwraps_typed_json_values() -> None:
    raw = [
        {"id": 0, "edges": [{"sink": 1, "attrs": {"type": {"type": "string", "string": "HAS_METHOD"}}}],
         "attrs": {"type": {"type": "string", "string": "Class"}, "line": {"type": "int", "int": 2}}},
        {"id": 1, "edges": [], "attrs": {"type": {"type": "string", "string": "Method"},
                                         "overload": {"type": "string", "string": "yes"}}},
    ]
    facts = parse_graph(raw)
    assert facts.nodes == {0: {"type": "Class", "line": 2}, 1: {"type": "Method", "overload": "yes"}}
    assert facts.edges == [(0, 1, "HAS_METHOD")]


def test_missing_cli_falls_back_to_the_plain_graph(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    plain = _build(root, None)
    document = _build(root, TsgConfig(executable=tmp_path / "missing-tsg.exe", tree_sitter_dir=tmp_path))
    validate_graph_document(document)
    report = document["statistics"]["tsg"]
    assert report["status"] == "fallback" and "missing-tsg.exe" in report["reason"]
    assert {n["type"] for n in document["nodes"]} == {n["type"] for n in plain["nodes"]}
    assert len(document["edges"]) == len(plain["edges"])
    assert "tsg" not in plain["statistics"]


def test_facts_are_merged_into_a_valid_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, root, path: FAKE_FACTS)
    document = _build(root, TsgConfig(executable=Path("tsg"), tree_sitter_dir=Path(".")))

    validate_graph_document(document)
    assert _facts_summary(document) == EXPECTED
    report = document["statistics"]["tsg"]
    assert report["status"] == "ready" and report["file_count"] == 1
    assert report["unmatched"] == {}

    limit = next(n for n in document["nodes"] if n["type"] == "GlobalVariable")
    assert limit["range"] == {"start_line": 1, "start_col": 0, "end_line": 1, "end_col": 10,
                              "start_byte": 0, "end_byte": 10}
    assert limit["content_hash"] == "sha256:" + hashlib.sha256(b"LIMIT = 10").hexdigest()
    plain = _build(root, None)
    assert document["graph_version"] != plain["graph_version"]


def test_merged_graph_round_trips_through_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path / "repo")
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file", lambda config, root, path: FAKE_FACTS)
    document = _build(root, TsgConfig(executable=Path("tsg"), tree_sitter_dir=Path(".")))
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    assert _facts_summary(store.load_document(document["graph_version"])) == EXPECTED


@needs_cli
def test_real_cli_emits_the_same_facts(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = TsgConfig.from_env()
    assert config is not None
    assert _canonical(tsg_extractor.run_file(config, root, "src/app.py")) == _canonical(FAKE_FACTS)
    document = _build(root, config)
    validate_graph_document(document)
    assert _facts_summary(document) == EXPECTED


DUP_SOURCE = "if X:\r\n    def f(a):\r\n        pass\r\nelse:\r\n    def f(a):\r\n        pass\r\n"
DUP_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: {"type": "Function", "name": "f", "line": 2, "col": 4, "end_line": 3, "end_col": 12},
        2: {"type": "Identifier", "name": "a", "kind": "normal", "line": 2, "col": 10, "end_line": 2, "end_col": 11},
        3: {"type": "Function", "name": "f", "line": 5, "col": 4, "end_line": 6, "end_col": 12},
        4: {"type": "Identifier", "name": "a", "kind": "normal", "line": 5, "col": 10, "end_line": 5, "end_col": 11},
    },
    edges=[(0, 1, "HAS_METHOD"), (0, 3, "HAS_METHOD"), (1, 2, "CONTAINS"), (3, 4, "CONTAINS")],
)


def test_identifier_properties_and_duplicate_defs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, {"src/dup.py": DUP_SOURCE})
    document = _build(root, _fake_cli(monkeypatch, {"src/dup.py": DUP_FACTS}))
    validate_graph_document(document)
    identifiers = sorted((n for n in document["nodes"] if n["type"] == "Identifier"),
                         key=lambda n: n["range"]["start_line"])
    assert [n["name"] for n in identifiers] == ["a", "a"]
    assert identifiers[0]["id"] != identifiers[1]["id"]
    assert identifiers[1]["id"].endswith("@definition:5:10")
    first = identifiers[0]
    assert (first["range"]["start_byte"], first["range"]["end_byte"]) == (17, 18)
    assert first["content_hash"] == "sha256:" + hashlib.sha256(b"a").hexdigest()
    assert first["properties"] == {"annotation": None, "has_default": False, "position": 0, "kind": "normal"}
    assert document["statistics"]["tsg"]["added"]["Identifier"] == 2
    assert document["statistics"]["tsg"]["unmatched"] == {}


KINDS_SOURCE = (
    "def f(a, b: int, c=1, d: str = 'x', *args, e, **kw): pass\n"
    "class K:\n"
    "    @classmethod\n"
    "    def m(cls, x): pass\n"
    "lam = lambda z: z\n"
)


@needs_cli
def test_real_cli_identifier_kinds(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/kinds.py": KINDS_SOURCE})
    document = _build(root, TsgConfig.from_env())
    validate_graph_document(document)
    params: dict[str, list[tuple]] = {}
    for node in document["nodes"]:
        if node["type"] == "Identifier":
            owner, _ = node["qualified_name"].split("::<param:")
            p = node["properties"]
            params.setdefault(owner, []).append(
                (p["position"], node["name"], p["kind"], p["annotation"], p["has_default"]))
    assert sorted(params["kinds.f"]) == [
        (0, "a", "normal", None, False), (1, "b", "normal", "int", False), (2, "c", "normal", None, True),
        (3, "d", "normal", "str", True), (4, "args", "var_positional", None, False),
        (5, "e", "normal", None, False), (6, "kw", "var_keyword", None, False)]
    assert params["kinds.K.m"] == [(1, "x", "normal", None, False)]
    assert set(params) == {"kinds.f", "kinds.K.m"}


# L1-3 ConfigEntry. Line 10 is the f-string negative case (no ConfigRead); line 8 is a write.
CFG_SOURCE = (
    "import os\n"
    "DEBUG = os.getenv('DEBUG')\n"
    "class Settings:\n"
    "    url = os.environ['DB_URL']\n"
    "def load():\n"
    "    a = os.environ.get('DB_URL')\n"
    "    b = os.environ.get('DB_URL')\n"
    "    os.environ['MODE'] = 'x'\n"
    "    f = lambda: os.getenv('LAMBDA_KEY')\n"
    '    c = os.getenv(f"K{a}")\n'
    "    return a, b, f\n"
)
OTHER_SOURCE = "import os\nKEY = os.getenv('DEBUG')\n"


def _read(key: str, access: str, callee: str, line: int, col: int, end_col: int, **extra: str) -> dict:
    return {"type": "ConfigRead", "key": key, "access": access, "callee": callee, "line": line, "col": col,
            "end_line": line, "end_col": end_col, **extra}


def _call(name: str, line: int, col: int, end_col: int) -> dict:
    return {"type": "CallSite", "name": name, "line": line, "col": col, "end_line": line, "end_col": end_col}


# What python.tsg emits for CFG_SOURCE, checked against the real CLI by test_real_cli_config_reads.
CFG_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: {"type": "GlobalVariable", "name": "DEBUG", "line": 2, "col": 0, "end_line": 2, "end_col": 26},
        2: _call("os.getenv", 2, 8, 26),
        3: _read("DEBUG", "getenv", "os.getenv", 2, 8, 26),
        4: {"type": "Class", "name": "Settings", "line": 3, "col": 0, "end_line": 4, "end_col": 30},
        5: _read("DB_URL", "environ_subscript", "os.environ", 4, 10, 30),
        6: {"type": "Function", "name": "load", "line": 5, "col": 0, "end_line": 11, "end_col": 18},
        7: _call("os.environ.get", 6, 8, 32),
        8: _read("DB_URL", "environ_get", "os.environ.get", 6, 8, 32),
        9: _call("os.environ.get", 7, 8, 32),
        10: _read("DB_URL", "environ_get", "os.environ.get", 7, 8, 32),
        11: _read("MODE", "environ_subscript", "os.environ", 8, 4, 22, write="yes"),
        12: _call("os.getenv", 9, 16, 39),
        13: _read("LAMBDA_KEY", "getenv", "os.getenv", 9, 16, 39),
        14: _call("os.getenv", 10, 8, 26),
    },
    edges=[(0, 2, "HAS_CALLSITE"), (0, 3, "REFERENCES"), (0, 5, "REFERENCES"), (0, 6, "HAS_METHOD"),
           (6, 7, "HAS_CALLSITE"), (6, 8, "REFERENCES"), (6, 9, "HAS_CALLSITE"), (6, 10, "REFERENCES"),
           (6, 11, "REFERENCES"), (6, 12, "HAS_CALLSITE"), (6, 13, "REFERENCES"), (6, 14, "HAS_CALLSITE")],
)
OTHER_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: {"type": "GlobalVariable", "name": "KEY", "line": 2, "col": 0, "end_line": 2, "end_col": 24},
        2: _call("os.getenv", 2, 6, 24),
        3: _read("DEBUG", "getenv", "os.getenv", 2, 6, 24),
    },
    edges=[(0, 2, "HAS_CALLSITE"), (0, 3, "REFERENCES")],
)


def test_config_entries_across_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, {"src/cfg.py": CFG_SOURCE, "src/other.py": OTHER_SOURCE})
    document = _build(root, _fake_cli(monkeypatch, {"src/cfg.py": CFG_FACTS, "src/other.py": OTHER_FACTS}))
    validate_graph_document(document)
    nodes = {n["id"]: n for n in document["nodes"]}
    entries = {n["qualified_name"]: n for n in nodes.values() if n["type"] == "ConfigEntry"}
    assert sorted(entries) == ["env:DB_URL", "env:DEBUG", "env:LAMBDA_KEY"]
    debug = entries["env:DEBUG"]
    assert debug["id"] == "vgar:t/repo:config:env:DEBUG" and debug["name"] == "DEBUG"
    assert debug["path"] is None and debug["range"] is None
    assert debug["properties"] == {"source": "environment",
                                   "read_sites": [{"path": "src/cfg.py", "line": 2},
                                                  {"path": "src/other.py", "line": 2}]}
    references = sorted(
        (nodes[e["source_id"]]["qualified_name"], nodes[e["target_id"]]["qualified_name"],
         e["properties"]["lines"], e["properties"]["access"])
        for e in document["edges"] if e["type"] == "REFERENCES" and nodes[e["target_id"]]["type"] == "ConfigEntry")
    assert references == [
        ("cfg", "env:DB_URL", [4], "environ_subscript"),
        ("cfg", "env:DEBUG", [2], "getenv"),
        ("cfg.load", "env:DB_URL", [6, 7], "environ_get"),
        ("cfg.load", "env:LAMBDA_KEY", [9], "getenv"),
        ("other", "env:DEBUG", [2], "getenv"),
    ]
    assert document["statistics"]["tsg"]["added"]["ConfigEntry"] == 3
    assert document["statistics"]["tsg"]["unmatched"] == {}


# Aliased os imports are env reads; look-alike names not imported from os are not.
ALIAS_SOURCE = (
    "import os as o\n"
    "from os import environ, getenv\n"
    "A1 = o.getenv('A1')\n"
    "A2 = o.environ['A2']\n"
    "A3 = o.environ.get('A3')\n"
    "A4 = getenv('A4')\n"
    "A5 = environ.get('A5')\n"
)
LOOKALIKE_SOURCE = (
    "environ = {}\n"
    "def getenv(key): ...\n"
    "F1 = environ['F1']\n"
    "F2 = getenv('F2')\n"
    "F3 = environ.get('F3')\n"
)


def _global(name: str, line: int, end_col: int) -> dict:
    return {"type": "GlobalVariable", "name": name, "line": line, "col": 0, "end_line": line, "end_col": end_col}


ALIAS_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: _global("A1", 3, 19), 2: _call("o.getenv", 3, 5, 19), 3: _read("A1", "getenv", "o.getenv", 3, 5, 19),
        4: _global("A2", 4, 20), 5: _read("A2", "environ_subscript", "o.environ", 4, 5, 20),
        6: _global("A3", 5, 24), 7: _call("o.environ.get", 5, 5, 24),
        8: _read("A3", "environ_get", "o.environ.get", 5, 5, 24),
        9: _global("A4", 6, 17), 10: _call("getenv", 6, 5, 17), 11: _read("A4", "getenv", "getenv", 6, 5, 17),
        12: _global("A5", 7, 22), 13: _call("environ.get", 7, 5, 22),
        14: _read("A5", "environ_get", "environ.get", 7, 5, 22),
    },
    edges=[(0, 2, "HAS_CALLSITE"), (0, 3, "REFERENCES"), (0, 5, "REFERENCES"), (0, 7, "HAS_CALLSITE"),
           (0, 8, "REFERENCES"), (0, 10, "HAS_CALLSITE"), (0, 11, "REFERENCES"), (0, 13, "HAS_CALLSITE"),
           (0, 14, "REFERENCES")],
)
LOOKALIKE_FACTS = TsgFileFacts(
    nodes={
        0: {"type": "Discard"},
        1: _global("environ", 1, 12),
        2: {"type": "Function", "name": "getenv", "line": 2, "col": 0, "end_line": 2, "end_col": 20},
        3: {"type": "Identifier", "name": "key", "kind": "normal", "line": 2, "col": 11, "end_line": 2, "end_col": 14},
        4: _global("F1", 3, 18), 5: _read("F1", "environ_subscript", "environ", 3, 5, 18),
        6: _global("F2", 4, 17), 7: _call("getenv", 4, 5, 17), 8: _read("F2", "getenv", "getenv", 4, 5, 17),
        9: _global("F3", 5, 22), 10: _call("environ.get", 5, 5, 22),
        11: _read("F3", "environ_get", "environ.get", 5, 5, 22),
    },
    edges=[(0, 2, "HAS_METHOD"), (2, 3, "CONTAINS"), (0, 5, "REFERENCES"), (0, 7, "HAS_CALLSITE"),
           (0, 8, "REFERENCES"), (0, 10, "HAS_CALLSITE"), (0, 11, "REFERENCES")],
)


def test_config_reads_require_an_os_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, {"src/alias_cfg.py": ALIAS_SOURCE, "src/lookalike.py": LOOKALIKE_SOURCE})
    document = _build(root, _fake_cli(monkeypatch, {"src/alias_cfg.py": ALIAS_FACTS,
                                                    "src/lookalike.py": LOOKALIKE_FACTS}))
    validate_graph_document(document)
    nodes = {n["id"]: n for n in document["nodes"]}
    references = sorted(
        (nodes[e["source_id"]]["qualified_name"], nodes[e["target_id"]]["name"], e["properties"]["access"])
        for e in document["edges"] if e["type"] == "REFERENCES" and nodes[e["target_id"]]["type"] == "ConfigEntry")
    assert references == [("alias_cfg", "A1", "getenv"), ("alias_cfg", "A2", "environ_subscript"),
                          ("alias_cfg", "A3", "environ_get"), ("alias_cfg", "A4", "getenv"),
                          ("alias_cfg", "A5", "environ_get")]
    assert document["statistics"]["tsg"]["unmatched"] == {}


@needs_cli
def test_real_cli_config_reads(tmp_path: Path) -> None:
    files = {"src/cfg.py": (CFG_SOURCE, CFG_FACTS), "src/alias_cfg.py": (ALIAS_SOURCE, ALIAS_FACTS),
             "src/lookalike.py": (LOOKALIKE_SOURCE, LOOKALIKE_FACTS)}
    root = _write(tmp_path, {path: source for path, (source, _) in files.items()})
    config = TsgConfig.from_env()
    assert config is not None
    for path, (_, facts) in files.items():
        assert _canonical(tsg_extractor.run_file(config, root, path)) == _canonical(facts), path


@needs_cli
def test_real_cli_survives_syntax_errors(tmp_path: Path) -> None:
    root = _write(tmp_path, {"src/bad.py": "def broken(:\n    pass\n", "src/good.py": "def ok(a): return a\n"})
    document = _build(root, TsgConfig.from_env())
    validate_graph_document(document)
    assert document["statistics"]["tsg"]["status"] in {"ready", "partial"}
    assert "good.ok::<param:a>" in {n["qualified_name"] for n in document["nodes"] if n["type"] == "Identifier"}
