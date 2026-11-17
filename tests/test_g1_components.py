"""Component boundary quality kit (plan 2026-11-17 Task 3; spec §1.2): sampling, sheet, score."""
from __future__ import annotations

import pytest

from vgar.evaluation.g1_components import (
    boundary_quality,
    read_component_sheet,
    sample_components,
    write_component_sheet,
)


def _doc(repo: str, names: list[str]) -> dict:
    nodes = [{"id": f"vgar:{repo}:python:component:{n}", "type": "Component", "name": n, "qualified_name": n,
              "properties": {"files": [f"{n}/__init__.py"]}} for n in names]
    return {"repo_key": f"{repo}-task", "nodes": nodes, "edges": []}


def test_sample_is_capped_per_repo_and_deterministic():
    docs = {"r1": _doc("r1", ["a", "b", "c"]), "r2": _doc("r2", ["x"])}
    first = sample_components(docs, per_repo=2, seed=0)
    assert [c["repo"] for c in first].count("r1") == 2 and [c["repo"] for c in first].count("r2") == 1
    assert first == sample_components(docs, per_repo=2, seed=0)
    assert first[0].keys() == {"component_id", "repo", "task_id", "name", "files"}


def test_sheet_round_trip_has_empty_labels(tmp_path):
    sampled = sample_components({"r1": _doc("r1", ["a"])}, per_repo=5, seed=0)
    write_component_sheet(tmp_path / "components.csv", sampled)
    rows = read_component_sheet(tmp_path / "components.csv")
    assert [r["component_id"] for r in rows] == ["vgar:r1:python:component:a"] and rows[0]["label"] == ""
    assert rows[0]["files"] == "a/__init__.py"


def test_boundary_quality_counts_and_rate():
    rows = [{"label": "correct"}, {"label": "Merge "}, {"label": "correct"}, {"label": "split"}]
    result = boundary_quality(rows)
    assert (result["n"], result["correct"], result["merge"], result["split"]) == (4, 2, 1, 1)
    assert result["correct_rate"] == 0.5 and len(result["ci95"]) == 2


def _kit_cli(monkeypatch):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "g1_component_kit.py"
    spec = importlib.util.spec_from_file_location("g1_component_kit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_documents", lambda kit: {"r1": _doc("r1", ["a", "b"])})
    return module


def _label_all(sheet, label="correct", drop=0):
    rows = read_component_sheet(sheet)[drop:]
    for row in rows:
        row["label"] = label
    import csv
    with open(sheet, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_lock_cannot_be_redone(tmp_path, monkeypatch):
    kit = _kit_cli(monkeypatch)
    out = tmp_path / "c"
    assert kit.main(["--kit", "k", "--out", str(out)]) == 0
    _label_all(out / "components.csv")
    assert kit.main(["--kit", "k", "--out", str(out), "--lock"]) == 0
    _label_all(out / "components.csv", "split")
    assert kit.main(["--kit", "k", "--out", str(out), "--lock"]) == 2
    assert kit.main(["--kit", "k", "--out", str(out), "--score"]) == 2


def test_dropped_rows_are_refused(tmp_path, monkeypatch):
    kit = _kit_cli(monkeypatch)
    out = tmp_path / "c"
    kit.main(["--kit", "k", "--out", str(out)])
    _label_all(out / "components.csv", drop=1)
    assert kit.main(["--kit", "k", "--out", str(out), "--lock"]) == 2


def test_boundary_quality_refuses_blank_or_unknown():
    with pytest.raises(ValueError):
        boundary_quality([{"label": ""}])
    with pytest.raises(ValueError):
        boundary_quality([{"label": "maybe"}])
