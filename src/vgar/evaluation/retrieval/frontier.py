"""F*_approx: an approximation of the dependency frontier F*(T, R) of proposal §8.2 (spec 2026-11-17 §2.4).

F*_approx = the gold functions plus every repository function or method whose short name appears as a name token
on an added line of a source file (``is_source``) of the gold patch and has exactly one definition in the corpus.
Comments, strings and non-source files are left out; a line inside a multi-line docstring still counts, since each
added line is tokenized on its own. It uses no graph, so it does not favour the graph arms. Tests are left out
because the R1 corpus excludes test files for every arm.
"""
from __future__ import annotations

import builtins
import io
import keyword
import tokenize
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from vgar.evaluation.retrieval.chunks import is_source
from vgar.evaluation.retrieval.scoring import CorpusIndex

_SKIP = frozenset(keyword.kwlist) | frozenset(dir(builtins))


def _name_tokens(code: str) -> list[str]:
    """NAME tokens of one line of code; tokens before a tokenize error (open bracket or string) are kept."""
    names: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code + "\n").readline):
            if token.type == tokenize.NAME:
                names.append(token.string)
    except (tokenize.TokenError, SyntaxError):
        pass
    return names


def added_code_names(patch: str) -> set[str]:
    """Names in the code (not comments or strings) of the added lines of source files of a unified diff."""
    names: set[str] = set()
    path = None
    for line in patch.splitlines():
        if line.startswith("+++"):
            target = line[4:].split("\t", 1)[0]
            path = target[2:] if target.startswith("b/") else None
        elif line.startswith("+") and path is not None and is_source(path):
            names.update(_name_tokens(line[1:].strip()))
    return names - _SKIP


def dependency_frontier(patch: str, gold: Mapping[str, Any], corpus: CorpusIndex) -> list[str]:
    """Sorted function ids of F*_approx for one task.

    Args:
        patch: Gold patch (unified diff).
        gold: Gold labels with ``gold_functions``.
        corpus: Function identities of the task's corpus.
    """
    by_name: dict[str, list[str]] = defaultdict(list)
    for definitions in corpus.definitions.values():
        for definition in definitions:
            by_name[definition["symbol"].rsplit(".", 1)[-1]].append(definition["parent_id"])
    extra = {by_name[name][0] for name in added_code_names(patch) if len(by_name.get(name, ())) == 1}
    return sorted(set(gold["gold_functions"]) | extra)
