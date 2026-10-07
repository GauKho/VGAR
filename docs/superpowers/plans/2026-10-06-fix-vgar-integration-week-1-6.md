# Kế hoạch sửa lỗi tích hợp VGAR — phạm vi tuần 3–6

> **Hướng dẫn cho phiên triển khai:** Chỉ bắt đầu khi người dùng xác nhận. Dùng `superpowers:executing-plans`, `superpowers:test-driven-development`, `superpowers:systematic-debugging` và `superpowers:verification-before-completion`. Triển khai trực tiếp từng milestone; không tự spawn agent, commit hoặc push. Chỉ tick khi có bằng chứng kiểm thử mới.

**Trạng thái:** `APPROVED / PARTIAL_HANDOFF` — milestone 1–7 có evidence; lỗi host source/version binding đã sửa và full suite mới nhất **359 passed / 4 skipped**. Ngày 07/10 người dùng duyệt `--no-jedi` làm profile chính: pilot **3/3 SUCCEEDED**; dev25 đã kết thúc với **19 thành công, 6 lỗi**, comparison có **19/25 valid pairs**, dưới ngưỡng tối thiểu 20 nên gate benchmark chưa đạt. Báo cáo metric/CI, manual10 self-audit và affected-files self-review đã hoàn tất; không thay owner sign-off. Environment50–100/smoke3 bị loại trừ. Sáu task lỗi dừng theo quy tắc fail một lần, không retry ngầm. Xem PROGRESS, [kết quả dev25](../../reviews/2026-10-07-dev25-no-jedi-results.md) và [báo cáo task chưa hoàn thành](../../BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md).

**Điều chỉnh theo người dùng:** Tuần 1–2 là research, không yêu cầu tích hợp vào VGAR và không được ghi là task chưa hoàn thành của repo. Kế hoạch này chỉ sửa lỗi/hoàn thiện tích hợp tuần 3–6. Giữ tên file cũ để không làm hỏng các liên kết đã chia sẻ.

**Cập nhật sau đợt mở lại07/10 (ưu tiên hơn checkpoint19/25 ở trên):** suitecode365passed4skip; Pylint duplicate inheritance fixed; overlay/worker selective ownership cófullbase/deltavalidation vàpublicsnapshot isolation. Newrun25 `20261007T114731162059Z-f27e07ec6a8b`23success2WinError5; comparison `20261007T122342844612Z-12c751a0b3f6`23pairs COMPARED_PARTIAL. Minimum20đã có, **Gate8.4 target25 vẫn unchecked**, không thay yêu cầu/population. ColdSympy2timeouts giữriêng; Jedi/directWindowsrename methods đã lỗi lặp thìdừng, ownersreview cònchờ. Theo [hướng dẫn hiện tại,mục6](../../GIAI_THICH_VGAR_TRUOC_SAU_FIX_TUAN_3_6_VA_CACH_KIEM_THU.md); PROGRESS lưusource/evidence/methods. Không commit/push/mởscope hayrerunwholeaudit.

**Mục tiêu:** Khắc phục lỗi ở ranh giới M1/M2/M3, hoàn thiện grounding/context qua MCP và tạo bằng chứng nghiệm thu retrieval đến hết tuần 6.

**Kiến trúc giữ nguyên:** Python graph builder + SQLite; API grounding/retrieval của M1; BM25, gold mapping và shared scorer của M2; MCP stdio/LangChain của M3. Không viết lại hệ thống.

**Stack:** Python theo pyproject hiện tại; Tree-sitter, Jedi, SQLite, Pydantic, pytest, MCP SDK và LangChain adapters. Retrieval dùng tokenizer đã pin, không cần model weights/GPU.

**Căn cứ:** [Báo cáo review và danh sách lỗi](../../reviews/2026-10-06-review-vgar-week-1-6.md), [project_plan_16_weeks.md](../../../../New_task/project_plan_16_weeks.md), [Contract Freeze](../../../../New_task/VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md).

## 1. Phạm vi và nguyên tắc

- Chỉ sửa `D:\Project\CAPSTONES\VGAR`, yêu cầu tích hợp tuần 3–6. Không sửa `vgar_mcp_mvp`, `VGAR-main`, `M2_week_5_6`, Archify hoặc plan đã đóng băng.
- Không tạo/tích hợp literature matrix, research design, research sign-off hoặc sửa model inference để hoàn thành tuần 1–2. Giữ schema/contract và tokenizer/config evaluation hiện có làm đầu vào cho tuần 3–6; không coi tài liệu research ngoài repo là lỗi tích hợp.
- Trước khi triển khai: kiểm tra Git status/diff/checkpoint mới; giữ thay đổi chưa commit. Không làm lại guards đã có.
- Giữ frozen `ContextPayload`, vocabulary PASS/FAIL/ERROR/NOT_RUN và semantics của `graph_version`. Không thêm public `schema_version`.
- Giữ ID các entity không bị duplicate. Nếu phải thay identity cho duplicate, ghi ADR, kiểm tra mapping M2 và invalidate cache liên quan.
- Không tự thêm node type FailingTest: giải thích mapping failing-test report → Test/Issue/REPRODUCES hiện có; cần owner/consumer review.
- Developer patch/gold chỉ dùng trong evaluator, không đưa vào query, grounding hoặc ranking. `graph_f2p` dùng FAIL_TO_PASS phải được ghi riêng là oracle-assisted.
- Giữ dev25 manifest/split và dataset revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`; không mở held-out để tune.
- Giữ tokenizer `Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554`; snippet budget 8.000 token. Snippet budget không đồng nghĩa tổng context của LLM.
- Không tải weights, chạy inference hoặc fine-tune trong đợt sửa này. Không bỏ validator/hash check để làm kết quả xanh.
- Không xóa hàng loạt cache/results hoặc ghi đè artifact cũ. Mỗi lần kiểm thử tạo evidence mới.
- Không gọi timeout/interrupted là PASS. Lưu argv, stdout/stderr, exit code, duration, config, source hash và trace khi có lỗi.
- Không mở rộng sang full repair, GraphDiff, incremental graph, impact analysis hay tuần 7–16.

## 2. Thứ tự triển khai và ownership

| Milestone | Nội dung | Phối hợp | Gate |
|---|---|---|---|
| 1 | Producer/comparator và semantics báo cáo | M2 + M3 | Shape từ runner thật được chấp nhận; dữ liệu sai bị từ chối |
| 2 | Graph transaction, snapshot, bindings và identities | M1 + M2 | Các fixture rollback/conditional/duplicate/inheritance đạt |
| 3 | Source scope, workspace và recorder | M1 + M2 + M3 | Cache không lẫn source; package thật vẫn được giữ |
| 4 | MCP workspace guard và test evidence | M2 + M3 | Chặn root sai trước write/exec; thống nhất envelope |
| 5 | Cache integrity và lifecycle evaluation | M1 + M2/M3 | Tamper bị phát hiện; timeout/OOM có artifact cuối |
| 6 | Retrieval MCP và LangChain display flow | M1 + M3 | Issue → anchors → context → display qua transport thật |
| 7 | Hướng dẫn vận hành và tài liệu tích hợp tuần 3–6 | Cả nhóm; M3 điều phối | Hướng dẫn/config/evidence paths đúng code, không thêm research tasks |
| 8 | Paired evaluation, manual audit và bàn giao | Cả nhóm | 20–30 paired task, metric/token cost và 10 task kiểm tra thủ công |

Ước lượng kỹ thuật: **5–9 ngày làm việc**, tùy edge cases và phối hợp interface. Chưa tính chuẩn bị/chạy 50–100 môi trường SWE-bench. Đây không phải cam kết Graph sẽ tốt hơn BM25 hoặc benchmark chạy xong trong vài phút.

Milestones 1–6 ưu tiên lỗi kỹ thuật. Milestone 7 cập nhật tài liệu vận hành của chính các thay đổi đó. Milestone 8 chỉ chạy sau gates trước đó; phê duyệt thay đổi contract hoặc benchmark vẫn cần nhóm/leader khi phát sinh.

## 3. File map dự kiến

Các đường dẫn không bắt đầu bằng `src/` hoặc `tests/` trong bảng đều tương đối với nhóm được nêu. Đây là bản đồ dự kiến, không phải yêu cầu sửa mọi file.

| Nhóm | File hiện tại hoặc file dự kiến |
|---|---|
| Comparison | `src/vgar/evaluation/retrieval/compare.py`, `report.py`; `scripts/compare_graph_vs_bm25.py`; `tests/m2/test_graph_arm.py`; mới `tests/m2/test_retrieval_compare_contract.py` |
| Graph | `src/vgar/graph/builder.py`, `retrieval.py`; tests builder/retrieval/anchors/overlay và `tests/m2/test_retrieval_scoring.py` |
| Source scope | Mới `src/vgar/source_scope.py`, `tests/test_source_scope.py`; consumers builder/retrieval/workspace/runtime và `scripts/record_m2_test.py` |
| MCP boundary | `src/vgar/mcp/servers/repository_server.py`, `execution_server.py`; client/tooling, settings, CLI và prepare node; mới `tests/test_mcp_workspace_guard.py` |
| Cache/lifecycle | `src/vgar/evaluation/retrieval/graph_arm.py`, `evidence.py`; `scripts/run_graph_retrieval.py`; mới worker và tests cache/lifecycle |
| Retrieval MCP | `src/vgar/graph/port.py`, `sqlite_service.py`, `demo_service.py`, `factory.py`; Graph MCP/registry; mới `scripts/smoke_w5_w6.py`, `tests/test_w5_w6_retrieval_mcp.py` |
| Settings tích hợp | `src/vgar/config/settings.py` chỉ khi cần workspace lease/MCP wiring tuần 3–6; không sửa model inference loader trong đợt này |
| Tài liệu vận hành | `docs/m5_m6_retrieval_evaluation.md`, `docs/w5_w6_completion.md`, README, MCP contract/ADR liên quan trực tiếp và `PROGRESS.md` |

Nếu tên file test dự kiến chưa tồn tại, tạo test ở module phù hợp; không đổi kiến trúc chỉ để khớp bảng.

## 4. Milestone 1 — Comparator đọc đúng producer, báo cáo công bằng

**Liên quan:** F01, F08, R03, R04.

**Interface dự kiến:** Giữ `compare_runs(...)` trả thư mục/record; validator đọc summary `arms: dict[str, dict]` của Graph runner. `cap=None` cho primary BM25 full-rank; cap dương là sensitivity riêng. Không sửa raw run cũ.

- [x] Viết regression dùng **serializer của runner thật**, không tự thêm `arm='graph'`; một task có hai arms `graph`/`graph_f2p` phải được xử lý đúng.
- [x] Test reject BM25-as-Graph, missing arms/artifacts, duplicate task IDs, khác query/corpus/base commit/patch hash/gold identity/dataset/scorer/counter/budget/snippet policy.
- [x] Test zero paired tasks không được thành công; partial pairs báo attempted/succeeded/failed/skipped và denominator từng metric.
- [x] Chạy tests mới trước sửa để ghi RED; lỗi phải có message cụ thể.
- [x] Sửa validator/serialization, giữ các fairness guards đúng hiện có.
- [x] Tách full-rank BM25, capped-rank sensitivity và packed coverage/token cost. Không dùng một cột khiến người đọc hiểu packed cũng bị cap khi chưa repack.
- [x] Chọn rank-only sensitivity, không chọn capped-system/repack; CLI không ngầm dùng cap 100, báo cáo đọc max_candidates từ Graph config.
- [x] Gắn nhãn issue-only vs oracle-assisted F2P; không gộp claim.
- [x] Chạy comparison/scoring tests, lưu JSON và cập nhật checkpoint.

Lệnh kiểm thử dự kiến:

```powershell
python -m pytest tests/m2/test_graph_arm.py tests/m2/test_retrieval_compare_contract.py -q
```

**Gate:** Summary thật được so sánh, malformed/zero-pair không báo thành công giả; raw artifact không bị thay đổi.

## 5. Milestone 2 — Graph transaction, snapshot và symbol bindings

**Liên quan:** F03, F06, F09, F10.

**Interfaces:** Giữ `PythonGraphBuilder.build(repository_root)` và `GraphContextRetriever.retrieve(...)`. Thêm inventory nội bộ ở `document['statistics']['source_inventory']`: relative path → raw content hash, gồm failed files. Failed file không được tạo fake retrievable entities.

- [x] Test induced extraction failure: retrieval ở file tốt vẫn chạy; sửa bytes của failed file sau build vẫn gây snapshot mismatch; thêm/xóa file thật vẫn bị phát hiện.
- [x] Test rollback xóa đủ state: nodes, edges, symbols, classes, calls, scopes; không còn dangling ID trong `symbols_by_qualified_name`.
- [x] Test `from pkg.base import A; class A(A)`: resolve tới imported base nếu có đủ bằng chứng, không tạo self-loop. Ambiguous/dynamic base giữ unresolved diagnostic.
- [x] Test conditional definitions, duplicate class/function và nested scope: distinct deterministic ID/source range; mapping M2 đúng occurrence.
- [x] Test setter detector: nhận `@x.setter`, không nhận `@app.get(...)`, `@pytest.mark.parametrize` hoặc deleter thành setter.
- [x] Ghi RED rồi sửa transaction, traversal compound bodies, binding-aware inheritance và setter rule; giữ missing-module guards đã có.
- [x] Retriever so full inventory/hashes thay vì coi known failed files là newly added. **Không bỏ snapshot validation.**
- [x] Chạy tests builder/retrieval/anchors/overlay/adapter; đối chiếu schemas và ID continuity.
- [x] Ghi ADR cho failed-file inventory/duplicate identities; automated M2 consumer occurrence-mapping tests.
- [ ] Sign-off ADR của M1 owner/M2 consumer trong nhóm (không tự ghi phê duyệt thay).

Các nhóm test: `tests/test_graph_builder*.py`, `tests/test_graph_retrieval.py`, `tests/test_task_anchors.py`, `tests/test_task_overlay.py`, `tests/m2/test_retrieval_scoring.py`. Trên PowerShell, liệt kê explicit các builder test nếu wildcard không được pytest mở rộng.

**Gate:** Không còn rollback → whole-task snapshot failure hoặc inherited self-loop; gold coverage/denominator không bị thay đổi để làm số đẹp.

## 6. Milestone 3 — Source scope và preflight có giới hạn

**Liên quan:** F04, F05.

**Interfaces dự kiến:** `SourceScope(excluded_paths: tuple[str, ...] = ())`; discovery prune directories trước descent. Builder, retriever, workspace và fingerprint dùng cùng scope của run.

- [x] Test VGAR operational cache không bị index/copy/hash; generic repository có package thật tên `data` vẫn giữ source.
- [x] Test scope builder/retriever nhất quán và thay đổi source thật vẫn được phát hiện.
- [x] Test recorder tạo pending evidence **trước** discovery/hash; preflight timeout/error được finalize, không chờ vô hạn trước pytest.
- [x] Sửa profile VGAR loại đúng `data/downloads`, `data/gold`, `data/graphs`, `data/repositories`, `results`, `artifacts`, `logs` và temp/generated paths đã biết.
- [x] Không blanket-ignore mọi `data/`/`results/` của mọi repo; không chỉ index `src` rồi mất TESTS edges.
- [x] Không tăng size limits để né lựa chọn source sai. Giữ symlink/path policy hiện có.
- [x] Chạy scope/workspace/baseline/evidence tests; chạy recorder full suite vào evidence directory mới để kiểm preflight và source hash.

Lệnh dự kiến:

```powershell
python -m pytest tests/test_source_scope.py tests/m2/test_workspace.py tests/m2/test_baseline.py tests/m2/test_evidence_writer.py -q
```

**Gate:** Source target không trộn source benchmark; recorder có pending → final và thời hạn rõ ràng.

## 7. Milestone 4 — MCP dùng đúng workspace và M2 runner

**Liên quan:** F11; yêu cầu bảo vệ source/contract từ tuần 3–4.

**Interfaces dự kiến:** Settings có leased workspace root, truyền qua `VGAR_WORKSPACE_ROOT` do host quản lý. Root tool args phải khớp lease. Giữ tool signatures nếu được; output thống nhất `ToolResponse`, cập nhật consumers cùng milestone.

- [x] Test patch vào synthetic-original thay vì leased workspace bị từ chối **trước khi ghi**; bytes gốc không đổi.
- [x] Test execution root/selector ngoài lease, stale lease và symlink/reparse; real symlink cases skip khi máy không cho tạo.
- [x] Khi chưa bind workspace: health/list tools được, read/write/exec không có quyền phải trả structured error theo capability policy.
- [x] Test common envelope/audit cho tất cả tools; không để health/read dùng status `OK` ngoài frozen vocabulary.
- [x] Test timeout/output/JUnit evidence qua MCP dùng M2 `repair.test_runner.run_tests`, không subprocess runner thứ hai.
- [x] Ghi RED; wire CLI/prepare/client/settings và server guard; graph DB read-only root tách khỏi write lease.
- [x] Cập nhật scripted agent/smoke để đọc `data` trong envelope; automated consumer tests. Parser transport giữ nguyên vì đã preserve envelope.
- [ ] Consumer sign-off của nhóm cho lease/envelope behavior (không tự ghi thay).
- [x] Chạy MCP contract/parser/settings/workflow tests và stdio fake-agent smoke; lưu transcript, patch, audit và hashes. Hai Graph resource warnings vẫn còn, xử lý milestone 6.

**Gate:** Không write/exec ngoài leased workspace; envelope và test evidence nhất quán.

Đây là guard capability và contract, **không phải OS/container security sandbox**. Chạy pytest của repo không tin cậy vẫn có thể thực thi arbitrary code trên host.

## 8. Milestone 5 — Cache integrity và evaluation lifecycle

**Liên quan:** F07, F12, R01.

**Interfaces dự kiến:**

- Reuse extracted tree phải kiểm file set/hash hiện tại; marker repo/SHA chưa đủ.
- Cache key gồm raw tree hash, builder/resolver/schema hashes, source-scope/config và phiên bản parser/resolver. Kiểm graph JSON/meta pair khi reuse.
- Worker subprocess xử lý một task; parent quản lý timeout, exit, stage/trace và finalize artifact.
- CLI thêm `--task-timeout-seconds` (đề xuất 300), `--resume-run`, `--task-id`; resume phải khớp manifest/config/source fingerprint.

- [x] Test tree/cache tamper, same-size corruption, resolver/schema/scope/parser identity và interrupted cache write.
- [x] Test synthetic worker timeout/crash/MemoryError: terminal artifact đúng, không để run ghi RUNNING vô hạn khi parent còn sống; xử lý process tree trên Windows.
- [x] Test resume mismatch bị từ chối; successes giữ nguyên, failure retry tạo attempt mới trong run nối tiếp; reject duplicate IDs/invalid limits.
- [x] Fingerprint recursive tests/m2, tests/unit, fixtures và config/lock; không đưa archive/weights vào code digest.
- [x] Emit phases LOAD_SOURCE/EXTRACT_TREE/BUILD_GRAPH/GROUND/RETRIEVE/SCORE/WRITE, full traceback, durations và RSS (worker + parent-observed tree).
- [x] Tạo pending evidence trước setup tokenizer/manifest; finalize setup errors và KeyboardInterrupt.
- [x] Triển khai isolation đủ cho retrieval tuần 6; không kéo incremental graph/large performance suite tuần 11–12 vào task.
- [x] Không tối ưu deep copies khi chưa có đo benchmark; giữ immutable snapshot/caller-mutation tests, không dùng global mutable graph.
- [x] Chạy cache/lifecycle/dataset/token-counter tests và full suite 333 passed/4 skipped; chưa chạy 25 task ở milestone này.

**Gate:** Cache sai bị phát hiện, task lỗi có diagnostic xác định stage; resume không trộn cấu hình khác.

## 9. Milestone 6 — Retrieval tools và display flow qua MCP

**Liên quan:** F02, R02, R05.

**Interfaces mục tiêu:**

- `find_task_anchors(issue_text, failing_tests=None) -> ToolResponse`: anchors, graph version và ambiguity/unmatched diagnostics.
- `get_related_context(anchor_ids, budget_tokens, task_handle) -> ToolResponse`: shared `ContextPayload`; diagnostics trong metadata/sidecar. Người dùng đã duyệt thêm task_handle và giữ client stateless; không đổi fields của frozen payload.
- Required tool names: `graph_find_task_anchors`, `graph_get_related_context`; giữ ba graph tools/resources hiện có.

- [x] Test stable anchors/context, invalid IDs/budget, stale snapshot, no-anchor/ambiguity và task isolation.
- [x] Test real stdio + SQLite fixture: issue → anchors → context → display; đúng ContextPayload và token count, không LLM/gold.
- [x] Ghi RED vì tools đang thiếu; triển khai port, SQLite/demo services, factory, registry và server qua common envelope/audit.
- [x] SQLite adapter lấy source root/snapshot từ host, áp cùng hash/scope; demo backend không giả kết quả benchmark.
- [x] Callers/callees reject depth khác 1; không báo giả multi-hop.
- [x] Viết scripts/smoke_w5_w6.py; source unchanged và context validation là gate.
- [x] MCP/resources/context/SQLite + transport + full suite 353 pass/4 skip; tài liệu được cập nhật ở milestone 7.

**Điểm cần chốt interface:** Không có global “last issue”. Binding task/overlay phải theo host session/run hoặc service instance riêng. Nếu adapter stateless buộc phải thêm public `task_id`/handle, dừng xin M1/M3 consumer review trước; không tự đổi frozen payload/signature. Milestone này chỉ đạt khi isolation được kiểm thử, không chỉ discovery thấy tên tool.

## 10. Milestone 7 — Tài liệu vận hành và nghiệm thu tích hợp tuần 3–6

**Liên quan:** R04, R06 và tài liệu bị ảnh hưởng bởi milestones 1–6. Không chứa yêu cầu hoàn thiện research tuần 1–2 hoặc sửa model inference loader.

- [x] Ghi cấu hình evaluation thực tế trong docs/m5_m6_retrieval_evaluation.md; không tạo research design mới.
- [x] Evidence ghi inference NOT_RUN; không bịa token generation/repair success.
- [x] ADR Test + Issue/REPRODUCES, native snippets/scorer policy/unavailable features/task_handle.
- [x] README Python/venv/.env/W6 tools/statuses/security; handoff cũ có historical addendum.
- [x] Commands --help/local doc links/tokenizer binding PASS; PROGRESS đối chiếu actual results.

**Gate:** Thành viên chạy và đọc evidence tuần 3–6 được theo hướng dẫn. Không yêu cầu đưa research tuần 1–2 vào repo, không đánh giá tình trạng research từ việc file không có trong checkout.

## 11. Milestone 8 — Nghiệm thu theo gate tăng dần

Không dùng patch-generation success làm tiêu chí của retrieval tuần 5–6.

- [x] **Gate 8.1:** Full recorder mới nhất **359 passed/4 skipped**, phase DONE, source unchanged; evidence `artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json`. Bốn skip là kiểm thử symlink phụ thuộc quyền máy, không tính là pass.
- [x] **Gate 8.2:** Actual fixture build → overlay → retrieve → adapter → score → serialize → compare → REPORT, inputs/source nguyên bytes; evidence 20261007T012636266959Z-7ac7378bc98e. Bytes/4 diagnostic fixture, không benchmark chính thức; không chèn artificial `arm` vào output runner.
- [x] **Gate 8.3:** Pilot chính no-Jedi được người dùng duyệt07/10: Django11138/matplotlib14623/xarray3993, **3/3 SUCCEEDED**, official tokenizer/8000/offline/worker1/deadline300s; run20261007T013925676777Z-55ae5fb6a24a. Giữ Jedi0/3 riêng, không coi Jedi đã được sửa.
- [ ] **Gate 8.4:** Mục tiêu 25 completed paired tasks. Đã lưu đủ 25 attempts nhưng chỉ **19 valid pairs / 6 lỗi**, chưa đạt ngưỡng tối thiểu 20. Cùng query/base/corpus/gold/counter/budget/scorer/snippet policy; không loại task lỗi khỏi manifest để làm xanh gate. BM25 được phục hồi nguyên raw Git blobs vào bản sao riêng, không rerun hay bỏ hash guard.
- [x] Báo rõ no-anchor/mapping/denominator: 19 task thành công có zero no-anchor, unmapped=0; không suy diễn cho 6 task lỗi. No-anchor vẫn là retrieval miss; unscorable vẫn N/A theo scorer, không silently drop.
- [ ] Nếu chỉ 20–24 valid pairs: lưu đủ 25 attempts và failure taxonomy, cần leader duyệt exclusion/protocol; không tự gạch task để đạt gate. Dưới 20 pairs chưa đạt DoD.
- [x] Báo file/function Recall@3/5/10, MRR, packed coverage, token cost, latency và CI trên **19 cặp hợp lệ**, oracle arm riêng; xem `docs/reviews/2026-10-07-dev25-no-jedi-results.md`. Graph thấp hơn BM25 trên các metric chính trong subset này; không đặt gate “Graph phải thắng BM25”, không coi báo cáo partial là đạt Gate 8.4.
- [x] Kiểm tra thủ công **10 task distinct**: issue/base/gold, anchors, top-k, tokens, source proof, unmapped labels và nhận xét; có reviewer/date. Self-audit07/10 trong `docs/reviews/2026-10-07-manual-retrieval-audit-10.md`; không owner sign-off, không thay paired25.
- [ ] **LOẠI TRỪ ĐỢT NÀY theo người dùng ngày07/10:** Environment readiness50–100 và smoke3; không chạy/kiểm Docker/install. Yêu cầu gốc vẫn lưu nhưng không dùng làm task triển khai trong phiên này.
- [x] Tách retrieval gate và environment gate trong báo cáo/checkpoint. Environment bị loại trừ đợt này: không thử môi trường, Docker hay cài dependency benchmark; không gọi W6 hoàn thành khi retrieval gate còn thiếu.
- [x] Ghi `docs/w5_w6_completion.md` mapping task → code/evidence/limits/sign-off; cập nhật evaluation report và PROGRESS. Owner sign-off vẫn pending, không tự phê duyệt thay M1/M2/M3.
- [x] Kiểm tra diff/status, self-review chỉ affected files; xem `docs/reviews/2026-10-07-affected-files-review-w3-w6.md`. Không có independent reviewer, không tự commit/push; sáu lỗi benchmark ghi rõ chưa sửa.

## 12. Tài nguyên, chi phí và evidence

| Lượt | Tài nguyên | Giới hạn đề xuất |
|---|---|---|
| Unit/integration | CPU và Python env; không GPU/LLM | Wrapper timeout 240 giây/lượt; full outputs |
| Tokenizer/MCP | Assets tokenizer đã pin | Offline, không tải model weights |
| Retrieval smoke | CPU/RAM/source cache | 3 task, worker 1, 300 giây/task |
| Retrieval dev25 | Như smoke; artifact mới | Tổng task timeouts tối đa khoảng 125 phút, chưa tính setup; không phải dự báo latency |
| Environment subset | Tùy repository/dependency/container | Estimate riêng sau 3 environment smoke; không cài mọi repo vào chung một venv |

API inference cho core fix/retrieval: **0 USD** vì không gọi model. Compute/storage thuê ngoài không được giả định miễn phí. Jedi và no-Jedi là profiles riêng; chỉ quyết định tăng RAM sau stage-level measurements.

Sau mỗi milestone lưu ở `artifacts/fixes/w3-w6/<UTC-run-id>/`:

- `result.json`: argv/cwd/interpreter/versions/start/end/exit/duration/status/config/source hashes/task ID.
- stdout/stderr đầy đủ, embedded JSON hoặc files riêng.
- `diagnostics.json`: phase, time/RSS, trace, input tái hiện và expected/observed.
- Diff của milestone nếu cần bàn giao; loại secrets, không stage/push ngầm.
- PROGRESS: task đã xong, evidence, bước kế tiếp, pending approvals.

Source hash gốc/workspace phải dùng cùng scope. Artifact audit cũ bất biến.

## 13. Self-review và điểm dừng

Kế hoạch bao phủ F01–F12: comparison → 1; graph → 2; source scope → 3; MCP boundary → 4; cache/provenance → 5; retrieval MCP → 6; tài liệu vận hành → 7; DoD tích hợp tuần 3–6 → 8. Research tuần 1–2 không thuộc task sửa hoặc tiêu chí nghiệm thu repo.

Giữ type/interface, tách rank/packed/oracle semantics, không bỏ failure denominator. Không kéo full repair/fine-tuning hoặc tuần 7–16 vào scope.

**Dừng xin ý kiến** khi cần đổi frozen contract/IDs rộng, benchmark split/model, bỏ validator, dùng held-out, cài môi trường lớn ngoài giới hạn hoặc sửa repo đang đóng băng. Nhóm/leader phải duyệt contract và sign-off; agent không thay được phê duyệt đó.

## 14. Cách xác nhận

Bạn có thể nhắn:

> Tôi xác nhận kế hoạch fix VGAR tuần 3–6 trong file 2026-10-06-fix-vgar-integration-week-1-6.md. Hãy triển khai từng milestone, lưu evidence và cập nhật PROGRESS; không sửa/tích hợp research tuần 1–2, không sửa hệ thống cũ, không commit/push cho đến khi tôi yêu cầu.

Khi được xác nhận, bước đầu là kiểm tra status/diff/checkpoint mới và triển khai milestone 1 từ code hiện tại, không làm lại toàn bộ audit.
