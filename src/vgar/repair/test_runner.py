"""Bounded, shell-free pytest runner for a disposable workspace."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

if os.name == "nt":
    import ctypes

from vgar.contracts.evidence import TestCaseResult, TestRunResult
from vgar.contracts.repair import FailureReason

from .workspace import safe_relative_path

MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def _validate_selector(selector: str) -> str:
    if not selector or selector.startswith("-") or "\n" in selector or "\r" in selector:
        raise ValueError(f"Invalid pytest selector: {selector!r}")
    parts = selector.split("::")
    if any(not part for part in parts):
        raise ValueError(f"Invalid pytest selector: {selector!r}")
    safe_relative_path(parts[0])
    if any("/" in part or "\\" in part for part in parts[1:]):
        raise ValueError(f"Invalid pytest selector: {selector!r}")
    return selector


class _WindowsJob:
    """Windows job object: inherited children stay in the same killable process tree."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle_type = ctypes.c_void_p
        kernel.CreateJobObjectW.argtypes = [handle_type, ctypes.c_wchar_p]
        kernel.CreateJobObjectW.restype = handle_type
        kernel.AssignProcessToJobObject.argtypes = [handle_type, handle_type]
        kernel.AssignProcessToJobObject.restype = ctypes.c_int
        kernel.TerminateJobObject.argtypes = [handle_type, ctypes.c_uint]
        kernel.TerminateJobObject.restype = ctypes.c_int
        kernel.CloseHandle.argtypes = [handle_type]
        kernel.CloseHandle.restype = ctypes.c_int
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        if not kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            error = ctypes.get_last_error()
            kernel.CloseHandle(self.handle)
            raise OSError(error, "AssignProcessToJobObject failed")

    def terminate(self) -> None:
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 1):
            raise OSError(ctypes.get_last_error(), "TerminateJobObject failed")

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _kill_tree(process: subprocess.Popen[bytes], job: _WindowsJob | None = None) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        if job is None:
            raise RuntimeError("Cannot guarantee Windows process-tree cleanup without a job object")
        job.terminate()
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _parse_junit(path: Path) -> tuple[list[TestCaseResult], dict[str, int]]:
    if not path.exists():
        return [], {}
    cases: list[TestCaseResult] = []
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        child = next((node for node in case if node.tag in {"failure", "error", "skipped"}), None)
        kind = {"failure": "failed", "error": "error", "skipped": "skipped"}.get(child.tag, "passed") if child is not None else "passed"
        counts[kind] += 1
        status = "PASS" if kind == "passed" else ("NOT_RUN" if kind == "skipped" else ("ERROR" if kind == "error" else "FAIL"))
        try:
            duration = max(0, round(float(case.attrib.get("time", "0")) * 1000))
        except ValueError:
            duration = 0
        cases.append(TestCaseResult(name=f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}",
                                    status=status, duration_ms=duration,
                                    detail=(child.text or child.attrib.get("message")) if child is not None else None))
    return cases, counts


def run_tests(workspace: Path, selectors: tuple[str, ...], timeout_seconds: float) -> TestRunResult:
    root = Path(workspace).resolve(strict=True)
    if not root.is_dir() or not selectors or timeout_seconds <= 0:
        raise ValueError("Workspace, selectors and positive timeout are required")
    selected = tuple(_validate_selector(item) for item in selectors)
    tool_dir = Path(tempfile.mkdtemp(prefix=".m2-pytest-", dir=root))
    junit = tool_dir / "junit.xml"
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            f"--junitxml={junit}", *selected]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else " ".join(argv)
    environment = os.environ.copy()
    for key in list(environment):
        if any(secret in key.upper() for secret in ("TOKEN", "PASSWORD", "API_KEY", "SECRET")):
            environment.pop(key, None)
    environment["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    start = time.monotonic()
    timed_out = False
    output_truncated = False
    launch_error: OSError | None = None
    exit_code: int | None = None
    job: _WindowsJob | None = None
    try:
        with (tool_dir / "stdout.bin").open("wb") as out, (tool_dir / "stderr.bin").open("wb") as err:
            try:
                process = subprocess.Popen(argv, cwd=root, env=environment, stdout=out, stderr=err,
                                           shell=False, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                                           start_new_session=os.name != "nt")
                if os.name == "nt":
                    try:
                        job = _WindowsJob(process)
                    except OSError:
                        process.kill()
                        process.wait()
                        raise
            except OSError as exc:
                launch_error = exc
            else:
                while process.poll() is None:
                    if time.monotonic() - start >= timeout_seconds:
                        timed_out = True
                        _kill_tree(process, job)
                        break
                    if (tool_dir / "stdout.bin").stat().st_size > MAX_OUTPUT_BYTES or (tool_dir / "stderr.bin").stat().st_size > MAX_OUTPUT_BYTES:
                        output_truncated = True
                        _kill_tree(process, job)
                        break
                    time.sleep(0.05)
                exit_code = process.wait()
                if job is not None:
                    job.terminate()
                    job.close()
                    job = None
        stdout_data = (tool_dir / "stdout.bin").read_bytes()
        stderr_data = (tool_dir / "stderr.bin").read_bytes()
        if len(stdout_data) > MAX_OUTPUT_BYTES or len(stderr_data) > MAX_OUTPUT_BYTES:
            output_truncated = True
        try:
            cases, counts = _parse_junit(junit)
        except (ET.ParseError, ValueError):
            cases, counts = [], {}
        if timed_out:
            status, reason = "ERROR", FailureReason(code="TEST_TIMEOUT", message="Pytest exceeded timeout")
        elif output_truncated:
            status, reason = "ERROR", FailureReason(code="VERIFICATION_INCOMPLETE", message="Pytest output limit exceeded")
        elif launch_error is not None:
            status, reason = "ERROR", FailureReason(code="INTERNAL_ERROR", message=f"Cannot start pytest: {launch_error}")
        elif exit_code == 0:
            status, reason = "PASS", None
        elif exit_code == 1 and counts.get("failed", 0) > 0:
            status, reason = "FAIL", FailureReason(code="TEST_FAILED", message="Pytest assertions failed")
        else:
            status, reason = "ERROR", FailureReason(code="VERIFICATION_INCOMPLETE", message=f"Pytest exited {exit_code} before a valid result")
        return TestRunResult(status=status, command=command, argv=argv, exit_code=exit_code,
                             duration_ms=round((time.monotonic() - start) * 1000),
                             stdout=stdout_data.decode("utf-8", errors="replace"),
                             stderr=stderr_data.decode("utf-8", errors="replace"),
                             timeout_seconds=timeout_seconds, cases=cases, case_counts=counts,
                             reason=reason, complete=not (timed_out or output_truncated),
                             output_truncated=output_truncated, stdout_bytes=len(stdout_data),
                             stderr_bytes=len(stderr_data))
    finally:
        if job is not None:
            job.close()
        for attempt in range(20):
            try:
                shutil.rmtree(tool_dir)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
