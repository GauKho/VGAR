"""TV2 TR-1: trace link precision and recall over a manifest, with the gold patch files as approximate labels.

Example (from the project root):
  python scripts/measure_trace_links.py --manifest data/manifest.json --repositories /path/to/checkouts --output trace.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.dataset import require_split, validate_task
from vgar.evaluation.trace_quality import (
    TraceScore,
    score_task,
    summarise,
)
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.task_overlay import TaskOverlayBuilder


def measure(manifest: dict[str, Any], repositories: Path, allow_heldout: bool = False) -> dict[str, Any]:
    """Score every task of a manifest whose checkout is at its base commit.

    Args:
        manifest: A manifest in the format of scripts/prepare_manifest.py.
        repositories: Directory holding one checkout per ``instance_id``.
        allow_heldout: Also accept held-out tasks, which still need the signed protocol freeze.
    """
    tasks = manifest.get("tasks")
    if not tasks:
        raise ValueError("Manifest tasks must be nonempty")
    for task in tasks:
        validate_task(task)
    require_split(manifest, allowed=("dev", "heldout") if allow_heldout else ("dev",))
    if len({task["instance_id"] for task in tasks}) != len(tasks):
        raise ValueError("Duplicate tasks in manifest")
    scores: list[TraceScore] = []
    skipped: list[dict[str, str]] = []
    for task in tasks:
        checkout = repositories / task["instance_id"]
        reason = _skip_reason(checkout, task["base_commit"])
        if reason:
            skipped.append({"instance_id": task["instance_id"], "reason": reason})
            continue
        document = PythonGraphBuilder(repo_key=f"trace/{task['instance_id']}", repository_revision=task["base_commit"]).build(checkout)
        # No failing tests: the agent does not have them when it receives a task.
        overlay = TaskOverlayBuilder(document).build(task["instance_id"], task["problem_statement"])
        scores.append(score_task(document, overlay, task["changed_source_files"]))
    return {"tasks": [asdict(score) for score in scores], "skipped": skipped, "summary": summarise(scores)}


def _skip_reason(checkout: Path, base_commit: str) -> str | None:
    if not checkout.is_dir():
        return "missing_checkout"
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return None if head.stdout.strip() == base_commit else "head_mismatch"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure trace link precision and recall")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True, help="directory with one checkout per instance_id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-heldout", action="store_true", help="also accept held-out tasks; needs the signed protocol freeze")
    args = parser.parse_args(argv)
    result = measure(json.loads(args.manifest.read_text(encoding="utf-8")), args.repositories, args.allow_heldout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"tasks={len(result['tasks'])} skipped={len(result['skipped'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
