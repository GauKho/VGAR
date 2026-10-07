"""Read-only integrity/parity/timing analysis of saved runs; no new benchmark."""
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from vgar.evaluation.retrieval.compare import DELTA_METRICS
from vgar.evaluation.retrieval.evidence import new_run, sha256, source_fingerprint, write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    directory, evidence = new_run(Path(__file__).parent / "closure", "reopened-integrity-parity-analysis")
    run = ROOT / "results/retrieval/20261007T114731162059Z-f27e07ec6a8b"
    old = ROOT / "results/retrieval/20261007T014445273889Z-664d06a6c1c0"
    comparison = ROOT / "results/retrieval/20261007T122342844612Z-12c751a0b3f6"
    try:
        current, previous, paired = read(run / "result.json"), read(old / "result.json"), read(comparison / "result.json")
        assert current["complete"] and paired["complete"]
        assert len(current["task_results"]) == 25 and paired["paired_tasks"] == 23
        assert current["source"]["digest"] == source_fingerprint(ROOT)["digest"], "Code changed after benchmark"
        results, checks = {}, []
        for row in current["task_results"]:
            path = run / "tasks" / f"{row['instance_id']}.json"
            assert sha256(path.read_bytes()) == row["artifact_hash"], f"Raw hash mismatch: {path}"
            task = read(path)
            assert task["status"] == row["status"] and task["instance_id"] == row["instance_id"]
            telemetry = read(Path(row["attempt_path"]) / "telemetry.json")
            checks.append({"instance_id": row["instance_id"], "status": row["status"],
                           "artifact_hash": row["artifact_hash"], "duration_seconds": task["duration_seconds"],
                           "peak_rss_bytes": task["peak_rss_bytes"],
                           "graph_cached": task.get("graph", {}).get("cached"),
                           "actual_stages": telemetry["stages"], "phase": task.get("phase"),
                           "error": task.get("error"), "traceback": task.get("traceback")})
            results[row["instance_id"]] = task
        parity = []
        metric_names = (*DELTA_METRICS, "anchor_count", "no_anchors", "unmapped_count", "candidates_in")
        manual_ids = [row["instance_id"] for row in previous["task_results"] if row["status"] == "SUCCEEDED"][:10]
        for row in previous["task_results"]:
            task = results[row["instance_id"]]
            if row["status"] != "SUCCEEDED" or task["status"] != "SUCCEEDED":
                continue
            path = old / "tasks" / f"{row['instance_id']}.json"
            assert sha256(path.read_bytes()) == row["artifact_hash"], "Historical raw hash mismatch"
            before = read(path)
            for arm in ("graph", "graph_f2p"):
                for key in ("rank_order", "rank_hash", "anchors"):
                    assert before["arms"][arm][key] == task["arms"][arm][key], f"Parity mismatch {row['instance_id']}:{arm}:{key}"
                for name in metric_names:
                    assert before["arms"][arm]["metrics"].get(name) == task["arms"][arm]["metrics"].get(name), f"Metric mismatch {row['instance_id']}:{arm}:{name}"
            parity.append(row["instance_id"])
        assert len(parity) == 17 and set(manual_ids) <= set(parity)
        successes = [row for row in checks if row["status"] == "SUCCEEDED"]
        evidence.update(status="PASS", exit_code=0, benchmark_status=current["status"],
                        comparison_status=paired["status"], paired_tasks=23, attempted_tasks=25,
                        raw_hashes_verified=25, checks=checks, unchanged_overlap_ids=parity,
                        prior_manual10_ranking_and_metrics_unchanged=manual_ids,
                        cache_hits=sum(row["graph_cached"] is True for row in successes),
                        cache_misses=sum(row["graph_cached"] is False for row in successes),
                        summaries=paired["summaries"], paired_statistics=paired["paired"],
                        source_digest=current["source"]["digest"],
                        caveats=["PASS is integrity analysis, not full benchmark/repair PASS",
                                 "23 paired observations condition on successful tasks; 2 failures remain in denominator25",
                                 "Warm cache latency is not cold-start; actual stage times, not cached historical build_seconds",
                                 "Self review does not replace owner approvals; environment/inference NOT_RUN"])
    except Exception as exc:
        evidence.update(status="ERROR", exit_code=1, error=str(exc), traceback=traceback.format_exc())
    evidence["complete"] = True
    write_json(directory / "result.json", evidence)
    print(json.dumps({key: evidence.get(key) for key in
                      ("status", "error", "benchmark_status", "comparison_status", "paired_tasks", "raw_hashes_verified", "cache_hits", "cache_misses")}, ensure_ascii=False))
    print(directory / "result.json")
    return evidence["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
