# TV2 · Nối layer 1–3 vào layer 4–6 theo hướng dẫn build-server: báo cáo chạy (11–12/11/2026)

Spec: `docs/superpowers/specs/2026-11-11-tv2-layer-integration-design.md`. Plan: `docs/superpowers/plans/2026-11-11-tv2-layer-integration.md`. Ledger: `.superpowers/sdd/2026-11-11-tv2-layer-integration/progress.md`. Code TV1/TV3 lấy từ commit gộp `ea4d6fac`. Chưa commit phần mới (người dùng tự commit).

## Kết quả

**Mọi tool và resource của proposal §10.2/§10.3 trên graph server chạy được bằng graph thật theo kiểu hướng dẫn build-server** (hàm `@mcp.tool()` gọi thẳng code layer 1–5), không cần context do host ký. Không còn backend giả `demo`.

| Tool / resource | Chạy bằng | Trước đợt này | Sau | Test |
|---|---|---|---|---|
| `search_symbols`, `find_task_anchors`, `get_related_context`, `analyze_patch_impact`, `get_related_tests` | `SQLiteGraphService` | ✅ | ✅, graph nạp một lần cho mỗi version | `test_tv2_integration_service.py` |
| `get_callers` / `get_callees` `depth=1` | `SQLiteGraphService` | ✅ | ✅ không đổi | `test_get_callers_depth_one_is_unchanged` |
| `get_callers` / `get_callees` `depth>1` | `traverse` (MAY_CALL trả riêng) | ❌ `CAPABILITY_UNAVAILABLE` | ✅ | `test_traverse_*`, `test_get_*_depth_two_*` |
| `explain_dependency_path` | `explain_dependency_path` | ❌ | ✅ | `test_path_*` |
| `verify_patch_graph_constraints` | `patch_evidence.verify_patch` (schema, structural, API, import cycles, IM-1 `port_check`) | ❌ cần context | ✅ | `test_tv2_patch_evidence.py` (Task 5) |
| `run_relevant_tests` (execution server) | `patch_evidence.run_patch_tests` (chọn test theo graph, chạy trên bản copy trước/sau patch) | ❌ cần context | ✅ | Task 6 |
| `rank_patch_candidates` | `patch_evidence.rank_candidates` (evidence 9 trường, `score(patch)` §8.5) | ❌ cần context | ✅ | Task 7 |
| `build_or_update_graph` | `GraphJobController` của TV1 (worker gọi `IncrementalGraphBuilder` của TV2) | Tool ghi, cần grant | Giữ nguyên | — |
| `vgar://repo/summary`, `graph/node`, `graph/subgraph` | `SQLiteGraphService` | ✅ | ✅ | `test_resources.py` |
| `vgar://repo/schema` | `schema_description()` (SC-1) | ❌ | ✅ | `test_schema_resource_is_the_sc1_description` |
| `vgar://component/{id}` | G_arch: `component, files, public_ports, dependencies, dependents, tests, risk` | ❌ | ✅ | `test_component_has_the_proposal_keys_and_real_values` |
| `vgar://task/{id}` | overlay của `find_task_anchors` | ❌ | ✅ | `test_task_*` |
| `vgar://evidence/baseline` | fingerprint graph; test/invariant `NOT_RUN` | ❌ | ✅ | `test_baseline_marks_tests_and_invariants_not_run` |
| `vgar://audit/log` | audit TV1 | ✅ cần context | ✅ không đổi | `test_audit_resource_still_needs_trusted_context` |
| `get_related_context` + lịch sử L4-1 | `read_commit_history` tới revision của graph (mặc định tắt) | ❌ | ✅ | `test_history_*` |

Khi host đăng ký provider của TV1/TV3 thì server vẫn đi đường cũ (`test_registered_traversal_provider_still_wins`, và các test provider hiện có của TV1/TV3).

## Kiểm theo hướng dẫn và plan (spec §9)

- **Chỉ dữ liệu thật:** `VGAR_GRAPH_BACKEND=demo` bị từ chối; thiếu `VGAR_GRAPH_DATABASE` hoặc file không tồn tại thì báo lỗi khi khởi động (`test_tv2_real_backend.py`). Envelope của các tool có `backend = "sqlite"`.
- **Không ghi stdout:** `test_tv2_no_stdout.py` (module mới không có `print`; gọi các tool kiểu hướng dẫn không ghi gì ra stdout).
- **Graph fixture qua validate schema:** `test_fixture_graph_passes_schema_validation`.
- **Chạy tay qua stdio** (client MCP có sẵn của repo, SDK 1.30):
  - `python -m vgar.cli index tests/fixtures/w7_w8_handoff/multi_file_invoice/repo --db <tmp>/invoice.db` → 23 node.
  - Bật graph server với `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_GRAPH_DATABASE`, `VGAR_REPOSITORY_ROOT`: liệt kê đủ 11 tool `graph_*`; `search_symbols("invoice_total")` trả symbol thật; `get_callers(discounted_price, depth=2)` → 4 symbol hop 1–2; `explain_dependency_path(invoice_total → discounted_price)` → `CONTAINS, CALLS`; `verify_patch_graph_constraints(<reference patch>)` → `PASS` (schema, structural, api, source_imports, port_check `PASS`; fanout `NOT_RUN`). Mọi kết quả `backend = sqlite`.
- **Chưa chạy (cần môi trường SDK2 của TV1, giao TV1):** Inspector CLI `--protocol-era modern/legacy`, nối Claude Desktop / Claude Code thật.

## Suite

- Baseline (trước đợt này, trên `ea4d6fac`): 38 fail / 3.597 pass, toàn lỗi đã biết (thiếu MCP SDK2 `mcp.Client`/`mcp_types`; Docker; 3 lỗi có sẵn trên HEAD).
- Mốc sau Task 4: 32 fail / 3.637 pass; sau Task 7: 32 fail / 3.658 pass; **0 lỗi mới** so với baseline. 6 lỗi JARVIS/Joern của baseline nay qua vì Docker đã bật trên máy.
- Lượt cuối: xem dòng cuối của ledger.

## Độ lệch có lý do (đưa nhóm chốt)

- **H4, chữ ký tool:** tool đọc không nhận `repo_path` (repo do backend cấu hình); `find_task_anchors`/`get_related_context` có `graph_version`, `task_id`; giới hạn dùng `max_nodes` / `max_hops`.
- **H5, xác nhận thao tác ghi:** theo hướng dẫn, host hỏi người dùng trước khi gọi tool; tool ghi (`build_or_update_graph`, `run_relevant_tests`, `apply_patch`) tách khỏi tool đọc; grant của TV1 vẫn còn.
- **H3, MAY_CALL:** callers/callees giữ danh sách chính chỉ CALLS; MAY_CALL trả riêng trong `may_call`.
- **H10, trọng số:** tạm theo pilot TV3 (`configs/mcp_server/ranking_weights.json`).
- Test cũ của TV1 đổi theo spec §7.2: `test_depth_one_payload_is_legacy_but_depth_two_cannot_lie` (depth 2 nay `PASS`), hai test resource cần context (nay 4 resource đồ thị đọc được không cần context; audit và context giả vẫn bị từ chối).

## Bàn giao

- **TV1:** Inspector modern/legacy và Claude Code thật; runbook đã đổi lệnh `demo` sang `vgar index` + `VGAR_GRAPH_DATABASE` (script preflight/smoke/check_runtime nhận DB từ môi trường); L6-6 theo §11.2; backend `snapshot` với document SC-1 đầy đủ; phát hiện prompt injection.
- **TV3:** L4-2/3/5/6/7, L5-1/3, fanout (EV-2), §12.3 field schema/OpenAPI, §12.4, V1 trên bộ dev, EV-3 qua Docker.
- **Môi trường:** đã cài `dulwich==1.2.18` (extra `history`) vào `.venv` để chạy lịch sử commit.

## Lệnh tái tạo

```bash
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tv2_real_backend.py tests/test_tv2_integration_service.py \
  tests/test_tv2_patch_evidence.py tests/mcp_server/test_tv2_guide_routing.py tests/mcp_server/test_tv2_no_stdout.py
python -m vgar.cli index <repo> --db <graph>.db
VGAR_GRAPH_BACKEND=sqlite VGAR_GRAPH_DATABASE=<graph>.db VGAR_REPOSITORY_ROOT=<repo> python -m vgar.mcp.servers.graph_server
```
