"""L2-2: constants and pure rules for MAY_CALL edges (proposal lines 551-567).

Design: docs/superpowers/specs/2026-11-08-tv2-l2-2-may-call-design.md
"""
from __future__ import annotations

import builtins
import re

RULE_VERSION = "may-call-v1"
MAX_CANDIDATES = 5
CONFIDENCE_CAP = 0.50
NAME_TOOL_PRECISION = 0.5
ANALYZER_TOOL_PRECISION = 0.7
NAME_SOURCE_TOOL = "vgar-builder-heuristic"

_TOOL_WEIGHT, _TYPE_WEIGHT, _IMPORT_WEIGHT = 0.6, 0.2, 0.2
_RECEIVER_ROOT = re.compile(r"\(*\s*([A-Za-z_]\w*)")
# super() names a class in the repo, so it is handled by the caller instead of being treated as a library call.
BUILTIN_RECEIVERS = frozenset(dir(builtins)) - {"super"}


def receiver_root(callee_text: str) -> str | None:
    """The leading identifier of the receiver; None for literal receivers such as ``", ".join`` or ``[1].pop``."""
    match = _RECEIVER_ROOT.match(callee_text)
    if match is None or callee_text[match.end():match.end() + 1] in {'"', "'"}:
        return None
    return match.group(1)


def callee_name(callee_text: str) -> str | None:
    """The part after the last dot, when it is an identifier."""
    name = callee_text.rsplit(".", 1)[-1]
    return name if name.isidentifier() else None


def confidence(tool_precision: float, *, import_coherent: bool) -> float:
    """type_match is 0: a call whose type matched would already be resolved."""
    score = _TOOL_WEIGHT * tool_precision + _TYPE_WEIGHT * 0 + _IMPORT_WEIGHT * int(import_coherent)
    return min(CONFIDENCE_CAP, round(score, 2))


def evidence(match_kind: str, *, same_module: bool, imported: bool) -> list[str]:
    context = [*(["same_module_scope"] if same_module else []), *(["import_path"] if imported else [])]
    if match_kind == "name":
        return ["name_match", *context, "unresolved_type"]
    return [match_kind, *context]
