# Spec: log và trace của `vgar solve --agent` đọc được, khách quan (M3-W12)

Ngày 03/11/2026. Người duyệt hướng: người dùng (M3), duyệt 03/11 trong phiên chạy M3-X2b.
Liên quan: `docs/superpowers/specs/2026-11-03-m3-w12-design.md` (bảng M1, rủi ro R1–R8), `docs/m3_w12_agent_runbook.md`.

## 1. Vì sao

Ba lần chạy M3-X2b ngày 03/11 cho thấy log hiện tại không giúp người đọc hiểu chuyện gì xảy ra:

| # | Hiện tượng (run `results/m3/w12/agent/20261103T124141Z`) | Hậu quả |
|---|---|---|
| P1 | `input_tokens`, `token_budget`, `total_token_count`, `tokenizer_label` hiện `[REDACTED]` | Regex bí mật (`_SECRET_KEY`, `observability/instrumentation.py`) bắt chữ `token`; hội đồng tưởng nhóm che số liệu |
| P2 | `"status": "PASS"` bọc ngoài `"verdict": "ERROR"` | Không phân biệt gọi MCP thành công với kết quả task |
| P3 | `MCP_TOOL_START` in inventory 24 file, overlay, bundle hash (~3 KB/dòng) | Dữ liệu kiểm chứng lấn dữ liệu đọc |
| P4 | `generate_patch` và lượt model của agent không có dòng nào | Bước dài nhất (~15 phút) im lặng, người chạy tưởng treo |
| P5 | `VERIFICATION_INCOMPLETE`, `detail: null` | Nguyên nhân thật (sinh patch quá `generation_timeout`) bị mất |
| P6 | `"run_id": null` mọi dòng | Không nối log với `run_record.json` |
| P7 | `"tests": {"type": "dict"}` | Cắt độ sâu còn tên kiểu, vô nghĩa |
| P8 | `Processing request of type ListToolsRequest`, `torch_dtype is deprecated` | Log thư viện xen giữa sự kiện thật |

Ngoài ra hội đồng sẽ hỏi những câu log hiện tại không trả lời được: agent tự quyết hay làm theo gợi ý `NEXT`
của host; attempt dừng ở bước nào; lỗi là hạ tầng, protocol hay model; thời gian đi đâu; máy nào, model nằm
trên GPU bao nhiêu; code chạy có đúng commit không (clone X2b chạy commit `eded53cb` cộng file chưa commit).

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu:** ba tầng log, mỗi tầng một người đọc; sửa P1–P8; thêm sáu thông tin E1–E6 (§4); áp dụng theo
từng đường chạy (§6), gồm E3 và E6 cho batch runner A0–A3 trước khi freeze held-out.

**Không làm (đợt này):** E7 tóm tắt patch/test, E8 bảng tổng batch (§6, làm sau nếu kịp). Không thêm metric
vào bảng M1. Không in toàn văn prompt, diff, issue, output lệnh ra console hay trace.

**Phản mục tiêu:** log làm đổi hành vi repair (observability lỗi thì nuốt, như `emit` hiện nay); số trong log
khác số trong `run_record.json`/trace JSON (log chỉ đọc từ cùng nguồn, không tự tính lại); che bớt sự kiện
bất lợi (lượt agent làm theo `NEXT`, call bị host từ chối, lỗi hạ tầng đều phải hiện).

## 3. Ba tầng

### 3.1. Tầng 1 — console (người chạy, trình bày hội đồng)

Header, một dòng mỗi bước khi bước **bắt đầu** nếu bước có thể dài (`generate_patch`, `get_task_context`,
`run_relevant_tests`, `verify_patch`) và khi bước **kết thúc**, một dòng mỗi lượt model, khối kết quả. Mẫu
(dựng từ run seaborn 03/11; lý do timeout là suy luận, bản thật in lý do của generator):

```
== solve --agent · mwaskom__seaborn-3069 · A2 (graph) · exp d12a97b9 · commit eded53cb + dirty 4 files
   model Qwen3-4B-Instruct-2507@cdbee75f · generator worker · cap in 6000 / out 1536 tok · gen timeout 900 s
   machine GPU <tên> 6141 MiB · RAM 7 GiB · model placement GPU 71% / CPU 29%
   admission PASS · admission_hash 68964899 · bundle graph 6d719d1d
time      try  by     step                    result   time     detail
12:54:16  1/3  agent  get_task_context        PASS     36.7 s   run 20261103T125416…-ef3e99a9 · prompt 3903/6000 tok · 5 items (truncated) · 2 failing tests
12:54:52  1/3  agent  model turn 2            →generate_patch  23.1 s  in 825 / out 16 tok · NEXT generate_patch · followed
12:54:52  1/3  agent  generate_patch          running  …        timeout 900 s
13:10:42  1/3  agent  generate_patch          ERROR   950.4 s   GENERATION_TIMEOUT
13:11:42  1/3  host   verify_patch (close)    REJECT    0.7 s   no patch: generation failed
== RESULT FAILED · class MODEL · 3/3 attempts
   attempt 1/3: generated ✗ GENERATION_TIMEOUT → applied – → tests – → static – → verdict REJECT
   time 54 min = generation 47.5 (88%) · agent turns 1.2 · baseline/tests in Docker 2.2 · verify 0.1 · other 3.0
   agent: 9 calls · invalid 0 · followed NEXT 9/9 · audit 10/10
   trace results/m3/w12/agent/…/agent-traces/20261103T134842…-mwaskom__seaborn-3069.json
```

Cột `by` là `agent` (Qwen chọn) hoặc `host` (lưới an toàn: đóng attempt, mở lại với feedback). Ba dòng cũ
`[status]`, `[run]`, `[trace]` giữ nguyên nội dung và đứng cuối khối kết quả (runbook và người dùng đang dựa vào).

### 3.2. Tầng 2 — trace JSON từng task (bản ghi chính thức, nguồn bảng M1)

File vẫn là `agent-traces/<stamp>-<task>.json`. **Chỉ thêm trường**, giữ nguyên `calls`, `model_calls`, `runs`,
`messages`, `result`, `duration_ms` để `agent_metrics.py` và trace cũ (run trước 03/11) vẫn đọc được.
Thêm `schema: "vgar-agent-trace-v2"` và:

- `header`: task, variant, arm, experiment_id, model id@revision, generator path, caps, `generation_timeout`,
  `admission_hash`, `inventory_hash`, bundle hash (chỉ hash, không inventory), `code` (E6), `machine` (E5).
- Mỗi phần tử `calls` thêm `t` (UTC bắt đầu), `attempt`, `transport_status` (MCP gọi được: `OK`/`ERROR`)
  tách khỏi `status` (kết quả bước), `run_id`, `metrics` (dict nhỏ theo bước: token prompt, số item, số
  failing test, file bị sửa, số test PASS/FAIL), `next_hint` (dòng `NEXT` host trả lại).
- Mỗi phần tử `model_calls` thêm `next_hint` (gợi ý đang hiệu lực khi lượt bắt đầu), `followed` (E1).
- `attempts`: phễu E2; `failure_class` (E3); `time_breakdown` (E4).

### 3.3. Tầng 3 — debug

Dòng `[VGAR_TRACE] …` như hiện nay chỉ in khi `VGAR_TRACE=debug`; mặc định tắt. Audit JSONL của server
(`VGAR_MCP_AUDIT_LOG`) không đổi; audit completeness không phụ thuộc tầng này.

## 4. Thông tin thêm (E1–E6)

**E1. Agent làm theo gợi ý hay tự quyết.** `hint_tools` = tên tool xuất hiện trong dòng `NEXT` gần nhất
(`"generate_patch to retry with feedback, or verify_patch to finish"` → {generate_patch, verify_patch};
`stop` → {}). Lượt đầu: gợi ý là `get_task_context` (câu lệnh người dùng "Start with get_task_context").
`followed` = tool agent gọi ∈ `hint_tools`; lượt không gọi tool → `followed = null`, ghi `ended` (agent dừng).
Kết quả in `followed NEXT x/y`. Không diễn giải trong log; diễn giải thuộc Discussion.

**E2. Phễu từng attempt.** Mỗi attempt (một `run_id`): `generated` (✓/✗ + lý do), `applied` (✓/✗/–),
`failing_fixed` (k/n hoặc –), `relevant` (PASS/FAIL/–), `static` (✓/✗/–), `verdict` (ACCEPT/REJECT). Lấy từ
`calls` và `run_record.json` của attempt, cùng định nghĩa phễu W10 (F1–F8).

**E3. Nhãn lỗi.** Một nhãn cho kết cục task, theo bảng (mã lạ → `UNCLASSIFIED`, in mã gốc):

| Nhãn | Mã |
|---|---|
| `VERIFIED` | verdict `ACCEPT` |
| `INFRA` | `Docker operation incomplete`, `No such image`, `MCP_TRANSPORT_ERROR`, `INTERNAL_ERROR` không thuộc dòng dưới |
| `PROTOCOL` | `Full prompt exceeds …` (OVER_CAP), `ADMISSION_REJECTED`, `TASK_EXCLUDED`, `TASK_INPUT_MISSING`, `SELECTOR_OUTSIDE_SCOPE` |
| `MODEL` | `GENERATION_TIMEOUT`, `GENERATION_ERROR`, `PATCH_PARSE_ERROR`, `NO_OP`, `CONTEXT_NOT_FOUND`, `TEST_FAILED`, `STATIC_*`, verdict `REJECT` sau khi patch đã apply |

Nhãn của task = nhãn của attempt cuối có lý do khác `VERIFICATION_INCOMPLETE`; `VERIFICATION_INCOMPLETE`
do host đóng attempt hỏng thì mang lý do của bước hỏng trước nó (sửa P5). Chỉ `INFRA` được chạy lại (D22).

Bổ sung 04/11, sau lần chạy X2b `20261103T151652Z`: engine trả `VERIFICATION_INCOMPLETE` cho hai nguyên nhân
khác nhau, nên `refine_code` đọc `run_record.json` để tách ra:
- `stages.generation.truncated` → `OUTPUT_TRUNCATED`, tính là `MODEL`.
- Một lệnh có `timed_out: true` → `TOOL_TIMEOUT`, tính là `INFRA`.

Bằng chứng (đường dẫn stage và số giây) ghi vào `failure_class.evidence` và in thành dòng `cause` của khối kết quả.
Agent host, batch runner và chat dùng chung hàm này.

**E4. Thời gian đi đâu.** `generation` (tổng `generate_patch`), `agent_turns` (tổng `model_calls`),
`docker` (stage baseline, apply, tests, verification từ `run_record.json` các attempt), `other` = tổng − phần
trên (nạp model, khởi động MCP). In phút và phần trăm; các phần cộng đúng bằng `duration_ms`.

**E5. Máy và vị trí model.** Tên GPU, VRAM tổng (`torch.cuda.get_device_properties`), RAM tổng (`/proc/meminfo`,
Windows thì bỏ trống), phần trăm tham số trên GPU so với CPU/disk từ `hf_device_map` của model đã nạp
(agent model; generator worker chạy process riêng thì ghi `worker: không đo`). Lỗi đo → trường `null`,
không làm hỏng run.

**E6. Trạng thái code.** `git rev-parse HEAD`, danh sách file trong `git status --porcelain` (không tính
`results/`) kèm sha256 12 ký tự. Console: `commit <7> + dirty <n> files`; trace: danh sách đầy đủ. Không có
git → `null`. `commit.txt` trong runbook đổi sang lệnh ghi cả hai.

## 5. Sửa lỗi P1–P8

- **P1:** `_SECRET_KEY` không bắt khóa đếm token: `input_tokens`, `output_tokens`, `*_tokens`,
  `total_token_count`, `token_budget`, `token_budget_unit`, `tokenizer_label`. Vẫn che `token`, `access_token`,
  `api_key`, `authorization`, `password`, `secret`, `credential`. Test cả hai chiều trong `tests/test_redaction.py`.
- **P2, P3, P7:** console và trace v2 chỉ dùng `metrics` đã chọn (§3.2); `[VGAR_TRACE]` giữ nguyên ở chế độ debug.
- **P4:** dòng `running` khi bắt đầu bước dài; dòng lượt model từ callback `ModelTurns`.
- **P5:** E3.
- **P6:** host đặt `run_id` của attempt hiện tại cho mọi dòng console và `calls`; `emit` debug dùng
  `trace_run(run_id)` sẵn có.
- **P8:** logger của server MCP (`mcp.server`) mức WARNING trong process server; cảnh báo `torch_dtype`
  của transformers lọc riêng khi nạp agent model. Thanh tiến trình nạp checkpoint giữ.

## 6. Phạm vi theo đường chạy

Khảo sát code 03/11: P1–P8 sinh ra từ `observability/instrumentation.py` (chung cho mọi đường qua MCP) và từ host
agent (`agents/tool_agent.py`). Batch runner không qua MCP nên không mắc P1–P8, nhưng thiếu E3 và E6.

| Đường chạy | File chính | Dùng cho | Nhận gì trong đợt này |
|---|---|---|---|
| `solve --agent` | `agents/tool_agent.py`, `cli.py` | X2b, bảng M1 | Đủ §3–§5 |
| `vgar chat` | `agents/chat.py` | Demo bảo vệ | Sửa chung (6.1) + console §3.1 dùng chung renderer (6.3) |
| Batch runner A0–A3 | `evaluation/repair/runner.py`, `launch.py`, `aggregate.py` | Kết quả chính W10/W12/held-out | E6 + E3 (6.2) |
| `solve` thường (workflow) | `agents/workflow.py`, `agents/nodes/mcp_repair.py` | Pilot, smoke | Chỉ sửa chung (6.1) |
| Graph trace | `observability/graph_trace.py` | Debug retrieval | Không đổi (opt-in JSONL, đã có `run_id`) |

### 6.1. Sửa chung (một lần, mọi đường qua MCP)

P1 (regex che token), P6 (`run_id` trong `emit`), P8 (log thư viện) sửa ở `instrumentation.py` và ở server MCP,
nên `solve`, `chat`, `solve --agent` cùng hết lỗi. Chế độ debug §3.3 cũng áp dụng chung.

### 6.2. Batch runner A0–A3 (phải xong trước khi freeze protocol held-out)

- **E6.** Hiện `experiment.json` và `run_record.json` chỉ ghi `base_commit` của repo task, **không ghi commit
  code VGAR**. Mỗi attempt record của runner ghi `code` (HEAD + file chưa commit kèm sha, như §4 E6).
  `status` in commit của attempt; `aggregate` báo `MIXED_CODE` khi các attempt trong cùng experiment chạy trên
  code khác nhau, và ghi danh sách commit vào `aggregate.json`. Không chặn run (ràng buộc chặn thuộc protocol
  freeze, M3-W12-2, ngoài spec này).
- **E3.** Cột `class` (`VERIFIED`/`INFRA`/`PROTOCOL`/`MODEL`/`UNCLASSIFIED`) trong bảng `status` và trong
  `aggregate.md`/`aggregate.json`, dùng **cùng một hàm** phân loại với host agent (§4 E3), đặt trong
  `src/vgar/evaluation/failure_class.py`. Quy tắc chạy lại D22 tra cột này thay vì phân loại tay.
- Runner thuộc code M2: PR cần M2 review (`docs/status/w11_w12_assignment.md`, quyền sở hữu `configs/m2/`,
  `src/vgar/repair/`).

### 6.3. `vgar chat`

`chat.py` gọi `repair_get_task_context`/`repair_verify_patch` qua MCP như host agent. Console dùng chung renderer
`agents/trace_report.py` (header, dòng bước, khối kết quả, nhãn E3, thời gian E4, máy E5, code E6). E1 tính như
§4 nếu chat có dòng `NEXT`; không có thì bỏ trống, không suy diễn. Hợp nhất chat với `AgentRepairHost`
(F1–F7, W11) không thuộc spec này.

### 6.4. `solve` thường

Chỉ nhận 6.1. Đường này không sinh số cho paper; không thêm console mới.

## 7. Làm sau (nếu kịp)

- **E7.** Tóm tắt patch (file, +/− dòng, trong `allowed_source_paths`, sha diff) và test (failing k/n, relevant).
- **E8.** `$OUT/summary.md`: mỗi task một dòng (kết cục, nhãn, attempt, thời gian, link trace/run_record).

## 8. Ràng buộc

- Không đổi logic repair, quyết định của host, prompt, policy; `ruff`/test hiện có vẫn xanh.
- Trace v2 tương thích ngược: `agent_metrics.py` đọc được cả v1 lẫn v2; test với một trace v1 thật
  (`tests/fixtures`) và một trace v2.
- Không chép code mới vào `~/vgar-x2b` khi một run đang chạy. Run X2b đang chạy giữ log cũ; số bảng M1 vẫn
  tính từ trace v1.
- File chạm tới: `observability/instrumentation.py`, `agents/tool_agent.py`, `cli.py` (phần `--agent`),
  server MCP repair (mức log), `evaluation/agent_metrics.py` (đọc v2), runbook X2b; một module mới cho
  console renderer (`src/vgar/agents/trace_report.py`); hàm nhãn lỗi chung (`src/vgar/evaluation/failure_class.py`);
  `agents/chat.py` (console); `evaluation/repair/runner.py`, `aggregate.py` (E6, E3, cần M2 review).
- Test chạy không cần GPU/Docker: renderer và nhãn lỗi kiểm trên trace cố định; E5 kiểm với model giả có
  `hf_device_map`.

## 9. Quyết định của người viết spec (người dùng kiểm khi đọc)

- Trace v2 chỉ thêm trường, không đổi tên trường cũ, để không phải chạy lại hay chuyển đổi trace đã có.
- `followed` tính theo tập tool trong `NEXT`, không theo tool đầu tiên; gợi ý có hai lựa chọn thì chọn cái nào
  cũng tính là theo.
- `VERIFICATION_INCOMPLETE` do host đóng không được tính là nguyên nhân; nhãn lấy từ bước hỏng trước nó.
- Bảng nhãn E3 xếp `INTERNAL_ERROR` vào `INFRA` trừ thông điệp OVER_CAP; đúng với 3 lần chạy 03/11, có thể
  sai với mã mới — mã lạ hiện `UNCLASSIFIED` thay vì đoán.
- Mặc định tắt `[VGAR_TRACE]`: người đang dựa vào dòng này để debug phải đặt `VGAR_TRACE=debug`.
- E6 cho runner ghi ở **từng attempt record**, không chỉ `experiment.json`, vì `experiment.json` ghi một lần ở
  lần chạy đầu còn rerun (D22) có thể diễn ra trên code khác; `MIXED_CODE` chỉ cảnh báo, không chặn.
- Hàm nhãn E3 đặt ở `evaluation/`, dùng chung cho runner và host agent, để hai đường không phân loại khác nhau.
