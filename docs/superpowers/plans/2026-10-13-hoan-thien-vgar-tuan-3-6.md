# Hoàn thiện VGAR tuần 3–6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Dùng `superpowers:executing-plans` nếu triển khai Native; dùng `superpowers:subagent-driven-development` chỉ khi người dùng chọn cách đó. Thực hiện từng milestone, kiểm thử rồi cập nhật checkpoint. Các bước `- [ ]` dưới đây **chưa được triển khai theo kế hoạch này**.

**Goal:** Hoàn thiện hoặc xác minh đủ 16 task đang có trạng thái MP, CT, CX trong tuần 3–6 của `Task Status.md`, dựa trên code và evidence thật, không mở rộng sang tuần 7 trở đi.

**Architecture:** Giữ Tree-sitter, graph Python, SQLite, task overlay, retrieval hiện có và ba MCP server stdio. Sửa hẹp lỗi binding/resource và quyền truy cập workspace; tái sử dụng pytest runner, DTO context, gold-label extractor và evaluation scripts. Tách workload retrieval trên source khỏi workload kiểm tra môi trường SWE-bench bằng Docker; không chạy coding agent hoặc LLM trong kế hoạch này.

**Tech Stack:** Python trong khoảng hiện có `>=3.11,<3.14`, ưu tiên Python 3.11; Tree-sitter `0.25.2`, grammar Python `0.25.0`; SQLite; MCP và LangChain adapters; pytest; tokenizer-only Qwen; SCIP/Pyright runtime theo npm lock; SWE-bench harness/Docker cho nhánh environment readiness.

**Spec:** [project_plan_16_weeks.md](D:/Project/CAPSTONES/New_task/project_plan_16_weeks.md), riêng các mục tuần 3–4 và 5–6; [Task Status.md](<D:/Project/CAPSTONES/VGAR/Task Status.md>), mục 5.2–5.3. Các tài liệu proposal/research khác chỉ hỗ trợ giải thích, không thay thế scope này.

**Trạng thái tài liệu:** Đề xuất để người dùng review và xác nhận. Việc viết file này không đồng nghĩa đã sửa code, chạy benchmark hoặc hoàn tất 16 task.

## Global Constraints — các giới hạn chung

- Chỉ sửa repo `D:/Project/CAPSTONES/VGAR`. Không sửa hệ thống cũ, notebook fine-tune, `M2_week_3+4`, `M2_week_5_6` hoặc các clone khác.
- Không làm lại các task HT. Có thể chạy regression liên quan để chứng minh thay đổi không phá phần HT.
- Giữ nội dung đã sửa/chưa commit. Không reset, checkout đè source, xóa repo hoặc apply stash cũ.
- Giữ SQLite và cấu trúc package hiện có; không quay lại Jedi, không thêm Kùzu, GNN, CFG/PDG hoặc full Arch-CPG.
- Không triển khai sinh unified diff bằng LLM, repair loop, type/lint/API verification, ranking patch, full ablation A0–A3 hay fine-tune: các phần đó nằm ngoài tuần 3–6.
- Không thêm `schema_version` vào DTO đã freeze; giữ tên/chữ ký public MCP tools và cấu trúc `ContextPayload`. Runtime config, diagnostic sidecar và CLI option mới phải được phân biệt với public contract.
- Chỉ dùng development tasks. Không dùng gold patch, gold-file/function hoặc oracle test labels làm đầu vào ranking/anchor chính.
- Mỗi lần kiểm thử/chạy lệnh có một evidence JSON độc lập, ID duy nhất, stdout/stderr và thời gian; không chỉ chép dòng “PASS” vào tài liệu.
- Một task/profile thất bại hai lần thì dừng profile đó, ghi nguyên nhân/phương pháp đã thử và chuyển sang task không phụ thuộc. Không tự tăng RAM, mua cloud hoặc đổi benchmark để che lỗi.
- Không commit/push trong kế hoạch này nếu chưa có yêu cầu riêng. Không tự xóa cache Docker dùng chung hoặc di chuyển ổ đĩa.

## Review Focus — năm trường hợp cần kiểm thử rõ

1. Explicit import trỏ ra module khác nhưng trùng tên function nội bộ: phải giữ unresolved, không tạo CALLS sai. Milestone M1 chịu trách nhiệm.
2. MCP resource dùng node ID có `:`, `/`, `%` hoặc được percent-encode: round-trip đúng, chỉ decode một lần tại URI boundary. M1 chịu trách nhiệm.
3. Tool nhận đường dẫn ngoài workspace đã được host cấp, hoặc pytest chỉ skip/không có JUnit hợp lệ: không sửa repo gốc và không báo test PASS giả. M2 chịu trách nhiệm.
4. Source/hash/graph version/tokenizer hoặc task overlay không khớp: phải từ chối context/cặp evaluation, không so sánh âm thầm hai snapshot khác nhau. M4–M5 chịu trách nhiệm.
5. Docker engine không sẵn sàng, hết dung lượng, timeout hoặc harness tái dùng report cũ: phải lưu trạng thái chặn/thất bại, không cộng vào số task runnable. M6 chịu trách nhiệm.

---

## 1. Kế hoạch này giải quyết điều gì?

Hiện repo đã có nhiều module cần thiết. Vấn đề không phải “viết lại toàn bộ”, mà là ba loại khoảng trống:

- **MP — hoàn thành một phần:** Có implementation nhưng còn lỗi cụ thể, chưa có chạy thật hoặc có khác biệt chưa được duyệt so với plan.
- **CT — chưa triển khai:** Thiếu workflow/deliverable mà code hiện tại chưa cung cấp.
- **CX — chưa xác minh:** Tài liệu nói đã làm hoặc có số liệu lịch sử, nhưng chưa đủ raw evidence/provenance để xác nhận cho checkout hiện tại.

**HT — hoàn thành** chỉ được dùng đúng phạm vi của từng task. Ví dụ, BM25 chạy và có bảng retrieval không có nghĩa agent đã sửa được lỗi; 50 task runnable không có nghĩa đã chạy 50 lần repair bằng LLM.

Mục tiêu cuối là một bộ bàn giao có source hoạt động, kết quả tái lập được và trạng thái trung thực. Nếu tài nguyên hoặc phê duyệt liên nhóm chưa đủ, task tương ứng giữ chưa hoàn thành kèm blocker, không tự chuyển HT.

## 2. Điểm xuất phát đã kiểm tra

### 2.1. Source và worktree

| Hạng mục | Trạng thái tại lúc lập kế hoạch |
| --- | --- |
| Repo | `D:/Project/CAPSTONES/VGAR` |
| Branch | `integration/main-m1-w5-w6-20261013` |
| HEAD | `73814b8f89666c71b1911e42e98b8ecc7f6e3e99` |
| Nền main | `b39e0dbf87645d39b9a68e87b19d0655df264a05`, đã fast-forward với nhánh M1 |
| `git diff` trước khi viết kế hoạch | Không có diff source sản phẩm |
| Các additions cần giữ | `PROGRESS.md`, `Task Status.md`, `docs/audit/` chưa track |
| Checklist tuần 3–4 | 22 mục: 16 HT, 5 MP, 1 CX |
| Checklist tuần 5–6 | 20 mục: 10 HT, 5 MP, 1 CT, 4 CX |
| Phạm vi cần xử lý | 16 mục: 10 MP, 1 CT, 5 CX |

Evidence audit hiện có ở `docs/audit/2026-10-13/`; đó là evidence **trước sửa**, phải giữ nguyên. Khi triển khai cần kiểm tra status/diff/checkpoint mới, không mặc định HEAD vẫn giống ngày lập kế hoạch.

### 2.2. Kết quả có thật nhưng không được diễn giải quá mức

| Evidence đã có | Ý nghĩa đúng |
| --- | --- |
| Main baseline: 196 passed, 1 skipped | Baseline trước tích hợp; không phải nghiệm thu checkout sau tích hợp |
| Integrated suite: 411 passed, 1 failed, 2 skipped | Có regression tại `test_hf_model.py`, chưa được nói toàn suite xanh |
| Scripted smoke: 16 checks, 6 calls PASS | MCP/orchestration chạy với edit được lập trình sẵn; không phải LLM thật |
| Strict MCP smoke FAIL tại encoded node resource | Có lỗi resource transport cần sửa ở M1 |
| Probe external import sinh false CALLS | Có lỗi binding cần sửa, không chỉ thiếu tài liệu |
| Probe root ngoài lease vẫn sửa được | Cần server-side guard, prompt nhắc “không sửa repo gốc” chưa đủ |
| Probe pytest all-skipped bị PASS | Cần sửa acceptance semantics của runner, không chỉ dựa exit code 0 |
| Handoff có số dev25/21 pairs lịch sử | Chưa có raw run tại clone này; không được đưa thành kết quả hiện tại |

Failure `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config` là lệch test/constructor contract liên quan generation config; audit **không chứng minh inference thật bị crash**. Sửa toàn bộ HF/coding runtime không thuộc kế hoạch tuần 3–6 này. M8 vẫn ghi failure nếu còn, không giấu bằng cách gọi toàn suite đã pass.

## 3. Danh sách 16 task và điều kiện đóng

ID trong bảng được giữ nguyên từ `Task Status.md`. “M1, M2...” ở cột milestone dưới đây là **mã milestone của kế hoạch**, không phải đổi người sở hữu M1/M2/M3 trong nhóm.

| ID trong Task Status | Hiện tại | Việc còn thiếu | Milestone | Điều kiện để chuyển HT |
| --- | --- | --- | --- | --- |
| W03-04-M1-04 | MP | Nghiệm thu symbol resolver/indexer thật | M3 | SCIP strict chạy trên 1–2 repo mẫu; có runtime lock, source hash, index hash, số resolved/unresolved; không lấy static fallback làm SCIP PASS |
| W03-04-M1-05 | MP | Chặn false external-import binding | M1 | Regression negative và direct/alias/relative calls pass; confidence/provenance còn đúng |
| W03-04-M2-01 | MP | Bind workspace quyền ghi và integrity | M2 | MCP từ chối root ngoài lease; patch chỉ trên copy; source unchanged trên cả success/failure/timeout |
| W03-04-M3-02 | MP | Node/subgraph resource round-trip | M1 | Summary/node/subgraph đọc thành công qua stdio; encoded ID trả đúng node và version |
| W03-04-DOD-01 | MP | Callers/callees/imports hợp lý sau sửa binding | M1, M3 | Queries fixture + sample hiện tại đúng; false edge đã bị loại và được kiểm tra thủ công |
| W03-04-DOD-02 | CX | Manual validation ít nhất 20 edges hiện tại | M3 | 20 annotations có source/provenance/expected/actual và reviewer trong nhóm xác nhận |
| W05-06-CHUNG-03 | MP | Evidence retrieval sơ bộ thật | M5 | Run BM25/Graph đúng protocol trên 20–30 task, có raw artifacts, lỗi và denominators |
| W05-06-M1-03 | MP | Biểu diễn failing test khác literal FailingTest | M4 | Test/Issue/REPRODUCES được M1/M3 duyệt tương đương bằng ADR; nếu không duyệt, giữ MP và xử lý contract riêng |
| W05-06-M1-06 | MP | API-risk mặc định đang có weight 0 | M5 | Profile risk khác 0 có tests và evaluation; quyết định default/deviation được lưu, không nói feature tác động rank khi weight còn 0 |
| W05-06-M2-03 | CX | Raw retrieval evaluation 20–30 tasks | M5 | Manifest dev25, attempted/completed/failed rõ; ít nhất 20 valid paired task results, không xóa task timeout |
| W05-06-M2-04 | MP | Context/gold mapping handoff có evidence | M4, M5 | M1 payload qua adapter/validator trên cùng source; coverage/mapping failures lưu; M1/M2/M3 sign-off |
| W05-06-M3-02 | MP | Chạy issue → anchors → context → display | M4 | Tokenizer assets xác thực; LangChain/MCP smoke thật, overlay nhất quán và context đúng budget |
| W05-06-M3-03 | CT | 50–100 task có môi trường thực sự runnable | M6 | Tối thiểu 50 task có baseline/gold/test oracle hợp lệ theo tiêu chí M6; source archive đơn thuần không tính |
| W05-06-M3-04 | CX | Draft Related Work graph/retrieval | M7 | Có draft với nguồn gốc/primary sources, giải thích phương pháp và hạn chế; không lấy README thay Related Work |
| W05-06-DOD-01 | CX | Bảng Graph vs BM25 tái sinh từ raw | M5 | Recall@3/5/10 file/function và token cost; paired IDs/config/source khớp; bảng regenerate được |
| W05-06-DOD-02 | CX | Manual inspect ít nhất 10 retrieval tasks | M5 | 10 hồ sơ rubric và context/gold mapping; đánh giá tốt/một phần/kém có lý do, được người trong nhóm review |

Không có task nào trong bảng được tự tick chỉ vì đã tạo file giải thích hoặc checklist.

## 4. Các quyết định đề xuất cần review

### 4.1. Cách biểu diễn failing test

**Đề xuất:** Giữ node `Test` hiện có, node `Issue` và edge `REPRODUCES` của task overlay. Ghi rõ failing test là báo cáo của task, chưa phải kết quả test execution. Cách này tránh thêm node type làm lệch schema/consumer của M1 và M3.

Plan chính có ghi `Issue`/`FailingTest`. Vì vậy, cần ADR `docs/adr/w3-w6-failing-test-representation.md` nêu mapping tương đương và được M1/M3 xác nhận. **Đây là đề xuất của người lập kế hoạch, chưa phải lựa chọn đã được người dùng duyệt.** Nếu nhóm bắt buộc literal `FailingTest`, không tự đổi contract; ghi task MP và xin duyệt thiết kế nhỏ trước khi sửa schema/ID/consumer.

### 4.2. Public API risk trong ranking

**Đề xuất:** Giữ baseline v10 để có đối chứng; thêm đúng một profile thử nghiệm với `public_api_risk=0.10`, giữ nguyên các weight khác và cách normalize hiện có. Không chạy tuning sweep, không nhìn heldout, không đổi gold labels để cải thiện số.

Profile mới phải chứng minh risk thực sự làm thay đổi score trong fixture. Chỉ đề nghị đổi default nếu mean function Recall@5 tăng và mean file Recall@5/packed gold coverage không giảm trên paired dev set; số mẫu hợp lệ và CI phải công bố. Tiêu chí này là quy tắc lựa chọn kỹ thuật, không phải lời hứa thống kê có ý nghĩa.

Nếu không đạt, giữ baseline, báo kết quả negative và xin nhóm duyệt việc default tắt risk. Không được tự kết luận mục “rank theo API risk” đã đáp ứng mặc định khi weight vẫn 0. Một profile có thể đóng phần implementation/evaluation, nhưng đóng task toàn bộ còn phụ thuộc quyết định ghi trong ADR.

### 4.3. Hai workload dataset khác nhau

- **Retrieval:** 25 task dev multi-file Python; mục tiêu 25/25 có kết quả hợp lệ, tối thiểu 20 valid paired results để đáp ứng evaluation sơ bộ 20–30 tasks. Giữ failures của toàn manifest trong báo cáo; nếu chỉ có 21 valid pairs, ghi `PARTIAL`, không viết “25 task đều chạy thành công”.
- **Environment readiness:** Tối thiểu 50 task dev, có thể gồm single-file và multi-file để đủ pool. Plan tuần 5–6 không bắt buộc cả 50–100 đều multi-file. Report riêng số mỗi loại và task nào trùng dev25; không tăng sample bằng task heldout.

Đo retrieval chỉ cần source tại base commit. Nghiệm thu runnable cần dependency environment, test_patch và oracle thực chạy. Hai việc không thay thế nhau.

## 5. Trình tự và phụ thuộc

```text
M0: freeze đầu vào, evidence, môi trường nhẹ
 ├─ M1: sửa binding + MCP resources ── M3: resolver thật + kiểm 20 edges
 ├─ M2: workspace lease + runner acceptance
 └─ M4: config + tokenizer + context flow/handoff
          └─ M5: paired dev25 + risk profile + manual10

M6: SWE-bench readiness50, chỉ chạy Docker sau resource gate
M7: Related Work, có thể làm trong khi M6 bị chặn
M8: nghiệm thu, cập nhật Task Status + PROGRESS + báo cáo bàn giao
```

M4 có thể chuẩn bị song song về mặt công việc với M1/M2, nhưng chạy smoke nghiệm thu sau M1. Không bắt buộc dùng nhiều agent/process: mặc định Native và một worker benchmark để hạn chế RAM/token. M6 không được chặn việc bàn giao M1–M5/M7 nếu engine hoặc tài nguyên chưa sẵn sàng.

## 6. Quy ước output và evidence xuyên suốt

Mọi đường dẫn không có drive dưới đây tương đối với `D:/Project/CAPSTONES/VGAR`. Đường dẫn ở phần “Tạo” là **file dự kiến**, chưa tồn tại chỉ vì được liệt kê trong plan.

```text
VGAR/
  PROGRESS.md                         checkpoint mới nhất, điểm dừng thật
  Task Status.md                      trạng thái từng ID, link evidence
  docs/superpowers/plans/             kế hoạch đang review
  docs/adr/                          quyết định representation/ranking/limits
  docs/handoff/w3-w6/                 sign-off và báo cáo bàn giao
  data/manifests/                     retrieval dev25 đã pin
  data/readiness/                     oracle sidecar riêng, không vào query
  artifacts/w3-w6/
    commands/<run-id>/result.json     mỗi invocation một bản ghi tổng
    tests/<run-id>/result.json        TestRunResult + command/log/timing
    resolver/<run-id>/               graph, index, manifest, annotations20
    mcp-context/<run-id>/             anchors, context, audit, hashes
    readiness/<run-id>/              preflight + per-task baseline/gold
  results/retrieval/<run-id>/         raw BM25/Graph runs như code hiện có
  results/w3-w6/<run-id>/             comparison, manual10, tổng kết
```

### 6.1. Mỗi lần test/lệnh cần lưu gì?

Một `result.json` là entry point của invocation; stdout/stderr ngắn được giữ trong JSON, log lớn thành sidecar với hash và đường dẫn tương đối. Bản ghi có:

- `run_id`, `task_id` hoặc milestone ID, `started_at_utc`, `ended_at_utc` và `duration_seconds`.
- `command_argv`, `cwd`, interpreter/executable, exit code; không log token/password.
- Source HEAD, trạng thái dirty, source fingerprint, input/config/manifest hashes, package/runtime versions.
- Status và `complete`, timeout/output-limit/exception, đường dẫn outputs + SHA256.
- Với pytest: counts passed/failed/error/skipped, JUnit và `TestRunResult` thật.
- Với benchmark: tất cả task attempted/completed/failed, danh sách IDs, per-stage timing và metric denominator.
- Với guard tests: source hash trước/sau, workspace ID và expected/actual rejection.

`duration` đo bằng monotonic clock; UTC start/end dùng để đối chiếu. Không tính duration bằng “thời gian bắt đầu trừ thời gian kết thúc”.

Giữ pending record trước khi chạy; finalize atomic khi xong. Nếu bị ngắt, giữ record chưa complete, không suy PASS. Lệnh có exit 0 chỉ là process completed; muốn test/benchmark PASS cần điều kiện nghiệm thu của chính workload.

### 6.2. Quy tắc dừng và resume

Tạo `docs/handoff/w3-w6/UNFINISHED_TASKS.md` với cột ID, trạng thái, root cause, evidence, profile/SHA đã thử, số lần thất bại, phương pháp không nên lặp, điều kiện có thể chạy lại. Mỗi milestone xong hoặc dừng đều cập nhật `PROGRESS.md`.

Resume chỉ bỏ qua task đã complete **và** khớp toàn bộ source/config/dataset/tokenizer hash. Không dùng “folder có result.json” làm điều kiện duy nhất. Profile hoặc source đổi phải có run mới, giữ evidence cũ để đối chiếu.

## 7. M0 — Khóa đầu vào, môi trường nhẹ và ghi evidence

**Vai trò:** Điều kiện triển khai an toàn; không dùng milestone này để tự đóng 16 mục.

**Files:**

- Đọc/giữ: `PROGRESS.md`, `Task Status.md`, `docs/audit/2026-10-13/`.
- Tạo: `scripts/requirements_w3_w6.txt`, `scripts/record_command.py`, `tests/test_command_evidence.py`.
- Tạo: `docs/handoff/w3-w6/protocol.md`, `docs/handoff/w3-w6/UNFINISHED_TASKS.md`.
- Cập nhật progress, không sửa runtime/source khác trong milestone này.

**Interfaces:**

- Generic recorder CLI: `record_command.py --task-id ID --artifact-dir PATH --timeout-seconds N -- executable arg1 ...`.
- Output: command evidence theo mục 6, status `COMPLETED/FAILED/TIMEOUT/BLOCKED`; không giả lập `TestRunResult` cho npm/tokenizer/harness commands.
- Pytest tiếp tục dùng `scripts/record_m2_test.py` và writer hiện có. Recorder nhận một command dạng argv, không ghép shell command string.

**Các bước:**

- [ ] Đọc checkpoint, `git status --short`, `git diff` mới; lưu HEAD/dirty/source snapshot, giữ nguyên additions và stash.
- [ ] Khóa protocol chỉ tuần 3–6; copy 16 ID mục 3 vào acceptance checklist; phân biệt lỗi HF ngoài scope và test fixtures bị thay đổi khi initialize SQLite.
- [ ] Tạo môi trường `.venv-w3-w6` riêng nếu chưa có. Requirements tái sử dụng pin M1 hiện có, thêm `datasets==4.8.5` cho retrieval; không cài Torch, Transformers, PEFT, TRL, tải weights hoặc thay package của venv cũ.
- [ ] Nếu một exact pin không có package khả dụng, ghi `DEPENDENCY_UNAVAILABLE` và đề nghị pin tương thích; không âm thầm dùng interpreter khác rồi gọi clean-install PASS.
- [ ] Viết tests recorder: Unicode/space in path, process exit khác 0, timeout + child cleanup, redaction, pending/final atomic và `duration_seconds >= 0`.
- [ ] Chạy tests để thấy failure trước implementation recorder; viết tối thiểu rồi chạy lại. Tái sử dụng cách atomic write/cleanup của M2, không đổi schema EvidenceBundle.
- [ ] Xác minh import graph/contracts/MCP và kiểm tra package metadata. Tránh import model factory trong smoke nhẹ.

**Kiểm tra sau triển khai:**

```powershell
# Mỗi session: chọn interpreter rõ ràng, không phụ thuộc $python còn từ session cũ.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path -LiteralPath '.\.venv-w3-w6\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
& $python -m pytest tests/test_command_evidence.py tests/test_settings.py -q
```

**Gate:** Môi trường nhẹ import được; evidence của recorder và pytest readable/đúng timing. Đây là gate sẽ kiểm khi triển khai, chưa phải kết quả đã có.

## 8. M1 — Sửa binding sai và MCP resources

**Đóng:** W03-04-M1-05, W03-04-M3-02; đóng phần code của W03-04-DOD-01.

**Files:**

- Sửa: `src/vgar/graph/builder.py`, riêng `_resolve_symbol` và đường gọi liên quan.
- Sửa: `src/vgar/mcp/servers/graph_server.py`, boundary của node/subgraph resource.
- Bổ sung: `tests/test_graph_builder.py`.
- Tạo: `tests/test_mcp_resource_roundtrip.py`.

**Interfaces giữ nguyên:** Builder output schema; public MCP resource URI `vgar://repo/summary`, `vgar://graph/node/{id}`, `vgar://graph/subgraph/{id}`; graph version và node ID canonical không đổi.

**Các bước:**

- [ ] Viết `test_explicit_external_import_never_binds_same_named_internal_symbol`: fixture có `from other.module import helper` và một internal `helper`; assert không có CALLS từ callsite đó đến internal helper.
- [ ] Viết negative trường hợp alias, shadowing, unresolved receiver; giữ positive tests local/relative imports, direct call, class method đã hoạt động.
- [ ] Chạy regression trước sửa; chỉ sửa expectation lịch sử đang chấp nhận false edge sau khi ghi root cause, không xóa test để xanh.
- [ ] Sửa resolver: explicit import không resolve được về đúng module thì không rơi xuống unique-name fallback nội bộ; giữ unresolved/candidate diagnostics và provenance. Không nâng confidence để cứu binding không có bằng chứng.
- [ ] Viết stdio resource tests cho raw và encoded ID, Unicode, ID chứa literal `%`, node không tồn tại và subgraph; assert đúng node/version, error có cấu trúc.
- [ ] Decode URI parameter một lần đúng boundary; không dùng thao tác này cho repository paths. Test `%25`/double-encoded string để tránh decode hai lần hoặc đổi nghĩa literal ID.
- [ ] Chạy strict resource smoke và caller/callee/import regression sau sửa; lưu comparison false edge trước/sau.

**Commands dự kiến:**

```powershell
& $python -m pytest tests/test_graph_builder.py tests/test_mcp_resource_roundtrip.py -q
```

**Gate:** Node/subgraph transport thật pass, external-import negative pass và queries positive không mất edge hợp lệ. W03-04-DOD-01 chỉ đóng hoàn toàn sau manual sample ở M3.

## 9. M2 — Workspace lease và test acceptance thật

**Đóng:** W03-04-M2-01. Sửa các lỗi sát acceptance của wrapper HT, không viết repair loop mới.

**Files:**

- Tạo: `src/vgar/repair/access_policy.py`, `tests/m2/test_access_policy.py`, `tests/test_mcp_workspace_boundary.py`.
- Sửa hẹp: `src/vgar/config/settings.py`, `src/vgar/mcp/client.py`, `src/vgar/mcp/servers/repository_server.py`, `src/vgar/mcp/servers/execution_server.py`.
- Sửa: `src/vgar/repair/test_runner.py`; bổ sung `tests/m2/test_test_runner.py`, `tests/m2/test_workspace.py`.
- Chỉ để cấp lease trước khi tạo MCP client và kiểm integrity trên mọi terminal path: `src/vgar/cli.py`, `src/vgar/agents/nodes/prepare.py`, `src/vgar/agents/workflow.py`; có thể thêm field giữ lease vào `src/vgar/agents/runtime.py`. Không đổi planning/model/prompt logic.

**Interfaces:**

- Thêm config nội bộ `WorkspaceSettings(source_root: Path | None, workspace_root: Path | None, worktree_id: str | None, mutation_enabled: bool = False)` trong `Settings`.
- Host cấp các giá trị từ `WorkspaceLease` do `create_workspace(...)` hiện có tạo, rồi tạo MCP client. Không nhận quyền ghi từ model/tool arguments.
- Config env tương ứng: `VGAR_SOURCE_ROOT`, `VGAR_WORKSPACE_ROOT`, `VGAR_WORKTREE_ID`, `VGAR_ALLOW_MUTATION`; đọc tập trung trong settings và truyền qua `to_env()`.
- Guard: `require_workspace_root(repo_path: str, policy: WorkspaceSettings, *, mutation: bool) -> Path`; realpath phải bằng exact leased root, leased root khác source root, worktree ID hợp lệ và mutation được host bật.
- Giữ chữ ký `apply_patch(repo_path, path, old_text, new_text)` và `run_pytest(repo_path, selector, timeout_seconds=30)`; không đổi tool thành unified-diff API.

**Các bước:**

- [ ] Viết failing tests: root gốc, root sibling, traversal, absolute child path, symlink/junction escape bị từ chối; root đúng lease được phép; không config thì mutation fail closed.
- [ ] Thêm guard dùng chung; dùng safe-relative-path và kiểm file containment trước read/edit/test, không tin prefix string. MCP read/test cũng chỉ truy cập leased root của phiên được cấu hình.
- [ ] Bind lease từ host trước khi client spawn; default không có authorized workspace thì không được sửa. Migration docs phải nêu caller cũ tự đưa `repo_path` chưa đủ cấp quyền.
- [ ] Viết `test_all_skipped_is_verification_incomplete`, `test_exit_zero_without_valid_junit_is_incomplete`, `test_mixed_pass_skip_is_valid`; tests chỉ skipped hoặc thiếu/corrupt JUnit không được PASS. `passed > 0`, `failed == 0`, `error == 0` và JUnit hợp lệ là điều kiện PASS cùng exit 0.
- [ ] Dùng `run_tests(workspace, selectors, timeout_seconds)` hiện có trong execution MCP thay vì subprocess wrapper riêng. Giữ keys status/exit/selector/stdout/stderr/error mà consumer đang dùng; lấy counts/duration/reason từ TestRunResult trong diagnostics/evidence.
- [ ] Bound timeout MCP trong `(0,120]` giây, output theo giới hạn runner hiện có, child-process cleanup trên timeout và bỏ secrets khỏi child env. Đây là boundary tối thiểu của tuần 3–4, không phải triển khai policy/security toàn tuần 11–12.
- [ ] Chạy success, failed tests, timeout và internal error trên dummy repo; source fingerprint trước/sau phải bằng nhau trên mọi terminal path; only workspace modified và cleanup có exact target validation. Kiểm bằng injected/scripted agent hoặc client, không chạy HF thật để nghiệm thu guard.
- [ ] Chạy regression baseline/writer để chắc việc sửa acceptance không đổi evidence contract hoặc khiến assertion failure thành infrastructure PASS.

**Commands dự kiến:**

```powershell
& $python -m pytest tests/m2/test_workspace.py tests/m2/test_access_policy.py tests/m2/test_test_runner.py tests/m2/test_baseline.py tests/m2/test_evidence_writer.py tests/test_mcp_workspace_boundary.py -q
```

**Gate:** Mô hình/script không thể đổi writable root qua argument; source unchanged cả fail/timeout; pytest skip-only/không đầy đủ không PASS. Disposable copy + path guard không phải OS sandbox: không được dùng nó như bảo đảm chạy code thù địch trên host an toàn tuyệt đối.

## 10. M3 — Resolver thật và manual validation 20 edges

**Đóng:** W03-04-M1-04, W03-04-DOD-02 và phần quality của W03-04-DOD-01.

**Files tái sử dụng:** `configs/scip/package-lock.json`, `configs/lsp/package-lock.json`, `scripts/install_scip_runtime.ps1`, `scripts/install_lsp_runtime.ps1`, `scripts/build_graph.py`, `src/vgar/graph/scip_resolver.py`, `src/vgar/graph/scip_profile.py`, `src/vgar/graph/lsp_resolver.py`.

**Tạo:** `scripts/validate_w3_w6_edges.py`, `tests/test_edge_validation_report.py`; annotations/result trong `artifacts/w3-w6/resolver/<run-id>/`; sign-off ở `docs/handoff/w3-w6/edge-review.md`.

**Interfaces:** Annotation record có `edge_id`, `edge_type`, source/target IDs, file/span/source excerpt, expected/actual, confidence, provenance, resolver/index/source hashes, decision và rationale. Script kiểm đủ ít nhất 20 distinct emitted CALLS/IMPORTS; unresolved negative cases lưu riêng.

**Các bước:**

- [ ] Xác minh npm/runtime lock: `@sourcegraph/scip-python:0.6.6` và `pyright:1.1.414` trong file lock, không chạy `npm update` hoặc thêm Jedi.
- [ ] Cài vào nơi script đã quy định sau khi được phép tải. Path SCIP có chữ `w7-w8` là tên folder lịch sử, không làm việc nghiệm thu resolver tối thiểu thành task tuần 7–8; không rename folder lan rộng.
- [ ] Build `tests/fixtures/sample_repo` và một repo Python mẫu nhỏ thứ hai bằng SCIP strict. Ghi command thực, `.scip`/manifest/hash, số nodes/edges và resolver coverage. Chọn interpreter/import-root rõ ràng, giữ config repo mẫu nguyên vẹn.
- [ ] Nếu SCIP fail hai lần, giữ task MP và chuyển phần khác. Có thể đề nghị profile LSP đã lock như phương án thay thế; chỉ chạy sau khi ghi nguyên nhân khác biệt, không gộp SCIP fail + static pass thành nghiệm thu SCIP.
- [ ] Lấy ít nhất 10 CALLS và 10 IMPORTS từ hai repo mẫu, đọc source và annotate từng edge; kiểm cả local/relative/import alias/method và case external-import đã sửa. Fixture `sample_repo` hiện chỉ có 5 CALLS/5 IMPORTS: không lặp lại edges để đủ20. Dùng repo mẫu thứ hai có đủ phần còn thiếu; nếu cần tạo fixture riêng thì đặt ở `tests/fixtures/w3_w6_symbol_review_repo/`, giữ repo mẫu cũ nguyên vẹn. Thêm negative unresolved cases nhưng không cộng chúng thành emitted edge đúng.
- [ ] Người khác trong nhóm đối chiếu 20 annotations và ký xác nhận. Automated tests có thể kiểm tính đầy đủ/hashes, **không thay chữ ký manual reviewer**.
- [ ] Xuất report số đúng/sai/ambiguous, policy xử lý ambiguous, resolver coverage và mẫu chọn. Precision trên sample chỉ đại diện sample, không phải recall/precision toàn repository.

**Commands dự kiến:**

```powershell
& $python -m pytest tests/test_scip_enrichment.py tests/test_lsp_enrichment.py tests/test_edge_validation_report.py -q
# Build thật dùng scripts/build_graph.py với --resolver scip --strict-resolver,
# --scip-entry và --scip-python lấy từ installation receipt, không đoán đường dẫn.
```

**Gate:** Có strict indexer evidence trên 1–2 repo, queries hợp lý và 20 manual labels đã được review. Peer review chưa có thì giữ CX riêng dù script pass.

## 11. M4 — Context runtime, token assets và handoff

**Đóng:** W05-06-M3-02; phần code/contract của W05-06-M2-04; W05-06-M1-03 sau phê duyệt representation.

**Files:**

- Sửa: `src/vgar/config/settings.py`, `src/vgar/graph/factory.py`, `scripts/smoke_w5_w6_retrieval.py` để cấu hình và lưu output nhất quán.
- Tests: `tests/test_settings.py`, `tests/test_mcp_client.py`, `tests/test_context_contract.py`, `tests/test_source_evidence.py`; tạo `tests/test_context_runtime_handoff.py`.
- Tái sử dụng: `src/vgar/contracts/context.py`, `src/vgar/evaluation/retrieval/m1_adapter.py`, `gold_labels.py`, `scripts/provision_m1_tokenizer.py`, `scripts/accept_m1_tokenizer.py`.
- Tạo docs: ADR failing-test mục 4.1; `docs/handoff/w3-w6/context-gold-mapping.md`.

**Interfaces:**

- Thêm `repository_root: Path | None`, `tokenizer_manifest: Path | None` vào `GraphSettings`; serialize các env `VGAR_REPOSITORY_ROOT`, `VGAR_TOKENIZER_MANIFEST` qua Settings/to_env cùng backend/database/version.
- Giữ inputs `graph_version`, `task_id`, `issue_text`, `failing_tests` tường minh giữa hai MCP calls. Không cần task_handle mới hoặc persistent session mới.
- Giữ `ContextPayload`/`SourceRange`/`ContextItem`; diagnostic sidecar ghi source/tokenizer hashes và overlay ID, không nhét field mới vào DTO `extra=forbid`.
- Bổ sung `--output-directory PATH` cho retrieval smoke; lưu anchors/context/audit/manifest và return code rõ ràng.

**Các bước:**

- [ ] Viết tests Settings truyền đúng root/tokenizer theo phiên, env cũ không được làm query source khác; missing/root mismatch đưa lỗi có nghĩa, không fallback demo âm thầm.
- [ ] Cấu hình factory dùng Settings; giữ source hash/range verifier và explicit task inputs khi client mở session mới mỗi call.
- [ ] Provision **chỉ tokenizer assets**, không weights, từ `Qwen/Qwen3-4B-Instruct-2507` revision `cdbee75f17c01a7cc42f958dc650907174af0554`; kiểm filenames/SHA256 theo manifest, pin counting policy.
- [ ] Chạy acceptance tokenizer hiện có; thêm Unicode/CRLF/source span exactness vào handoff regression nếu chưa được các tests hiện tại phủ.
- [ ] Chạy flow trên sample repo qua LangChain adapters thật: build/persist → issue → anchors → related context → validate → display và save. Assert cùng overlay ID, đúng graph version, nguồn/range/hash, `total_token_count <= 8000`.
- [ ] Test issue rỗng/không có anchor, ambiguity, source sửa sau indexing, tokenizer assets sai/hash sai. Giữ diagnostics/unknown, không đoán target hay dùng gold để tạo anchor.
- [ ] Kiểm M1 payload sang M2 adapter và gold file/function labels trên cùng base source; deletion/addition/rename/function overlap/unmapped chunk có coverage rõ.
- [ ] Soạn ADR mapping Test + Issue + REPRODUCES; ghi rõ reported failing test không phải execution evidence. Thu sign-off M1/M2/M3 cho contract/gold handoff, không tự ký thay.

**Commands dự kiến:**

```powershell
& $python -m pytest tests/test_settings.py tests/test_mcp_client.py tests/test_context_contract.py tests/test_source_evidence.py tests/test_context_runtime_handoff.py tests/m2/test_retrieval_scoring.py -q
# Smoke dùng --tokenizer-manifest từ receipt đã xác thực và --output-directory riêng.
# Không import/tải model để chạy issue → context.
```

**Gate:** Context flow thật tái lập được trong clone mới; consumer validation và source/token counts pass. Tổng 8000 ở đây là snippets/context policy hiện có, không được gọi là tổng token toàn prompt repair. ADR/sign-off chưa được duyệt thì task liên quan vẫn MP.

## 12. M5 — Paired retrieval dev25, risk profile và manual10

**Đóng:** W05-06-CHUNG-03, W05-06-M2-03, W05-06-DOD-01, W05-06-DOD-02, phần empirical của W05-06-M2-04; W05-06-M1-06 theo quyết định mục 4.2.

**Files:**

- Tái sử dụng: `scripts/prepare_manifest.py`, `run_bm25_retrieval.py`, `run_graph_retrieval.py`, `compare_graph_vs_bm25.py`; toàn package `src/vgar/evaluation/retrieval/`.
- Sửa hẹp: `src/vgar/graph/retrieval.py` chỉ nếu cần expose profile; `scripts/run_graph_retrieval.py` thêm `--ranking-profile`; config/profile hash trong run evidence và cache key.
- Tạo: `configs/retrieval/w3-w6-v10-risk.json`, `scripts/inspect_retrieval_cases.py`, `tests/test_ranking_profile.py`, `tests/test_manual_retrieval_report.py`.
- Bổ sung regression hiện có: `tests/m2/test_dataset_split.py`, `test_retrieval_eval_graph.py`, `test_retrieval_scoring.py`, `test_retrieval_evaluation.py` khi metadata/protocol cần phủ.

### 12.1. Khóa dữ liệu và so sánh công bằng

**Dataset đề xuất:** SWE-bench Verified revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, cùng revision có trong manifest lịch sử `M2_week_5_6/data/manifests/verified-c104f840cc67-25.json`. Chỉ tái dùng archive đã có khi hash thực khớp. Không copy số liệu từ run cũ không cùng source/config vào report mới.

Giữ splitter deterministic hiện có: hash `instance_id`, bucket dưới 40 là dev; phần còn lại heldout. Select 25 dev với patch sửa ít nhất hai source files, theo repository round-robin hiện có. Lưu IDs, repo/base commit, patch hash, eligibility, raw dataset hash và selection audit. Không tự khẳng định toàn dataset có chính xác 70/71 task.

Protocol chính:

| Tham số | Giá trị/quy tắc |
| --- | --- |
| Query | `problem_statement`/issue text, không developer patch/gold paths |
| Graph source | Repository tại base commit, không áp gold patch khi indexing |
| Graph profile baseline | V10 hiện có, 2 hops, tối đa 100 candidates, confidence gate 0.6 |
| BM25 | k1=1.2, b=0.75, function/code corpus hiện có |
| Budget | 8000 tokens với cùng verified tokenizer/counter identity |
| Source/snippet policy | Cùng source revision; fair-packing policy được ghi riêng native ranking |
| Task timeout ban đầu | 300 giây, 1 worker; pilot xác minh trước khi freeze final run |
| Risk profile | Chỉ API risk từ 0 → 0.10; các giá trị khác giữ nguyên và lưu đầy đủ |
| Eval labels | Gold-file/gold-function từ extractor, chỉ scorer/manual inspection được thấy |
| Primary | Graph issue-only vs BM25 issue-only; failing-tests-assisted là diagnostic riêng nếu đã có, không gộp |
| Failures | Giữ trong attempted denominator; paired metrics trên intersection hợp lệ và công bố N |

BM25 dùng term frequency, inverse document frequency và length normalization; các tham số hiện có phù hợp baseline nhỏ, không cần thêm neural retriever cho tuần 5–6. [Nguồn thuật toán BM25](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html).

### 12.2. Các bước triển khai/evaluation

- [ ] Tìm raw artifact cũ theo SHA/config trước; nếu thiếu/không tương thích, ghi lý do chạy mới. Không làm lại extraction/BM25 đã HT.
- [ ] Tạo/revalidate dev25 manifest bằng revision explicit, không default “current”. Query/corpus không thấy gold; test mutation gold paths không làm thay đổi candidates trước scoring.
- [ ] Viết risk-profile tests: weight hợp lệ, weights/hash được log; fixture chỉ khác API risk có score khác; weight 0 tái tạo baseline; đổi profile không reuse cache kết quả sai.
- [ ] Expose `--ranking-profile PATH` qua `RetrievalConfig` hiện có. Cache graph và cache ranking phân biệt: source/index không đổi có thể reuse graph, không reuse scores của profile khác.
- [ ] Chạy pilot 3 task theo thứ tự manifest để đo stage time/RAM/timeout. Không bật Jedi; primary vẫn static/internal resolver như graph runner hiện có. SCIP strict qualification ở M3 không tự đổi primary benchmark thành SCIP.
- [ ] Nếu pilot fail, phân loại indexing/anchors/tokenizer/mapping/infra. Tối đa hai lần cùng task/profile; lần hai chỉ khi có giả thuyết/thay đổi xác định. Không tiếp tục loop cố lấy score. Nếu sửa/tăng timeout sau pilot, freeze profile mới và ghi quyết định trước dev25; không trộn timeout policies không công bố.
- [ ] Chạy BM25 và Graph v10 trên dev25; ghi candidate/rank/packed context/gold mapping per task, peak RSS và stage timing. Worker process tách theo task, không giữ toàn bộ graph JSON của nhiều repo trong RAM.
- [ ] Chạy duy nhất profile risk trên cùng manifest/query/source/budget; đối chiếu score và metric paired với v10. Không yêu cầu Graph nhất định thắng BM25 để gọi execution hoàn thành.
- [ ] Sinh bảng từ raw JSON bằng compare script; kiểm IDs, manifests, gold hashes, counter/budget và current builder/ranking source fingerprints trước khi so sánh.
- [ ] Manual inspect 10 task theo lựa chọn định trước: round-robin repos trong dev25, không chỉ chọn task có score tốt. Với task lỗi, ghi failure; chọn task hợp lệ kế tiếp theo cùng rule để đủ 10 context reviews và công bố task bị thay thế.
- [ ] Mỗi case có issue, anchors, top candidates, packed snippets, gold labels, file/function coverage, source ranges và nhận xét good/partial/poor. Ghi lỗi anchor/ranking/packing/mapping riêng; reviewer nhóm xác nhận, không biến auto scorer thành manual review.
- [ ] Viết ADR ranking: kết quả baseline/risk, điều kiện adoption, default giữ/đổi và giới hạn. Nếu phải thay default hoặc duyệt tắt risk, xin xác nhận thay vì tự đánh HT.

### 12.3. Metrics phải trình bày

- File/function Recall@3, @5, @10: phần gold label tìm thấy trong k kết quả; denominator và labels unmappable phải có.
- MRR khi extractor có valid gold function/file; không coi task không có labels là 0 hay loại mà không báo.
- Rank recall và packed-context recall tách nhau: candidate có trong top-k chưa chắc được đưa vào context khi budget đầy.
- `total_token_count`, context token cost và token counter identity; không phải API billing cost vì không gọi LLM.
- Attempted/completed/failed, valid paired N, per-repository summaries; không trình bày 21 pairs như 25 completions.
- Chênh lệch paired và bootstrap 95% CI với seed cố định 0; báo descriptive uncertainty, không thêm nhiều phép thử/ablation ngoài scope.

**Commands có sẵn để dùng sau M0/M4:**

```powershell
& $python scripts/prepare_manifest.py . --count 25 --split dev --min-source-files 2 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
& $python -m pytest tests/m2/test_dataset_split.py tests/m2/test_retrieval_evaluation.py tests/m2/test_retrieval_eval_graph.py tests/m2/test_retrieval_scoring.py tests/test_ranking_profile.py tests/test_manual_retrieval_report.py -q
# run_bm25_retrieval.py và run_graph_retrieval.py nhận root + manifest PATH.
# Lấy PATH/run_id từ receipt/result mới, không dán tên run lịch sử.
# --ranking-profile là option sẽ bổ sung, chưa có sẵn lúc lập kế hoạch.
```

**Gate:** Tất cả 25 task attempted được lưu, ít nhất 20 valid pairs; bảng Recall/tokens tái sinh được và 10 manual cases đã review. Mục tiêu tốt nhất là 25/25; nếu không đạt phải để run PARTIAL và failures, không xóa/invent kết quả. Task benchmark có thể đạt yêu cầu 20–30 task sơ bộ mà không được diễn giải “mọi task trong dev25 đều thành công”.

## 13. M6 — Chuẩn bị và xác minh 50 task SWE-bench runnable

**Đóng:** W05-06-M3-03. Đây là mục CT lớn nhất và có điều kiện tài nguyên thực tế, không phải chỉ tạo manifest 50 rows.

### 13.1. Tình trạng máy và resource gate

Read-only diagnostics lúc lập kế hoạch cho thấy:

- Docker client `28.5.1` có mặt; context `desktop-linux`; server chưa trả version, named pipe Linux engine không tồn tại. **Chưa có Docker engine runnable.**
- Ổ D còn `75,293,917,184` bytes, khoảng **70.1 GiB**. Đây là dung lượng trống, không phải dung lượng tổng.
- Thông tin RAM 16 GB dựa trên thông tin người dùng cung cấp trước; chưa đo lại RAM/CPU qua system API ở phiên lập kế hoạch.
- `.venv-swebench` có distribution `swebench 5.0.2`, editable source ở `.toolchains/SWE-bench`, HEAD `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`, worktree sạch tại lần đọc. Cần pin cả SHA và API, không chỉ version.

Hướng dẫn chính thức khuyến nghị ít nhất 120 GB trống, RAM 16 GB và CPU 8+ cho harness. Đây là khuyến nghị, không phải chứng minh mọi pilot nhỏ sẽ thất bại nếu ít hơn; nhưng chưa có cơ sở để hứa batch50 an toàn trên trạng thái hiện tại. [SWE-bench harness requirements](https://www.swebench.com/SWE-bench/reference/harness/).

**Preflight bắt buộc trước chạy Docker:** Engine Linux hoạt động; xác định nơi Docker lưu images/VHD và volume chứa workspace/logs; đo dung lượng thật ở các nơi đó, RAM/CPU Docker và proxy/network. Không mặc định Docker lưu mọi thứ trên D.

Nếu dung lượng/engine chưa đạt: giữ task blocked, hoàn thiện code/unit tests readiness và chuyển M7/M8. Muốn mở engine, giải phóng/di chuyển storage hoặc dùng máy khác cần quyết định phù hợp của người dùng; không xóa rộng hoặc tự mua tài nguyên. Có thể duyệt một smoke rất nhỏ riêng, nhưng smoke3 không đủ đóng task50.

### 13.2. Files và interfaces dự kiến

- Tạo: `src/vgar/evaluation/readiness/__init__.py`, `manifest.py`, `harness_adapter.py`, `runner.py`.
- Tạo: `scripts/prepare_swebench_readiness.py`, `scripts/check_swebench_readiness.py`.
- Tạo: `tests/m2/test_readiness_manifest.py`, `tests/m2/test_readiness_runner.py`.
- Tạo: `docs/handoff/w3-w6/environment-readiness.md`; outputs `data/readiness/` và `artifacts/w3-w6/readiness/<run-id>/`.
- Không sửa source `.toolchains/SWE-bench` hoặc môi trường cũ. Adapter bám API của SHA đã pin, kiểm signature trước chạy.

**Interfaces nội bộ:**

- `prepare_readiness_manifest(dataset_rows, retrieval_manifest, *, target_count=50, max_candidates=100) -> dict`: khóa IDs và snapshot, giữ dev25 trong pool rồi thêm task dev deterministic; không vượt 100 candidates để chạy vô hạn.
- Sidecar lưu `repo`, `base_commit`, `version`, `test_patch`, developer `patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, oracle/assets hashes và metadata environment cần bởi harness. Các fields oracle không truyền vào retrieval query hoặc MCP context.
- `probe_environment(task: dict, *, run_id: str, timeout_seconds: int, harness_source: Path) -> dict`: chạy baseline và gold độc lập, trả trạng thái oracle + log/hash/timing thực.
- CLI checker: `--manifest PATH --phase smoke3|batch5|full50 --resume RUN_DIRECTORY --timeout-seconds 900 --max-workers 1`; resume option chỉ dùng khi có run phù hợp, không bắt nhập nếu chưa có.

### 13.3. Runnable nghĩa là gì?

Một task được tính `RUNNABLE` khi:

1. Image/dependency environment của đúng task/base commit khởi động được.
2. Baseline chạy **test_patch trên base source, chưa áp developer source patch**; thấy đủ F2P/P2P test IDs bắt buộc để đánh giá, có ít nhất một F2P fail và P2P không regression theo oracle.
3. Gold developer patch được áp trong container độc lập, cùng image/test policy; tất cả oracle F2P và P2P required pass, harness resolved phù hợp.
4. Không timeout, missing tests, all-skipped hoặc test-log parser failure; source/task/test/image identity và logs đầy đủ.

F2P phải có ít nhất một test hợp lệ. P2P có thể rỗng nếu chính snapshot dataset như vậy: ghi `P2P_NOT_APPLICABLE` và số lượng0, không gọi đó là regression coverage. Nếu F2P rỗng, oracle không parse được hoặc gold không hợp lệ: ghi `ORACLE_INVALID`/`TEST_LOG_INVALID`/`GOLD_FAILED`; không tick runnable vì container exit 0. Có thể tách `ENV_STARTED` để chẩn đoán nhưng không tính vào 50.

### 13.4. Cách làm với harness, tránh baseline giả

Official harness hỗ trợ gold patch validation và lưu reports/logs; nên dùng nó cho kiểm chứng môi trường, không tự viết hệ thống chấm repair thay thế. [Gold validation workflow](https://www.swebench.com/SWE-bench/reference/harness/).

Source đang có `run_instance(..., skip_patch=True)` cho negative/base mode, nhưng CLI `main` không expose `--no-patch`. Vì vậy:

- Adapter kiểm API SHA đã pin, tạo TestSpec từ task snapshot, baseline gọi Python API với `skip_patch=True`, gold gọi cùng API với `skip_patch=False` và developer patch thật.
- Không đưa empty patch qua CLI rồi mặc định nó đã chạy baseline: loader có thể loại predictions rỗng. Không invent một no-op patch để né loader.
- Ghi `source_patch_applied=false` cho baseline; kiểm source diff và đọc test statuses từ official log parser. Baseline không phải model patch submission; đừng suy patch-applied từ report field được thiết kế cho grading.
- Mỗi baseline/gold/retry có run ID mới. Harness cache dựa run ID/instance nên dùng lại ID có thể trả report cũ dù patch khác. [Result caching warning](https://www.swebench.com/SWE-bench/reference/harness/).
- API/import/path receipt và pinned harness source phải đi kèm output. Nếu chuyển harness version làm thay API, dừng adapter và xin review, không thử đoán parameters trên batch50.

### 13.5. Các bước triển khai và chạy

- [ ] Viết unit tests manifest: cùng HF revision, dev-only, ≥50 target IDs nếu pool đủ; giữ dev25, dedup, đủ oracle fields; 50 rows source-only không đủ RUNNABLE.
- [ ] Viết unit tests runner bằng fake adapter: engine unavailable, timeout, gold fail, no test IDs, parser error, all-skipped, resume hash mismatch, cached stale report và negative mode không áp source patch. Unit tests không được ghi thành Docker evidence.
- [ ] Viết adapter pin API và runner checkpoint; command argv không chứa secrets, logs từng task, phase/attempt/profile rõ, source/test/image digests có receipt.
- [ ] Tạo candidate manifest từ snapshot HF đã pin, tối đa 100 dev candidates gồm single/multi-file. Report eligibility counts thật; nếu đủ pool không đồng nghĩa đủ runnable.
- [ ] Chạy preflight bằng lệnh read-only; không khởi động batch khi engine/storage fail. Lưu JSON blocker và chuyển task khác.
- [ ] Sau khi resource gate được giải quyết, smoke3: chọn ba task đầu từ ba repository khác nhau theo rule deterministic; hai lượt base/gold mỗi task. Đo pull/build/time/RAM/storage thật.
- [ ] Freeze timeout/budget resource policy sau smoke; mặc định test timeout 900 giây/lượt, một task worker; pull/build có deadline riêng 1800 giây/task, giới hạn không phải một lệnh chạy vô hạn.
- [ ] Batch5 rồi full50 tuần tự; giữ trạng thái per task atomic. Ngừng khi thiếu dung lượng headroom, memory pressure hoặc engine errors; không tiếp tục “đợi thêm” không có tiến độ. Giới hạn cache theo owner inventory; chỉ cleanup container/temp riêng có exact ID, không `docker system prune -a`.
- [ ] Task fail lần đầu: ghi nguyên nhân, chỉ retry nếu có phương pháp khác dựa trên lỗi. Sau lần hai dừng task/profile; không giữ retry vô hạn. Nếu phải thêm candidate để đủ50, giữ danh sách rejected/replacement và selection audit, không che việc benchmark có vấn đề.
- [ ] Sinh manifest runnable chính thức chỉ từ task đạt tiêu chí 13.3. Nếu <50 thì ghi CT/MP cùng số đã xác minh và blocker; không đóng HT.

**Kiểm tra sau triển khai:**

```powershell
& $python -m pytest tests/m2/test_readiness_manifest.py tests/m2/test_readiness_runner.py -q
# Runtime Docker dùng interpreter harness riêng, không bắt nhẹ graph venv cài Torch.
# Lệnh check_swebench_readiness.py chưa tồn tại ở thời điểm lập kế hoạch.
```

**Gate:** Ít nhất 50 distinct task với base/gold/oracle evidence hợp lệ. Không cần GPU/LLM, không cần 50 trajectories sửa lỗi. Nếu máy chưa đủ tài nguyên, phần này phải còn mở trung thực dù các milestone code khác đã hoàn thành.

## 14. M7 — Draft Related Work đúng phạm vi graph/retrieval

**Đóng:** W05-06-M3-04.

**Files:** Tạo hoặc nhận `docs/paper/related_work_graph_retrieval.md` và `docs/paper/references_graph_retrieval.bib`; receipt/reference checklist trong `docs/handoff/w3-w6/related-work-review.md`.

**Các bước:**

- [ ] Hỏi/nhận draft M3 đã viết nếu nằm ngoài clone; không suy người khác chưa làm chỉ vì file không được commit.
- [ ] Nếu chưa có bản bàn giao, viết draft ngắn có ba nhóm: text/code retrieval và BM25; repository graph + symbol resolution; benchmark/evaluation và gold-label limitations.
- [ ] Mỗi paper có bài toán, representation/retrieval, benchmark, giới hạn và điểm dùng/không dùng trong VGAR; tách “tham khảo” khỏi “đã tích hợp thuật toán của paper”.
- [ ] Dùng nguồn primary có link ở mục 17; kiểm full text phần phương pháp khi mô tả chi tiết, không dựa abstract để viết claims kết quả cụ thể.
- [ ] Viết khác biệt hiện tại của VGAR: Python graph + task anchors + bounded context + MCP; verification/repair novelty tuần sau chưa được dùng như kết quả tuần 3–6.
- [ ] Đối chiếu citation/BibTeX/link; không gọi graph retrieval tự nó là mới, không đưa số benchmark paper thành kết quả dự án.

**Gate:** Draft đọc được, references traceable, phù hợp implementation thực tế. Đây không phải yêu cầu hoàn thành literature table 30–50 papers của tuần 1–2.

## 15. M8 — Regression, trạng thái và bàn giao

**Files cập nhật:** `Task Status.md`, `PROGRESS.md`, docs/handoff/ADR liên quan; tạo `docs/handoff/w3-w6/BAO_CAO_HOAN_THIEN_TUAN_3_6.md`.

**Các bước:**

- [ ] Chạy suite scoped graph/contracts/MCP/M2/retrieval đã tác động, ghi evidence từng invocation và kết quả aggregated. Không chỉ chạy test mới bỏ qua regression cũ.
- [ ] Nếu có interpreter full-stack phù hợp, chạy full suite có timeout và record; nếu không đủ dependency, ghi `NOT_RUN`/blocked. Đối chiếu failure HF đã biết, không tick toàn repo xanh khi vẫn còn failure ngoài scope.
- [ ] Nếu tests làm đổi tracked `artifacts/sample_graph.db`, lưu bản generated riêng và xử lý đúng thay đổi do test của phiên hiện tại; không restore source/thay đổi của người dùng. Về lâu dài có thể chuyển test DB sang temp khi fixture này thuộc phần đang chạm, không cleanup toàn repo.
- [ ] Kiểm không có product file ngoài danh sách milestone bị sửa; không có secrets/data oracle trong MCP audit/prompt. Tất cả public contracts còn tương thích hoặc có ADR/approval cụ thể.
- [ ] Đối chiếu đủ 16 IDs, update theo điều kiện mục3. Chưa manual sign-off/resource gate thì ghi MP/CX/CT cùng reason và next action, không tự hoàn thành từ tài liệu.
- [ ] Tạo báo cáo tiếng Việt: bug trước/sau, files đổi, test matrix, actual outputs/hashes, 20 edges, dev25 metrics/failures, manual10, readiness count, quyết định chưa duyệt và giới hạn scope.
- [ ] Cập nhật checkpoint cuối: HEAD/dirty, phần đã xong, run receipt paths, failures đã thử hai lần, task tiếp theo và lệnh resume đúng interpreter/input. Không commit/push nếu chưa được yêu cầu.

**Điều kiện nghiệm thu tổng:**

| Hạng mục | Điều kiện |
| --- | --- |
| Source | Giữ kiến trúc, không overwrite current changes; code fixes có regression |
| Graph | False explicit-import edge loại đúng; SCIP/LSP evidence thật và 20 manual labels |
| MCP | Resources round-trip, context flow thực, workspace boundary enforce ở server |
| Runner | Skipped-only/missing JUnit không PASS; source unchanged cả timeout/failure |
| Retrieval | 20–30 task thực, raw runs, paired table/denominators, 10 manual reviews |
| Ranking/representation | Có quyết định được duyệt, không tự đổi public schema/default |
| Runnable dataset | ≥50 task có actual base/gold oracle receipt, hoặc ghi rõ chưa đạt |
| Documentation | Related Work + status/checkpoint/handoff đồng nhất code/evidence |

Không có điều kiện “Graph phải thắng BM25 mọi metric” hoặc “tất cả 16 mục bắt buộc được tick bất chấp blocker”. Kết quả negative có giá trị khoa học nếu đo đúng; task thiếu runtime/manual approval thì vẫn thiếu.

## 16. Công sức, tài nguyên và cách tránh lãng phí

Ước lượng sau đây dùng để bố trí công việc, **không phải thời gian benchmark đã đo**:

| Milestone | Công sức chủ động dự kiến | Tài nguyên/rủi ro |
| --- | --- | --- |
| M0 | 2–3 giờ | Venv nhẹ, evidence; exact package pins cần kiểm khả dụng |
| M1 | 3–4 giờ | CPU; regression binding/URI |
| M2 | 4–6 giờ | CPU; Windows process/lease guards |
| M3 | 3–5 giờ + peer review | Node/SCIP; cần tải runtime và reviewer20edges |
| M4 | 3–4 giờ + sign-off | Tokenizer-only; không weights/GPU |
| M5 | 4–6 giờ + runtime/dev review | Một worker; source archives và graphs; không giữ nhiều graph trong RAM |
| M6 | 4–6 giờ viết/kiểm wrapper; runtime riêng | Docker/storage lớn; có thể blocked trên máy hiện tại |
| M7 | 2–3 giờ | Đọc nguồn primary và viết draft |
| M8 | 2–3 giờ | Regression/report/acceptance |

Tổng phần chủ động khoảng **27–40 giờ**, chưa tính tải/build/test50, chờ approval hoặc sửa lỗi external environment. Với 50 task và hai lượt base/gold, nếu mỗi lượt chạm timeout 900 giây thì riêng test ceiling đã là 25 giờ; build/pull chưa tính. Đây là phép tính giới hạn, **không dự báo batch chắc chắn mất 25 giờ**. ETA phải lấy từ smoke3 và receipt thực.

Phần mềm/dataset ưu tiên miễn phí; kế hoạch không gọi API model nên API budget 0 USD. Nếu dùng máy/cloud ngoài, cần người dùng duyệt loại máy, thời lượng và cap trước; không có cơ sở báo chi phí cloud cụ thể khi chưa chọn provider.

Tiết kiệm thời gian/token bằng cách: native execution, không audit toàn repo lần nữa; sửa theo evidence; cached source có hash; một worker; stage logs và deadline; dừng sau hai failures/profile; làm M7/M8 khi M6 blocked. Không dùng thêm usage để lặp lại cả full25/full50 chỉ vì một task fail.

## 17. Nguồn tham khảo và evidence nội bộ

### Nguồn nội bộ có ưu tiên

1. [project_plan_16_weeks.md](D:/Project/CAPSTONES/New_task/project_plan_16_weeks.md): scope/DoD tuần 3–6.
2. [Task Status.md](<D:/Project/CAPSTONES/VGAR/Task Status.md>): 16 ID, code/evidence và findings hiện tại.
3. [PROGRESS.md](D:/Project/CAPSTONES/VGAR/PROGRESS.md): source/checkpoint/audit gần nhất.
4. [m1_retrieval_method.md](D:/Project/CAPSTONES/VGAR/docs/m1_retrieval_method.md): ranking/packing hiện có; ưu tiên code nếu phần mô tả lịch sử khác default.
5. [context_payload_contract.md](D:/Project/CAPSTONES/VGAR/docs/context_payload_contract.md), [evidence_bundle_schema.md](D:/Project/CAPSTONES/VGAR/docs/evidence_bundle_schema.md): contract đã có, không tự thêm schema version.

### Primary sources

- [Manning, Raghavan, Schütze — Okapi BM25](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html): tham số/length normalization và vai trò baseline text retrieval.
- [RepoGraph — Repository-level Code Graph, ICLR 2025](https://arxiv.org/abs/2410.14684): related work về repository graph hỗ trợ software engineering; không tuyên bố repo đang tái lập nguyên hệ thống RepoGraph.
- [CodexGraph — Code Graph Databases, NAACL 2025](https://aclanthology.org/2025.naacl-long.7/): related work về truy vấn cấu trúc code; không yêu cầu đưa graph database/agent của paper vào MVP này.
- [SWE-bench official harness](https://www.swebench.com/SWE-bench/reference/harness/): gold validation, resource guidance và result caching; API thực phải khớp harness SHA được pin.
- [SWE-bench official repository](https://github.com/SWE-bench/SWE-bench): nguồn kiểm tra TestSpec/log parser/API khi xây readiness adapter.

Sources được kiểm link ngày 13/10/2026. Paper full-text claims và pin runtime sẽ được kiểm cụ thể trong milestone sở hữu; không sao chép số thành tích của paper vào kết quả VGAR.

## 18. Cách xác nhận và bắt đầu triển khai

Người dùng có thể xác nhận kế hoạch này với đề xuất giữ `Test + Issue + REPRODUCES` qua ADR, thử một profile API-risk 0.10 và triển khai **Native**. Mặc định không thay resource/dataset/contract khi chưa duyệt.

Sau khi được xác nhận, bước đầu là **M0 từ trạng thái code hiện tại**, không clone lại hoặc audit lại toàn bộ. Milestone có test fail sẽ được ghi vào checkpoint trước khi chuyển tiếp. M6 chỉ được nghiệm thu runtime khi Docker/resource gate thực sự đủ; phê duyệt kế hoạch không tự cấp quyền xóa storage/mua cloud.

Kế hoạch chưa triển khai, chưa đóng task và chưa commit/push.
