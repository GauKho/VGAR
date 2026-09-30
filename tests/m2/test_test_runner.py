from __future__ import annotations

from pathlib import Path
import time

import pytest

from vgar.repair.test_runner import run_tests


def _repo(tmp_path: Path, source: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_case.py").write_text(source, encoding="utf-8")
    return repo


def test_pass_records_case_and_stdout(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "def test_ok():\n    print('hello')\n    assert True\n")
    result = run_tests(repo, ("tests/test_case.py",), 10)
    assert result.status == "PASS"
    assert result.exit_code == 0
    assert result.case_counts["passed"] == 1
    assert result.duration_ms >= 0
    assert result.command


def test_assertion_failure_is_fail_not_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "def test_bad():\n    assert False, 'expected failure'\n")
    result = run_tests(repo, ("tests/test_case.py",), 10)
    assert result.status == "FAIL"
    assert result.reason and result.reason.code == "TEST_FAILED"
    assert result.case_counts["failed"] == 1
    assert "expected failure" in result.stdout


def test_invalid_selector_rejected_without_running(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "def test_ok():\n    pass\n")
    with pytest.raises(ValueError):
        run_tests(repo, ("../outside.py",), 10)
    with pytest.raises(ValueError):
        run_tests(repo, ("-k",), 10)


def test_timeout_is_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "import time\ndef test_slow():\n    time.sleep(30)\n")
    result = run_tests(repo, ("tests/test_case.py",), 0.5)
    assert result.status == "ERROR"
    assert result.reason and result.reason.code == "TEST_TIMEOUT"
    assert not result.complete


def test_missing_pytest_target_is_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "def test_ok():\n    pass\n")
    result = run_tests(repo, ("tests/missing.py",), 10)
    assert result.status == "ERROR"
    assert result.exit_code != 0


def test_launch_failure_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import vgar.repair.test_runner as runner

    repo = _repo(tmp_path, "def test_ok():\n    pass\n")

    def cannot_launch(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("python missing")

    monkeypatch.setattr(runner.subprocess, "Popen", cannot_launch)
    result = runner.run_tests(repo, ("tests/test_case.py",), 10)
    assert result.status == "ERROR"
    assert result.reason and result.reason.code == "INTERNAL_ERROR"


def test_timeout_kills_spawned_child(tmp_path: Path) -> None:
    source = ("import subprocess, sys\n"
              "def test_slow():\n"
              "    child = subprocess.Popen([sys.executable, '-c', \"import pathlib,time; time.sleep(2); pathlib.Path('sentinel.txt').write_text('alive')\"])\n"
              "    child.wait()\n")
    repo = _repo(tmp_path, source)
    result = run_tests(repo, ("tests/test_case.py",), 0.7)
    assert result.status == "ERROR"
    time.sleep(2.3)
    assert not (repo / "sentinel.txt").exists()


def test_output_limit_is_error_even_for_fast_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import vgar.repair.test_runner as runner

    repo = _repo(tmp_path, "def test_chatty():\n    print('x' * 5000)\n    assert False\n")
    monkeypatch.setattr(runner, "MAX_OUTPUT_BYTES", 128)
    original_sleep = time.sleep
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: original_sleep(1))
    result = runner.run_tests(repo, ("tests/test_case.py",), 10)
    assert result.status == "ERROR"
    assert result.output_truncated is True
    assert result.reason and result.reason.code == "VERIFICATION_INCOMPLETE"
