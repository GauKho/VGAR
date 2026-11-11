"""Component-level recall, since RQ2 asks about file/function/component ([P] line 85)."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

KS = (1, 3, 5)


def component_metrics(document: Mapping[str, Any], ranked_paths: Iterable[str], *,
                      gold_files: Iterable[str]) -> dict[str, float | None]:
    """Recall@k and MRR of gold components over a ranked list of file paths.

    Gold components are the G_arch Components whose files touch a gold file. A
    ranked path counts as its Component; paths outside every Component count as
    a miss at that rank. Without Components every value is None.

    Args:
        document: Graph document holding the Component nodes.
        ranked_paths: File path of each ranked item, best first (repeats allowed).
        gold_files: Files changed by the gold patch.
    """
    owner = {path: node["id"] for node in document["nodes"] if node["type"] == "Component"
             for path in node["properties"]["files"]}
    gold = {owner[path] for path in gold_files if path in owner}
    empty: dict[str, float | None] = {f"component_recall@{k}": None for k in KS} | {"component_mrr": None}
    if not owner or not gold:
        return empty
    seen: list[str | None] = []
    for path in ranked_paths:
        component = owner.get(path)
        if component is None or component not in seen:
            seen.append(component)
    found = {k: {c for c in seen[:k] if c in gold} for k in KS}
    first = next((rank for rank, component in enumerate(seen, 1) if component in gold), None)
    return {f"component_recall@{k}": len(found[k]) / len(gold) for k in KS} | {
        "component_mrr": 1 / first if first else 0.0}
