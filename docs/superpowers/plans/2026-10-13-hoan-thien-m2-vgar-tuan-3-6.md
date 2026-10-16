# Chỉ hoàn thiện M2 của VGAR tuần 3–6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Dùng `superpowers:executing-plans` khi người dùng chọn triển khai Native. Nếu người dùng chọn Subagent-driven thì dùng `superpowers:subagent-driven-development`. Thực hiện từng milestone, lưu evidence và cập nhật checkpoint; chưa triển khai trước khi người dùng xác nhận kế hoạch này.

**Goal:** Hoàn thiện phần M2 còn thiếu trong tuần 3–6, giữ nguyên và kiểm tra hồi quy các phần M2 đã hoàn thành, không nhận thêm task của M1/M3 hoặc tuần 7 trở đi.

**Architecture:** Tái sử dụng disposable workspace, pytest runner, baseline/EvidenceBundle writer và BM25/gold-label/evaluation modules đang có trong VGAR. M2 nhận graph/context của M1 như một dependency đã pin; chỉ kiểm tra và chuẩn hóa phía consumer/scorer của M2, không sửa thuật toán graph/retrieval của M1. Chỉ nối guard/runner M2 vào adapter MCP hiện có nếu cần để boundary workspace có hiệu lực trong hệ thống.

**Tech Stack:** Python `>=3.11,<3.14` theo repo, ưu tiên Python 3.11; pytest; Pydantic; JSON/atomic writer; BM25; gold-label extractor; Tree-sitter/tokenizer hiện có được sử dụng như dependency, không phát triển lại. Không cần LLM inference, GPU hoặc Docker để hoàn thành workload M2 trong kế hoạch này.

**Spec:** [project_plan_16_weeks.md](D:/Project/CAPSTONES/New_task/project_plan_16_weeks.md), chỉ hai mục **M2 — Repair & Verification** của tuần 3–4 và 5–6; [Task Status.md](<D:/Project/CAPSTONES/VGAR/Task Status.md>), chỉ 8 ID `W03-04-M2-*` và `W05-06-M2-*`.

**Trạng thái:** Plan mới để review. Thay thế phạm vi triển khai của [kế hoạch toàn M1/M2/M3 trước đó](D:/Project/CAPSTONES/VGAR/docs/superpowers/plans/2026-10-13-hoan-thien-vgar-tuan-3-6.md); bản cũ được giữ làm lịch sử, không tự thực hiện các milestone của bản cũ.

## Global Constraints — giới hạn chung

- Chỉ triển khai trong `D:/Project/CAPSTONES/VGAR`. Không sửa các repo cũ, `M2_week_3+4`, `M2_week_5_6`, notebook hoặc training pipeline.
- Không làm lại 5 task M2 đã HT. Sửa bug cụ thể ảnh hưởng acceptance và bổ sung regression không có nghĩa viết lại module đã có.
- Không tự triển khai task M1/M3, không cập nhật trạng thái các task đó sang HT.
- Không sửa graph builder/resolver, không cài/nghiệm thu SCIP/LSP, không quay lại Jedi; không thêm FailingTest node, task_handle, ranking profile hoặc tuning API risk.
- Không sửa resources MCP hoặc tạo flow issue → context mới của M3; không làm Related Work, runnable50/Docker harness, 20-edge manual validation hoặc ablation A0–A3.
- Giữ DTO `ContextPayload`, `EvidenceBundle`, public tool names/arguments và taxonomy hiện có. Không thêm `schema_version`; metadata bổ sung đặt trong evidence/diagnostic sidecar tương ứng.
- Không triển khai model sinh patch, unified-diff repair engine, repair loop, type/lint/API verification hoặc fine-tune: các mục này không nằm trong M2 tuần 3–6.
- Gold developer patch chỉ dùng để tạo nhãn/chấm evaluation, không vào issue query, anchors hoặc context retrieval chính.
- Một task/profile fail hai lần thì dừng profile, giữ evidence, ghi nguyên nhân và chuyển phần không bị phụ thuộc. Không tự chạy lại full benchmark vô hạn.
- Không commit/push, reset/rollback source hoặc ghi đè thay đổi chưa commit nếu chưa có yêu cầu riêng.

## Review Focus — năm tình huống phải kiểm thử

1. Caller đưa root khác workspace được host cấp, path traversal, absolute path hoặc link escape: từ chối trước read/edit/test; source gốc không đổi. Milestone S1.
2. Pytest exit 0 nhưng chỉ skipped, JUnit thiếu/hỏng, hoặc timeout/output vượt giới hạn: không báo verification PASS. S2.
3. M1 context/ranking không khớp base source, symbol/span/corpus/hash: M2 từ chối hoặc ghi unmapped rõ ràng, không đoán mapping để nâng Recall. S3.
4. Task không có gold function hợp lệ, source parse lỗi hoặc failure trong evaluation: công bố denominator/coverage, không biến missing thành zero hoặc loại task âm thầm. S3–S4.
5. Raw run thiếu, tokenizer counter khác, manifest/profile đổi hoặc resume artifact stale: không ghép so sánh và không lấy bảng lịch sử làm evidence checkout hiện tại. S0/S4.

---

## 1. Phạm vi mới có bao nhiêu task?

M2 có **8 task**, hiện `Task Status.md` ghi **5 HT, 2 MP và 1 CX**. Kế hoạch tập trung hoàn thiện **3 task còn mở**, đồng thời sửa hai lỗi acceptance của pytest/MCP runner và kiểm tra hồi quy phần đã HT.

- **HT:** Hoàn thành theo phạm vi được audit; không đồng nghĩa mọi edge case hoặc toàn repo đều pass.
- **MP:** Hoàn thành một phần, cần sửa hoặc bổ sung evidence/sign-off.
- **CX:** Chưa đủ bằng chứng để xác minh cho checkout hiện tại.

| ID | Task chính thức của M2 | Hiện tại | Cách xử lý trong plan mới | Milestone |
| --- | --- | --- | --- | --- |
| W03-04-M2-01 | Sandbox/worktree để chạy patch an toàn | MP | Hoàn thiện quyền truy cập theo lease và integrity trên success/failure/timeout | S1 |
| W03-04-M2-02 | Test runner wrapper cho pytest | HT | Giữ runner; sửa skipped-only/incomplete acceptance và tránh MCP wrapper khác semantics | S2 |
| W03-04-M2-03 | Baseline command/stdout/stderr/exit/duration | HT | Giữ baseline; regression và evidence mới cho những path bị tác động | S2 |
| W03-04-M2-04 | Schema EvidenceBundle và writer JSON | HT | Giữ schema/writer; kiểm pending/final, timing, source hashes và completeness | S2, S5 |
| W05-06-M2-01 | BM25 trên function/code chunks | HT | Tái sử dụng, không thay thuật toán hoặc tuning k1/b | S3, S4 |
| W05-06-M2-02 | Gold-file/gold-function từ developer patch | HT | Tái sử dụng; kiểm mapping/coverage khi nhận dữ liệu M1 | S3 |
| W05-06-M2-03 | Retrieval evaluation trên 20–30 SWE-bench task | CX | Khôi phục artifact tương thích hoặc chạy mới dev25, lưu đủ raw results/failures | S4 |
| W05-06-M2-04 | Phối hợp M1 debug context format/gold-label mapping | MP | Kiểm adapter/scorer phía M2, ghi mismatch và bàn giao/sign-off với M1 | S3, S4 |

**Ba mục chính cần đóng:** `W03-04-M2-01`, `W05-06-M2-03`, `W05-06-M2-04`. Không biến plan mới thành yêu cầu chạy lại cả 8 task từ đầu.

### Những phần được bỏ khỏi kế hoạch triển khai cũ

Sửa false CALLS trong graph builder; decode node/subgraph resources; SCIP qualification; manual20 edges; đổi FailingTest representation; thử API-risk profile; phát triển MCP context flow; runnable50–100; Related Work; task chung/DoD không thuộc trách nhiệm M2.

Bảng Graph vs BM25 và kiểm tra mapping vẫn được tạo vì trực tiếp phục vụ **evaluation của M2**, nhưng không dùng nó để tự đóng toàn bộ DoD của nhóm. Có thể chọn vài case để giải thích lỗi mapping; **không bắt buộc nhận thêm manual10 task** của DoD chung trong scope này.

## 2. Điểm xuất phát và phần cần giữ

- Repo/branch tại lúc lập plan: `VGAR`, `integration/main-m1-w5-w6-20261013`, HEAD `73814b8f89666c71b1911e42e98b8ecc7f6e3e99`.
- Source sản phẩm không có diff trước khi viết plan; `PROGRESS.md`, `Task Status.md`, `docs/audit/` và plan rộng trước đó là additions cần giữ.
- Audit trước sửa nằm tại `docs/audit/2026-10-13/`; không xóa/ghi đè để thay failure thành pass.
- Disposable copy và pytest runner đã hoạt động trên fixtures. Khoảng trống là model/caller có thể chọn root khác lease; skipped-only pytest bị đánh PASS và execution MCP đang dùng một wrapper riêng.
- BM25, gold extractor và scoring hiện có đã có tests. Handoff có số dev25/21 pairs lịch sử nhưng thiếu raw evidence tại clone mới; chưa được gọi là kết quả mới.
- Full suite trước đó: 411 passed, 1 failed, 2 skipped. Failure HF generation-config nằm ngoài scope M2 này; không tự sửa model runtime hoặc tuyên bố toàn repo xanh.

Khi triển khai, phải đọc status/diff/checkpoint mới trước S0. Các số trên là snapshot lập kế hoạch, không thay thế kiểm tra ở thời điểm thực hiện.

## 3. M2 cần gì từ M1 và M3?

| Dependency cần nhận | Dùng để làm gì | Nếu chưa có/lỗi thì xử lý thế nào |
| --- | --- | --- |
| M1: graph document của đúng base commit, node IDs/types/paths/ranges và candidates đã xếp hạng | M2 ánh xạ node/function sang corpus/gold labels và chấm retrieval | Lưu mismatch, không sửa builder/ranking; BM25 vẫn chạy độc lập được |
| M1: ContextPayload và provenance/counter identity | Kiểm schema, range/snippet và packing dưới budget | Kiểm consumer phía M2; lỗi producer ghi `DEPENDENCY_M1` và bàn giao M1 |
| M1: retriever/grounding API đang có | Dùng làm Graph arm đối chứng, không viết lại graph retrieval | Gọi Python API qua graph runner hiện có; không cần sửa MCP resource lỗi để chạy arm này |
| M3 hoặc dữ liệu có provenance tương đương: task ID, repo/base commit, split, snapshot/revision | Chọn dev25 và tái lập evaluation | Tái dùng manifest đã pin; nếu thiếu, dùng `prepare_manifest.py` hiện có để chuẩn bị input retrieval, không làm runnable50 |
| M3: tokenizer assets/manifest hoặc bundle hiện có của M1 | Hai arms dùng cùng counter thật, không so sánh tokenizer thật với bytes/4 | Tái dùng bundle có hash; nếu thiếu, chỉ provision tokenizer-only bằng script hiện có, không sửa counter hay tải model weights |
| MCP hiện có: repository/execution adapters | Đưa guard/runner M2 vào đường gọi thực để chặn root ngoài lease | Chỉ adapter wiring tối thiểu mục4; không phát triển tools/resources mới |
| Người phụ trách M1: review mapping/handoff | Đóng mục phối hợp M1, xác nhận producer/consumer hiểu thống nhất | Có thể hoàn tất tests/code M2 trước; chưa có sign-off thì mục phối hợp vẫn MP |

**Tính độc lập:** Workspace/pytest/baseline/evidence/BM25/gold extraction làm được độc lập. Graph-vs-BM25 và task phối hợp cần output M1 phù hợp. Không cần M1 đạt mọi task hoặc M3 chạy được Docker50 để bắt đầu M2.

Lỗi graph binding đã biết có thể làm quality của Graph arm thấp hoặc có candidates sai. Nếu payload hợp lệ, M2 đo và công bố giới hạn đó; nếu payload/source identity không hợp lệ, M2 từ chối cặp hoặc ghi task fail. Không sửa M1 để cứu metric, không dùng gold để lọc/rerank candidates.

## 4. Giới hạn thay đổi file: chỉ logic M2 và wiring bắt buộc

### 4.1. Files M2 được phép tác động khi có lý do cụ thể

- `src/vgar/repair/workspace.py`, `test_runner.py`, `baseline.py`, `evidence_writer.py`.
- Module mới dự kiến: `src/vgar/repair/access_policy.py`.
- `src/vgar/evaluation/retrieval/scoring.py`, `graph_arm.py`, `compare.py`, `report.py`, `evaluation.py`, `gold_labels.py`: chỉ sửa bug phía M2 đã có failing test; không mặc định sửa hết các file.
- `scripts/record_m2_test.py`, `run_m2_baseline.py`, `prepare_manifest.py`, `run_bm25_retrieval.py`, `run_graph_retrieval.py`, `compare_graph_vs_bm25.py`: tái dùng; chỉ bổ sung bounds/evidence/receipt nếu cần cho invocation đang thực hiện.
- Tests M2, docs bàn giao M2, status/progress và artifacts của lần chạy mới.

### 4.2. Adapter mỏng cần cho an toàn workspace

Để sửa `W03-04-M2-01` thật sự trong hệ thống, guard của M2 phải được gọi tại nơi nhận yêu cầu edit/test. Vì vậy có thể cần thay đổi tối thiểu:

- `src/vgar/config/settings.py`, `src/vgar/mcp/client.py`: truyền server-owned lease config, không mở rộng graph settings.
- `src/vgar/mcp/servers/repository_server.py`: gọi M2 path/lease guard trước read/edit.
- `src/vgar/mcp/servers/execution_server.py`: gọi cùng guard và pytest runner M2.
- `src/vgar/cli.py`, `src/vgar/agents/nodes/prepare.py`, `src/vgar/agents/runtime.py`, `src/vgar/agents/workflow.py`: chỉ cấp lease trước khi tạo client và kiểm source integrity/cleanup mọi terminal path.

**Đây là wiring của task an toàn M2, không nhận task phát triển MCP của M3.** Không đổi tool signatures, không sửa graph server/resource, prompt/model hoặc repair logic. Test wiring bằng injected/scripted consumer, không chạy HF thật.

Nếu nhóm yêu cầu các file adapter do M3 tự sửa: M2 bàn giao policy, tests và patch hướng dẫn cho M3; chưa tích hợp/round-trip được thì **M2-01 vẫn MP ở mức tích hợp**, không gọi guard module riêng là hệ thống đã an toàn. Người dùng có thể chọn cách bàn giao này khi review; mặc định đề xuất wiring tối thiểu để đóng đúng lỗi đã audit.

## 5. Thứ tự triển khai

```text
S0: khóa scope/input + chọn môi trường/evidence
 ├─ S1: lease boundary và source integrity
 │    └─ S2: pytest acceptance + baseline/evidence regression
 └─ S3: context/gold mapping consumer + handoff M1
      └─ S4: pilot3 → dev25 BM25/Graph → bảng metrics
S5: regression các phần tác động + Task Status/PROGRESS + bàn giao M2
```

Nếu S3 bị chặn bởi M1 thì vẫn làm S1/S2 và chạy BM25 của S4; Graph comparison/handoff giữ pending. Không chuyển sang sửa M1/M3 để “cố hoàn thành”.

## 6. S0 — Chốt đầu vào và evidence, không audit lại toàn repo

**Files đọc:** `PROGRESS.md`, `Task Status.md`, plan mới này và hai đoạn M2 trong plan16W.

**Outputs:** `docs/handoff/m2-w3-w6/protocol.md`, `docs/handoff/m2-w3-w6/UNFINISHED_TASKS.md`, checkpoint mới. Nếu cần môi trường nhẹ mới, tạo requirements riêng `scripts/requirements_m2_w3_w6.txt` từ pins hiện có.

**Các bước:**

- [ ] Kiểm `git status --short`, `git diff`, HEAD và checkpoint; giữ changes hiện tại. Không clone lại hoặc chạy full repo audit.
- [ ] Ghi 8 ID mục1, 3 ID cần đóng, constraints/allowlist file; giữ graph/ranking profile đang có, không đưa profile risk của plan cũ vào.
- [ ] Tìm raw dev evidence/bundle tokenizer đã có và kiểm provenance. Chỉ reuse nếu source/config/manifest/counter/hash tương thích; nếu không, ghi lý do phải chạy mới.
- [ ] Chọn interpreter rõ ràng. Nếu chưa có môi trường tương thích, tạo `.venv-m2-w3-w6` riêng, dùng pins phù hợp từ requirements M1/repo hiện có, không install full `.[dev]` kéo model/training stack. Kiểm import M2, pytest, graph dependency và tokenizer; không tải weights.
- [ ] Tái dùng `record_m2_test.py`, M2 writer và evaluation evidence utilities. Không tạo một hệ thống ghi log mới trùng chức năng.
- [ ] Ghi profile fixture timeout120s, Graph task timeout300s ban đầu và một worker. Deadline của các batch/readiness khác trong plan cũ không áp dụng vào scope này.

**Gate S0:** Có protocol/receipt interpreter/source và input hash; chưa thay task sang HT chỉ vì chuẩn bị xong.

## 7. S1 — Hoàn thiện workspace lease, không viết repair engine

**Task:** `W03-04-M2-01`.

**Files:** `src/vgar/repair/access_policy.py` mới; `workspace.py` nếu phát hiện lỗi cần sửa; adapter allowlist mục4.2. Tests mới: `tests/m2/test_access_policy.py`, `tests/m2/test_workspace_adapter.py`; bổ sung `tests/m2/test_workspace.py`.

**Interfaces nội bộ dự kiến:**

- `WorkspaceSettings(source_root: Path | None, workspace_root: Path | None, worktree_id: str | None, mutation_enabled: bool = False)`; host tạo từ `WorkspaceLease`, không lấy root quyền ghi từ model.
- `require_workspace_root(repo_path: str, policy: WorkspaceSettings, *, mutation: bool) -> Path`; yêu cầu resolved root đúng exact root được cấp, khác source root, lease ID hợp lệ; mutation được host bật.
- Config tương ứng qua settings/to_env: `VGAR_SOURCE_ROOT`, `VGAR_WORKSPACE_ROOT`, `VGAR_WORKTREE_ID`, `VGAR_ALLOW_MUTATION`. Giữ tên/chữ ký tool edit/test hiện có.
- Dùng `safe_relative_path` và `fingerprint_source` hiện có; không thêm unified-diff parser/apply mới.

**Các bước theo test-first:**

- [ ] Viết tests: root gốc/root sibling/root không được cấp bị từ chối; lease thật được cấp thì edit/test trên copy hợp lệ.
- [ ] Viết tests traversal/drive/absolute path, selector ngoài root, symlink/junction escape; case không cấu hình quyền mutation fail closed. Link tests cần quyền Windows phải báo skip có lý do, không nói đã chạy nếu skip.
- [ ] Chạy negative tests trước implementation; lưu failure evidence để chứng minh chúng bắt đúng lỗi root hiện tại.
- [ ] Implement policy/guard nhỏ, realpath equality + containment; truyền policy từ host trước spawn MCP, không cấp lại từ tool input. Default không config lease thì không được sửa.
- [ ] Nối guard vào adapter read/edit/test hiện có; chỉ thay boundary, không đổi model hoặc public MCP schema.
- [ ] Chạy scripted round-trip trên dummy repo: edit copy đúng thì thành công; đổi root qua tool argument bị từ chối. Kiểm source hash trước/sau bằng nhau.
- [ ] Kiểm source integrity trên success, test assertion fail, timeout, tool error và workflow exception; cleanup chỉ target owned lease đã resolve, không xóa repo gốc.

**Gate S1:** Guard thực sự enforce ở đường gọi sử dụng, source unchanged trên mọi terminal path được test. Code policy riêng chưa wiring chỉ là partial. Disposable copy/path guard **không phải OS sandbox**; không quảng bá là an toàn chạy code thù địch trên host.

## 8. S2 — Sửa acceptance của pytest, giữ baseline/EvidenceBundle

**Tasks:** Regression `W03-04-M2-02/03/04`; hỗ trợ đóng M2-01.

**Files:** `src/vgar/repair/test_runner.py`, adapter execution mục4.2; `baseline.py`/`evidence_writer.py` chỉ nếu regression chứng minh cần đổi. Tests hiện có `tests/m2/test_test_runner.py`, `test_baseline.py`, `test_evidence_writer.py`, `test_contracts.py`.

**Interfaces giữ nguyên:** `run_tests(workspace: Path, selectors: tuple[str, ...], timeout_seconds: float) -> TestRunResult`; `run_baseline(...) -> EvidenceBundle`; `begin_run(...)` và `finish_run(...)` hiện có. Thêm metadata ở sidecar/`metadata`, không sửa shape của DTO public.

**Các bước:**

- [ ] Thêm `test_all_skipped_is_incomplete`, `test_exit_zero_without_valid_junit_is_incomplete`, `test_mixed_pass_skip_can_pass`; assert status/reason/counts/completeness, không chỉ exit code.
- [ ] Thêm regression collection error/no tests/assertion fail/timeout/process child cleanup/output limit; secret env không đi vào child pytest. Dùng dummy fixture, không sửa source repo thật để tạo failure.
- [ ] Chạy tests mới để xác nhận lỗi hiện tại trước sửa. Giữ tests runner đã HT.
- [ ] PASS chỉ khi exit0, JUnit hợp lệ, passed>0, failed=0, error=0 và kết quả đầy đủ. All-skipped/missing/corrupt JUnit phải ERROR với `VERIFICATION_INCOMPLETE`, không PASS. Không nâng all-skipped thành thông báo “tests passed”.
- [ ] Cho `execution_server.run_pytest` tái sử dụng runner M2 thay vì subprocess wrapper riêng. Giữ output keys consumer đang dùng; counts/duration/reason lưu trong diagnostics/evidence. Không thêm execution tools mới.
- [ ] Kiểm timeout MCP trong `(0,120]` cho fixture và output giới hạn hiện có; timeout giết child process, không chỉ process cha rồi để pytest tiếp tục chạy.
- [ ] Chạy baseline clean/failing/incomplete trên disposable copy. Failing repo có `tests.status=FAIL`, `patch_applied=False` và source unchanged là baseline hợp lệ, **không phải M2 sửa lỗi thất bại**.
- [ ] Kiểm JSON có command/argv, stdout/stderr, exit, `duration_ms`, `started_utc`, `ended_utc`, source hashes, interpreter, pending/final atomic. Writer record `complete` nghĩa invocation đã finalize; `.test_result.complete` nghĩa verification đầy đủ — không đánh đồng hai field.

**Gate S2:** Tests/assertion failure/incomplete/timeout phân biệt đúng; baseline và writer contract giữ nguyên; các task HT không regression. Schema có type/lint/API fields default NOT_RUN không có nghĩa tuần3–6 đã thực hiện những checks đó.

## 9. S3 — Kiểm context/gold mapping phía M2, không sửa M1

**Task chính:** `W05-06-M2-04`; regression của BM25/gold extraction HT.

**Files:** Tái dùng `src/vgar/evaluation/retrieval/scoring.py`, `graph_arm.py`, `gold_labels.py`, `chunks.py`, `metrics.py`, `compare.py`; `src/vgar/contracts/context.py` chỉ đọc để validate shape. Tạo `tests/m2/test_context_gold_handoff.py` và `docs/handoff/m2-w3-w6/CONTEXT_GOLD_HANDOFF.md`.

**Interfaces hiện có:**

- `CorpusIndex(sources)` tạo canonical function identities của cùng source corpus.
- `graph_rank(instance_id, candidates, nodes, sources, corpus, *, arm='graph', include=None) -> RankRecord`; dùng candidate order M1 cung cấp, **không resort/rerank** bằng gold.
- `extract_gold(patch, sources) -> dict`; changed-file/function proxy, không phải chứng minh root cause.
- `evaluate_graph_task(...) -> dict` freeze rank hash trước gold extraction; `score_record(...)` chấm rank và packed từ cùng RankRecord/counter.
- `m1_adapter.py` là legacy packed-context/bytes4: **không dùng `compare_run` legacy cho artifacts scoring-v1** và không chuyển pipeline mới ngược về legacy.

**Các bước:**

- [ ] Chốt producer receipt: repo/base commit, source fingerprint, graph version, node/path/span/symbol, candidate order, ContextPayload và tokenizer/counter identity. Diagnostic metadata ở sidecar, không thêm field DTO.
- [ ] Viết tests mapping method/function cùng tên ở các file, nested/duplicate definitions, file/class/module candidates, Test excluded và ambiguous function. Function không map được lưu unmapped; không đoán theo tên gần giống.
- [ ] Viết tests source revision/hash/corpus/query mismatch, byte range/Unicode/CRLF và snippet-source mismatch. Giữ convention range từ contract/source evidence, không tự đổi byte column sang ký tự.
- [ ] Kiểm gold cases add/delete/rename/multi-function/unparseable source mà extractor đang hỗ trợ. Thiếu label/function coverage phải báo denominator riêng, không cho None thành0 hoặc chọn function gần nhất.
- [ ] Chạy tests; chỉ sửa bug consumer/scorer M2 có failing test. Nếu node/span/candidate sai từ producer, lưu minimal repro và ghi `DEPENDENCY_M1`; không sửa builder/resolver/ranking.
- [ ] Đối chiếu trực tiếp M1 output thật trên một repo mẫu bằng graph runner/Python API hiện có, validate ContextPayload/native source evidence, rồi mapping/scoring M2; không cần phát triển MCP context flow.
- [ ] Lập handoff gồm fields/conventions, profile/hash, valid case, mismatch case, coverage và unresolved examples. Gửi để người phụ trách M1 review/xác nhận; không tự ký thay hoặc đánh task phối hợp HT khi chưa có evidence phối hợp.

**Gate S3:** Consumer regression pass, mapping diagnostics thật và handoff M1 có xác nhận. Nếu producer chưa cung cấp dữ liệu đúng/sign-off, M2 code có thể hoàn tất nhưng M2-04 vẫn MP với blocker cụ thể.

## 10. S4 — Retrieval evaluation sơ bộ trên dev25

**Task chính:** `W05-06-M2-03`; evidence thực nghiệm cho M2-04. Không nhận nhiệm vụ cải thiện ranking M1.

### 10.1. Protocol cố định

| Hạng mục | Quy định |
| --- | --- |
| Dataset | SWE-bench Verified, revision đề xuất giữ từ manifest lịch sử: `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` |
| Split | Dev deterministic theo splitter hiện có; không heldout |
| Sample | 25 multi-file Python tasks theo eligibility/round-robin hiện có; lưu IDs và selection audit |
| Retrieval source | Repo tại `base_commit`; không áp developer source patch khi indexing |
| Query chính | Issue/problem_statement, không gold paths/diff/oracle FAIL_TO_PASS |
| BM25 | k1=1.2, b=0.75, function/code chunks hiện có; không tuning |
| Graph | Profile hiện có/static, 2 hops,100 candidates, confidence0.6 và weights hiện tại; không thêm risk profile hoặc đổi resolver |
| Budget/counter | 8000; cùng verified tokenizer/counter label, hash và packing policy giữa arms |
| Rank units | Dedup theo file/function **trước k**, đúng `metrics.py` hiện có; không coi10 chunks cùng function là10 functions |
| Runtime | 1 worker; Graph timeout300s/task ban đầu; pilot trước khi freeze full profile |
| Labels | Gold file/function chỉ được scorer đọc sau khi rank đã freeze; log rank hash |
| Đối chứng | Graph issue-only vs BM25 issue-only, BM25 full ranking |
| Diagnostics sẵn có | `graph_f2p` là oracle diagnostic; `bm25_capped` là cap diagnostic, không dùng làm headline baseline hoặc tuyên bố ablation A0–A3 |

Tokenizer bundle hiện có: Qwen3-4B-Instruct-2507 revision `cdbee75f17c01a7cc42f958dc650907174af0554`, bốn files tokenizer được manifest kiểm hash. Đây **không phải chọn/chạy reasoning hoặc coding model**. Nếu thiếu bundle, có thể dùng provision script hiện có để lấy tokenizer-only; không sửa M1 counter hoặc tải weights.

### 10.2. Các bước

- [ ] Nhận/khôi phục raw dev run cũ nếu cùng source/config/hash đủ. Nếu không tương thích, tạo run mới, giữ evidence lịch sử và giải thích vì sao không reuse.
- [ ] Dùng `prepare_manifest.py` hiện có với revision explicit, dev count25/min-source-files2; lưu archive/patch/corpus hashes. Tái dùng downloads đúng hash; không sửa script trừ lỗi M2 cần thiết.
- [ ] Chạy/kiểm BM25 và gold extraction tests trước workload lớn; giữ rank freeze, labels không ảnh hưởng retrieval candidates.
- [ ] Pilot3 từ cùng manifest, lưu timings/RSS/failure stage. Nếu lỗi package/tokenizer/input, sửa trong M2 hoặc ghi dependency. Nếu M1 runtime lỗi hai lần, dừng Graph profile, không tự chỉnh M1; BM25 vẫn tiếp tục.
- [ ] Freeze timeout/source/config sau pilot. Nếu đổi timeout sau đo, lưu profile riêng và áp policy thống nhất cho run mới; không ghép hai profile khác nhau âm thầm.
- [ ] Chạy BM25 và Graph dev25 bằng scripts hiện có. Per-task worker Graph giúp giải phóng RAM; không giữ nhiều graph của các repository trong kernel/process chính và không chạy cả hai arms đồng thời.
- [ ] Nếu có lỗi runner M2 thiếu bounds/cleanup, chỉ sửa runner/evidence phía M2 với failing test. Không tối ưu graph algorithm, đổi anchors/weights hoặc tăng tài nguyên để lấy số đẹp.
- [ ] Dùng `compare_graph_vs_bm25.py`/`compare_runs` hiện có. Xác minh same manifest/dataset/counter/scoring/snippet policy, per-task query/corpus/base commit/patch hashes trước comparison; bổ sung guard M2 nếu thiếu, không bypass để tạo bảng.
- [ ] Ghi tất cả25 task attempted, trạng thái và failure lý do; paired metrics trên intersection hợp lệ, N rõ cho từng metric. Mục tiêu25/25; tối thiểu20 valid pairs để đáp ứng evaluation sơ bộ20–30 tasks.
- [ ] Bảng/report được sinh từ raw JSON, không chép bảng21pair lịch sử. Review vài cases mapping lỗi/tốt/kém để giải thích; không cherry-pick case thành bằng chứng Graph tốt hơn.
- [ ] Không yêu cầu Graph phải thắng BM25 để đóng task chạy evaluation. Kết quả negative phải giữ, kèm giới hạn producer và labels.

### 10.3. Output và metrics

Raw ở `results/retrieval/<run-id>/result.json` và `tasks/<instance_id>.json`; comparison có `REPORT.md`/result và link hai run nguồn. Dataset/manifest ở `data/manifests/`; archive/gold paths theo manifest, không đoán đường dẫn khi chạy.

- File/function Recall@3/5/10: tỷ lệ gold labels được top-k unique files/functions tìm thấy.
- MRR: vị trí label relevant đầu tiên; công bố eligible denominator, labels không đầy đủ là ineligible chứ không tự gán0.
- Rank-mode và packed-mode coverage tách nhau; snippet không vừa budget có thể không xuất hiện trong context dù có trong ranking.
- `context_tokens`, token counter/hash và cùng snippet policy; là context cost, không phải USD/API tokens của model.
- Attempted/completed/failed, valid paired N, mapping/unmapped/parse failures; seed0 và bootstrap CI hiện có nếu report sinh được.
- Native M1 context tokens không trộn với fair packed metrics của scorer; report giải thích hai policy nếu cả hai được lưu.

**Gate S4:** Có raw artifacts đúng provenance cho ít nhất20 valid task pairs trong manifest25 và bảng tự regenerate được. Nếu21 pairs thì ghi21 valid/25 attempted cùng4 failures; không nói25 đều pass. Nếu dưới20 pairs, M2-03 giữ CX/MP và report blocker; BM25 completed riêng không đủ gọi paired evaluation hoàn thành.

## 11. S5 — Nghiệm thu M2 và cập nhật bàn giao

**Files:** `Task Status.md`, `PROGRESS.md`; tạo `docs/handoff/m2-w3-w6/BAO_CAO_HOAN_THIEN_M2_TUAN_3_6.md`, cập nhật `UNFINISHED_TASKS.md`.

**Các bước:**

- [ ] Chạy tests M2 và tests boundary trực tiếp bị thay đổi; giữ evidence riêng từng invocation. Không chạy lại toàn bộ benchmark nếu chỉ đổi Markdown/report.
- [ ] Kiểm allowlist diff: không sửa graph builder/resolver/retrieval, resource/flow M3, HF/model hoặc task tuần7+. Adapter ngoài package M2 chỉ có lease/runner/integrity wiring đã nêu.
- [ ] Kiểm raw report có IDs/hashes/counter đúng và task failures không biến mất; source gốc unchanged các fixture safety test.
- [ ] Cập nhật đúng 8 ID M2: 5 HT giữ nguyên nếu không regression; 3 mục còn mở chỉ HT khi đạt gate tương ứng. Không thay status các ID M1/M3/task chung.
- [ ] Ghi báo cáo: trước/sau bug M2, files changed, tests actual passed/failed/skipped, inputs/outputs cụ thể, retrieval metrics, dependency blockers và giới hạn.
- [ ] Checkpoint ghi source HEAD/dirty, milestone gần nhất, receipt paths, phương pháp đã fail hai lần và next action. Không commit/push.

Không cần full HF suite để kiểm M2 lightweight; nếu full suite không chạy hoặc còn failure đã biết thì ghi rõ. “M2 đạt acceptance” không đồng nghĩa “toàn repo/end-to-end LLM đã pass”.

## 12. Evidence và cấu trúc bàn giao

```text
VGAR/
  docs/superpowers/plans/2026-10-13-hoan-thien-m2-vgar-tuan-3-6.md
  docs/handoff/m2-w3-w6/
    protocol.md
    CONTEXT_GOLD_HANDOFF.md
    UNFINISHED_TASKS.md
    BAO_CAO_HOAN_THIEN_M2_TUAN_3_6.md
  artifacts/m2/test-runs/<timestamp-run-id>.json
  results/retrieval/<run-id>/
    result.json
    tasks/<instance_id>.json
    REPORT.md                    # ở comparison/report run nếu đã sinh
  data/manifests/<manifest>.json
  PROGRESS.md
  Task Status.md
```

Các file bàn giao/tests mới ở trên là **dự kiến tạo sau xác nhận**. `artifacts/m2/test-runs` hiện dùng mỗi invocation một JSON filename, không ép đổi thành directory/result.json gây thay format đang hoạt động.

Mỗi test invocation lưu run/task ID, start/end UTC, duration monotonic, interpreter, command/argv/cwd, stdout/stderr/exit, counts/skip/timeout, status/completeness và source hashes. Benchmark lưu thêm dataset/base commit/config/counter/scoring/hash, all task results và denominators. Pending/interrupted record được giữ, không suy success.

`UNFINISHED_TASKS.md` có ID, milestone, nguyên nhân cụ thể, evidence, profile/SHA/input đã thử, số failures, phương pháp không lặp lại và điều kiện retry. Resume chỉ dùng complete artifact đúng hash/config, không lấy “run mới nhất” nếu nó là smoke3 để thay full25.

## 13. Lệnh kiểm thử dự kiến sau khi plan được duyệt

Đây là commands hướng dẫn triển khai, **chưa được chạy trong phiên lập plan**. Tests mới chưa tồn tại trước implementation; việc install chỉ làm khi cần, không lặp mỗi session.

```powershell
# MỖI SESSION: khai báo interpreter thật, tránh lỗi & $python khi biến chưa có giá trị.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path -LiteralPath '.\.venv-m2-w3-w6\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'

# SAU S1/S2: chạy tests và lưu evidence bằng script M2 có sẵn.
& $python scripts/record_m2_test.py tests/m2/test_workspace.py tests/m2/test_access_policy.py tests/m2/test_workspace_adapter.py tests/m2/test_test_runner.py tests/m2/test_baseline.py tests/m2/test_evidence_writer.py --task-id m2-w3-w4-acceptance --timeout-seconds 120
$LASTEXITCODE

# SAU S3: regression consumer/mapping/BM25/gold, không chạy lại graph algorithm M1.
& $python scripts/record_m2_test.py tests/m2/test_context_gold_handoff.py tests/m2/test_retrieval_scoring.py tests/m2/test_graph_arm.py tests/m2/test_retrieval_evaluation.py --task-id m2-w5-w6-handoff --timeout-seconds 120
$LASTEXITCODE

# CHỈ KHI CHƯA CÓ MANIFEST TƯƠNG THÍCH: chuẩn bị input dev25, không Docker/test environment50.
& $python scripts/prepare_manifest.py . --count 25 --split dev --min-source-files 2 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
```

Lệnh benchmark sử dụng paths từ receipt đã kiểm, không dán run cũ hay đoán file manifest:

```powershell
# Các biến sau được lấy từ protocol/receipt của lần chạy hiện tại:
# $manifestPath = manifest dev25 đã pin; $tokenizerManifestPath = manifest tokenizer đã kiểm hash.
& $python scripts/run_bm25_retrieval.py . $manifestPath --tokenizer-manifest $tokenizerManifestPath --budget-tokens 8000 --limit 3
& $python scripts/run_graph_retrieval.py . $manifestPath --tokenizer-manifest $tokenizerManifestPath --budget-tokens 8000 --task-timeout 300 --limit 3

# Sau pilot gate mới chạy dev25: bỏ --limit 3; không chạy cả hai arms đồng thời.
# $bm25RunPath/$graphRunPath phải là cùng protocol/full25, lấy từ run receipts.
& $python scripts/compare_graph_vs_bm25.py . $bm25RunPath $graphRunPath --seed 0
```

Khi implementation hoàn tất, hướng dẫn bàn giao sẽ ghi cụ thể cách đọc receipt/tự tìm run **đúng kind/manifest/profile/complete**, không yêu cầu người dùng tự nhớ timestamp. Không chọn latest folder mù quáng hoặc tự động coi exit0 của compare là đủ20 valid pairs.

## 14. Ước lượng và tiêu chí kết thúc

| Milestone | Công sức chủ động dự kiến | Điều kiện phụ thuộc |
| --- | --- | --- |
| S0 | 1–2 giờ | Interpreter/input/evidence tương thích |
| S1 | 3–5 giờ | Wiring lease được phép tích hợp theo mục4.2 |
| S2 | 2–3 giờ | Regression và subprocess/Windows guards |
| S3 | 2–4 giờ + review M1 | M1 output hợp lệ/sign-off; không tự sửa producer |
| S4 | 2–4 giờ + runtime | Source archives/tokenizer; one worker; ít nhất20 valid pairs |
| S5 | 1–2 giờ | Kết quả/tests/receipts đầy đủ |

Tổng ước lượng **11–20 giờ chủ động**, chưa tính download/benchmark/chờ team review. Đây là ước lượng, không phải kết quả chạy. Đo ETA từ pilot3 trước khi hứa thời gian full25.

M2 plan này không gọi API LLM, không cần GPU, không làm Docker50. Sử dụng phần mềm/dataset hiện có; không tự thuê cloud/nâng tài nguyên. Máy vẫn có thể gặp pressure khi build graph dependency; khi đó lưu stage/RSS/timeout và bàn giao M1, không chuyển thành task tối ưu graph ngoài scope.

**Nghiệm thu tốt nhất:** 8 task M2 đạt đúng phạm vi, 3 task còn mở có evidence mới, guard tích hợp đúng, ≥20 valid paired task results và handoff M1 được xác nhận. Nếu adapter integration hoặc M1 sign-off/runtime chưa đủ, bàn giao phần M2 đã xong với status partial — không gọi100% chỉ vì đã viết tests/docs.

## 15. Xác nhận trước khi triển khai

Đề xuất triển khai **Native** để tiết kiệm token và giữ thay đổi nhỏ. Cần người dùng xác nhận plan mới này; xác nhận bao gồm adapter wiring tối thiểu phục vụ M2-01, **không** bao gồm thực hiện các task M1/M3 đã loại ra.

Sau xác nhận: kiểm trạng thái hiện tại và bắt đầu S0. Không chạy milestone M0–M8 của plan rộng cũ. Chưa sửa code, cài dependency, chạy test/benchmark hoặc thay trạng thái task trong phiên lập kế hoạch này.
