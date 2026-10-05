"""LEGACY (packed-context only, bytes/4 token policy). Superseded by scoring.py (rank + packed from one rank).
Kept for the frozen ContextPayload shape validation; do not use compare_run with scoring-v1 artifacts."""
import math
import json
import time
from pathlib import Path
from .bm25 import pack_context
from .chunks import normalize_path, physical_lines
from .evidence import new_run, sha256, source_fingerprint, utc_now, write_json
from .metrics import aggregate_metrics, evaluate_ranking


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Invalid {name}")
    return value


def adapt_context(exported, bm25_result):
    if not isinstance(exported, dict) or not isinstance(bm25_result, dict):
        raise ValueError("M1 export and BM25 artifact must be JSON objects")
    for key in ("instance_id", "repository", "base_commit", "query_hash", "corpus_hash"):
        if exported.get(key) != bm25_result[key]:
            raise ValueError(f"M1 metadata mismatch: {key}")
    payload = exported["context"]
    if not isinstance(payload, dict):
        raise ValueError("M1 context must be a JSON object")
    expected = {"graph_version", "anchor_ids", "items", "total_token_count", "token_budget", "truncated"}
    if set(payload) != expected or not isinstance(payload["graph_version"], str) or not payload["graph_version"]:
        raise ValueError("Invalid ContextPayload shape / graph_version")
    if not isinstance(payload["anchor_ids"], list) or any(not isinstance(a, str) or not a for a in payload["anchor_ids"]):
        raise ValueError("Invalid anchor IDs")
    if not isinstance(payload["truncated"], bool) or not isinstance(payload["items"], list):
        raise ValueError("Invalid context items/truncated")
    integer(payload["token_budget"], "budget", 1)
    integer(payload["total_token_count"], "total_token_count")
    if payload["token_budget"] != bm25_result["context"]["token_budget"]:
        raise ValueError("Unequal comparison budgets")
    if payload["total_token_count"] != sum(integer(i["token_count"], "token_count") for i in payload["items"]) or payload["total_token_count"] > payload["token_budget"]:
        raise ValueError("M1 token accounting mismatch")
    converted = []
    fields = {"node_id", "path", "symbol", "range", "snippet", "relevance_score", "graph_distance", "graph_rationale", "confidence", "token_count"}
    for item in payload["items"]:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Invalid ContextItem fields")
        path = normalize_path(item["path"])
        for name in ("node_id", "symbol", "snippet"):
            if not isinstance(item[name], str) or not item[name]:
                raise ValueError(f"Empty/non-string {name}")
        for name in ("relevance_score", "confidence"):
            value = item[name]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid {name}")
        integer(item["graph_distance"], "graph_distance")
        if not isinstance(item["graph_rationale"], list) or not item["graph_rationale"] or any(not isinstance(r, str) or not r for r in item["graph_rationale"]):
            raise ValueError("Missing graph rationale")
        span = item["range"]
        if not isinstance(span, dict) or set(span) != {"start_line", "start_col", "end_line", "end_col"}:
            raise ValueError("Invalid source range")
        for name, value in span.items():
            integer(value, name, 1 if name.endswith("line") else 0)
        if (span["start_line"], span["start_col"]) > (span["end_line"], span["end_col"]):
            raise ValueError("Reversed source range")
        matches = {c["parent_id"]: c for c in bm25_result["candidate_map"] if c["path"] == path and c["symbol"] == item["symbol"] and
                   c["parent_start_line"] <= span["start_line"] <= span["end_line"] <= c["parent_end_line"]}
        if len(matches) != 1:
            raise ValueError(f"Ambiguous/unmapped M1 function: {path}::{item['symbol']}; coordinate with M1")
        canonical = next(iter(matches.values()))
        source_lines = {}
        for chunk in bm25_result["candidate_map"]:
            if chunk["parent_id"] == canonical["parent_id"]:
                for offset, line in enumerate(physical_lines(chunk["snippet"])):
                    source_lines[chunk["start_line"] + offset] = line
        try:
            lines = [source_lines[number].encode("utf-8") for number in range(span["start_line"], span["end_line"] + 1)]
            if span["start_col"] > len(lines[0]) or span["end_col"] > len(lines[-1]):
                raise ValueError("Source column outside snippet")
            if len(lines) == 1:
                lines[0] = lines[0][span["start_col"]:span["end_col"]]
            else:
                lines[0] = lines[0][span["start_col"]:]
                lines[-1] = lines[-1][:span["end_col"]]
            expected_snippet = b"\n".join(lines).decode("utf-8")
        except (KeyError, UnicodeError) as exc:
            raise ValueError("Source range cannot be validated against base snippet") from exc
        if item["snippet"].replace("\r\n", "\n").rstrip("\n") != expected_snippet.rstrip("\n"):
            raise ValueError("M1 snippet differs from pinned base source")
        converted.append(dict(item, chunk_id=item["node_id"], parent_id=canonical["parent_id"], kind=canonical["kind"]))
    repacked = pack_context(converted, payload["token_budget"])
    repacked.update(graph_version=payload["graph_version"], native_total_token_count=payload["total_token_count"],
                    native_truncated=payload["truncated"], anchor_ids=payload["anchor_ids"])
    return repacked


def compare_run(run, exports, results_root):
    run, exports = Path(run), Path(exports)
    parent = json.loads((run / "result.json").read_text(encoding="utf-8"))
    directory, report = new_run(results_root, "graph_vs_bm25")
    started = time.perf_counter()
    report.update(source=source_fingerprint(Path(__file__).resolve().parents[2]), stdout="", stderr="")
    report.update(bm25_run=str(run.resolve()), bm25_run_hash=sha256((run / "result.json").read_bytes()),
                  exports=str(exports.resolve()), pairs=[], missing_exports=[], invalid_exports=[],
                  comparison_policy="same_query_commit_corpus_budget_and_recounted_token_estimate; context_only")
    for task in parent["task_results"]:
        if task["status"] != "SUCCEEDED":
            continue
        instance = task["instance_id"]
        source_path = run / "tasks" / f"{instance}.json"
        export_path = exports / f"{instance}.json"
        if not export_path.exists():
            report["missing_exports"].append(instance)
            continue
        try:
            artifact = source_path.read_bytes()
            if task.get("artifact_hash") and task["artifact_hash"] != sha256(artifact):
                raise ValueError("BM25 task artifact hash mismatch")
            result = json.loads(artifact)
            if result.get("scoring_version"):
                raise ValueError("Legacy compare_run needs pre-scoring-v1 artifacts; use scoring.graph_rank + score_record")
            context = adapt_context(json.loads(export_path.read_text(encoding="utf-8")), result)
            report["pairs"].append({"instance_id": instance, "export_hash": sha256(export_path.read_bytes()),
                                   "graph_metrics": evaluate_ranking(context["items"], result["gold"]),
                                   "bm25_metrics": result["context_metrics"], "graph_token_estimate": context["total_token_count"],
                                   "bm25_token_estimate": result["context"]["total_token_count"], "adapted_context": context})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            report["invalid_exports"].append({"instance_id": instance, "error": str(exc)})
    report["paired_tasks"] = len(report["pairs"])
    report["eligible_bm25_tasks"] = sum(t["status"] == "SUCCEEDED" for t in parent["task_results"])
    report["status"] = "AWAITING_M1" if not report["pairs"] and not report["invalid_exports"] else (
        "SUCCEEDED" if not report["missing_exports"] and not report["invalid_exports"] else "INCOMPLETE_COMPARISON")
    report.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  stdout=f"Status={report['status']}; paired={report['paired_tasks']}/{report['eligible_bm25_tasks']}\n",
                  stderr=json.dumps(report["invalid_exports"], ensure_ascii=False), exit_code=0 if report["status"] == "SUCCEEDED" else 2)
    report["summaries"] = {name: aggregate_metrics([{"status": "SUCCEEDED", "metrics": p[name + "_metrics"] | {"context_token_estimate": p[name + "_token_estimate"]}} for p in report["pairs"]]) for name in ("graph", "bm25")}
    write_json(directory / "result.json", report)
    return directory, report