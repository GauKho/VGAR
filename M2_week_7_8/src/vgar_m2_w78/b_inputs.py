"""Freeze only trusted B inputs/protected history, separately from runtime revisions."""
import json

from .bootstrap import ROOT, verify_reference
from .config import load_config
from .contracts import RepairPolicy, RepairTask
from .context_adapter import load_handoff
from .evidence import digest
from .pipeline import require_trusted_fixture


def frozen_input_matches(target, original):
    """Keep history immutable; permit only byte-pinned VGAR layout relocation."""
    current = target.read_bytes()
    if current == original:
        return True
    allowed = {
        'config/demo.json': ('sha256:d1ba30333e9193a1e225ee3c2219b53cdec2be7c55756acb7eb89055be5b0825',
                             'sha256:aff993fb4fb3296b321c4529d1dabce73dce40667837e205dc661d76eba27fa3'),
        'config/source_pin.json': ('sha256:d62411622591bdd7dbfb87af7873a998f9e0f449662bc79ffba7cdec495b603a',
                                   'sha256:47b1d542f7d640da6c332365de786ccba92c5e041650515e1bd6395e52394913'),
        'tests/conftest.py': ('sha256:00bf9077554ae86d55aaccbcf8892266f941d8829210e42f6e1f9f7933aa6bf8',
                              'sha256:6b532975fd496bf9c70f7e30ba960cf63cf14bc814b27d068fa16032a3e04d3b'),
    }
    try:
        relative = target.relative_to(ROOT).as_posix()
        expected = allowed.get(relative)
        backup = ROOT/'integration/originals'/relative
        return bool(expected and (digest(original), digest(current)) == expected
                    and backup.read_bytes() == original)
    except (ValueError, OSError):
        return False


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
                if not frozen_input_matches(target, old.read_bytes()):
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
