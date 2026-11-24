# `get_related_context`: agent xin budget và server cấp như thế nào (phiên A-en big-pickle, 23/11/2026)

Tài liệu này lưu lại phần xin/nhận token context của agent trong phiên A-en big-pickle (`ses_df7276b7`, 21:39–22:02,
commit kết quả `c04d180`) và mô tả cơ chế theo code ở commit `b23b9364`.

## Tệp lưu trữ

| Tệp | Nội dung |
|---|---|
| [tv2_get_related_context_budget_2026-11-23.csv](tv2_get_related_context_budget_2026-11-23.csv) | 13 lần gọi: budget agent gửi, budget server cấp, token và số mục nhận được, kích thước response, host có cắt không; ghép theo `request_id` |
| [tv2_get_related_context_budget_audit_2026-11-23.jsonl](tv2_get_related_context_budget_audit_2026-11-23.jsonl) | 13 dòng audit gốc của server cho `get_related_context`; đã bỏ danh sách `candidates` (top 20) và `config` cho gọn, giữ số đếm và lý do bỏ mục |
| `D:\kltn\vgar-work\opencode-logs\ses_df7276b7_graph_audit.jsonl` (ngoài repo) | Bản sao đầy đủ audit log của server cho cả phiên (116 dòng = 116 lần gọi VGAR); bản gốc `D:\kltn\vgar-work\data\shopflow-clean\graph.jsonl` sẽ bị khối reset xóa |
| `D:\kltn\vgar-work\opencode-logs\ses_df7276b72ffetYKJMAPODVXxnI.json` (ngoài repo) | Phiên OpenCode dựng lại từ `opencode.db`: tham số agent gửi và output agent nhận |

Kiểm chứng khi ghép: với cả 13 lần gọi, `budget_tokens` trong audit bằng giá trị agent gửi, và `total_token_count`
trong audit bằng giá trị trong output agent nhận.

## Cơ chế xin và nhận

1. **Agent xin.** `budget_tokens` là tham số không bắt buộc của tool (số nguyên, kiểu strict: `true` hay `"8000"` bị
   từ chối). Schema tool công bố mặc định 12000, trần 12000 (`src/vgar/mcp/servers/graph_server.py:223-249`). Không
   tham số thì server dùng mặc định. Kịch bản A không nói gì về budget: các con số trong phiên này do mô hình tự chọn.
2. **Server cấp.** `effective = min(budget_tokens, 12000)` (`graph_server.py:250`). Giá trị ≤ 0 bị từ chối
   (`src/vgar/graph/retrieval.py:199-200`). Xin quá 12000 thì bị cắt về 12000 và đánh dấu `clamped`.
3. **Đóng gói** (`retrieval.py:355-418`):
   - ứng viên là vùng lân cận k=2 quanh anchor, giới hạn bởi `max_candidates` (biến host `VGAR_RETRIEVAL_MAX_CANDIDATES`);
     nếu giới hạn này cắt vùng lân cận thì `traversal_limited = true`;
   - đi theo thứ hạng; mỗi mục tốn số token = byte UTF-8 của **riêng đoạn code** / 4;
   - mục nằm lồng trong đoạn đã chọn bị bỏ (`overlapping_selected_range`);
   - mục làm tổng vượt budget bị bỏ (`token_budget`), các mục nhỏ hơn phía sau vẫn được thử; khi đó `truncated = true`.
4. **Agent nhận** (`graph_server.py:257-271`): `context.items`, `context.total_token_count`, `context.token_budget`,
   `context.truncated`, và `diagnostics.budget = {requested, effective, ceiling, clamped}`, `diagnostics.traversal_limited`.
   Danh sách ứng viên và lý do bỏ mục không trả cho agent.
5. **Server ghi audit** (`graph_server.py:272-277`, `src/vgar/mcp/tooling.py:74-151`): mỗi lần gọi một dòng JSON ở tệp
   `VGAR_MCP_AUDIT_LOG`, gồm `timestamp`, `request_id`, `status`, `duration_ms`, `graph_version`, `task_id`,
   `budget_tokens` (xin), `effective_budget_tokens` (cấp), `item_count`, `total_token_count` và `diagnostics`
   (số ứng viên, số mục bị bỏ, 20 ứng viên đầu, lý do bỏ mục).

Lưu ý: budget chỉ đếm đoạn code. Metadata của từng mục, `source_metadata` và phần thụt lề JSON không được đếm, nên kích
thước response có thể lớn hơn nhiều so với `budget × 4` byte.

## 13 lần gọi trong phiên

| # | Bước | Agent xin | Server cấp | Token code nhận | Số mục | Ứng viên / bị bỏ (lồng nhau) | `truncated` | Response | Host cắt |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 12000 | 12000 | 4810 | 36 | 86 / 50 | false | 65,2 KB | có |
| 2 | 1 | 8000 | 8000 | – (ERROR `INVALID_QUERY`) | – | – | – | 0,4 KB | không |
| 3 | 2 | 7000 | 7000 | 3708 | 54 | 80 / 26 | false | 83,6 KB | có |
| 4 | 2 | 7000 | 7000 | 4001 | 39 | 66 / 27 | false | 65,3 KB | có |
| 5 | 2 | 7000 | 7000 | 2612 | 38 | 56 / 18 | false | 59,9 KB | có |
| 6 | 2 | 7000 | 7000 | 2553 | 26 | 37 / 11 | false | 45,2 KB | không |
| 7 | 2 | 7000 | 7000 | 2204 | 30 | 44 / 14 | false | 47,9 KB | không |
| 8 | 2 | 7000 | 7000 | 261 | 4 | 8 / 4 | false | 6,7 KB | không |
| 9 | lỗi 3 | 8000 | 8000 | 2015 | 28 | 42 / 14 | false | 43,3 KB | không |
| 10 | lỗi 1 | 10000 | 10000 | 4266 | 54 | 89 / 35 | false | 83,3 KB | có |
| 11 | lỗi 2 | 9000 | 9000 | 4303 | 60 | 97 / 37 | false | 91,4 KB | có |
| 12 | lỗi 4 | 10000 | 10000 | 4067 | 50 | 71 / 21 | false | 79,4 KB | có |
| 13 | lỗi 5 | 10000 | 10000 | 3222 | 34 | 55 / 21 | false | 55,9 KB | có |

Cột "Ứng viên / bị bỏ" lấy từ `diagnostics` trong audit; mọi mục bị bỏ đều có lý do `overlapping_selected_range`.
Kích thước response tính theo KB = 1.024 byte (cột `response_bytes` trong CSV). Giờ của từng dòng và `request_id` có trong CSV.

## Nhận xét

- Agent tự chọn budget 7000–10000 ở 12/13 lần (chỉ lần đầu là 12000), không lần nào dùng mặc định.
- Budget chưa bao giờ là giới hạn: `truncated = false` ở cả 12 lần thành công, `traversal_limited = false`, không mục nào
  bị bỏ vì `token_budget`. Token nhận được (261–4810) là toàn bộ vùng lân cận k=2 sau khi bỏ các mục lồng nhau.
- Response lớn gấp nhiều lần phần code: ví dụ lần 11, 4303 token code (khoảng 17 KB) nhưng response 91,4 KB. 8/12 lần
  thành công vượt ngưỡng cắt 50 KB của OpenCode.
- Hệ quả cho đợt sửa output: hạ mặc định xuống 4.000 không thay đổi phiên này, vì agent luôn tự xin budget. Thay đổi có
  tác dụng là làm gọn định dạng response. Mặc định 4.000 chỉ có tác dụng với agent không truyền budget và trên repo lớn,
  nơi vùng lân cận vượt budget.
