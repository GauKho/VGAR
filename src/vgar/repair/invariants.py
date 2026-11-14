"""L5-2: likely invariants from baseline test traces, checked on the candidate (proposal §5.2 Layer 5, §12.4).

Samples come only from tests that passed on the baseline (on both sides): behaviour on the paths of
tests that failed is expected to change. This module holds the Python side of the design: sample
selection, the fallback templates (used when Daikon does not run), the exception supplement (Daikon
ignores exceptional exits), the noise filter and the program point → graph node id mapping.
Invariants are likely invariants, not proof.
"""
from __future__ import annotations

import itertools
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vgar.graph.builder import module_name_for
from vgar.repair.daikon import (
    DaikonConfig,
    DaikonUnavailable,
    declarations,
    run_daikon,
    write_dtrace,
)

logger = logging.getLogger(__name__)

# Team's choice, fixed from the 14/11 demo-shop spike; not tuned on evaluation data.
NOISE_PATTERNS = (r"is a power of 2", r"\*\*2", r"is boolean", r"% \S+ == 0", r"__len__\b",
                  r"has only one value")
_NOISE = re.compile("|".join(NOISE_PATTERNS))
META = "__test__"


def load_trace(folder: Path) -> tuple[list[dict], dict]:
    """Records and meta written by ``invariant_trace_plugin``; empty when the folder has no trace.

    Args:
        folder: The plugin's ``--vgar-trace-dir``.
    """
    trace, meta = Path(folder) / "trace.jsonl", Path(folder) / "trace_meta.json"
    if not trace.is_file():
        return [], {}
    records = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    return records, json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}


def select_samples(records: list[dict], tests: set[str]) -> dict[str, list[dict]]:
    """Primitive values per program point (``<ppt>:::ENTER`` / ``<ppt>:::EXIT``) from the given tests.

    Args:
        records: Trace records.
        tests: Pytest node ids whose samples are kept.
    """
    points: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record["kind"] == "raise" or record.get("test") not in tests:
            continue
        row = {k: v for k, v in record["vars"].items() if not isinstance(v, dict)}
        row[META] = record["test"]
        points[f"{record['ppt']}:::{'ENTER' if record['kind'] == 'enter' else 'EXIT'}"].append(row)
    return dict(points)


def point_sets(base: dict[str, list], cand: dict[str, list]) -> tuple[list[str], list[str]]:
    """(points only in the candidate, points only in the baseline)."""
    return sorted(set(cand) - set(base)), sorted(set(base) - set(cand))


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def learn_python(points: dict[str, list[dict]]) -> list[dict]:
    """Fallback templates: constant, one of <= 3 values, bounds, >= 0, ==/</<=/>/>= and y = a*x + b.

    A point needs 2 samples for any invariant and 3 for the binary templates.

    Args:
        points: ``select_samples`` result of the baseline.
    """
    found = []
    for ppt, rows in sorted(points.items()):
        if len(rows) < 2:
            continue
        names = sorted({k for row in rows for k in row if k != META})
        columns = {n: [row.get(n, "__missing__") for row in rows] for n in names}
        numeric = [n for n in names if all(_number(v) for v in columns[n])]
        for n in names:
            values = columns[n]
            if "__missing__" in values:
                continue
            distinct = sorted(set(map(json.dumps, values)))
            if len(distinct) == 1:
                found.append({"ppt": ppt, "kind": "const", "var": n, "value": json.loads(distinct[0])})
            elif len(distinct) <= 3:
                found.append({"ppt": ppt, "kind": "one_of", "var": n, "values": [json.loads(d) for d in distinct]})
            if n in numeric and len(distinct) > 3:
                found.append({"ppt": ppt, "kind": "range", "var": n, "min": min(values), "max": max(values)})
            if n in numeric and len(distinct) > 1 and min(values) >= 0:
                found.append({"ppt": ppt, "kind": "nonneg", "var": n})
        if len(rows) < 3:
            continue
        for x, y in itertools.combinations(numeric, 2):
            xs, ys = columns[x], columns[y]
            if len(set(xs)) == 1 and len(set(ys)) == 1:
                continue
            for op, test in (("==", lambda a, b: a == b), ("<", lambda a, b: a < b), ("<=", lambda a, b: a <= b),
                             (">", lambda a, b: a > b), (">=", lambda a, b: a >= b)):
                if all(test(a, b) for a, b in zip(xs, ys)):
                    found.append({"ppt": ppt, "kind": "cmp", "var": x, "op": op, "other": y})
                    break
            pairs = sorted(set(zip(xs, ys)))
            if len({a for a, _ in pairs}) >= 3:
                (x1, y1), (x2, y2) = pairs[0], pairs[-1]
                if x2 != x1:
                    a = (y2 - y1) / (x2 - x1)
                    b = y1 - a * x1
                    if a != 0 and not (a == 1 and b == 0) and all(
                            abs(a * px + b - py) <= 1e-6 * max(1, abs(py)) for px, py in pairs):
                        found.append({"ppt": ppt, "kind": "linear", "var": y, "other": x, "a": a, "b": b})
    return found


def _holds(inv: dict, row: dict) -> bool | None:
    if inv["var"] not in row or ("other" in inv and inv["other"] not in row):
        return None
    v = row[inv["var"]]
    kind = inv["kind"]
    if kind == "const":
        return v == inv["value"]
    if kind == "one_of":
        return v in inv["values"]
    if not _number(v):
        return False
    if kind == "range":
        return inv["min"] <= v <= inv["max"]
    if kind == "nonneg":
        return v >= 0
    w = row[inv["other"]]
    if not _number(w):
        return False
    if kind == "cmp":
        return {"==": v == w, "<": v < w, "<=": v <= w, ">": v > w, ">=": v >= w}[inv["op"]]
    return abs(inv["a"] * w + inv["b"] - v) <= 1e-6 * max(1, abs(v))


def describe(inv: dict) -> str:
    """Readable text of a fallback invariant."""
    kind = inv["kind"]
    if kind == "const":
        return f"{inv['var']} == {inv['value']!r}"
    if kind == "one_of":
        return f"{inv['var']} one of {inv['values']!r}"
    if kind == "range":
        return f"{inv['min']} <= {inv['var']} <= {inv['max']}"
    if kind == "nonneg":
        return f"{inv['var']} >= 0"
    if kind == "cmp":
        return f"{inv['var']} {inv['op']} {inv['other']}"
    return f"{inv['var']} == {inv['a']:g} * {inv['other']} + {inv['b']:g}"


def check_python(invariants: list[dict], points: dict[str, list[dict]]) -> list[dict]:
    """One violation per (invariant, first candidate sample that breaks it).

    Args:
        invariants: ``learn_python`` result.
        points: ``select_samples`` result of the candidate.
    """
    violations = []
    for inv in invariants:
        for row in points.get(inv["ppt"], []):
            if _holds(inv, row) is False:
                violations.append({"program_point": inv["ppt"], "invariant": describe(inv), "test": row.get(META, "")})
                break
    return violations


def exception_violations(base: list[dict], cand: list[dict], tests: set[str]) -> list[dict]:
    """Exception supplement: per (program point, test), a new exception class or one no longer raised.

    Args:
        base: Baseline trace records.
        cand: Candidate trace records.
        tests: Baseline-passing test node ids.
    """
    def raised(records: list[dict]) -> tuple[dict, set]:
        classes: dict[tuple[str, str], set[str]] = defaultdict(set)
        calls: set[tuple[str, str]] = set()
        for record in records:
            if record.get("test") not in tests or record["kind"] == "enter":
                continue
            calls.add((record["ppt"], record["test"]))
            if record["kind"] == "raise":
                classes[(record["ppt"], record["test"])].add(record.get("exception", "Exception"))
        return classes, calls

    before, _ = raised(base)
    after, after_calls = raised(cand)
    seen_per_point: dict[str, set[str]] = defaultdict(set)
    for (ppt, _), names in before.items():
        seen_per_point[ppt] |= names
    out = []
    for (ppt, test), names in sorted(after.items()):
        for name in sorted(names - seen_per_point[ppt]):
            out.append({"program_point": ppt, "invariant": f"raises only {sorted(seen_per_point[ppt])}, now {name}",
                        "test": test})
    for (ppt, test), names in sorted(before.items()):
        if (ppt, test) in after_calls and not after.get((ppt, test)):
            out.append({"program_point": ppt, "invariant": f"raises {sorted(names)} in this test, no longer raises",
                        "test": test})
    return out


def is_noise(text: str, derived: frozenset[str] | set[str] = frozenset()) -> bool:
    """True for invariant texts that carry no meaning for Python code (the fixed noise list).

    Args:
        text: Invariant text.
        derived: Container-length variable names the Daikon writer generated (``x_size``); user
            variables with the same suffix are not noise.
    """
    return bool(_NOISE.search(text)) or any(re.search(rf"\b{re.escape(name)}\b", text) for name in derived)


def derived_names(records: list[dict]) -> set[str]:
    """Daikon names of the container lengths (``x.__len__`` becomes ``x_size``) present in the records."""
    return {name.replace(".__len__", "_size").replace(".", "_")
            for record in records for name in record["vars"] if name.endswith(".__len__")}


def node_id_for(record: dict, repo_key: str, source_roots: tuple[str, ...], repository_name: str) -> str:
    """Graph node id of the traced function (the builder's id scheme and module-name rule).

    Args:
        record: Trace record with ``path`` and ``qualname``.
        repo_key: Graph repository key.
        source_roots: Source roots the graph was built with.
        repository_name: Folder name of the repository root.
    """
    path, qualname = record["path"], record["qualname"]
    module = module_name_for(path, source_roots, repository_name)
    parts = qualname.split(".")
    kind = "method" if len(parts) > 1 and "<locals>" not in parts else "function"
    if parts[-1].startswith("test_") and (Path(path).name.startswith("test_") or "/tests/" in f"/{path}"):
        kind = "test"
    return f"vgar:{repo_key}:python:{kind}:{path}:{module}.{qualname}"


# ---------------------------------------------------------------- orchestration (EV-3)
LIMITATION = "LIKELY_INVARIANTS_NOT_PROOF"
PROFILE = "tv3-l5-invariants-v1"


class InvariantExecutor:
    """Adds the L5-1 trace plugin to every pytest command of the wrapped executor (like ``ContractExecutor``)."""

    def __init__(self, executor, trace_dir: Path):
        self.executor, self.trace_dir = executor, Path(trace_dir)

    def run(self, argv, cwd, timeout_seconds):
        """Run ``argv``; pytest commands get ``-p vgar.repair.invariant_trace_plugin --vgar-trace-dir=<dir>``."""
        import sys

        if tuple(argv[:3]) == (sys.executable, "-m", "pytest"):
            argv = (*argv, "-p", "vgar.repair.invariant_trace_plugin", f"--vgar-trace-dir={self.trace_dir}")
        return self.executor.run(argv, cwd, timeout_seconds)


@dataclass(frozen=True)
class InvariantSettings:
    """Host settings for L5: Daikon location and the graph naming used for node ids."""

    daikon: DaikonConfig = field(default_factory=DaikonConfig)
    repo_key: str = ""
    source_roots: tuple[str, ...] = ("src",)
    repository_name: str = ""


def not_run_record(reason: str, status: str = "NOT_RUN") -> dict:
    """A ``semantic_invariants`` record for a run that measured nothing (``NOT_RUN`` or ``ERROR``)."""
    return {"profile": PROFILE, "status": status, "reasons": [reason], "noise_patterns": list(NOISE_PATTERNS), "engine": None, "learned": 0,
            "filtered_noise": 0, "violations": [], "violations_total": 0, "new_points": [], "unexercised_points": [],
            "limitations": [LIMITATION], "python_version": None, "daikon_version": None}


def fit_record(record: dict, max_bytes: int) -> dict:
    """Cut the violation list (keeping ``violations_total``) until the record fits ``max_bytes``.

    Args:
        record: ``semantic_invariants`` record.
        max_bytes: Byte budget for this record inside the EV-3 evidence.
    """
    out = dict(record)
    for key in ("violations", "new_points", "unexercised_points"):
        items = list(out.get(key, []))
        while items and len(json.dumps(out)) > max_bytes:
            items = items[:len(items) // 2]
            out[key] = items
    return out


def compute_semantic_invariants(base_dir: Path, cand_dir: Path, baseline_outcomes: dict[str, str],
                                settings: InvariantSettings, deadline: float) -> dict:
    """Learn on the baseline trace, check the candidate trace (spec §3).

    Args:
        base_dir: Trace folder of the baseline test run.
        cand_dir: Trace folder of the candidate test run.
        baseline_outcomes: Pytest node id → ``PASS``/``FAIL`` on the baseline.
        settings: Daikon and graph naming settings.
        deadline: ``time.monotonic()`` value by which Daikon must finish.
    """
    passing = {test for test, status in baseline_outcomes.items() if status == "PASS"}
    if not passing:
        return not_run_record("NO_BASELINE_PASSING_TEST")
    base_records, base_meta = load_trace(base_dir)
    cand_records, cand_meta = load_trace(cand_dir)
    if not any(r.get("test") in passing for r in base_records):
        return not_run_record("TRACE_EMPTY")
    base_selected = [r for r in base_records if r.get("test") in passing]
    cand_selected = [r for r in cand_records if r.get("test") in passing]
    base_points, cand_points = select_samples(base_selected, passing), select_samples(cand_selected, passing)
    if not set(base_points) & set(cand_points):
        return not_run_record("CANDIDATE_TRACE_EMPTY")  # candidate never reached a learned point (crash, no trace)
    reasons: list[str] = []
    engine, daikon_version = "python-fallback", None
    learned: list[str] | None = None
    violations: list[dict] = []
    if settings.daikon.configured:
        work = Path(base_dir).parent / "daikon"
        work.mkdir(parents=True, exist_ok=True)
        decls = declarations(base_selected)
        write_dtrace(base_selected, work / "base.dtrace", decls)
        write_dtrace(cand_selected, work / "cand.dtrace", decls)
        try:
            # Leave time for the fallback and for publishing the evidence (spec: Daikon within the deadline).
            now = time.monotonic()
            budget = deadline - max(5.0, 0.2 * (deadline - now))
            learned, violated, daikon_version = run_daikon(settings.daikon, work / "base.dtrace",
                                                           work / "cand.dtrace", work, budget)
            engine = f"daikon {daikon_version or 'unknown'}"
            for text in violated:
                point, _, invariant = text.partition("  ")
                violations.append({"program_point": point, "invariant": invariant, "test": ""})
        except DaikonUnavailable as error:
            logger.warning("Daikon unavailable, Python fallback: %s", error)
            reasons.append(f"daikon unavailable: {error}")
            learned = None
    else:
        reasons.append("daikon not configured")
    if learned is None:
        invariants = learn_python(base_points)
        learned = [f"{inv['ppt']}  {describe(inv)}" for inv in invariants]
        violations = check_python(invariants, cand_points)
    violations += exception_violations(base_records, cand_records, passing)
    derived = derived_names(base_records)
    kept_learned = [text for text in learned if not is_noise(text, derived)]
    noise = len(learned) - len(kept_learned)
    violations = [v for v in violations if not is_noise(v["invariant"], derived)]
    where = {r["ppt"]: r for r in base_records + cand_records}
    repository_name = settings.repository_name or Path(base_dir).name
    for violation in violations:
        record = where.get(violation["program_point"].split(":::")[0])
        violation["node_id"] = node_id_for(record, settings.repo_key, settings.source_roots, repository_name) \
            if record else ""
    new, unexercised = point_sets(base_points, cand_points)
    limitations = [LIMITATION] + (["TRACE_TRUNCATED"] if base_meta.get("truncated") or cand_meta.get("truncated") else [])
    return {"profile": PROFILE, "status": "FAIL" if violations else "PASS", "reasons": reasons,
            "noise_patterns": list(NOISE_PATTERNS), "engine": engine,
            "learned": len(kept_learned), "filtered_noise": noise, "violations": violations,
            "violations_total": len(violations), "new_points": new, "unexercised_points": unexercised,
            "limitations": limitations, "python_version": base_meta.get("python"), "daikon_version": daikon_version}
