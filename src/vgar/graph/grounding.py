from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from vgar.contracts.schema import validate_graph_document


_LOCATION = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[\w./\\-]+\.py)"
    r"(?P<selector>(?:::[A-Za-z_]\w*)*)"
    r"(?:\[[^\]\r\n]*\])?"
    r"(?::(?P<line>-?\d+))?"
    r"(?![\w./\\-])"
)
_TRACEBACK = re.compile(
    r'File [\"\'](?P<path>[^\"\']+\.py)[\"\'], line (?P<line>-?\d+)'
    r'(?:,\s+in\s+[A-Za-z_]\w*)?'
)
_QUOTED_LOCATION = re.compile(
    r'[\"\'](?P<path>[^\"\'\r\n]+\.py)[\"\']'
    r'(?P<selector>(?:::[A-Za-z_]\w*)*)(?:\[[^\]\r\n]*\])?'
    r'(?::(?P<line>-?\d+))?'
)
_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}
_ROUTE = re.compile(
    r'(?<![\w/:])(?:(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE)[ \t]+)?'
    r'(?P<route>/[A-Za-z0-9_{}<>:./-]*)(?![\w/])'
)
_SYMBOL = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\b")
_SYMBOL_TYPES = {"Class", "Function", "Method", "Test"}


@dataclass(frozen=True)
class AnchorEvidence:
    kind: str
    matched_text: str
    source: str


@dataclass
class TaskAnchor:
    node_id: str
    path: str
    symbol: str
    score: float
    evidence: list[AnchorEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class AmbiguousMatch:
    matched_text: str
    candidate_ids: list[str]


@dataclass
class AnchorResult:
    graph_version: str
    anchors: list[TaskAnchor]
    ambiguous_matches: list[AmbiguousMatch]
    unmatched_locations: list[str]


class TaskAnchorFinder:
    """M1 grounding over one validated snapshot; no source edits or model calls."""

    def __init__(self, document: dict[str, Any]) -> None:
        validate_graph_document(document)
        self.graph_version = document["graph_version"]
        self.nodes = sorted(
            (
                node for node in document["nodes"]
                if node["type"] in _SYMBOL_TYPES | {"File"} and node["path"]
            ),
            key=lambda node: node["id"],
        )
        self.files = {node["path"]: node for node in self.nodes if node["type"] == "File"}
        self.routes: dict[str, list[tuple[dict[str, Any], frozenset[str]]]] = {}
        for node in self.nodes:
            if node["type"] not in {"Function", "Method"}:
                continue
            for decorator in node["properties"].get("decorators", []):
                route = _static_route(decorator)
                if route is not None:
                    path, methods = route
                    self.routes.setdefault(path, []).append((node, methods))

    def find_task_anchors(
        self, issue_text: str, failing_tests: list[str] | None = None,
    ) -> AnchorResult:
        if not isinstance(issue_text, str):
            raise TypeError("issue_text must be a string")
        if failing_tests is not None and (
            not isinstance(failing_tests, list)
            or any(not isinstance(text, str) for text in failing_tests)
        ):
            raise TypeError("failing_tests must be a list of strings")
        anchors: dict[str, TaskAnchor] = {}
        ambiguous: dict[tuple[str, tuple[str, ...]], AmbiguousMatch] = {}
        unmatched: set[str] = set()

        def add(matches: list[dict[str, Any]], evidence: AnchorEvidence, score: float) -> None:
            ids = sorted({node["id"] for node in matches})
            if len(ids) > 1:
                ambiguous[(evidence.matched_text, tuple(ids))] = AmbiguousMatch(evidence.matched_text, ids)
                score = min(score, 0.5)
            for node in matches:
                anchor = anchors.setdefault(node["id"], TaskAnchor(
                    node["id"], node["path"], node["qualified_name"], score,
                ))
                anchor.score = max(anchor.score, score)
                if evidence not in anchor.evidence:
                    anchor.evidence.append(evidence)

        texts = [("issue", issue_text)] + [("failing_test", text) for text in sorted(set(failing_tests or []))]
        for source, text in texts:
            consumed: list[tuple[int, int]] = []
            # Tracebacks carry their line number after a comma, rather than a colon.
            for pattern in (_TRACEBACK, _QUOTED_LOCATION, _LOCATION):
                for match in pattern.finditer(text):
                    if any(start <= match.start() < end for start, end in consumed):
                        continue
                    consumed.append(match.span())
                    path = match.group("path").replace("\\", "/")
                    paths = self._match_paths(path)
                    selector = match.groupdict().get("selector") or ""
                    line = int(match.group("line")) if match.group("line") else None
                    matches = []
                    for matched_path in paths:
                        candidates = [node for node in self.nodes if node["path"] == matched_path]
                        if selector:
                            suffix = selector.replace("::", ".")
                            candidates = [
                                node for node in candidates if node["type"] == "Test"
                                and node["qualified_name"].endswith(suffix)
                                and (line is None or _contains_line(node["range"], line))
                            ]
                        elif line is not None:
                            candidates = [
                                node for node in candidates
                                if _contains_line(node["range"], line)
                            ]
                            symbols = [node for node in candidates if node["type"] in _SYMBOL_TYPES]
                            if symbols:
                                size = min(node["range"]["end_byte"] - node["range"]["start_byte"] for node in symbols)
                                candidates = [node for node in symbols if node["range"]["end_byte"] - node["range"]["start_byte"] == size]
                            else:
                                candidates = [node for node in candidates if node["type"] == "File"]
                        else:
                            candidates = [self.files[matched_path]]
                        matches.extend(candidates)
                    kind = "pytest_selector" if selector else ("path_line" if line is not None else "path")
                    if matches:
                        add(matches, AnchorEvidence(kind, match.group(), source), 1.0 if selector else (0.95 if line is not None else 0.7))
                    else:
                        unmatched.add(match.group())

            for match in _ROUTE.finditer(text):
                if any(start <= match.start() < end for start, end in consumed):
                    continue
                method, route = match.group("method"), match.group("route")
                matches = [
                    node for node, methods in self.routes.get(route, [])
                    if method is None or method in methods
                ]
                if matches:
                    consumed.append(match.span())
                    add(matches, AnchorEvidence("route", match.group(), source), 0.9 if method else 0.85)
                else:
                    consumed.append(match.span())
                    unmatched.add(match.group())

            for match in _SYMBOL.finditer(text):
                if any(start <= match.start() < end for start, end in consumed):
                    continue
                token = match.group()
                matches = [
                    node for node in self.nodes if node["type"] in _SYMBOL_TYPES
                    and (node["qualified_name"] == token if "." in token else node["name"] == token)
                ]
                if matches:
                    add(matches, AnchorEvidence("symbol", token, source), 0.8 if "." in token else 0.6)

        return AnchorResult(
            self.graph_version,
            sorted(anchors.values(), key=lambda item: (-item.score, item.path, item.symbol, item.node_id)),
            [ambiguous[key] for key in sorted(ambiguous)],
            sorted(unmatched),
        )

    def _match_paths(self, path: str) -> list[str]:
        if ".." in path.split("/") or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
            return []
        normalized = path.removeprefix("./")
        if normalized in self.files:
            return [normalized]
        return sorted(candidate for candidate in self.files if candidate.endswith("/" + normalized))


def _contains_line(source_range: dict[str, int], line: int) -> bool:
    """A zero-column exclusive end does not include the following line."""
    end = source_range["end_line"] - (source_range["end_col"] == 0)
    return source_range["start_line"] <= line <= end


def _static_route(decorator: str) -> tuple[str, frozenset[str]] | None:
    """Read literal decorator metadata only; never import/execute app code."""
    if not isinstance(decorator, str):
        return None
    try:
        expression = ast.parse(decorator.lstrip("@").strip(), mode="eval").body
    except (SyntaxError, ValueError):
        return None
    if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Attribute):
        return None
    verb = expression.func.attr
    if verb not in {"route", "api_route"} and verb.upper() not in _HTTP_METHODS:
        return None
    path = expression.args[0] if expression.args else next(
        (item.value for item in expression.keywords if item.arg in {"path", "rule"}), None,
    )
    if not isinstance(path, ast.Constant) or not isinstance(path.value, str) or not path.value.startswith("/"):
        return None
    if verb.upper() in _HTTP_METHODS:
        return path.value, frozenset({verb.upper()})
    method_arg = next((item.value for item in expression.keywords if item.arg == "methods"), None)
    if method_arg is None:
        return path.value, frozenset({"GET"})
    if not isinstance(method_arg, (ast.List, ast.Tuple, ast.Set)) or not method_arg.elts:
        return None
    if any(not isinstance(item, ast.Constant) or not isinstance(item.value, str) for item in method_arg.elts):
        return None
    methods = frozenset(item.value.upper() for item in method_arg.elts)
    return (path.value, methods) if methods <= _HTTP_METHODS else None