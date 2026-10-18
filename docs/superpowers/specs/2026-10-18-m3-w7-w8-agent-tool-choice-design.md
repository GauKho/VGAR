# M3 W7-W8 giai đoạn 2: agent tự điều phối MCP repair tools — thiết kế

Ngày: 2026-10-18 · Nhánh: `feature/m3-w7-w8-repair-loop` · Người làm: M3

## 1. Mục đích và lý do

Giai đoạn 1 (`docs/superpowers/specs/2026-10-17-m3-w7-w8-mcp-repair-loop-design.md`) đã có `vgar solve`: các node LangGraph gọi 4 MCP tools của server `repair` theo **thứ tự cố định**, chạy thật 3/3 PASS, trùng byte với golden.

Giai đoạn 2 là bước "model tự chọn tool" (proposal mục 9.1). Người dùng muốn **cho thấy agent tự điều phối các tools và kết thúc với status PASS**.

Bằng chứng từ spike (`m2-temp/spike_agent_choose_tools.py`, kết quả trong `results/agent-spike/`) quyết định hình dạng thiết kế:

- Khi model phải tự viết diff vào tham số tool call, format diff hỏng: thiếu tiền tố `-` ở dòng `def`, thụt lề thừa. Kết quả nhảy giữa các task, lần 2 pass B/C còn lần 5 pass A/B, và tốt nhất chỉ 2/3.
- Khi model viết diff dạng văn bản trả lời đơn lượt với V11, như luồng cố định và lần 6 của spike, diff đúng cả 3/3.

Vì vậy người dùng chọn **cách 1: agent chọn tool, nhưng diff do bộ sinh V11 đơn lượt của luồng cố định tạo ra**. Agent không bao giờ tự viết diff.

## 2. Mục tiêu, không phải mục tiêu, phản mục tiêu

**Mục tiêu (người dùng quyết định)**
- Một chế độ agent cho `vgar solve`, trong đó agent tự quyết định gọi tool nào, khi nào gọi, có sinh lại hay không và khi nào kết thúc.
- **Real:** A/B/C (`examples/m2/tasks/`) đều kết thúc PASS / ACCEPT. Kỳ vọng agent đi thẳng một mạch: context → sinh → áp → test → verify.
- **Fake:** kết thúc PASS **sau khi đi qua nhánh sinh lại**. Lần sinh đầu cố ý hỏng, lần sau đúng. Có test tự động.
- Khi sinh lại, feedback lỗi của lần trước được đưa vào prompt V11. Nếu không có feedback thì vô ích, vì giải mã greedy sẽ cho đúng cùng một diff.

**Không phải mục tiêu**
- Không cố ý làm hỏng lần đầu ở chế độ real. Người dùng đã đồng ý: nhánh sinh lại với model thật sẽ được kiểm chứng sau, trên task khó hơn.
- SWE-bench Verified. Đây là dự án riêng, nên làm sau bằng một bản chạy thử nhỏ.
- Retrieval sống từ graph (tuần 9–10). Vẫn dùng bundle M1 đã xuất sẵn.
- Agent tự viết diff hoặc tự viết feedback.
- Draft Methodology (đầu việc riêng).

**Phản mục tiêu — coi là thất bại dù chạy được**
- Sửa `repair_v11.txt` (SHA `ba6d1478…`), parser hoặc verification để agent pass.
- Lần sinh đầu của chế độ agent có `prompt.txt` khác golden (`tests/fixtures/m2/golden_v11/`).
- Đổi hành vi hoặc kết quả của `vgar solve` luồng cố định, `vgar repair`, `vgar run` hoặc `vgar chat`.
- Một run kết thúc mà không qua `verify_patch`, tức worktree không được dọn hoặc `run_record` không hoàn tất.
- Trace báo agent đã gọi một tool mà thực ra host gọi thay, hoặc ngược lại.
- Báo PASS khi `verify_patch` không trả ACCEPT.

## 3. Ràng buộc

- Giữ mọi ràng buộc của spec giai đoạn 1 §4: bảo mật, chỉ trusted fixtures, trạng thái lưu xuống đĩa.
- Model là Qwen3-4B, giải mã greedy. GPU hiện tại phải offload sang CPU/đĩa ngay cả khi chỉ có một bản model.
- Chạy real tốn GPU, và **người dùng tự chạy** các lần real; người làm không tự khởi chạy hay dừng chúng.
- Bài học từ spike: chỉnh prompt agent thì phải chạy lại trên **cả 3 task**, mỗi lần đổi một yếu tố.

## 4. Kiến trúc

```text
vgar solve --task T --mode fake|real --agent
  └─ agent (LangChain create_agent; model = Qwen in-process [real] | scripted [fake])
       tools (không tool nào có tham số do model điền):
         get_task_context ─MCP→ repair_get_task_context
         generate_patch   ─ client: bộ sinh V11 (§6) — giữ diff trong host
         apply_patch      ─MCP→ repair_apply_patch(run_dir, diff đã giữ, generation meta)
         run_relevant_tests ─MCP→ repair_run_relevant_tests
         verify_patch     ─MCP→ repair_verify_patch
```

- **Mỗi lần thử là một run riêng (quyết định của Claude, giống spike và giống spec giai đoạn 1 §5).** Server giữ nguyên quy tắc "áp patch đúng 1 lần mỗi run". Run mới ghi `supersedes_run_id` = run trước và `rerun_reason`. Cả hai trường này đã có trong `start_session`.
- **Agent không thấy `run_dir` hay đường dẫn.** Host giữ run hiện tại và tự gắn tham số, như spike đã làm.
- **`generate_patch` chạy phía client**, vì model nằm phía client. Cách chạy model ở chế độ real là quyết định mở, xem §6.

## 5. Các tool agent thấy

| Tool | Agent gọi khi | Host làm gì | Agent nhận lại |
|---|---|---|---|
| `get_task_context()` | đầu tiên, một lần | Mở run đầu (MCP `repair_get_task_context`) | Bản tóm tắt dạng văn bản: issue, các test đang fail, file được phép sửa. **Không gửi V11 cho agent** |
| `generate_patch()` | sau context; hoặc sau một lần thất bại nếu muốn thử lại | Nếu run hiện tại đã thất bại (áp hoặc test không PASS): nếu run chưa được verify thì host gọi `repair_verify_patch` để đóng nó (ghi là host gọi); nếu agent đã tự verify thì không gọi lại. Tiếp theo host tạo feedback (§7) và mở run mới với feedback. Sau đó sinh diff từ prompt của run hiện tại và giữ lại. Nếu đang giữ một diff chưa áp thì trả lỗi "hãy gọi apply_patch" và không sinh lại, vì greedy sẽ cho cùng diff | Tóm tắt: status, lần thử thứ mấy trên tối đa 3, các file mà diff động tới. Không trả nguyên diff (quyết định của Claude: giữ context agent ngắn) |
| `apply_patch()` | sau khi sinh | Gửi diff đã giữ cùng generation meta qua MCP | status, reason, changed_files; nếu lỗi thì thêm một dòng mô tả lỗi |
| `run_relevant_tests()` | sau khi áp thành công | MCP | PASS/FAIL và tên các test fail |
| `verify_patch()` | cuối cùng | MCP, đóng run hiện tại | status, recommendation |

- **Giới hạn:** tối đa 3 lần sinh mỗi task (giống spike). Có giới hạn số tool call (ví dụ 15) và giới hạn đệ quy. Khi hết lượt sinh, `generate_patch` trả lỗi "không còn lượt, hãy gọi verify_patch".
- **Lưới an toàn:** nếu agent dừng mà run hiện tại chưa được verify, host gọi `verify_patch` và ghi là host gọi.
- **Gọi sai thứ tự:** server từ chối như hiện nay, và lỗi được trả về cho agent dưới dạng văn bản.
- **Kết quả cuối của `solve --agent`** lấy từ lần `verify_patch` của **run cuối cùng**. Chỉ PASS khi recommendation là ACCEPT.
- **System prompt của agent** là một file mới trong `src/vgar/agents/prompts/` (tên do người làm chọn). Nó mô tả 5 tool, thứ tự thông thường, quyền sinh lại sau thất bại, và yêu cầu luôn kết thúc bằng `verify_patch`. Được chỉnh trong giới hạn §3.

## 6. Bộ sinh diff — làm cả hai phương án (người dùng quyết định)

Người dùng chọn **làm cả A và B** để có hai phương án so sánh. Chọn bằng cờ `vgar solve --agent --generator worker|agent`; mặc định `worker`, tức phương án A (quyết định của Claude: mặc định là đường đã được chứng minh).

Bộ sinh của M2 (`HFGenerator`, `src/vgar/models/huggingface/generator_hf.py`) mở **một tiến trình worker mới và nạp model từ snapshot đã pin cho mỗi lần sinh**. Nó cũng kiểm hash prompt, dùng `output_cap` 1.536 và giải mã greedy. Ở luồng cố định chỉ có worker này giữ model. Trong chế độ agent, agent lại giữ thêm một bản Qwen trong tiến trình client (`create_core_model`, `max_new_tokens` mặc định 512, không pin revision).

| | A. Dùng worker M2 cho `generate_patch` | B. Dùng chính model của agent |
|---|---|---|
| Kết quả diff | Đúng đường đã được 3/3 và trùng golden | Code sinh khác; phải chạy lại để biết có còn 3/3 hay không |
| Bộ nhớ | **Hai bản model cùng lúc** (agent + worker); GPU vốn đã offload, nên có thể chậm hẳn hoặc hết RAM | Một bản model |
| Thời gian | Thêm thời gian nạp worker mỗi lần sinh (khoảng 20 s+) | Không phải nạp thêm |
| Việc phải làm | Ít: gọi `build_generation` như node `generate` | Phải áp đúng thiết lập M2 (`output_cap` 1.536, pin revision, cùng chat template) lên model của agent |

Fake mode không bị ảnh hưởng bởi lựa chọn này: cả hai giá trị của `--generator` đều dùng bộ sinh fake (§8).

**Yêu cầu cho phương án B:**
- Sinh từ chính `prompt.messages` mà server trả về; không dựng lại prompt.
- Dùng thiết lập của policy/profile M2: số token sinh tối đa = `output_cap`, giải mã greedy, cùng `model_id` và revision đã pin trong `configs/m2/demo.json`. Nếu model của agent đang nạp không khớp revision đó thì báo lỗi rõ ràng, không âm thầm chạy.
- Chat template render ở phía client phải trùng `prompt.rendered`, tức cùng hash với `prompt_hash`, giống cách worker M2 kiểm `input_sha256`. Nếu khác thì `generate_patch` trả ERROR, không sinh.
- Generation meta gửi kèm `apply_patch` có cùng các khóa như phương án A (status, mode, finish_reason, truncated, input/output tokens, thời gian) và ghi rõ đường sinh là `agent_model`.
- Không yêu cầu `applied.diff` trùng golden. Kết quả được ghi lại và so sánh với A.

## 7. Feedback khi sinh lại

- `build_repair_prompt(..., feedback=...)` (`src/vgar/repair/prompt.py:34`) và `start_session(feedback=...)` đã hỗ trợ sẵn: dict 4 khóa `task_id`, `source_run_id`, `category`, `message`, tối đa 300 tokens, được nối vào cuối tin nhắn user. Template V11 không đổi.
- **Thay đổi server:** tool MCP `repair_get_task_context` nhận thêm tham số tùy chọn `feedback`, và nếu có mặt thì cả `supersedes_run_id`, `rerun_reason`, rồi chuyển xuống `start_session`. Khi không truyền, hành vi và `prompt.txt` giữ y hệt hiện nay.
- **Tạo feedback (code mới, phía host):** đọc `run_record.json` của run vừa thất bại.
  - `category` = `reason` của run, ví dụ `PATCH_PARSE_ERROR` hay `TEST_FAILED`.
  - `message` = một mô tả ngắn: lỗi parser/apply lấy từ `error_detail` (`message`, `parser_diagnostics`), hoặc tên các test fail và lỗi ngắn gọn.

  M2 từng có code tương tự trong `run_b_experiment.py`, nhưng code đó không được mang sang `src/vgar`. Nội dung chính xác của `message` do người làm chọn, miễn là văn bản do host tạo, không phải do agent.
- Bằng chứng hiện có: M2 từng chạy V11 kèm feedback với model thật đúng một lần (task B, feedback 131 tokens, PASS). Chưa có lần nào V11 tự thất bại rồi sửa được nhờ feedback.

## 8. Chế độ fake

- **Agent fake:** một chat model kịch bản (tiền lệ: `ScriptedToolModel` trong `scripts/smoke_w3_w4_agent.py`). Nó gọi tool theo luật cố định: context → sinh → áp → nếu áp hoặc test thất bại và còn lượt thì sinh lại → test → verify. Fake mode kiểm chứng **phần ống nối của host và nhánh sinh lại**, không kiểm chứng quyết định của model thật.
- **Bộ sinh fake:** lần 1 trả một diff hỏng (ví dụ thiếu tiền tố `-` ở dòng `def`, đúng lỗi spike đã gặp), lần 2 trả `tests/fixtures/m2/reference_patches/<task>.diff`.

## 9. Logging và bằng chứng

- Mỗi run giữ `run_record.json` như hiện nay: `mcp_calls`, prompt, generation và cả `prompt_feedback` ở run sinh lại.
- Thêm một **trace agent** cho mỗi lần chạy `solve --agent`, gồm:
  - thứ tự tool call, mỗi call ghi agent gọi hay host gọi, status và thời gian;
  - danh sách các `run_dir` và quan hệ supersedes giữa chúng;
  - các tin nhắn của agent.

  Định dạng và vị trí file do người làm chọn.
- Sau khi người dùng chạy real, kết quả A/B/C được ghi vào tài liệu nghiệm thu, giống giai đoạn 1.

## 10. Kiểm chứng

1. **Fake, nhánh sinh lại (test tự động):** cho A/B/C, run 1 kết thúc REVISE vì PATCH_PARSE_ERROR. Run 2 có `supersedes_run_id` = run 1 và `prompt_feedback` khác rỗng, kết thúc PASS/ACCEPT. Trace có đủ chuỗi tool và mọi run đều đã qua `verify_patch`.
2. **Prompt lần đầu trùng golden:** run 1 của chế độ agent có `prompt.txt` trùng byte với `tests/fixtures/m2/golden_v11/{A,B,C}`.
3. **Đường thẳng với raw golden (test tự động):** agent kịch bản cùng bộ sinh tiêm `raw_model_output.txt` của golden thì ra một run duy nhất, `applied.diff` trùng golden.
4. **Feedback:** prompt của run sinh lại chứa khối "Previous attempt feedback", tối đa 300 tokens, và phần còn lại trùng prompt lần đầu.
5. **Rào chắn (test tự động):**
   - hết lượt sinh thì không mở thêm run;
   - agent dừng sớm thì host verify và trace ghi host gọi;
   - gọi sai thứ tự thì agent nhận lỗi và run vẫn được verify.
6. **Không hồi quy:** golden test của `vgar repair` và của luồng cố định vẫn xanh; full suite không thêm failure nào.
7. **Phương án B (test tự động, không cần GPU):** với một model giả, render khác `prompt.rendered` thì `generate_patch` trả ERROR. Revision không khớp thì báo lỗi rõ ràng. Số token sinh tối đa bằng `output_cap`.
8. **Real (người dùng chạy):** `vgar solve --mode real --agent --generator worker` và `--generator agent` cho A/B/C, mục tiêu 3/3 PASS mỗi phương án. Ghi lại để so sánh: kết quả, chuỗi tool, thời gian mỗi task, và việc máy có chịu được hai bản model (phương án A) hay không. Nếu không đạt: ghi lại, chẩn đoán từ trace; chỉ chỉnh system prompt của agent trong giới hạn §3; không sửa V11, parser hay verification.

## 11. Quyết định của người dùng

1. §6: làm cả hai phương án A và B.
2. Giai đoạn 2 làm tiếp trên branch `feature/m3-w7-w8-repair-loop`; chưa merge/PR giai đoạn 1.

## 12. Để người làm tự quyết

- Vị trí code của chế độ agent: module mới trong `src/vgar/agents/`. Đặt sau cờ `--agent` của `vgar solve` là quyết định của Claude; người dùng chưa chốt.
- Định dạng văn bản tóm tắt trả về cho agent, và nội dung `message` của feedback.
- Giá trị cụ thể của giới hạn tool call và giới hạn đệ quy.
- Định dạng và vị trí trace agent.
- Cách agent kịch bản đọc kết quả tool để quyết định sinh lại.
