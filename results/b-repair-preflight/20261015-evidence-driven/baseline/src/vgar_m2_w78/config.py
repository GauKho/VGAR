import json
from pathlib import Path
from .contracts import ModelProfile, RepairPolicy


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if set(data) != {'policy', 'model'}:
        raise ValueError('Unexpected config fields')
    model = data['model']
    for field in ('snapshot', 'interpreter', 'tokenizer_manifest'):
        model[field] = (path.parent / model[field]).resolve()
    return RepairPolicy.model_validate(data['policy']), ModelProfile.model_validate(model)

