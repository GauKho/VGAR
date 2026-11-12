# Agent tự dựng và cập nhật graph qua MCP (proposal §10–§11, plan L6-5/L6-6, hướng dẫn build-server 2026-07-28)

Ngày: 12/11/2026 · Người đề xuất: TV2 · Phạm vi: chỉ proposal và plan 2 tuần.

## 1. Mục đích

Gắn server VGAR vào Claude Code hoặc OpenCode đúng quy trình proposal: mở repo → agent gọi `build_or_update_graph` (người dùng xác nhận) → dùng tool đọc → sửa code → agent gọi lại `build_or_update_graph` để **cập nhật tăng dần** → kiểm patch. Hiện tool này trả `Host-bound context required` (cần grant của host TV1), nên người dùng phải chạy `vgar index` bằng tay và kết nối lại server sau mỗi lần sửa.

Căn cứ:
- Proposal §10.3: `build_or_update_graph(repo_path)` là core tool đầu tiên.
- Proposal §10.5: "read-only graph tools mặc định; write operations tách riêng và cần confirmation"; "path jail: chỉ truy cập repo được allowlist"; "timeout và resource limit"; "audit log mọi tool call".
- Proposal §11: cập nhật tăng dần `O(Δ + Fanout(Δ))`, không rebuild toàn repo sau mỗi lần sửa.
- Plan L6-5 (bảo mật), L6-6 (incremental cho `build_or_update_graph`, có cache), L6-8 (nối Claude Code).
- Hướng dẫn build-server `2026-07-28` (khung thực hiện bắt buộc): tool là hàm `@mcp.tool()` có docstring `Args:`; việc lâu không chặn event loop; không ghi stdout, log `logging.getLogger(__name__)` ra stderr; chạy `mcp.run(transport="stdio")`; gắn vào host bằng mục `mcpServers` (`command`, `args`, `env`, đường dẫn tuyệt đối) trong file cấu hình của host; host hỏi người dùng trước khi gọi tool ("with user approval").

## 2. Mục tiêu

1. **Đường kiểu hướng dẫn cho `build_or_update_graph`** khi host không đăng ký provider `build` (Claude Code, OpenCode): tool dựng hoặc cập nhật graph của **đúng repo đã cấu hình** (`VGAR_REPOSITORY_ROOT`) và ghi vào `VGAR_GRAPH_DATABASE`. Khi host TV1 có provider `build` và grant, giữ nguyên đường cũ (như mẫu `_has_provider` của đợt nối layer).
2. **Cập nhật tăng dần:** một `IncrementalGraphBuilder` sống theo tiến trình server. Lần gọi đầu: `build` (cold). Các lần sau: `update` (chỉ file đổi, U1 đã chứng minh khớp dựng lại). Graph giống hệt `vgar index` cho cùng repo: `repo_key = tên thư mục`, `repository_revision = "cli"`, `source_roots` mặc định.
3. **Tool đọc thấy graph mới ngay**, không cần kết nối lại: store SQLite đọc bản `ready` mới nhất mỗi lời gọi; `SQLiteGraphService` đã cache theo `graph_version`.
4. **Server khởi động được khi chưa có graph** (repo mới): nếu `VGAR_GRAPH_DATABASE` chưa tồn tại nhưng `VGAR_REPOSITORY_ROOT` hợp lệ, server vẫn chạy; tool đọc trả lỗi rõ ràng `GRAPH_NOT_BUILT` kèm hướng dẫn "gọi build_or_update_graph"; `vgar://repo/summary` cũng vậy. Không có dữ liệu giả.
5. **Xác nhận thao tác ghi (§10.5) theo hướng dẫn:** host hỏi người dùng trước khi gọi tool; `build_or_update_graph` vẫn là tool riêng, tách khỏi tool đọc, và docstring ghi rõ nó ghi graph. Không thêm cơ chế xác nhận trong server (không annotations, không grant mới).
6. **Gắn vào host đúng cách của hướng dẫn:** file cấu hình mẫu dạng `mcpServers` cho từng host, đường dẫn tuyệt đối, khai đủ `env`: `configs/mcp_server/claude-desktop.example.json` (`%APPDATA%\Claude\claude_desktop_config.json`), `configs/mcp_server/mcp.example.json` (Claude Code, `.mcp.json` scope project), `configs/mcp_server/opencode.example.jsonc` (OpenCode). README và `debugging.md` chỉ cách chép, sửa đường dẫn, thoát hẳn host rồi mở lại. Không thêm lệnh CLI mới.

## 3. Không làm

- Không bỏ hay đổi đường grant/provider của TV1 (`GraphJobController`, `BoundContext`).
- Không tự dựng graph khi server khởi động (agent quyết định qua tool, người dùng xác nhận).
- Không theo dõi file thay đổi (file watcher); cập nhật chỉ khi agent gọi tool.
- Không đổi thuật toán tăng dần (`IncrementalGraphBuilder` giữ nguyên; bước nối cạnh vẫn O(N) như U1 đã ghi).

## 4. Hành vi của `build_or_update_graph` (đường kiểu hướng dẫn)

- Đầu vào `repo_path`: phải trỏ đúng `VGAR_REPOSITORY_ROOT` sau khi resolve (path jail); khác → `PATH_OUTSIDE_ROOT`. Đường link/reparse → từ chối.
- Chạy trong luồng riêng (`anyio.to_thread`), có khóa để hai lời gọi không dựng đồng thời; giới hạn thời gian cấu hình được (`VGAR_GRAPH_BUILD_TIMEOUT_SECONDS`, mặc định 900).
- Kết quả envelope `PASS`: `{graph_version, previous_graph_version, mode: "cold"|"incremental", changed_files, nodes, edges, duration_ms, unchanged: bool}`. Lỗi parse/ghi → `ERROR` có mã.
- Ghi audit như mọi tool (input hash, mode, version).
- Log `INFO` một dòng kết quả.

## 5. Kiểm

- Test: cold build từ DB rỗng → tool đọc trả symbol thật; sửa một file → gọi lại → `mode=incremental`, `changed_files=1`, graph bằng `vgar index` dựng lại; tool đọc thấy symbol mới mà không khởi động lại server; `repo_path` khác → `PATH_OUTSIDE_ROOT`; server khởi động không có DB → tool đọc `GRAPH_NOT_BUILT`; host có provider `build` → đi đường cũ; tool mới có docstring `Args:`, chạy ngoài event loop, không ghi stdout.
- Stdio thật bằng SDK2 trên `vgar-demo-shop`: khởi động không DB → build → query → sửa file → build lại (incremental) → query thấy thay đổi.
- File cấu hình mẫu là JSON hợp lệ, chỉ có 3 server, đường dẫn và `env` đủ; Claude Code (`claude mcp list`) và Inspector thấy server khi dùng cấu hình mẫu.
- Suite đầy đủ không lỗi mới.

## 6. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Đụng phần L6-6 của TV1 | Đường mới chỉ chạy khi không có provider `build`; đường TV1 giữ nguyên; báo TV1 trong báo cáo |
| Repo lớn: cold build lâu, vượt timeout của host | Timeout cấu hình được; OpenCode `timeout.execution`; README ghi hướng dẫn dựng trước bằng `vgar index` cho repo lớn |
| Hai server (graph, execution) cùng mở DB khi đang ghi | SQLite tự khóa; execution chỉ đọc bản `ready` |
| Bỏ quy tắc "thiếu DB thì dừng khi khởi động" của đợt nối layer | Chỉ nới khi `VGAR_REPOSITORY_ROOT` hợp lệ; lỗi rõ ràng thay vì dữ liệu giả |
