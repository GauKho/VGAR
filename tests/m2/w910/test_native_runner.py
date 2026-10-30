"""Native Django/sympy runner adapter: real captured logs, Python 3.5 source, pytest report contract."""
import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT/'tests/fixtures/m2/native_runner'
SOURCE = ROOT/'src/vgar/repair/native_runner.py'
REPRO = 'tests/vgar_repro/tests.py::Repro::'


def nr():
    from vgar.repair import native_runner
    return native_runner


def read(name):
    return (LOGS/name).read_text(encoding='utf-8')


def test_django_label():
    assert nr().django_label('tests/vgar_repro/tests.py::Repro::test_x') == 'vgar_repro.tests.Repro.test_x'
    assert nr().django_label('tests/vgar_repro/tests.py::Repro') == 'vgar_repro.tests.Repro'
    assert nr().django_label('tests/vgar_repro/tests.py') == 'vgar_repro.tests'
    with pytest.raises(ValueError):
        nr().django_label('django/db/models.py')


def test_sympy_file():
    assert nr().sympy_file('sympy/a/tests/test_r.py::test_x') == 'sympy/a/tests/test_r.py'
    with pytest.raises(ValueError):
        nr().sympy_file('sympy/a/tests/test_r.py::C::test_x')


# Django 1.11 (py3.5, result lines interleaved with migration output), 3.0 (py3.6), 4.1 (py3.9), 5.0 (py3.11 qualname format).
@pytest.mark.parametrize('log', ['django111_runtests.log', 'django_runtests.log', 'django41_runtests.log', 'django50_runtests.log'])
def test_parse_django_all_families(log):
    outcomes, errors = nr().parse_django(read(log))
    assert outcomes == {REPRO+'test_doc': 'PASS', REPRO+'test_fail': 'FAIL', REPRO+'test_pass': 'PASS'}
    assert errors == []


@pytest.mark.parametrize('suffix', ['', '.vgar_repro.tests'])
def test_parse_django_import_error_is_collection_error(suffix):
    log = ('vgar_repro.tests (unittest.loader._FailedTest%s) ... ERROR\n\n'
           'ImportError: Failed to import test module: vgar_repro.tests\n' % suffix)
    outcomes, errors = nr().parse_django(log)
    assert outcomes == {} and errors


@pytest.mark.parametrize('log', ['sympy_bin_test.log', 'sympy11_bin_test.log'])
def test_parse_sympy_logs(log):
    outcomes, errors = nr().parse_sympy(read(log))
    path = 'sympy/vgar_repro/tests/test_repro.py::'
    assert outcomes == {path+'test_fail': 'FAIL', path+'test_pass': 'PASS'}
    assert errors == []


def test_parse_sympy_import_failure_is_collection_error():
    outcomes, errors = nr().parse_sympy('sympy/vgar_repro/tests/test_repro.py[?]   Failed to import          [FAIL]\n')
    assert outcomes == {} and errors


def test_source_is_python35_compatible():
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source, feature_version=(3, 5))
    assert not any(isinstance(n, ast.JoinedStr) for n in ast.walk(tree)), 'f-strings need Python 3.6'
    assert not any(isinstance(n, ast.AnnAssign) for n in ast.walk(tree)), 'variable annotations need Python 3.6'
    assert not any(isinstance(n, ast.FunctionDef) and (n.returns or any(a.annotation for a in n.args.args))
                   for n in ast.walk(tree))
    assert 'capture_output' not in source and 'text=True' not in source  # Python 3.7 subprocess keywords


def test_source_stdlib_api_targets_python35():
    pytest.importorskip('vermin')  # optional; the real gate is the Django 1.11 (Python 3.5) image run
    result = subprocess.run([sys.executable, '-m', 'vermin', '--target=3.5-', '--no-tips', '--violations', str(SOURCE)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout.decode()


FAKE_RUNTESTS = '''import sys
labels = sys.argv[1:]
sys.stderr.write("Creating test database...")
for name, result in (("test_pass", "ok"), ("test_fail", "FAIL")):
    if any(label in ("vgar_repro.tests", "vgar_repro.tests.Repro." + name) for label in labels):
        sys.stderr.write("%s (vgar_repro.tests.Repro) ... %s\\n" % (name, result))
sys.exit(1 if any(l in ("vgar_repro.tests", "vgar_repro.tests.Repro.test_fail") for l in labels) else 0)
'''


def run_native(tmp_path, selectors, collect=False):
    (tmp_path/'fake_runtests.py').write_text(FAKE_RUNTESTS, encoding='utf-8')
    report, junit = tmp_path/'out/nodeids.json', tmp_path/'out/junit.xml'
    command = {'env': {'VGAR_FAKE': '1'}, 'argv': ['fake_runtests.py']}
    argv = [sys.executable, str(SOURCE), '--runner', 'django_runtests', '--command-json', json.dumps(command),
            '--report', str(report), '--junit', str(junit), *(['--collect-only'] if collect else []), *selectors]
    process = subprocess.run(argv, cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process, json.loads(report.read_text(encoding='utf-8')), junit


def test_report_matches_pytest_plugin_contract(tmp_path):
    from vgar.repair import pytest_plugin
    process, data, junit = run_native(tmp_path, ['tests/vgar_repro/tests.py'])
    assert set(data) == set(pytest_plugin.STATE) | {'exit_code'}
    assert data['complete'] is True and data['collection_errors'] == []
    assert data['node_ids'] == [REPRO+'test_fail', REPRO+'test_pass']
    assert data['outcomes'] == {REPRO+'test_fail': 'FAIL', REPRO+'test_pass': 'PASS'}
    assert process.returncode == 1 and data['exit_code'] == 1
    ET.fromstring(junit.read_text(encoding='utf-8'))
    assert b'test_fail (vgar_repro.tests.Repro) ... FAIL' in process.stdout  # raw runner output stays as evidence


def test_selected_passing_test_exits_zero(tmp_path):
    process, data, _ = run_native(tmp_path, [REPRO+'test_pass'])
    assert data['outcomes'] == {REPRO+'test_pass': 'PASS'} and process.returncode == 0


def test_collect_only_exits_zero_when_tests_found(tmp_path):
    process, data, _ = run_native(tmp_path, ['tests/vgar_repro/tests.py'], collect=True)
    assert process.returncode == 0 and data['node_ids']


def test_no_tests_found_is_error_exit(tmp_path):
    process, data, _ = run_native(tmp_path, ['tests/other_app/tests.py'])
    assert process.returncode == 2 and data['node_ids'] == []
