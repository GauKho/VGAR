# Thiết kế: security cho MCP server (M3-W11-1: S1–S5)

> **Ngày:** 01/11/2026 · **Người soạn:** người dùng (đang giữ vai M1 và M3) cùng Claude Code
> **Trạng thái:** đã thống nhất trong buổi brainstorm #2. Chờ người dùng duyệt tài liệu, sau đó viết plan.
> **Nguồn:**
> - spec chia việc §4, W11 ngày 4 (M3-W11-1), và Phụ lục A (S1–S5);
> - contract C4 và C6 trong `docs/m3_w11_decisions.md`.
>
> **Dựa trên:** thiết kế legacy server `docs/superpowers/specs/2026-11-01-m3-w11-legacy-servers-design.md`, gồm `VGAR_LEASE_ROOT`, danh sách selector, `read_file(path)` và `run_pytest(selector)`.

## 1. Mục đích

DoD của cổng W12 yêu cầu "tool không chạy lệnh tùy ý". Server MCP phải chạy được ở **mọi máy có code**: Windows lúc phát triển, WSL trên máy GPU, CI Linux và máy demo (người dùng nói).

Spec yêu cầu 5 kiểm chứng:
- **S1:** path traversal.
- **S2:** root sai.
- **S3:** selector độc.
- **S4:** timeout phải dừng **cả cây tiến trình**.
- **S5:** output phải bị chặn **ngay trong lúc chạy**, không phải cắt sau khi đã nhận hết.

## 2. Hiện trạng (kiểm code 01/11)

- **Engine M2 đã giải quyết S4 và S5** trong `run_bounded` (`src/vgar/repair/executor.py:81-138`):
  - Windows: tiến trình con được tạo ở trạng thái treo, gán vào Job Object có cờ `KILL_ON_JOB_CLOSE`, rồi mới cho chạy tiếp. Đóng job thì cả cây tiến trình bị dừng.
  - POSIX: tiến trình chạy trong session riêng, dừng bằng `os.killpg(SIGKILL)`.
  - Output ghi ra file. Cứ 20 ms kiểm một lần, vượt `output_cap` thì dừng tiến trình.
  - `clean_environment` lọc các biến có chứa TOKEN, PASSWORD, SECRET hoặc API_KEY.
- `execution_server.run_pytest` hiện **không** dùng `run_bounded`. Nó gọi `subprocess.run(timeout=…)`, nên khi hết giờ chỉ dừng tiến trình cha, và output bị cắt sau khi đã nhận hết.
- **Lỗ hổng mới tìm thấy:** các tool `apply_patch`, `run_relevant_tests`, `verify_patch` của `repair_server` nhận `run_dir` **do model truyền vào** (`repair_server.py:43-50`). Trong `vgar chat`, model được gọi thẳng các tool này, nên có thể trỏ sang **một run khác có trên máy** rồi apply patch hoặc chốt kết quả cho run đó.

## 3. Goals, non-goals, anti-goals

**Goals:** cả 5 kiểm chứng S1–S5 đều có test **ở mức tool MCP** và chạy được trên Windows lẫn Linux.

**Non-goals**
- Viết lại cơ chế quản lý tiến trình. Phần này dùng `run_bounded`.
- Audit mọi call (S8), redact secret (S6), allowlist biến môi trường (S7). Ba mục này thuộc W11 ngày 3 và 5.
- Sandbox ở mức hệ điều hành (container, seccomp) cho `execution_server`.

**Anti-goals**
- Có bất kỳ tool nào nhận đường dẫn hoặc `run_dir` nằm ngoài root do host cấp.
- Test S4 hoặc S5 chỉ chạy được trên một hệ điều hành.
- Đổi hành vi của engine M2 hoặc runner A0–A3.

## 4. Thiết kế đã chốt

### 4.1. Runner C6 dựa trên `run_bounded` (người dùng chọn)

- `src/vgar/mcp/pytest_runner.py` có hàm `run_selector(root, selector, *, timeout_seconds, output_cap)`. Hàm này bọc `vgar.repair.executor.run_bounded`, gọi với `argv = (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", selector)` cố định và `cwd = root`.
  - Truyền `environment={"PYTHONPATH": f"{root / 'src'}{os.pathsep}{root}", "PYTHONIOENCODING": "utf-8"}` để giữ đúng hành vi import của `execution_server.py:37-40` hiện tại. `run_bounded` tự thêm `PYTEST_DISABLE_PLUGIN_AUTOLOAD` và lọc các biến chứa bí mật.
  - `timed_out` → raise `CodedToolError(TIMEOUT, …)`.
  - `output_truncated` → trả `truncated: true` cùng phần output đã có.
  - `status == "ERROR"` vì lý do khác (ví dụ không khởi động được tiến trình) → raise `CodedToolError(INTERNAL_ERROR, …)`. Thông báo chi tiết chỉ ghi vào audit.
- **Điều kiện:** M2 xác nhận giữ nguyên chữ ký `run_bounded(argv, cwd, timeout_seconds, *, output_cap, environment)`. Ghi điều này thành mục C6 trong `docs/m3_w11_decisions.md`.
- Mục này **thay** cho câu "chuyển code `execution_server.py:36-69` sang làm fake" trong plan legacy server, Task 3.

### 4.2. Chặn root và path dùng chung (S1, S2)

- Thêm hai hàm vào `src/vgar/mcp/tooling.py` (tôi chọn):
  - `leased_root(env_name) -> Path`: lấy root từ biến môi trường. Thiếu biến, hoặc giá trị không phải thư mục, thì raise `CodedToolError(ROOT_NOT_LEASED)`.
  - `inside(root, candidate) -> Path`: `resolve()` đường dẫn rồi kiểm có nằm trong `root.resolve()` không. Nếu không thì raise `CodedToolError(PATH_OUTSIDE_ROOT)`. Hàm này chặn được cả `..` lẫn symlink.
- `repository_server.read_file` và `execution_server.run_pytest` dùng `leased_root("VGAR_LEASE_ROOT")`.
- **`repair_server`** dùng `leased_root("VGAR_RUN_ROOT")` (tôi chọn):
  - `apply_patch`, `run_relevant_tests`, `verify_patch`: `run_dir` phải nằm trong root này;
  - `get_task_context`: `output_root` phải nằm trong root này.

  Host đặt `VGAR_RUN_ROOT = output_root`:
  - `Runtime.repair_tools()` (`src/vgar/agents/runtime.py:62`), là chỗ duy nhất `solve`, `solve --agent` và `chat` kết nối tới repair server;
  - `vgar chat`.
- Thiếu `VGAR_RUN_ROOT` thì `repair_server` **từ chối** (tôi chọn: chặt). `tests/m2/w78/test_w78_repair_server.py` gọi thẳng hàm server, nên phải thêm một fixture đặt biến này. Thay đổi đó cần M2 review.

### 4.3. Selector (S3)

Danh sách selector được phép và cách server dựng `argv` cố định giữ nguyên như thiết kế legacy server §3.3. Không có shell, không có cờ do model chọn.

### 4.4. Giới hạn do server đặt, gom về một chỗ (tôi chọn)

- Đặt các hằng sau ở cấp module trong `tooling.py`:
  - `READ_FILE_MAX_BYTES = 64 * 1024`
  - `PYTEST_TIMEOUT_SECONDS = 120`
  - `PYTEST_OUTPUT_CAP = 12_000`
- Server import từ đây. Ghi các giá trị vào `docs/mcp_tool_contract.md`. Không tool nào nhận các giá trị này làm tham số.

### 4.5. Danh sách tool được phép công khai (S9, thực thi trong `registry.py`; tôi chọn)

- Thêm `PUBLIC_TOOLS` (tên đầy đủ có tiền tố, ví dụ `repository_read_file`, `execution_run_pytest`, `repair_apply_patch`, cùng các tool graph) và hàm `validate_public_tools(tools)`. Gặp tool không có trong danh sách thì raise `RuntimeError`.
- `load_mcp_tools` (`src/vgar/agents/core.py`) và `vgar tools` gọi `validate_public_tools`. Như vậy một tool mới thêm vào server sẽ không tự lọt ra cho agent khi chưa qua guard.

## 5. Kiểm chứng (`tests/test_mcp_security.py`)

| ID | Test | Kỳ vọng |
|---|---|---|
| S1 | `read_file("../x")`, `read_file` trên symlink ra ngoài root, `run_pytest("tests/../../x.py")` | `PATH_OUTSIDE_ROOT` hoặc `SELECTOR_REJECTED`. Không có file nào bị đọc, không có tiến trình nào được tạo |
| S2 | `read_file` khi thiếu `VGAR_LEASE_ROOT`. `repair_apply_patch` với `run_dir` nằm ngoài `VGAR_RUN_ROOT`, dù `run_dir` đó là một run có thật | `ROOT_NOT_LEASED` hoặc `PATH_OUTSIDE_ROOT`. Run kia không đổi gì |
| S3 | Selector có cờ, có khoảng trắng, có `\n`, có `..`, hoặc không có trong danh sách | `SELECTOR_REJECTED`, runner không được gọi |
| S4 | `run_pytest` chạy một test tạo **tiến trình cháu** (ghi PID ra file) rồi `sleep` lâu hơn timeout. Test đặt timeout nhỏ bằng monkeypatch | `TIMEOUT`. Sau đó PID của tiến trình cháu không còn sống. Kiểm được trên cả Windows lẫn POSIX bằng `psutil` nếu có sẵn, nếu không thì dùng `os.kill(pid, 0)` hoặc `OpenProcess` |
| S5 | `run_pytest` chạy một test in liên tục khoảng 50 MB. Test đặt output cap nhỏ bằng monkeypatch | Trả về trước khi in xong (thời gian ≪ thời gian in hết), `truncated: true`, độ dài output ≤ cap |
| S9 | Một tool lạ xuất hiện trong danh sách tool | `validate_public_tools` raise |

S4 và S5 chạy pytest thật, nên mất vài giây. Đánh dấu cả hai là `slow` nếu nhóm có marker này, nhưng **vẫn chạy trong CI**.

## 6. Ràng buộc

- File của M3: `src/vgar/mcp/**`, `src/vgar/agents/runtime.py`, `src/vgar/agents/core.py`, `src/vgar/cli.py`.
- File cần M2 review:
  - `tests/m2/w78/test_w78_repair_server.py`, chỉ thêm fixture;
  - phần dùng `run_bounded`, theo cam kết giữ chữ ký ở C6.
- Không sửa `graph_server.py` trong W11 ngày 1–2.
- Làm **sau** plan legacy server, vì dùng lại `CodedToolError`, `pytest_runner` và hai biến môi trường. Khi viết plan nên gộp vào Task 3 của plan legacy server nếu chưa làm task đó.

## 7. Để lại cho người làm

- Cách kiểm "tiến trình còn sống" trên từng hệ điều hành trong test S4.
- Có tách `leased_root` và `inside` sang một module riêng (ví dụ `src/vgar/mcp/guards.py`) hay không.
- Danh sách cụ thể của `PUBLIC_TOOLS`, lấy từ `vgar tools` sau khi xong plan legacy server.

## 8. Quyết định của Claude (để người dùng kiểm khi đọc)

- Hai hàm `leased_root` và `inside` dùng chung cho cả 3 server (§4.2).
- `repair_server` kiểm `run_dir` và `output_root` theo `VGAR_RUN_ROOT`, và **từ chối khi thiếu biến** (§4.2).
- Gom các giới hạn thành hằng trong `tooling.py` (§4.4).
- `PUBLIC_TOOLS` trong `registry.py`, chặn tool lạ ngay khi nạp (§4.5).
- Lỗi khởi động tiến trình trả `INTERNAL_ERROR`, chi tiết chỉ ghi vào audit (§4.1).
