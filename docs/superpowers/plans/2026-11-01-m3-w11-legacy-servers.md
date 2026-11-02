# M3 W11: vá legacy server (D7, D9, D19) và security S1–S5 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model không chọn được root nào, không chạy được selector tùy ý, và không ghi được file ngoài `repair_server`. `vgar run` không còn báo thành công khi chưa kiểm chứng. `vgar chat --task` sửa bug qua engine M2, và kết luận lấy từ verdict của engine.

**Architecture:**
- `repository_server` và `execution_server` đọc root từ biến môi trường `VGAR_LEASE_ROOT` do host đặt, và đọc danh sách selector được phép từ `VGAR_ALLOWED_SELECTORS`. Cả hai trả kết quả qua `run_tool` (envelope có sẵn) với các mã lỗi C4.
- Phần chạy pytest tách thành một runner fake theo interface C6, để M2 thay bằng runner thật sau.
- Phía CLI: `run` truyền lease của sandbox vào server. `chat` mở run sửa lỗi trước, rồi truyền worktree của run làm lease.

**Tech Stack:** Python 3.11, FastMCP (`mcp.server.fastmcp`), langchain-mcp-adapters, pytest.

**Spec:**
- `docs/superpowers/specs/2026-11-01-m3-w11-legacy-servers-design.md` (đã duyệt 01/11).
- `docs/superpowers/specs/2026-11-01-m3-w11-security-design.md` (đã duyệt 01/11, gộp vào plan này: Task 1, 3, 8, 9).
- Mã lỗi theo C4 trong `docs/m3_w11_decisions.md`.

## Global Constraints

- **Không sửa `src/vgar/mcp/servers/graph_server.py`**: trong W11 ngày 1–2 file này thuộc B02 của M1.
- Không đổi runner A0–A3, `policy_hash`, hay `repair_server`.
- Mã lỗi dùng đúng tên C4: `ROOT_NOT_LEASED`, `PATH_OUTSIDE_ROOT`, `SELECTOR_REJECTED`, `TIMEOUT`. Mọi mã đều có `retryable = False`.
- CI: `python -m pytest -m "not hf and not docker" -q --deselect tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory` phải xanh. Chạy xong thì `git checkout -- artifacts/sample_graph.db`.
- **Người dùng tự commit.** Mỗi task kết thúc bằng danh sách file.
  - PR1 `m3/w11-legacy-servers` gồm Task 1–4.
  - PR2 `m3/w11-run-chat` gồm Task 5–7.
  - PR3 `m3/w11-security` gồm Task 8–9.
  - Reviewer là M2.
- **Không sửa `src/` khi một run retrieval của plan ranking đang chạy**, vì mỗi worker nạp lại source. Kiểm `.superpowers/sdd/2026-11-01-m1-w11-graph-ranking/` trước mỗi task.

## Review Focus

1. **Symlink ra ngoài root.** Một symlink trong worktree trỏ ra ngoài thì `read_file` phải trả `PATH_OUTSIDE_ROOT`, không được đọc. Kiểm bằng `resolve()` rồi mới so với root → Task 2, test `test_read_file_rejects_symlink_escape`. Bỏ qua test trên Windows nếu không tạo được symlink.
2. **Selector "lách" danh sách.** Ví dụ `tests/test_auth.py::test_x --pdb`, hoặc `tests/../x.py`, hoặc selector nhiều dòng. Các trường hợp này phải bị từ chối mà không có tiến trình con nào được tạo → Task 3, `test_run_pytest_rejects_selector_tricks`.
3. **File không phải UTF-8.** `read_file` trên file nhị phân phải trả lỗi rõ ràng (`INVALID_ARGUMENT`), không được làm sập server → Task 2.
4. **Chat kết thúc khi agent chưa verify.** Host phải gọi `repair_verify_patch` và in verdict, không được in câu trả lời của model như thể đó là kết quả → Task 6.
5. **`vgar run` có selector nhưng pytest fail.** Exit code phải khác 0, và `verified=False` → Task 5.

---

### Task 1: Mã lỗi C4 dạng exception, và `untrusted` trong metadata

**Files:**
- Modify: `src/vgar/mcp/schemas.py`
- Modify: `src/vgar/mcp/tooling.py` (`run_tool` nhận thêm `untrusted: bool = False`)
- Test: `tests/test_mcp_tool_contract.py`

**Interfaces:**
- Produces:
  - Các hằng `ROOT_NOT_LEASED`, `PATH_OUTSIDE_ROOT`, `SELECTOR_REJECTED`, `TIMEOUT` trong `schemas.py`.
  - `class CodedToolError(Exception)`, khởi tạo bằng `__init__(self, code: str, message: str)`, có hai thuộc tính `.code` và `.message`.
- Produces: `error_from_exception(CodedToolError(c, m))` trả `ToolError(code=c, message=m)`. Nhánh này kiểm **trước** nhánh `ValueError`.
- Produces: `run_tool(..., untrusted=True)` ghi `metadata.untrusted = True`. Mặc định không có khóa này, nên envelope của graph giữ nguyên.
- Produces (security §4.2, §4.4), đặt trong `tooling.py`:
  - `leased_root(env_name: str) -> Path`: thiếu biến hoặc giá trị không phải thư mục thì raise `CodedToolError(ROOT_NOT_LEASED)`.
  - `inside(root: Path, candidate: Path) -> Path`: `resolve()` rồi kiểm, đường dẫn ra ngoài root thì raise `CodedToolError(PATH_OUTSIDE_ROOT)`.
  - Các hằng `READ_FILE_MAX_BYTES = 64 * 1024`, `PYTEST_TIMEOUT_SECONDS = 120`, `PYTEST_OUTPUT_CAP = 12_000`.

- [ ] **Step 1: Viết test**
  - `test_coded_tool_error_keeps_its_code`: `error_from_exception(CodedToolError(ROOT_NOT_LEASED, "no lease"))` có `.code == "ROOT_NOT_LEASED"` và `.message == "no lease"`.
  - `test_run_tool_marks_untrusted_text`: gọi `run_tool(server="t", tool="x", backend="b", audit=AuditLogger(tmp), call=lambda: {"v": 1}, untrusted=True)`, kiểm `["metadata"]["untrusted"] is True`.
  - `test_leased_root_and_inside` (S1, S2): thiếu biến → `ROOT_NOT_LEASED`; `inside(root, root / ".." / "x")` → `PATH_OUTSIDE_ROOT`; `inside(root, root / "a.py")` trả đường dẫn đã resolve.
- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_mcp_tool_contract.py -q -k "coded or untrusted"`. Kỳ vọng: FAIL, `ImportError: CodedToolError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy cả file test.** Kỳ vọng: PASS. 11 test cũ không đổi.

### Task 2: `repository_server`: `read_file(path)` theo lease, bỏ `apply_patch`

**Files:**
- Modify: `src/vgar/mcp/servers/repository_server.py` (viết lại, khoảng 50 dòng)
- Create: `tests/test_mcp_legacy_servers.py`

**Interfaces:**
- Consumes: `CodedToolError` và các mã lỗi (Task 1), `run_tool(..., untrusted=True)`.
- Produces: các tool MCP `health()` và `read_file(path: str)`. `read_file` trả envelope có `data = {"path", "content", "truncated", "size_bytes"}`.
- Dùng `READ_FILE_MAX_BYTES` import từ `tooling.py`, và `repository_server` re-export lại để test truy cập được.

**Cách làm:**
- Gọi `root = leased_root("VGAR_LEASE_ROOT")` **ở mỗi lần gọi**, rồi `target = inside(root, root / safe_relative_path(path))`.
- Đọc bytes, cắt ở `READ_FILE_MAX_BYTES`, rồi decode UTF-8 với `errors="strict"`. Lỗi decode raise `ValueError`, và `run_tool` sẽ trả `INVALID_ARGUMENT`.
- Audit field: `path`, `truncated`.

- [ ] **Step 1: Viết test** (gọi thẳng hàm tool trong module, monkeypatch `VGAR_LEASE_ROOT` và `_audit_logger`)
  - **S2** `test_read_file_without_lease_is_root_not_leased`: thiếu biến môi trường → `status == "ERROR"`, `error.code == "ROOT_NOT_LEASED"`.
  - **S2** `test_read_file_rejects_parent_escape`: `read_file("../outside.txt")` → `PATH_OUTSIDE_ROOT`.
  - `test_read_file_rejects_symlink_escape` (Review Focus 1): `pytest.skip` nếu `os.symlink` raise `OSError`.
  - **S16** `test_read_file_truncates_at_server_cap`: file 70 KiB → `truncated is True`, `len(content.encode()) == READ_FILE_MAX_BYTES`.
  - **S12** `test_read_file_marks_content_untrusted`: `metadata.untrusted is True`.
  - `test_read_file_binary_is_invalid_argument` (Review Focus 3).
  - **S14 (một phần)** `test_repository_server_has_no_write_tool`: `asyncio.run(repository_server.mcp.list_tools())` chỉ có `{"health", "read_file"}`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, vì chữ ký hàm cũ còn `repo_path` và `apply_patch` vẫn còn.
- [ ] **Step 3: Implement** theo phần "Cách làm".
- [ ] **Step 4: Chạy test.** Kỳ vọng: PASS. Chạy thêm `grep -rn "repository_apply_patch\|repo_path" src/vgar scripts` để tìm caller còn sót, rồi sửa hết. Riêng `scripts/smoke_mcp.py` để Task 7 sửa.

### Task 3: `execution_server.run_pytest(selector)` qua runner C6 (`run_bounded`), kèm S4, S5

**Files:**
- Create: `src/vgar/mcp/pytest_runner.py` (runner C6, bọc `vgar.repair.executor.run_bounded`; security §4.1)
- Modify: `src/vgar/mcp/servers/execution_server.py`
- Test: `tests/test_mcp_legacy_servers.py`

**Interfaces:**
- Produces: `run_selector(root: Path, selector: str, *, timeout_seconds: int, output_cap: int) -> dict`. Hàm trả `{"exit_code", "stdout", "stderr", "truncated"}`.
  - Hàm gọi `run_bounded((sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", selector), root, timeout_seconds, output_cap=output_cap, environment={"PYTHONPATH": <root/src> + os.pathsep + <root>, "PYTHONIOENCODING": "utf-8"})`.
  - `timed_out` → raise `CodedToolError(TIMEOUT)`.
  - `output_truncated` → `truncated: True`.
  - `status == "ERROR"` vì lý do khác → raise `CodedToolError(INTERNAL_ERROR)`.

  `run_bounded` đã dừng cả cây tiến trình (Job Object trên Windows, `killpg` trên POSIX) và chặn output trong lúc chạy, nên đáp ứng S4 và S5. M2 cam kết giữ nguyên chữ ký (C6).
- Produces: tool MCP `run_pytest(selector: str)`. Envelope có `data = {"selector", "verdict": "PASS" | "FAIL", "exit_code", "stdout", "stderr", "truncated"}`.
- Dùng `PYTEST_TIMEOUT_SECONDS` và `PYTEST_OUTPUT_CAP` import từ `tooling.py`, và `execution_server` re-export lại.

**Cách làm:**
- Danh sách selector được phép lấy từ `json.loads(os.environ.get("VGAR_ALLOWED_SELECTORS", "[]"))`.
- Một selector **được phép** khi thỏa cả ba điều kiện:
  1. không bắt đầu bằng `-`, và không có khoảng trắng, `\n`, `\r`, `..`;
  2. bằng đúng một mục trong danh sách, **hoặc** bắt đầu bằng `<mục>/` hay `<mục>::`;
  3. phần path (trước `::`) nằm trong lease root sau khi `resolve()`.

  Không thỏa thì raise `CodedToolError(SELECTOR_REJECTED, …)` **trước khi** gọi `run_selector`.
- Root lấy y như Task 2.

- [ ] **Step 1: Viết test**
  - **S3** `test_run_pytest_rejects_selector_outside_allow_list`: monkeypatch `pytest_runner.run_selector` bằng hàm đếm số lần gọi. Allow list là `["tests/test_auth.py::test_ok"]`, gọi `run_pytest("tests/test_other.py")` → `SELECTOR_REJECTED`, và số lần gọi là 0.
  - `test_run_pytest_rejects_selector_tricks` (Review Focus 2): thử `["-k x", "tests/test_auth.py::test_ok --pdb", "tests/../x.py", "tests/a.py\n-x"]`, tất cả đều bị từ chối, số lần gọi là 0.
  - `test_run_pytest_accepts_scope_prefix`: allow list là `["tests"]`, gọi `run_pytest("tests/test_auth.py::test_ok")` → fake được gọi 1 lần, với `timeout_seconds == PYTEST_TIMEOUT_SECONDS`.
  - `test_run_pytest_timeout_is_coded`: fake raise `CodedToolError(TIMEOUT, "…")` → `error.code == "TIMEOUT"`.
  - `test_run_pytest_runs_real_pytest_in_lease`: dùng runner thật trên một repo tmp có `tests/test_ok.py` → `verdict == "PASS"`.
  - **S14 (một phần)** `test_execution_server_tools`: `list_tools()` chỉ có `{"health", "run_pytest"}`, và input schema của `run_pytest` chỉ có `selector`.
  - Trong `tests/test_mcp_security.py`:
    - **S4** `test_timeout_kills_grandchild`: test trong lease tạo một tiến trình cháu (`subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])`), ghi PID ra file, rồi tự `sleep`. Monkeypatch `execution_server.PYTEST_TIMEOUT_SECONDS = 3` → `TIMEOUT`. Trong vòng 5 giây, PID đó không còn sống. Kiểm bằng `psutil.pid_exists` nếu import được; nếu không thì dùng `os.kill(pid, 0)` trên POSIX, hoặc `OpenProcess` qua `ctypes` trên Windows.
    - **S5** `test_output_is_capped_while_running`: test in liên tục khoảng 50 MB. Monkeypatch cap về 100 KB → `truncated is True`, `len(stdout) <= cap`, và chạy xong trong 20 giây.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, `ModuleNotFoundError: vgar.mcp.pytest_runner`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy file test và `tests/test_mcp_security.py -k "timeout or capped"`.** Kỳ vọng: PASS trên máy hiện tại. CI Linux sẽ chạy cùng test đó.

### Task 4: Danh sách tool S9/S14, và truyền lease từ host vào agent

**Files:**
- Modify: `src/vgar/agents/core.py` (`create_core_agent` và `load_mcp_tools` nhận `servers` và `extra_env`)
- Modify: `src/vgar/cli.py` (`build_agent` nhận `servers` và `extra_env`, rồi chuyển tiếp)
- Test: `tests/test_mcp_legacy_servers.py`

**Interfaces:**
- Produces:
  - `create_core_agent(settings=None, *, run_id=None, servers: tuple[str, ...] = SERVER_NAMES, extra_env: dict[str, str] | None = None)`
  - `load_mcp_tools(settings=None, *, run_id=None, servers=SERVER_NAMES, extra_env=None)`
  - `build_agent(settings, *, run_id=None, servers=SERVER_NAMES, extra_env=None)`

  Tất cả chuyển thẳng `servers` và `extra_env` cho `create_mcp_client`.

- [ ] **Step 1: Viết test**
  - **S9/S14** `test_no_tool_accepts_root_or_timeout_and_only_repair_writes`: với từng module trong `repository_server`, `execution_server` và `repair_server`, lấy `list_tools()` rồi kiểm:
    - không input schema nào có field `repo_path` hoặc `timeout_seconds`;
    - tên tool có chữ `patch` hoặc `write` chỉ được xuất hiện trong `repair_server`.
  - `test_load_mcp_tools_forwards_lease_env`: monkeypatch `vgar.agents.core.create_mcp_client` để ghi lại tham số và trả một client giả có `get_tools` trả `[object()]`. Gọi `load_mcp_tools(..., servers=("repository",), extra_env={"VGAR_LEASE_ROOT": "x"})` rồi kiểm tham số được chuyển đúng.
- [ ] **Step 2: Chạy test.** Kỳ vọng: test thứ hai FAIL, `TypeError: unexpected keyword 'servers'`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy file test và `tests/test_mcp_client.py`.** Kỳ vọng: PASS. Kết thúc PR1. Danh sách file: `schemas.py`, `tooling.py`, `repository_server.py`, `execution_server.py`, `pytest_runner.py`, `core.py`, `cli.py` (chỉ phần `build_agent`), và các test.

### Task 5: `vgar run`: truyền lease vào server, không selector thì `UNVERIFIED` (D9)

**Files:**
- Modify: `src/vgar/cli.py:207-289` (`cmd_run`)
- Create: `tests/test_cli_run_chat.py`

**Interfaces:**
- Consumes: `build_agent(..., servers=("graph", "repository", "execution"), extra_env=...)` (Task 4).
- Produces: `cmd_run` truyền `extra_env={"VGAR_LEASE_ROOT": str(lease.path), "VGAR_ALLOWED_SELECTORS": json.dumps([args.selector] if args.selector else [])}`.
  - Không có `--selector`: in `[verify] UNVERIFIED: no selector`, `emit("RUN_END", verified=False, …)`, trả **2**.
  - Có selector nhưng pytest độc lập fail: trả 1.

- [ ] **Step 1: Viết test.** Monkeypatch `vgar.cli.build_agent` trả một agent giả: `ainvoke` trả `{"messages": [AIMessage("done")]}`, đồng thời ghi lại `extra_env`. Repo tmp có `tests/test_ok.py`.
  - **D9** `test_run_without_selector_is_unverified`: `await cmd_run(Namespace(query="q", repo=tmp, selector=None, keep=False))` trả 2, stdout có chuỗi `UNVERIFIED`.
  - `test_run_passes_lease_and_allowed_selector`: `extra_env["VGAR_LEASE_ROOT"]` là đường dẫn lease, **không phải** repo gốc. `VGAR_ALLOWED_SELECTORS` là `[selector]`.
  - `test_run_with_failing_selector_returns_1` (Review Focus 5): selector trỏ tới test fail → trả 1.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, vì bản hiện tại trả 0 khi không có selector.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy file test.** Kỳ vọng: PASS.

### Task 6: `vgar chat --task`: lease là worktree, kết luận theo verdict (D19)

**Files:**
- Create: `src/vgar/agents/chat.py`
- Modify: `src/vgar/cli.py` (`cmd_chat`; parser của `chat`: bỏ `--repo`, thêm `--task`, `--config`, `--mode` mặc định `real`)
- Test: `tests/test_cli_run_chat.py`

**Interfaces:**
- Consumes: `Runtime`, `_call` (`vgar.agents.nodes.mcp_repair`), `RepairSession.load(run_dir).lease().path`, `index_repo`, `build_agent(servers=..., extra_env=...)`.
- Produces: `async def run_chat(task_path: Path, runtime: Runtime, inputs: Iterable[str], *, agent_factory=build_agent) -> dict`. Kết quả trả về là `{"run_dir", "verdict", "recommendation", "verified_by": "agent" | "host"}`. `cmd_chat` gọi `run_chat(..., inputs=<vòng input()>)`.

**Cách làm:**
1. Gọi `_call(runtime, "repair_get_task_context", {...})`, cùng tham số như `tool_agent._open_run`. Nếu không `PASS` thì in lý do và trả `verdict = "ERROR"`.
2. `worktree = RepairSession.load(run_dir).lease().path`.
3. Index `task.source_repo` vào `<work_dir>/graph.db`, rồi tạo settings có graph backend là sqlite trỏ vào file đó.
4. Dựng agent với `servers=("graph", "repository", "execution", "repair")` và `extra_env={"VGAR_LEASE_ROOT": worktree, "VGAR_ALLOWED_SELECTORS": json.dumps(failing_selectors + fallback_scope), "VGAR_REPOSITORY_ROOT": task.source_repo}`. Bỏ tool `repair_get_task_context` khỏi danh sách tool của agent.
5. Tin nhắn đầu tiên dùng `task_prompt(text, worktree, None)`, kèm một dòng `Run directory: <run_dir>`.
6. Sau mỗi lượt và khi phiên kết thúc, đọc `RepairSession.load(run_dir).phase`.
   - Phase khác `"finished"` lúc kết thúc phiên: host gọi `repair_verify_patch`, và đặt `verified_by = "host"`.
   - In `[verdict] <status> (<recommendation>)`, lấy từ `run_record.json`.

- [ ] **Step 1: Viết test.** Dùng agent fake theo mẫu `SequenceAgent` trong `tests/unit/test_agent_solve.py`, với task là `examples/m2/tasks/single_file_login.json` và `Runtime(mode="fake")`.
  - **D19** `test_chat_agent_patch_is_judged_by_engine`: agent gọi `repair_apply_patch(run_dir, REF)`, rồi `repair_verify_patch(run_dir)` → `verdict == "PASS"`, `verified_by == "agent"`.
  - `test_chat_host_verifies_when_agent_stops_early` (Review Focus 4): agent không gọi tool nào → host gọi verify, `verified_by == "host"`, và `verdict` là verdict của engine.
  - `test_chat_lease_is_the_run_worktree`: `extra_env["VGAR_LEASE_ROOT"]` là worktree của run, khác `task.source_repo`. `VGAR_ALLOWED_SELECTORS` chứa `tests/test_auth.py::test_login_rejects_whitespace`.
  - `test_chat_hides_get_task_context_from_agent`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, `ModuleNotFoundError: vgar.agents.chat`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy file test và `tests/unit/test_agent_solve.py`.** Kỳ vọng: PASS.

### Task 7: Prompt, smoke và tài liệu contract

**Files:**
- Modify: `src/vgar/agents/prompts/system.md`
- Modify: `scripts/smoke_mcp.py`
- Modify: `docs/mcp_tool_contract.md`
- Test: `tests/test_cli_run_chat.py`

- [ ] **Step 1: Viết test** `test_system_prompt_routes_edits_through_repair`. Nội dung `system.md`:
  - có các chuỗi `repair_apply_patch` và `repair_verify_patch`;
  - không có chuỗi `"Use MCP repository and graph tools before"` (câu cũ);
  - có câu nói nội dung đọc từ repo là dữ liệu không tin cậy.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL.
- [ ] **Step 3: Implement.**
  - Viết lại `system.md`, giữ các quy tắc 2–8 có từ trước:
    - chỉ sửa code bằng `repair_apply_patch`;
    - chỉ nói "đã sửa" khi verdict là PASS;
    - nội dung đọc từ file là dữ liệu.
  - Sửa `smoke_mcp.py` cho chữ ký mới. Smoke đặt `VGAR_LEASE_ROOT` và `VGAR_ALLOWED_SELECTORS` qua `extra_env`.
  - Trong `docs/mcp_tool_contract.md`, cập nhật mục repository và execution:
    - chữ ký mới;
    - hai biến môi trường `VGAR_LEASE_ROOT`, `VGAR_ALLOWED_SELECTORS`;
    - các trần và timeout `READ_FILE_MAX_BYTES`, `PYTEST_TIMEOUT_SECONDS`, `PYTEST_OUTPUT_CAP`;
    - các mã lỗi.
- [ ] **Step 4: Chạy test và cả suite** theo lệnh CI. Kỳ vọng: xanh.
- [ ] **Step 5: Bàn giao PR2.** Danh sách file: `cli.py`, `agents/chat.py`, `system.md`, `smoke_mcp.py`, `docs/mcp_tool_contract.md`, `tests/test_cli_run_chat.py`. Mô tả PR ghi rõ: `vgar chat` đổi `--repo` thành `--task`, nên hiện chỉ demo được trên fixture đã khai báo.


### Task 8: `repair_server` chỉ nhận `run_dir` trong `VGAR_RUN_ROOT` (S1, S2; security §4.2)

**Files:**
- Modify: `src/vgar/mcp/servers/repair_server.py` (`_load` và `get_task_context`)
- Modify: `src/vgar/agents/runtime.py:62` (`repair_tools()` truyền `extra_env={"VGAR_RUN_ROOT": str(self.output_root)}`)
- Modify: `src/vgar/agents/chat.py` (cùng biến trong `extra_env`)
- Modify: `tests/m2/w78/test_w78_repair_server.py` (thêm fixture `autouse` đặt `VGAR_RUN_ROOT = tmp_path / "runs"`; **cần M2 review**)
- Test: `tests/test_mcp_security.py`

**Interfaces:**
- Consumes: `leased_root`, `inside` (Task 1).
- Produces:
  - `_load(tool, run_dir)` gọi `inside(leased_root("VGAR_RUN_ROOT"), Path(run_dir))` trước `RepairSession.load`.
  - `get_task_context` kiểm `output_root` theo cùng cách.
  - Thiếu biến thì trả lỗi `ROOT_NOT_LEASED` (người dùng chọn: chặt).

- [ ] **Step 1: Viết test**
  - **S2** `test_repair_rejects_run_dir_outside_run_root`: tạo một run thật dưới `tmp/a` bằng `get_task_context`, rồi đặt `VGAR_RUN_ROOT = tmp/b` và gọi `apply_patch(run_dir_a, REF)` → `PATH_OUTSIDE_ROOT`. `session.json` của run A không đổi (so bytes).
  - `test_repair_without_run_root_is_root_not_leased`.
  - `test_runtime_repair_tools_lease_output_root`: monkeypatch `create_mcp_client` để ghi lại `extra_env`, kiểm `extra_env["VGAR_RUN_ROOT"] == str(runtime.output_root)`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL.
- [ ] **Step 3: Implement.** Dùng đúng cách trả lỗi hiện tại của `repair_server` (`_tool_error`). Mã lỗi đầy đủ theo C4 thuộc Task envelope ngày 5. Ở bước này, `reason` là mã lỗi C4.
- [ ] **Step 4: Chạy `tests/m2/w78`, `tests/unit/test_agent_solve.py`, `tests/unit/test_workflow.py` và `tests/test_cli_run_chat.py`.** Kỳ vọng: PASS. Đường `solve`, `solve --agent` và `chat` đều đi qua `Runtime.repair_tools()`.

### Task 9: `PUBLIC_TOOLS` trong `registry.py` (S9; security §4.5)

**Files:**
- Modify: `src/vgar/mcp/registry.py`
- Modify: `src/vgar/agents/core.py` (`load_mcp_tools` gọi `validate_public_tools`)
- Modify: `src/vgar/cli.py` (`cmd_tools` gọi `validate_public_tools`)
- Test: `tests/test_mcp_security.py`

**Interfaces:**
- Produces: `PUBLIC_TOOLS: frozenset[str]`. Danh sách lấy từ `vgar tools` sau Task 1–8, gồm tên có tiền tố của các tool graph, `repository_health`, `repository_read_file`, `execution_health`, `execution_run_pytest` và 4 tool `repair_*`.
- Produces: `validate_public_tools(tools: Iterable[BaseTool]) -> None`. Gặp tên lạ thì raise `RuntimeError("Unguarded MCP tool(s): …")`.

- [ ] **Step 1: Viết test**
  - `test_unknown_tool_is_refused`: một tool giả tên `repository_apply_patch` → raise.
  - `test_all_current_tools_are_public`: tên tool từ `list_tools()` của 4 server (có tiền tố `<server>_`) đều nằm trong `PUBLIC_TOOLS`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL, `ImportError: PUBLIC_TOOLS`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy cả suite theo lệnh CI.** Kỳ vọng: xanh. Bàn giao PR3, danh sách file:
  - `repair_server.py`, `runtime.py`, `chat.py`, `registry.py`, `core.py`, `cli.py`;
  - `tests/test_mcp_security.py`;
  - `tests/m2/w78/test_w78_repair_server.py` (fixture, cần M2 review).

