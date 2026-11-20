"""Embedding search baseline of R1 (proposal §13.1 "embedding search"; spec 2026-11-17 §2.2).

Ranks the same 80-line chunks as BM25 (``extract_chunks``) by cosine similarity between the problem statement and
each chunk, over the whole corpus. The model runs only when the runner is given ``--embedding-model``; tests use a
fake embedder.
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from array import array
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from vgar.evaluation.retrieval.chunks import extract_chunks
from vgar.evaluation.retrieval.scoring import RankItem, RankRecord

# Query prefix each model was trained with (model cards); another model needs --embedding-query-prefix.
QUERY_PREFIXES = {"nomic-ai/CodeRankEmbed": "Represent this query for searching relevant code: ",
                  "jinaai/jina-embeddings-v2-base-code": ""}
REVISION_SHA = re.compile(r"[0-9a-f]{40}")


class Embedder(Protocol):
    model_id: str
    revision: str
    query_prefix: str
    max_tokens: int

    def encode(self, texts: list[str], *, query: bool) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """A pinned sentence-transformers model; vectors are L2-normalised."""

    def __init__(self, model_id: str, revision: str, query_prefix: str, *, max_tokens: int, device: str = "cuda",
                 batch_size: int = 8):
        from sentence_transformers import (
            SentenceTransformer,  # only in the GPU environment, never in CI
        )

        self.model_id, self.revision, self.query_prefix, self.batch_size = model_id, revision, query_prefix, batch_size
        self.max_tokens = max_tokens
        self._model = SentenceTransformer(model_id, revision=revision, device=device, trust_remote_code=True)
        self._model.max_seq_length = max_tokens   # longer input is truncated; the default (8192) runs out of GPU memory

    def encode(self, texts: list[str], *, query: bool) -> list[list[float]]:
        inputs = [self.query_prefix + text for text in texts] if query else texts
        vectors = self._model.encode(inputs, batch_size=self.batch_size, normalize_embeddings=True,
                                     show_progress_bar=False)
        return [list(map(float, vector)) for vector in vectors]


class EmbeddingCache:
    """Chunk vectors keyed by model, revision, token limit, chunk id and snippet hash, in one SQLite file."""

    def __init__(self, folder: Path):
        Path(folder).mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(Path(folder) / "embeddings.sqlite")
        self._db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")

    @staticmethod
    def key(model_id: str, revision: str, max_tokens: int, chunk_id: str, snippet: str) -> str:
        snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()
        return hashlib.sha256(f"{model_id}\0{revision}\0{max_tokens}\0{chunk_id}\0{snippet_hash}".encode()).hexdigest()

    def get_many(self, keys: list[str]) -> dict[str, list[float]]:
        found: dict[str, list[float]] = {}
        for start in range(0, len(keys), 500):
            part = keys[start:start + 500]
            rows = self._db.execute(f"SELECT key, vector FROM vectors WHERE key IN ({','.join('?' * len(part))})", part)
            found.update((key, array("d", blob).tolist()) for key, blob in rows)
        return found

    def put_many(self, items: dict[str, list[float]]) -> None:
        with self._db:
            self._db.executemany("INSERT OR REPLACE INTO vectors VALUES (?, ?)",
                                 [(key, array("d", vector).tobytes()) for key, vector in items.items()])


EMBEDDING_SETTINGS = ("model_id", "revision", "query_prefix", "max_tokens")


def embedding_settings(embedder: Embedder | None) -> dict[str, str | int] | None:
    """Model id, revision, query prefix and token limit of a run, or ``None`` without the embedding arm."""
    if embedder is None:
        return None
    return {name: getattr(embedder, name) for name in EMBEDDING_SETTINGS}


def _cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / norm if norm else 0.0


def embedding_rank(instance_id: str, issue_text: str, sources: Mapping[str, str], embedder: Embedder, *,
                   cache: EmbeddingCache | None = None) -> RankRecord:
    """Every chunk of the corpus, most similar to the issue first; ties by path, then start line.

    Args:
        instance_id: Task id.
        issue_text: Problem statement (the only query, as for every arm).
        sources: Path -> source text.
        embedder: Model wrapper; ``encode(texts, query=...)``.
        cache: Optional vector cache shared across tasks.
    """
    chunks, failures = extract_chunks(dict(sources))
    if not chunks:
        raise ValueError("No parseable source chunks")
    keys = [EmbeddingCache.key(embedder.model_id, embedder.revision, embedder.max_tokens, c["chunk_id"], c["snippet"])
            for c in chunks]
    vectors = cache.get_many(keys) if cache is not None else {}
    hits = sum(key in vectors for key in keys)
    missing = [index for index, key in enumerate(keys) if key not in vectors]
    if missing:
        fresh = embedder.encode([chunks[index]["snippet"] for index in missing], query=False)
        new = {keys[index]: vector for index, vector in zip(missing, fresh)}
        vectors.update(new)
        if cache is not None:
            cache.put_many(new)
    query = embedder.encode([issue_text], query=True)[0]
    scored = sorted(((_cosine(query, vectors[key]), chunk) for key, chunk in zip(keys, chunks)),
                    key=lambda row: (-row[0], row[1]["path"], row[1]["start_line"]))
    items = [RankItem(item_id=c["chunk_id"], path=c["path"], kind=c["kind"], symbol=c["symbol"], start_line=c["start_line"],
                      end_line=c["end_line"], snippet=c["snippet"],
                      function_id=None if c["kind"] == "module" else c["parent_id"], score=score) for score, c in scored]
    return RankRecord(instance_id, "embedding", items,
                      meta={**embedding_settings(embedder), "corpus_chunks": len(chunks),
                            "cache_hits": hits, "parse_failures": failures})
