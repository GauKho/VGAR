# TV2 · Layer 1 còn lại: Identifier, Route, Schema, ConfigEntry, `IMPLEMENTS`, `CONFIGURES`

> **Trạng thái:** bản nháp, chờ duyệt. Soạn ngày 08/11/2026.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (gọi tắt **[plan]**) và
> proposal `D:\kltn\proposal_vgar_mcp_final_corrected.md` (gọi tắt **[P]**, dẫn số dòng).
>
> **Đánh dấu:** mục nào ghi **(TV2 chốt)** là anh/chị đã quyết trong phiên 08/11. Mục nào ghi **(đề xuất)**
> là lựa chọn của người viết spec, chờ duyệt.

## 1. Bối cảnh và lý do

Spec này lo phần còn lại của hai task Layer 1 trong plan:

| Task | Plan ghi | Đã có (L1-1, 08/11) | Spec này làm |
|---|---|---|---|
| **L1-2** (ngày 1) | node `Identifier`; cạnh `HAS_METHOD`, `HAS_CALLSITE` | `HAS_METHOD`, `HAS_CALLSITE` | `Identifier` |
| **L1-3** (ngày 2) | Field, GlobalVariable, ConfigEntry, Route, Schema; `IMPLEMENTS`, `CONFIGURES` | Field, GlobalVariable | ConfigEntry, Route, Schema, `IMPLEMENTS`. Riêng `CONFIGURES` chỉ chốt hợp đồng (xem §7) |

Các task khác sẽ đọc các node này:

- **GA-1 (lift `G_arch`):** dùng tín hiệu "framework route/config" và "deployment/config files" ([P] dòng 581, 583).
- **GT-1 (`G_task`):** issue `--MENTIONS--> [Route: POST /login]` ([P] dòng 336).
- **R1 (retrieval):** tập `F*` có cả `Route: POST /login` và `Config: PASSWORD_HASH_ALGO` ([P] dòng 805–807).
- **EV-2 của TV3 (check API):** "route path/method changed?" và "schema/protobuf/OpenAPI field removed?" ([P] dòng 1237–1238).
- **`IMPLEMENTS`:** đúng ví dụ mở đầu của proposal, "Class C implements Interface I" ([P] dòng 32).

## 2. Mục tiêu, phạm vi loại trừ, điều cần tránh

**Mục tiêu**

1. Graph do pipeline tạo ra (`build_graph.py`) có thêm bốn loại node Identifier, Route, Schema, ConfigEntry và cạnh
   `IMPLEMENTS`. Graph đó qua `validate_graph_document`. Đây cũng là tiêu chí xong của L1-1 **(TV2 chốt)**, áp dụng
   tương tự cho các task này.
2. Có test tầng 1 bằng `pytest`, so với đáp án viết tay trên repo mẫu ([plan] Phụ lục A.2 dòng 353, 368).

**Không làm trong spec này**

- `CONFIGURES` thật sự. Proposal định nghĩa cạnh này là `ConfigEntry -> Component/Service` ([P] dòng 236), nên phải
  đợi GA-2 tạo node Component. Spec này chỉ chốt hợp đồng (§7).
- ConfigEntry lấy từ file cấu hình (`.env`, `.ini`, `.toml`, `.yaml`). Graph chỉ dựng cho code Python ([plan]
  §1.1), và tree-sitter-graph mới được cấu hình grammar Python **(đề xuất)**.
- Schema lấy từ protobuf hay OpenAPI, cùng các thư viện ngoài danh sách ở §4.3.
- Gộp prefix của router/blueprint vào path của Route, vì prefix nằm ở file khác.
- Coi `Protocol` là được hiện thực khi class chỉ khớp về cấu trúc (structural typing) mà không kế thừa trực tiếp.
- Expose các loại mới ra MCP tool hoặc resource. Đó là L6-2, L6-3 của TV1.
- Builder incremental. Đó là L6-6 của TV1.

**Điều cần tránh** (vẫn tính là hỏng dù code chạy)

- Đổi graph mặc định, tức khi không bật tree-sitter-graph. Các thí nghiệm đang có phải giữ nguyên graph cũ.
- Đoán chỉ dựa vào tên. Ví dụ: coi mọi class có base tên `BaseModel` là Schema dù không import từ pydantic.
- Sinh cạnh có endpoint sai schema, hoặc làm `unmatched` khác rỗng trên repo thật mà không giải thích được.

## 3. Ràng buộc và quyết định đã chốt

- tree-sitter-graph là **nguồn fact bổ sung**: builder giữ nguyên phần tự trích, tree-sitter-graph chỉ thêm
  **(TV2 chốt)**.
- Dùng **đúng tên trong proposal**; các loại mới được ghi trong `schema.py` là "proposed, pending team review"
  **(TV2 chốt)**.
- Phụ thuộc **tùy chọn, có fallback** ([P] dòng 1476, 1462) **(TV2 chốt)**.
- **Quy tắc bật và tắt (đề xuất):** mọi fact Layer 1 mới, kể cả những fact không cần tới CLI, chỉ được thêm khi
  tree-sitter-graph chạy được (`statistics.tsg.status` là `ready` hoặc `partial`). Khi `fallback`, graph phải
  giống hệt graph thường, như test `test_missing_cli_falls_back_to_the_plain_graph` đang yêu cầu.
- Grammar là tree-sitter-python **v0.23.6** (ABI 14), vì CLI tree-sitter-graph 0.12 link với tree-sitter 0.24.

## 4. Thiết kế từng loại

Quy ước chung cho mọi loại:
- `repo_key`, `language: "python"`, `graph_version` và `content_hash` theo đúng quy ước builder đang dùng.
- Provenance có đủ `source_tool`, `rule_id`, `source_revision` ([P] dòng 559–567).
- Fact gắn với Discard hoặc với stub `@overload` thì bị bỏ, giống L1-1.

Mỗi loại lấy fact từ một nguồn **(đề xuất)**:

| Loại | Nguồn fact | Lý do |
|---|---|---|
| Identifier | Luật mới trong `tsg/python.tsg` | Builder chỉ ghi tên tham số, không ghi kiểu |
| ConfigEntry | Luật mới trong `tsg/python.tsg` | Builder không lưu literal của đối số |
| Route | `properties.decorators` của builder, đọc bằng `_static_route` (`graph/grounding.py:424`) | Dùng chung cách đọc với `find_task_anchors`, nên graph và grounding cho cùng kết quả |
| Schema, `IMPLEMENTS` | `properties.bases`/`decorators` của builder, node Import, cạnh `INHERITS` | Muốn xác nhận phải dùng thông tin import và kế thừa giữa nhiều file, việc tree-sitter-graph không làm được |

Mọi fact tính từ dữ liệu builder vẫn chỉ được thêm khi tree-sitter-graph chạy được (§3).

### 4.1 Identifier (L1-2)

- **Phạm vi:** chỉ **tham số của def**, đúng như ví dụ ở [P] dòng 530–531 (`Identifier: username`,
  `Identifier: password` của `login(self, username, password)`). Không phải mọi identifier trong thân hàm
  **(đề xuất)**.
  - Bỏ tham số đầu tiên tên `self` hoặc `cls` của Method, vì ví dụ trong proposal không có `self`.
  - Bỏ tham số của lambda, vì lambda không có node def.
- **Node:**
  - `type: "Identifier"`, `name` là tên tham số.
  - `qualified_name: "{def_qn}::<param:{name}>"`, theo kiểu `::<call:N>` của CallSite, để không trùng với một def
    lồng bên trong cùng tên.
  - `id: "vgar:{repo}:python:identifier:{path}:{def_qn}::<param:{name}>"`.
  - `range` là vị trí của identifier tham số.
  - `properties`:
    - `annotation`: chuỗi kiểu, hoặc `null`; tương ứng `IDENTIFIER[name, type]` ở [P] dòng 185;
    - `has_default`: bool;
    - `position`: chỉ số, bắt đầu từ 0, tính cả `self`/`cls` đã bỏ;
    - `kind`: `"normal"`, `"var_positional"` hoặc `"var_keyword"`.
- **Cạnh:** `Function|Method|Test --CONTAINS--> Identifier`, `rule_id: "python.tsg.identifier.v1"`,
  `source_tool: "tree-sitter-graph"`, `confidence: 1.0` **(đề xuất)**.
- **Ghép với builder:** tìm def theo (path, dòng, cột, tên) như L1-1. Def không khớp thì tính vào
  `unmatched.Identifier`.

### 4.2 ConfigEntry (L1-3)

- **Phạm vi:** khóa biến môi trường được **đọc** trong code Python với **khóa là string literal**. Các dạng được
  nhận **(đề xuất)**:
  - `os.getenv("K")` và `getenv("K")`;
  - `os.environ.get("K")` và `environ.get("K")`;
  - `os.environ["K"]` và `environ["K"]` khi đọc. Phép ghi `os.environ["K"] = ...` không tính.

  Khóa không phải literal, ví dụ f-string hay biến, thì bỏ qua.
- **Node:** mỗi khóa là **một node cho cả repo**, vì cùng một khóa được đọc ở nhiều nơi:
  - `type: "ConfigEntry"`, `name: "K"`, `qualified_name: "env:K"`, `id: "vgar:{repo}:config:env:K"`;
  - `path` và `range` để `null`. ConfigEntry **không** thuộc nhóm source-backed, giống Issue.
  - `properties`: `{"source": "environment", "read_sites": [{"path", "line"}...]}`, sắp theo path rồi theo dòng.
- **Cạnh:** `reader --REFERENCES--> ConfigEntry`.
  - Reader là def bao quanh chỗ đọc.
  - Lệnh đọc ở cấp module hoặc trong thân class, tức fact đang gắn với Discard, thì reader là **Module** của file
    đó **(đề xuất)**.
  - `rule_id: "python.tsg.config_env.v1"`, `properties: {"access": "getenv|environ_get|environ_subscript", "lines": [...]}`.
  - Một reader đọc cùng khóa nhiều lần chỉ có một cạnh; các dòng được gom vào `lines`.
- Hằng số cấu hình kiểu `PASSWORD_HASH_ALGO` ([P] dòng 806) đã có mặt dưới dạng GlobalVariable. Nhận diện module
  nào là module cấu hình là tín hiệu của GA-1, không làm ở đây.

### 4.3 Route (L1-3)

- **Phạm vi:** decorator trên Function/Method/Test mà `_static_route(decorator)` trả về `(path, methods)`. Hàm này
  chỉ nhận path literal bắt đầu bằng `/`, và verb là một HTTP method hoặc `route`/`api_route` có `methods=`.
- **Node:** mỗi cặp (handler, decorator) là một node:
  - `type: "Route"`, `name: "{METHODS} {path}"`. Các method sắp xếp và nối bằng `,`, ví dụ `"POST /login"`, đúng
    định dạng ở [P] dòng 336.
  - `qualified_name: "{handler_qn}::<route:{name}>"`; `id` theo cùng mẫu. Nếu một handler có hai decorator cho
    ra cùng `name`, chỉ tạo một node **(đề xuất)**.
  - `range` là range của handler, vì builder chỉ lưu chữ của decorator chứ không lưu vị trí của nó
    **(đề xuất)**.
  - `properties`:
    - `methods` (danh sách), `route_path`, `decorator` (nguyên văn);
    - `receiver`: tên ở trước dấu chấm, ví dụ `app` hay `router`. Giữ lại để sau này gộp prefix.
- **Cạnh:**
  - `Module --CONTAINS--> Route`;
  - `Route --REFERENCES--> handler`, với `confidence: 0.8`, `rule_id: "python.layer1.route.v1"`,
    `source_tool: "vgar-python-graph-builder"`. Mức 0.8 vì ta chỉ thấy cú pháp decorator, chưa xác nhận receiver là
    một ứng dụng web **(đề xuất)**.

### 4.4 Schema (L1-3)

- **Phạm vi:** class mô tả hình dạng dữ liệu, chỉ nhận khi **tên đã được xác nhận qua import**, không đoán theo
  tên **(đề xuất)**:
  - **(a)** decorator là `dataclass`, có import từ `dataclasses`. Gồm `@dataclass`, `@dataclass(...)`,
    `@dataclasses.dataclass`.
  - **(b)** base là `BaseModel`, có import từ `pydantic`.
  - **(c)** base là `TypedDict`, có import từ `typing` hoặc `typing_extensions`.
  - **(d)** class kế thừa, qua cạnh `INHERITS` ở bất kỳ độ sâu nào, từ một class trong repo đã là Schema theo
    (b) hoặc (c).
- **Cách xác nhận một tên:** so với các node Import của module chứa class. Tên khớp `alias or imported_name`, hoặc
  có dạng `alias_module.attr` với module tương ứng.
- **Node:**
  - `type: "Schema"`, `name` là tên class, `qualified_name: "{class_qn}::<schema>"`;
  - `range` là range của class;
  - `properties: {"schema_kind": "dataclass|pydantic|typed_dict", "evidence": "decorator|base|inherited"}`.
- **Cạnh:**
  - `Module --CONTAINS--> Schema`;
  - `Schema --REFERENCES--> Class`, với `confidence` là 1.0 cho (a), (b), (c) và 0.9 cho (d);
    `rule_id: "python.layer1.schema.v1"`.
- Các field của schema chính là các node `Class --CONTAINS--> Field` đã có từ L1-1.

### 4.5 `IMPLEMENTS` (L1-3)

- **Interface:** proposal viết "Class -> Interface" ([P] dòng 233) nhưng không có node type Interface. Vì vậy
  interface ở đây là **một Class trong repo** thỏa một trong các điều kiện dưới, và tên phải được xác nhận qua import
  như §4.4 **(đề xuất)**:
  - base là `ABC` (từ `abc`);
  - base là `Protocol` (từ `typing` hoặc `typing_extensions`);
  - có `metaclass=ABCMeta` (từ `abc`). Builder ghi dạng này là `"metaclass=ABCMeta"` trong `bases`.
- **Cạnh:** với mỗi cạnh `INHERITS` A → B mà B là interface và **A không phải interface**, thêm
  `A --IMPLEMENTS--> B`. Một interface kế thừa interface khác là mở rộng, không phải hiện thực.
  - `confidence` lấy bằng confidence của cạnh `INHERITS`;
  - `properties: {"interface_kind": "abc|protocol"}`;
  - `rule_id: "python.layer1.implements.v1"`.
- Chỉ xét kế thừa trực tiếp: `A(B)`, `B(Base)`, `Base(ABC)` cho ra `B IMPLEMENTS Base`, nhưng không cho ra
  `A IMPLEMENTS Base`.

## 5. Thay đổi trong `contracts/schema.py`

Mọi dòng thêm vào đều kèm chú thích "Proposed … pending team review" và dẫn dòng proposal, như đã làm ở L1-1.

| Tập hợp | Thêm |
|---|---|
| `NODE_TYPES` | `Identifier`, `Route`, `Schema`, `ConfigEntry` |
| `SOURCE_BACKED_NODE_TYPES` | `Identifier`, `Route`, `Schema` (không có ConfigEntry) |
| `EDGE_ENDPOINTS["CONTAINS"]` | `(Function\|Method\|Test, Identifier)`, `(Module, Route)`, `(Module, Schema)` |
| `EDGE_ENDPOINTS["REFERENCES"]` | `(Route, Function\|Method\|Test)`, `(Schema, Class)`, `(Module\|Function\|Method\|Test, ConfigEntry)` |
| `EDGE_ENDPOINTS["IMPLEMENTS"]` (mới) | `(Class, Class)` |

## 6. Ghép vào pipeline

- **Vị trí:**
  - Fact từ tree-sitter-graph (Identifier, ConfigEntry) được ghép trong `_merge_tsg_facts`, cùng chỗ với L1-1.
  - Fact tính từ dữ liệu builder (Route, Schema, `IMPLEMENTS`) cần cạnh `INHERITS` và Import đã được liên kết, nên
    phải chạy **sau** `_link_inheritance()` và **trước** `_validate`.
- **Báo cáo:** `statistics.tsg.added` và `statistics.tsg.unmatched` ghi thêm số đếm theo từng loại mới. Không thêm
  trường báo cáo nào khác **(đề xuất)**.
- **`graph_version`:** nhãn `tsg-facts-v1` đổi thành `tsg-facts-v2`. Đổi nhãn vì quy tắc tính các fact từ dữ liệu
  builder có thay đổi, mà các quy tắc này không nằm trong file `.tsg` nên mã băm của file luật không phản ánh được.
- **Không đổi gì khi `tsg=None`.**

## 7. Hợp đồng cho `CONFIGURES` (làm ở GA-2)

Khi GA-2 đã có node Component **(đề xuất)**:
- thêm `ConfigEntry --CONFIGURES--> Component` cho mỗi Component có chứa ít nhất một reader của ConfigEntry đó;
- `properties: {"reader_count": n}`;
- chỉ thêm vào `EDGE_ENDPOINTS` lúc GA-2 thêm Component.

Spec này **không** thêm `CONFIGURES` vào schema.

## 8. Test và tiêu chí nghiệm thu

Tất cả là test tầng 1, không cần LLM ([plan] Phụ lục A.2).

1. **Repo mẫu viết tay** trong `tests/`, mỗi loại một nhóm, so với tập kết quả mong đợi viết tay. Phải có các
   trường hợp âm:
   - tham số `self`/`cls`, lambda, `*args`/`**kwargs`;
   - khóa môi trường là f-string, phép ghi `os.environ[...] = ...`;
   - route có path không phải literal, decorator `@x.get` không có path;
   - `BaseModel` tự định nghĩa trong repo (không phải Schema), dataclass dùng alias, Schema qua kế thừa;
   - `Protocol` kế thừa `Protocol` (không phải `IMPLEMENTS`), `metaclass=ABCMeta`.
2. **Fact giả cho phần tree-sitter-graph** (Identifier, ConfigEntry), cộng một test với CLI thật để chứng minh fact
   giả đúng với những gì CLI xuất ra. Test này tự skip nếu không có `VGAR_TSG_EXECUTABLE` và
   `VGAR_TSG_TREE_SITTER_DIR`, như test L1-1 đang làm.
3. **Fallback:** thiếu CLI thì graph giống hệt graph thường. Test cũ phải tiếp tục pass.
4. **Lưu và đọc lại qua SQLite** (`SQLiteGraphStore.ingest` rồi `load_document`) vẫn qua validate.
5. **Không hồi quy:** khi `tsg=None`, nhóm test graph đang có (985 test ngày 08/11) đều pass.
6. **Chạy thật** `build_graph.py --tsg-*` trên vgar-demo-shop và `pydata__xarray-4629` @ `a41edc7b`:
   - graph qua validate;
   - `unmatched` rỗng, hoặc mỗi mục lệch đều có lý do ghi trong báo cáo;
   - ghi lại số đếm từng loại và thời gian build.

**Xong** khi đạt cả 6 mục trên. Đây là phần đóng góp của Layer 1 vào cổng cuối Tuần 1, mục #1 và #3
([plan] dòng 155, 157).

## 9. Điểm chờ duyệt (xếp theo mức ảnh hưởng)

1. **Phạm vi Identifier:** chỉ tham số (theo ví dụ [P] dòng 530–531), hay mọi identifier? Mọi identifier sẽ làm số
   node tăng rất mạnh. Ví dụ, xarray có hơn 32 nghìn CallSite.
2. **Phạm vi ConfigEntry:** chỉ biến môi trường đọc trong code Python, hay cả file cấu hình?
3. **Quy tắc bật và tắt (§3):** Route, Schema, `IMPLEMENTS` không cần CLI nhưng vẫn chỉ xuất hiện khi
   tree-sitter-graph chạy được, để fallback giữ nguyên graph cũ.
4. **Tên và endpoint cạnh:** dùng `REFERENCES` cho Route → handler, Schema → Class, reader → ConfigEntry, vì proposal
   ghi `REFERENCES: Entity -> Entity` ([P] dòng 234) và không có tên cạnh riêng cho các quan hệ này.
5. Các mức confidence 0.8 (Route) và 0.9 (Schema qua kế thừa).

## 10. Để người làm tự quyết

- Pattern cụ thể của các stanza `.tsg` cho tham số và cho lệnh đọc biến môi trường.
- Cách tổ chức hàm trong builder. Nếu `builder.py` dài thêm quá nhiều, có thể tách phần tính Route, Schema,
  `IMPLEMENTS` ra một module riêng.
- Tên file test, và dùng chung hay tách riêng repo mẫu cho từng loại.
