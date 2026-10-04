# M1 retrieval method — semantic-context-v1

Ngày: 03/10/2026. Baseline implementation sau khi người dùng yêu cầu triển khai
theo [proposal, mục 9.2](../../docs/proposal_vgar_mcp_final_corrected.md).
Tham số/trọng số dưới đây là heuristic khởi đầu có thể cấu hình, chưa được tune
hoặc xác nhận bằng evaluation. Không dùng developer patch/gold labels để retrieve.

## API và phạm vi

```python
retriever = GraphContextRetriever(
    document, repository_root,
    count_tokens=counter, counter_label="model/tokenizer@revision:counting-policy",
)
payload = retriever.get_related_context(anchor_ids, budget_tokens,
                                        issue_text=issue_text, overlay=task_overlay)
details = retriever.retrieve(anchor_ids, budget_tokens,
                             issue_text=issue_text, overlay=task_overlay)
```

`ContextPayload` dùng nguyên shared model đã duyệt. `RetrievalResult` chỉ là
sidecar nội bộ M1: config/features/candidates/omissions/counter label/overlay ID.
Không sửa GraphService Protocol, MCP tools, model loader, agent hoặc repair.
Instance giữ bản sao graph/config; base graph và source không bị ghi bởi retrieval.

## Semantic neighborhood

- Bounded multi-source BFS, xử lý equal-depth paths theo confidence và tie-break
  ổn định. Mặc định **2 semantic hops**, **100 entities**, confidence edge ≥0.60.
- Fold Function/Method/Test → CallSite → target thành một CALLS hop, reverse
  thành CALLERS. Confidence của relation là min của supporting stored edges.
- Fold Module → Import → Module thành IMPORTS/IMPORTED_BY. Không expand external
  modules không có source, tránh nối các module nội bộ qua chung external package.
- Duyệt hai chiều CONTAINS, TESTS, INHERITS và REFERENCES nếu đã có trong snapshot.
  Cycle/dedup theo node ID. File → Module → Function vẫn là hai semantic hops.
- Chỉ source-backed File/Module/Class/Function/Method/Test làm candidates. Không
  lấy Issue/Repository/Import/CallSite làm snippet độc lập.
- Anchor uncertainty từ overlay score được giữ trong path confidence; ambiguous
  anchor score 0.5 không tự biến thành resolved confidence 1.0.
- Khi chạm candidate cap, lưu `traversal_limited` và payload `truncated=true`.
  Candidate cap áp dụng trước ranking, không claim tìm global top-k ngoài cap.
- `max_hops/max_candidates/min_edge_confidence` và weights cấu hình trong M1;
  API `get_subgraph` hiện có của M3 vẫn đếm raw stored edges như trước.

## Ranking theo sáu đặc trưng của proposal

| Feature | Cách tính baseline | Trọng số gốc |
|---|---|---:|
| task_similarity | Jaccard từ vựng giữa issue và name/qualified name/path/signature; split camelCase, underscore; ASCII word tokens | 0.20 |
| graph_distance | 1 / (1 + shortest semantic distance từ anchors) | 0.30 |
| edge_confidence | Bottleneck confidence trên path ngắn nhất, gồm anchor score nếu có; chọn strongest path khi cùng độ dài | 0.20 |
| failing_test_proximity | 1 / (1 + distance từ Test có REPRODUCES rõ ràng); ngoài bounded frontier là 0 | 0.20 |
| public_api_risk | Với visibility=public: 0.5 + 0.5 × unique callers / (1 + unique callers); node khác là 0 | 0.10 |
| recent_change_frequency | Counts theo node ID, fallback path, chia max supplied counts; chỉ khi có mapping kèm history_label | 0.10 |

Score = tổng(weight × feature) / tổng weights của **active features**. History
không được cung cấp thì feature là null và bị loại khỏi mẫu số. Không có test
REPRODUCES thì failing-test feature cũng null/excluded; không coi là đã đo bằng 0.
Một window lịch sử được cung cấp được hiểu có count=0 cho các key không xuất hiện.

Tie-break: score giảm dần, rồi distance, path, qualified name, node ID tăng dần.
Mỗi candidate có features/rationale; mỗi ContextItem có relevance/confidence/distance.
Scores là heuristic ưu tiên context, không phải xác suất hoặc độ đúng đã đo.

`task_similarity` chưa là embedding/LLM semantic similarity. `public_api_risk`
là proxy từ visibility/fan-in, không chứng minh API được export hoặc patch phá API.
Falling-test proximity có bounded frontier/candidate cap riêng được ghi trong
diagnostics. Architecture/component dependency chưa có trong current vocabulary,
được ghi unavailable; không tự tạo component nodes hoặc giả dữ liệu lịch sử.

## Source và snippet checks

- Với context không rỗng, kiểm toàn bộ tập `.py` trong graph File nodes so với
  source hiện tại (theo ignored directories của builder). File thêm/xóa/đổi hash
  phải rebuild graph trước khi retrieve.
- Chỉ đọc normalized repository-relative POSIX paths; resolve symlink và chặn
  đường dẫn ra ngoài repository. Node path phải thuộc một File trong snapshot.
- Kiểm file hash, start/end bytes, line/column consistency và node snippet hash.
  Slice bytes rồi decode UTF-8; không lấy UTF-8 column làm character index.
- Kiểm lại snapshot sau token counting/packing để phát hiện source đổi trong
  lượt retrieve. Đây không phải atomic filesystem snapshot.
- Fail closed bằng `GRAPH_ERROR` hiện có. Unknown ID dùng NODE_NOT_FOUND;
  invalid input/limit dùng INVALID_QUERY/INVALID_LIMIT. Không thêm public error.

## Token packing

- Counter được inject, bắt buộc label mô tả nguồn/policy. Người dùng đã duyệt
  Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554 và budget
  8000 snippets cho standalone M1; không suy ra protocol freeze liên nhóm.
- Budget chỉ dành cho snippet text. Chat template, separators, metadata, issue,
  instructions, special tokens và response reserve do prompt/runtime layer quản lý.
- Greedy theo rank: pack nguyên snippet, skip nếu không vừa, tiếp tục xem snippet
  nhỏ hơn phía sau. Không clipping và không đổi source range để vừa budget.
- Không pack hai byte ranges chồng lặp cùng file; giữ snippet đã chọn trước.
  Omission vì duplicate/overlap không riêng lẻ làm truncated=true; budget/cap có.
- Token count từng item được kiểm là integer ≥0, total đúng bằng tổng và ≤budget.
- Empty anchors trả empty payload/truncated=false. Node ID sai không bị âm thầm bỏ.

## CLI

```powershell
& 'D:\KLTN\M1\.venv-win\Scripts\python.exe' scripts/get_related_context.py `
  'D:\KLTN\reports\vgar_m1_20261003\graph_m1_ms3_no_jedi.json' `
  'D:\KLTN\VGAR' --budget-tokens 200 --demo-counter --explain `
  --issue-text 'src/vgar/graph/builder.py:93 has a nested scope bug' `
  --failing-test 'tests/test_graph_builder.py::GraphBuilderRegressionTests::test_nested_function_shadows_module_function'
```

Demo counter đếm whitespace units, **không phải model tokens**; label xuất ra
stderr và diagnostic sidecar. Có `--anchor-id`, `--issue-file`, `--max-hops`,
`--max-candidates` và optional `--history-file/--history-label`.

CLI có `--tokenizer-manifest` để nạp official assets local đã kiểm SHA256 với
LocalTokenizerCounter/tokenizers 0.22.1; không cần Transformers. Revision/hash/
policy/runtime được ghi trong M1 diagnostics, không thêm shared payload fields.
Đã nghiệm thu counter này bằng 95 tests và full-repo actual token API/CLI/boundary.
Xem [setup/commands/evidence](m1_tokenizer_acceptance.md). Python API cho phép
runtime truyền counter đã khởi tạo thay vì load lại. Option cũ
`--tokenizer-id/--tokenizer-revision` vẫn dùng Transformers local cache only.

## Nghiệm thu tiếp theo

[Retrieval checkpoint manifest](../artifacts/m1/context-retrieval/manifest.json) ghi unit/fixture/full-repo evidence.
Standalone tokenizer/revision/8000 snippet budget đã nghiệm thu; model revision và
total prompt allocation M3 vẫn cần đồng bộ. Milestone 4 mới chạy dev retrieval evaluation/Graph-vs-BM25; chưa
claim Recall/MRR hoặc lợi ích repair chỉ từ tests và các task tổng hợp này.
