"""RT-1 check over the self-made 12-task benchmark (spec §6 item 1b), on a one-task bundle."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

from vgar.graph.retrieval import RetrievalConfig

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_rt1_benchmark", ROOT / "scripts/check_rt1_benchmark.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def _bundle(tmp_path: Path, instance_id: str) -> Path:
    repo = tmp_path / "bundle" / "mini"
    (repo / "shop" / "pricing").mkdir(parents=True)
    (repo / "shop" / "checkout").mkdir(parents=True)
    for package in ("shop", "shop/pricing", "shop/checkout"):
        (repo / package / "__init__.py").write_text("", encoding="utf-8")
    (repo / "shop/pricing/rounding.py").write_text("def round_vnd(amount):\n    return int(amount / 100) * 100\n",
                                                  encoding="utf-8")
    (repo / "shop/checkout/total.py").write_text(
        "from shop.pricing.rounding import round_vnd\n\ndef subtotal(lines):\n    return round_vnd(sum(lines))\n",
        encoding="utf-8")
    for command in (["init", "-q"], ["add", "-A"],
                    ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "-m", "base"]):
        subprocess.run(["git", *command], cwd=repo, check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                            text=True).stdout.strip()
    task = {"instance_id": instance_id, "repo": "mini", "base_commit": commit,
            "problem_statement": "round_vnd rounds negative amounts toward zero",
            "FAIL_TO_PASS": [], "changed_source_files": ["shop/pricing/rounding.py"]}
    (tmp_path / "bundle" / "tasks").mkdir()
    (tmp_path / "bundle" / "tasks" / "manifest.json").write_text(json.dumps([task]), encoding="utf-8")
    return tmp_path / "bundle"


CONFIGS = {"default": RetrievalConfig(), "dependents": RetrievalConfig(use_component_dependents=True)}


def test_report_has_every_key_and_default_is_repeatable(tmp_path):
    report = checker.check_benchmark(_bundle(tmp_path, "task-01"), CONFIGS)
    row = report["tasks"]["task-01"]
    assert set(row["configs"]) == {"default", "dependents"}
    for result in row["configs"].values():
        assert {"node_ids", "gold_rank", "changed_vs_default", "repeatable"} <= set(result)
    assert row["configs"]["default"]["repeatable"] is True
    assert row["configs"]["default"]["changed_vs_default"] is False
    assert row["configs"]["default"]["gold_rank"] == 1


def test_default_only_tasks_skip_other_configs(tmp_path):
    report = checker.check_benchmark(_bundle(tmp_path, "task-06"), CONFIGS)
    row = report["tasks"]["task-06"]
    assert set(row["configs"]) == {"default"}
    assert row["default_only_reason"] == checker.DEFAULT_ONLY_TASKS["task-06"]
