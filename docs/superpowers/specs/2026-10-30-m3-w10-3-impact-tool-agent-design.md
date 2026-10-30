# M3-W10-3: Qwen tự gọi tool `analyze_patch_impact` trong vòng retry của `vgar solve --agent`

Ngày: 30/10/2026 · Người làm: M3 · Nguồn: `VGAR_W9_W16_Deliverables (1).md` v2, M3-W10-3 (và phần còn treo của M3-W10-4)
Trạng thái: đã chốt với người dùng 30/10, chờ plan. Chưa viết code.

## 1. Bối cảnh và lý do

M3-W10-3 đã có tool MCP `analyze_patch_impact` trong `src/vgar/mcp/servers/graph_server.py` (commit `82652b47`). Tool trả envelope chuẩn có `ImpactReport`, ghi audit (chỉ hash của diff) và trả lỗi theo schema. `tests/test_w10_impact_mcp.py` 8/8 PASS.

Còn thiếu: **chưa agent nào gọi tool này**. Test hiện tại gọi hàm Python trực tiếp, còn test stdio chỉ kiểm tool có trong danh sách. Vòng retry của `tool_agent` (`src/vgar/agents/tool_agent.py`) chỉ nối server `repair`. `build_feedback(record, impact=)` (M3-W10-4) đã nhận được impact nhưng không ai truyền vào (`docs/status/m3.md`: "Vòng retry của `tool_agent` chưa gọi tool impact: chuyển W11").

Người dùng muốn hoàn tất W10 bằng cách để **Qwen tự chọn gọi** tool impact trong vòng retry đã có, qua MCP stdio thật, và có test chứng minh, kể cả với mô hình thật.

## 2. Mục tiêu, ngoài phạm vi, điều không được xảy ra

**Mục tiêu**
- Agent của `vgar solve --agent` có thêm tool thứ 6 là `analyze_patch_impact`, do Qwen tự quyết định có gọi hay không.
- Mỗi lần gọi đi qua MCP stdio tới server `graph` (`graph_analyze_patch_impact`), dùng graph SQLite thật của repo task.
- Kết quả impact hiện ra trong câu trả lời của tool cho Qwen, đồng thời được đưa vào feedback của lần `generate_patch` tiếp theo.
- Có test tự động (fake, chạy được trong CI) và một lần kiểm tra bằng Qwen3-4B thật (người dùng chạy trên GPU).

**Ngoài phạm vi**
- Claude Code hoặc agent bên ngoài, đóng gói package MCP.
- Workflow cố định (`agents/workflow.py`, `nodes/mcp_repair.py`) và runner ablation A0–A2: không đổi, nên không ảnh hưởng fairness hay các số W10 đã chạy.
- Sửa thuật toán impact (`graph/impact.py`) hoặc độ nhiễu IMPORTS ở hop 2.
- Tối ưu prompt để Qwen gọi tool nhiều hơn.

**Không được xảy ra**
- Host tự gọi impact thay cho Qwen. Trace phải phản ánh đúng lựa chọn của Qwen.
- Qwen phải viết diff, đường dẫn hay `graph_version`. Tool không có tham số, giống 5 tool cũ.
- Diff bị ghi vào audit hay trace dưới dạng nội dung (giữ quy tắc hash của graph server).
- Lỗi graph làm hỏng vòng retry. Nếu impact lỗi, retry vẫn chạy, chỉ là không có dòng impact.
- Repo nguồn của task bị thay đổi (kiểm tra `fingerprint_source` hiện có vẫn phải PASS).

## 3. Hành vi đã chốt

### 3.1 Tool `analyze_patch_impact` cho agent
- Không có tham số (`NoArgs`). Mô tả ngắn, ví dụ: "After an applied patch failed its tests, show which callers, importers and tests depend on the code it changed. Optional; call before generate_patch."
- Chỉ được gọi khi **lần thử hiện tại đã apply thành công rồi thất bại**: `run["applied"]` là `True` và `run["failed"]` là `True`. Lý do: `diff_to_nodes` dùng parser strict nên diff không parse được (`PATCH_PARSE_ERROR`) sẽ luôn trả `INVALID_ARGUMENT`.
- Mỗi lần thử chỉ gọi tối đa một lần.
- Gọi sai lúc (chưa có task, lần thử chưa thất bại, patch chưa apply, đã gọi rồi): host từ chối bằng `_refuse(...)` (`HOST_REFUSED`), giống các tool khác.
- Host giữ diff **đã apply** của lần thử hiện tại. Hiện tại `apply_patch` đặt `self.diff = None` nên cần lưu riêng. Host cũng giữ `graph_version` của snapshot.
- Câu trả lời theo format `_reply` hiện có (`STATUS`, các dòng field, `NEXT`), ngắn (khoảng ≤ 400 ký tự cho phần field). Gồm số node bị ảnh hưởng, số test, trạng thái `COMPLETE`/`PARTIAL` và vài tên tiêu biểu. Nên dùng lại logic của `_impact_message` trong `feedback.py`, không viết lại.
- `NEXT` sau tool impact giữ logic `_next()` hiện có (retry bằng `generate_patch` hoặc `verify_patch`).
- Tool `ERROR` (ví dụ `GRAPH_NOT_READY`, `INVALID_ARGUMENT`, lỗi transport): trả `STATUS: ERROR` với `REASON`/`DETAIL`, không lưu impact, retry vẫn được.
- Mỗi lần gọi được ghi vào `host.trace` qua `_log("analyze_patch_impact", "agent", status, reason, start)`.

### 3.2 Đưa impact vào feedback
- Nếu lần thử vừa thất bại có impact `PASS`, lần `generate_patch` kế tiếp gọi `build_feedback(self._record(), impact=<ImpactReport data>)`. Nếu không có thì gọi như hiện nay.
- Impact gắn với lần thử nó phân tích. Không mang sang lần thử sau nữa.

### 3.3 Graph cho task
- Lần đầu tool impact được gọi trong một solve, host index **repo nguồn của task** (`task.source_repo`) vào một file SQLite trong `work_dir` của solve. Dùng lại `index_repo`/`PythonGraphBuilder` và lấy `graph_version` từ document.
- Host mở một client MCP stdio chỉ nối server `graph`, với `VGAR_GRAPH_BACKEND=sqlite`, `VGAR_GRAPH_DATABASE=<db đó>`, `VGAR_REPOSITORY_ROOT=<task.source_repo>`. Không sửa `os.environ` của tiến trình cha. Nếu `create_mcp_client` chưa truyền được biến cần thiết thì sửa tối thiểu trong `src/vgar/mcp/client.py` (M3 sở hữu).
- Client graph được tạo một lần mỗi solve và tái dùng, giống `Runtime.repair_tools()`.
- Graph và db nằm trong `work_dir` nên được dọn cùng `cleanup_work_dir`.

### 3.4 Prompt hệ thống
`src/vgar/agents/prompts/repair_agent.md` thêm tool vào danh sách, kèm một câu về thời điểm dùng: sau khi `run_relevant_tests` báo FAIL và còn lượt, có thể gọi `analyze_patch_impact` trước `generate_patch`. Đây là tool tùy chọn. Thứ tự "Usual order" giữ nguyên.

### 3.5 Agent giả theo kịch bản
`ScriptedRepairAgent` (`agents/fakes.py`) gọi `analyze_patch_impact` sau khi `run_relevant_tests` thất bại và còn lượt, rồi mới `generate_patch`. Từ câu trả lời của tool impact (PASS hay ERROR), agent giả đi tiếp `generate_patch` nếu còn lượt. Fake mode của `vgar solve --agent` vì vậy luôn đi qua tool mới.

Hệ quả cần xử lý: fake mode hiện dùng `break_diff(reference)` (lỗi parse, không apply được) làm lần thử đầu, nên sẽ không bao giờ tới được tool impact. Cần thêm **patch sai nhưng hợp lệ** (apply được, test vẫn FAIL) cho 3 task fixture `single_file_login`, `multi_file_invoice`, `missing_links`. Đặt ở `tests/fixtures/m2/wrong_patches/<task>.diff`. Các test hiện có dựa vào `break_diff` phải giữ nguyên hành vi. Cách đổi fake mode mặc định (dùng patch sai thay `break_diff`, hay chỉ dùng trong test mới) để builder quyết, miễn là test cũ vẫn PASS.

### 3.6 Ngân sách tool call
`MAX_TOOL_CALLS = 15`. Kịch bản xấu nhất (3 lần thử, mỗi lần thất bại có gọi impact): 1 + 3×3 + 2 + 1 = 13 lần gọi, vẫn dưới 15. Không đổi hằng số.

## 4. Kiểm chứng

### 4.1 Test tự động (CI, không GPU)
1. **End-to-end fake qua stdio thật:** solve `single_file_login` với agent giả. Lần 1 dùng patch sai hợp lệ, lần 2 dùng reference. Kiểm tra:
   - trace có `analyze_patch_impact` với `by == "agent"`, `status == "PASS"`;
   - prompt hoặc feedback của run thứ 2 có dòng `"Static graph impact of the previous patch"`;
   - kết quả cuối `ACCEPT`, repo nguồn không đổi.
2. **Từ chối:** gọi trước `get_task_context`, sau một lần thử chưa thất bại, sau lần apply bị `PATCH_PARSE_ERROR`, gọi hai lần trong cùng một lần thử. Mỗi trường hợp trả `HOST_REFUSED` và không mở server graph khi không cần.
3. **Lỗi graph:** tool graph trả `ERROR` (ví dụ giả lập `GRAPH_NOT_READY`). Câu trả lời là `STATUS: ERROR`, retry vẫn chạy, feedback không có dòng impact.
4. **Không có impact thì feedback giữ nguyên:** Qwen (agent giả) bỏ qua tool impact. Feedback giống hệt hiện nay (test `SequenceAgent`).
5. Toàn bộ suite hiện có vẫn PASS (`tests/unit/test_agent_solve.py`, `test_agent_tools.py`, `test_agent_feedback.py`, `tests/test_w10_impact_mcp.py`, …).

### 4.2 Kiểm tra bằng mô hình thật (người dùng chạy trên GPU)
- Agent: Qwen3-4B thật (`default_agent_model`, real mode). 3 task: `examples/m2/tasks/{single_file_login,multi_file_invoice,missing_links}.json`.
- Ép lần thử đầu thất bại: generator theo kịch bản trả patch sai hợp lệ ở lần 1, reference ở các lần sau. Như vậy mọi task đều tới điểm Qwen phải quyết định có gọi impact không, và phần đo không phụ thuộc chất lượng generator.
- Một script (đặt ở `scripts/`) chạy 3 task tuần tự, nạp model một lần, rồi in bảng từ trace. Bảng gồm: task, Qwen có gọi impact không, `STATUS` của tool, feedback lần 2 có dòng impact không, recommendation cuối, số tool call, thời gian. Ghi bảng ra JSON trong `results/`.
- Mình chỉ đưa lệnh, người dùng tự chạy và dán output (quy ước GPU). Ước tính khoảng 6–8 phút mỗi task.
- **Tiêu chí đạt** (quyết định của mình, người dùng chưa chốt ngưỡng): ít nhất **1/3 task** có Qwen gọi `analyze_patch_impact` với `STATUS: PASS` qua stdio, và feedback lần sau có dòng impact. Số task còn lại, kể cả khi Qwen bỏ qua tool hoặc gọi sai thứ tự, được ghi đúng như quan sát vào `docs/status/m3.md`, không giấu.

## 5. Ràng buộc
- Chỉ sửa file thuộc M3 (`src/vgar/agents/`, `src/vgar/mcp/`, `scripts/`, tests, docs của M3). Không sửa `graph/impact.py`, `graph_server.py` của tool, hay engine repair của M2.
- Giữ phong cách code hiện có của `tool_agent.py`: dòng ngắn, ít comment, trả lời dạng plain text.
- Người dùng tự commit. Mình chỉ đưa danh sách file và lệnh.

## 6. Phần để builder tự quyết
- Đổi fake mode mặc định hay chỉ dùng patch sai trong test mới (§3.5).
- Cách truyền biến môi trường cho client graph (§3.3).
- Nội dung chính xác của 3 patch sai, miễn là apply được và test fixture vẫn FAIL. Phải kiểm bằng chạy thật ở fake mode.
- Tên và tham số dòng lệnh của script kiểm tra thật.

## 7. Cập nhật tài liệu khi xong
- `docs/status/m3.md`: M3-W10-3 ghi "agent gọi được qua stdio", kèm bảng kết quả thật. Bỏ ghi chú "chuyển W11" ở M3-W10-4.
- Memory `w10-impact-chain`: đóng mục mở "tool_agent retry does not call the tool".
