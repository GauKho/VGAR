"""Per-level deduplication BEFORE k, with explicit ineligible denominators."""
import statistics


def unique(values):
    return list(dict.fromkeys(values))


def evaluate_ranking(ranked, gold, ks=(1, 3, 5, 10, 20)):
    result = {}
    for level, key, label in (("file", "path", "gold_files"), ("function", "parent_id", "gold_functions")):
        relevant = set(gold[label]) if level != "function" or gold.get("function_labels_complete", True) else set()
        ordering = unique(r[key] for r in ranked if key in r and (level == "file" or r.get("kind") != "module"))
        first = next((i + 1 for i, value in enumerate(ordering) if value in relevant), None)
        result[f"{level}_gold_count"] = len(relevant)
        result[f"{level}_mrr"] = (1 / first if first else 0) if relevant else None
        for k in ks:
            hits = len(relevant.intersection(ordering[:k]))
            result[f"{level}_recall@{k}"] = hits / len(relevant) if relevant else None
            result[f"{level}_all_gold@{k}"] = int(hits == len(relevant)) if relevant else None
    return result


def aggregate_metrics(task_results):
    completed = [r for r in task_results if r.get("status") == "SUCCEEDED"]
    metrics = {}
    keys = sorted({key for r in completed for key in r["metrics"]})
    for key in keys:
        values = [r["metrics"][key] for r in completed if r["metrics"].get(key) is not None]
        metrics[key] = {"mean": statistics.mean(values) if values else None, "eligible_tasks": len(values)}
    return {"attempted_tasks": len(task_results), "completed_tasks": len(completed),
            "failed_tasks": len(task_results) - len(completed), "metrics": metrics}
