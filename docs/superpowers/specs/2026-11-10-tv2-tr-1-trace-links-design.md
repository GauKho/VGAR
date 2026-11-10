# TV2 · TR-1: trace links từ `G_task` tới `G_repo` và `G_arch`

> **Trạng thái:** đã duyệt 10/11/2026, cập nhật cùng ngày theo kết quả research và số đo mới.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), **[cp]** `Downloads\context\check proposal.txt`, **[rq]** `rq metrics matrix.txt`. Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(research)** là câu trả lời research ngày 10/11 đã đối chiếu với proposal và số đo. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh

[plan] dòng 130 ghi TR-1 là "Trace links từ `G_task` tới `G_repo` và `G_arch`". [P] định nghĩa `Trace` là "ánh xạ nối task/requirement với component/code/test" (172), là bước `build_trace_links(G_task, G_repo, G_arch)` của pipeline (491). [cp] Bước 7 yêu cầu nối `G_task` với cả `G_repo` và `G_arch`.

**Hiện trạng sau GT-1:**

| Liên kết | Trạng thái |
|---|---|
| Issue → File, Module, Class, Function, Method, Test, Route (`MENTIONS`) | Có |
| Issue → Component (`TRACES_TO`) | Có, nằm trong `TaskOverlayBuilder._add_traces` |
| `StackTraceFrame`, `FailingTest`, `ErrorMessage` → code | Chưa có: các node này chỉ treo vào Issue |
| Requirement → Component | Không có: GT-1 đã chốt Requirement chỉ có trong schema |
| Đo trace link P/R | Chưa có |

**Đo trên 16 task SWE-bench** có checkout trong WSL (đều thuộc bộ dev theo `split_of`; bỏ django, sympy, matplotlib, scikit-learn, sphinx vì quá nặng), không truyền failing test, lấy file trong patch gold làm đáp án xấp xỉ như [plan] dòng 400 và [rq] cho phép. Số trong ngoặc vuông là khoảng tin cậy 95%, bootstrap theo task.

| Cách chọn Issue → Component | Số cạnh | Đúng | Precision | Recall |
|---|---|---|---|---|
| Mọi cạnh (hiện tại) | 32 | 14 | 0,44 | 0,82 |
| `confidence` ≥ 0,5 đến 0,7 (kết quả như nhau) | 26 | 14 | 0,54 [0,41–0,76] | 0,82 [0,65–1,00] |
| `confidence` ≥ 0,75 | 25 | 13 | 0,52 | 0,76 |
| `confidence` ≥ 0,8 | 7 | 6 | 0,86 | 0,35 |
| Top-2 mỗi issue, trong các cạnh ≥ 0,7 | 21 | 14 | 0,67 | 0,82 |
| Top-1 mỗi issue | 14 | 12 | 0,86 [0,67–1,00] | 0,71 [0,50–0,88] |
| Baseline: luôn chọn component nhiều file nhất (hòa lấy id nhỏ nhất, §6) | 16 | 8 | 0,50 [0,25–0,75] | 0,47 [0,25–0,71] |
| Baseline: chọn ngẫu nhiên 1 component | | | 0,10 | |

Top-1 có 2 task hòa ở vị trí đầu, nên số đúng thực sự nằm trong khoảng 11–13 tùy cách tách hòa. MRR là 0,81. Issue → file code có precision 0,04 (14/319), recall 0,56 (14/25).

Trong 12 cạnh sai ở mức ≥ 0,7 có 11 cạnh chỉ dựa vào một anchor, và 9 trong 11 cạnh đó có tên anchor là từ thông dụng trùng với một symbol trong repo, như `isinstance`, `time`, `x`, `value`, `kwargs`. Chỉ 1/16 issue có traceback (`psf__requests-1724`, 3 traceback giống nhau, tổng 33 frame).

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Có bước `build_trace_links` riêng, như [P] 491 **(TV2 chốt)**.
2. `StackTraceFrame`, `FailingTest`, `ErrorMessage` nối được tới code bằng khớp chính xác **(TV2 chốt)**.
3. Issue → Component giữ mọi cạnh kèm `confidence`, cạnh yếu chỉ bị lọc khi đo hoặc khi dùng ([P] 551–557, **research**). Mục tiêu này thay cho "không tạo cạnh khi chỉ có anchor yếu" của bản trước.
4. Đường dẫn tuyệt đối trong traceback trở thành anchor **(research)**.
5. Có công cụ đo trace link P/R để G1 dùng lại **(TV2 chốt)**, có baseline, khoảng tin cậy, và không chạy được trên held-out theo mặc định **(research)**.

**Ngoài phạm vi**

- Giảm nhiễu Issue → file: thuộc bước tìm anchor và RT-1 **(TV2 chốt)**.
- Chỉnh thêm luật theo 16 task đã đo, để tránh khớp quá mức **(TV2 chốt)**.
- Cắt top-k ở đầu ra công cụ cho agent: thuộc RT-1 **(research)**.
- Gán nhãn tay các trace link: thuộc G1 ([plan] dòng 166).
- Requirement, UserStory và `TESTS: Test → Requirement`: GT-1 đã chốt chưa có luật trích.

**Điều cần tránh**

- Làm đổi anchor hoặc cạnh `MENTIONS` của issue không có đường dẫn tuyệt đối trong traceback.
- Đoán đích khi có nhiều ứng viên: không chắc thì không tạo cạnh.
- Nối frame của thư viện chuẩn hoặc script của người báo lỗi vào file trùng tên trong repo.
- Đưa `FAIL_TO_PASS` vào công cụ đo.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | Tách `build_trace_links` thành module riêng | **(TV2 chốt)** |
| 2 | Liên kết của frame, failing test, error message dùng `RESOLVES_TO`; `TRACES_TO` giữ đúng nghĩa ở [P] 318, 873 | **(đề xuất)** |
| 3 | Bảng khớp frame ở §4.2 và các giá trị `confidence` | **(đề xuất)** |
| 4 | Giữ cạnh yếu; mốc 0,7 chỉ dùng khi đo | **(research)**, [P] 551–557 |
| 5 | Sửa đường dẫn tuyệt đối ngay trong TR-1 | **(research)** |
| 6 | Số báo cáo chính cho G1 là precision, recall ở `confidence` ≥ 0,7; top-1, top-2 và baseline đi kèm | **(đề xuất)** |
| 7 | `SCHEMA_VERSION` lên `vgar-schema-full-v5`, profile overlay đổi | **(đề xuất)** |

Về quyết định 2: [P] 864 định nghĩa `beta` là các cặp đầu cuối được phép của một loại cạnh, và [P] 318, 873 chỉ cho `TRACES_TO` đi từ Issue hoặc Requirement tới Component. [P] 548 có sẵn `CallSite --RESOLVES_TO--> Method`, cùng nghĩa với việc một tham chiếu dạng văn bản được xác định tới định nghĩa của nó. Dùng lại tên này không phải thêm tên cạnh mới và không làm sai `beta(TRACES_TO)`.

## 4. `build_trace_links`

File mới `graph/trace_links.py`, có `logger`, không in ra stdout.

```python
@dataclass(frozen=True)
class TraceLink:
    edge_type: str  # "TRACES_TO" hoặc "RESOLVES_TO"
    source_id: str
    target_id: str
    confidence: float
    rule_id: str
    evidence: list[dict[str, str]]
    properties: dict[str, Any]

def build_trace_links(issue_id: str, task_nodes: list[dict[str, Any]], grounding: AnchorResult, nodes: list[dict[str, Any]]) -> list[TraceLink]: ...
def rank_component_traces(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

`TaskOverlayBuilder` gọi `build_trace_links` thay cho `_add_traces`, và biến mỗi `TraceLink` thành một cạnh trong overlay. `_edge` nhận thêm `rule_id` để các luật mới có id riêng. Cạnh `MENTIONS` và `REPRODUCES` giữ nguyên chỗ cũ.

| Nguồn | Cạnh | Đích | `rule_id` |
|---|---|---|---|
| Issue | `TRACES_TO` | Component | `task.traces_to.v1` |
| StackTraceFrame | `RESOLVES_TO` | File, Class, Function, Method, Test | `task.resolves_to.frame.v1` |
| FailingTest | `RESOLVES_TO` | Test | `task.resolves_to.failing_test.v1` |
| ErrorMessage | `RESOLVES_TO` | Class | `task.resolves_to.error.v1` |

### 4.1 Issue → Component

Giữ nguyên cách hiện tại: gom anchor theo Component qua `properties.files`, bỏ anchor mà mọi bằng chứng đều mơ hồ, `confidence` là `score` lớn nhất, `properties.anchor_count`, `evidence` tối đa 5. Không lọc theo `confidence`.

`rank_component_traces` nhận các cạnh `TRACES_TO` của một issue và trả về theo thứ tự: `confidence` giảm dần, `anchor_count` giảm dần, `target_id` tăng dần. Công cụ đo dùng hàm này, RT-1 dùng lại. Đổi chỗ hai khóa đầu không làm đổi top-1 trên 16 task đã đo.

Mốc 0,7 theo thang điểm sẵn có của grounding: đó là mức thấp nhất vẫn chỉ đích danh một vị trí (đường dẫn, liên kết mã nguồn; tên trong code là 0,75), còn phía dưới là từ thường, tên đoán theo receiver và tên mơ hồ.

### 4.2 StackTraceFrame → code

**Đường dẫn tuyệt đối.** `graph/grounding.py` có thêm hàm thuần `resolve_absolute_frame(path: str, files: Collection[str]) -> str | None`, dùng ở hai nơi:

- `TaskAnchorFinder`: với match của `_TRACEBACK` có đường dẫn tuyệt đối, dùng hàm này thay cho `_match_paths`, để frame thành anchor `path_line` như frame tương đối. `_QUOTED_LOCATION`, `_LOCATION` và đường dẫn tương đối không đổi.
- `build_trace_links`: tìm file cho frame.

**Tìm file** từ `properties.file`, sau khi đổi `\` thành `/`. Đường dẫn có đoạn `..` không khớp.

| Dạng đường dẫn | Cách khớp | Ví dụ thật từ `psf__requests-1724` |
|---|---|---|
| Có `site-packages/` hoặc `dist-packages/` | Lấy phần sau lần xuất hiện cuối; phải trùng đúng một trong `<phần đó>`, `src/<phần đó>`, `lib/<phần đó>` | `/Library/Python/2.7/site-packages/requests/api.py` → `requests/api.py` |
| Nằm dưới thư mục `pythonX.Y` | Thư viện chuẩn, không khớp | `.../lib/python2.7/httplib.py` |
| Tuyệt đối khác (`/...`, `C:/...`) | Path repo dài nhất mà đường dẫn kết thúc bằng `/<path repo>`; path repo phải có ít nhất một thư mục | `/Users/hwkns/test_requests.py` không nối vào `test_requests.py` ở gốc repo |
| Tương đối, có thư mục | Khớp đúng, hoặc đúng một path repo kết thúc bằng `/<đường dẫn>` | |
| Tương đối, chỉ có tên file | Chỉ khớp file cùng tên ở gốc repo | |

Ba luật đầu đã thử trên 33 frame thật: 18 frame nối được, 12 frame `httplib.py` và 3 frame script của người báo lỗi không nối. Luật `site-packages` không nối `site-packages/urllib3/x.py` vào bản vendored `requests/packages/urllib3/x.py`, vì đó là hai bản code khác nhau.

**Chọn đích** trong file đó. Symbol gồm Class, Function, Method, Test. Tên hàm được ưu tiên hơn số dòng, vì traceback thường đến từ phiên bản khác:

| Trường hợp | Đích | `confidence` |
|---|---|---|
| Symbol nhỏ nhất chứa dòng có tên đúng `function` | Symbol đó | 0,95 |
| Dòng không khớp, nhưng file có đúng một symbol tên `function` | Symbol đó | 0,8 |
| `function` trống hoặc bắt đầu bằng `<` (`<module>`, `<lambda>`) | File | 0,7 |
| Còn lại | File | 0,6 |

`evidence` là `[{"kind": "frame_location", "file": ..., "line": ...}]`. Frame sâu nhất trong repo suy ra được từ `order` lớn nhất trong các frame có cạnh, nên không thêm trường mới.

### 4.3 FailingTest → Test

Mỗi id trong `properties.test_node_ids` là một cạnh. `confidence` là `score` của anchor đó. `evidence` là `[{"kind": "test_selector", "selector": ...}]`. Node `FailingTest` chỉ có khi nơi gọi truyền `failing_tests`.

### 4.4 ErrorMessage → Class

Từ `properties.exception_type`:

| Trường hợp | Đích | `confidence` |
|---|---|---|
| Tên có dấu chấm, trùng đúng `qualified_name` của một Class | Class đó | 0,9 |
| Tên không có dấu chấm và là exception có sẵn của Python (`ValueError`, `ConnectionError`) | Không tạo cạnh | |
| Còn lại: lấy phần cuối của tên, repo có đúng một Class tên đó và Class đó là exception | Class đó | 0,6 |
| Còn lại | Không tạo cạnh | |

Class là exception khi `properties.bases` có exception có sẵn của Python, hoặc có lớp cha trong repo là exception (tìm theo tên, phải đúng một Class, có chặn vòng lặp). Không xác định được thì coi là không phải.

`evidence` là `[{"kind": "exception_name", "name": ...}]`.

## 5. Schema và overlay

- `EDGE_ENDPOINTS` thêm `"RESOLVES_TO"` với các cặp `(StackTraceFrame, File)`, `(StackTraceFrame, Class)`, `(StackTraceFrame, Function)`, `(StackTraceFrame, Method)`, `(StackTraceFrame, Test)`, `(FailingTest, Test)`, `(ErrorMessage, Class)`, kèm ghi chú "Proposed, pending team review".
- `TRACES_TO` không đổi.
- `SCHEMA_VERSION` lên `vgar-schema-full-v5`; hai assert ở `tests/test_task_graph.py:42` và `tests/test_code_graph.py:47` đổi theo.
- `profile` trong `overlay_id` đổi thành `task-overlay-v11-trace-links`.
- `sqlite_service` trả `trace_edges` là toàn bộ `overlay.edges`, nên công cụ MCP hiện có nhận thêm cạnh mới mà không đổi giao diện.
- Retrieval không duyệt `TRACES_TO` và `RESOLVES_TO`. Thay đổi duy nhất tới retrieval là anchor mới từ frame tuyệt đối.

## 6. Công cụ đo

`evaluation/trace_quality.py` (hàm thuần) và `scripts/measure_trace_links.py`.

```python
@dataclass(frozen=True)
class RankedTrace:
    confidence: float
    correct: bool

@dataclass(frozen=True)
class TraceScore:
    task_id: str
    has_traceback: bool
    components: int
    gold_files: int
    gold_components: int
    largest_component_correct: bool
    traces: tuple[RankedTrace, ...]  # theo thứ tự của rank_component_traces
    top_tied: bool
    mentioned_files: int
    mentioned_correct: int

def score_task(document: dict[str, Any], overlay: TaskOverlay, gold_files: Sequence[str]) -> TraceScore: ...
def summarise(scores: Sequence[TraceScore], seed: int = 0, rounds: int = 2000) -> dict[str, Any]: ...
```

**`score_task`.** Component đúng là Component có chứa file đáp án. "Nhiều file nhất" tính theo `properties.files`, hòa thì lấy id nhỏ nhất.

**`summarise`** trả ba nhóm: mọi task, task có traceback, task không có traceback **(research)**. Mỗi nhóm có `n` và:

- Precision, recall Issue → Component, cộng dồn trên các task rồi mới chia, cho: mọi cạnh; `confidence` ≥ 0,5, 0,6, 0,7, 0,8 **(research)**; top-1 và top-2 trong các cạnh ≥ 0,7.
- MRR và số task hòa ở vị trí đầu.
- Baseline: chọn ngẫu nhiên (`gold_components / components` trung bình theo task) và luôn chọn component nhiều file nhất **(research)**.
- Precision, recall Issue → file.
- Khoảng tin cậy 95% cho precision và recall của mức ≥ 0,7, top-1 và baseline nhiều file nhất: bootstrap theo task, cùng quy ước số vòng, seed và phân vị với `evaluation/retrieval/compare.py` **(research)**. Lấy mẫu theo task vì các cạnh trong một task không độc lập.

**Script.** `scripts/measure_trace_links.py --manifest <json> --repositories <thư mục> --output <json> [--allow-heldout]`.

- Manifest theo định dạng của `scripts/prepare_manifest.py`. Đáp án là `changed_source_files` của từng task.
- Gọi `validate_task` và `require_split` như `evaluate_manifest`: mặc định chỉ nhận bộ dev; held-out cần `--allow-heldout` và phải qua kiểm tra freeze sẵn có **(research)**, [plan] dòng 70, 391.
- Checkout nằm ở `<thư mục>/<instance_id>`; HEAD khác `base_commit` thì bỏ task đó và ghi lại.
- Không truyền failing test vào overlay, vì agent không có thông tin này khi nhận task.

## 7. Tiêu chí nghiệm thu

**Test không cần repo thật**, chạy trên Windows và WSL:

| Nhóm | Ca |
|---|---|
| Issue → Component | Các test GT-1 giữ nguyên, không sửa; cạnh `confidence` thấp vẫn có; `rank_component_traces` đúng thứ tự, hòa tách theo id |
| Anchor từ traceback | Frame tuyệt đối trong `site-packages` thành anchor `path_line`; đường dẫn tuyệt đối trong văn xuôi vẫn bị bỏ; issue không có traceback tuyệt đối có anchor và `MENTIONS` như cũ |
| Tìm file của frame | Mỗi dòng bảng §4.2; layout `src/` và `lib/`; bản vendored; script trùng tên file ở gốc repo; đường dẫn Windows; đường dẫn có `..`; nhiều file cùng khớp |
| Chọn đích frame | Mỗi dòng bảng chọn đích ở §4.2 |
| FailingTest | Có cạnh; `confidence` đúng |
| ErrorMessage | Tên qualified; tên có sẵn của Python; Class trùng tên nhưng không phải exception; kế thừa nhiều tầng; vòng kế thừa; nhiều Class trùng tên |
| Schema | `RESOLVES_TO` qua `validate_graph_document`; cặp đầu cuối sai bị từ chối, gồm frame → File bằng `TRACES_TO` |
| Overlay | `overlay_id` đổi theo profile; thứ tự cạnh ổn định |
| Công cụ đo | Số tính tay cho mọi mục ở §6; cùng seed cho cùng khoảng tin cậy; từ chối task held-out; bỏ task sai `base_commit`; không truyền failing test |

**Chạy thật** (ghi vào `docs/status/`):

1. Chạy công cụ trên 16 task đã đo. 15 task không có traceback phải cho đúng các cạnh như lần đo ở §1; nếu khác là lỗi. `psf__requests-1724` được phép khác vì có thêm anchor từ frame tuyệt đối, và báo cáo phải ghi rõ khác ở đâu.
2. Trên `psf__requests-1724`: 18/33 frame có cạnh; số frame theo từng dòng của bảng chọn đích.
3. Toàn bộ test suite chỉ còn đúng các test fail đã biết.

Không đặt ngưỡng đạt cho precision, recall vì nguồn không quy định.

## 8. Giới hạn đã biết và bàn giao

- Đáp án là file trong patch gold: một component được đọc để hiểu lỗi nhưng không bị sửa, hoặc một cách sửa khác cũng qua test, vẫn tính là sai. Nhãn tay thuộc G1 ([plan] dòng 166), cỡ mẫu và người gán do nhóm quyết.
- 16 task chỉ đủ cho pilot. Với tỷ lệ quanh 0,5, khoảng tin cậy rộng khoảng ±22 điểm phần trăm ở 16 mẫu, ±14 ở 50 mẫu, và cần khoảng 385 mẫu mới còn ±5. Các khoảng của precision, recall và baseline ở §1 đang chồng lên nhau.
- Precision ở mức ≥ 0,7 (0,54) chỉ nhỉnh hơn baseline nhiều file nhất (0,50), và baseline này đổi theo cách tách hòa (9/16 nếu `astropy__astropy-13398` tách hòa ngược lại); recall cao hơn rõ. Top-1 vượt baseline ở cả hai, nhưng hai task hòa và cỡ mẫu nhỏ làm kết quả này chưa chắc.
- Nhóm có traceback chỉ có 1 task trên bộ này, nên số của nhóm đó chỉ để báo cáo.
- Các frame cùng đường dẫn tương đối với nhiều file trong repo không có cạnh.
- Requirement chưa có liên kết vì chưa có luật trích.

**Bàn giao cho RT-1:** nên dùng top-1 hoặc top-2 `TRACES_TO` thay vì mọi cạnh; nên giảm điểm các anchor là từ thông dụng, vì đây là nguồn chính của cạnh sai; đo lại các đề xuất cộng điểm theo component trước khi đưa vào. [P] 981–991 đã liệt kê các đặc trưng xếp hạng, gồm `edge_confidence`.

## 9. Các đề xuất của research không đưa vào

Danh mục tài liệu (các số 1–39) không có trong bản dán, nên các trích dẫn chưa được dùng làm căn cứ.

| Câu | Đề xuất | Lý do |
|---|---|---|
| 1 | Đổi thang điểm anchor thành các nhóm mới | Thang hiện tại đã rời rạc theo loại bằng chứng; đổi sẽ làm đổi mọi anchor |
| 2 | Điểm độ hiếm, công thức 3 trọng số | Cả 11 cạnh sai một anchor đều có tên duy nhất trong repo, nên độ hiếm theo định nghĩa còn đẩy chúng lên. Theo tần suất trong mã nguồn, ngưỡng cân bằng nhất trong các ngưỡng đã thử đạt P 0,71, R 0,71 và phải chọn trên chính 16 task. Công thức trọng số bằng nhau đạt P 0,56. Top-1 đạt P 0,86, R 0,71 mà không cần ngưỡng |
| 3 | Mốc đo 0,5 | Trên 16 task cho kết quả như 0,7; mốc 0,7 có nghĩa rõ hơn, báo cáo cả hai |
| 4 | Cắt thích ứng 0,5 × max, tối đa 3 | Trên thang `confidence` gần như không cắt gì (P 0,52); việc cắt để RT-1 đo |
| 6 | BM25 cho component, MAP, Jaccard | Plan không yêu cầu BM25 ở mức component; hầu hết task có 1 component đúng nên MAP gần bằng MRR; Jaccard lặp thông tin của P/R |
| 7 | Công thức Wilson; 50 task đạt ±5% | Công thức được ghi là Wald; ±5% cần khoảng 385 mẫu (§8) |
| 10 | Frame sâu nhất đáng tin nhất | Task duy nhất có traceback cho kết quả ngược lại: frame sâu nhất ở `connectionpool.py`, đáp án là `sessions.py`. Chưa đủ cơ sở để thành luật |
| 12 | `CALLS_SYMBOL`, `INVOLVES_FILE`, `THROWN_BY` | Không có trong proposal hay các file context; dùng `RESOLVES_TO` (quyết định 2) |
| 13 | `EXTENDS`, `ExternalSymbol`, kiểm tra import | Repo dùng `INHERITS` và `properties.bases`; không có node `ExternalSymbol`; tên có sẵn của Python thì không tạo cạnh |
| 15, 16 | Công thức cộng điểm, lọc theo ngữ cảnh, tỉa đồ thị | Thuộc RT-1, cần đo khi làm RT-1 |
