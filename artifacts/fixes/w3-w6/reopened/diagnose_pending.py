"""Bounded diagnostics for reopened Week 3-6 failures; never edit old evidence."""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.evidence import new_run, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    args = parser.parse_args()
    run, record = new_run(Path(__file__).parent / "diagnostics", "pending-root-cause")
    started = time.perf_counter()
    old = ROOT / "results/retrieval/20261007T014445273889Z-664d06a6c1c0"
    record.update(task_id=args.task_id, prior_run=str(old))
    write_json(run / "result.json", record)
    try:
        attempts = sorted((old / "attempts" / args.task_id).glob("*/request.json"))
        if len(attempts) != 1:
            raise ValueError("Expected exactly one historical attempt")
        request = json.loads(attempts[0].read_text(encoding="utf-8"))
        if args.task_id.startswith("pylint"):
            from vgar.graph.builder import PythonGraphBuilder
            from vgar.evaluation.retrieval.graph_arm import verify_python_tree
            # Retain raw graph in memory only to inspect the validator's failure.
            candidates = []
            for marker in (ROOT / "data/repositories/trees/rebuilt").glob("*/.vgar_tree.json"):
                meta = json.loads(marker.read_text(encoding="utf-8"))
                if meta.get("repo") == request["row"]["repo"] and meta.get("commit") == request["row"]["base_commit"]:
                    candidates.append(marker.parent)
            if not candidates:
                raise ValueError("No preserved raw tree")
            tree = candidates[0]
            record["tree"] = str(tree)
            record["tree_verified"] = verify_python_tree(tree)
            builder = PythonGraphBuilder(repo_key=request["row"]["repo"].replace("/", "__"),
                                         repository_revision=request["row"]["base_commit"], use_jedi=False)
            try:
                builder.build(tree)
            except Exception as exc:
                record["observed_error"] = {"class": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
            grouped = collections.defaultdict(list)
            for edge in builder.edges:
                grouped[edge["id"]].append(edge)
            record["duplicates"] = [
                {"edges": values, "source": builder.nodes_by_id.get(values[0]["source_id"]),
                 "target": builder.nodes_by_id.get(values[0]["target_id"])}
                for values in grouped.values() if len(values) > 1
            ]
            record["status"] = "PASS" if record["duplicates"] else "NO_REPRODUCTION"
        else:
            raise ValueError("This diagnostic currently supports the duplicate-edge case")
        record["exit_code"] = 0 if record["status"] == "PASS" else 1
    except Exception as exc:
        record.update(status="ERROR", exit_code=1, error_class=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    record.update(complete=True, duration_seconds=time.perf_counter() - started)
    write_json(run / "result.json", record)
    print(json.dumps({"evidence": str(run / "result.json"), "status": record["status"], "duplicates": record.get("duplicates")}, ensure_ascii=False))
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
