# M1 ContextPayload — baseline được người dùng duyệt

Ngày đối chiếu: 03/10/2026. Model implementation ở
`src/vgar/contracts/context.py`; `src/vgar/graph/context.py` là compatibility
re-export. Người dùng duyệt baseline, ownership đề xuất và nguyên tắc token
ngày 03/10/2026 trong [decision log](m1_contract_decision_log.md).
Xác nhận consumer M2/M3 và cấu hình production cụ thể còn là follow-up riêng.

## Shape và validation đang có

| Model | Fields | Validation |
|---|---|---|
| SourceRange | start_line, start_col, end_line, end_col | line ≥1, col ≥0; end không trước start |
| ContextItem | node_id, path, symbol, range, snippet, relevance_score, graph_distance, graph_rationale, confidence, token_count | ID/path/symbol không rỗng; score/confidence 0–1; distance/tokens ≥0; rationale không rỗng |
| ContextPayload | graph_version, anchor_ids, items, total_token_count, token_budget, truncated | snapshot không rỗng; budget >0; tổng item tokens bằng total và không vượt budget |

Tất cả model dùng `extra="forbid"`. `truncated` mặc định false; các field còn
lại bắt buộc. Danh sách anchors/items được phép rỗng. Validator không kiểm tra
node IDs có thật trong graph hoặc source snippet/hash khớp snapshot; đây là
trách nhiệm retrieval producer. Milestone 3 đã triển khai các source/ID checks
trong M1, không thêm validation logic vào shared model; xem [method](m1_retrieval_method.md).

SourceRange giữ quy ước source graph: line one-based; columns zero-based UTF-8
byte offsets; end exclusive. Snippet extraction phải đọc theo byte/source range,
không coi column UTF-8 là character index. Với end_col=0 ở đầu dòng tiếp theo,
không đưa cả dòng đó vào snippet.

Path phải là repository-relative POSIX. Validator reject absolute POSIX,
backslash, parent traversal và Windows drive (kể cả C:/repo/service.py hoặc
C:service.py); UNC cũng bị từ chối. D08 đã sửa ngày 03/10 theo duyệt của người
dùng, có regression test qua cả M1/shared import. JSON schema/fields giữ nguyên;
behavior validator chặt hơn. Không suy ra validator đã kiểm nguồn file/snapshot.

## Ví dụ và fixture

`tests/fixtures/contracts/context_payload.json` kiểm shape và budget accounting;
token_count=48 là dữ liệu fixture, không phải kết quả đếm bằng tokenizer model.
ID fixture là opaque string và không được dùng để suy ra ID graph mới.

```python
from vgar.contracts.context import ContextPayload

payload = ContextPayload.model_validate(data)
serialized = payload.model_dump(mode="json")
```

Import cũ của M1 vẫn hợp lệ và trả đúng cùng class:

```python
from vgar.graph.context import ContextPayload
```

## Ownership và producer checks được duyệt cho M1

- M1 tạo anchors/candidates, kiểm source snapshot, xếp hạng, đếm và pack snippets.
- M2 đọc ContextPayload để repair; M3 expose/serialize, gắn transport/audit và
  phân bổ tổng prompt budget. Handoff này cần consumer xác nhận.
- Producer phải kiểm node IDs và repository-relative source path trong snapshot,
  content hash/range và đảm bảo snippet thật khớp source. Các stale outcomes
  phải được thống nhất trước khi thêm public error code.
- Dùng injected token counter gắn với model/tokenizer revision trong production.
  Unit-test counter không được báo thành token cost của thí nghiệm.
- token_budget chỉ giới hạn snippets. Wrapper/instructions/issue/response reserve
  được tính ở prompt layer; total_token_count không đại diện toàn prompt.
- Khi candidate hợp lệ bị bỏ vì budget hoặc candidate limit, đặt truncated=true;
  không có anchor/candidate thì trả empty payload và truncated=false.
- Baseline là pack nguyên snippets, loại bỏ duplicate source ranges;
  không clipping giữa symbol trong baseline. Policy clipping khác cần ghi rõ range
  và token accounting tương ứng.

Baseline retrieval/packing nội bộ M1 đã triển khai và kiểm thử ở Milestone 3.
Official tokenizer/revision và 8000 snippet budget đã được duyệt/nghiệm thu
standalone M1: [tokenizer acceptance](m1_tokenizer_acceptance.md). Dev evaluation,
model/prompt runtime M3 và consumer integration còn riêng; D05/D09 trong decision log.
