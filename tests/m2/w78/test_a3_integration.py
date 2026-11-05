"""A2/A3 use one generation and real trusted-fixture execution, never a model."""
import json
from pathlib import Path

import pytest

from vgar.models.generator import FakeGenerator
from vgar.repair.contracts import RepairPolicy
from vgar.repair.evidence import digest
from vgar.repair.pipeline import run_repair
from vgar.repair.workspace import inventory
from w78_support import CharacterChatTokenizer

ROOT = Path(__file__).resolve().parents[3]
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
API_BREAK = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n-def login(value):\n-    return bool(value)\n+def login(value, /):\n+    return bool(value.strip())\n'
DYNAMIC_EXPORT = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,3 @@\n+__all__ = [name for name in ("login",)]\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


class CountingGenerator(FakeGenerator):
    def __init__(self, patch):
        super().__init__(patch)
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return super().generate(*args, **kwargs)


@pytest.mark.parametrize('name', ['A2', 'A3'])
@pytest.mark.parametrize('patch,api_status,a3_status,reason', [
    (FIX, 'PASS', 'PASS', None),
    (API_BREAK, 'FAIL', 'FAIL', 'API_BREAK'),
    (DYNAMIC_EXPORT, 'NOT_RUN', 'ERROR', 'VERIFICATION_INCOMPLETE'),
])
def test_a3_changes_only_required_verification_with_one_generation(
        m1_case, tmp_path, name, patch, api_status, a3_status, reason):
    task, counter = m1_case
    before = inventory(task.source_repo)
    path = ROOT / 'configs/m2/variants' / ('A3.json' if name == 'A3' else 'w10/A2.json')
    definition = json.loads(path.read_bytes())
    generator = CountingGenerator(patch)
    run = run_repair(task, RepairPolicy(), generator, None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp',
        experiment={'variant_policy': definition, 'arm': 'graph'})
    wanted = a3_status if name == 'A3' else 'PASS'
    assert run.record['status'] == wanted, run.record.get('error_detail')
    assert generator.calls == 1
    assert run.record['stages']['generation']['status'] == 'PASS'
    assert run.record['experiment']['variant_id'] == name
    assert run.record['experiment']['variant_policy']['patch_mode'] == 'normalized'
    assert run.record['experiment']['variant_policy']['path_listing'] == 'context'
    assert run.record['stages']['verification']['tests']['status'] == 'PASS'
    assert run.record['stages']['baseline']['variant_policy_hash'] == run.record['experiment']['policy_hash']
    assert run.record['original_source_unchanged'] is True
    assert inventory(task.source_repo) == before
    bundle = json.loads((run.directory / 'evidence_bundle.json').read_bytes())
    assert bundle['recommendation'] == {'PASS': 'ACCEPT', 'FAIL': 'REVISE', 'ERROR': 'REJECT'}[wanted]
    assert bundle['metadata']['canonical_sha256'] == digest(run.path.read_bytes())
    assert bundle['metadata']['experiment'] == run.record['experiment']
    if name == 'A3' and reason:
        assert reason in [r['code'] for r in bundle['verification']['reasons']]
    for check, expected in [('api', api_status), ('structural', 'PASS')]:
        dto = bundle['verification'][check + '_check']
        assert dto['status'] == expected
        detail = run.directory / dto['details_ref']
        assert json.loads(detail.read_bytes())['status'] == expected
        assert digest(detail.read_bytes()) == run.record['stages']['verification']['compatibility_hashes'][check]
