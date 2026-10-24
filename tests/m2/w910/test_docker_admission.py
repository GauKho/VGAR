"""Docker bridge argv/report/integrity semantics without a Docker dependency."""

import io
import sys
import tarfile
import time

import pytest

import test_admission as admission_cases
from test_admission import admit

admitted_case = admission_cases.admitted_case


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
