# Review bàn giao các file bị ảnh hưởng — VGAR tuần 3–6

Ngày: **07/10/2026**. Reviewer: **Codex, tự review implementation**; không phải người review độc lập hoặc sign-off của M1/M2/M3.

Phạm vi: diff chưa commit so với HEAD `b39e0dbf87645d39b9a68e87b19d0655df264a05`, các module mới của kế hoạch fix tuần3–6 và những consumer trực tiếp. Không quét lại toàn bộ repo, không đánh giá research tuần1–2, model inference/fine-tuning, tuần7–16 hay hệ thống cũ. Không commit/push. Task environment bị người dùng loại trừ, không chạy Docker hoặc cài môi trường SWE-bench.

## 1. Các boundary đã đối chiếu

| Boundary | File chính đã đọc/diff | Điều đã kiểm |
|---|---|---|
| Builder → snapshot → retrieval | `src/vgar/graph/builder.py`, `retrieval.py`, `src/vgar/source_scope.py` | Transaction rollback; inventory cả file lỗi; IDs occurrence; scope thống nhất; raw-byte hash không bị bỏ |
| Archive → tree → graph cache | `evaluation/retrieval/graph_arm.py`, `graph_cache.py`, `worker.py` | Tree rebuild mới giữ cache cũ; link/marker/hash guards; cache key gồm profile/implementation/scope/parser; gold đọc ở SCORE sau ranking |
| Parent → worker → evidence | `evaluation/retrieval/lifecycle.py`, `evidence.py`, `scripts/run_graph_retrieval.py` | Deadline/RSS/phase; process-tree cleanup; terminal error/partial coverage; immutable resume forks; public-worker credential filter |
| Producer → scorer → comparator → report | `evaluation/retrieval/compare.py`, `report.py`, `scripts/compare_graph_vs_bm25.py` | Đọc đúng `arms`; cùng population/query/corpus/gold/budget/counter; full rank primary; capped sensitivity không repack; oracle F2P tách riêng |
| SQLite → MCP → ContextPayload | `graph/sqlite_store.py`, `sqlite_service.py`, `port.py`, `factory.py`, `demo_service.py`, `mcp/servers/graph_server.py`, `registry.py` | Source metadata/spans; persistent task_handle; không global last issue; stale/tampered snapshot fail closed; frozen data, diagnostics metadata |
| Host → repository/execution tools | `config/settings.py`, `mcp/workspace_guard.py`, `servers/repository_server.py`, `execution_server.py`, `mcp/tooling.py`, `agents/nodes/prepare.py`, `cli.py` | Host cấp lease; root/path guards; atomic exact edit; common envelope; shared M2 pytest evidence; source-root wiring cần regression cuối |
| Test recorder → source preflight | `repair/source_preflight.py`, `workspace.py`, `test_runner.py`, `evidence_writer.py`, `scripts/record_m2_test.py` | Pending trước setup, preflight có deadline, stdin không dùng MCP, trước/sau cùng scope, lỗi không gọi PASS |
| Scripts/docs consumers | Tokenizer acceptance, W3–4 scripted smokes, W5–6 context smoke, README/contract/ADR/DoD/vận hành | Không giả inference/repair success; no-Jedi primary benchmark được duyệt; environment và owner approvals không tick thay |

Các path rút gọn `evaluation/`, `graph/`, `repair/`, `mcp/`, `config/`, `agents/` thuộc `src/vgar/`. Đây là checklist boundary của affected changes, **không** tuyên bố mọi dòng/file trong repo đều được đọc lại. Regressions liên quan đã chạy trong full suite; evidence trước fix cuối ở [PROGRESS](../../PROGRESS.md).

## 2. Findings và quyết định

### Important — host-created snapshot chưa bind nguồn cho retrieval tools

Tại `src/vgar/cli.py` hàm `sandbox` và `src/vgar/agents/nodes/prepare.py` hàm `prepare_workspace`, code chỉ thay backend/database và workspace_root, nhưng kế thừa `graph.source_root`/`graph.version` từ settings của repo khác (hoặc source_root=None). `SQLiteGraphService.get_related_context` yêu cầu source root khớp snapshot; vì vậy W6 smoke explicit binding có thể PASS trong khi tool mới trong CLI/workflow không dùng được hoặc khởi động với version cũ.

**ĐÃ SỬA sau benchmark terminal:** thêm `tests/test_host_retrieval_binding.py`, bốn cases CLI/workflow × sourceNone/foreignsource-version; real index/copy/SQLite/retriever, không mock context hoặc LLM. [RED4failed](../../artifacts/fixes/w3-w6/host-source-binding/red/20261007T022822980290Z-56e0e1b5b2f0/result.json) xác định unbound source/foreign graph version; [GREEN24passed](../../artifacts/fixes/w3-w6/host-source-binding/green/20261007T022850657004Z-ab7bcbcda011/result.json). Hai host bind `graph.source_root=lease.path`, `version=None` cho DB vừa tạo; giữ pinned-tokenizer/fallback policy và original settings. Không đổi model/builder/scorer/defaultJedi/contract.

[Full recorder](../../artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json): **359 passed, 4 skipped**, test exit0/phaseDONE, pytest140,38s, wrapper144,980s; trước/sau source hash `518ded59bb8dac41faa33ce6ccc9a7c3d015a628f82576775f6293bb84e3ff10` giống nhau. Diagnostic fixture counter chỉ dành regression, không benchmark tokenizer. Hash guards vẫn từ chối stale-source sau patch; đây không automatic incremental reindex.

### Important — benchmark chưa đủ coverage và duplicate edge chưa sửa

[Dev25 terminal](2026-10-07-dev25-no-jedi-results.md) có **19success/6failures**, dưới ngưỡng20. `pylint6386` GraphValidationError duplicateedge ở BUILD_GRAPH là lỗi code còn mở; baSympy timeout ở PREPARE_RETRIEVAL và haiDjango WinError5 rename cần điều tra riêng. Theo user fail1-rule, dừng các task này, không retry/đổideadline/bỏvalidator/xóa denominator. Không gọi chúng là minors hoặc Graph đã thắngBM25; report/CI giữ đúng19pairs, oracle riêng. Đây là findings **chưa giải quyết** nên chưa đủ điều kiện nghiệm thu/merge theo plan.

### Minor / deferred — chi phí đọc graph và journal khi repo lớn

`src/vgar/graph/builder.py:219` lọc dictionary toàn cục để journal mỗi file; `sqlite_service.py` nạp document và reground để kiểm task_handle. Đây là đường có thể tốn CPU/RAM, **chưa được profiling để xác định tỷ lệ thời gian**. Không sửa bằng phỏng đoán, không đưa incremental graph/performance engineering tuần11–12 vào đợt này. Deadline, RSS và stage-level evidence hiện đã có để nhóm đánh giá sau.

### Giới hạn không được coi là lỗi đã sửa

- Jedi profile timeout0/3; no-Jedi primary là quyết định benchmark được người dùng duyệt, **không phải fix Jedi** hoặc chứng minh mọi CALLS resolve được. App vẫn bật Jedi mặc định.
- Graph retrieval có thể thua BM25, zero-hit hoặc nhiều anchor nhiễu. Đây là kết quả nghiên cứu phải báo, không đổi weights/scorer/gold theo final measurements để gọi PASS.
- Lease là capability policy, không OS sandbox. External pytest thực thi code trên host. MCP chỉ lọc các secret keys được liệt kê; không chứng minh mọi secret trong environment/filesystem đều bị chặn. Public retrieval-worker filter rộng hơn nhưng cũng không phải security proof.
- App CLI không có selector vẫn có thể trả exit0 mà không independent pytest; README đã giải thích, không coi đó là repair validation. Task đợt này không nghiệm thu real-model repair.
- Chủ quyền sign-off của các thành viên và environment readiness không được thay bằng unit/fixture PASS.

## 3. Declined to judge / ngoài scope

1. Chất lượng planner/coder và fine-tuning: ngoài tuần3–6, inference NOT_RUN.
2. Environment50–100/smoke3: người dùng loại khỏi đợt này, giữ trạng thái NOT_RUN.
3. CFG/PDG/deep data flow/GraphDiff/incremental rebuild: không thuộc plan fix tuần3–6; unavailable_features phải báo đúng.
4. Merge/publication: người dùng chưa cho commit/push; không thay branch/index.
5. Runtime semantics của dynamic Python hoặc class conditional ambiguous: không suy ra chắc chắn từ static graph; unresolved phải giữ.

## 4. Handoff / approvals thực sự

| Owner | Cần review | Trạng thái |
|---|---|---|
| M1 | Definition identities/failed-file inventory; source scope; qualified-name + span mapping; no-Jedi quality limitations | **Chờ owner** |
| M2 | Base-patch labels, eligible denominators; primary full-rank/packed policy; ERROR vs FAIL evidence; manual audit kết quả thật | **Chờ owner** |
| M3 | Lease/envelope consumers; `task_handle` input mới với stateless client; source/tokenizer host bindings; resource IDs | **Chờ owner** |

Người dùng đã duyệt **task_handle** và **no-Jedi benchmark chính**; đó là quyền triển khai, không tự gán là tất cả owners đã ký. ADR: [identities](../adr/2026-10-06-graph-transactions-and-definition-identities.md), [task handles](../adr/2026-10-06-stateless-task-handles-and-context-boundary.md).

## 5. Verdict hiện tại

**Self-review affected files đã hoàn tất; chưa đủ điều kiện đóng DoD/merge.** Host binding có RED→GREEN + full suite359passed/4skipped; [manual10](2026-10-07-manual-retrieval-audit-10.md) đã hoàn tất self-audit. Dev25 chỉ19validpairs/6failures, duplicateedge/permission/timeout còn mở; owner sign-off chưa có. Không fresh/independent reviewer, đánh giá tự review yếu hơn và được nêu rõ. Không destructive operations, không bỏ guards/overwrite dirty code, không commit/push. Task môi trường bị loại trừ không bị đánh dấu PASS.
