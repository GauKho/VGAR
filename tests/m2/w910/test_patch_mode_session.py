"""patch_mode='normalized' inside the real fake-generation pipeline; strict mode is unchanged."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# Header counts are wrong (strict parse fails) but the context is exact and unique.
BAD_HEADER_FIX = ('--- a/auth.py\n+++ b/auth.py\n@@ -9,9 +9,9 @@\n def login(value):\n'
                  '-    return bool(value)\n+    return bool(value.strip())\n')
NOOP = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value)\n'
FABRICATED = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def logout(value):\n-    return None\n+    return 0\n'


def run(w9_case, tmp_path, raw, variant_dir='w10'):
    from vgar.models.generator import FakeGenerator
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.pipeline import run_repair
    task, count, tokenizer = w9_case
    definition = json.loads((ROOT/'configs/m2/variants'/variant_dir/'A0.json').read_text())
    handle = run_repair(task, RepairPolicy(), FakeGenerator(raw), None, tmp_path/'runs', m1_counter=count,
                        tokenizer=tokenizer, temp_root=tmp_path/'temp',
                        experiment={'variant_policy': definition, 'arm': 'bm25'})
    return json.loads(handle.path.read_text()), handle.directory


def test_normalized_fixes_bad_header_and_records_strict_probe(w9_case, tmp_path):
    record, directory = run(w9_case, tmp_path, BAD_HEADER_FIX)
    pn = record['stages']['parse_patch']['patch_normalization']
    assert pn['mode'] == 'normalized' and pn['strict_parse_ok'] is False and pn['strict_apply_ok'] is False
    assert pn['hunks_total'] == 1 and pn['hunks_relocated'] == 1 and pn['hunks_noop_dropped'] == 0
    assert pn['normalized_diff_sha256'].startswith('sha256:')
    assert record['stages']['apply']['status'] == 'PASS'
    assert record['status'] == 'PASS', record.get('error_detail')
    assert (directory/'normalized.diff').is_file() and (directory/'candidate.diff').read_text() == BAD_HEADER_FIX


def test_noop_candidate_fails_with_no_op_code(w9_case, tmp_path):
    record, _ = run(w9_case, tmp_path, NOOP)
    assert (record['status'], record['reason']) == ('FAIL', 'NO_OP')
    stage = record['stages']['parse_patch']
    assert stage['status'] == 'FAIL' and stage['error']['code'] == 'NO_OP'
    assert stage['patch_normalization']['hunks_noop_dropped'] == 1
    assert record['stages']['apply']['status'] == 'NOT_RUN'


def test_fabricated_context_is_not_rescued(w9_case, tmp_path):
    record, _ = run(w9_case, tmp_path, FABRICATED)
    assert (record['status'], record['reason']) == ('FAIL', 'CONTEXT_NOT_FOUND')
    assert record['stages']['parse_patch']['patch_normalization']['strict_parse_ok'] is True


def test_strict_mode_unchanged(w9_case, tmp_path):
    record, directory = run(w9_case, tmp_path, BAD_HEADER_FIX, variant_dir='.')
    assert (record['status'], record['reason']) == ('FAIL', 'PATCH_PARSE_ERROR')
    assert 'patch_normalization' not in record['stages']['parse_patch']
    assert not (directory/'normalized.diff').exists()


def test_file_level_rule_violation_keeps_parse_patch_evidence(w9_case, tmp_path):
    protected = '--- a/tests/test_auth.py\n+++ b/tests/test_auth.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n'
    record, directory = run(w9_case, tmp_path, protected)
    assert (record['status'], record['reason']) == ('FAIL', 'PATCH_PARSE_ERROR')
    stage = record['stages']['parse_patch']
    assert stage['status'] == 'FAIL' and stage['error']['code'] == 'PATCH_PARSE_ERROR'
    assert stage['patch_normalization']['strict_parse_ok'] is False
    assert (directory/'candidate.diff').read_text() == protected
    assert record['failure']['stage'] == 'parse_patch'
