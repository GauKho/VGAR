"""Docker bridge argv/report/integrity semantics without a Docker dependency."""

import io
import sys
import tarfile
import time

import pytest

import test_admission as admission_cases
from test_admission import admit

admitted_case = admission_cases.admitted_case


@pytest.fixture
def snapshot_transport_case(admitted_case, tmp_path, monkeypatch):
    """Exercise the real archive/attestation path; only Docker CLI is simulated."""
    import hashlib
    import json
    from pathlib import Path
    import shutil

    executor = make_executor(admitted_case, tmp_path)
    state = dict(failure=None, allow_retained=False, copies=[], cleanups=[], after_copy=None,
                 artifact_root=tmp_path, report_payloads={'nodeids.json': b'{"sentinel": "kept"}'},
                 report_copies=[], report_failure=None, target_transform=None)
    monkeypatch.setattr(executor, '_identity', lambda directory: None)

    def checked(args, directory, deadline):
        if args[0] == 'cp' and Path(args[1]).name == 'control':
            archive = Path(args[1]) / 'snapshot.tar'
            assert archive.is_file()
            if state['failure'] == 'copy':
                raise RuntimeError('transport copy failed')
            target = tmp_path / 'fake-container' / executor.operation_id / 'snapshot.tar'
            target.parent.mkdir(parents=True)
            shutil.copyfile(archive, target)
            state['copies'].append(dict(path=target, size=target.stat().st_size,
                                        digest='sha256:' + hashlib.sha256(target.read_bytes()).hexdigest()))
            if state['after_copy']:
                state['after_copy'](archive)
        elif args[0] == 'cp' and args[1].endswith(':/vgar/result.json'):
            if state['failure'] == 'report':
                raise RuntimeError('target report missing')
            config = json.loads((directory / 'control/config.json').read_bytes())
            data = dict(complete=True, exit_code=0, snapshot_before=config['expected'],
                        snapshot_after=config['expected'], runtime=config['runtime'],
                        base=config['base_identity'], protocol='vgar-docker-repair-v1', argv=config.get('argv'))
            data['report_artifacts'] = {
                name: dict(state='AVAILABLE', size_bytes=len(state['report_payloads'][name]),
                           sha256='sha256:' + hashlib.sha256(state['report_payloads'][name]).hexdigest())
                if name in state['report_payloads'] else dict(state='MISSING')
                for name in config.get('report_names', [])}
            if state['target_transform']:
                state['target_transform'](data)
            Path(args[2]).write_text(json.dumps(data), encoding='utf-8')
        elif args[0] == 'cp' and any(args[1].endswith(':/vgar/' + n) for n in ('nodeids.json', 'junit.xml')):
            name = args[1].rsplit('/', 1)[1]
            state['report_copies'].append(name)
            if name not in state['report_payloads'] or state['report_failure'] == 'copy':
                raise RuntimeError('report docker cp failed')
            raw = state['report_payloads'][name]
            Path(args[2]).write_bytes(raw + b'tampered' if state['report_failure'] == 'hash' else raw)
        return {'stdout': ''}

    def cli(args, directory, deadline):
        assert args[0] == 'exec'
        if not state['allow_retained']:
            assert not (directory / 'control/snapshot.tar').exists(), 'host transport archive retained after copy'
        with tarfile.open(state['copies'][-1]['path']) as container_archive:
            assert 'xarray/core.py' in container_archive.getnames()
        if state['failure'] == 'probe':
            raise RuntimeError('target probe failed')
        if state['failure'] == 'interrupt':
            raise KeyboardInterrupt()
        return dict(status='PASS', complete=True, exit_code=0, stdout='', stderr='')

    monkeypatch.setattr(executor, '_checked', checked)
    monkeypatch.setattr(executor, '_cli', cli)
    monkeypatch.setattr(executor, '_cleanup',
                        lambda directory: state['cleanups'].append(directory) or {'status': 'PASS'})
    try:
        yield executor, state
    finally:
        executor.lease.__exit__()


def test_snapshot_transport_is_removed_before_probe_with_hash_receipt(snapshot_transport_case):
    import json
    e, state = snapshot_transport_case
    report = e.lease.private / 'reports/saved/nodeids.json'
    result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60,
                                 reports={'nodeids.json': report})
    directory = e.evidence_root / e.operation_id
    receipt = json.loads((directory / 'snapshot_transport.json').read_bytes())
    assert result['status'] == 'PASS' and result['complete'] is True
    assert result['snapshot_transport'] == receipt
    assert receipt['operation_id'] == e.operation_id
    assert receipt['archive_path'] == 'control/snapshot.tar'
    assert receipt['archive_bytes'] == state['copies'][0]['size']
    assert receipt['archive_sha256'] == state['copies'][0]['digest']
    assert receipt['copy_status'] == 'PASS' and receipt['cleanup_status'] == 'REMOVED'
    assert receipt['retained_bytes'] == 0
    assert (directory / 'control/config.json').is_file()
    assert (directory / 'control/docker_probe.py').is_file()
    assert json.loads(report.read_bytes()) == {'sentinel': 'kept'}
    assert json.loads((directory / 'command.json').read_bytes())['snapshot_transport'] == receipt
    assert len(state['cleanups']) == 1


@pytest.mark.parametrize('phase', ['copy', 'probe', 'report', 'interrupt', 'build'])
def test_snapshot_transport_failure_cleans_archive_and_preserves_primary_error(
    snapshot_transport_case, monkeypatch, phase,
):
    import json
    e, state = snapshot_transport_case
    state['failure'] = phase
    if phase == 'build':
        def broken_add(*a, **kw):
            raise RuntimeError('archive build failed')
        monkeypatch.setattr(tarfile.TarFile, 'add', broken_add)
    error = KeyboardInterrupt if phase == 'interrupt' else RuntimeError
    message = {'copy': 'transport copy failed', 'probe': 'target probe failed',
               'report': 'target report missing', 'build': 'archive build failed'}.get(phase)
    with pytest.raises(error, match=message):
        e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    directory = e.evidence_root / e.operation_id
    assert not (directory / 'control/snapshot.tar').exists()
    receipt = json.loads((directory / 'snapshot_transport.json').read_bytes())
    assert receipt['copy_status'] == ('ERROR' if phase == 'copy' else 'NOT_STARTED' if phase == 'build' else 'PASS')
    assert receipt['cleanup_status'] == 'REMOVED' and receipt['retained_bytes'] == 0
    assert len(state['cleanups']) == 1


def test_snapshot_unlink_error_warns_without_changing_result(snapshot_transport_case, monkeypatch, caplog):
    from pathlib import Path
    e, state = snapshot_transport_case
    state['allow_retained'] = True
    original = Path.unlink
    attempts = []

    def denied(path, *args, **kwargs):
        if path.name == 'snapshot.tar' and path.parent.name == 'control':
            attempts.append(path)
            raise PermissionError('archive locked')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', denied)
    result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    receipt = result['snapshot_transport']
    assert result['status'] == 'PASS' and result['complete'] is True
    assert receipt['cleanup_status'] == 'ERROR'
    assert receipt['retained_bytes'] == state['copies'][0]['size']
    assert 'archive locked' in receipt['reason']
    assert 'archive locked' in caplog.text
    assert len(attempts) == 1 and len(state['cleanups']) == 1


@pytest.mark.parametrize('primary_failure', [None, 'probe'])
def test_snapshot_receipt_write_error_is_warning_not_primary_failure(
    snapshot_transport_case, monkeypatch, caplog, primary_failure,
):
    from vgar.repair import docker_executor
    e, state = snapshot_transport_case
    state['failure'] = primary_failure
    original = docker_executor.atomic_json

    def denied(path, value):
        if path.name == 'snapshot_transport.json':
            raise OSError('receipt storage unavailable')
        return original(path, value)

    monkeypatch.setattr(docker_executor, 'atomic_json', denied)
    if primary_failure:
        with pytest.raises(RuntimeError, match='target probe failed'):
            e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    else:
        result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
        assert result['status'] == 'PASS'
        assert result['snapshot_transport']['cleanup_status'] == 'REMOVED'
        assert 'receipt storage unavailable' in result['snapshot_transport']['receipt_error']
    assert 'receipt storage unavailable' in caplog.text
    assert not (e.evidence_root / e.operation_id / 'control/snapshot.tar').exists()


def test_repeated_snapshot_operations_do_not_accumulate_host_archives(snapshot_transport_case):
    import json
    e, state = snapshot_transport_case
    roots, receipts = [], []
    for _ in range(14):
        result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
        roots.append(result['docker_evidence'])
        receipts.append(result['snapshot_transport'])
    assert len(set(roots)) == 14 and len(state['copies']) == 14
    assert not list(e.evidence_root.glob('*/control/snapshot.tar'))
    assert len(list(e.evidence_root.glob('*/snapshot_transport.json'))) == 14
    summary = dict(fixture_only=True, real_docker=False, operations=14,
                   host_transport_archives_remaining=0,
                   host_transport_bytes_removed=sum(r['archive_bytes'] for r in receipts),
                   simulated_container_copies=14, receipts=receipts)
    (state['artifact_root'] / 'transport-fixture-summary.json').write_text(json.dumps(summary), encoding='utf-8')


def test_snapshot_cleanup_absence_and_repeated_call_are_safe(snapshot_transport_case):
    e, state = snapshot_transport_case
    result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    again = e._cleanup_snapshot_transport(e.evidence_root / e.operation_id)
    assert again == result['snapshot_transport']


def test_snapshot_cleanup_rejects_directory_replacement(snapshot_transport_case):
    e, state = snapshot_transport_case
    state['allow_retained'] = True

    def replace(archive):
        archive.unlink()
        archive.mkdir()
        (archive / 'keep.txt').write_text('keep', encoding='utf-8')
    state['after_copy'] = replace
    result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    assert result['status'] == 'PASS'
    assert result['snapshot_transport']['cleanup_status'] == 'ERROR'
    assert (e.evidence_root / e.operation_id / 'control/snapshot.tar/keep.txt').read_text() == 'keep'


def test_snapshot_archive_path_rejects_other_operation(snapshot_transport_case, tmp_path):
    e, _ = snapshot_transport_case
    e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    outside = tmp_path / 'not-this-operation'
    outside.mkdir()
    with pytest.raises(ValueError, match='(?i)operation|scope|outside'):
        e._snapshot_archive_path(outside)


def test_snapshot_absent_when_operation_fails_before_archive_creation(snapshot_transport_case, monkeypatch):
    import json
    e, state = snapshot_transport_case
    monkeypatch.setattr(e, '_execute', lambda *a: (_ for _ in ()).throw(RuntimeError('before archive')))
    with pytest.raises(RuntimeError, match='before archive'):
        e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    receipt = json.loads((e.evidence_root / e.operation_id / 'snapshot_transport.json').read_bytes())
    assert receipt['cleanup_status'] == 'ABSENT' and receipt['retained_bytes'] == 0
    assert receipt['copy_status'] == 'NOT_STARTED'
    assert receipt['archive_bytes'] is None and receipt['archive_sha256'] is None
    assert len(state['cleanups']) == 1


def test_snapshot_unlink_error_never_masks_probe_error(snapshot_transport_case, monkeypatch, caplog):
    import json
    from pathlib import Path
    e, state = snapshot_transport_case
    state.update(failure='probe', allow_retained=True)
    original = Path.unlink

    def denied(path, *args, **kwargs):
        if path.name == 'snapshot.tar' and path.parent.name == 'control':
            raise PermissionError('archive remains locked')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', denied)
    with pytest.raises(RuntimeError, match='target probe failed'):
        e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    receipt = json.loads((e.evidence_root / e.operation_id / 'snapshot_transport.json').read_bytes())
    assert receipt['cleanup_status'] == 'ERROR' and 'archive remains locked' in caplog.text


def test_snapshot_control_link_is_rejected_without_touching_external_files(
    snapshot_transport_case, tmp_path,
):
    import json
    import os
    import subprocess

    e, state = snapshot_transport_case
    state.update(failure='probe', allow_retained=True)
    external = tmp_path / 'external-control'
    external.mkdir()
    sentinel = external / 'snapshot.tar'
    sentinel.write_bytes(b'never delete external evidence')
    swapped = []

    def swap(archive):
        control = archive.parent
        original = control.with_name('original-control')
        assert control.resolve().is_relative_to(e.lease.private.resolve())
        assert original.parent.resolve() == control.parent.resolve()
        control.rename(original)
        if os.name == 'nt':
            proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(control), str(external)],
                                  capture_output=True, check=False)
            assert proc.returncode == 0, proc.stderr
        else:
            control.symlink_to(external, target_is_directory=True)
        swapped.append((control, original))

    state['after_copy'] = swap
    try:
        with pytest.raises(RuntimeError, match='target probe failed'):
            e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
        receipt = json.loads((e.evidence_root / e.operation_id / 'snapshot_transport.json').read_bytes())
        assert receipt['cleanup_status'] == 'ERROR'
        assert 'reparse' in receipt['reason'] or 'link' in receipt['reason']
        assert sentinel.read_bytes() == b'never delete external evidence'
    finally:
        for control, original in swapped:
            assert control.parent.resolve() == original.parent.resolve()
            if os.name == 'nt':
                control.rmdir()  # Remove only the fixture junction entry, never its target.
            else:
                control.unlink()
            original.rename(control)


def test_snapshot_metadata_stat_error_is_optional_and_archive_still_removed(
    snapshot_transport_case, monkeypatch, caplog,
):
    from pathlib import Path
    e, _ = snapshot_transport_case
    original_stat, original_metadata = Path.stat, e._snapshot_archive_metadata
    active = [False]

    def metadata(directory):
        active[0] = True
        try:
            return original_metadata(directory)
        finally:
            active[0] = False

    def denied(path, *args, **kwargs):
        if (active[0] and path.name == 'snapshot.tar'
                and kwargs.get('follow_symlinks', True)):
            raise PermissionError('metadata stat denied')
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(e, '_snapshot_archive_metadata', metadata)
    monkeypatch.setattr(Path, 'stat', denied)
    result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    assert result['status'] == 'PASS' and result['complete'] is True
    assert result['snapshot_transport']['cleanup_status'] == 'REMOVED'
    assert result['snapshot_transport']['retained_bytes'] == 0
    assert 'metadata stat denied' in caplog.text


def test_fallback_hash_interrupt_preserves_build_error_and_container_cleanup(
    snapshot_transport_case, monkeypatch,
):
    import json
    from pathlib import Path
    e, state = snapshot_transport_case
    original_open = Path.open

    def build_failed(directory, *args):
        control = directory / 'control'
        control.mkdir()
        (control / 'snapshot.tar').write_bytes(b'partial archive')
        raise RuntimeError('archive build failed')

    def interrupted(path, mode='r', *args, **kwargs):
        if path.name == 'snapshot.tar' and mode == 'rb':
            raise KeyboardInterrupt('interrupted metadata read')
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(e, '_execute', build_failed)
    monkeypatch.setattr(Path, 'open', interrupted)
    observed = None
    try:
        e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60)
    except BaseException as error:
        observed = error
    assert type(observed) is RuntimeError and str(observed) == 'archive build failed'
    assert len(state['cleanups']) == 1
    directory = e.evidence_root / e.operation_id
    assert not (directory / 'control/snapshot.tar').exists()
    receipt = json.loads((directory / 'snapshot_transport.json').read_bytes())
    assert receipt['copy_status'] == 'NOT_STARTED' and receipt['cleanup_status'] == 'REMOVED'
    assert 'KeyboardInterrupt' in receipt['metadata_error']


def make_executor(case, tmp_path):
    from vgar.repair.admission import prepare_admitted_workspace
    from vgar.repair.docker_executor import DockerExecutor

    admission = admit(case)
    lease = prepare_admitted_workspace(case[0], admission, tmp_path / "lease")
    return DockerExecutor(lease, case[0], admission, time.monotonic() + 120, 8192)


def test_pytest_is_mapped_to_pinned_target_and_fixed_report_paths(
    admitted_case, tmp_path
):
    e = make_executor(admitted_case, tmp_path)
    directory = e.lease.private / "reports/one"
    directory.mkdir(parents=True)
    argv = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "vgar.repair.pytest_plugin",
        "--m2-report-json=" + str(directory / "nodeids.json"),
        "--junitxml=" + str(directory / "junit.xml"),
        "--collect-only",
        "tests/vgar_w9_repro_issue.py",
    )
    try:
        mapped, reports = e.map_command(argv)
        assert mapped[0] == "/opt/miniconda3/envs/testbed/bin/python"
        assert "vgar_pytest_reporter" in mapped
        assert "--m2-report-json=/vgar/nodeids.json" in mapped
        assert reports == {
            "nodeids.json": directory / "nodeids.json",
            "junit.xml": directory / "junit.xml",
        }
    finally:
        e.lease.__exit__()


@pytest.mark.parametrize(
    "args",
    [
        (sys.executable, "-c", "print(1)"),
        ("sh", "-c", "true"),
        (
            sys.executable,
            "-m",
            "pytest",
            "--override-ini=x",
            "tests/vgar_w9_repro_issue.py",
        ),
        (sys.executable, "-m", "ruff", "check", "--fix", "xarray/core.py"),
    ],
)
def test_unapproved_commands_rejected_before_transport(admitted_case, tmp_path, args):
    e = make_executor(admitted_case, tmp_path)
    try:
        with pytest.raises(ValueError):
            e.map_command(args)
    finally:
        e.lease.__exit__()


@pytest.mark.parametrize('available', [(), ('nodeids.json',), ('nodeids.json', 'junit.xml')])
def test_report_transport_copies_only_attested_available_files(snapshot_transport_case, available):
    e, state = snapshot_transport_case
    payloads = {'nodeids.json': b'{"complete":true}', 'junit.xml': b'<testsuite/>'}
    state['report_payloads'] = {name: payloads[name] for name in available}
    paths = {name: e.lease.private / 'reports/saved' / name for name in payloads}
    result = e.execute_operation({'kind': 'command', 'argv': ['pytest']}, 60, reports=paths)
    assert result['complete'] is True
    assert set(state['report_copies']) == set(available)
    for name, path in paths.items():
        if name in available:
            assert path.read_bytes() == payloads[name]
        else:
            assert not path.exists()
            assert result['target_result']['report_artifacts'][name] == {'state': 'MISSING'}
    assert state['cleanups']


@pytest.mark.parametrize('fault', ['copy', 'hash', 'metadata', 'runtime'])
def test_report_transport_failure_is_not_patch_failure(snapshot_transport_case, fault):
    e, state = snapshot_transport_case
    state['report_failure'] = fault
    if fault in ('metadata', 'runtime'):
        def corrupt(data):
            if fault == 'metadata':
                data['report_artifacts']['nodeids.json']['size_bytes'] = True
            else:
                data['runtime'] = {'python': 'wrong'}
        state['target_transform'] = corrupt
    report = e.lease.private / 'reports/saved/nodeids.json'
    if fault == 'runtime':
        result = e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60,
                                     reports={'nodeids.json': report})
        assert result['complete'] is False
    else:
        with pytest.raises((RuntimeError, ValueError)):
            e.execute_operation({'kind': 'syntax', 'targets': ['xarray/core.py']}, 60,
                                reports={'nodeids.json': report})
    assert not report.exists()
    assert state['cleanups']


def test_private_test_drift_is_rejected_before_transport(admitted_case, tmp_path):
    e = make_executor(admitted_case, tmp_path)
    try:
        (e.lease.path / "tests/vgar_w9_repro_issue.py").write_text(
            "def test_issue(): pass"
        )
        with pytest.raises(ValueError):
            e.verify_snapshot()
    finally:
        e.lease.__exit__()


def test_target_archive_rejects_traversal_and_links(tmp_path):
    from vgar.repair.docker_probe import load_snapshot

    for name, link in [("../escape", False), ("safe.py", True)]:
        archive = tmp_path / ("link.tar" if link else "traversal.tar")
        with tarfile.open(archive, "w") as t:
            item = tarfile.TarInfo(name)
            item.size = 1
            if link:
                item.type = tarfile.SYMTYPE
                item.linkname = "../outside"
            t.addfile(item, None if link else io.BytesIO(b"x"))
        with pytest.raises(ValueError):
            load_snapshot(
                str(archive), str(tmp_path / "root"), {name: "sha256:" + "a" * 64}
            )
    assert not (tmp_path / "escape").exists()


def test_target_attestation_and_syntax_use_actual_bytes(tmp_path):
    from vgar.repair.docker_probe import attest_snapshot, syntax_report

    root = tmp_path / "root"
    root.mkdir()
    (root / "code.py").write_bytes(b"def broken(:\n")
    import hashlib

    expected = {
        "code.py": "sha256:"
        + hashlib.sha256((root / "code.py").read_bytes()).hexdigest()
    }
    assert attest_snapshot(str(root), expected) == expected
    report = syntax_report(str(root), ["code.py"])
    assert (
        report["diagnostics"][0]["path"] == "code.py"
        and report["tool_version"] == sys.version.split()[0]
    )
    (root / "code.py").write_text("drift")
    with pytest.raises(ValueError):
        attest_snapshot(str(root), expected)


def test_timeout_always_calls_cleanup_and_never_publishes_pass(
    admitted_case, tmp_path, monkeypatch
):
    e = make_executor(admitted_case, tmp_path)
    calls = []
    monkeypatch.setattr(e, "_identity", lambda d: None)

    def cli(args, directory, deadline):
        calls.append(args)
        return {"complete": True, "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(e, "_cli", cli)
    monkeypatch.setattr(
        e, "_execute", lambda *a: (_ for _ in ()).throw(TimeoutError("deadline"))
    )
    monkeypatch.setattr(
        e, "_cleanup", lambda *a: calls.append(["cleanup"]) or {"status": "PASS"}
    )
    try:
        with pytest.raises(TimeoutError):
            e.execute_operation({"kind": "syntax", "targets": ["xarray/core.py"]}, 60)
        assert calls[-1] == ["cleanup"]
    finally:
        e.lease.__exit__()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes only")
def test_control_dir_is_usable_by_capless_container_root(
    admitted_case, tmp_path, monkeypatch
):
    # docker cp keeps host uid/mode; root with --cap-drop ALL cannot bypass them.
    from pathlib import Path

    e = make_executor(admitted_case, tmp_path)
    modes = {}

    def checked(args, directory, deadline):
        if args[0] == "cp":
            control = Path(args[1])
            modes.update({p.name: p.stat().st_mode & 0o777 for p in control.iterdir()})
            modes["."] = control.stat().st_mode & 0o777
            raise RuntimeError("stop after transport")
        return {"stdout": ""}

    monkeypatch.setattr(e, "_identity", lambda d: None)
    monkeypatch.setattr(e, "_checked", checked)
    monkeypatch.setattr(e, "_cleanup", lambda *a: {"status": "PASS"})
    try:
        with pytest.raises(RuntimeError, match="stop after transport"):
            e.execute_operation({"kind": "syntax", "targets": ["xarray/core.py"]}, 60)
        assert modes["."] == 0o777
        assert all(mode & 0o444 == 0o444 for name, mode in modes.items() if name != ".")
    finally:
        e.lease.__exit__()


def test_cleanup_failure_is_fatal_even_after_success(
    admitted_case, tmp_path, monkeypatch
):
    e = make_executor(admitted_case, tmp_path)
    monkeypatch.setattr(e, "_identity", lambda d: None)
    monkeypatch.setattr(e, "_execute", lambda *a: {"complete": True, "exit_code": 0})
    monkeypatch.setattr(
        e, "_cleanup", lambda *a: {"status": "ERROR", "reason": "cannot verify removal"}
    )
    try:
        with pytest.raises(RuntimeError, match="cleanup"):
            e.execute_operation({"kind": "syntax", "targets": ["xarray/core.py"]}, 60)
    finally:
        e.lease.__exit__()


NATIVE_COMMAND = {"env": {}, "argv": ["tests/runtests.py", "--verbosity", "2", "--settings=test_sqlite", "--parallel", "1"]}


def native_case(case):
    """Same admitted task, but its environment profile is a qualified Django-native (v2) profile."""
    import json
    from vgar.evaluation.harness.task_env import NATIVE_SCOPE, SENTINELS, build_profile, validate_profile

    task, mp, pp, kwargs = case
    old = validate_profile(json.loads(pp.read_text(encoding="utf-8")))
    probe = {"protocol": "vgar-native-sentinel-v1", "status": "COLLECTED", "reason": None,
             "source_before": old["source_before"], "source_after": old["source_after"],
             "runtime": dict(old["runtime"], pytest=None),
             "collection": {"exit_code": 0, "node_ids": [SENTINELS["django_runtests"]["node_id"]], "errors": []}}
    row = {"instance_id": old["task_id"], "repo": old["repo"], "base_commit": old["base_commit"]}
    image = {"reference": old["env_ref"].removeprefix("docker://"), "image_id": old["image_id"]}
    profile = build_profile(row, image, NATIVE_SCOPE, probe, daemon_id=old["daemon_id"],
                            test_runner="django_runtests", native_command=NATIVE_COMMAND)
    pp.write_text(json.dumps(profile), encoding="utf-8")
    return task, mp, pp, dict(kwargs, expected_profile_hash=profile["profile_hash"])


def pytest_argv(directory, *tail):
    return (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "vgar.repair.pytest_plugin",
            "--m2-report-json=" + str(directory / "nodeids.json"), "--junitxml=" + str(directory / "junit.xml"), *tail)


def test_native_profile_maps_pytest_argv_to_native_runner(admitted_case, tmp_path):
    import json

    e = make_executor(native_case(admitted_case), tmp_path)
    directory = e.lease.private / "reports/one"
    directory.mkdir(parents=True)
    try:
        mapped, reports = e.map_command(pytest_argv(directory, "--collect-only", "tests/vgar_w9_repro_issue.py"))
        assert mapped[:4] == ["/opt/miniconda3/envs/testbed/bin/python", "/vgar/vgar_native_runner.py",
                              "--runner", "django_runtests"]
        assert json.loads(mapped[mapped.index("--command-json") + 1]) == NATIVE_COMMAND
        assert mapped[mapped.index("--report") + 1] == "/vgar/nodeids.json"
        assert mapped[mapped.index("--junit") + 1] == "/vgar/junit.xml"
        assert mapped[-2:] == ["--collect-only", "tests/vgar_w9_repro_issue.py"]
        assert reports == {"nodeids.json": directory / "nodeids.json", "junit.xml": directory / "junit.xml"}
        with pytest.raises(ValueError):
            e.map_command(pytest_argv(directory, "tests/test_base.py"))  # still outside the admitted scope
    finally:
        e.lease.__exit__()


def test_native_runner_is_shipped_in_control_dir(admitted_case, tmp_path, monkeypatch):
    from pathlib import Path

    e = make_executor(native_case(admitted_case), tmp_path)
    names = set()

    def checked(args, directory, deadline):
        if args[0] == "cp":
            names.update(p.name for p in Path(args[1]).iterdir())
            raise RuntimeError("stop after transport")
        return {"stdout": ""}

    monkeypatch.setattr(e, "_identity", lambda d: None)
    monkeypatch.setattr(e, "_checked", checked)
    monkeypatch.setattr(e, "_cleanup", lambda *a: {"status": "PASS"})
    try:
        with pytest.raises(RuntimeError, match="stop after transport"):
            e.execute_operation({"kind": "syntax", "targets": ["xarray/core.py"]}, 60)
        assert {"vgar_native_runner.py", "vgar_pytest_reporter.py"} <= names
    finally:
        e.lease.__exit__()


@pytest.mark.parametrize("pytest_available", [True, False])
def test_probe_runtime_identity_without_pytest(monkeypatch, pytest_available):
    # Native-runner images (Django, sympy) have no pytest; their profile pins runtime pytest=None.
    import platform as host_platform
    from vgar.repair import docker_probe

    if not pytest_available:
        monkeypatch.setitem(sys.modules, "pytest", None)
    expected = {"python": host_platform.python_version(), "executable": sys.executable,
                "pytest": pytest.__version__ if pytest_available else None}
    stop = RuntimeError("stop after runtime identity")
    monkeypatch.setattr(docker_probe.subprocess, "check_call", lambda *a, **k: (_ for _ in ()).throw(stop))
    result = docker_probe.run({"root": "/nonexistent", "runtime": expected, "argv": None, "base_commit": "a" * 40})
    assert result["runtime"] == expected
    assert "stop after runtime identity" in result["traceback"]


def test_probe_command_loads_the_image_pytest_plugins(tmp_path, monkeypatch):
    # The image's own plugins (e.g. pytest-doctestplus for astropy's --doctest-rst addopts) must load,
    # as they do during qualification and in the official harness; the image is digest-pinned.
    import platform as host_platform
    from vgar.repair import docker_probe

    seen = {}
    monkeypatch.chdir(tmp_path)  # run() chdirs into the root; restore the session cwd afterwards
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setattr(docker_probe.subprocess, "check_call", lambda *a, **k: 0)
    monkeypatch.setattr(docker_probe, "base_identity", lambda root: "base")
    monkeypatch.setattr(docker_probe, "load_snapshot", lambda *a: {})
    monkeypatch.setattr(docker_probe, "attest_snapshot", lambda *a: {})
    monkeypatch.setattr(docker_probe.subprocess, "call", lambda argv, cwd, env: seen.update(env) or 0)
    runtime = {"python": host_platform.python_version(), "executable": sys.executable, "pytest": pytest.__version__}
    result = docker_probe.run({"root": str(tmp_path), "runtime": runtime, "base_commit": "a" * 40,
                               "base_identity": "base", "archive": "x", "expected": {}, "kind": "command",
                               "argv": ["python", "-m", "pytest"]})
    assert result["complete"] is True and result["exit_code"] == 0
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in seen
    assert seen["PYTHONPATH"] == "/vgar" and seen["PYTHONDONTWRITEBYTECODE"] == "1"


def test_probe_reads_non_ascii_config_as_utf8(tmp_path, monkeypatch):
    # Python 3.5/3.6 testbeds run under the C locale (ASCII); Django trees contain non-ASCII file names.
    # UTF-8 of U+00C1 holds byte 0x81, which no 8-bit locale codec (ascii, cp1252) decodes.
    import json
    from vgar.repair import docker_probe

    config, result = tmp_path / "config.json", tmp_path / "result.json"
    config.write_bytes(json.dumps({"root": str(tmp_path / "none"), "runtime": {}, "argv": None,
                                   "expected": {"tests/Ácafe.py": "sha256:" + "a" * 64}},
                                  ensure_ascii=False).encode("utf-8"))
    monkeypatch.setattr(sys, "argv", ["docker_probe.py", str(config), str(result)])
    opened = []

    def recording_open(file, mode="r", *args, **kwargs):
        opened.append((str(file), mode, kwargs.get("encoding")))
        return open(file, mode, *args, **kwargs)

    # Host Python >= 3.7 coerces the C locale to UTF-8 (PEP 538); the 3.5/3.6 targets do not, so pin the codec.
    monkeypatch.setattr(docker_probe, "open", recording_open, raising=False)
    assert docker_probe.main() == 97  # run() fails on the fake root, but the config was read and a result written
    assert json.loads(result.read_text(encoding="utf-8"))["complete"] is False
    assert (str(config), "r", "utf-8") in opened


def test_target_exec_forces_utf8_locale(admitted_case, tmp_path, monkeypatch):
    e = make_executor(admitted_case, tmp_path)
    calls = []

    def cli(args, directory, deadline):
        calls.append(args)
        raise RuntimeError("stop at exec")

    monkeypatch.setattr(e, "_identity", lambda d: None)
    monkeypatch.setattr(e, "_checked", lambda args, directory, deadline: {"stdout": ""})
    monkeypatch.setattr(e, "_cli", cli)
    monkeypatch.setattr(e, "_cleanup", lambda *a: {"status": "PASS"})
    try:
        with pytest.raises(RuntimeError, match="stop at exec"):
            e.execute_operation({"kind": "syntax", "targets": ["xarray/core.py"]}, 60)
        exec_args = next(a for a in calls if a[0] == "exec")
        assert exec_args[exec_args.index("-e") + 1] == "LC_ALL=C.UTF-8"
    finally:
        e.lease.__exit__()
