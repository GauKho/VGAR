# TV2 · GA-1 và GA-2: lift `G_arch` từ graph Python

> **Trạng thái:** đã duyệt 09/11/2026.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (gọi tắt **[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng) và các nguồn của plan: **[cp]**
> `Downloads\context\check proposal.txt`, **[test]**, **[rq]**. Không dùng plan 16 tuần hay deliverable của chúng.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh và lý do

| Task | Plan ghi | Spec này làm |
|---|---|---|
| **GA-1** (ngày 3) | Lift `G_arch`: các tín hiệu ở [P] 576–585, cohesion/coupling, `infer_public_ports`, `DEPENDS_ON` có trọng số | Toàn bộ, trừ tín hiệu co-change (cần L4-1 của TV3) |
| **GA-2** (ngày 4) | Node Component, Port, Connector, Service, Module, DeploymentUnit, ExternalSystem; cạnh `DEPENDS_ON`, `EXPOSES_PORT`, `CONSUMES_PORT`, `COMMUNICATES_WITH`, `CONTAINS_COMPONENT`, `DEPLOYS_TO` | Khai báo đủ trong schema. Sinh dữ liệu cho mọi loại trừ Connector và ExternalSystem (§5.5) |
| **L1-3** (phần còn lại) | Cạnh `CONFIGURES` | Đóng theo hợp đồng ở spec Layer 1 §7 |

GA-1 và GA-2 làm chung **(TV2 chốt)**: kết quả lift phải ghi vào node, cạnh của GA-2 thì mới qua validate được.

Các task sẽ đọc kết quả này: `components_depending_on` của RT-1 ([P] 979), `DEPENDS_ON` và port của IM-1 ([P] 1007–1024),
check "mất port" ([P] 892, 1228), `TRACES_TO` của TR-1 ([P] 873), và tool, resource của TV1 ([plan] Phụ lục B #1;
`vgar://component/{id}`, [P] 1058–1066). A3/A4 của Ablation cần `G_arch` ([rq]).

## 2. Mục tiêu, phạm vi loại trừ, điều cần tránh

**Mục tiêu**

1. Graph do `PythonGraphBuilder` tạo ra có thêm tầng `G_arch` và qua `validate_graph_document`.
2. Có test tầng 1 bằng `pytest`, so với đáp án viết tay trên repo mẫu ([test] mục 1; [plan] Phụ lục B #3).
3. Đóng `CONFIGURES` của L1-3.

**Không làm trong spec này**

- Expose `G_arch` ra MCP tool, resource: L6-2, L6-3 của TV1. Trường `risk` ([P] 1065) tính ở đó.
- Dùng `G_arch` trong retrieval và impact: RT-1, IM-1.
- Check "mất port", cycle, tầng kiến trúc: IM-1 và EV-2.
- Chấm chất lượng ranh giới Component: G1, cần nhãn tay ([plan] O7).
- Tín hiệu co-change: chờ L4-1. Trong lúc đó báo `unavailable`.
- Cơ chế sửa tay ranh giới ([P] 1473): plan chỉ nêu ở mục rủi ro, không có dòng task.
- Tách nhỏ Component dựa trên cohesion/coupling. [P] 587: "chỉ nên là heuristic".

**Điều cần tránh** (vẫn tính là hỏng dù code chạy)

- Sửa bất kỳ node hay cạnh `G_repo` có sẵn. Bỏ `G_arch` đi thì graph phải giống hệt trước khi có spec này.
- Tự chế node từ tên gọi khi không có bằng chứng. Thà để 0 node và báo rõ.
- Chỉnh quy tắc để hợp riêng một repo cụ thể.
- Làm build thất bại vì thiếu tín hiệu tùy chọn hoặc file deploy hỏng.

## 3. Ràng buộc đã biết từ code

- Builder chạy theo từng pha link rồi mới ráp `document` (`builder.py:153-263`). Incremental dùng lại đúng `build()` nên pha mới
  chạy lại toàn repo sau mỗi lần cập nhật (`incremental.py:188, 201`).
- `Function`/`Method` đã có `properties.signature` và `properties.visibility` (`builder.py:737, 746`). Builder chưa đọc `__all__`.
- `validate_graph_document` kiểm endpoint, confidence, provenance. Node loại "source-backed" phải có `path` và `range`.
- `sqlite_store.py:541` chỉ loại `MAY_CALL` khỏi truy vấn subgraph.
- Component, DeploymentUnit, Service có `path` hoặc `range` là `None`, giống Repository. Các chỗ đọc `node['path']` không kiểm `None` phải được rà, ít nhất là `evaluation/incremental_bench.py:45`.

## 4. Vị trí trong pipeline

- Module mới `src/vgar/graph/arch_lift.py`, gồm hàm thuần nhận dữ liệu graph và trả mô tả node, cạnh cần thêm **(đề xuất)**.
- `PythonGraphBuilder.build` gọi một pha mới sau `_link_chain_references` và trước khi ráp `document`.
- **Mặc định bật** **(đề xuất)**, vì tool của TV1 và A3/A4 của Ablation cần `G_arch` ([plan] Phụ lục B #1; [rq]).
- **Định danh:** thêm `RULE_VERSION` của lift vào `BUILDER_VERSION`, đổi `SCHEMA_VERSION` thành `vgar-schema-full-v2`, và băm nội dung file deploy
  (§5.5) ở cuối `_calculate_graph_version`.
- **Báo cáo:** `statistics.arch` như §7.

## 5. Quy tắc lift

### 5.1 Chia Component

Định nghĩa: **package** là thư mục có `__init__.py` ([cp] 82). File test là file mà `_is_test_path` (`builder.py:1997`) trả True. Package test là package mà
`_is_test_path(<dir>/__init__.py)` trả True.

**Quy tắc (đề xuất):**

1. Đếm số package không phải test.
2. **Từ 2 trở lên, chế độ `package`:** mỗi package không phải test là một Component. File thuộc package gần nhất chứa nó. File không thuộc package nào không vào Component.
3. **Dưới 2, chế độ `module`:** mỗi file `.py` không phải test là một Component. Riêng `__init__.py` không định nghĩa Class, Function, Method nào thì bỏ.

[cp] chỉ gợi ý vế 2. Vế 3 là bổ sung, vì nếu không thì repo một package như `vgar-demo-shop` chỉ có một Component và không có cạnh nào để viết đáp án ([plan] Phụ lục B #3).

File test không bao giờ thuộc Component. File không có node Module (parse lỗi) cũng không thuộc Component và được tính vào `unassigned_source_files`; package chỉ được tính khi `__init__.py` của nó có node Module **(đề xuất)**.

### 5.2 Tám tín hiệu của [P] 576–585

Chỉ tín hiệu đầu quyết định ranh giới. Các tín hiệu khác ghi vào thuộc tính **(đề xuất)**.

| Tín hiệu | Vai trò |
|---|---|
| package/module path | Ranh giới Component (§5.1) |
| import/call density | `weight`, cohesion, coupling (§5.3) |
| class ownership | Gán Class, Function, Method vào Component theo file chứa nó |
| naming convention | Nhận diện file và package test |
| framework route/config | Route đánh dấu Port (§5.4); ConfigEntry tạo `CONFIGURES` (§5.6) |
| co-change history | `unavailable` cho tới khi có L4-1 |
| deployment/config files | DeploymentUnit, Service (§5.5) |
| test grouping | `properties.tests` của Component |

### 5.3 `DEPENDS_ON`, cohesion, coupling

**Cạnh được đếm (đề xuất):** `CALLS` (từ path của CallSite tới path của đích) và `IMPORTS` (từ path của Import tới path của Module nội bộ). `MAY_CALL` không được đếm vì là ứng viên độ tin cậy thấp.
Đầu cạnh không thuộc Component nào, như test hay script, thì bỏ qua.

**`DEPENDS_ON`:** mỗi cặp có hướng (A, B), A khác B, có ít nhất một cạnh được đếm thì sinh một cạnh ([P] 609–612).

- `properties`: `weight` là tổng số cạnh ([P] 610), `call_count`, `import_count`.
- `confidence`: trung bình confidence của các cạnh được đếm, làm tròn 4 chữ số **(đề xuất)**.
- `provenance.evidence`: tối đa 5 id cạnh gốc, sắp xếp tăng dần **(đề xuất)**.

Phụ thuộc hai chiều được giữ nguyên ([P] 285–293).

**Cohesion, coupling** theo [P] 590–595, `epsilon = 1e-9`, làm tròn 6 chữ số:

- `internal_dependency_weight`: số cạnh được đếm có cả hai đầu trong Component.
- `external_dependency_weight`: số cạnh được đếm có đúng một đầu trong Component, đầu kia thuộc Component khác, tính **cả hai chiều** **(đề xuất, [P] không nói chiều)**.
- `number_of_entities_in_component`: số Class, Function, Method thuộc Component (không tính Test).

### 5.4 Port, `EXPOSES_PORT`, `CONSUMES_PORT`

`infer_public_ports`: mỗi `Function` hoặc `Method` thuộc Component là một Port khi thỏa **một** trong các điều kiện:

1. Tên không bắt đầu bằng `_` ([cp] 83).
2. Tên nằm trong `__all__` của chính module định nghĩa nó ([cp] 83).
3. Là handler của một Route **(đề xuất)**. Chỉ có khi bật tree-sitter-graph.

Loại trừ **(đề xuất)**: hàm lồng trong hàm, method của class có tên bắt đầu bằng `_`.

`__all__`: chỉ đọc phép gán cấp module với list hoặc tuple toàn literal chuỗi, bằng `ast`, và chỉ parse file có chứa chuỗi `__all__` **(đề xuất)**. Dạng khác (`__all__ += ...`, biểu thức) thì bỏ qua. Tên re-export không tạo Port ở module re-export; Port thuộc Component định nghĩa symbol đó.

**Node Port:** `path` và `range` lấy từ symbol. Port không thuộc `SOURCE_BACKED_NODE_TYPES`, vì nhóm đó bắt buộc có cạnh `CONTAINS` tới file (`structural_check.py:143-145`) mà Port thì không có (sửa khi thực hiện, 09/11). `name` là tên ngắn, `qualified_name` là tên đầy đủ của symbol, id là `vgar:{repo}:python:port:{path}:{qualified_name}`.
`properties`: `symbol_id`, `signature`, `owner_component_id`, `kind` (`function` hoặc `method`), `export` (`public_name`, `dunder_all` hoặc `route`), `routes` (danh sách tên Route, có thể rỗng).

Định danh Port gắn với symbol, chữ ký nằm ở thuộc tính **(đề xuất)**, nên đổi chữ ký vẫn là cùng một port bị thay đổi ([P] 1235).

- **`EXPOSES_PORT`** ([P] 265): Component → mỗi Port của nó. `confidence` 1.0, `resolution` `exact`.
- **`CONSUMES_PORT`** ([P] 266, 279): Component A → Port của Component B, A khác B, khi A có `CALLS` tới symbol của Port đó. `properties.call_count`. `confidence` là giá trị lớn nhất của các cạnh `CALLS` đó, `resolution` `heuristic` **(đề xuất)**.

Giới hạn đã biết: gọi constructor (`CALLS` tới Class) có tính vào `weight` nhưng không tạo `CONSUMES_PORT`, vì [cp] 83 định nghĩa Port là hàm hoặc method.

### 5.5 Module, Service, DeploymentUnit, Connector, ExternalSystem

**Module, `CONTAINS_COMPONENT`:** dùng lại node Module sẵn có của `G_repo`, không tạo node thứ hai **(đề xuất)**. Mỗi Component có một cạnh, từ Module của `__init__.py` trong chế độ `package`, hoặc Module của chính file trong chế độ `module`.

**File deploy:** tìm theo `IGNORED_DIRECTORY_NAMES` của builder. Đây là phần đề xuất, vì [P] chỉ nêu "deployment/config files" (583) mà không có luật.

| Loại | Điều kiện sinh |
|---|---|
| **DeploymentUnit** | Mỗi file tên `Dockerfile`, `Dockerfile.*` hoặc `*.Dockerfile`. Id `vgar:{repo}:deployment_unit:{path}`, `path` là file đó, không source-backed |
| **`DEPLOYS_TO`** | Component có thư mục (chế độ `package`) hoặc file (chế độ `module`) nằm trong nguồn của `COPY`/`ADD` không có `--from=`. Nguồn tính tương đối theo thư mục chứa Dockerfile. `confidence` 0.6 |
| **Service** | Mỗi khóa trong `services:` của `docker-compose*.y(a)ml` hoặc `compose.y(a)ml`. Id `vgar:{repo}:service:{compose_path}:{name}`. `properties`: `image`, `build_context`, `compose_file` |
| **`COMMUNICATES_WITH`** | Từ Service tới Service có trong `depends_on` (dạng list hoặc map), cùng file compose. `confidence` 0.7 |

Đọc YAML bằng `yaml.safe_load`, thêm `pyyaml` vào `dependencies` của `pyproject.toml`. File không đọc được thì bỏ qua và ghi vào `statistics.arch.deployment.errors`.

**Connector, ExternalSystem:** khai báo trong schema, **không có luật sinh** **(đề xuất)**. [P] chỉ nêu tên (254, 258), và node Module ngoài repo gồm cả `dataclasses`, `pytest` nên không thể coi là hệ thống ngoài. GA-2 vì vậy còn thiếu phần này cho tới khi nhóm định nghĩa.

### 5.6 `CONFIGURES` (đóng L1-3)

Theo spec Layer 1 §7: `ConfigEntry --CONFIGURES--> Component` cho mỗi Component có ít nhất một reader (`REFERENCES` tới ConfigEntry, từ node có path thuộc Component). `properties.reader_count`. `confidence` 0.8, `resolution` `heuristic`.
ConfigEntry chỉ có khi bật tree-sitter-graph, nên cạnh này cũng chỉ có khi đó.

### 5.7 Node Component

Không source-backed, `path` và `range` là `None`. Id `vgar:{repo}:python:component:{key}`, `key` là thư mục (chế độ `package`) hoặc path bỏ `.py` (chế độ `module`). `qualified_name` là tên module, `name` là phần cuối của nó.

`properties`: `kind`, `files`, `tests`, `entity_count`, `cohesion`, `coupling`, `internal_dependency_weight`, `external_dependency_weight`.

- `files`: path tăng dần ([P] 1060).
- `tests`: path của các file có node Test với cạnh `TESTS` tới entity trong Component, tăng dần ([P] 1064).

Trường chung của node mới **(đề xuất)**: `language` là `python` cho Component, Port và `None` cho DeploymentUnit, Service. `content_hash` của Port lấy từ symbol; các loại còn lại là `_hash_text` của id.

Mọi cạnh của lift dùng `rule_id` dạng `python.arch.<tên>.v1` và `source_tool` là `vgar-arch-lift` **(đề xuất)**. Thứ tự node, cạnh phải xác định: cùng đầu vào cho cùng đầu ra.

## 6. Thay đổi schema

Trong `schema.py`, ghi chú "proposed, pending team review" như các loại trước **(TV2 chốt 08/11)**:

- `NODE_TYPES` thêm Component, Port, Connector, Service, DeploymentUnit, ExternalSystem. Module đã có.
- `EDGE_ENDPOINTS` thêm:
  - `DEPENDS_ON`: (Component, Component). GT-1 sẽ thêm cặp Requirement.
  - `EXPOSES_PORT`, `CONSUMES_PORT`: (Component, Port).
  - `COMMUNICATES_WITH`: (Service, Service).
  - `CONTAINS_COMPONENT`: (Module, Component).
  - `DEPLOYS_TO`: (Component, DeploymentUnit).
  - `CONFIGURES`: (ConfigEntry, Component) và (ConfigEntry, Service) ([P] 236).
- `delta` (thuộc tính bắt buộc theo từng loại) để cho SC-1, spec này không làm.

Truy vấn subgraph ở `sqlite_store.py:541` loại thêm các cạnh `G_arch` để hành vi hiện có không đổi **(đề xuất)**. Tool mới sẽ do TV1 thêm ở L6-3.

## 7. Báo cáo `statistics.arch`

```json
{
  "mode": "package",
  "component_count": 7,
  "port_count": 1000,
  "unassigned_source_files": 5,
  "signals": {"package_path": "used", "density": "used", "class_ownership": "used", "naming": "used",
              "route_config": "absent", "co_change": "unavailable", "deployment": "absent", "test_grouping": "used"},
  "deployment": {"dockerfiles": 0, "compose_files": 0, "errors": []}
}
```

Giá trị trong `signals`: `used`, `absent` (đã tìm, repo không có hoặc chưa bật tree-sitter-graph), `unavailable` (chưa có nguồn).

## 8. Test và tiêu chí nghiệm thu

Tất cả là test tầng 1, không cần LLM ([test] mục 1). `vgar-demo-shop` nằm ngoài repo này nên CI dùng fixture riêng.

**Fixture viết tay:** `tests/fixtures/vgar-arch-cases/`, đáp án viết tay, không sinh từ code lift.

| Repo mẫu | Phải kiểm |
|---|---|
| `multi_package` (từ 2 package trở lên) | Chế độ `package`; package test bị loại; file ngoài package; `__all__` có tên riêng tư; hàm lồng; method của class `_X`; re-export; phụ thuộc hai chiều; Dockerfile có `COPY`; compose có `depends_on`; file compose hỏng |
| `single_package` | Chế độ `module`; bỏ `__init__.py` rỗng; `DEPENDS_ON` và `weight` |
| `flat_scripts` (không có package) | Chế độ `module` |
| Có route và env, chạy với tree-sitter-graph thật | Handler `_x` có route thành Port; `CONFIGURES` và `reader_count`. Tự skip nếu thiếu `VGAR_TSG_*`, như các test Layer 1 |

**Tiêu chí:**

1. Node, cạnh của từng fixture khớp đúng đáp án viết tay, gồm cả `weight`, cohesion và coupling tính tay.
2. Repo không có file Python cho 0 Component, graph vẫn hợp lệ.
3. Graph qua `validate_graph_document`. `MAY_CALL` không làm thay đổi `weight`.
4. **Chỉ thêm vào:** bỏ `G_arch` thì node, cạnh còn lại giống hệt graph trước spec này.
5. **Incremental:** sửa một file rồi cập nhật, `G_arch` giống hệt lần build lại toàn bộ.
6. Test tầng 1 của Layer 1–3 ([plan] Tuần 2, ngày 1) vẫn xanh, cộng các test mới: `test_graph_builder.py`, `test_graph_builder_robustness.py`, `test_graph_schema.py`, `test_incremental.py`, `test_impact.py`, `test_graph_retrieval.py`, `test_scip_enrichment.py`, `test_lsp_enrichment.py`, `test_task_anchors.py`, `test_tsg_enrichment.py`, `test_layer1_facts.py`, `test_may_call.py`, `test_callgraph_cases.py`. Test của các plan trước không phải tiêu chí. Test cũ chỉ được sửa khi nó ghim cứng tổng số node, cạnh hoặc giá trị định danh, và mỗi lần sửa phải ghi vào báo cáo chạy thật.
7. **Chạy thật trên `vgar-demo-shop`, static:** 7 Component, đúng 7 cạnh `DEPENDS_ON`:

   | Từ | Tới | `weight` |
   |---|---|---|
   | `cart` | `catalog` | 3 |
   | `checkout` | `cart` | 2 |
   | `checkout` | `discounts` | 2 |
   | `checkout` | `shipping` | 2 |
   | `checkout` | `tax` | 2 |
   | `discounts` | `money` | 2 |
   | `tax` | `money` | 2 |

8. **Một lần chạy kiểm tra trên `pydata__xarray-4629`** **(đề xuất)**, để phát hiện lỗi trước Ablation: graph qua validate, ghi số đếm vào báo cáo. Plan không bắt buộc GA chạy trên xarray. **Không dùng số của lần chạy này để chỉnh quy tắc.**

Báo cáo chạy thật ghi vào `docs/status/`, kèm lệnh tái tạo.

## 9. Phần để người triển khai tự quyết

- Cách chia hàm trong `arch_lift.py`, và cách truyền `evidence` qua `_add_edge`.
- Cấu trúc chi tiết của các fixture và định dạng file đáp án, miễn đủ các trường hợp ở §8.
- Vị trí cụ thể của pha lift trong đoạn `builder.py:231-247`, miễn là sau khi đã có đủ `CALLS`.

## 10. Câu hỏi mở cần nhóm trả lời

| # | Điểm | Ảnh hưởng |
|---|---|---|
| 1 | Connector và ExternalSystem sinh từ đâu? [P] chỉ nêu tên | GA-2 chưa đủ cho tới khi có câu trả lời |
| 2 | Schema mới vẫn "pending team review"; bản trả lời TV1 đang chờ TV2 ký | Hợp đồng "Sáng ngày 1" của plan |
