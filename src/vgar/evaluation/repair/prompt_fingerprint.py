"""Prompt template lookup for experiment fingerprints only: the verification campaign hashes the template its
configs name (``policy.prompt_version``); nothing here builds a prompt or calls a model.

Moved from the removed M2 generation engine (spec 2026-11-12 §4.1b); the template bytes are unchanged, so every
recorded template hash still matches.
"""
import re
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / 'prompts'


def template_path(version: str) -> Path:
    """Path of the registered template for a prompt version such as ``m2-w78-v11``.

    Args:
        version: Prompt version named by a repair policy.
    """
    match = re.fullmatch(r'm2-w78-v([1-9][0-9]*)', version)
    if not match:
        raise ValueError('Unsupported prompt version: ' + str(version))
    path = PROMPTS / ('repair_v' + match[1] + '.txt')
    if not path.is_file() or path.is_symlink():
        raise ValueError('Unregistered or missing prompt version: ' + version)
    return path
