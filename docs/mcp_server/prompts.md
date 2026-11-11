# L6-4 — `repair_with_graph_context`

Ngày làm việc09/11/2026 (Asia/Saigon). Artifact UTC: `results/mcp_server/prompts/20261108T181049Z-template/`.

## Interface và trạng thái

Graph server đăng ký đúng **1 prompt** tên `repair_with_graph_context`; repository/execution/repair servers vẫn0. Tổng tools20 và resources8 canonical +1 alias không đổi. Prompt phục vụ được độc lập với graph/verification providers; đây là template thật, không phải một agent hoặc một campaign sửa lỗi.

Ba arguments bắt buộc, đều truyền dạng chuỗi theo MCP:

```json
{
  "issue_text": "Sửa lỗi đăng nhập\nGiữ Unicode π.",
  "failing_tests": "[\"tests/test_auth.py::test_login\"]",
  "context_budget": "128"
}
```

- `issue_text`: UTF-8 không rỗng; giữ Unicode/multiline, không đọc thêm file.
- `failing_tests`: JSON array string chứa tên test không rỗng; `[]` hợp lệ. Giữ thứ tự và duplicate, không tự chọn thêm test hoặc gọi collector.
- `context_budget`: positive ASCII decimal string. Leading zeros được chuẩn hóa trước parse; bool/float/scientific notation/âm/zero bị từ chối. Không có default budget, không kế thừa B1500 hoặc sửa budget thí nghiệm cũ. Giá trị chỉ là chỉ dẫn cho retrieval, không phải proof đã đếm/pack đúng tokens.

Renderer trả **hai user messages**: instruction cố định tiếng Anh và JSON task data có `untrusted=true`. Nội dung issue/tests không được nội suy vào instruction. JSON encoding giữ giả delimiter/role override dưới dạng data; đây không phải lời hứa mô hình sẽ chống được mọi prompt injection.

## Bảy bước theo proposal §10.4

1. Find task anchors — graph server `find_task_anchors`, binding task/snapshot từ trusted host.
2. Retrieve graph context — `get_related_context`, dùng requested context budget; host/tokenizer/service vẫn quyết định giới hạn và accounting.
3. Read only files selected by graph — repository `read_file`, lease/path jail và protected files giữ nguyên.
4. Propose minimal patch — unified diff tối thiểu, không tự cấp quyền apply hoặc sửa source gốc.
5. Analyze impact — `analyze_patch_impact` cùng snapshot/diff; nêu coverage partial/unsupported.
6. Run tests and verification — execution `run_relevant_tests` trên private admitted candidate, host authorization; các verification interfaces đã có, gồm graph `verify_patch_graph_constraints`. Không dùng ranking score để vượt required FAIL/incomplete hoặc phá repair lifecycle.
7. Explain evidence — chỉ viện dẫn kết quả/artifact thực, phân biệt unavailable/failed/incomplete với measured results.

Host quyết định prefix/qualified tool names thực tế. Prompt không invent tool, IDs, snapshot, grant hoặc evidence; không tự gọi tool/provider, tạo vòng retry hoặc chứng minh workflow đã chạy. Thiếu capability/binding/permission thì báo dependency. Các provider pending của L6-2/L6-3 không được đóng bởi prompt PASS.

## Pure renderer, giới hạn và redaction

`src/vgar/mcp/proposal/prompts.py` chứa `PromptRenderer`, frozen `PromptLimits`, workflow/template ID/hash và audited `serve_prompt` boundary. `tests/fixtures/mcp_server/prompt_contract.json` là oracle viết riêng trước implementation, gồm expected instructions/data; test đối chiếu bytes và SHA-256.

Cùng input/config/runtime tạo cùng rendered messages; timestamp/request ID chỉ có ở audit. Không đọc repo/env/gold/tokenizer hoặc gọi generator/agent/provider trong render. Nếu có trusted BoundContext đang active thì xác minh authority/lifecycle (metadata roots/cancel marker), dùng known secrets để redact; không đọc source contents hoặc tự tạo context/grant. Render không bắt buộc source checkout/binding.

Byte caps default **65.536 UTF-8 bytes tổng input** và **65.536 bytes tổng rendered message text**; host chỉ được đặt thấp hơn. Vượt cap trả lỗi, không truncate. Numeric budget quá khả năng parse/serialize của runtime trả validation error chung; không sửa Python global integer settings hay token budget. Leading zeros dài được normalize nên budget tương đương1 vẫn hợp lệ trong byte caps.

Host có thể cấu hình trước serving:

```python
from vgar.mcp.proposal.prompts import PromptLimits, PromptRenderer
from vgar.mcp.servers import graph_server

# Values supplied by trusted host/bootstrap; never MCP arguments or model text.
graph_server.prompt_renderer = PromptRenderer(
    limits=PromptLimits(max_input_bytes=32768, max_rendered_bytes=32768),
    secret_values=host_secret_values,
)
graph_server.main()
```

Known secret values và patterns được redact trong data; nếu một configured secret xung đột với phần instruction/numeric output không thể redact an toàn, trả lỗi thay vì đổi policy hoặc leak. Model không thể truyền `secret_values`, `limits`, `context` hoặc `confirmed=true` để thay config. Error/audit không echo raw values. V11 source/payload/policies không bị sửa.

## Boundary protocol và audit

Public `get_prompt` override gọi strict/audited boundary trước SDK prompt lookup/render validation: unknown name, missing/extra arguments và invalid values đã dispatch trả lỗi an toàn, không bị SDK1 echo raw input.

`prompt_render` chỉ ghi các request **đã được SDK dispatch đến prompt boundary**, với static prompt name/template hash, status, input/rendered bytes và correlation khi có. Không lưu raw issue/tests/messages. Audit failure không trả prompt thành công.

Phải phân biệt request sai **cấu trúc JSON-RPC/MCP params** bị SDK từ chối trước application dispatch. Đây không phải render attempt; không bịa `prompt_render` hoặc transport request ID cho trường hợp chưa chạy renderer. SDK1 có validation warning chứa raw data: process-local log filter đổi thành thông báo generic và ghi riêng `protocol_reject` với correlation unavailable. SDK2 trả generic protocol error trước dispatch mà không có renderer event. Raw-STDIO regression kiểm cả hai, rồi gửi tiếp request hợp lệ để xác nhận session còn hoạt động.

Không patch SDK package, viết transport proxy, native agent host hoặc sửa global client settings. Guard chỉ nằm trong graph server process; protocol-level observability không được suy từ số prompt_render như thể bao phủ mọi malformed frame. SDK2/SDK1 lanes được kiểm riêng.

## Kiểm thử và gọi từ client/Inspector

```powershell
$sdk2 = 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VGAR_GRAPH_BACKEND = 'demo'
$env:PYTHONPATH = "$PWD\src"
& $sdk2 -B -m pytest tests/mcp_server/test_prompt.py tests/mcp_server/test_prompt_wire.py tests/mcp_server/test_runtime_cli.py -q -p no:cacheprovider --basetemp "$env:TEMP\vg-l64-user-01"
```

Chọn temp mới mỗi lần. SDK2 wire tests dùng official Client với modern/legacy server và SDK1 server; raw test dùng official STDIO streams để kiểm structural rejection mà high-level Client đã chặn từ phía client. Synthetic input/config chỉ phục vụ test; implementation được gọi là production renderer thực.

Với Inspector/host đã được cấu hình riêng: dùng SDK2 interpreter và `-B -m vgar.mcp.servers.graph_server`, đặt `PYTHONPATH` trỏ checkout `src`; chọn prompt `repair_with_graph_context`, nhập đúng3 arguments như JSON ở trên và kiểm2 messages/7 bước. Không ghi đè cấu hình global; không dùng `npx ...@latest` làm lệnh tái tạo đã pin. Setup/pin version/chạy Inspector hoặc Claude Code thật vẫn thuộc L6-8, chưa được nghiệm thu trong L6-4.

Runtime checker hiện kiểm `list_prompts`, required arguments và gọi `get_prompt` đối chiếu oracle thật. Controller từ chối worker chỉ khai PASS/listing mà thiếu prompt_gate PASS. `prompt_gate=PASS` trong receipt không có nghĩa external agent đã chạy bảy bước.

Lệnh đầy đủ/log/XML/receipts/hash nằm trong artifact. Seals H1/L6-1/L6-2/L6-3/L6-5, V11, policies và DB tracked được giữ. **Dừng sau L6-4**, không tự chuyển task hoặc chạy model/Docker/commit/push.
