# ADR — task_handle cho retrieval MCP stateless

Ngày: 06/10/2026. Phạm vi: tích hợp tuần 3–6, không research tuần 1–2.

## Quyết định và quyền phê duyệt

Người dùng đã chọn **“Thêm task_handle, giữ client stateless (đề xuất)”** khi được hỏi về stop rule của milestone 6. Đây là xác nhận triển khai; không thay cho sign-off chính thức của owner M1/M3 trong nhóm.

`MultiServerMCPClient.get_tools()` hiện tạo session mới mỗi tool call. Hai issue khác nhau có thể có cùng anchor IDs nhưng khác Issue/MENTIONS/REPRODUCES overlay; không thể dùng anchor IDs làm identity cho task. Probe có source hash không đổi: `artifacts/fixes/w3-w6/20261006T152805151430Z-13a7856b5827/result.json`.

Chốt input/output:

```text
find_task_anchors(issue_text, failing_tests=None)
  -> ToolResponse.data: task_handle, graph_version, anchor_ids,
     anchors, ambiguous_matches, unmatched_locations

get_related_context(anchor_ids, budget_tokens, task_handle)
  -> ToolResponse.data: ContextPayload (giữ nguyên mọi field)
  -> metadata: task_handle, overlay_id, counter_label, retrieval_diagnostics
```

Không có global last issue. Handle là content hash của graph_version + issue + failing reports đã chuẩn hóa. SQLite giữ task context riêng, không chèn overlay vào repository graph. Get-context kiểm handle hash, anchors tính lại và graph snapshot hiện tại trước khi retrieval. Có thể chọn subset anchors của task đó, không thể thêm anchors của task khác. Task A → B → A qua ba subprocess vẫn trả đúng context A/B/A.

## Persistence và tương thích

- `node_source_metadata` lưu language/range gốc, gồm byte offsets; adapter không suy diễn bytes từ line numbers. `task_contexts` giữ handle/context, capacity 10.000; hết capacity báo lỗi, không tự xóa task của người dùng.
- Đây là bảng nội bộ; **không** thêm public schema_version. ID/graph contract/ContextPayload không đổi.
- Snapshot SQLite cũ không có source metadata vẫn dùng search/callers/callees được. Retrieval cần ingest snapshot mới, báo GRAPH_NOT_READY nếu thiếu spans; không làm migration giả có đầy đủ dữ liệu.
- Source root và pinned tokenizer do host cấp qua Settings/env. Client không cho model tự chọn source root của retrieval. Source hashes/file inventory vẫn được M1 kiểm.
- Demo backend không có source snapshot thật: hai retrieval tools trả GRAPH_NOT_READY, không tạo context giả để báo benchmark PASS.
- Handle không phải access token hay OS authorization. MCP ở local stdio; không được dùng cơ chế này thay authentication cho server công khai.

## Test/Issue và failing tests

Giữ taxonomy hiện có: Issue + Test + MENTIONS/REPRODUCES. Failing-test report là **đầu vào báo đã fail**, chưa phải bằng chứng đã execute: edge có `input_reported_failure=true`, `execution_verified=false`. Không tự thêm loại node FailingTest. Verification test result vẫn do M2 runner tạo, riêng với task grounding.

## Token/context semantics

- M1 ContextPayload: pack snippet theo source span, đếm từng snippet, không special tokens. total_token_count không gồm issue, instructions, tool JSON, metadata hay output reserve.
- Evaluator M2 dùng chính candidate ranking đó nhưng repack theo shared scorer: header + tối đa 80 dòng/snippet, overlap policy đã pin. Đây là **context đánh giá**, không đồng nhất với native M1 snippet context. Báo cả diagnostics để so đúng.
- `graph` issue-only; `graph_f2p` dùng FAIL_TO_PASS của benchmark, là **oracle-assisted**, không được gộp claim với issue-only.
- CFG/data flow/history feature chưa có không được giả là có: xem unavailable_features/normalized weights ở diagnostics.

## Giới hạn khác

Callers/callees chỉ depth=1. Depth khác 1 trả INVALID_LIMIT, không echo depth=2 rồi chỉ trả direct neighbors. Graph resources thử ID nguyên bản trước; chỉ unquote URI một lần sau NODE_NOT_FOUND, tránh làm hỏng ID thật có dấu `%`.

Sign-off owner M1/M3: **chờ nhóm**, không tự đánh dấu thay.
