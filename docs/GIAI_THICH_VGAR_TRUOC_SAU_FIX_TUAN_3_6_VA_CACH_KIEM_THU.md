# Giải thích VGAR trước và sau sửa lỗi tích hợp tuần 3–6, và hướng dẫn tự kiểm thử

**Ngày lập: 07/10/2026, múi giờ Asia/Saigon.**

**Repository được giải thích:** `D:\Project\CAPSTONES\VGAR`. Mọi đường dẫn tương đối trong tài liệu này tính từ root đó, trừ các liên kết Markdown được tính từ thư mục `docs/`.

**Đối tượng:** thành viên M1, M2, M3 và leader muốn hiểu việc đã triển khai, tự đọc evidence, tự kiểm thử và bàn giao đúng trạng thái. Đây là tài liệu giải thích code/evidence, không phải một kế hoạch sửa lỗi mới hoặc xác nhận toàn bộ đồ án hoàn thành.

**Trạng thái tổng quát:** `PARTIAL_HANDOFF`. Các sửa chữa tích hợp đã có kiểm thử kỹ thuật; benchmark còn lỗi và chưa đủ gate. Không có công việc chạy ngầm được khởi động bởi việc viết tài liệu này. Không commit/push, không sửa hệ thống cũ, không thực hiện environment readiness đã bị loại trừ.

## Mục lục

1. [Task thực sự là gì, phải làm gì và không làm gì?](#1-task-thực-sự-là-gì-phải-làm-gì-và-không-làm-gì)
2. [Các kết quả khác nhau mà nhóm cần phân biệt](#2-các-kết-quả-khác-nhau-mà-nhóm-cần-phân-biệt)
3. [Nền tảng có sẵn trước đợt fix: M1, M2, M3](#3-nền-tảng-có-sẵn-trước-đợt-fix-m1-m2-m3)
4. [Bảng bug/gap trước khi sửa](#4-bảng-buggap-trước-khi-sửa)
5. [Bảng thay đổi sau khi sửa](#5-bảng-thay-đổi-sau-khi-sửa)
6. [Trạng thái task: chưa hoàn thành trước, hoàn thành sau](#6-trạng-thái-task-chưa-hoàn-thành-trước-hoàn-thành-sau)
7. [Cấu trúc repo và vai trò từng nhóm file](#7-cấu-trúc-repo-và-vai-trò-từng-nhóm-file)
8. [Các flow: input, xử lý, test, output](#8-các-flow-input-xử-lý-test-output)
9. [Đã kiểm thử những gì, kết quả nằm ở đâu?](#9-đã-kiểm-thử-những-gì-kết-quả-nằm-ở-đâu)
10. [Đọc kết quả benchmark và tài nguyên](#10-đọc-kết-quả-benchmark-và-tài-nguyên)
11. [Tự chạy trên Windows PowerShell từ đầu đến cuối](#11-tự-chạy-trên-windows-powershell-từ-đầu-đến-cuối)
12. [Thuật ngữ và câu hỏi thường gặp](#12-thuật-ngữ-và-câu-hỏi-thường-gặp)
13. [Checklist bàn giao và nguồn đối chiếu](#13-checklist-bàn-giao-và-nguồn-đối-chiếu)

## 1. Task thực sự là gì, phải làm gì và không làm gì?

### 1.1. Nguồn yêu cầu

Yêu cầu đến từ `D:\Project\CAPSTONES\New_task\project_plan_16_weeks.md`, tài liệu bổ sung `VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md`, kế hoạch đã duyệt trong [plan fix](superpowers/plans/2026-10-06-fix-vgar-integration-week-1-6.md) và các quyết định sau đó của người dùng.

Kế hoạch fix giữ tên `week-1-6` vì đó là tên đã chia sẻ, **nhưng phạm vi triển khai thực tế là tuần 3–6**. Tuần 1–2 là research, không cần tích hợp vào repo và không được ghi thành task code còn thiếu. Tuần 7–16, fine-tuning, deep data flow, kiến trúc verifier nâng cao không được kéo vào đợt này.

### 1.2. Nội dung tuần 3–4

| Owner | Nội dung yêu cầu | Hiểu bằng ngôn ngữ đơn giản |
|---|---|---|
| M1 | Parse Python bằng Tree-sitter; file/module/class/function/method/import/callsite; nodes/edges; resolver tối thiểu; confidence/provenance; SQLite; unit tests | Đọc code và xây bản đồ “file nào chứa hàm nào, ai import/gọi ai”, giữ bằng chứng nguồn |
| M2 | Workspace/sandbox, pytest wrapper, baseline command/stdout/stderr/exit/duration, evidence schema/writer JSON | Chạy test trên bản sao, ghi lỗi ban đầu và toàn bộ kết quả để đối chiếu |
| M3 | MCP server, ba graph resources, ba graph tools, LangChain client, audit log | Cho client gọi graph qua giao thức chuẩn thay vì gắn chặt trực tiếp vào implementation |
| DoD nhóm | Query hợp lý; kiểm thủ công ít nhất 20 call/import edges; node/edge/build-time log | Không chỉ có code; phải có ví dụ và bằng chứng chất lượng |

Workspace hiện tại là disposable copy và capability guard, **không phải container/OS sandbox**. Nó bảo vệ các thao tác tool được kiểm soát, không bảo đảm code pytest của repo không tin cậy không thể đọc/ghi tài nguyên host.

### 1.3. Nội dung tuần 5–6

| Owner | Nội dung yêu cầu | Sản phẩm cần có |
|---|---|---|
| M1 | Task anchors từ issue/path/symbol/stack trace/test/route; task trace; k-hop retrieval; ranking; pack theo token budget | Grounding API và `ContextPayload` có snippets gắn với source |
| M2 | BM25 trên function/code chunks; gold-file/gold-function từ developer patch; retrieval evaluation 20–30 tasks; phối hợp mapping/context với M1 | Baseline và evaluator/scorer có thể so sánh công bằng |
| M3 | Expose anchors/context qua MCP; LangChain issue → anchors → context → display; manifest/subset; draft Related Work | Client thực sự gọi được API mới; dataset manifest tái lập |
| DoD nhóm | Graph vs BM25 Recall@3/5/10 + token cost; manual-inspect ít nhất 10 task | Bảng thực nghiệm và audit, không phải lời khẳng định Graph luôn tốt hơn |

Phần “50–100 tasks có environment chạy được” trong plan gốc đã được người dùng **loại trừ khỏi đợt triển khai hiện tại**, bao gồm smoke3 môi trường. Không cài/chạy Docker hoặc dependencies của các SWE-bench repositories để làm task đó. Related Work do nhóm quản lý; không suy từ việc thiếu draft trong checkout rằng research chưa hoàn thành, và không triển khai thêm research ở đợt fix.

### 1.4. Vì sao cần một đợt fix tích hợp?

Trước đây từng module có code và tests riêng, nhưng các module chưa thống nhất assumptions. Ví dụ: M1 bỏ file parse lỗi khỏi graph trong khi retriever coi file vẫn tồn tại trên đĩa là source mới; M2 runner xuất `arms` nhưng comparator tìm `arm`; M3 chưa expose retrieval API của M1. Do đó “test module PASS” không đồng nghĩa “ghép M1/M2/M3 chạy đúng”.

Đợt fix nhằm sửa **ranh giới** này, giữ implementation đang hoạt động, thêm regressions nhỏ và ghi evidence. Không viết lại repo, không dùng fine-tune để chữa lỗi giao diện/schema/file system.

### 1.5. Những quyết định được duyệt

- Triển khai trực tiếp trong VGAR, giữ dirty changes; không tạo worktree/commit/push.
- Giữ frozen `ContextPayload`, vocabulary `PASS/FAIL/ERROR/NOT_RUN`, không thêm public `schema_version`.
- Dùng `Issue` + node `Test` hiện có và `MENTIONS/REPRODUCES`, không tự thêm node type `FailingTest` ngoài frozen schema; có ADR giải thích.
- Thêm **`task_handle`** vào input `get_related_context` để client vẫn stateless và không nhầm issue.
- Duyệt **`--no-jedi` làm profile benchmark chính** sau khi pilot Jedi timeout; không đổi app mặc định và không gọi Jedi đã được sửa.
- Task fail một lần có thể dừng/chuyển task khác; giữ lỗi trong báo cáo, không retry ngầm hoặc xóa denominator.

## 2. Các kết quả khác nhau mà nhóm cần phân biệt

| Hoạt động | Input | Output | Có sửa code target không? | Có LLM không? | Chứng minh được gì? |
|---|---|---|---|---|---|
| Chạy pytest suite của VGAR | `tests/` của VGAR | cases/exit/stdout/JUnit/evidence | Không chủ đích sửa source VGAR; tests tạo dữ liệu tạm | Không inference thật trong bộ nghiệm thu này | Các assertions/regressions của implementation |
| Chạy baseline M2 | Một repo tin cậy + selectors | Kết quả test trước patch trong bản sao | Không apply patch | Không | Hiện trạng lỗi/pass trước sửa |
| Scripted W3–4 smoke | Fixture + hành vi/patch định sẵn | Baseline FAIL → patch → tests PASS + audit | Chỉ bản sao fixture | Không, hoặc scripted model ở script agent riêng | Tool/executor/verification wiring có hoạt động |
| W6 MCP context smoke | Fixture + issue + tokenizer | Anchors/context/display/audit | Không | Không | Grounding/retrieval qua transport stateless |
| SWE-bench retrieval | Manifest + base source + issue; patch chỉ scorer | Ranking/coverage/metrics/tokens/trace | Không sửa lỗi target | Không | Khả năng tìm code theo gold changed-code proxy |
| Agent repair thật | Repo + task + model + test policy | Patch và verification | Bản sao workspace nếu guards đúng | Có | Chỉ task/đường chạy đã thực sự được xác minh |

**359 passed / 4 skipped** là kết quả suite code. **19/25** là số task retrieval chạy thành công, không phải 19 task được repair. Hiện chưa đo repair pass rate SWE-bench trong đợt fix này. Tokenizer đếm token không phải LLM inference.

## 3. Nền tảng có sẵn trước đợt fix: M1, M2, M3

Không phải tất cả file hiện tại đều do đợt fix tạo mới.

- **M1 có sẵn:** builder, resolver Jedi, graph schema, grounding, task overlay, bounded retriever, tokenizer counter, SQLite store/query/service. Đợt fix sửa robustness/bindings/source inventory và nối retrieval vào service/transport.
- **M2 có sẵn:** disposable workspace, pytest wrapper, baseline/writer/schema; AST code chunks, BM25, developer-patch gold extraction, shared scorer/metrics và scripts evaluation. Đợt fix sửa cross-arm contract/fairness/cache/lifecycle/provenance và bổ sung integration tests.
- **M3 có sẵn:** MCP client/servers/registry/audit, LangChain/LangGraph agent, CLI/config/model backend. Đợt fix mở rộng tuần 6, thống nhất envelope và lease, sửa consumer host binding. Không huấn luyện model, không chuyển repo này sang runtime của hệ thống cũ.

```text
                                  M3: client / CLI / orchestration
                                                |
                     +--------------------------+----------------------+
                     |                          |                      |
               Graph MCP                 Repository MCP          Execution MCP
                     |                          |                      |
          M1: SQLite/grounding/          M2: leased workspace     M2: pytest wrapper
              bounded retrieval               + edits               + evidence

Evaluation ngoại tuyến M2 ---> gọi API M1 trực tiếp ---> shared scorer ---> report
                            (KHÔNG đi qua MCP, KHÔNG gọi LLM)
```

Owner là phân công nhóm, không phải kết luận ai gây ra bug. Những sửa chữa xuyên module cần owners cùng review.

## 4. Bảng bug/gap trước khi sửa

### 4.1. Danh sách F01–F12 từ audit ban đầu

Nguồn gốc chính xác: [audit ngày 06/10](reviews/2026-10-06-review-vgar-week-1-6.md). “Trước” là baseline `main@b39e0dbf87645d39b9a68e87b19d0655df264a05`, không phải tất cả phiên bản lịch sử. Probe nằm trong `artifacts/reviews/2026-10-06-w1-w6/probes.json` và `extra-probes.json`. `issue_reproduced=true` chứng minh **đã thấy lỗi**, không phải sửa thành công.

| ID / ưu tiên | Lỗi/gap trước triển khai | Hậu quả / nguyên nhân | File ranh giới | Sau fix / giới hạn |
|---|---|---|---|---|
| F01 / P0 | Producer xuất `arms`, comparator đọc `arm`; fixture test tự chèn `arm` | Summary thật bị từ chối; unit test bỏ lỡ lỗi tích hợp | `scripts/run_graph_retrieval.py`, `evaluation/retrieval/compare.py`, `tests/m2/test_graph_arm.py` | Đọc đúng output thật; regression chạy runner → compare → report |
| F02 / P0 | MCP chỉ có ba graph tools; grounding/context chỉ API nội bộ | LangChain chưa gọi được issue → anchors → context | `graph/port.py`, services, `mcp/servers/graph_server.py`, registry | Expose hai tools; persistent task_handle; stateless smoke |
| F03 / P0 | File extraction rollback khác inventory retriever; symbol index còn stale IDs | File lỗi nằm trên đĩa bị hiểu là source mới; rebuild vẫn fail | `graph/builder.py`, `graph/retrieval.py` | Transaction rollback đầy đủ + failed-file inventory/hash; không bỏ snapshot guard |
| F04 / P1 | Quét code trong source cache của SWE-bench khi target là VGAR | Trộn repo ngoại vào graph, tăng CPU/RAM/nhiễu | Builder discovery/source scope | Scope riêng VGAR prune operational paths; repo thường giữ package thật |
| F05 / P1 | Copy/hash cache lớn; fingerprint trước pending và ngoài timeout pytest | Có thể treo trước test mà chưa có JSON; vượt workspace limits | `repair/workspace.py`, `scripts/record_m2_test.py` | Shared scope; pending trước preflight; deadline riêng trước/sau pytest |
| F06 / P1 | M1 bỏ definitions trong compound blocks; duplicate qualified names collision | M1/M2 coverage/identity khác; rollback cả file | `graph/builder.py`, `evaluation/retrieval/chunks.py`, scorer | Compound traversal + occurrence IDs; regression cross-arm. Không bảo đảm static Python hoàn hảo |
| F07 / P1 | Tree marker đúng nhưng không rehash bytes; graph cache identity thiếu deps | Dùng tree/graph stale, so sánh sai source | `graph_arm.py`, graph cache/runner | Verify file set/hash/cache pair/schema/implementation; explicit rebuild giữ cache cũ |
| F08 / P1 | Capped rank nhưng packed metrics uncapped được trình bày dễ gây hiểu nhầm | Người đọc tưởng cả context cũng capped | `compare.py`, `report.py` | Primary full rank; cap chỉ rank-only sensitivity, không giả repack |
| F09 / P2 | Mọi dotted decorator bị coi là property setter | `@app.get`/`@pytest.mark` có ID suffix sai | `graph/builder.py` | Nhận diện setter đúng thay vì chỉ tìm dấu chấm |
| F10 / P0 | `from pkg import A; class A(A)` resolve base về chính class mới | Self-loop `INHERITS` khiến validator từ chối Python hợp lệ | Inheritance/binding resolution của builder | Resolve theo binding trước định nghĩa class; validator giữ nguyên |
| F11 / P0–P1 | Tool nhận write root tùy ý; repo/execution thiếu common envelope và dùng runner riêng | Có thể sửa nhầm source; evidence/status khác contract | MCP repository/execution, workspace guard, runner | Lease host cấp, path/root guards, common envelope/audit, M2 pytest wrapper |
| F12 / P2 | Fingerprint chỉ `tests/*.py`, bỏ nested tests/fixtures | Provenance không phát hiện thay đổi code kiểm thử | `evaluation/retrieval/evidence.py` | Recursive fingerprint gồm nested tests/fixtures/config/lock |

Trong bảng, các path `graph/`, `repair/`, `evaluation/`, `mcp/` đều dưới `src/vgar/`. P0/P1/P2 là thứ tự ưu tiên kỹ thuật, không phải thang đánh giá bảo mật CVSS.

### 4.2. Các rủi ro/gap R01–R06 cũng được ghi trước triển khai

| ID | Trước fix | Xử lý / trạng thái hiện tại |
|---|---|---|
| R01 | Run lịch sử có 7 MemoryError, thiếu traceback/stage/RSS; nhiều bản graph deepcopy; không worker deadline/resume | Đã thêm diagnostics/lifecycle/isolation. Jedi timeout chưa được sửa; no-Jedi chính đã duyệt. Ba Sympy vẫn timeout preparation; chưa có profiling đủ để kết luận mọi lỗi do RAM |
| R02 | Model loader/context budget chưa được xác minh inference thật/pinned runtime revision | Ngoài phạm vi tuần 3–6 fix; **không sửa/không nghiệm thu** model hoặc fine-tune. Không lấy tokenizer pin làm pin model weights |
| R03 | Fairness guards thiếu dataset/gold/population checks; zero pairs có thể exit 0; survivor bias | Bổ sung guards và partial/zero nonzero; báo denominator/errors; vẫn cần diễn giải bias của 19 success pairs |
| R04 | Graph+F2P dùng FAIL_TO_PASS metadata nhưng có thể bị hiểu như issue-only | Tách rõ oracle-assisted arm; không đưa gold developer patch vào ranker; không dùng F2P làm primary |
| R05 | `depth=2` bị echo nhưng chỉ direct callers/callees | Reject depth ngoài 1; k-hop native retrieval là chức năng khác |
| R06 | Handoff/spec/contract cũ không khớp code, checklist gây hiểu nhầm | Gắn historical addendum; README/contracts/ADR/PROGRESS/completion/report phản ánh trạng thái thật. YAML không được runtime đọc |

### 4.3. Lỗi/gap phát hiện sau đó, không được gộp giả vào audit ban đầu

| Vấn đề bổ sung | Biết chắc từ evidence | Cách xử lý hiện tại |
|---|---|---|
| Tree/BM25 artifacts bị LF → CRLF sau Git checkout | Raw-byte hashes không khớp; đối chiếu archive/Git blobs chứng minh newline transformation ở artifacts liên quan | Tree rebuild sang UUID mới; BM25 recovery copy nguyên Git blobs 25/25 đúng hash. Không sửa marker/recorded hash |
| Atomic telemetry replace bị Windows reader khóa | Regression/trace `PermissionError` khi writer replace JSON | Retry bounded riêng PermissionError khi ghi JSON: tối đa 20 lần, 10ms; lock kéo dài vẫn ERROR. **Không** đồng nghĩa rename thư mục Django đã được sửa |
| Worker public retrieval thừa hưởng credential names | Test synthetic credential trước fix fail | Filter tên biến môi trường; không in secret thật. Không phải bảo đảm chống mọi secret/code độc hại |
| Host graph source/version binding | CLI/workflow kế thừa source_root=None hoặc foreign source/version | RED4 → fix bind leased source/reset version → GREEN24 → suite359; không đổi ranking/model |
| Sáu errors trên no-Jedi dev25 | 3 Sympy timeout, 2 Django WinError5, 1 Pylint duplicate edge | **Chưa sửa**. Dừng sau một attempt mỗi case, giữ trong population/report |

Không coi mọi lỗi KeyError/Path/MemoryError ở run lịch sử là còn tồn tại trên code hiện tại: source digests khác nhau và evidence cũ không đủ trace. Bảng ghi cái đã tái hiện hoặc đã quan sát, không suy đoán nguyên nhân chưa có bằng chứng.

## 5. Bảng thay đổi sau khi sửa

### 5.1. Milestone, file, output và tác dụng

| Milestone | Thay đổi thực hiện | File chính | Output/tác dụng | Bằng chứng mức nào? |
|---|---|---|---|---|
| 1 — Comparison contract | Consumer dùng `arms`; population/query/base/corpus/patch/gold/counter/scorer guards; zero/partial nonzero; full rank primary | `src/vgar/evaluation/retrieval/compare.py`, `report.py`, `scripts/compare_graph_vs_bm25.py`, tests comparator | `result.json`/`REPORT.md` không còn dựa vào shape giả; phản ánh failures | Regression + actual fixture pipeline + real partial19 comparison |
| 2 — Graph robustness | File transactions/journal rollback; inventory cả failed files; compound/duplicates/bindings/setter/inheritance | `src/vgar/graph/builder.py`, `retrieval.py`, `tests/test_graph_transaction_bindings.py` | Snapshot/source proof nhất quán, occurrence-aware node IDs | Fixtures; **Pylint duplicate edge thật vẫn còn** |
| 3 — Source scope / recorder | Prune trước descent; VGAR-specific operational exclusions; generic repo không mất package `data`; pending trước preflight; preflight deadlines | `src/vgar/source_scope.py`, `repair/source_preflight.py`, `workspace.py`, recorder, `tests/test_source_scope.py` | Chạy trên VGAR không trộn cache; hash timeout có evidence | Tests scope/preflight + full recorder |
| 4 — MCP/M2 boundary | Host lease, root/link/path guards; atomic exact edit giữ newline; shared response/audit; execution gọi M2 runner | `mcp/workspace_guard.py`, tooling, repo/execution servers, settings, CLI/prepare và smokes | ToolResponse + audit + pytest/JUnit evidence nhất quán | Boundary tests + stdio/scripted fixtures; không OS sandbox |
| 5 — Cache/lifecycle | Tree/cache verification; versioned immutable recovery; per-task process/deadline/logs/RSS; resume fork guards; recursive source fingerprint | `evaluation/retrieval/graph_cache.py`, `lifecycle.py`, `worker.py`, `graph_arm.py`, `evidence.py`, runner | Run/task/attempt artifacts, stage trace, terminal ERROR, new run khi resume | Lifecycle/cache regressions và real dev25 traces |
| 6 — W6 MCP retrieval | Store source spans/metadata và persistent task context; expose anchors/context; stateless task_handle; depth guard/resource-ID decoding | `graph/sqlite_store.py`, `sqlite_service.py`, `port.py`, `factory.py`, `demo_service.py`, graph server/registry/settings, `scripts/smoke_w5_w6.py` | `ContextPayload`, diagnostics sidecar, `context.json`, `CONTEXT.md`, audit | Direct tests + fresh-session transport fixture + pinned tokenizer |
| 7 — Docs/handoff | Contract/ADR/README/run guidance/completion/current status | `docs/`, `README.md`, `PROGRESS.md`, `.env.example` | Nhóm thấy đúng semantics/limits, không coi history là hiện tại | Local-link/PowerShell syntax checks; owner approval riêng |
| 8 — Acceptance evidence | Full suite; actual fixture compare/report; no-Jedi pilot/dev25; partial CI; manual10; affected self-review | Tests, `results/retrieval/`, `artifacts/fixes/w3-w6/`, review docs | Có evidence cả thành công và lỗi; benchmark chưa đạt gate | Pilot3/3, dev25 19/25, suite359/4skip; **không complete toàn W6** |
| Fix cuối — host binding | `graph.source_root=lease.path`, `graph.version=None`, workspace_root đúng cho DB mới | `src/vgar/cli.py::sandbox`, `src/vgar/agents/nodes/prepare.py::prepare_workspace`, `tests/test_host_retrieval_binding.py` | Consumer không đọc source/version của repo khác | RED4 → GREEN24 → full359; sửa sau measurements |

### 5.2. Những gì giữ nguyên

Giữ Python graph/SQLite, internal M1 APIs, M2 BM25/shared scorer, MCP stdio/client và LangChain/LangGraph. Giữ default Jedi của app; no-Jedi là **profile benchmark**. Không đổi dataset dev25, tokenizer pin, snippet budget8000, gold/query policy để làm đẹp metrics. Không thêm public schema version. Không tải LLM weights/train/call API trong nghiệm thu retrieval này. Không xóa evidence cũ.

Hai bảng SQLite nội bộ mới `node_source_metadata` và `task_contexts` phục vụ retrieval/source binding; không phải thay frozen public graph schema. Snapshot cũ không có source metadata cần ingest snapshot mới, không đoán source spans thiếu.

## 6. Trạng thái task: chưa hoàn thành trước, hoàn thành sau

### 6.1. Chưa hoàn thành / chưa đủ bằng chứng / loại trừ

| Nội dung | Trạng thái | Vì sao / lỗi gì? | Nằm ở đâu để xem? | Cần gì để đóng? |
|---|---|---|---|---|
| Paired retrieval20–30, mục tiêu25 | **Chưa đạt** | 19 valid pairs trên25 attempts; dưới20. Không bổ sung/drop task để đủ số | `results/retrieval/20261007T014445273889Z-664d06a6c1c0/`, comparison `20261007T022806825449Z-7e61dc92fe7b/` | Điều tra failures khi được mở lại; quyết định protocol/run mới và owners review |
| sympy__sympy-16597 | **Dừng, chưa sửa** | Timeout300,031s `PREPARE_RETRIEVAL`, peak RSS4.785.938.432bytes | Graph run `tasks/sympy__sympy-16597.json` | Profile preparation/constructor/cache/build cost; không mặc định tăng RAM/deadline |
| sympy__sympy-17318 | **Dừng, chưa sửa** | Timeout300,010s `PREPARE_RETRIEVAL`, RSS4.904.476.672bytes | `tasks/sympy__sympy-17318.json` cùng run | Như trên; không có MemoryError được ghi |
| sympy__sympy-20438 | **Dừng, chưa sửa** | Timeout300,043s `PREPARE_RETRIEVAL`; build đã tốn223,357s; deadline cho cả task | `tasks/sympy__sympy-20438.json` | Đo thời gian build/preparation, giữ guards |
| django__django-11885 | **Dừng, chưa sửa** | `PermissionError/WinError5`, `EXTRACT_TREE`, rename partial directory,3,541s | `tasks/django__django-11885.json` | Reproducer xác định handle/ACL/timing; chưa biết antivirus/process cụ thể |
| django__django-13512 | **Dừng, chưa sửa** | Cùng nhóm WinError5,3,397s | `tasks/django__django-13512.json` | Không tự đổi ACL/tắt bảo vệ/xóa partial tree |
| pylint-dev__pylint-6386 | **Dừng, lỗi code chưa sửa** | `GraphValidationError` duplicate edge ID trong `BUILD_GRAPH`,32,684s | `tasks/pylint-dev__pylint-6386.json` | M1 định vị occurrence, thêm regression, sửa nguyên nhân; không bỏ validator/dedup giấu collision |
| Jedi profile | **Chưa sửa** | Pilot0/3 timeout BUILD_GRAPH300s; no-Jedi approval không fix Jedi | Run `20261006T160820338280Z-24c3cf0056d1`, báo cáo pending | Chỉ điều tra tiếp khi được duyệt, không trộn metrics hai profiles |
| Sign-off owners M1/M2/M3 | **Chờ người phụ trách** | Automated tests/self-audit không thay review nhóm; task_handle/no-Jedi đã được user duyệt nhưng không phải ba owner cùng ký | ADR identities/task handles + affected-files review | Owners review contract/identity/scoring/source binding và xác nhận |
| Environment readiness50–100/smoke3 | **EXCLUDED_BY_USER / NOT_RUN** | Người dùng yêu cầu không làm đợt này; archive/source không chứng minh tests environments chạy | Báo cáo pending / completion | Chỉ mở lại theo yêu cầu; không tính là đã PASS |
| Inference thật / SWE-bench repair rate / full verifier nâng cao | **Ngoài phạm vi** | Không chạy model/sinh patch benchmark ở đợt này, không có số đo | README/model/workflow; report ghi inferenceNOT_RUN | Một task triển khai/đánh giá riêng được duyệt; không suy từ retrieval |
| Minor performance findings | **Deferred, chưa sửa** | Global dictionary journal/deepcopy/full-graph reads/reground có thể tốn CPU/RAM, chưa biết tỷ lệ thời gian | Affected-files self-review | Profiling cụ thể; không tối ưu phỏng đoán/đổi architecture |

Tất cả six task artifacts nằm dưới đường dẫn đầy đủ `D:\Project\CAPSTONES\VGAR\results\retrieval\20261007T014445273889Z-664d06a6c1c0\tasks\`. Một bundle tổng hợp toàn bộ failures là `artifacts/fixes/w3-w6/benchmark-handoff/20261007T022932115081Z-785d8f78eb4e/result.json`.

### 6.2. Nội dung đã hoàn thành, ở mức cụ thể nào?

| Nội dung | Mức hoàn thành / output | Implementation / tài liệu | Giới hạn |
|---|---|---|---|
| pytest wrapper M2 | Command/argv, stdout/stderr, exit/duration, cases/JUnit/status | `src/vgar/repair/test_runner.py`; default records `artifacts/m2/test-runs/` | Tests trusted repo; timeout/output limit; không là proof semantic correctness |
| Baseline trước patch | Disposable copy + hash trước/sau + EvidenceBundle, `patch_applied=false` | `repair/baseline.py`, `scripts/run_m2_baseline.py` | Chạy test, **không tự sửa lỗi** |
| Evidence writer/recorder | Atomic pending→final, phase/preflight traces, mỗi invocation JSON riêng | `repair/evidence_writer.py`, `source_preflight.py`, recorder | Hard kill/mất điện có thể để pending; không bảo đảm finalize tức thì |
| Graph/source robustness | Transactions/identity/binding/snapshot guards/scope regression | Builder/retrieval/source_scope + tests | Không đảm bảo mọi Python dynamic case; duplicateedge Pylint còn mở |
| BM25/chunks/gold/scorer | Baseline25 từ run lịch sử, cross-arm mapping/guards tests | `evaluation/retrieval/` | Gold changed-code proxy không phải ground truth đầy đủ về relevance |
| Cache/provenance/lifecycle | Verified tree/pairs; bounded workers; hashes/logs/telemetry/resume fork | graph_cache/lifecycle/worker/evidence | RSS sampling có giới hạn; stop fail1 hiện không được tự resume |
| MCP W6 tools/context | Hai tools mới + persistent task_handle + frozen context + display | Graph service/server, `scripts/smoke_w5_w6.py` | Demo backend không có source thật trả GRAPH_NOT_READY |
| MCP lease/envelope/audit | Shared response/audit/host workspace restrictions; M2 executor | MCP modules + workspace tests | Capability guard, không OS sandbox |
| Host source/version binding | CLI/workflow bind đúng source của leased copy | CLI/prepare + test_host_retrieval_binding | Source đổi sau patch vẫn stale; **không automatic incremental reindex** |
| Pilot no-Jedi | 3/3 thành công, official counter | `results/retrieval/20261007T013925676777Z-55ae5fb6a24a/` | Không phải paired25/repair |
| Báo cáo Graph–BM25/CI | Partial19 pairs, errors/population25, oracle riêng | Comparison result/REPORT + review dev25 | Report hoàn tất, **benchmark gate chưa đạt** |
| Manual10 | Issue/base/gold/anchors/top5/packing/source interpretation cho10distinct tasks | `docs/reviews/2026-10-07-manual-retrieval-audit-10.md` | Self-audit, chọn10success đầu manifest không theo accuracy; không independent owner approval |
| Full suite cuối | **359 passed,4 skipped**, source trước=sau | Full recorder cuối, mục9 | Bốn symlink skip không phải PASS; không thay real repair |
| Handoff/self-review | Current status/ADR/run instructions/failure report | PROGRESS, README, docs/reviews, completion | Không tự commit/push/merge hoặc ký thay owners |

## 7. Cấu trúc repo và vai trò từng nhóm file

### 7.1. Bản đồ thư mục

```text
VGAR/
  pyproject.toml, uv.lock, .env.example, .gitignore
  README.md, PROGRESS.md
  configs/                         YAML lịch sử; runtime không đọc
  src/vgar/
    source_scope.py                scope dùng chung
    contracts/                     graph/context/evidence/error DTO và validators
    graph/                         M1: parse, resolve, store, ground, retrieve
    repair/                        M2: copy, pytest, baseline, evidence
    evaluation/retrieval/          M2 + M1 integration: corpus/rank/gold/score/run/compare
    mcp/servers/                   graph/repository/execution server
    agents/                        LangChain core + LangGraph workflow
    models/                        model backend, không train trong đợt này
    config/                        Settings từ env/.env
  scripts/                         entry points chạy từng flow
  tests/                           unit/integration/regression; fixtures nằm riêng
  data/                            manifest/gold/download/source trees/graph caches
  results/retrieval/               benchmark/paired report, không source application
  artifacts/                       graph/tokenizer/test/review/fix evidence
  logs/                            MCP audit mặc định
  docs/                            contract, ADR, review, hướng dẫn, completion
```

Đợt fix thêm modules hỗ trợ vào cấu trúc hiện có, **không đổi repo thành một kiến trúc khác**. `src/vgar` mới là package chạy. Dữ liệu trong `data/` và `results/` không phải code của ứng dụng mà agent phải sửa khi target là VGAR.

### 7.2. Root/config/contracts

| File | Vai trò, cách hoạt động |
|---|---|
| `pyproject.toml` | Package `vgar-mcp`, Python>=3.11,<3.14; dependencies; entry point `vgar`; pytest bỏ `tests/fixtures` và dùng `src` |
| `uv.lock` | Lock dependencies; không tự bảo đảm mọi máy có wheel/driver/GPU phù hợp |
| `.env.example` | Mẫu env; không chứa secrets thật; chỉ copy khi `.env` chưa có |
| `.gitignore` | Tránh đưa runtime/cache/temp/secret artifacts không phù hợp lên Git; việc file bị ignore không có nghĩa không tồn tại local |
| `src/vgar/config/settings.py` | Resolve env thật > `.env` > defaults; graph backend/database/source/version/tokenizer/workspace; model/agent config |
| `config/__init__.py`, `logging.py` | Export config API và cấu hình logging; không phải planner |
| `src/vgar/source_scope.py` | Xác định inventory/prune; nhận diện VGAR bằng pyproject.name + src/vgar; không blanket-ignore package data của repo khác |
| `contracts/schema.py` | Validate graph document/nodes/edges; giữ duplicate/self-loop checks thay vì bỏ để task xanh |
| `contracts/graph.py` | DTO graph/query dùng chung giữa service và MCP |
| `contracts/context.py` | Frozen SourceRange/ContextItem/ContextPayload; kiểm path relative, sum token_count và budget |
| `contracts/error.py` | Stable graph error classes/codes, ví dụ GRAPH_NOT_READY/NODE_NOT_FOUND/INVALID_LIMIT |
| `contracts/evidence.py`, `repair.py` | TestRunResult/TestCaseResult/VerificationResult/EvidenceBundle và failure reasons |
| `configs/{agent,evaluation,mcp,model}.yaml` | Tài liệu/config lịch sử; Settings runtime không đọc. Sửa YAML không đổi runtime hiện tại |

### 7.3. M1: `src/vgar/graph/`

| File | Input → xử lý → output |
|---|---|
| `builder.py` | Repo Python → scoped inventory/Tree-sitter extraction/bindings/edges/validator → graph document + statistics/inventory/errors |
| `jedi_resolver.py` | Unresolved call/symbol → Jedi static lookup → nội bộ resolvable targets; no-Jedi benchmark không dùng fallback này |
| `grounding.py` | Issue/path/symbol/stacktrace/test/route → scored TaskAnchors + ambiguous/unmatched diagnostics |
| `task_overlay.py` | Snapshot + issue/failing reports → task-specific Issue/trace overlay, không mutate base snapshot |
| `retrieval.py` | Snapshot/source + anchors/overlay → confidence/distance/task/API heuristics, bounded traversal → candidates/native context/omissions |
| `token_counter.py` | Local manifest/assets đã pin → tokenizer counter/provenance; không load model weights |
| `sqlite_store.py` | Ingest/query graph snapshots; giữ source byte metadata và immutable task_contexts; không chuyển contract vào MCP |
| `sqlite_service.py` | GraphService adapter trên SQLite; kiểm source/handle/snapshot, reground, retrieve; trả DTO/context diagnostics |
| `port.py` | Protocol/service boundary mà MCP dùng: search/callers/callees/anchors/context/resources |
| `factory.py` | Chọn demo/sqlite từ Settings; dựng service và counter đúng policy |
| `demo_service.py` | Fixture backend cho discovery/query cũ; không giả source-backed W6 retrieval nếu thiếu snapshot |

Ranking hiện dùng heuristics, không GNN hay planner đã fine-tune. Features có thể unavailable (`architecture_dependencies`, `recent_change_frequency`, failing-test proximity khi không có tests); code báo rõ và renormalize active weights, không gán chứng cứ tưởng tượng.

### 7.4. M2: `src/vgar/repair/`

| File | Vai trò / output |
|---|---|
| `workspace.py` | Fingerprint/copy repo, lease/path validation, source-size giới hạn, cleanup bản sao; không clone Git worktree bắt buộc |
| `source_preflight.py` | Chạy fingerprint bounded subprocess, trả scope/hash/argv/log/duration; tách khỏi pytest timeout |
| `test_runner.py` | Validate một/nhiều selectors; shell-free `sys.executable -m pytest`; process-tree/output/timeout guards; parse JUnit thành cases/status |
| `baseline.py` | Disposable workspace → pytest trước patch → source hash/source_unchanged → EvidenceBundle `patch_applied=false` |
| `evidence_writer.py` | `begin_run/update_pending/finish_run`; atomic JSON, mỗi invocation identity riêng; không finalize lại record đã đóng |

Pytest output có giới hạn 8 MiB trong wrapper; output quá lớn được báo lỗi/truncated theo result, không hứa capture vô hạn. Full stdout/stderr được giữ trong phạm vi giới hạn đã cấu hình. Test source không tin cậy có thể thực thi code tùy ý trên host dù selector đã được kiểm.

`record_m2_test.py` chạy tests **trong root VGAR hiện tại**, không phải copy toàn bộ suite trước test; nó kiểm source fingerprint trước/sau. `run_m2_baseline.py` mới chạy repo target trên disposable copy. Hai lệnh không có cùng semantics.

### 7.5. Retrieval evaluator: `src/vgar/evaluation/retrieval/`

| File | Vai trò / điểm quan trọng |
|---|---|
| `dataset.py` | Pin HF snapshot, deterministic dev/heldout split theo instance_id, multi-file selection, validate task, download/read bounded source archives |
| `chunks.py` | AST file/function/method entities, spans/qualified names/duplicate identities; code chunks cho BM25/corpus |
| `bm25.py` | Tokenize lexical/camelCase/snake_case, inverted postings, BM25 k1=1.2,b=0.75; rank không đọc patch |
| `gold_labels.py` | Parse developer diff/hunks, align base→patched text trong bộ nhớ, xác định changed file/function; giữ new/deleted/unmapped events |
| `scoring.py` | CorpusIndex, BM25/Graph → RankRecord, dedup/pack/header/max80lines/overlap, same gold denominator/counter cho hai arms |
| `metrics.py` | Recall/MRR/aggregate metrics với eligible denominators; không đo repair PASS |
| `evaluation.py` | BM25 manifest loop, per-task artifacts/summary/config/cost; không graph worker lifecycle |
| `graph_arm.py` | Python tree extraction/integrity + Graph arms + adapter/shared evaluation; gold chỉ chấm sau ranking |
| `graph_cache.py` | Verified graph JSON/meta pair; cache identities/source hashes/schema, explicit rebuild pair mới |
| `worker.py` | Một subprocess/task; TOKENIZER/LOAD_SOURCE/EXTRACT_TREE/BUILD_GRAPH/PREPARE_RETRIEVAL/GROUND/RETRIEVE/SCORE/WRITE |
| `lifecycle.py` | Parent spawn/watchdog/process tree/log/RSS/terminal error và immutable resume fork; filter credentials theo tên |
| `evidence.py` | UTC run IDs, raw SHA256, recursive implementation fingerprint, atomic JSON; `record_command` lưu caller argv/stdout/stderr/exit/time |
| `compare.py` | Strict same-population/protocol/hash checks, valid pairs/failures, per-arm Δ/bootstrap CI, partial nonzero |
| `report.py` | Render saved run/comparison thành REPORT.md; không tự download/rerun retrieval |
| `m1_adapter.py` | Adapter/comparison cho exported context theo đường pipeline cũ; không thay worker của native Graph benchmark mới |

**Cảnh báo:** `bm25.py` còn estimator/helper bytes/4, nhưng official runners inject `LocalTokenizerCounter` vào shared scorer. Thấy estimator trong file không có nghĩa run chính đã dùng fallback; phải đọc `config.counter_label/counter_is_fallback` của run.

### 7.6. M3: MCP, agents và models

| File/nhóm | Vai trò |
|---|---|
| `mcp/client.py` | Dựng MultiServerMCPClient, server subprocess dùng cùng sys.executable; tools có prefix; filter child env |
| `mcp/registry.py` | Required tool sets W3–4/W5–6; validate discovery names |
| `mcp/schemas.py` | Common ToolResponse `status/data/error/metadata`; graph query PASS/ERROR, verification có FAIL/NOT_RUN |
| `mcp/result_parser.py` | Parse JSON trả về qua MCP/LangChain content blocks; không đo model reasoning |
| `mcp/tooling.py`, `audit.py` | Envelope/error mapping/request_id/duration và audit tool/resource calls |
| `mcp/workspace_guard.py` | Server chỉ nhận leased workspace/path allowed; reject root/link escapes trước đọc/ghi/pytest |
| `mcp/servers/graph_server.py` | 5 graph tools + resources: summary/node/subgraph; encoded ID thử raw rồi decode đúng lúc |
| `mcp/servers/repository_server.py` | health/read_file/apply_patch; thực chất exact text edit transaction, không mặc nhiên là arbitrary unified-diff applier |
| `mcp/servers/execution_server.py` | health/run_pytest; dùng M2 runner, lưu full test artifact vào `<audit parent>/m2-tool-runs` |
| `agents/core.py` | LangChain core agent + MCP tool loading/hard tool-call budget; có thể dùng scripted factory trong tests |
| `agents/state.py`, `routes.py` | Typed workflow state và route retry/finalize/fail |
| `agents/runtime.py` | Index repo, settings/agent factory, temp directory lifecycle |
| `agents/workflow.py` | LangGraph outer initialize→prepare→repair→verify→finalize/retry; chỉ repair gọi model |
| `agents/nodes/initialize.py` | Chuẩn hóa input/state trước chạy |
| `agents/nodes/prepare.py` | Index/copy workspace, bind graph/source/version đúng, trả paths cho workflow |
| `agents/nodes/repair.py` | Invoke agent và lưu thông tin thay đổi trong workspace |
| `agents/nodes/verify.py` | Chạy kiểm thử độc lập; không tin câu “đã sửa” của agent |
| `agents/nodes/finalize.py` | Trạng thái cuối và đường bàn giao/evidence của workflow |
| `agents/prompts/{system,inspect,repair,verification}.md` | Prompt text có sẵn; không phải model weights hoặc dataset SFT |
| `models/{base,config,factory}.py`, `models/huggingface/{hf_model,local_hf_chat_model}.py` | Local HF loading/chat adapter; model defaults Qwen3-4B-Instruct-2507; không fine-tune trong đợt này |
| `cli.py` | doctor/tools/index/run/chat; bind host sandbox và independent pytest nếu có selector |

Các `__init__.py` của package chủ yếu định nghĩa/export API hoặc namespace; không phải các bước pipeline cần người dùng chạy lần lượt. Không nên gọi mọi file `.py` một cách riêng lẻ.

### 7.7. Scripts: chọn đúng entry point

| Script | Mục đích | Có model? |
|---|---|---|
| `record_m2_test.py` | Chạy suite/selected tests VGAR, mỗi invocation JSON | Không inference |
| `run_m2_baseline.py` | Baseline test target trong copy, không patch | Không |
| `build_graph.py`, `load_graph_fixture.py` | Repo→graph JSON→SQLite | Không |
| `find_task_anchors.py`, `build_task_overlay.py`, `get_related_context.py` | Direct M1 graph task APIs | Không |
| `run_m1_tests.py` | Entry point tests M1, không benchmark repair | Không |
| `provision_m1_tokenizer.py`, `accept_m1_tokenizer.py` | Provision exact tokenizer files và acceptance/provenance | Không weights |
| `requirements_m1_tokenizer.txt` | Dependency hỗ trợ tokenizer; không phải file tasks |
| `prepare_manifest.py` | Pin/select dataset dev tasks/gold audit; không chạy target tests | Không |
| `run_bm25_retrieval.py`, `run_graph_retrieval.py` | Official retrieval arms | Không |
| `compare_graph_vs_bm25.py` | Pair saved runs, tạo result/REPORT | Không |
| `smoke_w5_w6.py` | Stateless MCP/LangChain context display, pinned counter hoặc diagnostic flag | Không |
| `smoke_w3_w4_full.py` | Deterministic full fixture/MCP/baseline→edit→pytest→evidence | Không |
| `smoke_w3_w4_agent.py` | Scripted orchestrator hoặc HF nếu chọn `--model hf` | Tùy flag |
| `smoke_w3_w4_repair_loop.py` | Fixture repair-loop integration, phải đọc mode/log để xác định model | Không suy thành benchmark repair |
| `smoke_w3_w4.py`, `smoke_mcp.py`, `smoke_real_repo_graph.py` | Connectivity/query/build smoke có sẵn | Không tự chứng minh inference |
| `run_agent.py`, `smoke_workflow.py`, `smoke_hf_agent.py`, `smoke_model.py` | Agent/workflow/model entry points có sẵn | Có thể load/call model, không chạy ở đợt retrieval nghiệm thu |

### 7.8. Data, results, artifacts, logs, docs

| Thư mục/file | Chứa gì? / tác dụng |
|---|---|
| `data/manifests/verified-c104f840cc67-dev-25.json` | 25tasks pin: instance_id/repo/base_commit/problem_statement/split/query/patch hashes/gold path. Là benchmark input, không model checkpoint |
| `data/gold/` | Developer patch evaluator dùng làm labels; không issue prompt |
| `data/downloads/` | HF dataset snapshot caches; clone Git không đảm bảo các binaries được gửi đầy đủ |
| `data/repositories/` | Source archives tại base_commit; `trees/` là Python tree materialized; `trees/rebuilt/<uuid12>/` giữ recovery mới |
| `data/graphs/` | Graph cache pairs; runtime path cụ thể phải xem graph metadata, không đoán từ tên repo |
| `results/retrieval/<run>/result.json` | Summary/config/source identity/task statuses/metrics; comparison result khác shape Graph result |
| `results/retrieval/<graph-run>/tasks/<id>.json` | Canonical per-task output; summary ghi raw artifact hash |
| `results/retrieval/<graph-run>/attempts/<id>/<uuid>/` | Request/pending/telemetry/worker-result/stdout/stderr mỗi attempt, không overwrite attempt trước |
| `artifacts/m1/` | Sample graph/quality review/tokenizer acceptance/assets; số graph sample lịch sử không phải số code hiện tại |
| `artifacts/m2/test-runs/` | Recorder/baseline JSON mặc định, kể cả FAIL/ERROR; không mọi file đều có EvidenceBundle |
| `artifacts/reviews/2026-10-06-w1-w6/` | Audit trước sửa: suite/probes/extra/saved-runs/provenance; tên w1-w6 không mở lại research |
| `artifacts/fixes/w3-w6/` | RED/GREEN/full suite/smoke/recovery/manual/comparison-driver evidence của đợt fix |
| `artifacts/m8-fixture-99543a81/` | Actual synthetic fixture inputs/archives/gold/graph/runs/REPORT giữ để đối chiếu pipeline |
| `logs/mcp_audit.jsonl` | Audit mặc định, append theo calls. Run smoke có audit riêng trong folder để không lẫn |
| `docs/adr/` | Quyết định identity/transaction và stateless task handles; rationale/compatibility/limits |
| `docs/reviews/` | Audit trước fix, kết quả dev25, manual10, affected self-review |
| `docs/superpowers/plans/` | Kế hoạch lịch sử/approved; không thay trạng thái code hiện tại |
| `docs/specs/`, handoff/comparison/graph-quality docs | Specifications và snapshot lịch sử, cần đọc date/addendum |
| `docs/w3_w4_completion.md`, `w5_w6_completion.md` | Task→code→evidence→limits; không tự ký thay owners |
| `docs/context_payload_contract.md`, `mcp_tool_contract.md`, `evidence_bundle_schema.md`, `verification_design.md` | Output/input contracts và phạm vi an toàn/verification |
| `docs/GIAI_THICH_VGAR_M2_W3_W4_VA_CACH_KIEM_THU.md` | Hướng dẫn M2 nền tảng cũ; tài liệu hiện tại bổ sung toàn integration W3–6 |
| `PROGRESS.md` | Checkpoint hiện tại + ledger lịch sử để phiên sau tiếp tục không làm lại |

Các directories runtime/tạm có thể không tồn tại sau clone hoặc đã cleanup. Tên file lạ/rác root không được đợt này xóa nếu chưa rõ thuộc user hay tool; không phải module chính để chạy. Tài liệu này giải thích modules/outputs liên quan, không khẳng định đã audit từng binary/cache entry.

## 8. Các flow: input, xử lý, test, output

### 8.1. Flow A — test code VGAR bằng M2 recorder

**Input:** root `D:\Project\CAPSTONES\VGAR`, selectors như `tests`, `tests/m2` hoặc nhiều file, và timeout. Tests là assertions Python trong `D:\Project\CAPSTONES\VGAR\tests\`; fixtures là source/diff/JSON mẫu bên dưới `tests/fixtures/` hoặc tạo bằng `tmp_path`.

```text
record_m2_test.py + selectors
  → begin_run: ghi JSON pending trước khi fingerprint
  → source_preflight subprocess BEFORE: scoped hash + timeout riêng
  → run_tests: validate selectors → pytest subprocess → JUnit/stdout/stderr
  → source_preflight subprocess AFTER
  → so fingerprint → finish_run atomic JSON → script exit
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, không đọc protocol stdin, không dùng shell command string do model tùy ý truyền. Pytest selectors đã kiểm không path escape hoặc bắt đầu bằng option. Timeout runner/process tree khác preflight timeout.

**Output mặc định:** `D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\<UTC>-<uuid>.json`. Ghi `command/argv/cwd/python_executable/phase`, preflight fields, nested `test_result` gồm `exit_code/duration_ms/stdout/stderr/cases/case_counts/reason`. JUnit được parse vào JSON; `.m2-pytest-*` tạm không phải file tồn tại bền vững để bàn giao. Cần đọc JSON, không mặc định đường JUnit trong command còn mở được.

Nếu code đổi trong test, record ERROR dù pytest có thể exit0. Test suite dùng temp fixtures, source fingerprint guards chỉ phạm vi inventory đã định nghĩa, không chứng minh mọi file trên ổ D bất biến.

### 8.2. Flow B — baseline và scripted repair fixture

**Baseline input:** `D:\Project\CAPSTONES\VGAR\tests\fixtures\m2\failing_repo\src\demo.py` và `...\tests\test_demo.py`; selector `tests/test_demo.py::test_answer`.

```text
Target fixture lỗi → create_workspace(copy + hash)
  → pytest trước patch → FAIL như fixture thiết kế
  → EvidenceBundle patch_applied=false
  → source hash trước/sau không đổi → cleanup copy
```

`run_m2_baseline.py` dừng ở đó. Nó **không sửa** `demo.py`, không dùng developer gold patch để tự repair.

Với `smoke_w3_w4_full.py`, flow khác:

```text
sample_repo → graph JSON → SQLite → MCP query/resources
failing_repo → leased copy → baseline FAIL
  → scripted exact edit qua Repository MCP
  → Execution MCP → M2 pytest → PASS
  → EvidenceBundle + audit + source fixture unchanged
```

Output khi dùng `--keep`: script in `artifacts: <temp work>`; gồm graph.json/graph.db/mcp_audit.jsonl/evidence và các tool records. Workspace lease riêng vẫn cleanup theo logic script; không nhầm `--keep` là giữ mã repaired lease mãi mãi. Patch là hành vi định sẵn của fixture, không model học/hiểu SWE-bench.

### 8.3. Flow C — W6 stateless MCP context

**Input:** fixture failing_repo, hai issue nói về `demo.answer`, pinned tokenizer manifest. Script tạo copy dưới output run folder, graph JSON/SQLite và Settings source_root rõ ràng.

```text
Issue A → Graph MCP find_task_anchors → {anchor_ids, task_handle_A}
Issue B → Graph MCP find_task_anchors → {anchor_ids, task_handle_B}
                  (cùng anchors nhưng khác task handle)
Session mới → get_related_context(anchors,8000,task_handle_A) → ContextPayload A
Session mới → get_related_context(anchors,8000,task_handle_B) → ContextPayload B
Session mới → handle_A lần nữa → context A không bị issue B ghi đè
Unknown handle → ERROR, không giả context
```

Vì adapter mở session mới mỗi tool call, `anchor_ids` đơn thuần không đủ biết issue. SQLite `task_contexts` giữ task binding bất biến; metadata trả task_handle/overlay_id/counter label. Frozen `data` vẫn là ContextPayload, không thêm schema_version hoặc nhét sidecar vào data.

**Context item:** node_id/path/symbol/range/snippet/relevance_score/graph_distance/graph_rationale/confidence/token_count. **Context tổng:** graph_version/anchor_ids/items/total_token_count/token_budget/truncated.

**Output:** `D:\Project\CAPSTONES\VGAR\artifacts\fixes\w3-w6\<run>\{result.json,graph.json,graph.db,context.json,CONTEXT.md,mcp_audit.jsonl,fixture\...}` mặc định; có thể chọn output-root riêng. Result giữ calls/arguments/responses/hashes, inferenceNOT_RUN. Flow test assertions về binding/budget/hash/display, không đánh giá LLM repair.

### 8.4. Flow D — SWE-bench retrieval benchmark và comparison

**Input chính:**

- Manifest đầy đủ: `D:\Project\CAPSTONES\VGAR\data\manifests\verified-c104f840cc67-dev-25.json`.
- Query: trường `problem_statement` trong từng task, không phải toàn bộ file proposal hoặc developer diff.
- Repo/base source: `repo` và immutable `base_commit` trong task; archive có `source_provenance.cache_path` thật trong task output, dưới `data/repositories/`.
- Gold: `gold_patch_path` dưới `data/gold/`; chỉ evaluator đọc sau ranking. Exact path từng task xem manifest, không giả tên cố định.
- Counter: `artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json`, Qwen3-4B tokenizer pin; 8000 snippet tokens.

```text
                         Manifest task + problem_statement
                                       |
            +--------------------------+-------------------------------+
            |                                                          |
  BM25: archive→Python AST chunks                      Graph task worker
            |                                      TOKENIZER / LOAD_SOURCE
       lexical rank                                  EXTRACT_TREE / BUILD_GRAPH
            |                                        PREPARE_RETRIEVAL
            |                                        GROUND / RETRIEVE
            +--------------------------+-------------------------------+
                                       |
                     SCORE: mở developer patch, extract gold
                     normalize identity / same pack / same metrics
                                       |
                           canonical task JSON + run summary
                                       |
                 compare_runs: verify population/protocol/artifact hashes
                                       |
                          result.json + REPORT.md + paired CI
```

Parent chạy **một worker tại một thời điểm**, mỗi task deadline300s tổng. PREPARE_RETRIEVAL tạo CorpusIndex/overlay builder/retriever/include policy; constructor có validation/copy/index work nên vẫn tốn thời gian trước GROUND. GraphF2P dùng FAIL_TO_PASS metadata riêng, không coi là actual base test failures đã chạy.

M2 scorer ánh xạ graph candidate sang AST code identity/source spans, rồi chấm cùng gold với BM25. Gold-function bao gồm những changed entities có thể map về base; new-file/new-function/deleted/unmapped được ghi riêng. Gold không phải tất cả code liên quan, vì developer có thể chọn một trong nhiều giải pháp.

**Output cụ thể của lần đã đo:**

```text
D:\Project\CAPSTONES\VGAR\results\retrieval\20261007T014445273889Z-664d06a6c1c0\
  result.json                      25 attempts,19success,6errors; config/source/status
  tasks\<instance_id>.json         rank/packed/gold/metrics hoặc failure/attempt_path
  attempts\<instance_id>\<uuid>\
    request.json                    manifest row/config/counter input
    result.json                     pending/terminal của parent
    telemetry.json                  phase/stages/RSS
    worker-result.json              worker output/trace khi worker gửi được
    stdout.log, stderr.log          capture logs

D:\Project\CAPSTONES\VGAR\results\retrieval\20261007T022806825449Z-7e61dc92fe7b\
  result.json                       COMPARED_PARTIAL,19pairs/25attempts
  REPORT.md                         metric tables, coverage, CI, oracle riêng
```

Timeout/crash có thể không có `worker-result.json`; đó là khác biệt có chủ đích, không giả worker đã finalize. Đọc canonical task/parent result/telemetry để biết lỗi. Không chia metrics cho19 rồi nói population25 đều thành công.

### 8.5. Flow E — regression host source binding

Test ở `tests/test_host_retrieval_binding.py` tạo hai repo tạm: `demo.answer` trả0 ở target và trả99 ở foreign repo. Parametrize CLI/workflow × sourceNone/foreignbinding thành4 cases.

```text
Foreign/empty graph settings + target repo
  → host index/copy → fresh SQLite DB + leased workspace
  → source_root=lease.path / version=None
  → reopen store như consumer thật → find anchors → retrieve
  → assert snippet có return0, không return99
  → assert token policy/settings/source target không bị đổi
```

Test dùng counter từ đếm words cho fixture, **không official benchmark tokenizer**. Không invoke model, không mock context. Source/version bindings là cấu hình ở Settings, không đổi entity IDs cho đẹp kết quả. Sau khi agent sửa source, hash guard snapshot cũ có thể fail: fix này không implement incremental reindex.

## 9. Đã kiểm thử những gì, kết quả nằm ở đâu?

### 9.1. Test files theo lỗi/ranh giới

| Nhóm tests | Điều kiểm tra |
|---|---|
| `tests/m2/test_retrieval_compare_contract.py`, `test_graph_arm.py`, `test_retrieval_scoring.py` | Actual runner shape, strict pairing/hash/gold/denominators, full-rank/cap/packing, fixture compare→REPORT |
| `tests/test_graph_transaction_bindings.py`, builder/schema/robustness tests | Failed-file rollback/inventory, compound/duplicate definitions, import/inheritance binding, property setter, schema |
| `tests/test_source_scope.py`, `tests/m2/test_workspace.py` | Operational prune, genuine package data preserved, snapshot/hash/limits, timeout pending |
| `tests/test_mcp_workspace_guard.py`, `tests/test_mcp_stdio_smoke.py` | Actual stdio, leased root/path/link/reparse, CRLF atomic edit, common envelope/process/exec guards |
| `tests/m2/test_retrieval_cache_integrity.py` | Tampered tree/pair/schema/config/implementation/relative root/reparse, explicit immutable rebuild |
| `tests/m2/test_retrieval_lifecycle.py` | Worker success/failure/timeout/crash/log limits/RSS/resume guards/atomic write/credential filter |
| `tests/test_w5_w6_retrieval_mcp.py` | task_handle across sessions, same anchors/different issues, SQLite metadata/spans, errors/limits/resources/frozen context |
| `tests/test_host_retrieval_binding.py` | Four real index/store/retrieval source-binding regressions |
| `tests/m2/test_test_runner.py`, `test_baseline.py`, `test_evidence_writer.py`, `test_contracts.py` | Pytest output/JUnit/selectors/deadline/cases, prepatch baseline, JSON lifecycle/evidence contracts |
| `tests/test_task_anchors.py`, `test_task_overlay.py`, `test_graph_retrieval.py`, `test_token_counter.py` | Grounding/traces/retrieval features/token count/source integrity |
| `tests/test_settings.py`, `test_mcp_client.py`, `test_mcp_tool_contract.py`, `test_mcp_result_parser.py` | Settings/env/child process config, tool names/contracts/content parsing |
| `tests/test_agent_tools.py`, `tests/unit/test_{state,tool_budget,workflow}.py`, `test_hf_model.py` | Workflow/core/state/budget/model adapters via test fixtures/mocks; không quality benchmark của LLM thật |

Các test files khác vẫn được full suite collect theo pyproject; bảng này nhóm theo purpose, không nói chỉ các file trong bảng được chạy. `tests/fixtures` không bị collect như bộ task benchmark khi chạy `tests`.

### 9.2. Ledger kết quả chính

RED là cố ý chạy regression trước fix để thấy bug. Failed/intermediate artifacts được giữ, không phải tất cả là lỗi hiện tại còn tồn tại. Counts tăng do thêm tests/parametrization, không thể lấy số testcase thành % task đồ án hoàn thành.

| Giai đoạn | Kết quả đã ghi | Evidence từ root VGAR |
|---|---|---|
| Audit trước fix | 196passed,1skipped | `artifacts/reviews/2026-10-06-w1-w6/suite.json` + invocation/probes |
| Milestone1 | 229passed,1skipped | `artifacts/fixes/w3-w6/20261006T142425974910Z-8fb13933b223/result.json` |
| Milestone2 | 262passed,1skipped | `artifacts/fixes/w3-w6/20261006T143502696933Z-6cb5ab8fc972/result.json` |
| Milestone3 | 280passed,1skipped | `artifacts/fixes/w3-w6/milestone-3-recorder/20261006T144237228849Z-4325f253f000497e91f42f1d239d7a92.json` |
| Milestone4 | 297passed,4skipped | `artifacts/fixes/w3-w6/milestone-4-final-recorder/20261006T145817942402Z-f51338144ff44baf9107386b9162e8fa.json` |
| Milestone5 sau fix lock | 333passed,4skipped | `artifacts/fixes/w3-w6/milestone-5-final-lock-recorder/20261006T152645096811Z-b038ede0d432457686d956b8dae4f9d2.json` |
| Các regression/tokenizer/fixture sau đó | 353→354→355passed,4skipped | Ledger PROGRESS, không lẫn các RED artifacts |
| Host binding RED | 4failed đúng bug cần sửa | `artifacts/fixes/w3-w6/host-source-binding/red/20261007T022822980290Z-56e0e1b5b2f0/result.json` |
| Host binding targeted GREEN | 24passed | `artifacts/fixes/w3-w6/host-source-binding/green/20261007T022850657004Z-ab7bcbcda011/result.json` |
| Full recorder cuối | **359passed,4skipped**, testexit0, phaseDONE, source trước=sau | `artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json` |
| Actual fixture gate8.2 | PASS, giữ input/source và fullREPORT | `artifacts/fixes/w3-w6/20261007T012636266959Z-7ac7378bc98e/result.json` |
| Official MCP fixture | PASS với pinned tokenizer | `artifacts/fixes/w3-w6/20261006T155804375314Z-70ff70a28f6c/result.json` |
| No-Jedi pilot3 | SUCCEEDED3/3 | `results/retrieval/20261007T013925676777Z-55ae5fb6a24a/result.json` |
| No-Jedi dev25 | PARTIAL_FAILURE19success/3FAILED/3ERROR | `results/retrieval/20261007T014445273889Z-664d06a6c1c0/result.json` |
| Real paired comparison | COMPARED_PARTIAL19/25,exit1 chủ đích | `results/retrieval/20261007T022806825449Z-7e61dc92fe7b/result.json` |
| BM25 recovery | 25/25rawhash đúng | `artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/result.json` |
| Manual10 đã diễn giải | Self-audit completed, không sign-off | `artifacts/fixes/w3-w6/manual10-no-jedi/completed/20261007T021118025559Z-44e2a8e0c817/result.json` + manual review |
| Docs kiểm trước tài liệu này | PASS79local links,20PS blocks parse | `artifacts/fixes/w3-w6/doc-checks/20261007T023848631553Z-4a967f69cae2/result.json` |

**Lưu ý về đường dẫn ledger:** tên run là output thật, không phải input cần người dùng gõ lại khi tự test. Phần11 tự tìm run mới theo output-root/task-id. Tài liệu giải thích này không chạy lại suite/benchmark; số liệu trên là saved evidence của đợt fix trước, không fresh runtime measurements lúc viết tài liệu.

Bốn skip của full recorder cuối:

- `tests.m2.test_workspace::test_external_symlink_rejected`.
- `tests.test_mcp_workspace_guard::test_link_target_is_rejected_before_read_or_write`.
- `tests.test_mcp_workspace_guard::test_root_symlink_cannot_redirect_lease_to_original`.
- `tests.test_mcp_workspace_guard::test_selector_inside_lease_cannot_reference_external_symlink`.

Máy không có quyền tạo real symlink cần cho fixtures. Chúng được serialized `NOT_RUN`; synthetic reparse guard tests vẫn chạy. Không gọi skip là pass. Full suite có pytest140,38s, nested testduration143,797s, wrapper144,980s — đó là ba lớp timing khác nhau.

## 10. Đọc kết quả benchmark và tài nguyên

### 10.1. Kết quả primary conditional19 pairs

| Metric | BM25 | Graph issue-only | Hiểu thế nào? |
|---|---:|---:|---|
| File Recall@5 | 0,5439 | 0,2412 | Trung bình phần gold files tìm được trong5files đầu sau dedup; không task repair rate |
| Function Recall@5 | 0,2982 | 0,0877 | Phần gold functions tìm được trong5functions đầu |
| File MRR | 0,5888 | 0,3023 | Vị trí gold file đầu tiên, càng sớm càng tốt |
| Function MRR | 0,4334 | 0,1944 | Vị trí gold function đầu tiên |
| Packed gold-function coverage | 0,4690 | 0,2316 | Gold source range thực sự có trong snippets đã pack |
| Mean packed tokens | 7997,7 | 7142,2 | Snippet/header budget cost theo scorer; thấp hơn không tự tốt hơn |

Graph hiện **kém BM25 trên phần lớn metric của19successpairs**. Có0no-anchor tasks nhưng trung bình78,6anchors/task; nhiều anchors không bảo đảm anchors relevant. Không đổi weights/gold/scorer rồi nói kết quả cũ tốt hơn.

Ví dụ một task có gold2files, top5 chứa1file đúng → fileRecall@5=1/2. Gold đầu ở rank4 → reciprocal rank1/4. File đúng xuất hiện trong ranking nhưng snippet bị budget loại hoặc không chứa gold lines → packed coverage có thể thấp hơn rank recall.

CI paired bootstrap95%,2000resamples,seed0; Δ=Graph−BM25. FileRecall@5 Δ−0,3026, CI[−0,5088;−0,0921]. FunctionRecall@5 Δ−0,2105, CI[−0,3596;−0,0702]. CI conditional trên19pairs, **không** đo cả25 vì6failure không có valid ranking; tất cả Sympy thất bại gây selection bias. Không thêm confirmatory statistical claim cho nhiều hypotheses từ bảng descriptive này.

### 10.2. Đọc REPORT đúng

REPORT được tạo với BM25 source run25 làm nền. Header/“Số chính”/per-task BM25 có thể ghi completed25. **Riêng phần GraphvsBM25/coverage là19pairs trên25attempts.** Đừng dùng header để kết luận Graph25/25. Oracle GraphF2P phải đọc riêng. Comparisonexit1 ở trạng thái COMPARED_PARTIAL là báo thiếu coverage, không scorer crash.

Gold labels là changed-code proxy. New files chưa tồn tại ở base không thể retrieve từ base. Unmapped/ineligible labels cần N/A/denominator đúng, không biến mọi missing label thành0 hoặc drop âm thầm. Mapping coverage1 trong19eligible cases không chứng minh call edges/relevance hoàn hảo.

### 10.3. Vì sao mất thời gian, và có cần GPU không?

Dev25 mất2576,420s≈42,94phút tổng. Success19: mean86,005s/task,median63,949s,p95/max176,730s. BUILD_GRAPH stage hiện tại mean57,582s trên success19. Ba cachehits khiến metadata `graph_build_seconds` có thể là build từ trước; khi đọc latency phải dùng telemetry hiện tại, không giả cold/warm giống nhau.

Peak RSS lớn nhất quan sát4.904.476.672bytes≈4,57GiB. Đây là resident RAM/process-tree sampling, không GPUVRAM/virtual-memory/totalTaskManagerRAM. Pytest, Windows, IDE và source/caches có chi phí thêm; không hứa máy chỉ cần đúng4,57GiB là chắc chắn đủ. Ba Sympy hết deadline **trước ranking**, hai Django lỗi permission, Pylint lỗi graph schema: không có căn cứ gộp tất cả thành thiếu GPU/RAM.

Retrieval/test fixtures ở đây không load weights/call LLM: API inference cost **0USD**. CPU/RAM/disk/network/thuê máy vẫn có chi phí. Cài pyproject có torch/model dependencies nhưng không nghĩa retrieval cần GPU. Model inference thật là flow khác, có thể chậm do offload; đợt này không đo hoặc fix nó.

## 11. Tự chạy trên Windows PowerShell từ đầu đến cuối

Phần này cho thành viên **tự chọn chạy**, không có lệnh benchmark nào được tự động thực thi lúc viết tài liệu. Khuyến nghị: đọc evidence đã có → setup nếu thiếu → unit/baseline/smoke. Benchmark đang dừng theo user fail1-rule, chỉ mở lại khi được duyệt. Không chạy tất cả blocks bất chấp cảnh báo.

### 11.1. Lần đầu: tạo venv riêng, không mượn hệ thống cũ

**Chỉ chạy nếu máy/checkout chưa setup.** Không gõ cả ký hiệu prompt `(.venv) PS ...>` và không đổi execution policy toàn máy.

```powershell
# LẦN ĐẦU: vào root VGAR; nếu clone nơi khác, thay đúng root một lần.
Set-Location 'D:\Project\CAPSTONES\VGAR'

# LẦN ĐẦU: chỉ tạo venv khi chưa có, không overwrite venv đang hoạt động.
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Không tạo được Python 3.11 venv; kiểm tra py --list.' }
}

# LẦN ĐẦU hoặc khi dependencies đổi: dùng đúng interpreter của repo này.
# Cần mạng/package access và disk; bước này có thể cài cả torch/model dependencies.
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Cài dependency lỗi; dừng, không chạy benchmark.' }

# LẦN ĐẦU: copy config mẫu nếu chưa có; không overwrite secrets hiện tại.
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
```

Không cần pip install lại ở mỗi lần test. Khi package import/counter bị mismatch, đọc thông báo và pyproject trước; không tự upgrade hàng loạt để né pin. Python3.11 là ví dụ cùng major/minor với máy đã đo; pyproject cho phép3.11–3.13 nhưng không hứa mọi wheel/environment khác đều đã được nghiệm thu.

### 11.2. Mỗi phiên PowerShell: bind `$python`, encoding và source rõ ràng

```powershell
# MỖI PHIÊN: shell mới không nhớ biến $python của shell cũ.
Set-Location 'D:\Project\CAPSTONES\VGAR'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) { throw 'Chưa có venv riêng; làm 11.1 trước.' }
$python = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')
& $python --version

# CHỈ ĐỌC/IMPORT: xác nhận đang import package VGAR, không package cũ editable.
& $python -c "import sys,vgar; print(sys.executable); print(vgar.__file__)"
if ($LASTEXITCODE -ne 0) { throw 'Import VGAR lỗi; không chạy tiếp.' }
```

Kỳ vọng `vgar.__file__` nằm dưới `D:\Project\CAPSTONES\VGAR\src\vgar\`. Nếu `& $python` báo “expression ... not valid”, thường `$python` chưa đặt/không phải command path. Chạy lại block11.2, không paste chỉ dòng invoke trong shell mới.

Không cần activate venv khi luôn dùng `& $python`. Nếu thích activate, chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` và `.\.venv\Scripts\Activate.ps1` **trong phiên đó**; không bắt buộc đổi policy machine-wide. `$env:PYTHONUTF8='1'` hữu ích tránh lỗi tiếng Việt, không sửa graph/model hoặc tốc độ benchmark.

### 11.3. Đọc evidence trước, không chạy lại benchmark

Block này không cần Python/venv; chỉ đọc JSON đã có. Nó chọn **full25 no-Jedi complete**, không chọn pilot/latest arbitrary folder. Kết quả complete có thể là partial failure.

```powershell
# CHỈ ĐỌC: tự tìm full25 no-Jedi mới nhất theo metadata, không nhập run ID.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$graphCandidates = @(Get-ChildItem -LiteralPath '.\results\retrieval' -Directory | ForEach-Object {
    $jsonPath = Join-Path $_.FullName 'result.json'
    if (Test-Path -LiteralPath $jsonPath) {
        $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $jsonPath | ConvertFrom-Json
        if ($record.kind -eq 'retrieval_graph' -and $record.complete -eq $true -and
            $record.task_results.Count -eq 25 -and $record.config.graph.use_jedi -eq $false) {
            [pscustomobject]@{ Path=$_.FullName; Started=$record.started_utc; Data=$record }
        }
    }
})
$selectedGraph = $graphCandidates | Sort-Object Started -Descending | Select-Object -First 1
if (-not $selectedGraph) { throw 'Không tìm thấy saved full25 no-Jedi; không tự chạy benchmark để bù.' }
$graphRun = $selectedGraph.Path
$graphResult = $selectedGraph.Data
Write-Host "Đang đọc: $graphRun"
$graphResult | Select-Object run_id,status,complete,exit_code,duration_seconds
$graphResult.task_results | Group-Object status | Select-Object Name,Count
$graphResult.task_results | Select-Object instance_id,status,phase,duration_seconds,peak_rss_bytes

# CHỈ ĐỌC: lấy failure canonical JSON; không tự retry task lỗi.
foreach ($task in @($graphResult.task_results | Where-Object { $_.status -ne 'SUCCEEDED' })) {
    $taskPath = Join-Path $graphRun ('tasks\' + $task.instance_id + '.json')
    Write-Host "Failure artifact: $taskPath"
    Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath
}
```

Selector này tìm saved runs để đọc, **không xác nhận hash/protocol bằng mắt**. Khi compare phải dùng strict comparator/hash checks. Nếu có run khác về sau, lệnh hiển thị run mới nhất đúng loại; muốn đối chiếu chính xác số liệu07/10, dùng paths bất biến trong mục9/10.

Đọc comparison khớp chính graph run đó, không chọn REPORT của một smoke:

```powershell
# CHỈ ĐỌC: cần biến $graphRun ở block11.3, cùng shell.
$comparisons = @(Get-ChildItem -LiteralPath '.\results\retrieval' -Directory | ForEach-Object {
    $jsonPath = Join-Path $_.FullName 'result.json'
    if (Test-Path -LiteralPath $jsonPath) {
        $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $jsonPath | ConvertFrom-Json
        if ($record.kind -eq 'graph_vs_bm25' -and $record.complete -eq $true -and $record.graph_run -eq $graphRun) {
            [pscustomobject]@{ Path=$_.FullName; Started=$record.started_utc; Data=$record }
        }
    }
})
$chosenComparison = $comparisons | Sort-Object Started -Descending | Select-Object -First 1
if (-not $chosenComparison) { throw 'Không thấy comparison cho graph run đã chọn; đọc status trước, không giả REPORT có sẵn.' }
$comparisonResult = $chosenComparison.Data
$comparisonResult | Select-Object run_id,status,complete,exit_code,paired_tasks,eligible_bm25_tasks
$comparisonResult.coverage | ConvertTo-Json -Depth 6
$reportPath = Join-Path $chosenComparison.Path 'REPORT.md'
if (-not (Test-Path -LiteralPath $reportPath)) { throw 'Saved comparison thiếu REPORT.md.' }
Get-Content -Encoding UTF8 -LiteralPath $reportPath
```

Saved `graph_run` là absolute path của máy tạo evidence. Sau clone khác root, so sánh path literal có thể không match: đó là provenance cũ, **không sửa JSON cũ**. Chọn comparison theo run_id/hash từ metadata hoặc đọc report paths ở mục9 sau đổi phần root local, rồi strict-verify artifacts khi cần. Khối trên dành cho checkout/root hiện tại đã đo.

### 11.4. Test nhẹ trước: chỉ regression host binding

Từ11.2 dùng `$python` đã bind. Mỗi lần test dùng **folder riêng tự tạo**, không nhập UTC run folder và không trộn với smoke/benchmark.

```powershell
# TEST MỚI: chạy4cases host binding, không load model; tạo evidence mới.
$testRoot = Join-Path '.\artifacts\m2\manual-checks' ('host-binding-' + [guid]::NewGuid().ToString('N'))
& $python scripts\record_m2_test.py tests/test_host_retrieval_binding.py --task-id my-host-binding --timeout-seconds 120 --preflight-timeout-seconds 30 --artifact-dir $testRoot
$testExit = $LASTEXITCODE
Write-Host "Script exit: $testExit"

# CHỈ ĐỌC: tự lấy JSON trong folder vừa dùng, không gõ tên file evidence.
$testFile = Get-ChildItem -LiteralPath $testRoot -Filter '*.json' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $testFile) { throw 'Không có evidence; xem lỗi setup trước khi pytest chạy.' }
Write-Host "Evidence: $($testFile.FullName)"
$testResult = Get-Content -Raw -Encoding UTF8 -LiteralPath $testFile.FullName | ConvertFrom-Json
$testResult | Select-Object task_id,status,complete,phase,python_executable
$testResult.test_result | Select-Object exit_code,duration_ms,status,case_counts
$testResult.test_result.stdout
$testResult.test_result.stderr
$testResult | Select-Object source_hash_before,source_hash_after
```

Ở phiên bản đã nghiệm thu, bốn cases này đã pass trong evidence. Nếu lần tự chạy đầu fail, giữ JSON/trace và dừng task đó để điều tra; không chạy lặp lại nhiều lần hoặc sửa packages tùy tiện. Sau thay đổi code/dependencies, số cases/timing có thể khác, phải đọc output thật.

### 11.5. Test nhiều file, cả M2, hoặc toàn bộ suite VGAR

**Nhiều file không cần một test selector đặc biệt “multifile”.** Có thể truyền nhiều selectors vì recorder nhận `nargs='+'`; một file test cũng có thể kiểm logic xuyên nhiều source files. “Chạy nhiều file test” và “lỗi cần sửa nhiều source files” là hai khái niệm khác nhau.

```powershell
# TÙY CHỌN: test2files liên quan boundary, không toàn suite.
$checkRoot = Join-Path '.\artifacts\m2\manual-checks' ('boundary-' + [guid]::NewGuid().ToString('N'))
& $python scripts\record_m2_test.py tests/test_host_retrieval_binding.py tests/test_w5_w6_retrieval_mcp.py --task-id my-boundary-check --timeout-seconds 180 --preflight-timeout-seconds 30 --artifact-dir $checkRoot
$LASTEXITCODE
```

Hoặc test cả thư mục M2:

```powershell
# TÙY CHỌN: toàn tests/m2, chưa phải tất cả M1/M3.
$checkRoot = Join-Path '.\artifacts\m2\manual-checks' ('m2-' + [guid]::NewGuid().ToString('N'))
& $python scripts\record_m2_test.py tests/m2 --task-id my-m2-suite --timeout-seconds 240 --preflight-timeout-seconds 30 --artifact-dir $checkRoot
$LASTEXITCODE
```

Hoặc toàn bộ bộ test code:

```powershell
# TÙY CHỌN: full suite, chạy1lần khi thực sự muốn nghiệm thu checkout hiện tại.
$checkRoot = Join-Path '.\artifacts\m2\manual-checks' ('full-suite-' + [guid]::NewGuid().ToString('N'))
& $python scripts\record_m2_test.py tests --task-id my-full-suite --timeout-seconds 240 --preflight-timeout-seconds 30 --artifact-dir $checkRoot
$suiteExit = $LASTEXITCODE
Write-Host "Full suite script exit: $suiteExit"

# CHỈ ĐỌC: tự đọc kết quả vừa chạy, không chọn latest ở folder khác.
$checkFile = Get-ChildItem -LiteralPath $checkRoot -Filter '*.json' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $checkFile) { throw 'Không có JSON full-suite.' }
$checked = Get-Content -Raw -Encoding UTF8 -LiteralPath $checkFile.FullName | ConvertFrom-Json
$checked | Select-Object run_id,task_id,status,complete,phase
$checked.test_result.case_counts | ConvertTo-Json
$checked.test_result.cases | Where-Object { $_.status -ne 'PASS' } | Select-Object name,status,detail
$checked.test_result.stdout
$checked.test_result.stderr
```

Đọc exit ngay sau command, trước command khác. `Get-Content`/`Write-Host` không thay cho test status. `record_m2_test` trả script exit1 khi FAIL/ERROR/hash change; nested pytest exit code có thể khác. Timeout240 cho pytest, thêm preflight30 trước/30 sau và setup/cleanup, không có nghĩa toàn wrapper chắc chắn kết thúc trong240s.

### 11.6. Chạy baseline có chủ đích FAIL để hiểu M2

```powershell
# TEST MỚI: fixture này cố ý lỗi answer0 !=42. Baselinekhôngsửa repo.
$baselineRoot = Join-Path '.\artifacts\m2\manual-checks' ('baseline-' + [guid]::NewGuid().ToString('N'))
& $python scripts\run_m2_baseline.py tests\fixtures\m2\failing_repo tests/test_demo.py::test_answer --task-id my-prepatch-baseline --timeout-seconds 120 --artifact-dir $baselineRoot
$baselineExit = $LASTEXITCODE
Write-Host "Baseline exit: $baselineExit (1 dự kiến với fixture lỗi)"

# CHỈ ĐỌC: output phải cópatch_applied=false, testsFAIL và source hashgiữ nguyên.
$baselineFile = Get-ChildItem -LiteralPath $baselineRoot -Filter '*.json' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $baselineFile) { throw 'Thiếu baseline evidence; xem lỗi workspace/setup.' }
$baseline = Get-Content -Raw -Encoding UTF8 -LiteralPath $baselineFile.FullName | ConvertFrom-Json
$baseline | Select-Object status,complete,source_hash_before,source_hash_after
$baseline.evidence_bundle.verification | ConvertTo-Json -Depth 6
Get-Content -Encoding UTF8 -LiteralPath tests\fixtures\m2\failing_repo\src\demo.py
```

`src/demo.py` vẫn `return 0` là **đúng** với baseline, không phải agent sửa thất bại: lệnh này không chạy agent. Để thấy patch→PASS cần flow scripted tiếp theo hoặc một repair task thật có model/executor đã nghiệm thu.

### 11.7. Full scripted smoke, lưu cả caller logs vào một JSON

Script full có mode `--keep` giữ graph/audit/evidence ở temp work. Dùng `record_command` có sẵn để capture command/exit/stdout/stderr/duration vào folder mới. Đây không bổ sung script sản phẩm.

```powershell
# TÙY CHỌN: deterministic full smoke,không HF model, không external SWE-bench tests.
# --keep giữ tool/evidence tempfolder; tempfolder path nằm trong stdout captured.
$recordRoot = 'artifacts/m2/manual-checks/full-smoke-caller'
& $python -B -c "import sys; from pathlib import Path; sys.path.insert(0,'src'); from vgar.evaluation.retrieval.evidence import record_command; command=[sys.executable,'-B','scripts/smoke_w3_w4_full.py','--strict-resources','--keep']; p,r=record_command(command,Path('.'),Path(sys.argv[1]),timeout=240,kind='manual-full-smoke'); print(p); print(r['stdout']); print(r['stderr']); raise SystemExit(r['exit_code'])" $recordRoot
$smokeExit = $LASTEXITCODE
Write-Host "Full smoke exit: $smokeExit"
```

Caller JSON chứa transcript và actual temp path. `record_command` timeout là capture timeout của wrapper, không bảo đảm process-tree/security isolation cho mọi command; subprocess pytest bên dưới vẫn có M2 process guards. Không dùng helper này để execute code không tin cậy hoặc benchmarks bị dừng. Nếu chạy bị hủy/mất điện, giữ pending/log và kiểm đúng invocation, không kill mọi Python trên máy.

### 11.8. Tokenizer: chỉ provision khi thiếu assets

**Lần đầu khi clone thiếu bundle**, cần mạng. Không tải weights và không overwrite acceptance manifest đã pin. Tokenizer có bốn files approved, tổng15.880.703 bytes trong lần provision đã ghi; không phải model Qwen4B nặng nhiều GB.

```powershell
# CHỈ ĐỌC/VALIDATE: kiểm tokenizer bundle đúng manifest/hash/runtime trước.
$tokenizerManifest = 'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json'
if (-not (Test-Path -LiteralPath $tokenizerManifest)) { throw 'Thiếu acceptance manifest; lấy đúng artifact từ team, không tự thay pin.' }
& $python -B -c "import sys; sys.path.insert(0,'src'); from vgar.graph.token_counter import LocalTokenizerCounter; c=LocalTokenizerCounter(sys.argv[1]); print(c.counter_label); print(c.provenance); print(c('def answer(): return 0'))" $tokenizerManifest
$counterExit = $LASTEXITCODE
Write-Host "Tokenizer check exit: $counterExit"
```

Nếu check fail, phân biệt thiếu assets, hash mismatch, runtime compatibility từ error. **Chỉ khi assets thiếu**, provision exactpin:

```powershell
# LẦN ĐẦU KHI THIẾU ASSETS: tạo manifest provisioning riêng, không đổi acceptance.
$provisionManifest = Join-Path '.\artifacts\m1' ('tokenizer-provision-' + [guid]::NewGuid().ToString('N') + '.json')
& $python scripts\provision_m1_tokenizer.py --model-id Qwen/Qwen3-4B-Instruct-2507 --revision cdbee75f17c01a7cc42f958dc650907174af0554 --assets-root artifacts\m1\tokenizers --manifest $provisionManifest
if ($LASTEXITCODE -ne 0) { throw 'Provision không thành công; không dùng fallback để chấm official benchmark.' }
```

Counter kiểm đúng bốn approved files/tokenizer version/hash/policy. Nếu assets hiện có bị corruption, provisioner từ chối thay vì silently overwrite; cần leader xác định nguyên nhân và recovery copy, không xóa bundle/hash guard tùy ý.

### 11.9. W6 context qua MCP, tự tìm output vừa tạo

```powershell
# TEST MỚI: dùng pinned counter, không model. Output-root riêng giúp tự chọn chính xác.
$w6Root = Join-Path '.\artifacts\m2\manual-checks' ('w6-context-' + [guid]::NewGuid().ToString('N'))
& $python scripts\smoke_w5_w6.py --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --output-root $w6Root
$w6Exit = $LASTEXITCODE
Write-Host "W6 MCP exit: $w6Exit"
$w6Dir = Get-ChildItem -LiteralPath $w6Root -Directory | Sort-Object Name -Descending | Select-Object -First 1
if (-not $w6Dir) { throw 'Không có W6 runfolder.' }
$w6Result = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $w6Dir.FullName 'result.json') | ConvertFrom-Json
$w6Result | Select-Object status,complete,inference,counter_label,counter_is_fallback,duration_seconds
$w6Result.calls | Select-Object tool,arguments,response
$w6Context = Join-Path $w6Dir.FullName 'CONTEXT.md'
if (Test-Path -LiteralPath $w6Context) { Get-Content -Encoding UTF8 -LiteralPath $w6Context }
else { $w6Result | ConvertTo-Json -Depth 8 }
```

Thiếu official tokenizer có thể dùng `--allow-fallback-counter` **chỉ** để diagnostic fixture khi được chọn; output phải flag fallback, không nhập vào official comparison. Không chạy cả hai flags tokenizer/fallback cùng lúc vì argparse yêu cầu chọn một trong hai.

### 11.10. Sau clone: data lấy ở đâu? Khi nào chạy retrieval mới?

Team nên mang theo approved manifest/gold/acceptance manifest và lấy source archives bằng pipeline. Hai download/source-cache folders có thể không được Git push đầy đủ; clone source code không tạo data tự động. `--offline` nghĩa **không download source**, thiếucache là LOAD_SOURCEerror, không phải code ranking yếu.

Nếu approved manifest đã có, đừng regenerate nó chỉ vì máy mới. Muốn provision source có mạng, runner bỏ `--offline` sẽ fetch archive tại pinned base commit rồi cache; **đó vẫn là chạy retrieval mới**, cần được mở lại khi benchmark đang dừng. Team có thể chuyển cache bundle kèm hash cho retrieval offline, nhưng phải verify provenance/raw bytes, không normalize để né guards.

Nếu manifest/gold không có sau clone, chỉ regenerate khi leader cho phép và giữ revision/split/count/min-source-files. Lệnh sau là hướng dẫn setup **có điều kiện**, không dùng để rewrite input25 hiện tại:

```powershell
# CHỈ CHẠY KHI LEADER DUYỆT regenerate dữ liệu thiếu; cần mạng.
# Không sử dụng heldout để debug/tune và không chạy nếu đang giữ manifest chuẩn.
& $python scripts\prepare_manifest.py . --count 25 --split dev --min-source-files 2 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
$LASTEXITCODE
```

**Không chạy lại pilot/dev25/resume chỉ vì muốn thử các commands này.** Pilot3 đã đạt; dev25 failures bị dừng. Khi được duyệt measurements mới, lệnh profile cố định tham khảo là:

```powershell
# CHỈ KHI ĐƯỢC MỞ LẠI BENCHMARK:runmới, giữ profile/no-Jedi/counter/budget.
# --offline đòi sourcecache đã có; --rebuild-trees bảo toàn oldcache và tăng disk.
& $python scripts\run_graph_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --task-timeout-seconds 300 --offline --rebuild-trees --no-jedi
$LASTEXITCODE
```

Runner in `run: ...` từ đầu và status từng task; đọc `complete/status` cuối, không đoán từ UI im lặng. Source fingerprint đã đổi sau host fix/test mới, nên **resume run07/10 cũ trên checkout mới bị guard từ chối là đúng**. Resume khi identity thực sự giống sẽ tạo run mới, copy verified successes và chạy failures bằng attempts mới; hiện retry failures là việc người dùng không cho tự làm. Không sửa recorded identity hoặc tăng timeout để né error.

Nếu cần compare run mới đã được duyệt, dùng automatic selectors và recovery copy đã kiểm hash trong [hướng dẫn vận hành](m5_m6_retrieval_evaluation.md), sau đó `compare_graph_vs_bm25.py`. Lệnh chỉ compare không rerun source retrieval nhưng vẫn tạo evidence/report mới. Không dùng hai run BM25/Graph mới nhất tùy tiện chỉ vì cùng budget mà khác population/protocol/counter.

### 11.11. Agent thật là một flow khác, không dùng command hệ thống cũ

Repo này có CLI `vgar run/chat` và workflow LangGraph. Không copy lệnh `qualify_repair_smoke.py`, preflight/budgetprofile từ `vgar_mcp_mvp` cũ vào VGAR vì không phải entrypoints của repo này.

Khi nhóm mở riêng task inference và có model/runtime phù hợp, ví dụ entrypoint có sẵn là:

```powershell
# THAM KHẢO CHO TASK INFERENCE RIÊNG: có thể load Qwen weights, tốn RAM/VRAM/thời gian.
# Không cần lệnh này để nghiệm thu code/retrieval W3–6 ở trên.
$env:VGAR_TOKENIZER_MANIFEST = (Resolve-Path -LiteralPath 'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json').Path
& $python -m vgar.cli run 'Fix demo.answer so the failing test passes.' --repo tests/fixtures/m2/failing_repo --selector tests/test_demo.py::test_answer --keep
$LASTEXITCODE
```

CLI có selector mới chạy independent pytest sau agent. Không selector, exit0 có thể không xác minh repair. Source copy mới được bind đúng, nhưng model tool-use/quality và stale graph sau patch vẫn cần đo riêng; không hứa lệnh trên chắc chắn repair PASS hoặc GPU đủ. Không chạy trên repo không tin cậy vì lease không cách ly OS.

### 11.12. Khi test fail: gửi gì cho leader?

Gửi evidence JSON/path, task_id/run_id, exact argv, cwd/interpreter, exit/status/phase, stdout/stderr/trace, source/config/tokenizer identities và reproduction nhỏ nếu có. Nếu cần nhiều log, gửi attempt folder hoặc tổng bundle, không chỉ screenshot progress. Kiểm secrets trong raw logs trước chia sẻ. Không delete failures, đổi gold, thay reported hash hoặc tự claim PASS từ stdout của model.

Mỗi loại run có shape khác:

- M2 recorder/baseline: nested `$result.test_result.exit_code/duration_ms/case_counts`.
- Graph run: top `exit_code/duration_seconds`, `task_results`, config/selected tasks.
- Comparison: `coverage/paired_tasks/summaries/per_task`, không `task_results` như Graph.
- MCP context smoke: `calls`, context/counter artifacts và hashes/inference, không pytest cases.

Đọc sai shape thường dẫn đến thấy `{}` hoặc cột trống, không có nghĩa artifact không có dữ liệu.

## 12. Thuật ngữ và câu hỏi thường gặp

| Thuật ngữ | Giải thích trong VGAR |
|---|---|
| Node / edge | Entity của code và quan hệ; ví dụ Function/Method, CONTAINS/IMPORTS/CALLS/INHERITS |
| Source span / range | Vị trí dòng/cột/byte của entity; dùng để lấy snippet và mapgold |
| Qualified name | Tên có namespace như `package.Class.method`; duplicate definitions cần occurrence identity thêm, không chỉ tên |
| Snapshot / graph_version | Graph ứng với một trạng thái source; không schema version hoặc version protocol MCP |
| Inventory | Danh sách file/source hashes mà snapshot biết, bao gồm file extractionfailed để retriever không hiểu nhầm source mới |
| Transaction / rollback | Thay đổi extractionfile là một đơn vị; lỗi phải hoàn nguyên đủindexes/nodes/edges, không state nửa vời |
| Anchor / grounding | Điểm code ứng viên ban đầu từ issue/test/path/symbol. Không phải tất cả anchors đều liên quan đúng yêu cầu |
| Task overlay / trace | Layer Issue/Test/MENTIONS/REPRODUCES gắn task với snapshot, không sửa base graph |
| Task handle | ID bất biến được lưu trong SQLite để session sau biết chính xác issue/overlay, không dùng biến toàn cục “issue cuối cùng” |
| Stateless client | Mỗi call có thể mở session mới; lưu task context ở server/store/handle, không dựa vào bộ nhớ session |
| Context / snippet | Đoạn code được đưa cho consumer; metadata để biết file/symbol/rationale/confidence |
| Token budget | Giới hạn token của snippet theo counter policy; 8000 không bao gồm toàn LLM prompt vì prompt/tools/history cần thêm |
| Confidence / provenance | Mức tin cậy heuristic của cạnh và phương pháp tạo cạnh; không phải xác suất đã được hiệu chuẩn nếu chưa có nghiên cứu/calibration |
| BM25 | Tìm code theo từ trong issue/code; cân bằng tần suất từ, độ hiếm và chiều dài đoạn; không LLM |
| Gold | Nhãn proxy từ developer patch: file/function bị sửa; chỉ evaluator dùng, không cung cấp cho agent/ranker |
| Multi-file | Developer patch sửa ít nhất hai source Python files theo selection policy. Không đồng nghĩa mỗi task phải có đúng hai calls/tests |
| Recall@k | Tỷ lệ gold entities hợp lệ tìm được trong k kết quả đầu, sau dedup ở đúng level |
| MRR | Trung bình nghịch đảo thứ hạng gold đầu tiên: rank1=1, rank4=0,25; không hit=0, unscorable có thể N/A |
| Packed coverage | Gold source thực sự nằm trong context đã pack theo budget; khác full-rank recall |
| Oracle-assisted / F2P | Dùng FAIL_TO_PASS benchmark metadata; không phải actual test failure đã chạy tại base |
| Bootstrap CI / paired | Lấy mẫu lại cùng task pairs để ước lượng độ bất định của chênh lệch; ở đây chỉ trên 19 valid pairs |
| Survivor / selection bias | Chỉ chấm được tasks thành công; sáu lỗi thiếu metrics và không có Sympy trong subset. Không suy từ 19 sang 25 một cách vô điều kiện |
| Cache pair / hash guard | Graph data + metadata phải khớp identity/raw hash; stale/corruption bị từ chối thay vì gán nhãn ready |
| LF / CRLF | Hai cách biểu diễn xuống dòng; nhìn nội dung giống nhưng bytes/SHA256 khác. Git checkout có thể chuyển đổi; recovery phải giữ đúng bytes |
| Resume fork | Run mới nối tiếp, giữ run cũ bất biến; không sửa failed artifact thành PASS |
| Lease / capability | Host cấp quyền root bản copy cụ thể cho tools; không OS sandbox/container |
| Baseline | Kết quả trước patch để đối chiếu; chạy baseline không tự repair |
| Regression / RED→GREEN | Test bắt bug trước fix phải fail; sau fix pass; không giả test output |
| Pytest selector / node ID | `tests/`=cả thư mục; `tests/a.py`=file; `tests/a.py::test_x`=test cụ thể; `::Class::method` cho class tests |
| PASS/FAIL/ERROR/NOT_RUN | Verdict tool/test: pass assertions; fail assertion/verification; không thực hiện được; chưa chạy/skip. Không coi ERROR là lỗi accuracy được chấm |
| SUCCEEDED/PARTIAL_FAILURE | Run-level retrieval status, khác vocabulary frozen MCP; run kết thúc không đồng nghĩa toàn task PASS |
| EvidenceBundle | Bằng chứng có cấu trúc về test/patch_applied/hash/verification của M2; run JSON summary không tự động là EvidenceBundle |
| JUnit | XML test report pytest tạo, được parse thành cases trong JSON portable; không cần copy tay XML tạm |
| RSS / VRAM | RAM resident của process(es) / memory GPU. Retrieval RSS không phải VRAM |
| ADR / DoD / sign-off | Architecture Decision Record / gate hoàn thành / owner review xác nhận; agent không ký thay nhóm |

**“Suite pass rồi sao W6 chưa hoàn thành?”** Vì suite chỉ chứng minh các assertions trong tests. Benchmark vẫn 19 pairs dưới 20, sáu failures còn mở, owners chưa ký. Không lấy số 359 thay cho 25 task retrieval.

**“No-Jedi là graph giả hay fallback LLM?”** Không. Vẫn Tree-sitter, resolver nội bộ và graph traversal. Chỉ tắt lớp Jedi static fallback; edge coverage/chất lượng có thể thay đổi, nên được ghi rõ profile.

**“Tại sao code fine-tune/GPU không được fix?”** Scope hiện tại tuần 3–6 là graph/retrieval/transport/evidence. Schema/rename permission/contract bugs không được sửa bằng training, và đợt này chưa đo model inference.

**“Có thể clone là chạy ngay?”** Code thì clone được; dependencies/tokenizer/source archives/approved data cần provision. Không push cache không ngăn logic code chạy, nhưng offline benchmark thiếu cache vẫn fail. Không thể hứa không lỗi trên mọi máy.

**“Report partial có thể dùng báo cáo đồ án không?”** Có thể trình bày trung thực kết quả sơ bộ/coverage/bias/failure taxonomy; không gọi là benchmark hoàn thành hoặc Graph đã cải thiện. Giữ manifest/arms/scorer pin để so sánh tiếp công bằng.

## 13. Checklist bàn giao và nguồn đối chiếu

- [x] Task/phạm vi và các ranh giới trước/sau sửa được giải thích bằng code/evidence.
- [x] Có ledger/test evidence/metric report/manual audit/current PROGRESS.
- [x] Có hướng dẫn cài lần đầu/mỗi phiên, selectors/multi-file/full suite và tự tìm output.
- [x] Giữ cả failures/RED/legacy evidence; không overwrite source cache/recorded hash để làm xanh.
- [ ] Paired benchmark đủ ngưỡng 20–30/mục tiêu 25: **hiện 19**, không tick.
- [ ] Sáu failures và Jedi/performance issues được điều tra/fix theo đúng approvals; hiện đã dừng.
- [ ] Owners M1/M2/M3 review identities/task_handle/scoring/source binding và ký thật.
- [ ] Environment readiness 50–100/smoke3: **bị loại trừ**, không PASS.
- [ ] Commit/push khi người dùng yêu cầu; không tự publish trong đợt viết tài liệu.

### Nguồn nội bộ ưu tiên

1. [Project plan 16 tuần](../../New_task/project_plan_16_weeks.md) và [Contract Freeze](../../New_task/VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md): yêu cầu/phạm vi, không phải execution evidence.
2. [Audit trước sửa](reviews/2026-10-06-review-vgar-week-1-6.md): F01–F12/R01–R06, probes và nguyên nhân đã tái hiện.
3. [Kế hoạch fix đã duyệt](superpowers/plans/2026-10-06-fix-vgar-integration-week-1-6.md): milestones/gates/approvals.
4. [PROGRESS](../PROGRESS.md): trạng thái hiện tại, RED/GREEN/full-run paths và checkpoint khôi phục.
5. [Báo cáo task chưa hoàn thành](BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md): nguyên nhân chưa đóng và quy tắc dừng task.
6. [Completion W5–6](w5_w6_completion.md), [W3–4](w3_w4_completion.md): task mapping và cập nhật cho checkpoint lịch sử.
7. [Dev25 report](reviews/2026-10-07-dev25-no-jedi-results.md), [manual10](reviews/2026-10-07-manual-retrieval-audit-10.md), [affected self-review](reviews/2026-10-07-affected-files-review-w3-w6.md): measurements/diễn giải/giới hạn.
8. [Hướng dẫn retrieval](m5_m6_retrieval_evaluation.md), [MCP contract](mcp_tool_contract.md), [context contract](context_payload_contract.md), [evidence schema](evidence_bundle_schema.md), [verification design](verification_design.md).
9. [ADR identities](adr/2026-10-06-graph-transactions-and-definition-identities.md), [ADR task handles](adr/2026-10-06-stateless-task-handles-and-context-boundary.md).

**Tóm tắt để nói với leader:** “Đã sửa các ranh giới graph/source/cache/scorer/MCP/workspace và thêm evidence/regressions, giữ kiến trúc hiện tại. Suite cuối 359 pass/4 skip, no-Jedi pilot 3/3. Dev25 chỉ 19 success/6 errors, Graph kém BM25 trên subset 19, nên chưa đóng DoD; đã lưu report/CI/manual audit/failures và chờ quyết định/sign-off. Chưa chạy model repair SWE-bench, environment bị loại trừ, không commit/push.”
