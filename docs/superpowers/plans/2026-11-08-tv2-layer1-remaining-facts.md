# Plan triển khai: Layer 1 còn lại của TV2 (Identifier, ConfigEntry, Route, Schema, `IMPLEMENTS`)

> **Dành cho agent thực thi:** BẮT BUỘC dùng kèm skill superpowers:subagent-driven-development (khuyến nghị)
> hoặc superpowers:executing-plans để làm plan này theo từng task. Mỗi bước có ô `- [ ]` để đánh dấu tiến độ.

**Mục tiêu:** Khi bật tree-sitter-graph, graph do `build_graph.py` tạo ra có thêm node Identifier, ConfigEntry,
Route, Schema và cạnh `IMPLEMENTS`, và graph đó qua `validate_graph_document`.

**Kiến trúc:**
- Identifier và ConfigEntry là fact cú pháp trong từng file. Chúng đến từ luật mới trong
  `src/vgar/graph/tsg/python.tsg` và được ghép trong `PythonGraphBuilder._merge_tsg_facts`.
- Route, Schema và `IMPLEMENTS` được tính từ dữ liệu builder đã có: `properties.decorators`/`bases`, node Import,
  cạnh `INHERITS`. Các luật thuần (không phụ thuộc builder) nằm ở module mới `src/vgar/graph/layer1_rules.py`.
  Builder gọi chúng trong `_derive_layer1_facts()`, chạy sau `_link_inheritance()`.
- Mọi fact mới chỉ được thêm khi `statistics.tsg.status` là `ready` hoặc `partial`.

**Công nghệ:** Python 3.11, py-tree-sitter 0.25.2, CLI tree-sitter-graph 0.12.0, grammar tree-sitter-python
v0.23.6, pytest.

**Spec:** `docs/superpowers/specs/2026-11-08-tv2-layer1-remaining-facts-design.md`. Người thực thi phải đọc cả
spec lẫn plan.

## Ràng buộc chung

- Chỉ dùng hai nguồn: plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` và proposal. Không tự mở rộng
  phạm vi.
- **Không đổi graph khi `tsg=None`.** Khi `tsg` có nhưng status là `fallback`, graph phải giống hệt graph thường.
- Mọi dòng thêm vào `src/vgar/contracts/schema.py` đều kèm chú thích `Proposed ... pending team review` và dẫn
  dòng proposal.
- Provenance của cạnh mới:
  - cạnh từ tree-sitter-graph: `source_tool: "tree-sitter-graph"`;
  - cạnh tính từ dữ liệu builder: `source_tool: "vgar-python-graph-builder"` (giá trị mặc định của `_add_edge`).
- Các `rule_id`: `python.tsg.identifier.v1`, `python.tsg.config_env.v1`, `python.layer1.route.v1`,
  `python.layer1.schema.v1`, `python.layer1.implements.v1`.
- Các mức confidence: Identifier 1.0; ConfigEntry 1.0; Route 0.8; Schema 1.0 cho (a)/(b)/(c) và 0.9 cho (d);
  `IMPLEMENTS` lấy bằng confidence của cạnh `INHERITS` tương ứng.
- **Người dùng tự commit.** Ở mỗi bước "Commit", agent dừng lại, liệt kê file và đưa lệnh `git add`/`git commit`.
  Agent không tự chạy hai lệnh đó.
- **Test với CLI thật** chỉ chạy khi có `VGAR_TSG_EXECUTABLE` và `VGAR_TSG_TREE_SITTER_DIR`, và khi PATH có gcc
  (WinLibs `D:\tools\winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r3\mingw64\bin`). Thiếu thì test
  tự skip.
- **Lệnh test chuẩn:** `python -m pytest -q -p no:cacheprovider <file>`. Nhóm test graph để kiểm tra hồi quy là
  danh sách đã dùng ngày 08/11, gồm các file `tests/test_graph_*.py`, `test_incremental.py`, `test_impact.py`,
  `test_graph_retrieval.py`, `tests/m2/w1112` và các file liên quan. Mốc so sánh: 985 passed.

## Trọng tâm rà soát

Năm tình huống spec không nói tới nhưng dễ gây lỗi nhất. Mỗi dòng có một test, nằm trong task phụ trách phần
code đó.

1. **File có lỗi cú pháp.** Build vẫn chạy xong, graph qua validate, và fact của các file khác vẫn có mặt.
   Test ở Task 6.
2. **Def trùng tên trong nhánh `if`/`else`.** Builder gán id có hậu tố `@definition:dòng:cột` cho def thứ hai.
   Identifier của hai def phải có id khác nhau, không được nổ lỗi trùng id. Test ở Task 1.
3. **File dùng xuống dòng CRLF.** `start_byte`/`end_byte` của node mới phải đúng với byte thật của file.
   Test ở Task 1.
4. **Lệnh đọc biến môi trường trong thân class hoặc bên trong lambda.** Đọc trong thân class thì reader là Module.
   Đọc trong lambda nằm trong hàm thì reader là hàm đó. Test ở Task 2.
5. **Hai class/handler trùng qualified name** (duplicate định nghĩa). Node Schema/Route có id duy nhất theo cùng
   quy tắc hậu tố. Test ở Task 4.

---

### Task 1: Identifier (tham số của def)

**Files:**
- Sửa: `src/vgar/graph/tsg/python.tsg` (thêm stanza cho tham số)
- Sửa: `src/vgar/graph/builder.py` (`_merge_tsg_facts`)
- Sửa: `src/vgar/contracts/schema.py`
- Test: `tests/test_tsg_enrichment.py`

**Giao diện:**
- Dùng lại: `TsgFileFacts`, `run_file`, `_merge_tsg_facts`, `_add_tsg_symbol` của L1-1.
- Tạo ra: fact tree-sitter-graph có `type: "Identifier"`, các thuộc tính `name`, `line`, `col`, `end_line`,
  `end_col`, `kind` (`"normal"` | `"var_positional"` | `"var_keyword"`), và tùy chọn `annotation` (chuỗi),
  `has_default` (`"yes"`). Có cạnh từ node def tới Identifier, nhãn `"CONTAINS"`.

- [ ] **Bước 1: Viết test fail**
  - Mở rộng `FAKE_FACTS` và `EXPECTED` trong `tests/test_tsg_enrichment.py` với các Identifier của `SOURCE`:
    `self` và `sku` của `add`, `sku` của `check`.
  - `_facts_summary` thêm khóa `"Identifier"` (danh sách `qualified_name` đã sắp xếp).
  - `EXPECTED["Identifier"] == ["app.Cart.add::<param:sku>", "app.check::<param:sku>"]` (không có `self`).
  - `EXPECTED["CONTAINS"]` thêm `("app.Cart.add", "app.Cart.add::<param:sku>")` và
    `("app.check", "app.check::<param:sku>")`.
  - Thêm `test_identifier_properties_and_duplicate_defs` (dùng fact giả). Repo có file `src/dup.py` với xuống dòng
    **CRLF**: `"if X:\r\n    def f(a):\r\n        pass\r\nelse:\r\n    def f(a):\r\n        pass\r\n"`. Kiểm tra:
    - có 2 node Identifier tên `a`, id khác nhau, và id thứ hai kết thúc bằng `@definition:5:10`;
    - Identifier đầu có `range["start_byte"] == 17`, `range["end_byte"] == 18`, `content_hash` bằng
      sha256 của `b"a"`;
    - `properties == {"annotation": None, "has_default": False, "position": 0, "kind": "normal"}`.
  - Thêm `test_real_cli_identifier_kinds` (skip khi thiếu CLI) trên đoạn code
    `"def f(a, b: int, c=1, d: str = 'x', *args, e, **kw): pass\nclass K:\n    @classmethod\n    def m(cls, x): pass\nlam = lambda z: z\n"`.
    Kiểm tra theo thứ tự:
    - `a(0, normal)`, `b(1, annotation "int")`, `c(2, has_default)`, `d(3, "str", has_default)`,
      `args(4, var_positional)`, `e(5, normal)`, `kw(6, var_keyword)`;
    - với `K.m`: chỉ có `x`, `position == 1`;
    - không có Identifier nào tên `z`.

- [ ] **Bước 2: Chạy test, xác nhận fail**
  Lệnh: `python -m pytest -q -p no:cacheprovider tests/test_tsg_enrichment.py`
  Mong đợi: FAIL ở khóa `Identifier` (graph chưa có node Identifier).

- [ ] **Bước 3: Thêm vào `schema.py`**
  - `NODE_TYPES` và `SOURCE_BACKED_NODE_TYPES` thêm `"Identifier"`.
  - `CONTAINS` thêm `(Function, Identifier)`, `(Method, Identifier)`, `(Test, Identifier)`.
  - Chú thích dẫn [P] dòng 185 và 530–531.

- [ ] **Bước 4: Thêm stanza cho tham số vào `python.tsg`**
  - Các node tham số con của `(function_definition parameters: (parameters ...))`: `identifier`,
    `typed_parameter`, `default_parameter`, `typed_default_parameter`, `list_splat_pattern`,
    `dictionary_splat_pattern`. Dạng `typed_parameter` có thể bọc splat, như `*xs: int`.
  - `annotation` lấy bằng `source-text` của field `type`.
  - Chỉ tạo stanza dưới `parameters`, nên tham số lambda (`lambda_parameters`) tự động bị loại.

- [ ] **Bước 5: Ghép trong `_merge_tsg_facts`**
  - Với mỗi def đã ghép được: sắp Identifier của nó theo `(line, col)`, đánh `position` từ 0, rồi bỏ phần tử đầu
    nếu def là `Method` và tên là `self` hoặc `cls`.
  - Tạo node bằng `_add_tsg_symbol`, hoặc một biến thể có thêm tham số `qualified_name`, với
    `qualified_name = f"{def_qn}::<param:{name}>"`. Khi id trùng thì thêm hậu tố `@definition:{line}:{col}`, giống
    L1-1.
  - `properties` gồm 4 khóa như Bước 1.
  - Cạnh `CONTAINS` có `rule_id="python.tsg.identifier.v1"`.
  - Đếm vào `added["Identifier"]`. Identifier có def không ghép được thì tính vào `unmatched["Identifier"]`.

- [ ] **Bước 6: Chạy test, xác nhận pass**
  - Lệnh với CLI thật:
    `VGAR_TSG_EXECUTABLE=... VGAR_TSG_TREE_SITTER_DIR=... python -m pytest -q -p no:cacheprovider tests/test_tsg_enrichment.py`
    Mong đợi: tất cả PASS, kể cả `test_real_cli_emits_the_same_facts` với `FAKE_FACTS` đã mở rộng.
  - Chạy thêm nhóm test graph. Mong đợi: 985 passed, không hồi quy.

- [ ] **Bước 7: Commit** (người dùng tự chạy)
  `git add src/vgar/graph/tsg/python.tsg src/vgar/graph/builder.py src/vgar/contracts/schema.py tests/test_tsg_enrichment.py`
  `git commit -m "feat(graph): L1-2 Identifier nodes for def parameters via tree-sitter-graph"`

### Task 2: ConfigEntry (biến môi trường đọc trong code)

**Files:**
- Sửa: `src/vgar/graph/tsg/python.tsg`, `src/vgar/graph/builder.py`, `src/vgar/contracts/schema.py`
- Test: `tests/test_tsg_enrichment.py`

**Giao diện:**
- Tạo ra: fact tree-sitter-graph `type: "ConfigRead"` với `key` (nội dung chuỗi, không có dấu nháy), `access`
  (`"getenv"` | `"environ_get"` | `"environ_subscript"`), `line`, `col`, `end_line`, `end_col`, và tùy chọn
  `write: "yes"`. Có cạnh từ `.enclosing_def` (có thể là Discard) tới fact đó, nhãn `"REFERENCES"`.

- [ ] **Bước 1: Viết test fail `test_config_entries_across_files`** (fact giả; `run_file` được monkeypatch, trả fact
  theo path)
  - `src/cfg.py`:
    `"import os\nDEBUG = os.getenv('DEBUG')\nclass Settings:\n    url = os.environ['DB_URL']\ndef load():\n    a = os.environ.get('DB_URL')\n    b = os.environ.get('DB_URL')\n    os.environ['MODE'] = 'x'\n    f = lambda: os.getenv('LAMBDA_KEY')\n    return a, b, f\n"`
  - `src/other.py`: `"import os\nKEY = os.getenv('DEBUG')\n"`
  - Kiểm tra:
    - Có đúng các node ConfigEntry `env:DB_URL`, `env:DEBUG`, `env:LAMBDA_KEY`. Không có `env:MODE`, vì đó là
      phép ghi.
    - `env:DEBUG`: `path is None`, `range is None`,
      `properties == {"source": "environment", "read_sites": [{"path": "src/cfg.py", "line": 2}, {"path": "src/other.py", "line": 2}]}`.
    - Các cạnh `REFERENCES` (nguồn → đích, `lines`, `access`):
      - `cfg → env:DEBUG`, `[2]`, `"getenv"`;
      - `cfg → env:DB_URL`, `[4]`, `"environ_subscript"` (đọc trong thân class nên reader là Module);
      - `cfg.load → env:DB_URL`, `[6, 7]`, `"environ_get"`;
      - `cfg.load → env:LAMBDA_KEY`, `[9]`, `"getenv"`;
      - `other → env:DEBUG`, `[2]`, `"getenv"`.
    - Graph qua `validate_graph_document`.
  - Thêm `test_real_cli_config_reads` (skip khi thiếu CLI). Dùng file `src/cfg.py` ở trên cộng thêm dòng
    `    c = os.getenv(f"K{a}")` đặt trong `load`. Kiểm tra `_canonical(run_file(...))` bằng `_canonical` của fact giả;
    fact giả không có mục nào cho f-string.

- [ ] **Bước 2: Chạy test, xác nhận fail**
  Lệnh: `python -m pytest -q -p no:cacheprovider tests/test_tsg_enrichment.py -k config`
  Mong đợi: FAIL (chưa có ConfigEntry).

- [ ] **Bước 3: Thêm vào `schema.py`**
  - `NODE_TYPES` thêm `"ConfigEntry"`. **Không** thêm vào `SOURCE_BACKED_NODE_TYPES`.
  - `REFERENCES` thêm `(Module|Function|Method|Test, ConfigEntry)`.
  - Chú thích dẫn [P] dòng 221 và 806.

- [ ] **Bước 4: Thêm stanza vào `python.tsg`**
  - Ba dạng đọc:
    - `os.getenv("K")` / `getenv("K")`;
    - `os.environ.get("K")` / `environ.get("K")`;
    - `os.environ["K"]` / `environ["K"]`.
  - Lọc tên bằng predicate `#eq?`.
  - Khóa chỉ nhận khi là `(string (string_start) (string_content) (string_end))` có anchor, tức không có
    `interpolation`.
  - Thêm một stanza riêng cho `(assignment left: (subscript ...) @s)` để gán `write = "yes"` lên node của `@s`.

- [ ] **Bước 5: Ghép**
  - Gom ConfigRead của **mọi file** trước, sau khi vòng lặp file đã chạy xong. Bỏ các read có `write`.
  - Reader của read là def đã ghép được. Nếu nguồn là Discard thì reader là Module của file.
  - Mỗi khóa tạo một node: `id = f"vgar:{repo}:config:env:{key}"`, `qualified_name = f"env:{key}"`,
    `language: "python"`, `content_hash = _hash_text(f"env:{key}")`.
  - Mỗi cặp (reader, key) một cạnh, `properties = {"access": <các access sắp xếp, nối bằng ",">, "lines": [...]}`.
  - Đếm vào `added["ConfigEntry"]`.

- [ ] **Bước 6: Chạy test, xác nhận pass**
  Chạy `tests/test_tsg_enrichment.py` với CLI thật, rồi chạy nhóm test graph. Mong đợi: PASS hết, 985 test graph
  vẫn pass.

- [ ] **Bước 7: Commit** (người dùng tự chạy)
  `git commit -m "feat(graph): L1-3 ConfigEntry for environment reads via tree-sitter-graph"`

### Task 3: Route

**Files:**
- Tạo: `src/vgar/graph/layer1_rules.py`
- Sửa: `src/vgar/graph/builder.py` (thêm `_derive_layer1_facts()`, gọi ngay sau `self._link_inheritance()`, chỉ khi
  `self.tsg_report` có status `ready` hoặc `partial`)
- Sửa: `src/vgar/contracts/schema.py`
- Test: `tests/test_layer1_facts.py` (mới)

**Giao diện:**
- Tạo ra:
  - `layer1_rules.route_specs(decorators: list[str]) -> list[RouteSpec]`, với
    `RouteSpec = NamedTuple(name: str, methods: list[str], route_path: str, decorator: str, receiver: str)`.
    Hàm dùng `vgar.graph.grounding._static_route` và bỏ các bản trùng `name`.
  - `PythonGraphBuilder._derive_layer1_facts(self) -> None`.
  - Helper dùng chung trong builder:
    `_add_layer1_node(self, owner: dict, kind: str, name: str, qualified_name: str, range_: dict, content_hash: str, properties: dict) -> str`.
    Helper tự thêm hậu tố `@definition:{line}:{col}` khi id trùng và trả về id. Task 4 dùng lại hàm này.
- Fixture cho test: `_build_ready(root)`, dùng `monkeypatch` để `check_available` trả
  `(None, "tree-sitter-graph 0.12.0")` và `run_file` trả `TsgFileFacts()`.

- [ ] **Bước 1: Viết test fail `test_routes_from_decorators`**
  - `src/api.py`:
    `"@app.post('/pay')\ndef pay(): ...\n@app.get('/items')\n@app.get('/items')\ndef items(): ...\n@router.route('/legacy', methods=['GET', 'POST'])\ndef legacy(): ...\n@app.get(PATH)\ndef dyn(): ...\n@cache.get\ndef cached(): ...\n"`
  - Kiểm tra:
    - tên các Route, đã sắp xếp, là `["GET /items", "GET,POST /legacy", "POST /pay"]`;
    - Route `GET,POST /legacy` có `properties == {"methods": ["GET", "POST"], "route_path": "/legacy", "decorator": "@router.route('/legacy', methods=['GET', 'POST'])", "receiver": "router"}`
      và `range` bằng `range` của handler `legacy`;
    - mỗi Route có đúng một cạnh `REFERENCES` tới handler, `confidence == 0.8`, và có cạnh `Module --CONTAINS--> Route`;
    - graph qua validate.
  - Thêm `test_layer1_facts_absent_without_tsg_and_on_fallback`: với `tsg=None`, và với CLI không tồn tại, graph
    không có node Route. Task 4 và 5 sẽ mở rộng test này cho Schema và `IMPLEMENTS`.

- [ ] **Bước 2: Chạy test, xác nhận fail**
  Lệnh: `python -m pytest -q -p no:cacheprovider tests/test_layer1_facts.py`
  Mong đợi: FAIL (thiếu `layer1_rules`).

- [ ] **Bước 3: Thêm vào `schema.py`**
  - `NODE_TYPES` và `SOURCE_BACKED` thêm `"Route"`.
  - `CONTAINS` thêm `(Module, Route)`.
  - `REFERENCES` thêm `(Route, Function|Method|Test)`.
  - Chú thích dẫn [P] dòng 222, 336 và 1237.

- [ ] **Bước 4: Cài đặt `route_specs` và phần Route trong `_derive_layer1_facts`**
  - `qualified_name = f"{handler_qn}::<route:{name}>"`, owner là Module của file handler.
  - `content_hash` là sha256 của chữ decorator.
  - Đếm vào `tsg_report["added"]["Route"]`.

- [ ] **Bước 5: Chạy test, xác nhận pass**, rồi chạy nhóm test graph. Mong đợi: PASS.

- [ ] **Bước 6: Commit** (người dùng tự chạy)
  `git commit -m "feat(graph): L1-3 Route nodes from static route decorators"`

### Task 4: Schema

**Files:**
- Sửa: `src/vgar/graph/layer1_rules.py`, `src/vgar/graph/builder.py`, `src/vgar/contracts/schema.py`
- Test: `tests/test_layer1_facts.py`

**Giao diện:**
- Tạo ra:
  - `layer1_rules.import_table(imports: list[dict]) -> dict[str, str]`: ánh xạ tên cục bộ sang đường dẫn đầy đủ.
    `imports` là `properties` của các node Import trong một module. Ví dụ: `"dc" -> "dataclasses.dataclass"`,
    `"t" -> "typing"`, `"BaseModel" -> "pydantic.BaseModel"`.
  - `layer1_rules.resolve(expression: str, table: dict[str, str]) -> str | None`: bỏ `@`, bỏ phần `(...)`, bỏ
    tiền tố `metaclass=`, rồi phân giải `a.b.c` theo `table` (phần đầu qua bảng, phần sau nối nguyên).
    Ví dụ: `resolve("t.TypedDict", ...) == "typing.TypedDict"`.
  - `layer1_rules.schema_kind(decorators: list[str], bases: list[str], table: dict[str, str]) -> tuple[str, str] | None`:
    trả về `(schema_kind, evidence)` cho các trường hợp (a), (b), (c) của spec §4.4.
  - Task 5 dùng lại `import_table` và `resolve`.

- [ ] **Bước 1: Viết test fail `test_schemas_require_resolved_imports`**
  - `src/models.py`:
    `"from dataclasses import dataclass as dc\nimport dataclasses\nimport typing as t\nfrom pydantic import BaseModel\n@dc(frozen=True)\nclass A: ...\n@dataclasses.dataclass\nclass B: ...\nclass C(BaseModel): ...\nclass D(C): ...\nclass E(t.TypedDict): ...\nif X:\n    class A2(BaseModel): ...\nelse:\n    class A2(BaseModel): ...\n"`
  - `src/sub.py`: `"from models import C\nclass H(C): ...\n"`
  - `src/fake.py`: `"class BaseModel: ...\nclass F(BaseModel): ...\n@dataclass\nclass G: ...\n"`
  - Kiểm tra tập `(tên class, schema_kind, evidence, confidence của cạnh REFERENCES)`, đúng bằng:
    `{("A","dataclass","decorator",1.0), ("B","dataclass","decorator",1.0), ("C","pydantic","base",1.0), ("D","pydantic","inherited",0.9), ("E","typed_dict","base",1.0), ("A2","pydantic","base",1.0), ("A2","pydantic","base",1.0), ("H","pydantic","inherited",0.9)}`
    (hai mục `A2` là hai node khác nhau).
  - Hai node Schema của `A2` có id khác nhau.
  - Không có Schema nào cho `F` hay `G`.
  - Mở rộng test fallback để có Schema.

- [ ] **Bước 2: Chạy test, xác nhận fail.**

- [ ] **Bước 3: Thêm vào `schema.py`**
  - `NODE_TYPES` và `SOURCE_BACKED` thêm `"Schema"`.
  - `CONTAINS` thêm `(Module, Schema)`.
  - `REFERENCES` thêm `(Schema, Class)`.
  - Chú thích dẫn [P] dòng 223 và 1238.

- [ ] **Bước 4: Cài đặt `import_table`, `resolve`, `schema_kind` và phần Schema trong `_derive_layer1_facts`**
  - Các đích hợp lệ: `dataclasses.dataclass`, `pydantic.BaseModel`, `typing.TypedDict`,
    `typing_extensions.TypedDict`.
  - Trường hợp (d): lan truyền qua cạnh `INHERITS` (nguồn kế thừa đích) tới điểm bất động, chỉ xuất phát từ các
    Schema loại (b)/(c).
  - Import của một module lấy qua cạnh `Module --CONTAINS--> Import`.
  - Node: `qualified_name = f"{class_qn}::<schema>"`, `range` và `content_hash` lấy từ Class.

- [ ] **Bước 5: Chạy test, xác nhận pass**, rồi chạy nhóm test graph.

- [ ] **Bước 6: Commit** (người dùng tự chạy)
  `git commit -m "feat(graph): L1-3 Schema nodes for dataclass, pydantic and TypedDict classes"`

### Task 5: `IMPLEMENTS`

**Files:**
- Sửa: `src/vgar/graph/layer1_rules.py`, `src/vgar/graph/builder.py`, `src/vgar/contracts/schema.py`
- Test: `tests/test_layer1_facts.py`

**Giao diện:**
- Dùng lại: `import_table` và `resolve` (Task 4).
- Tạo ra: `layer1_rules.interface_kind(bases: list[str], table: dict[str, str]) -> str | None`. Trả `"abc"` khi
  một base phân giải ra `abc.ABC` hoặc `abc.ABCMeta`; trả `"protocol"` khi phân giải ra `typing.Protocol` hoặc
  `typing_extensions.Protocol`.

- [ ] **Bước 1: Viết test fail `test_implements_edges`**
  - `src/ifaces.py`:
    `"from abc import ABC, ABCMeta\nfrom typing import Protocol\nclass Repo(ABC): ...\nclass Meta(metaclass=ABCMeta): ...\nclass Reader(Protocol): ...\nclass SubReader(Reader, Protocol): ...\nclass SqlRepo(Repo): ...\nclass Both(Meta, Reader): ...\nclass Child(SqlRepo): ...\nclass Plain: ...\n"`
  - Kiểm tra tập `(nguồn, đích, interface_kind)` của các cạnh `IMPLEMENTS`, đúng bằng:
    `{("SqlRepo","Repo","abc"), ("Both","Meta","abc"), ("Both","Reader","protocol")}`.
  - Confidence của mỗi cạnh bằng confidence của cạnh `INHERITS` cùng cặp.
  - Graph qua validate.
  - Mở rộng test fallback để có `IMPLEMENTS`.

- [ ] **Bước 2: Chạy test, xác nhận fail.**

- [ ] **Bước 3: Thêm vào `schema.py`**: `EDGE_ENDPOINTS["IMPLEMENTS"] = {("Class", "Class")}`, chú thích dẫn
  [P] dòng 32 và 233.

- [ ] **Bước 4: Cài đặt `interface_kind` và phần `IMPLEMENTS` trong `_derive_layer1_facts`**
  - Duyệt từng cạnh `INHERITS` A → B. Thêm cạnh khi `interface_kind(B)` khác `None` và `interface_kind(A)` là
    `None`.

- [ ] **Bước 5: Chạy test, xác nhận pass**, rồi chạy nhóm test graph.

- [ ] **Bước 6: Commit** (người dùng tự chạy)
  `git commit -m "feat(graph): L1-3 IMPLEMENTS edges to ABC and Protocol classes"`

### Task 6: Tích hợp và nghiệm thu

**Files:**
- Sửa: `src/vgar/graph/builder.py` (nhãn `graph_version`)
- Test: `tests/test_layer1_facts.py`, `tests/test_tsg_enrichment.py`
- Tạo: `docs/status/tv2_layer1_run_2026-11-08.md` (ghi kết quả chạy thật)

- [ ] **Bước 1: Viết test**
  - `test_all_layer1_types_round_trip_through_sqlite`: dùng các repo mẫu của Task 1–5 trong một repo,
    `SQLiteGraphStore.ingest`, rồi `load_document`. Kiểm tra tập `(type, qualified_name)` của các node Identifier,
    ConfigEntry, Route, Schema và tập cạnh `IMPLEMENTS` không đổi sau khi đọc lại.
  - `test_real_cli_survives_syntax_errors` (skip khi thiếu CLI): repo có `src/bad.py = "def broken(:\n    pass\n"`
    và `src/good.py = "def ok(a): return a\n"`. Kiểm tra:
    - build không raise và graph qua validate;
    - status là `"ready"` hoặc `"partial"`;
    - có `good.ok::<param:a>`.

- [ ] **Bước 2: Đổi nhãn** `b"\0tsg-facts-v1:"` thành `b"\0tsg-facts-v2:"` trong `_calculate_graph_version`.

- [ ] **Bước 3: Chạy toàn bộ test liên quan**
  - Chạy `tests/test_tsg_enrichment.py` và `tests/test_layer1_facts.py` với CLI thật.
  - Chạy nhóm test graph.
  - Mong đợi: PASS hết. Nhóm test graph có 985 test cũ cộng các test mới.

- [ ] **Bước 4: Chạy thật**
  `python scripts/build_graph.py <repo> <out>.json --repo-key <k> --revision base --tsg-executable <exe> --tsg-tree-sitter-dir <dir>`
  - Chạy trên `D:/kltn/vgar-demo-shop/vgar-demo-shop` và trên `pydata__xarray-4629` tại `a41edc7bf5302f2ea327943c0c48c532b12009bc`.
  - Mong đợi: lệnh in `Built ...`, không có cảnh báo `tree-sitter-graph`, và `statistics.tsg.unmatched == {}`.
    Nếu không rỗng, ghi lý do của từng mục lệch.

- [ ] **Bước 5: Ghi `docs/status/tv2_layer1_run_2026-11-08.md`**, gồm:
  - với mỗi repo: số node của từng loại mới, `added`, `unmatched`, thời gian build có và không có
    tree-sitter-graph;
  - lệnh để tái tạo kết quả.

- [ ] **Bước 6: Commit** (người dùng tự chạy)
  `git commit -m "test(graph): Layer 1 acceptance (SQLite, parse errors) and run report"`
