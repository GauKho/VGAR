"""M3-W12-2: held-out opens only after the protocol-freeze tag, with an unchanged freeze file (spec §4.4)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.evaluation import heldout_gate
from vgar.evaluation.heldout_gate import (
    ACCESS_LOG,
    FREEZE_FILE,
    assert_heldout_unlocked,
    freeze_sha256,
    latest_freeze_tag,
)
from vgar.evaluation.retrieval import dataset

ROOT = Path(__file__).resolve().parents[1]
HELD_ID, DEV_ID = 't-1', 't-2'   # split_of: t-1 heldout, t-2 dev (tests/m2/test_dataset_split.py)


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@t', '-c', 'user.name=t', *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'docs').mkdir(parents=True)
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'core.autocrlf', 'false')
    (repo / FREEZE_FILE).write_bytes(b'# Protocol\n\nmetric: F3\n')   # LF on every OS
    _git(repo, 'add', '.')
    _git(repo, 'commit', '-qm', 'freeze')
    return repo


def _tag(repo, name):
    _git(repo, 'tag', '-a', name, '-m', name)


def _manifest(split):
    task = HELD_ID if split == 'heldout' else DEV_ID
    return {'split': split, 'tasks': [{'instance_id': task, 'split': split}]}


def test_no_tag_refuses(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match='protocol-freeze'):
        assert_heldout_unlocked({'freeze_sha256': 'sha256:' + '0' * 64}, repo=repo)


def test_file_edited_after_tag_refuses(tmp_path):
    repo = _repo(tmp_path)
    _tag(repo, 'protocol-freeze')
    expected = freeze_sha256(repo)
    (repo / FREEZE_FILE).write_text('changed\n', encoding='utf-8')
    with pytest.raises(ValueError, match='changed after'):
        assert_heldout_unlocked({'freeze_sha256': expected}, repo=repo)


@pytest.mark.parametrize('value', [None, 'sha256:' + '1' * 64])
def test_manifest_freeze_hash_missing_or_wrong_refuses(tmp_path, value):
    repo = _repo(tmp_path)
    _tag(repo, 'protocol-freeze')
    with pytest.raises(ValueError, match='freeze_sha256'):
        assert_heldout_unlocked({} if value is None else {'freeze_sha256': value}, repo=repo)


def test_unlocked_passes_and_logs(tmp_path):
    repo = _repo(tmp_path)
    _tag(repo, 'protocol-freeze')
    assert_heldout_unlocked({'freeze_sha256': freeze_sha256(repo), 'manifest_hash': 'sha256:m'}, repo=repo,
                            command='run_graph_retrieval')
    line = json.loads((repo / ACCESS_LOG).read_text(encoding='utf-8').splitlines()[-1])
    assert line['tag'] == 'protocol-freeze' and line['command'] == 'run_graph_retrieval'
    assert line['commit'] == _git(repo, 'rev-parse', 'HEAD') and line['manifest_hash'] == 'sha256:m'


def test_gate_ignores_line_ending_differences(tmp_path):
    repo = _repo(tmp_path)
    _tag(repo, 'protocol-freeze')
    path = repo / FREEZE_FILE
    path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
    assert_heldout_unlocked({'freeze_sha256': freeze_sha256(repo)}, repo=repo)


def test_latest_tag_orders_amendments_numerically(tmp_path):
    repo = _repo(tmp_path)
    assert latest_freeze_tag(repo) is None
    for name in ('protocol-freeze', 'protocol-freeze-amend-9', 'protocol-freeze-amend-10', 'protocol-freezer'):
        _tag(repo, name)
    assert latest_freeze_tag(repo) == 'protocol-freeze-amend-10'


def test_require_split_dev_unchanged_and_heldout_gated(monkeypatch):
    calls = []
    monkeypatch.setattr(dataset, 'assert_heldout_unlocked', lambda manifest, **kw: calls.append(manifest))
    dataset.require_split(_manifest('dev'), allowed=('dev', 'heldout'))
    assert calls == []
    dataset.require_split(_manifest('heldout'), allowed=('dev', 'heldout'))
    assert len(calls) == 1


def test_require_split_heldout_refused_in_repo_without_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(heldout_gate, 'ROOT', _repo(tmp_path))
    with pytest.raises(ValueError, match='protocol-freeze'):
        dataset.require_split(_manifest('heldout'), allowed=('dev', 'heldout'))


# ---- manifest and freeze document (Task 4) ----

def test_prepare_dataset_heldout_requires_freeze_hash(tmp_path):
    with pytest.raises(ValueError, match='freeze_sha256'):
        dataset.prepare_dataset(tmp_path, split='heldout', freeze_sha256=None)
    with pytest.raises(ValueError, match='freeze_sha256'):
        dataset.prepare_dataset(tmp_path, split='dev', freeze_sha256='sha256:' + '0' * 64)


def test_prepare_manifest_heldout_without_tag_errors(tmp_path):
    if latest_freeze_tag(ROOT) is not None:
        pytest.skip('repo already frozen; the script would download the dataset')
    process = subprocess.run([sys.executable, 'scripts/prepare_manifest.py', str(tmp_path), '--split', 'heldout',
                              '--allow-heldout'], cwd=ROOT, capture_output=True, text=True)
    assert process.returncode != 0 and 'protocol-freeze' in process.stderr


def test_prepare_dataset_freeze_protocol_checked_before_download(tmp_path):
    with pytest.raises(ValueError, match='freeze_protocol'):
        dataset.prepare_dataset(tmp_path, split='dev', freeze_protocol='r1')
    with pytest.raises(ValueError, match='unknown freeze protocol'):
        dataset.prepare_dataset(tmp_path, split='heldout', freeze_sha256='sha256:' + '0' * 64, freeze_protocol='other')


def test_prepare_manifest_r1_without_tag_names_r1_tag(tmp_path):
    if latest_freeze_tag(ROOT, 'r1') is not None:
        pytest.skip('repo already frozen for R1; the script would download the dataset')
    process = subprocess.run([sys.executable, 'scripts/prepare_manifest.py', str(tmp_path), '--split', 'heldout',
                              '--allow-heldout', '--protocol', 'r1'], check=False, cwd=ROOT, capture_output=True,
                             text=True)
    assert process.returncode != 0 and 'protocol-freeze-r1' in process.stderr


FREEZE_SECTIONS = ['## 1. Commit và môi trường', '## 2. Model và prompt', '## 3. Variants', '## 4. Budget và timeout',
                   '## 5. Retrieval', '## 6. Dataset', '## 7. Harness', '## 8. Metric', '## 9. Phép thống kê',
                   '## 10. Lệnh chạy', '## 11. Chữ ký', '## 12. Amendment']


def test_freeze_document_has_required_sections():
    text = (ROOT / FREEZE_FILE).read_text(encoding='utf-8')
    assert [s for s in FREEZE_SECTIONS if s not in text] == []
    for value in ('sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a',
                  'sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd',
                  'McNemar', 'Holm', 'A1 vs A0', 'A2 vs A1', 'A3 vs A2', '10.000'):
        assert value in text


# ---- Plan 2026-11-17 Task 7: a second protocol (R1) with its own freeze file and tag ------------------------------

R1_FILE = 'docs/protocol_freeze_r1_heldout.md'


def _r1_repo(tmp_path):
    repo = _repo(tmp_path)
    (repo / R1_FILE).write_bytes(b'# R1 protocol\n')
    _git(repo, 'add', '.')
    _git(repo, 'commit', '-qm', 'r1 freeze')
    return repo


def test_r1_tag_does_not_unlock_repair(tmp_path):
    repo = _r1_repo(tmp_path)
    _tag(repo, 'protocol-freeze-r1')
    assert latest_freeze_tag(repo, 'r1') == 'protocol-freeze-r1'
    assert latest_freeze_tag(repo, 'repair') is None


def test_repair_tag_does_not_unlock_r1(tmp_path):
    repo = _r1_repo(tmp_path)
    _tag(repo, 'protocol-freeze')
    assert latest_freeze_tag(repo, 'r1') is None and latest_freeze_tag(repo) == 'protocol-freeze'


def test_manifest_protocol_selects_freeze_file_and_logs_protocol(tmp_path):
    repo = _r1_repo(tmp_path)
    _tag(repo, 'protocol-freeze-r1')
    manifest = {**_manifest('heldout'), 'freeze_protocol': 'r1', 'freeze_sha256': freeze_sha256(repo, 'r1')}
    assert_heldout_unlocked(manifest, repo=repo, command='t')
    assert json.loads((repo / ACCESS_LOG).read_text(encoding='utf-8').splitlines()[-1])['protocol'] == 'r1'
    with pytest.raises(ValueError):
        assert_heldout_unlocked({**manifest, 'freeze_protocol': 'repair'}, repo=repo)


def test_r1_amendment_tag_wins(tmp_path):
    repo = _r1_repo(tmp_path)
    _tag(repo, 'protocol-freeze-r1')
    _git(repo, 'commit', '--allow-empty', '-qm', 'amend')
    _tag(repo, 'protocol-freeze-r1-amend-2')
    assert latest_freeze_tag(repo, 'r1') == 'protocol-freeze-r1-amend-2'


def test_unknown_protocol_is_refused(tmp_path):
    with pytest.raises(ValueError):
        latest_freeze_tag(_repo(tmp_path), 'other')


def test_count_heldout_eligible_reads_paths_only(tmp_path):
    spec = importlib.util.spec_from_file_location('count_heldout_eligible', ROOT / 'scripts' / 'count_heldout_eligible.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    patch_two = ('diff --git a/p/a.py b/p/a.py\n--- a/p/a.py\n+++ b/p/a.py\n@@ -1 +1 @@\n-x\n+y\n'
                 'diff --git a/p/b.py b/p/b.py\n--- a/p/b.py\n+++ b/p/b.py\n@@ -1 +1 @@\n-x\n+y\n')
    patch_one = 'diff --git a/p/a.py b/p/a.py\n--- a/p/a.py\n+++ b/p/a.py\n@@ -1 +1 @@\n-x\n+y\n'
    task = {'repo': 'o/r', 'base_commit': 'a' * 40, 'problem_statement': 'x'}
    rows = [{**task, 'instance_id': HELD_ID, 'patch': patch_two}, {**task, 'instance_id': DEV_ID, 'patch': patch_one}]
    counts = module.count_eligible(rows)
    assert counts == {'heldout': 1, 'at_least_1': 1, 'at_least_2': 1, 'by_repo': {'o/r': {'at_least_1': 1, 'at_least_2': 1}}}
    with pytest.raises(ValueError, match='base_commit'):
        module.count_eligible([*rows, {**task, 'instance_id': HELD_ID, 'base_commit': 'main', 'patch': patch_one}])


def test_count_heldout_eligible_logs_parquet_hash(tmp_path, monkeypatch, capsys):
    pa = pytest.importorskip('pyarrow')
    import pyarrow.parquet as pq
    spec = importlib.util.spec_from_file_location('count_heldout_eligible', ROOT / 'scripts' / 'count_heldout_eligible.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    parquet = tmp_path / 'test.parquet'
    pq.write_table(pa.table({'instance_id': [HELD_ID], 'repo': ['o/r'], 'base_commit': ['a' * 40],
                             'problem_statement': ['x'], 'patch': ['']}), parquet)
    assert module.main([str(parquet)]) == 0
    expected = dataset.sha256(parquet.read_bytes())
    assert json.loads(capsys.readouterr().out)['parquet_sha256'] == expected
    entry = json.loads((tmp_path / module.ACCESS_LOG).read_text(encoding='utf-8').splitlines()[-1])
    assert entry['parquet_sha256'] == expected and entry['parquet'] == str(parquet)


def test_heldout_manifest_name_carries_protocol():
    revision = 'b' * 40
    assert dataset.manifest_name(revision, 'dev', 50) == 'verified-bbbbbbbbbbbb-dev-50.json'
    repair, r1 = (dataset.manifest_name(revision, 'heldout', 50, p) for p in ('repair', 'r1'))
    assert repair == 'verified-bbbbbbbbbbbb-heldout-repair-50.json' and r1 == 'verified-bbbbbbbbbbbb-heldout-r1-50.json'
    assert dataset.manifest_name(revision, 'heldout', 50) == repair   # no protocol means repair, as in the gate


def test_caller_protocol_must_match_manifest_protocol(tmp_path):
    repo = _r1_repo(tmp_path)
    _tag(repo, 'protocol-freeze')                                   # only the repair freeze is signed
    repair = {**_manifest('heldout'), 'freeze_sha256': freeze_sha256(repo)}
    assert_heldout_unlocked(repair, repo=repo, protocol='repair')
    with pytest.raises(ValueError, match='protocol'):
        assert_heldout_unlocked(repair, repo=repo, protocol='r1')   # the R1 runner must not open on the repair tag


def test_require_split_passes_expected_protocol(monkeypatch):
    seen = {}
    monkeypatch.setattr(dataset, 'assert_heldout_unlocked', lambda manifest, **kw: seen.update(kw))
    dataset.require_split(_manifest('heldout'), allowed=('dev', 'heldout'), protocol='r1')
    assert seen['protocol'] == 'r1'
    dataset.require_split(_manifest('heldout'), allowed=('dev', 'heldout'))
    assert seen['protocol'] == 'repair'
