import json
import time
from pathlib import Path

from .bm25 import BM25, pack_context
from .chunks import extract_chunks
from .dataset import read_repository_sources, validate_task
from .evidence import new_run, sha256, source_fingerprint, utc_now, write_json
from .gold_labels import extract_gold
from .metrics import aggregate_metrics, evaluate_ranking, unique


def evaluate_task(task, sources, budget_tokens=4000, k1=1.2, b=0.75):
    validate_task(task)
    started = time.perf_counter()
    chunks, parse_failures = extract_chunks(sources)
    if not chunks:
        raise ValueError("No parseable source chunks")
    corpus_hash = sha256(json.dumps({path: sha256(source) for path, source in sorted(sources.items())}, sort_keys=True))
    engine = BM25(chunks, k1=k1, b=b)
    index_seconds = time.perf_counter() - started
    started = time.perf_counter()
    ranked = engine.search(task["problem_statement"])
    # Ranking and context have been frozen before gold patch is opened/extracted.
    context = pack_context(ranked, budget_tokens)
    retrieval_seconds = time.perf_counter() - started
    gold = extract_gold(task["patch"], sources)
    metrics = evaluate_ranking(ranked, gold)
    metrics.update(context_token_estimate=context["total_token_count"], index_seconds=index_seconds,
                   retrieval_seconds=retrieval_seconds, mapping_coverage=gold["mapping_coverage"],
                   file_retrievability_coverage=gold["file_retrievability_coverage"])
    # Save first 20 unique files/functions even if large parent creates many windows.
    selected, seen_file, seen_function = [], set(), set()
    for item in ranked:
        if len(selected) < 100 or item["path"] not in seen_file and len(seen_file) < 20 or item["parent_id"] not in seen_function and len(seen_function) < 20:
            selected.append(item)
        seen_file.add(item["path"])
        if item["kind"] != "module":
            seen_function.add(item["parent_id"])
    return {"instance_id": task["instance_id"], "repository": task["repo"], "base_commit": task["base_commit"],
            "status": "SUCCEEDED", "query": task["problem_statement"], "query_hash": sha256(task["problem_statement"]),
            "patch_hash": sha256(task["patch"]), "corpus_hash": corpus_hash, "corpus_chunk_count": len(chunks),
            "parse_failures": parse_failures, "gold": gold, "ranked": selected, "ranking_saved_count": len(selected),
            "ranking_total_count": len(ranked), "context": context, "metrics": metrics,
            "ranked_identity_order": {"files": unique(c["path"] for c in ranked),
                                      "functions": unique(c["parent_id"] for c in ranked if c["kind"] != "module")},
            "context_metrics": evaluate_ranking(context["items"], gold),
            "candidate_map": [{k: c[k] for k in ("chunk_id", "parent_id", "path", "symbol", "kind", "start_line", "end_line", "parent_start_line", "parent_end_line", "source_hash", "snippet")} for c in chunks]}


def evaluate_manifest(root, manifest_path, limit=None, budget_tokens=4000, offline=False, resume=None):
    root, manifest_path = Path(root), Path(manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not manifest.get("tasks") or limit is not None and limit < 1 or budget_tokens < 1:
        raise ValueError("Manifest tasks must be nonempty and limit/budget positive")
    for task in manifest["tasks"]:
        validate_task(task)
    if len({t["instance_id"] for t in manifest["tasks"]}) != len(manifest["tasks"]):
        raise ValueError("Duplicate tasks in manifest")
    config = {"manifest_hash": sha256(manifest_bytes), "budget_tokens": budget_tokens, "k1": 1.2, "b": 0.75,
              "token_policy": "utf8_bytes_ceil_div4", "window_lines": 80, "overlap_lines": 16, "limit": limit}
    source = source_fingerprint(root)
    binding = sha256(json.dumps({"config": config, "source": source["digest"]}, sort_keys=True))
    previous = {}
    if resume:
        old = json.loads((Path(resume) / "result.json").read_text(encoding="utf-8"))
        if old.get("binding_hash") != binding:
            raise ValueError("Resume source/config/manifest mismatch; start a fresh run")
        for summary in old["task_results"]:
            if summary.get("status") == "SUCCEEDED":
                artifact = (Path(resume) / "tasks" / f"{summary['instance_id']}.json").read_bytes()
                if summary.get("artifact_hash") != sha256(artifact):
                    raise ValueError("Resume artifact hash/integrity mismatch")
                full = json.loads(artifact)
                if full["instance_id"] != summary["instance_id"] or any(k not in full for k in ("gold", "context", "candidate_map", "ranked")):
                    raise ValueError("Incomplete/tampered resume task artifact")
                row = next((t for t in manifest["tasks"] if t["instance_id"] == full["instance_id"]), None)
                if row is None or any(full[key] != row[key] for key in ("base_commit", "query_hash", "patch_hash")) or full["repository"] != row["repo"] or full["metrics"] != summary["metrics"] or full["corpus_hash"] != summary["corpus_hash"]:
                    raise ValueError("Resume task metadata/metrics integrity mismatch")
                previous[summary["instance_id"]] = full
    directory, record = new_run(root / "results" / "retrieval", "retrieval")
    record.update(config=config, source=source, binding_hash=binding, dataset_id=manifest["dataset_id"],
                  dataset_revision=manifest["dataset_revision"], manifest_path=str(manifest_path.resolve()),
                  task_results=[], resume_from=str(resume) if resume else None, m1_comparison_status="AWAITING_REAL_M1_EXPORTS",
                  stdout="", stderr="", exit_code=None)
    started = time.perf_counter()
    tasks = manifest["tasks"][:limit] if limit else manifest["tasks"]
    write_json(directory / "result.json", record)
    for number, row in enumerate(tasks, 1):
        task_start = time.perf_counter()
        try:
            patch_path = (root / row["gold_patch_path"]).resolve()
            if not patch_path.is_relative_to(root.resolve() / "data" / "gold"):
                raise ValueError("Gold patch path outside data/gold")
            patch = patch_path.read_text(encoding="utf-8")
            if sha256(patch) != row["patch_hash"] or sha256(row["problem_statement"]) != row["query_hash"]:
                raise ValueError("Manifest patch/query hash mismatch")
            if row["instance_id"] in previous:
                result = dict(previous[row["instance_id"]], resumed=True)
            else:
                sources, provenance = read_repository_sources(row, root / "data" / "repositories", network=not offline)
                result = evaluate_task(dict(row, patch=patch), sources, budget_tokens)
                result["source_provenance"] = provenance
            # Gold-free handoff material exists in both fresh and resumed runs.
            request = {"instance_id": result["instance_id"], "repository": result["repository"], "base_commit": result["base_commit"],
                       "query": result["query"], "query_hash": result["query_hash"], "corpus_hash": result["corpus_hash"],
                       "budget_tokens": budget_tokens, "token_policy": config["token_policy"], "candidates": result["candidate_map"]}
            write_json(directory / "m1_requests" / f"{row['instance_id']}.json", request)
            result["duration_seconds"] = time.perf_counter() - task_start
            write_json(directory / "tasks" / f"{row['instance_id']}.json", result)
            artifact_hash = sha256((directory / "tasks" / f"{row['instance_id']}.json").read_bytes())
        except Exception as exc:
            result = {"instance_id": row["instance_id"], "status": "FAILED", "error_class": type(exc).__name__, "error": str(exc),
                      "duration_seconds": time.perf_counter() - task_start}
            record["stderr"] += f"{row['instance_id']}: {type(exc).__name__}: {exc}\n"
            write_json(directory / "tasks" / f"{row['instance_id']}.json", result)
            artifact_hash = sha256((directory / "tasks" / f"{row['instance_id']}.json").read_bytes())
        record["task_results"].append({k: result[k] for k in result if k not in {"ranked", "context", "candidate_map", "gold", "query"}})
        record["task_results"][-1]["artifact_hash"] = artifact_hash
        message = f"[{number}/{len(tasks)}] {row['instance_id']}: {result['status']} ({result['duration_seconds']:.2f}s)"
        print(message, flush=True)
        record["stdout"] += message + "\n"
        record["summary"] = aggregate_metrics(record["task_results"])
        write_json(directory / "result.json", record)
    record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  status="SUCCEEDED" if record["summary"]["failed_tasks"] == 0 else "PARTIAL_FAILURE",
                  exit_code=0 if record["summary"]["failed_tasks"] == 0 else 1)
    write_json(directory / "result.json", record)
    return directory, record
