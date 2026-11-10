"""RT-1 measurement tooling: gold for the 50-task dev manifest and the streaming ablation driver."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gold = _load("materialize_dev_gold", "scripts/materialize_dev_gold.py")
ablation = _load("run_rt1_ablation", "scripts/run_rt1_ablation.py")

PATCH = "diff --git a/pkg/core.py b/pkg/core.py\n--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
DEV_IDS = ["owner__repo-1", "owner__repo-6"]   # both fall in the dev split (checked below)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _manifest_and_parquet(tmp_path: Path, *, query_hash_ok: bool = True):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from vgar.evaluation.retrieval.dataset import split_of
    assert all(split_of(i) == "dev" for i in DEV_IDS)
    rows = [{"instance_id": i, "repo": "owner/repo", "base_commit": "a" * 40, "problem_statement": f"bug {i}",
             "patch": PATCH, "FAIL_TO_PASS": "[\"tests/test_core.py::test_x\"]"} for i in DEV_IDS]
    parquet = tmp_path / "test-00000-of-00001.parquet"
    pq.write_table(pa.Table.from_pylist(rows), parquet)
    tasks = [{"instance_id": r["instance_id"], "repo": r["repo"], "base_commit": r["base_commit"],
              "problem_statement": r["problem_statement"], "split": "dev", "version": "1",
              "query_hash": _sha(r["problem_statement"].encode()) if query_hash_ok else "sha256:" + "0" * 64}
             for r in rows]
    manifest = {"dataset_id": "princeton-nlp/SWE-bench_Verified", "dataset_revision": "c" * 40, "split": "dev",
                "parquet_hash": _sha(parquet.read_bytes()), "manifest_hash": "sha256:" + "1" * 64, "tasks": tasks}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, parquet


def test_materialize_adds_gold_fields(tmp_path):
    manifest, parquet = _manifest_and_parquet(tmp_path)
    out = gold.materialize(manifest, parquet, tmp_path / "root")
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source_manifest_hash"] == "sha256:" + "1" * 64
    task = written["tasks"][0]
    assert task["changed_source_files"] == ["pkg/core.py"] and task["is_multi_file"] is False
    assert task["patch_hash"] == _sha(PATCH.encode())
    assert (tmp_path / "root" / task["gold_patch_path"]).read_text(encoding="utf-8") == PATCH
    assert (tmp_path / "root" / "data" / "downloads" / ("c" * 40) / parquet.name).exists()


def test_materialize_rejects_a_different_parquet(tmp_path):
    manifest, parquet = _manifest_and_parquet(tmp_path)
    parquet.write_bytes(parquet.read_bytes() + b"x")
    with pytest.raises(ValueError, match="parquet"):
        gold.materialize(manifest, parquet, tmp_path / "root")


def test_materialize_rejects_a_changed_query(tmp_path):
    manifest, parquet = _manifest_and_parquet(tmp_path, query_hash_ok=False)
    with pytest.raises(ValueError, match="query_hash"):
        gold.materialize(manifest, parquet, tmp_path / "root")


# --------------------------------------------------------------------------- ablation driver
def _gold_manifest(tmp_path: Path) -> Path:
    manifest, parquet = _manifest_and_parquet(tmp_path)
    return gold.materialize(manifest, parquet, tmp_path / "root")


def _fake_runner(calls):
    def run_bounded_task(root, row, fail_to_pass, args, builder_hash):
        calls.append((row["instance_id"], Path(args.retrieval_config).name if args.retrieval_config else "default"))
        metrics = {"file_recall@5": 1.0, "function_recall@5": 0.5, "file_mrr": 1.0}
        return {"instance_id": row["instance_id"], "status": "SUCCEEDED", "duration_seconds": 0.1,
                "graph": {"build_seconds": 0.1, "cached": False, "nodes": 1, "edges": 0},
                "corpus_hash": "c", "query_hash": row["query_hash"],
                "arms": {arm: {"metrics": metrics} for arm in ("graph", "graph_f2p")}}
    return run_bounded_task


def _argv(tmp_path, manifest, *extra):
    config = tmp_path / "may_call.json"
    config.write_text(json.dumps({"may_call_factor": 0.5}), encoding="utf-8")
    return [str(tmp_path / "root"), str(manifest), "--config", "default", "--config", f"may_call={config}",
            "--out", str(tmp_path / "out"), "--allow-fallback-counter", *extra]


@pytest.fixture
def patched(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(ablation.runner, "run_bounded_task", _fake_runner(calls))
    monkeypatch.setattr(ablation.runner, "load_fail_to_pass", lambda root, manifest: {
        t["instance_id"]: ["tests/test_core.py::test_x"] for t in manifest["tasks"]})
    monkeypatch.setattr(ablation, "builder_digest", lambda: "digest")
    return calls


def test_each_config_gets_its_own_complete_run(tmp_path, patched):
    assert ablation.main(_argv(tmp_path, _gold_manifest(tmp_path))) == 0
    for name in ("default", "may_call"):
        record = json.loads((tmp_path / "out" / name / "result.json").read_text(encoding="utf-8"))
        assert record["complete"] and [t["instance_id"] for t in record["task_results"]] == DEV_IDS
        assert (tmp_path / "out" / name / "tasks" / f"{DEV_IDS[0]}.json").exists()
    assert len(patched) == 4


def test_resume_skips_finished_tasks(tmp_path, patched):
    manifest = _gold_manifest(tmp_path)
    ablation.main(_argv(tmp_path, manifest))
    patched.clear()
    assert ablation.main(_argv(tmp_path, manifest, "--resume")) == 0
    assert patched == []
    record = json.loads((tmp_path / "out" / "default" / "result.json").read_text(encoding="utf-8"))
    assert len(record["task_results"]) == 2


def test_existing_output_without_resume_is_refused(tmp_path, patched):
    manifest = _gold_manifest(tmp_path)
    ablation.main(_argv(tmp_path, manifest))
    with pytest.raises(SystemExit):
        ablation.main(_argv(tmp_path, manifest))


def test_prune_removes_only_the_finished_task(tmp_path, patched):
    manifest = _gold_manifest(tmp_path)
    repos = tmp_path / "root" / "data" / "repositories"
    other = repos / "archives" / ("other__repo-" + "b" * 40 + ".tar.gz")
    for path in (repos / "archives" / ("owner__repo-" + "a" * 40 + ".tar.gz"),
                 repos / "archives" / ("owner__repo-" + "a" * 40 + ".tar.json"),
                 repos / "trees" / ("owner__repo-" + "a" * 40) / "pkg" / "core.py", other):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    assert ablation.main(_argv(tmp_path, manifest, "--prune", "--only", str(_ids_file(tmp_path)))) == 0
    assert not (repos / "archives" / ("owner__repo-" + "a" * 40 + ".tar.gz")).exists()
    assert not (repos / "trees" / ("owner__repo-" + "a" * 40)).exists()
    assert not (repos / "archives" / ("owner__repo-" + "a" * 40 + ".tar.json")).exists()
    assert other.exists()
    assert (tmp_path / "out" / "default" / "result.json").exists()


def _ids_file(tmp_path: Path) -> Path:
    path = tmp_path / "ids.txt"
    path.write_text(DEV_IDS[0] + "\n", encoding="utf-8")
    return path


def test_worker_function_can_be_sent_to_a_spawned_process():
    import pickle
    restored = pickle.loads(pickle.dumps(ablation.runner.task_worker))
    assert restored.__name__ == "task_worker"


def test_compare_reports_each_config_against_default(tmp_path, patched):
    compare = _load("compare_rt1_ablation", "scripts/compare_rt1_ablation.py")
    ablation.main(_argv(tmp_path, _gold_manifest(tmp_path)))
    report = compare.compare_all(tmp_path / "out")
    assert set(report) == {"may_call"}
    assert report["may_call"]["file_recall@5"]["n"] == 2
    assert report["may_call"]["file_recall@5"]["mean_delta"] == 0


def test_resume_restores_a_summary_lost_after_the_artifact_was_written(tmp_path, patched):
    manifest = _gold_manifest(tmp_path)
    ablation.main(_argv(tmp_path, manifest))
    path = tmp_path / "out" / "default" / "result.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["task_results"] = record["task_results"][:1]          # stopped between artifact and record write
    path.write_text(json.dumps(record), encoding="utf-8")
    assert ablation.main(_argv(tmp_path, manifest, "--resume")) == 0
    record = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(t["instance_id"] for t in record["task_results"]) == DEV_IDS


def test_resume_refuses_a_changed_config(tmp_path, patched):
    manifest = _gold_manifest(tmp_path)
    ablation.main(_argv(tmp_path, manifest))
    # Same folder name, different override file content.
    (tmp_path / "may_call.json").write_text(json.dumps({"may_call_factor": 1.0}), encoding="utf-8")
    with pytest.raises(SystemExit, match="ranking config"):
        ablation.main(_changed_argv(tmp_path, manifest))


def _changed_argv(tmp_path, manifest):
    config = tmp_path / "may_call.json"
    return [str(tmp_path / "root"), str(manifest), "--config", "default", "--config", f"may_call={config}",
            "--out", str(tmp_path / "out"), "--allow-fallback-counter", "--resume"]
