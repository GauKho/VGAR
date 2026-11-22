"""Unified diff of the working tree against a graph's stored source, in the form patch.parse_unified_diff reads.

The diff is logical like patch._bind: line endings are not compared (a CRLF/LF change cannot be expressed), a
missing final newline is (spec 2026-11-22 §4.3).
"""
from __future__ import annotations

import difflib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_NO_EOL = "\0"
# str.splitlines also breaks on these; patch.parse_unified_diff would then reject the diff it is given.
_OTHER_SEPARATORS = ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")


@dataclass(frozen=True)
class WorktreeDiff:
    """What the working tree changed against the stored source."""

    diff: str                     # git-style unified diff; "" when nothing can be checked
    files: tuple[str, ...]        # paths in the diff, sorted
    not_checked: tuple[str, ...]  # "new file: p", "deleted file: p", "line endings only: p", "not UTF-8: p",
                                  # "unsupported line separator: p"
    changed_lines: int            # '+'/'-' lines in the hunk bodies


def _tokens(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    tokens = [line.rstrip("\r\n") for line in lines]
    if lines and not lines[-1].endswith(("\n", "\r")):
        tokens[-1] += _NO_EOL         # a missing final newline is a real change; line endings are not
    return tokens


def _name(prefix: str, path: str) -> str:
    name = prefix + path
    return json.dumps(name, ensure_ascii=False) if any(char.isspace() for char in path) else name


def worktree_diff(sources: Mapping[str, bytes], root: Path) -> WorktreeDiff:
    """Diff the ``.py`` files the builder sees under ``root`` against ``sources``.

    Args:
        sources: Stored bytes of the graph's files, keyed by repository-relative path.
        root: Working tree of the repository.

    Returns:
        The diff, the files in it, the changes it cannot carry, and its changed-line count.
    """
    from vgar.graph.builder import discover_python_files

    root = Path(root)
    current = {path.relative_to(root).as_posix(): path.read_bytes() for path in discover_python_files(root)}
    lines: list[str] = []
    files: list[str] = []
    not_checked: list[str] = []
    changed = 0
    for path in sorted(set(sources) | set(current)):
        if path not in sources:
            not_checked.append(f"new file: {path}")
            continue
        if path not in current:
            not_checked.append(f"deleted file: {path}")
            continue
        if sources[path] == current[path]:
            continue
        try:
            old_text, new_text = sources[path].decode("utf-8"), current[path].decode("utf-8")
        except UnicodeDecodeError:
            not_checked.append(f"not UTF-8: {path}")
            continue
        if any(separator in text for text in (old_text, new_text) for separator in _OTHER_SEPARATORS):
            not_checked.append(f"unsupported line separator: {path}")
            continue
        old, new = _tokens(old_text), _tokens(new_text)
        if old == new:
            not_checked.append(f"line endings only: {path}")
            continue
        files.append(path)
        lines.append(f"diff --git {_name('a/', path)} {_name('b/', path)}")
        for index, line in enumerate(difflib.unified_diff(old, new, _name("a/", path), _name("b/", path),
                                                          n=3, lineterm="")):
            if index >= 2 and line[:1] in "+-":
                changed += 1
            if line.endswith(_NO_EOL):
                lines.extend([line[:-1], "\\ No newline at end of file"])
            else:
                lines.append(line)
    return WorktreeDiff(diff="\n".join(lines) + "\n" if lines else "", files=tuple(files),
                        not_checked=tuple(sorted(not_checked)), changed_lines=changed)
