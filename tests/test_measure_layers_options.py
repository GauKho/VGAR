"""I1 and R1 measurement scripts take the layer settings and the new flags (spec 2026-11-15 §5)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from vgar.graph.layer_config import (
    LayerConfigs,
    add_layer_options,
    layer_profile,
    layers_from_args,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_layer_options_round_trip(tmp_path):
    import argparse

    parser = argparse.ArgumentParser()
    add_layer_options(parser)
    args = parser.parse_args(["--tsg-executable", str(tmp_path / "tsg"), "--tsg-tree-sitter-dir", str(tmp_path),
                              "--joern", "--joern-timeout", "60"])
    layers = layers_from_args(args)
    assert layers.tsg.executable == tmp_path / "tsg" and layers.joern.timeout_seconds == 60 and layers.jarvis is None
    assert layers_from_args(parser.parse_args([])) == LayerConfigs()


def test_measure_patch_impact_parses_layer_and_flag_options(tmp_path):
    measure = _load(ROOT / "scripts" / "measure_patch_impact.py", "measure_patch_impact")
    args = measure.parse_args(["--manifest", "m.json", "--data-root", "d", "--parquet", "p", "--task-inputs", "t",
                               "--out", "o", "--joern", "--follow-variable-readers", "--narrow-with-dataflow"])
    assert args.joern and args.follow_variable_readers and args.narrow_with_dataflow
    assert measure.impact_flags(args) == {"follow_variable_readers": True, "narrow_with_dataflow": True}


def test_gold_impact_passes_layers_and_flags(tmp_path, monkeypatch):
    import vgar.evaluation.gold_impact as gold

    checkout = tmp_path / "repo"
    (checkout / "pkg").mkdir(parents=True)
    (checkout / "pkg" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    seen = {}

    def fake_impact(diff, document, root, *, patch_policy, **flags):
        seen["flags"] = flags
        raise RuntimeError("stop after recording")

    monkeypatch.setattr(gold, "analyze_patch_impact", fake_impact)
    row = {"patch": "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -2 +2 @@\n-    return 1\n+    return 2\n",
           "test_patch": "", "FAIL_TO_PASS": "[]"}
    out = gold.evaluate_task("t", checkout, ["pkg"], row, layers=LayerConfigs(),
                             impact_flags={"follow_variable_readers": True})
    assert seen["flags"] == {"follow_variable_readers": True}
    assert "layers" not in out and out["impact_flags"] == {"follow_variable_readers": True}


def test_default_i1_shape_has_no_layers_or_flags(tmp_path, monkeypatch):
    # Default I1 output keeps the pre-15/11 shape: impact_flags / layers appear only when something is on.
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    import vgar.evaluation.gold_impact as gold

    checkout = tmp_path / "repo"
    (checkout / "pkg").mkdir(parents=True)
    (checkout / "pkg" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(gold, "analyze_patch_impact", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop")))
    row = {"patch": "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -2 +2 @@\n-    return 1\n+    return 2\n",
           "test_patch": "", "FAIL_TO_PASS": "[]"}
    out = gold.evaluate_task("t", checkout, ["pkg"], row,
                             impact_flags={"follow_variable_readers": False, "narrow_with_dataflow": False})
    assert "impact_flags" not in out and "layers" not in out

    from vgar.evaluation.retrieval.dataset import split_of

    task_id = next(f"t{i}" for i in range(100) if split_of(f"t{i}") == "dev")
    measure = _load(ROOT / "scripts" / "measure_patch_impact.py", "measure_patch_impact_shape")
    manifest = {"split": "dev", "tasks": [{"instance_id": task_id, "split": "dev"}]}
    (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
    pq.write_table(pa.Table.from_pylist([{"instance_id": task_id, **row}]), tmp_path / "p.parquet")
    monkeypatch.setattr(measure, "evaluate_task", lambda *a, **k: {"task_id": task_id, "status": "ERROR", "reason": "x"})
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / f"{task_id}.json").write_text(json.dumps({"source_roots": ["pkg"]}), encoding="utf-8")
    measure.main(["--manifest", str(tmp_path / "m.json"), "--data-root", str(tmp_path), "--parquet",
                  str(tmp_path / "p.parquet"), "--task-inputs", str(tmp_path / "tasks"), "--out", str(tmp_path / "o")])
    record = json.loads((tmp_path / "o" / "i1.json").read_text(encoding="utf-8"))
    assert "impact_flags" not in record and "layers" not in record


def test_r1_options_reach_builder_and_config(tmp_path):
    r1 = _load(ROOT / "ablation_matrix" / "run_r1_ablation.py", "run_r1_ablation_layers")
    args = r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--use-variable-references",
                          "--tsg-executable", str(tmp_path / "tsg"), "--tsg-tree-sitter-dir", str(tmp_path)])
    assert r1.arm_flags(args) == {"task_trace": {"use_variable_references": True}}
    assert layers_from_args(args).tsg is not None
    plain = r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter"])
    assert r1.arm_flags(plain) == {} and layers_from_args(plain) == LayerConfigs()


def test_r1_records_layers_and_flags_for_any_layer(tmp_path):
    r1 = _load(ROOT / "ablation_matrix" / "run_r1_ablation.py", "run_r1_ablation_provenance")
    base = ["root", "m.json", "--out", "o", "--allow-fallback-counter"]
    assert r1.layers_and_flags(r1.parse_args(base)) is None
    assert r1.layers_and_flags(r1.parse_args(base + ["--enable-jarvis"])) == {"arm_flags": {}, "layers": ["jarvis"]}
    assert r1.layers_and_flags(r1.parse_args(base + ["--use-variable-references"])) == {
        "arm_flags": {"task_trace": {"use_variable_references": True}}, "layers": []}


def test_r1_records_layer_status_from_the_built_graph(tmp_path):
    # A layer that timed out must show as failed in the task result, not only as requested.
    r1 = _load(ROOT / "ablation_matrix" / "run_r1_ablation.py", "run_r1_ablation_status")
    args = r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--joern", "--enable-jarvis"])
    document = {"statistics": {"jarvis": {"status": "ready"},
                               "code_graph": {"status": "timeout", "reason": "Joern exceeded 900.0 s"}}}
    status = r1.layers_and_flags(args, document)["layer_status"]
    assert status["jarvis"]["status"] == "ready" and status["tsg"]["status"] == "off"
    assert status["joern"] == {"status": "failed", "reason": "Joern exceeded 900.0 s"}
    plain = r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--use-variable-references"])
    assert "layer_status" not in r1.layers_and_flags(plain, document)


def test_cache_key_changes_with_layers(tmp_path):
    from vgar.graph.joern_runner import JoernConfig

    assert layer_profile(LayerConfigs()) is None
    assert layer_profile(LayerConfigs(joern=JoernConfig())) != layer_profile(LayerConfigs(joern=JoernConfig(timeout_seconds=1)))
    assert layer_profile(LayerConfigs(joern=JoernConfig())) is not None


def test_variant_outputs_applies_arm_flags(monkeypatch):
    variants = _load(ROOT / "ablation_matrix" / "retrieval_variants.py", "retrieval_variants_flags")
    assert variants.arm_config("task_trace", {"task_trace": {"use_variable_references": True}}).use_variable_references
    assert not variants.arm_config("no_task_trace", {"task_trace": {"use_variable_references": True}}).use_variable_references


@pytest.mark.parametrize("flag", ["--follow-variable-readers", "--narrow-with-dataflow"])
def test_measure_flags_default_off(flag):
    measure = _load(ROOT / "scripts" / "measure_patch_impact.py", "measure_patch_impact_defaults")
    args = measure.parse_args(["--manifest", "m", "--data-root", "d", "--parquet", "p", "--task-inputs", "t", "--out", "o"])
    assert measure.impact_flags(args) == {"follow_variable_readers": False, "narrow_with_dataflow": False}
