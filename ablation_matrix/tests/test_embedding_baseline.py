"""Embedding baseline of R1 (plan 2026-11-17 Task 5; spec §2.2). A fake embedder; no model is loaded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_r1_ablation as run
from embedding_baseline import EmbeddingCache, embedding_rank

from vgar.evaluation.retrieval.chunks import extract_chunks


class Fake:
    model_id, revision, query_prefix = "fake", "r0", ""

    def __init__(self):
        self.encoded = 0

    def encode(self, texts, *, query):
        self.encoded += len(texts)
        return [[t.count("alpha"), t.count("beta"), t.count("gamma") + 0.001] for t in texts]


SOURCES = {"pkg/a.py": "def one():\n    alpha = 1\n", "pkg/b.py": "def two():\n    beta = 2\n"}


def test_ranks_every_chunk_by_cosine():
    record = embedding_rank("t", "beta problem", SOURCES, Fake())
    assert record.arm == "embedding" and record.items[0].path == "pkg/b.py"
    assert len(record.items) == record.meta["corpus_chunks"]
    assert record.meta["model_id"] == "fake" and record.meta["revision"] == "r0"


def test_same_chunks_as_bm25_corpus():
    ours = [item.item_id for item in embedding_rank("t", "alpha", SOURCES, Fake()).items]
    assert sorted(ours) == sorted(chunk["chunk_id"] for chunk in extract_chunks(dict(SOURCES))[0])


def test_ties_break_by_path_then_line():
    record = embedding_rank("t", "nothing", SOURCES, Fake())
    assert [item.path for item in record.items] == ["pkg/a.py", "pkg/b.py"]


def test_cache_is_keyed_by_model_and_revision(tmp_path):
    cache = EmbeddingCache(tmp_path)
    embedding_rank("t", "alpha", SOURCES, Fake(), cache=cache)
    other = Fake()
    other.revision = "r1"
    record = embedding_rank("t", "alpha", SOURCES, other, cache=cache)
    assert record.meta["cache_hits"] == 0
    again = Fake()
    hit = embedding_rank("t", "alpha", SOURCES, again, cache=cache)
    assert hit.meta["cache_hits"] == hit.meta["corpus_chunks"] and again.encoded == 1   # only the query


def test_runner_without_embedding_flag_has_no_embedding_arm():
    args = run.parse_args(["root", "manifest.json", "--out", "o", "--allow-fallback-counter"])
    assert args.embedding_model is None and "embedding" in run.TEXT_ARMS


def test_runner_pairs_include_embedding_baselines():
    for pair in (("no_task_trace", "embedding"), ("task_trace", "embedding"), ("task_trace_rt1", "embedding"),
                 ("task_trace_rt1", "bm25"), ("task_trace_rt1", "grep")):
        assert pair in run.PAIRS


SHA = "a" * 40
BASE = ["root", "manifest.json", "--out", "o", "--allow-fallback-counter"]


def test_meta_records_query_prefix():
    assert embedding_rank("t", "alpha", SOURCES, Fake()).meta["query_prefix"] == ""


@pytest.mark.parametrize("revision", ["main", "v1.0", "a" * 39, "A" * 40])
def test_runner_refuses_revision_that_is_not_a_sha(revision):
    with pytest.raises(SystemExit):
        run.parse_args(BASE + ["--embedding-model", "nomic-ai/CodeRankEmbed", "--embedding-revision", revision])


def test_runner_takes_query_prefix_from_known_model():
    coderank = run.parse_args(BASE + ["--embedding-model", "nomic-ai/CodeRankEmbed", "--embedding-revision", SHA])
    jina = run.parse_args(BASE + ["--embedding-model", "jinaai/jina-embeddings-v2-base-code", "--embedding-revision", SHA])
    assert coderank.embedding_query_prefix.startswith("Represent this query") and jina.embedding_query_prefix == ""


def test_runner_needs_prefix_for_unknown_model():
    with pytest.raises(SystemExit):
        run.parse_args(BASE + ["--embedding-model", "other/model", "--embedding-revision", SHA])
    args = run.parse_args(BASE + ["--embedding-model", "other/model", "--embedding-revision", SHA,
                                  "--embedding-query-prefix", "query: "])
    assert args.embedding_query_prefix == "query: "


def _artifact(tmp_path, arms, status="SUCCEEDED"):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"instance_id": "t", "status": status, "arms": arms}), encoding="utf-8")
    return path


SETTINGS = {"model_id": "m", "revision": SHA, "query_prefix": "q: "}


def test_resume_with_same_embedding_passes(tmp_path):
    run.check_resume_embedding(_artifact(tmp_path, {"bm25": {}, "embedding": {"meta": dict(SETTINGS, cache_hits=3)}}),
                               SETTINGS)


@pytest.mark.parametrize("change", [{"model_id": "other"}, {"revision": "b" * 40}, {"query_prefix": ""}])
def test_resume_with_other_embedding_stops(tmp_path, change):
    artifact = _artifact(tmp_path, {"bm25": {}, "embedding": {"meta": SETTINGS}})
    with pytest.raises(SystemExit):
        run.check_resume_embedding(artifact, dict(SETTINGS, **change))


def test_resume_adding_or_dropping_embedding_stops(tmp_path):
    with pytest.raises(SystemExit):
        run.check_resume_embedding(_artifact(tmp_path, {"bm25": {}}), SETTINGS)
    with pytest.raises(SystemExit):
        run.check_resume_embedding(_artifact(tmp_path, {"bm25": {}, "embedding": {"meta": SETTINGS}}), None)


def test_resume_ignores_failed_and_history_results(tmp_path):
    run.check_resume_embedding(_artifact(tmp_path, {}, status="FAILED"), SETTINGS)
    run.check_resume_embedding(_artifact(tmp_path, {"task_trace": {}}), SETTINGS)
