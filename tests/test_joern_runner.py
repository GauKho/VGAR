"""L3-1: running Joern in Docker; every failure must come back as a status, never as an exception."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest
import tree_sitter_python
from tree_sitter import Language, Node, Parser

from vgar.graph import joern_runner
from vgar.graph.code_graph import (
    JoernMethod,
    function_statements,
    parse_export,
    project_method,
)
from vgar.graph.joern_runner import JoernConfig, docker_command, run_joern

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "joern"
MINIMAL_EXPORT = "METHOD\tpkg/a.py\tm.login\t1\tlogin\nEND\n"
PARSER = Parser(Language(tree_sitter_python.language()))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("def login():\n    return 1\n", encoding="utf-8")
    (root / "other.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _mount(command: list[str], target: str) -> Path:
    suffix = f":{target}"
    return Path(next(part[:-len(suffix)] for part in command if part.endswith(suffix)))


def _name_of(command: list[str]) -> str:
    return command[command.index("--name") + 1]


def _fake_docker(calls: list[list[str]], export: str | None = MINIMAL_EXPORT, returncode: int = 0, stderr: str = "") -> Callable:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        if export is not None and any("joern --script" in part for part in command):
            (_mount(command, "/out") / "edges.tsv").write_bytes(export.encode("utf-8"))
        return subprocess.CompletedProcess(command, returncode, "", stderr)
    return run


@pytest.mark.parametrize("path_type,root,expected", [
    (PureWindowsPath, "C:\\Users\\thư mục\\s", "C:/Users/thư mục/s:/src:ro"),
    (PurePosixPath, "/home/a b/s", "/home/a b/s:/src:ro"),
])
def test_docker_command_mounts_each_path_as_one_argument(path_type: type[PurePath], root: str, expected: str) -> None:
    command = docker_command(JoernConfig(), "n", path_type(root), path_type("/o"), path_type("/w"), "true")
    assert expected in command and command[:2] == ["docker", "run"]
    assert "--rm" in command and command[command.index("--network") + 1] == "none" and command[command.index("--name") + 1] == "n"


def test_only_the_given_files_are_staged(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staged: list[list[str]] = []
    inner = _fake_docker([])

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        source = _mount(command, "/src:ro")
        staged.append(sorted(path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()))
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert staged == [["pkg/a.py"], ["pkg/a.py"]]


def test_ready_returns_parsed_methods(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([]))
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "ready" and result.reason is None and [method.name for method in result.methods] == ["login"]


def test_two_containers_have_distinct_names(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert len(calls) == 2 and _name_of(calls[0]) != _name_of(calls[1])


def test_each_run_uses_new_container_names(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert len({_name_of(command) for command in calls}) == 4


def test_no_python_files_does_not_call_docker(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    result = run_joern(repo, [], JoernConfig())
    assert result.status == "ready" and result.methods == () and calls == []


def test_missing_docker_is_unavailable(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", run)
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "unavailable" and "docker" in result.reason and result.methods == ()


def test_missing_networkx_is_unavailable(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    monkeypatch.setattr(joern_runner.importlib.util, "find_spec", lambda name: None)
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "unavailable" and "code-graph" in result.reason and calls == []


def test_nonzero_exit_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], returncode=1, stderr="first\nboom\n"))
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "failed" and "boom" in result.reason


def test_nonzero_exit_without_output_still_has_a_reason(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], returncode=3))
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "failed" and "3" in result.reason


@pytest.mark.parametrize("error_at", ["copyfile", "TemporaryDirectory"])
def test_staging_error_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch, error_at: str) -> None:
    def full_disk(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_docker(calls))
    monkeypatch.setattr(joern_runner.shutil if error_at == "copyfile" else joern_runner.tempfile, error_at, full_disk)
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "failed" and "No space left" in result.reason and calls == []


@pytest.mark.parametrize("export", [None, "CFG\tx\nEND\n", "", "END\n", "METHOD\tpkg/a.py\tm.login\t1\tlogin\n"],
                         ids=["no-file", "short-row", "empty", "no-methods", "truncated"])
def test_missing_or_broken_output_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch, export: str | None) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_docker([], export=export))
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "failed" and result.reason and result.methods == ()


def _timing_out(calls: list[list[str]], remove_error: BaseException | None = None) -> Callable:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        if command[1] == "rm":
            if remove_error is not None:
                raise remove_error
            return subprocess.CompletedProcess(command, 0, "", "")
        raise subprocess.TimeoutExpired(command, 1)
    return run


def test_timeout_removes_the_container(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _timing_out(calls))
    result = run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig())
    assert result.status == "timeout" and result.reason
    assert calls[-1] == ["docker", "rm", "-f", _name_of(calls[0])] and len(calls) == 2


@pytest.mark.parametrize("error", [OSError("gone"), subprocess.TimeoutExpired("docker", 30)], ids=["os-error", "timeout"])
def test_rm_failure_after_timeout_does_not_raise(repo: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    monkeypatch.setattr(subprocess, "run", _timing_out([], remove_error=error))
    assert run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig()).status == "timeout"


def test_timeout_is_shared_by_both_steps(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    budgets: list[float] = []
    inner = _fake_docker([])

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        budgets.append(float(kwargs["timeout"]))
        clock[0] += 60.0
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(joern_runner.time, "monotonic", lambda: clock[0])
    assert run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig(timeout_seconds=100.0)).status == "ready"
    assert budgets == [100.0, 40.0]


def test_spent_budget_stops_before_the_second_step(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    calls: list[list[str]] = []
    inner = _fake_docker(calls)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        clock[0] += 150.0
        return inner(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(joern_runner.time, "monotonic", lambda: clock[0])
    assert run_joern(repo, [repo / "pkg" / "a.py"], JoernConfig(timeout_seconds=100.0)).status == "timeout"
    assert len(calls) == 1


def _functions(source: bytes) -> list[Node]:
    found, stack = [], [PARSER.parse(source).root_node]
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            found.append(node)
        stack.extend(reversed(node.named_children))
    return found


def _line_flows(methods: tuple[JoernMethod, ...] | list[JoernMethod], source: bytes) -> dict[tuple[str, int], tuple]:
    """Flow of every function of flow_cases.py, in line numbers, so two runs of Joern can be compared."""
    by_key = {(method.name, method.line): method for method in methods if method.path == "flow_cases.py"}
    flows = {}
    for function in _functions(source):
        name = function.child_by_field_name("name").text.decode()
        line = function.start_point.row + 1
        statements = function_statements(function, source)
        lines = [statement.node.start_point.row + 1 for statement in statements]
        flow = project_method(by_key[name, line], statements)
        flows[name, line] = ({(lines[a], lines[b]) for a, b in flow.cfg}, {(lines[a], lines[b]) for a, b in flow.control},
                             {(lines[use], None if definition is None else lines[definition]): names for (use, definition), names in flow.data.items()},
                             flow.raises_fixed)
    return flows


def _recorded() -> tuple[list[JoernMethod], bytes]:
    text = (FIXTURE_DIR / "flow_cases.edges.tsv").read_text(encoding="utf-8")
    return parse_export(text), (FIXTURE_DIR / "flow_cases.py").read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.docker
def test_real_joern_matches_the_recorded_fixture(tmp_path: Path) -> None:
    recorded, source = _recorded()
    (tmp_path / "flow_cases.py").write_bytes(source)
    result = run_joern(tmp_path, [tmp_path / "flow_cases.py"], JoernConfig())
    assert result.status == "ready", result.reason
    assert _line_flows(result.methods, source) == _line_flows(recorded, source)


@pytest.mark.docker
def test_real_joern_crlf_equals_lf(tmp_path: Path) -> None:
    recorded, source = _recorded()
    crlf = source.replace(b"\n", b"\r\n")
    (tmp_path / "flow_cases.py").write_bytes(crlf)
    result = run_joern(tmp_path, [tmp_path / "flow_cases.py"], JoernConfig())
    assert result.status == "ready", result.reason
    assert _line_flows(result.methods, crlf) == _line_flows(recorded, source)
