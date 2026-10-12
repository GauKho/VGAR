# M1 retrieval method — semantic-context-v10-source-cache

## Profile hiện tại (12/10/2026)

`semantic-context-v10-source-cache` lọc tên biến, định nghĩa hàm/class, tham số và
thuộc tính được gán cục bộ trong đoạn Python tái hiện trước khi
grounding/ranking. Alias import được đối chiếu với module trong graph; import
ngoài repository không được đoán thành method nội bộ. Đoạn code không parse
được tiếp tục dùng lexical fallback; không import hoặc chạy code từ issue.
Điểm relevance mặc định giữ cách tính của v9. Cache similarity có tối đa
8192 entry, phân biệt query và đầu vào
diagnostic/source; cache hit/miss chỉ ghi trong debug trace. `use_topic_evidence`
thử tập trung vào dòng mô tả đầu tiên, nhưng mặc định tắt vì thử nghiệm hiện tại
chưa cải thiện ổn định chất lượng context.
Các dòng báo phiên bản môi trường không được dùng làm tên symbol; tên Python
được viết rõ trong code vẫn có thể làm anchor.
Phần báo phiên bản có heading rõ ràng (`Installed versions`, `Version information`,
`Output of …show_versions()`, `Output of …--version` hoặc `… --version output`) cũng được loại khỏi
grounding/ranking. Phần tái hiện lỗi và các heading tiếp theo vẫn được giữ;
đề cập `show_versions()` bên ngoài phần báo môi trường vẫn là bằng chứng code.

Bí danh phương thức gán trực tiếp trong cùng class được đối chiếu với hàm
thực thi. Grounding/ranking nhận cả tên alias và tên hàm; ContextPayload giữ
range và snippet của hàm gốc. Alias bị ghi đè, xóa hoặc phụ thuộc nhánh điều
kiện không được tự suy đoán.

Tên API được chấm theo độ hiếm trong tập symbol (IDF) và mức khớp với issue.
Với Function/Method/Test có source parse được, task similarity gồm 80% điểm
tên API và 20% độ khớp token trong code thực thi, dùng IDF của tập hàm. Không
lấy docstring, comment, tên biến cục bộ hoặc nội dung scope lồng làm bằng chứng
cho hàm ngoài. Source không parse được dùng điểm tên/path như trước; paths này
được ghi trong diagnostics. Cache có giới hạn theo snapshot và query; source
vẫn được kiểm hash mỗi lượt retrieval. `use_source_evidence=False` tắt tín hiệu này.

Dòng có nhãn WARNING/ERROR/CRITICAL hoặc tên exception được đối chiếu với
chuỗi tĩnh tại lệnh ghi log/raise trong source đã kiểm hash. Fragment phải có
ít nhất bốn từ; placeholder không được suy diễn. Hàm khớp là source hint,
không phải binding runtime: confidence 0.85 khi có một hàm, 0.50 khi có nhiều
hàm. Điểm task similarity giữ mức khớp này nếu lớn hơn điểm tên/code thông thường.
Docstring và chuỗi không dùng tại log/raise không tạo message hint.
`use_diagnostic_evidence=False` tắt tính năng.

Tên thư mục nguồn được nhắc trong issue có thể bổ sung seed khi anchor hiện
có nằm ngoài thư mục đó. Thư mục chứa quá nửa số hàm đủ điều kiện không được
dùng để thu hẹp scope. Chỉ chọn hàm có token code khớp issue, theo source
similarity; tối đa 10 seed và không quá một phần năm quota seed (tối thiểu 1).
Confidence của component hint là 0.45; `use_component_seeds=False` tắt tính năng.
Các hint dùng chung giới hạn traversal/token budget, không tạo edge trong graph.
ContextPayload ghi tập anchor thực tế gồm đầu vào và seed bổ sung. Sidecar,
graph rationale và JSONL ghi `SOURCE_DIAGNOSTIC`/`SOURCE_COMPONENT`, fragment
hoặc tên component cùng các seed được cân nhắc.

Trọng số mặc định hiện tại: task similarity 0.50, graph distance 0.20, edge
confidence 0.10, failing-test proximity 0.20, public API risk 0.00, history 0.10.
Weights vẫn được chuẩn hóa theo các feature có đầu vào. Public API risk tiếp
tục xuất trong diagnostics và có thể cấu hình, nhưng mặc định không tăng điểm
retrieval chỉ vì một hàm có nhiều caller.

Khoảng cách từ failing test chỉ đi qua CALLS/CALLERS/TESTS/TESTED_BY. Quan hệ
chứa file/class và reference hint không được coi là liên kết test thực thi.
Khi có issue, điểm proximity của code ngoài Test được nhân với mức khớp issue
trực tiếp để hạn chế ưu tiên setup/cleanup chỉ vì chúng cùng được gọi trong test.
Test được báo lỗi và truy vấn chỉ có failing tests giữ điểm proximity gốc.
`gate_failing_test_evidence=False` tắt phép nhân; diagnostics giữ
`raw_failing_test_proximity`, `failing_test_rationale` và điểm sau điều chỉnh.

Relevance có thể truyền từ anchor sang dependency qua CALLS/TESTS hoặc tham
chiếu member có bằng chứng source, giảm theo hệ số 0.7 mỗi hop. Quan hệ chứa
file/class không truyền relevance này. Diagnostics giữ cả mức khớp tên trực
tiếp và score sau khi xét dependency; tham chiếu không được coi là runtime call.

Native context packing có thể dành tối đa 20% budget cho các implementation
của kiểu trả về đã khai báo, khi hàm gọi nằm trong ba anchor đứng đầu và đã
được chọn vào context. Các snippet này được pack ngay sau hàm gọi; phần còn
lại theo ranking. `reference_budget_fraction=0` tắt ưu tiên này. Ranking vẫn
giữ nguyên; packing dùng chung của benchmark có thể khác native ContextPayload,
nên hai loại coverage phải được báo cáo riêng.

Frontier được chọn theo relevance trên các nhánh đang chờ; neighbor chỉ dùng
candidate quota khi được chọn. Giới hạn hops/candidates, uncertainty của anchor,
source verification và token budget vẫn áp dụng. Đây là heuristic phát triển,
chưa được xác nhận trên toàn bộ benchmark; không dùng gold labels để retrieve.
Khi có issue, đường cùng số hop được chọn theo relevance trước confidence,
tránh đường chứa file/class che đường dependency liên quan hơn. Không có issue
vẫn chọn confidence trước; `prefer_relevant_paths=False` tắt ưu tiên relevance.

Các mục dưới đây mô tả baseline `semantic-context-v1` ngày 03/10/2026; tham số
và cách duyệt hiện tại dùng profile phía trên.

Ngày: 03/10/2026. Baseline implementation sau khi người dùng yêu cầu triển khai
theo [proposal, mục 9.2](../../docs/proposal_vgar_mcp_final_corrected.md).
Tham số/trọng số dưới đây là heuristic khởi đầu có thể cấu hình, chưa được tune
hoặc xác nhận bằng evaluation. Không dùng developer patch/gold labels để retrieve.

## API và phạm vi

Đóng gói ngày 12/10/2026 giữ ranking/packing baseline v10. Thử nghiệm BM25
fusion và ưu tiên snippet hàm đã được tách khỏi core/CLI vì gây regression ở
một số development cases. Code thử nghiệm và evidence được giữ local trong
thư mục ignored; chúng không thuộc gói bàn giao.

Lượt đánh giá gồm 7 dev cases, 19/21 resolver variants có kết quả; hai lượt SCIP
và SCIP+LSP của Xarray-3993 timeout ở 120 giây. Với ranking baseline, SCIP tăng
coverage native Matplotlib từ 2/6 lên 3/6 hàm; các case thành công khác không
cải thiện coverage. LSP thêm 16 CALLS nhưng chưa cải thiện retrieval so với SCIP
trong lượt bounded này (200 requests). Static là mặc định; SCIP/LSP tùy chọn.
Coverage từ class/file không đồng nghĩa từng hàm được chọn trực tiếp. Các số
liệu là kiểm chứng retrieval trên dev, không phải repair success hoặc held-out.

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
