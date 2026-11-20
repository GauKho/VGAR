"""T2 (spec 2026-11-19 §8): Qwen navigates the repository to localise the code to change; arms differ only in tools.

Arms: ``base`` (grep/read_file/list_dir), ``graph_v0`` (+ graph server tools on the ``base`` graph),
``graph_v0_scip`` (+ graph tools on the ``scip`` graph, built beforehand by ``baseline/run_offline.py``).
Output ``<out>/<arm>/<instance_id>.json``: the conversation, every tool call, and the scores. Dev split only.

  PYTHONPATH=src python baseline/nav/run_nav.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
      --out ~/rt1/results/nav --arms base,graph_v0 --only ~/rt1/nav10.txt
"""
from __future__ import annotations

import argparse
import inspect
import json
import posixpath
import statistics
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import baseline._paths

# isort: split
import run_graph_retrieval as runner

from baseline.frontier_v2 import frontier_core_v2
from baseline.graph_store import graph_db_path, load_or_build
from baseline.nav.model import MAX_ANSWER_ITEMS, MODEL_ID, parse_final, parse_tool_calls
from baseline.nav.tools import (
    CONTEXT_RESULT_TOKENS,
    FileTools,
    GraphTools,
    ToolResult,
    cap_tokens,
)
from baseline.profiles import build_layers
from vgar.evaluation.retrieval.dataset import require_split, validate_task
from vgar.evaluation.retrieval.gold_labels import extract_gold
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    RankItem,
    RankRecord,
    bytes_div4_counter,
    flat_metrics,
    score_record,
)

ARMS = {"base": None, "graph_v0": "base", "graph_v0_scip": "scip", "graph_conf": "base"}   # arm -> graph build
CONFIDENCE_ARMS = {"graph_conf"}   # CALLS edges shown with confidence and provenance (harness-side trial)
SYSTEM_PROMPT = (
    "You are a coding agent. Find the files and functions that must change to resolve the issue. "
    "Use the tools to explore the repository; call one or more tools per turn. When you are done, reply with only a "
    'JSON object {"files": ["path", ...], "functions": ["path::module.Class.function", ...]}, at most '
    f"{MAX_ANSWER_ITEMS} files and {MAX_ANSWER_ITEMS} functions, most likely first.")
FINAL_REQUEST = "The tool budget is used up. Reply now with the final JSON object only."
CONTEXT_REQUEST = "The context is almost full. Reply now with the final JSON object only."
ANSWER_MARGIN = 2500   # one capped tool result (<= 2000 tokens) plus the request still fit under the context limit
KS = (1, 3, 5, 10, 20)
RANK_METRICS = (*(f"file_recall@{k}" for k in KS), *(f"function_recall@{k}" for k in KS), "file_mrr", "function_mrr")
NAV_METRICS = ("seen_frontier_recall", "seen_all_gold_files", "non_gold_files_read", "tool_calls", "mean_tool_seconds",
               "completion_tokens")


async def run_task(model: Any, tools: dict[str, Any], schemas: list[dict[str, Any]], row: dict, *,
                   max_calls: int = 12, max_context_tokens: int = 16000, max_seconds: float = 1200) -> dict[str, Any]:
    """One task: the model calls tools until it answers, the call budget ends, or the context is full.

    Args:
        model: Object with ``prompt_tokens(messages, tools)`` and ``generate(messages, tools)``.
        tools: Tool name -> callable taking keyword arguments, returning a ``ToolResult`` (or an awaitable of one).
        schemas: Function schemas shown to the model.
        row: Task with ``problem_statement``.
        max_calls: Tool call budget.
        max_context_tokens: Prompt size that stops the loop.
        max_seconds: Wall-clock limit of the task, checked between steps.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Issue:\n{row['problem_statement']}"}]
    calls, spans, turns = [], [], []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0}
    answer, status, ended_by = None, "NO_ANSWER", "answer"

    def generate(tool_schemas: list[dict[str, Any]]) -> str:
        text, used = model.generate(messages, tool_schemas)
        for key in usage:
            usage[key] += used[key]
        turns.append(text)
        messages.append({"role": "assistant", "content": text})
        return text

    started_task = time.perf_counter()
    while True:
        if time.perf_counter() - started_task >= max_seconds:
            status, ended_by = "TIMEOUT", "time_limit"
            break
        prompt = model.prompt_tokens(messages, schemas)
        if prompt > max_context_tokens:
            status, ended_by = "CONTEXT_FULL", "context_full"
            break
        if prompt > max_context_tokens - ANSWER_MARGIN:   # ask for the answer instead of scoring the task as 0
            messages.append({"role": "user", "content": CONTEXT_REQUEST})
            answer = parse_final(generate([]))
            status, ended_by = ("OK" if answer else "CONTEXT_FULL"), "context_limit"
            break
        text = generate(schemas)
        requested = parse_tool_calls(text)
        if not requested:
            answer = parse_final(text)
            status = "OK" if answer else "BAD_ANSWER"
            break
        for call in requested[: max_calls - len(calls)]:
            started, error = time.perf_counter(), None
            name = call.get("name", "?")
            print(f"    {row.get('instance_id', '?')} call {name} {json.dumps(call.get('arguments'), ensure_ascii=False)[:120]}",
                  file=sys.stderr, flush=True)   # heartbeat: a hang now shows which call it is in
            if "error" in call:
                result, error = ToolResult(f"bad tool call: {call['error']}"), call["error"]
            elif name not in tools:
                result, error = ToolResult(f"unknown tool {name!r}"), "unknown tool"
            else:
                try:
                    result = tools[name](**call["arguments"])
                    if inspect.isawaitable(result):
                        result = await result
                except Exception as exc:  # noqa: BLE001 -- a bad call is shown to the model, the run goes on
                    result, error = ToolResult(f"error: {type(exc).__name__}: {exc}"), str(exc)
            shown = cap_tokens(result.text, CONTEXT_RESULT_TOKENS if name == "get_related_context" else 1500)
            logged = {"name": name, "arguments": call.get("arguments"), "seconds": time.perf_counter() - started,
                      "tokens": len(result.text.encode("utf-8")) // 4, "error": error, "result": shown}
            if result.raw is not None:
                logged["raw"] = result.raw   # full server answer (diagnostics: candidates, features, scores, config)
            calls.append(logged)
            spans += result.spans
            messages.append({"role": "tool", "content": shown})
        if len(calls) >= max_calls:
            messages.append({"role": "user", "content": FINAL_REQUEST})
            answer = parse_final(generate([]))
            status, ended_by = ("OK" if answer else "NO_ANSWER"), "call_budget"
            break
    return {"status": status, "ended_by": ended_by, "answer": answer, "turns": turns, "tool_calls": calls, "spans": spans, "usage": usage}


def _match(definitions: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for definition in definitions:
        symbol = definition["symbol"]
        if symbol == name or symbol.endswith("." + name) or name.endswith("." + symbol):
            return definition
    return None


def _resolve(corpus: CorpusIndex, entry: str) -> dict[str, Any] | None:
    """``path::name`` within that file; a bare dotted name by exact symbol, else by a unique dotted suffix."""
    if "::" in entry:
        path, _, name = entry.partition("::")
        return _match(corpus.definitions.get(path.strip().lstrip("./"), []), name.strip())
    everything = [d for values in corpus.definitions.values() for d in values]
    exact = [d for d in everything if d["symbol"] == entry]
    suffix = [d for d in everything if d["symbol"].endswith("." + entry)]
    return (exact or suffix)[0] if len(exact) == 1 or (not exact and len(suffix) == 1) else None


def _files_read(calls: list[dict[str, Any]]) -> set[str]:
    """Files the model opened with ``read_file`` (grep hits are not reads)."""
    return {posixpath.normpath(call["arguments"]["path"]).lstrip("/") for call in calls
            if call.get("name") == "read_file" and isinstance(call.get("arguments"), dict)
            and isinstance(call["arguments"].get("path"), str)}


def score_nav(result: dict[str, Any], row: dict, sources: dict[str, str]) -> dict[str, Any]:
    """R1 metrics of the final answer, what the model read, and the MCP usability counts."""
    corpus = CorpusIndex(sources)
    gold = extract_gold(row["patch"], sources)
    frontier = set(frontier_core_v2(row["patch"], gold, corpus))
    items: list[RankItem] = []
    answer = result.get("answer") or {"files": [], "functions": []}
    for entry in answer["functions"]:
        definition = _resolve(corpus, entry)
        if definition is not None and all(item.item_id != definition["parent_id"] for item in items):
            items.append(RankItem(item_id=definition["parent_id"], path=definition["path"], kind=definition["kind"],
                                  symbol=definition["symbol"], start_line=definition["start_line"],
                                  end_line=definition["end_line"], function_id=definition["parent_id"]))
    for path in answer["files"]:
        if path in sources and all(item.path != path for item in items):
            items.append(RankItem(item_id=f"file:{path}", path=path, kind="file", symbol=path, start_line=1,
                                  end_line=max(1, len(sources[path].splitlines()))))
    record = RankRecord(instance_id=row["instance_id"], arm="nav", items=items)
    metrics = flat_metrics(score_record(record, gold, budget_tokens=12000, counter=bytes_div4_counter,
                                        counter_label=FALLBACK_COUNTER_LABEL))
    definitions = {d["parent_id"]: d for values in corpus.definitions.values() for d in values}
    spans = [tuple(span) for span in result.get("spans", [])]
    seen = {fid for fid in frontier if fid in definitions and any(
        path == definitions[fid]["path"] and start <= definitions[fid]["start_line"]
        and definitions[fid]["end_line"] <= end for path, start, end in spans)}
    shown = {span[0] for span in spans}
    gold_files = set(gold["gold_files"])
    calls = result.get("tool_calls", [])
    opened = _files_read(calls)
    metrics.update(status=result["status"], seen_frontier_recall=len(seen) / len(frontier) if frontier else None,
                   seen_all_gold_files=int(gold_files <= shown) if gold_files else None,
                   files_read=len(opened), non_gold_files_read=len(opened - gold_files), tool_calls=len(calls),
                   mean_tool_seconds=statistics.fmean(c["seconds"] for c in calls) if calls else 0.0,
                   prompt_tokens=result["usage"]["prompt_tokens"], completion_tokens=result["usage"]["completion_tokens"],
                   cross_file=len(gold_files) >= 2)
    return metrics


def nav_table(nav_dir: Path) -> str:
    """Markdown, per arm: number of tasks, status counts and metric means; answer ranking @k, then navigation."""
    arms = [(arm_dir.name, [json.loads(p.read_text(encoding="utf-8"))["metrics"] for p in sorted(arm_dir.glob("*.json"))])
            for arm_dir in sorted(p for p in Path(nav_dir).iterdir() if p.is_dir() and p.name in ARMS)]
    tables = []
    for names in (RANK_METRICS, NAV_METRICS):
        lines = ["| arm | n | status | " + " | ".join(names) + " |", "|---" * (3 + len(names)) + "|"]
        for arm, rows in arms:
            statuses = {}
            for metrics in rows:
                statuses[metrics["status"]] = statuses.get(metrics["status"], 0) + 1
            cells = []
            for metric in names:
                values = [m[metric] for m in rows if m.get(metric) is not None]
                cells.append(f"{statistics.fmean(values):.3f}" if values else "–")
            status = ", ".join(f"{key} {value}" for key, value in sorted(statuses.items()))
            lines.append(f"| {arm} | {len(rows)} | {status} | " + " | ".join(cells) + " |")
        tables.append("\n".join(lines))
    return "\n\n".join(tables) + "\n"


async def _run_arm(model: Any, arm: str, root: Path, row: dict, sources: dict[str, str], tree: Path,
                   graphs_dir: Path, builder_hash: str, max_calls: int, audit_dir: Path) -> dict[str, Any]:
    files = FileTools(tree)
    try:
        return await _run_arm_tools(model, arm, root, row, tree, files, graphs_dir, builder_hash, max_calls, audit_dir)
    finally:
        files.close()   # stops the grep child process


async def _run_arm_tools(model: Any, arm: str, root: Path, row: dict, tree: Path, files: FileTools, graphs_dir: Path,
                         builder_hash: str, max_calls: int, audit_dir: Path) -> dict[str, Any]:
    tools: dict[str, Any] = {"grep": files.grep, "read_file": files.read_file, "list_dir": files.list_dir}
    build = ARMS[arm]
    if build is None:
        return await run_task(model, tools, files.schemas(), row, max_calls=max_calls)
    if build == "base":
        _, meta = load_or_build(root, row, tree, build="base", layers=build_layers("base", {}),
                                graphs_dir=graphs_dir, builder_hash=builder_hash)
    else:
        meta_path = graph_db_path(graphs_dir, build, row["instance_id"]).with_suffix(".meta.json")
        if not meta_path.exists():
            raise FileNotFoundError(f"{meta_path}: build it first with baseline/run_offline.py")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) | {"db": meta_path.with_suffix(".db")}
    async with GraphTools(tree, meta["db"], meta["graph_version"], row["instance_id"],
                          audit_dir / f"{arm}-{row['instance_id']}.jsonl", with_confidence=arm in CONFIDENCE_ARMS) as graph:
        for name in GraphTools.TOOLS:
            tools[name] = lambda _name=name, **kwargs: graph.call(_name, kwargs)
        return await run_task(model, tools, files.schemas() + graph.schemas(), row, max_calls=max_calls)


def _rescore(out: Path, root: Path, tasks: list[dict], arms: list[str], prepare_task: Any) -> int:
    """Recompute the metrics of saved results with the current ``score_nav`` (conversations are kept).

    An answer step the parser missed (no answer, ended by answering, the call budget or the context limit) is parsed
    again from its saved last turn, so every result uses the current ``parse_final``.
    """
    for row in tasks:
        paths = [out / arm / f"{row['instance_id']}.json" for arm in arms]
        if not any(path.exists() for path in paths):
            continue
        row = dict(row, patch=(root / row["gold_patch_path"]).read_text(encoding="utf-8"))
        sources, _ = prepare_task(root, row)
        for path in (p for p in paths if p.exists()):
            result = json.loads(path.read_text(encoding="utf-8"))
            if (result.get("answer") is None and result.get("turns")
                    and result.get("ended_by") in ("answer", "call_budget", "context_limit")):
                result["answer"] = parse_final(result["turns"][-1])
                if result["answer"]:
                    result["status"] = "OK"
            result["metrics"] = score_nav(result, row, sources) if result.get("usage") else {"status": "ERROR"}
            path.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
            print(f"rescored {path.parent.name}/{path.name}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    import anyio

    from baseline.run_offline import prepare_task

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arms", default="base,graph_v0", help=f"comma-separated, from {','.join(ARMS)}")
    parser.add_argument("--only", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--graphs-dir", type=Path)
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--rescore", action="store_true", help="recompute metrics of saved results; no model")
    args = parser.parse_args(argv)
    arms = args.arms.split(",")
    if set(arms) - set(ARMS):
        parser.error(f"--arms: unknown {sorted(set(arms) - set(ARMS))}")
    root = args.root.expanduser().resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require_split(manifest, allowed=("dev",), protocol="r1")
    tasks = manifest["tasks"]
    if args.only:
        wanted = set(args.only.read_text(encoding="utf-8").split())
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    tasks = tasks[: args.limit] if args.limit else tasks
    graphs_dir = (args.graphs_dir or root / "graphs").expanduser()
    builder_hash = runner.source_fingerprint(baseline._paths.ROOT)["digest"]
    if args.rescore:
        return _rescore(args.out, root, tasks, arms, prepare_task)
    from baseline.nav.model import QwenModel
    model = QwenModel(args.model_id)   # loaded once for the whole run
    for number, row in enumerate(tasks, 1):
        validate_task(row)
        row = dict(row, patch=(root / row["gold_patch_path"]).read_text(encoding="utf-8"))
        try:
            sources, tree = prepare_task(root, row)
            prepare_error = None
        except Exception as error:  # noqa: BLE001 -- one missing archive must not stop a long run
            sources, tree, prepare_error = None, None, f"{type(error).__name__}: {error}"
        for arm in arms:
            target = args.out / arm / f"{row['instance_id']}.json"
            if args.resume and target.exists() and json.loads(target.read_text(encoding="utf-8")).get("status") != "ERROR":
                continue   # errored runs (e.g. a CUDA failure) are run again
            started = time.perf_counter()
            try:
                if prepare_error:
                    raise RuntimeError(prepare_error)
                result = anyio.run(_run_arm, model, arm, root, row, sources, tree, graphs_dir, builder_hash,
                                   args.max_calls, args.out / "audit")
            except Exception as error:  # noqa: BLE001 -- the task stays in the denominator
                result = {"status": "ERROR", "reason": f"{type(error).__name__}: {error}", "answer": None,
                          "turns": [], "tool_calls": [], "spans": [], "usage": {"prompt_tokens": 0,
                                                                                  "completion_tokens": 0, "seconds": 0}}
            metrics = score_nav(result, row, sources) if sources is not None else {"status": "ERROR"}
            result.update(arm=arm, instance_id=row["instance_id"], model_id=args.model_id,
                          seconds=time.perf_counter() - started, metrics=metrics)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
            print(f"[{number}/{len(tasks)}] {row['instance_id']} {arm}: {result['status']} "
                  f"({result['seconds']:.0f} s, {len(result['tool_calls'])} calls)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
