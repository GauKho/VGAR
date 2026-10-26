"""M2 repair configuration files and repository-relative locations."""
import json
import os
from pathlib import Path

from vgar.repair.contracts import ModelProfile, RepairPolicy, RepairTask

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / 'configs/m2'


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if set(data) != {'policy', 'model'}:
        raise ValueError('Unexpected config fields')
    model = data['model']
    for field in ('snapshot', 'tokenizer_manifest'):
        model[field] = (path.parent / Path(model[field]).expanduser()).resolve()
    # A venv interpreter is a symlink on POSIX; resolving it loses the venv's site-packages.
    model['interpreter'] = Path(os.path.abspath(path.parent / Path(model['interpreter']).expanduser()))
    return RepairPolicy.model_validate(data['policy']), ModelProfile.model_validate(model)


def load_task(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_repo', 'bundle_directory'):
        data[key] = (path.parent / data[key]).resolve()
    return RepairTask.model_validate(data)
