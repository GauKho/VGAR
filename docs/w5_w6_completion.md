# Nghiệm thu tích hợp tuần 3–6 — cập nhật 07/10/2026

Milestone1–6 qua gate kỹ thuật fixtures; milestone7 có doc links/CLI/counter consistency evidence PASS. Milestone8 gates8.1/8.2 và pilot3 PASS. Dev25 no-Jedi terminal **19success/6failures, 19validpairs/25attempts**, **chưa đạt ngưỡng20**; duplicateedge Pylint6386 còn mở, không gọi builder đúng mọi repo. Full suite cuối **359passed/4skipped**. Manual10 self-audit và affected-files self-review hoàn tất, owners chưa ký. Jedi failures giữ riêng, không retry. Environment50–100/smoke3 bị loại trừ. [Task chưa hoàn thành](BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md) ghi nguyên nhân/evidence/điều kiện tiếp tục. Không inference/fine-tune/hệ thống cũ/commit/push; researchtuần1–2 không tích hợp.

## Task → code → evidence

| Nội dung | Code chính | Gate hiện tại |
|---|---|---|
| Graph transactions/bindings | src/vgar/graph/{builder,retrieval}.py | regression failed-file inventory/compound/duplicates/inheritance |
| Shared source scope/recorder | src/vgar/source_scope.py, repair/{workspace,source_preflight}.py, scripts/record_m2_test.py | generated paths pruned; generic real packages giữ; pending/preflight timeout tests |
| MCP boundary + M2 runner | src/vgar/mcp/workspace_guard.py, servers/{repository,execution}_server.py, repair/test_runner.py | actual stdio/scripted LangGraph/lease/envelope/CRLF/timeouts |
| BM25/chunks/gold/scorer | src/vgar/evaluation/retrieval/{bm25,chunks,gold_labels,scoring}.py | BM25 dev25 lịch sử; mapping/shared scoring tests; graph paired mới còn gate |
| Fair comparator/report | retrieval/{compare,report}.py | actual serializer, same protocol/population/hashes; full rank/cap sensitivity riêng |
| Cache/provenance/lifecycle | retrieval/{graph_arm,graph_cache,evidence,lifecycle,worker}.py, scripts/run_graph_retrieval.py | bytes/links/partial/tamper guards; timeout/crash/resume identity/RSS tests |
| Retrieval MCP/task handles | graph/{port,sqlite_store,sqlite_service,factory}.py, mcp/servers/graph_server.py | 5 tools, task isolation persist SQLite, frozen ContextPayload, invalid/stale/tamper tests |
| Context display | scripts/smoke_w5_w6.py | official counter fixture PASS; stateless A/B/A, hash unchanged, 10+15 snippet tokens; không benchmark |

Paths rút gọn graph/repair/mcp bắt đầu từ src/vgar/; retrieval bắt đầu src/vgar/evaluation/. Không suy ra bảng là module fine-tune.

Full gate milestone6: [JSON](../artifacts/fixes/w3-w6/milestone-6-final-recorder/20261006T154059255443Z-54a8f6ac3e3a41308263d01880fd43f2.json), **353 passed, 4 skipped**. Sau thêm recovery regression: [recorder](../artifacts/fixes/w3-w6/milestone-8-tree-recovery-recorder/20261006T160554839620Z-209a0f28af6049328d43ab81cf33a219.json), **354 passed, 4 skipped**, source trước/sau giống nhau. Skips do quyền real symlink; reparse metadata tests vẫn chạy. Full logs/cases trong evidence; RED runs giữ nguyên. [PROGRESS](../PROGRESS.md) chứa ledger.

Official tokenizer MCP fixture [result](../artifacts/fixes/w3-w6/20261006T155804375314Z-70ff70a28f6c/result.json) PASS. Pilot source-hash FAIL [run](../results/retrieval/20261006T155910874325Z-e34289af181b/result.json) được chẩn đoán là Git LF→CRLF; default guard đúng, --rebuild-trees giữ cache cũ. Recovery [run](../results/retrieval/20261006T160820338280Z-24c3cf0056d1/result.json) đã terminal: **0/3, PARTIAL_FAILURE**, cả ba task timeout BUILD_GRAPH300s, không MemoryError. [Diagnostic xarray không Jedi](../results/retrieval/20261006T162334561191Z-8d3c4f6a13e7/result.json) SUCCEEDED, 21.509s tổng/build4.220s/peakRSS392.568.832 bytes; không thay profile chính và không paired benchmark. Docker Linux daemon chưa chạy, environment gate vẫn NOT_RUN.

Sau targeted review credential filter và hoàn thiện fixture compare→REPORT: [recorder mới nhất](../artifacts/fixes/w3-w6/milestone-8-credential-final-recorder/20261007T012625128617Z-0a58010aea154438b18dba6077931c47.json) **355 passed, 4 skipped**, source trước=sau; [fixture gate8.2](../artifacts/fixes/w3-w6/20261007T012636266959Z-7ac7378bc98e/result.json) PASS, có toàn bộ REPORT trong JSON và artifact inputs/outputs giữ riêng. Không dùng fixture counter để thay official benchmark.

## Gates còn cần bằng chứng

- [x] Official tokenizer fixture + pilot3 dev25 no-Jedi đã duyệt, không fallback; source nguyên vẹn. [Pilot3](../results/retrieval/20261007T013925676777Z-55ae5fb6a24a/result.json) SUCCEEDED3/3.
- [ ] Paired25 cùng protocol, oracle arm riêng; **19pairs**, dưới20 chưa đạt. Không retry/loại task để làm đủ số.
- [x] Report/CI/latency/denominator đã tạo **trên19validpairs**, không phải paired25 nghiệm thu: [kết quả](reviews/2026-10-07-dev25-no-jedi-results.md), [REPORT](../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/REPORT.md). Graph kémBM25, giữ kết quả thật/oracle riêng.
- [x] Manual review10 distinct tasks, reviewer/date, issue/base/gold/anchors/top-k/tokens/source/unmapped. [Self-audit10](reviews/2026-10-07-manual-retrieval-audit-10.md), integrity10/10; không owner sign-off/independent review, không thay paired25.
- [ ] **LOẠI TRỪ đợt này theo người dùng07/10:** Environment readiness50–100, smoke3 trước. Hiện NOT_RUN; không kiểm/chạy Docker/install; archives không chứng minh tests chạy được.
- [ ] M1/M2/M3 sign-off ADR identities/task handles/consumer mapping. User đã duyệt task_handle; agent không ký thay owners.

## Hướng dẫn và giới hạn

Host CLI/workflow source binding đã RED4failed→GREEN24passed; [full recorder cuối](../artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json) **359passed/4skipped**, testexit0/phaseDONE, pytest140,38s, runner144,980s, source trước/sau giống nhau. Skipped cases là symlink permission, serialized NOT_RUN, không PASS. [Affected-files self-review](reviews/2026-10-07-affected-files-review-w3-w6.md) giữ các Important findings chưa sửa của benchmark; không fresh reviewer hoặc owner sign-off.

[Vận hành](m5_m6_retrieval_evaluation.md), [MCP contract](mcp_tool_contract.md), [ADR](adr/2026-10-06-stateless-task-handles-and-context-boundary.md).

8000 là snippet budget, không toàn prompt; native M1 vs scorer header/max80lines là hai policies. Retrieval không sinh patch; inference NOT_RUN, API inference0USD, không bịa repair rate. Lease là policy guard, không OS sandbox. Handoff cũ gắn nhãn lịch sử; tuần7–16 ngoài scope.
