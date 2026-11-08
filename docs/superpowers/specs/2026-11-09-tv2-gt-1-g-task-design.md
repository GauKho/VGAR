# TV2 · GT-1: trích `G_task` từ issue và test đang fail

> **Trạng thái:** bản nháp, chờ duyệt. Soạn ngày 09/11/2026.
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng) và các nguồn của plan trong `Downloads\context`:
> **[cp]** `check proposal.txt`, **[test]** `test.txt`, **[rq]** `rq metrics matrix.txt`, **[mm]** `metrics matrix.txt`.
> Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng, không phải yêu cầu.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.
> Không có đánh dấu nghĩa là nguồn đã ghi rõ.

## 1. Bối cảnh và lý do

| Plan ghi ở GT-1 | Spec này làm |
|---|---|
| Node BugReport, FailingTest, ErrorMessage, StackTraceFrame, AcceptanceCriterion | Khai báo và sinh dữ liệu |
| Node Requirement, UserStory, Constraint, Actor | Chỉ khai báo trong schema (§5.7) **(TV2 chốt)** |
| Cạnh `TRACES_TO` | `Issue → Component` (§5.6) |
| Cạnh `DEPENDS_ON`, `CONFLICTS_WITH` giữa Requirement | Chỉ khai báo trong schema (§5.7) |

Issue, `MENTIONS`, `REPRODUCES` đã có từ trước ([cp] 93). Task phía sau là TR-1 ([plan], nối `G_task` với `G_repo` và `G_arch`).

**Đo trên 50 issue của bộ dev** (`configs/m1/w10_dev_manifest.json`, chỉ đọc `problem_statement`), với đúng các luật ở §5:

| Loại | Số issue có dữ liệu | Ghi chú |
|---|---|---|
| StackTraceFrame | 5/50 | 72 frame |
| ErrorMessage | 10/50 | 16 dòng trước khi gộp trùng |
| BugReport (chỉ từ issue text) | 10/50 | Từ khóa như "bug", "error" có ở 31/50 nhưng không dùng (§5.4) |
| AcceptanceCriterion | 0/50 | Luật có, bộ dev chưa có dữ liệu |
| Route trong issue | 0/50 | |
| Label dạng dòng `Labels:` | 0/50 | Nên label nhận qua tham số (§4) |

## 2. Mục tiêu, phạm vi loại trừ, điều cần tránh

**Mục tiêu**

1. `TaskOverlayBuilder.build` trả về thêm các node, cạnh `G_task` ở §5, và kết quả qua `validate_graph_document`.
2. Có test tầng 1 với đáp án viết tay ([test] mục 1).

**Không làm trong spec này**

- Trace link tới `G_repo`, đo trace link P/R: TR-1 và G1.
- Trích từ docs ([P] 456 có nhắc nhưng không có luật).
- Embedding, classifier: [P] 632 để sau MVP.
- Expose qua MCP: L6-2, L6-3 của TV1.

**Điều cần tránh** (vẫn tính là hỏng dù code chạy)

- Lấy `failing_tests` hoặc nhãn từ dữ liệu gold. GT-1 chỉ dùng những gì caller truyền vào.
- Suy ra BugReport từ từ khóa trong văn bản.
- Tự chế Requirement, UserStory, Constraint, Actor khi không có luật.
- Làm build overlay thất bại vì văn bản issue lạ.
- Đổi `overlay.nodes[0]`: phần tử đầu phải luôn là Issue (`retrieval.py:173`).

## 3. Hiện trạng cần biết

- `TaskOverlayBuilder.build(task_id, issue_text, failing_tests)` (`task_overlay.py:34`) tạo một node Issue, các cạnh `MENTIONS` tới anchor, và `Test --REPRODUCES--> Issue`. Cuối hàm validate toàn bộ.
- `retrieval.py:170-171` coi mọi nguồn của `REPRODUCES` là node Test. Cạnh `FailingTest → BugReport` mới sẽ làm sai chỗ này, nên phải lọc (§7).
- Tất cả node `G_task` là riêng cho từng task, không nằm trong graph của repo.

## 4. Vị trí trong pipeline

`G_task` nằm trong overlay theo từng task **(TV2 chốt)**, không ghi vào graph repo.

- Module mới `src/vgar/graph/task_graph.py`: hàm thuần `extract_task_facts(issue_text, *, failing_tests, labels)`, chỉ đọc văn bản, không đọc graph **(đề xuất)**.
- `TaskOverlayBuilder.build` nhận thêm tham số tùy chọn `labels: list[str] | None = None` ([P] 628). Label được chuẩn hóa `strip().lower()`, bỏ trùng, sắp xếp, lưu ở `properties.labels` của Issue (`[]` khi không truyền).
- `profile` trong `overlay_id` đổi thành `task-overlay-v10-g-task`.

## 5. Quy tắc trích

Id của mọi node mới: `vgar:{repo_key}:task:{task_hash}:{kind}:{n}`, với `task_hash` là phần hash trong id Issue hiện có, `n` đếm từ 0 theo thứ tự xuất hiện. Node không source-backed: `path`, `range`, `language` là `None`. `qualified_name` là `{task_id}::{kind}:{n}`. `content_hash` là `_digest` của `properties` **(đề xuất)**.

Mọi cạnh mới dùng `_edge` sẵn có, `rule_id` dạng `task.<loại cạnh viết thường>.v1`.

| Cạnh | Confidence | Căn cứ |
|---|---|---|
| Issue → StackTraceFrame | 0.95 | Khớp định dạng traceback |
| Issue → ErrorMessage | 0.9 | Khớp định dạng dòng lỗi |
| Issue → AcceptanceCriterion | 0.7 | Theo vị trí trong văn bản |
| Issue → BugReport | 0.7 | Luật cấu trúc §5.4 |
| Issue → Route | 0.8 có method, 0.6 không có method | §5.5 |
| FailingTest → BugReport | 0.8 | Do caller báo, chưa chạy kiểm chứng |

Các giá trị này đều là **(đề xuất)**.

### 5.1 StackTraceFrame ([P] 624, 648–649; [cp] 91)

Mỗi lần khớp `File "<path>", line <N>` (có thể có `, in <tên>`), dấu nháy đơn hoặc kép, là một node, kể cả frame trùng nhau. Regex:

```text
File ["'](?P<path>[^"'\r\n]+)["'], line (?P<line>\d+)(?:,\s+in\s+(?P<function>\S+))?
```

`name`: `<path>:<line>`. `properties`: `file`, `line` (số nguyên), `function` (hoặc `None`), `order`. `kind` là `stack_frame`.

### 5.2 ErrorMessage ([P] 626)

Mỗi dòng khớp regex dưới, gộp theo toàn văn dòng (đã `strip`). `kind` là `error`.

```text
^[ \t]*(?:[A-Za-z_]\w*\.)*(?:[A-Z]\w*(?:Error|Exception|Warning)|Exception):[ \t]*\S.*$
```

`name`: tên lỗi không có phần module. `properties`: `exception_type` (đủ phần module), `message`, `occurrences`.

### 5.3 AcceptanceCriterion ([P] 629)

Chỉ lấy gạch đầu dòng nằm ngay dưới một dòng tiêu đề khớp `acceptance criteria`, `acceptance test(s)` hoặc `definition of done` (không phân biệt hoa thường, được có `#`, `*`, `_`, `>`, `-` ở đầu) **(đề xuất)**. Gạch đầu dòng ở nơi khác không tính, vì phần lớn không phải tiêu chí.

Bỏ các khối ` ``` ` trước khi xét. Dãy gạch đầu dòng (`-`, `*`, `+`, `1.`, `1)`, có thể kèm `[ ]`, `[x]`) được phép cách nhau bằng dòng trống và dừng ở dòng đầu tiên không phải gạch đầu dòng. Gộp theo văn bản. `name`: 80 ký tự đầu. `properties`: `text`, `checked` (`True`, `False` hoặc `None`). `kind` là `acceptance`.

### 5.4 BugReport và FailingTest ([P] 303, 307, 322, 627–628)

**BugReport** (`kind` là `bug_report`, tối đa một node, `name` là `task_id`) được sinh khi có ít nhất một trong các dấu hiệu sau **(đề xuất)**: có StackTraceFrame, có ErrorMessage, `failing_tests` không rỗng, hoặc label `bug`. `properties.signals` liệt kê dấu hiệu đã khớp, gồm `stack_frame`, `error_message`, `failing_test`, `label`, sắp xếp tăng dần.

**FailingTest** (`kind` là `failing_test`): mỗi selector trong `failing_tests` sau khi bỏ trùng và sắp xếp là một node, `name` là selector. `properties`: `selector`, `test_node_ids` (id các node Test trong anchor có bằng chứng `source == "failing_test"` mà `matched_text` bằng selector hoặc nằm trong selector, tăng dần, có thể rỗng).

`REPRODUCES`: `FailingTest → BugReport` đúng theo [P] 322. Cạnh `Test → Issue` đang có ([P] 652) giữ nguyên. `properties` giữ `input_reported_failure: true`, `execution_verified: false`.

### 5.5 Route ([P] 336, 625)

Dùng `_ROUTE` của `grounding.py`. `Issue --MENTIONS--> Route` khi trong issue có đường dẫn trùng `properties.route_path` của node Route và, nếu có method, method đó nằm trong `properties.methods`. Route chỉ có khi graph được build với tree-sitter-graph.

### 5.6 `TRACES_TO` ([P] 318, 338, 873)

`Issue --TRACES_TO--> Component` cho mỗi Component có file chứa ít nhất một anchor, bỏ các anchor mà toàn bộ bằng chứng là mơ hồ (`ambiguous_matches`) **(đề xuất)**. Tra Component theo `properties.files`.

`confidence`: điểm lớn nhất của các anchor đó. `properties.anchor_count`. `provenance.evidence`: tối đa 5 id anchor tăng dần, mỗi phần tử dạng `{"kind": "anchor", "node_id": ...}`. Graph không có Component thì không sinh cạnh.

### 5.7 Chỉ khai báo trong schema

Requirement, UserStory, Constraint, Actor, cùng `DEPENDS_ON` và `CONFLICTS_WITH` giữa Requirement, không có luật sinh **(TV2 chốt)**. [P] chỉ định nghĩa kiểu ở 304–311, 320–321, và [P] 619 nói MVP không cần NLP phức tạp. GT-1 vì vậy còn thiếu phần này cho tới khi nhóm định nghĩa.

## 6. Thay đổi schema

Trong `schema.py`, ghi chú "proposed, pending team review" như các loại trước:

- `NODE_TYPES` thêm 9 loại: BugReport, Requirement, UserStory, AcceptanceCriterion, FailingTest, ErrorMessage, StackTraceFrame, Constraint, Actor.
- `MENTIONS`: thêm đích StackTraceFrame, ErrorMessage, AcceptanceCriterion, BugReport **(TV2 chốt, đề xuất riêng cho BugReport)**, Route ([P] 336).
- `TRACES_TO`: (Issue, Component), (Requirement, Component).
- `REPRODUCES`: thêm (FailingTest, BugReport).
- `DEPENDS_ON`: thêm (Requirement, Requirement). `CONFLICTS_WITH`: (Requirement, Requirement).
- `TESTS`: thêm đích Requirement ([P] 319).
- `SCHEMA_VERSION` thành `vgar-schema-full-v3`.

## 7. Thay đổi khác

`retrieval.py:170-171`: chỉ lấy `REPRODUCES` có đích là node Issue (`overlay.nodes[0]["id"]`), để FailingTest không bị coi là node Test.

## 8. Test và tiêu chí nghiệm thu

Test tầng 1, không cần LLM. File mới `tests/test_task_graph.py`, đáp án viết tay.

**Hàm thuần `extract_task_facts`:**

- Traceback có frame `<module>`, frame `<stdin>`, dấu nháy đơn, frame không có `, in`, nhiều traceback.
- Dòng lỗi có module (`requests.exceptions.ConnectionError: x`), gộp trùng và `occurrences`.
- Không phải dòng lỗi: `except ValueError:`, `ValueError:` không có message, `Warning: x`, `raise ValueError("x")`.
- Tiêu chí: tiêu đề dạng `##`, `**...**`, có dấu `:`; checkbox; danh sách đánh số; dừng đúng chỗ; gạch đầu dòng ngoài mục đó không tính; tiêu đề trong khối ` ``` ` không tính.
- BugReport: từng dấu hiệu riêng lẻ; **issue chỉ chứa từ "bug" không sinh BugReport**.
- Văn bản rỗng và văn bản lạ (rất dài, ký tự không in được): không lỗi.

**Overlay trên `tests/fixtures/vgar-arch-cases/multi_package`:**

- Issue có traceback tới `app/service.py`: đúng frame, ErrorMessage, BugReport, `TRACES_TO` tới `app`, đúng `confidence`, `anchor_count`. Đây cũng là kiểm thử "issue có traceback" của [test] dòng 23.
- `failing_tests` có selector khớp và không khớp: `FailingTest`, `test_node_ids`, `REPRODUCES` đúng.
- `overlay.nodes[0]` là Issue. Kết quả qua validate.
- Anchor mơ hồ không tạo `TRACES_TO`.
- Label: `bug` sinh BugReport, label khác không sinh; `properties.labels` đã chuẩn hóa.
- Route: chạy với CLI tree-sitter-graph thật trên `web_app`, tự skip nếu thiếu.
- Retrieval: có `failing_tests` thì danh sách test dùng cho `failing_test_proximity` không chứa id FailingTest.

**Tiêu chí:**

1. Tất cả test trên xanh.
2. Test tầng 1 Layer 1–3 vẫn xanh: 13 file ở spec GA §8 mục 6, `tests/test_arch_lift.py` và `tests/test_task_overlay.py`. Test cũ chỉ được sửa khi ghim cứng số node, cạnh của overlay; mỗi lần sửa phải ghi vào báo cáo.
3. **Chạy toàn bộ test suite** (bỏ marker `hf`, `docker`) và báo từng test fail so với mốc có 3 test đã biết. Test của plan cũ không phải tiêu chí, nhưng fail mới phải được điều tra, vì GA đã có một lỗi thật chỉ lộ ra ở bước này.
4. **Chạy thật:** `extract_task_facts` trên 50 issue, chỉ dùng `problem_statement`: 72 frame ở 5 issue, ErrorMessage và BugReport ở 10 issue. Dựng overlay cho `pydata__xarray-4629` trên checkout có sẵn: qua validate, ghi `TRACES_TO` vào báo cáo. **Không chỉnh luật theo số của lần chạy này.**

Báo cáo ghi vào `docs/status/`, kèm lệnh tái tạo.

## 9. Phần để người triển khai tự quyết

- Cấu trúc dataclass của kết quả `extract_task_facts`.
- Chia hàm trong `task_graph.py` và thứ tự node sau Issue, miễn xác định.

## 10. Câu hỏi mở cần nhóm trả lời

| # | Điểm | Ảnh hưởng |
|---|---|---|
| 1 | Requirement, UserStory, Constraint, Actor trích từ đâu | GT-1 chưa đủ cho tới khi có câu trả lời |
| 2 | Schema mới vẫn "pending team review" | Hợp đồng "Sáng ngày 1" của plan |
