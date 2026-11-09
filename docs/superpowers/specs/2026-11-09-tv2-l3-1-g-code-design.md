# TV2 · L3-1: dựng `G_code` bằng Joern và adapter mỏng

> **Trạng thái:** đã duyệt, 09/11/2026.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), **[cp]** `Downloads\context\check proposal.txt`, **[test]** `test.txt`.
> Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng, không phải yêu cầu.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh

| [plan] ghi ở L3-1 | Spec này làm |
|---|---|
| Cạnh `AST_CHILD`, `CFG_NEXT`, `DATA_DEPENDS_ON`, `CONTROL_DEPENDS_ON` ([P] 193–197) | §4, §6 |
| Công cụ: "Joern pysrc2cpg, CodeQL Python, hoặc bản gọn" ([cp] Bước 4) | Joern (§5) |
| L3-2 Joern ("optional Joern backend", [P] 1453) | Gộp vào L3-1 **(TV2 chốt)** |

[P] 348–355 nói VGAR-MCP không tự viết static analyzer mà hợp nhất facts từ tool vào Arch-CPG. Joern làm phân tích; adapter chỉ chuẩn hóa ([P] 202, 401).

**Thực nghiệm trước khi viết spec** (chi tiết ở §10): Joern chạy được trên xarray nhưng coi `raise` là chạy tiếp ở 535/694 câu. Adapter sửa lỗi này và đạt 332/332 mẫu độc lập.

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Khi bật tùy chọn, graph có node `Statement` và 4 loại cạnh trên, qua `validate_graph_document`.
2. Khi tắt, graph giữ nguyên hoàn toàn như hiện tại.
3. Khi Docker hoặc Joern không chạy được, graph vẫn build xong và báo rõ `G_code` chưa có ([P] 1462).
4. Có test tầng 1 với đáp án viết tay ([test] mục 1), không cần Docker trong CI.
5. Phủ đủ 4 loại AST mà [P] 144 nêu: `function`, `if`, `call`, `identifier`; mọi câu lệnh trong hàm đều có node.
6. Chạy được khi máy chủ là Windows và Linux **(TV2 chốt)**.

**Ngoài phạm vi**

- L3-3 CodeQL; L3-4 Glean; L3-5 Kythe ([P] 403–404 khuyến cáo không dùng cho MVP này).
- Node cho toán tử, hằng và các biểu thức khác **(đề xuất)**: thân hàm không phải test của xarray có 134.982 node cú pháp, so với 13.333 câu lệnh và 35.604 tên biến.
- Dùng `G_code` trong retrieval, impact: plan 2 tuần chưa có task nào cần.
- `G_code` cho code test và cho câu lệnh ở mức module, class **(đề xuất)**.
- Chạy Joern trong tool MCP hoặc trong incremental update: chỉ chạy lúc build đầy đủ.
- Tự viết CFG hay dataflow.

**Điều cần tránh**

- Làm thay đổi graph khi tùy chọn đang tắt.
- Build thất bại chỉ vì không có Docker.
- Để container Joern chạy mồ côi khi quá thời gian.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | Joern làm phân tích, adapter mỏng chuẩn hóa | **(TV2 chốt)** |
| 2 | `G_code` bật bằng tùy chọn, mặc định tắt | **(TV2 chốt)** |
| 3 | Chạy Joern qua Docker, ghim digest image | **(đề xuất)** |
| 4 | Một loại node `Statement` có thuộc tính `kind` | **(đề xuất)** |
| 5 | Câu lệnh lấy từ tree-sitter, Joern chỉ cho quan hệ | **(đề xuất)** |
| 6 | `CONTROL_DEPENDS_ON` tính lại từ CFG đã sửa | **(đề xuất)** |
| 7 | `elif` là node riêng, để phủ hết câu lệnh | **(TV2 chốt)** |
| 8 | Thêm `Identifier` cho tên biến trong thân hàm | **(TV2 chốt)** |
| 9 | `DATA_DEPENDS_ON` ghi tên biến truyền dữ liệu | **(TV2 chốt)** |
| 10 | Nghiệm thu thêm: so số câu lệnh với `ast`, dataflow bằng `ast`, vết chạy thật | **(TV2 chốt)** |
| 11 | Chạy được trên Windows và Linux | **(TV2 chốt)** |

## 4. Node và cạnh

Khai báo trong `contracts/schema.py`, kèm ghi chú "Proposed, pending team review". Thêm `G_CODE_EDGE_TYPES`; `SCHEMA_VERSION` lên `vgar-schema-full-v4`.

### 4.1 Node `Statement`

| Trường | Giá trị |
|---|---|
| `id` | `{id của hàm chứa}::{kind}#{n}`, `n` là số thứ tự cùng `kind` trong hàm. Sửa một hàm không đổi id của hàm khác |
| `path`, `range`, `content_hash` | Lấy từ tree-sitter, `range` là cả khối, hash đúng bytes của `range` |
| `name`, `qualified_name` | `kind`; `{qualified_name của hàm}::{kind}#{n}` |
| `properties` | `kind`, `owner_id`; `condition` với `if`, `while` ([P] 186); `value` với `return` ([P] 187) |

- `kind` là tên node tree-sitter bỏ hậu tố `_statement`; `function_definition` là `def`; `class_definition` là `class`; `decorated_definition` lấy theo định nghĩa bên trong nó; `elif_clause` là `elif`, có `condition`. Luật này theo cú pháp, không phải danh sách viết tay, nên không bỏ sót loại câu lệnh nào.
- Câu lệnh của hàm là các statement trong thân hàm, kể cả lồng trong `if`, `for`, `try`. Không đi vào thân `def`, `class` lồng bên trong; thân của hàm lồng thuộc về chính node hàm đó.
- `else`, `except`, `finally` là mệnh đề của câu lệnh chứa nó, không phải node riêng.
- Không thêm `Statement` vào `SOURCE_BACKED_NODE_TYPES`, giống Port, vì node này không nằm trong chuỗi `CONTAINS`.

### 4.2 Node `Identifier` cho tên biến

Dùng lại loại `Identifier` đã có ([P] 185). Mỗi lần một tên biến xuất hiện trong thân hàm là một node.

- Lấy các node `identifier` của tree-sitter trong câu lệnh. **Không** lấy tên thuộc tính (`y` trong `x.y`) và tên tham số khi gọi (`k` trong `f(k=1)`), vì đó là tên trường, không phải biến **(đề xuất)**.
- `id`: `{id của hàm chứa}::identifier:{tên}#{n}`, `n` là thứ tự xuất hiện của tên đó trong hàm.
- `properties`: `extractor` là `code-graph`; có `type` khi biến được khai báo kiểu trong câu lệnh đó ([P] 185).
- Có cạnh `CONTAINS` từ hàm chứa, như `Identifier` của tham số, vì loại này thuộc `SOURCE_BACKED_NODE_TYPES`.

### 4.3 Cạnh

| Cạnh | Nguồn → đích | Nghĩa | `confidence` | `resolution` |
|---|---|---|---|---|
| `AST_CHILD` | Function/Method → Statement; Statement → Statement; Statement → CallSite; Statement → Identifier | Nằm trong, có `properties.ordinal` | 1.0 | `exact` |
| `CFG_NEXT` | Statement → Statement | Chạy xong nguồn thì có thể chạy đích | 0.9 | `heuristic` |
| `DATA_DEPENDS_ON` | Statement → Statement; Statement → Function/Method | Nguồn dùng dữ liệu do đích tạo ra; đích là hàm khi dữ liệu là tham số. `properties.variables` là danh sách tên biến, để truy vấn đúng theo từng biến | 0.8 | `heuristic` |
| `CONTROL_DEPENDS_ON` | Statement → Statement | Nguồn có chạy hay không do đích quyết định | 0.9 | `heuristic` |

Giá trị `confidence` và `resolution` **(đề xuất)**. `source_tool` là `joern-pysrc2cpg`, riêng `AST_CHILD` là `vgar-python-graph-builder`. `rule_id` dạng `python.code.<loại cạnh viết thường>.v1`.

## 5. Chạy Joern

File mới `graph/joern_runner.py`.

```python
@dataclass(frozen=True)
class JoernConfig:
    image: str = "ghcr.io/joernio/joern@sha256:26571901cb0311b98013ad73c5078c979da690147ce2d3d9b41d707da556f122"
    docker: str = "docker"
    timeout_seconds: float = 900.0

def run_joern(root: Path, python_files: list[Path], config: JoernConfig) -> JoernResult: ...
```

- Bật qua `PythonGraphBuilder(joern=JoernConfig())`, mặc định `None`. CLI: `scripts/build_graph.py --joern`, `--joern-image`, `--joern-timeout`.
- Chép các file `.py` không phải test vào thư mục tạm, để Joern chỉ thấy đúng tập file của builder.
- Chạy 2 container `--rm --network none`, mount mã nguồn chỉ đọc: `joern-parse --language PYTHONSRC`, rồi `joern --script` với `export.sc` nằm trong package (`graph/joern/export.sc`).
- `export.sc` xuất mỗi cạnh CFG, CDG, REACHING_DEF một dòng kèm id node, nhãn, dòng, code, file, method, và tên biến của cạnh REACHING_DEF; và mỗi `raise` có nằm trong `try` hay không.
- Mỗi container có `--name` riêng. Quá `timeout_seconds` thì `docker rm -f` theo tên.
- `export.sc` kết thúc bằng dòng `END`. File kết quả rỗng, thiếu dòng `END` hoặc không có method nào là `failed`.
- Không có Docker, lỗi khi chép file, lỗi khác hoặc quá giờ: `JoernResult.status` khác `ready` kèm `reason`. Không ném lỗi ra ngoài.

`JoernResult.status` thuộc `ready`, `unavailable`, `failed`, `timeout`.

**Windows và Linux:** Joern luôn chạy trong container Linux; khác biệt chỉ ở máy chủ. Lệnh Docker gọi không qua shell, đường dẫn mount dùng `Path.as_posix()`. Sau khi chạy, container mở quyền thư mục kết quả (`chmod -R a+rwX /out`), để Linux xóa được file do root trong container tạo ra. `export.sc` và đường dẫn trong kết quả luôn dùng `/`.

## 6. Adapter

File mới `graph/code_graph.py`, các hàm thuần, không chạy Docker.

1. **Chọn method:** ghép method của Joern với Function/Method của graph theo `(path, dòng def, tên)`. Bỏ các method phụ của Joern (`<module>`, `<body>`, `<fakeNew>`, `<lambda>...`). Hàm không ghép được thì không có `G_code` và được đếm trong report.
2. **Sửa `raise`:** `raise` ngoài `try` mà có cạnh chạy tiếp thì bỏ các cạnh đó và nối thẳng tới `METHOD_RETURN`. Bỏ các cạnh dataflow đi từ dòng của `raise` đó sang dòng khác. `raise` trong `try` để nguyên.
3. **Tính lại `CONTROL_DEPENDS_ON`:** Ferrante–Ottenstein–Warren trên CFG đã sửa, dùng `networkx.immediate_dominators` trên đồ thị đảo. Node không tới được exit thì bỏ qua và đếm trong report.
4. **Chiếu về `Statement`:** mỗi node Joern về câu lệnh đầu tiên bắt đầu trên dòng của nó; nếu không có thì về câu lệnh nhỏ nhất của hàm chứa dòng đó. Node `BLOCK` và `JUMP_TARGET` (Joern không gán số dòng cho nhánh `case`) là trong suốt: đi xuyên qua nó tới node kế tiếp. Bỏ cạnh trong cùng một câu lệnh. Tham số (`METHOD_PARAMETER_IN`) chiếu về chính node hàm.
5. **Đổi chiều dataflow:** Joern ghi từ nơi định nghĩa sang nơi dùng; `DATA_DEPENDS_ON` đi từ nơi dùng sang nơi định nghĩa. Nhiều cạnh Joern giữa cùng hai câu lệnh gộp thành một, `variables` là tập tên biến đã sắp xếp; chỉ giữ giá trị là một tên biến đơn, bỏ giá trị là cả biểu thức.

`networkx` khai báo trong nhóm optional `code-graph` của `pyproject.toml`, import khi chạy adapter. Thiếu gói thì `status` là `unavailable`.

## 7. Tích hợp vào builder

- `run_joern` chạy trước `_calculate_graph_version`, như SCIP, tree-sitter-graph.
- Khi có `joern`, `graph_version` thêm `joern-code-graph-v1`, image và `status`. Khi không có, `graph_version` không đổi theo tùy chọn này.
- Thêm pha `_add_code_graph` sau `_resolve_calls`, trước `_lift_architecture`.
- `statistics.code_graph`: `status`, `reason`, `image`, số `Statement`, số cạnh mỗi loại, số `raise` đã sửa, số method ghép được và không ghép được.
- `IncrementalGraphBuilder` không nhận tùy chọn này.
- `build_graph.py` in `WARNING` khi đã bật mà `status` khác `ready`, như tree-sitter-graph.

## 8. Ảnh hưởng tới code có sẵn

| Nơi | Xử lý |
|---|---|
| `sqlite_store.get_subgraph` (dòng 530) | Thêm `G_CODE_EDGE_TYPES` vào danh sách loại trừ, và bỏ `Identifier` có `extractor` là `code-graph`, để resource subgraph không phình ra |
| `retrieval._index_relations`, `impact.compute_impact` | Không đổi, chúng bỏ qua loại cạnh lạ |
| `impact._snapshot` | Không đổi. Khi bật, kiểm thêm node `Statement` nên chậm hơn; đây là lý do mặc định tắt |
| Graph worker của TV1 | Không truyền tùy chọn nên không bị ảnh hưởng |

## 9. Tiêu chí nghiệm thu

**Dữ liệu test không cần Docker:** `tests/fixtures/joern/flow_cases.py` và `flow_cases.edges.tsv` (kết quả `export.sc` thật, ghi lại một lần).

**Đáp án viết tay cho 6 hàm** (số dòng trong `flow_cases.py`):

| Hàm | `CFG_NEXT` | `CONTROL_DEPENDS_ON` (nguồn phụ thuộc đích) |
|---|---|---|
| `login` | 2→3, 3→4, 3→5, 5→6 | 4, 5, 6 phụ thuộc 3 |
| `guarded` | 11→13, 11→16, 13→14, 14→16, 16→17 | 13, 14 phụ thuộc 11 |
| `managed` | 21→22, 22→21, 21→23 | không có |
| `checked` | 27→28, 27→29, 29→30; không có 28→29 | 28, 29, 30 phụ thuộc 27 |
| `looped` | 34→35, 35→36, 35→39, 36→37, 36→38, 37→39, 38→35 | 36 phụ thuộc 35; 37, 38, 35 phụ thuộc 36 |
| `matched` (cú pháp `match`) | 43→45, 43→47, 45→48, 47→48 | 45, 47 phụ thuộc 43 |

Dataflow phải có đường tương ứng (được phép đi qua câu trung gian): `login` 2→3, 2→5, 5→6 và tham số→2; `checked` tham số→27, tham số→28, tham số→29, 29→30; `looped` 34→38, 34→39, 35→36, 35→38, 38→39; `matched` 45→48, 47→48. Riêng `error` của `except ... as` trong `guarded` và tham số→43 của `matched` là giới hạn đã biết (§10).

**Test tầng 1:**

| Nhóm | Ca |
|---|---|
| Schema | Node, cạnh mới qua validate; cặp đầu cuối sai bị từ chối |
| Câu lệnh | `kind`, `range`, `content_hash` đúng bytes; không đi vào thân hàm lồng; `elif` là node riêng, `except` không; số câu lệnh mỗi hàm bằng số đếm từ `ast` của Python trên mọi repo mẫu; id không đổi khi sửa hàm khác; dòng thêm phía trên không đổi id |
| `Identifier` | Có node cho biến đọc, biến ghi, có `CONTAINS` từ hàm và `AST_CHILD` từ câu lệnh; không có node cho tên thuộc tính, tên tham số khi gọi; có `type` khi khai báo kiểu |
| Dataflow | `x, y = f()` rồi `g(x)`: `variables` của cạnh chỉ có `x`; nhiều biến cùng cặp câu lệnh gộp một cạnh |
| Adapter | 6 hàm ở bảng trên; `raise` trong `try` giữ nguyên; `raise` đã là exit không đổi; method phụ bị bỏ; node không tới được exit không làm lỗi |
| `AST_CHILD` | Hàm → câu lệnh, câu lệnh lồng, câu lệnh → `CallSite`, `ordinal` đúng thứ tự |
| Builder | Không bật: document giống hệt trước, không có `Statement`; bật với kết quả Joern giả: có đủ 4 loại cạnh, `validate_graph_document` đạt |
| Lỗi | `docker` không tồn tại, lệnh trả mã lỗi, quá giờ (có `docker rm -f`): graph vẫn build, `status` đúng, không có `Statement` |
| Windows, Linux | Lệnh Docker được dựng đúng với đường dẫn dạng `C:\...` và `/home/...`; kết quả dùng `/` |
| Tích hợp | `get_subgraph` không trả cạnh `G_code`; `graph_version` khác nhau khi bật và tắt |
| Docker thật (marker `docker`) | `run_joern` trên `flow_cases.py` cho đúng bảng trên |

**Toàn bộ:**

1. Test mới pass; toàn bộ test suite (bỏ marker `hf`, `docker`) chỉ còn đúng các test fail đã biết.
2. Chạy thật trên xarray-4629, ghi vào `docs/status/`: thời gian, số node và cạnh, kích thước graph, `raise` đã sửa, tỷ lệ method ghép được. Số này chỉ để kiểm tra, không dùng để chỉnh luật.
3. Ba phép kiểm độc lập trên repo thật, ghi tỷ lệ đạt và phân tích các ca không đạt, không đặt ngưỡng vì nguồn không quy định:
   - Mẫu `if ...: raise` có câu theo sau, đáp án từ `ast`.
   - Số câu lệnh mỗi hàm so với `ast`.
   - Dataflow: `x = ...` rồi câu ngay sau dùng `x`, đáp án từ `ast`, kiểm cạnh có `x` trong `variables`.
4. Vết chạy thật trên repo mẫu có test: chạy test với `sys.settrace`, mọi bước chuyển giữa hai câu lệnh trong cùng lời gọi hàm phải có trong `CFG_NEXT`.
5. Chạy thật trên cả máy chủ Windows và Linux (WSL Ubuntu), hai kết quả phải giống nhau về node và cạnh.

## 10. Thực nghiệm và giới hạn

**Kết quả trên image đã ghim, xarray-4629:**

| Chỉ số | Kết quả |
|---|---|
| Joern parse / xuất cạnh / adapter | 29 s / khoảng 20 s / 7,5 s |
| `raise` | 694 câu: 523 đã sửa, 96 vốn đúng, 75 trong `try` để nguyên |
| `if ...: raise` có câu theo sau, đáp án độc lập từ `ast` | Joern gốc 0/332, sau adapter 332/332 (CFG và control) |
| 5 hàm đáp án viết tay | 14/15 phép so đúng |
| Hàm của graph ghép được với method Joern | 1.956/1.974 (99,1%) |
| Dòng của node Joern nằm trong câu lệnh hoặc dòng `def` | 22.168/22.168 |
| Cạnh mức dòng, bỏ test | `CFG_NEXT` 22.870, dataflow 42.907, control 10.507 |

Thực nghiệm chiếu về dòng; spec chiếu về `Statement`, nên số cuối sẽ đo lại ở §9.

**Giới hạn đã biết**

- Joern không tạo dataflow cho biến trong `except ... as error`.
- Joern không tạo dataflow tới một tên biến đứng một mình làm điều kiện của `if`, `while`, `match` (`if flag:`). Điều kiện có so sánh, `not` hoặc lời gọi thì có. Tự bổ sung nghĩa là tự viết dataflow, nên để nguyên; đáp án viết tay giữ ở test `xfail(strict)`.
- Trong 75 `raise` nằm trong `try` để nguyên, có 12 câu vẫn chạy tiếp.
- Dataflow chỉ mới có đáp án trên 5 hàm; Joern coi tham số của lời gọi có thể bị sửa, nên có đường đi vòng qua câu trung gian.
- 18/1.974 hàm không ghép được, chủ yếu `@property` và hàm lồng trùng tên.
- `except` gộp vào `try` theo §4.1.
- Khi bật, xarray có thêm khoảng 13 nghìn `Statement` và 36 nghìn `Identifier` ở code không phải test, nên graph lớn hơn đáng kể.
- Joern chỉ cho số dòng, nên các câu lệnh trên cùng một dòng được gộp về câu đầu tiên bắt đầu trên dòng đó. Với `if c: raise E`, `raise` không có cạnh CFG riêng nhưng không sinh cạnh sai. xarray không có ca này; thư viện chuẩn `http` có 37 ca.
- Chạy cần Docker và image 3,7 GB; thêm khoảng 1 phút với repo cỡ xarray.
- Chưa dùng được cho repo không phải Python; ngoài phạm vi.
