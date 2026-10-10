from __future__ import annotations

import io
import json
import tarfile

import pytest

from vgar.evaluation.retrieval.compare import cap_bm25, compare_runs, paired_stats
from vgar.evaluation.retrieval.evaluation import evaluate_task
from vgar.evaluation.retrieval.evidence import sha256, write_json
from vgar.evaluation.retrieval.graph_arm import corpus_fingerprint, evaluate_graph_task, extract_python_tree
from vgar.evaluation.retrieval.metrics import aggregate_metrics
from vgar.evaluation.retrieval.report import write_report
from vgar.evaluation.retrieval.scoring import CorpusIndex

AUTH = 'def login(user, password):\n    return check(user, password)\n\n\ndef check(user, password):\n    return user == "root"\n'
OTHER = "def helper():\n    return 1\n"
SOURCES = {"src/auth.py": AUTH, "src/other.py": OTHER}
PATCH = ("--- a/src/auth.py\n+++ b/src/auth.py\n@@ -5,2 +5,2 @@\n def check(user, password):\n"
         '-    return user == "root"\n+    return user == "admin"\n')
SHA = "a" * 40
TASK = {"instance_id": "t-2", "repo": "o/r", "base_commit": SHA, "problem_statement": "login check password user fails", "patch": PATCH}
words = lambda text: len(text.split())
NODES = {
    "F:check": {"id": "F:check", "type": "Function", "path": "src/auth.py", "qualified_name": "auth.check", "range": {"start_line": 5, "end_line": 6}},
    "F:login": {"id": "F:login", "type": "Function", "path": "src/auth.py", "qualified_name": "auth.login", "range": {"start_line": 1, "end_line": 2}},
    "F:helper": {"id": "F:helper", "type": "Function", "path": "src/other.py", "qualified_name": "other.helper", "range": {"start_line": 1, "end_line": 2}},
    "T:test": {"id": "T:test", "type": "Test", "path": "tests/test_auth.py", "qualified_name": "tests.test_auth.test_login", "range": {"start_line": 1, "end_line": 2}},
}


def cands(*ids):
    return [{"node_id": i, "relevance_score": 1 - n / 10} for n, i in enumerate(ids)]


def outputs(graph_ids=("F:helper", "F:login", "T:test", "F:check"), f2p_ids=("F:check", "F:login")):
    return {"graph": {"candidates": cands(*graph_ids), "anchors": [{"node_id": "F:login", "symbol": "auth.login"}], "seconds": 0.1},
            "graph_f2p": {"candidates": cands(*f2p_ids), "anchors": [], "seconds": 0.2}}


def run_task(outs=None):
    return evaluate_graph_task(TASK, SOURCES, CorpusIndex(SOURCES), NODES, outs or outputs(), budget_tokens=200,
                               counter=words, counter_label="fake-words")


def test_two_arms_scored_with_shared_scoring_and_tests_excluded():
    result = run_task()
    g, f = result["arms"]["graph"], result["arms"]["graph_f2p"]
    assert [i["item_id"] for i in g["ranked"]] == ["F:helper", "F:login", "F:check"]           # Test dropped, order kept
    assert g["metrics"]["file_recall@3"] == 1.0 and g["metrics"]["function_recall@3"] == 1.0
    assert g["metrics"]["function_mrr"] == pytest.approx(1 / 3) and f["metrics"]["function_mrr"] == 1.0
    assert g["metrics"]["excluded_count"] == 1 and g["metrics"]["unmapped_count"] == 0
    assert f["metrics"]["no_anchors"] == 1 and g["metrics"]["no_anchors"] == 0
    assert g["scoring"]["rank_hash"] == g["rank_hash"] and result["corpus_hash"] == corpus_fingerprint(SOURCES)


def test_empty_candidates_is_a_miss_not_a_failure():
    result = run_task({"graph": {"candidates": [], "anchors": [], "seconds": 0.0},
                       "graph_f2p": {"candidates": [], "anchors": [], "seconds": 0.0}})
    metrics = result["arms"]["graph"]["metrics"]
    assert result["status"] == "SUCCEEDED" and metrics["file_recall@10"] == 0.0 and metrics["file_mrr"] == 0.0 and metrics["no_anchors"] == 1


def make_tar(path, files, commit=SHA, repo="o/r"):
    with tarfile.open(path, "w:gz") as bundle:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{repo.split('/')[-1]}-{commit}/{name}")
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))


def test_extract_python_tree_keeps_tests_and_bytes_and_is_idempotent(tmp_path):
    raw = b"# \xc4\x91\r\ndef f():\r\n    return 1\r\n"
    make_tar(tmp_path / "a.tar.gz", {"src/a.py": raw, "tests/test_a.py": b"def test_a(): pass\n", "README.md": b"x",
                                      "big.py": b"x" * 2_000_001})
    meta = extract_python_tree(tmp_path / "a.tar.gz", "o/r", SHA, tmp_path / "tree")
    assert meta["python_file_count"] == 2 and meta["skipped"] == [{"path": "big.py", "reason": "file_over_2MB"}]
    assert (tmp_path / "tree" / "src" / "a.py").read_bytes() == raw and (tmp_path / "tree" / "tests" / "test_a.py").exists()
    assert not (tmp_path / "tree" / "README.md").exists()
    assert extract_python_tree(tmp_path / "a.tar.gz", "o/r", SHA, tmp_path / "tree") == meta
    with pytest.raises(ValueError, match="different repo/commit"):
        extract_python_tree(tmp_path / "a.tar.gz", "o/r", "b" * 40, tmp_path / "tree")


def test_extract_rejects_foreign_archive_root(tmp_path):
    make_tar(tmp_path / "bad.tar.gz", {"a.py": b"x = 1\n"}, commit="c" * 40)
    with pytest.raises(ValueError, match="Archive root"):
        extract_python_tree(tmp_path / "bad.tar.gz", "o/r", SHA, tmp_path / "t2")


def test_cap_bm25_only_changes_rank_metrics():
    bm25 = evaluate_task(TASK, SOURCES, 200, counter=words, counter_label="fake-words")
    capped = cap_bm25(bm25, 1)
    assert capped["rank_items"] == 1 and capped["context_tokens"] == bm25["metrics"]["context_tokens"]
    assert capped["file_reach"] <= bm25["metrics"]["file_reach"]
    assert cap_bm25(bm25, 10_000)["file_recall@5"] == bm25["metrics"]["file_recall@5"]


def test_paired_stats_counts_and_ci_are_deterministic():
    base = {"a": {"file_recall@5": 0.0}, "b": {"file_recall@5": 0.5}, "c": {"file_recall@5": 1.0}}
    other = {"a": {"file_recall@5": 1.0}, "b": {"file_recall@5": 0.5}, "c": {"file_recall@5": 0.5}}
    stats = paired_stats(base, other, seed=1)["file_recall@5"]
    assert (stats["wins"], stats["ties"], stats["losses"], stats["n"]) == (1, 1, 1, 3)
    assert stats == paired_stats(base, other, seed=1)["file_recall@5"] and stats["ci95"][0] <= stats["mean_delta"] <= stats["ci95"][1]


def finish_run(directory, kind, task_results, summary_key, summary, config):
    record = {"run_id": directory.name, "kind": kind, "complete": True, "dataset_id": "d", "dataset_revision": "r", "config": config,
              "task_results": task_results, summary_key: summary}
    write_json(directory / "result.json", record)


def test_compare_runs_end_to_end_and_report(tmp_path):
    config = {"manifest_hash": "fixture-manifest", "budget_tokens": 200, "counter_label": "fake-words", "scoring_version": "retrieval-scoring-v1",
              "snippet_policy": {"max_snippet_lines": 80}, "counter_is_fallback": False, "snippet": 1}
    bm_dir, gr_dir = tmp_path / "bm", tmp_path / "gr"
    bm = evaluate_task(TASK, SOURCES, 200, counter=words, counter_label="fake-words")
    write_json(bm_dir / "tasks" / "t-2.json", bm)
    bm_row = {k: bm[k] for k in ("instance_id", "status", "metrics", "corpus_hash")} | {"artifact_hash": sha256((bm_dir / "tasks" / "t-2.json").read_bytes())}
    finish_run(bm_dir, "retrieval", [bm_row], "summary", aggregate_metrics([bm_row]) | {"completed_tasks": 1}, config)
    gr = run_task()
    write_json(gr_dir / "tasks" / "t-2.json", gr)
    gr_row = {"instance_id": "t-2", "status": "SUCCEEDED",
              "graph_build_seconds": 1.5, "artifact_hash": sha256((gr_dir / "tasks" / "t-2.json").read_bytes()),
              "arms": {a: {"metrics": {k: d["metrics"].get(k)} for k in ("file_recall@5", "function_recall@5")}
                       for a, d in gr["arms"].items()}}
    finish_run(gr_dir, "retrieval_graph", [gr_row], "summary_by_arm", {}, config)

    directory, report = compare_runs(bm_dir, gr_dir, tmp_path / "out", cap=1)
    assert report["status"] == "COMPARED" and report["paired_tasks"] == 1
    assert set(report["summaries"]) == {"bm25", "bm25_capped", "graph", "graph_f2p"}
    assert report["summaries"]["bm25"]["metrics"]["file_recall@5"]["mean"] == bm["metrics"]["file_recall@5"]
    assert report["primary_comparison"]["bm25_rank"] == "full"
    assert report["graph_diagnostics"]["graph_f2p"]["no_anchor_tasks"] == 1
    text = write_report(bm_dir, comparison=directory, destination=directory / "REPORT.md").read_text(encoding="utf-8")
    assert "graph+F2P" in text and "Delta theo cặp task" in text and "Task cần kiểm tay" in text and "AWAITING_GRAPH" not in text

    # fairness guards
    bad = json.loads((gr_dir / "result.json").read_text(encoding="utf-8"))
    bad["config"]["budget_tokens"] = 4000
    write_json(gr_dir / "result.json", bad)
    with pytest.raises(ValueError, match="budget_tokens"):
        compare_runs(bm_dir, gr_dir, tmp_path / "out2")


def test_source_tree_publication_retries_windows_sharing_error(tmp_path, monkeypatch):
    from pathlib import Path
    make_tar(tmp_path / 'a.tar.gz', {'src/a.py': b'def f(): return 1\n'})
    original = Path.rename
    attempts = []
    def temporarily_locked(self, target):
        attempts.append(self)
        if len(attempts) < 3:
            error = PermissionError('scanner has the directory open')
            error.winerror = 32
            raise error
        return original(self, target)
    monkeypatch.setattr(Path, 'rename', temporarily_locked)
    monkeypatch.setattr('vgar.evaluation.retrieval.graph_arm.time.sleep', lambda _: None)
    meta = extract_python_tree(tmp_path / 'a.tar.gz', 'o/r', SHA, tmp_path / 'tree')
    assert meta['python_file_count'] == 1
    assert len(attempts) == 3
