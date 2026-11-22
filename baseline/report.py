"""Layer report (spec 2026-11-19 §6): T0 graph quality (G1), T1 profiles in cumulative order, T2 navigation.

  python baseline/report.py --layers ~/rt1/results/layers --g1 ~/rt1/g1/report_scip4/g1_report.json \
      --nav ~/rt1/results/nav --out docs/status/tv2_layer_harness_<date>.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import baseline._paths  # noqa: F401

# isort: split
import compare_runs

from baseline.profiles import BASELINE_PROFILE, PROFILE_ORDER

DEFAULT_METRICS = ["file_recall@1", "function_recall@5", "function_mrr", "native_gold_function_in_context",
                   "native_all_gold_files_in_context", "native_frontier_in_context", "native_context_tokens"]
TEXT_ARMS = ("bm25", "grep", "neighbor", "embedding")


def _fmt(value: float, metric: str) -> str:
    return f"{value:.0f}" if "tokens" in metric else f"{value:.3f}"


def layer_table(run_dir: Path, metrics: list[str], min_gold_files: int = 0) -> str:
    """Markdown: every profile present, mean and paired delta against the previous profile present (shared tasks).

    A profile in ``BASELINE_PROFILE`` is compared with its named profile when that one is present, and never becomes
    the previous profile of the next row.
    """
    loaded = compare_runs.load(Path(run_dir))
    run = {i: t for i, t in loaded.items() if t.get("status") == "SUCCEEDED"
           and compare_runs.gold_file_count(t) >= min_gold_files}
    errors = len(loaded) - sum(t.get("status") == "SUCCEEDED" for t in loaded.values())
    present = [p for p in PROFILE_ORDER if any(p in t["arms"] for t in run.values())]
    lines = [f"Tasks: {len(run)} (≥ {min_gold_files} gold files), {errors} ERROR", "",
             "| profile | vs | n | " + " | ".join(metrics) + " |", "|---" * (3 + len(metrics)) + "|"]
    previous = None
    for profile in present + [arm for arm in TEXT_ARMS if any(arm in t["arms"] for t in run.values())]:
        base = BASELINE_PROFILE.get(profile) if BASELINE_PROFILE.get(profile) in present else previous
        if base is None or profile in TEXT_ARMS:
            ids = [i for i, t in run.items() if profile in t["arms"]]
            cells = []
            for metric in metrics:
                values = [run[i]["arms"][profile]["metrics"].get(metric) for i in ids]
                values = [v for v in values if v is not None]
                cells.append(_fmt(statistics.fmean(values), metric) if values else "–")
            lines.append(f"| {profile} | – | n={len(ids)} | " + " | ".join(cells) + " |")
        else:
            shared = {i: t for i, t in run.items() if base in t["arms"] and profile in t["arms"]}
            out = compare_runs.compare_arms(shared, base, [profile])
            cells = []
            for metric in metrics:
                pair = out["pairs"].get(profile, {}).get(metric)
                if pair is None:
                    cells.append("–")
                    continue
                mean = out["means"][profile][metric][1]
                low, high = pair["ci95"]
                cells.append(f"{_fmt(mean, metric)} ({pair['delta']:+.3f} [{low:+.3f}; {high:+.3f}] "
                             f"{pair['wins']}/{pair['losses']})")
            lines.append(f"| {profile} | {base} | n={out['n_tasks']} | " + " | ".join(cells) + " |")
        if profile not in TEXT_ARMS and profile not in BASELINE_PROFILE:
            previous = profile
    return "\n".join(lines) + "\n"


def g1_table(g1_json: Path) -> str:
    """Markdown: call edge precision/recall per G1 configuration (CALLS only, and with MAY_CALL)."""
    configurations = json.loads(Path(g1_json).read_text(encoding="utf-8"))["configurations"]
    lines = ["| configuration | CALLS P | CALLS R | CALLS R CI95 | +MAY_CALL P | +MAY_CALL R |", "|---" * 6 + "|"]
    for name, block in configurations.items():
        if block.get("status") != "ok":
            lines.append(f"| {name} | {block.get('status')} | | | | |")
            continue
        calls, both = block["calls"]["calls_only"], block["calls"]["with_may_call"]
        low, high = calls["recall_ci95"]
        lines.append(f"| {name} | {calls['precision']:.3f} | {calls['recall']:.3f} | [{low:.3f}; {high:.3f}] "
                     f"| {both['precision']:.3f} | {both['recall']:.3f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layers", type=Path, help="run directory of baseline/run_offline.py")
    parser.add_argument("--g1", type=Path, action="append", default=[], help="g1_report.json (repeatable)")
    parser.add_argument("--t0-link", action="append", default=[], metavar="NAME=PATH",
                        help="other T0 reports (TR-1, GD1, U1), listed with their path")
    parser.add_argument("--nav", type=Path, help="run directory of baseline/nav/run_nav.py")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    parts = ["# Layer harness report", "", "Generated by: `python baseline/report.py " + " ".join(sys.argv[1:]) + "`", ""]
    if args.g1 or args.t0_link:
        parts += ["## T0 graph quality", ""]
        for path in args.g1:
            parts += [f"G1 `{path}`", "", g1_table(path)]
        parts += [f"- {link.split('=', 1)[0]}: `{link.split('=', 1)[-1]}`" for link in args.t0_link] + [""]
    if args.layers:
        parts += ["## T1 profiles (offline)", "", f"Run `{args.layers}`", "", "### All tasks", "",
                  layer_table(args.layers, DEFAULT_METRICS), "### Multi-file tasks (≥ 2 gold files)", "",
                  layer_table(args.layers, DEFAULT_METRICS, min_gold_files=2)]
    if args.nav:
        from baseline.nav.run_nav import nav_table
        parts += ["## T2 navigation (Qwen)", "", nav_table(args.nav)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
