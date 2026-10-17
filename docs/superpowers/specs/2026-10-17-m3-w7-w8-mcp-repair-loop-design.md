# M3 W7-W8: vòng repair cố định gọi MCP tools — thiết kế

Ngày: 2026-10-17 · Nhánh: `feature/m3-w7-w8-repair-loop` · Người làm: M3

## 1. Mục đích và lý do

Hoàn thành phần **M3 tuần 7–8** của `D:\kltn\project_plan_16_weeks.md` (dòng 219–226):

- Expose MCP tools `apply_patch`, `run_relevant_tests`, `verify_patch` bản cơ bản.
- LangChain loop một vòng: retrieve → generate → patch → verify.
- Log prompt version, model configuration, tool calls, latency, token usage.
- Deliverable: demo end-to-end cho 3–5 task nhỏ.

Hiện `vgar solve` (LangGraph `initialize → repair_run → finalize|failed`) đã chạy được chuỗi này, nhưng mọi bước nằm trong process. Vì vậy `run_record.mcp_calls` luôn rỗng (`mcp_scope=standalone_not_executed`), và M2 chưa có MCP tool nào. Người dùng chọn: **vòng lặp phải thật sự gọi MCP tools**, để kiến trúc đúng như proposal (agent → MCP server → sandbox) và log thấy từng tool call.

## 2. Các giai đoạn (người dùng quyết định)

1. **Spec này — luồng cố định:** các node LangGraph gọi MCP tools theo thứ tự cố định; model chỉ viết diff từ prompt V11.
2. **Sau — model tự chọn tool:** agent được giao MCP tools và tự quyết định gọi tool nào (proposal mục 9.1). Phần này có spec riêng, không nằm trong spec này. Server và tools trong spec này phải dùng lại được cho giai đoạn đó.

## 3. Mục tiêu, không phải mục tiêu, phản mục tiêu

**Mục tiêu**
- Một MCP server mới tên `repair` với 4 tools (§5).
- `vgar solve --task T [--mode fake|real]` chạy luồng cố định qua MCP (§6).
- `run_record.json` của mỗi run ghi được `mcp_calls` (§7), cùng các thông tin đã có: prompt version, model, token, thời gian.
- Demo end-to-end trên 3 task A/B/C (`examples/m2/tasks/`). Con số 3 là mức tối thiểu của plan, không thêm task.

**Không phải mục tiêu**
- Model tự chọn tool (giai đoạn 2).
- Retrieval sống từ graph. Bước retrieve dùng **bundle M1 đã xuất sẵn** do người dùng chọn; retrieval sống thuộc tuần 9–10.
- Vòng thử lại khi verify fail (`REVISE`).
- Chạy trên task ngoài `configs/m2/trusted_fixtures.json`.
- Draft Methodology (một đầu việc M3 tuần 7–8, làm riêng dưới dạng tài liệu).
- Thay đổi `vgar run`/`vgar chat` hoặc các tool exact-edit `repository_apply_patch`/`execution_run_pytest`.

**Phản mục tiêu — coi là thất bại dù chạy được**
- Prompt V11 hoặc `applied.diff` của fake A/B/C qua MCP khác golden (`tests/fixtures/m2/golden_v11/`).
- Có hai bản code pipeline song song: một cho `vgar repair`, một cho MCP tools.
- Tool ghi ra ngoài worktree riêng, hoặc chạy được trên fixture chưa đăng ký.
- Một run để lại worktree không được dọn, hoặc `run_record` thiếu bước, trên bất kỳ nhánh lỗi nào.
- `mcp_calls` ghi lại điều không thực sự đi qua MCP.

## 4. Ràng buộc

- Prompt V11, parser và apply giữ nguyên hành vi. Golden test hiện có vẫn phải xanh.
- `vgar repair` giữ nguyên CLI và kết quả: vẫn là đường chạy trong process của M2. **"Kết quả" gồm** `status`, `reason`, evidence bundle (cả `recommendation`), artifacts (`prompt.txt`, `raw_model_output.txt`, `candidate.diff`, `transport.diff`, `applied.diff`), **tên các stage** trong `run_record.stages` và các khóa của từng stage. Thứ tự lệnh bên trong được giữ như hiện nay. Riêng stage `verification` được ghi làm hai lượt: tool test ghi phần collection/tests, tool verify ghi phần static/assessment. Kết quả cuối vẫn là một stage `verification` với cùng các khóa, và static checks vẫn bị bỏ qua khi collection lỗi (đúng như `verify_patch` hiện nay). (Quyết định của Claude.)
- MCP client hiện dùng `MultiServerMCPClient` với `get_tools()`. Thư viện `langchain_mcp_adapters` ghi rõ "A new session will be created for each tool call" (`client.py` dòng 175), nên **mỗi tool call có thể là một lần khởi động server mới**. Mọi trạng thái giữa các tool phải lưu xuống đĩa.
- Bảo mật theo proposal mục 10.5:
  - path jail: chỉ fixture trong `trusted_fixtures.json`;
  - tool ghi file tách khỏi tool đọc;
  - allowlist lệnh: dùng `NativeExecutor` của M2;
  - timeout cho từng tool và cho cả run;
  - không đưa secret vào env: dùng `_child_env` hiện có;
  - audit log mọi tool call: dùng `instrument_mcp_tool` hiện có.
- Dùng lại code `src/vgar/repair`. Không viết lại logic M2.

## 5. MCP server `repair` (quyết định: server mới, tách khỏi `repository`/`execution`)

File `src/vgar/mcp/servers/repair_server.py`, chạy bằng `python -m vgar.mcp.servers.repair_server`. Client thêm tiền tố tên server, nên tên tool là `repair_<tên>`.

| Tool | Đọc/Ghi | Input | Làm gì | Trả về |
|---|---|---|---|---|
| `repair_get_task_context` | ghi (tạo worktree) | `task_path`, `mode`, `work_root` | Bắt đầu run: kiểm trusted fixture → nhận handoff M1 → tạo worktree riêng → chạy baseline (quyết định: baseline nằm ở bước này vì prompt V11 cần `baseline.failed_cases`, xem `repair/prompt.py:66-71`) | `run_id`, `worktree_id`, context M1 đã kiểm, `failed_cases`, đủ dữ liệu để client dựng prompt V11 |
| `repair_apply_patch` | ghi (chỉ trong worktree) | `run_id`, `diff`, siêu dữ liệu generation | Parse unified diff theo `PatchPolicy` → apply vào worktree | `status`, `changed_files`, lý do nếu FAIL |
| `repair_run_relevant_tests` | đọc + chạy lệnh | `run_id` | Chọn test liên quan → chạy | `failing_tests`, `relevant_tests` (dạng `TestGroupResult`), trạng thái |
| `repair_verify_patch` | ghi (dọn worktree) | `run_id` | Static checks + đánh giá cuối → kiểm source gốc không đổi → **dọn worktree** → ghi `evidence_bundle.json` và kết thúc run | Evidence bundle (có `recommendation`) và đường dẫn `run_record.json` |

- **Trạng thái lưu xuống đĩa (quyết định):** mỗi run có một thư mục, chính là thư mục run M2 hiện nay (`run_record.json`, `prompt.txt`, …). Thư mục này giữ thêm đủ trạng thái để một process server mới dựng lại được worktree lease, baseline, task và deadline.
- **Một bản code (quyết định):** tách `run_repair` thành các hàm bước dùng chung. `run_repair` (cho `vgar repair`) gọi các bước trong process. Các tool gọi đúng các hàm đó qua ranh giới process.
- **`repair_verify_patch` là chốt kết thúc duy nhất.** Mọi nhánh của luồng sau khi `repair_get_task_context` thành công đều phải gọi nó: generate lỗi, apply FAIL, test lỗi. Như vậy worktree luôn được dọn, và `run_record`/bundle luôn được hoàn tất với `recommendation` đúng (REVISE/REJECT). Client gọi nó trong `finally` khi đã có `run_id`.
- **Khi chính `repair_get_task_context` lỗi** (ví dụ task chưa đăng ký, handoff sai, baseline không đạt): tool tự dọn worktree nếu đã tạo, tự kết thúc run với `status=ERROR` giống `vgar repair` hiện nay, ghi `mcp_calls` của chính nó, rồi trả về `status=ERROR`, `reason`, `recommendation="REJECT"` và `run_record_path`. Không có bundle, vì chưa có worktree lease; điều này giống `vgar repair` hiện nay. `solve` đi thẳng tới `failed` và báo `run_record_path` đó. (Quyết định của Claude.)
- **Vị trí worktree:** client truyền `work_root`, tức thư mục tạm `work_dir` mà `run_task` đang sở hữu. Server chỉ tạo worktree bên trong thư mục đó. Nhờ vậy cơ chế `rmtree` hiện có vẫn là lưới an toàn. Nếu cả process client chết giữa chừng thì worktree có thể sót lại, và đây cũng chính là giới hạn của `vgar solve` hiện nay. Tuần 7–8 không làm thêm bộ dọn rác hay reaper. (Quyết định của Claude.)
- **Thứ tự gọi tool trong một run (giai đoạn 1):** server kiểm thứ tự chặt `get_task_context → apply_patch (đúng 1 lần) → run_relevant_tests → verify_patch`, và từ chối gọi sai thứ tự bằng một lỗi rõ ràng. `run_relevant_tests` có thể bị bỏ qua (khi apply không PASS); `verify_patch` thì luôn được gọi. Siêu dữ liệu generation trên `apply_patch` là **tùy chọn**. Ở giai đoạn 2 (model tự chọn tool), mỗi lần thử là một run mới, giống thiết kế thử lại của M2 (`supersedes_run_id`), nên không cần nhiều patch trong một run. (Quyết định của Claude.)
- Phần ghi `prompt.txt`, `raw_model_output.txt` và stage `generation` vào cùng `run_record` vẫn giống hệt `vgar repair` hiện nay. Cơ chế cụ thể để làm vậy do người làm chọn (§9).

## 6. Luồng `vgar solve` (luồng cố định)

```text
START → initialize
      → retrieve  : MCP repair_get_task_context(task_path, mode)
      → generate  : trong process — build_repair_prompt V11 + FakeGenerator/HFGenerator
      → apply     : MCP repair_apply_patch(run_id, diff, generation metadata)
      → test      : MCP repair_run_relevant_tests(run_id)       (bỏ qua nếu apply không PASS)
      → verify    : MCP repair_verify_patch(run_id)             (luôn chạy nếu đã có run_id)
      → finalize | failed → END
```

- Client MCP cho `solve` chỉ nối server `repair`. Quyết định: `SERVER_NAMES` mặc định của `vgar run/chat` không đổi, để agent exact-edit không nhìn thấy tools mới.
- Trạng thái và kết quả cuối của `solve` giữ như hiện nay: `status`, `repair_status`, `failure_reason`, `evidence`, `run_record_path`. Riêng `evidence` lấy từ kết quả của `repair_verify_patch`.
- Không có cạnh thử lại. Mỗi run đúng một lần generate.

## 7. Logging

`run_record.json` của run (do server ghi):
- `mcp_scope`: `"repair_server"` khi run đi qua MCP; `vgar repair` giữ `"standalone_not_executed"`.
- `mcp_calls`: danh sách theo thứ tự, mỗi phần tử gồm `tool`, `input_sha256`, `started_utc`, `duration_ms`, `status`. Không ghi nguyên input; `diff` đã nằm trong artifact riêng.
- Giữ nguyên các mục đã có: `policy.prompt_version`, `model`, `stages.prompt.input_tokens`, `stages.generation.output_tokens`/`duration_ms`, thời gian từng stage.

Audit JSONL/`emit` của `instrument_mcp_tool` vẫn ghi như với các server khác.

## 8. Kiểm chứng

1. **Golden qua MCP:** test chạy luồng `solve` qua MCP thật cho A/B/C. Test **tiêm `raw_model_output.txt` của golden** qua `Runtime.generator`, giống cách golden test hiện có tiêm `FakeGenerator`. Vì `reference_patches` khác raw output của golden, lệnh CLI `--mode fake` thuần không bị đòi trùng byte. Kết quả `prompt.txt` và `applied.diff` phải trùng byte với `tests/fixtures/m2/golden_v11/{A,B,C}`, và `run_record.mcp_calls` phải có đủ 4 tool theo đúng thứ tự. CLI `vgar solve --mode fake` chỉ cần PASS cả ba. (Quyết định của Claude.)
2. Golden test hiện có của `vgar repair` vẫn xanh. Đây là bằng chứng hai đường dùng chung code.
3. Test cho từng nhánh lỗi: diff không hợp lệ (bundle `REVISE`), generator lỗi (bundle `REJECT`), task chưa đăng ký (`repair_get_task_context` trả `REJECT`, không có bundle). Mỗi nhánh phải kết thúc `FAILED`, worktree được dọn và `run_record` hoàn tất.
4. Test gọi tool sai thứ tự bị từ chối với lỗi rõ ràng.
5. Test rằng trạng thái sống sót qua ranh giới process: mỗi tool chạy trong một process server mới mà vẫn đúng.
6. Full suite không thêm failure nào so với hiện tại (681 pass, 1 fail legacy `test_hf_model`).
7. Cuối cùng chạy thật `vgar solve --mode real` cho A/B/C và ghi lại kết quả. Nếu không PASS thì ghi lại, điều tra một lần và báo người dùng; không sửa prompt hay parser.

## 9. Để người làm tự quyết

- Định dạng file trạng thái trong thư mục run, và cách dựng lại `WorkspaceLease` từ đó.
- Cách đưa `prompt.txt`, raw output và stage `generation` vào `run_record` khi generate chạy phía client. Ví dụ: gửi kèm trong `repair_apply_patch`, hoặc client ghi trực tiếp vào thư mục run. Điều kiện: kết quả trên đĩa giống `vgar repair`.
- Tên các hàm bước sau khi tách `run_repair`.
- Có dùng một MCP session dùng chung cho cả run hay không. Không bắt buộc, vì trạng thái đã nằm trên đĩa.
- Cách đo `duration_ms` của từng tool call: phía client hay phía server.
