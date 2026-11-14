"""GD1 evaluator on hand-made labelled sheets with known answers."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_graphdiff.py"


def _ev():
    spec = importlib.util.spec_from_file_location("evaluate_graphdiff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(number: int, label: str, *, split: str = "eval", annotator: str = "a") -> dict[str, str]:
    return {"row_id": f"r{number}", "split": split, "commit": "c", "path": "p.py", "entity": f"m.e{number}",
            "label": label, "annotator": annotator}


LABELS = ["bug-fix"] * 4 + ["refactor", "refactor", "formatting", "formatting", "unrelated", "unrelated"]


def _sheet():
    return [_row(i, label) for i, label in enumerate(LABELS)]


def test_prf_and_retention_known_values():
    predicted = {("c", "p.py", f"m.e{i}") for i in (0, 1, 2, 4)}  # 3 of 4 bug-fix, 1 refactor
    arm = _ev().evaluate(_sheet(), {"graphdiff": predicted})["arms"]["graphdiff"]
    assert (arm["precision"], arm["recall"], arm["f1"], arm["retention"]) == pytest.approx((0.75, 0.75, 0.75, 0.4))
    assert arm["predicted_negative_by_label"] == {"bug-fix": 1, "refactor": 1, "formatting": 2, "unrelated": 2}


def test_raw_baseline_has_recall_one():
    arm = _ev().evaluate(_sheet(), {})["arms"]["raw_baseline"]
    assert (arm["precision"], arm["recall"], arm["retention"]) == pytest.approx((0.4, 1.0, 1.0))


def test_unsure_rows_excluded_and_counted():
    rows = _sheet() + [_row(20, "unsure"), _row(21, "unsure")]
    result = _ev().evaluate(rows, {"graphdiff": {("c", "p.py", "m.e20")}})
    assert result["unsure"] == 2 and result["rows"] == 10
    assert result["arms"]["graphdiff"]["retention"] == 0.0


def test_kappa_on_double_labels():
    first = ["bug-fix"] * 5 + ["refactor"] * 5
    second = ["bug-fix"] * 4 + ["refactor"] + ["bug-fix"] + ["refactor"] * 4
    rows = [_row(i, label) for i, label in enumerate(first)] + \
        [_row(i, label, annotator="b") for i, label in enumerate(second)]
    result = _ev().evaluate(rows, {})
    assert result["kappa"]["double_labelled_rows"] == 10
    assert result["kappa"]["cohen_kappa"] == pytest.approx(0.6)
    assert result["rows"] == 10  # the first annotator's label is used for the metrics


def test_only_eval_split_by_default():
    rows = _sheet() + [_row(30, "bug-fix", split="dev")]
    assert _ev().evaluate(rows, {})["rows"] == 10
    assert _ev().evaluate(rows, {}, split="dev")["rows"] == 1


def test_uncovered_commits_are_excluded_and_reported():
    rows = _sheet() + [dict(_row(40, "bug-fix"), commit="other")]
    result = _ev().evaluate(rows, {"graphdiff": set()}, covered_commits={"c"})
    assert result["uncovered_commits"] == ["other"] and result["uncovered_rows"] == 1 and result["rows"] == 10


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError):
        _ev().evaluate([_row(0, "bugfix")], {})


def _write_run(folder: Path, edits: list[dict], summary: dict) -> None:
    folder.mkdir(parents=True)
    (folder / "graph_edits.jsonl").write_text("".join(json.dumps(e) + "\n" for e in edits), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_cli_reads_runs_and_writes_report(tmp_path):
    sheet = tmp_path / "sheet.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["row_id", "split", "commit", "path", "entity", "label", "annotator"])
        writer.writeheader()
        writer.writerows(_sheet())
    edit = {"commit_id": "c", "path": "p.py", "entity": "m.e0", "validated": True, "high_confidence": False}
    summary = {"commit_ids": ["c"], "parse_errors": [{"commit": "c"}],
               "refactoringminer_fallbacks": {"no output for commit": 2},
               "refactoringminer_version": "3.2.0", "python_version": "3.11"}
    _write_run(tmp_path / "full", [edit], summary)
    _write_run(tmp_path / "ast", [edit, dict(edit, entity="m.e4")], dict(summary, refactoringminer_version=None))
    out = tmp_path / "gd1"
    assert _ev().main(["--sheet", str(sheet), "--full", str(tmp_path / "full"), "--ast-only", str(tmp_path / "ast"),
                       "--out", str(out)]) == 0
    report = json.loads((out / "gd1.json").read_text(encoding="utf-8"))
    assert report["arms"]["graphdiff"]["recall"] == 0.25 and report["arms"]["graphdiff_high_confidence"]["recall"] == 0
    assert report["arms"]["ast_only"]["precision"] == 0.5
    # counted on the full runs only (the ast-only run covers the same commits)
    assert report["parse_errors"] == 1 and report["commits_without_refactoringminer"] == 2
    assert report["title"].startswith("GD1") and (out / "gd1.md").read_text(encoding="utf-8").startswith("# GD1")


def test_cli_fails_when_a_sheet_commit_has_no_run(tmp_path):
    sheet = tmp_path / "sheet.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["row_id", "split", "commit", "path", "entity", "label", "annotator"])
        writer.writeheader()
        writer.writerows(_sheet())
    _write_run(tmp_path / "full", [], {"commit_ids": ["elsewhere"]})
    out = tmp_path / "gd1"
    assert _ev().main(["--sheet", str(sheet), "--full", str(tmp_path / "full"), "--out", str(out)]) == 1
    assert json.loads((out / "gd1.json").read_text(encoding="utf-8"))["uncovered_commits"] == ["c"]


def test_cli_dev_split_is_not_called_gd1(tmp_path):
    sheet = tmp_path / "sheet.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["row_id", "split", "commit", "path", "entity", "label", "annotator"])
        writer.writeheader()
        writer.writerows([_row(0, "bug-fix", split="dev")])
    _write_run(tmp_path / "full", [], {"commit_ids": ["c"]})
    out = tmp_path / "gd1"
    _ev().main(["--sheet", str(sheet), "--full", str(tmp_path / "full"), "--out", str(out), "--split", "dev"])
    assert json.loads((out / "gd1.json").read_text(encoding="utf-8"))["title"].startswith("development split, not GD1")
