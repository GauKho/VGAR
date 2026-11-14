"""L5 tier-1 measurement: the 14 demo-shop variants of the 14/11 spike, Python fallback engine."""
from __future__ import annotations

import time

import pytest
from invariant_helpers import VARIANTS, run_variant

from vgar.repair.invariants import InvariantSettings, compute_semantic_invariants

EXPECTED = {"base": "PASS", "fix": "PASS", "refactor": "PASS", "mutant": "FAIL", "miss": "PASS"}


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return run_variant("base", tmp_path_factory.mktemp("base"))


@pytest.mark.parametrize("name", list(VARIANTS), ids=[f"{n}-{VARIANTS[n][0]}" for n in VARIANTS])
def test_demo_shop_variants(baseline, name, tmp_path):
    base_trace, outcomes = baseline
    cand_trace, _ = run_variant(name, tmp_path)
    record = compute_semantic_invariants(base_trace, cand_trace, outcomes, InvariantSettings(repo_key="shop"),
                                         time.monotonic() + 60)
    assert record["status"] == EXPECTED[VARIANTS[name][0]], record["violations"]
    assert record["engine"] == "python-fallback" and record["learned"] > 50
