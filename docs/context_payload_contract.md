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

## Gói bàn giao cho M2 tuần 7–8

`vgar.graph.handoff.create_context_handoff` nhận graph và data wrapper từ
`get_related_context`, kiểm node/path/symbol/range với graph cùng snapshot,
source thực và token counter. `write_context_handoff` ghi vào thư mục mới,
không ghi đè gói cũ:

| File | Nội dung |
|---|---|
| `context.json` | Chính `ContextPayload` hiện có, không thêm fields |
| `context_manifest.json` | Repo key/revision/graph version, context hash, Python source inventory/hash, bindings của từng item, quy ước range và token counter |
| `test_links.json` | Mapping path/node ID → pytest selectors, lý do/giới hạn traversal, failing selectors và fallback scope |
| `repair-context.txt` | Phần context có path/symbol/range để ghép vào prompt của M2 |

`source_metadata.content_hash` trong retrieval wrapper là hash của node/snippet,
không mặc định là hash toàn file. Manifest dùng `files[path]` cho SHA256 toàn
file và `items[node_id].snippet_sha256` cho đúng byte slice. `source_digest` là
SHA256 của JSON canonical chứa mapping file hashes. Manifest dùng nhãn riêng
`vgar.m1-handoff.v1`; không thêm public `schema_version` vào shared DTO.

Scope hiện chỉ gồm `.py` theo inventory của builder; danh sách excluded directory
names được ghi rõ, không follow filesystem links. Đây không phải kiểm tra hash
toàn repo, tests/config ngoài scope hoặc bằng chứng toàn W7–8 đã hoàn tất.
Snippet giữ nguyên UTF-8/CRLF, không có wrapper trong nội dung và không clipping
giữa symbol; `truncated` báo omitted items do budget, không báo snippet bị cắt.

Export từ kết quả smoke đã lưu, dùng cùng tokenizer đã provision:

```powershell
python scripts\export_m1_handoff.py `
    --graph artifacts\m1\w7-w8\smoke\graph.json `
    --context-response artifacts\m1\w7-w8\smoke\context.json `
    --repository tests\fixtures\sample_repo `
    --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json `
    --changed-path src/auth/service.py `
    --failing-test tests/test_auth.py::test_login --selected-test tests
```

Mỗi invocation có output directory riêng và `result.json`, kể cả input validation
ERROR. `PASS` của exporter chỉ nói gói M1 đã được kiểm, không nói LLM/patch/tests
đã thành công. CLI in absolute output path. Artifacts nằm dưới thư mục ignored
`artifacts/m1/w7-w8/`.

Phía nhận dùng snapshot identity từ task/config được duyệt, không lấy các giá
trị expected một cách ngầm định từ chính manifest đang kiểm:

```python
from vgar.contracts.handoff import validate_context_handoff, adapt_test_hints
from vgar.contracts.prompt_context import render_context_for_repair

context = validate_context_handoff(
    payload_json, manifest_json, original_snapshot_root,
    expected_graph_version=task_graph_version,
    expected_repo_key=task_repo_key, expected_revision=task_revision,
    count_tokens=approved_snippet_counter, counter_label=approved_counter_label,
)
context_text = render_context_for_repair(context)
test_inputs = adapt_test_hints(test_links_json, manifest_json, original_snapshot_root)
# test_inputs: test_links, failing_selectors, fallback_scope; values are tuples.
```

Consumer checks không import graph builder/MCP/model runtime. Có thể nhận gói
trên clone ở đường dẫn khác nếu đúng source snapshot. Empty context, file set/hash
mismatch, range/snippet mismatch hoặc token count sai bị từ chối trước prompt.
Hash giúp phát hiện sai lệch dữ liệu, không phải chữ ký chứng thực producer.
Token counter này kiểm ngân sách snippets; M2 tính lại toàn chat template bằng
tokenizer của backend được duyệt, không suy từ `total_token_count`.

Test hints được xác thực trên **original snapshot trước patch**, rồi truyền mapping
vào bước chọn test của M2 sau khi có changed files. Targets mặc định là paths và
packed node IDs; file/symbol ngoài mapping cần fallback hoặc query bổ sung từ
graph gốc. Explicit failing selectors được giữ riêng, fallback scope không bị
cắt theo graph limit. Selector existence/path được kiểm, nhưng tên testcase,
parameterization và khả năng collect còn do M2 xác thực bằng pytest trên worktree.
Các cờ `collection_verified=false`, `coverage_verified=false` giữ giới hạn đó rõ
ràng; thiếu links không chặn M2 chạy failing tests hoặc toàn scope đã chọn.
