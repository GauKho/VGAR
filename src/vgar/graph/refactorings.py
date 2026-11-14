"""L4-2: detect refactorings in a commit window (proposal §7.3 step [1]).

Two detectors give the same ``Refactoring`` record:

* ``refactoringminer``: RefactoringMiner's ``-json`` output, either produced live (one JVM for the
  whole window with ``-bc``) or read from a folder of precomputed files. ``-bc <start> <end>``
  walks the commits after ``start`` up to ``end``, merged branches included; only results whose
  commit is in the first-parent window are kept. When the oldest window commit is the root, there is
  no ``start`` before it and the root falls back to ``ast`` (it only adds definitions anyway).
* ``ast``: definitions removed and added in the same commit with an identical body (name and
  positions ignored), the rule measured in ``scripts/graphdiff_bench/evaluate.py``.

The ``ast`` result is always computed, because the confidence term ``algorithm_agreement``
compares the two detectors. A commit without RefactoringMiner output uses the ``ast`` result and
says why in ``fallback_reason``.

Precomputed layout (``VGAR_REFACTORINGMINER_OUTPUT``): ``<end commit>.json`` for a whole window or
``<commit>.json`` for one commit, each optionally with ``<same name>.stderr.txt``; an optional
``metadata.json`` holds ``{"tool_version": ...}``.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vgar.graph.history import CommitHistory

logger = logging.getLogger(__name__)

DEFINITIONS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
Blobs = Mapping[str, tuple[bytes | None, bytes | None]]
# (prefix of the RefactoringMiner type in lower case, family); the first match wins.
FAMILIES = (("rename method", "rename_method"), ("rename function", "rename_method"),
            ("rename class", "rename_class"), ("move class", "move_class"), ("extract and move", "extract_method"),
            ("extract method", "extract_method"), ("extract function", "extract_method"),
            ("move and rename class", "move_class"), ("move and inline", "inline_method"),
            ("move and rename", "move_method"), ("move method", "move_method"), ("move function", "move_method"),
            ("move operation", "move_method"), ("rename parameter", "rename_parameter"),
            ("rename variable", "rename_variable"), ("rename local variable", "rename_variable"),
            ("inline method", "inline_method"), ("inline function", "inline_method"))
RENAMING_FAMILIES = {"rename_method", "rename_class", "move_method", "move_class"}
DECLARATION_TYPES = {"METHOD_DECLARATION", "TYPE_DECLARATION"}
# Declarations RefactoringMiner lists that are not the refactoring's before/after symbol.
NOT_A_SIDE_SYMBOL = ("source method declaration after extraction", "target method declaration before inline")


@dataclass(frozen=True)
class SymbolRef:
    """A definition in one side of a commit; ``name`` is the qualified name inside the module, "" for the module."""

    path: str
    name: str


@dataclass(frozen=True)
class Refactoring:
    detector: Literal["refactoringminer", "ast"]
    type: str
    family: str
    before: tuple[SymbolRef, ...]
    after: tuple[SymbolRef, ...]
    involved: frozenset[SymbolRef]
    renames: Mapping[str, str]
    description: str
    tool_version: str | None


@dataclass(frozen=True)
class CommitRefactorings:
    commit_id: str
    detector: Literal["refactoringminer", "ast"]
    refactorings: tuple[Refactoring, ...]
    ast_refactorings: tuple[Refactoring, ...]
    fallback_reason: str | None
    parse_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RefactoringMinerConfig:
    home: Path | None = None
    java_home: Path | None = None
    output: Path | None = None
    timeout_seconds: int = field(default=3600, compare=False)

    @classmethod
    def from_env(cls) -> RefactoringMinerConfig:
        """Read ``VGAR_REFACTORINGMINER_HOME``, ``VGAR_JAVA_HOME`` and ``VGAR_REFACTORINGMINER_OUTPUT``.

        Raises:
            ValueError: A variable is set to a relative path.
        """
        values: dict[str, Path | None] = {}
        for key, name in (("home", "VGAR_REFACTORINGMINER_HOME"), ("java_home", "VGAR_JAVA_HOME"),
                          ("output", "VGAR_REFACTORINGMINER_OUTPUT")):
            raw = os.environ.get(name, "").strip()
            if raw and not Path(raw).is_absolute():
                raise ValueError(f"{name} must be an absolute path")
            values[key] = Path(raw) if raw else None
        return cls(**values)


def family_of(refactoring_type: str) -> str:
    """Family of a RefactoringMiner type name; ``other`` when no family matches."""
    low = refactoring_type.lower()
    return next((family for key, family in FAMILIES if low.startswith(key)), "other")


def definitions(source: bytes | None) -> dict[str, ast.AST] | None:
    """Qualified name -> first definition with that name; ``None`` when the source does not parse."""
    if source is None:
        return {}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    out: dict[str, ast.AST] = {}

    def walk(body: list[ast.stmt], scope: str) -> None:
        for node in body:
            if isinstance(node, DEFINITIONS):
                out.setdefault(scope + node.name, node)
                if isinstance(node, ast.ClassDef):
                    walk(node.body, scope + node.name + ".")
    walk(tree.body, "")
    return out


def span(node: Any) -> tuple[int, int]:
    """First line (decorators included) and last line of a definition."""
    return min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno


def enclosing(defs: Mapping[str, ast.AST], line: int) -> str:
    """Innermost definition containing ``line``; "" (the module) when none does."""
    best, size = "", 10 ** 9
    for name, node in defs.items():
        start, end = span(node)
        if start <= line <= end and end - start < size:
            best, size = name, end - start
    return best


def _shape(node: ast.AST) -> str:
    clone = copy(node)
    clone.name = "_"  # type: ignore[attr-defined]
    return ast.dump(clone)


def _parent(name: str) -> str:
    return name.rpartition(".")[0]


def _members(defs: Mapping[str, ast.AST] | None, path: str, class_name: str) -> set[SymbolRef]:
    return {SymbolRef(path, name) for name in (defs or {}) if name.startswith(class_name + ".")}


def ast_refactorings(blobs: Blobs) -> tuple[Refactoring, ...]:
    """Exact-body pairs of definitions removed and added in one commit.

    Args:
        blobs: Before/after bytes per changed ``.py`` path of the commit.
    """
    defs = {path: (definitions(old), definitions(new)) for path, (old, new) in blobs.items()}
    removed, added = [], []
    for path, (before, after) in sorted(defs.items()):
        if before is None or after is None:
            continue  # the parse error is reported by the AST diff
        removed += [(path, name, before[name]) for name in before.keys() - after.keys()]
        added += [(path, name, after[name]) for name in after.keys() - before.keys()]
    removed.sort(key=lambda item: (item[0], item[1]))
    added.sort(key=lambda item: (item[0], item[1]))
    pairs, used = [], set()
    for old_path, old_name, old_node in removed:
        for new_path, new_name, new_node in added:
            if (new_path, new_name) in used or type(old_node) is not type(new_node):
                continue
            if _shape(old_node) != _shape(new_node):
                continue
            used.add((new_path, new_name))
            pairs.append((old_path, old_name, new_path, new_name, old_node))
            break
    paired_classes = {(p, n) for p, n, _, _, node in pairs if isinstance(node, ast.ClassDef)}
    result = []
    for old_path, old_name, new_path, new_name, node in pairs:
        if _parent(old_name) and (old_path, _parent(old_name)) in paired_classes:
            continue  # member of a renamed or moved class
        same_place = old_path == new_path and _parent(old_name) == _parent(new_name)
        is_class = isinstance(node, ast.ClassDef)
        family = ("rename_class" if same_place else "move_class") if is_class else \
            ("rename_method" if same_place else "move_method")
        before, after = SymbolRef(old_path, old_name), SymbolRef(new_path, new_name)
        involved = {before, after}
        if is_class:
            involved |= _members(defs[old_path][0], old_path, old_name) | _members(defs[new_path][1], new_path, new_name)
        old_short, new_short = old_name.split(".")[-1], new_name.split(".")[-1]
        result.append(Refactoring("ast", family, family, (before,), (after,), frozenset(involved),
                                  {new_short: old_short} if old_short != new_short else {},
                                  f"{family} {old_path}::{old_name} -> {new_path}::{new_name}", None))
    return tuple(result)


def _map_location(location: Mapping[str, Any], side: int, blobs: Blobs,
                  defs: dict[str, tuple[dict[str, ast.AST] | None, dict[str, ast.AST] | None]]) -> SymbolRef | None:
    path = str(location.get("filePath", "")).replace("\\", "/")
    if path not in blobs:
        return None  # outside the files this commit changes
    side_defs = defs[path][side]
    if side_defs is None:
        return None
    line = int(location.get("startLine", 0))
    name = next((n for n, node in side_defs.items() if span(node)[0] <= line <= node.lineno), None)  # type: ignore[attr-defined]
    return SymbolRef(path, name if name is not None else enclosing(side_defs, line))


def _rm_refactoring(item: Mapping[str, Any], blobs: Blobs, tool_version: str | None) -> Refactoring:
    defs = {path: (definitions(old), definitions(new)) for path, (old, new) in blobs.items()}
    family = family_of(str(item.get("type", "")))
    sides: list[list[SymbolRef]] = [[], []]
    involved: set[SymbolRef] = set()
    for side, key in ((0, "leftSideLocations"), (1, "rightSideLocations")):
        for location in item.get(key, []) or []:
            symbol = _map_location(location, side, blobs, defs)
            if symbol is None:
                continue
            involved.add(symbol)
            description = str(location.get("description", "")).lower()
            if (location.get("codeElementType") in DECLARATION_TYPES and symbol.name and symbol not in sides[side]
                    and not description.startswith(NOT_A_SIDE_SYMBOL)):
                sides[side].append(symbol)
    if family in ("rename_class", "move_class"):
        for side, symbols in enumerate(sides):
            for symbol in symbols:
                involved |= _members(defs[symbol.path][side], symbol.path, symbol.name)
    renames: dict[str, str] = {}
    if family in RENAMING_FAMILIES and sides[0] and sides[1]:
        old_short, new_short = sides[0][0].name.split(".")[-1], sides[1][0].name.split(".")[-1]
        if old_short != new_short:
            renames[new_short] = old_short
    return Refactoring("refactoringminer", str(item.get("type", "")), family, tuple(sides[0]), tuple(sides[1]),
                       frozenset(involved), renames, str(item.get("description", item.get("type", ""))), tool_version)


def subjects(refactoring: Refactoring) -> frozenset[SymbolRef]:
    """Symbols a refactoring fully explains (rule R, first clause).

    Rename and move: the before and after declarations and, for classes, their members. Extract: the
    extracted definition. Inline: the inlined definition. Every other family (and the source method of
    an extract, the target of an inline) is involved but not explained: its edit stays a code change.
    """
    family = refactoring.family
    if family in RENAMING_FAMILIES:
        declared = set(refactoring.before) | set(refactoring.after)
        members = {symbol for symbol in refactoring.involved
                   if any(symbol.path == d.path and symbol.name.startswith(d.name + ".") for d in declared)}
        return frozenset(declared | members)
    if family == "extract_method":
        return frozenset(refactoring.after)
    if family == "inline_method":
        return frozenset(refactoring.before)
    return frozenset()


def parse_refactoringminer_json(data: Mapping[str, Any], blobs_by_commit: Mapping[str, Blobs],
                                tool_version: str | None) -> dict[str, tuple[Refactoring, ...]]:
    """Refactorings per commit for the commits present in ``blobs_by_commit``; others are ignored.

    Args:
        data: Parsed ``-json`` output of RefactoringMiner.
        blobs_by_commit: Before/after bytes per changed ``.py`` path, per window commit.
        tool_version: RefactoringMiner version recorded on each result.
    """
    result: dict[str, tuple[Refactoring, ...]] = {}
    for commit in data.get("commits", []) or []:
        commit_id = str(commit.get("sha1", ""))
        if commit_id not in blobs_by_commit:
            continue
        result[commit_id] = tuple(_rm_refactoring(item, blobs_by_commit[commit_id], tool_version)
                                  for item in commit.get("refactorings", []) or [])
    return result


def _jar_version(home: Path) -> str | None:
    for jar in sorted((home / "lib").glob("RefactoringMiner-*.jar")):
        match = re.fullmatch(r"RefactoringMiner-(.+)\.jar", jar.name)
        if match:
            return match.group(1)
    return None


def _precomputed(config: RefactoringMinerConfig, history: CommitHistory) -> tuple[list[dict], str, str | None]:
    assert config.output is not None
    datasets, stderr = [], []
    for name in [history.revision] + [c.commit_id for c in history.commits if c.commit_id != history.revision]:
        path = config.output / f"{name}.json"
        if path.is_file():
            datasets.append(json.loads(path.read_text(encoding="utf-8")))
            log = path.with_suffix(".stderr.txt")
            if log.is_file():
                stderr.append(log.read_text(encoding="utf-8", errors="replace"))
    metadata = config.output / "metadata.json"
    version = json.loads(metadata.read_text(encoding="utf-8")).get("tool_version") if metadata.is_file() else None
    return datasets, "\n".join(stderr), version


def _live(repo_root: Path, config: RefactoringMinerConfig, history: CommitHistory) -> tuple[list[dict], str, str | None]:
    assert config.home is not None
    oldest = history.commits[-1]
    start = oldest.parent_ids[0] if oldest.parent_ids else oldest.commit_id
    java = str(config.java_home / "bin" / ("java.exe" if os.name == "nt" else "java")) if config.java_home else "java"
    with tempfile.TemporaryDirectory(prefix="vgar-rm-") as folder:
        target = Path(folder) / "window.json"
        # RefactoringMiner.bat is not used: its class path is longer than cmd.exe accepts.
        command = [java, "-classpath", str(config.home / "lib" / "*"), "org.refactoringminer.RefactoringMiner",
                   "-bc", str(repo_root), start, history.commits[0].commit_id, "-json", str(target)]
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=config.timeout_seconds, check=False)
        if process.returncode != 0 or not target.is_file():
            raise RuntimeError(f"rc={process.returncode}: {(process.stderr or '')[-200:].strip()}")
        return [json.loads(target.read_text(encoding="utf-8"))], process.stderr or "", _jar_version(config.home)


def detect_refactorings(repo_root: Path, history: CommitHistory, blobs_by_commit: Mapping[str, Blobs],
                        config: RefactoringMinerConfig) -> dict[str, CommitRefactorings]:
    """Step [1] for every commit of the window, with the ``ast`` fallback.

    Args:
        repo_root: Local Git repository (RefactoringMiner live mode reads it).
        history: First-parent window from ``read_commit_history``.
        blobs_by_commit: ``read_python_blobs`` result per window commit.
        config: RefactoringMiner settings; an empty config means ``ast`` only.
    """
    ast_results = {c.commit_id: ast_refactorings(blobs_by_commit.get(c.commit_id, {})) for c in history.commits}
    rm: dict[str, tuple[Refactoring, ...]] = {}
    stderr, reason = "", None
    try:
        if config.output is not None:
            datasets, stderr, version = _precomputed(config, history)
        elif config.home is not None:
            datasets, stderr, version = _live(Path(repo_root), config, history)
        else:
            datasets, version, reason = [], None, "not configured"
        for data in datasets:
            rm.update(parse_refactoringminer_json(data, blobs_by_commit, version))
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        logger.warning("RefactoringMiner unavailable: %s", error)
        reason = f"process failed: {type(error).__name__}: {error}"
    result = {}
    for commit in history.commits:
        cid = commit.commit_id
        warnings = tuple(line.strip() for line in stderr.splitlines() if cid in line or cid[:7] in line.split())
        if cid in rm:
            result[cid] = CommitRefactorings(cid, "refactoringminer", rm[cid], ast_results[cid], None, warnings)
        else:
            result[cid] = CommitRefactorings(cid, "ast", ast_results[cid], ast_results[cid],
                                             reason or "no output for commit", warnings)
    return result
