# Đợt 6: SCIP mặc định, LSP dự phòng — kết quả chạy (24/11/2026)

Spec: `docs/superpowers/specs/2026-11-24-tv2-scip-in-served-graph-design.md`. Plan:
`docs/superpowers/plans/2026-11-24-tv2-scip-in-served-graph.md`. Máy: Windows, node v24.15.0, scip-python 0.6.6, pyright
1.1.414 (cài bằng `scripts/install_scip_runtime.ps1`, `install_lsp_runtime.ps1`). Repo đo: ShopFlow `68c96af`
(`git archive` của `D:\kltn\shopflow-clean1\shopflow`). Script spike: `D:\kltn\vgar-work\spikes\`.

## Server khởi động như host thật (`python -m vgar.mcp.servers.graph_server`, không đặt biến SCIP/LSP)

Test `tests/mcp_server/test_tv2_resolver_default_stdio.py` (stdio, thư mục đang đứng = repo):

| Cấu hình host | `layers.scip` | `layers.lsp` | File lạ trong repo |
|---|---|---|---|
| mặc định | `ready` | `skipped` ("SCIP ready") | không; run SCIP ở `<db dir>/scip-runs/` |
| `VGAR_SCIP=off` | `off` | `ready` | không |

## ShopFlow qua server MCP (trong process)

| | Không layer (trước đợt 6) | SCIP mặc định | SCIP lỗi → LSP |
|---|---|---|---|
| `layers` | tất cả `off` | `scip: ready`, `lsp: skipped` | `scip: failed`, `lsp: ready` |
| `statistics.resolver.active` | `static` | `scip` | `lsp` |
| CALLS / MAY_CALL | 87 / 67 | 136 / 5 | 136 / 5 (cùng tập 136 cạnh với SCIP) |
| Dựng lần đầu | 0,4 s | 2,9 s | khoảng 4 s |
| Cập nhật sau một lần sửa | 0,13 s (từng phần) | 6,4 s (dựng đầy đủ + `checks_before_update` chạy `verify` trên ứng viên bằng SCIP) | – |
| `changed_files` sau khi sửa `pricing.py` | `["shopflow/services/pricing.py"]` | `["shopflow/services/pricing.py"]` | – |
| `analyze_patch_impact` (sửa thuế) | PASS, COMPLETE | PASS, COMPLETE | – |
| `verify_patch_graph_constraints` (sửa thuế) | PASS | **PASS** (trước đợt 6: ERROR) | – |
| `run_relevant_tests` | NOT_RUN (`NO_RELATED_TESTS`) | như bên trái | – |

## Replay 13 lần `get_related_context` của phiên A (`ses_df7276b7`) và `verify` lỗi 5

| # | Không layer: byte / bỏ mục | SCIP: byte / bỏ mục | LSP dự phòng: byte / bỏ mục |
|---|---|---|---|
| 1 | 32616 / 4 | 32290 / 2 | 32290 / 2 |
| 2 | ERROR (anchor là Component) | ERROR | ERROR |
| 3 | 32758 / 8 | 32640 / 5 | 32640 / 5 |
| 4 | 32327 / 0 | 30491 / 0 | 30491 / 0 |
| 5 | 26937 / 0 | 26288 / 0 | 26288 / 0 |
| 6 | 22574 / 0 | 21961 / 0 | 21961 / 0 |
| 7 | 22288 / 0 | 21661 / 0 | 21661 / 0 |
| 8 | 3120 / 0 | 3120 / 0 | 3120 / 0 |
| 9 | 19698 / 0 | 19674 / 0 | 19674 / 0 |
| 10 | 32475 / 10 | 32102 / 11 | 32102 / 11 |
| 11 | 32359 / 13 | 32333 / 12 | 32333 / 12 |
| 12 | 32414 / 6 | 32758 / 3 | 32758 / 3 |
| 13 | 27499 / 0 | 24158 / 0 | 24158 / 0 |

Cả ba: không hàm lỗi nào bị bỏ (lần 9–13); `verify` lỗi 5 trả `status` NOT_RUN, "api NOT_RUN (API_UNSUPPORTED_DECLARATION:
ALLOWED_TRANSITIONS in shopflow/models/order.py)". Thư mục đang đứng của script không có thư mục `artifacts` mới.

## Nhận xét

- Lớp 2 của proposal (§5.4: SCIP hoặc LSP) giờ chạy mặc định trong server MCP; resolver tự viết chỉ còn là tầng dự phòng cuối.
- Trên ShopFlow, SCIP và LSP cho cùng tập cạnh CALLS; tăng 87 → 136 so với resolver tĩnh, MAY_CALL đoán theo tên giảm 67 → 5.
- Giá phải trả: mỗi lần cập nhật dựng lại đầy đủ (ShopFlow 6,4 s gồm cả kiểm trước khi dựng; repo lớn hơn có thể lên tới phút,
  xem R1 với SCIP 18/11). Cần đo ở lượt OpenCode thật.

## Lượt OpenCode cho TV2 (spec §5.4)

- `opencode.json` không cần đổi: server tự bật SCIP khi có runtime. Kiểm trước: `node --version` chạy được; hai runtime đã cài
  (`artifacts/m1/w7-w8/scip-runtime`, `artifacts/m1/w5-w6/lsp-runtime`).
- Sau lượt chạy cần đo: `layers` ở mọi lần `build_or_update_graph`; thời gian mỗi lần dựng; trạng thái các lần `verify`; có
  file lạ trong repo không (`git status`); test ẩn; token. So với Lượt lặp 5 (cùng mô hình, không layer).
