"""B-only durable experiment; mutable work is archived as immutable revisions."""
from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import time

from .campaign import CampaignStore, assess_record, process_identity, verify_frozen_files
from .evidence import atomic_json, digest
from .executor import utc_now

B = 'multi_file_invoice'


def reservation_deadline(entry):
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(entry['started_utc'])).total_seconds()
    return time.monotonic() + entry['timeout_seconds'] - max(0, elapsed)


def archive_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Archived revision changed: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def runtime_fingerprint(root):
    root = Path(root).resolve()
    return {str(p.resolve()): digest(p.read_bytes()) for folder in ('src', 'scripts', 'config')
        for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts
        and p.suffix in ('.py', '.json', '.ini', '.toml')}


def b_decision(attempts, stop_reason=None):
    if stop_reason:
        return dict(status='ERROR', complete=True, reason=stop_reason, next=None)
    if any(not a['complete'] for a in attempts):
        return dict(status='NOT_RUN', complete=False, reason='RUNNING', next=None)
    if attempts and attempts[-1]['status'] == 'PASS':
        return dict(status='PASS', complete=True, reason=None, next=None)
    used = sum(a.get('elapsed_seconds', 0) for a in attempts)
    if len(attempts) >= 8 or used >= 14400:
        return dict(status='FAIL', complete=True, reason='BUDGET_EXHAUSTED', next=None)
    return dict(status='NOT_RUN', complete=False, reason='WAIT_DIAGNOSIS' if attempts else 'READY',
                next=B, remaining_seconds=14400-used)


def diagnose(record):
    text = json.dumps({k:record.get(k) for k in ('error_detail','integrity_error','integrity_exception','stages')},
                      ensure_ascii=False).lower()
    reason = record.get('reason') or ''
    if (record.get('original_source_unchanged') is False or record.get('integrity_error')
            or any(s in text for s in ('hash mismatch', 'source changed', 'frozen input', 'protected source',
                                      'prompt bytes mismatch', 'input hash mismatch'))):
        return dict(category='integrity', action='STOP', reason=reason)
    if record.get('status') == 'ERROR' or any(s in text for s in ('out of memory', 'winerror', 'timeout')):
        return dict(category='runtime', action='DIAGNOSE_RUNTIME', reason=reason)
    if reason in ('PATCH_PARSE_ERROR', 'PATCH_APPLY_FAILED', 'TEST_FAILED', 'TYPECHECK_FAILED', 'LINT_FAILED', 'VERIFICATION_INCOMPLETE'):
        return dict(category='candidate', action='REVISE_PROMPT', reason=reason)
    return dict(category='unknown', action='STOP', reason=reason)


def diagnose_assessment(record, errors):
    if not errors:
        return diagnose(record)
    if any(code in ('PUBLIC_SIGNATURE_CHANGED', 'ACTUAL_CHANGED_FILES') for code in errors) and all(
            code in ('PUBLIC_SIGNATURE_CHANGED', 'ACTUAL_CHANGED_FILES') for code in errors):
        return dict(category='candidate', action='REVISE_PROMPT', reason=','.join(errors))
    if all(code in ('REAL_GENERATION_DIAGNOSTICS','CLEANUP_INCOMPLETE','B_ARTIFACT_AUDIT_INCOMPLETE',
                    'BOTH_REQUIRED_BASELINE_FAILURES') for code in errors):
        return dict(category='runtime', action='DIAGNOSE_RUNTIME', reason=','.join(errors))
    return dict(category='integrity', action='STOP', reason=','.join(errors))


class BExperimentStore(CampaignStore):
    @classmethod
    def create(cls, directory, snapshot):
        if snapshot.get('task_id') != B or snapshot.get('task', {}).get('task_id') != B:
            raise ValueError('B experiment only accepts multi_file_invoice')
        store = cls(directory)
        store.directory.mkdir(parents=True, exist_ok=False)
        atomic_json(store.directory/'frozen_inputs.json', snapshot)
        store.frozen = snapshot
        store.state = dict(campaign_id=store.directory.name, attempts=[], prompts={}, runtimes={},
            prompt=None, runtime=None, started_utc=utc_now(), ended_utc=None,
            max_attempts=8, budget_seconds=14400, stop_reason=None,
            frozen_sha256=digest((store.directory/'frozen_inputs.json').read_bytes()))
        store._save()
        return store

    def decision(self):
        return b_decision(self.state['attempts'], self.state.get('stop_reason'))

    def _save(self):
        self.state.update({k:v for k,v in self.decision().items() if k != 'next'})
        if self.state['complete'] and not self.state['ended_utc']:
            self.state['ended_utc'] = utc_now()
        atomic_json(self.path, self.state)
        rows = ['# B-only development experiment', '', f'Status: {self.state["status"]}',
                f'Reason: {self.state["reason"]}', '', '|Attempt|Prompt|Runtime|Status|Cause|Record|',
                '|---|---|---|---|---|---|']
        for a in self.state['attempts']:
            rows.append(f'|{a["number"]}|{a["version"]}|{a["runtime_revision"]}|{a["status"]}|'
                        f'{a.get("diagnosis", {}).get("category", "pending")}|{a.get("record", "")}|')
        rows += ['', 'First audited PASS only; no independent confirmation/A-C/SWE-bench claim.']
        (self.directory/'REPORT.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')

    def _reload(self):
        self.state = json.loads(self.path.read_text(encoding='utf-8'))
        frozen = self.directory/'frozen_inputs.json'
        if digest(frozen.read_bytes()) != self.state['frozen_sha256']:
            raise ValueError('Frozen input manifest changed')
        self.frozen = json.loads(frozen.read_text(encoding='utf-8'))
        verify_frozen_files(self.frozen)
        if (self.frozen.get('task_id') != B or self.state['max_attempts'] != 8
                or self.state['budget_seconds'] != 14400 or len(self.state['attempts']) > 8):
            raise ValueError('B limits/task changed')
        for group in ('prompts', 'runtimes'):
            for revision in self.state[group].values():
                manifest = Path(revision['manifest'])
                if digest(manifest.read_bytes()) != revision['sha256']:
                    raise ValueError('Revision manifest changed')
                data = json.loads(manifest.read_text(encoding='utf-8'))
                for archive, expected in data['archives'].items():
                    if digest(Path(archive).read_bytes()) != expected:
                        raise ValueError('Archived revision changed: ' + archive)
        pending = False
        for n, a in enumerate(self.state['attempts'], 1):
            if pending or a['number'] != n or a['attempt_id'] != f'attempt-{n:02}':
                raise ValueError('Attempt ledger order changed')
            if not a['complete']:
                pending = True
                if a['status'] != 'NOT_RUN':
                    raise ValueError('Historical pending outcome changed')
            elif a.get('record'):
                if digest(Path(a['record']).read_bytes()) != a['canonical_sha256']:
                    raise ValueError('Historical canonical changed')
                assessment = self._assess(a, a['record'])
                # Run-end integrity errors are independently captured in the
                # immutable terminal receipt, not inferred from later runtime.
                extra = [e for e in a['gate_errors'] if e in (
                    'RUNTIME_CHANGED_DURING_RUN', 'PROTECTED_INPUT_CHANGED_DURING_RUN')]
                assessment['gate_errors'].extend(extra)
                if assessment['gate_errors']:
                    assessment['status'] = 'ERROR'
                if any(a.get(k) != assessment[k] for k in ('status','observed_status','gate_errors','canonical_sha256')):
                    raise ValueError('Historical outcome differs from canonical assessment')
            elif a.get('reason') != 'CONFIRMED_INTERRUPTION':
                raise ValueError('Terminal attempt lacks evidence')
            runtime = self.revision('runtimes', a['runtime_revision'])
            prompt = self.revision('prompts', a['version'])
            if (a['runtime_files'] != runtime['files'] or a['template_hash'] != prompt['template_hash']
                    or a['runtime_manifest_sha256'] != self.state['runtimes'][a['runtime_revision']]['sha256']):
                raise ValueError('Historical revision binding changed')
            if a['complete']:
                receipt = Path(a['run_root'])/'outcome.json'
                if (not receipt.is_file() or digest(receipt.read_bytes()) != a.get('outcome_sha256')
                        or json.loads(receipt.read_text(encoding='utf-8')) != {k:v for k,v in a.items() if k != 'outcome_sha256'}):
                    raise ValueError('Historical outcome/accounting receipt changed')
                elapsed = (datetime.fromisoformat(a['ended_utc'])-datetime.fromisoformat(a['started_utc'])).total_seconds()
                if a['elapsed_seconds'] < elapsed or elapsed < 0:
                    raise ValueError('Historical accounting invalid')
        expected = self.decision()
        if any(self.state[k] != expected[k] for k in ('status', 'complete', 'reason')):
            raise ValueError('Derived experiment state changed')

    def _register(self, group, name, data):
        path = self.directory/'revisions'/f'{name}.json'
        if name in self.state[group]:
            raise ValueError('Revision is append-only')
        if path.exists():
            existing = json.loads(path.read_text(encoding='utf-8'))
            if {k:v for k,v in existing.items() if k != 'created_utc'} != {k:v for k,v in data.items() if k != 'created_utc'}:
                raise ValueError('Orphan revision differs from requested registration')
        else:
            atomic_json(path, data)
        self.state[group][name] = dict(manifest=str(path), sha256=digest(path.read_bytes()))

    def _can_edit(self, reason, trigger):
        self._owned()
        if self.state['complete'] or any(not a['complete'] for a in self.state['attempts']):
            raise RuntimeError('Terminal/Pending experiment cannot register revisions')
        if not reason.strip():
            raise ValueError('Revision requires a reason/hypothesis')
        if self.state['attempts'] and trigger != self.state['attempts'][-1].get('record'):
            raise ValueError('Revision must reference latest triggering record')

    def register_runtime(self, reason, test_record, trigger=None):
        self._can_edit(reason, trigger)
        root = Path(self.frozen['runtime_root'])
        fingerprint = runtime_fingerprint(root)
        proof_path = Path(test_record).resolve()
        proof = json.loads(proof_path.read_text(encoding='utf-8'))
        command = proof.get('stages', {}).get('pytest', {})
        if (proof.get('status') != 'PASS' or not proof.get('complete') or proof.get('mode') != 'offline'
                or command.get('exit_code') != 0 or 'tests' not in command.get('argv', [])
                or proof.get('runtime_before') != fingerprint or proof.get('runtime_after') != fingerprint):
            raise ValueError('Runtime requires full-suite PASS at this exact fingerprint')
        parent = self.state['runtime']
        previous = self.revision('runtimes', parent)['files'] if parent else {}
        if fingerprint == previous:
            raise ValueError('Unchanged runtime is not a repair')
        name = f'r{len(self.state["runtimes"])+1:03}'
        folder = self.directory/'runtime-archives'/name
        folder.mkdir(parents=True, exist_ok=True)
        archives = {}
        changes = []
        for source, expected in fingerprint.items():
            file = Path(source)
            target = folder/file.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = file.read_bytes()
            if digest(data) != expected:
                raise ValueError('Runtime changed during archive')
            archive_once(target, data)
            archives[str(target)] = expected
            if previous.get(source) != expected:
                old = ''
                if parent and source in previous:
                    old = (self.directory/'runtime-archives'/parent/file.relative_to(root)).read_text(encoding='utf-8')
                changes.extend(difflib.unified_diff(old.splitlines(True), data.decode('utf-8').splitlines(True),
                    fromfile=str(file.relative_to(root)), tofile=str(file.relative_to(root))))
        proof_copy = folder/'qualification.json'
        archive_once(proof_copy, proof_path.read_bytes())
        archives[str(proof_copy)] = digest(proof_copy.read_bytes())
        diff = folder/'changes.diff'
        archive_once(diff, ''.join(changes).encode('utf-8'))
        archives[str(diff)] = digest(diff.read_bytes())
        self._register('runtimes', name, dict(files=fingerprint, archives=archives, parent=parent,
            reason=reason, trigger=trigger, test_record=str(proof_path), created_utc=utc_now()))
        self.state['runtime'] = name
        self._save()
        return name

    def revision(self, group, name):
        return json.loads(Path(self.state[group][name]['manifest']).read_text(encoding='utf-8'))

    def register_prompt(self, version, reason, trigger=None):
        self._can_edit(reason, trigger)
        if version != f'm2-w78-v{10+len(self.state["prompts"])}':
            raise ValueError('Prompt must be next append-only version starting V10')
        path = Path(self.frozen['runtime_root'])/'prompts'/('repair_v'+version.rsplit('v',1)[1]+'.txt')
        data = path.read_bytes()
        if path.is_symlink() or not data:
            raise ValueError('Invalid prompt')
        if b'\r' in data:
            raise ValueError('Prompt revisions require LF line endings before reservation')
        archive = self.directory/'prompt-archives'/(version+'.txt')
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive_once(archive, data)
        self._register('prompts', version, dict(path=str(path), template_hash=digest(data),
            archives={str(archive): digest(data)}, parent=self.state['prompt'], reason=reason,
            trigger=trigger, created_utc=utc_now()))
        self.state['prompt'] = version
        self._save()

    def reserve(self):
        self._owned()
        if any(not a['complete'] for a in self.state['attempts']):
            raise RuntimeError('Pending attempt cannot restart')
        decision = self.decision()
        if decision['complete']:
            raise RuntimeError('Experiment terminal or budget exhausted')
        runtime = self.state['runtime']
        if not runtime or runtime_fingerprint(self.frozen['runtime_root']) != self.revision('runtimes', runtime)['files']:
            raise ValueError('Current runtime is not registered/qualified')
        version = self.state['prompt']
        if not version:
            raise ValueError('No prompt registered')
        prompt = self.revision('prompts', version)
        if digest(Path(prompt['path']).read_bytes()) != prompt['template_hash']:
            raise ValueError('Registered prompt changed')
        number = len(self.state['attempts'])+1
        entry = dict(number=number, attempt_id=f'attempt-{number:02}', task_id=B, version=version,
            template_hash=prompt['template_hash'], runtime_revision=runtime,
            runtime_files=self.revision('runtimes', runtime)['files'],
            runtime_manifest_sha256=self.state['runtimes'][runtime]['sha256'],
            status='NOT_RUN', complete=False, started_utc=utc_now(), ended_utc=None,
            owner=dict(pid=os.getpid(), birth=process_identity(os.getpid())),
            timeout_seconds=min(1800.0, decision['remaining_seconds']),
            run_root=str(self.directory/'attempts'/f'{number:02}'), record=None)
        self.state['attempts'].append(entry)
        self._save()
        Path(entry['run_root']).mkdir(parents=True, exist_ok=False)
        return entry

    def bind_prompt(self, run, prompt):
        self._owned()
        verify_frozen_files(self.frozen)
        entry = self.state['attempts'][-1]
        identity = digest(json.dumps([entry['runtime_manifest_sha256'], prompt.template_hash, prompt.prompt_hash]))
        if any(a.get('request_identity') == identity for a in self.state['attempts'][:-1]):
            raise ValueError('Duplicate unchanged real generation is forbidden')
        if entry['template_hash'] != prompt.template_hash:
            raise ValueError('Prompt differs from reservation')
        entry.update(request_identity=identity, prompt_hash=prompt.prompt_hash, input_tokens=prompt.input_tokens)
        run.record.update(runtime_revision=entry['runtime_revision'],
            runtime_manifest_sha256=entry['runtime_manifest_sha256'], request_identity=identity)
        run.save()
        self._save()

    def _assess(self, entry, path):
        path = Path(path).resolve()
        if path.parent.parent != Path(entry['run_root']).resolve():
            raise ValueError('Invalid terminal record location')
        record = json.loads(path.read_text(encoding='utf-8'))
        if (record.get('campaign_id') != self.state['campaign_id'] or record.get('attempt_id') != entry['attempt_id']
                or record.get('task_id') != B or record.get('policy', {}).get('prompt_version') != entry['version']):
            raise ValueError('Attempt/canonical identity mismatch')
        assessment = assess_record(path)
        if record['status'] == 'PASS':
            from .b_acceptance import audit_b_pass
            assessment['gate_errors'].extend(audit_b_pass(path, self.frozen, entry))
            if assessment['gate_errors']:
                assessment['status'] = 'ERROR'
        return assessment

    def _receipt(self, entry):
        path = Path(entry['run_root'])/'outcome.json'
        data = {k:v for k,v in entry.items() if k != 'outcome_sha256'}
        from .evidence import encode_json
        archive_once(path, encode_json(data))
        entry['outcome_sha256'] = digest(path.read_bytes())

    def finish(self, path):
        self._owned()
        entry = self.state['attempts'][-1]
        if entry['complete']:
            raise ValueError('Attempt already finalized')
        assessment = self._assess(entry, path)
        record = json.loads(Path(path).read_text(encoding='utf-8'))
        # Runtime may change between attempts, never while a reserved run executes.
        if runtime_fingerprint(self.frozen['runtime_root']) != self.revision('runtimes', entry['runtime_revision'])['files']:
            assessment['gate_errors'].append('RUNTIME_CHANGED_DURING_RUN')
            assessment['status'] = 'ERROR'
        try:
            verify_frozen_files(self.frozen)
        except ValueError:
            assessment['gate_errors'].append('PROTECTED_INPUT_CHANGED_DURING_RUN')
            assessment['status'] = 'ERROR'
        diagnosis = diagnose_assessment(record, assessment['gate_errors'])
        entry.update(assessment, complete=True, ended_utc=utc_now(),
            diagnosis=diagnosis, reason=record.get('reason') or diagnosis.get('reason'))
        entry['elapsed_seconds'] = max(record.get('duration_ms', 0)/1000,
            (datetime.now(timezone.utc)-datetime.fromisoformat(entry['started_utc'])).total_seconds())
        if entry['diagnosis']['category'] in ('integrity','unknown') and assessment['status'] != 'PASS':
            self.state['stop_reason'] = 'UNRESOLVED_' + entry['diagnosis']['category'].upper()
        self._receipt(entry)
        self._save()

    def recover_pending(self):
        self._owned()
        if not self.state['attempts'] or self.state['attempts'][-1]['complete']:
            return 'NONE'
        entry = self.state['attempts'][-1]
        if process_identity(entry['owner']['pid']) == entry['owner']['birth']:
            return 'LIVE'
        receipt = Path(entry['run_root'])/'outcome.json'
        if receipt.is_file():
            terminal = json.loads(receipt.read_text(encoding='utf-8'))
            if any(terminal.get(k) != entry.get(k) for k in ('attempt_id','started_utc','run_root','version','runtime_revision')):
                raise ValueError('Orphan outcome differs from reservation')
            entry.update(terminal, outcome_sha256=digest(receipt.read_bytes()))
            if entry.get('diagnosis', {}).get('category') in ('integrity','unknown'):
                self.state['stop_reason'] = 'UNRESOLVED_' + entry['diagnosis']['category'].upper()
            self._save()
            self._reload()
            return 'RECOVERED'
        records = list(Path(entry['run_root']).glob('*/run_record.json'))
        if len(records) == 1 and json.loads(records[0].read_text(encoding='utf-8')).get('complete'):
            self.finish(records[0])
        else:
            entry.update(status='ERROR', complete=True, reason='CONFIRMED_INTERRUPTION', ended_utc=utc_now(),
                elapsed_seconds=max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(entry['started_utc'])).total_seconds()))
            self._receipt(entry)
            self._save()
        return 'RECOVERED'
