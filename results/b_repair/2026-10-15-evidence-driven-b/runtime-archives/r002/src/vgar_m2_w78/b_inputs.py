"""Freeze only trusted B inputs/protected history, separately from runtime revisions."""
import json

from .bootstrap import ROOT, verify_reference
from .config import load_config
from .contracts import RepairPolicy, RepairTask
from .context_adapter import load_handoff
from .evidence import digest
from .pipeline import require_trusted_fixture


def freeze_b_inputs():
    reference = verify_reference()
    policy, profile = load_config(ROOT/'config/demo.json')
    defaults = RepairPolicy().model_dump()
    if any(policy.model_dump()[k] != v for k,v in defaults.items() if k != 'prompt_version'):
        raise ValueError('B must retain approved budgets')
    path = ROOT/'examples/tasks/multi_file_invoice.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_repo','bundle_directory'):
        value[key] = (path.parent/value[key]).resolve()
    task = RepairTask.model_validate(value)
    require_trusted_fixture(task)
    from vgar.graph.token_counter import LocalTokenizerCounter
    counter = LocalTokenizerCounter(profile.tokenizer_manifest)
    handoff = load_handoff(task, counter, counter.counter_label)
    task = task.model_copy(update={'failing_selectors': tuple(sorted(set(task.failing_selectors) | set(handoff.inputs['failing_selectors'])))})
    files = {}
    def freeze(file):
        files[str(file.resolve())] = digest(file.read_bytes())
    # Only old tests/fixtures and old templates are frozen; new regression test
    # files are allowed, existing tests/source/gold are not rewritten.
    baseline = ROOT/'results/b-repair-preflight/20261015-evidence-driven/baseline'
    for folder in ('tests','examples','config','prompts'):
        for old in (baseline/folder).rglob('*'):
            if old.is_file():
                target = ROOT/old.relative_to(baseline)
                if target.read_bytes() != old.read_bytes():
                    raise ValueError('Protected pre-edit input changed: '+str(target))
                freeze(target)
    for relative in ('patch.py','verification.py','checks.py','test_runner.py','test_selection.py','campaign.py','adaptive_campaign.py'):
        freeze(ROOT/'src/vgar_m2_w78'/relative)
    for directory in ('results/acceptance/2026-10-14-prompt-v3-v4', 'results/adaptive_acceptance/2026-10-15-v5-plus'):
        for file in (ROOT/directory).rglob('*'):
            if file.is_file() and file.suffix in ('.json','.txt','.diff','.md'):
                freeze(file)
    freeze(profile.tokenizer_manifest)
    manifest = json.loads(profile.tokenizer_manifest.read_text(encoding='utf-8'))
    assets = (profile.tokenizer_manifest.parent/manifest['assets_directory']).resolve()
    for file in assets.iterdir():
        if file.is_file():
            freeze(file)
    for name in ('config.json','generation_config.json','tokenizer.json','tokenizer_config.json',
                 'special_tokens_map.json','chat_template.jinja','model.safetensors.index.json'):
        file = profile.snapshot/name
        if file.is_file():
            freeze(file)
    return dict(task_id=task.task_id, task=task.model_dump(mode='json'),
        runtime_root=str(ROOT), policy=policy.model_dump(), model=profile.model_dump(mode='json'),
        reference=reference, files=files,
        scope='B development prototype; model revision declared by pinned local cache, no independent weight attestation')
