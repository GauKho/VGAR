# Repository Only From Host Configuration, SDK 2 Only — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The three MCP servers work only on the repository the host configuration declares, are built the way the build-server guide shows (`from mcp.server import MCPServer`, package `mcp` only), and stop with a named variable when the configuration is incomplete.

**Architecture:** Delete the folder auto-detection (`workspace.py`) and server instructions; a new `host_config.py` checks the host-declared environment when a server is started by a host. `server_factory.py` drops the SDK 1 lane and imports SDK 2 directly; the SDK 1 protocol-log workaround goes.

**Tech Stack:** Python 3.11, `mcp==2.2.0`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-explicit-repository-config-design.md`

## Global Constraints

- Sources: build-server guide `2026-07-28` (Python tab), proposal §10.3/§10.5, plan L6-3/L6-4/L6-5.
- `from mcp.server import MCPServer`; MCP types only from `mcp.types`, errors from `mcp.shared.exceptions`; no `mcp_types`, no `FastMCP`, no `instructions`.
- Nothing on stdout; one `logging.getLogger(__name__)` per module; `mcp.run(transport="stdio")` unchanged.
- `pyproject.toml` stays `mcp==2.2.0`. The three per-repository example files are not edited.
- The user commits: each task ends with the file list, not a commit.

## Review Focus

1. Host value with surrounding spaces (`" D:/repo "`): treated as the stripped value, as `leased_root` callers already strip.
2. Forward-slash Windows paths (`D:/kltn/repo`) are absolute; drive-relative `D:repo` is not.
3. Host omits `VGAR_GRAPH_DATABASE` / `VGAR_MCP_AUDIT_LOG` while the project `.env` supplies relative values: the server stops naming the variable instead of crashing on `artifacts\sample_graph.db` or writing `logs/` into the repository.
4. `VGAR_GRAPH_BACKEND=snapshot` (used by `test_storage_snapshots.py`): no repository root or database is required.
5. `vgar-execution` started from the example config (no `VGAR_LEASE_ROOT`): it still starts; `run_pytest` keeps answering `ROOT_NOT_LEASED` per call.

Each line has a test in Task 1.

---

### Task 1: Repository only from the host configuration

**Files:**
- Create: `src/vgar/mcp/host_config.py`
- Delete: `src/vgar/mcp/workspace.py`, `tests/mcp_server/test_tv2_workspace_defaults.py`, `configs/mcp_server/mcp.shared.example.json`
- Modify: `src/vgar/mcp/servers/graph_server.py:33-55` (import, `__main__` call, `_instructions`, `instructions=`), `src/vgar/mcp/servers/execution_server.py:33-45`, `src/vgar/mcp/servers/repository_server.py:20-29`, `src/vgar/mcp/server_factory.py` (drop the `instructions` parameter of both functions), `README.md`
- Restore: `tests/test_tv2_live_build.py` to `HEAD` (`git restore tests/test_tv2_live_build.py`: removes this session's tokenizer assertions)
- Modify: `tests/test_w10_impact_mcp.py:84` (add `"VGAR_MCP_AUDIT_LOG": str(tmp_path / "audit.jsonl")` to the subprocess env; take `tmp_path`)
- Test: `tests/mcp_server/test_host_config.py`

**Interfaces:**
- Produces: `check_host_config(server: Literal["graph", "execution", "repository"], environ: Mapping[str, str] | None = None) -> list[str]` (problems, each starting with the variable name; `environ` defaults to `os.environ`; values are stripped) and `require_host_config(server) -> None` (logs every problem with `logger.error` on stderr, then `raise SystemExit(2)`).

Rules (value = stripped string):

| Server | Required |
|---|---|
| graph | `VGAR_MCP_AUDIT_LOG` absolute; if `VGAR_GRAPH_BACKEND` (default `sqlite`) is `sqlite`: `VGAR_REPOSITORY_ROOT` absolute existing directory, `VGAR_GRAPH_DATABASE` absolute |
| execution | `VGAR_MCP_AUDIT_LOG` absolute, `VGAR_REPOSITORY_ROOT` absolute existing directory, `VGAR_GRAPH_DATABASE` absolute; `VGAR_LEASE_ROOT` optional, but if set: absolute existing directory |
| repository | `VGAR_MCP_AUDIT_LOG` absolute, `VGAR_LEASE_ROOT` absolute existing directory |

Problem texts: `"<NAME> is not set"`, `"<NAME>=<value> is not an absolute path"`, `"<NAME>=<value> is not an existing directory"`. `require_host_config` ends with one line: `"declare these in the host configuration (env), with absolute paths (proposal §10.5: only allowlisted repositories)"`.

- [ ] **Step 1: Write the failing tests** in `tests/mcp_server/test_host_config.py`

```python
from vgar.mcp.host_config import check_host_config

def full(tmp_path, **extra):
    repo = tmp_path / "repo"; repo.mkdir(exist_ok=True)
    return {"VGAR_REPOSITORY_ROOT": str(repo), "VGAR_LEASE_ROOT": str(repo),
            "VGAR_GRAPH_DATABASE": str(tmp_path / "g.db"), "VGAR_MCP_AUDIT_LOG": str(tmp_path / "a.jsonl"), **extra}

def test_full_configuration_has_no_problems(tmp_path):
    for server in ("graph", "execution", "repository"):
        assert check_host_config(server, full(tmp_path)) == []

def test_graph_names_every_missing_variable():
    names = {p.split()[0] for p in check_host_config("graph", {})}
    assert names == {"VGAR_REPOSITORY_ROOT", "VGAR_GRAPH_DATABASE", "VGAR_MCP_AUDIT_LOG"}

def test_dotenv_relative_values_are_rejected(tmp_path):
    env = full(tmp_path, VGAR_GRAPH_DATABASE="artifacts/sample_graph.db", VGAR_MCP_AUDIT_LOG="logs/mcp_audit.jsonl")
    problems = check_host_config("graph", env)
    assert any(p.startswith("VGAR_GRAPH_DATABASE=artifacts/sample_graph.db is not an absolute path") for p in problems)
    assert any(p.startswith("VGAR_MCP_AUDIT_LOG=logs/mcp_audit.jsonl is not an absolute path") for p in problems)

def test_root_must_be_an_existing_directory(tmp_path):
    problems = check_host_config("graph", full(tmp_path, VGAR_REPOSITORY_ROOT=str(tmp_path / "missing")))
    assert problems == [f"VGAR_REPOSITORY_ROOT={tmp_path / 'missing'} is not an existing directory"]

def test_values_are_stripped_and_forward_slashes_are_absolute(tmp_path):
    env = {k: f" {v.replace(chr(92), '/')} " for k, v in full(tmp_path).items()}
    assert check_host_config("graph", env) == []

def test_drive_relative_path_is_not_absolute(tmp_path):   # Windows only: skip elsewhere
    ...  # VGAR_GRAPH_DATABASE="D:graph.db" -> "... is not an absolute path"

def test_snapshot_backend_needs_no_repository_or_database(tmp_path):
    assert check_host_config("graph", {"VGAR_GRAPH_BACKEND": "snapshot", "VGAR_MCP_AUDIT_LOG": str(tmp_path / "a")}) == []

def test_execution_lease_root_is_optional_but_checked_when_set(tmp_path):
    env = full(tmp_path); env.pop("VGAR_LEASE_ROOT")
    assert check_host_config("execution", env) == []
    assert check_host_config("execution", {**env, "VGAR_LEASE_ROOT": "repo"}) == ["VGAR_LEASE_ROOT=repo is not an absolute path"]

def test_repository_requires_lease_root(tmp_path):
    env = full(tmp_path); env.pop("VGAR_LEASE_ROOT")
    assert [p.split()[0] for p in check_host_config("repository", env)] == ["VGAR_LEASE_ROOT"]

def test_server_process_without_configuration_exits_naming_the_variable(tmp_path):
    # subprocess: [sys.executable, "-B", "-m", "vgar.mcp.servers.repository_server"], cwd=tmp_path,
    # env={"PYTHONPATH": <repo>/src, "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1", "SYSTEMROOT": os.environ["SYSTEMROOT"]},
    # stdin=DEVNULL, timeout=60
    # assert returncode == 2; "VGAR_LEASE_ROOT is not set" in stderr; "VGAR_MCP_AUDIT_LOG is not set" in stderr; stdout == ""
    ...

def test_graph_server_with_relative_database_exits_before_opening_it(tmp_path):
    # same, module vgar.mcp.servers.graph_server, env adds full(tmp_path) with VGAR_GRAPH_DATABASE="artifacts/sample_graph.db"
    # assert returncode == 2; "VGAR_GRAPH_DATABASE=artifacts/sample_graph.db is not an absolute path" in stderr;
    # "Graph database not found" not in stderr; not (tmp_path / "artifacts").exists()
    ...
```

- [ ] **Step 2: Run them, expect failure**

Run: `.venv/Scripts/python.exe -m pytest -q tests/mcp_server/test_host_config.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'vgar.mcp.host_config'`

- [ ] **Step 3: Implement `check_host_config` and `require_host_config` in `src/vgar/mcp/host_config.py`** per the table; module docstring cites proposal §10.5. In each server replace `if __name__ == "__main__": apply_workspace_defaults("<name>")` with `if __name__ == "__main__": require_host_config("<name>")` (graph: before `create_graph_service()` runs). Remove `_instructions()` and the `instructions=` arguments; remove the `instructions` parameter from `create_server` and `create_resource_server`. Delete the three files listed above.

- [ ] **Step 4: README** (`README.md`, current working-tree version): delete "One configuration for every repository" and its Claude Code / OpenCode shared commands; Quick start and the host sections attach with the per-repository examples; the `claude mcp add` / `opencode.cmd mcp add` commands pass `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_GRAPH_DATABASE`, `VGAR_REPOSITORY_ROOT`, `VGAR_MCP_AUDIT_LOG` (graph, execution) and `VGAR_LEASE_ROOT`, `VGAR_MCP_AUDIT_LOG` (repository), all absolute; delete the sentence about server instructions; Troubleshooting: replace the project-marker row with "`… is not set` / `… is not an absolute path` on start: declare it in the host configuration".

- [ ] **Step 5: Run the task's tests and the MCP suite**

Run: `.venv/Scripts/python.exe -m pytest -q tests/mcp_server tests/test_w10_impact_mcp.py tests/test_tv2_live_build.py`
Expected: the new tests pass; failures only in the four `sdk1*` cases that fail today (Task 2 removes them). If another subprocess test fails with `VGAR_MCP_AUDIT_LOG … not an absolute path`, add `VGAR_MCP_AUDIT_LOG=str(tmp_path / "audit.jsonl")` to its env.

- [ ] **Step 6: Check nothing references the removed code**

Run: `git grep -n "apply_workspace_defaults\|PROJECT_MARKERS\|mcp.shared.example\|instructions=" -- src tests README.md configs`
Expected: no output.

- [ ] **Step 7: Report the file list to the user** (no commit).

---

### Task 2: SDK 2 only, package `mcp` only

**Files:**
- Modify: `src/vgar/mcp/server_factory.py`, `src/vgar/mcp/proposal/prompts.py:138-165` (delete `ProtocolValidationFilter`, `install_protocol_log_guard`, `audit_protocol_reject`), `src/vgar/mcp/servers/graph_server.py` (drop `protocol_reject=` and its import)
- Modify tests: `tests/mcp_server/test_sdk_runtime.py:19-75`, `tests/mcp_server/test_prompt_wire.py` (lines 1, 13, 19, 77-79, 109-111), `tests/mcp_server/test_resource_wire.py:14-18`, `tests/mcp_server/test_incremental_serving.py:85-86`, `tests/test_w10_impact_mcp.py:87-96`
- Modify: `README.md` Testing section (drop the sentence about TV1's legacy interpreter)

**Interfaces:**
- Consumes: Task 1's factory signatures without `instructions`.
- Produces: `create_server(name: str, *, log_level: str = "WARNING") -> MCPServer`; `create_resource_server(name: str, resource_reader, *, log_level: str = "WARNING", prompt_reader=None) -> MCPServer` (subclass of `MCPServer` with the existing `read_resource` / `get_prompt` overrides; errors via `mcp.shared.exceptions.MCPError`; `GetPromptResult` from `mcp.types`).

- [ ] **Step 1: Replace the four version-selection tests** in `test_sdk_runtime.py` with:

```python
def test_create_server_is_the_sdk2_mcpserver():
    from mcp.server import MCPServer
    from vgar.mcp.server_factory import create_server
    server = create_server("vgar-test")
    assert isinstance(server, MCPServer) and server.name == "vgar-test"
```

and in `test_prompt_wire.py` make `test_raw_protocol_rejection_has_no_secret_or_fake_render` SDK 2 only, `import mcp.types as types`, and assert `rejects == []`.

- [ ] **Step 2: Run, expect the import-check to fail**

Run: `git grep -n "mcp_types\|fastmcp\|FastMCP\|import_module(\"mcp" -- src tests`
Expected: matches in `server_factory.py` and `test_prompt_wire.py` (to be removed).

- [ ] **Step 3: Implement** the Interfaces in `server_factory.py` with top-level `from mcp.server import MCPServer`, `import mcp.types as types`, `from mcp.shared.exceptions import MCPError`; no `metadata`, `packaging`, `import_module`. Delete the three functions in `prompts.py` and the `protocol_reject` wiring in `graph_server.py`. Drop the `sdk1*` parameter ids and `LEGACY*` constants from the wire tests, and the SDK 1 `except ImportError` branch in `test_w10_impact_mcp.py`.

- [ ] **Step 4: Verify**

Run: `git grep -n "mcp_types\|fastmcp\|FastMCP\|SDK1\|ProtocolValidationFilter\|protocol_reject" -- src tests` → no output.
Run: `.venv/Scripts/python.exe -m pytest -q tests/mcp_server tests/test_w10_impact_mcp.py tests/test_tv2_live_build.py` → 0 failed.
Run: `.venv/Scripts/python.exe -m pytest -q` → no failures beyond the three known before this change (record them from a run on `HEAD` first if unsure).

- [ ] **Step 5: Report the file list to the user** (no commit).
