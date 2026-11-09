"""IM-1: Ports and public API a patch removes. Spec: docs/superpowers/specs/2026-11-09-tv2-im-1-impact-design.md §5.

Compares the baseline Ports of the patched files with the Ports their patched bytes still expose. A file's Ports
depend only on that file and a patch cannot add, delete or rename files, so the rest of the repository is not rebuilt.
Works from bytes in memory: no disk write, no subprocess, and the repository's code is parsed, never imported or run.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from vgar.contracts.impact import LostPort, PortCheck, RemovedApi, UncheckedPath
from vgar.graph import arch_lift
from vgar.graph.builder import PythonGraphBuilder
from vgar.repair.check_result import CheckAnalysis

logger = logging.getLogger(__name__)

_SIZE_LIMIT = 5 * 1024 * 1024
_UNREADABLE_FILE = ("API_PARSE_ERROR", "API_DYNAMIC_EXPORTS")


def _module_names(nodes: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {n["path"]: n["properties"]["module_name"] for n in nodes if n["type"] == "Module" and n["path"]}


def _key(node: dict[str, Any], modules: Mapping[str, str]) -> tuple[str, str]:
    """(path, name inside the file). The module prefix depends on source_roots, which a graph does not record."""
    return node["path"], node["qualified_name"].removeprefix(modules[node["path"]] + ".")


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _ports_after(document: dict[str, Any], files: Mapping[str, bytes]) -> tuple[Counter, dict[str, str]]:
    """How many Ports each key still has after the patch, and why any file could not be read."""
    if sum(map(len, files.values())) > _SIZE_LIMIT:
        return Counter(), dict.fromkeys(files, "AFTER_TOO_LARGE")
    builder = PythonGraphBuilder(repo_key=document["repo_key"], repository_revision=document["repository_revision"])
    builder.graph_version = document["graph_version"]
    try:
        for path, data in files.items():
            builder.extract_source(path, data, "repo")
    except (ValueError, OSError, RecursionError) as error:
        logger.warning("Could not extract the patched files for the lost-port check: %s", type(error).__name__)
        return Counter(), dict.fromkeys(files, "AFTER_EXTRACT_FAILED")
    broken = {n["path"] for n in builder.nodes if n["type"] == "File" and n["properties"]["parse_status"] != "parsed"}
    broken |= {path for path, data in files.items() if not _is_utf8(data)}  # tree-sitter reads what Python would reject
    exports = {path: arch_lift.read_dunder_all(data) for path, data in files.items() if b"__all__" in data}
    modules = _module_names(builder.nodes)
    kept = Counter(_key(node, modules) for node, _ in arch_lift.select_ports(builder.nodes, builder.edges, exports)
                   if node["path"] not in broken)
    return kept, dict.fromkeys(broken, "AFTER_PARSE_FAILED")


def _readable_changes(analysis: CheckAnalysis | None) -> list[dict[str, Any]]:
    """check_api's changes, without the removals it only inferred because it could not read the patched symbol."""
    if analysis is None:
        return []
    after = [item for item in analysis.details["diagnostics"] if item["side"] == "candidate"]
    files = {item["path"] for item in after if item["reason"] in _UNREADABLE_FILE}
    symbols = {(item["path"], item.get("symbol")) for item in after}
    return [change for change in analysis.details["changes"] if change["reason"] != "API_SYMBOL_REMOVED"
            or (change["path"] not in files and (change["path"], change["symbol"]) not in symbols)]


def check_lost_ports(document: dict[str, Any], after: Mapping[str, bytes], analysis: CheckAnalysis | None) -> PortCheck:
    """Ports of `document` that the patched Python files `after` no longer expose. Unknown is reported, never read as safe."""
    if not after or not any(n["type"] == "Component" for n in document["nodes"]):
        return PortCheck()
    baseline: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in document["nodes"]:
        if node["type"] == "Port" and node["path"] in after:
            baseline[node["path"]].append(node)
    kept, unchecked = _ports_after(document, {path: after[path] for path in baseline})
    modules = _module_names(document["nodes"])
    consumers: dict[str, list[str]] = defaultdict(list)
    for edge in document["edges"]:
        if edge["type"] == "CONSUMES_PORT":
            consumers[edge["target_id"]].append(edge["source_id"])
    changes = _readable_changes(analysis)
    reasons ={(change["path"], change["symbol"]): change["reason"] for change in changes}

    lost: list[dict[str, Any]] = []
    checked: list[str] = []
    for path, ports in baseline.items():
        if path in unchecked:
            continue
        checked.append(path)
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for port in ports:
            if port["properties"]["export"] == "route":  # knowing the routes needs the tree-sitter-graph CLI
                unchecked[path] = "ROUTE_FACTS_UNAVAILABLE"
            else:
                groups[_key(port, modules)].append(port)
        for key, group in groups.items():
            missing = len(group) - kept[key]
            if missing > 0:  # duplicates share a key, so which one went is unknown: take the highest ids
                lost.extend(sorted(group, key=lambda port: port["id"])[-missing:])

    port_keys = {_key(port, modules) for ports in baseline.values() for port in ports}
    tests ={n["path"] for n in document["nodes"] if n["type"] == "File" and n["properties"]["is_test_file"]}
    return PortCheck(
        status="PARTIAL" if unchecked else "COMPLETE",
        checked_paths=sorted(checked),
        lost=[LostPort(path=port["path"], port_id=port["id"], qualified_name=port["qualified_name"],
                       export=port["properties"]["export"], owner_component_id=port["properties"]["owner_component_id"],
                       consumers=sorted(consumers[port["id"]]), api_reason=reasons.get(_key(port, modules))) for port in lost],
        removed_api=[RemovedApi(path=change["path"], symbol=change["symbol"]) for change in changes
                     if change["reason"] == "API_SYMBOL_REMOVED" and (change["path"], change["symbol"]) not in port_keys
                     and change["path"] not in tests],
        unchecked=[UncheckedPath(path=path, reason=reason) for path, reason in sorted(unchecked.items())],
    )
