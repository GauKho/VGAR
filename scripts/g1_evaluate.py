"""G1 evaluator (spec 2026-11-16): call edge and name-use P/R of the graph against the locked labels.

  python scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report \
      [--tsg-executable P --tsg-tree-sitter-dir P] [--enable-jarvis] [--scip-entry P --scip-node node]

Exit codes: 0 report written; 2 sheets not locked, edited after the lock, or checkout differs from the kit;
3 the user's agreement labels disagree with Claude's and settlement.csv does not settle all of them
(disagreements.csv is written for the user to fill in).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.g1_labels import (
    DEFAULT_AGREEMENT_SHEET,
    SHEETS,
    GraphIndex,
    bom_adjusted,
    check_lock,
    item_from_dict,
    micro_pr,
    parse_label,
    read_sheet,
    run_agreements,
    score_item,
    sha256_file,
)

NOTE = ("Labels assigned by Claude; 30 items were labelled a second time by a separate Claude pass (not a human); "
        "disagreements are settled by the user.")
HUMAN_NOTE = ("Labels assigned by Claude; agreement with a human labeller on the items of the agreement sheet; "
              "disagreements are settled by the user.")


def _configurations(args) -> dict:
    from vgar.graph.layer_config import LayerConfigs, layers_from_args, scip_config

    base = layers_from_args(args)
    configs = {"static": LayerConfigs()}
    configs["tsg"] = LayerConfigs(tsg=base.tsg) if base.tsg else "not run: no --tsg-executable"
    if base.tsg and base.jarvis:
        configs["tsg_jarvis"] = LayerConfigs(tsg=base.tsg, jarvis=base.jarvis)
    else:
        configs["tsg_jarvis"] = "not run: needs --tsg-executable and --enable-jarvis"
    if base.tsg and args.scip_entry:
        scip = scip_config(args.scip_entry, node=args.scip_node, timeout=600, strict=False, environment=None,
                           native_config=False, import_roots=(), target_only=None, python=None)
        configs["scip_tsg"] = LayerConfigs(tsg=base.tsg, scip=scip)
    else:
        configs["scip_tsg"] = "not run: needs --tsg-executable and --scip-entry"
    return configs


def _labels(rows: dict, items: dict) -> dict:
    return {i: parse_label(row["label"], items[i].candidates) for i, row in rows.items() if row["label"].strip()}


def _evaluate(configs, tasks, items, labels) -> dict:
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.layer_config import layer_summary

    out = {}
    for name, layers in configs.items():
        if isinstance(layers, str):
            out[name] = {"status": layers}
            continue
        rows_calls, rows_calls_may, rows_names, graphs = [], [], [], {}
        for task in tasks:
            document = PythonGraphBuilder(repo_key=task["task_id"], repository_revision=task["base_commit"],
                                          **layers.builder_kwargs()).build(Path(task["tree"]))
            graphs[task["task_id"]] = {"graph_version": document.get("graph_version"),
                                       "layers": layer_summary(document, layers)}
            index = GraphIndex(document)
            for item_id, item in items.items():
                if item.task_id != task["task_id"]:
                    continue
                item = bom_adjusted(item, Path(task["tree"]))
                if item.kind == "call":
                    rows_calls.append(score_item(index, item_id, item, labels[item_id]))
                    rows_calls_may.append(score_item(index, item_id, item, labels[item_id], may_call=True))
                else:
                    rows_names.append(score_item(index, item_id, item, labels[item_id]))
        has_reads = layers.tsg is not None
        expressible = [r for r in rows_names if r.label.cls == "in_repo" and r.label.targets
                       and all(not isinstance(t, str) and t.kind in {"global", "field"} for t in r.label.targets)]
        per_repo = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        for row in rows_calls + (rows_names if has_reads else []):
            tp = len(row.truth & row.predicted)
            per_repo[f"{row.kind}:{row.repo}"]["tp"] += tp
            per_repo[f"{row.kind}:{row.repo}"]["fp"] += len(row.predicted) - tp
            per_repo[f"{row.kind}:{row.repo}"]["fn"] += len(row.truth) - tp
        out[name] = {
            "status": "ok",
            "calls": {"calls_only": micro_pr(rows_calls), "with_may_call": micro_pr(rows_calls_may),
                      "status_counts": dict(Counter(r.status for r in rows_calls)),
                      "external_or_builtin_linked": sum(r.label.cls in {"external", "builtin"} and bool(r.predicted)
                                                        for r in rows_calls),
                      "unmapped_targets": sum(r.unmapped for r in rows_calls)},
            "names": ({"all": micro_pr(rows_names),
                       "in_function": micro_pr([r for r in rows_names if r.status != "outside_function"]),
                       "expressible": micro_pr(expressible),
                       "status_counts": dict(Counter(r.status for r in rows_names)),
                       "unmapped_targets": sum(r.unmapped for r in rows_names)}
                      if has_reads else "not applicable: reads edges need tree-sitter-graph"),
            "per_repo": dict(per_repo), "graphs": graphs}
    return out


def _fmt(pr: dict) -> str:
    def num(v):
        return "—" if v is None else f"{v:.3f}"

    def ci(v):
        return "" if not v else f" [{v[0]:.3f}; {v[1]:.3f}]"
    return (f"P {num(pr['precision'])}{ci(pr['precision_ci95'])} · R {num(pr['recall'])}{ci(pr['recall_ci95'])} "
            f"(n={pr['n']}, tp={pr['tp']}, fp={pr['fp']}, fn={pr['fn']})")


def _markdown(report: dict) -> str:
    lines = ["# G1 labelled edges report", "", report.get("note", NOTE), ""]
    agree = report.get("agreement")
    if report.get("agreement_status"):
        lines += [f"**Agreement {report['agreement_status']}** — the labels are Claude's alone.", ""]
    if agree:
        kappa = "—" if agree["kappa"] is None else f"{agree['kappa']:.3f}"
        lines += [(f"Agreement on {agree['n']} items: raw {agree['raw']:.3f}, kappa {kappa}; "
                   f"settled: {len(report['settlement']['changed'])}."), ""]
    for name, block in report["configurations"].items():
        lines.append(f"## {name}")
        if block["status"] != "ok":
            lines += [block["status"], ""]
            continue
        lines += [f"- calls, CALLS: {_fmt(block['calls']['calls_only'])}",
                  f"- calls, CALLS + MAY_CALL: {_fmt(block['calls']['with_may_call'])}"]
        if isinstance(block["names"], dict):
            lines += [f"- name uses, all: {_fmt(block['names']['all'])}",
                      f"- name uses, inside function bodies: {_fmt(block['names']['in_function'])}",
                      f"- name uses, expressible (globals and fields): {_fmt(block['names']['expressible'])}"]
        else:
            lines.append(f"- name uses: {block['names']}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    from vgar.graph.layer_config import add_layer_options

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scip-entry", type=Path)
    parser.add_argument("--scip-node", default="node")
    parser.add_argument("--agreement-sheet", default=DEFAULT_AGREEMENT_SHEET,
                        help="agreement sheet in the kit; any other name than the default is a human labeller's")
    add_layer_options(parser)
    args = parser.parse_args(argv)
    kit = args.kit
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    try:
        for sheet in SHEETS:
            check_lock(kit, sheet)
        for task in manifest["tasks"]:
            if sha256_file(Path(task["archive"])) != task["archive_sha256"]:
                raise ValueError(f"archive of {task['task_id']} differs from the kit")
    except (ValueError, FileNotFoundError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    items = {k: item_from_dict(v) for k, v in json.loads((kit / "items.json").read_text(encoding="utf-8")).items()}
    main_rows = {**read_sheet(kit / "calls.csv"), **read_sheet(kit / "name_uses.csv")}
    labels = _labels(main_rows, items)
    outcome = run_agreements(kit, args.agreement_sheet, manifest, items, labels, main_rows)
    if outcome.exit_code is not None:
        return outcome.exit_code
    labels = outcome.labels
    report = {"note": HUMAN_NOTE if outcome.report["agreement_source"] == "human" else NOTE, **outcome.report}
    report["configurations"] = _evaluate(_configurations(args), manifest["tasks"], items, labels)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "g1_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=list),
                                             encoding="utf-8")
    (args.out / "g1_report.md").write_text(_markdown(report), encoding="utf-8")
    print(args.out / "g1_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
