"""GT-1: pragmatic task-graph facts from issue text and reported failing tests (proposal §6.6, lines 619-630).

Pure rules over text; ``TaskOverlayBuilder`` turns the facts into G_task nodes and edges.
Design: docs/superpowers/specs/2026-11-09-tv2-gt-1-g-task-design.md
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

# At most 18 digits: longer numbers are not real lines, and int() rejects very long ones.
_FRAME = re.compile(r"""File ["'](?P<path>[^"'\r\n]+)["'], line (?P<line>\d{1,18})(?!\d)(?:,\s+in\s+(?P<function>\S+))?""")
_ERROR = re.compile(
    r"^[ \t]*(?P<type>(?:[A-Za-z_]\w*\.)*(?:[A-Z]\w*(?:Error|Exception|Warning)|Exception)):[ \t]*(?P<message>\S.*)$",
    re.MULTILINE,
)
_FENCE = re.compile(r"^```.*?^```[^\n]*$", re.MULTILINE | re.DOTALL)
_CRITERIA_HEADING = re.compile(r"^[ \t#*_>-]*(?:acceptance criteria|acceptance tests?|definition of done)\b[ \t*_:#-]*$", re.IGNORECASE)
_BULLET = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(?:\[(?P<box>[ xX])\][ \t]*)?(?P<text>\S.*)$")


@dataclass(frozen=True)
class FrameFact:
    file: str
    line: int
    function: str | None
    order: int


@dataclass(frozen=True)
class ErrorFact:
    exception_type: str
    message: str
    occurrences: int


@dataclass(frozen=True)
class CriterionFact:
    text: str
    checked: bool | None


@dataclass(frozen=True)
class TaskFacts:
    frames: tuple[FrameFact, ...]
    errors: tuple[ErrorFact, ...]
    criteria: tuple[CriterionFact, ...]
    bug_signals: tuple[str, ...]
    labels: tuple[str, ...]
    failing_tests: tuple[str, ...]


def _errors(text: str) -> tuple[ErrorFact, ...]:
    seen: dict[tuple[str, str], int] = {}
    for match in _ERROR.finditer(text):
        key = (match.group("type"), match.group("message").strip())
        seen[key] = seen.get(key, 0) + 1
    return tuple(ErrorFact(kind, message, count) for (kind, message), count in seen.items())


def _criteria(text: str) -> tuple[CriterionFact, ...]:
    """Bullets directly under an acceptance heading; a line that is neither blank nor a bullet ends the list."""
    found: dict[str, bool | None] = {}
    collecting = False
    for line in _FENCE.sub("", text).split("\n"):
        if _CRITERIA_HEADING.match(line):
            collecting = True
            continue
        if not collecting or not line.strip():
            continue
        bullet = _BULLET.match(line)
        if bullet is None:
            collecting = False
            continue
        box = bullet.group("box")
        found.setdefault(bullet.group("text").strip(), None if box is None else box in "xX")
    return tuple(CriterionFact(item, checked) for item, checked in found.items())


def extract_task_facts(issue_text: str, *, failing_tests: Sequence[str] = (), labels: Sequence[str] = ()) -> TaskFacts:
    text = issue_text.replace("\r\n", "\n")
    frames = tuple(FrameFact(match.group("path"), int(match.group("line")), match.group("function"), order)
                   for order, match in enumerate(_FRAME.finditer(text)))
    errors = _errors(text)
    tests = tuple(sorted({test.strip() for test in failing_tests if test.strip()}))
    normalized = tuple(sorted({label.strip().lower() for label in labels if label.strip()}))
    signals = [name for name, present in (("error_message", errors), ("failing_test", tests),
                                          ("label", "bug" in normalized), ("stack_frame", frames)) if present]
    return TaskFacts(frames, errors, _criteria(text), tuple(signals), normalized, tests)
