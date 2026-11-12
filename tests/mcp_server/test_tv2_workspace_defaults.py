"""The repository is the folder the coding agent was opened in; one graph per repository, named after it.

A host started in ``D:/x/backend`` serves that repository with no path in its MCP config. The graph lives outside
the repository, at ``<data dir>/graphs/<folder name>-<8 hex of the full path>.db``, so two repositories with the
same folder name never share a graph, and reopening the same repository reuses its graph.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vgar.mcp import workspace

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "tests" / "fixtures" / "vgar-demo-shop"
KEYS = ("VGAR_REPOSITORY_ROOT", "VGAR_LEASE_ROOT", "VGAR_GRAPH_DATABASE", "VGAR_MCP_AUDIT_LOG")


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    return path


def test_same_folder_name_in_two_places_gives_two_graphs(tmp_path):
    first = workspace.default_database(_repo(tmp_path / "a" / "backend"), tmp_path / "data")
    second = workspace.default_database(_repo(tmp_path / "b" / "backend"), tmp_path / "data")
    assert first != second
    assert first.parent == second.parent == tmp_path / "data" / "graphs"
    assert first.name.startswith("backend-") and first.suffix == ".db" and len(first.stem) == len("backend-") + 8


def test_same_repository_always_gives_the_same_graph(tmp_path):
    repo = _repo(tmp_path / "shop")
    assert workspace.default_database(repo, tmp_path / "d") == workspace.default_database(repo / ".", tmp_path / "d")


def test_defaults_come_from_the_folder_the_agent_was_opened_in(tmp_path):
    repo = _repo(tmp_path / "my shop")
    environ: dict[str, str] = {}
    assert workspace.apply_workspace_defaults("graph", environ, cwd=repo, base=tmp_path / "data") == repo.resolve()
    assert environ["VGAR_REPOSITORY_ROOT"] == environ["VGAR_LEASE_ROOT"] == str(repo.resolve())
    assert environ["VGAR_GRAPH_DATABASE"] == str(workspace.default_database(repo, tmp_path / "data"))
    assert Path(environ["VGAR_GRAPH_DATABASE"]).name.startswith("my_shop-")
    # Logs stay out of the repository the agent is editing.
    assert environ["VGAR_MCP_AUDIT_LOG"] == str(tmp_path / "data" / "logs" / "graph.jsonl")


def test_explicit_configuration_wins(tmp_path):
    repo, other = _repo(tmp_path / "repo"), _repo(tmp_path / "other")
    environ = {"VGAR_REPOSITORY_ROOT": str(other), "VGAR_GRAPH_DATABASE": "D:/g/x.db", "VGAR_MCP_AUDIT_LOG": "a.jsonl"}
    workspace.apply_workspace_defaults("graph", environ, cwd=repo, base=tmp_path / "data")
    assert environ["VGAR_REPOSITORY_ROOT"] == str(other) and environ["VGAR_LEASE_ROOT"] == str(other.resolve())
    assert environ["VGAR_GRAPH_DATABASE"] == "D:/g/x.db" and environ["VGAR_MCP_AUDIT_LOG"] == "a.jsonl"


def test_explicit_root_names_its_own_graph(tmp_path):
    repo = _repo(tmp_path / "repo")
    environ = {"VGAR_REPOSITORY_ROOT": str(repo)}
    workspace.apply_workspace_defaults("graph", environ, cwd=tmp_path, base=tmp_path / "data")
    assert environ["VGAR_GRAPH_DATABASE"] == str(workspace.default_database(repo, tmp_path / "data"))


@pytest.mark.parametrize("marker", [".git", "pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini"])
def test_a_project_marker_makes_a_folder_a_repository(tmp_path, marker):
    folder = tmp_path / "r"
    folder.mkdir()
    (folder / marker).mkdir() if marker == ".git" else (folder / marker).write_text("", encoding="utf-8")
    assert workspace.apply_workspace_defaults("graph", {}, cwd=folder, base=tmp_path / "d") == folder.resolve()


def test_a_folder_that_is_not_a_repository_gets_no_defaults(tmp_path):
    # Opening the agent in a home or download folder must not offer to graph the whole folder.
    environ: dict[str, str] = {}
    assert workspace.apply_workspace_defaults("graph", environ, cwd=tmp_path, base=tmp_path / "d") is None
    assert environ == {}


def test_data_dir_is_local_app_data_on_windows_and_cache_elsewhere(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    expected = tmp_path / ("local" if os.name == "nt" else "cache") / "vgar"
    assert workspace.data_dir() == expected


def _serve(module: str, cwd: Path, data: Path, calls: list[tuple[str, dict]]) -> tuple[list[dict], str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("VGAR_")}
    env.update(PYTHONPATH=str(ROOT / "src"), PYTHONUTF8="1", PYTHON_DOTENV_DISABLED="1", LOCALAPPDATA=str(data),
               XDG_CACHE_HOME=str(data))
    stderr_path = data.parent / f"{module}.stderr.log"
    with stderr_path.open("w", encoding="utf-8") as err:
        process = subprocess.Popen([sys.executable, "-B", "-m", f"vgar.mcp.servers.{module}"], cwd=cwd, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True,
                                   encoding="utf-8")

        def send(message: dict) -> None:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def receive(identifier: int) -> dict:
            while True:
                line = process.stdout.readline()
                if not line:
                    raise EOFError("server closed stdout")
                message = json.loads(line)
                if message.get("id") == identifier:
                    return message

        responses = []
        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "ws-test", "version": "1"}}})
            responses.append(receive(1))
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            for number, (tool, arguments) in enumerate(calls, start=2):
                send({"jsonrpc": "2.0", "id": number, "method": "tools/call",
                      "params": {"name": tool, "arguments": arguments}})
                responses.append(receive(number))
        except EOFError:
            pass
        finally:
            process.stdin.close()
            process.wait(timeout=300)
    return responses, stderr_path.read_text(encoding="utf-8")


def test_graph_server_opened_in_a_repository_builds_its_own_graph(tmp_path):
    repo = tmp_path / "work" / "vgar-demo-shop"
    shutil.copytree(SHOP, repo, ignore=shutil.ignore_patterns(".claude", ".mcp.json", "logs", ".*_cache"))
    data = tmp_path / "data"
    responses, stderr = _serve("graph_server", repo, data, [("build_or_update_graph", {"repo_path": str(repo)}),
                                                             ("search_symbols", {"query": "discount_amount"})])
    assert len(responses) == 3, stderr[-3000:]
    instructions = responses[0]["result"]["instructions"]
    assert "build_or_update_graph" in instructions and str(repo.resolve()) in instructions
    built = json.loads(responses[1]["result"]["content"][0]["text"])
    assert built["status"] == "PASS" and built["data"]["mode"] == "cold"
    found = json.loads(responses[2]["result"]["content"][0]["text"])
    assert found["status"] == "PASS" and found["data"]["symbols"]
    graphs = list((data / "vgar" / "graphs").glob("vgar-demo-shop-*.db"))
    assert graphs == [workspace.default_database(repo, data / "vgar")]
    assert not (repo / "logs").exists()  # nothing written into the repository
    assert (data / "vgar" / "logs" / "graph.jsonl").is_file()


def test_execution_server_tells_the_agent_to_build_the_graph_first(tmp_path):
    repo = _repo(tmp_path / "repo")
    responses, stderr = _serve("execution_server", repo, tmp_path / "data", [])
    assert responses, stderr[-3000:]
    assert "build_or_update_graph" in responses[0]["result"]["instructions"]
