# Agent tự dựng và cập nhật graph qua MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code/OpenCode gọi `build_or_update_graph` để dựng graph lần đầu rồi cập nhật tăng dần sau mỗi lần sửa; tool đọc thấy graph mới ngay; gắn server bằng file cấu hình `mcpServers` như hướng dẫn build-server.

**Architecture:** Module mới `vgar.graph.live_build.LiveGraphBuilder` giữ một `IncrementalGraphBuilder` theo tiến trình, có khóa và giới hạn thời gian, ghi vào SQLite của server. `graph_server.build_or_update_graph` đi đường kiểu hướng dẫn khi host không có provider `build` (mẫu `_has_provider`), chạy ngoài event loop. Factory cho server khởi động khi DB chưa có nếu `VGAR_REPOSITORY_ROOT` hợp lệ; tool đọc trả `GRAPH_NOT_READY` có gợi ý.

**Tech Stack:** Python 3.11, MCP SDK 2.2.0 (`MCPServer`), SQLite, `IncrementalGraphBuilder` (TV2 L6-6/U1).

**Spec:** `docs/superpowers/specs/2026-11-12-agent-builds-graph-design.md` (duyệt 12/11/2026).

## Global Constraints

- Theo hướng dẫn build-server `2026-07-28`: `@mcp.tool()` + docstring `Args:`; việc lâu chạy ngoài event loop (`anyio.to_thread`); không ghi stdout; `logging.getLogger(__name__)` ra stderr; gắn host bằng `mcpServers` (`command`, `args`, `env`, đường dẫn tuyệt đối); xác nhận do host làm, không thêm annotations hay grant mới.
- Chỉ dựng đúng `VGAR_REPOSITORY_ROOT` (path jail §10.5); `repo_path` khác hoặc là link → `PATH_OUTSIDE_ROOT`.
- Graph giống `vgar index`: `repo_key = tên thư mục`, `repository_revision = "cli"`, `source_roots` mặc định.
- Đường provider/grant của TV1 giữ nguyên khi `core_tools.registry.get("build")` có giá trị.
- Không dữ liệu giả. Lỗi graph chưa dựng dùng mã có sẵn `GRAPH_NOT_READY`, thông điệp gợi ý `build_or_update_graph`.
- Không commit (người dùng tự commit). Không sửa `src` khi suite đang chạy. Suite nền: 5 fail / 3.106 pass (4 `sdk1-legacy` + 1 HEAD).

## Review Focus

1. Hai lời gọi `build_or_update_graph` cùng lúc → lời gọi sau chờ khóa, không dựng song song, không hỏng DB. Test: Task 2 `test_concurrent_runs_are_serialized`.
2. `repo_path` tương đối, có dấu `/` cuối, hoa thường khác nhau trên Windows → vẫn được nhận nếu resolve ra đúng root; symlink/junction → từ chối. Test: Task 3 `test_repo_path_must_resolve_to_the_configured_root`.
3. Repo không có file Python nào hoặc file lỗi cú pháp → `ERROR` có thông điệp, server sống. Test: Task 2 `test_syntax_error_file_does_not_kill_the_server`.
4. DB bị xóa giữa phiên → lời gọi build kế tiếp dựng cold lại, tool đọc không trả graph cũ. Test: Task 2 `test_deleted_database_triggers_a_cold_rebuild`.
5. Dựng quá giới hạn thời gian → `ERROR` mã `TIMEOUT`, khóa được nhả. Test: Task 2 `test_timeout_releases_the_lock`.

---

### Task 1: Server khởi động khi chưa có graph

**Files:** Modify `src/vgar/graph/factory.py`, `src/vgar/graph/sqlite_store.py` (thông điệp `GraphNotReadyError` khi chưa có bản ready); Test `tests/test_tv2_live_build.py`.

**Interfaces:** Produces: `create_graph_service()` trả service SQLite khi `VGAR_GRAPH_DATABASE` chưa tồn tại nhưng `VGAR_REPOSITORY_ROOT` là thư mục (tạo thư mục cha của DB); vẫn `RuntimeError` khi cả hai đều thiếu.

- [ ] **Step 1: Test lỗi**
```python
def test_server_starts_without_a_database_when_the_repo_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "g" / "graph.db"))
    monkeypatch.setenv("VGAR_REPOSITORY_ROOT", str(FIXTURE_REPO))
    service = create_graph_service()
    with pytest.raises(GraphNotReadyError, match="build_or_update_graph"):
        service.get_repository_summary()

def test_missing_database_without_repo_root_still_fails(tmp_path, monkeypatch):
    # VGAR_REPOSITORY_ROOT unset → RuntimeError("Graph database not found")
```
- [ ] **Step 2:** FAIL. **Step 3:** sửa factory và thông điệp. **Step 4:** PASS; `tests/test_tv2_real_backend.py` cập nhật đúng một test nếu nó khẳng định quy tắc cũ (ghi ruling).

### Task 2: `LiveGraphBuilder`

**Files:** Create `src/vgar/graph/live_build.py`; Test `tests/test_tv2_live_build.py`.

**Interfaces:** Produces `LiveGraphBuilder(repository_root: Path, database: Path, *, timeout_seconds: float = 900)` với `run() -> dict` trả `{graph_version, previous_graph_version, mode: "cold"|"incremental", changed_files: list[str], nodes: int, edges: int, duration_ms: int, unchanged: bool}`; dùng `IncrementalGraphBuilder(repo_key=root.name, repository_revision="cli")`; `threading.Lock` theo instance; ingest vào `SQLiteGraphStore(database)`.

- [ ] **Step 1: Test lỗi** (`FIXTURE_REPO` chép sang `tmp_path`):
  - `test_cold_build_matches_vgar_index` — `run()` lần đầu `mode == "cold"`, `graph_version` bằng `index_repo` trên cùng repo.
  - `test_edit_gives_incremental_update_equal_to_a_rebuild` — sửa một file, `run()` → `mode == "incremental"`, `changed_files == [<file>]`, version bằng `index_repo` dựng lại.
  - `test_second_run_without_changes_is_unchanged` — `unchanged is True`, version giữ nguyên.
  - `test_concurrent_runs_are_serialized`, `test_syntax_error_file_does_not_kill_the_server`, `test_deleted_database_triggers_a_cold_rebuild`, `test_timeout_releases_the_lock` (Review Focus 1, 3, 4, 5).
- [ ] **Step 2:** FAIL `ModuleNotFoundError`. **Step 3:** cài đặt; logger module, docstring `Args:`. **Step 4:** PASS.

### Task 3: Tool `build_or_update_graph` kiểu hướng dẫn

**Files:** Modify `src/vgar/mcp/servers/graph_server.py`; Test `tests/mcp_server/test_tv2_build_tool.py`.

**Interfaces:** Consumes `LiveGraphBuilder` (Task 2). Produces: khi `not _has_provider("build")`, tool kiểm `repo_path` (resolve, không link) bằng `VGAR_REPOSITORY_ROOT`, chạy `LiveGraphBuilder.run` trong `anyio.to_thread.run_sync`, trả envelope qua `_tool` với audit `{"repo_path_sha256", "mode", "graph_version"}`; một `LiveGraphBuilder` theo tiến trình (lazy); timeout từ `VGAR_GRAPH_BUILD_TIMEOUT_SECONDS`. Docstring nêu rõ tool ghi graph.

- [ ] **Step 1: Test lỗi**
  - `test_build_then_read_without_restart` — server có DB rỗng: `get_callers` trả `GRAPH_NOT_READY`; `build_or_update_graph(root)` PASS `mode="cold"`; `search_symbols` trả symbol thật.
  - `test_edit_then_rebuild_is_incremental_and_visible` — sửa file thêm hàm mới, build lại → `incremental`, `search_symbols` thấy hàm mới.
  - `test_repo_path_must_resolve_to_the_configured_root` — đường khác → `PATH_OUTSIDE_ROOT`; tương đối/khác hoa thường cùng root → PASS.
  - `test_registered_build_provider_keeps_the_tv1_path` — registry có provider `build` → gọi `core_tools.respond_async` như cũ.
- [ ] **Step 2:** FAIL. **Step 3:** cài đặt. **Step 4:** PASS; `pytest -q tests/mcp_server` không lỗi mới.

### Task 4: File cấu hình mẫu theo hướng dẫn và tài liệu

**Files:** Create `configs/mcp_server/claude-desktop.example.json`, `configs/mcp_server/mcp.example.json`, `configs/mcp_server/opencode.example.jsonc`; Modify `README.md` (mục gắn host + quy trình agent dựng graph), `docs/mcp_server/debugging.md`; Test `tests/test_tv2_live_build.py::test_host_examples_declare_three_servers_with_absolute_paths`.

- [ ] **Step 1: Test lỗi** — mỗi file mẫu parse được (jsonc bỏ comment), có đúng `vgar-graph`, `vgar-execution`, `vgar-repository`; `command` là đường dẫn tuyệt đối dạng placeholder `<ABSOLUTE ...>`; `env` có `VGAR_GRAPH_BACKEND`, `VGAR_GRAPH_DATABASE`, `VGAR_REPOSITORY_ROOT` cho graph và execution.
- [ ] **Step 2:** FAIL. **Step 3:** viết file và tài liệu (chép file, sửa đường dẫn, thoát hẳn host rồi mở lại; quy trình: query → agent gọi build → đồng ý → sửa → build lại). **Step 4:** PASS.

### Task 5: Kiểm thật và báo cáo

- [ ] **Step 1:** Stdio SDK2 trên bản sao `vgar-demo-shop`: khởi động không DB → `search_symbols` `GRAPH_NOT_READY` → `build_or_update_graph` cold → query → sửa file → build lại incremental → query thấy thay đổi; Inspector `tools/list`.
- [ ] **Step 2:** Suite đầy đủ (hỏi người dùng nếu máy thiếu RAM) → không lỗi mới.
- [ ] **Step 3:** Báo cáo `docs/status/tv2_agent_builds_graph_run_2026-11-12.md` (kết quả, rulings, ghi chú cho TV1 về L6-6).
