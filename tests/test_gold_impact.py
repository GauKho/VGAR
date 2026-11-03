"""I1 (M1-X2, RQ3): graph impact vs a diff-only baseline on gold patches."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.evaluation.gold_impact import (
    TestKey,
    diff_only_tests,
    evaluate_task,
    filter_patch,
    match_tests,
    parse_f2p,
    patch_files,
    render_i1,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]


def _test_node(path, qualified_name):
    return {'id': f'test:{path}:{qualified_name}', 'type': 'Test', 'path': path,
            'qualified_name': qualified_name, 'name': qualified_name.rsplit('.', 1)[-1]}


@pytest.mark.parametrize('raw,key', [
    ('tests/test_x.py::TestC::test_m[1-2]', TestKey('tests/test_x.py', 'TestC', 'test_m')),
    ('tests/test_x.py::test_top', TestKey('tests/test_x.py', None, 'test_top')),
    ('test_m (app.tests.TestC)', TestKey('app/tests', 'TestC', 'test_m')),
    ('test_m', TestKey(None, None, 'test_m')),
])
def test_parse_f2p(raw, key):
    assert parse_f2p(raw) == key


@pytest.mark.parametrize('raw', ['', 'not a test name', 'a.b.c'])
def test_parse_f2p_unknown_format(raw):
    assert parse_f2p(raw) is None


def test_match_by_path_class_and_name():
    nodes = [_test_node('tests/test_x.py', 'test_x.TestC.test_m'), _test_node('tests/test_y.py', 'test_y.test_m')]
    assert match_tests([TestKey('tests/test_x.py', 'TestC', 'test_m')], nodes, set()) == {0: {nodes[0]['id']}}


def test_match_class_with_source_root_prefixed_qualified_name():
    nodes = [_test_node('tests/test_x.py', 'tests.test_x.TestC.test_m'), _test_node('tests/test_x.py', 'tests.test_x.test_m')]
    assert match_tests([TestKey('tests/test_x.py', 'TestC', 'test_m')], nodes, set()) == {0: {nodes[0]['id']}}
    assert match_tests([TestKey('tests/test_x.py', None, 'test_m')], nodes, set()) == {0: {nodes[1]['id']}}


def test_django_module_matches_file_or_package():
    nodes = [_test_node('app/tests.py', 'app.tests.TestC.test_m'),
             _test_node('app/tests/test_a.py', 'app.tests.test_a.TestC.test_m')]
    assert match_tests([TestKey('app/tests', 'TestC', 'test_m')], nodes, set()) == {0: {nodes[0]['id']}}


def test_django_module_relative_to_tests_dir():
    nodes = [_test_node('tests/model_fields/test_x.py', 'model_fields.test_x.TestC.test_m')]
    assert match_tests([TestKey('model_fields/test_x', 'TestC', 'test_m')], nodes, set()) == {0: {nodes[0]['id']}}


def test_bare_name_restricted_to_test_patch_files():
    nodes = [_test_node('sympy/a/tests/test_a.py', 'test_a.test_m'), _test_node('sympy/b/tests/test_b.py', 'test_b.test_m')]
    assert match_tests([TestKey(None, None, 'test_m')], nodes, {'sympy/b/tests/test_b.py'}) == {0: {nodes[1]['id']}}


def test_unmatched_key_is_absent():
    nodes = [_test_node('tests/test_x.py', 'test_x.test_m')]
    assert match_tests([TestKey('tests/test_x.py', None, 'test_other')], nodes, set()) == {}


# ---- per-task evaluation (Task 5) ----

FIXTURE = Path(__file__).parent / 'fixtures/m1_w10_impact'
GOLD = ('diff --git a/pkg/core.py b/pkg/core.py\n--- a/pkg/core.py\n+++ b/pkg/core.py\n'
        '@@ -11 +11 @@\n-    return x + 1\n+    return x + 2\n'
        'diff --git a/pkg/new.py b/pkg/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/pkg/new.py\n'
        '@@ -0,0 +1 @@\n+X = 1\n'
        'diff --git a/tests/test_core.py b/tests/test_core.py\n--- a/tests/test_core.py\n+++ b/tests/test_core.py\n'
        '@@ -5 +5 @@\n-    assert helper(1) == 2\n+    assert helper(1) == 3\n')
TEST_PATCH = ('diff --git a/tests/test_core.py b/tests/test_core.py\n--- a/tests/test_core.py\n+++ b/tests/test_core.py\n'
              '@@ -5,0 +6,4 @@\n+\n+\n+def test_added_by_patch():\n+    assert True\n')
ROW = {'patch': GOLD, 'test_patch': TEST_PATCH,
       'FAIL_TO_PASS': ['tests/test_core.py::test_helper', 'tests/test_core.py::test_added_by_patch']}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    shutil.copytree(FIXTURE, root)
    return root


def test_filter_patch_drops_files_outside_kept_set():
    diff, dropped = filter_patch(GOLD, {'pkg/core.py', 'pkg/api.py', 'pkg/__init__.py'})
    assert dropped == ['pkg/new.py', 'tests/test_core.py']
    assert '+++ b/pkg/core.py' in diff and 'pkg/new.py' not in diff and 'tests/test_core.py' not in diff


def test_patch_files_reads_new_and_deleted_files():
    deleted = 'diff --git a/pkg/old.py b/pkg/old.py\ndeleted file mode 100644\n--- a/pkg/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-X = 1\n'
    assert patch_files(GOLD + deleted) == ['pkg/core.py', 'pkg/new.py', 'tests/test_core.py', 'pkg/old.py']


def test_diff_only_tests_use_module_named_test_files():
    nodes = [_test_node('tests/test_core.py', 'tests.test_core.test_helper'),
             _test_node('tests/core_test.py', 'tests.core_test.test_x'), _test_node('tests/test_api.py', 'tests.test_api.test_y')]
    assert diff_only_tests(['pkg/core.py'], nodes) == {nodes[0]['id'], nodes[1]['id']}


def test_evaluate_task_counts_only_baseline_f2p(repo):
    out = evaluate_task('demo__w10-1', repo, ['pkg'], ROW)
    assert out['status'] == 'OK', out.get('reason')
    assert out['f2p_total'] == 2 and out['f2p_measurable'] == 1 and out['f2p_unmatched'] == 1
    assert out['graph']['f2p_hit'] == 1 and out['diff_only']['f2p_hit'] == 1
    assert out['graph']['test_patch_files_hit'] == 1 and out['test_patch_files'] == 1
    assert out['dropped_files'] == ['pkg/new.py', 'tests/test_core.py']


def test_evaluate_task_error_stays_in_denominator(repo):
    out = evaluate_task('demo__w10-1', repo, ['pkg'], ROW | {'patch': 'diff --git a/pkg/core.py b/pkg/core.py\n'
                        '--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -99 +99 @@\n-nope\n+nope2\n'})
    assert out['status'] == 'ERROR' and out['reason']


def test_evaluate_task_without_source_change(repo):
    out = evaluate_task('demo__w10-1', repo, ['pkg'], ROW | {'patch': TEST_PATCH})
    assert out['status'] == 'NO_SOURCE_CHANGE'


def _row(measurable, graph_hit=0, diff_hit=0):
    method = lambda hit: {'f2p_hit': hit, 'region_tests': 3, 'region_nodes': 5, 'test_patch_files_hit': 1}
    return {'status': 'OK', 'f2p_total': measurable, 'f2p_measurable': measurable, 'f2p_unmatched': 0,
            'test_patch_files': 1, 'graph': method(graph_hit), 'diff_only': method(diff_hit)}


def test_summary_micro_recall_and_na():
    rows = [_row(2, graph_hit=1), _row(0), {'status': 'ERROR', 'reason': 'x'}]
    summary = summarize(rows)
    assert summary['n_tasks'] == 3 and summary['n_error'] == 1 and summary['n_no_measurable_f2p'] == 1
    assert summary['graph']['recall_micro'] == 0.5 and summary['diff_only']['recall_micro'] == 0.0
    assert summary['graph']['median_region_tests'] == 3


def test_render_i1_is_pure_function_of_summary():
    summary = summarize([_row(2, graph_hit=1)])
    markdown = render_i1(summary)
    assert markdown.splitlines()[0].startswith('| Phương pháp | N task | F2P đo được | Recall F2P trong vùng')
    assert render_i1(json.loads(json.dumps(summary))) == markdown


def test_cli_refuses_heldout_manifest(tmp_path):
    task = {'instance_id': 'astropy__astropy-12907', 'split': 'heldout'}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'split': 'heldout', 'tasks': [task]}), encoding='utf-8')
    process = subprocess.run([sys.executable, 'scripts/measure_patch_impact.py', '--manifest', str(manifest),
                              '--data-root', str(tmp_path), '--parquet', str(tmp_path / 'x.parquet'),
                              '--task-inputs', str(tmp_path), '--out', str(tmp_path / 'out')],
                             cwd=ROOT, capture_output=True, text=True)
    assert process.returncode != 0 and 'allowed' in process.stderr
    assert not (tmp_path / 'out').exists()
