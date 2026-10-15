"""Durable, bounded V3→V4 acceptance; never mix versions or restart pending work."""
from contextlib import contextmanager
import json
import os
from pathlib import Path

from .evidence import atomic_json, digest
from .executor import utc_now
from .diagnostics import exception_details

CASES = ('single_file_login', 'multi_file_invoice', 'missing_links')
VERSIONS = ('m2-w78-v3', 'm2-w78-v4')


def verify_frozen_files(snapshot):
    for name, expected in snapshot.get('files', {}).items():
        path = Path(name)
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError('Frozen input/code changed: ' + name)


def next_step(history):
    if len(history) > 6:
        raise ValueError('Campaign exceeds six attempts')
    version, index, failures, terminal = VERSIONS[0], 0, 0, None
    for entry in history:
        if terminal or entry['version'] != version or entry['task_id'] != CASES[index]:
            raise ValueError('Invalid campaign history/order')
        status = entry['status']
        if status == 'PASS':
            index += 1
            if index == 3:
                terminal = dict(status='PASS', final_version=version, reason=None, next=None)
        elif status == 'FAIL':
            failures += 1
            if failures >= 2:
                terminal = dict(status='FAIL', final_version=None, reason='FAILURE_LIMIT', next=None)
            else:
                version, index = VERSIONS[1], 0
        elif status == 'ERROR':
            terminal = dict(status='ERROR', final_version=None, reason='RUNTIME_OR_EVIDENCE_ERROR', next=None)
        else:
            raise ValueError('Only terminal attempts can advance campaign')
    if terminal:
        return terminal
    if len(history) >= 6:
        return dict(status='FAIL', final_version=None, reason='ATTEMPT_LIMIT', next=None)
    return dict(status='NOT_RUN', final_version=None, reason=None, next=dict(version=version, task_id=CASES[index]))


def process_identity(pid):
    """Return process birth identity, None only for confirmed absent PID."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error in (87, 1168):
                return None
            raise RuntimeError('Cannot establish pending process identity: ' + str(error))
        try:
            times = [w.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                raise RuntimeError('Cannot read pending process creation time')
            # A zombie/terminated handle has a nonzero exit time and is not live.
            if times[1].dwHighDateTime or times[1].dwLowDateTime:
                return None
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
    except FileNotFoundError:
        return None
    fields = text[text.rfind(')') + 2:].split()
    return None if fields[0] == 'Z' else fields[19]


def assess_record(path):
    """Audit acceptance evidence, not just a trusted top-level PASS string."""
    path = Path(path)
    record = json.loads(path.read_text(encoding='utf-8'))
    errors = []
    caught_exceptions = []
    if not record.get('complete') or record.get('mode') != 'real' or record.get('status') not in ('PASS', 'FAIL', 'ERROR'):
        errors.append('NON_REAL_OR_INCOMPLETE_RECORD')
    status = record.get('status', 'ERROR')
    if status == 'PASS':
        stages, model = record.get('stages', {}), record.get('model', {})
        if model.get('model_id') != 'Qwen/Qwen3-4B-Instruct-2507' or model.get('revision') != 'cdbee75f17c01a7cc42f958dc650907174af0554':
            errors.append('MODEL_PIN_MISMATCH')
        if record.get('original_source_unchanged') is not True:
            errors.append('SOURCE_INTEGRITY')
        for name in ('context', 'prompt', 'generation', 'parse_patch', 'apply', 'baseline', 'verification'):
            if stages.get(name, {}).get('status') != 'PASS':
                errors.append('INCOMPLETE_STAGE:' + name)
        generated, applied = stages.get('generation', {}), stages.get('apply', {})
        if generated.get('mode') != 'real' or generated.get('truncated') is not False:
            errors.append('NON_REAL_OR_TRUNCATED_GENERATION')
        expected = {'single_file_login': ['auth.py'], 'multi_file_invoice': ['invoice.py', 'pricing.py'],
                    'missing_links': ['formatter.py']}.get(record.get('task_id'))
        if applied.get('patch_applied') is not True or sorted(applied.get('changed_files', [])) != expected:
            errors.append('ACTUAL_CHANGED_FILES')
        baseline, verification = stages.get('baseline', {}), stages.get('verification', {})
        selection = stages.get('selection', {})
        tests = verification.get('tests', {})
        required = baseline.get('required_ids', [])
        outcomes = tests.get('outcomes', {})
        if (not required or baseline.get('tests', {}).get('status') != 'FAIL'
                or any(outcomes.get(n) != 'PASS' for n in required)
                or any(outcomes.get(n) != 'PASS' for n,s in baseline.get('tests', {}).get('outcomes', {}).items() if s == 'PASS')):
            errors.append('REQUIRED_OR_REGRESSION')
        if (tests.get('status') != 'PASS' or not tests.get('command', {}).get('complete')
                or tests.get('command', {}).get('exit_code') != 0 or verification.get('collection', {}).get('status') != 'PASS'):
            errors.append('TEST_EXECUTION')
        collection = verification.get('collection', {})
        collected, collected_command = collection.get('node_ids', []), collection.get('command', {})
        if (not collected or not set(required).issubset(collected) or set(outcomes) != set(collected)
                or not collected_command.get('complete') or collected_command.get('exit_code') != 0
                or '--collect-only' not in collected_command.get('argv', [])):
            errors.append('ACTUAL_COLLECTION')
        if not selection.get('selected') or not selection.get('required_selectors'):
            errors.append('TEST_SELECTION')
        if record.get('task_id') == 'missing_links' and (
                selection.get('fallback_required') is not True or not selection.get('fallback_scope')
                or not set(selection['fallback_scope']).issubset(selection.get('selected', []))
                or 'unlinked' not in selection.get('reasons', [])):
            errors.append('MISSING_LINKS_FALLBACK')
        if any(verification.get('static', {}).get(n, {}).get('status') != 'PASS' for n in ('syntax', 'mypy', 'ruff')):
            errors.append('STATIC_CHECKS')
        try:
            files = {}
            for key in ('applied', 'bundle'):
                file = (path.parent / record['artifacts'][key]).resolve()
                if file.parent != path.parent.resolve() or file.is_symlink() or not file.read_bytes():
                    raise ValueError('Invalid delivered artifact')
                files[key] = file
            bundle = json.loads(files['bundle'].read_text(encoding='utf-8'))
            exports = [c for c in applied.get('commands', []) if c.get('argv', [])[:2] == ['git', 'diff']]
            if (len(exports) != 1 or exports[0].get('status') != 'PASS' or not exports[0].get('complete')
                    or exports[0].get('output_truncated') or exports[0].get('timed_out')
                    or files['applied'].read_bytes() != exports[0].get('stdout', '').encode('utf-8')):
                errors.append('APPLIED_EXPORT_BINDING')
            if bundle['metadata']['canonical_sha256'] != digest(path.read_bytes()):
                errors.append('BUNDLE_HASH')
            public = bundle['verification']
            if (public.get('patch_applied') is not True or any(public[n]['status'] != 'PASS' for n in ('tests', 'typecheck', 'lint'))
                    or bundle['source_hash_before'] != bundle['source_hash_after']):
                errors.append('PUBLIC_VERIFICATION')
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append('ARTIFACT_MISSING_OR_INVALID')
            caught_exceptions.append(exception_details(error))
    return dict(status='ERROR' if errors else status, gate_errors=errors, observed_status=status,
                exception_diagnostics=caught_exceptions,
                record=str(path.resolve()), canonical_sha256=digest(path.read_bytes()))


class CampaignStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / 'campaign.json'
        self.locked = False
        self.state = {}

    @classmethod
    def create(cls, directory, snapshot):
        store = cls(directory)
        store.directory.mkdir(parents=True, exist_ok=False)
        frozen = store.directory / 'frozen_inputs.json'
        atomic_json(frozen, snapshot)
        store.state = dict(campaign_id=store.directory.name, status='NOT_RUN', complete=False,
            started_utc=utc_now(), ended_utc=None, max_attempts=6, max_failures=2,
            frozen_sha256=digest(frozen.read_bytes()), attempts=[], final_version=None)
        atomic_json(store.path, store.state)
        return store

    @classmethod
    def open(cls, directory):
        store = cls(directory)
        store._reload()
        return store

    def _reload(self):
        self.state = json.loads(self.path.read_text(encoding='utf-8'))
        if digest((self.directory / 'frozen_inputs.json').read_bytes()) != self.state['frozen_sha256']:
            raise ValueError('Frozen snapshot changed')
        if self.state['max_attempts'] != 6 or self.state['max_failures'] != 2:
            raise ValueError('Frozen campaign limits changed')
        frozen = json.loads((self.directory / 'frozen_inputs.json').read_text(encoding='utf-8'))
        verify_frozen_files(frozen)
        pending = False
        for number, entry in enumerate(self.state['attempts'], 1):
            if pending or entry['number'] != number or entry['attempt_id'] != f'attempt-{number:02}':
                raise ValueError('Historical ledger order changed')
            if not entry['complete']:
                pending = True
                if entry['status'] != 'NOT_RUN':
                    raise ValueError('Pending ledger outcome changed')
            elif entry.get('record'):
                assessment = self._assess_entry(entry, entry['record'], frozen)
                if any(entry.get(key) != assessment[key] for key in ('status','observed_status','canonical_sha256','gate_errors')):
                    raise ValueError('Historical ledger differs from canonical assessment')
            elif entry.get('status') != 'ERROR' or entry.get('reason') != 'CONFIRMED_INTERRUPTION':
                raise ValueError('Historical terminal ledger lacks canonical evidence')
        step = self.decision()
        if any(self.state.get(k) != step[k] for k in ('status','final_version')) or self.state['complete'] != (step['next'] is None):
            raise ValueError('Historical derived campaign state changed')

    @contextmanager
    def session(self):
        stream = (self.directory / '.owner.lock').open('a+b')
        try:
            if not stream.tell():
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError('Campaign locked by another owner') from error
            self.locked = True
            self._reload()
            yield self
        finally:
            if self.locked:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                self.locked = False
            stream.close()

    def _owned(self):
        if not self.locked:
            raise RuntimeError('Campaign mutation requires exclusive owner session')

    def decision(self):
        return next_step([e for e in self.state['attempts'] if e['complete']])

    def reserve(self):
        self._owned()
        verify_frozen_files(json.loads((self.directory / 'frozen_inputs.json').read_text(encoding='utf-8')))
        if any(not e['complete'] for e in self.state['attempts']):
            raise RuntimeError('Pending attempt must be reconciled, never restarted')
        step = self.decision()
        if step['next'] is None:
            raise RuntimeError('Campaign is terminal; no further generation allowed')
        number = len(self.state['attempts']) + 1
        entry = dict(**step['next'], number=number, attempt_id=f'attempt-{number:02}',
            status='NOT_RUN', complete=False, started_utc=utc_now(), ended_utc=None,
            owner={'pid': os.getpid(), 'birth': process_identity(os.getpid())},
            run_root=str(self.directory / 'attempts' / f'{number:02}'), record=None)
        Path(entry['run_root']).mkdir(parents=True, exist_ok=False)
        self.state['attempts'].append(entry)
        atomic_json(self.path, self.state)
        return entry

    def _commit(self, entry, assessment):
        entry.update(assessment, complete=True, ended_utc=utc_now())
        step = self.decision()
        self.state.update(status=step['status'], complete=step['next'] is None, final_version=step['final_version'], reason=step['reason'])
        if self.state['complete']:
            self.state['ended_utc'] = utc_now()
        atomic_json(self.path, self.state)

    def _assess_entry(self, entry, path, frozen):
        path = Path(path).resolve()
        if Path(entry['run_root']).resolve() not in path.parents or path.name != 'run_record.json':
            raise ValueError('Canonical path outside reserved attempt')
        record = json.loads(path.read_text(encoding='utf-8'))
        if (record.get('campaign_id') != self.state['campaign_id'] or record.get('attempt_id') != entry['attempt_id']
                or record.get('task_id') != entry['task_id'] or record.get('policy', {}).get('prompt_version') != entry['version']):
            raise ValueError('Canonical identity differs from reserved attempt')
        assessment = assess_record(path)
        if 'model' in frozen and record.get('model') != frozen['model']:
            assessment['gate_errors'].append('FROZEN_MODEL_CONFIG_MISMATCH')
        if record['status'] == 'PASS' and 'templates' in frozen and record.get('stages', {}).get('prompt', {}).get('template_hash') != frozen['templates'][entry['version']]:
            assessment['gate_errors'].append('FROZEN_TEMPLATE_MISMATCH')
        if 'tasks' in frozen and record.get('task') != frozen['tasks'][entry['task_id']]['task']:
            assessment['gate_errors'].append('FROZEN_TASK_MISMATCH')
        if assessment['gate_errors']:
            assessment['status'] = 'ERROR'
        return assessment

    def finish(self, path):
        self._owned()
        entry = self.state['attempts'][-1]
        if entry['complete']:
            raise ValueError('Attempt already finalized')
        frozen = json.loads((self.directory / 'frozen_inputs.json').read_text(encoding='utf-8'))
        assessment = self._assess_entry(entry, path, frozen)
        self._commit(entry, assessment)

    def recover_pending(self):
        self._owned()
        if not self.state['attempts'] or self.state['attempts'][-1]['complete']:
            return 'NONE'
        entry = self.state['attempts'][-1]
        identity = process_identity(entry['owner']['pid'])
        if identity is not None and identity == entry['owner']['birth']:
            return 'LIVE'
        candidates = list(Path(entry['run_root']).glob('*/run_record.json'))
        if len(candidates) == 1:
            record = json.loads(candidates[0].read_text(encoding='utf-8'))
            if record.get('complete'):
                self.finish(candidates[0])
                return 'RECOVERED'
        self._commit(entry, dict(status='ERROR', reason='CONFIRMED_INTERRUPTION', gate_errors=['NO_UNIQUE_TERMINAL_RECORD']))
        return 'RECOVERED'
