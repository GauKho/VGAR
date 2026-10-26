"""Owned cleanup must survive short sharing locks, never hide permanent errors."""
import ctypes
import errno
import json
import os
from pathlib import Path
import threading

import pytest

from w78_support import CharacterChatTokenizer
from vgar.repair import contracts as m_contracts
from vgar.repair import evidence as m_evidence
from vgar.models import generator as m_generator
from vgar.repair import pipeline as m_pipeline
from vgar.repair import workspace as m_workspace
from test_w78_pipeline import FIX


def owned_tree(tmp_path):
    root = tmp_path / 'temp'
    private = root / 'm2-w78-cleanup-test'
    (private / 'seed').mkdir(parents=True)
    (private / 'seed' / 'app.py').write_bytes(b'value = 1\n')
    return root, private


def windows_error(code, path):
    error = PermissionError(errno.EACCES, 'Controlled Windows sharing violation', str(path))
    error.winerror = code
    return error


def is_seed(path):
    # Linux shutil.rmtree calls os.rmdir('seed', dir_fd=...), so match the name.
    return Path(path).name == 'seed'


def saved_cleanup(root, private):
    return json.loads((root / '.cleanup-records' / (private.name + '.json')).read_text(encoding='utf-8'))


@pytest.mark.parametrize('code', [32, 33])
def test_owned_cleanup_retries_sharing_lock_and_records_actual_outcome(tmp_path, monkeypatch, code):
    module = m_workspace
    root, private = owned_tree(tmp_path)
    original = os.rmdir
    remaining = [2]

    def rmdir(path, *args, **kwargs):
        if is_seed(path) and remaining[0]:
            remaining[0] -= 1
            raise windows_error(code, private / 'seed')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, 'rmdir', rmdir)
    module._remove_owned(private, root)
    assert not private.exists()
    report = saved_cleanup(root, private)
    assert report['status'] == 'PASS' and report['complete'] is True
    assert len(report['attempts']) == 3
    assert [a['winerror'] for a in report['attempts'][:-1]] == [code, code]
    assert report['attempts'][0]['failed_path'] == str(private / 'seed')
    assert 'PermissionError' in report['attempts'][0]['traceback']
    assert report['started_utc'] and report['ended_utc'] and report['duration_ms'] >= 0
    assert report['lock_owner'] == 'not_identified'


def test_owned_cleanup_does_not_swallow_persistent_sharing_lock(tmp_path, monkeypatch):
    module = m_workspace
    root, private = owned_tree(tmp_path)
    original = os.rmdir

    def rmdir(path, *args, **kwargs):
        if is_seed(path):
            raise windows_error(32, private / 'seed')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, 'rmdir', rmdir)
    with pytest.raises(PermissionError) as caught:
        module._remove_owned(private, root)
    assert caught.value.winerror == 32 and private.exists()
    report = saved_cleanup(root, private)
    assert report['status'] == 'ERROR' and report['complete'] is True
    assert len(report['attempts']) == 6
    assert caught.value.cleanup_diagnostics == report
    assert all(a['winerror'] == 32 for a in report['attempts'])


def test_owned_cleanup_propagates_non_sharing_error_without_backoff(tmp_path, monkeypatch):
    module = m_workspace
    root, private = owned_tree(tmp_path)
    original = os.rmdir
    failure = OSError(errno.EIO, 'Controlled non-sharing I/O error', str(private / 'seed'))

    def rmdir(path, *args, **kwargs):
        if is_seed(path):
            raise failure
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, 'rmdir', rmdir)
    with pytest.raises(OSError) as caught:
        module._remove_owned(private, root)
    assert caught.value is failure
    report = saved_cleanup(root, private)
    assert report['status'] == 'ERROR' and len(report['attempts']) == 1


def test_cleanup_ownership_guard_runs_before_any_delete_or_log(tmp_path):
    module = m_workspace
    root, private = owned_tree(tmp_path)
    with pytest.raises(ValueError, match='Refusing cleanup'):
        module._remove_owned(private, tmp_path / 'different-root')
    assert (private / 'seed' / 'app.py').read_bytes() == b'value = 1\n'
    assert not (root / '.cleanup-records').exists()


@pytest.mark.parametrize('blocked', [False, True])
def test_pipeline_links_cleanup_evidence_and_never_passes_a_locked_workspace(m1_case, tmp_path, monkeypatch, blocked):
    task, counter = m1_case
    original = os.rmdir

    def rmdir(path, *args, **kwargs):
        if blocked and is_seed(path):
            raise windows_error(32, path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, 'rmdir', rmdir)
    run = m_pipeline.run_repair(task, m_contracts.RepairPolicy(),
        m_generator.FakeGenerator(FIX), None, tmp_path / 'runs',
        m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    record = json.loads(run.path.read_text(encoding='utf-8'))
    assert record['status'] == ('ERROR' if blocked else 'PASS')
    assert record['original_source_unchanged'] is True
    cleanup = record['stages']['cleanup']
    assert cleanup['status'] == ('ERROR' if blocked else 'PASS')
    assert cleanup == json.loads(Path(cleanup['diagnostics_path']).read_text(encoding='utf-8'))
    if blocked:
        assert len(cleanup['attempts']) == 6
        assert record['reason'] == 'FINALIZATION_ERROR'
        assert record['finalization_errors'][0]['stage'] == 'cleanup'
        assert 'PermissionError' in record['finalization_errors'][0]['traceback']
    bundle = json.loads((run.directory / record['artifacts']['bundle']).read_text(encoding='utf-8'))
    assert bundle['metadata']['canonical_sha256'] == m_evidence.digest(run.path.read_bytes())


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows directory sharing handle')
def test_real_windows_directory_handle_is_released_before_cleanup_returns(tmp_path):
    module = m_workspace
    root, private = owned_tree(tmp_path)
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # FILE_SHARE_READ | FILE_SHARE_WRITE, deliberately no FILE_SHARE_DELETE.
    handle = kernel.CreateFileW(str(private / 'seed'), 1, 3, None, 3, 0x02000000, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    closed = threading.Event()

    def release():
        kernel.CloseHandle(handle)
        closed.set()

    timer = threading.Timer(0.25, release)
    timer.start()
    try:
        module._remove_owned(private, root)
        assert closed.is_set() and not private.exists()
        report = saved_cleanup(root, private)
        assert report['status'] == 'PASS'
        assert any(a['winerror'] == 32 for a in report['attempts'])
    finally:
        timer.join(timeout=2)
        if not closed.is_set():
            release()
