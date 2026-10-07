"""Real subprocess and resume regressions; no network, weights or benchmark claims."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.evidence import sha256, write_json


def lifecycle():
    from vgar.evaluation.retrieval import lifecycle as module
    return module


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), True])
def test_invalid_worker_deadline_is_rejected(tmp_path, seconds):
    with pytest.raises(ValueError, match="timeout"):
        lifecycle().run_worker({"row": {"instance_id": "fixture"}}, tmp_path / "attempt", seconds)


def test_timeout_has_terminal_artifact_stage_output_and_kills_children(tmp_path):
    code = ("import subprocess,sys,time; from pathlib import Path; "
            "from vgar.evaluation.retrieval.evidence import write_json; d=Path(sys.argv[2]); "
            "write_json(d/'telemetry.json', {'phase':'BUILD_GRAPH','stages':[],'peak_rss_bytes':123}); "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "(d/'child.pid').write_text(str(p.pid)); print('started',flush=True); time.sleep(60)")
    directory = tmp_path / "attempt"
    result = lifecycle().run_worker({"row": {"instance_id": "fixture"}}, directory, 1.5,
                                   worker_command=[sys.executable, "-B", "-c", code])
    assert result["status"] == "ERROR" and result["complete"]
    assert result["error_class"] == "TimeoutError" and result["phase"] == "BUILD_GRAPH"
    assert result["peak_rss_bytes"] >= 123 and "started" in result["stdout"]
    saved = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert saved == result and result["command_argv"]
    pid = int((directory / "child.pid").read_text())
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            assert kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(exit_code))
            kernel.CloseHandle(ctypes.c_void_p(handle))
            assert exit_code.value != 259, "descendant is still running"
    else:
        # A dead descendant may remain a zombie until init reaps it.
        state = Path(f"/proc/{pid}/stat")
        assert not state.exists() or state.read_text().split()[2] == "Z"


def test_timeout_retains_parent_measured_peak_not_just_stage_start(tmp_path):
    code = ("import sys,time; from pathlib import Path; from vgar.evaluation.retrieval.evidence import write_json; "
            "d=Path(sys.argv[2]); write_json(d/'telemetry.json', {'phase':'BUILD_GRAPH','stages':[],'peak_rss_bytes':1}); "
            "blocks=bytearray(32*1024*1024); blocks[::4096]=b'x'*(len(blocks)//4096); time.sleep(60)")
    result = lifecycle().run_worker({"row": {"instance_id": "fixture"}}, tmp_path / "attempt", 1.5,
                                   worker_command=[sys.executable, "-B", "-c", code])
    assert result["status"] == "ERROR" and result["phase"] == "BUILD_GRAPH"
    assert result["peak_rss_bytes"] > 32 * 1024 * 1024 and result["rss_samples"]


def test_worker_crash_without_json_is_not_success(tmp_path):
    result = lifecycle().run_worker({"row": {"instance_id": "fixture"}}, tmp_path / "attempt", 10,
                                   worker_command=[sys.executable, "-B", "-c", "import os; os._exit(17)"])
    assert result["status"] == "ERROR" and result["complete"]
    assert result["worker_exit_code"] == 17 and result["error_class"] == "WorkerProcessError"


def test_public_retrieval_worker_does_not_inherit_credentials(tmp_path, monkeypatch):
    # These names were not covered by the old ACCESS_TOKEN substring filter.
    # Use synthetic values only; never echo a developer's actual credentials.
    names = ("HF_TOKEN", "GITHUB_TOKEN", "HUGGING_FACE_HUB_TOKEN", "AWS_SESSION_TOKEN",
             "WANDB_API_KEY", "SERVICE_PASSWORD", "SERVICE_SECRET", "ACCESS_TOKEN", "TOKEN")
    for name in names:
        monkeypatch.setenv(name, "synthetic-test-value")
    monkeypatch.setenv("VGAR_WORKER_DIAGNOSTIC", "retained")
    code = (
        "import os,sys; from pathlib import Path; "
        "from vgar.evaluation.retrieval.evidence import write_json; "
        f"names={names!r}; "
        "assert all(name not in os.environ for name in names), 'credential inherited'; "
        "assert os.environ['TOKENIZERS_PARALLELISM']=='false'; "
        "assert os.environ['VGAR_WORKER_DIAGNOSTIC']=='retained'; "
        "write_json(Path(sys.argv[2])/'worker-result.json', "
        "{'instance_id':'fixture','status':'SUCCEEDED','complete':True})"
    )
    result = lifecycle().run_worker({"row": {"instance_id": "fixture"}}, tmp_path / "attempt", 10,
                                   worker_command=[sys.executable, "-B", "-c", code])
    assert result["status"] == "SUCCEEDED", result["stderr"]
    assert result["worker_exit_code"] == 0
    assert all(os.environ[name] == "synthetic-test-value" for name in names)


def test_memory_error_records_trace_stage_and_rss_in_actual_worker(tmp_path):
    code = ("from vgar.evaluation.retrieval import worker; import sys; "
            "exec(\"def fail(request, stages):\\n    with stages.step('BUILD_GRAPH'):\\n        raise MemoryError('fixture oom')\\n\"); "
            "worker.run_task=fail; sys.exit(worker.main(sys.argv[1:]))")
    result = lifecycle().run_worker({"row": {"instance_id": "fixture"}}, tmp_path / "attempt", 10,
                                   worker_command=[sys.executable, "-B", "-c", code])
    assert result["status"] == "FAILED" and result["error_class"] == "MemoryError"
    assert result["phase"] == "BUILD_GRAPH" and "fixture oom" in result["traceback"]
    assert result["peak_rss_bytes"] > 0 and result["stages"][0]["duration_seconds"] >= 0


def test_interrupted_parent_kills_worker_and_finalizes_attempt(tmp_path, monkeypatch):
    module = lifecycle()
    sleeps = []

    def interrupt(seconds):
        sleeps.append(True)
        raise KeyboardInterrupt()

    monkeypatch.setattr(module.time, "sleep", interrupt)
    directory = tmp_path / "attempt"
    with pytest.raises(KeyboardInterrupt):
        module.run_worker({"row": {"instance_id": "fixture"}}, directory, 10,
                          worker_command=[sys.executable, "-B", "-c", "import time; time.sleep(60)"])
    record = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert sleeps and record["complete"] and record["error_class"] == "KeyboardInterrupt"


def test_resume_validates_identity_and_copies_success_without_mutating_prior(tmp_path):
    prior = tmp_path / "prior"
    result = {"instance_id": "t-2", "status": "SUCCEEDED", "arms": {}}
    write_json(prior / "tasks/t-2.json", result)
    record = {"kind": "retrieval_graph", "resume_identity": {"digest": "code/config"},
              "task_results": [{"instance_id": "t-2", "status": "SUCCEEDED",
                                "artifact_hash": sha256((prior / "tasks/t-2.json").read_bytes())},
                               {"instance_id": "retry", "status": "FAILED"}]}
    write_json(prior / "result.json", record)
    before = {p.relative_to(prior).as_posix(): p.read_bytes() for p in prior.rglob("*.json")}
    copied = lifecycle().resume_successes(prior, tmp_path / "next", record["resume_identity"])
    assert set(copied) == {"t-2"}
    assert (tmp_path / "next/tasks/t-2.json").read_bytes() == (prior / "tasks/t-2.json").read_bytes()
    assert before == {p.relative_to(prior).as_posix(): p.read_bytes() for p in prior.rglob("*.json")}
    with pytest.raises(ValueError, match="resume.*identity"):
        lifecycle().resume_successes(prior, tmp_path / "bad", {"digest": "different"})
    (prior / "tasks/t-2.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        lifecycle().resume_successes(prior, tmp_path / "tampered", record["resume_identity"])


def runner():
    path = Path(__file__).resolve().parents[2] / "scripts/run_graph_retrieval.py"
    spec = importlib.util.spec_from_file_location("graph_runner_lifecycle_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind", ["invalid_limit", "duplicate", "missing_manifest", "keyboard_interrupt"])
def test_runner_pending_before_setup_and_terminal_setup_error(tmp_path, monkeypatch, kind):
    module = runner()
    manifest = tmp_path / "manifest.json"
    row = {"instance_id": "t-2", "repo": "o/r", "base_commit": "a" * 40,
           "problem_statement": "login fails", "split": "dev"}
    if kind != "missing_manifest":
        write_json(manifest, {"dataset_id": "fixture", "dataset_revision": "fixture", "split": "dev",
                              "tasks": [row, row] if kind == "duplicate" else [row]})
    args = ["runner", str(tmp_path), str(manifest), "--allow-fallback-counter", "--offline"]
    if kind == "invalid_limit":
        args += ["--limit", "0"]
    monkeypatch.setattr(sys, "argv", args)
    if kind == "keyboard_interrupt":
        def fail(*a):
            saved = list((tmp_path / "results/retrieval").glob("*/result.json"))
            assert len(saved) == 1 and not json.loads(saved[0].read_text())["complete"]
            raise KeyboardInterrupt()
        monkeypatch.setattr(module, "load_fail_to_pass", fail)
    assert module.main() != 0
    saved = list((tmp_path / "results/retrieval").glob("*/result.json"))
    assert len(saved) == 1
    record = json.loads(saved[0].read_text(encoding="utf-8"))
    assert record["complete"] and record["status"] in {"ERROR", "INTERRUPTED"}
    assert record["phase"] == "SETUP" and record["traceback"] and record["exit_code"] != 0


def fixture_manifest(tmp_path):
    import pyarrow as arrow
    import pyarrow.parquet as parquet
    from vgar.evaluation.retrieval.dataset import split_of
    ids = [f"fixture-{n}" for n in range(20) if split_of(f"fixture-{n}") == "dev"][:2]
    commit = "a" * 40
    archive = tmp_path / f"data/repositories/archives/o__r-{commit}.tar.gz"
    archive.parent.mkdir(parents=True)
    with tarfile.open(archive, "w:gz") as bundle:
        raw = b"def login(user):\n    return user == 'root'\n"
        member = tarfile.TarInfo(f"r-{commit}/src/auth.py")
        member.size = len(raw)
        bundle.addfile(member, io.BytesIO(raw))
    write_json(archive.with_suffix(".json"), {"url": f"https://codeload.github.com/o/r/tar.gz/{commit}",
                                           "base_commit": commit, "archive_hash": sha256(archive.read_bytes())})
    patch = "--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1,2 +1,2 @@\n def login(user):\n-    return user == 'root'\n+    return user == 'admin'\n"
    tasks = []
    for iid in ids:
        target = tmp_path / f"data/gold/{iid}.patch"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patch, encoding="utf-8", newline="\n")
        query = "login user fails"
        tasks.append({"instance_id": iid, "repo": "o/r", "base_commit": commit, "split": "dev",
                      "problem_statement": query, "query_hash": sha256(query), "patch_hash": sha256(patch),
                      "gold_patch_path": target.relative_to(tmp_path).as_posix()})
    snapshot = tmp_path / "data/downloads/fixture"
    snapshot.mkdir(parents=True)
    parquet.write_table(arrow.Table.from_pylist([{"instance_id": iid, "FAIL_TO_PASS": "[]"} for iid in ids]),
                        snapshot / "test-00000-of-00001.parquet")
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"dataset_id": "synthetic-fixture", "dataset_revision": "fixture", "split": "dev", "tasks": tasks})
    return manifest, tasks


def test_actual_resume_forks_success_retries_failure_and_preserves_all_prior_files(tmp_path, monkeypatch):
    manifest, tasks = fixture_manifest(tmp_path)
    module = runner()
    # A missing gold artifact is a genuine SCORE failure, not a fake summary.
    bad_patch = tmp_path / tasks[1]["gold_patch_path"]
    patch_bytes = bad_patch.read_bytes()
    bad_patch.unlink()
    args = ["runner", str(tmp_path), str(manifest), "--allow-fallback-counter", "--offline", "--no-jedi", "--max-hops", "0"]
    monkeypatch.setattr(sys, "argv", args)
    assert module.main() == 1
    prior = next((tmp_path / "results/retrieval").iterdir())
    before = {p.relative_to(prior).as_posix(): p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    first = json.loads((prior / "result.json").read_text())
    assert [r["status"] for r in first["task_results"]] == ["SUCCEEDED", "FAILED"]
    failed = json.loads((prior / "tasks" / f"{tasks[1]['instance_id']}.json").read_text())
    assert failed["phase"] == "SCORE" and "FileNotFoundError" in failed["traceback"]
    bad_patch.write_bytes(patch_bytes)
    monkeypatch.setattr(sys, "argv", args + ["--resume-run", str(prior)])
    assert module.main() == 0
    next_run = next(p for p in (tmp_path / "results/retrieval").iterdir() if p != prior)
    record = json.loads((next_run / "result.json").read_text())
    assert record["resumed_from"] == str(prior.resolve()) and record["inference"] == "NOT_RUN"
    assert record["task_results"][0]["reused_from_run"] == str(prior.resolve())
    assert len(list((next_run / "attempts").glob("*/*/result.json"))) == 1
    assert before == {p.relative_to(prior).as_posix(): p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    success = json.loads((next_run / "tasks" / f"{tasks[1]['instance_id']}.json").read_text())
    assert {"LOAD_SOURCE", "EXTRACT_TREE", "BUILD_GRAPH", "GROUND", "RETRIEVE", "SCORE", "WRITE"} <= {s["phase"] for s in success["stages"]}
    assert success["peak_rss_bytes"] > 0 and success["command_argv"]


def test_explicit_tree_rebuild_recovers_crlf_cache_without_mutating_legacy_tree(tmp_path, monkeypatch):
    from vgar.evaluation.retrieval.graph_arm import extract_python_tree
    manifest, tasks = fixture_manifest(tmp_path)
    row = tasks[0]
    key = row["repo"].replace("/", "__") + "-" + row["base_commit"]
    tree = tmp_path / "data/repositories/trees" / key
    archive = tmp_path / "data/repositories/archives" / (key + ".tar.gz")
    extract_python_tree(archive, row["repo"], row["base_commit"], tree)
    target = tree / "src/auth.py"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    before = {p.relative_to(tree).as_posix(): p.read_bytes() for p in tree.rglob("*") if p.is_file()}
    module = runner()
    args = ["runner", str(tmp_path), str(manifest), "--allow-fallback-counter", "--offline", "--no-jedi", "--limit", "1"]
    monkeypatch.setattr(sys, "argv", args)
    assert module.main() == 1  # default integrity guard must remain fail closed
    failed = next((tmp_path / "results/retrieval").iterdir())
    bad = json.loads((failed / "tasks" / (row["instance_id"] + ".json")).read_text())
    assert bad["phase"] == "EXTRACT_TREE" and "integrity" in bad["error"]
    monkeypatch.setattr(sys, "argv", args + ["--rebuild-trees"])
    try:
        code = module.main()
    except SystemExit as exc:  # argparse missing option is an observable CLI failure
        code = exc.code
    assert code == 0
    completed = next(p for p in (tmp_path / "results/retrieval").iterdir() if p != failed)
    result = json.loads((completed / "tasks" / (row["instance_id"] + ".json")).read_text())
    fresh = Path(result["source_tree"]["path"])
    assert fresh != tree and fresh.is_relative_to(tmp_path / "data/repositories/trees")
    assert (fresh / "src/auth.py").read_bytes() == b"def login(user):\n    return user == 'root'\n"
    assert before == {p.relative_to(tree).as_posix(): p.read_bytes() for p in tree.rglob("*") if p.is_file()}
    run = json.loads((completed / "result.json").read_text())
    assert run["config"]["execution"]["rebuild_trees"] is True and run["inference"] == "NOT_RUN"


@pytest.mark.parametrize("changed", ["budget", "manifest", "source"])
def test_actual_runner_resume_rejects_changed_bindings_with_terminal_evidence(tmp_path, monkeypatch, changed):
    manifest, tasks = fixture_manifest(tmp_path)
    module = runner()
    args = ["runner", str(tmp_path), str(manifest), "--allow-fallback-counter", "--offline", "--no-jedi", "--limit", "1"]
    monkeypatch.setattr(sys, "argv", args)
    assert module.main() == 0
    prior = next((tmp_path / "results/retrieval").iterdir())
    if changed == "budget":
        args += ["--budget-tokens", "200"]
    elif changed == "manifest":
        data = json.loads(manifest.read_text())
        data["purpose"] = "changed"
        write_json(manifest, data)
    else:
        actual = module.source_fingerprint
        monkeypatch.setattr(module, "source_fingerprint", lambda root: dict(actual(root), digest="changed-source"))
    monkeypatch.setattr(sys, "argv", args + ["--resume-run", str(prior)])
    assert module.main() == 1
    next_run = next(p for p in (tmp_path / "results/retrieval").iterdir() if p != prior)
    result = json.loads((next_run / "result.json").read_text())
    assert result["complete"] and result["status"] == "ERROR" and "identity" in result["error"]


def test_task_selector_restricts_population_and_rejects_unknown_id(tmp_path, monkeypatch):
    manifest, tasks = fixture_manifest(tmp_path)
    module = runner()
    args = ["runner", str(tmp_path), str(manifest), "--allow-fallback-counter", "--offline", "--no-jedi"]
    monkeypatch.setattr(sys, "argv", args + ["--task-id", tasks[1]["instance_id"]])
    assert module.main() == 0
    first = next((tmp_path / "results/retrieval").iterdir())
    record = json.loads((first / "result.json").read_text())
    assert record["selected_task_ids"] == [tasks[1]["instance_id"]] and len(record["task_results"]) == 1
    monkeypatch.setattr(sys, "argv", args + ["--task-id", "unknown"])
    assert module.main() == 1
    failed = next(p for p in (tmp_path / "results/retrieval").iterdir() if p != first)
    result = json.loads((failed / "result.json").read_text())
    assert result["complete"] and "unknown" in result["error"]


def test_tokenizer_setup_error_still_has_terminal_pending_evidence(tmp_path, monkeypatch):
    manifest, _ = fixture_manifest(tmp_path)
    module = runner()
    monkeypatch.setattr(sys, "argv", ["runner", str(tmp_path), str(manifest), "--tokenizer-manifest", str(tmp_path / "absent.json")])
    assert module.main() == 1
    saved = next((tmp_path / "results/retrieval").glob("*/result.json"))
    result = json.loads(saved.read_text())
    assert result["complete"] and result["status"] == "ERROR" and result["phase"] == "SETUP"
    assert result["error_class"] == "FileNotFoundError" and "absent.json" in result["traceback"]


def test_atomic_evidence_write_retries_transient_windows_read_lock(tmp_path, monkeypatch):
    from vgar.evaluation.retrieval import evidence
    path = tmp_path / "telemetry.json"
    write_json(path, {"phase": "SETUP"})
    original = evidence.os.replace
    attempts = []

    def locked(source, target):
        attempts.append(True)
        if len(attempts) < 3:
            assert json.loads(path.read_text())["phase"] == "SETUP"
            raise PermissionError("transient Windows read lock")
        original(source, target)

    monkeypatch.setattr(evidence.os, "replace", locked)
    evidence.write_json(path, {"phase": "BUILD_GRAPH"})
    assert len(attempts) == 3 and json.loads(path.read_text())["phase"] == "BUILD_GRAPH"


def test_atomic_write_permanent_lock_fails_without_overwriting_prior(tmp_path, monkeypatch):
    from vgar.evaluation.retrieval import evidence
    path = tmp_path / "telemetry.json"
    write_json(path, {"phase": "SETUP"})
    original = path.read_bytes()
    monkeypatch.setattr(evidence.os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("permanent lock")))
    with pytest.raises(PermissionError, match="permanent"):
        evidence.write_json(path, {"phase": "BUILD_GRAPH"})
    assert path.read_bytes() == original and not list(tmp_path.glob("*.tmp"))
