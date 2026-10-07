# MCP contracts — tuần 3–6, cập nhật 06/10/2026

Nguồn sự thật: src/vgar/mcp/servers/, mcp/tooling.py và contracts/. Client dùng tool_name_prefix; MCP stdio dùng cùng sys.executable của host.

## Envelope chung

```json
{"status":"PASS","data":{},"error":null,"metadata":{"duration_ms":0,"request_id":"unique-request","backend":"sqlite","tool":"find_task_anchors"}}
```

Vocabulary PASS/FAIL/ERROR/NOT_RUN, không tự dùng WARN. Query PASS chỉ là call thành công (có thể empty), không repair PASS. ERROR có data=null và error code/message/details; verification FAIL giữ data. Execution ERROR có full TestRunResult trong error.details/artifact. Metadata cho diagnostics; context.data vẫn extra=forbid.

Ba server có audit request/status/duration/error/counts. Không audit old/new patch text hoặc nguyên issue trong anchor call; evidence/stdout vẫn cần review secrets trước chia sẻ. Resources trả document trực tiếp, failures là protocol errors, không tool envelope.

## Graph tools (5)

| External name | Input | data khi PASS | Giới hạn |
|---|---|---|---|
| graph_search_symbols | query:str, limit:int=20 | query, limit, symbols[] | service kiểm limit |
| graph_get_callers | symbol_id:str, depth:int=1 | symbol_id, depth, callers[] | chỉ depth=1, khác → INVALID_LIMIT |
| graph_get_callees | symbol_id:str, depth:int=1 | symbol_id, depth, callees[] | chỉ depth=1, khác → INVALID_LIMIT |
| graph_find_task_anchors | issue_text:str, failing_tests:list[str] hoặc null | grounding diagnostics, graph_version, task_handle, anchor_ids | issue không rỗng ≤64KiB; reports≤100, mỗi report không rỗng ≤8KiB |
| graph_get_related_context | anchor_ids:list[str], budget_tokens:int, task_handle:str | frozen ContextPayload | budget dương; anchors thuộc task; valid snapshot/source/counter |

```text
issue → find_task_anchors → task_handle + anchor_ids
                 session mới ↓
get_related_context(anchor_ids, 8000, task_handle)
                             ↓
ToolResponse.data = ContextPayload → display
```

Handle vgar-task:<sha256> bind graph_version/issue/reports, persist SQLite; không global last issue. Service kiểm lại hash/anchors. Handle immutable, quota10000 contexts, hết quota báo lỗi không tự purge. Snapshot đổi → GRAPH_NOT_READY; handle đúng format nhưng không tồn tại → NODE_NOT_FOUND; sai format/hash hoặc anchor không thuộc task → INVALID_QUERY; budget sai → INVALID_LIMIT. Lỗi ngoài taxonomy → INTERNAL_ERROR, đọc audit/trace để debug.

Host bind VGAR_GRAPH_BACKEND=sqlite, VGAR_GRAPH_DATABASE, VGAR_GRAPH_SOURCE_ROOT, VGAR_TOKENIZER_MANIFEST. Source phải khớp inventory/hash/scope. VGAR_ALLOW_FALLBACK_COUNTER=1 chỉ diagnostic fixture, không benchmark. Demo retrieval → GRAPH_NOT_READY. Legacy snapshot thiếu language/byte spans phải ingest mới; không thêm schema_version hoặc thay frozen graph/context.

Metadata context: task_handle, overlay_id, counter_label, retrieval_diagnostics (omissions, unavailable_features, traversal_limited, config). Token budget chỉ snippets, không toàn prompt. Failing reports dùng Test + Issue/REPRODUCES, không proof tests chạy; benchmark graph_f2p dùng FAIL_TO_PASS là oracle-assisted, tách issue-only graph.

## Repository/execution tools (5)

| External name | Inputs | data/điều kiện |
|---|---|---|
| repository_health | none | server, phase, workspace_bound; không cần lease |
| repository_read_file | repo_path:str, path:str | path, content UTF-8; file≤16MiB |
| repository_apply_patch | repo_path:str, path:str, old_text:str, new_text:str | status/path/patch_diff/changed_files hoặc reason; exact unique nonempty edit≤1MiB mỗi text, output file≤16MiB |
| execution_health | none | server, phase, workspace_bound; không cần lease |
| execution_run_pytest | repo_path:str, selector:str, timeout_seconds:int=30 | status/selector/test_result/artifact_path/exit_code/stdout/stderr/reason; 0<timeout≤240s |

Host cấp VGAR_WORKSPACE_ROOT disposable lease. Chặn root khác, traversal, symlink/junction/reparse; không để model cấp lease qua input. Đây không phải OS sandbox; external pytest có thể chạy host code. apply_patch là một exact edit atomic có stale-source check, không universal unified-diff executor; mismatch → FAIL/PATCH_APPLY_FAILED.

Execution gọi repair/test_runner.py, stdin=DEVNULL, capture command/duration/stdout/stderr/JUnit/case counts/timeout. Evidence `<VGAR_MCP_AUDIT_LOG parent>/m2-tool-runs/`. Test failure → FAIL; collection/no tests/timeout/runner errors không PASS. Fingerprint shared scope, không semantic proof.

## Resources, tests

- vgar://repo/summary
- vgar://graph/node/{node_id}
- vgar://graph/subgraph/{node_id}, resource depth cố định2, không caller multi-hop

Encoded IDs thử raw trước, chỉ unquote một lần sau NODE_NOT_FOUND. Literal % ID nếu tồn tại không bị sửa.

scripts/smoke_w3_w4_full.py --strict-resources kiểm W3–4; scripts/smoke_w5_w6.py --tokenizer-manifest <path> kiểm SQLite→MCP→LangChain display không model/gold. Tests: test_w5_w6_retrieval_mcp.py, test_mcp_workspace_guard.py, test_mcp_stdio_smoke.py. [Vận hành](m5_m6_retrieval_evaluation.md), [ADR](adr/2026-10-06-stateless-task-handles-and-context-boundary.md), [PROGRESS](../PROGRESS.md). Technical PASS không thay owner sign-off.
