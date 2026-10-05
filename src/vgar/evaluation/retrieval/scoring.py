"""Retrieval scoring adapter: ONE ranked list per (task, arm) -> TWO scoring modes.

* mode ``rank``   (primary)   - Recall@k / MRR on the full ranking, independent of any budget.
* mode ``packed`` (secondary) - what an agent would actually see after greedy packing under a
                                token budget with ONE shared counter and ONE snippet policy.

Both modes read the same ``RankRecord``; retrieval is never run twice.
Stdlib + sibling M2 modules only (no import of vgar.graph / M1), so the package docstring
"never imports VGAR" stays true.  M1 data enters as plain dicts (graph document nodes and
``RetrievalResult.candidates``).

Unit rules (decision log W5-6):
  Function / Method   -> counted at file level AND function level
  Class / File / Module -> file level only
  Test                -> kept in the graph for traversal, EXCLUDED from the scored rank
  anything that cannot be mapped is recorded in ``unmapped`` / ``excluded``; it never fails the task.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from .bm25 import BM25
from .chunks import entities, extract_chunks, is_source, normalize_path, physical_lines
from .metrics import evaluate_ranking

TokenCounter = Callable[[str], int]
SCORING_VERSION = "retrieval-scoring-v1"

FUNCTION_KINDS = frozenset({"function", "method"})
FILE_ONLY_KINDS = frozenset({"class", "file", "module"})
EXCLUDED_KINDS = frozenset({"test"})


# --------------------------------------------------------------------------- data model
@dataclass(frozen=True)
class RankItem:
    item_id: str                      # BM25 chunk_id or M1 node_id
    path: str
    kind: str                         # function | method | class | file | module
    symbol: str
    start_line: int
    end_line: int
    snippet: str = field(repr=False, compare=False, default="")
    function_id: str | None = None    # canonical BM25 parent_id; None => file level only
    score: float | None = None

    @property
    def group(self) -> str:
        return self.function_id or self.item_id


@dataclass
class RankRecord:
    instance_id: str
    arm: str
    items: list[RankItem]
    excluded: list[dict[str, Any]] = field(default_factory=list)   # dropped on purpose (tests, not in corpus)
    unmapped: list[dict[str, Any]] = field(default_factory=list)   # kept, but a level could not be resolved
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def rank_hash(self) -> str:
        payload = json.dumps([[i.item_id, i.path, i.function_id] for i in self.items], separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_json(self, include_snippets: bool = False) -> dict[str, Any]:
        rows = []
        for rank, item in enumerate(self.items, 1):
            row = {"rank": rank, "item_id": item.item_id, "path": item.path, "kind": item.kind,
                   "symbol": item.symbol, "function_id": item.function_id, "score": item.score,
                   "lines": [item.start_line, item.end_line],
                   "snippet_sha256": "sha256:" + hashlib.sha256(item.snippet.encode("utf-8")).hexdigest()}
            if include_snippets:
                row["snippet"] = item.snippet
            rows.append(row)
        return {"instance_id": self.instance_id, "arm": self.arm, "scoring_version": SCORING_VERSION,
                "rank_hash": self.rank_hash, "items": rows, "excluded": self.excluded,
                "unmapped": self.unmapped, "meta": self.meta}


# --------------------------------------------------------------------------- corpus identity
class CorpusIndex:
    """Function identities of the ``is_source`` corpus, built with the SAME ``entities()`` as gold labels."""

    def __init__(self, sources: Mapping[str, str]):
        self.definitions: dict[str, list[dict[str, Any]]] = {}
        self.parse_failures: list[str] = []
        for raw, text in sorted(sources.items()):
            path = normalize_path(raw)
            if not is_source(path):
                continue
            try:
                self.definitions[path] = entities(path, text)
            except (SyntaxError, ValueError):
                self.parse_failures.append(path)

    @property
    def paths(self) -> frozenset[str]:
        return frozenset(self.definitions)

    def resolve_function(self, path: str, symbol: str, start_line: int, end_line: int) -> tuple[str | None, str | None]:
        defs = self.definitions.get(path)
        if defs is None:
            return None, "PATH_NOT_IN_CORPUS"
        same = [d for d in defs if d["symbol"] == symbol]
        if len(same) > 1:   # conditional defs / property setters: BM25 suffixes parent_id with @definition:s:e
            same = [d for d in same if d["start_line"] <= start_line and end_line <= d["end_line"]]
            if len(same) > 1:
                return None, "AMBIGUOUS_FUNCTION"
        return (same[0]["parent_id"], None) if same else (None, "NO_FUNCTION_MATCH")


def make_include(corpus: CorpusIndex) -> Callable[[Mapping[str, Any]], bool]:
    """THE scoring filter.  Pass the same predicate to ``GraphContextRetriever.retrieve(include=...)``
    once M1 adds it, so Test nodes and non-corpus files never consume rank slots or budget."""
    paths = corpus.paths
    return lambda node: str(node.get("type", "")).lower() not in EXCLUDED_KINDS and node.get("path") in paths


# --------------------------------------------------------------------------- arm -> RankRecord
def bm25_rank(instance_id: str, query: str, sources: Mapping[str, str], *, k1: float = 1.2, b: float = 0.75,
              chunks: list[dict[str, Any]] | None = None, failures: list[dict[str, Any]] | None = None) -> RankRecord:
    """Pass ``chunks``/``failures`` when the caller already ran ``extract_chunks`` (avoids parsing twice)."""
    if chunks is None:
        chunks, failures = extract_chunks(dict(sources))
    if not chunks:
        raise ValueError("No parseable source chunks")
    items = [RankItem(item_id=c["chunk_id"], path=c["path"], kind=c["kind"], symbol=c["symbol"],
                      start_line=c["start_line"], end_line=c["end_line"], snippet=c["snippet"],
                      function_id=None if c["kind"] == "module" else c["parent_id"], score=c["score"])
             for c in BM25(chunks, k1=k1, b=b).search(query)]
    return RankRecord(instance_id, "bm25", items, meta={"parse_failures": failures or [], "k1": k1, "b": b,
                                                        "corpus_chunks": len(chunks)})


def graph_rank(instance_id: str, candidates: Iterable[Mapping[str, Any]], nodes: Mapping[str, Mapping[str, Any]],
               sources: Mapping[str, str], corpus: CorpusIndex, *, arm: str = "graph",
               include: Callable[[Mapping[str, Any]], bool] | None = None) -> RankRecord:
    """``candidates`` = ``RetrievalResult.candidates`` (already sorted by M1; never re-sorted here).
    ``nodes``      = {node_id: node} from the graph document (candidates carry no node type)."""
    candidates = list(candidates)
    items: list[RankItem] = []
    excluded: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    line_cache: dict[str, list[str]] = {}
    keep = include or make_include(corpus)
    for cand in candidates:
        node_id = cand["node_id"]
        node = nodes.get(node_id)
        if node is None:
            unmapped.append({"item_id": node_id, "scope": "item", "reason": "NODE_NOT_IN_DOCUMENT"})
            continue
        kind = str(node["type"]).lower()
        if kind in EXCLUDED_KINDS:
            excluded.append({"item_id": node_id, "reason": "TEST_EXCLUDED"})
            continue
        if kind not in FUNCTION_KINDS | FILE_ONLY_KINDS:
            excluded.append({"item_id": node_id, "reason": "UNSUPPORTED_KIND", "kind": kind})
            continue
        try:
            path = normalize_path(node["path"])
        except ValueError:
            excluded.append({"item_id": node_id, "reason": "INVALID_PATH"})
            continue
        if path not in corpus.paths or path not in sources or not keep(node):
            excluded.append({"item_id": node_id, "reason": "NOT_IN_CORPUS", "path": path})
            continue
        span = node.get("range") or {}
        start, end = int(span.get("start_line", 1)), int(span.get("end_line", 1))
        if path not in line_cache:
            line_cache[path] = physical_lines(sources[path], keepends=True)
        snippet = "".join(line_cache[path][start - 1:end])        # full physical lines, same policy as BM25 chunks
        function_id = None
        if kind in FUNCTION_KINDS:
            function_id, reason = corpus.resolve_function(path, node["qualified_name"], start, end)
            if reason:   # keep the item at file level; only the function level is lost
                unmapped.append({"item_id": node_id, "scope": "function_level", "reason": reason,
                                 "symbol": node["qualified_name"]})
        items.append(RankItem(item_id=node_id, path=path, kind=kind, symbol=node["qualified_name"],
                              start_line=start, end_line=end, snippet=snippet, function_id=function_id,
                              score=cand.get("relevance_score")))
    return RankRecord(instance_id, arm, items, excluded, unmapped,
                      meta={"candidates_in": len(candidates)})


# --------------------------------------------------------------------------- packing (shared by every arm)
def render(item: RankItem, max_snippet_lines: int | None, header: bool) -> str:
    body = "".join(item.snippet.splitlines(keepends=True)[:max_snippet_lines]) if max_snippet_lines else item.snippet
    return f"{item.path}::{item.symbol}\n{body}" if header and item.symbol else body


def pack_items(items: list[RankItem], budget_tokens: int, counter: TokenCounter, *,
               max_snippet_lines: int | None = 80, header: bool = True) -> dict[str, Any]:
    """Greedy, rank order, skip-and-continue (identical to both existing packers).
    An item is skipped as redundant if it overlaps an already packed item of a DIFFERENT group
    (class vs its method); windows of the same function are allowed."""
    if isinstance(budget_tokens, bool) or budget_tokens < 1:
        raise ValueError("budget_tokens must be positive")
    packed: list[tuple[RankItem, int]] = []
    skipped = {"token_budget": 0, "overlap": 0}
    total = 0
    for item in items:
        if any(o.path == item.path and o.group != item.group and item.start_line <= o.end_line and o.start_line <= item.end_line
               for o, _ in packed):
            skipped["overlap"] += 1
            continue
        cost = counter(render(item, max_snippet_lines, header))
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise TypeError("counter must return a nonnegative int")
        if total + cost <= budget_tokens:
            packed.append((item, cost))
            total += cost
        else:
            skipped["token_budget"] += 1
    return {"items": packed, "total_tokens": total, "skipped": skipped}


def _first_gold_tokens(packed: list[tuple[RankItem, int]], hit: Callable[[RankItem], bool]) -> int | None:
    running = 0
    for item, cost in packed:
        running += cost
        if hit(item):
            return running
    return None


# --------------------------------------------------------------------------- the two scoring modes
def score_record(record: RankRecord, gold: Mapping[str, Any], *, budget_tokens: int, counter: TokenCounter,
                 counter_label: str, max_snippet_lines: int | None = 80, header: bool = True,
                 ks: tuple[int, ...] = (1, 3, 5, 10, 20)) -> dict[str, Any]:
    gold_files = set(gold["gold_files"])
    gold_funcs = set(gold["gold_functions"]) if gold.get("function_labels_complete", True) else set()

    # mode 1: full rank.  A gold item the arm never reached is a miss (rank = inf, MRR 0), NOT a dropped task.
    rows = [{"path": i.path, "kind": i.kind, **({"parent_id": i.function_id} if i.function_id else {})}
            for i in record.items]
    rank_metrics = evaluate_ranking(rows, gold, ks)
    rank_files = {i.path for i in record.items}
    rank_funcs = {i.function_id for i in record.items if i.function_id}
    rank_mode = {
        "metrics": rank_metrics,
        "reach": {"file": len(gold_files & rank_files) / len(gold_files) if gold_files else None,
                  "function": len(gold_funcs & rank_funcs) / len(gold_funcs) if gold_funcs else None},
        "size": {"items": len(record.items), "files": len(rank_files), "functions": len(rank_funcs)},
    }

    # mode 2: packed context under the shared counter/budget (set-based, no k).
    packed = pack_items(record.items, budget_tokens, counter, max_snippet_lines=max_snippet_lines, header=header)
    p_files = {i.path for i, _ in packed["items"]}
    p_funcs = {i.function_id for i, _ in packed["items"] if i.function_id}
    packed_metrics = {
        "gold_file_in_context": len(gold_files & p_files) / len(gold_files) if gold_files else None,
        "gold_function_in_context": len(gold_funcs & p_funcs) / len(gold_funcs) if gold_funcs else None,
        "all_gold_files_in_context": int(gold_files <= p_files) if gold_files else None,
        "all_gold_functions_in_context": int(gold_funcs <= p_funcs) if gold_funcs else None,
        "total_tokens": packed["total_tokens"],
        "tokens_to_first_gold_file": _first_gold_tokens(packed["items"], lambda i: i.path in gold_files),
        "tokens_to_first_gold_function": _first_gold_tokens(packed["items"], lambda i: i.function_id in gold_funcs),
        "items_packed": len(packed["items"]), "skipped": packed["skipped"],
        "truncated": packed["skipped"]["token_budget"] > 0,   # overlap skips are redundancy, not truncation
    }
    return {"instance_id": record.instance_id, "arm": record.arm, "scoring_version": SCORING_VERSION,
            "rank_hash": record.rank_hash,
            "rank": rank_mode,
            "packed": {"budget_tokens": budget_tokens, "counter_label": counter_label,
                       "snippet_policy": {"max_snippet_lines": max_snippet_lines, "header": header,
                                          "overlap": "skip_if_overlaps_different_group"},
                       "metrics": packed_metrics},
            "excluded_count": len(record.excluded), "unmapped": record.unmapped,
            "excluded_reasons": _count(e["reason"] for e in record.excluded)}


def _count(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


# --------------------------------------------------------------------------- flat view for aggregation / reports
FALLBACK_COUNTER_LABEL = "FALLBACK:utf8_bytes_ceil_div4"


def bytes_div4_counter(text: str) -> int:
    """Fallback only (decision W5-6). Not a model tokenizer; results using it must be flagged."""
    return (len(text.encode("utf-8")) + 3) // 4


def flat_metrics(scored: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten ``score_record`` output into the numeric dict ``aggregate_metrics`` expects.
    Every arm (BM25 and Graph) must go through this so report keys are identical."""
    out: dict[str, Any] = dict(scored["rank"]["metrics"])
    out["file_reach"] = scored["rank"]["reach"]["file"]
    out["function_reach"] = scored["rank"]["reach"]["function"]
    out["rank_items"] = scored["rank"]["size"]["items"]
    for key, value in scored["packed"]["metrics"].items():
        if key == "skipped":
            out["packed_skipped_token_budget"] = value["token_budget"]
            out["packed_skipped_overlap"] = value["overlap"]
        elif key == "total_tokens":
            out["context_tokens"] = value
        else:
            out[f"packed_{key}"] = int(value) if isinstance(value, bool) else value
    out["unmapped_count"] = len(scored["unmapped"])
    out["excluded_count"] = scored["excluded_count"]
    return out