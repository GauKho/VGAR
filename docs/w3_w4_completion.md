# W3-W4 Completion — Graph MVP + MCP/LangChain Connectivity

This checkpoint closes the required W3-W4 scope without changing M1 graph-construction logic.

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
