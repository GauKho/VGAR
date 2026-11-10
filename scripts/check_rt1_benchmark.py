"""RT-1 check over the self-made repair benchmark (spec RT-1 §6 item 1b).

For every task and config: ranked candidates, rank of the first gold file,
whether the ranking differs from the default config, and whether two runs
give the same result. The bundle is only read: each repository must already
be at the task's ``base_commit``.

Usage:
    python scripts/check_rt1_benchmark.py <bundle> --out report.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import (
    GraphContextRetriever,
    RetrievalConfig,
    ranking_config_hash,
)
from vgar.graph.task_overlay import TaskOverlayBuilder

BUDGET_TOKENS = 12000
# Tasks whose repository does not yet meet the condition of their flag (spec §6 item 1b).
DEFAULT_ONLY_TASKS = {
    "task-03": "no matching flag (common-anchor penalty dropped from RT-1)",
    "task-06": "pending repo fix: issue has no 'File \"...\", line N' traceback",
    "task-08": "pending repo fix: issue has no 'File \"...\", line N' traceback",
    "task-09": "pending repo fix: issue has no 'File \"...\", line N' traceback",
}
CONFIGS = {
    "default": RetrievalConfig(),
    "dependents": RetrievalConfig(use_component_dependents=True),
    "may_call_0_5": RetrievalConfig(may_call_factor=0.5),
    "trace": RetrievalConfig(use_trace_component=True),
    "all_on": RetrievalConfig(use_component_dependents=True, may_call_factor=0.5, use_trace_component=True),
}


def _head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


def _run(document: dict[str, Any], repo: Path, task: dict[str, Any], config: RetrievalConfig) -> list[dict[str, Any]]:
    overlay = TaskOverlayBuilder(document).build(task["instance_id"], task["problem_statement"], None)
    retriever = GraphContextRetriever(document, repo, count_tokens=lambda text: len(text) // 4,
                                      counter_label="rt1-benchmark:chars-div4", config=config)
    result = retriever.retrieve(sorted({anchor.node_id for anchor in overlay.grounding.anchors}), BUDGET_TOKENS,
                                issue_text=task["problem_statement"], overlay=overlay,
                                include=lambda node: not (node.get("path") or "").startswith("tests/"))
    return result.candidates


def check_benchmark(bundle: Path, configs: dict[str, RetrievalConfig]) -> dict[str, Any]:
    """Run every task of the bundle under every config.

    Args:
        bundle: Folder holding ``tasks/manifest.json`` and one folder per repository.
        configs: Named retrieval configs; ``default`` is the reference for ``changed_vs_default``.
    """
    tasks = json.loads((bundle / "tasks" / "manifest.json").read_text(encoding="utf-8"))
    graphs: dict[str, dict[str, Any]] = {}
    report: dict[str, Any] = {"budget_tokens": BUDGET_TOKENS,
                              "configs": {name: ranking_config_hash(config) for name, config in configs.items()},
                              "tasks": {}}
    for task in tasks:
        repo = bundle / task["repo"]
        if _head(repo) != task["base_commit"]:
            raise ValueError(f"{task['repo']} is not at base_commit {task['base_commit']} for {task['instance_id']}")
        if task["repo"] not in graphs:
            graphs[task["repo"]] = PythonGraphBuilder(repo_key=task["repo"], repository_revision=task["base_commit"]).build(repo)
        gold = set(task.get("changed_source_files", []))
        names = ["default"] if task["instance_id"] in DEFAULT_ONLY_TASKS else list(configs)
        row: dict[str, Any] = {"configs": {}}
        if task["instance_id"] in DEFAULT_ONLY_TASKS:
            row["default_only_reason"] = DEFAULT_ONLY_TASKS[task["instance_id"]]
        reference = None
        for name in names:
            first = _run(graphs[task["repo"]], repo, task, configs[name])
            second = _run(graphs[task["repo"]], repo, task, configs[name])
            node_ids = [candidate["node_id"] for candidate in first]
            reference = node_ids if name == "default" else reference
            gold_rank = next((rank for rank, candidate in enumerate(first, 1) if candidate["path"] in gold), None)
            row["configs"][name] = {
                "node_ids": node_ids, "gold_rank": gold_rank,
                "changed_vs_default": reference is not None and node_ids != reference,
                "repeatable": node_ids == [candidate["node_id"] for candidate in second],
            }
        report["tasks"][task["instance_id"]] = row
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = check_benchmark(args.bundle.resolve(), CONFIGS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for task_id, row in report["tasks"].items():
        cells = [f"{name}: rank={r['gold_rank']} changed={r['changed_vs_default']} repeatable={r['repeatable']}"
                 for name, r in row["configs"].items()]
        print(task_id, " | ".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
