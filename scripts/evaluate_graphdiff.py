"""GD1 from a labelled GraphDiff sheet: P/R/F1, retention and noise confusion against the raw-diff baseline.

Positives are rows labelled ``bug-fix``; ``unsure`` rows are counted and excluded. A row is predicted
positive by an arm when that arm has a validated edit on the same (commit, path, entity). Arms:
``graphdiff`` (validated edits of the full run), ``graphdiff_high_confidence``, ``ast_only``
(approach C, validated edits of a run without RefactoringMiner) and ``raw_baseline`` (every row).
Only the evaluation split is GD1; ``--split dev`` is for tuning and is titled so.

Usage:
    python scripts/evaluate_graphdiff.py --sheet sheet.csv --full <run dir>... [--ast-only <run dir>...]
        --out <dir> [--split eval]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

LABELS = ("bug-fix", "refactor", "formatting", "unrelated", "unsure")
Key = tuple[str, str, str]


def _key(row: Mapping[str, Any]) -> Key:
    return (row["commit"], row["path"], row["entity"])


def _kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[label] * right[label] for label in LABELS) / len(pairs) ** 2
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def _scores(rows: Sequence[Mapping[str, str]], predicted: set[Key] | None) -> dict[str, Any]:
    tp = fp = fn = 0
    negatives: Counter[str] = Counter()
    positives = 0
    for row in rows:
        hit = predicted is None or _key(row) in predicted
        gold = row["label"] == "bug-fix"
        if hit:
            positives += 1
            tp, fp = tp + gold, fp + (not gold)
        else:
            fn += gold
            negatives[row["label"]] += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall) if precision and recall else 0.0) \
        if precision is not None and recall is not None else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "predicted_positive": positives, "retention": positives / len(rows) if rows else None,
            "predicted_negative_by_label": dict(sorted(negatives.items()))}


def evaluate(rows: Iterable[Mapping[str, str]], predictions: Mapping[str, set[Key]], *,
             split: str = "eval", covered_commits: set[str] | None = None) -> dict[str, Any]:
    """Metrics per arm on one split.

    Args:
        rows: Sheet rows (``row_id, split, commit, path, entity, label, annotator``); a second row with the
            same ``row_id`` is a second annotator's label.
        predictions: Arm name -> keys predicted positive; ``raw_baseline`` is added (every row).
        split: ``eval`` (GD1) or ``dev``.
        covered_commits: Commits the GraphDiff runs read; rows of other commits are excluded and reported
            (they would otherwise count as predicted negatives). ``None`` skips the check.

    Raises:
        ValueError: A label outside the five allowed values.
    """
    primary: dict[str, Mapping[str, str]] = {}
    second: dict[str, str] = {}
    for row in rows:
        if row["split"] != split:
            continue
        if row["label"] not in LABELS:
            raise ValueError(f"row {row['row_id']}: label {row['label']!r} is not one of {LABELS}")
        if row["row_id"] not in primary:
            primary[row["row_id"]] = row
        elif row["row_id"] not in second and row.get("annotator") != primary[row["row_id"]].get("annotator"):
            second[row["row_id"]] = row["label"]
    uncovered = sorted({row["commit"] for row in primary.values()
                        if covered_commits is not None and row["commit"] not in covered_commits})
    uncovered_rows = sum(row["commit"] in uncovered for row in primary.values())
    primary = {key: row for key, row in primary.items() if row["commit"] not in uncovered}
    labelled = [row for row in primary.values() if row["label"] != "unsure"]
    arms = {name: _scores(labelled, set(keys)) for name, keys in predictions.items()}
    arms["raw_baseline"] = _scores(labelled, None)
    pairs = [(primary[row_id]["label"], label) for row_id, label in second.items()]
    return {"split": split, "rows": len(labelled), "unsure": len(primary) - len(labelled),
            "positives": sum(row["label"] == "bug-fix" for row in labelled), "arms": arms,
            "kappa": {"double_labelled_rows": len(pairs), "cohen_kappa": _kappa(pairs)},
            "uncovered_commits": uncovered, "uncovered_rows": uncovered_rows}


def _predictions(folders: Sequence[Path], field: str) -> tuple[set[Key], list[dict[str, Any]]]:
    keys: set[Key] = set()
    summaries = []
    for folder in folders:
        for line in (folder / "graph_edits.jsonl").read_text(encoding="utf-8").splitlines():
            edit = json.loads(line)
            if edit.get(field):
                keys.add((edit["commit_id"], edit["path"], edit["entity"]))
        summary = folder / "summary.json"
        summaries.append(json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else {})
    return keys, summaries


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--full", type=Path, nargs="+", required=True)
    parser.add_argument("--ast-only", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--split", choices=("eval", "dev"), default="eval")
    args = parser.parse_args(argv)
    with args.sheet.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    full, summaries = _predictions(args.full, "validated")
    high, _ = _predictions(args.full, "high_confidence")
    predictions = {"graphdiff": full, "graphdiff_high_confidence": high}
    if args.ast_only:
        predictions["ast_only"], _ = _predictions(args.ast_only, "validated")
    covered: set[str] | None = set()
    for summary in summaries:
        if "commit_ids" not in summary:
            covered = None  # an older run without its commit list: coverage cannot be checked
            break
        covered |= set(summary["commit_ids"])  # type: ignore[operator]
    result = evaluate(rows, predictions, split=args.split, covered_commits=covered)
    title = "GD1 (evaluation split)" if args.split == "eval" else "development split, not GD1"
    result.update(
        title=title, command=[str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])],
        parse_errors=sum(len(s.get("parse_errors", [])) for s in summaries),
        commits_without_refactoringminer=sum(sum(s.get("refactoringminer_fallbacks", {}).values()) for s in summaries),
        refactoringminer_versions=sorted({s["refactoringminer_version"] for s in summaries
                                          if s.get("refactoringminer_version")}),
        python_versions=sorted({s["python_version"] for s in summaries if s.get("python_version")}))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "gd1.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# {title}", "", (f"Rows: {result['rows']} (bug-fix {result['positives']}), unsure excluded: "
                                f"{result['unsure']}, Cohen's kappa: {_fmt(result['kappa']['cohen_kappa'])} on "
                                f"{result['kappa']['double_labelled_rows']} double-labelled rows"), "",
             (f"Sheet commits not read by any run (rows excluded): {result['uncovered_commits']} "
              f"({result['uncovered_rows']} rows)"), "",
             "| Arm | P | R | F1 | Retention | Predicted negatives by label |", "|---|---:|---:|---:|---:|---|"]
    for name, arm in result["arms"].items():
        lines.append(f"| {name} | {_fmt(arm['precision'])} | {_fmt(arm['recall'])} | {_fmt(arm['f1'])} | "
                     f"{_fmt(arm['retention'])} | {arm['predicted_negative_by_label']} |")
    lines += ["", (f"Parse errors: {result['parse_errors']}; commits without RefactoringMiner: "
                   f"{result['commits_without_refactoringminer']}; RefactoringMiner: "
                   f"{result['refactoringminer_versions']}; Python: {result['python_versions']}"), "", "Command: `" + " ".join(result["command"]) + "`"]
    (args.out / "gd1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"title": title, "rows": result["rows"], "uncovered_commits": len(result["uncovered_commits"])}))
    return 1 if result["uncovered_commits"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
