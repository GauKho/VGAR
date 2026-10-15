"""Read-only scoped closeout checks; writes only its own audit evidence."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from vgar_m2_w78.b_experiment import BExperimentStore, runtime_fingerprint
from vgar_m2_w78.b_acceptance import audit_b_pass
from vgar_m2_w78.campaign import assess_record
from vgar_m2_w78.contracts import RepairTask
from vgar_m2_w78.evidence import begin_run
from vgar_m2_w78.executor import run_bounded
from vgar_m2_w78.pipeline import require_trusted_fixture

run = begin_run(ROOT/'results/b-repair-preflight/20261015-evidence-driven/closeout', 'b-closeout-audit', mode='offline')
try:
    store = BExperimentStore.open(ROOT/'results/b_repair/2026-10-15-evidence-driven-b')
    entries = store.state['attempts']
    assert store.decision()['status'] == 'PASS' and store.decision()['next'] is None
    assert len(entries) == 2 and all(a['complete'] for a in entries)
    assert [a['status'] for a in entries] == ['FAIL', 'PASS']
    assert sum(a['elapsed_seconds'] for a in entries) < 14400
    assert runtime_fingerprint(ROOT) == store.revision('runtimes', entries[-1]['runtime_revision'])['files']
    require_trusted_fixture(RepairTask.model_validate(store.frozen['task']))
    accepted = Path(entries[-1]['record'])
    assessment = assess_record(accepted)
    errors = audit_b_pass(accepted, store.frozen, entries[-1])
    assert assessment['status'] == 'PASS' and not assessment['gate_errors'] and not errors
    record = json.loads(accepted.read_text(encoding='utf-8'))
    raw = (accepted.parent/record['artifacts']['raw_output']).read_bytes()
    assert raw == (accepted.parent/record['artifacts']['candidate']).read_bytes()
    run.stage('canonical_and_b_audit', dict(status='PASS', canonical=str(accepted),
        assessment=assessment, additional_gate_errors=errors, attempts=len(entries),
        elapsed_seconds=sum(a['elapsed_seconds'] for a in entries), host_corrected_raw=False))
    baseline = ROOT/'results/b-repair-preflight/20261015-evidence-driven/baseline'
    allowed = {'PROGRESS.md', 'scripts/record_tests.py', 'src/vgar_m2_w78/generator_hf.py',
        'src/vgar_m2_w78/hf_backend.py', 'src/vgar_m2_w78/context_presentation.py',
        'src/vgar_m2_w78/prompt.py', 'src/vgar_m2_w78/pipeline.py'}
    originals = [p for p in baseline.rglob('*') if p.is_file()]
    changed = {p.relative_to(baseline).as_posix() for p in originals
               if p.read_bytes() != (ROOT/p.relative_to(baseline)).read_bytes()}
    assert changed == allowed, changed
    run.stage('scope', dict(status='PASS', baseline_files=len(originals),
        modified_existing=sorted(changed), frozen_protected_files=len(store.frozen['files']),
        claims_excluded=['A/C acceptance', 'independent repeat', 'SWE-bench', 'full weight attestation']))
    lint = run_bounded((sys.executable,'-m','ruff','check','--select','E9,F','src','scripts','tests'),ROOT,30)
    run.stage('ruff', lint)
    assert lint['status'] == 'PASS'
    run.finish('PASS', reason=None)
except BaseException as error:
    from vgar_m2_w78.diagnostics import exception_details
    run.finish('ERROR', **exception_details(error))
    print(run.path)
    raise
print(run.path)
