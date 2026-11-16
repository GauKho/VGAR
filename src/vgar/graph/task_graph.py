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
# Requirement-family rules agreed by the team on 16/11 (spec 2026-11-17-tv2-gt-1-requirements-design §2-§3).
_EXPECTED_HEADING = re.compile(r"^[ \t#*_>-]*expected(?:[ \t]+(?:behaviou?r|result|output|outcome)s?)?\b[ \t*_:#-]*$",
                               re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)  # issue-template hints
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_MAX_SENTENCE = 300
_STORY = re.compile(r"\bAs an? (?P<actor>[^,.]{1,40}?),? I (?:want|would like|need)\b", re.IGNORECASE)
_VERSION = re.compile(r"\bpython\s*[23](?:\.\d+)+|\b[A-Za-z][\w.-]*\s*(?:==|>=|<=|~=|!=)\s*\d+(?:\.\d+)*", re.IGNORECASE)
_PROHIBITION = re.compile(r"\b(?:must not|should not|shouldn't|mustn't|without breaking|backwards?[- ]compatib\w*)", re.IGNORECASE)
_MODAL = re.compile(r"\b(?:should|must|expected|needs to)\b", re.IGNORECASE)
_DEPENDS = re.compile(r"^(?:this|that|it|which)\b.*\b(?:requires|depends on)\b", re.IGNORECASE)
_CONFLICTS = re.compile(r"\b(?:conflicts with|contradicts)\b", re.IGNORECASE)


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
class RequirementFact:
    text: str
    source: str  # "expected_section", "modal" or "follow_up"


@dataclass(frozen=True)
class ConstraintFact:
    text: str
    kind: str  # "version" or "prohibition"


@dataclass(frozen=True)
class StoryFact:
    text: str
    actor: str


@dataclass(frozen=True)
class TaskFacts:
    frames: tuple[FrameFact, ...]
    errors: tuple[ErrorFact, ...]
    criteria: tuple[CriterionFact, ...]
    bug_signals: tuple[str, ...]
    labels: tuple[str, ...]
    failing_tests: tuple[str, ...]
    requirements: tuple[RequirementFact, ...] = ()
    constraints: tuple[ConstraintFact, ...] = ()
    stories: tuple[StoryFact, ...] = ()
    # (source requirement index, target requirement index, "DEPENDS_ON" or "CONFLICTS_WITH")
    requirement_links: tuple[tuple[int, int, str], ...] = ()


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


def _sentences(text: str) -> list[tuple[str, bool]]:
    """(sentence, under an Expected heading) in order; skips code, traceback and error lines, and very long sentences."""
    found: list[tuple[str, bool]] = []
    expected = started = False
    for line in _COMMENT.sub("", _FENCE.sub("", text)).split("\n"):
        if _EXPECTED_HEADING.match(line):
            expected, started = True, False
            continue
        if not line.strip():
            expected = expected and not started
            continue
        if line.startswith(("    ", "\t")) or _FRAME.search(line) or _ERROR.match(line):
            continue
        if line.lstrip().startswith("#"):
            expected = False
            continue
        started = True
        found.extend((sentence.strip(), expected) for sentence in _SENTENCE_END.split(line.strip())
                     if sentence.strip() and len(sentence.strip()) <= _MAX_SENTENCE)
    return found


def _requirement_facts(text: str) -> tuple[tuple[RequirementFact, ...], tuple[ConstraintFact, ...], tuple[StoryFact, ...],
                                            tuple[tuple[int, int, str], ...]]:
    """One node type per sentence, in the order UserStory, Constraint, Requirement (spec §1-§3)."""
    requirements: list[RequirementFact] = []
    constraints: list[ConstraintFact] = []
    stories: list[StoryFact] = []
    links: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    previous_was_requirement = False
    for sentence, expected in _sentences(text):
        if sentence in seen:
            continue
        seen.add(sentence)
        story = _STORY.search(sentence)
        is_requirement = False
        if story:
            stories.append(StoryFact(sentence, story.group("actor").strip().lower()))
        elif _VERSION.search(sentence) or _PROHIBITION.search(sentence):
            constraints.append(ConstraintFact(sentence, "version" if _VERSION.search(sentence) else "prohibition"))
        elif expected or _MODAL.search(sentence) or (previous_was_requirement and _DEPENDS.search(sentence)):
            source = "expected_section" if expected else "modal" if _MODAL.search(sentence) else "follow_up"
            if requirements and previous_was_requirement:
                kind = "DEPENDS_ON" if _DEPENDS.search(sentence) else "CONFLICTS_WITH" if _CONFLICTS.search(sentence) else None
                if kind:
                    links.append((len(requirements), len(requirements) - 1, kind))
            requirements.append(RequirementFact(sentence, source))
            is_requirement = True
        previous_was_requirement = is_requirement
    return tuple(requirements), tuple(constraints), tuple(stories), tuple(links)


def extract_task_facts(issue_text: str, *, failing_tests: Sequence[str] = (), labels: Sequence[str] = ()) -> TaskFacts:
    text = issue_text.replace("\r\n", "\n")
    frames = tuple(FrameFact(match.group("path"), int(match.group("line")), match.group("function"), order)
                   for order, match in enumerate(_FRAME.finditer(text)))
    errors = _errors(text)
    tests = tuple(sorted({test.strip() for test in failing_tests if test.strip()}))
    normalized = tuple(sorted({label.strip().lower() for label in labels if label.strip()}))
    signals = [name for name, present in (("error_message", errors), ("failing_test", tests),
                                          ("label", "bug" in normalized), ("stack_frame", frames)) if present]
    return TaskFacts(frames, errors, _criteria(text), tuple(signals), normalized, tests, *_requirement_facts(text))
