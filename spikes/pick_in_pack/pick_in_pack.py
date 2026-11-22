"""Pick-in-pack test: can Qwen pick the gold function out of a graph context that surely contains it?

No tools, one generation per (task, position). The pack is the real graph_v1_b3000 context of the task (distractors)
plus the gold function, placed first, in the middle or last; relevance scores are reassigned in pack order so the
position is not given away. Output: one JSON line per (task, position); finished lines are kept on a rerun.

  PYTHONPATH=src:. python spikes/pick_in_pack/pick_in_pack.py ~/rt1 ~/rt1/results/pick_in_pack.jsonl
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from baseline.nav.run_nav import ANSWER_FORMAT
from baseline.run_offline import prepare_task
from vgar.contracts.prompt_context import render_context_for_repair

MAX_DISTRACTORS = 7
SYSTEM = ("You are a coding agent. Find the files and functions that must change to resolve the issue. "
          "The graph context below was retrieved for this issue; answer from it. " + ANSWER_FORMAT)


def qualname(entry: str) -> str:
    """``path::a.b``, ``path.py:a.b`` or ``a.b`` -> ``a.b``."""
    if "::" in entry:
        return entry.split("::", 1)[1].strip()
    _, sep, tail = entry.partition(".py:")
    return tail.strip() if sep else entry.strip()


def same_function(answer: str, gold: str) -> bool:
    a, g = qualname(answer), qualname(gold)
    return bool(a) and (a == g or g.endswith("." + a) or a.endswith("." + g))


assert same_function("pkg/m.py::pkg.m.C.f", "pkg/m.py::pkg.m.C.f") and same_function("pkg/m.py:pkg.m.C.f", "pkg/m.py::pkg.m.C.f")
assert same_function("C.f", "pkg/m.py::pkg.m.C.f") and not same_function("f2", "pkg/m.py::pkg.m.C.f")


def gold_snippet(source: str, qual: str) -> tuple[str, int, int] | None:
    """Source text and 1-based lines of the def whose Class.method chain is the longest suffix of ``qual``."""
    best = None

    def walk(node: ast.AST, chain: tuple[str, ...]) -> None:
        nonlocal best
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                here = chain + (child.name,)
                name = ".".join(here)
                if (not isinstance(child, ast.ClassDef) and (qual == name or qual.endswith("." + name))
                        and (best is None or len(here) > best[0])):
                    best = (len(here), child)
                walk(child, here)

    walk(ast.parse(source), ())
    if best is None:
        return None
    node = best[1]
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "\n".join(source.splitlines()[start - 1:node.end_lineno]), start, node.end_lineno


def build_pack(distractors: list[dict], gold_item: dict, position: str) -> list[dict]:
    items = [dict(item) for item in distractors]
    index = {"first": 0, "middle": len(items) // 2, "last": len(items)}[position]
    items.insert(index, dict(gold_item))
    scores = sorted((item["relevance_score"] for item in distractors), reverse=True) or [0.5]
    scores = scores + [scores[-1]] * (len(items) - len(scores))
    for item, score in zip(items, sorted(scores, reverse=True)):
        item["relevance_score"] = score
    return items


def main(root: Path, out: Path) -> None:
    from baseline.nav.model import (  # heavy (torch); not needed by the self-checks above
        QwenModel,
        parse_final,
    )
    rows = json.loads((root / "data/manifests/w10-dev-50-gold.json").read_text(encoding="utf-8"))["tasks"]
    done = {(r["i"], r["position"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    model = QwenModel()
    for row in rows:
        i = row["instance_id"]
        gold = json.loads((root / f"results/align_b4/tasks/{i}.json").read_text())["gold"]["gold_functions"]
        nav = json.loads((root / f"results/nav_v3/graph_v1_b3000/{i}.json").read_text())
        calls = [c for c in nav["tool_calls"] if c["name"] == "get_related_context" and isinstance(c.get("raw"), dict)
                 and (c["raw"].get("data") or {}).get("context")]
        if not gold or not calls:
            continue
        context = calls[0]["raw"]["data"]["context"]
        path, _, qual = gold[0].partition("::")
        sources, _ = prepare_task(root, row)
        found = gold_snippet(sources[path], qual) if path in sources else None
        if found is None:
            continue
        snippet, start, end = found
        distractors = [item for item in context["items"] if not any(same_function(item["symbol"], g) for g in gold)
                       and not (item["path"] == path and item["range"]["start_line"] <= end
                                and start <= item["range"]["end_line"])][:MAX_DISTRACTORS]
        if not distractors:
            continue
        confidences = sorted(item["confidence"] for item in distractors)
        gold_item = {"node_id": f"vgar:{i.split('__')[0]}:python:function:{path}:{qual}", "path": path, "symbol": qual,
                     "range": {"start_line": start, "start_col": 0, "end_line": end, "end_col": 0}, "snippet": snippet,
                     "relevance_score": 0.5, "graph_distance": 0, "graph_rationale": ["TASK_ANCHOR"],
                     "confidence": confidences[len(confidences) // 2], "token_count": len(snippet.encode()) // 4}
        for position in ("first", "middle", "last"):
            if (i, position) in done:
                continue
            items = build_pack(distractors, gold_item, position)
            total = sum(item["token_count"] for item in items)
            payload = dict(context, items=items, total_token_count=total, token_budget=max(context["token_budget"], total))
            messages = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": f"Issue:\n{row['problem_statement']}\n\n"
                                                    f"{render_context_for_repair(payload)}"}]
            text, usage = model.generate(messages, [])
            answer = parse_final(text) or {}
            functions = answer.get("functions", [])
            record = {"i": i, "position": position, "pack_size": len(items),
                      "gold_index": next(k for k, item in enumerate(items) if item["symbol"] == qual),
                      "gold": gold[0], "answer": functions[:5], "parsed": bool(answer),
                      "correct_at_1": bool(functions) and same_function(functions[0], gold[0]),
                      "gold_in_answer": any(same_function(f, gold[0]) for f in functions),
                      "picked_from_pack": bool(functions) and any(same_function(functions[0], item["symbol"]) for item in items),
                      "prompt_tokens": usage["prompt_tokens"], "seconds": round(usage["seconds"], 1)}
            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            print(f"{i} {position} correct={record['correct_at_1']} {record['seconds']} s", flush=True)
    print("PICK DONE", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser())
