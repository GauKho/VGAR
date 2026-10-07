# W3-W4 Completion — Graph MVP + MCP/LangChain Connectivity

Historical checkpoint before the integration fixes of 06/10/2026; see the dated addendum below for current status.

## Implemented

- M1 Python graph builder integrated under `src/vgar/graph/`.
- Tree-sitter Python extraction and Jedi enrichment remain the graph construction backend.
- SQLite graph store/service is selectable with `VGAR_GRAPH_BACKEND=sqlite`.
- MCP graph server now uses `create_graph_service()` instead of hard-coded demo storage.
- Required MCP tools: `graph_search_symbols`, `graph_get_callers`, `graph_get_callees`.
- Required MCP resources: `vgar://repo/summary`, `vgar://graph/node/{id}`, `vgar://graph/subgraph/{id}`.
- Graph tool/resource calls are written to the MCP audit JSONL log.
- Backend metadata reports `demo` or `sqlite` dynamically.
- `scripts/smoke_w3_w4.py` validates LangChain MCP tool discovery and real tool invocation.

## Required validation on the project machine

```powershell
python -m pytest -q

$env:VGAR_GRAPH_BACKEND = "sqlite"
$env:VGAR_GRAPH_DATABASE = (Resolve-Path .\artifacts\sample_graph.db)
python .\scripts\smoke_mcp.py
python .\scripts\smoke_w3_w4.py
```

Expected gates:

1. M1 graph tests pass.
2. SQLite graph resource tests pass.
3. MCP exposes all three prefixed graph tools.
4. `graph_search_symbols` returns symbols from the SQLite graph.
5. callers/callees return stable VGAR contract payloads.
6. `logs/mcp_audit.jsonl` records graph tool/resource activity.

W5-W6 task grounding and graph-guided context retrieval are intentionally not added here.

## Addendum — 06/10/2026

The preceding sentence describes the earlier checkpoint, not current tool availability. W6 SQLite/MCP retrieval now uses a persistent task_handle; [MCP contract](mcp_tool_contract.md) and [completion](w5_w6_completion.md) supersede operational details.

Builder transaction/inventory/bindings/duplicate identities and shared source scope now have regressions. Repository/execution requires host workspace leases, uses common envelopes and the shared M2 pytest wrapper. Lease is not an OS sandbox.

Full recorder: `../artifacts/fixes/w3-w6/milestone-6-final-recorder/20261006T154059255443Z-54a8f6ac3e3a41308263d01880fd43f2.json`: 353 passed, 4 symlink privilege skips. Strict W3-W4 stdio/resource smoke passes in that suite; previous node/subgraph WARNs were fixed. No real model/benchmark repair in that suite. [PROGRESS](../PROGRESS.md) records RED/GREEN provenance and pending owner sign-off.
