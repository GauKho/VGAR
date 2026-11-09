# TV2 · L2-1: call graph Python bằng JARVIS

> **Trạng thái:** đã duyệt, 10/11/2026 (đã soát lại với code, mã nguồn JARVIS và mô phỏng trên dữ liệu đã lưu).
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng). Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh

[plan] dòng 119 ghi L2-1 là "PyCG/JARVIS cho call graph Python"; dòng 184 và 202 gắn việc này với gate G1 (call edge P/R). [P] xếp công cụ này vào Layer 2 (368), vai trò "tăng precision cho Python/SWE-bench" (407), là lựa chọn theo ngôn ngữ (428) và backend tùy chọn (1455). Tiêu chí của [P]: "precision improves for supported languages", "fallback still works without heavy backend" (1461–1462). Graph phải lưu `confidence` và provenance (557–568).

**Chọn JARVIS** **(TV2 chốt)**: trên 13 repo không gồm xarray, chạy Python 3.8, giới hạn 300 s, JARVIS xong 12/13, PyCG 8/13 và upstream PyCG đã archive.

**Dữ liệu trước khi viết spec**, từ kết quả JARVIS đã lưu trên `requests` và `jinja2`, so với resolver static (chưa bật SCIP):

| So với graph hiện tại | Lời gọi | Tỷ lệ |
|---|---|---|
| Trùng `CALLS` | 768 | 76% |
| Trùng ứng viên `MAY_CALL` | 120 | 12% |
| Không có call site cùng tên (gọi qua biến hoặc ngầm) | 105 | 10% |
| Khác `CALLS` | 9 | 1% |
| Có call site chưa phân giải cùng tên | 5 | 0,5% |

**Thử luật ở §6** với JARVIS chạy thật trên `python:3.11-slim` (`PYTHONHASHSEED=0`, dàn file như §5), chấm trên cả `vgar-callgraph-cases` và bản `-flat` bằng script mô phỏng luật. Đây là ước lượng, chưa phải nghiệm thu (§9):

| | `CALLS` tp / precision / recall | `CALLS + MAY_CALL` tp / precision / recall | `CALLS` nhận nhầm lời gọi ngoài |
|---|---|---|---|
| Chưa có JARVIS | 13 / 0,929 / 0,220 | 43 / 0,566 / 0,729 | 0 |
| Luật §6 | 25 / 0,962 / 0,424 | 52 / 0,642 / 0,881 | 0 |

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Khi bật tùy chọn, kết quả JARVIS xác nhận cạnh đã có, phân giải thêm call site, và thêm `MAY_CALL` theo §6; graph qua `validate_graph_document`.
2. Khi tắt, graph giữ nguyên hoàn toàn.
3. Docker, image thiếu, JARVIS lỗi hoặc hết giờ: graph vẫn build xong bằng SCIP/static và báo rõ ([P] 1462).
4. Có test không cần Docker, dùng kết quả JARVIS đã ghi lại.
5. Chạy được trên máy chủ Windows và Linux **(TV2 chốt)**.

**Ngoài phạm vi**

- PyCG; cập nhật incremental (JARVIS phân tích toàn repo một lượt).
- Code test **(TV2 chốt)**.
- Giữ kết quả dở khi hết giờ: JARVIS chỉ ghi JSON một lần ở cuối **(TV2 chốt)**.
- Lưu lời gọi ra ngoài repo thành node hoặc thuộc tính; chỉ đếm **(TV2 chốt)**.
- Cạnh Function→Function: schema và [P] 554 yêu cầu `CALLS`, `MAY_CALL` đi từ `CallSite` **(TV2 chốt)**.
- Cài thư viện phụ thuộc của repo vào image: JARVIS chỉ đọc mã nguồn trong repo **(đề xuất)**.

**Điều cần tránh**

- Làm giảm `confidence` của cạnh đã có.
- Thay `CALLS` đã có bằng kết quả JARVIS.
- Tạo `CALLS` trên call site mà SCIP/LSP đã xác định là lời gọi ra ngoài repo.
- Tạo cạnh cho lời gọi ngầm (`raise X` gọi `X.__init__`, `with ctx` gọi `__enter__`) hoặc cho hàm có sẵn (`isinstance`, `len`).
- Mất cạnh âm thầm vì một file không parse được.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | JARVIS là tool chính, mặc định tắt, bật bằng `--enable-jarvis` | **(TV2 chốt)** |
| 2 | Image riêng dựng từ `python:3.11-slim`, JARVIS ghim commit | **(TV2 chốt)** |
| 3 | Nạp trước `importlib.metadata`, `PYTHONHASHSEED=0`, parse trước và báo file bị loại | **(TV2 chốt)** |
| 4 | Hết 120 s thì bỏ toàn bộ kết quả, ghi `JARVIS_TIMEOUT`, dùng SCIP/static | **(TV2 chốt)** |
| 5 | Một đích thì `CALLS` 0.75, nhiều đích thì `MAY_CALL`; xung đột thì giữ cả hai; ghép theo tên rồi số tham số; tối đa 5 ứng viên | **(TV2 chốt)** |
| 6 | Công thức tích lũy ở §6.4, `w = 0.6` | **(TV2 chốt)** |
| 7 | `C_jarvis = 0.75` | **(đề xuất)** |
| 8 | Điều kiện "chắc chắn" trước khi tạo `CALLS` (§6.3) | **(đề xuất)**, mô phỏng cho thấy cần thiết |
| 9 | Thứ tự ưu tiên khi ghép call site; bước 4 chỉ áp cho gọi qua biến hoặc biểu thức (§6.2) | **(đề xuất)**, mô phỏng cho thấy cần thiết |
| 10 | Khi nâng `MAY_CALL` thành `CALLS`, bỏ các ứng viên `MAY_CALL` còn lại của call site đó | **(đề xuất)** |
| 11 | SCIP/LSP báo lời gọi ra ngoài repo thì JARVIS chỉ được thêm `MAY_CALL` | **(đề xuất)** |
| 12 | Dàn file theo source root không phải package; đổi tên qua đường dẫn file (§5, §6.1) | **(đề xuất)** |

## 4. Image

`src/vgar/graph/jarvis/Dockerfile` và `boot.py`, build trên máy.

```bash
docker build -t vgar/jarvis-analyzer:v1.0 src/vgar/graph/jarvis
```

- `FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`.
- Tải `https://github.com/pythonJaRvis/pythonJaRvis.github.io` tại commit `8871b86494a1aec0095686ffa543994a7361af88`, chỉ giữ `Jarvis/tool/Jarvis`. Mã nguồn JARVIS ghi giấy phép Apache-2.0 ở đầu file; nhóm không cần publish image này. Image cần sẵn `setuptools` (JARVIS dùng `pkg_resources`).
- JARVIS chỉ đọc mã nguồn: loader của nó trả nội dung rỗng (`machinery/imports.py`, `get_data` trả `""`), nên không chạy code của repo. Container vẫn chạy `--network none`, mã nguồn mount chỉ đọc.
- Dùng chế độ mặc định của JARVIS, đúng như các lần đo: không bật `--precision`, `--decy`, không truyền `--entry_point`.
- `boot.py` chạy trong container, làm theo thứ tự:
  1. `import importlib.metadata`, tránh lỗi `FreezableDefaultDict` trên 3.11.
  2. Liệt kê `/src/**/*.py`, sắp xếp, parse từng file **theo đúng cách JARVIS đọc** (`open(path, "rt", errors="ignore")` rồi `ast.parse`). File lỗi ghi vào `/out/skipped.json`, không đưa cho JARVIS. Thực nghiệm cho thấy file lỗi làm JARVIS bỏ qua âm thầm hoặc crash tùy vị trí. File có AST sâu quá 150 tầng cũng bị loại: JARVIS duyệt đệ quy và crash từ độ sâu 255, còn các repo đã đo chưa tới 30.
  3. Chạy JARVIS với `--package /src`, ghi `/out/graph.json`.
  4. `chmod -R a+rwX /out`, để máy chủ Linux xóa được.

## 5. Chạy JARVIS

File mới `graph/jarvis_runner.py`, có `logger = logging.getLogger(__name__)`, không in ra stdout.

```python
@dataclass(frozen=True)
class JarvisConfig:
    image: str = "vgar/jarvis-analyzer:v1.0"
    docker: str = "docker"
    timeout_seconds: float = 120.0

def staged_path(relative_path: str, root: Path, source_roots: tuple[str, ...]) -> str: ...
def run_jarvis(root: Path, python_files: list[Path], source_roots: tuple[str, ...], config: JarvisConfig) -> JarvisResult: ...
```

- `JarvisResult`: `status` thuộc `ready`, `unavailable`, `failed`, `timeout`; `reason`; `graph: dict[str, list[str]]`; `skipped_files: tuple[str, ...]`.
- Trước khi chạy: `docker image inspect <image>`, tối đa 30 s. Lỗi thì `unavailable`, `reason` nêu lệnh build.
- `staged_path` dàn file không phải test vào thư mục tạm. File nằm trong source root **không có `__init__.py`** thì tính đường dẫn từ source root đó; còn lại tính từ gốc repo, vì `xarray/` là package và import tuyệt đối phải giữ tên `xarray`. Trùng đường dẫn thì giữ file đầu và thêm file sau vào `skipped_files`.
- `docker run --rm --name <duy nhất> --network none -e PYTHONHASHSEED=0`, mount mã nguồn chỉ đọc. Gọi không qua shell, đường dẫn dùng `as_posix()`. Stdout của JARVIS (nó in tên từng file) được thu lại, không chuyển ra stdout của tiến trình.
- Hết giờ: `docker rm -f` theo tên, `status` là `timeout`, `reason` bắt đầu bằng `JARVIS_TIMEOUT`. Không ném lỗi ra ngoài.
- Phần chạy Docker giống `joern_runner` thì dùng chung, không chép.

## 6. Đưa kết quả vào graph

File mới `graph/jarvis_merge.py`, hàm thuần trên dữ liệu; builder áp kết quả. Thêm pha `_apply_jarvis` ngay sau `_resolve_calls` (và `_link_chain_references`), trước khi đếm `scip_call_count`.

### 6.1 Đổi tên về node

Mỗi Function, Method, Class ngoài test có tên theo JARVIS: lấy `staged_path` của file đổi thành tên module, nối với phần sau tên module trong `qualified_name`. Tính từ đường dẫn nên đúng với cả `source_roots=("xarray",)`.

Với mỗi cặp `A → B` của JARVIS:

- `A` phải là Function/Method ngoài test.
- `B` không có node (`<builtin>.str`, `<map>.get`, `urllib...`, `x.<lambda1>`): tính là lời gọi ngoài, bỏ và đếm; **giữ lại tên cuối** (`get`) để dùng ở §6.3.
- `pkg.C.__init__`, `pkg.C.__new__` và `pkg.C` là cùng một lời gọi constructor. `CALLS` trỏ vào Class, `MAY_CALL` trỏ vào `__init__`/`__new__`, như builder đang làm.
- Một tên ứng với nhiều node (getter và setter cùng `qualified_name`): bỏ và đếm `ambiguous_names`.

### 6.2 Ghép vào call site

Với mỗi đích `B` của `A`, dừng ở bước đầu tiên có kết quả **(đề xuất)**:

1. **Đã có cạnh:** call site nào trong `A` đã có `CALLS` hoặc ứng viên `MAY_CALL` tới `B` thì chỉ ghép vào các call site đó.
2. **Trùng tên, chưa phân giải:** call site chưa phân giải có phần sau dấu chấm cuối của `callee_text` bằng tên `B` (constructor thì bằng tên class). Còn nhiều thì loại theo số tham số: bỏ call site có `argument_count` lớn hơn số tham số của `B` (Method bỏ `self`/`cls`), trừ khi `signature` có `*`.
3. **Trùng tên, đã phân giải về đích khác:** đây là xung đột, xử lý ở §6.3.
4. **Gọi qua biến hoặc biểu thức:** call site chưa phân giải có `callee_text` là biểu thức (`HANDLERS[action]()`, `may_call.callee_name` trả `None`), hoặc là tên trần trỏ tới tham số, biến cục bộ (`_resolve_lexical_binding` trả `True`). `B` là dunder thì không gắn. Các cạnh này luôn là `MAY_CALL`, `match_kind` là `jarvis_indirect`.

Không bước nào khớp thì đếm `no_call_site`. `J(s)` là tập đích đã ghép vào call site `s` ở bước 1–3.

### 6.3 Luật cạnh

**Chắc chắn** **(đề xuất)** nghĩa là cả bốn điều sau đều đúng: `J(s)` có đúng một đích; chính `s` mang tên đích đó; `A` chỉ có một call site mang tên đó; JARVIS không báo đích cùng tên nào khác trong `A` mà không đặt được vào một node (đích ngoài repo như `<map>.get`, hoặc tên ứng với nhiều node). Nếu thiếu điều này, `data.get()` và `codec.get()` trong cùng hàm sẽ bị gán chung vào `Codec.get`.

| Trạng thái call site `s` | Điều kiện | Kết quả |
|---|---|---|
| Có `CALLS` tới `t` | `t ∈ J(s)` | Giữ cạnh, thêm `jarvis` vào `evidence`, nâng `confidence` theo §6.4 |
| Có `CALLS` tới `t` | `t ∉ J(s)`, `J(s)` không rỗng | Giữ `CALLS`; thêm `MAY_CALL` tới từng đích, `confidence` 0.50, `evidence` có `conflict_with_call`; đếm `conflicts` |
| SCIP/LSP ghi `resolution_reason: external_or_non_callable` | `J(s)` không rỗng | Không tạo `CALLS`; thêm `MAY_CALL` như dòng trên **(đề xuất)** |
| Chưa phân giải, có ứng viên `MAY_CALL` | Chắc chắn, đích là một ứng viên | Thay `MAY_CALL` đó bằng `CALLS` 0.75; bỏ các ứng viên còn lại của `s` |
| Chưa phân giải, có ứng viên `MAY_CALL` | Còn lại | Ứng viên trùng được thêm `jarvis` vào `evidence`; đích mới thành `MAY_CALL` |
| Chưa phân giải, không có ứng viên | Chắc chắn | `CALLS` 0.75 |
| Chưa phân giải, không có ứng viên | Không chắc chắn | `MAY_CALL` |

- Mỗi call site có tối đa 5 ứng viên `MAY_CALL` tính cả ứng viên cũ (`may_call.MAX_CANDIDATES`). Vượt thì không thêm cạnh mới và đếm `overflow_unresolved_calls`.
- `MAY_CALL` mới: `confidence` theo `may_call.confidence(ANALYZER_TOOL_PRECISION, import_coherent=...)`, tức 0.42 hoặc 0.50 ([P] 554). `match_kind` là `jarvis`, `jarvis_indirect` hoặc `jarvis_conflict`; `rule_id` theo mẫu `python.call.may_call.<match_kind>.v1`; `evidence` theo `may_call.evidence`. Khi thêm hoặc bỏ cạnh, `properties.candidate_count` của mọi `MAY_CALL` trên call site đó và `statistics.may_call` phải được cập nhật.
- `source_tool` là `jarvis`, `source_tool_version` là commit.
- `CALLS` mới: `rule_id` `python.call.jarvis.resolve.v1`, `resolution` `analyzer`, `properties` có đủ `binding_kind: jarvis`, `argument_match: null`, `candidate_rank: 1`, `confidence_reason`. Call site được đặt `resolution_status: resolved`, `candidate_count: 1` (validator kiểm tra số này bằng số cạnh `CALLS`), `resolver: jarvis`; đích là Class thì `dispatch_kind: constructor`.
- `CALLS` đã có **giữ nguyên** `source_tool` ([P] 565), chỉ thêm vào `evidence`.

### 6.4 Nâng confidence

`C_new = 1 - (1 - C_old) × (1 - w × C_jarvis)`, `w = 0.6`, `C_jarvis = 0.75`, làm tròn 2 chữ số. `C_new` không bao giờ nhỏ hơn `C_old`. Ví dụ `0.60` thành `0.78`, `0.95` thành `0.97`. Không nâng `confidence` của `MAY_CALL`, vì validator giới hạn cạnh này ở 0.50.

## 7. Tích hợp vào builder

- `PythonGraphBuilder(jarvis=JarvisConfig())`, mặc định `None`. CLI: `--enable-jarvis`, `--jarvis-image`, `--jarvis-timeout`.
- `run_jarvis` chạy trước `_calculate_graph_version`. Khi bật, `graph_version` thêm `jarvis-call-graph-v1`, image, commit và `status`.
- `statistics.jarvis`: `status`, `reason`, `image`, `skipped_files`, `edges_total`, `external`, `ambiguous_names`, `no_call_site`, `confirmed`, `upgraded`, `new_calls`, `new_may_call`, `conflicts`, `overflow_unresolved_calls`.
- `resolver.static_call_count` không tính cạnh `jarvis`; thêm `jarvis_call_count`.
- `IncrementalGraphBuilder` không nhận tùy chọn này.
- `build_graph.py` in `WARNING` khi đã bật mà `status` khác `ready`.

Không đổi `SCHEMA_VERSION`, vì không thêm loại node hay cạnh. `visualization.py` hiện cạnh `jarvis` là "Static"; không sửa vì ngoài phạm vi.

## 8. Tiêu chí nghiệm thu

**Test không cần Docker**, dùng `graph.json` ghi lại từ JARVIS thật:

| Nhóm | Ca |
|---|---|
| Đổi tên | Tên ngoài repo, `<builtin>`, `<lambda>`; constructor; getter và setter trùng tên; layout `src/`, repo phẳng, `source_roots=("xarray",)` |
| Ghép call site | Mỗi bước ở §6.2; cạnh đã có được ưu tiên; `*args`; `HANDLERS[action]()`; tham số `handler(x)`; `isinstance`, `len` và tên import không nhận cạnh; lời gọi ngầm không tạo cạnh |
| Luật cạnh | Mỗi dòng ở §6.3; `data.get()` và `codec.get()` trong cùng hàm không thành `CALLS`; vượt 5 ứng viên; đích là Class; validator đạt sau khi nâng |
| Confidence | Đơn điệu với 0.60, 0.95, 0.98; `source_tool` giữ nguyên; `MAY_CALL` không quá 0.50 |
| Builder | Tắt: document giống hệt; bật: qua validate; `graph_version` khác nhau khi bật và tắt; `statistics.may_call` khớp số cạnh |
| Lỗi | Thiếu Docker, thiếu image, mã lỗi, hết giờ (có `docker rm -f`), JSON hỏng: graph vẫn build, `status` đúng, không có cạnh `jarvis` |
| `boot.py` | File lỗi cú pháp bị loại và ghi vào `skipped.json`, ở mọi vị trí trong danh sách; file không phải UTF-8 đọc như JARVIS |
| Windows, Linux | Lệnh Docker đúng với đường dẫn `C:\...`, `/home/...`, có dấu cách và tiếng Việt |

**Đo trên repo thật, cần Docker** (marker `docker` hoặc script ghi vào `docs/status/`):

1. `vgar-callgraph-cases` và bản `-flat`, chấm bằng cách của `tests/test_callgraph_cases.py`: precision và recall của `CALLS` và của `CALLS + MAY_CALL`, có và không có JARVIS. **Đạt khi precision của `CALLS` không giảm và recall tăng** **(TV2 chốt)**, đồng thời `claims_external`, `claims_unknown` của `CALLS` không tăng **(đề xuất)**. Mốc hiện tại ở chế độ static: `CALLS` không có cạnh sai; `CALLS + MAY_CALL` precision 0,579, recall 0,746.
2. 13 repo đã thử: chạy trên 3.11, so số cạnh và thời gian với kết quả 3.8 đã lưu (các lần đó chưa cố định seed nên chênh nhỏ là bình thường). Repo hết 120 s được ghi lại, không chỉnh luật để né. Chạy thêm xarray và ghi kết quả.
3. Chạy hai lần cùng repo: kết quả giống hệt.
4. Windows và WSL Ubuntu: `graph.json` giống hệt trên cùng mã nguồn.
5. Toàn bộ test suite chỉ còn đúng các test fail đã biết.

## 9. Giới hạn đã biết

- Số ở bảng thứ hai của §1 chỉ là ước lượng: JARVIS chạy thật, nhưng luật gộp cạnh là script mô phỏng và chỉ có hai repo fixture. Script chưa xét constructor kế thừa nên có `fp = 1` ở cả hai dòng; test thật báo 0.
- Độ đúng mới đo được trên hai repo fixture; trên repo thật chỉ có số lượng cạnh.
- Bảng đầu §1 đo với resolver static; khi bật SCIP, tỷ lệ sẽ khác.
- `PYTHONHASHSEED=0` chỉ giúp lặp lại được, không làm kết quả đúng hơn. Với cùng seed, các version Python vẫn lệch nhẹ (vgar khoảng 20/5.375 cạnh).
- File dùng cú pháp mới hơn 3.11 (`def f[T]`) bị loại và báo trong `skipped_files`; các cạnh của file đó vẫn lấy từ SCIP/static.
- Không phân giải được constructor kế thừa khi tên class khác tên class định nghĩa `__init__`; các ca này được đếm ở `no_call_site`.
- xarray-4629 từng hết giờ ở 580–900 s trong lần thử trên Windows; với image và cách dàn file của spec, 101 file không phải test xong trong 13,6 s. Chưa tách được yếu tố nào quyết định, và repo khác vẫn có thể hết 120 s.
- `_do_import` của JARVIS đọc `sys.modules` trước, nên đã thử repo có `utils.py`, `formats.py` cấp cao nhất trùng tên module của JARVIS: cạnh vẫn đúng. Chưa thử `machinery`, `processing`.
