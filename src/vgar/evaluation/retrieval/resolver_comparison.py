"""Paired resolver scoring; no graph, model, or repository-code execution."""
from __future__ import annotations

import json
import math
from statistics import mean

from .evidence import sha256


def resolver_cache_key(repo, revision, source_digest, implementation_digest, profile):
    """Separate resolver/runtime/source identities even when repo and commit agree."""
    identity = {"repo": repo, "revision": revision, "sources": source_digest,
                "implementation": implementation_digest, "profile": profile}
    return sha256(json.dumps(identity, sort_keys=True))[7:]


def native_context_metrics(context, gold, corpus):
    """Count whole gold functions contained in actual payload ranges, including class/file items.

    Coordinates are UTF-8 bytes, end exclusive. Missing/incomplete labels remain null.
    The shared 80-line scoring pack is a separate metric and is never substituted here.
    """
    items = context["items"]
    files = set(gold["gold_files"])
    functions = set(gold["gold_functions"]) if gold["function_labels_complete"] else set()
    definitions = {d["parent_id"]: d for values in corpus.definitions.values() for d in values}
    covered = set()
    for identity in functions:
        definition = definitions.get(identity)
        if definition is None:
            continue
        start = definition["start_line"], definition["start_col"]
        end = definition["end_line"], definition["end_col"]
        for item in items:
            span = item["range"]
            if (item["path"] == definition["path"]
                    and (span["start_line"], span["start_col"]) <= start
                    and end <= (span["end_line"], span["end_col"])):
                covered.add(identity)
                break
    return {"native_gold_file_in_context": len(files & {i["path"] for i in items}) / len(files) if files else None,
            "native_gold_function_in_context": len(covered) / len(functions) if functions else None,
            "native_context_tokens": context["total_token_count"], "native_context_items": len(items),
            "native_context_truncated": int(context["truncated"])}


def paired_summary(pairs, metric_names):
    """Only identical successful pairs contribute deltas; failures retain the attempted denominator."""
    complete = []
    failures = []
    for pair in pairs:
        left, right = pair["static"], pair["scip"]
        if left["status"] != "SUCCEEDED" or right["status"] != "SUCCEEDED":
            failures.append({"instance_id": pair["instance_id"], "static_status": left["status"],
                             "scip_status": right["status"]})
            continue
        for key in ("instance_id", "base_commit", "query_hash", "patch_hash", "corpus_hash", "comparison_binding"):
            if left[key] != right[key]:
                raise ValueError(f"Paired input/config mismatch: {key}")
        if left["source_tree"]["tree_hash"] != right["source_tree"]["tree_hash"]:
            raise ValueError("Paired source tree mismatch")
        if left["graph"]["source_digest"] != right["graph"]["source_digest"]:
            raise ValueError("Paired actual source digest mismatch")
        if left["graph"].get("auxiliary_digest") != right["graph"].get("auxiliary_digest"):
            raise ValueError("Paired config/stub digest mismatch")
        if right["graph"]["resolver_report"]["active"] != "scip":
            raise ValueError("SCIP fallback cannot be counted as a successful SCIP comparison")
        complete.append(pair)
    arms = {}
    for arm in ("graph", "graph_f2p"):
        metrics = {}
        for name in metric_names:
            values = []
            for pair in complete:
                a = pair["static"]["arms"][arm]["metrics"].get(name)
                b = pair["scip"]["arms"][arm]["metrics"].get(name)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and math.isfinite(b):
                    values.append((a, b))
            metrics[name] = {"eligible_pairs": len(values), "static_mean": mean(a for a, b in values) if values else None,
                             "scip_mean": mean(b for a, b in values) if values else None,
                             "mean_delta_scip_minus_static": mean(b - a for a, b in values) if values else None,
                             "increased": sum(b > a for a, b in values), "equal": sum(b == a for a, b in values),
                             "decreased": sum(b < a for a, b in values)}
        arms[arm] = metrics
    builds = [(p["static"]["graph"]["build_seconds"], p["scip"]["graph"]["build_seconds"]) for p in complete]
    return {"attempted_pairs": len(pairs), "successful_pairs": len(complete), "failed_pairs": failures,
            "build_seconds": {"static_mean": mean(a for a, b in builds) if builds else None,
                              "scip_mean": mean(b for a, b in builds) if builds else None,
                              "measurement": "cold build; includes indexing for SCIP; OS cache not controlled"},
            "metrics_by_arm": arms,
            "interpretation": "Small development pilot; changed-code proxy labels; no repair-success or significance claim."}
