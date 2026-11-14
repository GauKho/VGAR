"""CLI scripts/graphdiff.py writes graph edits, the raw-diff baseline and a summary."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from git_fixture import linear_repo, write_tree

from vgar.graph.builder import PythonGraphBuilder

pytest.importorskip("dulwich")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "graphdiff.py"


def _load():
    spec = importlib.util.spec_from_file_location("graphdiff_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> tuple[Path, Path, str]:
    source = b"def total(items):\n    return sum(items)\n"
    root = tmp_path / "repo"
    ids = linear_repo(root, [("base", {"src/shop/cart.py": source}),
                             ("Fix total", {"src/shop/cart.py": source.replace(b"sum(items)", b"sum(items) or 0")})])
    tree = write_tree(tmp_path / "tree", {"src/shop/cart.py": source.replace(b"sum(items)", b"sum(items) or 0")})
    document = PythonGraphBuilder(repo_key="fx", repository_revision=ids[-1], source_roots=("src",)).build(tree)
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps(document), encoding="utf-8")
    return root, graph, ids[-1]


def test_cli_writes_three_files(tmp_path, monkeypatch):
    for name in ("VGAR_REFACTORINGMINER_HOME", "VGAR_JAVA_HOME", "VGAR_REFACTORINGMINER_OUTPUT"):
        monkeypatch.delenv(name, raising=False)
    root, graph, head = _repo(tmp_path)
    out = tmp_path / "out"
    assert _load().main([str(root), "--graph", str(graph), "--max-commits", "5", "--out", str(out)]) == 0
    edits = [json.loads(line) for line in (out / "graph_edits.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = [json.loads(line) for line in (out / "raw_baseline.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["commits_read"] == 2 and summary["revision"] == head
    assert any(edit["edit_type"] == "UPDATE_METHOD_BODY" and edit["validated"] for edit in edits)
    assert raw and "symbol" in raw[0]
    assert summary["command"][0].endswith("graphdiff.py")


def test_cli_default_out_folder_under_results(tmp_path, monkeypatch):
    root, graph, head = _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert _load().main([str(root), "--graph", str(graph)]) == 0
    assert (tmp_path / "results" / "graphdiff" / f"repo-{head[:12]}" / "summary.json").is_file()


def test_cli_rejects_relative_refactoringminer_home(tmp_path):
    root, graph, _ = _repo(tmp_path)
    with pytest.raises(SystemExit):
        _load().main([str(root), "--graph", str(graph), "--rm-home", "relative"])
