# Debug và logging của server MCP VGAR

Theo hướng dẫn MCP `2026-07-28` (trang [build-server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server) và [debugging](https://modelcontextprotocol.io/docs/2026-07-28/tools/debugging)):

- Server stdio **không bao giờ ghi stdout**: stdout là kênh JSON-RPC, một dòng `print()` là hỏng phiên.
- Log dùng `logging` của thư viện chuẩn, một logger mỗi module (`logging.getLogger(__name__)`), ghi ra **stderr**. Host tự thu stderr của server stdio.
- Logging qua giao thức (`notifications/message`) đã **deprecated** ở `2026-07-28`, VGAR không dùng.

## Bật log

Đặt `VGAR_MCP_LOG_LEVEL` trong phần `env` của cấu hình host (server stdio chỉ nhận một phần biến môi trường của máy, nên phải khai rõ):

| Giá trị | Ghi gì |
|---|---|
| `WARNING` (mặc định) | Chỉ cảnh báo và lỗi; không có dòng theo từng lời gọi (giữ trace spec P8 của TV1) |
| `INFO` | Thêm dòng khởi động (tên server, phiên bản `mcp`, backend, DB, `graph_version`, repo root) và một dòng cho mỗi lời gọi tool: `tool=<tên> server=<server> status=<PASS|ERROR> duration_ms=<n> request_id=<id>` |
| `DEBUG` | Thêm dòng bắt đầu mỗi lời gọi kèm `args=` là các trường audit (hash, kích thước, tên); **không bao giờ có nội dung diff hay giá trị bí mật** |

Lỗi khởi động (ví dụ `Graph database not found`) luôn được ghi ở mức `ERROR` trước khi tiến trình thoát. Giá trị lạ của `VGAR_MCP_LOG_LEVEL` rơi về `WARNING` kèm một dòng cảnh báo.

Ví dụ Claude Code (PowerShell, một dòng):

```powershell
claude --% mcp add vgar-graph -s local -e VGAR_MCP_LOG_LEVEL=INFO -e VGAR_GRAPH_BACKEND=sqlite -e VGAR_GRAPH_DATABASE=D:/kltn/graphs/<repo>.db -e VGAR_REPOSITORY_ROOT=<repo> -e PYTHONUTF8=1 -- D:/kltn/vgar_mcp_mvp_demo/.venv/Scripts/python.exe -m vgar.mcp.servers.graph_server
```

## Xem log ở đâu

| Host | Nơi xem |
|---|---|
| Claude Code | `%LOCALAPPDATA%\claude-cli-nodejs\Cache\<project>\mcp-logs-<server>\*.jsonl` (stderr của server nằm trong các dòng `"error":"Server stderr: ..."`); trong phiên gõ `/mcp` để xem trạng thái và kết nối lại |
| Claude Desktop | `%APPDATA%\Claude\logs\mcp*.log` (theo hướng dẫn); đổi cấu hình thì thoát hẳn rồi mở lại, đóng cửa sổ là chưa đủ |
| OpenCode | `opencode mcp list` cho trạng thái kết nối; `/mcps` trong phiên để kết nối hoặc ngắt |

**Audit log** (`VGAR_MCP_AUDIT_LOG`, mặc định `logs/mcp_audit.jsonl`) ghi mọi lời gọi tool và mọi lần đọc resource: tên tool, trạng thái, thời gian, `request_id`, hash đầu vào. Đây là nguồn số liệu cho nhóm chỉ số MCP usability (§13.2: số lần gọi tool mỗi task, độ trễ tool), độc lập với host.

## MCP Inspector

Hướng dẫn coi Inspector là chỗ debug đầu tiên. Inspector chỉ truyền một phần biến môi trường cho server, nên mọi biến phải đưa qua `-e` (đã chạy thử 12/11/2026 với MCP SDK 2.2.0: cả `modern` và `legacy` liệt kê đủ 11 tool):

```powershell
npx -y @modelcontextprotocol/inspector --cli `
  -e VGAR_GRAPH_BACKEND=sqlite -e VGAR_GRAPH_DATABASE=D:/kltn/graphs/<repo>.db -e VGAR_REPOSITORY_ROOT=<repo> `
  D:/kltn/vgar_mcp_mvp_demo/.venv/Scripts/python.exe -m vgar.mcp.servers.graph_server `
  --protocol-era modern --method tools/list
```

`--protocol-era modern` là giao thức `2026-07-28` (cần server MCP SDK 2.x); `legacy` là `2025-11-25`. Nếu python của server không cài gói `vgar` (venv chỉ có dependency), thêm `-e PYTHONPATH=D:/kltn/vgar_mcp_mvp_demo/src`; thiếu thì Inspector báo `Connection closed during the version negotiation probe` và stderr có `No module named 'vgar'`.

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| `GRAPH_NOT_READY` … `call the build_or_update_graph tool` | Chưa dựng graph cho repo: để agent gọi `build_or_update_graph` (host hỏi bạn xác nhận), hoặc chạy `vgar index` |
| `Graph database not found` | Không khai `VGAR_REPOSITORY_ROOT` nên server không thể tự dựng graph: `python -m vgar.cli index <repo> --db <file>.db`, rồi đặt `VGAR_GRAPH_DATABASE` là **đường dẫn tuyệt đối** |
| `Backend 'demo' was removed` | `.env` cũ còn `VGAR_GRAPH_BACKEND=demo`; đổi sang `sqlite` |
| Server không thấy biến môi trường | Server stdio chỉ nhận một phần biến của máy; khai đủ trong `env` của cấu hình host |
| `-32022 UnsupportedProtocolVersionError` | Host và server không chung bản giao thức; lỗi liệt kê các bản server hỗ trợ (SDK 1.x: `2025-11-25`; SDK 2.x thêm `2026-07-28`) |
| `PATCH_DOES_NOT_APPLY` | Diff lệch số dòng hoặc nội dung với snapshot; lấy diff bằng `git diff`, không tự viết số dòng; graph cũ thì chạy lại `vgar index` |
| Claude Code báo `Connection closed` sau khi bấm dừng một lời gọi | Xem báo cáo chạy `docs/status/tv2_remove_langchain_sdk2_run_2026-11-12.md`; gõ `/mcp` và kết nối lại server |
