"""L2-1: the pure rules that turn JARVIS's function-level call graph into decisions about call sites."""
from __future__ import annotations

import pytest

from vgar.graph.jarvis_merge import (
    Site,
    Target,
    accumulate,
    merge_caller,
    resolve_callees,
)


def _site(id="s", text="foo", args=0, calls=(), candidates=(), external=False, lexical=False) -> Site:
    return Site(id, text, args, frozenset(calls), frozenset(candidates), external, lexical)


def _target(id="B", name="foo", max_arguments=None, dunder=False) -> Target:
    return Target(id, name, max_arguments, dunder)


def test_existing_edge_is_bound_first() -> None:
    x, y = _site("x", "x.foo", calls=("X.foo",)), _site("y", "y.foo")
    outcome = merge_caller([x, y], [_target("X.foo"), _target("Y.foo")], set())
    assert outcome.confirmed == (("x", "X.foo"),)
    assert outcome.may_call == (("y", "Y.foo", "jarvis"),) and outcome.new_calls == ()


def test_no_false_conflict_on_a_resolved_site_with_the_same_name() -> None:
    x, y = _site("x", "x.foo", calls=("X.foo",)), _site("y", "y.foo")
    outcome = merge_caller([x, y], [_target("Y.foo")], set())
    assert outcome.counts["conflicts"] == 0 and outcome.may_call == (("y", "Y.foo", "jarvis"),)


def test_two_sites_with_one_name_are_never_certain() -> None:
    data, codec = _site("d", "data.get", candidates=("C.get",)), _site("c", "codec.get", candidates=("C.get",))
    outcome = merge_caller([data, codec], [_target("C.get", "get")], {"get"})
    assert outcome.upgraded == () and outcome.new_calls == ()
    assert set(outcome.supported) == {("d", "C.get"), ("c", "C.get")}


def test_certain_candidate_is_upgraded() -> None:
    outcome = merge_caller([_site(candidates=("B",))], [_target()], set())
    assert outcome.upgraded == (("s", "B"),) and outcome.may_call == () and outcome.supported == ()


def test_external_name_blocks_certainty() -> None:
    outcome = merge_caller([_site()], [_target()], {"foo"})
    assert outcome.new_calls == () and outcome.may_call == (("s", "B", "jarvis"),)


def test_certainty_needs_the_site_to_carry_the_name() -> None:
    init, make = _site("i", "super().__init__", candidates=("B",)), _site("m", "make.Base", candidates=("B",))
    outcome = merge_caller([init, make], [_target("B", "Base")], set())
    assert outcome.upgraded == (("m", "B"),) and outcome.supported == (("i", "B"),)


def test_certain_unresolved_site_gets_a_call() -> None:
    outcome = merge_caller([_site()], [_target()], set())
    assert outcome.new_calls == (("s", "B"),) and outcome.may_call == ()


def test_several_targets_become_may_call() -> None:
    outcome = merge_caller([_site()], [_target("A"), _target("B")], set())
    assert outcome.may_call == (("s", "A", "jarvis"), ("s", "B", "jarvis")) and outcome.new_calls == ()


def test_arity_removes_a_site_only_when_several_match() -> None:
    sites = [_site("one", args=1), _site("three", args=3)]
    outcome = merge_caller(sites, [_target(max_arguments=1)], set())
    assert outcome.may_call == (("one", "B", "jarvis"),) and outcome.new_calls == ()


def test_arity_is_not_applied_to_a_single_site() -> None:
    outcome = merge_caller([_site(args=3)], [_target(max_arguments=1)], set())
    assert outcome.new_calls == (("s", "B"),)


def test_arity_can_remove_every_site() -> None:
    outcome = merge_caller([_site("a", args=3), _site("b", args=4)], [_target(max_arguments=1)], set())
    assert outcome.may_call == () and outcome.new_calls == () and outcome.counts["no_call_site"] == 1


def test_max_arguments_none_keeps_all_sites() -> None:
    outcome = merge_caller([_site("a", args=1), _site("b", args=3)], [_target()], set())
    assert outcome.may_call == (("a", "B", "jarvis"), ("b", "B", "jarvis"))


def test_conflict_keeps_calls_and_adds_may_call() -> None:
    outcome = merge_caller([_site(calls=("T",))], [_target()], set())
    assert outcome.confirmed == () and outcome.may_call == (("s", "B", "jarvis_conflict"),) and outcome.counts["conflicts"] == 1


def test_confirm_wins_when_target_is_among_calls() -> None:
    outcome = merge_caller([_site(calls=("T",))], [_target("T"), _target("B")], set())
    assert outcome.confirmed == (("s", "T"),) and outcome.may_call == () and outcome.counts["conflicts"] == 0


def test_external_site_never_gets_a_call() -> None:
    outcome = merge_caller([_site(external=True)], [_target()], set())
    assert outcome.new_calls == () and outcome.may_call == (("s", "B", "jarvis_conflict"),) and outcome.counts["conflicts"] == 1


def test_conflict_does_not_repeat_an_existing_candidate() -> None:
    outcome = merge_caller([_site(external=True, candidates=("B",))], [_target()], set())
    assert outcome.may_call == () and outcome.supported == (("s", "B"),) and outcome.upgraded == ()


def test_external_site_gets_no_indirect_edge() -> None:
    outcome = merge_caller([_site(text="handler", external=True, lexical=True)], [_target(name="other")], set())
    assert outcome.may_call == () and outcome.counts["no_call_site"] == 1


def test_new_target_joins_existing_candidates() -> None:
    outcome = merge_caller([_site(candidates=("A",))], [_target("A"), _target("B")], set())
    assert outcome.supported == (("s", "A"),) and outcome.may_call == (("s", "B", "jarvis"),)


def test_six_new_targets_overflow() -> None:
    outcome = merge_caller([_site()], [_target(f"T{n}") for n in range(6)], set())
    assert outcome.may_call == () and outcome.counts["overflow_unresolved_calls"] == 1


def test_existing_candidates_count_towards_the_cap() -> None:
    outcome = merge_caller([_site(candidates=("C0", "C1", "C2", "C3"))], [_target("N0"), _target("N1")], set())
    assert outcome.may_call == () and outcome.counts["overflow_unresolved_calls"] == 1


def test_five_candidates_are_allowed() -> None:
    outcome = merge_caller([_site(candidates=("C0", "C1", "C2", "C3"))], [_target("N0")], set())
    assert outcome.may_call == (("s", "N0", "jarvis"),) and outcome.counts["overflow_unresolved_calls"] == 0


def test_expression_callee_is_indirect() -> None:
    outcome = merge_caller([_site(text="HANDLERS[action]")], [_target(name="handle_create")], set())
    assert outcome.may_call == (("s", "B", "jarvis_indirect"),)


def test_local_name_is_indirect() -> None:
    outcome = merge_caller([_site(text="handler", lexical=True)], [_target(name="other")], set())
    assert outcome.may_call == (("s", "B", "jarvis_indirect"),)


def test_indirect_is_never_a_call() -> None:
    outcome = merge_caller([_site(text="HANDLERS[action]")], [_target(name="only")], set())
    assert outcome.new_calls == () and outcome.upgraded == ()


def test_builtin_name_gets_no_edge() -> None:
    outcome = merge_caller([_site(text="isinstance")], [_target(name="other")], set())
    assert outcome.may_call == () and outcome.counts["no_call_site"] == 1


def test_attribute_call_with_another_name_gets_no_edge() -> None:
    outcome = merge_caller([_site(text="obj.other")], [_target()], set())
    assert outcome.may_call == () and outcome.counts["no_call_site"] == 1


def test_dunder_target_is_not_attached() -> None:
    outcome = merge_caller([_site(text="HANDLERS[a]")], [_target(name="__enter__", dunder=True)], set())
    assert outcome.may_call == () and outcome.counts["no_call_site"] == 1


def test_resolved_site_gets_no_indirect_edge() -> None:
    outcome = merge_caller([_site(text="HANDLERS[a]", calls=("T",))], [_target(name="other")], set())
    assert outcome.may_call == () and outcome.counts["no_call_site"] == 1


def test_resolve_callees_collects_external_names() -> None:
    targets, external, counts = resolve_callees(["<map>.get", "append", "urllib.x.y", "pkg.f.<lambda1>"], {})
    assert targets == [] and external == {"get", "append", "y", "<lambda1>"} and counts["external"] == 4


def test_resolve_callees_merges_constructor_forms() -> None:
    names = {"pkg.C": [_target("C", "C")], "pkg.C.__init__": [_target("init", "__init__", 1)]}
    targets, external, _ = resolve_callees(["pkg.C.__init__", "pkg.C"], names)
    assert targets == [_target("C", "C")] and external == set()


def test_resolve_callees_marks_implicit_constructor() -> None:
    targets, _, _ = resolve_callees(["pkg.C.__new__"], {"pkg.C": [_target("C", "C")]})
    assert targets == [_target("C", "C", dunder=True)]


def test_resolve_callees_marks_dunder_methods() -> None:
    targets, _, _ = resolve_callees(["pkg.C.__enter__"], {"pkg.C.__enter__": [_target("e", "__enter__")]})
    assert targets == [_target("e", "__enter__", dunder=True)]


def test_resolve_callees_counts_ambiguous_names() -> None:
    targets, external, counts = resolve_callees(["pkg.size"], {"pkg.size": [_target("g", "size"), _target("s", "size")]})
    assert targets == [] and external == {"size"} and counts["ambiguous_names"] == 1 and counts["external"] == 0


def test_resolve_callees_drops_repeated_names() -> None:
    targets, _, _ = resolve_callees(["pkg.f", "pkg.f"], {"pkg.f": [_target("f", "f")]})
    assert targets == [_target("f", "f")]


@pytest.mark.parametrize("old,new", [(0.60, 0.78), (0.95, 0.97), (0.98, 0.99)])
def test_accumulate(old: float, new: float) -> None:
    assert accumulate(old) == new and accumulate(old) >= old


def test_accumulate_never_rounds_below_the_old_value() -> None:
    assert accumulate(0.9905) >= 0.9905
