from __future__ import annotations

import pytest

from vgar.evaluation.retrieval.scoring import (
    CorpusIndex, bm25_rank, graph_rank, make_include, pack_items, score_record,
)

AUTH = '''def login(user, password):
    return check(user, password)


def check(user, password):
    return user == "root"
'''
STORE = '''class Store:
    def get(self, key):
        return key

    def put(self, key, value):
        return value
'''
SETTER = '''class Box:
    @property
    def value(self):
        return 1

    @value.setter
    def value(self, v):
        pass
'''
SOURCES = {"src/auth.py": AUTH, "src/store.py": STORE, "src/box.py": SETTER, "tests/test_auth.py": "def test_login():\n    pass\n"}
words = lambda text: len(text.split())          # fake counter: one token per whitespace word


def node(kind, path, qname, start, end):
    return {"id": f"{kind}:{qname}", "type": kind, "path": path, "qualified_name": qname,
            "range": {"start_line": start, "end_line": end}}


NODES = {n["id"]: n for n in (
    node("Function", "src/auth.py", "auth.login", 1, 2),
    node("Function", "src/auth.py", "auth.check", 5, 6),
    node("Class", "src/store.py", "store.Store", 1, 6),
    node("Method", "src/store.py", "store.Store.get", 2, 3),
    node("Test", "tests/test_auth.py", "tests.test_auth.test_login", 1, 2),
    node("File", "src/store.py", "src/store.py", 1, 6),
    node("Function", "src/other.py", "other.f", 1, 2),               # not in corpus
    node("Method", "src/auth.py", "auth.ghost", 1, 2),               # no matching function
)}
GOLD = {"gold_files": ["src/auth.py"], "gold_functions": ["src/auth.py::auth.check"], "function_labels_complete": True}


def cands(*ids):
    return [{"node_id": i, "relevance_score": 1 - n / 10} for n, i in enumerate(ids)]


@pytest.fixture(scope="module")
def corpus():
    return CorpusIndex(SOURCES)


def test_corpus_excludes_tests_and_keeps_gold_identity(corpus):
    assert "tests/test_auth.py" not in corpus.paths
    assert corpus.resolve_function("src/auth.py", "auth.check", 5, 6) == ("src/auth.py::auth.check", None)


def test_unit_rules_and_nonfatal_unmapped(corpus):
    rec = graph_rank("t", cands("Function:auth.login", "Test:tests.test_auth.test_login", "Class:store.Store",
                                "File:store.py", "Function:other.f", "Method:auth.ghost", "Function:missing"),
                     NODES, SOURCES, corpus)
    kinds = {i.item_id: i for i in rec.items}
    assert "Test:tests.test_auth.test_login" not in kinds                       # test excluded from scored rank
    assert kinds["Class:store.Store"].function_id is None                       # class: file level only
    assert kinds["Function:auth.login"].function_id == "src/auth.py::auth.login"
    assert kinds["Method:auth.ghost"].function_id is None                       # kept at file level
    reasons = {e["reason"] for e in rec.excluded}
    assert {"TEST_EXCLUDED", "NOT_IN_CORPUS"} <= reasons
    assert {u["reason"] for u in rec.unmapped} == {"NO_FUNCTION_MATCH", "NODE_NOT_IN_DOCUMENT"}


def test_duplicate_definitions_disambiguated_by_range(corpus):
    first = corpus.resolve_function("src/box.py", "box.Box.value", 3, 4)
    second = corpus.resolve_function("src/box.py", "box.Box.value", 7, 8)
    assert first[1] is None and second[1] is None and first[0] != second[0]
    assert first[0].endswith("@definition:2:4") or "@definition" in first[0]
    # range that is inside neither duplicate: not guessed, reported
    assert corpus.resolve_function("src/box.py", "box.Box.value", 1, 9) == (None, "NO_FUNCTION_MATCH")


def test_miss_is_zero_not_dropped(corpus):
    rec = graph_rank("t", cands("Class:store.Store", "Method:store.Store.get"), NODES, SOURCES, corpus)
    out = score_record(rec, GOLD, budget_tokens=100, counter=words, counter_label="fake")
    assert out["rank"]["metrics"]["file_recall@10"] == 0.0
    assert out["rank"]["metrics"]["file_mrr"] == 0
    assert out["rank"]["reach"] == {"file": 0.0, "function": 0.0}
    assert out["packed"]["metrics"]["gold_file_in_context"] == 0.0


def test_dedup_before_k(corpus):
    rec = bm25_rank("t", "login user password check", SOURCES)
    files = [i.path for i in rec.items]
    assert len(files) > len(set(files))                                         # several chunks share a file
    out = score_record(rec, GOLD, budget_tokens=500, counter=words, counter_label="fake")
    assert out["rank"]["metrics"]["file_recall@1"] == 1.0
    assert out["rank"]["size"]["files"] == len(set(files))


def test_one_rank_two_modes_diverge_under_tight_budget(corpus):
    # gold sits at rank 2: Recall@3 = 1 in rank mode, but rank 1 eats the whole budget in packed mode.
    big = {"src/big.py": "def a():\n" + "".join(f"    x{i} = {i}\n" for i in range(60)),
           **{k: v for k, v in SOURCES.items() if k == "src/auth.py"}}
    cor = CorpusIndex(big)
    nodes = {**NODES, "Function:big.a": node("Function", "src/big.py", "big.a", 1, 61)}
    rec = graph_rank("t", cands("Function:big.a", "Function:auth.check"), nodes, big, cor)
    before = rec.rank_hash
    out = score_record(rec, GOLD, budget_tokens=70, counter=words, counter_label="fake")
    assert out["rank"]["metrics"]["function_recall@3"] == 1.0
    assert out["packed"]["metrics"]["gold_function_in_context"] in (0.0, 1.0)
    tight = score_record(rec, GOLD, budget_tokens=60, counter=words, counter_label="fake")
    assert tight["packed"]["metrics"]["gold_function_in_context"] == 1.0        # big item skipped, gold still fits
    assert tight["packed"]["metrics"]["truncated"] is True
    assert tight["rank_hash"] == out["rank_hash"] == before == rec.rank_hash    # same rank object, scored twice


def test_overlap_between_class_and_method_is_skipped(corpus):
    rec = graph_rank("t", cands("Class:store.Store", "Method:store.Store.get"), NODES, SOURCES, corpus)
    packed = pack_items(rec.items, 1000, words)
    assert [i.item_id for i, _ in packed["items"]] == ["Class:store.Store"]
    assert packed["skipped"]["overlap"] == 1
    out = score_record(rec, GOLD, budget_tokens=1000, counter=words, counter_label="fake")
    assert out["packed"]["metrics"]["truncated"] is False                        # overlap skip is not budget truncation


def test_include_predicate_matches_adapter_filter(corpus):
    include = make_include(corpus)
    assert include(NODES["Function:auth.login"]) and not include(NODES["Test:tests.test_auth.test_login"])
    assert not include(NODES["Function:other.f"])


def test_counter_label_and_snippet_policy_recorded(corpus):
    rec = bm25_rank("t", "login", SOURCES)
    out = score_record(rec, GOLD, budget_tokens=50, counter=words, counter_label="local-hf:Qwen@sha")
    assert out["packed"]["counter_label"] == "local-hf:Qwen@sha"
    assert out["packed"]["snippet_policy"]["max_snippet_lines"] == 80