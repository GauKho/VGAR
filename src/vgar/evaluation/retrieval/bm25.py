"""Positive Robertson IDF BM25. Ranking never sees developer patches."""
import math
import re
from collections import Counter, defaultdict


def tokenize(text):
    terms = []
    for word in re.findall(r"[A-Za-z0-9_]+", text):
        terms.append(word.lower())
        split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", word)
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", split).replace("_", " ")
        pieces = split.lower().split()
        if pieces != [word.lower()]:
            terms.extend(pieces)
    return terms


def estimate_tokens(text):
    """Explicit estimator, not an LLM tokenizer: ceil(UTF-8 bytes / 4)."""
    return (len(text.encode("utf-8")) + 3) // 4


def context_text(item):
    return f"{item['path']}::{item.get('symbol', '')}\n{item['snippet']}" if "path" in item else item["snippet"]


class BM25:
    def __init__(self, documents, k1=1.2, b=0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        self.documents = list(documents)
        ids = [d["chunk_id"] for d in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate chunk IDs")
        self.k1, self.b = k1, b
        self.lengths, self.postings = [], defaultdict(list)
        for index, document in enumerate(self.documents):
            terms = Counter(tokenize(document["text"]))
            self.lengths.append(sum(terms.values()))
            for term, count in terms.items():
                self.postings[term].append((index, count))
        self.avgdl = sum(self.lengths) / len(self.lengths) if self.lengths else 0

    def search(self, query, limit=None):
        scores = defaultdict(float)
        n = len(self.documents)
        if not n or not self.avgdl:
            return []
        for term in sorted(set(tokenize(query))):
            hits = self.postings.get(term, ())
            if not hits:
                continue
            idf = math.log1p((n - len(hits) + 0.5) / (len(hits) + 0.5))
            for index, tf in hits:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[index] / self.avgdl)
                scores[index] += idf * tf * (self.k1 + 1) / (tf + norm)
        ordering = sorted(scores, key=lambda i: (-scores[i], self.documents[i]["chunk_id"]))
        if limit is not None:
            ordering = ordering[:limit]
        return [dict(self.documents[i], score=scores[i]) for i in ordering]


def pack_context(ranked, budget_tokens):
    if budget_tokens <= 0:
        raise ValueError("Token budget must be positive")
    items, total, skipped = [], 0, []
    for candidate in ranked:
        cost = estimate_tokens(context_text(candidate))
        if total + cost <= budget_tokens:
            items.append(dict(candidate, token_count=cost))
            total += cost
        else:
            skipped.append(candidate["chunk_id"])
    return {"items": items, "total_token_count": total, "token_budget": budget_tokens,
            "truncated": bool(skipped), "skipped_chunk_ids": skipped, "token_policy": "utf8_bytes_ceil_div4"}
