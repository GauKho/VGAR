# L6-6 — Build/update graph qua MCP — 09/11/2026

## Baseline và phạm vi

Chỉ L6-6 theo approved plan trong chat và Final_Task implementation plan. Cache extraction RAM theo phiên MCP; một subprocess/one repo, restart/error/cancel mất extraction cache; SQLite snapshots giữ bền. Không TV2/TV3 algorithms/schema mới/L6-8/model/Docker/campaign/install/commit/push.

Branch `m2/w12-a3-verifier-d15-20261105`, HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`. Artifact `results/mcp_server/graph_jobs/20261109T050523Z-incremental/`: baseline có2.701 hashes gồm dirty tracked/untracked, index và seals H1/L6-1/2/3/4/5/7; status/staged/unstaged giữ nguyên.

## IN_PROGRESS — Điểm tiếp tục

- New `proposal/graph_jobs.py` trusted controller/config, `_graph_worker.py` persistent static builder subprocess. Controller thread sở hữu repo lock + exact single-use build grant + staging/copy + worker IPC + derived storage grant + publication/evidence. Worker không authority/grants/DB, không import/execute target source.
- `tools.py` thêm opt-in exact-type controller; default provider path giữ nguyên. Registry/binding tạo riêng mỗi signed request. `graph_server.main` đóng controller trong finally. Không đổi inventory/signatures/legacy payloads/default launchers.
- `storage_capabilities.py` thêm request_context cho cancellation cùng namespacerequest, so mọi identity/root/scope fields trừ storage snapshot ID, thêm operation_deadline chỉ được thu hẹp request deadline. Grant storage vẫn exact full identity/doc hash.
- RED modulemissing; GREEN10; RED4hardening (ACK trước publication, original publication receipt trong cache index, code drift restart worker, readiness) → GREEN14. RED metadata staging+effective profile → semantic GREEN22 gồm6 mutation cases, mỗi case2 updates so full build (chỉ bỏ statistics.build_time_ms).
- Review read-only đã tái hiện3 issues. Repository.name/root_uri đã normalize về host repo sau kiểm private-source binding. Effective profile hash bind operator_profile/config/code (không phụ thuộc runtime build_time_ms để invalidate). Worker ACK được kiểm trước ingest, không publish khi thiếu ACK.
- Mới thêm RED deadline/cached-source baseline/summary type: storage deadline trước publication; reuse source cũ khác worker lineage phải resetworker/cold, receipt khai changes_baseline_snapshot_hash; reject bool/count/duration/path/workerPID summary hỏng. Một lượt RED có NameError test Path, đã sửa và rerun RED đúng riêng summary. Gate `green-review` đang chạy; xem XML/command log trước khi rerun.
- Còn phải bổ sung/hoàn tất: concurrency native processes, cancellation/process-tree/timeout/crash barriers, `-O`, official SDK2 STDIO build+snapshot read bằng provider thật trên fixture, storage/legacy/full MCP regression, Ruff/preservation/docs/seal. Chưa DONE.
- Chỉ một reviewer `/root/graph_jobs_review` đã review read-only, cần followup recheck findings sau fix. Không spawn implementer khác.

Python SDK2 `D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe`; legacy `...\vgar-week78-cuda\Scripts\python.exe`. UTF8/-B/demo collection/no pytest cache, fresh short temp ngoài repo. Artifact có run_command.py và mcp_regression_safety.py để copy sample DB sang temp; không thử migration/query write trên DB tracked.

Final status sẽ append sau evidence thực. Rich-schema/provider mới vẫn WAITING_SCHEMA_PROVIDER/WAITING_PROVIDER.


## Kết quả cuối


## L6-6 — DONE kỹ thuật build/update legacy; graph mới WAITING_PROVIDER — 09/11/2026

- Trusted controller nối build_or_update_graph với IncrementalGraphBuilder thật và SQLite snapshots L6-7. Một worker subprocess giữ cache extraction RAM theo phiên/repo, cold/warm/reuse rõ; relink vẫn toàn repo, không claim O(Δ+Fanout) hoặc benchmark production.
- Controller thread sở hữu validate/authorization/repo lock/copy/worker/storage/receipt; adapter không giữ OS lock ở thread khác. Build grant single-use trước staging/spawn; worker không authority/grants/DB và không import/execute target. Request-scoped registry/binding, opt-in bootstrap, default/legacy API/payload/inventory20tools/8canonical+alias/1prompt giữ nguyên.
- Source private copy/hash và worker job/instance/document/summary/ACK được kiểm trước publication. Repository metadata normalize về host repo sau proof, không để URI staging đã xóa. Effective profile bind operator profile/config/code; cache pin full identity/manifest/DB/original publication receipt, không latest/graph_version-only. Reuse snapshot cũ khác worker lineage reset worker; receipt ghi baseline thật hoặc cold-empty.
- Derived storage context dùng exact identity grant, cùng parent request scope; parent cancellation/operation deadline được kiểm cả trước/sau source scan và trong commit/publication guard. Timeout/cancel/error kill process tree và bỏ extraction cache; thiếu ACK không publish; native crash/orphan không tự adopt. Error khi source root biến mất vẫn cleanup worker, không che integrity thành PASS.
- Final SDK2 **399 PASS,0skip/fail/error**:45 cases L6-6 mới +354 regression MCP/storage/incremental/SQLite đã có. Legacy **102 PASS +1skip cũ**; các nhóm overlap, không cộng unique totals. Ba real STDIO lanes SDK2modern/legacy và SDK1server thực hiện cold→reuse→warm→read snapshot, nằm trong45 cases mới. Native process/cancellation/crash, optimized Python, config/source/schema/resolver/profile/code invalidation và semantic full-build equivalence có evidence.
- Review read-only đã đóng metadata staging, worker baseline và deadline sau source-scan; có RED→GREEN regressions. Intermediate gate từng phát hiện default expired-context exception bị đổi và lỗi fixture đăng ký lại authority; đã giữ ValueError legacy và sửa helper test, không nới grants/checks hoặc thêm skip/xfail.
- Ruff scoped/pip check/whitespace/preservation PASS. HEAD/branch/index/staged, package inventories, source plans, DB/V11/policies/M2/Linux reports và sealed artifacts trước giữ nguyên; PROGRESS/contract/status chỉ append. Process inventory sau gates không có server/worker còn sót.
- Runbook docs/mcp_server/graph_jobs.md; checkpoint docs/checkpoints/2026-11-09-mcp-graph-jobs.md; artifact results/mcp_server/graph_jobs/20261109T050523Z-incremental/ chứa actual commands/log/JUnit, worker/cache/equivalence/wire/crash/review, snapshot examples và checksums. Fixture source là synthetic, provider/builder/storage thật; không dùng làm bằng chứng dataset/model repair hoặc schema mới.
- **G_arch/G_task/Trace/Component/Port vẫn WAITING_SCHEMA_PROVIDER/WAITING_PROVIDER**. Chưa đóng toàn11 core tools production hoặc L6-8/external-host integration. Không model/Docker/campaign/install/commit/push. **Dừng sau L6-6.**
