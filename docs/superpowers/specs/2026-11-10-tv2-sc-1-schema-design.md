# TV2 · SC-1: schema `S = (TN, TE, beta, delta, Gamma)` cho mọi loại mới

> **Trạng thái:** đã duyệt 10/11/2026 (`delta` chỉ gồm khóa có code đọc; nhãn tầng và `SCHEMA_HASH` là dữ liệu phụ cho `vgar://repo/schema`).
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), **[cp]** `check proposal.txt`, **[test]** `test.txt`, **[mm]** `metrics matrix.txt`.
> Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng.
>
> **Đánh dấu:** **(research)** là câu trả lời research ngày 10/11 đã đối chiếu với nguồn và số đo. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh

[P] 857–866 định nghĩa `S = (TN, TE, beta, delta, Gamma)`: tập loại node, tập loại cạnh, cặp đầu cuối được phép, thuộc tính bắt buộc theo loại node, và bất biến. [P] 878–882: nếu mỗi bất biến là check kiểu, check thuộc tính, check đầu cuối hoặc tìm vòng trên một tập cạnh, thì kiểm `G ⊨ S` chạy trong `O(|V|+|E|)`. [P] 1213–1220 liệt kê schema check: loại node hợp lệ, đầu cuối cạnh hợp lệ, đủ thuộc tính bắt buộc, không mất anchor bắt buộc.

[plan] dòng 131 giao SC-1 cho TV2: `S` cho mọi loại mới và validate trong `O(|V|+|E|)`. Dòng 157 và 365: graph của repo mẫu phải qua validate, không có lỗi (cổng cuối tuần 1). Dòng 105: TV1 làm resource `vgar://repo/schema`, cần dữ liệu schema từ TV2.

**Hiện trạng** (`contracts/schema.py`):

| Thành phần | Có | Thiếu |
|---|---|---|
| `TN`, `TE`, `beta` | 32 loại node, 26 loại cạnh, cặp đầu cuối cho mọi loại cạnh | `Connector`, `ExternalSystem` chưa có định nghĩa của nhóm |
| `delta` | Trường chung của mọi node và cạnh; `path`, `range` của node gắn mã nguồn; `MAY_CALL` có `evidence` và `confidence` ≤ 0,5 | Thuộc tính riêng theo loại |
| `Gamma` | Đúng một `Repository`; id node, id cạnh không trùng; cùng `graph_version`; không tự nối; đầu cuối tồn tại; `CONTAINS` không vòng; `candidate_count` của `CallSite` khớp số cạnh `CALLS` | Bất biến cho các tầng mới |
| `O(\|V\|+\|E\|)` | Mỗi check một lượt; tìm vòng bằng DFS | DFS đệ quy, tràn khi lồng sâu; chưa có số đo |
| `S` dạng dữ liệu | Không | Cần cho `vgar://repo/schema` |

**Số đo trên graph thật** (5 repo của `tests/fixtures/vgar-arch-cases`, có overlay task): 19/32 loại node và 16/26 loại cạnh xuất hiện khi build mặc định. Phần còn lại chỉ có khi bật tree-sitter-graph (`Field`, `GlobalVariable`, `Identifier`, `Route`, `Schema`, `ConfigEntry`, `HAS_METHOD`, `HAS_CALLSITE`) hoặc Joern (`Statement` và 4 cạnh `G_code`), chưa có luật trích (`Requirement`, `UserStory`, `Constraint`, `Actor`, `CONFLICTS_WITH`), chưa được định nghĩa (`Connector`, `ExternalSystem`), hoặc fixture không có code kích hoạt (`IMPLEMENTS`, `REFERENCES`, `CONFIGURES`). Tỉ lệ cạnh trên node là 1,15–1,33 trên fixture nhỏ, nhưng 1,5–1,8 trên graph SWE-bench thật (đo ở bước chạy thật); validate graph 3.527 node mất khoảng 25 ms.

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Khai báo đủ `delta` cho 32 loại node và thuộc tính riêng của các loại cạnh cần có.
2. Thêm vào `Gamma` các bất biến cứng của tầng mới, đều kiểm được tuyến tính.
3. Validate không đệ quy, có số đo chứng minh tuyến tính.
4. Xuất `S` dạng dữ liệu cùng dấu vân tay, cho `vgar://repo/schema`.
5. Test chứng minh validator đủ chặt: mọi mutant sinh từ `S` đều bị từ chối **(research)**.

**Ngoài phạm vi**

- Bất biến kiến trúc so với baseline (không thêm vòng `DEPENDS_ON`, không mất port, mỗi File thuộc đúng một Component): [P] 285–293, thuộc EV-2 của TV3 ([plan] dòng 150).
- Check "không mất anchor bắt buộc" giữa graph trước và sau patch: so hai graph, thuộc EV-2.
- Schema của graph edit ở §7 (GraphDiff): TV3.
- Phần lưu SQL cho schema mới và view cũ: TV1.
- Định nghĩa `Connector`, `ExternalSystem`: nhóm chốt.
- Kiểm lại cục bộ khi cập nhật incremental ([P] 1177): đo ở U1.

**Điều cần tránh**

- Đổi tên hay chữ ký các hàm TV1 đang gọi: `validate_graph_document(document)`, `NODE_TYPES`, `RESOLVER_PROFILE`.
- Đổi tên loại node, cạnh (ví dụ thêm tiền tố `code.`), vì mọi id và mọi consumer đang dùng tên hiện tại.
- Thêm profile thứ hai cho validator: một `S` duy nhất như [P] 857, như TV2 đã chốt khi gỡ profile cũ.
- Thêm thư viện mới.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | `delta` của mỗi loại node chỉ gồm các khóa `properties` builder luôn ghi **và** có code khác đọc tới, kèm kiểu JSON; khóa chỉ để mô tả không bắt buộc | **(TV2 chốt)** |
| 2 | `Gamma` mới chỉ gồm bất biến cứng: tham chiếu bằng id phải tồn tại và đúng loại, bậc vào của `AST_CHILD` ≤ 1 | **(research)**, [P] 878 |
| 3 | Nhãn tầng là một trường riêng (`G_repo`, `G_code`, `G_arch`, `G_task`), không đổi tên loại; chỉ là dữ liệu phụ trong `schema_description()`, validator không dùng | **(TV2 chốt)**; không theo gợi ý tiền tố của research |
| 4 | Dấu vân tay: giữ `SCHEMA_VERSION`, thêm `SCHEMA_HASH` là SHA-256 của JSON đã chuẩn hóa của `S`; TV1 tự quyết có dùng hay không | **(TV2 chốt)**, **(research)** |
| 5 | Tìm vòng `CONTAINS` bằng DFS dùng stack tự quản, báo đường đi của vòng | **(research)**; không thêm Kahn vì DFS đã đủ |
| 6 | Chứng minh tuyến tính bằng benchmark riêng: fit log-log trên graph tổng hợp và graph thật, không assert thời gian trong CI | **(research)** |
| 7 | Test bằng mutant sinh tự động từ chính `S`, không dùng Hypothesis | **(đề xuất)**; Hypothesis chưa được cài |
| 8 | Không thêm bộ đếm phép toán vào validator | **(đề xuất)**; xem §8 |

## 4. `S` trong `contracts/schema.py`

Giữ `NODE_TYPES`, `EDGE_ENDPOINTS`, `SCHEMA_VERSION`, `validate_graph_document(document, *, trusted_ids=...)` như hiện tại. Thêm:

```python
NODE_PROPERTIES: dict[str, dict[str, str]]      # delta: loại node -> {khóa: kiểu JSON}
EDGE_PROPERTIES: dict[str, dict[str, str]]      # thuộc tính bắt buộc riêng theo loại cạnh
LAYERS: dict[str, str]                           # loại node hoặc cạnh -> "G_repo" | "G_code" | "G_arch" | "G_task"
INVARIANTS: tuple[tuple[str, str], ...]          # Gamma: (tên, mô tả)
SCHEMA_HASH: str                                 # "sha256:" + hash của schema_description() đã chuẩn hóa

def schema_description() -> dict[str, Any]: ...  # S dạng dữ liệu
```

Kiểu JSON là một trong `string`, `integer`, `number`, `boolean`, `array`, `object`, `string|null`, `integer|null`, `array|null`. `integer` không nhận `bool`.

### 4.1 `delta` cho node

Chỉ gồm khóa builder luôn ghi và có code khác trong `src/vgar` đọc tới (quét `["khóa"]` và `.get("khóa")` ngoài các file sinh ra node, ngày 10/11). Kiểu đo trên graph thật của 5 repo `vgar-arch-cases` **(TV2 chốt)**:

| Loại | Khóa bắt buộc và kiểu |
|---|---|
| Repository | `repository_revision` string, `root_uri` string |
| File | `is_test_file` boolean, `parse_status` string, `size_bytes` integer |
| Module | `is_external` boolean, `is_package` boolean, `module_name` string, `resolution_status` string |
| Class | `bases` array, `decorators` array |
| Function | `decorators` array, `visibility` string |
| Method | `decorators` array, `visibility` string, `method_kind` string, `owner_class_id` string |
| Import | `imported_module` string, `imported_name` string\|null, `level` integer, `raw_text` string, `resolution_status` string |
| CallSite | `candidate_count` integer, `resolution_status` string |
| Component | `files` array, `kind` string, `tests` array |
| Port | `export` string, `kind` string, `owner_component_id` string, `symbol_id` string |
| Issue | `failing_tests` array, `issue_text` string, `task_id` string |
| StackTraceFrame | `file` string, `line` integer, `function` string\|null |
| ErrorMessage | `exception_type` string, `message` string, `occurrences` integer |
| AcceptanceCriterion | `text` string |
| FailingTest | `selector` string, `test_node_ids` array |
| Test, Service, DeploymentUnit, BugReport | không có khóa riêng có code đọc |

Tên chung như `kind`, `message`, `text` có thể trùng với dict khác khi quét; plan đọc lại từng chỗ đọc trước khi chốt, bỏ khóa nào không thật sự được đọc.

Bảy loại chỉ có khi bật công cụ (`Field`, `GlobalVariable`, `Identifier`, `Route`, `Schema`, `ConfigEntry`, `Statement`): plan áp cùng luật (khóa luôn ghi và có code đọc) sau khi đọc code sinh node. Sáu loại chưa có nơi sinh ra (`Requirement`, `UserStory`, `Constraint`, `Actor`, `Connector`, `ExternalSystem`): chỉ có trường chung, ghi trong `schema_description()` là `"producer": null`.

### 4.2 Thuộc tính riêng của cạnh

| Loại cạnh | Khóa bắt buộc trong `properties` |
|---|---|
| `DEPENDS_ON` (Component → Component) | `weight` là số nguyên ≥ 1 |
| `TRACES_TO` (Issue → Component) | `anchor_count` là số nguyên ≥ 1 |
| `MAY_CALL` | giữ luật hiện có |

Cả hai khóa đều có trong graph thật (số nguyên) và có code đọc (`rank_component_traces`, phần tính `weight` của impact). `DEPENDS_ON` giữa Requirement không có khóa riêng.

### 4.3 `Gamma`

Giữ bảy bất biến đang có. Thêm:

| Tên | Luật |
|---|---|
| `port_owner` | `owner_component_id` của Port là một Component. Không đòi cạnh `EXPOSES_PORT`: view hay subgraph có thể bỏ bớt cạnh mà vẫn hợp lệ (sửa khi chạy suite: test BM25 xóa hết cạnh) |
| `port_symbol` | `symbol_id` của Port là id của một node có trong graph |
| `method_owner` | `owner_class_id` của Method là một Class |
| `failing_test_targets` | Mỗi id trong `test_node_ids` của FailingTest là một Test |
| `ast_single_parent` | Mỗi node có tối đa một cạnh `AST_CHILD` đi vào |

Mỗi luật kiểm bằng tra từ điển hoặc đếm bậc vào, một lượt. Bất biến nào sai trên graph thật ở §7 thì bỏ và ghi lý do, không sửa dữ liệu để khớp.

### 4.4 Tìm vòng `CONTAINS`

Đổi `_containment_cycle_errors` sang DFS dùng stack tự quản. Báo lỗi gồm đường đi của vòng, ví dụ `CONTAINS cycle: a -> b -> a`. Kết quả với graph hợp lệ không đổi.

### 4.5 `schema_description()`

Trả về, với khóa và danh sách đã sắp xếp:

```json
{
  "schema_version": "vgar-schema-full-v5",
  "node_types": {"Port": {"layer": "G_arch", "properties": {"owner_component_id": "string", "...": "..."}, "producer": "builder"}},
  "edge_types": {"EXPOSES_PORT": {"layer": "G_arch", "endpoints": [["Component", "Port"]], "properties": {}}},
  "common": {"node": ["id", "type", "repo_key", "name", "qualified_name", "graph_version", "properties"], "edge": ["id", "type", "source_id", "target_id", "confidence", "graph_version", "properties", "provenance"]},
  "invariants": [{"name": "port_owner", "description": "..."}]
}
```

`SCHEMA_HASH` là `"sha256:" + sha256(json.dumps(schema_description(), sort_keys=True, separators=(",", ":")))`. Sửa comment không đổi hash; thêm loại hay đổi luật thì đổi. Nhãn tầng theo [P] §4: `G_repo` (§4.2), `G_code` (§4.1), `G_arch` (§4.4), `G_task` (§4.5).

## 5. Benchmark tuyến tính

`scripts/bench_schema_validation.py --output <json>`:

- Graph tổng hợp hợp lệ với `N = |V|+|E|` ở 7 mức từ khoảng 1.000 tới 200.000, tỉ lệ cạnh trên node khoảng 1,2–1,4 như graph thật, có chuỗi `CONTAINS` lồng sâu. Mỗi mức đo 20 lần, lấy trung vị **(research)**.
- Fit `log T` theo `log N`, báo hệ số góc và R². Kỳ vọng hệ số góc gần 1.
- Đo thêm trên graph thật đã có trong WSL (xarray, django, sympy), báo thời gian.
- Không đặt ngưỡng đạt; ghi số vào báo cáo.

## 6. Test

| Nhóm | Ca |
|---|---|
| Document tối thiểu | Từ `S`, dựng một document hợp lệ nhỏ nhất có đủ 32 loại node và 26 loại cạnh; document này qua validate |
| Mutant `delta` | Với mỗi loại node và mỗi khóa bắt buộc: bỏ khóa → bị từ chối; đổi sang sai kiểu → bị từ chối. Tương tự cho §4.2 |
| Mutant `beta` | Với mỗi loại cạnh: đổi đích sang một loại không được phép → bị từ chối |
| Mutant `Gamma` | Mỗi bất biến cũ và mới có ít nhất một ca vi phạm → bị từ chối đúng tên lỗi |
| Tỉ lệ bắt | Đếm mutant sinh ra và mutant bị từ chối; phải là 100% |
| Lồng sâu | Chuỗi `CONTAINS` 5.000 tầng hợp lệ qua validate; vòng ở tầng sâu bị báo kèm đường đi |
| Xuất `S` | Đủ 32 loại node, 26 loại cạnh, mọi bất biến; JSON đọc lại được; `SCHEMA_HASH` không đổi giữa hai lần gọi và giữa Windows với WSL |
| Graph thật | 5 repo `vgar-arch-cases` qua validate; ca có tree-sitter-graph hoặc Joern chạy khi máy có công cụ, như các test L1 và L3 |
| Tương thích | `validate_graph_document(document)` và `NODE_TYPES` giữ nguyên chữ ký và tên |

## 7. Tiêu chí nghiệm thu

1. Mọi test ở §6 pass trên Windows và WSL.
2. Graph của 31 task dev (16 task trước cùng 15 task repo lớn) và overlay của chúng qua validate với `S` mới. Bất biến hay khóa nào làm graph thật fail thì xem lại `delta` hoặc bỏ bất biến đó, ghi vào báo cáo.
3. Benchmark ở §5 có số liệu, ghi vào `docs/status/`.
4. Toàn bộ test suite chỉ còn đúng các test fail đã biết.
5. Khi nhóm chốt repo mẫu chung ([plan] dòng 97, 470), thêm một ca "repo mẫu qua validate, không có lỗi".

## 8. Giới hạn và các đề xuất research không đưa vào

- **Repo mẫu tạm:** [plan] dòng 368 nêu `tests/fixtures/m2` và `vgar-demo-shop`. `m2` chỉ có một file nên không sinh được Component, Port; `vgar-demo-shop` không có trên máy. SC-1 dùng `vgar-arch-cases` cho tới khi nhóm chốt **(đề xuất)**.
- **Lỗi phát hiện khi tìm hiểu:** build một thư mục có `__init__.py` ngay ở gốc (ví dụ `src/vgar`) sinh ra Module có `name` rỗng, và validator từ chối. Đây là lỗi của builder Layer 1, không thuộc SC-1; đề xuất sửa riêng.
- **`delta` theo dữ liệu hiện nay** khóa hành vi của builder: bỏ một khóa sẽ làm validate fail. Đó là mục đích của schema, nhưng mỗi lần đổi builder phải sửa `S` cùng lúc.

| Đề xuất research | Lý do không đưa vào |
|---|---|
| Hai profile STRICT/PERMISSIVE (câu 7); profile chiếu view cũ ở server (câu 10) | Trái với một `S` duy nhất ([P] 857) và quyết định gỡ profile của TV2. View cũ là phần TV1 tự chọn, TV1 lọc theo nhãn tầng |
| Đổi tên loại thành `code.Statement`, `repo.Function` (câu 8) | Đổi mọi id và mọi consumer; dùng trường `layer` thay thế. Gợi ý của research cũng xếp sai tầng (`G_code` là L1) so với [P] §4 |
| Phiên bản dạng `2.1.0` (câu 9) | Giữ chuỗi `SCHEMA_VERSION` hiện có, vì đã nằm trong `graph_version`; thêm `SCHEMA_HASH` |
| Hypothesis (câu 1) | Chưa được cài; mutant sinh từ `S` phủ cùng các luật mà không thêm thư viện |
| Snapshot JSON từ công cụ thật (câu 2) | Document tối thiểu sinh từ `S` đã phủ các loại chỉ có khi bật công cụ; test thật của L1, L3 vẫn chạy khi có công cụ |
| Kahn trước rồi DFS (câu 14) | DFS dùng stack tự quản đã tuyến tính và báo được đường đi |
| Bộ đếm phép toán trong validator (câu 13) | Thêm code vào đường chạy chính chỉ để test; benchmark riêng đã đủ cho báo cáo. Nếu cần chặn hồi quy trong CI thì làm sau |
| Tỉ lệ cạnh/node 1,5–3,0 theo ARISE, RepoGraph (câu 12); 500.000 phần tử (câu 11) | Graph của repo này đo được 1,15–1,33, dùng số đo thật; dừng ở khoảng 200.000 để vừa RAM máy |
| "Mỗi File thuộc đúng 1 Component" là bất biến cứng | Chính research xếp nó vào nhóm so với baseline (câu 5); thuộc EV-2 |
