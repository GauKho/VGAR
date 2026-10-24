"""Local trusted test data: real pytest/mypy/Ruff, no M1 bundle or model needed."""
import json
import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair.contracts import RepairPolicy
from vgar.repair.evidence import atomic_json
from vgar.repair.executor import NativeExecutor
from vgar.repair.patch import PatchPolicy, apply_patch, parse_unified_diff
from vgar.repair.policy import load_variant
from vgar.repair.verification import capture_baseline, verify_patch
from vgar.repair.workspace import create_workspace, inventory

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests/fixtures/m2_w9/static_debt'


@pytest.mark.parametrize(('name', 'new_error', 'expected'), [
    ('A2', False, 'PASS'), ('A0', True, 'PASS'), ('A2', True, 'FAIL'),
])
def test_real_tools_distinguish_existing_debt_and_new_debt(tmp_path, name, new_error, expected):
    source = tmp_path / 'source'
    shutil.copytree(FIXTURE, source)
    original = inventory(source)
    variant = load_variant(ROOT / 'configs/m2/variants' / (name + '.json'))
    task = SimpleNamespace(allowed_source_paths=('app.py',), fallback_scope=('tests',),
        failing_selectors=('tests/test_app.py::test_required',))
    before, after, applied = None, None, None
    try:
        with create_workspace(source, tmp_path / 'private') as lease:
            private = lease.private
            executor, policy = NativeExecutor(lease), RepairPolicy()
            before = capture_baseline(task, lease, executor, policy, variant=variant)
            assert before['status'] == 'PASS', json.dumps(before, ensure_ascii=False)
            assert before['static']['mypy']['report']['execution_status'] == 'COMPLETE'
            assert before['static']['mypy']['report']['diagnostics']
            body = (' def answer() -> int:\n-    return 1\n+    return 2\n' +
                    ('+\n+\n+def new_debt() -> int:\n+    return "new debt"\n' if new_error else ''))
            patch = '--- a/app.py\n+++ b/app.py\n@@ -5,2 +5,' + ('6' if new_error else '2') + ' @@\n' + body
            applied = apply_patch(lease, parse_unified_diff(patch, PatchPolicy(('app.py',), ('tests',))), executor)
            assert applied.status == 'PASS', applied
            selection = {'selected': ('tests',), 'related_selectors': ()}
            after = verify_patch(task, lease, applied, before, selection, executor, policy, variant=variant)
            assert after['tests']['status'] == 'PASS'
            assert after['status'] == expected, json.dumps(after, ensure_ascii=False)
            assert after['policy_checks']['mypy']['status'] == ('FAIL' if new_error else 'PASS')
        assert not private.exists()
        assert inventory(source) == original
    finally:
        # Optional local recorder output; normal pytest still owns only tmp_path.
        destination = Path(os.environ['VGAR_W9_EVIDENCE_ROOT']) if os.environ.get('VGAR_W9_EVIDENCE_ROOT') else tmp_path
        atomic_json(destination / 'native' / (name + '-' + str(new_error) + '-' + uuid.uuid4().hex + '.json'),
                    {'variant': name, 'new_error': new_error, 'expected': expected,
                     'baseline': before, 'apply': applied.model_dump() if applied else None,
                     'verification': after, 'original_source_unchanged': inventory(source) == original})
