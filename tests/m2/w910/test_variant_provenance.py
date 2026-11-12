"""Opt-in profile, persisted binding and real fake-repair integration."""
import copy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
DEBT_FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,3 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n+unused: int = "debt"\n'


def test_profile_binds_explicit_arm_and_derives_hash_without_mutating_input(experiment_input):
    from vgar.repair.experiment import RepairExperiment
    from vgar.repair.policy import policy_hash
    before = copy.deepcopy(experiment_input)
    profile = RepairExperiment.model_validate(experiment_input)
    assert profile.variant_policy.arm == 'bm25'
    assert profile.policy_hash == policy_hash(profile.variant_policy)
    assert experiment_input == before
    assert profile.snapshot()['variant_id'] == 'A0'
    assert profile.snapshot()['policy_hash'] == profile.policy_hash


@pytest.mark.parametrize('fault', ['bad_arm', 'mismatched_arm', 'variant', 'hash_override', 'missing_arm', 'bad_hashes'])
def test_profile_rejects_invalid_input(experiment_input, fault):
    from vgar.repair.experiment import RepairExperiment
    if fault == 'bad_arm':
        experiment_input['arm'] = 'A0'
    elif fault == 'mismatched_arm':
        experiment_input['variant_policy']['arm'] = 'graph'
    elif fault == 'variant':
        experiment_input['variant_policy']['variant_id'] = 'A9'
    elif fault == 'hash_override':
        experiment_input['policy_hash'] = 'sha256:'+'a'*64
    elif fault == 'missing_arm':
        experiment_input.pop('arm')
    else:
        experiment_input['expected_hashes'] = {'context.json': 'sha256:'+'a'*64}
    with pytest.raises(ValueError):
        RepairExperiment.model_validate(experiment_input)
