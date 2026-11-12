# TV2 · Agent tự dựng và cập nhật graph qua MCP: báo cáo chạy (12/11/2026)

Spec: `docs/superpowers/specs/2026-11-12-agent-builds-graph-design.md`. Plan: `docs/superpowers/plans/2026-11-12-agent-builds-graph.md`. Ledger: `.superpowers/sdd/2026-11-12-agent-builds-graph/progress.md`. Nền: commit `90a79029`. Chưa commit (người dùng tự commit).

## Kết quả

Gắn VGAR vào Claude Code / OpenCode giờ đi đúng quy trình proposal §10–§11, theo khung của hướng dẫn build-server `2026-07-28`:

1. Khai báo 3 server trong file cấu hình của host (`mcpServers`, đường dẫn tuyệt đối, `env`), từ file mẫu `configs/mcp_server/{claude-desktop.example.json, mcp.example.json, opencode.example.jsonc}`; DB có thể chưa tồn tại.
2. Mở host trong repo, đặt câu hỏi. Tool đọc trả `GRAPH_NOT_READY` kèm gợi ý cho tới khi có graph.
3. Agent gọi `build_or_update_graph`; host hỏi người dùng (xác nhận §10.5). Lần đầu: dựng cold.
4. Agent đọc graph, sửa code, gọi lại `build_or_update_graph`: **cập nhật tăng dần** (chỉ file đổi, `IncrementalGraphBuilder`), tool đọc thấy graph mới ngay ở lời gọi kế tiếp, không cần kết nối lại.
5. Agent kiểm patch bằng `verify_patch_graph_constraints`, `run_relevant_tests`, `rank_patch_candidates`.

## Kiểm thật (MCP SDK 2.2.0, stdio)

| Bước | `2026-07-28` |
|---|---|
| Server khởi động không có DB | OK, 11 tool |
| `search_symbols` trước khi dựng | `ERROR GRAPH_NOT_READY` ("call the build_or_update_graph tool or run `vgar index`") |
| `build_or_update_graph` lần 1 | `PASS`, `mode=cold`, 137 node |
| Tìm `discount_amount` | thấy |
| Sửa `shop/discounts.py` (thêm `loyalty_bonus`), dựng lại | `PASS`, `mode=incremental`, `changed_files=["shop/discounts.py"]` |
| Tìm `loyalty_bonus` | thấy, không kết nối lại |
| `repo_path` là repo khác | `ERROR PATH_OUTSIDE_ROOT` |
| MCP Inspector `tools/list` trên server chưa có DB | 11 tool; mô tả `build_or_update_graph` ghi rõ tool ghi graph |

Graph dựng cold và graph sau cập nhật tăng dần đều có `graph_version` bằng `vgar index` dựng lại trên cùng repo (test).

## Thay đổi

| File | Thay đổi |
|---|---|
| `src/vgar/graph/live_build.py` (mới) | `LiveGraphBuilder`: một `IncrementalGraphBuilder` theo tiến trình; mỗi lúc một job dựng chạy trên luồng riêng; lời gọi quá `VGAR_GRAPH_BUILD_TIMEOUT_SECONDS` (mặc định 900) nhận `TIMEOUT`, job chạy tiếp và lời gọi sau dùng lại kết quả; dựng cold khi chưa có graph hoặc DB bị xóa; ghi snapshot rồi xóa các snapshot cũ của repo |
| `src/vgar/graph/sqlite_store.py` | `prune_other_versions(keep, repo_key)`: DB chỉ giữ snapshot hiện tại của repo, nên hoàn tác một sửa đổi trả đúng code đã hoàn tác và DB không phình theo số lần sửa |
| `src/vgar/mcp/servers/graph_server.py` | `build_or_update_graph` kiểu hướng dẫn (docstring `Args:`, chạy ngoài event loop, path jail, audit) khi host không có đường tin cậy của TV1; dòng log khởi động không làm sập server khi chưa có graph |
| `src/vgar/graph/factory.py` | Server khởi động khi DB chưa có nếu `VGAR_REPOSITORY_ROOT` là thư mục; thiếu cả hai vẫn dừng như trước |
| `src/vgar/contracts/error.py` | `GRAPH_NOT_READY` khi chưa có bản nào kèm gợi ý gọi `build_or_update_graph` |
| `configs/mcp_server/*.example.json(c)` (mới) | Cấu hình mẫu cho Claude Desktop, Claude Code (`.mcp.json`), OpenCode |
| `README.md`, `docs/mcp_server/debugging.md` | Cách gắn theo hướng dẫn, quy trình làm việc, dựng trước cho đánh giá/repo lớn, dòng lỗi `GRAPH_NOT_READY` |
| Test | `tests/test_tv2_live_build.py`, `tests/mcp_server/test_tv2_build_tool.py`, thêm 1 test stdio trong `test_tv2_server_logging.py`; chỉnh 3 test cũ (ledger) |

## Ranh giới với TV1 (L6-6)

Đường mới chỉ chạy khi host **không** có đường tin cậy: không provider `build`, không `graph_jobs`, không `context_factory`, không context đã ký. Host của TV1 giữ nguyên grant và `GraphJobController` (test của TV1 vẫn qua). Plan L6-6 nói "Incremental update theo thuật toán §11.2 cho `build_or_update_graph`, có cache": đường mới dùng đúng `IncrementalGraphBuilder` (U1: khớp dựng lại 12/12); bước nối cạnh vẫn O(N) như U1 đã ghi.

## Giới hạn

- Dựng cold repo lớn có thể vượt giới hạn thời gian gọi tool của host. Dựng trước bằng `vgar index` chỉ giúp tool đọc trả lời sớm; lần gọi `build_or_update_graph` đầu tiên của tiến trình server vẫn là dựng đầy đủ (cache tăng dần nằm trong RAM). Khi một lời gọi trả `TIMEOUT`, job vẫn chạy và lời gọi kế tiếp chờ, dùng lại kết quả, không dựng lại từ đầu.
- Cache tăng dần nằm trong RAM của tiến trình graph server; khởi động lại server thì lời gọi đầu dựng cold (ra cùng version nếu code không đổi).
- Execution server không tự cập nhật graph; nó đọc bản `ready` mới nhất do graph server ghi.
