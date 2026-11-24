# Đợt 5: thu nhỏ output của tool VGAR cho agent (TV2, 24/11/2026)

Trạng thái: **bản nháp 1, chờ TV2 duyệt**. Các quyết định ở §6.1 đã chốt với TV2 ngày 24/11. Nguồn số liệu:
`docs/status/tv2_opencode_ab_shopflow_2026-11-22.md` (lượt lặp 3), `docs/status/tv2_get_related_context_budget_2026-11-23.md`,
log phiên A-en big-pickle `ses_df7276b7` (`D:\kltn\vgar-work\opencode-logs\`). Chỉ sửa tầng MCP; không đổi retrieval,
contract `ContextPayload`, R1 hay handoff.

## 1. Vì sao

Ở cặp big-pickle, nhánh có VGAR (A) sửa lỗi bằng nhánh không VGAR (B) (18/105 test ẩn fail, cùng danh sách) nhưng tốn gấp
2,0 lần thời gian và 2,4 lần token. Server chỉ chạy 19 giây; phần chênh nằm ở phía mô hình, mà nguyên nhân rõ nhất là output
tool quá lớn: OpenCode cắt output ở 50 KB, agent đọc lại file và output bị cắt, ngữ cảnh đầy và bị nén 3 lần (0,40 triệu token).

| Hiện tượng (phiên A big-pickle) | Nguyên nhân trong code |
|---|---|
| `get_related_context`: 12 lần thành công, response 6,7–91,4 KB (trung bình 60,6 KB), 8 lần vượt 50 KB và bị cắt, dù phần code chỉ 261–4810 token | Mỗi mục context mang `graph_rationale` lặp id đầy đủ của node (156 KB trên 453 mục, ngang phần code 154 KB), `symbol`/`path`/`range` có cột trùng thông tin trong `node_id`, `confidence`, `token_count`; response còn kèm `source_metadata` (hash từng node, trung bình 8,9 KB) (`sqlite_service.py:215-222`, `graph_server.py:253-271`) |
| Budget chưa bao giờ là giới hạn: agent tự xin 7.000–10.000 (lần đầu 12.000), `truncated = false` ở cả 12 lần, không mục nào bị bỏ vì budget | Budget chỉ đếm byte UTF-8 / 4 của đoạn code (`retrieval.py:382-391`); metadata và lớp vỏ JSON không bị giới hạn |
| `verify_patch_graph_constraints`: trung bình 48 KB mỗi lần | 29 KB là 114 dòng `IMPORT_NOT_INTERNALLY_RESOLVED` (import thư viện chuẩn, lặp lại y hệt mỗi lần) trong `checks.structural.details.diagnostics`; 8 KB là `checks.api.details.analysis_scope` |
| Thụt lề JSON: output dài thêm 14–31% ở mọi tool | SDK MCP 2.2.0 chuyển dict thành text bằng `to_json(..., indent=2)` (`.venv/Lib/site-packages/mcp/server/mcpserver/utilities/func_metadata.py:653`) |
| Lớp vỏ ngoài ghi `"status": "PASS"` ngay trên `data.status: "NOT_RUN"`; nemotron báo PASS ở 2/3 lượt A dù kết luận là NOT_RUN hoặc ERROR | `run_tool` luôn trả PASS khi tool chạy xong (`tooling.py:113`); hợp đồng hiện quy định PASS nghĩa "tool trả lời được" (`docs/mcp_server/contract.md:28`) |

Mô phỏng thiết kế ở §4 trên 12 output thật: `get_related_context` từ 60,6 KB còn 26,0 KB trung bình, lớn nhất từ 91,4 còn 32,1 KB;
`verify` từ 48 KB còn khoảng 1 KB (script: `C:\Users\nlhnh\.claude\jobs\8cbd1456\tmp\simulate_final.py`, chỉ đọc log).

## 2. Mục tiêu

- Mỗi response của `get_related_context` không quá 32 KiB, kể cả trên repo lớn.
- `verify_patch_graph_constraints` mặc định trả bản tóm tắt (khoảng 1 KB); bản đầy đủ chỉ khi được yêu cầu.
- Với tool có kết luận (`verify_patch_graph_constraints`, `run_relevant_tests`), `status` ngoài cùng là kết luận
  (PASS/FAIL/NOT_RUN); không còn PASS ngoài cùng khi kết luận không phải PASS.
- Text gửi cho host là JSON gọn (không thụt lề) cho mọi tool của cả ba server.
- Không mất thông tin agent cần: hàm lỗi vẫn có trong context, agent vẫn có `node_id` để gọi tool khác và `path` + dòng để đọc file.

Không làm:
- Không đổi retrieval (xếp hạng, đóng gói, đếm token byte/4), `ContextPayload`, R1, handoff; các phần này gọi service trực
  tiếp và giữ nguyên output.
- Không phân trang hay cơ chế "xin tiếp phần bị cắt".
- Không nén mất thông tin (tóm tắt đoạn code bằng LLM, cắt giữa đoạn code).

Tránh (làm hỏng mục tiêu dù chạy được):
- Bỏ mất hàm lỗi khỏi context do giới hạn kích thước.
- Tuyên bố "rẻ hơn" chỉ dựa vào số token; chi phí phải đo bằng $/task solved (§5.4).

## 3. Các hướng đã cân nhắc

| Hướng | Đánh đổi | Kết luận |
|---|---|---|
| Chỉ hạ budget mặc định | Gần như không giảm gì: budget không phải giới hạn trong phiên A, và agent luôn tự truyền budget | Bỏ; giữ hạ mặc định như lớp bảo vệ phụ |
| **Làm gọn output ở tầng MCP + mặc định 4.000 / trần 12.000 + giới hạn 32 KiB** | Đổi hình dạng output cho agent (cần cập nhật test và tài liệu); service và R1 không đổi | **Chọn** |
| Đổi `ContextPayload` hoặc retrieval | Ảnh hưởng R1, handoff, so sánh với số liệu cũ | Bỏ |
| Phân trang / phục hồi phần bị cắt | Thêm cơ chế; tài liệu (chưa xác minh) cho thấy model hiếm khi dùng | Bỏ |
| Nén mất thông tin (tóm tắt snippet) | Có thể làm agent đọc lại hoặc sửa sai | Bỏ |

## 4. Thiết kế

### 4.1 JSON gọn cho mọi tool

- Text content mà host nhận là JSON không thụt lề (`separators=(",", ":")`, giữ ký tự Unicode).
- `structuredContent` giữ nguyên như hiện nay (cùng dict).
- Gọi trực tiếp hàm tool trong Python vẫn trả dict như cũ (các test hiện có gọi trực tiếp hàm tool).
- Làm ở một chỗ: `src/vgar/mcp/server_factory.py`, áp dụng cho `create_server` và `create_resource_server` (graph,
  execution, repository). Cách đề xuất: khi đăng ký tool, bọc hàm để kết quả gửi qua MCP là `CallToolResult` với text gọn
  và `structured_content` là dict; hàm gốc của module không đổi. Cách làm cụ thể để builder chọn, miễn giữ ba điều trên.
- Resource không đổi (đã trả chuỗi thô).

### 4.2 `get_related_context`

**Budget.** `DEFAULT_CONTEXT_BUDGET = 4000`, `MAX_CONTEXT_BUDGET = 12000` (`graph_server.py:223-224`). Cách đếm không đổi
(byte UTF-8 của đoạn code / 4). Chú thích hằng số ghi: mặc định lệch so với `budget_tokens=12000` trong proposal §9.2, lý do
là giới hạn output của host và số đo phiên A; trần 12000 vẫn theo §10.5. Docstring của tool nói rõ: budget là mức tối đa cho
phần code của một lần gọi; phần không dùng không tốn gì; budget cao chỉ trả thêm code khi có; response còn bị giới hạn 32 KiB.

**Hình dạng mục context** (chỉ trong response MCP):

| Trường | Giá trị | Thay cho |
|---|---|---|
| `node_id` | giữ nguyên | |
| `path` | giữ nguyên | |
| `lines` | `[start_line, end_line]` | `range` (bỏ cột) |
| `score` | `relevance_score` làm tròn 3 chữ số | `relevance_score` |
| `distance` | `graph_distance` | |
| `why` | mỗi dòng của `graph_rationale`: dòng nguồn (`TASK_ANCHOR`, `SOURCE_COMPONENT`, `TRACE_COMPONENT`) giữ nguyên; dòng cạnh `RELATION:<node_id>-><node_id>` thành `RELATION <qualified_name> -> <qualified_name>` | `graph_rationale` |
| `snippet` | giữ nguyên | |

Bỏ khỏi mục: `symbol` (là phần cuối của `node_id`), `confidence`, `token_count`. Thứ tự mục giữ theo thứ hạng.

**Phần còn lại của response.** Bỏ `source_metadata` (vẫn có trong output của service cho handoff). Đổi
`context_format` thành `vgar.context.agent.v1` để phân biệt với `vgar.context.v1` của service. Các trường nhỏ khác
(`graph_version`, `task_id`, `overlay_id`, `repository_revision`, `counter_label`, `context.anchor_ids`,
`context.total_token_count`, `context.token_budget`, `context.truncated`, `diagnostics`) giữ nguyên.

**Giới hạn 32 KiB.** Đo trên JSON gọn của `data`. Nếu vượt 32.768 byte: bỏ dần các mục từ cuối danh sách (điểm thấp nhất) cho
đến khi vừa; luôn giữ ít nhất mục đầu tiên (nếu riêng mục đó đã vượt thì response vượt giới hạn, ghi `over_limit: true`).
Khi có cắt:
- `context.total_token_count` tính lại bằng tổng token của các mục còn lại;
- `context.truncated = true`;
- `diagnostics.response_limit = {"limit_bytes": 32768, "dropped_items": n}` và một câu gợi ý: response giữ dưới 32 KiB
  nên đã bỏ n mục điểm thấp nhất; gọi lại với ít anchor hơn hoặc đọc file nếu cần.

Khi budget làm `truncated = true` (repo lớn), `diagnostics` cũng có câu gợi ý: có thể gọi lại với `budget_tokens` tối đa 12000.

Audit thêm `response_bytes` và `dropped_items` (khi có cắt) vào dòng của lần gọi.

**Kết quả mô phỏng trên 12 output thật** (vẫn với budget agent đã xin):

| Lần | Hiện tại | Sau khi làm gọn | Mục bị bỏ do 32 KiB |
|---|---|---|---|
| 1 (kiến trúc) | 65,2 KB | 31,8 KB | 4/36 |
| 3–8 (rà lỗi) | 6,7–83,6 KB | 3,3–32,0 KB | 8/54 ở một lần, các lần khác 0 |
| 9 (lỗi 3) | 43,3 KB | 19,4 KB | 0/28 |
| 10 (lỗi 1) | 83,3 KB | 31,7 KB | 10/54 |
| 11 (lỗi 2) | 91,4 KB | 32,1 KB | 12/60 |
| 12 (lỗi 4) | 79,4 KB | 32,0 KB | 5/50 |
| 13 (lỗi 5) | 55,9 KB | 27,1 KB | 0/34 |

Không hàm lỗi nào bị bỏ: `coupon_rate` vị trí 2/54 và `OrderService.place_order` 31/54 (lỗi 1, giữ 44 mục đầu),
`quote_order` 2/60, `Notifier.order_shipped` 3/50 và `InventoryService.commit` 5/50, `Order.can_transition` 4/34.
Rủi ro: ở lỗi 3, `Order.__init__` đứng 26/28; lần này không bị cắt, nhưng hàm lỗi ở cuối danh sách là điểm yếu của xếp hạng
(xem ghi chú retrieval review 22/11), không phải của giới hạn.

### 4.3 `verify_patch_graph_constraints`: bản tóm tắt mặc định

Tham số mới `details: bool = False`. Chỉ đổi nhánh không có provider (`graph_server.py:606-619`); nhánh provider
(`core_tools.respond`) giữ nguyên.

Bản tóm tắt (`details = false`):

| Trường | Nội dung |
|---|---|
| `status`, `reasons`, `graph_version`, `diff_sha256` | như hiện nay |
| `summary` | một câu: PASS → các kiểm tra đã chạy và file đã kiểm; NOT_RUN/FAIL → check nào, lý do nào, và symbol nào (nếu có). Ví dụ: "Change NOT verified: api NOT_RUN (API_UNSUPPORTED_DECLARATION: ALLOWED_TRANSITIONS in shopflow/models/order.py)" |
| `checks` | `{tên: {status, reasons}}`, không có `details` |
| `unsupported_changes` | symbol vừa sửa mà kiểm tra API không xử lý được, kèm lý do (giao của `analysis_scope.selected` với `excluded_diagnostics`) |
| `diagnostic_counts` | số chẩn đoán theo lý do, ví dụ `{"IMPORT_NOT_INTERNALLY_RESOLVED": 114}` |
| `checked_diff` | `source`, `files`, `sha256`, `not_checked` (bỏ `diff`; agent có diff qua `git diff`) |

`details = true`: output đầy đủ như hiện nay, cộng `summary`.

### 4.4 `status` ngoài cùng là kết luận

- `run_tool` / `run_tool_async` (`tooling.py:74-166`) nhận thêm một hàm tùy chọn lấy kết luận từ `data`.
- Tool có hàm này (`verify_patch_graph_constraints`, `run_relevant_tests` ở `execution_server.py:98-127`): `status` =
  `data.status` khi là PASS, FAIL hoặc NOT_RUN. Khi `data.status` là ERROR: `status` = ERROR, giữ `data` và điền `error`.
- Tool ném lỗi: `status` = ERROR như hiện nay.
- Mọi tool khác giữ PASS = "tool trả lời được".
- Ràng buộc: không bao giờ có `status` ngoài cùng là PASS khi `data.status` khác PASS.
- Dòng audit ghi `status` bằng `status` ngoài cùng.
- Cập nhật `docs/mcp_server/contract.md:28`: tool có kết luận đặt kết luận ở `status` ngoài cùng; các tool khác giữ PASS/ERROR.

### 4.5 Tương thích

- R1, handoff, evaluation gọi service trực tiếp, không qua tool MCP: không đổi (`graph/handoff.py:60-80` kiểm
  `vgar.context.v1` trên output của service; `repair/context_adapter.py:26-50` đọc bundle handoff).
- `build_or_update_graph` (`checks_before_update`) gọi hàm kiểm tra nội bộ, không qua tool: không đổi.
- **Output MCP không còn là `ContextPayload` v1 hợp lệ** (thiếu `symbol`, `range` có cột, `confidence`, `token_count`).
  Không có code chạy thật nào validate output tool MCP bằng `ContextPayload`; chỉ test M1 tuần 7–8
  `tests/test_w7_w8_m1.py:64-71` khẳng định điều này (kiểm `context_format == "vgar.context.v1"`, validate `ContextPayload`,
  đọc `source_metadata`, gọi `render_context_for_repair`). Test này sửa theo định dạng mới; phần `render_context_for_repair`
  chuyển sang kiểm trên output của service. Nếu giữ đủ trường v1 (chỉ bỏ `source_metadata` và thụt lề), mô phỏng trên 12
  output thật cho trung bình 41,4 KB, lớn nhất 61,2 KB, và giới hạn 32 KiB phải cắt ở 9/12 lần (135/453 mục, so với 5/12 lần
  và 39 mục ở thiết kế này), dễ mất hàm lỗi.
- Test sẽ phải sửa (builder tìm đủ bằng grep):
  - `tests/mcp_server/test_tv2_context_budget.py`: mặc định 12000 thành 4000; schema `default == 4000`;
  - `tests/test_w7_w8_m1.py:64-71` (như trên);
  - test chờ `status` ngoài cùng PASS khi `verify` hoặc `run_relevant_tests` có kết luận khác PASS (ví dụ
    `tests/test_patch_checks_from_snapshot.py`, `tests/test_agent_loop_fixes.py`, `tests/test_tv2_patch_evidence.py`).
  - `tests/test_w5_w6_mcp.py:47-52` chỉ đọc `items` và `total_token_count`, hai trường này vẫn giữ.
- Host: OpenCode và Claude Code đọc text content; `structuredContent` không đổi.

### 4.6 Tài liệu

- Docstring `get_related_context` (budget, hình dạng mục, giới hạn 32 KiB), `verify_patch_graph_constraints` (`details`,
  `status` ngoài cùng), `run_relevant_tests` (`status` ngoài cùng).
- `README.md:245`, `docs/mcp_server/tools.md:13`: mặc định 4000, trần 12000, giới hạn 32 KiB, lệch §9.2.
- `docs/mcp_server/contract.md:28` (và các dòng 62, 67 nếu cần).

### 4.7 Ngoài phạm vi (ghi nhận)

- `find_task_anchors`: `trace_edges` chiếm 59% của trung bình 12 KB.
- Kích thước output của `explain_dependency_path`, `analyze_patch_impact` (chỉ hưởng phần JSON gọn).
- Nhóm context theo file, giới hạn số file hay mục điểm thấp (hướng precision).
- Đo sai số của đếm byte/4 so với tokenizer thật.
- Nén lịch sử phía host.
- Xếp hạng retrieval (hàm lỗi ở cuối danh sách).

## 5. Kiểm chứng

### 5.1 Test mới (TDD, viết trước khi sửa)

1. JSON gọn: gọi tool qua client SDK trên mỗi server; text không có xuống dòng thụt lề và parse lại bằng
   `structuredContent`; gọi trực tiếp hàm Python vẫn trả dict.
2. `get_related_context`:
   - không truyền budget → `diagnostics.budget.requested == 4000`, tổng token ≤ 4000; schema `default == 4000`;
   - truyền 12000 → được 12000; truyền 50000 → cắt về 12000 (test cũ giữ nguyên);
   - mục có đúng các trường `node_id, path, lines, score, distance, why, snippet`; `why` dạng `RELATION a -> b`;
   - không có `source_metadata`; `context_format == "vgar.context.agent.v1"`;
   - repo lớn (fixture `big_server` hiện có, 20 hàm khoảng 4000 byte), budget 12000 → JSON gọn của `data` ≤ 32.768 byte,
     `truncated == true`, `diagnostics.response_limit.dropped_items > 0`, `total_token_count` = tổng token các mục còn lại,
     thứ tự mục giữ nguyên;
   - một mục lớn hơn 32 KiB → vẫn trả mục đó, `over_limit == true`;
   - audit có `response_bytes`.
3. `verify_patch_graph_constraints`:
   - mặc định: có `summary`, `checks` chỉ có `status`/`reasons`, có `diagnostic_counts`, `checked_diff` không có `diff`;
   - sửa hằng số cấp module (như `ALLOWED_TRANSITIONS`) → `status` ngoài cùng NOT_RUN, `unsupported_changes` nêu symbol đó;
   - không có thay đổi → `status` ngoài cùng NOT_RUN;
   - vi phạm cấu trúc → FAIL; mọi kiểm tra qua → PASS;
   - `details=true` → có `checks.*.details` như cũ.
4. `run_relevant_tests` không có test liên quan → `status` ngoài cùng NOT_RUN.
5. Một tool không có kết luận (ví dụ `search_symbols`) vẫn PASS.

### 5.2 Chạy lại trên ShopFlow (sau khi cài)

Script dựng graph của ShopFlow ở commit gốc (`ee54b36`) trong thư mục tạm, gọi lại 12 lần `get_related_context` với đúng
anchor, budget, `issue_text` của phiên A, và gọi `verify` trên diff sửa hằng số của lỗi 5. Đạt khi:
- mọi response ≤ 32 KiB;
- hàm lỗi của từng lỗi vẫn có mặt (bảng §4.2);
- `verify` lỗi 5 trả `status` ngoài cùng NOT_RUN và nêu `ALLOWED_TRANSITIONS`.

### 5.3 Bộ test đầy đủ

Toàn bộ suite pass (3592 test hiện tại, trừ các lỗi Docker/harness đã biết), cộng test mới.

### 5.4 Đo chi phí (không thuộc nghiệm thu đợt này)

Lượt OpenCode tiếp theo (TV2 tự chạy) báo cáo: $/task solved theo một bảng giá giả định có tách input, ghi cache, đọc
cache, output; ít nhất 3 lần chạy mỗi cấu hình; thêm biến thể A dùng prompt giống B (không bắt gọi kiểm tra).

## 6. Quyết định

### 6.1 Đã chốt với TV2 (24/11)

- Mặc định 4.000, trần 12.000 (lệch §9.2, ghi rõ trong code và tài liệu).
- Ưu tiên chính là làm gọn output; hạ mặc định là lớp bảo vệ phụ.
- Giới hạn 32 KiB cho response `get_related_context`, bỏ mục điểm thấp nhất khi vượt, ghi trong `diagnostics`.
- `verify` trả bản tóm tắt, `details=true` cho bản đầy đủ.
- NOT_RUN (và FAIL) ra `status` ngoài cùng.

### 6.2 Mình tự chọn (sửa được khi duyệt)

- Output MCP của `get_related_context` không còn là `ContextPayload` v1 (§4.5); service vẫn trả v1.
- Tên trường mới: `lines`, `score`, `distance`, `why`; bỏ `symbol`, `confidence`, `token_count`.
- `context_format` mới `vgar.context.agent.v1`.
- Đo giới hạn trên JSON gọn của `data` (lớp vỏ thêm khoảng 0,2 KB); luôn giữ ít nhất một mục.
- Bản tóm tắt `verify` bỏ `checked_diff.diff`.
- Áp quy tắc `status` ngoài cùng cho cả `run_relevant_tests` (cùng loại tool có kết luận).
- JSON gọn làm ở `server_factory.py` cho cả ba server.
- Audit ghi thêm `response_bytes`, `dropped_items`.

## 7. Cơ sở tài liệu

Nguồn do TV2 tìm ngày 24/11. "Đã biết" là bài mình biết có thật; "chưa xác minh" cần đối chiếu bài gốc trước khi trích trong
luận văn.

| Nhận định | Nguồn | Trạng thái | Dùng cho |
|---|---|---|---|
| Graph tool tốn token vì độ dài kết quả truy vấn không kiểm soát được | CodexGraph | đã biết | Giới hạn 32 KiB ở server |
| Thông tin ở giữa context dài bị bỏ sót | Liu và cộng sự, "Lost in the Middle"; NoLiMa (Modarressi 2025) | đã biết | Giữ thứ tự xếp hạng, không nâng mặc định |
| Định vị mức file: LocAgent 92,7%, giảm khoảng 86% chi phí; Agentless 32,00% với $0,70/instance | LocAgent; Agentless | đã biết | Benchmark repo lớn đo định vị và chi phí |
| Cải thiện định vị theo concern (+22% Hit@k) | RepoLens (Ying 2025) | TV2 đã xác minh | Nửa "định vị bug nhiều file" |
| Context chọn lọc dùng ít hơn 50–87% token mà vẫn định vị tốt | CodeNib (Yu 2026) | chưa xác minh | Làm gọn output |
| Explorer rẻ hơn giữ 78–94% Hit@3, ít hơn 84–95% token | Awad 2026 | chưa xác minh | Làm gọn output |
| Định vị mức file chi phối; mở rộng mức dòng thường gây nhiễu | Sepidband 2026 | chưa xác minh | §4.7 (nhóm theo file) |
| 81–100% ca thất bại vẫn qua validation agent tự chạy | Lin 2026 | chưa xác minh | `status` ngoài cùng |
| Budget 4k–32k, RepoMap tốt nhất ở 8K, không phương pháp nào thắng mọi mức | Qin 2026 | chưa xác minh | Mặc định 4.000 nằm trong vùng đã đo |
| Phục hồi nội dung bị lược ít được model dùng | Fan 2026 | chưa xác minh | Không phân trang |
| Index cấu trúc $2,30 so với $2,92 của OpenCode trên $/solved | Bhola 2026 | chưa xác minh | §5.4 |
| "Nén output tool tăng 6,8% chi phí; cache chiếm 80–87% hóa đơn" | "Weinberger 2026" | **đã loại**: không tồn tại bài như vậy | Không dùng |
