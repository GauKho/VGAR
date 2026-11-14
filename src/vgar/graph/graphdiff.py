"""L4-5/L4-6 GraphDiff: commit history to graph edits with confidence and provenance (proposal §7.2–7.4).

Steps of §7.3 used here: [1] refactorings (``refactorings.py``), [3] AST diff (``ast_diff.py``),
[4] AST edits to graph edits on ``PythonGraphBuilder`` node ids, [5] confidence. Step [2]
(tangled changes) is not implemented: ``is_tangled_risk`` and ``tangle_risk`` are ``None`` and
its weight is 0.

``edit_type`` names other than ``UPDATE_METHOD_BODY`` are the team's choice (the proposal gives
only that one). No edit is dropped: refactoring, docstring and test-file edits stay with
``validated = False``.
"""
from __future__ import annotations

import ast
import difflib
import logging
import re
import sys
import textwrap
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vgar.graph.ast_diff import (
    PythonFileDiff,
    SymbolEdit,
    _global_names,
    diff_python_commit,
    read_python_blobs,
)
from vgar.graph.builder import PythonGraphBuilder, module_name_for
from vgar.graph.history import CommitChange, read_commit_history
from vgar.graph.refactorings import (
    CommitRefactorings,
    Refactoring,
    RefactoringMinerConfig,
    SymbolRef,
    detect_refactorings,
    span,
    subjects,
)

logger = logging.getLogger(__name__)

Blobs = Mapping[str, tuple[bytes | None, bytes | None]]
SNAPSHOT_TYPES = {"Function", "Method", "Class", "Test", "GlobalVariable", "Module"}
KIND_TYPES = {"class": "Class", "function": "Function", "method": "Method", "test": "Test",
              "globalvariable": "GlobalVariable", "module": "Module"}
RENAME_FAMILIES = {"rename_method", "rename_class"}
MOVE_FAMILIES = {"move_method", "move_class"}


@dataclass(frozen=True)
class SnapshotIndex:
    """What GraphDiff needs from the snapshot graph."""

    repo_key: str
    revision: str
    source_roots: tuple[str, ...]
    repository_name: str
    by_symbol: Mapping[tuple[str, str], tuple[str, str]]
    node_ids: frozenset[str]
    tests_of: Mapping[str, frozenset[str]]
    test_imports: Mapping[str, frozenset[str]]

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, source_roots: tuple[str, ...] = ("src",),
                      repository_name: str) -> SnapshotIndex:
        """Index a graph document.

        Args:
            document: Graph built by ``PythonGraphBuilder``.
            source_roots: Source roots the graph was built with.
            repository_name: Folder name of the repository root (module name of a root ``__init__.py``).
        """
        nodes = {node["id"]: node for node in document["nodes"]}
        by_symbol: dict[tuple[str, str], tuple[str, str]] = {}
        for node in document["nodes"]:
            if node["type"] in SNAPSHOT_TYPES and node.get("path"):
                by_symbol.setdefault((node["path"], node["qualified_name"]), (node["id"], node["type"]))
        tests_of: dict[str, set[str]] = {}
        test_imports: dict[str, set[str]] = {}
        for edge in document["edges"]:
            source, target = nodes.get(edge["source_id"]), nodes.get(edge["target_id"])
            if source is None or target is None or not source.get("path"):
                continue
            if edge["type"] == "TESTS":
                tests_of.setdefault(target["id"], set()).add(source["path"])
            elif edge["type"] == "IMPORTS" and PythonGraphBuilder._is_test_path(source["path"]):
                test_imports.setdefault(target["qualified_name"], set()).add(source["path"])
        return cls(str(document["repo_key"]), str(document["repository_revision"]), tuple(source_roots),
                   repository_name, by_symbol, frozenset(nodes),
                   {key: frozenset(value) for key, value in tests_of.items()},
                   {key: frozenset(value) for key, value in test_imports.items()})


@dataclass
class GraphEdit:
    """One changed entity in one commit (proposal §7.2 fields plus provenance)."""

    commit_id: str
    path: str
    edit_type: str
    entity: str
    node_id: str
    node_type: str
    in_test_file: bool
    node_in_snapshot: bool
    before: tuple[int, int] | None
    after: tuple[int, int] | None
    is_refactoring: bool
    refactoring: dict[str, Any] | None
    symbol: str = field(repr=False, default="")
    is_tangled_risk: None = None
    confidence: float | None = None
    confidence_terms: dict[str, float | None] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    validated: bool = False
    high_confidence: bool = False

    def to_json(self) -> dict[str, Any]:
        """JSON-ready record without the internal ``symbol`` field."""
        data = asdict(self)
        data.pop("symbol")
        return data


@dataclass(frozen=True)
class _Resolved:
    entity: str
    node_id: str
    node_type: str
    in_snapshot: bool


def _resolve(index: SnapshotIndex, path: str, symbol: str, kind: str) -> _Resolved:
    """Map an ``ast`` symbol (qualified inside its module, "" for the module) to the builder's node."""
    module = module_name_for(path, index.source_roots, index.repository_name)
    entity = f"{module}.{symbol}" if symbol else module
    if not symbol:
        id_kind = "module"
    elif kind == "class":
        id_kind = "class"
    elif kind == "global":
        id_kind = "globalvariable"
    elif symbol.split(".")[-1].startswith("test_") and PythonGraphBuilder._is_test_path(path):
        id_kind = "test"
    else:
        id_kind = "method" if "." in symbol else "function"
    found = index.by_symbol.get((path, entity))
    if found is not None:
        return _Resolved(entity, found[0], found[1], True)
    node_id = f"vgar:{index.repo_key}:python:{id_kind}:{path}:{entity}"
    return _Resolved(entity, node_id, KIND_TYPES[id_kind], node_id in index.node_ids)


def _segment(source: bytes | None, lines: tuple[int, int] | None) -> str | None:
    if source is None or lines is None:
        return None
    text = source.decode("utf-8", errors="replace").splitlines()
    return textwrap.dedent("\n".join(text[lines[0] - 1:lines[1]]))


def rename_tokens(source: str, renames: Mapping[str, str]) -> str:
    """Replace each new short name by its old one (word boundaries)."""
    for new, old in renames.items():
        source = re.sub(rf"\b{re.escape(new)}\b", old, source)
    return source


def _same_ast(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    try:
        return ast.dump(ast.parse(left)) == ast.dump(ast.parse(right))
    except (SyntaxError, ValueError):
        return False


def _module_rest(source: bytes | None, drop_names: set[str]) -> list[str] | None:
    """Module statements other than definitions and plain-name assignments, renamed imports dropped."""
    try:
        tree = ast.parse(source or b"")
    except (SyntaxError, ValueError):
        return None
    out = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or _global_names(node):
            continue
        if isinstance(node, ast.ImportFrom):
            node.names = [alias for alias in node.names if alias.name not in drop_names]
            if not node.names:
                continue
        out.append(ast.dump(node))
    return out


def _first(spans: tuple[Any, ...]) -> tuple[int, int] | None:
    return (spans[0].start_line, spans[0].end_line) if spans else None


def _describe(refactoring: Refactoring, counterpart: str | None = None) -> dict[str, Any]:
    return {"type": refactoring.type, "family": refactoring.family, "description": refactoring.description,
            "detector": refactoring.detector, "counterpart": counterpart}


def type_commit_edits(commit: CommitChange, files: tuple[PythonFileDiff, ...], refs: CommitRefactorings,
                      blobs: Blobs, index: SnapshotIndex) -> list[GraphEdit]:
    """Turn one commit's AST edits into graph edits (confidence terms other than coherence left empty).

    Args:
        commit: L4-1 commit record.
        files: ``diff_python_commit`` result for the commit.
        refs: Step [1] result for the commit.
        blobs: ``read_python_blobs`` result for the commit.
        index: Snapshot graph index.
    """
    refactorings = refs.refactorings
    renames: dict[str, str] = {}
    for refactoring in refactorings:
        renames.update(refactoring.renames)
    evidence = ["ast"]
    if refs.detector == "refactoringminer":
        version = next((r.tool_version for r in refactorings if r.tool_version), None)
        evidence.append(f"refactoringminer {version or 'unknown version'}")
    else:
        evidence.append(f"refactoringminer unavailable: {refs.fallback_reason}")
    if refs.parse_warnings:
        evidence.append("refactoringminer_parse_warning")
    evidence += [f"parse error: {(f.after or f.before).path}" for f in files if f.parse_error]  # type: ignore[union-attr]

    entries: list[tuple[str, SymbolEdit]] = [((f.after or f.before).path, e)  # type: ignore[union-attr]
                                             for f in files if not f.parse_error for e in f.ast_diff.edits]
    removed_spans = {(path, e.symbol): e for path, e in entries if e.change == "REMOVED"}
    absorbed: set[tuple[str, str]] = set()
    paired: dict[tuple[str, str], tuple[Refactoring, SymbolRef]] = {}
    for path, e in entries:
        if e.change != "ADDED":
            continue
        for refactoring in refactorings:
            if (refactoring.family in RENAME_FAMILIES | MOVE_FAMILIES and SymbolRef(path, e.symbol) in refactoring.after
                    and refactoring.before):
                counterpart = refactoring.before[0]
                paired[(path, e.symbol)] = (refactoring, counterpart)
                absorbed.add((counterpart.path, counterpart.name))
                break

    def involved(symbol: SymbolRef) -> Refactoring | None:
        """The refactoring that fully explains ``symbol`` (it is that refactoring's subject)."""
        return next((r for r in refactorings if symbol in subjects(r)), None)

    def touched_by(symbol: SymbolRef) -> bool:
        return any(symbol in r.involved for r in refactorings)

    edits: list[GraphEdit] = []
    for path, e in entries:
        key = (path, e.symbol)
        if e.change == "REMOVED" and key in absorbed:
            continue
        kind = (e.after or e.before)[0].kind
        resolved = _resolve(index, path, e.symbol, kind)
        before, after = _first(e.before), _first(e.after)
        old, new = blobs.get(path, (None, None))
        symbol = SymbolRef(path, e.symbol)
        explaining: Refactoring | None = None
        description: dict[str, Any] | None = None
        touched = False
        if key in paired:
            explaining, counterpart = paired[key]
            family = explaining.family
            edit_type = "RENAME_SYMBOL" if family in RENAME_FAMILIES else "MOVE_SYMBOL"
            source = removed_spans.get((counterpart.path, counterpart.name))
            before = _first(source.before) if source else None
            counter = _resolve(index, counterpart.path, counterpart.name, kind).entity
            description = _describe(explaining, counter)
        elif kind == "global":
            edit_type = {"ADDED": "ADD_GLOBAL", "REMOVED": "REMOVE_GLOBAL", "MODIFIED": "UPDATE_GLOBAL"}[e.change]
        elif e.change == "ADDED":
            extract = next((r for r in refactorings if r.family == "extract_method" and symbol in r.after), None)
            edit_type = "EXTRACT_SYMBOL" if extract else "ADD_SYMBOL"
            explaining = extract
        elif e.change == "REMOVED":
            inline = next((r for r in refactorings if r.family == "inline_method" and symbol in r.before), None)
            edit_type = "INLINE_SYMBOL" if inline else "REMOVE_SYMBOL"
            explaining = inline
        elif "declaration" in e.changed_parts:
            edit_type = "UPDATE_SIGNATURE"
        elif "body" in e.changed_parts:
            edit_type = "UPDATE_CLASS_BODY" if kind == "class" else "UPDATE_METHOD_BODY"
        else:
            edit_type = "UPDATE_DOCSTRING"
        if explaining is None:
            explaining = involved(symbol)
        touched = explaining is None and touched_by(symbol)
        if explaining is None and e.change == "MODIFIED" and renames:
            # Rule R: the change is only the renamed references.
            after_text = _segment(new, after)
            touched = touched or (bool(after_text) and any(re.search(rf"\b{re.escape(n)}\b", after_text or "")
                                                            for n in renames))
            if touched and _same_ast(rename_tokens(after_text or "", renames), _segment(old, before)):
                explaining = next(r for r in refactorings if r.renames)
        if explaining is not None and description is None:
            description = _describe(explaining)
        is_refactoring = explaining is not None
        edits.append(GraphEdit(
            commit.commit_id, path, edit_type, resolved.entity, resolved.node_id, resolved.node_type,
            PythonGraphBuilder._is_test_path(path), resolved.in_snapshot, before, after, is_refactoring, description,
            symbol=e.symbol, evidence=list(evidence),
            confidence_terms={"semantic_coherence": 0.5 if touched and not is_refactoring else 1.0}))

    names = set(renames) | set(renames.values())
    for f in files:
        if f.parse_error or not f.ast_diff.module_statements_changed:
            continue
        path = (f.after or f.before).path  # type: ignore[union-attr]
        old, new = blobs.get(path, (None, None))
        resolved = _resolve(index, path, "", "module")
        explaining = involved(SymbolRef(path, ""))
        if explaining is None and renames:
            left, right = _module_rest(old, names), _module_rest(
                rename_tokens((new or b"").decode("utf-8", errors="replace"), renames).encode("utf-8"), names)
            if left is not None and left == right:
                explaining = next(r for r in refactorings if r.renames)
        edits.append(GraphEdit(
            commit.commit_id, path, "UPDATE_MODULE_STATEMENTS", resolved.entity, resolved.node_id, resolved.node_type,
            PythonGraphBuilder._is_test_path(path), resolved.in_snapshot, None, None, explaining is not None,
            _describe(explaining) if explaining else None, symbol="", evidence=list(evidence),
            confidence_terms={"semantic_coherence": 0.5}))
    return edits


def _entity_lines(source: bytes | None) -> tuple[list[tuple[str, str, tuple[int, int]]], bool]:
    """Every definition (repeated names included) and plain-name global as (name, kind, span); False when unparsable."""
    try:
        tree = ast.parse(source or b"")
    except (SyntaxError, ValueError):
        return [], False
    out: list[tuple[str, str, tuple[int, int]]] = []

    def walk(body: list[ast.stmt], scope: str) -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                out.append((scope + node.name, kind, span(node)))
                if isinstance(node, ast.ClassDef):
                    walk(node.body, scope + node.name + ".")
    walk(tree.body, "")
    for node in tree.body:
        for name in _global_names(node):
            out.append((name, "global", (node.lineno, node.end_lineno or node.lineno)))
    return out, True


def _innermost(entities: list[tuple[str, str, tuple[int, int]]], line: int) -> tuple[str, str]:
    best, kind, size = "", "module", 10 ** 9
    for name, entity_kind, (start, end) in entities:
        if start <= line <= end and end - start < size:
            best, kind, size = name, entity_kind, end - start
    return best, kind


def entity_source(source: bytes | None, symbol: str) -> str:
    """Source text of an entity ("" symbol: the module lines outside every entity); "" when absent.

    Args:
        source: File bytes of one side.
        symbol: ``ast`` qualified name inside the module.
    """
    if source is None:
        return ""
    lines = source.decode("utf-8", errors="replace").splitlines()
    entities, _ = _entity_lines(source)
    if symbol:
        return "\n\n".join(textwrap.dedent("\n".join(lines[start - 1:end]))
                           for name, _, (start, end) in entities if name == symbol)
    inside = {line for _, _, (start, end) in entities for line in range(start, end + 1)}
    return "\n".join(text for number, text in enumerate(lines, 1) if number not in inside).strip("\n")


def raw_diff_entities(commit: CommitChange, blobs: Blobs, index: SnapshotIndex) -> list[dict[str, Any]]:
    """Raw-diff baseline: the innermost entity of every changed text line, the module outside all entities.

    Comments, formatting and docstrings count, because a text diff cannot tell them apart.

    Args:
        commit: L4-1 commit record.
        blobs: ``read_python_blobs`` result for the commit.
        index: Snapshot graph index.
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for path, (old, new) in sorted(blobs.items()):
        left = (old or b"").decode("utf-8", errors="replace").splitlines()
        right = (new or b"").decode("utf-8", errors="replace").splitlines()
        sides = (_entity_lines(old)[0], _entity_lines(new)[0])
        changed: set[tuple[int, int]] = set()  # (side, line)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
            if tag != "equal":
                changed |= {(0, line) for line in range(i1 + 1, i2 + 1)} | {(1, line) for line in range(j1 + 1, j2 + 1)}
        for side, line in sorted(changed):
            name, kind = _innermost(sides[side], line)
            if (path, name) in rows:
                continue
            resolved = _resolve(index, path, name, kind)
            rows[(path, name)] = {"commit_id": commit.commit_id, "path": path, "symbol": name,
                                  "entity": resolved.entity, "node_id": resolved.node_id,
                                  "in_test_file": PythonGraphBuilder._is_test_path(path)}
    return list(rows.values())


def _default_weights() -> dict[str, float]:
    # Team's choice (proposal §7.4 gives no values); w3 = 0 while step [2] is missing.
    return {"algorithm_agreement": 0.3, "semantic_coherence": 0.2, "tangle_risk": 0.0,
            "test_relevance": 0.25, "trace_relevance": 0.25}


@dataclass(frozen=True)
class ConfidenceConfig:
    """Weights of §7.4 and the ``high_confidence`` threshold; tune on the L4-7 development split only."""

    weights: Mapping[str, float] = field(default_factory=_default_weights)
    threshold: float = 0.5


@dataclass(frozen=True)
class GraphDiffResult:
    edits: tuple[GraphEdit, ...]
    raw_baseline: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def _words(text: str) -> set[str]:
    from vgar.evaluation.retrieval.bm25 import tokenize

    return {word for word in tokenize(text) if len(word) >= 3}


def score_edit(edit: GraphEdit, commit: CommitChange, refs: CommitRefactorings, index: SnapshotIndex,
               config: ConfidenceConfig) -> None:
    """Fill ``confidence_terms``, ``confidence``, ``validated`` and ``high_confidence`` (§7.4–7.5).

    Args:
        edit: Edit from ``type_commit_edits`` (``semantic_coherence`` already set).
        commit: Its commit.
        refs: Step [1] result for the commit.
        index: Snapshot graph index.
        config: Weights and threshold.
    """
    terms = edit.confidence_terms
    symbol = SymbolRef(edit.path, edit.symbol)
    if refs.detector == "refactoringminer":
        rm_says = any(symbol in subjects(r) for r in refs.refactorings)
        ast_says = any(symbol in subjects(r) for r in refs.ast_refactorings)
        terms["algorithm_agreement"] = 1.0 if rm_says == ast_says else 0.0
    else:
        terms["algorithm_agreement"] = None
    terms.setdefault("semantic_coherence", 1.0)
    terms["tangle_risk"] = None

    changed_tests = sorted({version.path for change in commit.files for version in (change.before, change.after)
                            if version is not None and PythonGraphBuilder._is_test_path(version.path)})
    module = module_name_for(edit.path, index.source_roots, index.repository_name)
    linked = index.tests_of.get(edit.node_id, frozenset()) | index.test_imports.get(module, frozenset())
    terms["test_relevance"] = 1.0 if linked & set(changed_tests) else (0.5 if changed_tests else 0.0)
    edit.evidence += [f"test touched: {path}" for path in changed_tests]

    subject = _words(commit.subject)
    short = (edit.symbol or module).split(".")[-1]
    exact = subject & ({short.lower()} | _words(short))
    nearby = subject & (_words(module.replace(".", " ")) | _words(edit.path.replace("/", " ").removesuffix(".py")))
    terms["trace_relevance"] = 1.0 if exact else (0.5 if nearby else 0.0)
    edit.evidence += [f"message mentions: {word}" for word in sorted(exact or nearby)]

    available = [(config.weights.get(name, 0.0), value) for name, value in terms.items() if value is not None]
    total = sum(weight for weight, _ in available)
    edit.confidence = sum(weight * value for weight, value in available) / total if total else None
    edit.validated = not edit.is_refactoring and edit.edit_type != "UPDATE_DOCSTRING" and not edit.in_test_file
    edit.high_confidence = edit.validated and edit.confidence is not None and edit.confidence >= config.threshold


def run_graphdiff(repo_root: str | Path, document: Mapping[str, Any], *, max_commits: int,
                  source_roots: tuple[str, ...] = ("src",), rm_config: RefactoringMinerConfig | None = None,
                  config: ConfidenceConfig | None = None, repository_name: str | None = None) -> GraphDiffResult:
    """GraphDiff over the first-parent window that ends at the graph's own revision.

    Args:
        repo_root: Local Git repository with the history.
        document: Snapshot graph built at ``repository_revision`` (a full SHA-1).
        max_commits: Window size.
        source_roots: Source roots the graph was built with.
        rm_config: RefactoringMiner settings; ``None`` reads the ``VGAR_*`` environment.
        config: Weights and threshold.
        repository_name: Module name of a root ``__init__.py``; defaults to the folder name of ``repo_root``.
    """
    root = Path(repo_root)
    config = config or ConfidenceConfig()
    rm_config = rm_config if rm_config is not None else RefactoringMinerConfig.from_env()
    index = SnapshotIndex.from_document(document, source_roots=source_roots,
                                        repository_name=repository_name or root.resolve().name)
    history = read_commit_history(root, revision=index.revision, max_commits=max_commits)
    blobs = {commit.commit_id: read_python_blobs(root, commit) for commit in history.commits}
    refs = detect_refactorings(root, history, blobs, rm_config)
    edits: list[GraphEdit] = []
    raw: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    for commit in history.commits:
        files = diff_python_commit(root, commit)
        parse_errors += [{"commit": commit.commit_id, "path": (f.after or f.before).path,  # type: ignore[union-attr]
                          "side": f.parse_error.side, "message": f.parse_error.message} for f in files if f.parse_error]
        commit_edits = type_commit_edits(commit, files, refs[commit.commit_id], blobs[commit.commit_id], index)
        for edit in commit_edits:
            score_edit(edit, commit, refs[commit.commit_id], index, config)
        edits += commit_edits
        raw += raw_diff_entities(commit, blobs[commit.commit_id], index)
    versions = sorted({r.tool_version for item in refs.values() for r in item.refactorings if r.tool_version})
    summary = {
        "revision": index.revision, "history_label": history.history_label,
        "commit_ids": [commit.commit_id for commit in history.commits],
        "commits_requested": max_commits, "commits_read": len(history.commits),
        "commits_per_detector": dict(Counter(item.detector for item in refs.values())),
        "refactoringminer_fallbacks": dict(Counter(item.fallback_reason for item in refs.values()
                                                   if item.fallback_reason)),
        "refactoringminer_parse_warnings": sum(1 for item in refs.values() if item.parse_warnings),
        "parse_errors": parse_errors,
        "edits_total": len(edits), "edits_validated": sum(edit.validated for edit in edits),
        "edits_high_confidence": sum(edit.high_confidence for edit in edits),
        "raw_baseline_entities": sum(1 for row in raw if not row["in_test_file"]),
        "weights": dict(config.weights), "threshold": config.threshold,
        "refactoringminer_version": ", ".join(versions) or None, "python_version": sys.version,
        "source_roots": list(source_roots),
    }
    logger.info("GraphDiff %s: %d commits, %d edits", index.revision, len(history.commits), len(edits))
    return GraphDiffResult(tuple(edits), tuple(raw), summary)
