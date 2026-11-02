from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

from vgar.graph.retrieval import RetrievalConfig, ranking_config_hash

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("graph_eval_runner_config", ROOT / "scripts/run_graph_retrieval.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _args(retrieval_config=None):
    return argparse.Namespace(max_hops=2, max_candidates=100, retrieval_config=retrieval_config)


def test_without_override_file_the_default_config_is_used():
    assert runner.retrieval_config_from_args(_args()) == RetrievalConfig()


def test_override_file_replaces_only_named_fields(tmp_path):
    weights = {**RetrievalConfig().weights, "public_api_risk": 0.05}
    path = tmp_path / "step_b.json"
    path.write_text(json.dumps({"weights": weights}), encoding="utf-8")

    config = runner.retrieval_config_from_args(_args(retrieval_config=path))

    assert config.weights == weights
    assert config.max_hops == 2
    assert ranking_config_hash(config) != ranking_config_hash(RetrievalConfig())


def test_override_file_with_unknown_field_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"weight": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="weight"):
        runner.retrieval_config_from_args(_args(retrieval_config=path))
