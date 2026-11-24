# Đợt 5: chạy lại phiên A (big-pickle) trên ShopFlow sau khi làm gọn output (24/11/2026)

Spec: `docs/superpowers/specs/2026-11-24-tv2-smaller-tool-output-design.md` §5.2. Script:
`scripts/mcp_server/replay_shopflow_session.py`. Log phiên: `D:\kltn\vgar-work\opencode-logs\ses_df7276b72ffetYKJMAPODVXxnI.json`.

**Nguồn code:** không còn repo ShopFlow ở `ee54b36` trên máy; đã dùng `D:\kltn\shopflow-clean1.zip` (giải nén vào thư mục
tạm). Graph version dựng lại (`sha256:6062d5e3…`) khác bản trong log (`sha256:d075c60b…`). Version băm cả
`repository_revision`, mà bản zip không có git, nên khác version thì chưa chứng minh được code khác. Số mục và số mục bị bỏ
gần bằng bảng mô phỏng của spec §4.2. Coi kết quả là chỉ báo; chạy lại với repo ở `ee54b36` nếu cần số chính xác.

Mỗi lần gọi dùng đúng anchor, budget, `issue_text` của phiên A, theo thứ tự, trên graph của code gốc.

| # | status | data bytes | text bytes | items | dropped | hàm lỗi thiếu |
|---|---|---|---|---|---|---|
| 1 | PASS | 32616 | 32797 | 32 | 4 | - |
| 2 | ERROR | 2 | 304 | 0 | 0 | - |
| 3 | PASS | 32758 | 32939 | 46 | 8 | - |
| 4 | PASS | 32327 | 32508 | 39 | 0 | - |
| 5 | PASS | 26937 | 27118 | 38 | 0 | - |
| 6 | PASS | 22574 | 22755 | 26 | 0 | - |
| 7 | PASS | 22288 | 22469 | 30 | 0 | - |
| 8 | PASS | 3120 | 3301 | 4 | 0 | - |
| 9 | PASS | 19698 | 19879 | 28 | 0 | - |
| 10 | PASS | 32475 | 32656 | 44 | 10 | - |
| 11 | PASS | 32359 | 32540 | 47 | 13 | - |
| 12 | PASS | 32414 | 32595 | 44 | 6 | - |
| 13 | PASS | 27499 | 27680 | 34 | 0 | - |

Lần 2 là ERROR giống trong phiên (anchor là Component, không có code nguồn).

`verify_patch_graph_constraints` trên diff lỗi 5: `status` NOT_RUN; summary "Change NOT verified: api NOT_RUN
(API_UNSUPPORTED_DECLARATION: ALLOWED_TRANSITIONS in shopflow/models/order.py)".

**Kết luận: đạt** cả ba tiêu chí của §5.2: mọi response PASS ≤ 32.768 byte (text gửi host ≤ 32.939 byte); không hàm lỗi
nào bị bỏ (lần 9–13); verify lỗi 5 trả NOT_RUN và nêu `ALLOWED_TRANSITIONS`. So với phiên A: trung bình 60,6 KB, lớn nhất
91,4 KB, 8/12 lần vượt 50 KB.
