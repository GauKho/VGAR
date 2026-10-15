"""Bounded development tuning. Codex authors revisions; this module never does."""
import json
import os
from pathlib import Path

from .campaign import CampaignStore, assess_record, process_identity, verify_frozen_files
from .evidence import atomic_json, digest
from .executor import utc_now
from .prompt import template_path

A, B, C = 'single_file_login', 'multi_file_invoice', 'missing_links'


def _decision(history):
    terminal = lambda status, reason, version=None: dict(status=status, reason=reason, final_version=version, next=None)
    if any(e['status'] == 'ERROR' for e in history):
        return terminal('ERROR', 'RUNTIME_OR_EVIDENCE_ERROR')
    b = [e for e in history if e['phase'] == 'tuning_B']
    c = [e for e in history if e['phase'] == 'tuning_C']
    final = [e for e in history if e['phase'] == 'final']
    if len(b) > 4 or len(c) > 4 or len(final) > 3:
        raise ValueError('Adaptive quota exceeded')
    last = history[-1] if history else None
    phase, case = ('tuning_B', B) if not b or (b[-1]['status'] != 'PASS' and len(b) < 4) else ('tuning_C', C)
    if phase == 'tuning_C' and c and (c[-1]['status'] == 'PASS' or len(c) == 4):
        if b[-1]['status'] != 'PASS' or c[-1]['status'] != 'PASS':
            return terminal('FAIL', 'TUNING_QUOTA_EXHAUSTED')
        version = c[-1]['version']
        if len(final) == 3:
            passed = all(e['status'] == 'PASS' for e in final)
            return terminal('PASS' if passed else 'FAIL', None if passed else 'FINAL_VALIDATION_FAILED', version if passed else None)
        return dict(status='NOT_RUN', reason=None, final_version=None,
                    next=dict(task_id=(A, B, C)[len(final)], phase='final', version=version, require_new_prompt=False))
    new = last is None or last['status'] == 'FAIL'
    return dict(status='NOT_RUN', reason=None, final_version=None,
                next=dict(task_id=case, phase=phase, version=None if new else last['version'], require_new_prompt=new))


def adaptive_step(history):
    prefix = []
    for entry in history:
        expected = _decision(prefix)['next']
        if (expected is None or entry['task_id'] != expected['task_id'] or entry['phase'] != expected['phase']
                or entry['status'] not in ('PASS', 'FAIL', 'ERROR')):
            raise ValueError('Invalid adaptive history/order/quota')
        if expected['require_new_prompt']:
            if prefix and entry['version'] == prefix[-1]['version']:
                raise ValueError('Failure requires a new prompt revision')
        elif entry['version'] != expected['version']:
            raise ValueError('Unexpected prompt version; final is frozen')
        prefix.append(entry)
    return _decision(prefix)


def feedback_from(path):
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if record.get('status') != 'FAIL' or not record.get('complete'):
        raise ValueError('Feedback must reference a completed failed run')
    stages = record.get('stages', {})
    message = (stages.get('apply', {}).get('error') or {}).get('message')
    message = message or record.get('error_detail', {}).get('message')
    message = message or stages.get('verification', {}).get('tests', {}).get('command', {}).get('stdout')
    return dict(task_id=record['task_id'], source_run_id=record['run_id'],
                category=record.get('reason') or 'PATCH_FAILED', message=(message or 'Patch did not pass deterministic checks')[:4000])


def audit_archive(manifest_path):
    """Verify original runtime bytes and old evidence without expecting new code to be old."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    for entry in data['files'].values():
        archived = Path(entry['archive'])
        if archived.is_symlink() or digest(archived.read_bytes()) != entry['sha256']:
            raise ValueError('Archived runtime changed: ' + str(archived))
    for name, expected in {**data['historical'], **data['protected_external']}.items():
        if digest(Path(name).read_bytes()) != expected:
            raise ValueError('Historical/protected evidence changed: ' + name)
    for name in data['historical']:
        if Path(name).name == 'frozen_inputs.json':
            frozen = json.loads(Path(name).read_text(encoding='utf-8'))
            for original, expected in frozen.get('files', {}).items():
                observed = data['files'][original]['sha256'] if original in data['files'] else digest(Path(original).read_bytes())
                if observed != expected:
                    raise ValueError('Archived runtime differs from original frozen mapping: ' + original)
    current_changes = [name for name, entry in data['files'].items()
                       if not Path(name).is_file() or digest(Path(name).read_bytes()) != entry['sha256']]
    return dict(status='PASS', archived_files=len(data['files']), historical_files=len(data['historical']),
                current_runtime_changes=current_changes, note='Historical bytes verified; new code is not claimed to be old runtime')


class AdaptiveCampaignStore(CampaignStore):
    @classmethod
    def create(cls, directory, snapshot):
        store = cls(directory)
        store.directory.mkdir(parents=True, exist_ok=False)
        frozen = store.directory / 'frozen_inputs.json'
        atomic_json(frozen, snapshot)
        store.state = dict(campaign_id=store.directory.name, status='NOT_RUN', complete=False,
            started_utc=utc_now(), ended_utc=None, limits={'tuning_B': 4, 'tuning_C': 4, 'final': 3},
            frozen_sha256=digest(frozen.read_bytes()), revisions={}, attempts=[], final_version=None, reason=None)
        atomic_json(store.path, store.state)
        return store

    def decision(self):
        return adaptive_step([e for e in self.state['attempts'] if e['complete']])

    def _reload(self):
        self.state = json.loads(self.path.read_text(encoding='utf-8'))
        snapshot_path = self.directory / 'frozen_inputs.json'
        if digest(snapshot_path.read_bytes()) != self.state['frozen_sha256']:
            raise ValueError('Frozen adaptive snapshot changed')
        frozen = json.loads(snapshot_path.read_text(encoding='utf-8'))
        verify_frozen_files(frozen)
        if self.state['limits'] != {'tuning_B': 4, 'tuning_C': 4, 'final': 3}:
            raise ValueError('Adaptive limits changed')
        if 'archive_manifest' in frozen:
            if digest(Path(frozen['archive_manifest']).read_bytes()) != frozen['archive_sha256']:
                raise ValueError('Archive manifest changed')
            audit_archive(frozen['archive_manifest'])
        revisions = self.state['revisions']
        for index, (version, revision) in enumerate(revisions.items(), 5):
            if version != f'm2-w78-v{index}' or digest(template_path(version).read_text(encoding='utf-8')) != revision['template_hash']:
                raise ValueError('Prompt revision changed')
            registered = self.directory / 'revisions' / (version + '.json')
            if json.loads(registered.read_text(encoding='utf-8')) != revision:
                raise ValueError('Prompt registration changed')
        prefix, pending = [], False
        for number, entry in enumerate(self.state['attempts'], 1):
            expected = adaptive_step(prefix)['next']
            if (pending or expected is None or entry['number'] != number or entry['attempt_id'] != f'attempt-{number:02}'
                    or entry['version'] not in revisions or entry['phase'] != expected['phase'] or entry['task_id'] != expected['task_id']):
                raise ValueError('Historical adaptive ledger order changed')
            if not entry['complete']:
                pending = True
                if entry['status'] != 'NOT_RUN':
                    raise ValueError('Pending ledger changed')
            elif entry.get('record'):
                assessed = self._assess_entry(entry, entry['record'], frozen)
                if any(entry.get(k) != assessed[k] for k in ('status', 'observed_status', 'canonical_sha256', 'gate_errors')):
                    raise ValueError('Historical ledger differs from canonical evidence')
                prefix.append(entry)
            elif entry['status'] == 'ERROR' and entry.get('reason') == 'CONFIRMED_INTERRUPTION':
                prefix.append(entry)
            else:
                raise ValueError('Terminal attempt missing canonical record')
        step = self.decision()
        if (any(self.state[k] != step[k] for k in ('status', 'final_version', 'reason'))
                or self.state['complete'] != (step['next'] is None)):
            raise ValueError('Historical derived state changed')

    def register(self, version, reason, hypothesis):
        self._owned()
        if any(not a['complete'] for a in self.state['attempts']):
            raise RuntimeError('Pending attempt prohibits prompt changes')
        step = self.decision()['next']
        used = {e['version'] for e in self.state['attempts']}
        if step is None or not step['require_new_prompt'] or any(v not in used for v in self.state['revisions']):
            raise RuntimeError('No new prompt revision required/allowed')
        if version != f'm2-w78-v{5 + len(self.state["revisions"])}' or not reason.strip() or not hypothesis.strip():
            raise ValueError('Revision must be next version with reason and hypothesis')
        previous = self.state['attempts'][-1] if self.state['attempts'] else None
        template_hash = digest(template_path(version).read_text(encoding='utf-8'))
        if previous and template_hash == self.state['revisions'][previous['version']]['template_hash']:
            raise ValueError('New prompt is identical to unchanged parent template')
        revision = dict(template_hash=template_hash,
            parent_version=previous['version'] if previous else None,
            parent_record=previous.get('record') if previous else None, reason=reason, hypothesis=hypothesis, registered_utc=utc_now())
        path = self.directory / 'revisions' / (version + '.json')
        if path.exists():
            orphan = json.loads(path.read_text(encoding='utf-8'))
            if set(orphan) != set(revision) or any(orphan[k] != revision[k] for k in revision if k != 'registered_utc'):
                raise ValueError('Orphan prompt registration does not match intended revision')
            revision = orphan
        else:
            atomic_json(path, revision)
        self.state['revisions'][version] = revision
        try:
            atomic_json(self.path, self.state)
        except BaseException:
            self.state['revisions'].pop(version)
            raise

    def next_action(self):
        step = self.decision()
        if any(not e['complete'] for e in self.state['attempts']):
            return dict(action='PENDING', **step)
        if step['next'] is None:
            return dict(action='TERMINAL', **step)
        used = {e['version'] for e in self.state['attempts']}
        ready = [v for v in self.state['revisions'] if v not in used]
        need = step['next']['require_new_prompt']
        return dict(action='WAIT_PROMPT' if need and not ready else 'RUN_NEXT', **step)

    def reserve(self):
        self._owned()
        self._reload()
        if any(not e['complete'] for e in self.state['attempts']):
            raise RuntimeError('Pending attempt must be reconciled, never restarted')
        step = self.decision()['next']
        if step is None:
            raise RuntimeError('Adaptive campaign is terminal')
        if self.next_action()['action'] == 'WAIT_PROMPT':
            raise RuntimeError('New prompt revision required before next generation')
        used = {e['version'] for e in self.state['attempts']}
        version = next(v for v in self.state['revisions'] if v not in used) if step['require_new_prompt'] else step['version']
        previous = self.state['attempts'][-1] if self.state['attempts'] else None
        feedback = (feedback_from(previous['record']) if previous and previous['status'] == 'FAIL'
                    and previous['task_id'] == step['task_id'] and step['phase'] != 'final' else None)
        number = len(self.state['attempts']) + 1
        entry = dict(task_id=step['task_id'], phase=step['phase'], version=version, number=number,
            attempt_id=f'attempt-{number:02}', status='NOT_RUN', complete=False, feedback=feedback,
            started_utc=utc_now(), ended_utc=None, owner={'pid': os.getpid(), 'birth': process_identity(os.getpid())},
            run_root=str(self.directory / 'attempts' / f'{number:02}'), record=None)
        self.state['attempts'].append(entry)
        atomic_json(self.path, self.state)
        # Durable reservation precedes all setup; crash never leaves an uncounted launch.
        Path(entry['run_root']).mkdir(parents=True, exist_ok=False)
        return entry

    def _assess_entry(self, entry, path, frozen):
        path = Path(path).resolve()
        if Path(entry['run_root']).resolve() not in path.parents or path.name != 'run_record.json':
            raise ValueError('Canonical outside reserved adaptive attempt')
        record = json.loads(path.read_text(encoding='utf-8'))
        if (record.get('campaign_id') != self.state['campaign_id'] or record.get('attempt_id') != entry['attempt_id']
                or record.get('task_id') != entry['task_id'] or record.get('adaptive_phase') != entry['phase']
                or record.get('policy', {}).get('prompt_version') != entry['version']
                or record.get('prompt_feedback') != entry['feedback']):
            raise ValueError('Canonical adaptive identity/feedback changed')
        assessment = assess_record(path)
        errors = assessment['gate_errors']
        if 'model' in frozen and record.get('model') != frozen['model']:
            errors.append('FROZEN_MODEL_CONFIG_MISMATCH')
        if 'policy' in frozen and record.get('policy') != dict(frozen['policy'], prompt_version=entry['version']):
            errors.append('FROZEN_POLICY_MISMATCH')
        if 'tasks' in frozen and record.get('task') != frozen['tasks'][entry['task_id']]['task']:
            errors.append('FROZEN_TASK_MISMATCH')
        prompt = record.get('stages', {}).get('prompt', {})
        if record['status'] == 'PASS' and prompt.get('template_hash') != self.state['revisions'][entry['version']]['template_hash']:
            errors.append('FROZEN_TEMPLATE_MISMATCH')
        if entry['phase'] == 'final' and (entry['feedback'] is not None or prompt.get('metadata', {}).get('feedback') is not None):
            errors.append('FINAL_FEEDBACK_LEAK')
        if errors:
            assessment['status'] = 'ERROR'
        return assessment

    def recover_pending(self):
        self._owned()
        if not self.state['attempts'] or self.state['attempts'][-1]['complete']:
            next_step = self.decision()['next']
            used = {e['version'] for e in self.state['attempts']}
            if next_step and next_step['require_new_prompt'] and not any(v not in used for v in self.state['revisions']):
                version = f'm2-w78-v{5 + len(self.state["revisions"])}'
                path = self.directory / 'revisions' / (version + '.json')
                if path.exists():
                    orphan = json.loads(path.read_text(encoding='utf-8'))
                    self.register(version, orphan['reason'], orphan['hypothesis'])
                    return 'RECOVERED_REGISTRATION'
            return 'NONE'
        entry = self.state['attempts'][-1]
        identity = process_identity(entry['owner']['pid'])
        if identity is not None and identity == entry['owner']['birth']:
            return 'LIVE'
        records = list(Path(entry['run_root']).glob('*/run_record.json'))
        if len(records) == 1 and json.loads(records[0].read_text(encoding='utf-8')).get('complete'):
            self.finish(records[0])
        else:
            self._commit(entry, dict(status='ERROR', reason='CONFIRMED_INTERRUPTION', gate_errors=['NO_UNIQUE_TERMINAL_RECORD']))
        return 'RECOVERED'
