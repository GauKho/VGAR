"""TR-1: trace link precision and recall against the files of the gold patch.

Expected values are written by hand from the inputs.
Spec: docs/superpowers/specs/2026-11-10-tv2-tr-1-trace-links-design.md
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import G_ARCH_EDGE_TYPES
from vgar.evaluation import trace_quality
from vgar.evaluation.trace_quality import RankedTrace, TraceScore, score_task, summarise
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.grounding import AnchorResult
from vgar.graph.task_overlay import TaskOverlay, TaskOverlayBuilder

T1 = TraceScore("t1", False, 4, 1, 1, True, (RankedTrace(0.95, True), RankedTrace(0.75, False), RankedTrace(0.4, False)), False, 10, 1)
T2 = TraceScore("t2", True, 10, 2, 2, False, (RankedTrace(0.75, False), RankedTrace(0.75, True)), True, 5, 1)
ISSUE = ('Login crashes\n\nTraceback (most recent call last):\n  File "app/service.py", line 8, in login\n'
         '    user = normalize(name)\nValueError: bad name\n')
CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"


def test_summarise_hand_numbers() -> None:
    result = summarise([T1, T2])["all"]
    component = result["component"]
    assert result["n"] == 2
    assert component["all"] == {"kept": 5, "correct": 2, "gold": 3, "precision": pytest.approx(0.4), "recall": pytest.approx(2 / 3)}
    assert component["confidence_0.5"]["kept"] == 4 and component["confidence_0.6"]["kept"] == 4
    assert component["confidence_0.7"]["precision"] == pytest.approx(0.5) and component["confidence_0.7"]["recall"] == pytest.approx(2 / 3)
    assert component["confidence_0.8"]["precision"] == 1.0 and component["confidence_0.8"]["recall"] == pytest.approx(1 / 3)
    assert component["top1"]["kept"] == 2 and component["top1"]["precision"] == 0.5 and component["top1"]["recall"] == pytest.approx(1 / 3)
    assert component["top2"]["kept"] == 4 and component["top2"]["correct"] == 2
    assert result["mrr"] == pytest.approx(0.75) and result["top_ties"] == 1
    assert result["baselines"]["random_precision"] == pytest.approx(0.225)
    assert result["baselines"]["largest_component"] == {"kept": 2, "correct": 1, "gold": 3, "precision": 0.5, "recall": pytest.approx(1 / 3)}
    assert result["file"] == {"kept": 15, "correct": 2, "gold": 3, "precision": pytest.approx(2 / 15), "recall": pytest.approx(2 / 3)}
    assert set(result["ci95"]) == {"confidence_0.7", "top1", "largest_component"}


def test_top_k_only_uses_strong_edges() -> None:
    weak = replace(T1, traces=(RankedTrace(0.6, True),))
    assert summarise([weak])["all"]["component"]["top1"]["kept"] == 0


def test_groups_split_on_traceback() -> None:
    result = summarise([T1, T2])
    assert (result["with_traceback"]["n"], result["without_traceback"]["n"]) == (1, 1)
    assert result["with_traceback"]["component"]["all"]["kept"] == 2 and result["without_traceback"]["component"]["all"]["kept"] == 3


def test_empty_group_has_none() -> None:
    group = summarise([T1])["with_traceback"]
    assert group["n"] == 0 and group["mrr"] is None and group["baselines"]["random_precision"] is None
    assert group["component"]["all"] == {"kept": 0, "correct": 0, "gold": 0, "precision": None, "recall": None}
    assert group["ci95"]["top1"] == {"precision": None, "recall": None}


def test_same_seed_same_interval() -> None:
    assert summarise([T1, T2], seed=3)["all"]["ci95"] == summarise([T1, T2], seed=3)["all"]["ci95"]


def test_single_task_interval_is_the_point() -> None:
    assert summarise([T1], rounds=50)["all"]["ci95"]["top1"] == {"precision": [1.0, 1.0], "recall": [1.0, 1.0]}


class _ScriptedRandom:
    def __init__(self, samples: list[list[TraceScore]]) -> None:
        self.samples = iter(samples)
        self.sizes: list[int] = []

    def choices(self, population: list[TraceScore], k: int) -> list[TraceScore]:
        self.sizes.append(k)
        return next(self.samples)


@pytest.mark.parametrize(("low", "middle", "high", "expected"), [
    (1, 38, 1, {"precision": [0.25, 0.25], "recall": [0.5, 0.5]}),
    (3, 34, 3, {"precision": [0.0, 1.0], "recall": [0.0, 1.0]}),
])
def test_interval_hand_numbers(monkeypatch: pytest.MonkeyPatch, low: int, middle: int, high: int, expected: dict[str, list[float]]) -> None:
    # Pooled: (A, A) is 2/2 and 2/2; (A, B) is 1/4 and 1/2; (B, B) is 0/6 and 0/2. With 40 rounds the bounds are sorted positions 1 and 38.
    right = replace(T1, traces=(RankedTrace(0.9, True),), gold_components=1)
    wrong = replace(T1, traces=(RankedTrace(0.9, False),) * 3, gold_components=1)
    scripted = _ScriptedRandom([[right, right]] * high + [[right, wrong]] * middle + [[wrong, wrong]] * low)
    monkeypatch.setattr(trace_quality.random, "Random", lambda seed: scripted)
    assert trace_quality._interval([right, wrong], trace_quality._at_least(0.7), 0, 40) == expected
    assert scripted.sizes == [2] * 40


def test_no_edge_against_gold_gives_zero_recall() -> None:
    # Nothing linked while the gold patch touches a component: recall is 0, only precision is undefined.
    assert summarise([replace(T1, traces=())])["all"]["component"]["all"] == {"kept": 0, "correct": 0, "gold": 1, "precision": None, "recall": 0.0}


def test_mrr_counts_tasks_without_a_correct_edge_as_zero() -> None:
    assert summarise([T1, replace(T2, traces=())])["all"]["mrr"] == pytest.approx(0.5)


def _component(node_id: str, files: list[str]) -> dict[str, Any]:
    return {"id": node_id, "type": "Component", "name": node_id, "path": None, "properties": {"files": files}}


def _trace(target: str, confidence: float, count: int) -> dict[str, Any]:
    return {"type": "TRACES_TO", "source_id": "issue", "target_id": target, "confidence": confidence, "properties": {"anchor_count": count}}


def _stub(edges: list[dict[str, Any]], nodes: list[dict[str, Any]] | None = None) -> TaskOverlay:
    return TaskOverlay("v", "o", "t", nodes or [], edges, AnchorResult("v", [], [], []))


def test_score_task_on_real_overlay() -> None:
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(CASES / "multi_package")
    score = score_task(document, TaskOverlayBuilder(document).build("t1", ISSUE), ["app/service.py"])
    assert score.task_id == "t1" and score.has_traceback is True and score.gold_files == 1 and score.gold_components == 1
    assert score.traces == (RankedTrace(0.95, True),) and score.top_tied is False
    assert score.mentioned_correct == 1 and score.mentioned_files >= 1


def test_score_task_without_components() -> None:
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(CASES / "multi_package")
    removed = {"Component", "Port", "Service", "DeploymentUnit"}
    document = {**document, "nodes": [node for node in document["nodes"] if node["type"] not in removed],
                "edges": [edge for edge in document["edges"] if edge["type"] not in G_ARCH_EDGE_TYPES]}
    score = score_task(document, TaskOverlayBuilder(document).build("t1", ISSUE), ["app/service.py"])
    assert (score.components, score.gold_components, score.largest_component_correct, score.traces) == (0, 0, False, ())
    summary = summarise([score, T1])["all"]
    assert summary["baselines"]["random_precision"] == pytest.approx(0.25)
    assert summary["baselines"]["largest_component"]["kept"] == 1


@pytest.mark.parametrize(("gold", "expected"), [("a/x.py", True), ("b/x.py", False)])
def test_largest_tie_uses_smallest_id(gold: str, expected: bool) -> None:
    document = {"nodes": [_component("b", ["b/x.py", "b/y.py"]), _component("a", ["a/x.py", "a/y.py"])]}
    assert score_task(document, _stub([]), [gold]).largest_component_correct is expected


@pytest.mark.parametrize(("second", "tied"), [((0.8, 2), True), ((0.8, 1), False), ((0.75, 2), False)])
def test_top_tied_needs_same_confidence_and_count(second: tuple[float, int], tied: bool) -> None:
    document = {"nodes": [_component("a", ["a/x.py"]), _component("b", ["b/x.py"])]}
    assert score_task(document, _stub([_trace("a", 0.8, 2), _trace("b", *second)]), ["a/x.py"]).top_tied is tied


def test_score_task_ranks_traces() -> None:
    document = {"nodes": [_component("a", ["a/x.py"]), _component("b", ["b/x.py"])]}
    score = score_task(document, _stub([_trace("a", 0.7, 1), _trace("b", 0.9, 1)]), ["a/x.py"])
    assert score.traces == (RankedTrace(0.9, False), RankedTrace(0.7, True))


def test_mentioned_files_leave_out_tests_and_task_nodes() -> None:
    document = {"nodes": [{"id": "x", "type": "File", "path": "a/x.py"}, {"id": "y", "type": "Function", "path": "a/x.py"},
                          {"id": "z", "type": "File", "path": "a/z.py"}, {"id": "t", "type": "Test", "path": "tests/test_x.py"}]}
    frame = {"id": "frame", "type": "StackTraceFrame", "path": None}
    edges = [{"type": "MENTIONS", "source_id": "issue", "target_id": target} for target in ("x", "y", "z", "t", "frame")]
    score = score_task(document, _stub(edges, [frame]), ["a/x.py"])
    assert (score.mentioned_files, score.mentioned_correct) == (2, 1) and score.has_traceback is True
