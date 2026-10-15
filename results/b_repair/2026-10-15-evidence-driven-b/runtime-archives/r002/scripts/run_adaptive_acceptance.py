"""One authorized adaptive attempt per command; Codex, not this script, authors prompts."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar_m2_w78.adaptive_campaign import AdaptiveCampaignStore, audit_archive
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.contracts import ModelProfile, RepairPolicy, RepairTask
from vgar_m2_w78.evidence import atomic_json, begin_run, digest
from vgar_m2_w78.pipeline import run_repair
from vgar_m2_w78.diagnostics import exception_details

DEFAULT_CAMPAIGN = ROOT / 'results/adaptive_acceptance/2026-10-15-v5-plus'
DEFAULT_ARCHIVE = ROOT / 'results/adaptive-preflight/20261015T001508430263Z-6296d566fd2e/archive_manifest.json'


def freeze_adaptive_inputs(archive_path):
    from run_acceptance import freeze_inputs
    snapshot = freeze_inputs()
    # Legacy code/templates remain frozen. Adaptive templates are immutable PER revision,
    # registered separately, so appending V6 does not mutate a shared frozen runtime.
    snapshot['files'] = {name: value for name, value in snapshot['files'].items()
        if not (Path(name).parent == ROOT / 'prompts' and int(Path(name).stem.split('_v')[-1]) >= 5)}
    audit_archive(archive_path)
    snapshot.update(archive_manifest=str(archive_path.resolve()), archive_sha256=digest(archive_path.read_bytes()),
                    scope='adaptive development trusted fixtures; NOT benchmark or MCP')
    return snapshot


def export_final_profile(store):
    if store.state['status'] == 'PASS':
        frozen = json.loads((store.directory / 'frozen_inputs.json').read_text(encoding='utf-8'))
        atomic_json(store.directory / 'final_profile.json',
            dict(policy=dict(frozen.get('policy', {}), prompt_version=store.state['final_version']), model=frozen.get('model', {})))


def run_next(store):
    with store.session():
        if store.recover_pending() == 'LIVE':
            print(json.dumps(dict(action='PENDING', note='Owner alive; no generation started')))
            return 2
        action = store.next_action()
        if action['action'] == 'TERMINAL':
            export_final_profile(store)
            print(json.dumps(action, ensure_ascii=False, indent=2))
            return {'PASS': 0, 'FAIL': 1, 'ERROR': 2}[store.state['status']]
        if action['action'] == 'WAIT_PROMPT':
            print(json.dumps(action, ensure_ascii=False, indent=2))
            return 1
        attempt = store.reserve()
        frozen = json.loads((store.directory / 'frozen_inputs.json').read_text(encoding='utf-8'))
        profile = ModelProfile.model_validate(frozen['model'])
        policy = RepairPolicy.model_validate(dict(frozen['policy'], prompt_version=attempt['version']))
        task = RepairTask.model_validate(frozen['tasks'][attempt['task_id']]['task'])
        print(f'START {attempt["attempt_id"]} {attempt["phase"]} {attempt["task_id"]} {attempt["version"]}', flush=True)
        try:
            from vgar.graph.token_counter import LocalTokenizerCounter
            from vgar_m2_w78.generator_hf import HFGenerator, HFChatTokenizer
            counter = LocalTokenizerCounter(profile.tokenizer_manifest)
            generator = HFGenerator(profile, Path(attempt['run_root']) / 'model-workers', policy)
            result = run_repair(task, policy, generator, None, Path(attempt['run_root']),
                m1_counter=counter, tokenizer=HFChatTokenizer(generator, policy), profile=profile,
                campaign_id=store.state['campaign_id'], attempt_id=attempt['attempt_id'],
                feedback=attempt['feedback'], phase=attempt['phase'],
                rerun_reason='Approved bounded adaptive development; no raw diff repair or verifier relaxation')
        except BaseException as error:
            result = begin_run(Path(attempt['run_root']), 'adaptive-runtime-error', mode='real', task_id=task.task_id,
                campaign_id=store.state['campaign_id'], attempt_id=attempt['attempt_id'], adaptive_phase=attempt['phase'],
                prompt_feedback=attempt['feedback'], task=task.model_dump(mode='json'), policy=policy.model_dump(),
                model=profile.model_dump(mode='json'))
            result.finish('ERROR', reason=str(error), error_type=type(error).__name__, **exception_details(error))
        store.finish(result.path)
        print(result.path, flush=True)
        print(json.dumps(store.next_action(), ensure_ascii=False, indent=2))
        export_final_profile(store)
        return {'PASS': 0, 'FAIL': 1, 'ERROR': 2}[store.state['attempts'][-1]['status']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ('status', 'init', 'run-next', 'history'):
        modes.add_argument('--' + name, action='store_true')
    modes.add_argument('--register-prompt', metavar='VERSION')
    parser.add_argument('--campaign', type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument('--archive-manifest', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--reason', default='')
    parser.add_argument('--hypothesis', default='')
    args = parser.parse_args()
    try:
        if args.history:
            print(json.dumps(audit_archive(args.archive_manifest), ensure_ascii=False, indent=2))
            return 0
        if args.status and not (args.campaign / 'campaign.json').exists():
            print(json.dumps(dict(status='NOT_RUN', reason='CAMPAIGN_NOT_CREATED')))
            return 0
        if not args.status and not args.campaign.resolve().is_relative_to(ROOT / 'results/adaptive_acceptance'):
            raise ValueError('Adaptive writes must stay in M2 results/adaptive_acceptance')
        if args.init:
            store = AdaptiveCampaignStore.create(args.campaign, freeze_adaptive_inputs(args.archive_manifest))
            print(store.path)
            print(json.dumps(store.next_action()))
            return 0
        store = AdaptiveCampaignStore.open(args.campaign)
        if args.status:
            print(json.dumps(dict(**store.state, next_action=store.next_action()), ensure_ascii=False, indent=2))
            return 0
        verify_reference()
        if args.register_prompt:
            with store.session():
                store.register(args.register_prompt, args.reason, args.hypothesis)
            print(json.dumps(store.next_action()))
            return 0
        return run_next(store)
    except Exception as error:
        print(json.dumps(dict(status='ERROR', error=str(error), **exception_details(error)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
