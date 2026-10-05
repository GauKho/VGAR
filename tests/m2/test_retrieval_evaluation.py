from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.evaluation.retrieval import evaluation
from vgar.evaluation.retrieval.evaluation import evaluate_manifest, evaluate_task
from vgar.evaluation.retrieval.evidence import sha256
from vgar.evaluation.retrieval.report import write_report

AUTH = 'def login(user, password):\n    return check(user, password)\n\n\ndef check(user, password):\n    return user == "root"\n'
OTHER = "def helper():\n    return 1\n"
SOURCES = {"src/auth.py": AUTH, "src/other.py": OTHER}
PATCH = ("--- a/src/auth.py\n+++ b/src/auth.py\n@@ -5,2 +5,2 @@\n def check(user, password):\n"
         '-    return user == "root"\n+    return user == "admin"\n')
QUERY = "login check password user fails"
SHA = "a" * 40
words = lambda text: len(text.split())


def task(patch=PATCH):
    return {"instance_id": "t-1", "repo": "o/r", "base_commit": SHA, "problem_statement": QUERY, "patch": patch}


def test_one_rank_two_modes_and_label_recorded():
    result = evaluate_task(task(), SOURCES, 200, counter=words, counter_label="fake-words")
    assert result["scoring"]["packed"]["counter_label"] == "fake-words"
    assert result["scoring"]["rank_hash"] == result["rank_hash"]
    assert len(result["rank_order"]) == result["ranking_total_count"] <= len(result["candidate_map"])  # zero-score chunks are unranked
    m = result["metrics"]
    assert m["file_recall@3"] == 1.0 and m["function_recall@3"] == 1.0
    assert m["file_reach"] == 1.0 and m["packed_gold_function_in_context"] == 1.0
    assert m["context_tokens"] <= 200 and m["packed_tokens_to_first_gold_function"] is not None
    assert "bm25_rank" not in json.dumps(m)                               # flat numeric view only


def test_ranking_never_depends_on_patch():
    a = evaluate_task(task(), SOURCES, 200, counter=words, counter_label="x")
    other = PATCH.replace("src/auth.py", "src/other.py").replace('-    return user == "root"\n+    return user == "admin"\n',
                                                              "-    return 1\n+    return 2\n").replace(
        " def check(user, password):\n", " def helper():\n").replace("@@ -5,2 +5,2 @@", "@@ -1,2 +1,2 @@")
    b = evaluate_task(task(other), SOURCES, 200, counter=words, counter_label="x")
    assert a["rank_hash"] == b["rank_hash"] and a["rank_order"] == b["rank_order"]
    assert a["gold"]["gold_files"] != b["gold"]["gold_files"]             # different gold, identical ranking


def test_fallback_counter_is_labelled_and_custom_needs_label():
    result = evaluate_task(task(), SOURCES, 200)
    assert result["scoring"]["packed"]["counter_label"].startswith("FALLBACK")
    with pytest.raises(ValueError):
        evaluate_task(task(), SOURCES, 200, counter=words)


def test_manifest_run_report_and_resume(tmp_path: Path, monkeypatch, capsys):
    gold = tmp_path / "data" / "gold" / "patches"
    gold.mkdir(parents=True)
    (gold / "t-2.patch").write_text(PATCH, encoding="utf-8", newline="\n")
    row = {"instance_id": "t-2", "split": "dev", "repo": "o/r", "base_commit": SHA, "problem_statement": QUERY,
           "query_hash": sha256(QUERY), "patch_hash": sha256(PATCH), "gold_patch_path": "data/gold/patches/t-2.patch"}
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"dataset_id": "d", "dataset_revision": "r", "split": "dev", "tasks": [row]}), encoding="utf-8")
    monkeypatch.setattr(evaluation, "read_repository_sources", lambda r, root, network=True: (SOURCES, {"source_backend": "test"}))

    directory, record = evaluate_manifest(tmp_path, manifest, budget_tokens=200)           # fallback counter
    assert record["status"] == "SUCCEEDED" and record["config"]["counter_is_fallback"] is True
    assert "WARNING" in capsys.readouterr().out
    report = write_report(directory).read_text(encoding="utf-8")
    assert "CẢNH BÁO" in report and "Số chính" in report and "Số phụ" in report and "AWAITING_GRAPH" in report

    d2, r2 = evaluate_manifest(tmp_path, manifest, budget_tokens=200, counter=words, counter_label="fake-words")
    assert "CẢNH BÁO" not in write_report(d2).read_text(encoding="utf-8")
    d3, r3 = evaluate_manifest(tmp_path, manifest, budget_tokens=200, counter=words, counter_label="fake-words", resume=d2)
    assert r3["task_results"][0]["metrics"] == r2["task_results"][0]["metrics"]
    with pytest.raises(ValueError, match="mismatch"):                                       # counter change invalidates resume
        evaluate_manifest(tmp_path, manifest, budget_tokens=200, resume=d2)