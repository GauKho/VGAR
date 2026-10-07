"""Regressions for the real Graph-runner -> paired-comparison boundary."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import subprocess
import tarfile
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.compare import compare_runs
from vgar.evaluation.retrieval.evaluation import evaluate_task
from vgar.evaluation.retrieval.evidence import sha256, write_json
from vgar.evaluation.retrieval.graph_arm import evaluate_graph_task
from vgar.evaluation.retrieval.metrics import aggregate_metrics
from vgar.evaluation.retrieval.report import write_report
from vgar.evaluation.retrieval.scoring import CorpusIndex

SOURCE = 'def login(user):\n    return user == "root"\n'
SOURCES = {"src/auth.py": SOURCE}
PATCH = '--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1,2 +1,2 @@\n def login(user):\n-    return user == "root"\n+    return user == "admin"\n'
TASK = {"instance_id": "t-2", "repo": "o/r", "base_commit": "a" * 40,
        "problem_statement": "login user fails", "patch": PATCH}


def _words(text):
    return len(text.split())


def _write_pair(tmp_path):
    bm = evaluate_task(TASK, SOURCES, 200, counter=_words, counter_label="fixture-words")
    nodes = {"f": {"id": "f", "type": "Function", "path": "src/auth.py",
                   "qualified_name": "auth.login", "range": {"start_line": 1, "end_line": 2}}}
    outputs = {arm: {"candidates": [{"node_id": "f", "relevance_score": 1.0}],
                     "anchors": [{"node_id": "f", "symbol": "auth.login"}], "seconds": 0.1}
               for arm in ("graph", "graph_f2p")}
    gr = evaluate_graph_task(TASK, SOURCES, CorpusIndex(SOURCES), nodes, outputs,
                             budget_tokens=200, counter=_words, counter_label="fixture-words")
    dirs = tmp_path / "bm", tmp_path / "gr"
    config = {"budget_tokens": 200, "counter_label": "fixture-words", "counter_is_fallback": False,
              "scoring_version": "retrieval-scoring-v1", "snippet_policy": {"max_snippet_lines": 80},
              "retrieval": {"max_candidates": 1}}
    for directory, task, kind in zip(dirs, (bm, gr), ("retrieval", "retrieval_graph")):
        _save_task(directory, task)
        row = {"instance_id": task["instance_id"], "status": "SUCCEEDED",
               "artifact_hash": sha256((directory / "tasks" / "t-2.json").read_bytes())}
        if kind == "retrieval":
            row.update(metrics=task["metrics"], corpus_hash=task["corpus_hash"])
        else:
            # Same shape as the runner, deliberately NO singular 'arm'.
            row.update(graph_build_seconds=0.1,
                       arms={a: {"file_recall@5": data["metrics"]["file_recall@5"]}
                             for a, data in task["arms"].items()})
        record = {"run_id": directory.name, "kind": kind, "complete": True,
                  "dataset_id": "fixture", "dataset_revision": "revision", "config": config,
                  "task_results": [row], "summary": aggregate_metrics([row]) if kind == "retrieval" else {}}
        write_json(directory / "result.json", record)
    return dirs


def _save_task(directory, task):
    write_json(directory / "tasks" / f"{task['instance_id']}.json", task)
    result_path = directory / "result.json"
    if result_path.exists():
        record = json.loads(result_path.read_text(encoding="utf-8"))
        record["task_results"][0]["artifact_hash"] = sha256((directory / "tasks" / "t-2.json").read_bytes())
        write_json(result_path, record)


def _mutate_run(directory, mutate):
    path = directory / "result.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    mutate(record)
    write_json(path, record)


def test_actual_graph_summary_without_arm_is_accepted(tmp_path):
    bm_dir, gr_dir = _write_pair(tmp_path)
    directory, report = compare_runs(bm_dir, gr_dir, tmp_path / "out")
    assert report["paired_tasks"] == 1 and report["exit_code"] == 0
    assert set(report["summaries"]) == {"bm25", "graph", "graph_f2p"}
    text = write_report(bm_dir, comparison=directory, destination=directory / "REPORT.md").read_text(encoding="utf-8")
    assert "oracle-assisted" in text and "full rank" in text


def test_comparison_consumes_actual_runner_output(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_graph_retrieval.py"
    spec = importlib.util.spec_from_file_location("graph_runner_contract_test", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    archive = tmp_path / "data/repositories/archives" / f"o__r-{TASK['base_commit']}.tar.gz"
    archive.parent.mkdir(parents=True)
    with tarfile.open(archive, "w:gz") as bundle:
        for path, source in SOURCES.items():
            data = source.encode("utf-8")
            member = tarfile.TarInfo(f"r-{TASK['base_commit']}/{path}")
            member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
    write_json(archive.with_suffix(".json"), {"url": f"https://codeload.github.com/o/r/tar.gz/{TASK['base_commit']}",
                                            "archive_hash": sha256(archive.read_bytes()), "base_commit": TASK["base_commit"]})
    patch_path = tmp_path / "data" / "gold" / "patches" / "t-2.patch"
    patch_path.parent.mkdir(parents=True)
    patch_path.write_text(PATCH, encoding="utf-8", newline="\n")
    row = {k: v for k, v in TASK.items() if k != "patch"}
    row.update(split="dev", gold_patch_path="data/gold/patches/t-2.patch",
               patch_hash=sha256(PATCH), query_hash=sha256(TASK["problem_statement"]))
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"dataset_id": "fixture", "dataset_revision": "fixture-revision", "split": "dev", "tasks": [row]})
    # Only FAIL_TO_PASS snapshot acquisition is substituted; the isolated worker
    # loads this real synthetic archive via the production hash/provenance guard.
    monkeypatch.setattr(runner, "load_fail_to_pass", lambda *a: {"t-2": []})
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), str(manifest),
                                     "--allow-fallback-counter", "--no-jedi", "--offline", "--budget-tokens", "200"])
    # Archive, gold and manifest are inputs, not editable repair workspaces.
    original = {path: path.read_bytes() for path in (archive, archive.with_suffix(".json"), patch_path, manifest)}
    assert runner.main() == 0
    graph_dir = next((tmp_path / "results" / "retrieval").iterdir())
    record = json.loads((graph_dir / "result.json").read_text(encoding="utf-8"))
    assert "arm" not in record["task_results"][0]
    bm = evaluate_task(TASK, SOURCES, 200)
    bm_dir = tmp_path / "baseline"
    _save_task(bm_dir, bm)
    summary = {"instance_id": "t-2", "status": "SUCCEEDED", "metrics": bm["metrics"],
               "artifact_hash": sha256((bm_dir / "tasks" / "t-2.json").read_bytes())}
    write_json(bm_dir / "result.json", {"run_id": "baseline", "kind": "retrieval", "complete": True,
                                        "dataset_id": "fixture", "dataset_revision": "fixture-revision",
                                        "config": record["config"], "task_results": [summary],
                                        "summary": aggregate_metrics([summary])})
    # Diagnostic counter is explicitly allowed only in this synthetic test.
    compared_dir, comparison = compare_runs(bm_dir, graph_dir, tmp_path / "compared", allow_fallback=True)
    assert comparison["paired_tasks"] == 1 and comparison["exit_code"] == 0
    report_path = write_report(bm_dir, comparison=compared_dir, destination=compared_dir / "REPORT.md")
    text = report_path.read_text(encoding="utf-8")
    assert "oracle-assisted" in text and "full rank" in text
    assert all(path.read_bytes() == raw for path, raw in original.items())
    task_artifact = json.loads((graph_dir / "tasks/t-2.json").read_text(encoding="utf-8"))
    tree = Path(task_artifact["source_tree"]["path"])
    assert (tree / "src/auth.py").read_bytes() == SOURCE.encode("utf-8")
    assert task_artifact["inference"] == "NOT_RUN"


@pytest.mark.parametrize("key,value", [("dataset_id", "other"), ("dataset_revision", "other")])
def test_different_dataset_binding_is_rejected(tmp_path, key, value):
    bm, gr = _write_pair(tmp_path)
    _mutate_run(gr, lambda r: r.update({key: value}))
    with pytest.raises(ValueError, match="dataset"):
        compare_runs(bm, gr, tmp_path / "out")


@pytest.mark.parametrize("key", ["query_hash", "corpus_hash", "base_commit", "patch_hash", "repository", "gold"])
def test_different_task_binding_is_rejected(tmp_path, key):
    bm, gr = _write_pair(tmp_path)
    task = json.loads((gr / "tasks" / "t-2.json").read_text(encoding="utf-8"))
    task[key] = {"gold_files": ["other.py"]} if key == "gold" else "different"
    _save_task(gr, task)
    with pytest.raises(ValueError, match=key):
        compare_runs(bm, gr, tmp_path / "out")


@pytest.mark.parametrize("key,value", [("budget_tokens", 201), ("counter_label", "other"),
                                      ("scoring_version", "other"), ("snippet_policy", {})])
def test_different_config_is_rejected(tmp_path, key, value):
    bm, gr = _write_pair(tmp_path)
    _mutate_run(gr, lambda r: r["config"].update({key: value}))
    with pytest.raises(ValueError, match=key):
        compare_runs(bm, gr, tmp_path / "out")


@pytest.mark.parametrize("side", [0, 1])
def test_duplicate_task_ids_are_rejected(tmp_path, side):
    dirs = _write_pair(tmp_path)
    _mutate_run(dirs[side], lambda r: r["task_results"].append(dict(r["task_results"][0])))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        compare_runs(*dirs, tmp_path / "out")


@pytest.mark.parametrize("mutation", ["kind", "arms", "missing_arm", "artifact_hash", "population"])
def test_malformed_graph_run_is_rejected(tmp_path, mutation):
    bm, gr = _write_pair(tmp_path)
    def mutate(record):
        if mutation == "kind":
            record["kind"] = "retrieval"
        elif mutation == "arms":
            record["task_results"][0]["arms"] = {"bm25": {}}
        elif mutation == "missing_arm":
            del record["task_results"][0]["arms"]["graph_f2p"]
        elif mutation == "artifact_hash":
            record["task_results"][0]["artifact_hash"] = "sha256:bad"
        else:
            record["task_results"][0]["instance_id"] = "not-in-baseline"
    _mutate_run(gr, mutate)
    with pytest.raises(ValueError):
        compare_runs(bm, gr, tmp_path / "out")


def test_no_paired_tasks_is_not_success(tmp_path):
    bm, gr = _write_pair(tmp_path)
    _mutate_run(bm, lambda r: r["task_results"][0].update(status="FAILED"))
    _, report = compare_runs(bm, gr, tmp_path / "out")
    assert report["status"] == "NO_PAIRED_TASKS" and report["exit_code"] != 0
    assert report["coverage"]["bm25"]["failed_tasks"] == 1


def test_partial_comparison_reports_failures_and_metric_denominators(tmp_path):
    bm, gr = _write_pair(tmp_path)
    def add_task(record):
        record["task_results"].append({"instance_id": "failed-task",
                                        "status": "FAILED", "error_class": "MemoryError"})
    for directory in (bm, gr):
        _mutate_run(directory, add_task)
    _, report = compare_runs(bm, gr, tmp_path / "out")
    assert report["status"] == "COMPARED_PARTIAL" and report["exit_code"] != 0
    assert report["paired_tasks"] == 1 and len(report["skipped"]) == 1
    assert report["coverage"]["graph"]["attempted_tasks"] == 2
    assert report["coverage"]["graph"]["failed_tasks"] == 1
    assert report["summaries"]["graph"]["metrics"]["file_recall@5"]["eligible_tasks"] == 1


@pytest.mark.parametrize("mutation", ["missing_hash", "artifact_id", "artifact_status", "missing_gold", "missing_metrics"])
def test_missing_or_inconsistent_artifact_metadata_is_rejected(tmp_path, mutation):
    bm, gr = _write_pair(tmp_path)
    if mutation == "missing_hash":
        _mutate_run(gr, lambda r: r["task_results"][0].pop("artifact_hash"))
    else:
        task = json.loads((gr / "tasks" / "t-2.json").read_text(encoding="utf-8"))
        if mutation == "artifact_id":
            task["instance_id"] = "other-id"
        elif mutation == "artifact_status":
            task["status"] = "FAILED"
        elif mutation == "missing_gold":
            del task["gold"]
        else:
            del task["arms"]["graph"]["metrics"]
        # Update the genuine hash so the test catches metadata, not byte corruption.
        write_json(gr / "tasks" / "t-2.json", task)
        _mutate_run(gr, lambda r: r["task_results"][0].update(
            artifact_hash=sha256((gr / "tasks" / "t-2.json").read_bytes())))
    with pytest.raises(ValueError):
        compare_runs(bm, gr, tmp_path / "out")


def test_cap_is_only_separate_rank_sensitivity(tmp_path):
    bm, gr = _write_pair(tmp_path)
    directory, report = compare_runs(bm, gr, tmp_path / "out", cap=1)
    task = json.loads((bm / "tasks" / "t-2.json").read_text(encoding="utf-8"))
    assert report["summaries"]["bm25"]["metrics"]["rank_items"]["mean"] == task["metrics"]["rank_items"]
    sensitivity = report["rank_sensitivity"]
    assert sensitivity["cap"] == 1 and "context_tokens" not in sensitivity["summary"]["metrics"]
    assert sensitivity["packed_context_recomputed"] is False
    text = write_report(bm, comparison=directory, destination=directory / "REPORT.md").read_text(encoding="utf-8")
    assert "rank-only sensitivity" in text and "oracle-assisted" in text
    assert "Graph tối đa 100 node" not in text


def test_comparison_cli_defaults_to_full_rank(tmp_path):
    bm, gr = _write_pair(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts" / "compare_graph_vs_bm25.py"
    before = [(d / "result.json").read_bytes() for d in (bm, gr)]
    completed = subprocess.run([sys.executable, str(script), str(tmp_path), str(bm), str(gr)],
                               capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert completed.returncode == 0, completed.stderr
    report_path = Path(completed.stdout.strip())
    report = json.loads((report_path.parent / "result.json").read_text(encoding="utf-8"))
    assert report["bm25_cap"] is None and report["rank_sensitivity"] is None
    assert before == [(d / "result.json").read_bytes() for d in (bm, gr)]


@pytest.mark.parametrize("cap", [0, -1, True])
def test_invalid_cap_is_rejected(tmp_path, cap):
    with pytest.raises(ValueError, match="cap"):
        compare_runs(*_write_pair(tmp_path), tmp_path / "out", cap=cap)
