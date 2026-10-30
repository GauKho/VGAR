"""Arm fairness gate (spec §5.7): arms may differ only in arm and required checks, experiments not at all."""
from __future__ import annotations

from collections.abc import Sequence
import json

from vgar.evaluation.repair.manifest import Experiment
from vgar.repair.evidence import digest
from vgar.repair.policy import VariantPolicy
from vgar.repair.prompt import template_path

ARM_SPECIFIC = ('variant_id', 'arm', 'required_checks')


def _variant_common(exp: Experiment) -> dict:
    common = None
    for variant in exp.variants:
        # Normalized dump: defaults applied, the same way policy hashes see the variant.
        dump = VariantPolicy.model_validate_json(json.dumps(variant.policy)).model_dump(mode='json')
        shared = {k: v for k, v in sorted(dump.items()) if k not in ARM_SPECIFIC}
        shared.setdefault('patch_mode', 'strict')
        shared.setdefault('path_listing', 'all')
        if common is None:
            common = shared
        elif shared != common:
            field = next(k for k in sorted(set(shared) | set(common)) if shared.get(k) != common.get(k))
            raise ValueError(f'Arm fairness violation: {field} differs between variants of {exp.experiment_id}')
    return common or {}


def fairness_identity(exp: Experiment) -> dict:
    return {'model_id': exp.profile.model_id, 'revision': exp.profile.revision,
            'tokenizer_manifest_sha': digest(exp.profile.tokenizer_manifest.read_bytes()),
            'template_sha': digest(template_path(exp.policy.prompt_version).read_bytes()),
            'policy': exp.policy.model_dump(mode='json'),
            'bundle_profile_sha': (exp.raw['source'].get('bundle_profile') or {}).get('sha256'),
            'variant_common': _variant_common(exp)}


def check_arm_fairness(experiments: Sequence[Experiment]) -> None:
    identities = [fairness_identity(exp) for exp in experiments]
    for exp, identity in zip(experiments[1:], identities[1:]):
        for field in identities[0]:
            if identity[field] != identities[0][field]:
                raise ValueError(f'Arm fairness violation: {field} differs between experiments '
                                 f'{experiments[0].experiment_id} and {exp.experiment_id}')
