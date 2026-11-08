"""Layer 2 known-answer test: call edges against the hand-labelled repos in tests/fixtures/vgar-callgraph-cases."""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder

CASES = Path(__file__).parent / "fixtures" / "vgar-callgraph-cases"
REPOS = (("vgar-callgraph-cases", "src"), ("vgar-callgraph-cases-flat", "."))
EXPECT = re.compile(r"#\s*expect:\s*([^#]+)")


def _norm(name: str) -> str:
    return name.replace(".<locals>", "")


def _expectations(repo: Path, source_root: Path) -> dict[tuple[str, int], list[str]]:
    found = {}
    for path in sorted(source_root.rglob("*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if match := EXPECT.search(line):
                found[(path.relative_to(repo).as_posix(), line_number)] = [_norm(n.strip()) for n in match.group(1).split(",") if n.strip()]
    return found


def _score() -> tuple[Counter, Counter, list[tuple[str, int]]]:
    """(counts for CALLS only, counts for CALLS + MAY_CALL, annotated lines with no CallSite)."""
    certain: Counter = Counter()
    combined: Counter = Counter()
    missing = []
    for name, source in REPOS:
        repo = CASES / name
        document = PythonGraphBuilder(repo_key=f"cases/{name}", repository_revision="fixture").build(repo)
        nodes = {node["id"]: node for node in document["nodes"]}
        targets: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        bases: dict[str, list[str]] = defaultdict(list)
        for edge in document["edges"]:
            if edge["type"] in {"CALLS", "MAY_CALL"}:
                targets[edge["source_id"]][edge["type"]].append(edge["target_id"])
            elif edge["type"] == "INHERITS":
                bases[edge["source_id"]].append(edge["target_id"])
        sites = defaultdict(list)
        for node in document["nodes"]:
            if node["type"] == "CallSite":
                sites[(node["path"], node["range"]["start_line"])].append(node)

        def resolve(site_id: str, kind: str, expected: list[str]) -> set[str]:
            names = set()
            for target_id in targets[site_id][kind]:
                target = nodes[target_id]
                if target["type"] != "Class":
                    names.add(_norm(target["qualified_name"]))
                    continue
                lineage, stack = [], [target_id]
                while stack:
                    current = stack.pop()
                    if current not in lineage:
                        lineage.append(current)
                        stack.extend(bases[current])
                constructors = {f"{_norm(nodes[c]['qualified_name'])}.{m}" for c in lineage for m in ("__init__", "__new__")}
                names |= constructors & set(expected) or {_norm(target["qualified_name"])}
            return names

        for key, expected in _expectations(repo, repo / source).items():
            if key not in sites:
                missing.append(key)
                continue
            site = max(sites[key], key=lambda n: n["range"]["end_byte"] - n["range"]["start_byte"])
            exact = resolve(site["id"], "CALLS", expected)
            guessed = exact | resolve(site["id"], "MAY_CALL", expected)
            for counts, predicted in ((certain, exact), (combined, guessed)):
                if expected in (["external"], ["unknown"]):
                    counts[f"claims_{expected[0]}"] += bool(predicted)
                else:
                    counts.update(tp=len(predicted & set(expected)), fp=len(predicted - set(expected)), fn=len(set(expected) - predicted))
    return certain, combined, missing


@pytest.fixture(scope="module")
def scores() -> tuple[Counter, Counter, list[tuple[str, int]]]:
    return _score()


def test_every_annotated_call_has_a_callsite(scores) -> None:
    assert scores[2] == []


def test_certain_edges_are_never_wrong(scores) -> None:
    certain = scores[0]
    assert certain["fp"] == 0 and certain["claims_external"] == 0 and certain["claims_unknown"] == 0
    assert certain["tp"] >= 14


def test_may_call_does_not_regress(scores) -> None:
    # Baseline measured 08/11 in static mode: precision 0.579, recall 0.746. Lower these only on purpose.
    combined = scores[1]
    assert combined["tp"] >= 44 and combined["fp"] <= 32
    assert combined["claims_external"] <= 2 and combined["claims_unknown"] <= 1


@pytest.mark.skipif(sys.version_info < (3, 11), reason="verify_expect.py reads code.co_qualname")
@pytest.mark.parametrize(("name", "source"), REPOS)
def test_annotations_match_runtime(name: str, source: str) -> None:
    repo = CASES / name
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(CASES / "tools" / "verify_expect.py"), str(repo), str(repo / source)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
