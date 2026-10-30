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
