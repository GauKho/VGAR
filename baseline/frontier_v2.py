"""F*_core v2 (spec 2026-11-19 §9): F*_approx of ``vgar.evaluation.retrieval.frontier`` plus names on REMOVED lines.

F*_core v2 = the gold functions plus every repository function or method whose short name appears as a name token in
the code of an added or removed line of a source file of the gold patch, and has exactly one definition in the corpus.
No graph is used, so it does not favour the graph arms.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import baseline._paths  # noqa: F401
from vgar.evaluation.retrieval.chunks import is_source
from vgar.evaluation.retrieval.frontier import _SKIP, _name_tokens
from vgar.evaluation.retrieval.scoring import CorpusIndex


def changed_code_names(patch: str) -> set[str]:
    """Names in the code of added and removed lines of source files of a unified diff."""
    names: set[str] = set()
    old = path = None
    for line in patch.splitlines():
        if line.startswith("---"):
            source = line[4:].split("\t", 1)[0]
            old = source[2:] if source.startswith("a/") else None
        elif line.startswith("+++"):
            target = line[4:].split("\t", 1)[0]
            path = target[2:] if target.startswith("b/") else old   # deleted file: keep the old path
        elif line[:1] in "+-" and path is not None and is_source(path):
            names.update(_name_tokens(line[1:].strip()))
    return names - _SKIP


def frontier_core_v2(patch: str, gold: Mapping[str, Any], corpus: CorpusIndex) -> list[str]:
    """Sorted function ids of F*_core v2 for one task."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for definitions in corpus.definitions.values():
        for definition in definitions:
            by_name[definition["symbol"].rsplit(".", 1)[-1]].append(definition["parent_id"])
    extra = {by_name[name][0] for name in changed_code_names(patch) if len(by_name.get(name, ())) == 1}
    return sorted(set(gold["gold_functions"]) | extra)
