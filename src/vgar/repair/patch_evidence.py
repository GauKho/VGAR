"""Guide-style layer 5 functions over the real graph: graph checks, relevant tests and ranking of a patch.

Plain functions that MCP tools call directly (spec §7.3, §7.6, §7.7). They reuse the
existing checks (schema S, structure, API, local import cycles) and IM-1's lost-port
check, never write to the original repository, and report what was not measured as
``NOT_RUN`` instead of guessing.
"""
from __future__ import annotations

import hashlib
import json
import re
import logging
import shutil
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vgar.contracts.error import GraphNotReadyError
from vgar.contracts.schema import GraphValidationError, validate_graph_document
from vgar.graph.builder import PythonGraphBuilder, discover_python_files
from vgar.graph.snapshot_sources import NO_SOURCE_COPY_HINT, materialize_snapshot
from vgar.graph.test_selection import select_related_tests
from vgar.mcp import pytest_runner
from vgar.mcp.schemas import CodedToolError
from vgar.repair.api_check import check_api
from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff
from vgar.repair.source_imports import check_source_import_cycles
from vgar.repair.structural_check import check_structure

logger = logging.getLogger(__name__)

_IGNORED = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache")
_ORDER = ("ERROR", "FAIL", "NOT_RUN", "PASS")


def diff_sha256(diff: str) -> str:
    """Stable identity of a unified diff, used to key evidence of the same patch."""
    return "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()


def _policy(document: dict[str, Any]) -> PatchPolicy:
    paths = tuple(sorted(node["path"] for node in document["nodes"] if node["type"] == "File"))
    return PatchPolicy(paths, ())


def _root(service: Any) -> Path:
    if service.repository_root is None:
        raise GraphNotReadyError("Patch checks require the repository root of the snapshot (VGAR_REPOSITORY_ROOT)")
    return Path(service.repository_root)


def _result(status: str, reasons: list[str], checks: dict[str, Any], graph_version: str, diff: str) -> dict[str, Any]:
    return {"status": status, "checks": checks, "reasons": reasons, "graph_version": graph_version,
            "diff_sha256": diff_sha256(diff)}


_INLINE_DIFF_BYTES = 8192


def resolve_diff(service: Any, graph_version: str, diff: str) -> tuple[str, dict[str, Any]]:
    """The diff a check runs on and its ``checked_diff`` record (spec 2026-11-22 section 4.3).

    Args:
        service: ``SQLiteGraphService`` serving the graph (needs ``repository_root``).
        graph_version: Graph whose stored source the working tree is compared with.
        diff: Unified diff given by the caller; empty means the working tree's changes against the stored source.

    Returns:
        The diff to check ("" when nothing changed) and the record of what is checked.
    """
    if diff:
        files = sorted(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))
        return diff, _checked_diff(diff, "argument", files, [])
    sources = service.snapshot_sources(graph_version)
    if sources is None:
        raise ValueError(f"no diff given and {NO_SOURCE_COPY_HINT}, or pass the diff")
    from vgar.repair.worktree_diff import worktree_diff
    found = worktree_diff(sources, _root(service))
    limits = PatchPolicy((), ())
    if len(found.files) > limits.max_files or found.changed_lines > limits.max_changed_lines:
        raise ValueError(f"the working tree differs from graph {graph_version} in {len(found.files)} files / "
                         f"{found.changed_lines} changed lines (limit {limits.max_files} files, "
                         f"{limits.max_changed_lines} lines): check and rebuild the graph after each fix")
    return found.diff, _checked_diff(found.diff, "worktree", list(found.files), list(found.not_checked))


def _checked_diff(diff: str, source: str, files: list[str], not_checked: list[str]) -> dict[str, Any]:
    return {"source": source, "files": files, "sha256": diff_sha256(diff),
            "diff": diff if len(diff.encode("utf-8")) <= _INLINE_DIFF_BYTES else None, "not_checked": not_checked}


def with_checked_diff(result: dict[str, Any], checked: dict[str, Any]) -> dict[str, Any]:
    """A copy of a check result with ``checked_diff`` and one ``NOT_CHECKED`` reason per change it could not carry.

    Args:
        result: Result of verify_patch or run_patch_tests (possibly cached: never modified).
        checked: Record returned by ``resolve_diff``.
    """
    return {**result, "reasons": [*result["reasons"], *(f"NOT_CHECKED: {entry}" for entry in checked["not_checked"])],
            "checked_diff": checked}


def require_diff(diff: str, capability: str) -> str:
    """``diff`` for a host provider, which needs it explicitly (TV1 contract ``DiffRequest`` is unchanged).

    Args:
        diff: Diff given by the caller.
        capability: Provider capability, for the message.
    """
    if not diff:
        raise ValueError(f"diff is required with the host's {capability} provider")
    return diff


def _impact_report(diff: str, document: dict[str, Any], root: Path, policy: PatchPolicy,
                   sources: dict[str, bytes] | None) -> dict[str, Any]:
    """ImpactReport of ``diff`` on the graph's stored source, or on ``root`` for a graph that stores none."""
    from vgar.graph.impact import analyze_patch_impact
    if sources is None:
        return json.loads(analyze_patch_impact(diff, document, root, patch_policy=policy).canonical_json())
    with tempfile.TemporaryDirectory(prefix="vgar-impact-") as folder:
        baseline = materialize_snapshot(sources, Path(folder) / "snapshot")
        return json.loads(analyze_patch_impact(diff, document, baseline, patch_policy=policy).canonical_json())


def _port_status(port_check: dict[str, Any]) -> str:
    if port_check.get("lost") or port_check.get("removed_api"):
        return "FAIL"
    return "PASS" if port_check.get("status") == "COMPLETE" else "NOT_RUN"


def verify_patch(service: Any, diff: str, *, graph_version: str,
                 source_roots: tuple[str, ...] = ("src",)) -> dict[str, Any]:
    """Check a unified diff against schema S, structure, public API, import cycles and lost Ports.

    Args:
        service: ``SQLiteGraphService`` serving the baseline graph (needs ``repository_root``).
        diff: Unified diff against the snapshot's source.
        graph_version: Baseline graph to compare with.
        source_roots: Builder source roots used for the baseline graph.

    Returns:
        ``status`` (PASS/FAIL/NOT_RUN/ERROR), per-check ``checks``, ``reasons``, ``graph_version``, ``diff_sha256``.
    """
    root = _root(service)
    document = service._document(graph_version)
    policy = _policy(document)
    try:
        parsed = parse_unified_diff(diff, policy)
    except (ValueError, UnicodeError) as error:
        return _result("ERROR", [f"PATCH_REJECTED: {error}"], {}, graph_version, diff)

    sources = service.snapshot_sources(graph_version)
    with tempfile.TemporaryDirectory(prefix="vgar-verify-") as folder:
        copy = Path(folder) / "repo"
        if sources is not None:   # the code the graph was built from, whatever the working tree holds
            materialize_snapshot(sources, copy, worktree=root)
        else:
            shutil.copytree(root, copy, ignore=_IGNORED)
        builder = PythonGraphBuilder(repo_key=document["repo_key"], repository_revision=document["repository_revision"],
                                     source_roots=source_roots)
        builder.trace.path = None
        if builder._calculate_graph_version(copy, discover_python_files(copy)) != graph_version:
            from vgar.graph.impact import source_drift
            drift = source_drift(document, root) if sources is None else None   # stored source: builder options differ
            return _result("ERROR", [f"SOURCE_DIFFERS_FROM_SNAPSHOT: {drift} {NO_SOURCE_COPY_HINT}" if drift
                                     else "BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT"], {}, graph_version, diff)
        before = {path: (copy / path).read_bytes() for path in policy.allowed_paths if (copy / path).is_file()}
        try:
            changed, _ = _bind(parsed, copy)
        except (ValueError, UnicodeError) as error:
            return _result("ERROR", [f"PATCH_DOES_NOT_APPLY: {error}"], {}, graph_version, diff)
        for path, raw in changed.items():
            try:
                compile(raw, path, "exec", dont_inherit=True)
            except (SyntaxError, ValueError):
                return _result("FAIL", ["CANDIDATE_SYNTAX_ERROR"], {"schema": {"status": "NOT_RUN"}}, graph_version, diff)
            (copy / path).write_bytes(raw)
        try:
            candidate = builder.build(copy)
            validate_graph_document(candidate)
        except GraphValidationError as error:
            return _result("FAIL", ["CANDIDATE_SCHEMA_VIOLATION"], {"schema": {"status": "FAIL", "details": str(error)}},
                           graph_version, diff)

    after = {**before, **changed}
    api = check_api({path: before[path] for path in changed}, changed, changed_only=True)
    structure = check_structure(document, candidate, before_sources=before, after_sources=after)
    source_imports = check_source_import_cycles(document, candidate, before, after)

    report = _impact_report(diff, document, root, policy, sources)
    port_check = report.get("port_check", {})
    port_status = _port_status(port_check)

    structural_details = {key: value for key, value in structure.details.items() if key != "source_hashes"}
    checks = {"schema": {"status": "PASS"}, "structural": {**asdict(structure), "details": structural_details},
              "api": asdict(api), "source_imports": asdict(source_imports),
              "port_check": {"status": port_status, "details": port_check},
              "fanout": {"status": "NOT_RUN", "details": {"reason": "fanout increase is not measured in this round"}}}
    states = {api.status, structure.status, source_imports.status}
    if port_status in {"FAIL", "ERROR"}:
        states.add(port_status)
    status = next(value for value in _ORDER if value in states)
    reasons = list(dict.fromkeys((*api.reasons, *structure.reasons, *source_imports.reasons,
                                  *(["PUBLIC_PORT_LOST"] if port_status == "FAIL" else []))))
    logger.info("verify_patch %s -> %s", diff_sha256(diff), status)
    return _result(status, reasons, checks, graph_version, diff)


class _BudgetExceeded(Exception):
    """The whole test run used up its time budget."""


def _run(root: Path, selectors: list[str], timeout_seconds: int, output_cap: int, deadline: float) -> dict[str, str]:
    outcomes = {}
    for selector in selectors:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _BudgetExceeded
        result = pytest_runner.run_selector(root, selector, timeout_seconds=max(1, min(timeout_seconds, int(remaining))),
                                            output_cap=output_cap)
        outcomes[selector] = "PASS" if result["exit_code"] == 0 else "FAIL"
    if time.monotonic() > deadline:
        raise _BudgetExceeded
    return outcomes


def run_patch_tests(service: Any, diff: str, *, graph_version: str, failing_tests: list[str] | None = None,
                    timeout_seconds: int = 300, output_cap: int = 12_000,
                    budget_seconds: float = 900) -> dict[str, Any]:
    """Run the tests related to a patch on a temporary copy, before and after applying it once.

    Args:
        service: ``SQLiteGraphService`` serving the baseline graph (needs ``repository_root``).
        diff: Unified diff against the snapshot's source.
        graph_version: Baseline graph used to choose the tests.
        failing_tests: Selectors that must fail before the patch and pass after it.
        timeout_seconds: Time limit for each pytest run.
        output_cap: Captured output limit for each pytest run.
        budget_seconds: Time budget for all pytest runs of this call; exceeding it gives ERROR.

    Returns:
        ``status`` (PASS/FAIL/NOT_RUN/ERROR), the ``selectors`` run, ``baseline``/``candidate`` outcomes,
        ``previously_failing_fixed``, ``regressions``, ``reasons``, ``diff_sha256`` and ``cleaned``.
    """
    root = _root(service)
    document = service._document(graph_version)
    policy = _policy(document)
    record: dict[str, Any] = {"status": "ERROR", "selectors": [], "baseline": {}, "candidate": {},
                              "previously_failing_fixed": [], "regressions": [], "reasons": [],
                              "diff_sha256": diff_sha256(diff), "cleaned": False,
                              "broader_suite": "NOT_RUN", "coverage": "NOT_RUN"}
    try:
        parsed = parse_unified_diff(diff, policy)
    except (ValueError, UnicodeError) as error:
        return {**record, "reasons": [f"PATCH_REJECTED: {error}"], "cleaned": True}

    sources = service.snapshot_sources(graph_version)
    try:
        report = _impact_report(diff, document, root, policy, sources)
    except (ValueError, UnicodeError) as error:  # hunk does not match, or the repo drifted from the snapshot
        return {**record, "reasons": [f"PATCH_DOES_NOT_APPLY: {error}"], "cleaned": True}
    known = {node["id"] for node in document["nodes"]}
    symbols = [item["node_id"] for item in report.get("changed", []) if item.get("node_id") in known]
    selection = select_related_tests(document, symbols, changed_paths=sorted(parsed.files),
                                     failing_tests=list(failing_tests or []))
    deadline = time.monotonic() + budget_seconds
    folder = Path(tempfile.mkdtemp(prefix="vgar-tests-"))
    try:
        copy = folder / "repo"
        if sources is not None:
            materialize_snapshot(sources, copy, worktree=root)
        else:
            shutil.copytree(root, copy, ignore=_IGNORED)
        selectors = [item for item in selection["tests"] if (copy / item.split("::", 1)[0]).is_file()]
        record["selectors"] = selectors
        if not selectors:
            record.update(status="NOT_RUN", reasons=["NO_RELATED_TESTS"])
            return record
        try:
            changed, _ = _bind(parsed, copy)
        except (ValueError, UnicodeError) as error:
            record["reasons"] = [f"PATCH_DOES_NOT_APPLY: {error}"]
            return record
        baseline = _run(copy, selectors, timeout_seconds, output_cap, deadline)
        record["baseline"] = baseline
        missing = [item for item in failing_tests or [] if baseline.get(item) != "FAIL"]
        if missing:
            record.update(status="NOT_RUN", reasons=["FAILING_TEST_NOT_REPRODUCED"])
            return record
        for path, raw in changed.items():
            (copy / path).write_bytes(raw)
        candidate = _run(copy, selectors, timeout_seconds, output_cap, deadline)
        record["candidate"] = candidate
        fixed = [item for item in selectors if baseline[item] == "FAIL" and candidate[item] == "PASS"]
        regressions = [item for item in selectors if baseline[item] == "PASS" and candidate[item] == "FAIL"]
        still_failing = [item for item in selectors if candidate[item] == "FAIL" and item not in regressions]
        record.update(previously_failing_fixed=fixed, regressions=regressions,
                      status="FAIL" if regressions or still_failing else "PASS",
                      reasons=[*(["REGRESSION"] if regressions else []), *(["STILL_FAILING"] if still_failing else [])])
        return record
    except CodedToolError as error:
        record.update(status="ERROR", reasons=[f"TEST_RUNNER_{error.code}"])
        return record
    except _BudgetExceeded:
        record.update(status="ERROR", reasons=["TEST_BUDGET_EXCEEDED"])
        return record
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        record["cleaned"] = not folder.exists()
        logger.info("run_patch_tests %s -> %s", record["diff_sha256"], record["status"])


RANKING_WEIGHTS_PATH = Path(__file__).resolve().parents[3] / "configs" / "mcp_server" / "ranking_weights.json"
_NOT_MEASURED = ("static_typecheck_passed", "lint_passed", "semantic_invariant_preserved")


def load_ranking_weights(path: Path = RANKING_WEIGHTS_PATH) -> dict[str, float]:
    """The provisional ``score(patch)`` weights (spec H10).

    Args:
        path: JSON file with a ``weights`` object.
    """
    return dict(json.loads(Path(path).read_text(encoding="utf-8"))["weights"])


def _check(verify: dict[str, Any], name: str) -> str:
    fallback = "ERROR" if verify.get("status") == "ERROR" else "NOT_RUN"
    return verify.get("checks", {}).get(name, {}).get("status", fallback)


def evidence_fields(verify: dict[str, Any], tests: dict[str, Any]) -> dict[str, str]:
    """The nine evidence fields of proposal §8.5 from ``verify_patch`` and ``run_patch_tests`` results.

    Args:
        verify: Result of ``verify_patch`` for the patch.
        tests: Result of ``run_patch_tests`` for the patch.
    """
    structural = verify.get("checks", {}).get("structural", {})
    forbidden = structural.get("details", {}).get("subchecks", {}).get("forbidden_imports", {})
    test_status = tests.get("status", "NOT_RUN")
    fixed = ("PASS" if test_status == "PASS" and tests.get("previously_failing_fixed")
             else "FAIL" if test_status == "FAIL" else "ERROR" if test_status == "ERROR" else "NOT_RUN")
    fields = {"tests_passed": test_status, "previously_failing_tests_fixed": fixed,
              "schema_conformance_passed": _check(verify, "schema"),
              "no_new_forbidden_dependency": forbidden.get("status") or _check(verify, "structural"),
              "public_api_compatible": _check(verify, "api"),
              "impact_radius_acceptable": _check(verify, "port_check")}
    fields.update(dict.fromkeys(_NOT_MEASURED, "NOT_RUN"))
    return fields


def score_patch(fields: dict[str, str], weights: dict[str, float], impact_risk: float | None) -> tuple[float, float]:
    """``score(patch)`` of proposal §8.5 as a (lower, upper) interval; unmeasured fields widen the interval.

    Args:
        fields: The nine evidence fields.
        weights: ``tests``, ``schema_conformance``, ``architecture``, ``api``, ``semantic``, ``impact_risk``.
        impact_risk: Measured risk in [0, 1], or None when unmeasured (the whole penalty goes to the lower bound).
    """
    terms = (("tests_passed", weights["tests"] / 2), ("previously_failing_tests_fixed", weights["tests"] / 2),
             ("schema_conformance_passed", weights["schema_conformance"]),
             ("no_new_forbidden_dependency", weights["architecture"]),
             ("public_api_compatible", weights["api"]), ("semantic_invariant_preserved", weights["semantic"]))
    lower = sum(weight for name, weight in terms if fields[name] == "PASS")
    upper = lower + sum(weight for name, weight in terms if fields[name] in {"ERROR", "NOT_RUN"})
    if impact_risk is None:
        return lower - weights["impact_risk"], upper
    penalty = weights["impact_risk"] * impact_risk
    return lower - penalty, upper - penalty


def _impact_risk(verify: dict[str, Any]) -> float | None:
    status = _check(verify, "port_check")
    return 1.0 if status == "FAIL" else 0.0 if status == "PASS" else None


def rank_candidates(candidates: list[dict[str, Any]], *, verify_results: dict[str, dict[str, Any]],
                    test_results: dict[str, dict[str, Any]], weights: dict[str, float]) -> dict[str, Any]:
    """Order candidate patches: eligible first (graph checks and tests PASS), then score, then id.

    A high score never lifts a candidate whose required check failed above an eligible one.

    Args:
        candidates: ``{"candidate_id", "diff"}`` items.
        verify_results: ``verify_patch`` results keyed by ``diff_sha256(diff)``.
        test_results: ``run_patch_tests`` results keyed by ``diff_sha256(diff)``.
        weights: Score weights (see ``score_patch``).
    """
    rows = []
    for candidate in candidates:
        key = diff_sha256(candidate["diff"])
        verify, tests = verify_results[key], test_results[key]
        fields = evidence_fields(verify, tests)
        lower, upper = score_patch(fields, weights, _impact_risk(verify))
        rows.append({"candidate_id": candidate["candidate_id"], "diff_sha256": key,
                     "eligible": verify.get("status") == "PASS" and tests.get("status") == "PASS",
                     "score": round(lower, 6), "score_interval": [round(lower, 6), round(upper, 6)],
                     "evidence_fields": fields})
    rows.sort(key=lambda row: (not row["eligible"], -row["score"], row["candidate_id"]))
    return {"ranking": rows}
