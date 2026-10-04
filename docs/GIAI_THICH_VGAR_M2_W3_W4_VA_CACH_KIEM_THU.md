# Giải thích toàn bộ phần M2 tuần 3–4 trong VGAR và cách tự kiểm thử

Tài liệu này mô tả **trạng thái code tại ngày 30/09/2026**, không mô tả một hệ thống sửa lỗi hoàn chỉnh trong tương lai. Đường dẫn gốc trên máy hiện tại là `D:\Project\CAPSTONES\VGAR`. Mọi đường dẫn không có ổ đĩa bên dưới đều tính từ thư mục này.

## 0. Task M2 — Repair & Verification của tuần 3–4 thực sự yêu cầu gì?

### 0.1 Mục đích và ranh giới của task

Nguồn yêu cầu là mục **“Tuần 3–4 → M2 — Repair & Verification”** trong `D:\Project\CAPSTONES\New_task\project_plan_16_weeks.md`. Kế hoạch ghi bốn đầu việc: (1) thiết lập sandbox/worktree để chạy patch an toàn, (2) viết test runner wrapper cho pytest, (3) thu thập kết quả test **baseline** gồm command, stdout/stderr, exit code, duration, và (4) hoàn thiện schema `EvidenceBundle` cùng writer JSON. Deliverable được ghi rõ là **`run_tests` wrapper và baseline evidence JSON**. Tài liệu contract bổ sung `D:\Project\CAPSTONES\New_task\VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md` mô tả dạng dữ liệu mà M2 dự kiến đưa cho M3, không tự nó chứng minh code đã triển khai.

**Baseline là gì?** Đây là kết quả chạy test trên mã nguồn **trước khi có bản sửa**. Nếu test đang fail từ trước, sau này verifier phải phân biệt lỗi cũ với lỗi do patch gây ra; nếu test đang pass, sau patch không nên làm nó fail. Bởi vậy M2 tuần 3–4 cần ghi được kết quả ban đầu có thể truy vết, chứ chưa cần chứng minh coding agent sửa lỗi thành công. Input tối thiểu là **đường dẫn Python repository**, **pytest selector** (ví dụ `tests/test_auth.py`), **task ID** và **timeout**. Output chính là một file JSON cho mỗi lượt chạy, cùng trạng thái `PASS`/`FAIL`/`ERROR` và thông tin đủ để xem test đã chạy gì, ở đâu, trong bao lâu.

**Vì sao phải tách bản sao?** Chạy pytest có thể tạo cache, ghi file hoặc kích hoạt code của repository. M2 cần tránh việc test làm thay đổi **nguồn đầu vào**; vì vậy baseline được chạy trên bản sao tạm, rồi hash nguồn được so trước/sau. Cơ chế này chỉ cách ly file nguồn theo chính sách copy; nó **không phải container/OS sandbox** cho code không tin cậy. Trong kế hoạch, `apply_patch` và repair loop thực sự nằm ở tuần 7–8. Do đó cụm “để chạy patch an toàn” của checklist tuần 3–4 hiện mới được đáp ứng ở **phần chuẩn bị workspace**, chưa ở phần áp patch.

Để hiểu đúng phạm vi, hãy phân biệt ba tầng:

1. **M2 tuần 3–4:** tạo workspace tạm → chạy pytest trước patch → ghi baseline evidence.
2. **M2 các tuần sau:** nhận diff/patch → kiểm tra và áp vào workspace → chạy lại tests/type/lint/API/structure → đối chiếu baseline và xuất verification evidence sau patch.
3. **Hệ thống VGAR hoàn chỉnh:** M1 cung cấp graph/context, M3 đưa M2 vào MCP/agent loop và đánh giá benchmark. Hai tầng sau **không được suy ra** từ một lượt baseline `PASS`.

### 0.2 M2 đã thực hiện task bằng cách nào?

Theo thứ tự dữ liệu đi qua code hiện tại:

1. `scripts/run_m2_baseline.py` nhận repository, selector, task ID và timeout từ CLI; gọi `src/vgar/repair/baseline.py`.
2. `src/vgar/repair/workspace.py` duyệt file hợp lệ, tính SHA-256 của nguồn, kiểm path/giới hạn kích thước rồi copy vào thư mục `vgar-m2-...` tạm. Nó không thực hiện Git worktree và không áp patch.
3. `src/vgar/repair/evidence_writer.py` tạo trước một record JSON `complete=false`. Nếu tiến trình dừng giữa chừng, file còn thể hiện lượt chưa hoàn tất, không bị hiểu thành `PASS`.
4. `src/vgar/repair/test_runner.py` kiểm selector, chạy `sys.executable -m pytest -q` trong bản sao với timeout; ghi command/argv, stdout, stderr, exit code, duration, test cases và lý do lỗi nếu có.
5. `baseline.py` so hash nguồn sau test, tạo `VerificationResult` và `EvidenceBundle`; vì chưa có patch, `patch_applied=false`, còn type/lint/API/structure là `NOT_RUN`. Writer chốt **cùng file JSON** với `complete=true`; workspace tạm được dọn.

`scripts/record_m2_test.py` là một đường chạy **khác**: nó dùng cùng runner/writer để chạy test phát triển của **chính VGAR** (`tests/m2` hoặc `tests`), ngay trong cây VGAR, không tạo bản sao. Nó giúp lưu bằng chứng mỗi lần kiểm thử phần triển khai M2; **không** thay thế `run_m2_baseline.py` khi muốn kiểm tra một repository đầu vào.

### 0.3 Bảng đối chiếu từng yêu cầu, mức hoàn thành và bằng chứng

Các đường dẫn trong bảng đều nằm **trong `D:\Project\CAPSTONES\VGAR\`** nếu không ghi đầy đủ ổ đĩa. “Đã chạy thử” nghĩa là có test hoặc JSON thực tế; không có nghĩa contract đã được cả nhóm freeze hay hệ thống repair end-to-end đã đạt yêu cầu.

| Nội dung từ kế hoạch tuần 3–4                                         | Mức hiện tại                                                                                                                                         | Code/tài liệu nằm ở đâu?                                                                                                                                                                                                                                                                                                               | Output thực tế nằm ở đâu, chứa gì?                                                                                                                                                                                                                                                                                                                        | Tác dụng và giới hạn                                                                                                                                                                                         |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Sandbox/worktree để chạy patch an toàn**                            | **Một phần:** đã có disposable **file-copy workspace** cho baseline; **chưa có** `apply_patch`, Git worktree hay container/OS sandbox.               | `src/vgar/repair/workspace.py` (`create_workspace`, `WorkspaceLease`, `fingerprint_source`); được gọi từ `src/vgar/repair/baseline.py`. Test: `tests/m2/test_workspace.py`.                                                                                                                                                            | Bản sao tạm dạng`D:\Project\CAPSTONES\m2-temp\vgar-m2-...` (hoặc dưới `VGAR_M2_TEMP_ROOT`), **được xóa sau lượt chạy**. JSON giữ `source_repo`, `worktree_id`, `source_hash_before/after`; không có file patch sau sửa.                                                                                                                                   | Bảo vệ nguồn gốc khỏi thao tác test trên**bản sao**; xác nhận các file nằm trong chính sách fingerprint không đổi. Không an toàn để chạy test từ repository không tin cậy và chưa đáp ứng phần “chạy patch”. |
| **Test runner wrapper cho pytest**                                    | **Đã triển khai và có test** cho phạm vi chạy pytest cơ bản, lỗi, timeout, selector và output limit. Chưa có relevant-test selection dựa trên graph. | `src/vgar/repair/test_runner.py` (`run_tests`); contract `src/vgar/contracts/evidence.py` (`TestRunResult`, `TestCaseResult`); test `tests/m2/test_test_runner.py`. CLI gọi gián tiếp: `scripts/run_m2_baseline.py` hoặc `scripts/record_m2_test.py`.                                                                                  | Một`TestRunResult` được nhúng vào `artifacts/m2/test-runs/<timestamp>-<run_id>.json`: `status`, `command`, `argv`, `exit_code`, `duration_ms`, `stdout`, `stderr`, `cases`, `case_counts`, `reason`, `complete`, byte counts. JUnit XML chỉ là file **tạm** để lấy kết quả từng test và bị xóa.                                                           | Chạy pytest với cùng một giao diện, biết test nào pass/fail/skip, chặn timeout và ghi nguyên nhân lỗi; bản thân nó**không sinh/sửa code**.                                                                   |
| **Test result baseline: command, stdout/stderr, exit code, duration** | **Đã triển khai và chạy thử** trên fixture pass lẫn fail. Baseline hiện chỉ là **trước patch**; chưa có phép so sánh sau patch.                      | `src/vgar/repair/baseline.py` (`run_baseline`) điều phối; `src/vgar/repair/test_runner.py` đo/thu kết quả; `scripts/run_m2_baseline.py` là lệnh chạy. Test: `tests/m2/test_baseline.py`.                                                                                                                                               | Ví dụ PASS:`artifacts/m2/test-runs/20260930T094926633646Z-bca59c6e5ce64062a3ee9ac5a4c2cc20.json` có `command`, `stdout` báo `1 passed`, `stderr` rỗng, `exit_code=0`, `duration_ms=594`, hash trước/sau bằng nhau. Một JSON FAIL có chủ đích được nêu ở mục 9.                                                                                            | Tạo mốc khách quan để so sánh với patch về sau; không suy ra rằng lỗi đã được sửa chỉ vì baseline test pass.`duration_ms` đo subprocess pytest, không phải toàn bộ thời gian copy/hash/ghi JSON.             |
| **Schema EvidenceBundle và JSON writer**                              | **Đã có model + writer chạy được; contract liên nhóm còn cần M3 review/freeze.** Các check type/lint/API/structural mới là field, chưa có executor.  | `src/vgar/contracts/repair.py` (`Status`, `FailureReason`, `PatchApplyResult`); `src/vgar/contracts/evidence.py` (`VerificationResult`, `EvidenceBundle`); `src/vgar/repair/evidence_writer.py` (`begin_run`, `finish_run`); `docs/evidence_bundle_schema.md`. Test: `tests/m2/test_contracts.py`, `tests/m2/test_evidence_writer.py`. | `artifacts/m2/test-runs/*.json`, **mỗi lượt một file** tên timestamp+UUID. Record có run/task ID, thời điểm, repo/hash, môi trường, `test_result`, và baseline có `evidence_bundle.verification` với `patch_applied=false`, `tests=<TestRunResult>`, các check khác `NOT_RUN`. Writer ghi record pending trước và cập nhật final bằng file tạm + replace. | Giữ bằng chứng có cấu trúc để thành viên khác và evaluation đọc lại;`PatchApplyResult` mới là **kiểu dữ liệu**, không phải chức năng áp patch. JSON hiện có thể cần điều chỉnh sau khi nhóm chốt contract.   |

**Kết luận theo deliverable tuần 3–4:** Có `run_tests` wrapper và baseline evidence JSON thực tế. Phần còn thiếu quan trọng là **áp patch trong workspace** và **sandbox bảo mật**; vì vậy không đánh dấu toàn bộ câu “sandbox/worktree để chạy patch an toàn” là hoàn thành. Mục 8–10 bên dưới chỉ cách đọc output và tự chạy lại từng phần.

## 1. Đọc nhanh: tôi đã làm gì và chưa làm gì?

Tôi đã bổ sung hạ tầng **M2 — Repair & Verification, tuần 3–4** vào dự án `VGAR` đã có M1 và M3. Hạ tầng đó làm được bốn việc chính:

1. Tạo một **bản sao tạm** của repository cần kiểm tra, để lượt baseline không sửa file nguồn gốc.
2. Chạy `pytest` trong bản sao đó với timeout, ghi stdout/stderr, mã thoát, thời gian chạy và kết quả từng test.
3. Đóng gói kết quả thành `EvidenceBundle` và lưu **một file JSON riêng cho mỗi lượt chạy**.
4. Kiểm tra hash file nguồn trước/sau để phát hiện nếu nguồn đầu vào bị thay đổi.

Tôi **chưa** làm bộ sinh patch, áp dụng patch, vòng lặp coding agent, kiểm tra API/kiến trúc thật, hay chấm SWE-bench. `PASS` của baseline chỉ nói rằng **test hiện tại trên bản gốc đã chạy qua**; không có nghĩa agent đã sửa được lỗi. Những phần này thuộc milestone sau theo `New_task/project_plan_16_weeks.md`.

## 2. Tôi dựa vào những gì?

- `New_task/project_plan_16_weeks.md`, mục **M2 — Repair & Verification của tuần 3–4**, yêu cầu: workspace/sandbox cho patch, wrapper `pytest`, thu thập `command`, `stdout/stderr`, `exit code`, `duration`, và evidence JSON. Đây là phạm vi công việc chính.
- `New_task/VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md`, mục Repair/Verification Contract, đưa ra các kiểu `PatchApplyResult`, `TestRunResult`, `VerificationResult`/`EvidenceBundle`, `FailureReason` và trạng thái `PASS/FAIL/ERROR/NOT_RUN`. Ví dụ trong đó là **bản nháp contract**, nên nhóm/M3 vẫn cần review tên field trước khi coi là giao diện cố định.
- `New_task/2026-09-30-m2-repair-verification-w3-w4-implementation-plan.md` là implementation plan đã được bạn duyệt. File này chia việc thành Task 0–6 và quy định phát triển trên bản sao, chỉ chuyển file M2 đã kiểm tra vào `VGAR`.
- Code thực tế trong `VGAR/src/vgar/graph/` (M1), `VGAR/src/vgar/mcp/` và `VGAR/src/vgar/agents/` (M3). Tôi **không** lấy `M1_week_3+4` làm nguồn tích hợp và **không** sửa dự án cũ `vgar_mcp_mvp`.

Trước khi tích hợp, tôi tạo `D:\Project\CAPSTONES\M2_week_3+4\VGAR_candidate` để phát triển, ghi hash của 107 file không phải sản phẩm sinh tự động vào `M2_week_3+4/artifacts/input-manifest.json`, đối chiếu lại thấy **0 file gốc thay đổi**, rồi chuyển đúng 24 đường dẫn có trong `M2_week_3+4/artifacts/transfer-manifest.json`. Bản sao trước khi chuyển và bản dự phòng của các file bị sửa vẫn nằm trong `M2_week_3+4/` để đối chiếu. `VGAR` hiện tại không có thư mục `.git`, nên manifest hash được dùng để kiểm tra xung đột; đây **không phải** một Git commit.

## 3. Bản đồ thư mục: cái gì ở đâu?

```text
D:\Project\CAPSTONES\
├─ New_task\                         Kế hoạch 16 tuần, contract draft, implementation plan
├─ M2_week_3+4\
│  ├─ VGAR_candidate\                Bản sao phát triển/kiểm thử trước tích hợp
│  ├─ artifacts\                     Manifest, transcript bootstrap, bản dự phòng file cũ
│  └─ PROGRESS.md                    Checkpoint các việc đã/chưa hoàn thành
└─ VGAR\                             Dự án tích hợp hiện tại
   ├─ configs\                      Cấu hình model, agent, MCP, evaluation
   ├─ src\vgar\contracts\          Kiểu dữ liệu dùng giữa các module
   ├─ src\vgar\graph\              M1: xây dựng/truy vấn đồ thị code
   ├─ src\vgar\repair\             M2: workspace, pytest, evidence, baseline
   ├─ src\vgar\mcp\                M3: MCP client và servers
   ├─ src\vgar\agents\             M3: cấu trúc agent/LangGraph
   ├─ src\vgar\models\             M3: tích hợp model Hugging Face
   ├─ scripts\                      Các lệnh chạy thủ công và smoke test
   ├─ tests\                        Unit/integration tests và fixture nhỏ
   ├─ artifacts\sample_graph.*      Graph mẫu M1 (JSON và SQLite)
   ├─ artifacts\m2\test-runs\      Mỗi lượt test M2 lưu một JSON
   ├─ logs\                         Audit log MCP khi gọi graph tools
   ├─ docs\                         Hướng dẫn, contract và handoff
   ├─ pyproject.toml                 Dependencies và cấu hình pytest
   └─ README.md                      Hướng dẫn ngắn; phần M1 cũ còn đường dẫn lịch sử
```

`M2_week_3+4/VGAR_candidate` là nơi tôi viết/test trước; **`VGAR` mới là bản tích hợp cần nhóm tiếp tục dùng**. Không cần chạy đồng thời cả hai. `VGAR/artifacts/m2/test-runs/` là dữ liệu kết quả, không phải source code. `VGAR/m2-temp` cũng không phải thư mục cần tìm: mặc định script đặt workspace tạm ở **thư mục cha của `VGAR`**, ví dụ `D:\Project\CAPSTONES\m2-temp`, rồi dọn bản sao sau khi chạy.

## 4. M1 hiện có gì? M2 dựa vào M1 như thế nào?

M1 là tầng **hiểu cấu trúc repository Python**. Nó không tự sửa code. Các file chính:

| File/thư mục                                               | Vai trò hiện tại                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/vgar/graph/builder.py`                                | `PythonGraphBuilder` quét file `.py`, dùng Tree-sitter tạo node `Repository`, `File`, `Module`, `Class`, `Function`, `Method`, `Test`, `Import`, `CallSite`; nối các quan hệ như chứa, import, kế thừa và lời gọi. Tạo `graph_version` dựa trên hash nội dung/revision rồi kiểm tra document bằng schema. |
| `src/vgar/graph/jedi_resolver.py`                          | Dùng Jedi hỗ trợ giải quyết một số call/reference mà phân tích cú pháp đơn thuần chưa xác định được. Jedi là dependency cần có nếu chạy đủ test M1.                                                                                                                                                       |
| `src/vgar/graph/sqlite_store.py`                           | Lưu document graph vào SQLite và truy vấn symbol, callers/callees, node, subgraph, repository summary.                                                                                                                                                                                                    |
| `src/vgar/graph/sqlite_service.py`                         | Biến dữ liệu SQLite thành các DTO dùng chung trong`vgar.contracts.graph`.                                                                                                                                                                                                                                 |
| `src/vgar/graph/port.py`                                   | `GraphService` protocol: giao diện M3 gọi M1, không buộc M3 biết cách SQLite được cài đặt.                                                                                                                                                                                                                |
| `src/vgar/graph/factory.py`                                | Chọn`demo` mặc định hoặc `sqlite` qua `VGAR_GRAPH_BACKEND`; SQLite cần `VGAR_GRAPH_DATABASE`.                                                                                                                                                                                                             |
| `src/vgar/graph/demo_service.py`                           | Graph demo để thử MCP khi chưa chọn database thật. Không nên nhầm kết quả demo với graph của repo bạn đưa vào.                                                                                                                                                                                            |
| `src/vgar/graph/context.py`                                | Kiểu`ContextPayload`/`ContextItem` và kiểm tra path, token budget. Chưa đồng nghĩa với full graph-guided retrieval theo task.                                                                                                                                                                             |
| `scripts/build_graph.py`                                   | CLI tạo graph JSON từ một Python repo.                                                                                                                                                                                                                                                                    |
| `scripts/load_graph_fixture.py`                            | CLI nạp graph JSON vào SQLite.                                                                                                                                                                                                                                                                            |
| `artifacts/sample_graph.json`, `artifacts/sample_graph.db` | Dữ liệu graph mẫu để thử query/MCP. Đây là fixture M1 có sẵn,**không phải** kết quả M2.                                                                                                                                                                                                                   |

Các contract chung liên quan là `src/vgar/contracts/graph.py`, `context.py`, `schema.py`, `error.py`. M1/M3 dùng chúng để có một dạng dữ liệu chung; M2 W3–W4 **chưa gọi graph retrieval hoặc impact graph**. Nói chính xác: tôi lấy **dự án VGAR đã tích hợp M1+M3 làm nền**, dùng `tests/fixtures/sample_repo` làm đầu vào baseline, và giữ nguyên khả năng test/query của M1; tôi **chưa** lấy graph M1 làm thuật toán chọn test hoặc xác minh patch.

## 5. M3 hiện có gì? M2 đã kết nối vào M3 chưa?

M3 hiện giữ tầng MCP/agent/model. Các phần chính:

| File/thư mục                                                                       | Trạng thái và vai trò                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/vgar/mcp/client.py`, `configs/mcp.yaml`                                       | Tạo MCP client qua`stdio`, cấu hình ba server `graph`, `repository`, `execution`. Tên tool được thêm prefix theo server.                                                                                                                                                                                                              |
| `src/vgar/mcp/servers/graph_server.py`                                             | Expose các tool`search_symbols`, `get_callers`, `get_callees` (client thấy tên có prefix `graph_`) và resources `vgar://repo/summary`, `vgar://graph/node/{id}`, `vgar://graph/subgraph/{id}`. Nó gọi M1 thông qua graph service. Tham số `depth` ở callers/callees hiện được giữ cho giai đoạn sau; code hiện gọi quan hệ trực tiếp. |
| `src/vgar/mcp/servers/repository_server.py`                                        | Có `health()`, `read_file(repo_path, path)` và `apply_patch(repo_path, path, old_text, new_text)` (một thay thế văn bản chính xác, trả `patch_diff`; từ chối nếu `old_text` không có hoặc không duy nhất). Đường dẫn bị chặn thoát khỏi workspace. Client thấy tên có prefix `repository_`. |
| `src/vgar/mcp/servers/execution_server.py`                                         | Có `health()` và `run_pytest(repo_path, selector, timeout_seconds)`: chạy đúng một selector pytest trong workspace tạm (client thấy `execution_run_pytest`). Server này có đường chạy pytest riêng bằng `subprocess`, **không** gọi `repair/test_runner.py` của M2, và chưa expose `verify_patch`. |
| `src/vgar/mcp/audit.py`                                                            | Ghi JSONL audit cho các lời gọi/resource graph, mặc định`logs/mcp_audit.jsonl`. Audit này khác JSON kết quả pytest M2.                                                                                                                                                                                                                |
| `src/vgar/mcp/registry.py`                                                         | Kiểm tra sự hiện diện của các graph tools bắt buộc.                                                                                                                                                                                                                                                                                   |
| `src/vgar/agents/workflow.py`, `state.py`, `routes.py`                             | LangGraph outer workflow và state. Luồng hiện tại: `initialize → prepare_workspace → repair → verify → finalize` (hoặc `failed`). Nếu `verify` chưa PASS và `attempts < max_iterations` thì quay lại `repair`. Chỉ node `repair` gọi model; các node còn lại là code thường. `routes.py` có `route_after_repair` và `route_after_verify`. |
| `src/vgar/agents/nodes/` (`initialize`, `prepare`, `repair`, `verify`, `finalize`) | `initialize` kiểm tra input; `prepare` index repo vào `graph.db` tạm và copy sang workspace tạm (`repair/workspace.py`); `repair` chạy agent, các lần retry kèm phản hồi từ lần verify trước; `verify` chạy pytest độc lập bằng `repair/test_runner.py` và tạo evidence (typecheck/lint/API/structural vẫn `NOT_RUN`); `finalize` kiểm tra repo gốc không bị đổi. |
| `src/vgar/agents/core.py`                                                          | Tạo một LangChain agent (`create_agent`) từ MCP tools và model Hugging Face; là agent bên trong node `repair` và cũng được `vgar run`/`chat` dùng trực tiếp. `agent.max_tool_calls` được cưỡng chế ở đây (`ToolCallLimitMiddleware`, tính cho mỗi lượt chạy agent). **Chưa** phải repair loop hoàn chỉnh: chưa có graph retrieval theo task, impact analysis, typecheck/lint hay API check. |
| `src/vgar/models/huggingface/hf_model.py`, `local_hf_chat_model.py`                | Load tokenizer/model Hugging Face và cung cấp`LocalChatModel`. `configs/model.yaml` đang ghi Qwen3-4B-Instruct-2507. Chạy smoke model thật có thể tải weights và tốn RAM/GPU; các lệnh M2 trong tài liệu này **không load model**.                                                                                                    |
| `scripts/smoke_mcp.py`, `smoke_w3_w4.py`, `smoke_workflow.py`, `smoke_hf_agent.py` | Các smoke script của M3; mỗi script kiểm một ranh giới khác nhau.`smoke_workflow.py` chỉ in sơ đồ workflow (kiểm tra workflow compile được), không chạy repair.                                                                                                                                                                                          |

Placeholder còn lại: `scripts/run_agent.py` vẫn rỗng. Trước đây `src/vgar/cli.py`, `src/vgar/mcp/schemas.py` và `src/vgar/agents/nodes/verify.py` cũng rỗng nhưng nay đã có nội dung; `agents/nodes/model.py`, `agents/nodes/observe.py` và `agents/graph.py` đã bị xóa (agent chỉ còn một đường dựng là `agents/core.py`). `src/vgar/models/factory.py` định nghĩa `create_core_model`, nơi duy nhất biến `ModelSettings` thành chat model (torch/transformers chỉ import khi cần). `configs/*.yaml` không được code đọc (xem README), và `configs/evaluation.yaml` nêu ý định lưu artifact/benchmark nhưng không phải bằng chứng SWE-bench đã được triển khai.

**Ranh giới tích hợp hiện tại:** M1 graph ↔ M3 graph MCP đã nối. Workflow LangGraph đã gọi code M2: `prepare` dùng `repair/workspace.py` và `verify` dùng `repair/test_runner.py`. Tuy nhiên tool MCP `execution_run_pytest` mà agent thấy có đường chạy pytest riêng, nên kết quả agent tự thấy và kết quả verify độc lập đến từ hai cài đặt khác nhau. Trước khi hợp nhất, M3 cần review contract JSON M2.

## 6. Tôi đã thêm/sửa những file M2 nào? Giải thích từng file

### 6.1 Contract: dữ liệu truyền giữa các phần

| File                             | Vai trò và cách dùng                                                                                                                                                                                                                                                                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/vgar/contracts/repair.py`   | Định nghĩa`Status` gồm `PASS`, `FAIL`, `ERROR`, `NOT_RUN`; danh sách `FailureCode`; `FailureReason(code, message)`; `PatchApplyResult`. `PatchApplyResult` **mới là kiểu dữ liệu**, chưa có hàm áp patch. Pydantic từ chối một số trạng thái vô lý như `PASS` nhưng `patch_applied=false`.                                             |
| `src/vgar/contracts/evidence.py` | Định nghĩa`TestCaseResult`, `TestRunResult`, `CheckResult`, `VerificationResult`, `EvidenceBundle`. `TestRunResult` chứa toàn bộ dữ liệu của một lệnh pytest; `VerificationResult` có các tầng test/type/lint/API/structure; `EvidenceBundle` thêm nguồn, hash và run ID. Các tầng chưa chạy mặc định là `NOT_RUN`, không phải `PASS`. |

Hai model dùng Pydantic 2 để validate và `model_dump(mode="json")` để xuất JSON. Không có field `schema_version`, đúng chủ trương “No Schema Versioning” của bản kế hoạch contract. `graph_version` của M1 nếu có là **ID snapshot graph**, không phải version schema M2.

### 6.2 Engine: bản sao, chạy test, ghi chứng cứ

| File                                 | Vai trò và cách hoạt động                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/vgar/repair/__init__.py`        | Đánh dấu package`vgar.repair`.                                                                                                                                                                                                                                                                                                                                                                                          |
| `src/vgar/repair/workspace.py`       | `create_workspace()` duyệt file nguồn, bỏ qua `.git`, `.venv`, cache, artifact/log; từ chối symlink/junction, đường dẫn `..` và file quá giới hạn; tạo bản sao `vgar-m2-...`, cấp `worktree_id`, tính SHA-256. `WorkspaceLease` xóa **đúng bản sao tạm** khi kết thúc. Giới hạn mặc định: 16 MiB/file, 256 MiB tổng. Đây là file copy tạm, **không phải** `git worktree` và không phải sandbox bảo mật cấp OS.          |
| `src/vgar/repair/test_runner.py`     | `run_tests(workspace, selectors, timeout_seconds)` kiểm selector tương đối, chỉ chạy `sys.executable -m pytest -q` bằng `subprocess` với `shell=False`. Đặt `cwd` và `PYTHONPATH` vào bản sao, giới hạn thời gian/output, lưu stdout/stderr, tạo JUnit XML tạm để lấy test case rồi xóa XML. Windows Job Object giúp chấm dứt cả tiến trình con khi timeout. Giới hạn output hiện là 8 MiB cho mỗi luồng stdout/stderr. |
| `src/vgar/repair/evidence_writer.py` | `begin_run()` tạo file JSON có timestamp UTC + UUID và trạng thái pending trước khi pytest chạy; `finish_run()` cập nhật **cùng file** bằng ghi tạm + thay thế atomic. Nếu tiến trình dừng trước bước cuối, record còn `complete=false`, không bị ghi nhầm thành pass.                                                                                                                                                  |
| `src/vgar/repair/baseline.py`        | `run_baseline()` ghép bốn phần trên: copy nguồn → tạo record pending → chạy test → so hash nguồn → tạo `EvidenceBundle` → hoàn tất JSON → dọn workspace. `patch_applied=false`; type/lint/API/structure là `NOT_RUN`.                                                                                                                                                                                                   |

Lưu ý: việc lọc biến môi trường có tên chứa `TOKEN`, `PASSWORD`, `API_KEY`, `SECRET` giúp giảm nguy cơ truyền secrets vào tiến trình pytest, nhưng **không đủ để chạy repository không tin cậy**. Test Python vẫn có thể đọc/ghi tài nguyên host nếu được chạy. Docker/OS sandbox là việc của milestone sau.

### 6.3 Hai script bạn dùng ở PowerShell

| File                         | Khi nào dùng?                                                                | Chạy trên bản sao không?                                                                                                                | File kết quả                                                           |
| ---------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `scripts/record_m2_test.py`  | Chạy**test phát triển của chính dự án VGAR**, ví dụ `tests/m2` hoặc `tests`. | **Không.** Chạy pytest trong `VGAR` hiện tại, ghi hash trước/sau để phát hiện thay đổi. Chỉ dùng với các test của dự án mà bạn tin cậy. | `VGAR/artifacts/m2/test-runs/<timestamp>-<run_id>.json`.               |
| `scripts/run_m2_baseline.py` | Chụp trạng thái test**trước patch** của một repo/fixture đầu vào.            | **Có.** `run_baseline()` copy repo đầu vào sang workspace tạm rồi test trên bản sao.                                                    | Cũng tại`VGAR/artifacts/m2/test-runs/`, thêm object `evidence_bundle`. |

Đây là khác biệt quan trọng: **development test wrapper ≠ isolated baseline runner**. Nếu bạn chạy trực tiếp `python -m pytest` thì pytest vẫn chạy, nhưng script đó **không tự tạo** record JSON theo chuẩn M2.

### 6.4 Test và fixture M2

| File/thư mục                       | Kiểm gì?                                                                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/m2/test_contracts.py`       | Round-trip JSON/Pydantic, trạng thái hợp lệ,`NOT_RUN`, không có `schema_version`.                                                              |
| `tests/m2/test_workspace.py`       | Copy tách biệt, nguồn không đổi, cleanup, path traversal, giới hạn kích thước; một test symlink có thể skip nếu Windows không cho tạo symlink. |
| `tests/m2/test_test_runner.py`     | Pass, assertion fail, selector sai, lỗi khởi chạy, timeout, dừng tiến trình con, vượt giới hạn output.                                         |
| `tests/m2/test_evidence_writer.py` | Record pending/final, tên file không đụng nhau, stdout UTF-8, môi trường child được ghi đúng.                                                  |
| `tests/m2/test_baseline.py`        | Baseline pass/fail/timeout, hash nguồn,`NOT_RUN` cho các tầng chưa thực hiện, record còn pending nếu writer lỗi.                               |
| `tests/fixtures/m2/clean_repo/`    | Repo cực nhỏ:`src/demo.py` trả `42`, test mong đợi `42` → PASS.                                                                                |
| `tests/fixtures/m2/failing_repo/`  | Repo cực nhỏ:`src/demo.py` trả `0`, test mong đợi `42` → FAIL có chủ đích. Không phải lỗi triển khai M2.                                       |
| `tests/fixtures/sample_repo/`      | Fixture Python có sẵn từ M1/M3; tôi dùng`tests/test_auth.py` để chạy baseline tích hợp thật.                                                   |

### 6.5 Tài liệu, cấu hình và sản phẩm sinh ra

| File/thư mục                                   | Vai trò                                                                                                                                                                                                      |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/verification_design.md`                  | Quy trình, phân loại PASS/FAIL/ERROR, timeout, giới hạn và an toàn.                                                                                                                                          |
| `docs/evidence_bundle_schema.md`               | Tên object/field của contract và ví dụ JSON.                                                                                                                                                                 |
| `docs/m2_w3_w4_handoff.md`                     | Bàn giao cho M3: đã làm, file evidence, điều chưa làm.                                                                                                                                                       |
| `README.md`                                    | Được thêm mục M2 với lệnh chạy. Phần M1 cũ vẫn còn ví dụ đường dẫn`D:\KLTN`; không nên dùng đường dẫn đó cho cây `VGAR` hiện tại.                                                                            |
| `pyproject.toml`                               | Được thêm optional extra`dev = ["pytest>=8,<9"]`; Python được khai báo `>=3.11,<3.14`. Dependency Jedi cho M1 đã có trong dependencies chính.                                                                |
| `.gitignore`                                   | Được thêm quy tắc bỏ qua thư mục pytest tạm và`m2-temp/`. Không bỏ qua `artifacts/m2/test-runs/` vì đây là kết quả cần đối chiếu. Trước khi chia sẻ/commit JSON, vẫn phải kiểm tra log có secrets hay không. |
| `artifacts/m2/test-runs/*.json`                | **Dữ liệu kết quả**, một record cho mỗi lời gọi script. File mới sẽ được tạo khi bạn tự chạy, không có tên cố định.                                                                                          |
| `M2_week_3+4/PROGRESS.md`                      | Checkpoint ngoài`VGAR`: checklist đã/chưa xong.                                                                                                                                                              |
| `M2_week_3+4/artifacts/input-manifest.json`    | SHA-256 của đầu vào trước khi triển khai.                                                                                                                                                                    |
| `M2_week_3+4/artifacts/transfer-manifest.json` | Danh sách 24 file chuyển vào`VGAR`, hash trước/sau và thời gian.                                                                                                                                             |

## 7. Flow kiểm thử thực tế: input → xử lý → output

**Có hai flow khác nhau**, dù cùng sử dụng `src/vgar/repair/test_runner.py` và `src/vgar/repair/evidence_writer.py`:

- **Flow A — kiểm thử chính VGAR:** `scripts/record_m2_test.py` chạy `tests/m2` hoặc toàn bộ `tests` **trực tiếp trong VGAR**. Mục đích là kiểm tra code M1/M2/M3 đang phát triển và lưu một JSON cho lượt kiểm thử. **Không tạo bản sao**, không có `EvidenceBundle` lồng trong record.
- **Flow B — chụp baseline cho một repository đầu vào:** `scripts/run_m2_baseline.py` tạo **bản sao tạm** của repo đó, chạy test trong bản sao và lưu JSON **có `EvidenceBundle`**. Mục đích là ghi tình trạng **trước patch** để giai đoạn sau so sánh. Đây là flow đại diện cho deliverable M2 tuần 3–4.

### 7.1 Sơ đồ tổng quát

Sơ đồ chữ dưới đây vẫn đọc được trong VS Code ngay cả khi extension không hỗ trợ Mermaid:

```text
                        CHỌN MỘT TRONG HAI FLOW
                                  │
                  ┌───────────────┴────────────────┐
                  ▼                                ▼
       A. Test code dự án VGAR           B. Baseline repo đầu vào
       record_m2_test.py                 run_m2_baseline.py
       Input: VGAR/tests/...             Input: sample_repo + test selector
                  │                                │
                  │                     workspace.py: hash + copy repo
                  │                                │
                  └───────────────┬────────────────┘
                                  ▼
                    evidence_writer.py: JSON pending
                                  │
                                  ▼
                    test_runner.py: pytest subprocess
                    stdout/stderr/exit/duration/JUnit
                                  │
                  ┌───────────────┴────────────────┐
                  ▼                                ▼
       A. Hash lại VGAR                 B. Hash lại repo nguồn
       Không có EvidenceBundle          Tạo EvidenceBundle trước patch
                  │                                │
                  └───────────────┬────────────────┘
                                  ▼
                    JSON final trong artifacts/m2/test-runs/
                    A: test_result; B: test_result + evidence_bundle
                                  │
                                  ▼
                    B dọn bản sao; A không có bản sao
```

### 7.2 Flow A — chạy test cho **chính project VGAR**

**Input nằm ở đâu?** Entry point là `D:\Project\CAPSTONES\VGAR\scripts\record_m2_test.py`. Các test M2 ở `D:\Project\CAPSTONES\VGAR\tests\m2\`; khi chọn `tests`, pytest còn chạy các test hiện có khác trong `D:\Project\CAPSTONES\VGAR\tests\` (M1/M3). Ví dụ lệnh, chạy từ `D:\Project\CAPSTONES\VGAR` sau khi đã chuẩn bị Python ở mục 10:

```powershell
& $python .\scripts\record_m2_test.py tests --task-id my-vgar-full-suite --timeout-seconds 180
```

Trong lệnh này, `tests` là **pytest selector tương đối với thư mục VGAR**, `--task-id` là nhãn do người chạy đặt, còn `--timeout-seconds` là giới hạn thời gian. Không cần đưa issue text, model, patch hay dataset SWE-bench vào flow này.

**Quá trình xử lý:**

1. Script tính `fingerprint_source(VGAR)` từ các file được tính trong chính sách hash, rồi `begin_run()` tạo JSON pending (`status=NOT_RUN`, `complete=false`). Nó ghi `source_repo` và `cwd` là `D:\Project\CAPSTONES\VGAR`, `worktree_id=development-test`.
2. `run_tests(VGAR, ("tests",), 180)` kiểm selector, chạy Python hiện tại bằng `subprocess` (`shell=False`) với argv thực tế có `-m pytest -q -p no:cacheprovider --junitxml=<đường dẫn tạm> tests`. Working directory là **VGAR gốc**, không phải bản sao. Runner đặt `PYTHONPATH` gồm `VGAR\src` và `VGAR`, tắt pytest plugin autoload và bytecode; các biến môi trường có tên chứa `TOKEN`, `PASSWORD`, `API_KEY`, `SECRET` không truyền vào child process.
3. Runner ghi stdout/stderr vào file tạm, áp timeout và giới hạn output 8 MiB mỗi luồng, đọc exit code; đọc JUnit XML tạm để lấy tên/trạng thái/thời gian từng test. Sau đó xóa thư mục `.m2-pytest-...` chứa XML/stdout.bin/stderr.bin. Trên Windows, Job Object được dùng để dừng cây tiến trình khi timeout.
4. Script hash lại VGAR và `finish_run()` chốt **cùng JSON** với `status`, `test_result`, `source_hash_after`, `complete=true`. Script trả exit code `0` **chỉ khi** pytest `PASS` và hash trước/sau bằng nhau; ngược lại trả `1`. Hash chỉ phát hiện thay đổi ở tập file được tính, không ngăn test ghi vào cây VGAR hoặc nơi khác.

**Output nằm ở đâu?** Console in `M2 test: PASS; artifact: <đường dẫn JSON>` khi thành công. File thật được ghi dưới `D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\`. Ví dụ lượt đã chạy: `D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\20260930T094850907502Z-8ffe7c74094140dbb4c5447070a935c9.json`. File này chứa `task_id`, `source_repo`, `cwd`, `argv/command`, phiên bản Python/pytest, `test_result.stdout/stderr/exit_code/duration_ms/cases/case_counts` và hash trước/sau; **không có key `evidence_bundle`**. Lượt ví dụ ghi `60 passed, 1 skipped`, `status=PASS`; đây là kết quả **test code VGAR**, không phải một task repair đã giải thành công. Tên file của lần chạy mới sẽ khác do timestamp và UUID.

### 7.3 Flow B — chụp **pre-patch baseline** cho repo đầu vào

**Input nằm ở đâu?** Entry point là `D:\Project\CAPSTONES\VGAR\scripts\run_m2_baseline.py`. Ví dụ repo mẫu có sẵn là `D:\Project\CAPSTONES\VGAR\tests\fixtures\sample_repo\`; file code được kiểm là `src\auth\service.py`, trong đó `login(username, password)` trả `bool(username and password)`. File test là `tests\test_auth.py`, import `auth.service.login` và kiểm `login("alice", "secret")` trả giá trị đúng. Lệnh ví dụ, chạy từ thư mục VGAR:

```powershell
& $python .\scripts\run_m2_baseline.py .\tests\fixtures\sample_repo tests/test_auth.py --task-id my-auth-baseline --timeout-seconds 30
```

Tham số thứ nhất `./tests/fixtures/sample_repo` là **repo nguồn** cần quan sát. Tham số thứ hai `tests/test_auth.py` là **selector tương đối với repo nguồn**, không phải tương đối với VGAR. `--task-id` là ID/nhãn để truy vết; `--timeout-seconds` giới hạn **subprocess pytest**, không giới hạn toàn bộ thao tác copy/hash. Nếu không truyền `--artifact-dir`, JSON được lưu trong `VGAR\artifacts\m2\test-runs\`.

**Quá trình xử lý từng bước:**

1. `run_m2_baseline.py` lấy thư mục tạm từ `VGAR_M2_TEMP_ROOT` nếu bạn đặt; mặc định là `D:\Project\CAPSTONES\m2-temp\`. Script chuyển các biến `TMP`, `TEMP`, `TMPDIR` đến đây rồi gọi `run_baseline()` trong `src/vgar/repair/baseline.py`.
2. `create_workspace()` trong `src/vgar/repair/workspace.py` duyệt file của `sample_repo`, bỏ qua `.git`, `.venv`, cache, `artifacts`, `logs`, `.vgar`...; từ chối symlink/junction, file lớn hơn 16 MiB hoặc tổng file lớn hơn 256 MiB. Nó tính SHA-256 trên path + nội dung file được duyệt, copy vào `D:\Project\CAPSTONES\m2-temp\vgar-m2-<ngẫu nhiên>\` và kiểm lại repo nguồn không đổi trong khi copy. Đây là **file copy**, không phải `git worktree` hay sandbox OS.
3. `begin_run()` tạo một file JSON ngay từ đầu trong `VGAR\artifacts\m2\test-runs\`, trạng thái pending `NOT_RUN`, `complete=false`. JSON lưu đường dẫn `source_repo` gốc, hash trước test, `cwd` là **bản sao tạm**, `worktree_id` và thông tin interpreter/môi trường.
4. `run_tests()` chạy pytest **trong bản sao** với selector `tests/test_auth.py`. Runner đặt `PYTHONPATH` đến `vgar-m2-...\src` và chính thư mục `vgar-m2-...`, nên import `auth.service` đọc code của bản sao. Nó dùng `sys.executable -m pytest -q -p no:cacheprovider --junitxml=... tests/test_auth.py`; đường dẫn interpreter (`sys.executable`) chính là Python đang chạy script trên máy bạn, không cố định là một model hay một venv cụ thể. Stdout/stderr, exit code, thời gian và JUnit test case được đưa vào `TestRunResult`; XML và các file output thô chỉ tồn tại tạm thời.
5. `run_baseline()` hash lại **repo nguồn**, tạo `EvidenceBundle`: `verification.patch_applied=false`, `verification.tests=<TestRunResult>`, `typecheck/lint/api_check/structural_check=NOT_RUN`, `metadata.mode=pre_patch_baseline`. Writer chốt JSON `complete=true`, rồi `WorkspaceLease` xóa bản sao tạm. JSON giữ `cwd` lịch sử để audit, dù thư mục đó đã bị xóa.
6. CLI in `M2 baseline: <trạng thái>; source_unchanged: <True/False>` và `Evidence: <đường dẫn JSON>`. Exit code là `0` **chỉ nếu** test `PASS` và hash nguồn trước/sau bằng nhau. Test `FAIL`, `ERROR` hoặc nguồn đổi cho exit code `1`.

**Output nằm ở đâu và chứa gì?** Ví dụ JSON đã chạy: `D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\20260930T094926633646Z-bca59c6e5ce64062a3ee9ac5a4c2cc20.json`. Trong file này, `source_repo` trỏ đến `VGAR\tests\fixtures\sample_repo`, `cwd` trỏ đến bản sao tạm đã được dọn, `test_result.stdout` báo `1 passed`, `stderr` rỗng, `exit_code=0`, `duration_ms=594`, `case_counts.passed=1`, hai hash nguồn bằng nhau, và `evidence_bundle.verification.patch_applied=false`. Dòng `1 passed in 0.09s` của pytest và `duration_ms=594` **khác nhau vì đo hai khoảng khác nhau**: pytest báo thời gian chạy test, runner đo toàn bộ subprocess từ lúc khởi chạy đến khi đọc kết quả.

Để thấy flow FAIL được ghi như thế nào, dùng `D:\Project\CAPSTONES\VGAR\tests\fixtures\m2\failing_repo\`: `src\demo.py` trả `0` nhưng `tests\test_demo.py` mong `42`. Một JSON FAIL có chủ đích, sinh từ bản candidate trước khi tích hợp, nằm ở `D:\Project\CAPSTONES\M2_week_3+4\VGAR_candidate\artifacts\m2\test-runs\20260930T091531141463Z-7507513c8e7d4a1ea31c8d3b387a5366.json`; nó ghi `status=FAIL`, `exit_code=1`, `reason.code=TEST_FAILED` và assertion `assert 0 == 42`. Nếu bạn chạy lại trên VGAR hiện tại, JSON **mới** sẽ được tạo dưới `VGAR\artifacts\m2\test-runs\`. Lệnh cụ thể cho cả hai fixture nằm ở mục 10, Bước 5 và 7.

### 7.4 Bảng nhanh: đường dẫn nào là input, đường dẫn nào là output?

| Flow                     | Input bạn chọn                                                                                        | File code/test thực sự được chạy                                                                                | Output giữ lại                                                                                                               | Dữ liệu chỉ tạm thời                                                  |
| ------------------------ | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **A: development tests** | `VGAR\scripts\record_m2_test.py` + selector `tests/m2` hoặc `tests`                                   | `VGAR\tests\...` chạy ngay trong `D:\Project\CAPSTONES\VGAR`                                                    | `D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\<timestamp>-<UUID>.json`, có `test_result`, **không có** `evidence_bundle` | `VGAR\.m2-pytest-...\` chứa JUnit/output thô; được dọn sau lượt chạy  |
| **B: repo baseline**     | `VGAR\scripts\run_m2_baseline.py` + `VGAR\tests\fixtures\sample_repo` + selector `tests/test_auth.py` | `src/auth/service.py` và `tests/test_auth.py` **đã được copy** sang `D:\Project\CAPSTONES\m2-temp\vgar-m2-...\` | Cùng thư mục`VGAR\artifacts\m2\test-runs\<timestamp>-<UUID>.json`, thêm `evidence_bundle`                                    | Toàn bộ`vgar-m2-...\`, kể cả JUnit/output thô, được dọn sau lượt chạy |

`source_hash_before == source_hash_after` chỉ xác nhận các file nguồn **nằm trong chính sách fingerprint** không đổi. Hash bỏ qua `.git`, virtualenv, cache, `artifacts`, `logs` và `.vgar`; nó không chứng minh rằng mọi file ngoài repo/host an toàn. Không bước nào trong cả hai flow gọi LLM, M1 graph retrieval hoặc áp patch. `PASS` ở đây là **test status**, không phải **repair success**.

## 8. JSON kết quả nằm ở đâu và đọc thế nào?

Ví dụ thực tế của lượt baseline đã chạy: `artifacts/m2/test-runs/20260930T094926633646Z-bca59c6e5ce64062a3ee9ac5a4c2cc20.json`. Lượt này có `status=PASS`, `exit_code=0`, `duration_ms=594`, `case_counts.passed=1`, stderr rỗng và hash nguồn trước/sau bằng nhau. Thời gian 594 ms là **thời gian subprocess pytest**, không phải tổng mọi bước copy/hash/ghi JSON.

| JSON path                                                                  | Nội dung                                                                                                                                                                        |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_id`, `task_id`, `started_utc`, `ended_utc`                            | Định danh, nhãn task và thời điểm.                                                                                                                                              |
| `source_repo`, `source_hash_before`, `source_hash_after`                   | Repo đầu vào và SHA-256 trước/sau.                                                                                                                                              |
| `worktree_id`, `cwd`                                                       | ID bản sao và thư mục pytest đã chạy.`worktree_id` là nhãn do M2 sinh, không có nghĩa đã dùng Git worktree.                                                                     |
| `argv`, `command`                                                          | Lệnh pytest thực tế;`argv` là dạng list để tránh mơ hồ khi trích dẫn/escaping.                                                                                                  |
| `python_executable`, `python_version`, `pytest_version`, `environment`     | Phiên bản và môi trường quan trọng để tái lập.                                                                                                                                  |
| `status`, `complete` ở cấp cao nhất                                        | Trạng thái kết quả và việc**file JSON đã hoàn tất ghi** hay chưa. `complete=false` có thể là lượt bị ngắt, cần xem tiếp.                                                        |
| `test_result.status`, `exit_code`, `duration_ms`                           | PASS/FAIL/ERROR của**pytest**, mã thoát và thời gian tính bằng mili giây.                                                                                                       |
| `test_result.stdout`, `test_result.stderr`                                 | Toàn bộ text đã thu được từ hai luồng của pytest. Không được bỏ qua stderr khi tìm lỗi import/khởi chạy.                                                                        |
| `test_result.cases`, `case_counts`                                         | Tên, trạng thái, thời gian và chi tiết từng test lấy từ JUnit XML tạm. XML được xóa sau khi dữ liệu đã nhúng vào JSON.                                                          |
| `test_result.reason`                                                       | Mã và thông báo khi FAIL/ERROR, ví dụ`TEST_FAILED` hoặc `TEST_TIMEOUT`.                                                                                                         |
| `test_result.complete`, `output_truncated`, `stdout_bytes`, `stderr_bytes` | Pytest chạy trọn vẹn hay bị dừng; cỡ output thực thu.`output_truncated=true` báo vượt giới hạn output, dù tiến trình quá nhanh có thể đã ghi hơn ngưỡng trước khi bị phát hiện. |
| `evidence_bundle`                                                          | Chỉ có trong**baseline**, chứa `verification.patch_applied=false`, `verification.tests` và các tầng `typecheck/lint/api_check/structural_check=NOT_RUN`.                        |

**Đừng nhầm hai `complete`:** `complete` ngoài cùng nghĩa là record JSON đã được chốt; `test_result.complete` nghĩa là subprocess pytest không bị cắt do timeout/giới hạn output. Một lượt timeout có thể có `complete=true` ngoài cùng (bằng chứng được ghi xong) nhưng `test_result.complete=false`.

`PASS` = pytest hoàn thành và exit code 0. `FAIL` = có test assertion thất bại. `ERROR` = không thể có kết quả kiểm thử tin cậy (timeout, lỗi chạy, output quá giới hạn...). `NOT_RUN` = tầng đó chưa được thực hiện, **không** phải đạt yêu cầu. Với fixture hỏng có chủ đích, `FAIL` và exit code PowerShell 1 là **kết quả mong đợi của ví dụ**, không phải phải sửa M2.

## 9. Tôi đã kiểm thử những gì? Bằng chứng nào xác nhận?

Sau khi tích hợp, tôi chạy `scripts/record_m2_test.py tests` trên `VGAR`. Record cuối: `artifacts/m2/test-runs/20260930T094850907502Z-8ffe7c74094140dbb4c5447070a935c9.json`:

- **60 test PASS, 0 FAIL, 0 ERROR, 1 SKIP**, `status=PASS`, `complete=true` và hash nguồn trước/sau bằng nhau.
- 23 test case M2 được thu thập: 4 baseline, 5 contract, 2 evidence writer, 8 pytest runner, 4 workspace. Trong đó 1 test workspace phải skip vì Windows của phiên chạy không cho tạo symlink; vậy M2 có **22 pass + 1 skip**.
- Các test còn lại bao phủ schema/context/graph builder/SQLite graph pipeline, graph resource, MCP graph tool shape, state/route của M3 và cấu hình sinh của model ở mức mock. `test_hf_model.py` monkeypatch quá trình load, **không tải/chạy LLM thật**.
- Lượt baseline tích hợp trên `tests/fixtures/sample_repo` có record `artifacts/m2/test-runs/20260930T094926633646Z-bca59c6e5ce64062a3ee9ac5a4c2cc20.json`: `PASS`, một test passed, `patch_applied=false`, hash nguồn không đổi, bốn tầng type/lint/API/structural là `NOT_RUN`.
- Lượt baseline **FAIL có chủ đích** của fixture M2 được giữ ở `M2_week_3+4/VGAR_candidate/artifacts/m2/test-runs/20260930T091531141463Z-7507513c8e7d4a1ea31c8d3b387a5366.json`. Nó chứng minh test fail được ghi là `FAIL/TEST_FAILED`, không bị ngụy trang thành `PASS` hay lỗi hạ tầng.
- Tôi có các lượt red/green trong `M2_week_3+4/artifacts/` và candidate `artifacts/m2/test-runs/`; từng lỗi/timeout được giữ để kiểm tra lại, không xóa kết quả thất bại.

Trong một lượt full suite ban đầu trên candidate đã có ba thất bại do **môi trường/bản sao**: thiếu graph fixture `sample_graph.db` trong bản sao và interpreter thử đầu chưa có Jedi. Sau khi đưa fixture có sẵn vào candidate và dùng môi trường Python 3.11 đã cài Jedi, full suite candidate đạt 59 pass, 1 skip; bản VGAR tích hợp cuối đạt 60 pass, 1 skip sau khi thêm một test giới hạn output. Đây không phải việc sửa M1 để che lỗi.

**Giới hạn của kết quả:** 60 pass **không** chứng minh agent sửa được multi-file task, không phải SWE-bench score, không kiểm chứng LLM/fine-tuning hay MCP execution tool. Nó chứng minh các unit/integration test hiện có của hạ tầng chạy qua trong môi trường thử nghiệm đó.

## 10. Hướng dẫn tự chạy từ đầu đến cuối trên Windows PowerShell

**Không phải chạy Bước 0–8 từ đầu ở mọi lần.** Phân loại trước khi nhập lệnh:

| Loại thao tác                                      | Khi nào cần chạy?                                                                                                                                                          | Bước tương ứng                                                                                                                               |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Chuẩn bị một lần trên mỗi máy/bản clone**        | Tạo`.venv` **nếu chưa có**; cài dependency **nếu thiếu** hoặc khi `pyproject.toml`/môi trường thay đổi. Không cài lại chỉ vì vừa mở PowerShell.                            | Phần cài đặt ở Bước 1.                                                                                                                       |
| **Chuẩn bị lại khi mở cửa sổ PowerShell mới**      | Chuyển vào thư mục VGAR và gán lại biến`$python` vì biến PowerShell chỉ tồn tại trong phiên hiện tại. Nếu bạn muốn dùng thư mục tạm tùy chỉnh, đặt lại biến môi trường đó. | Bước 0, phần chọn interpreter ở Bước 1; Bước 2**nếu cần**.                                                                                   |
| **Chạy mỗi khi muốn tạo một kết quả kiểm thử mới** | Chọn**một hoặc vài** lệnh test đúng mục đích; mỗi lệnh chạy sẽ sinh một JSON mới. Không bắt buộc chạy tất cả Bước 3–8 theo thứ tự.                                         | Bước 3 (test M2), 4 (full suite), 5 (baseline mẫu), 5A (baseline repo khác), 7 (FAIL mẫu), 8 (MCP smoke, tùy chọn); Bước 6 dùng để đọc JSON. |

**Nếu bạn đã cài từ lần trước:** chạy Bước 0 → dòng gán `$python` và kiểm import ở Bước 1 → bỏ qua `venv`/`pip install` khi kiểm tra đạt → chọn Bước 3, 4, 5 hoặc 5A theo mục tiêu. Nếu cần xem JSON, chạy thêm Bước 6. Không cần chạy Bước 7–8 để xác nhận M2 baseline thường ngày.

Ví dụ **lần chạy lại để chụp baseline**, với điều kiện `.venv` và dependency đã được cài ở lần đầu (khối này **không cài đặt gì**):

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -c "import pydantic, pytest; print('M2 dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw 'Thiếu dependency M2; xem Bước 1C.' }
& $python .\scripts\run_m2_baseline.py .\tests\fixtures\sample_repo tests/test_auth.py --task-id my-auth-baseline --timeout-seconds 30
$LASTEXITCODE
```

Nếu lần đầu hoặc lệnh kiểm import thất bại, **đừng chạy lệnh baseline ngay**; làm Bước 1 bên dưới để cài phần đang thiếu. Ví dụ này chọn baseline; thay dòng cuối bằng Bước 3/4 khi mục tiêu là test code VGAR.

### Bước 0 — Vào đúng thư mục (**mỗi cửa sổ PowerShell mới**)

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
Get-Location
Test-Path .\pyproject.toml
Test-Path .\scripts\run_m2_baseline.py
Test-Path .\tests\fixtures\sample_repo\tests\test_auth.py
```

Ba `Test-Path` phải là `True`. Nếu khác, bạn đang ở nhầm thư mục hoặc bản VGAR khác.

### Bước 1 — Chọn Python và kiểm dependency (**kiểm trước, chỉ cài khi thiếu**)

**1A. Người mới chạy lần đầu trên bản clone này:** kiểm tra Python. VGAR khai báo hỗ trợ `>=3.11,<3.14`; ví dụ dưới dùng Python 3.11. Nếu lệnh báo không có Python 3.11, cần cài Python tương thích hoặc thay `-3.11` bằng phiên bản 3.12/3.13 bạn đã cài. Lệnh kiểm tra chỉ cần làm khi chưa biết môi trường máy mình:

```powershell
py -3.11 --version
```

Chỉ tạo `.venv` **nếu chưa có** `VGAR\.venv\Scripts\python.exe`. Không xóa hoặc tạo đè `.venv` đang dùng:

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    py -3.11 -m venv .venv
}
```

**1B. Cả người mới lẫn người đã cài:** trong **mỗi PowerShell mới**, gán lại `$python` đến interpreter của `.venv` và xem phiên bản. Việc này **không cài lại gì**:

```powershell
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python --version
```

Nếu `Resolve-Path` thất bại, `.venv` chưa có hoặc bạn đang ở sai thư mục; quay lại Bước 0/1A. Không dùng một `$python` còn sót từ cửa sổ hay project khác. **Không cần activate `.venv`** khi đã gọi trực tiếp `& $python`.

**1C. Chỉ cần M2:** chạy **lệnh kiểm tra import** dưới đây. Nếu in `M2 dependencies OK` và `$LASTEXITCODE` là `0`, **bỏ qua lệnh `pip install`**. Nếu báo `ModuleNotFoundError`/exit code khác 0, mới chạy lệnh cài rồi kiểm tra lại:

```powershell
& $python -c "import pydantic, pytest; print('M2 dependencies OK')"
$LASTEXITCODE
```

```powershell
# CHỈ KHI kiểm tra M2 ở trên thất bại hoặc bạn vừa tạo .venv mới:
& $python -m pip install 'pydantic>=2' 'pytest>=8,<9'
& $python -c "import pydantic, pytest; print('M2 dependencies OK')"
```

**1D. Muốn chạy full suite M1+M2+M3 hoặc MCP smoke:** chỉ kiểm tra M2 ở 1C **chưa đủ**. Kiểm tra các dependency của full project (và package VGAR đã cài trong venv):

```powershell
& $python -c "import vgar, pydantic, pytest, jedi, tree_sitter_python, mcp, langgraph, torch, transformers; print('VGAR dependencies OK')"
$LASTEXITCODE
```

Nếu in `VGAR dependencies OK` và exit code `0`, **không cài lại**. Nếu thiếu package, vừa tạo venv mới, hoặc sau khi nhóm thay `pyproject.toml` khiến bộ dependency hiện có không phù hợp, mới cài project và extra `dev` rồi kiểm lại:

```powershell
# CHỈ KHI kiểm tra full dependencies ở trên thất bại/cần đồng bộ dependency:
& $python -m pip install -e '.[dev]'
& $python -c "import vgar, pydantic, pytest, jedi, tree_sitter_python, mcp, langgraph, torch, transformers; print('VGAR dependencies OK')"
```

`pip install --upgrade pip` **không phải bước bắt buộc** và không cần chạy mỗi lần. Lệnh cài full có PyTorch/Transformers và các thư viện lớn, cần Internet, dung lượng ổ đĩa và thời gian; **không cần tải model Qwen** để chạy các test trong mục này. Lệnh kiểm import xác nhận package có thể import, **không** chứng minh mọi phiên bản đúng yêu cầu; nếu project đổi dependency hoặc test báo lỗi tương thích, cần đối chiếu `pyproject.toml` và cài đồng bộ lại. `uv.lock` trong cây hiện tại rỗng, nên chưa có lockfile để bảo đảm y hệt mọi phiên bản dependency. Bản kiểm thử tôi dùng trước đó là một interpreter Python 3.11 **đã có sẵn dependency**; tôi không cài thêm vào hay sửa source của dự án cũ.

### Bước 2 — Chọn nơi chứa workspace tạm (**tùy chọn, không cần lặp nếu dùng mặc định**)

Mặc định hai script M2 dùng `D:\Project\CAPSTONES\m2-temp`; chúng tự tạo thư mục gốc khi cần. **Bạn có thể bỏ qua toàn bộ Bước 2.** Chỉ dùng hai lệnh sau nếu muốn chọn một thư mục tạm khác hoặc muốn đặt đường dẫn rõ ràng cho phiên PowerShell này:

```powershell
$env:VGAR_M2_TEMP_ROOT = 'D:\Project\CAPSTONES\m2-temp'
New-Item -ItemType Directory -Force $env:VGAR_M2_TEMP_ROOT | Out-Null
```

Nên đặt trên ổ D còn trống. `New-Item -Force` trên thư mục đã tồn tại không phải cài đặt lại; nhưng cũng **không cần gọi mỗi lần** vì script tự tạo. Script sẽ tạo thư mục con tên `vgar-m2-...` rồi tự dọn. Đừng đặt `VGAR_M2_TEMP_ROOT` bên trong repo đầu vào cần chụp baseline. Nếu dùng đường dẫn tùy chỉnh, biến `$env:VGAR_M2_TEMP_ROOT` phải được đặt lại trong **PowerShell mới**; thư mục trên đĩa vẫn còn, không cần tạo lại. Cũng không cần xóa `m2-temp` giữa các lượt test.

### Bước 3 — Chạy test chỉ cho M2 (**mỗi lần muốn test M2; không bắt buộc mỗi phiên**)

```powershell
& $python .\scripts\record_m2_test.py tests/m2 --task-id my-m2-check --timeout-seconds 120
$LASTEXITCODE
```

Exit code `0` và dòng `M2 test: PASS; artifact: ...json` là kết quả tốt. Record sẽ ghi số pass/skip thực tế. Trên môi trường cho phép tạo symlink, test bị skip trước đây có thể chạy; số pass không nhất thiết luôn đúng 22. Nếu `M2 test: FAIL/ERROR`, **mở JSON được in ra** để xem lỗi, không chỉ nhìn exit code.

### Bước 4 — Chạy toàn bộ test hiện có của VGAR (**chọn khi cần full suite**)

Chỉ làm sau khi đã cài full dependencies ở Bước 1:

```powershell
& $python .\scripts\record_m2_test.py tests --task-id my-vgar-full-suite --timeout-seconds 180
$LASTEXITCODE
```

Trong phiên kiểm thử của tôi: `60 passed, 1 skipped`. Trên máy khác, thời gian và khả năng tạo symlink có thể khác. Pytest được cấu hình trong `pyproject.toml` để bỏ qua thư mục fixture như một test suite riêng. Lệnh này **không chạy model thật** và **không tự sửa lỗi**.

### Bước 5 — Chụp baseline sạch trên fixture có sẵn của M1/M3 (**chọn khi cần baseline mới**)

```powershell
$before = (Get-FileHash .\tests\fixtures\sample_repo\src\auth\service.py -Algorithm SHA256).Hash
& $python .\scripts\run_m2_baseline.py .\tests\fixtures\sample_repo tests/test_auth.py --task-id my-auth-baseline --timeout-seconds 30
$runExit = $LASTEXITCODE
$after = (Get-FileHash .\tests\fixtures\sample_repo\src\auth\service.py -Algorithm SHA256).Hash
"Exit code = $runExit; source file unchanged = $($before -eq $after)"
```

Mong đợi: `M2 baseline: PASS; source_unchanged: True`, exit code `0`, file nguồn trước/sau cùng hash. Đây là **một test auth mẫu**, không phải chạy repair trên toàn bộ VGAR.

### Bước 5A — Chụp baseline trên **một Python repository khác**

**Có thể**, nhưng đây vẫn chỉ là kiểm thử **trước patch** của repo bạn chọn, không phải VGAR tự sửa lỗi trong repo đó. Runner nhận **thư mục repo đã có trên máy**, không nhận URL GitHub trực tiếp. Nếu repo ở GitHub, bạn phải clone/checkout phiên bản muốn kiểm trước; nên ghi lại commit hash để có thể chạy lại cùng đầu vào. **Chỉ dùng repo bạn tin cậy**: dù M2 copy file để tránh sửa nhầm nguồn, pytest vẫn thực thi code Python trên máy Windows của bạn, không có Docker/OS sandbox. Đừng dùng repo lạ hoặc benchmark chưa được cô lập bằng cơ chế an toàn riêng.

**Điều kiện trước khi chạy:**

1. Repo đầu vào là **thư mục riêng**, không phải `D:\Project\CAPSTONES` hoặc thư mục cha của `D:\Project\CAPSTONES\m2-temp`. Temp root không được là chính repo, ở trong repo hoặc chứa repo; hai thư mục nên là **anh em hoặc tách hẳn nhau**.
2. Có ít nhất một pytest selector (file, thư mục test, hoặc node ID) **tương đối với gốc repo đó**. Ví dụ repo có `D:\Project\CAPSTONES\my_python_repo\tests\test_feature.py` thì selector là `tests/test_feature.py`, **không** phải đường dẫn tuyệt đối.
3. Repo có thể được copy theo chính sách hiện tại: bỏ qua `.git`, `.venv`, cache, `artifacts`, `logs`, `.vgar`, `node_modules`; từ chối symlink/junction; mặc định tối đa **16 MiB/file, 256 MiB tổng**. Nếu test cần file bị bỏ qua, kết quả baseline không còn đại diện đúng cho repo đó. Không sửa code để vượt giới hạn một cách vội vàng.
4. **Python interpreter chạy script cũng là interpreter chạy pytest cho repo đích.** `.venv` của VGAR cần có `pytest`, `pydantic` và các dependency mà **test của repo đích** thực sự import. Runner không tự `pip install` dependency cho repo đích. Tránh cài bừa package của repo đích vào `.venv` VGAR nếu có nguy cơ xung đột; có thể tạo venv **riêng** cho repo đích, cài M2 tối thiểu (`pydantic`, `pytest`) và các dependency đáng tin cậy của repo đó, rồi dùng Python của venv riêng để gọi script VGAR. Runner đang đặt `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; test phụ thuộc pytest plugin bên ngoài có thể không chạy đúng dù plugin đã cài. Trường hợp đó cần đánh giá cấu hình runner trước, không coi ngay là lỗi của repo.

**Ví dụ cho repo thật của bạn:** thay `D:\Project\CAPSTONES\my_python_repo` và `tests/test_feature.py` bằng đường dẫn/file **thực sự tồn tại**. Chạy trong PowerShell tại `VGAR`; nếu đang thấy `(.venv)`, có thể dùng `python` thay cho `$python`, nhưng kiểm tra `python -c "import sys; print(sys.executable)"` trước để chắc đúng interpreter.

Nếu muốn thử ngay trên **một repo mẫu khác `sample_repo`** mà không cần chuẩn bị repo riêng, dùng fixture `D:\Project\CAPSTONES\VGAR\tests\fixtures\m2\clean_repo` (file `src\demo.py` trả `42`, `tests\test_demo.py` đòi `42`):

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python .\scripts\run_m2_baseline.py .\tests\fixtures\m2\clean_repo tests/test_demo.py --task-id another-repo-demo --timeout-seconds 30
$LASTEXITCODE
```

Đây vẫn là fixture nhỏ, chưa đại diện cho repo lớn hay SWE-bench. Với **repo thật của bạn**, dùng mẫu lệnh sau:

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
$targetRepo = 'D:\Project\CAPSTONES\my_python_repo'  # THAY bằng repo của bạn
$selector = 'tests/test_feature.py'                    # THAY bằng file test/node ID của repo đó
if (-not (Test-Path -LiteralPath $targetRepo -PathType Container)) { throw 'Không tìm thấy repo đích' }
$selectorFile = ($selector -split '::', 2)[0]
if (-not (Test-Path -LiteralPath (Join-Path $targetRepo $selectorFile) -PathType Leaf)) { throw 'Không tìm thấy file test trong repo đích' }
& $python .\scripts\run_m2_baseline.py $targetRepo $selector --task-id external-repo-baseline --timeout-seconds 120
$runExit = $LASTEXITCODE
"Exit code = $runExit"
```

**Chạy toàn bộ thư mục test của repo đích:** nếu repo có thư mục `D:\Project\CAPSTONES\my_python_repo\tests\`, dùng **một selector là `tests`**. Pytest sẽ tự thu thập các test trong thư mục đó, kể cả ở các file con. Thay đường dẫn repo mẫu trong khối dưới bằng repo **thực sự tồn tại** của bạn:

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
$targetRepo = 'D:\Project\CAPSTONES\my_python_repo'  # THAY bằng repo của bạn
if (-not (Test-Path -LiteralPath $targetRepo -PathType Container)) { throw 'Không tìm thấy repo đích' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRepo 'tests') -PathType Container)) { throw 'Repo không có thư mục tests' }
& $python .\scripts\run_m2_baseline.py $targetRepo tests --task-id external-repo-all-tests --timeout-seconds 300
$runExit = $LASTEXITCODE
"Exit code = $runExit"
```

Ở đây `tests` là **đường dẫn thư mục tương đối với `$targetRepo`**, không phải `VGAR\tests`. Lệnh tạo **một JSON baseline** tổng hợp nhiều test case dưới `VGAR\artifacts\m2\test-runs\`; nó **không** tạo patch hay thực hiện sửa lỗi multi-file. Timeout 300 giây chỉ là ví dụ: chọn mức phù hợp với thời gian chạy thực tế của suite. Đoạn kiểm tra `-PathType Leaf` trong ví dụ **một file test** phía trên không dùng được cho selector là thư mục; vì vậy ví dụ này kiểm `-PathType Container`.

Nếu muốn chạy **một vài file thay vì cả thư mục**, đặt nhiều selector liên tiếp trước các option, ví dụ: `$targetRepo 'tests/test_feature.py' 'tests/test_api.py' --task-id ...`. Nếu repo không có thư mục `tests` nhưng có test ở nơi khác, thay `tests` bằng **đường dẫn tương đối tới thư mục test thật**. Nếu hoàn toàn không có test, M2 hiện không tự tạo test; không thể coi lượt baseline pytest là bằng chứng code repo đó đúng. Không dùng selector `.` hoặc path tuyệt đối vì runner chỉ cho phép đường dẫn tương đối an toàn.

**Output:** script in `M2 baseline: PASS/FAIL/ERROR; source_unchanged: True/False` và `Evidence: D:\Project\CAPSTONES\VGAR\artifacts\m2\test-runs\<timestamp>-<UUID>.json`. Đó là **file kết quả cần giữ**, gồm lệnh đã chạy, stdout/stderr, exit code, duration, từng test case, source hash và `EvidenceBundle`. Bản sao chạy test ở `D:\Project\CAPSTONES\m2-temp\vgar-m2-...\` chỉ tồn tại trong lượt chạy rồi được xóa. Tên JSON **mỗi lượt khác nhau**; hãy dùng đường dẫn `Evidence:` vừa in ra (hoặc Bước 6 để tìm file mới nhất nếu không có lượt khác ghi đồng thời).

- `PASS`, exit code script `0`: pytest hoàn tất với exit code `0` **và** source hash không đổi; không có nghĩa VGAR đã tạo patch/sửa lỗi.
- `FAIL`, thường exit code script `1`: có assertion pytest thất bại; xem `test_result.stdout`, `cases` và `reason`. Một repo có test fail sẵn là đầu vào baseline hợp lệ.
- `ERROR`, exit code script `1`: kiểm `test_result.reason`, `stdout`, `stderr` để phân biệt thiếu package, lỗi collection, timeout hoặc output quá lớn. **Không** tự kết luận repo bị lỗi logic chỉ vì môi trường test chưa sẵn sàng.
- Nếu lỗi xảy ra **trước khi writer tạo JSON** (ví dụ đường dẫn repo không tồn tại, symlink bị từ chối, vượt giới hạn copy), có thể **không có file `Evidence:` mới**; xem thông báo PowerShell và kiểm điều kiện đầu vào ở trên.

Muốn đọc JSON của repo mới, dùng các lệnh ở **Bước 6**. Không cần chạy lại Bước 0–4 nếu phiên PowerShell, `.venv` và dependency đã sẵn sàng.

### Bước 6 — Mở JSON vừa sinh và xem đúng field (**chạy sau test khi muốn xem chi tiết**)

Script ở Bước 5 in đường dẫn JSON. Bạn có thể dùng đường dẫn đó trực tiếp, hoặc lấy file mới nhất nếu không có tiến trình khác đang ghi đồng thời:

```powershell
$latest = Get-ChildItem .\artifacts\m2\test-runs\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$result = Get-Content -Raw $latest.FullName | ConvertFrom-Json
$latest.FullName
$result | Select-Object run_id,task_id,status,complete,source_hash_before,source_hash_after
$result.test_result | Select-Object status,command,exit_code,duration_ms,case_counts,reason
$result.test_result.stdout
$result.test_result.stderr
$result.evidence_bundle.verification | ConvertTo-Json -Depth 8
```

`$result.test_result.duration_ms / 1000` là số giây pytest chạy. Nếu vừa chạy `record_m2_test.py`, field `evidence_bundle` không có; chỉ baseline mới bổ sung field đó. So sánh hash bằng:

```powershell
$result.source_hash_before -eq $result.source_hash_after
```

### Bước 7 — Thử fixture thất bại có chủ đích (**tùy chọn; không cần chạy mỗi lần**)

```powershell
& $python .\scripts\run_m2_baseline.py .\tests\fixtures\m2\failing_repo tests/test_demo.py --task-id my-deliberate-fail --timeout-seconds 30
$LASTEXITCODE
```

Mong đợi: exit code `1`, JSON có `status=FAIL`, `test_result.reason.code=TEST_FAILED`, stdout chứa assertion `assert 0 == 42`, nguồn vẫn không đổi. Đây là kiểm tra **khả năng phân loại thất bại**, không phải dấu hiệu bạn cài sai.

### Bước 8 — Tùy chọn: kiểm M1 graph và M3 MCP riêng (**không cần để kiểm M2**)

Các test graph/MCP cơ bản đã nằm trong full suite Bước 4. Nếu muốn thử kết nối MCP thực qua `stdio` với SQLite mẫu:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$env:VGAR_GRAPH_BACKEND = 'sqlite'
$env:VGAR_GRAPH_DATABASE = (Resolve-Path .\artifacts\sample_graph.db).Path
& $python .\scripts\smoke_mcp.py
& $python .\scripts\smoke_w3_w4.py
```

Các smoke script này là code M3 cũ: chúng in kết quả ra console và graph server có thể ghi `logs/mcp_audit.jsonl`; **chúng không dùng `record_m2_test.py` và không tự tạo JSON pytest M2**. Nếu muốn giữ transcript PowerShell riêng, dùng `Start-Transcript`/`Stop-Transcript`. Trước khi chạy, cần full dependencies; `VGAR_GRAPH_DATABASE` phải trỏ đến database tồn tại. `smoke_workflow.py` chỉ thử LangGraph placeholder; `smoke_hf_agent.py` có thể load model lớn và **không cần chạy** để kiểm M2.

Khi xong, nếu không muốn các biến môi trường ảnh hưởng phiên lệnh sau:

```powershell
Remove-Item Env:VGAR_GRAPH_BACKEND,Env:VGAR_GRAPH_DATABASE,Env:PYTHONPATH -ErrorAction SilentlyContinue
```

## 11. Khi test lỗi, kiểm tra theo thứ tự nào?

1. **Không tìm thấy script/fixture:** chạy `Get-Location`, kiểm tra đang ở `D:\Project\CAPSTONES\VGAR`. Selector như `tests/test_auth.py` được hiểu **tương đối với repo đầu vào của baseline**, không phải luôn tương đối với `VGAR`.
2. **`No module named pytest`/`pydantic`:** cài gói vào **đúng `$python`** đang dùng. `pip` ngoài venv không đảm bảo cài vào interpreter của script.
3. **Test M1 về Jedi fail:** cài full dependencies của `pyproject.toml` (trong đó có `jedi==0.20.0`). Lượt kiểm thử đầu bằng môi trường không có Jedi đã thất bại ở một test M1.
4. **`GraphNotReadyError` trong test SQLite:** xác nhận `artifacts/sample_graph.db` tồn tại. Đây là fixture graph có sẵn; bản sao candidate ban đầu của tôi thiếu file này nên hai test đã fail, sau đó đã đưa vào.
5. **`TEST_TIMEOUT`:** mở JSON, xem `timeout_seconds`, `test_result.stdout/stderr` và `reason`. Có thể tăng `--timeout-seconds` nếu test bình thường cần thêm thời gian; không đổi timeout để che một tiến trình treo thực sự.
6. **`complete=false` ngoài cùng:** lượt có thể bị ngắt trước khi writer chốt JSON; không tính là PASS. Kiểm tra cả timestamp và process đang chạy trước khi chạy lại.
7. **`status=FAIL` trên `failing_repo`:** đúng mục đích. **`status=FAIL` trên `sample_repo`** thì xem assertion, import, dependency và môi trường cụ thể.
8. **RAM/GPU cao vì Hugging Face:** bạn có thể đã chạy `smoke_hf_agent.py`/`smoke_model.py`, không phải hai lệnh M2 ở Bước 3–5. M2 baseline chỉ chạy Python/pytest, không load Qwen.
9. **MCP không có tool verification:** hiện `execution_server.py` chỉ có `health`; M2 chưa nối qua MCP. Gọi M2 bằng Python service/CLI ở milestone này.
10. **Repo đầu vào cần file trong `artifacts/` hoặc file rất lớn:** workspace hiện bỏ qua các thư mục sinh tự động và giới hạn mặc định 16 MiB/file, 256 MiB tổng. Nếu test phụ thuộc các file bị bỏ qua, baseline không đại diện đúng repo đó; cần review chính sách copy và giới hạn trước khi dùng trên benchmark lớn, không tự kết luận code sửa lỗi thất bại.

## 12. Điều gì còn phải làm tiếp?

- M3/leader review `docs/evidence_bundle_schema.md`, một JSON baseline thật và tên field/failure code trước khi coi contract là cố định.
- M1 tiếp tục task grounding/retrieval; sau đó M2 mới có thể dùng graph/test links để chọn test liên quan và đánh giá impact.
- M2 ở các tuần sau cần parse/apply patch **trên workspace tạm**, kiểm tra tests/type/lint/API/structural thật, so sánh baseline và sau patch, rồi cung cấp tool cho M3.
- M3 nối M2 service vào execution MCP và LangGraph repair loop; xây evaluation reproducible trên tập task được chốt. Full suite hiện tại không thay thế cho việc này.
- Với repository không tin cậy hoặc SWE-bench, cần container/OS sandbox và giới hạn tài nguyên nghiêm túc hơn; bản sao file hiện tại chỉ là cơ chế chống sửa nhầm nguồn.

**Kết luận:** Kết quả bàn giao của tôi là **nền tảng kiểm thử và evidence trước patch**, đã tích hợp vào `VGAR` và có dữ liệu test để đối chiếu. Đây là một bước cần thiết của hệ thống sửa lỗi, nhưng chưa phải hệ thống coding agent hoàn chỉnh.
