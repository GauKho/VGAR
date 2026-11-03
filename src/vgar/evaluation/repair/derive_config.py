"""Experiment config for re-exported bundles (M1-W12 spec §4.8).

Runner configs pin every input by hash; W10 bundles cannot be reused after the W11 ranking freeze and resolver v4,
so a new config is derived from a template: same fields, selected tasks, hashes recomputed from the files on disk.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from vgar.contracts.handoff import byte_digest
from vgar.evaluation.repair.manifest import resolve

BUNDLE_FILES = ('context.json', 'context_manifest.json', 'test_links.json')
ARMS = ('bm25', 'graph')


def _absolute(value: str, base: Path) -> str:
    return value if value.startswith('@data/') else str((base / value).resolve())


def derive_config(template: dict, *, template_dir: Path, data_root: Path, task_ids: list[str], bundle_dir: str,
                  variants: list[dict]) -> dict:
    """Template with only task_ids, hashes recomputed from files; relative paths made absolute (template_dir)."""
    source = template['source']
    missing = [t for t in task_ids if t not in source['profiles']]
    if missing:
        raise ValueError(f'Tasks not in the template: {missing}')
    base = Path(template_dir).resolve()
    config = copy.deepcopy(template)
    config['repair_config'] = _absolute(template['repair_config'], base)
    config['variants'] = [dict(v) for v in variants]
    out = config['source']
    out['task_ids'] = list(task_ids)
    out['manifest']['path'] = _absolute(source['manifest']['path'], base)
    if 'bundle_profile' in source:
        out['bundle_profile']['path'] = _absolute(source['bundle_profile']['path'], base)
    out['task_inputs'] = _absolute(source['task_inputs'], base)
    out['profiles'], out['bundles'] = {}, {}
    for task in task_ids:
        pin = source['profiles'][task]
        profile = json.loads(resolve(pin['path'], base, data_root).read_text(encoding='utf-8'))
        out['profiles'][task] = {'path': pin['path'], 'sha256': profile['profile_hash']}  # admission's comparison
        out['bundles'][task] = {}
        for arm in ARMS:
            path = f'{bundle_dir}/{task}/{arm}'
            directory = resolve(path, base, data_root)
            hashes = {}
            for name in BUNDLE_FILES:
                if not (directory / name).is_file():
                    raise FileNotFoundError(f'Missing bundle file {directory / name}')
                hashes[name] = byte_digest((directory / name).read_bytes())
            out['bundles'][task][arm] = {'path': path, 'hashes': hashes}
    if 'graph_documents' in source:
        out['graph_documents'] = {}
        for task in task_ids:
            path = f'{bundle_dir}/{task}/graph.json'
            out['graph_documents'][task] = {'path': path,
                                            'sha256': byte_digest(resolve(path, base, data_root).read_bytes())}
    return config
