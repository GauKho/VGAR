"""Generate tables from actual artifacts; absent M1 is never a numeric zero."""
import json
from pathlib import Path


def fmt(value):
    return "N/A" if value is None else f"{value:.4f}"


def write_report(run, comparison=None):
    run = Path(run)
    record = json.loads((run / "result.json").read_text(encoding="utf-8"))
    summary = record["summary"]
    metrics = summary["metrics"]
    lines = ["# Kết quả retrieval M2 tuần 5–6", "", f"Run: `{record['run_id']}`; dataset: `{record['dataset_id']}` @ `{record['dataset_revision']}`.",
             f"Attempted: {summary['attempted_tasks']}; completed: {summary['completed_tasks']}; failed: {summary['failed_tasks']}.", "",
             "Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. Gold là changed-code proxy từ developer patch.", "",
             "## BM25 — ranking đầy đủ, dedup trước k", "", "| Metric | Mean (macro) | Eligible tasks |", "|---|---:|---:|"]
    for name in ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3", "function_recall@5", "function_recall@10", "file_mrr", "function_mrr", "context_token_estimate", "mapping_coverage", "file_retrievability_coverage"):
        value = metrics.get(name, {"mean": None, "eligible_tasks": 0})
        lines.append(f"| {name} | {fmt(value['mean'])} | {value['eligible_tasks']} |")
    lines += ["", "Token cost là estimate ceil(UTF-8 bytes/4), bao gồm path/symbol header và snippet; không phải bill/tokenizer LLM. API cost = 0 vì không gọi LLM.", "",
              "## Graph vs BM25 — cùng budget context", "", "Không so Graph context hữu hạn với toàn bộ BM25 ranking. Bảng paired chỉ dùng context đã đóng gói cùng token policy.", ""]
    if comparison:
        pair = json.loads((Path(comparison) / "result.json").read_text(encoding="utf-8"))
        lines += [f"Comparison status: **{pair['status']}**; paired tasks: {pair['paired_tasks']}/{pair['eligible_bm25_tasks']}.", ""]
        if pair["paired_tasks"]:
            lines += ["| System | File R@3 | File R@5 | File R@10 | Function R@3 | Function R@5 | Function R@10 | Token estimate |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
            for name in ("bm25", "graph"):
                values = pair["summaries"][name]["metrics"]
                numbers = [fmt(values[k]["mean"]) for k in ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3", "function_recall@5", "function_recall@10", "context_token_estimate")]
                lines.append(f"| {name} | " + " | ".join(numbers) + " |")
        else:
            lines += ["**Chưa có M1 output thật. Không có số đo Graph; chưa đạt DoD paired comparison.**", ""]
    else:
        lines.append("**AWAITING_M1**: cần ContextPayload thật + sidecar đúng commit/query/corpus, không dùng demo fixture thay benchmark.")
    lines += ["", "## Per task", "", "| Instance | Status | File R@5 | Function R@5 | Mapping coverage |", "|---|---|---:|---:|---:|"]
    for task in record["task_results"]:
        values = task.get("metrics", {})
        lines.append(f"| {task['instance_id']} | {task['status']} | {fmt(values.get('file_recall@5'))} | {fmt(values.get('function_recall@5'))} | {fmt(values.get('mapping_coverage'))} |")
    destination = run / "REPORT.md"
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
