"""Text baselines of [P] §13.1 without a graph: grep/ripgrep and the file-neighbor heuristic.

Both rank the same 80-line chunks as the BM25 baseline (``extract_chunks``), so
``score_record`` scores every A0 baseline in the same units.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from retrieval_variants import issue_words

from vgar.evaluation.retrieval.chunks import extract_chunks
from vgar.evaluation.retrieval.scoring import RankItem, RankRecord, bm25_rank


def _item(chunk: dict[str, Any], score: float) -> RankItem:
    return RankItem(item_id=chunk["chunk_id"], path=chunk["path"], kind=chunk["kind"], symbol=chunk["symbol"],
                    start_line=chunk["start_line"], end_line=chunk["end_line"], snippet=chunk["snippet"],
                    function_id=None if chunk["kind"] == "module" else chunk["parent_id"], score=score)


def grep_rank(instance_id: str, issue_text: str, sources: Mapping[str, str]) -> RankRecord:
    """Chunks ranked like ``rg -i -w`` over the issue's identifier words, rarer words weighted higher.

    Args:
        instance_id: Task id.
        issue_text: Problem statement.
        sources: Path -> source text.
    """
    chunks, failures = extract_chunks(dict(sources))
    words = issue_words(issue_text)
    patterns = {word: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", re.IGNORECASE)
                for word in words}
    lines = {chunk["chunk_id"]: chunk["snippet"].splitlines() for chunk in chunks}
    hits = {word: {cid: sum(1 for line in rows if pattern.search(line)) for cid, rows in lines.items()}
            for word, pattern in patterns.items()}
    idf = {word: math.log(1 + len(chunks) / df) for word in words
           if (df := sum(1 for count in hits[word].values() if count))}
    scored = []
    for chunk in chunks:
        score = sum(hits[word][chunk["chunk_id"]] * weight for word, weight in idf.items())
        if score > 0:
            scored.append((-score, chunk["path"], chunk["start_line"], chunk))
    items = [_item(chunk, -negative) for negative, _, _, chunk in sorted(scored, key=lambda row: row[:3])]
    return RankRecord(instance_id, "grep", items, meta={"words": words, "parse_failures": failures})


def _mentioned_files(issue_text: str, paths: list[str]) -> list[str]:
    lowered = issue_text.replace("\\", "/").lower()
    found = []
    for path in paths:
        module = path.removesuffix(".py").removesuffix("/__init__").replace("/", ".").lower()
        if path.lower() in lowered or (module.count(".") >= 1 and module in lowered):
            found.append(path)
    return sorted(found)


def _distance(path: str, mentioned: list[str]) -> int:
    folder = PurePosixPath(path).parent.parts
    best = 10**6
    for other in mentioned:
        if other == path:
            return 0
        theirs = PurePosixPath(other).parent.parts
        common = 0
        for mine, their in zip(folder, theirs):
            if mine != their:
                break
            common += 1
        best = min(best, 1 + (len(folder) - common) + (len(theirs) - common))
    return best


def neighbor_rank(instance_id: str, issue_text: str, sources: Mapping[str, str]) -> RankRecord:
    """Files the issue names first, then files by folder distance from them; BM25 orders within a distance.

    Args:
        instance_id: Task id.
        issue_text: Problem statement.
        sources: Path -> source text.
    """
    base = bm25_rank(instance_id, issue_text, sources)
    mentioned = _mentioned_files(issue_text, sorted(sources))
    if not mentioned:
        return RankRecord(instance_id, "neighbor", base.items,
                          meta={**base.meta, "mentioned_files": [], "fallback": "bm25"})
    order = {item.item_id: rank for rank, item in enumerate(base.items)}
    chunks, _ = extract_chunks(dict(sources))
    bm25_items = {item.item_id: item for item in base.items}
    every = [bm25_items.get(chunk["chunk_id"]) or _item(chunk, 0.0) for chunk in chunks]
    items = sorted(every, key=lambda item: (_distance(item.path, mentioned), order.get(item.item_id, len(order)),
                                            item.path, item.start_line))
    return RankRecord(instance_id, "neighbor", items, meta={**base.meta, "mentioned_files": mentioned, "fallback": None})
