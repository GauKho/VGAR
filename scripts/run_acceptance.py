"""Explicit bounded real campaign. --status reads only; --run resumes, never resets."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.campaign import CampaignStore, CASES, VERSIONS, verify_frozen_files
from vgar_m2_w78.config import load_config
from vgar_m2_w78.contracts import RepairTask, ModelProfile, RepairPolicy
from vgar_m2_w78.context_adapter import load_handoff
from vgar_m2_w78.evidence import begin_run, digest
from vgar_m2_w78.pipeline import run_repair, require_trusted_fixture
from vgar_m2_w78.prompt import template_path
from vgar_m2_w78.workspace import inventory
from vgar_m2_w78.diagnostics import exception_details


def load_task(case):
    path = ROOT / 'examples/tasks' / (case + '.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_repo', 'bundle_directory'):
        data[key] = (path.parent / data[key]).resolve()
    return RepairTask.model_validate(data)


def freeze_inputs():
    ref = verify_reference()
    policy, profile = load_config(ROOT / 'config/demo.json')
    defaults = RepairPolicy().model_dump()
    if any(policy.model_dump()[key] != value for key,value in defaults.items() if key != 'prompt_version'):
        raise ValueError('Acceptance profile must retain approved budgets/settings')
    from vgar.graph.token_counter import LocalTokenizerCounter
    counter = LocalTokenizerCounter(profile.tokenizer_manifest)
    files, tasks = {}, {}
    for folder in ('src', 'scripts', 'prompts', 'config'):
        for file in sorted((ROOT / folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix in ('.py','.txt','.json','.toml','.ini'):
                files[str(file.resolve())] = digest(file.read_bytes())
    for case in CASES:
        task_path = ROOT / 'examples/tasks' / (case + '.json')
        files[str(task_path)] = digest(task_path.read_bytes())
        task = load_task(case)
        require_trusted_fixture(task)
        h = load_handoff(task, counter, counter.counter_label)
        tasks[case] = dict(task=task.model_dump(mode='json'), source_hashes=inventory(task.source_repo),
                          bundle_hashes=h.hashes, source_digest=h.metadata['source_digest'])
        for name in h.hashes:
            p = task.bundle_directory / name
            files[str(p)] = digest(p.read_bytes())
        for name, hash_value in tasks[case]['source_hashes'].items():
            files[str(task.source_repo / name)] = hash_value
    files[str(profile.tokenizer_manifest)] = digest(profile.tokenizer_manifest.read_bytes())
    manifest = json.loads(profile.tokenizer_manifest.read_text(encoding='utf-8'))
    assets = (profile.tokenizer_manifest.parent / manifest['assets_directory']).resolve()
    for p in assets.iterdir():
        if p.is_file() and p.suffix in ('.json','.jinja','.txt'):
            files[str(p)] = digest(p.read_bytes())
    return dict(reference=ref, policy=policy.model_dump(), model=profile.model_dump(mode='json'),
                templates={v:digest(template_path(v).read_text(encoding='utf-8')) for v in VERSIONS},
                tasks=tasks, files=files, scope='real trusted-fixture prototype; not benchmark; not MCP')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--status', action='store_true')
    modes.add_argument('--run', action='store_true')
    parser.add_argument('--campaign', type=Path, default=ROOT/'results/acceptance/2026-10-14-prompt-v3-v4')
    args = parser.parse_args()
    if args.status:
        if not (args.campaign / 'campaign.json').is_file():
            print(json.dumps(dict(status='NOT_RUN', reason='CAMPAIGN_NOT_CREATED')))
        else:
            print(json.dumps(CampaignStore.open(args.campaign).state, ensure_ascii=False, indent=2))
        return 0
    try:
        store = CampaignStore.open(args.campaign) if (args.campaign/'campaign.json').is_file() else CampaignStore.create(args.campaign,freeze_inputs())
        with store.session():
            frozen = json.loads((store.directory/'frozen_inputs.json').read_text(encoding='utf-8'))
            verify_reference()
            verify_frozen_files(frozen)
            if store.recover_pending() == 'LIVE':
                print('Pending owner is LIVE: no generation started.',flush=True)
                print(store.path)
                return 2
            while store.decision()['next'] is not None:
                verify_frozen_files(frozen)
                attempt = store.reserve()
                print(f'START {attempt["attempt_id"]} {attempt["version"]} {attempt["task_id"]}',flush=True)
                profile = ModelProfile.model_validate(frozen['model'])
                policy = RepairPolicy.model_validate(dict(frozen['policy'],prompt_version=attempt['version']))
                try:
                    from vgar.graph.token_counter import LocalTokenizerCounter
                    from vgar_m2_w78.generator_hf import HFGenerator, HFChatTokenizer
                    task = RepairTask.model_validate(frozen['tasks'][attempt['task_id']]['task'])
                    counter = LocalTokenizerCounter(profile.tokenizer_manifest)
                    generator = HFGenerator(profile,Path(attempt['run_root'])/'model-workers',policy)
                    result = run_repair(task,policy,generator,None,Path(attempt['run_root']),
                        m1_counter=counter,tokenizer=HFChatTokenizer(generator,policy),profile=profile,
                        campaign_id=store.state['campaign_id'],attempt_id=attempt['attempt_id'],
                        supersedes_run_id='20261014T091104527173Z-8e59e14c75c7' if attempt['number']==1 else None,
                        rerun_reason='Approved fixed V3/V4 campaign, no model/budget/guard changes')
                except BaseException as error:
                    result = begin_run(Path(attempt['run_root']),'acceptance-runtime-error',mode='real',
                        task_id=attempt['task_id'],campaign_id=store.state['campaign_id'],attempt_id=attempt['attempt_id'],
                        policy=policy.model_dump(),model=profile.model_dump(mode='json'))
                    result.finish('ERROR',reason=str(error),error_type=type(error).__name__, **exception_details(error))
                store.finish(result.path)
                print(f'END {attempt["attempt_id"]} {store.state["attempts"][-1]["status"]} {result.path}',flush=True)
            print(json.dumps(store.state,ensure_ascii=False,indent=2))
            print(store.path)
            return {'PASS':0,'FAIL':1,'ERROR':2}[store.state['status']]
    except Exception as error:
        report = begin_run(ROOT/'results/acceptance-errors','campaign-command-error',mode='real',campaign=str(args.campaign))
        report.finish('ERROR',reason=str(error),error_type=type(error).__name__, **exception_details(error))
        print(report.path,flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
