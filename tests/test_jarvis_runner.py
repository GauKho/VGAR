"""L2-1: running JARVIS in Docker; every failure must come back as a status, never as an exception."""
from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest

from vgar.graph import jarvis_runner
from vgar.graph.jarvis_runner import (
    JARVIS_COMMIT,
    JarvisConfig,
    jarvis_command,
    module_name_of,
    run_jarvis,
    staged_path,
)

GRAPH = '{"pkg.a.f": ["pkg.a.g"]}'
DOCKERFILE = Path(__file__).parent.parent / "src" / "vgar" / "graph" / "jarvis" / "Dockerfile"
BASE_DIGEST = "sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "other.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _mount(command: list[str], target: str) -> Path:
    suffix = f":{target}"
    return Path(next(part[:-len(suffix)] for part in command if part.endswith(suffix)))


def _fake_docker(calls: list[list[str]], graph: str | None = GRAPH, skipped: str | None = "[]", returncode: int = 0,
                 stderr: str = "", inspect_code: int = 0) -> Callable:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        if command[1] == "image":
            return subprocess.CompletedProcess(command, inspect_code, "", "No such image")
        out = _mount(command, "/out")
        if graph is not None:
            (out / "graph.json").write_text(graph, encoding="utf-8")
        if skipped is not None:
            (out / "skipped.json").write_text(skipped, encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode, "", stderr)
    return run


def _run(repo: Path, files: list[Path] | None = None, config: JarvisConfig | None = None):
    return run_jarvis(repo, [repo / "src" / "pkg" / "a.py"] if files is None else files, ("src",), config or JarvisConfig())


@pytest.mark.parametrize("relative,roots,marker,expected", [
    ("src/pkg/a.py", ("src",), None, "pkg/a.py"),
    ("src/pkg/a.py", ("src",), "src/__init__.py", "src/pkg/a.py"),
    ("xarray/core.py", ("xarray",), "xarray/__init__.py", "xarray/core.py"),
    ("scripts/x.py", ("src",), None, "scripts/x.py"),
    ("a.py", (".",), None, "a.py"),
    ("src.py", ("src",), None, "src.py"),
])
def test_staged_path(tmp_path: Path, relative: str, roots: tuple[str, ...], marker: str | None, expected: str) -> None:
    if marker:
        (tmp_path / marker).parent.mkdir(parents=True)
        (tmp_path / marker).write_text("", encoding="utf-8")
    assert staged_path(relative, tmp_path, roots) == expected


@pytest.mark.parametrize("staged,name", [("pkg/a.py", "pkg.a"), ("pkg/__init__.py", "pkg"), ("a.py", "a")])
def test_module_name_of(staged: str, name: str) -> None:
    assert module_name_of(staged) == name


@pytest.mark.parametrize("path_type,root,expected", [
    (PureWindowsPath, "C:\\Users\\thư mục\\s", "C:/Users/thư mục/s:/src:ro"),
    (PurePosixPath, "/home/a b/s", "/home/a b/s:/src:ro"),
])
def test_jarvis_command_mounts_each_path_as_one_argument(path_type: type[PurePath], root: str, expected: str) -> None:
    command = jarvis_command(JarvisConfig(), "n", path_type(root), path_type("/o"))
    assert expected in command and command[-1] == "vgar/jarvis-analyzer:v1.0" and "PYTHONHASHSEED=0" in command
    assert "--rm" in command and command[command.index("--network") + 1] == "none" and command[command.index("--name") + 1] == "n"


def test_files_are_staged_from_the_source_root(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staged: list[str] = []
    inner = _fake_docker([])

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if command[1] == "run":
            source = _mount(command, "/src:ro")
            staged.extend(sorted(path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()))
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    assert _run(repo).status == "ready" and staged == ["pkg/a.py"]


def test_path_collision_goes_to_skipped(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "src" / "b.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "b.py").write_text("x = 2\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake_docker([]))
    assert _run(repo, [repo / "b.py", repo / "src" / "b.py"]).skipped_files == ("src/b.py",)


def test_ready_returns_graph_and_repo_paths_of_skipped_files(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], skipped='["pkg/a.py"]'))
    result = _run(repo)
    assert result.status == "ready" and result.reason is None
    assert result.graph == {"pkg.a.f": ["pkg.a.g"]} and result.skipped_files == ("src/pkg/a.py",)


def test_no_python_files_does_not_call_docker(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    result = _run(repo, [])
    assert result.status == "ready" and result.graph == {} and calls == []


def test_missing_docker_is_unavailable(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", run)
    result = _run(repo)
    assert result.status == "unavailable" and "docker" in result.reason and result.graph == {}


def test_missing_image_is_unavailable_and_names_the_build_command(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls, inspect_code=1))
    result = _run(repo)
    assert result.status == "unavailable" and "docker build" in result.reason and len(calls) == 1


@pytest.mark.parametrize("error_at", ["copyfile", "TemporaryDirectory"])
def test_staging_error_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch, error_at: str) -> None:
    def full_disk(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    monkeypatch.setattr(jarvis_runner.shutil if error_at == "copyfile" else jarvis_runner.tempfile, error_at, full_disk)
    result = _run(repo)
    assert result.status == "failed" and "No space left" in result.reason and [command[1] for command in calls] == ["image"]


def test_nonzero_exit_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], returncode=1, stderr="first\nboom\n"))
    result = _run(repo)
    assert result.status == "failed" and "boom" in result.reason


@pytest.mark.parametrize("content", [None, "not json", '{"a": "b"}', "[1]", '{"a": [1]}'], ids=["no-file", "not-json", "not-a-list", "not-a-dict", "not-strings"])
def test_broken_output_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch, content: str | None) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], graph=content))
    result = _run(repo)
    assert result.status == "failed" and result.reason and result.graph == {}


def test_missing_skipped_list_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], skipped=None))
    assert _run(repo).status == "failed"


def _timing_out(calls: list[list[str]]) -> Callable:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, 1)
        return subprocess.CompletedProcess(command, 0, "", "")
    return run


def test_timeout_removes_the_container_and_marks_the_reason(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _timing_out(calls))
    result = _run(repo)
    name = calls[1][calls[1].index("--name") + 1]
    assert result.status == "timeout" and result.reason.startswith("JARVIS_TIMEOUT") and calls[-1] == ["docker", "rm", "-f", name]


def test_timeout_of_the_image_check_removes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(subprocess, "run", run)
    assert _run(repo).status == "unavailable" and len(calls) == 1


def test_image_check_has_its_own_short_limit(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    budgets: list[float] = []
    inner = _fake_docker([])

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        budgets.append(float(kwargs["timeout"]))
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    _run(repo)
    assert budgets == [30.0, 120.0]


def test_each_run_uses_a_new_container_name(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    _run(repo)
    _run(repo)
    names = [command[command.index("--name") + 1] for command in calls if command[1] == "run"]
    assert len(names) == 2 and names[0] != names[1]


def test_tool_output_is_captured(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []
    inner = _fake_docker([])

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen.append(kwargs["capture_output"])
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    _run(repo)
    assert seen == [True, True]


def test_dockerfile_pins_base_and_commit() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert JARVIS_COMMIT in text and BASE_DIGEST in text


def _write(root: Path, files: dict[str, str]) -> list[Path]:
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return [root / name for name in files]


CALLS_WITH_MATCH = {
    "a.py": "from b import route\n\n\ndef main():\n    return route(1)\n",
    "b.py": "def route(v):\n    match v:\n        case 1:\n            return one()\n    return None\n\n\ndef one():\n    return 1\n",
}


@pytest.mark.docker
def test_real_jarvis_reports_a_call(tmp_path: Path) -> None:
    result = run_jarvis(tmp_path, _write(tmp_path, CALLS_WITH_MATCH), (".",), JarvisConfig())
    assert result.status == "ready", result.reason
    assert "b.route" in result.graph["a.main"] and "b.one" in result.graph["b.route"]


@pytest.mark.docker
def test_real_jarvis_skips_a_broken_last_file(tmp_path: Path) -> None:
    files = _write(tmp_path, {"a.py": "def f():\n    return g()\n\n\ndef g():\n    return 1\n", "z.py": "def broken(:\n"})
    result = run_jarvis(tmp_path, files, (".",), JarvisConfig())
    assert result.status == "ready", result.reason
    assert result.skipped_files == ("z.py",) and "a.g" in result.graph["a.f"]


@pytest.mark.docker
def test_real_jarvis_survives_one_very_deep_file(tmp_path: Path) -> None:
    deep = "def f(a):\n    return " + " + ".join(["a"] * 600) + "\n"
    files = _write(tmp_path, {"a.py": "def f():\n    return g()\n\n\ndef g():\n    return 1\n", "deep.py": deep})
    result = run_jarvis(tmp_path, files, (".",), JarvisConfig())
    assert result.status == "ready", result.reason
    assert result.skipped_files == ("deep.py",) and "a.g" in result.graph["a.f"]


@pytest.mark.docker
def test_real_jarvis_is_repeatable(tmp_path: Path) -> None:
    files = _write(tmp_path, CALLS_WITH_MATCH)
    assert run_jarvis(tmp_path, files, (".",), JarvisConfig()).graph == run_jarvis(tmp_path, files, (".",), JarvisConfig()).graph


@pytest.mark.docker
def test_real_jarvis_timeout_leaves_no_container(tmp_path: Path) -> None:
    result = run_jarvis(tmp_path, _write(tmp_path, CALLS_WITH_MATCH), (".",), JarvisConfig(timeout_seconds=0.5))
    assert result.status == "timeout" and result.reason.startswith("JARVIS_TIMEOUT")
    names = "pending"
    for _ in range(40):  # a container the daemon was still creating removes itself when it ends (--rm)
        names = subprocess.run(["docker", "ps", "-a", "--filter", "name=vgar-jarvis", "--format", "{{.Names}}"],
                               capture_output=True, text=True, check=True).stdout.strip()
        if not names:
            break
        time.sleep(0.5)
    assert names == ""
