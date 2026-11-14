"""L5-2 Python side: sample selection, fallback templates, exception supplement, noise filter, node ids."""
from __future__ import annotations

from invariant_helpers import run_variant

from vgar.repair.invariants import (
    check_python,
    describe,
    exception_violations,
    is_noise,
    learn_python,
    load_trace,
    node_id_for,
    point_sets,
    select_samples,
)


def _rec(ppt, kind, test, **values):
    return {"ppt": ppt, "path": "src/m.py", "qualname": ppt.split("(")[0].split(".")[-1], "kind": kind,
            "nonce": 1, "test": test, "vars": values}


def test_select_samples_keeps_only_given_tests():
    records = [_rec("m.f(x)", "enter", "t::ok", x=1), _rec("m.f(x)", "exit", "t::ok", x=1, **{"return": 2}),
               _rec("m.f(x)", "enter", "t::bad", x=9), _rec("m.f(x)", "exit", "t::bad", x=9, **{"return": 0})]
    points = select_samples(records, {"t::ok"})
    assert points == {"m.f(x):::ENTER": [{"x": 1, "__test__": "t::ok"}],
                      "m.f(x):::EXIT": [{"x": 1, "return": 2, "__test__": "t::ok"}]}


def test_objects_are_not_samples_but_fields_are():
    record = _rec("m.g()", "exit", "t", **{"return": {"__object__": "C", "__id__": 7}, "return.a": 1})
    assert select_samples([record], {"t"}) == {"m.g():::EXIT": [{"return.a": 1, "__test__": "t"}]}


def test_learn_and_check_templates():
    rows = [{"x": x, "y": 2 * x + 1, "s": "a", "k": k} for x, k in ((1, 0), (2, 1), (3, 0), (4, 1))]
    texts = {describe(inv) for inv in learn_python({"p:::EXIT": rows})}
    assert {"s == 'a'", "k one of [0, 1]", "1 <= x <= 4", "x >= 0", "x < y", "y == 2 * x + 1"} <= texts
    invariants = learn_python({"p:::EXIT": rows})
    assert check_python(invariants, {"p:::EXIT": rows}) == []
    broken = check_python(invariants, {"p:::EXIT": [{"x": 2, "y": 9, "s": "a", "k": 1}]})
    assert {v["invariant"] for v in broken} == {"y == 2 * x + 1"}


def test_too_few_samples_give_no_invariant():
    assert learn_python({"p:::EXIT": [{"x": 1}]}) == []
    texts = {describe(inv) for inv in learn_python({"p:::EXIT": [{"x": 1, "y": 2}, {"x": 2, "y": 3}]})}
    assert not any("y" in t and "x" in t for t in texts)  # binary templates need >= 3 samples


def test_missing_candidate_samples_are_unexercised():
    invariants = learn_python({"p:::EXIT": [{"x": 1}, {"x": 1}]})
    assert check_python(invariants, {}) == []
    new, unexercised = point_sets({"p:::EXIT": [{}]}, {"q:::EXIT": [{}]})
    assert (new, unexercised) == (["q:::EXIT"], ["p:::EXIT"])


def test_new_exception_class_is_violation():
    base = [{**_rec("m.f(x)", "raise", "t1", x=-1), "exception": "ValueError"}]
    cand = [{**_rec("m.f(x)", "raise", "t1", x=-1), "exception": "KeyError"}]
    violation, = exception_violations(base, cand, {"t1"})
    assert violation["program_point"] == "m.f(x)" and "KeyError" in violation["invariant"]


def test_stopped_raising_is_violation():
    base = [{**_rec("m.f(x)", "raise", "t1", x=-1), "exception": "ValueError"}]
    cand = [_rec("m.f(x)", "exit", "t1", x=-1, **{"return": 0})]
    violation, = exception_violations(base, cand, {"t1"})
    assert "ValueError" in violation["invariant"] and violation["test"] == "t1"
    assert exception_violations(base, cand, set()) == []  # only baseline-passing tests count


def test_noise_does_not_drop_user_size_variables():
    assert not is_noise("page_size == 10")
    assert is_noise("quantity >= this__quantities_size", {"this__quantities_size"})
    assert is_noise("this._quantities.__len__ < return.tax")


def test_noise_patterns():
    assert is_noise("quantity is a power of 2") and is_noise("return.discount == return.discount**2")
    assert is_noise("this__quantities_size % quantity == 0") and is_noise("return has only one value")
    assert is_noise("quantity >= this__quantities_size", {"this__quantities_size"})
    assert not is_noise("return.total one of { 250000, 440000, 550000 }")


def test_node_id_matches_builder_scheme():
    method = {"path": "src/shop/cart.py", "qualname": "Cart.add"}
    function = {"path": "src/shop/cart.py", "qualname": "helper"}
    assert node_id_for(method, "fx", ("src",), "r") == "vgar:fx:python:method:src/shop/cart.py:shop.cart.Cart.add"
    assert node_id_for(function, "fx", ("src",), "r") == "vgar:fx:python:function:src/shop/cart.py:shop.cart.helper"


def test_demo_shop_rule_gold_fix_zero_violations(tmp_path):
    base_trace, outcomes = run_variant("base", tmp_path)
    passing = {test for test, status in outcomes.items() if status == "PASS"}
    assert len(passing) == 10 and len(outcomes) == 11
    base_records, _ = load_trace(base_trace)
    invariants = learn_python(select_samples(base_records, passing))
    for name, expected in (("gold_fix", 0), ("M5_product_name_upper", 1)):
        trace, _ = run_variant(name, tmp_path)
        records, _ = load_trace(trace)
        violations = check_python(invariants, select_samples(records, passing))
        assert (len(violations) > 0) == bool(expected), (name, violations)


def test_empty_candidate_trace_is_not_run(tmp_path):
    import time

    from vgar.repair.invariants import InvariantSettings, compute_semantic_invariants

    base, outcomes = run_variant("base", tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    record = compute_semantic_invariants(base, empty, outcomes, InvariantSettings(), time.monotonic() + 60)
    assert (record["status"], record["reasons"]) == ("NOT_RUN", ["CANDIDATE_TRACE_EMPTY"])


def test_daikon_gets_a_deadline_with_margin(tmp_path, monkeypatch):
    import time

    import vgar.repair.invariants as inv
    from vgar.repair.daikon import DaikonConfig, DaikonUnavailable

    base, outcomes = run_variant("base", tmp_path)
    seen = {}

    def fake(config, b, c, work, deadline):
        seen["deadline"] = deadline
        raise DaikonUnavailable("deadline reached")

    monkeypatch.setattr(inv, "run_daikon", fake)
    jar = tmp_path / "d.jar"
    jar.write_bytes(b"")
    start = time.monotonic()
    record = inv.compute_semantic_invariants(base, base, outcomes, inv.InvariantSettings(
        daikon=DaikonConfig(jar=jar, java_home=tmp_path)), start + 100)
    assert seen["deadline"] <= start + 81 and record["engine"] == "python-fallback"


def test_result_records_noise_patterns(tmp_path):
    import time

    from vgar.repair.invariants import (
        NOISE_PATTERNS,
        InvariantSettings,
        compute_semantic_invariants,
    )

    base, outcomes = run_variant("base", tmp_path)
    record = compute_semantic_invariants(base, base, outcomes, InvariantSettings(), time.monotonic() + 60)
    assert record["noise_patterns"] == list(NOISE_PATTERNS)
