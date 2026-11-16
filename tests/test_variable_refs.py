"""Reader edges: function -> GlobalVariable / Field it reads or writes (spec 2026-11-15 §2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vgar.contracts.schema import EDGE_ENDPOINTS
from vgar.graph import tsg_extractor
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.tsg_extractor import TsgConfig, TsgFileFacts
from vgar.graph.variable_refs import VariableAccess, variable_accesses

SOURCE = (
    "LIMIT = 10\n"
    "class Cart:\n"
    "    size = 0\n"
    "    def add(self, sku):\n"
    "        self.items = sku[:LIMIT]\n"
    "        return self.size\n"
    "def check(LIMIT):\n"
    "    return LIMIT\n"
    "def bump():\n"
    "    global LIMIT\n"
    "    LIMIT = LIMIT + 1\n"
    "def outer():\n"
    "    def inner():\n"
    "        return LIMIT\n"
    "    return inner\n"
)
OTHER = "from app import LIMIT\n\n\ndef use():\n    return LIMIT\n"


def _acc(function, kind, owner, name, access):
    return VariableAccess(function, kind, owner, name, access)


def test_global_read_and_write():
    found = set(variable_accesses(SOURCE.encode()))
    assert _acc("Cart.add", "global", "", "LIMIT", "read") in found
    assert _acc("bump", "global", "", "LIMIT", "read_write") in found


def test_shadowed_global_is_not_a_read():
    assert not any(a.function == "check" for a in variable_accesses(SOURCE.encode()))


def test_self_field_read_write():
    found = set(variable_accesses(SOURCE.encode()))
    assert _acc("Cart.add", "field", "Cart", "items", "write") in found
    assert _acc("Cart.add", "field", "Cart", "size", "read") in found


def test_nested_function_belongs_to_outer():
    found = set(variable_accesses(SOURCE.encode()))
    assert _acc("outer", "global", "", "LIMIT", "read") in found
    assert not any(a.function.startswith("outer.") for a in found)


def test_imported_name_is_marked_imported():
    assert set(variable_accesses(OTHER.encode())) == {_acc("use", "imported", "", "LIMIT", "read")}


def test_syntax_error_gives_nothing():
    assert variable_accesses(b"def f(:\n") == []


# --- builder: edges only to nodes tree-sitter-graph created -----------------------------------------

def _f(type_, name, line, col, end_line, end_col):
    return {"type": type_, "name": name, "line": line, "col": col, "end_line": end_line, "end_col": end_col}


APP_FACTS = TsgFileFacts(
    nodes={0: {"type": "Discard"}, 1: _f("GlobalVariable", "LIMIT", 1, 0, 1, 10), 2: _f("Class", "Cart", 2, 0, 6, 24),
           3: _f("Field", "size", 3, 4, 3, 12), 4: _f("Method", "add", 4, 4, 6, 24),
           5: _f("Field", "items", 5, 8, 5, 32), 6: _f("Function", "check", 7, 0, 8, 16),
           7: _f("Function", "bump", 9, 0, 11, 21), 8: _f("Function", "outer", 12, 0, 15, 16),
           9: _f("Function", "inner", 13, 4, 14, 20)},
    edges=[(2, 4, "HAS_METHOD"), (0, 6, "HAS_METHOD"), (0, 7, "HAS_METHOD"), (0, 8, "HAS_METHOD"),
           (2, 3, "CONTAINS"), (2, 5, "CONTAINS")])
OTHER_FACTS = TsgFileFacts(nodes={0: {"type": "Discard"}, 1: _f("Function", "use", 4, 0, 5, 16)},
                           edges=[(0, 1, "HAS_METHOD")])


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "src" / "other.py").write_text(OTHER, encoding="utf-8")
    return tmp_path


def _reads(document: dict) -> dict[tuple[str, str], tuple[str, float, str]]:
    nodes = {n["id"]: n for n in document["nodes"]}
    return {(nodes[e["source_id"]]["qualified_name"], nodes[e["target_id"]]["qualified_name"]):
            (e["properties"]["access"], e["confidence"], e["resolution"])
            for e in document["edges"] if e["provenance"]["rule_id"] == "python.layer1.reads.v1"}


def _build_with_facts(tmp_path, monkeypatch):
    monkeypatch.setattr(tsg_extractor, "check_available", lambda config: (None, "tree-sitter-graph 0.12.0"))
    monkeypatch.setattr(tsg_extractor, "run_file",
                        lambda config, root, path: {"src/app.py": APP_FACTS, "src/other.py": OTHER_FACTS}[path])
    tsg = TsgConfig(executable=tmp_path / "tsg", tree_sitter_dir=tmp_path)
    return PythonGraphBuilder(repo_key="t/repo", repository_revision="rev", tsg=tsg).build(_repo(tmp_path))


def test_builder_adds_reader_edges(tmp_path, monkeypatch):
    reads = _reads(_build_with_facts(tmp_path, monkeypatch))
    assert reads[("app.Cart.add", "app.LIMIT")] == ("read", 1.0, "exact")
    assert reads[("app.Cart.add", "app.Cart.items")] == ("write", 1.0, "exact")
    assert reads[("app.Cart.add", "app.Cart.size")] == ("read", 1.0, "exact")
    assert reads[("app.bump", "app.LIMIT")] == ("read_write", 1.0, "exact")
    assert reads[("app.outer", "app.LIMIT")] == ("read", 1.0, "exact")
    assert not any(source == "app.check" for source, _ in reads)


def test_imported_global_is_heuristic(tmp_path, monkeypatch):
    reads = _reads(_build_with_facts(tmp_path, monkeypatch))
    assert reads[("other.use", "app.LIMIT")] == ("read", 0.8, "heuristic")


def test_no_edges_without_tsg_nodes(tmp_path):
    document = PythonGraphBuilder(repo_key="t/repo", repository_revision="rev").build(_repo(tmp_path))
    assert _reads(document) == {}


def test_schema_accepts_reader_endpoints():
    for source in ("Function", "Method", "Test"):
        for target in ("GlobalVariable", "Field"):
            assert (source, target) in EDGE_ENDPOINTS["REFERENCES"]


@pytest.mark.parametrize("name", ["FREE_SHIPPING_FROM", "SHIPPING_FEE"])
def test_demo_shop_shipping_constants_read_by_shipping_fee(name):
    source = (Path(__file__).resolve().parent / "fixtures" / "invariants" / "demo_shop" / "shop" / "shipping.py").read_bytes()
    assert _acc("shipping_fee", "global", "", name, "read") in set(variable_accesses(source))



def test_staticmethod_first_parameter_is_not_a_receiver():
    source = b"class Cart:\n    items = []\n    @staticmethod\n    def count(order):\n        return len(order.items)\n"
    assert not any(a.kind == "field" for a in variable_accesses(source))
