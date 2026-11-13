# MCP servers as the build-server guide and the proposal describe them (TV2, 13/11/2026)

## Sources

Only these three, as the user asked:

- **[G]** MCP build-server guide, Python tab: https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server
- **[P]** proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md`
- **[plan]** `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`

## Intent

The user saw the servers drift from these sources. This change removes what the sources do not describe and keeps what they require:

| Source says | Code today | Change |
|---|---|---|
| [G] "You must use the Python MCP SDK 2.0.0 or higher"; `from mcp.server import MCPServer` | `server_factory.py` picks SDK 1 (`mcp.server.fastmcp.FastMCP`) or SDK 2 at run time from package metadata | import `MCPServer` directly; drop the SDK 1 lane |
| [G] installs only `mcp` | `server_factory.py:69` and `tests/mcp_server/test_prompt_wire.py:79` import `mcp_types` (a package `mcp` depends on; `mcp.types` re-exports it) | import from `mcp.types` |
| [G] `mcp = MCPServer("weather")`: name only | `instructions` passed to `vgar-graph` and `vgar-execution` (added in `e668ba0f`) | remove `instructions` and the factory parameter |
| [G] SDK 2 | `ProtocolValidationFilter` (`proposal/prompts.py:138`) hides an SDK 1 log line; SDK 2.2.0 never emits `Failed to validate request` | remove the filter and its install hook |
| [P] §10.5 lines 1123–1138: "path jail: chỉ truy cập repo được allowlist"; §10.3 line 1074 `build_or_update_graph(repo_path)` | `workspace.py` (`e668ba0f`, `b4cbaec0`) takes the folder the host started in as the repository when the configuration names none | remove; the repository comes only from the host configuration |
| [G] client config with absolute paths | `configs/mcp_server/mcp.shared.example.json` names no repository | remove; keep the per-repository examples |

## Approaches

- **A, chosen by the user:** everything is declared in the host configuration; a server started without a required variable stops and names it.
- B, rejected: keep default graph/log locations and server instructions. Not in [G] or [P].

## Goals

1. `src/vgar/mcp/server_factory.py`: `from mcp.server import MCPServer`; `create_server(name, *, log_level)` returns `MCPServer(name, log_level=...)`; no `packaging`/metadata version selection, no FastMCP, no `instructions`. `create_resource_server` keeps its job (raw-URI resource reads and prompt rendering that [plan] L6-3/L6-4 and [P] lines 1045–1052, 1108–1120 require) on the SDK 2 class only, with `mcp.types` and `mcp.shared.exceptions.MCPError`.
2. Remove `ProtocolValidationFilter`, `install_protocol_log_guard` and the `protocol_reject` hook if nothing else needs them under SDK 2 (the plan confirms by test).
3. Delete `src/vgar/mcp/workspace.py` and its calls in the three servers; remove `_instructions()` from `graph_server.py` and the instructions text from `execution_server.py`.
4. Replace the removed startup call (only under `__name__ == "__main__"`) with a check that stops the process and names each problem variable: root variables the server reads (`VGAR_REPOSITORY_ROOT`, `VGAR_LEASE_ROOT`) must be absolute paths of existing directories; `VGAR_GRAPH_DATABASE` (graph, execution) and `VGAR_MCP_AUDIT_LOG` (all) must be absolute paths. Absolute is required because `import vgar` loads the project's `.env` (`config/settings.py:20`, `override=False`) and its relative values would resolve inside the repository being edited. The plan settles the exact list for `vgar-execution`.
5. Delete `configs/mcp_server/mcp.shared.example.json` and the README section "One configuration for every repository"; README attaches hosts with the per-repository examples (`mcpServers`, `command`, `args`, `env`, absolute paths), and its `claude mcp add` / `opencode mcp add` commands pass every required variable.
6. Tests: delete `tests/mcp_server/test_tv2_workspace_defaults.py` and the SDK 1 case of `tests/mcp_server/test_sdk_runtime.py`; `test_prompt_wire.py` uses `mcp.types`; add tests for the startup check (missing or relative variable: exit naming it; full configuration: starts).

## Non-goals

- Tools, resources, the prompt, graph building and incremental update keep their behaviour.
- `pyproject.toml` keeps `mcp==2.2.0` (one package; [G] shows `mcp[cli]`, whose extra only adds the `mcp` command line, not used here).
- The three per-repository example files are unchanged.
- `VGAR_TOKENIZER_MANIFEST` for `get_related_context` is a separate decision.

## Anti-goals

- No server works on a folder the configuration does not name.
- No server writes its graph or audit log inside the repository through a relative default.
- No import from a package other than `mcp` for MCP types.

## Constraints

- The user commits; the builder edits files and reports the file list.
- In-process imports of the servers in tests keep working.
- [G] rules stay: nothing on stdout, one `logging.getLogger(__name__)` per module, tool docstrings with `Args:`, `mcp.run(transport="stdio")`.

## Builder's calls (open to correction)

- Uncommitted tokenizer assertions added earlier this session to `tests/test_tv2_live_build.py` and `mcp.shared.example.json` are reverted (the example files no longer declare the tokenizer, so they fail today). This session's README edits are kept; only the sections above change.
- Error wording and where the startup check lives are left to the plan.
