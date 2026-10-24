"""Internal W9 opt-in policy and provenance; not admission or arm authentication."""
from __future__ import annotations

import copy
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vgar.repair.policy import VariantPolicy, policy_hash

SIDECARS = frozenset({'context.json', 'context_manifest.json', 'test_links.json'})


def validate_hashes(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != SIDECARS or any(
            not isinstance(v, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', v) for v in value.values()):
        raise ValueError('Expected exactly three sidecar SHA-256 hashes')
    return dict(sorted(value.items()))


class RepairExperiment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, revalidate_instances='always')
    variant_policy: VariantPolicy
    arm: Literal['bm25', 'graph']
    expected_hashes: dict[str, str] | None = None

    @field_validator('variant_policy', mode='before')
    @classmethod
    def parse_policy(cls, value):
        if isinstance(value, dict):
            # JSON policy arrays map to tuple fields through the existing strict JSON validator.
            return VariantPolicy.model_validate_json(json.dumps(value, allow_nan=False))
        return VariantPolicy.model_validate(value)

    @field_validator('expected_hashes')
    @classmethod
    def hashes(cls, value):
        return validate_hashes(value)

    @model_validator(mode='after')
    def bind_arm(self):
        if self.variant_policy.arm not in (None, self.arm):
            raise ValueError('Experiment arm conflicts with variant policy')
        effective = VariantPolicy.model_validate(self.variant_policy.model_copy(update={'arm': self.arm}))
        object.__setattr__(self, 'variant_policy', effective)
        return self

    @property
    def policy_hash(self):
        return policy_hash(self.variant_policy)

    def snapshot(self, *, bundle_hashes=None):
        return {'variant_id': self.variant_policy.variant_id, 'arm': self.arm,
            'policy_hash': self.policy_hash, 'variant_policy': self.variant_policy.model_dump(mode='json'),
            'expected_hashes': validate_hashes(self.expected_hashes), 'bundle_hashes': validate_hashes(bundle_hashes)}


def validate_experiment(value):
    if value is None:
        return None
    # Validate instances again and detach nested mutable dictionaries from the caller.
    return RepairExperiment.model_validate(copy.deepcopy(value))


def restore_experiment(snapshot):
    keys = {'variant_id', 'arm', 'policy_hash', 'variant_policy', 'expected_hashes', 'bundle_hashes'}
    if not isinstance(snapshot, dict) or set(snapshot) != keys:
        raise ValueError('Invalid persisted experiment snapshot')
    value = validate_experiment({k: snapshot[k] for k in ('variant_policy', 'arm', 'expected_hashes')})
    if value.snapshot(bundle_hashes=snapshot['bundle_hashes']) != snapshot:
        raise ValueError('Persisted experiment policy/hash mismatch')
    if snapshot['bundle_hashes'] is not None and snapshot['expected_hashes'] is not None and (
            snapshot['bundle_hashes'] != snapshot['expected_hashes']):
        raise ValueError('Persisted bundle binding differs from expected hashes')
    return value


def check_session_experiment(state, record):
    baselines = (state.get('baseline') or {}, record.get('stages', {}).get('baseline', {}))
    opted_in = any('experiment' in item or 'experiment_required' in item for item in (state, record))
    opted_in |= any('variant_policy_hash' in item for item in baselines)
    if not opted_in:
        return None
    if (state.get('experiment_required') is not True or record.get('experiment_required') is not True
            or 'experiment' not in state or 'experiment' not in record
            or state['experiment'] != record['experiment']):
        raise ValueError('Session/record experiment mismatch')
    value = restore_experiment(state['experiment'])
    if any('variant_policy_hash' in item and item['variant_policy_hash'] != value.policy_hash for item in baselines):
        raise ValueError('Baseline experiment policy changed')
    if any(item.get('status') == 'PASS' for item in baselines) and any(
            item.get('status') != 'PASS' or item.get('variant_policy_hash') != value.policy_hash for item in baselines):
        raise ValueError('Successful baseline requires matching policy in session and record')
    context = record.get('stages', {}).get('context', {})
    if context.get('status') == 'PASS' and context.get('hashes') != state['experiment']['bundle_hashes']:
        raise ValueError('Context experiment bundle binding changed')
    return value
