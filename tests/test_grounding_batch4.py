"""Grounding rules G1-G4 of batch 4 (spec 2026-11-23 §4.5, proposal §6.6 and §15)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.grounding import TaskAnchorFinder

SHOP = {
    "shop/__init__.py": "",
    "shop/customers.py": "class Customer:\n    pass\n\n\nclass OrderService:\n    pass\n",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
    return root


def _document(tmp_path: Path, files: dict[str, str], name: str = "repo") -> tuple[Path, dict]:
    root = _write(tmp_path / name, files)
    return root, PythonGraphBuilder(repo_key=f"t/{name}", repository_revision="rev").build(root)


@pytest.fixture
def finder(tmp_path) -> TaskAnchorFinder:
    return TaskAnchorFinder(_document(tmp_path, SHOP)[1])


def score(finder: TaskAnchorFinder, text: str, name: str) -> float:
    return next(a.score for a in finder.find_task_anchors(text).anchors if a.symbol.endswith("." + name))


# --- G2: a capitalized word at the start of a sentence is prose -------------------------------------------

def test_capitalized_word_at_sentence_start_is_prose(finder):
    assert score(finder, "Customer C003 cannot order.", "Customer") == 0.4


def test_capitalized_word_after_a_full_stop_is_prose(finder):
    assert score(finder, "It broke. Customer data is lost.", "Customer") == 0.4


def test_capitalized_word_mid_sentence_keeps_its_score(finder):
    assert score(finder, "It returns a Customer object.", "Customer") == 0.6


def test_camel_case_at_sentence_start_stays_code(finder):
    assert score(finder, "OrderService fails here.", "OrderService") == 0.6


# --- G1: name parts --------------------------------------------------------------------------------------

ORDERS = {
    "shop/__init__.py": "",
    "shop/discount.py": "def coupon_rate(code):\n    return 0\n\n\ndef tier_discount_rate(tier):\n    return 0\n",
    "shop/orders.py": ("class Order:\n    pass\n\n\ndef cancel_order(order):\n    return order\n\n\n"
                       "def ship_order(order):\n    return order\n\n\ndef order_total(order):\n    return 0\n\n\n"
                       "def order_lines(order):\n    return []\n\n\ndef order_status(order):\n    return ''\n\n\n"
                       "def order_id(order):\n    return ''\n"),
}
GEARS = {"gears/__init__.py": "", "gears/parts.py": "".join(
    f"def {name}_gear():\n    return 0\n\n\n" for name in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta"))}
LONG_TEXT = "The alpha beta gamma delta epsilon zeta gear set slips."


@pytest.fixture
def order_finder(tmp_path) -> TaskAnchorFinder:
    return TaskAnchorFinder(_document(tmp_path, ORDERS, "orders")[1])


def anchors(finder: TaskAnchorFinder, text: str, failing_tests: list[str] | None = None) -> dict:
    return {a.symbol.rsplit(".", 1)[-1]: a for a in finder.find_task_anchors(text, failing_tests).anchors}


def name_part_anchors(finder: TaskAnchorFinder, text: str, failing_tests: list[str] | None = None) -> list:
    return [a for a in finder.find_task_anchors(text, failing_tests).anchors
            if any(e.kind == "name_part" for e in a.evidence)]


def test_coupon_word_anchors_coupon_rate(order_finder):
    anchor = anchors(order_finder, "Orders with coupon WELCOME10 get a wrong rate.")["coupon_rate"]
    assert 0.3 <= anchor.score <= 0.5 and anchor.evidence[0].kind == "name_part"


def test_a_common_part_alone_makes_no_anchor(order_finder):
    assert name_part_anchors(order_finder, "the order is wrong") == []


def test_a_partly_covered_name_makes_no_anchor(order_finder):
    assert "tier_discount_rate" not in anchors(order_finder, "Orders with coupon WELCOME10 get a wrong rate.")


def test_an_inflected_word_matches_by_prefix(order_finder):
    assert "cancel_order" in anchors(order_finder, "A shipped order can be cancelled.")


def test_an_exact_mention_outranks_a_name_part(order_finder):
    assert anchors(order_finder, "`ship_order` breaks when shipped")["ship_order"].score == 0.75


def test_at_most_five_name_part_anchors(tmp_path):
    finder = TaskAnchorFinder(_document(tmp_path, GEARS, "gears")[1])
    assert len(name_part_anchors(finder, LONG_TEXT)) == 5


def test_failing_test_text_gets_no_name_part(order_finder):
    assert name_part_anchors(order_finder, "", ["tests/test_x.py::test_coupon_rate_cancel"]) == []


# --- G3: quoted error messages -----------------------------------------------------------------------------

MESSAGES = {
    "shop/__init__.py": "",
    "shop/discount.py": ("def combine_rates(a, b):\n    if a > 1:\n        raise ValueError(f\"discount rate out of range: {a}\")\n"
                         "    return a * b\n"),
    "shop/validators.py": "def check(e):\n    raise ValueError(f\"invalid email: {e!r}\")\n",
}


def _service(tmp_path: Path, files: dict[str, str], *, with_sources: bool = True):
    from vgar.graph.snapshot_sources import read_graph_sources
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore

    root, document = _document(tmp_path, files, "svc")
    store = SQLiteGraphStore(tmp_path / "svc.db")
    store.ingest(document, sources=read_graph_sources(root, document) if with_sources else None)
    return SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test"), document["graph_version"]


@pytest.fixture
def message_service(tmp_path):
    return _service(tmp_path, MESSAGES)


def kinds(anchor: dict) -> set[str]:
    return {evidence["kind"] for evidence in anchor["evidence"]}


def test_quoted_message_in_prose_anchors_the_raising_function(message_service):
    service, version = message_service
    result = service.find_task_anchors('Paying always gets "discount rate out of range".', graph_version=version, task_id="t")
    top = result["anchors"][0]
    assert top["symbol"].endswith("combine_rates") and "quoted_message" in kinds(top) and top["score"] == 0.85


def test_a_two_word_generic_message_does_not_match(message_service):
    service, version = message_service
    result = service.find_task_anchors('Registering fails with "invalid email".', graph_version=version, task_id="t")
    assert not [a for a in result["anchors"] if "quoted_message" in kinds(a)]


def test_one_quoted_word_or_backticked_text_is_not_a_phrase():
    from vgar.graph.source_evidence import quoted_phrases

    assert quoted_phrases('use coupon "WELCOME10" and `"discount rate out of range"`') == ()
    assert quoted_phrases("it says “discount rate out of range”") == ("discount rate out of range",)


def test_a_labelled_line_still_matches(message_service):
    service, version = message_service
    result = service.find_task_anchors("ValueError: discount rate out of range: 10", graph_version=version, task_id="t")
    assert result["anchors"][0]["symbol"].endswith("combine_rates")


def test_source_evidence_is_built_once_per_version(message_service, monkeypatch):
    from vgar.graph import source_evidence

    service, version = message_service
    built = []
    real = source_evidence.SourceEvidence.__init__

    def counted(self, *args, **kwargs):
        built.append(1)
        real(self, *args, **kwargs)

    monkeypatch.setattr(source_evidence.SourceEvidence, "__init__", counted)
    for _ in range(3):
        service.find_task_anchors('it says "discount rate out of range"', graph_version=version, task_id="t")
    assert len(built) == 1


# --- G4: fall back to the source text ----------------------------------------------------------------------

PAGES = {
    "shop/__init__.py": "",
    # SourceEvidence counts attributes, short literals and free names, not parameters or locals (by design).
    "shop/repo.py": ("class Repo:\n    def paginate(self, items, page):\n"
                     "        return items[(page - 1) * self.page_size:page * self.page_size]\n\n\n"
                     "def total(values):\n    return sum(values)\n"),
}
NO_NAME_TEXT = "Asking for page 1 with page size 2 returns one item."


def test_text_fallback_finds_a_function_by_its_body(tmp_path):
    service, version = _service(tmp_path, PAGES)
    result = service.find_task_anchors(NO_NAME_TEXT, graph_version=version, task_id="t")
    assert [a["symbol"].rsplit(".", 1)[-1] for a in result["anchors"]] == ["paginate"]
    assert result["anchors"][0]["score"] == 0.2 and kinds(result["anchors"][0]) == {"text_match"}


def test_no_text_fallback_when_another_anchor_exists(tmp_path):
    service, version = _service(tmp_path, PAGES)
    result = service.find_task_anchors("`paginate` returns one item for page size 2", graph_version=version, task_id="t")
    assert all("text_match" not in kinds(a) for a in result["anchors"])


def test_no_text_fallback_without_stored_source(tmp_path):
    service, version = _service(tmp_path, PAGES, with_sources=False)
    assert service.find_task_anchors(NO_NAME_TEXT, graph_version=version, task_id="t")["anchors"] == []
