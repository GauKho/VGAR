"""Turn JARVIS's function-level call graph into decisions about call sites (plan L2-1).

JARVIS says "A calls B" but not on which line. These pure rules choose the call site; the builder applies the result.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace

from vgar.graph import may_call

logger = logging.getLogger(__name__)

CALL_CONFIDENCE = 0.75
CONFLICT_CONFIDENCE = 0.50
_JARVIS_WEIGHT = 0.6
_CONSTRUCTOR_SUFFIXES = (".__init__", ".__new__")


@dataclass(frozen=True)
class Site:
    """One call site of the caller, as the graph knows it before JARVIS."""

    id: str
    callee_text: str
    argument_count: int
    calls: frozenset[str]  # targets of its CALLS edges; a constructor counts as the id of its Class
    candidates: frozenset[str]  # targets of its MAY_CALL edges; a constructor counts as the id of its Class
    external: bool  # SCIP or LSP concluded the call leaves the repository
    lexical: bool  # a bare name bound to a parameter or local variable


@dataclass(frozen=True)
class Target:
    """A function, method or class JARVIS named as a callee."""

    id: str
    name: str  # the function or method name; the class name for a constructor
    max_arguments: int | None  # None when the argument count cannot rule it out (a class, or a signature with *)
    dunder: bool = False


@dataclass(frozen=True)
class Outcome:
    """What to do with the call sites of one caller; every tuple is sorted."""

    confirmed: tuple[tuple[str, str], ...]  # (site, target) of an existing CALLS edge
    supported: tuple[tuple[str, str], ...]  # (site, target) of an existing MAY_CALL edge, which only gains evidence
    upgraded: tuple[tuple[str, str], ...]  # (site, candidate) that becomes CALLS
    new_calls: tuple[tuple[str, str], ...]
    may_call: tuple[tuple[str, str, str], ...]  # (site, target, match_kind)
    counts: Counter[str]  # no_call_site, conflicts, overflow_unresolved_calls


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def resolve_callees(callees: Iterable[str], names: Mapping[str, Sequence[Target]]) -> tuple[list[Target], set[str], Counter[str]]:
    """Map JARVIS's callee names to targets; return them, the last name part of the calls with no single target, and the counts."""
    found: dict[str, Target] = {}
    external: set[str] = set()
    counts: Counter[str] = Counter()
    for callee in callees:
        name, implicit = callee, False
        for suffix in _CONSTRUCTOR_SUFFIXES:
            if callee.endswith(suffix) and callee[:-len(suffix)] in names:
                name, implicit = callee[:-len(suffix)], True
        matches = names.get(name, ())
        if len(matches) != 1:
            counts["ambiguous_names" if matches else "external"] += 1
            external.add(callee.rsplit(".", 1)[-1])  # another callee of this name means a same-named call site cannot be certain
            continue
        target = replace(matches[0], dunder=implicit or _is_dunder(matches[0].name))
        known = found.get(target.id)
        found[target.id] = target if known is None else replace(known, dunder=known.dunder and target.dunder)
    return sorted(found.values(), key=lambda item: item.id), external, counts


def _bound_sites(sites: Sequence[Site], target: Target) -> list[Site] | None:
    """Steps 1-3 of the binding; None when no site carries the target's name or an edge to it."""
    known = [site for site in sites if target.id in site.calls or target.id in site.candidates]
    if known:
        return known
    named = [site for site in sites if may_call.callee_name(site.callee_text) == target.name]
    unresolved = [site for site in named if not site.calls]
    if len(unresolved) > 1:
        unresolved = [site for site in unresolved if target.max_arguments is None or site.argument_count <= target.max_arguments]
    return unresolved or [site for site in named if site.calls] or None


def _indirect_sites(sites: Sequence[Site], target: Target) -> list[Site]:
    """Step 4: a call through an expression or a local name; a call with its own different name cannot be this target."""
    if target.dunder:
        return []
    return [site for site in sites if not site.calls and not site.external
            and (may_call.callee_name(site.callee_text) is None or site.lexical)]


def merge_caller(sites: Sequence[Site], targets: Sequence[Target], external_names: AbstractSet[str]) -> Outcome:
    """Decide what the targets JARVIS reported for one caller mean for its call sites."""
    by_id = {target.id: target for target in targets}
    bound: dict[str, set[str]] = defaultdict(set)
    indirect: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for target in targets:
        chosen = _bound_sites(sites, target)
        if chosen is not None:
            for site in chosen:
                bound[site.id].add(target.id)
            continue
        eligible = _indirect_sites(sites, target)
        counts["no_call_site"] += not eligible
        for site in eligible:
            indirect[site.id].add(target.id)

    same_name = Counter(may_call.callee_name(site.callee_text) for site in sites)
    confirmed: list[tuple[str, str]] = []
    supported: list[tuple[str, str]] = []
    upgraded: list[tuple[str, str]] = []
    new_calls: list[tuple[str, str]] = []
    added: list[tuple[str, str, str]] = []

    def add(site: Site, wanted: dict[str, str]) -> None:
        if len(site.candidates | set(wanted)) > may_call.MAX_CANDIDATES:
            counts["overflow_unresolved_calls"] += 1
        else:
            added.extend((site.id, target_id, kind) for target_id, kind in wanted.items())

    for site in sorted(sites, key=lambda item: item.id):
        found, through = bound[site.id], indirect[site.id]
        if site.calls or site.external:
            agreed = found & site.calls
            confirmed.extend((site.id, target_id) for target_id in agreed)
            if found and not agreed:
                counts["conflicts"] += 1
                supported.extend((site.id, target_id) for target_id in found & site.candidates)
                if found - site.candidates:
                    add(site, dict.fromkeys(found - site.candidates, "jarvis_conflict"))
            continue
        only = next(iter(found)) if len(found) == 1 else None
        if (only is not None and not through and may_call.callee_name(site.callee_text) == by_id[only].name
                and same_name[by_id[only].name] == 1 and by_id[only].name not in external_names):
            if only in site.candidates:
                upgraded.append((site.id, only))
                continue
            if not site.candidates:
                new_calls.append((site.id, only))
                continue
        supported.extend((site.id, target_id) for target_id in found & site.candidates)
        wanted = dict.fromkeys(found - site.candidates, "jarvis") | dict.fromkeys(through - site.candidates, "jarvis_indirect")
        if wanted:
            add(site, wanted)
    if counts:
        logger.debug("JARVIS merge counts: %s", dict(counts))
    return Outcome(tuple(sorted(confirmed)), tuple(sorted(supported)), tuple(sorted(upgraded)), tuple(sorted(new_calls)), tuple(sorted(added)), counts)


def accumulate(old: float) -> float:
    """Raise the confidence of a CALLS edge JARVIS agrees with; the result is never below the old value."""
    return max(old, round(1 - (1 - old) * (1 - _JARVIS_WEIGHT * CALL_CONFIDENCE), 2))
