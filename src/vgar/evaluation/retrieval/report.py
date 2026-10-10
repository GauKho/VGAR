"""Generate tables from actual artifacts; absent M1 is never a numeric zero.

Two modes, both read from ONE rank per task (see scoring.py):
  rank   - primary: Recall@k / MRR on the full ranking, independent of budget.
  packed - secondary: what an agent sees after packing under the shared token budget.
"""
import json
from pathlib import Path

RANK_ROWS = ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3", "function_recall@5",
             "function_recall@10", "file_mrr", "function_mrr", "file_reach", "function_reach")
PACKED_ROWS = ("packed_gold_file_in_context", "packed_gold_function_in_context", "packed_all_gold_files_in_context",
               "packed_all_gold_functions_in_context", "context_tokens", "packed_tokens_to_first_gold_file",
               "packed_tokens_to_first_gold_function", "packed_items_packed", "packed_truncated")
TOKEN_ROWS = {"context_tokens", "packed_tokens_to_first_gold_file", "packed_tokens_to_first_gold_function", "packed_items_packed"}


def fmt(value, digits=4):
    return "N/A" if value is None else f"{value:.{digits}f}"


def _cell(metrics, name):
    value = metrics.get(name, {"mean": None, "eligible_tasks": 0})
    return fmt(value["mean"], 1 if name in TOKEN_ROWS else 4), value["eligible_tasks"]


def _single_table(metrics, names):
    lines = ["| Metric | Mean (macro) | Eligible tasks |", "|---|---:|---:|"]
    for name in names:
        number, eligible = _cell(metrics, name)
        lines.append(f"| {name} | {number} | {eligible} |")
    return lines


ARM_LABELS = {"bm25": "bm25 (full rank)", "bm25_capped": "bm25@cap (diagnostic)", "graph": "graph", "graph_f2p": "graph+F2P"}
DELTA_ROWS = ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3", "function_recall@5",
              "function_recall@10", "file_mrr", "function_mrr", "packed_gold_file_in_context",
              "packed_gold_function_in_context", "context_tokens")


def _paired_table(summaries, names):
    arms = [a for a in ("bm25", "bm25_capped", "graph", "graph_f2p") if a in summaries]
    lines = ["| Metric | " + " | ".join(ARM_LABELS[a] for a in arms) + " |", "|---|" + "---:|" * len(arms)]
    for name in names:
        cells = []
        for arm in arms:
            number, eligible = _cell(summaries[arm]["metrics"], name)
            cells.append(f"{number} (n={eligible})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return lines


def _delta_table(paired):
    lines = []
    for arm, stats in paired.items():
        lines += [f"**{ARM_LABELS[arm]} − BM25 full rank** (cùng task, bootstrap 95% CI của mean delta)", "",
                  "| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |", "|---|---:|---:|---|---:|"]
        for name in DELTA_ROWS:
            row = stats.get(name, {"n": 0})
            if not row["n"]:
                lines.append(f"| {name} | 0 | N/A | N/A | N/A |")
                continue
            digits = 1 if name == "context_tokens" else 4
            lines.append(f"| {name} | {row['n']} | {row['mean_delta']:+.{digits}f} | [{row['ci95'][0]:+.{digits}f}, {row['ci95'][1]:+.{digits}f}] | "
                         f"{row['wins']} / {row['ties']} / {row['losses']} |")
        lines.append("")
    return lines


def _comparison_extras(pair):
    lines = ["### Delta theo cặp task", ""] + _delta_table(pair.get("paired", {}))
    if pair.get("graph_diagnostics"):
        lines += ["### Chẩn đoán Graph (quyết định hybrid vs giảm nhiễu anchors)", "",
                  "| Arm | Task không có anchor | Anchors/task | Unmapped (tổng) | Unmapped/task | Candidates/task |", "|---|---:|---:|---:|---:|---:|"]
        for arm, d in pair["graph_diagnostics"].items():
            lines.append(f"| {ARM_LABELS[arm]} | {d['no_anchor_tasks']} | {fmt(d['mean_anchor_count'], 1)} | {d['unmapped_total']} | "
                         f"{fmt(d['mean_unmapped_per_task'], 2)} | {fmt(d['mean_candidates'], 1)} |")
        lines.append("")
    if pair.get("by_repo"):
        arms = [a for a in ("bm25", "graph", "graph_f2p")]
        lines += ["### Theo repo (mean File R@5 / Function R@5)", "", "| Repo | n | " + " | ".join(ARM_LABELS[a] for a in arms) + " |",
                  "|---|---:|" + "---:|" * len(arms)]
        for repo, row in pair["by_repo"].items():
            cells = [f"{fmt(row.get(f'{a}.file_recall@5'), 2)} / {fmt(row.get(f'{a}.function_recall@5'), 2)}" for a in arms]
            lines.append(f"| {repo} | {row['n']} | " + " | ".join(cells) + " |")
        lines.append("")
    if pair.get("inspection"):
        lines += ["### Task cần kiểm tay (Δ = Δfile R@5 + Δfunction R@5 so với BM25 full rank)", ""]
        for arm, groups in pair["inspection"].items():
            for title, key in (("Graph thua", "graph_loses"), ("Graph thắng", "graph_wins")):
                for item in groups[key]:
                    lines.append(f"- {ARM_LABELS[arm]} · {title} · `{item['instance_id']}` ({item['delta']:+.2f}); anchors: "
                                 + (", ".join(f"`{a}`" for a in item["anchors"]) or "_không có_"))
        lines.append("")
    return lines


def write_report(run, comparison=None, destination=None):
    run = Path(run)
    record = json.loads((run / "result.json").read_text(encoding="utf-8"))
    summary, config = record["summary"], record["config"]
    metrics = summary["metrics"]
    lines = ["# Kết quả retrieval M2 tuần 5–6", "",
             f"Run: `{record['run_id']}`; dataset: `{record['dataset_id']}` @ `{record['dataset_revision']}`.",
             f"Attempted: {summary['attempted_tasks']}; completed: {summary['completed_tasks']}; failed: {summary['failed_tasks']}.",
             f"Scoring: `{config['scoring_version']}`; budget: {config['budget_tokens']} token; counter: `{config['counter_label']}`.", ""]
    if config.get("counter_is_fallback"):
        lines += ["> **CẢNH BÁO — counter dự phòng bytes/4.** Số token dưới đây KHÔNG so được với M1 `LocalTokenizerCounter`. "
                  "Không dùng cho bảng Graph vs BM25 chính thức; chạy lại với tokenizer manifest.", ""]
    lines += ["Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. "
              "Gold là changed-code proxy từ developer patch.", "",
              "## Số chính — rank đầy đủ (dedup trước k)", "",
              "Recall@k và MRR tính trên toàn bộ ranking, không phụ thuộc budget. Gold mà arm không chạm tới là miss "
              "(MRR đóng góp 0), task không bị loại. `*_reach` = tỉ lệ gold xuất hiện ở bất kỳ hạng nào.", ""]
    lines += _single_table(metrics, RANK_ROWS)
    lines += ["", f"## Số phụ — context đóng gói @{config['budget_tokens']} token", "",
              "Phản ánh thứ agent thực sự nhìn thấy: cùng counter, cùng budget, cùng snippet policy "
              f"(tối đa {config['snippet_policy']['max_snippet_lines']} dòng/snippet, có header `path::symbol`). "
              "`tokens_to_first_gold_*` chỉ tính trên task có gold trong context (xem Eligible).", ""]
    lines += _single_table(metrics, PACKED_ROWS)
    lines += ["", "## Graph vs BM25", "",
              "Hai chế độ cùng đọc từ một rank mỗi task. Số chính là rank đầy đủ; số phụ là context đóng gói. "
              "Nếu hai số mâu thuẫn (Graph thắng ở rank, thua ở packed) thì phân tích, không chọn số đẹp hơn.", ""]
    if comparison:
        pair = json.loads((Path(comparison) / "result.json").read_text(encoding="utf-8"))
        lines += [f"Comparison status: **{pair['status']}**; paired tasks: {pair['paired_tasks']}/{pair['eligible_bm25_tasks']}.", ""]
        if pair["paired_tasks"] and pair.get("scoring_version") == config["scoring_version"]:
            lines += [f"`bm25@cap` = BM25 chấm lại trên top-{pair.get('bm25_cap', 100)} chunk (Graph tối đa 100 node); "
                      "đây là ablation phụ. Baseline chính là `bm25 (full rank)`; `graph+F2P` là oracle chẩn đoán.", ""]
            lines += ["### Rank đầy đủ (chính)", ""] + _paired_table(pair["summaries"], RANK_ROWS)
            lines += ["", "### Context đóng gói (phụ)", ""] + _paired_table(pair["summaries"], PACKED_ROWS)
            lines += [""] + _comparison_extras(pair)
        else:
            lines += ["**Chưa có Graph output cùng scoring version. Không có số đo Graph; chưa đạt DoD paired comparison.**", ""]
    else:
        lines.append("**AWAITING_GRAPH**: cần RankRecord thật của Graph (từ `RetrievalResult.candidates`, cùng corpus/counter/budget); "
                     "không dùng demo fixture thay benchmark.")
    lines += ["", "## Per task", "", "| Instance | Status | File R@5 | Function R@5 | Gold fn in context | Mapping coverage |",
              "|---|---|---:|---:|---:|---:|"]
    for task in record["task_results"]:
        values = task.get("metrics", {})
        lines.append(f"| {task['instance_id']} | {task['status']} | {fmt(values.get('file_recall@5'))} | "
                     f"{fmt(values.get('function_recall@5'))} | {fmt(values.get('packed_gold_function_in_context'))} | "
                     f"{fmt(values.get('mapping_coverage'))} |")
    destination = Path(destination) if destination else run / "REPORT.md"
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
