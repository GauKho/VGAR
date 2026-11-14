"""L4-5/L4-6 GraphDiff: graph edits on builder node ids, raw-diff baseline, confidence and validation."""
from __future__ import annotations

from pathlib import Path

import pytest
from git_fixture import linear_repo, write_tree

from vgar.graph.ast_diff import diff_python_commit, read_python_blobs
from vgar.graph.builder import PythonGraphBuilder, module_name_for
from vgar.graph.graphdiff import SnapshotIndex, raw_diff_entities, type_commit_edits
from vgar.graph.history import read_commit_history
from vgar.graph.refactorings import (
    CommitRefactorings,
    Refactoring,
    RefactoringMinerConfig,
    SymbolRef,
    detect_refactorings,
)

pytest.importorskip("dulwich")

CART = b'''"""Cart."""
LIMIT = 10


class Cart:
    """A cart."""

    def total(self, items):
        return sum(items)

    def count(self, items):
        return len(items)


def helper(x):
    return x + 1
'''


def _build(tree: Path, files: dict[str, bytes], revision: str) -> dict:
    write_tree(tree, files)
    return PythonGraphBuilder(repo_key="fx", repository_revision=revision, source_roots=("src",)).build(tree)


def edits_for(tmp_path: Path, before: dict[str, bytes], after: dict[str, bytes], *, refs=None, head=None,
              subject: str = "change"):
    root = tmp_path / "r"
    ids = linear_repo(root, [("base", before), (subject, after)])
    history = read_commit_history(root, revision=ids[-1], max_commits=1)
    commit = history.commits[0]
    blobs = read_python_blobs(root, commit)
    refs = refs or detect_refactorings(root, history, {commit.commit_id: blobs}, RefactoringMinerConfig())[commit.commit_id]
    document = _build(tmp_path / "tree", head if head is not None else after, ids[-1])
    index = SnapshotIndex.from_document(document, source_roots=("src",), repository_name="r")
    return type_commit_edits(commit, diff_python_commit(root, commit), refs, blobs, index), document, commit, blobs, index


def by_entity(edits):
    return {edit.entity: edit for edit in edits}


P = "src/shop/cart.py"


def test_edit_type_add_remove(tmp_path):
    after = CART.replace(b"def helper(x):\n    return x + 1\n", b"def fresh(y):\n    return y * 9\n")
    edits = by_entity(edits_for(tmp_path, {P: CART}, {P: after})[0])
    assert edits["shop.cart.fresh"].edit_type == "ADD_SYMBOL"
    assert edits["shop.cart.helper"].edit_type == "REMOVE_SYMBOL" and not edits["shop.cart.helper"].node_in_snapshot


def test_edit_type_rename_is_one_edit_on_after_node_with_counterpart(tmp_path):
    edits = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"def helper(", b"def assist(")})[0]
    edit, = edits
    assert (edit.edit_type, edit.entity, edit.is_refactoring) == ("RENAME_SYMBOL", "shop.cart.assist", True)
    assert edit.refactoring["counterpart"] == "shop.cart.helper" and edit.refactoring["family"] == "rename_method"
    assert edit.before is not None and edit.after is not None


def test_edit_type_move(tmp_path):
    helper = b"def helper(x):\n    return x + 1\n"
    before = {P: CART, "src/shop/util.py": b"X = 1\n"}
    after = {P: CART.replace(helper, b""), "src/shop/util.py": b"X = 1\n\n\n" + helper}
    edit, = edits_for(tmp_path, before, after)[0]
    assert (edit.edit_type, edit.path, edit.entity) == ("MOVE_SYMBOL", "src/shop/util.py", "shop.util.helper")


def _refs(commit_id: str, refactoring: Refactoring) -> CommitRefactorings:
    return CommitRefactorings(commit_id, "refactoringminer", (refactoring,), (), None, ())


def test_edit_type_extract(tmp_path):
    after = CART.replace(b"        return sum(items)\n", b"        return _sum(items)\n") + \
        b"\n\ndef _sum(items):\n    return sum(items)\n"
    extract = Refactoring("refactoringminer", "Extract Method", "extract_method", (SymbolRef(P, "Cart.total"),),
                          (SymbolRef(P, "_sum"),), frozenset({SymbolRef(P, "Cart.total"), SymbolRef(P, "_sum")}), {},
                          "Extract Method _sum from total", "3.2.0")
    edits = by_entity(edits_for(tmp_path, {P: CART}, {P: after}, refs=_refs("x", extract))[0])
    assert edits["shop.cart._sum"].edit_type == "EXTRACT_SYMBOL" and edits["shop.cart._sum"].is_refactoring
    # the source method is involved but not the refactoring's subject: not hidden, coherence 0.5 (final review)
    source = edits["shop.cart.Cart.total"]
    assert not source.is_refactoring and source.confidence_terms["semantic_coherence"] == 0.5


def test_edit_type_inline(tmp_path):
    after = CART.replace(b"def helper(x):\n    return x + 1\n", b"")
    inline = Refactoring("refactoringminer", "Inline Method", "inline_method", (SymbolRef(P, "helper"),), (),
                         frozenset({SymbolRef(P, "helper")}), {}, "Inline Method helper", "3.2.0")
    edit, = edits_for(tmp_path, {P: CART}, {P: after}, refs=_refs("x", inline))[0]
    assert (edit.edit_type, edit.is_refactoring) == ("INLINE_SYMBOL", True)


def test_edit_type_signature(tmp_path):
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"def helper(x)", b"def helper(x, y=0)")})[0]
    assert edit.edit_type == "UPDATE_SIGNATURE" and not edit.is_refactoring


def test_edit_type_method_body(tmp_path):
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"sum(items)", b"sum(items) or 0")})[0]
    assert (edit.edit_type, edit.entity, edit.node_type) == ("UPDATE_METHOD_BODY", "shop.cart.Cart.total", "Method")
    assert edit.node_id == "vgar:fx:python:method:src/shop/cart.py:shop.cart.Cart.total" and edit.node_in_snapshot


def test_edit_type_class_body(tmp_path):
    after = CART.replace(b'    """A cart."""\n', b'    """A cart."""\n    size = 3\n')
    edit, = edits_for(tmp_path, {P: CART}, {P: after})[0]
    assert (edit.edit_type, edit.node_type) == ("UPDATE_CLASS_BODY", "Class")


def test_edit_type_docstring(tmp_path):
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"A cart.", b"A shopping cart.")})[0]
    assert edit.edit_type == "UPDATE_DOCSTRING" and not edit.is_refactoring


def test_edit_type_global(tmp_path):
    edits = by_entity(edits_for(tmp_path, {P: CART}, {P: CART.replace(b"LIMIT = 10", b"LIMIT = 20\nNEW = 1")})[0])
    assert edits["shop.cart.LIMIT"].edit_type == "UPDATE_GLOBAL"
    assert edits["shop.cart.NEW"].edit_type == "ADD_GLOBAL"
    assert edits["shop.cart.LIMIT"].node_id == "vgar:fx:python:globalvariable:src/shop/cart.py:shop.cart.LIMIT"


def test_edit_type_module_statements(tmp_path):
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"LIMIT = 10\n", b"LIMIT = 10\nimport os\n")})[0]
    assert (edit.edit_type, edit.entity, edit.node_type) == ("UPDATE_MODULE_STATEMENTS", "shop.cart", "Module")
    assert edit.node_id == "vgar:fx:python:module:src/shop/cart.py:shop.cart" and edit.node_in_snapshot


def test_node_ids_equal_builder_ids(tmp_path):
    after = CART.replace(b"sum(items)", b"sum(items) or 0").replace(b"len(items)", b"len(items) + 0")
    edits, document, *_ = edits_for(tmp_path, {P: CART}, {P: after})
    ids = {node["id"] for node in document["nodes"]}
    assert edits and all(edit.node_id in ids for edit in edits)


def test_symbol_removed_before_snapshot_is_not_in_snapshot(tmp_path):
    after = CART.replace(b"x + 1", b"x + 2")
    edit, = edits_for(tmp_path, {P: CART}, {P: after}, head={P: after.replace(b"def helper(", b"def gone(")})[0]
    assert edit.entity == "shop.cart.helper" and not edit.node_in_snapshot
    assert edit.node_id == "vgar:fx:python:function:src/shop/cart.py:shop.cart.helper"


def test_in_test_file_uses_builder_rule(tmp_path):
    test_file = b"def test_total():\n    assert 1\n"
    helper_file = b"def make():\n    return 1\n"
    before = {"tests/test_cart.py": test_file, "src/shop/tests/helpers.py": helper_file}
    after = {"tests/test_cart.py": test_file.replace(b"1", b"2"), "src/shop/tests/helpers.py": helper_file.replace(b"1", b"2")}
    edits = by_entity(edits_for(tmp_path, before, after)[0])
    assert all(edit.in_test_file for edit in edits.values())
    assert edits["tests.test_cart.test_total"].node_type == "Test"


def test_whole_file_added_and_removed(tmp_path):
    edits = edits_for(tmp_path, {P: CART}, {"src/shop/new.py": b"def made():\n    return 1\n"})[0]
    types = {(edit.entity, edit.edit_type) for edit in edits}
    assert ("shop.new.made", "ADD_SYMBOL") in types and ("shop.cart.Cart.total", "REMOVE_SYMBOL") in types
    assert ("shop.cart.LIMIT", "REMOVE_GLOBAL") in types


def test_duplicate_definition_maps_to_first_node(tmp_path):
    source = b"def f():\n    return 1\n\n\ndef f():\n    return 2\n"
    edit, = edits_for(tmp_path, {"src/d.py": source}, {"src/d.py": source.replace(b"return 2", b"return 3")})[0]
    assert edit.node_id == "vgar:fx:python:function:src/d.py:d.f" and edit.node_in_snapshot


def test_parse_error_file_gives_no_edit_and_evidence(tmp_path):
    before = {P: CART, "src/old.py": b"x = 1\n"}
    after = {P: CART.replace(b"x + 1", b"x + 2"), "src/old.py": b"print 'x'\n"}
    edit, = edits_for(tmp_path, before, after)[0]
    assert edit.entity == "shop.cart.helper" and "parse error: src/old.py" in edit.evidence


def test_evidence_names_ast_and_missing_refactoringminer(tmp_path):
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"x + 1", b"x + 2")})[0]
    assert "ast" in edit.evidence and "refactoringminer unavailable: not configured" in edit.evidence
    assert edit.is_tangled_risk is None


def test_raw_baseline_includes_comment_and_docstring_hunks(tmp_path):
    after = CART.replace(b"        return len(items)\n", b"        # count them\n        return len(items)\n")
    after = after.replace(b"A cart.", b"A shopping cart.").replace(b'"""Cart."""\n', b'"""Cart."""\n# top\n')
    _, _, commit, blobs, index = edits_for(tmp_path, {P: CART}, {P: after})
    entities = {row["entity"] for row in raw_diff_entities(commit, blobs, index)}
    assert entities == {"shop.cart.Cart.count", "shop.cart.Cart", "shop.cart"}


def test_raw_baseline_maps_globals(tmp_path):
    _, _, commit, blobs, index = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"LIMIT = 10", b"LIMIT = 11")})
    row, = raw_diff_entities(commit, blobs, index)
    assert row["entity"] == "shop.cart.LIMIT" and row["node_id"].startswith("vgar:fx:python:globalvariable:")


def test_raw_baseline_on_unparsable_file(tmp_path):
    before = {P: CART, "src/old.py": b"x = 1\n"}
    after = {P: CART, "src/old.py": b"print 'x'\n"}
    _, _, commit, blobs, index = edits_for(tmp_path, before, after, head=before)
    rows = raw_diff_entities(commit, blobs, index)
    # before side parses (global x); after side does not, so its changed line belongs to the module
    assert {(row["path"], row["entity"]) for row in rows} == {("src/old.py", "old.x"), ("src/old.py", "old")}


def test_module_name_for_matches_builder():
    assert module_name_for("src/pkg/__init__.py", ("src",), "repo") == "pkg"
    assert module_name_for("src/pkg/mod.py", ("src",), "repo") == "pkg.mod"
    assert module_name_for("__init__.py", ("src",), "repo") == "repo"
    assert module_name_for("tools/x.py", ("src",), "repo") == "tools.x"


def test_statement_level_rm_type_does_not_hide_a_fix(tmp_path):
    invert = Refactoring("refactoringminer", "Invert Condition", "other", (SymbolRef(P, "helper"),),
                         (SymbolRef(P, "helper"),), frozenset({SymbolRef(P, "helper")}), {}, "Invert Condition", "3.2.0")
    edit, = edits_for(tmp_path, {P: CART}, {P: CART.replace(b"x + 1", b"x + 2")},
                      refs=CommitRefactorings("x", "refactoringminer", (invert,), (), None, ()))[0]
    assert not edit.is_refactoring and edit.confidence_terms["semantic_coherence"] == 0.5


def test_raw_baseline_setter_body_maps_to_setter_entity(tmp_path):
    source = (b"class K:\n    @property\n    def v(self):\n        return 1\n\n"
              b"    @v.setter\n    def v(self, x):\n        self._v = x\n")
    edits, _, commit, blobs, index = edits_for(tmp_path, {"src/a.py": source},
                                               {"src/a.py": source.replace(b"self._v = x", b"self._v = x + 1")})
    assert {edit.entity for edit in edits} == {"a.K.v"}
    assert {row["entity"] for row in raw_diff_entities(commit, blobs, index)} == {"a.K.v"}


def test_raw_baseline_global_sharing_a_function_name(tmp_path):
    source = b"def foo():\n    return 1\n\n\nfoo = staticmethod(foo)\n"
    edits, _, commit, blobs, index = edits_for(tmp_path, {"src/a.py": source},
                                               {"src/a.py": source.replace(b"staticmethod(foo)", b"classmethod(foo)")})
    assert {edit.entity for edit in edits} == {"a.foo"}
    assert {row["entity"] for row in raw_diff_entities(commit, blobs, index)} == {"a.foo"}


# --- L4-6 confidence, validation and run_graphdiff ---

from vgar.graph.graphdiff import ConfidenceConfig, run_graphdiff, score_edit

TEST_FILE = b"from shop.cart import Cart, helper\n\n\ndef test_total():\n    assert Cart().total([1]) == 1\n"


def scored(tmp_path, before, after, *, subject="change", refs=None, config=None):
    edits, _document, commit, blobs, index = edits_for(tmp_path, before, after, subject=subject, refs=refs)
    root = tmp_path / "r"
    history = read_commit_history(root, revision=commit.commit_id, max_commits=1)
    refs = refs or detect_refactorings(root, history, {commit.commit_id: blobs}, RefactoringMinerConfig())[commit.commit_id]
    for edit in edits:
        score_edit(edit, commit, refs, index, config or ConfidenceConfig())
    return by_entity(edits)


def test_algorithm_agreement_null_without_rm_and_scored_with_rm(tmp_path):
    change = {P: CART.replace(b"x + 1", b"x + 2")}
    edit = scored(tmp_path, {P: CART}, change)["shop.cart.helper"]
    assert edit.confidence_terms["algorithm_agreement"] is None
    rm = Refactoring("refactoringminer", "Rename Method", "rename_method", (SymbolRef(P, "helper"),),
                     (SymbolRef(P, "helper"),), frozenset({SymbolRef(P, "helper")}), {}, "Rename Method", "3.2.0")
    refs = CommitRefactorings("x", "refactoringminer", (rm,), (), None, ())
    edit = scored(tmp_path / "b", {P: CART}, change, refs=refs)["shop.cart.helper"]
    assert edit.confidence_terms["algorithm_agreement"] == 0.0  # RM says refactoring, ast says not
    refs = CommitRefactorings("x", "refactoringminer", (), (), None, ())
    edit = scored(tmp_path / "c", {P: CART}, change, refs=refs)["shop.cart.helper"]
    assert edit.confidence_terms["algorithm_agreement"] == 1.0


def test_semantic_coherence_values(tmp_path):
    base = CART + b"\n\ndef use():\n    return helper(1)\n"
    renamed = CART.replace(b"def helper(", b"def assist(") + b"\n\ndef use():\n    return assist(1) + 1\n"
    edits = scored(tmp_path, {P: base}, {P: renamed})
    assert edits["shop.cart.assist"].confidence_terms["semantic_coherence"] == 1.0
    assert edits["shop.cart.use"].confidence_terms["semantic_coherence"] == 0.5  # renamed reference + extra change
    assert not edits["shop.cart.use"].is_refactoring
    pure = scored(tmp_path / "b", {P: base}, {P: renamed.replace(b"assist(1) + 1", b"assist(1)")})
    assert pure["shop.cart.use"].is_refactoring and pure["shop.cart.use"].confidence_terms["semantic_coherence"] == 1.0
    module = scored(tmp_path / "c", {P: CART}, {P: CART + b"\nimport os\n"})["shop.cart"]
    assert module.confidence_terms["semantic_coherence"] == 0.5


def test_test_relevance_levels(tmp_path):
    fixed = CART.replace(b"sum(items)", b"sum(items) or 0")
    before = {P: CART, "tests/test_cart.py": TEST_FILE}
    after = {P: fixed, "tests/test_cart.py": TEST_FILE + b"\n# more\n"}
    edit = scored(tmp_path, before, after)["shop.cart.Cart.total"]
    assert edit.confidence_terms["test_relevance"] == 1.0 and "test touched: tests/test_cart.py" in edit.evidence
    other = {P: CART, "tests/test_other.py": b"def test_x():\n    assert 1\n"}
    other_after = {P: fixed, "tests/test_other.py": b"def test_x():\n    assert 2\n"}
    assert scored(tmp_path / "b", other, other_after)["shop.cart.Cart.total"].confidence_terms["test_relevance"] == 0.5
    alone = scored(tmp_path / "c", {P: CART}, {P: fixed})["shop.cart.Cart.total"]
    assert alone.confidence_terms["test_relevance"] == 0.0


def test_trace_relevance_levels(tmp_path):
    change = {P: CART.replace(b"x + 1", b"x + 2")}
    edit = scored(tmp_path, {P: CART}, change, subject="Fix helper rounding")["shop.cart.helper"]
    assert edit.confidence_terms["trace_relevance"] == 1.0
    method = {P: CART.replace(b"sum(items)", b"sum(items) or 0")}
    edit = scored(tmp_path / "b", {P: CART}, method, subject="Fix total of empty cart")["shop.cart.Cart.total"]
    assert edit.confidence_terms["trace_relevance"] == 1.0 and "message mentions: total" in edit.evidence
    edit = scored(tmp_path / "c", {P: CART}, change, subject="Repair cart module")["shop.cart.helper"]
    assert edit.confidence_terms["trace_relevance"] == 0.5
    edit = scored(tmp_path / "d", {P: CART}, change, subject="Bump to v2")["shop.cart.helper"]
    assert edit.confidence_terms["trace_relevance"] == 0.0


def test_confidence_normalises_over_non_null_terms(tmp_path):
    edit = scored(tmp_path, {P: CART}, {P: CART.replace(b"x + 1", b"x + 2")}, subject="Fix helper")["shop.cart.helper"]
    terms = edit.confidence_terms
    assert (terms["algorithm_agreement"], terms["tangle_risk"]) == (None, None)
    assert (terms["semantic_coherence"], terms["test_relevance"], terms["trace_relevance"]) == (1.0, 0.0, 1.0)
    assert edit.confidence == pytest.approx((0.2 + 0.25) / (0.2 + 0.25 + 0.25))


def test_validated_and_high_confidence_rule(tmp_path):
    after = CART.replace(b"def helper(", b"def assist(").replace(b"A cart.", b"A big cart.")
    after = after.replace(b"len(items)", b"len(items) + 0")
    edits = scored(tmp_path, {P: CART}, {P: after}, subject="Bump", config=ConfidenceConfig(threshold=0.99))
    assert not edits["shop.cart.assist"].validated  # refactoring
    assert not edits["shop.cart.Cart"].validated  # docstring
    count = edits["shop.cart.Cart.count"]
    assert count.validated and not count.high_confidence and count.confidence < 0.99
    tests = scored(tmp_path / "b", {"tests/test_a.py": b"def test_a():\n    assert 1\n"},
                   {"tests/test_a.py": b"def test_a():\n    assert 2\n"})
    assert not tests["tests.test_a.test_a"].validated


def _run(tmp_path, snapshots, *, max_commits=10, head_files=None):
    root = tmp_path / "r"
    ids = linear_repo(root, snapshots)
    document = _build(tmp_path / "tree", head_files or snapshots[-1][1], ids[-1])
    return run_graphdiff(root, document, max_commits=max_commits, source_roots=("src",)), ids


def test_no_edit_dropped(tmp_path):
    after = CART.replace(b"def helper(", b"def assist(").replace(b"A cart.", b"A big cart.")
    result, _ = _run(tmp_path, [("base", {P: CART}), ("change", {P: after})], max_commits=1)
    assert sorted(edit.entity for edit in result.edits) == ["shop.cart.Cart", "shop.cart.assist"]
    assert result.summary["edits_total"] == 2 and result.summary["edits_validated"] == 0


def test_history_ends_at_snapshot_revision(tmp_path):
    root = tmp_path / "r"
    fixed = CART.replace(b"x + 1", b"x + 2")
    ids = linear_repo(root, [("base", {P: CART}), ("fix", {P: fixed}),
                             ("later", {P: fixed.replace(b"len(items)", b"0")})])
    document = _build(tmp_path / "tree", {P: fixed}, ids[1])
    result = run_graphdiff(root, document, max_commits=10, source_roots=("src",))
    assert {edit.commit_id for edit in result.edits} == set(ids[:2])  # never the later commit
    assert not any(edit.entity == "shop.cart.Cart.count" and edit.edit_type != "ADD_SYMBOL" for edit in result.edits)
    assert result.summary["revision"] == ids[1]


def test_window_stops_at_root_commit(tmp_path):
    result, _ = _run(tmp_path, [("base", {P: CART}), ("fix", {P: CART.replace(b"x + 1", b"x + 2")})], max_commits=50)
    assert (result.summary["commits_requested"], result.summary["commits_read"]) == (50, 2)


def test_is_tangled_risk_always_null(tmp_path):
    result, _ = _run(tmp_path, [("base", {P: CART}), ("fix", {P: CART.replace(b"x + 1", b"x + 2")})])
    assert result.edits
    assert all(edit.is_tangled_risk is None and edit.confidence_terms["tangle_risk"] is None for edit in result.edits)
    assert all(edit.to_json()["is_tangled_risk"] is None for edit in result.edits)


def test_summary_counts_parse_errors_and_fallbacks(tmp_path):
    result, ids = _run(tmp_path, [("base", {P: CART, "src/old.py": b"x = 1\n"}),
                                  ("py2", {P: CART, "src/old.py": b"print 'x'\n"})], head_files={P: CART})
    summary = result.summary
    error, = summary["parse_errors"]
    assert (error["commit"], error["path"], error["side"]) == (ids[1], "src/old.py", "after")
    assert summary["commits_per_detector"] == {"ast": 2}
    assert summary["refactoringminer_fallbacks"] == {"not configured": 2}
    assert summary["refactoringminer_version"] is None and summary["python_version"]
    assert summary["weights"]["tangle_risk"] == 0.0 and summary["threshold"] == 0.5
    assert summary["raw_baseline_entities"] == len([r for r in result.raw_baseline if not r["in_test_file"]])
    assert summary["commit_ids"] == list(reversed(ids))
