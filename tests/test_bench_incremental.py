"""U1 incremental benchmark (M1-W12-1): scenarios, correctness against full rebuild, report rendering."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.evaluation.incremental_bench import MAX_REPEATS, SCENARIOS, pick_target, render_u1, run_bench
from vgar.graph.builder import PythonGraphBuilder

ROOT = Path(__file__).resolve().parents[1]
BASE = {
    "src/a.py": "from b import f\n\ndef caller():\n    return f()\n",
    "src/b.py": "def f():\n    return 1\n\ndef g():\n    return f()\n",
}


@pytest.fixture
def fixture_repo(tmp_path):
    root = tmp_path / "repo"
    for relative, text in BASE.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_pick_target_is_deterministic(fixture_repo):
    document = PythonGraphBuilder(repo_key="demo/u1", repository_revision="r", source_roots=("src",)).build(fixture_repo)
    assert pick_target(document, ("src",)) == pick_target(copy.deepcopy(document), ("src",))
    assert pick_target(document, ("src",)) == {"path": "src/b.py", "qualified_name": "b.f", "start_line": 1}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_each_scenario_matches_full_rebuild(fixture_repo, tmp_path, scenario):
    result = run_bench(fixture_repo, ("src",), repeats=2, workdir=tmp_path / "w")
    row = result["scenarios"][scenario]
    assert row["match"] is True
    assert len(row["warm_seconds"]) == 2 and len(row["cold_seconds"]) == 3
    assert row["files_changed"] >= 1 and 0 <= row["cache_hit"] <= 1


def test_repeats_bounded(fixture_repo, tmp_path):
    with pytest.raises(ValueError):
        run_bench(fixture_repo, ("src",), repeats=MAX_REPEATS + 1, workdir=tmp_path / "w")


def test_render_is_a_pure_function_of_json(fixture_repo, tmp_path):
    result = run_bench(fixture_repo, ("src",), repeats=2, workdir=tmp_path / "w")
    markdown = render_u1(result)
    assert markdown.splitlines()[0].startswith("| Kịch bản | Cold build (s) | Warm update p50/p95 (s) | Speedup")
    assert "phần parse là O(Δ), phần link vẫn O(N)" in markdown
    assert render_u1(json.loads(json.dumps(result))) == markdown
    result["scenarios"]["body_edit"]["match"] = False
    assert render_u1(result) != markdown


def test_bench_never_touches_source_repo(fixture_repo, tmp_path):
    before = _snapshot(fixture_repo)
    subprocess.run([sys.executable, "scripts/bench_incremental.py", "--repo", str(fixture_repo), "--source-roots", "src",
                    "--repeats", "2", "--out", str(tmp_path / "out")], check=True, cwd=ROOT)
    assert _snapshot(fixture_repo) == before
    assert (tmp_path / "out/u1.json").exists() and (tmp_path / "out/u1.md").exists()


def test_cli_fixture_mode(tmp_path):
    subprocess.run([sys.executable, "scripts/bench_incremental.py", "--fixture", "--repeats", "2",
                    "--out", str(tmp_path / "o")], check=True, cwd=ROOT)
    data = json.loads((tmp_path / "o/u1.json").read_text(encoding="utf-8"))
    assert set(data["scenarios"]) == set(SCENARIOS) and all(row["match"] for row in data["scenarios"].values())


def test_cli_rejects_too_many_repeats(tmp_path):
    process = subprocess.run([sys.executable, "scripts/bench_incremental.py", "--fixture", "--repeats", str(MAX_REPEATS + 1),
                              "--out", str(tmp_path / "o")], cwd=ROOT, capture_output=True, text=True)
    assert process.returncode != 0 and "repeats" in process.stderr
