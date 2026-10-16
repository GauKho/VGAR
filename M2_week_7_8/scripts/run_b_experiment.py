"""One B attempt per command; Codex authors justified revisions between attempts."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from vgar_m2_w78.b_experiment import BExperimentStore, reservation_deadline, diagnose_assessment
from vgar_m2_w78.b_inputs import freeze_b_inputs
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.contracts import ModelProfile, RepairPolicy, RepairTask
from vgar_m2_w78.diagnostics import exception_details
from vgar_m2_w78.evidence import begin_run
from vgar_m2_w78.executor import run_bounded
from vgar_m2_w78.pipeline import run_repair

DEFAULT = ROOT/'results/b_repair/2026-10-15-evidence-driven-b'


def feedback(entry):
    if not entry or not entry.get('record'):
        return None
    record = json.loads(Path(entry['record']).read_text(encoding='utf-8'))
    # Preserve the original diagnosis receipt; a corrected runtime may classify
    # its canonical evidence more accurately when building new feedback.
    if diagnose_assessment(record, entry.get('gate_errors', []))['category'] != 'candidate':
        return None
    error = record.get('error_detail', {})
    diagnostic = error.get('parser_diagnostics') or record.get('stages', {}).get('parse_patch', {}).get('parser_diagnostics')
    message = error.get('message') or (record.get('stages', {}).get('apply', {}).get('error') or {}).get('message')
    if not message:
        checks = record.get('stages', {}).get('verification', {})
        message = checks.get('tests', {}).get('command', {}).get('stdout') or json.dumps(checks.get('reasons', []))
    if diagnostic:
        message = json.dumps({k:diagnostic.get(k) for k in (
            'raw_line','raw_line_text','path','hunk_header','expected_counts','actual_counts','counts_complete','invalid_body_lines')},
            ensure_ascii=False) + '\n' + (message or '')
    return dict(task_id='multi_file_invoice', source_run_id=record['run_id'],
                category=entry.get('reason') or 'PATCH_FAILED',
                message=(json.dumps(entry.get('gate_errors', [])) + '\n' + (message or 'See execution failure'))[:4000])


def run_next(store):
    with store.session():
        if store.recover_pending() == 'LIVE':
            print('Pending owner LIVE: no new launch.')
            return 2
        previous = store.state['attempts'][-1] if store.state['attempts'] else None
        entry = store.reserve()
        deadline = reservation_deadline(entry)
        frozen = store.frozen
        profile = ModelProfile.model_validate(frozen['model'])
        policy = RepairPolicy.model_validate(dict(frozen['policy'], prompt_version=entry['version'],
                                                global_timeout=entry['timeout_seconds']))
        task = RepairTask.model_validate(frozen['task'])
        print(f'START {entry["attempt_id"]} B {entry["version"]}/{entry["runtime_revision"]}; max8, stopfirstPASS', flush=True)
        try:
            verify_reference(deadline=deadline)
            from vgar.graph.token_counter import LocalTokenizerCounter
            from vgar_m2_w78.generator_hf import HFGenerator, HFChatTokenizer
            counter = LocalTokenizerCounter(profile.tokenizer_manifest)
            generator = HFGenerator(profile, Path(entry['run_root'])/'model-workers', policy)
            result = run_repair(task, policy, generator, None, Path(entry['run_root']),
                m1_counter=counter, tokenizer=HFChatTokenizer(generator, policy), profile=profile,
                campaign_id=store.state['campaign_id'], attempt_id=entry['attempt_id'], phase='B_development',
                feedback=feedback(previous), before_generation=store.bind_prompt,
                deadline=deadline,
                rerun_reason='Approved B-only evidence-driven repair; existing guards unchanged')
        except BaseException as error:
            result = begin_run(Path(entry['run_root']), 'b-runtime-error', mode='real',
                task_id=task.task_id, campaign_id=store.state['campaign_id'], attempt_id=entry['attempt_id'],
                policy=policy.model_dump(), model=profile.model_dump(mode='json'), task=task.model_dump(mode='json'))
            result.finish('ERROR', reason='INTERNAL_ERROR', **exception_details(error))
        store.finish(result.path)
        print(result.path, flush=True)
        print(json.dumps(store.state['attempts'][-1].get('diagnosis'), ensure_ascii=False), flush=True)
        print(json.dumps(store.decision(), ensure_ascii=False), flush=True)
        return {'PASS':0, 'FAIL':1, 'ERROR':2}[store.state['attempts'][-1]['status']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('init','status','history','recover','register-runtime','run-next'):
        modes.add_argument('--'+mode, action='store_true')
    modes.add_argument('--register-prompt', metavar='VERSION')
    parser.add_argument('--campaign', type=Path, default=DEFAULT)
    parser.add_argument('--tests-record', type=Path)
    parser.add_argument('--reason', default='')
    parser.add_argument('--trigger')
    args = parser.parse_args()
    try:
        readonly = args.status or args.history
        if not readonly and not args.campaign.resolve().is_relative_to(ROOT/'results/b_repair'):
            raise ValueError('B experiment writes must stay in results/b_repair')
        if readonly and not (args.campaign/'campaign.json').is_file():
            print(json.dumps(dict(status='NOT_RUN', reason='CAMPAIGN_NOT_CREATED')))
            return 0
        if args.init:
            store = BExperimentStore.create(args.campaign, freeze_b_inputs())
        else:
            store = BExperimentStore.open(args.campaign)
        if args.run_next:
            return run_next(store)
        if args.register_runtime:
            if not args.tests_record:
                raise ValueError('--tests-record required')
            check = begin_run(args.campaign/'qualification', 'b-runtime-ruff', mode='offline')
            lint = run_bounded((sys.executable,'-m','ruff','check','--select','E9,F','src','scripts','tests'),ROOT,30)
            check.stage('ruff',lint)
            check.finish(lint['status'])
            if lint['status'] != 'PASS':
                raise ValueError('Ruff failed: ' + str(check.path))
            with store.session():
                store.register_runtime(args.reason,args.tests_record,trigger=args.trigger)
        elif args.register_prompt:
            with store.session():
                store.register_prompt(args.register_prompt,args.reason,trigger=args.trigger)
        elif args.recover:
            with store.session():
                print(store.recover_pending())
        print(json.dumps(dict(campaign=str(store.path), decision=store.decision(),
            attempts=[{k:a.get(k) for k in ('number','version','runtime_revision','status','complete','record','diagnosis','elapsed_seconds')}
                      for a in store.state['attempts']]), ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(json.dumps(dict(status='ERROR', **exception_details(error)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
