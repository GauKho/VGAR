"""Component boundary quality (proposal §13.2; spec 2026-11-17 §1.2): a human marks sampled Components.

Each sampled Component gets one label: ``correct`` (the boundary is right), ``merge`` (it should be joined with
another component) or ``split`` (it holds more than one component). The score is the share of ``correct``.
"""
from __future__ import annotations

import csv
import random
import statistics
from pathlib import Path

LABELS = ("correct", "merge", "split")
COLUMNS = ["component_id", "repo", "name", "files", "label", "note"]


def sample_components(documents: dict[str, dict], per_repo: int = 5, seed: int = 0) -> list[dict]:
    """Up to ``per_repo`` Components of each repository's graph, sorted by id then shuffled with ``seed``.

    Args:
        documents: Repository -> graph document of its task.
        per_repo: Components kept per repository.
        seed: Shuffle seed.
    """
    rng = random.Random(seed)
    sampled = []
    for repo in sorted(documents):
        document = documents[repo]
        components = sorted((n for n in document["nodes"] if n["type"] == "Component"), key=lambda n: n["id"])
        rng.shuffle(components)
        sampled.extend({"component_id": n["id"], "repo": repo, "task_id": document["repo_key"],
                        "name": n["qualified_name"], "files": list(n["properties"]["files"])}
                       for n in components[:per_repo])
    return sampled


def write_component_sheet(path: Path, sampled: list[dict]) -> None:
    """``components.csv`` with an empty ``label`` column; files are joined by ``;``."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        for item in sampled:
            writer.writerow({"component_id": item["component_id"], "repo": item["repo"], "name": item["name"],
                             "files": ";".join(item["files"]), "label": "", "note": ""})


def read_component_sheet(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def boundary_quality(rows: list[dict], seed: int = 0, rounds: int = 2000) -> dict:
    """Counts per label, share of ``correct`` and its bootstrap CI95.

    Raises:
        ValueError: A label is empty or not one of ``correct``, ``merge``, ``split``.
    """
    labels = ["".join(row["label"].split()).lower() for row in rows]
    bad = [index for index, label in enumerate(labels) if label not in LABELS]
    if bad:
        raise ValueError(f"empty or unknown labels at rows {bad}; use one of {LABELS}")
    correct = [1.0 if label == "correct" else 0.0 for label in labels]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(correct) for _ in correct) for _ in range(rounds))
    return {"n": len(labels), **{label: labels.count(label) for label in LABELS},
            "correct_rate": statistics.fmean(correct), "ci95": [means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]]}
