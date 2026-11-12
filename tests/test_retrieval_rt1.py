"""RT-1: G_arch dependents, MAY_CALL decay, TRACES_TO seeds and Port-based public API, each behind an off-by-default flag."""
from __future__ import annotations

import pytest

from vgar.contracts.error import InvalidLimitError, InvalidQueryError
from vgar.graph.retrieval import RetrievalConfig, ranking_config_hash

FROZEN = "sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a"


def test_default_hash_is_frozen():
    assert ranking_config_hash(RetrievalConfig()) == FROZEN


@pytest.mark.parametrize("field,value", [
    ("use_component_dependents", True), ("dependent_symbols_per_component", 5),
    ("may_call_factor", 0.5), ("use_trace_component", True), ("public_api_from_ports", True),
])
def test_each_flag_changes_the_hash(field, value):
    assert ranking_config_hash(RetrievalConfig(**{field: value})) != FROZEN


@pytest.mark.parametrize("field,value", [
    ("may_call_factor", -0.1), ("may_call_factor", 1.5), ("may_call_factor", True),
    ("dependent_symbols_per_component", 0), ("dependent_symbols_per_component", True),
    ("use_trace_component", 1), ("use_component_dependents", "yes"), ("public_api_from_ports", 0),
])
def test_invalid_flag_values_are_rejected(field, value):
    with pytest.raises((InvalidQueryError, InvalidLimitError)):
        RetrievalConfig(**{field: value})


# --------------------------------------------------------------------------- helpers
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder


def _write(root, files):
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _symbol_id(document, name):
    matches = sorted(node["id"] for node in document["nodes"]
                     if node["type"] in {"Function", "Method"} and node["name"] == name)
    assert matches, f"no symbol named {name}"
    return matches[0]


def _retrieve(tmp_path, files, *, anchor=None, issue="", overlay=False, include=None, document=None,
              tweak_overlay=None, **config):
    root = tmp_path / "repo"
    if not root.exists():
        _write(root, files)
    document = document or PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(root)
    retriever = GraphContextRetriever(document, root, count_tokens=lambda text: len(text) // 4,
                                      counter_label="test", config=RetrievalConfig(**config))
    built = TaskOverlayBuilder(document).build("t", issue, None) if overlay else None
    if built is not None and tweak_overlay is not None:
        tweak_overlay(built)
    anchors = [anchor_id for anchor_id in ([_symbol_id(document, anchor)] if anchor else [])]
    if built is not None:
        anchors += [item.node_id for item in built.grounding.anchors]
    return retriever.retrieve(sorted(set(anchors)), 12000, issue_text=issue, overlay=built, include=include)


def _confidence(result, symbol):
    return next(c["confidence"] for c in result.candidates if c["symbol"] == symbol)


def _ids(result):
    return [c["node_id"] for c in result.candidates]


# --------------------------------------------------------------------------- Task 2: components_depending_on
PRICING_REPO = {
    "shop/__init__.py": "",
    "shop/pricing/__init__.py": "",
    "shop/pricing/rounding.py": "def round_vnd(amount):\n    return (amount + 50) // 100 * 100\n",
    "shop/checkout/__init__.py": "",
    "shop/checkout/total.py": (
        "from shop.pricing.rounding import round_vnd\n\n"
        "def subtotal(lines):\n    return round_vnd(sum(lines)) + round_vnd(0)\n\n"
        "def grand_total(lines, tax):\n    return round_vnd(sum(lines) + tax)\n\n"
        "def apply_fee(lines, fee):\n    return round_vnd(sum(lines) + fee)\n\n"
        "def split_bill(lines, people):\n    return round_vnd(sum(lines) // people)\n"
    ),
    "shop/audit/__init__.py": "",
    "shop/audit/log.py": "def record(event):\n    return {'event': event}\n",
}


def _dependents(result):
    return [c for c in result.candidates if c["graph_rationale"][:1] == ["COMPONENT_DEPENDENT"]]


def test_dependents_add_at_most_three_callers(tmp_path):
    result = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd", use_component_dependents=True, max_hops=0)
    added = _dependents(result)
    # subtotal makes two calls, so it is always among the three kept callers.
    assert any(c["symbol"].endswith(".subtotal") for c in added)
    assert len(added) == 3 and all(c["graph_distance"] == 2 for c in added)
    assert "architecture_dependencies" not in result.unavailable_features


def test_dependents_off_keeps_old_candidates(tmp_path):
    off = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd", use_component_dependents=False)
    default = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd")
    assert _ids(off) == _ids(default) and not _dependents(off)
    assert "architecture_dependencies" in off.unavailable_features


def test_component_without_dependents_adds_nothing(tmp_path):
    on = _retrieve(tmp_path, PRICING_REPO, anchor="record", use_component_dependents=True)
    off = _retrieve(tmp_path, PRICING_REPO, anchor="record")
    assert _ids(on) == _ids(off) and not _dependents(on)


def test_cyclic_components_do_not_duplicate(tmp_path):
    files = {"pkg/__init__.py": "", "pkg/a/__init__.py": "", "pkg/b/__init__.py": "",
             "pkg/a/core.py": "from pkg.b.core import normalize\n\ndef parse(value):\n    return normalize(value)\n",
             "pkg/b/core.py": "from pkg.a.core import parse\n\ndef normalize(value):\n    return parse(value).lower()\n"}
    result = _retrieve(tmp_path, files, anchor="parse", use_component_dependents=True)
    assert len(_ids(result)) == len(set(_ids(result)))


def _without_architecture(document):
    dropped = {node["id"] for node in document["nodes"] if node["type"] in {"Component", "Port"}}
    return {**document, "nodes": [n for n in document["nodes"] if n["id"] not in dropped],
            "edges": [e for e in document["edges"] if e["source_id"] not in dropped and e["target_id"] not in dropped]}


def test_graph_without_components(tmp_path):
    _write(tmp_path / "repo", PRICING_REPO)
    document = _without_architecture(
        PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(tmp_path / "repo"))
    on = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd", document=document, use_component_dependents=True)
    off = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd", document=document)
    assert _ids(on) == _ids(off)
    assert "architecture_dependencies" in on.unavailable_features


def test_flat_repo_has_no_dependents(tmp_path):
    files = {"utils.py": "def slugify(value):\n    return value.lower()\n"}
    on = _retrieve(tmp_path, files, anchor="slugify", use_component_dependents=True)
    off = _retrieve(tmp_path, files, anchor="slugify")
    assert _ids(on) == _ids(off) and not _dependents(on)


def test_dependents_respect_include(tmp_path):
    result = _retrieve(tmp_path, PRICING_REPO, anchor="round_vnd", use_component_dependents=True,
                       include=lambda node: "checkout" not in (node.get("path") or ""))
    assert not _dependents(result)


# --------------------------------------------------------------------------- Task 3: MAY_CALL decay
_CONTAINER = "class {name}:\n    def __init__(self):\n        self.items = {{}}\n\n    def add(self, item, qty):\n        self.items[item] = qty\n"
DISPATCH_REPO = {
    "store/__init__.py": "",
    "store/cart.py": _CONTAINER.format(name="Cart"),
    "store/wishlist.py": _CONTAINER.format(name="Wishlist"),
    "store/inventory.py": _CONTAINER.format(name="Inventory"),
    "store/coupon.py": "def apply_coupon(cart):\n    cart.coupon_applied = True\n    return cart\n",
    "store/service.py": ("from store.coupon import apply_coupon\n\n"
                         "def handle_add(container, item, qty):\n    container.add(item, qty)\n\n"
                         "def checkout(cart):\n    return apply_coupon(cart)\n"),
}
ADDS = {"store.cart.Cart.add", "store.wishlist.Wishlist.add", "store.inventory.Inventory.add"}


def _walked_adds(result):
    return {c["symbol"] for c in result.candidates
            if c["symbol"] in ADDS and any(step.startswith("CALLS:") for step in c["graph_rationale"])}


def test_may_call_off_does_not_walk(tmp_path):
    assert not _walked_adds(_retrieve(tmp_path, DISPATCH_REPO, anchor="handle_add"))


def test_may_call_factor_reaches_all_candidates(tmp_path):
    result = _retrieve(tmp_path, DISPATCH_REPO, anchor="handle_add", may_call_factor=0.5)
    assert _walked_adds(result) == ADDS
    assert all(_confidence(result, symbol) <= 0.5 * 0.5 + 1e-9 for symbol in ADDS)


def test_higher_factor_never_lowers_score(tmp_path):
    def score(factor):
        result = _retrieve(tmp_path, DISPATCH_REPO, anchor="handle_add", may_call_factor=factor)
        return next(c["relevance_score"] for c in result.candidates if c["symbol"] == "store.cart.Cart.add")
    assert score(1.0) >= score(0.5)


def test_may_call_does_not_count_as_fan_in(tmp_path):
    def risk(**config):
        result = _retrieve(tmp_path, DISPATCH_REPO, anchor="add", **config)
        return {c["symbol"]: c["features"]["public_api_risk"] for c in result.candidates}
    assert risk(may_call_factor=1.0)["store.cart.Cart.add"] == risk()["store.cart.Cart.add"]


# --------------------------------------------------------------------------- Task 4: TRACES_TO seeds
FEE_REPO = {
    "fees/__init__.py": "",
    "fees/discounts/__init__.py": "",
    "fees/discounts/rules.py": "def calculate(order):\n    return 1000 // order.item_count\n\n\ndef discount_rate(order):\n    return 0.1\n",
    "fees/shipping/__init__.py": "",
    "fees/shipping/rates.py": "def calculate(order):\n    return weight_fee(order.weight)\n\n\ndef weight_fee(weight):\n    return weight * 1000\n",
    "fees/tax/__init__.py": "",
    "fees/tax/vat.py": "def calculate(order):\n    return weight_tax(order.weight)\n\n\ndef weight_tax(weight):\n    return int(weight * 0.1)\n",
    "fees/engine.py": ("from fees.discounts.rules import calculate as discount\n"
                       "from fees.shipping.rates import calculate as shipping\n"
                       "from fees.tax.vat import calculate as tax\n\n\n"
                       "def total(order):\n    return discount(order) + shipping(order) + tax(order)\n"),
}
TRACEBACK_ISSUE = """total() fails on an empty order
Traceback (most recent call last):
  File "fees/discounts/rules.py", line 2, in calculate
ZeroDivisionError: integer division or modulo by zero
"""
TIED_ISSUE = """weight given as text breaks fees
Traceback (most recent call last):
  File "fees/shipping/rates.py", line 6, in weight_fee
  File "fees/tax/vat.py", line 6, in weight_tax
TypeError: can't multiply sequence by non-int of type 'float'
"""


def _trace_seeds(result):
    return [c for c in result.candidates if c["graph_rationale"] == ["TRACE_COMPONENT"]]


def test_trace_component_ports_become_seeds(tmp_path):
    result = _retrieve(tmp_path, FEE_REPO, issue=TRACEBACK_ISSUE, overlay=True, use_trace_component=True)
    seeds = _trace_seeds(result)
    assert seeds and all(c["path"] == "fees/discounts/rules.py" for c in seeds)
    assert all(c["confidence"] == 0.45 for c in seeds)
    assert result.config["trace_component_id"]


def test_issue_without_traceback_is_unchanged(tmp_path):
    issue = "free shipping is wrong at 500000"
    on = _retrieve(tmp_path, FEE_REPO, issue=issue, overlay=True, use_trace_component=True)
    off = _retrieve(tmp_path, FEE_REPO, issue=issue, overlay=True)
    assert _ids(on) == _ids(off) and not _trace_seeds(on)


def test_trace_below_threshold_is_ignored(tmp_path):
    def weaken(overlay):
        for edge in overlay.edges:
            if edge["type"] == "TRACES_TO":
                edge["confidence"] = 0.6
    on = _retrieve(tmp_path, FEE_REPO, issue=TRACEBACK_ISSUE, overlay=True, tweak_overlay=weaken, use_trace_component=True)
    off = _retrieve(tmp_path, FEE_REPO, issue=TRACEBACK_ISSUE, overlay=True, tweak_overlay=weaken)
    assert _ids(on) == _ids(off) and not _trace_seeds(on)


def test_equal_traces_pick_the_same_component_every_run(tmp_path):
    first = _retrieve(tmp_path, FEE_REPO, issue=TIED_ISSUE, overlay=True, use_trace_component=True)
    second = _retrieve(tmp_path, FEE_REPO, issue=TIED_ISSUE, overlay=True, use_trace_component=True)
    assert _ids(first) == _ids(second)
    assert len({c["path"] for c in _trace_seeds(first)}) <= 1


def test_trace_seeds_respect_include(tmp_path):
    result = _retrieve(tmp_path, FEE_REPO, issue=TRACEBACK_ISSUE, overlay=True, use_trace_component=True,
                       include=lambda node: "discounts" not in (node.get("path") or ""))
    assert not _trace_seeds(result)


# --------------------------------------------------------------------------- Task 5: public_api_risk from Ports, service config
INVOICE_REPO = {
    "ledger/__init__.py": "",
    "ledger/invoice/__init__.py": "",
    "ledger/invoice/export.py": (
        "def _format_line(line):\n    return str(line)\n\n\n"
        "def helper(text):\n    return text.strip()\n\n\n"
        "def export_invoice(lines):\n    return [_format_line(line) for line in lines] + [helper('TOTAL')]\n"),
}


def _risk(result):
    return {c["symbol"].rsplit(".", 1)[-1]: c["features"]["public_api_risk"] for c in result.candidates}


def test_public_api_uses_ports_when_present(tmp_path):
    _write(tmp_path / "repo", INVOICE_REPO)
    document = PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(tmp_path / "repo")
    # Keep only the export_invoice Port, so helper is public by visibility but has no Port.
    ports = [n["id"] for n in document["nodes"] if n["type"] == "Port"
             and not n["properties"]["symbol_id"].endswith(".export_invoice")]
    document = {**document, "nodes": [n for n in document["nodes"] if n["id"] not in ports],
                "edges": [e for e in document["edges"] if e["source_id"] not in ports and e["target_id"] not in ports]}
    on = _risk(_retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice", document=document, public_api_from_ports=True))
    off = _risk(_retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice", document=document))
    assert on["export_invoice"] > 0.0 and on["_format_line"] == 0.0 and on["helper"] == 0.0
    assert off["helper"] > 0.0


def test_public_api_falls_back_to_visibility_without_ports(tmp_path):
    _write(tmp_path / "repo", INVOICE_REPO)
    document = _without_architecture(
        PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(tmp_path / "repo"))
    on = _retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice", document=document, public_api_from_ports=True)
    off = _retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice", document=document)
    assert _risk(on) == _risk(off)


def test_zero_weight_keeps_ranking(tmp_path):
    on = _retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice", public_api_from_ports=True)
    off = _retrieve(tmp_path, INVOICE_REPO, anchor="export_invoice")
    assert _ids(on) == _ids(off)


def test_service_passes_config(tmp_path):
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    _write(tmp_path / "repo", INVOICE_REPO)
    document = PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(tmp_path / "repo")
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    service = SQLiteGraphService(store, repository_root=tmp_path / "repo", count_tokens=len, counter_label="test")
    anchor = _symbol_id(document, "export_invoice")
    config = RetrievalConfig(may_call_factor=0.5)
    tuned = service.get_related_context([anchor], 1000, graph_version=document["graph_version"], task_id="a",
                                        issue_text="invoice", config=config)
    plain = service.get_related_context([anchor], 1000, graph_version=document["graph_version"], task_id="b",
                                        issue_text="invoice")
    assert tuned["diagnostics"]["config"]["ranking_config_hash"] == ranking_config_hash(config)
    assert plain["diagnostics"]["config"]["ranking_config_hash"] == FROZEN


# --------------------------------------------------------------------------- Task 8: RT1_CONFIG
def test_rt1_config_matches_the_measured_file():
    import json
    from pathlib import Path

    from vgar.graph.retrieval import RT1_CONFIG
    measured = json.loads((Path(__file__).resolve().parents[1] / "configs/rt1/rt1_config.json").read_text(encoding="utf-8"))
    assert RT1_CONFIG == RetrievalConfig(**measured)
    assert ranking_config_hash(RetrievalConfig()) == FROZEN


def test_dependent_limit_is_per_component_not_per_anchor(tmp_path):
    callers = "".join(f"def caller_{i}(x):\n    return round_vnd(x) + round_usd(x)\n\n" for i in range(8))
    files = {"shop/__init__.py": "", "shop/pricing/__init__.py": "",
             "shop/pricing/rounding.py": "def round_vnd(a):\n    return a\n\n\ndef round_usd(a):\n    return a\n",
             "shop/checkout/__init__.py": "",
             "shop/checkout/total.py": "from shop.pricing.rounding import round_vnd, round_usd\n\n" + callers}
    _write(tmp_path / "repo", files)
    document = PythonGraphBuilder(repo_key="t/rt1", repository_revision="rev").build(tmp_path / "repo")
    root = tmp_path / "repo"
    retriever = GraphContextRetriever(document, root, count_tokens=lambda text: len(text) // 4, counter_label="test",
                                      config=RetrievalConfig(use_component_dependents=True, max_hops=0))
    result = retriever.retrieve(sorted([_symbol_id(document, "round_vnd"), _symbol_id(document, "round_usd")]), 12000)
    assert len(_dependents(result)) == 3


def test_trace_seeds_come_from_the_failing_package_when_an_outer_frame_ties(tmp_path):
    issue = TRACEBACK_ISSUE.replace('Traceback (most recent call last):\n',
                                    'Traceback (most recent call last):\n  File "fees/engine.py", line 7, in total\n')
    result = _retrieve(tmp_path, FEE_REPO, issue=issue, overlay=True, use_trace_component=True)
    assert result.config["trace_component_id"].endswith(":component:fees/discounts")
    assert all(c["path"] == "fees/discounts/rules.py" for c in _trace_seeds(result))
