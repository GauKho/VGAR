# TV2 · IM-1: impact theo `G_arch` và check "mất port"

> **Trạng thái:** đã duyệt 09/11/2026.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng) và các nguồn của plan trong `Downloads\context`:
> **[cp]** `check proposal.txt`, **[test]** `test.txt`. Quy tắc build server lấy từ tài liệu MCP **[mcp]**
> <https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server>. Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng, không phải yêu cầu.
> Spec xét phần việc của TV2; §5.6 ghi các điểm giao với checkpoint MCP của TV1 (`f37df85f`), đã đối chiếu theo yêu cầu.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh

| [plan] ghi ở IM-1 | Spec này làm |
|---|---|
| Đi ngược thêm theo `DEPENDS_ON` ([P] 1011) | §4.3 |
| Đi theo `CONSUMES_PORT`/`EXPOSES_PORT` ([P] 1012) | §4.2, §4.3 |
| Risk features ([P] 1018–1023) | §4.5 |
| Check "mất port/public API" ([P] 892; [cp]: dựng `G'` rồi kiểm) | §5 |
| `Touched = {n \| n modified by diff}` ([P] 1001) | §4.6: sửa lỗi bỏ sót dòng chèn cuối hàm |

**Sửa kèm theo vì chặn IM-1:** `content_hash` của Route do L1-3 sinh (§4.7).

**Hiện trạng:** `compute_impact` đi ngược theo `CALLS`, `IMPORTS`, `INHERITS`, `TESTS` (`graph/impact.py:187`). `G_arch` đã có từ GA-1, GA-2.

**Đo trên xarray-4629 (graph `static`) và `boundary_cases`:**

| Chỉ số | xarray | `boundary_cases` |
|---|---|---|
| Component / Port | 7 / 1.065 | 4 / 21 |
| `DEPENDS_ON` / `CONSUMES_PORT` | 13 / 28 | 5 / 7 |
| Method công khai override lớp cha | 83 | 2 |
| Class công khai kế thừa method từ lớp `_Base` | 0 | 0 |

Build đầy đủ xarray mất 7,9–9,7 s. `IncrementalGraphBuilder.update` mất 1,4–1,9 s nhưng cần cache có sẵn. Kết quả thực nghiệm ở §10.

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. `compute_impact` trả thêm Port và Component bị ảnh hưởng, đúng luật §4.
2. Patch sửa method override thì thấy được nơi gọi qua lớp cha (§4.4).
3. `analyze_patch_impact` báo Port và public API bị mất cùng lý do (§5).
4. Có test tầng 1 với đáp án viết tay ([test] mục 1), chạy thật trên xarray.
5. Tool `analyze_patch_impact` vẫn đúng quy tắc [mcp] sau thay đổi (§5.5).

**Ngoài phạm vi**

- Đi theo `MAY_CALL`: [P] 1007–1012 không liệt kê.
- Check cycle mới và kết quả test covering: chỉ khai báo là chưa tính, IM-1 **chưa phủ** [P] 1021, 1023 (§4.5).
- Các check khác trên `G'` ([P] 889–891): `G'` của IM-1 chỉ phục vụ so Port (§5.1).
- Sinh Port cho method kế thừa từ lớp `_Base` **(đề xuất)**. Đo được 0 trường hợp ở cả hai repo. Lỗ hổng thật ở `boundary_cases` là override (§4.4).
- Đổi id Port, thêm loại node hay cạnh, đổi `SCHEMA_VERSION`.
- Sửa retrieval (RT-1).

**Điều cần tránh**

- Báo mất port giả khi chỉ dịch dòng.
- Coi "không kiểm được" là "không mất".
- Để Port, Component chiếm hết `max_nodes`.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | Nới `ImpactedNode`, không thêm trường riêng cho kiến trúc | **(TV2 chốt)** |
| 2 | Bước nâng tầng không tốn hop | **(TV2 chốt)** |
| 3 | Dùng dict `symbol_id → Port`, không thêm cạnh | **(TV2 chốt)** |
| 4 | Chỉ thêm Component vào kết quả, không bung thành viên | **(TV2 chốt)** |
| 5 | So tập Port, dùng `check_api` để giải thích | **(TV2 chốt)** |
| 6 | Thêm nhánh vào `neighbours`, không làm bảng khai báo | **(TV2 chốt)** |
| 7 | `G'` chỉ cho file bị patch, trích trong bộ nhớ (§5.1) | **(đề xuất)** |
| 8 | So theo `(path, tên trong file)`, nên không cần đổi hậu tố id Port (§5.2) | **(đề xuất)** |
| 9 | Port chỉ tính cho method bị sửa và method lớp cha của nó (§4.2), hẹp hơn "reachable" ở [P] 1007 | **(đề xuất)** |
| 10 | `DEPENDS_ON` chỉ đi 1 bước từ component của hàm bị sửa (§4.3) | **(TV2 chốt)**, sau thực nghiệm |
| 11 | Xử lý override ở IM-1 (§4.4); plan và proposal không ghi | **(TV2 chốt, ngoài nguồn)** |
| 12 | Nhận dòng chèn ngay sau hàm là sửa hàm đó (§4.6) | **(TV2 chốt)**, sau thực nghiệm |
| 13 | Sửa `content_hash` của Route (§4.7) | **(TV2 chốt)**, sau thực nghiệm |

## 4. Impact

### 4.1 Thay đổi contract (`contracts/impact.py`)

- `ImpactRelation` thêm `LIFT`, `EXPOSES_PORT`, `CONSUMES_PORT`, `DEPENDS_ON`.
- `ImpactedNode.kind` thêm `Port`, `Component`.
- `ImpactedNode.path` được `None`, chỉ với `Component`. Giá trị khác `None` vẫn phải qua kiểm tra đường dẫn. Không sửa `_Located`.
- `ImpactedNode.hops` cho phép `0`, chỉ với `Port`, `Component`.
- `canonical_json` sắp xếp được khi `path` là `None` (hiện sẽ lỗi `TypeError` ở dòng 232), và sắp xếp cả các danh sách của `port_check` (§5.3).

Graph không có node Component thì báo cáo giữ nguyên như hiện tại: `traversed` chỉ có 4 quan hệ cũ.

Tên `LIFT`, giá trị `hops = 0`, thứ tự duyệt ở §4.3 và cấu trúc `PortCheck` ở §5.3 không có trong nguồn **(đề xuất)**.

### 4.2 Nâng tầng (không tốn hop)

Index dựng một lần trong `compute_impact`:

- `port_of`: `properties.symbol_id` → Port.
- `component_of`: mỗi đường dẫn trong `Component.properties.files` → Component.

| Từ | Tới | `relation` | Điều kiện |
|---|---|---|---|
| Function, Method | Port của nó | `EXPOSES_PORT` | Chỉ với node trong tập *nguồn Port* |
| Function, Method, Class, Module | Component chứa file của nó | `LIFT` | Mọi node đã tới |

*nguồn Port* = node bị sửa + method lớp cha tìm được ở §4.4. Không dùng từ `Touched` cho tập này vì [P] 1001 định nghĩa `Touched` chỉ gồm node bị diff sửa. Giới hạn này giữ số Port nhỏ: Component của hàm gọi ở các hop sau vẫn được báo qua `LIFT`.

`LIFT` không phải cạnh trong graph, mà là ánh xạ `Lift` của [P] 171. Test không thuộc Component nên không được nâng.

### 4.3 Đi ngược (mỗi bước 1 hop)

Giữ nguyên 4 quan hệ cũ. Thêm:

| Từ | Tới | `relation` |
|---|---|---|
| Port | Component có `CONSUMES_PORT` tới Port đó | `CONSUMES_PORT` |
| Component chứa node bị sửa | Component có `DEPENDS_ON` tới nó | `DEPENDS_ON` |
| Method bị sửa | Method lớp cha (§4.4) | `INHERITS` |

`DEPENDS_ON` chỉ mở rộng từ Component chứa node bị sửa, tức tối đa 1 bước. Đi nhiều bước đã thử và báo 69–100% số Component của repo, phần lớn không có đường code nào dẫn tới (§10). Component phụ thuộc gián tiếp chỉ xuất hiện nếu có đường `CALLS`, `IMPORTS`, `INHERITS` hoặc `CONSUMES_PORT`.

Cạnh dưới `min_confidence` không được đi. Thứ tự duyệt:

```text
level = các node bị sửa, hops = 0
với hops = 0 .. max_hops:
    nâng tầng mọi node trong level, ghi nhận Port/Component với hops hiện tại
    nếu hops == max_hops: dừng
    duyệt Port, Component của mức này trước, rồi tới symbol, giữ nguyên thứ tự tìm thấy, sinh level kế với hops + 1
```

`via` là node ngay trước đó, kể cả với item hop 0. Khi graph có Component, `traversed` gồm cả 8 quan hệ. Node đi tới bằng nhiều đường giữ đường tìm thấy đầu tiên, như hiện tại. Port và Component được duyệt trước nên không bị `max_nodes` cắt mất.

### 4.4 Override **(TV2 chốt, ngoài nguồn)**

Plan và proposal không ghi luật này. TV2 đã đồng ý xử lý lỗ hổng này ở IM-1.

**Vấn đề:** ở `boundary_cases`, `save_with(store: BaseStore)` gọi `store.save`, nên `CALLS` trỏ vào `BaseStore.save`. Sửa `SqlStore.save` thì hiện không thấy nơi gọi này.

**Luật:** với mỗi Method bị sửa, đi ngược lên theo cạnh `INHERITS` đạt `min_confidence`. Trên mỗi nhánh, dừng ở lớp đầu tiên có method cùng tên, tránh lặp vô hạn nếu có chu trình. Method đó là một item ở hop 1, `relation` là `INHERITS`, và thuộc *nguồn Port*.

Bỏ qua `__init__`, `__new__` **(đề xuất)**: tạo object lớp cha không gọi tới constructor lớp con. Graph không có Component thì không áp dụng luật này, để báo cáo giữ nguyên như §4.1.

### 4.5 Risk features ([P] 1018–1023)

| [P] | Feature | Cách tính |
|---|---|---|
| public ports changed | `public_ports_changed` (mới) | Số node bị sửa có Port |
| callers affected | `impacted_callers` (có sẵn) | Đổi thành đếm item `relation == 'CALLS'`, kết quả cũ không đổi, không đếm nhầm method lớp cha |
| components affected | `components_affected` (mới) | Số item Component |
| cycle introduced | `dependency_cycle_introduced` (mới) | `available: false`, `NOT_COMPUTED` |
| high fan-in | `fan_in` (có sẵn) | Không đổi |
| tests covering pass | `covering_tests_pass` (mới) | `available: false`, `NOT_COMPUTED` |

`public_ports_changed`, `components_affected` cũng `NOT_COMPUTED` khi graph không có Component, và `NO_CHANGED_NODES` khi không có node bị sửa, giống các feature hiện có.

IM-1 chưa phủ 2 dòng của nguồn: cycle mới ([P] 1021) cần `G'` cả repo, kết quả test ([P] 1023) cần chạy test thật.

### 4.6 Xác định node bị sửa ([P] 1001) **(TV2 chốt)**

**Vấn đề:** dòng chèn ngay sau câu lệnh cuối của hàm nằm sau `end_byte`, nên `_map_patch` (`impact.py:155`) báo `NO_BASELINE_SYMBOL_AT_INSERTION` và impact rỗng. Đo được 64/64 patch loại này.

**Luật:** với khối chỉ có dòng thêm, tại điểm chèn `p`, xét Function, Method, Class của file có:

- `end_byte <= p`;
- đoạn từ `end_byte` tới `p` chỉ gồm dòng trống hoặc comment;
- mức thụt lề của dòng thêm đầu tiên khác rỗng lớn hơn `start_col` của symbol.

Chọn symbol nhỏ nhất. Ứng viên này được ưu tiên hơn symbol đang bao quanh `p`, nên dòng chèn cuối một method không nằm cuối class vẫn gán cho method, không gán cho class. Hòa thì giữ `AMBIGUOUS_BASELINE_SYMBOL`, không có ứng viên thì giữ kết quả cũ. `basis` là `insertion_in_existing_scope`.

### 4.7 `content_hash` của Route **(TV2 chốt)**

Route được sinh với hash của chuỗi decorator nhưng `range` của hàm (`builder.py`, `_derive_layer1_facts`), nên `_snapshot` báo `Graph source hash differs from baseline` và `analyze_patch_impact` lỗi hoàn toàn với repo có Route khi bật tree-sitter-graph. Sửa: Route dùng `content_hash` của hàm nó trỏ tới, là hash của đúng `range` đó. Decorator vẫn nằm trong `properties.decorator`.

## 5. Check "mất port"

### 5.1 `G'` chỉ cho file bị patch, trích trong bộ nhớ **(đề xuất)**

[P] 886 và [cp] nói dựng `G'`. Tập Port của một file chỉ phụ thuộc vào chính file đó, và patch không được thêm, xóa hay đổi tên file (`_map_patch` đã chặn). Nên `G'` cho các file bị patch cho cùng kết quả với dựng cả repo về **Port**. Bản rút gọn này không dùng được cho các check cycle hay sai kiểu cạnh ([P] 889–891).

Cách làm:

- Tách phần trích của `_extract_file` thành một hàm nhận `(đường dẫn, bytes)`; `_extract_file` đọc file rồi gọi hàm đó, hành vi không đổi.
- Check gọi hàm này với bytes sau patch của các file `.py` có Port trong `G`. **Không ghi đĩa, không spawn tiến trình**, không import hay chạy code của repo.
- Tách phần chọn Port của `_ports` thành hàm công khai `select_ports(nodes, edges, exports)`, dùng chung cho lift và check, để chỉ có một luật. Hành vi của `_ports` không đổi.

Không có file nào có Port thì kết quả là `COMPLETE`, không mất Port.

Giới hạn tài nguyên ([P] 1134): tổng kích thước các file cần trích vượt 5 MiB thì không trích, báo `AFTER_TOO_LARGE`.

### 5.2 So sánh

Khóa là `(path, tên trong file)`, với tên trong file là `qualified_name` bỏ phần `module_name` của file đó. Lý do: tiền tố module phụ thuộc `source_roots` mà graph không lưu, nên phải bỏ đi. `qualified_name` không chứa số dòng, nên dịch dòng không đổi khóa.

So theo số lần xuất hiện của từng khóa. Số lần giảm thì Port đó mất. Trùng khóa thì lấy Port có id lớn nhất theo thứ tự chuỗi là Port mất.

**Port mất** là: xóa hàm, đổi tên, đổi thành tên `_`, bỏ khỏi `__all__` với tên `_`, chuyển vào hàm hay class ẩn. Chỉ đổi chữ ký thì **không** mất, đã có `signature_changed`.

### 5.3 Kết quả

Thêm vào `ImpactReport`:

```python
class LostPort(_Located):
    port_id: Text
    qualified_name: Text
    export: Literal['public_name', 'dunder_all', 'route']
    owner_component_id: Text
    consumers: list[Text]         # Component có CONSUMES_PORT tới Port này trong G
    api_reason: Text | None       # reason của check_api cùng (path, symbol); None nếu không có

class RemovedApi(_Located):
    symbol: Text                  # tên trong file, ví dụ 'Order' hoặc 'Order.total'

class UncheckedPath(_Located):
    reason: Literal['AFTER_PARSE_FAILED', 'AFTER_EXTRACT_FAILED', 'AFTER_TOO_LARGE', 'ROUTE_FACTS_UNAVAILABLE']

class PortCheck(_Contract):
    status: Literal['NOT_COMPUTED', 'COMPLETE', 'PARTIAL'] = 'NOT_COMPUTED'
    checked_paths: list[Text] = []
    lost: list[LostPort] = []
    removed_api: list[RemovedApi] = []
    unchecked: list[UncheckedPath] = []
```

`removed_api` phủ phần "public API" của [P] 892: các mục `API_SYMBOL_REMOVED` của `check_api` không trùng Port nào của file đó, ví dụ class hoặc hằng công khai. Bỏ các mục ở file test, và các mục `check_api` chỉ suy ra vì không đọc được symbol sau patch (lỗi cú pháp, `__all__` động, khai báo không hỗ trợ); `api_reason` cũng bỏ các mục này. `check_api` không kết luận được ở nhiều file (§10), nên danh sách này là phần đã biết, không phải toàn bộ.

- `status` là `NOT_COMPUTED` khi graph không có Component hoặc patch không có file Python; `PARTIAL` khi `unchecked` khác rỗng.
- Risk feature `ports_lost` (mới): số Port mất khi `COMPLETE`, còn lại `available: false`, `NOT_COMPUTED`. `compute_impact` đặt mặc định chưa tính, như `signature_changed`.
- `compute_impact` không đổi chữ ký. Check chạy trong `analyze_patch_impact`, gọi hàm độc lập `check_lost_ports(document, after, analysis) -> PortCheck` ở file mới `graph/port_check.py`, dùng `analysis` của `check_api` đang có sẵn ở đó. Hàm không phụ thuộc MCP để nơi khác gọi lại được.

### 5.4 Khi không kiểm được

| Tình huống | Xử lý |
|---|---|
| File sau patch có `parse_status` khác `parsed`, hoặc không phải UTF-8 | `AFTER_PARSE_FAILED`, không báo mất |
| Trích lỗi (`ValueError`, `OSError`, `RecursionError`) | Mọi file `AFTER_EXTRACT_FAILED`, không báo mất, ghi log kèm tên lỗi |
| Tổng kích thước vượt 5 MiB | Mọi file `AFTER_TOO_LARGE`, không báo mất |
| File có Port `export == 'route'` | File đó có `ROUTE_FACTS_UNAVAILABLE`; riêng Port `route` bị bỏ qua, các Port khác của file vẫn so |

Port `route` chỉ gồm hàm tên `_` có route, vì tên công khai đã là `public_name`. Biết route cần CLI tree-sitter-graph, mà đường này không spawn tiến trình, nên không kiểm được. File đó vẫn nằm trong `checked_paths` vì các Port khác của nó đã được so.

### 5.5 Quy tắc MCP ([mcp])

Server graph chạy qua `stdio`, và IM-1 lần đầu đưa việc trích graph vào đường xử lý của tool.

| Quy tắc [mcp] | Áp dụng cho IM-1 |
|---|---|
| Server stdio không được ghi ra stdout, không dùng `print()` | `port_check.py` và đường gọi của nó không ghi stdout. Đã kiểm tra `builder.py`, `impact.py`, `api_check.py`, `GraphTrace` không có `print`. Có test bắt stdout ở mức file descriptor (§8) |
| Dùng `logging`, mỗi module một `logging.getLogger(__name__)` | `port_check.py` có logger riêng cho các lỗi ở §5.4 |
| Định nghĩa tool sinh từ type hint và docstring, có mục `Args:` | Viết lại docstring của `analyze_patch_impact` trong `mcp/servers/graph_server.py`: hiện chỉ nói callers/importers/subclasses/tests. Docstring phải nói có Port, Component và `port_check`, và có `Args:` cho `diff`, `graph_version`, `max_hops`, `max_nodes`. Không đổi tham số |
| Lỗi của tool không làm hỏng server | Lỗi ở §5.4 trả về trong `port_check`, không làm hỏng cả báo cáo impact. Lỗi khác vẫn đi qua envelope `run_tool` như hiện tại |

### 5.6 Điểm giao với checkpoint TV1 (`f37df85f`)

| Điểm | Xử lý trong IM-1 |
|---|---|
| Git | Ghép sạch. TV1 không sửa `graph/impact.py`, `contracts/impact.py`, `arch_lift.py`; docstring ở `graph_server.py` đã giả lập, không xung đột |
| `tools.md:15` ghi không thêm architecture facts, `contract.md:66` ghi architecture/port chờ TV2 | Chỉ thêm, không bỏ trường. Graph không có Component thì báo cáo như cũ. TV1 cập nhật `tools.md:15` |
| Lease, path jail, giới hạn trước khi đọc, ghi, spawn (`contract.md:166-168`) | Trích trong bộ nhớ (§5.1) |
| `VerificationProvider.verify_graph` chờ check mất port | `check_lost_ports` độc lập, nhận `(document, after, analysis)` |
| Quy tắc `COMPLETE`/unknown (`tools.md:61`) | `PortCheck.status` theo đúng nghĩa đó; không kiểm được thì `PARTIAL` |
| `check_api(changed_only=True)` của checkpoint | Chưa dùng vì nhánh hiện tại chưa có. Sau khi ghép có thể đổi riêng cho `removed_api`, `api_reason`; không đổi `signature_changed` |

## 6. File thay đổi

| File | Thay đổi |
|---|---|
| `src/vgar/contracts/impact.py` | §4.1, §5.3 |
| `src/vgar/graph/impact.py` | §4.2–§4.6, gọi check ở `analyze_patch_impact` |
| `src/vgar/graph/builder.py` | Tách hàm trích từ bytes (§5.1), sửa hash Route (§4.7) |
| `src/vgar/graph/port_check.py` (mới) | §5 |
| `src/vgar/graph/arch_lift.py` | Tách `select_ports` |
| `src/vgar/mcp/servers/graph_server.py` | Chỉ docstring của `analyze_patch_impact` (§5.5) |
| `tests/test_impact_arch.py`, `tests/test_port_check.py` (mới) | §8 |
| `tests/test_impact.py` và test đang ghim số item, danh sách feature | Sửa số, giữ ý nghĩa |

## 7. Ảnh hưởng tới code có sẵn

Không sửa các nơi này, chỉ ghi nhận:

- `agents/feedback.py:41` xếp theo `hops`, nên Port, Component ở hop 0 hiện trước trong dòng tóm tắt, và `len(items)` lớn hơn.
- `evaluation/gold_impact.py` dùng `len(report.impacted.items)` làm kích thước vùng ảnh hưởng, nên số này cũng tăng.

## 8. Tiêu chí nghiệm thu

**Đáp án viết tay trên `boundary_cases`.** Patch sửa thân `SqlStore.save` phải cho:

| Item | `hops` | `relation` |
|---|---|---|
| Port `storage.sql.SqlStore.save` | 0 | `EXPOSES_PORT` |
| Component `storage` | 0 | `LIFT` |
| Method `storage.base.BaseStore.save` | 1 | `INHERITS` |
| Port `storage.base.BaseStore.save` | 1 | `EXPOSES_PORT` |
| Component `api`, `services`, `plugins` | 1 | `DEPENDS_ON` |
| Function `services.orders.save_with` | 2 | `CALLS` |

**Test tầng 1, mỗi dòng một test:**

| Nhóm | Ca |
|---|---|
| Impact | Hàm private: có Component, không có Port. Consumer qua Port có `relation` `CONSUMES_PORT`. `DEPENDS_ON` không đi tiếp từ Component phụ thuộc. Cạnh dưới `min_confidence` không đi. `__init__` không đi lên lớp cha. Đa kế thừa và lớp trung gian không định nghĩa method. `max_nodes` nhỏ vẫn giữ Component. `max_hops=1`. Graph không có Component giữ nguyên báo cáo |
| Tương thích | Graph không có Component: `items` giống hệt `compute_impact` trước khi sửa, gồm cả `hops`, `relation`, `via`, trên repo có node tới được bằng nhiều đường |
| Node bị sửa | Dòng chèn cuối hàm: có node. Có comment hoặc dòng trống ở giữa: có node. Cùng mức thụt với `def`: không gán vào hàm đó. Cuối method trong class: gán method. Thụt bằng thân class: gán class |
| Route | Graph bật tree-sitter-graph trên `web_app`: mọi node source-backed có hash khớp `range`, `analyze_patch_impact` chạy được |
| Contract | `path=None` với Port bị từ chối. `hops=0` với Function bị từ chối. `canonical_json` chạy được khi có `path=None` |
| Mất port | Xóa `connect`. Đổi tên `format_total` (có `consumers` là `services`). Đổi `connect` thành `_connect`. Bỏ `_internal` khỏi `__all__`. Chỉ đổi chữ ký: không mất. Thêm dòng ở đầu file: không mất. Định nghĩa trùng tên, xóa một bản: mất đúng một. Patch chỉ sửa file test: `COMPLETE`, không mất. Graph build với `source_roots` khác mặc định: không báo mất giả. Lỗi cú pháp sau patch: `PARTIAL`, không mất. Vượt 5 MiB: `AFTER_TOO_LARGE`. Xóa class công khai: có trong `removed_api` |
| Chung | `check_lost_ports` không ghi đĩa, không spawn tiến trình. `select_ports` cho đúng tập Port như trước khi tách. Hàm trích từ bytes cho cùng node với `_extract_file` |
| MCP | Gọi `analyze_patch_impact` có check port: `capfd` không thấy gì ở stdout. Trích `G'` lỗi: báo cáo impact vẫn trả về, `port_check` là `PARTIAL`. Mô tả tool nhận từ `list_tools` có nhắc Port và có đủ 4 tham số |

**Toàn bộ:**

1. Test mới pass.
2. Toàn bộ test suite (bỏ marker `hf`, `docker`) chỉ còn đúng các test fail đã biết.
3. Chạy thật trên xarray-4629: một patch sửa thân hàm và một patch đổi tên hàm công khai; ghi số item, thời gian, Port mất vào `docs/status/`. Số này chỉ để kiểm tra, không dùng để chỉnh luật.

## 9. Giới hạn đã biết

- Component là package, nên kể cả đi 1 bước `DEPENDS_ON` vẫn rộng với repo ít Component như xarray. Component phụ thuộc gián tiếp không còn được báo qua `DEPENDS_ON`.
- `CONSUMES_PORT` chỉ có khi `CALLS` đã resolve. Lời gọi qua `self.` kế thừa từ package khác chỉ là `MAY_CALL`, nên không đếm; Component vẫn tới được qua `INHERITS` rồi `LIFT`.
- Override chỉ xét method bị sửa, không xét method đi tới ở các hop sau.
- Đổi lớp cha của class công khai không được xem là mất port.
- Với Port trùng khóa, không phân biệt được chính xác bản nào bị xóa.
- Port `route` chỉ gồm hàm tên `_` có route: không kiểm được mất port cho nhóm này (§5.4).
- [mcp] yêu cầu Python MCP SDK từ 2.0.0. L6-1 đã xử lý ở checkpoint TV1 bằng môi trường riêng `requirements/mcp-server.lock`; `pyproject.toml` vẫn `<2`. IM-1 không đổi SDK, phần docstring dùng được ở cả hai.
- TV1 chỉ hỗ trợ schema cũ trong snapshot, còn builder luôn sinh `G_arch`. Chưa kiểm được ghép này vì 60 test của TV1 không chạy được ở máy này (thiếu SDK2); cần kiểm trên môi trường SDK2.
- Chưa đo được độ chính xác của impact vì chưa có nhãn đúng/sai.

## 10. Kết quả thực nghiệm (09/11/2026)

Thực nghiệm viết thuật toán tổng quát ngoài `src`, tự sinh patch từ chính graph, chạy trên 14 repo: 11 repo mẫu, xarray-4629, mã nguồn `vgar`, networkx. Số dưới đây là lượt chạy theo thiết kế ở spec này.

| Kiểm tra | Kết quả |
|---|---|
| Check mất port so với dựng lại toàn bộ graph | 491/491 khớp |
| Lặp lại với tree-sitter-graph, build đầy đủ (11 repo mẫu) | 384/384 khớp; 6 mẫu Port `route` báo `PARTIAL` |
| Dòng chèn cuối hàm được nhận | 56/56 |
| Dòng cùng mức thụt với `def` bị gán nhầm | 0/54 |
| Ghi đĩa, spawn tiến trình, ghi stdout trong check | 0 |
| Đổi hash seed (11 repo mẫu) | Kết quả giống hệt |
| Tắt phần mới so với `compute_impact` hiện tại | 42/42 khớp, gồm cả `hops`, `relation`, `via` |
| Không mất item cũ, tăng `max_hops` không mất item, không vượt `max_nodes` | 0 vi phạm |
| Thời gian check | Trung vị 11–25 ms trên 3 repo thật, cao nhất 644 ms |
| Bị cắt ở `max_nodes=200` | 3 mẫu xarray, bằng đúng số mẫu bị cắt khi chưa có phần mới; không mất Component |
| Xóa class / hằng công khai có trong danh sách API bị xóa | 41/46 và 5/5 |
| `check_api` không kết luận | 355/491 (72%); 22 Port mất không có `api_reason` |

| Tỷ lệ Component được báo (trung vị) | Đi nhiều bước (bản cũ) | 1 bước (spec này) |
|---|---|---|
| xarray (7) | 86% | 57% |
| `vgar` (16) | 69% | 38% |
| networkx (25) | 100% | 8% |

Override thêm item ở 8/45 mẫu xarray (tối đa 17), 2/30 mẫu networkx (tối đa 11), 0/45 mẫu `vgar`.

**Lỗi đã gặp và đã sửa trong lúc thử:** một lượt trước có 41/42 mẫu khớp `compute_impact`, vì bản thử sắp xếp lại thứ tự duyệt nên đường tìm thấy đầu tiên bị khác. Sau khi giữ thứ tự tìm thấy (§4.3), lượt cuối khớp 42/42. Test "Tương thích" ở §8 giữ điều này khi code.

**Chưa kiểm:** độ chính xác của impact; patch nhiều file. Hash Route được sửa ngay trên graph của thực nghiệm, chưa sửa trong code. `check_api(changed_only=True)` chưa thử vì nhánh hiện tại chưa có.
