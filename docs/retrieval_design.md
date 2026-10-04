# M1 task grounding và task overlay — 03/10/2026

Cập nhật Milestone 3: graph retrieval/packing đã có baseline triển khai nội bộ M1,
86 tests đạt; xem [retrieval method](m1_retrieval_method.md) và
[checkpoint manifest](../artifacts/m1/context-retrieval/manifest.json). Phần grounding/overlay dưới đây giữ
policy đã triển khai; production token cost và dev evaluation còn riêng.

`TaskAnchorFinder(document).find_task_anchors(issue_text, failing_tests)` tìm
anchors trên một snapshot đã validate. `TaskOverlayBuilder(document).build(...)`
tạo Issue/trace edges trong sidecar riêng cho từng tác vụ. Đây là API nội bộ M1;
không thêm MCP tool, sửa shared DTO hoặc gọi model/repair.

Chỉ dùng mô tả lỗi và báo cáo test thất bại. Developer patch/gold labels dành
cho evaluation; không dùng làm đầu vào grounding để tránh rò rỉ đáp án.

## Grounding đã triển khai

| Đầu vào | Kết quả | Điểm heuristic khi không mơ hồ |
|---|---|---|
| Relative `.py` path | File; suffix/basename giữ mọi file khớp | 0.7 |
| `path.py:line` hoặc Python traceback | Symbol nhỏ nhất chứa dòng; File nếu không có symbol | 0.95 |
| `path.py::Class::test_name[param]` | Test hiện có; không tạo node cho mỗi parameter ID | 1.0 |
| Qualified/short symbol name | Exact qualified name / mọi symbol trùng short name | 0.8 / 0.6 |
| HTTP method + literal route | Handler có decorator/path/method phù hợp | 0.9 |
| Literal route không có method | Mọi handler có path đó | 0.85 |

- Mỗi anchor có bằng chứng gồm loại khớp, đoạn text và nguồn issue/failing-test.
- Nhiều node khớp cùng một đề cập: giữ candidates trong `ambiguous_matches`,
  giới hạn điểm bằng chứng đó ở 0.5. Bằng chứng độc lập rõ ràng có thể nâng điểm
  của một anchor; không xóa dấu vết mơ hồ.
- Kết quả/evidence ổn định khi báo cáo test được đổi thứ tự hoặc lặp lại.
- Đường dẫn tuyệt đối, drive Windows, traversal và dòng ngoài range không được
  đoán thành anchor. Frame name sau traceback không được dùng để cứu một path sai.
- Hỗ trợ path có khoảng trắng khi được đặt trong dấu nháy hoặc traceback.
- Ranges có end exclusive: end_col=0 không bao gồm dòng tiếp theo. Nếu selector
  kèm số dòng, dòng đó phải nằm trong Test được chọn.

Route detection chỉ đọc metadata decorator đã nằm trong graph; parse bằng AST,
không import/execute app. Hỗ trợ `.get/.post/.put/.patch/.delete/.head/.options/.trace`,
`.route` và `.api_route` với literal path, cùng literal `methods` nếu có. Với
route/api_route không ghi methods, baseline lấy GET. Path parameter chỉ khớp
template nguyên văn (ví dụ `/users/{user_id}`), chưa map `/users/123` về template.
Đây là heuristic theo cú pháp decorator, chưa xác minh framework/router binding.

## Task overlay

Một sidecar gồm `graph_version`, `overlay_id`, `task_id`, `nodes`, `edges` và
`grounding`. Không phải standalone portable graph: khi validate, ghép tạm nodes/
edges với base snapshot trong bộ nhớ. Không ghi sidecar vào base graph JSON/SQLite.

- Một Issue dùng task ID làm danh tính, không có source path/range. Nội dung issue
  và danh sách báo cáo test nằm trong properties; không có node type FailingTest.
- MENTIONS đi từ Issue tới anchors, bao gồm đề cập từ issue và failing-test input.
  Có score, evidence và `has_ambiguous_evidence` để không làm mất dấu vết.
- REPRODUCES đi từ Test tới Issue chỉ khi failing-test input khớp Test rõ ràng.
  Mơ hồ, File/Function hoặc tên Test chỉ xuất hiện trong issue không tạo edge này.
  Nếu có thêm selector rõ ràng độc lập, chỉ Test được selector xác nhận có edge.
- REPRODUCES ghi `input_reported_failure=true`, `execution_verified=false`:
  ghi nhận báo cáo đầu vào, chưa chứng minh đã chạy test tái hiện lỗi.
- graph_version vẫn chỉ snapshot repository. overlay_id hash snapshot + task ID +
  issue text + danh sách failing reports đã sort/dedup + internal profile.
  Thay nội dung task đổi overlay_id; base snapshot/node IDs không đổi.
- Builder giữ bản sao snapshot; tác vụ mới không làm nhiễm task cũ hoặc đầu vào.

Consumer cần giữ cặp `(graph_version, overlay_id)` khi lưu context/cache theo task.
Sidecar/API này chưa là shared transport contract; expose MCP thuộc handoff M3.

## Chạy độc lập

Từ `D:\KLTN\VGAR`, với môi trường Windows đã kiểm chứng:

```powershell
& 'D:\KLTN\M1\.venv-win\Scripts\python.exe' scripts/build_task_overlay.py `
  'D:\KLTN\reports\vgar_m1_20261003\graph_m1_ms2_release_no_jedi.json' `
  --task-id demo-login `
  --issue-text 'src/vgar/graph/builder.py has a validation failure' `
  --failing-test 'tests/test_graph_builder.py::GraphBuilderRegressionTests::test_nested_function_shadows_module_function'
```

JSON xuất qua stdout. Có thể dùng `--issue-file` và lặp `--failing-test`.
`scripts/find_task_anchors.py` tiếp tục chạy nếu chỉ cần anchors.

## Bằng chứng và phần tiếp theo

- [Handoff hiện tại](m1_handoff_2026-10-03.md): checkpoint grounding 67 tests, full-repo smoke,
  input/artifacts và ranh giới M2/M3.
- [Task artifacts/manifest](../artifacts/m1/task-grounding/manifest.json): bốn case
  synthetic trên snapshot VGAR hiện tại; không phải benchmark SWE-bench.

Đã có semantic traversal (caller/callee/test/import), bounded candidates,
ranking/rationale, source/hash-verified snippets và injected-counter packing.
Official counter/revision/8000 snippet budget đã nghiệm thu standalone M1,
95 tests đạt: [evidence](m1_tokenizer_acceptance.md). Tiếp theo export Recall/MRR/
token cost trên dev tasks. M2 cung cấp BM25/
gold mapping; M3 phụ trách manifest/protocol và MCP exposure.

Giới hạn: chỉ source Python đang có trong snapshot; unquoted paths có khoảng
trắng chưa hỗ trợ; route động, router prefix, URL→template, arbitrary API registration
và implicit HTTP methods chưa resolve. Finder vẫn scan snapshot nodes; scores
không phải xác suất hoặc retrieval relevance đã đo. Chưa hoàn tất toàn bộ W5–W6.
