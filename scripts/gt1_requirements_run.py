"""GT-1 real run: Requirement-family facts on the SWE-bench dev issues (problem_statement only).

Usage: python scripts/gt1_requirements_run.py <swe-bench parquet> <dev manifest json> [--examples N]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

import pyarrow.parquet as pq

from vgar.graph.task_graph import extract_task_facts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("parquet")
    parser.add_argument("manifest")
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args()
    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    tasks = manifest.get("tasks", manifest)
    ids = {task["instance_id"] if isinstance(task, dict) else task for task in tasks}
    table = pq.read_table(args.parquet, columns=["instance_id", "problem_statement"]).to_pylist()
    issues = {row["instance_id"]: row["problem_statement"] for row in table if row["instance_id"] in ids}
    totals: Counter[str] = Counter()
    having: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    examples: dict[str, list[str]] = {"Requirement": [], "Constraint": [], "UserStory": []}
    for instance_id, text in sorted(issues.items()):
        facts = extract_task_facts(text)
        counts = {"Requirement": len(facts.requirements), "Constraint": len(facts.constraints),
                  "UserStory": len(facts.stories), "Actor": len({story.actor for story in facts.stories}),
                  "DEPENDS_ON": sum(kind == "DEPENDS_ON" for *_, kind in facts.requirement_links),
                  "CONFLICTS_WITH": sum(kind == "CONFLICTS_WITH" for *_, kind in facts.requirement_links)}
        totals.update(counts)
        having.update(name for name, count in counts.items() if count)
        sources.update(item.source for item in facts.requirements)
        kinds.update(item.kind for item in facts.constraints)
        for name, items in (("Requirement", facts.requirements), ("Constraint", facts.constraints), ("UserStory", facts.stories)):
            if items and len(examples[name]) < args.examples:
                examples[name].append(f"{instance_id}: {items[0].text}")
    print(json.dumps({"issues": len(issues), "totals": totals, "issues_with": having, "requirement_sources": sources,
                      "constraint_kinds": kinds, "examples": examples}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
