"""Opt-in W9 variant definitions; no changes to W78 execution or verdicts.

An unresolved arm is explicit metadata, never an inferred retrieval choice.
Policy hashes cover this definition, not the model/budget/environment profile.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

CheckName = Literal['tests', 'syntax', 'mypy', 'ruff']
_ALL_CHECKS = frozenset({'tests', 'syntax', 'mypy', 'ruff'})
_REQUIRED = {'A0': frozenset({'tests'}), 'A1': frozenset({'tests'}), 'A2': _ALL_CHECKS}


class VariantPolicy(BaseModel):
    """Validated, immutable definition; arm=None means awaiting group agreement."""

    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, revalidate_instances='always')
    variant_id: Literal['A0', 'A1', 'A2']
    required_checks: tuple[CheckName, ...]
    recorded_checks: tuple[CheckName, ...] = ('tests', 'syntax', 'mypy', 'ruff')
    arm: Literal['bm25', 'graph'] | None = None
    static_mode: Literal['baseline_delta'] = 'baseline_delta'
    diagnostic_identity_version: Literal['m2-static-delta-v1'] = 'm2-static-delta-v1'

    @model_validator(mode='after')
    def validate_checks(self) -> VariantPolicy:
        for field, expected in (('required_checks', _REQUIRED[self.variant_id]),
                                ('recorded_checks', _ALL_CHECKS)):
            values = getattr(self, field)
            if len(values) != len(set(values)) or frozenset(values) != expected:
                raise ValueError(f'{self.variant_id} {field} must contain exactly {sorted(expected)}')
            object.__setattr__(self, field, tuple(sorted(values)))
        return self


def load_variant(path: Path) -> VariantPolicy:
    """Read a UTF-8 JSON policy; missing/invalid variants never fall back to A0."""
    return VariantPolicy.model_validate_json(Path(path).read_bytes())


def policy_hash(policy: VariantPolicy) -> str:
    """Hash canonical effective fields including defaults and explicit arm state."""
    validated = VariantPolicy.model_validate(policy)
    encoded = json.dumps(validated.model_dump(mode='json'), sort_keys=True,
                         ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


def required_checks(policy: VariantPolicy) -> frozenset[str]:
    """Required check names only; this function does not execute verification."""
    return frozenset(VariantPolicy.model_validate(policy).required_checks)
