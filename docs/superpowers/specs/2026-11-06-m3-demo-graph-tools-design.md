# M3: hoàn thiện tool graph cho agent chạy demo trên repo thật (06/11/2026)

Trạng thái: bản thiết kế, chờ người dùng duyệt. Nguồn: `docs/status/m3_status_synthesis_2026-11-06.md` (mục #11, #12,
#16, #25; smoke ở §2), `docs/status/m3_system_audit_2026-11-06.md` (R1, R2). Đường dẫn code không có tiền tố tính từ
`src/vgar/`.

## 1. Mục đích

Agent chạy bằng `vgar run` (chỉ đọc) và `vgar chat` trên repo thật, ví dụ `D:\kltn\vgar-demo-shop\vgar-demo-shop`,
phải dùng được cả 7 tool graph, mà model không cần biết chi tiết hạ tầng (hash snapshot, tokenizer, đường dẫn). Ngày
06/11, 4 trong 7 tool hỏng trên đường này:
- `get_related_context` báo `GRAPH_NOT_READY` vì thiếu tokenizer;
- trong `run`, `analyze_patch_impact` hỏng vì thiếu repo root;
- agent không biết `graph_version`, nên `find_task_anchors`, `get_related_context`, `get_related_tests`,
  `analyze_patch_impact` đều không gọi được.

## 2. Mục tiêu, không làm, không được làm

**Mục tiêu:** 5 task ở §3. Xong khi probe MCP trên bản sao repo demo cho cả 7 tool graph PASS khi gọi **không truyền**
`graph_version`.

**Không làm** (để sau):
- giữ session MCP suốt phiên (#18);
- bước dựng task từ repo (`vgar solve --agent --repo`);
- thống nhất chat (G2);
- tool liệt kê file;
- chuẩn bị repo demo (việc của M1).

**Không được làm:**
- Đổi kết quả của batch A0–A3 hoặc `solve --agent`: hai đường này truyền `graph_version` tường minh và không đi qua
  host của `run`/`chat`.
- Nới cơ chế bảo vệ snapshot: truyền sai version vẫn phải báo lỗi.
- Cho model chọn đường dẫn, tokenizer hay snapshot.
- Đổi ranking, budget hay hash cấu hình retrieval.

## 3. Thiết kế từng task

### Task A: `graph_version` không bắt buộc (#12)

- 4 tool trong `mcp/servers/graph_server.py` (`find_task_anchors`, `get_related_context`, `get_related_tests`,
  `analyze_patch_impact`): `graph_version: str = ""`.
- **Bỏ trống** (chuỗi rỗng hoặc chỉ có khoảng trắng): server dùng snapshot đã chọn lúc khởi động. Đó là kết quả
  `store.resolve_graph_version()` trong `graph/factory.py`: nếu có `VGAR_GRAPH_VERSION` thì dùng bản đó, không có thì
  dùng snapshot `ready` mới nhất. Cùng snapshot với `search_symbols`.
- **Truyền giá trị:** giữ nguyên hành vi hiện nay; sai thì `GRAPH_NOT_READY` (`graph/sqlite_store.py:273`).
- **Nơi xử lý mặc định:** một chỗ duy nhất trong `SQLiteGraphService`, ví dụ hàm `_version(graph_version)`, dùng chung
  cho 4 hàm service. Tool không tự đoán.
- **Kết quả trả về:** `data.graph_version` ghi snapshot đã dùng. `get_related_context` đã có trường này; thêm cho 3 tool
  còn lại nếu chưa có. Dòng audit ghi `graph_version` đã dùng, không ghi chuỗi rỗng.
- **Backend demo (không phải SQLite):** vẫn báo `GRAPH_NOT_READY` như cũ.
- **Docstring 4 tool:** thêm một câu "graph_version is optional; omit it to use the served snapshot" để model đọc được
  từ schema.
- **`task_id` cũng không bắt buộc:** `find_task_anchors` và `get_related_context` có `task_id: str = ""`; bỏ trống thì
  service dùng `"interactive"`. `task_id` chỉ dùng để đặt tên và hash overlay (`graph/task_overlay.py:41-55`), không vào
  ranking. Truyền giá trị thì giữ nguyên như cũ, nên `solve --agent` và các script không đổi.
- **Tài liệu:** cập nhật `docs/mcp_tool_contract.md` (tham số mới không bắt buộc). M2 review.

### Task B: host truyền môi trường cho server graph (#11)

Server graph đọc 3 biến lúc khởi động (`graph/factory.py:27-39`). Host phải truyền đủ cả 3.

| Biến | `vgar run` (`cli.py` `cmd_run`/`sandbox`) | `vgar chat` (`agents/chat.py:82-85`) |
|---|---|---|
| `VGAR_REPOSITORY_ROOT` | **Thêm**: `lease.path` (bản sao; lúc khởi động có cùng byte với bản vừa index) | Giữ như hiện có: `task.source_repo` (bản đã index; bản sao sẽ bị vá nên không dùng được để kiểm source) |
| `VGAR_GRAPH_VERSION` | **Thêm**: version của DB vừa dựng (`SQLiteGraphStore(db).resolve_graph_version()`) | **Thêm**: như bên trái |
| `VGAR_TOKENIZER_MANIFEST` | **Thêm**: `tokenizer_manifest` của profile mặc định `configs/m2/demo.json`, qua `load_config` | **Thêm**: `tokenizer_manifest` của `runtime.config_path`, qua `load_config` |

- Profile hiện ghim `artifacts/m2/w5-w6/tokenizer_manifest.json`, cùng tokenizer với thí nghiệm, nên context trong demo
  được đếm token giống lúc chạy thí nghiệm.
- **Thiếu file tokenizer:** báo lỗi rõ và dừng ngay khi khởi động lệnh, trước khi nạp model, thay vì để agent nhận
  `GRAPH_NOT_READY` giữa chừng.
- **Gom về một chỗ:** một hàm nhỏ (ví dụ trong `agents/runtime.py`) trả dict 3 biến từ `(database, repository_root,
  config_path)`; cả `run` lẫn `chat` cùng gọi. `impact_graph_tool` (`agents/runtime.py:29`) dùng chung hàm này khi tiện;
  hành vi của nó không đổi.

### Task C: dòng phản hồi impact đếm đúng test (#3 trong danh sách task)

- **Lỗi:** `agents/feedback.py:42` chỉ đếm item có `kind == "Test"`. Trên django-10914, dòng phản hồi ghi "0 test(s)"
  nhưng ngay sau đó liệt kê `tests.admin_widgets.tests (imports)`.
- **Sửa:** một item tính là test khi `kind == "Test"`, hoặc khi đường dẫn của nó (hoặc `qualified_name` nếu không có
  đường dẫn) nằm trong thư mục `tests`/`test`, hoặc tên file có dạng `test_*.py` / `*_test.py`. Dòng phản hồi thành:
  `21 dependent node(s) (5 in tests, 16 in code)`.
- Không đổi thứ tự sắp xếp, không đổi giới hạn `IMPACT_ITEMS` và `IMPACT_CHARS`.
- **Tác động:** dòng này nằm trong prompt của lần thử lại trong `solve --agent`, nên prompt của các run agent về sau sẽ
  đổi. Batch A0–A3 không dùng feedback, nên không bị ảnh hưởng.

### Task D: đóng run khi agent bị hủy (#16)

- **Lỗi:** `agents/tool_agent.py:552-563` chỉ bắt `Exception`, nên khi gặp `asyncio.CancelledError` (Ctrl-C, timeout
  bên ngoài) thì không gọi `host.close()`, trong khi `finally` vẫn xóa workspace.
- **Sửa:** khi bị hủy hoặc gặp `BaseException` khác, vẫn gọi `host.close()` trước khi dọn workspace, rồi ném lại lỗi gốc.
- **Giới hạn thời gian cho bước đóng:** `host.close()` có thể chạy test, mất vài phút. Bước đóng khi bị hủy chạy trong
  `asyncio.shield`, bọc `asyncio.wait_for(..., CANCEL_CLOSE_TIMEOUT_SECONDS = 120)`. Hết hạn, hoặc người dùng bấm Ctrl-C
  lần nữa, thì bỏ bước đóng, ghi vào trace rồi ném lỗi gốc.
- **Trace:** trên nhánh bị hủy vẫn gọi `_write_trace`, với kết quả có `error = "CancelledError"`, cộng lỗi đóng nếu có.
  Cách này khớp cách nhánh `Exception` đang ghi `error`.
- **Lỗi khi đóng:** nếu chính `host.close()` lỗi, không được che mất lỗi gốc; ghi lỗi đóng vào trường `error` của kết
  quả trong trace.
- Áp dụng cùng cách cho `vgar chat` (`agents/chat.py`): khi bị hủy, nếu run chưa `finished` thì gọi
  `repair_verify_patch` giống nhánh host đang có, cùng `shield` và cùng giới hạn 120 s.
- `agents/workflow.py` không nằm trong phạm vi: node `verify` đã là bước kết thúc duy nhất.

### Task E: timeout cho tool graph phía client (#25)

- **Vì sao không đặt ở server:** tool graph là hàm đồng bộ chạy trong tiến trình server, nên timeout phía server không
  dừng được việc đang chạy.
- **Cách làm:** đặt `session_kwargs={"read_timeout_seconds": timedelta(seconds=GRAPH_TOOL_TIMEOUT_SECONDS)}` **chỉ cho
  kết nối `graph`** trong `mcp/client.py`. Hết giờ thì client bỏ request, session đóng, tiến trình server bị dừng.
- **Không đặt cho `repair` và `execution`:** `get_task_context` có lúc mất trên 300 s, và các bước này đã có timeout
  riêng của engine.
- **Giá trị:** `GRAPH_TOOL_TIMEOUT_SECONDS = 120`. Smoke django khoảng 43 s mỗi call, repo demo dưới 1 s.
- **Agent thấy gì:** với `handle_tool_errors=True`, agent nhận thông báo lỗi thay vì exception, và vòng lặp chạy tiếp.

## 4. Kiểm chứng

Mỗi task viết test trước (TDD) và chạy bằng `pytest -m "not hf and not docker"`.

| Task | Test |
|---|---|
| A | Với DB có 1 snapshot: mỗi tool trong 4 tool gọi không có `graph_version` → PASS và `data.graph_version` = snapshot đang phục vụ; truyền đúng → PASS; truyền `"guess"` → `GRAPH_NOT_READY`. Với DB có 2 snapshot và `VGAR_GRAPH_VERSION` trỏ bản cũ: bỏ trống → dùng bản cũ |
| B | `run` và `chat` truyền đủ 3 biến (giả lập `create_core_agent`/`build_agent` và đọc `extra_env`); thiếu file tokenizer → lỗi rõ trước khi nạp model |
| C | Fixture `tests/fixtures/agents/impact_django_10914.json`, chép từ `data` của `/tmp/vgar-impact-smoke/result.json` trên WSL (`wsl -e cat …`, 14 KB): dòng phản hồi có `in tests` > 0; test cũ của `impact_message` vẫn qua |
| D | Agent giả bị hủy giữa chừng: `close` được gọi đúng 1 lần, `CancelledError` vẫn được ném ra, workspace vẫn được dọn |
| E | Kết nối `graph` có `read_timeout_seconds`; `repair`/`execution` không có |

**Kiểm chứng cuối:** script giữ lại trong repo, `scripts/smoke_demo_graph_tools.py REPO`. Script không phải test pytest,
nên không chạy trong CI.
1. Chép REPO sang thư mục tạm, rồi dựng graph.
2. Lấy môi trường bằng chính hàm của Task B, rồi gọi cả 7 tool graph qua `create_mcp_client`, **không truyền**
   `graph_version` và `task_id`.
3. Input cố định cho repo demo:
   - issue: "Checkout with coupon SAVE10 on a 500000 VND order gives no discount";
   - `search_symbols("discount")`;
   - `get_callers`/`get_callees` trên `shop.discounts.discount_amount`;
   - `find_task_anchors` với failing test `tests/test_x.py::test_bug`;
   - `get_related_context` với các anchor đó, `budget_tokens=2000`;
   - `get_related_tests` trên `discount_amount`;
   - `analyze_patch_impact` với diff đổi `>` thành `>=` trong `shop/discounts.py`.
4. In status của từng tool. Exit 0 chỉ khi đủ 7/7 PASS và context có `shop/discounts.py`.

Chạy tay trên `D:\kltn\vgar-demo-shop\vgar-demo-shop` và ghi kết quả vào báo cáo hoàn thành.

## 5. Lựa chọn tôi tự quyết (người dùng kiểm khi đọc)

- Repo root của `run` là bản sao (`lease.path`); của `chat` giữ là `task.source_repo`.
- Tokenizer lấy từ profile `configs/m2/demo.json`, không thêm cờ CLI.
- Timeout 120 s, chỉ đặt cho server graph.
- Cách nhận diện item test trong impact (§3 Task C).
- Không đổi `agents/workflow.py`.
- `task_id` không bắt buộc, mặc định `"interactive"`.
- Bước đóng khi bị hủy: `shield` + 120 s; Ctrl-C lần hai thì bỏ; trace vẫn được ghi.
- Script smoke được giữ lại trong repo, chạy tay, không vào CI; input cố định cho repo demo.

## 6. Ngoài phạm vi, ghi vào Hạn chế

- Mỗi lần gọi MCP vẫn mở lại tiến trình server (khoảng 2,3 s mỗi call).
- Grounding từ mô tả lỗi viết bằng lời vẫn yếu (#15). Spec này chỉ làm cho tool **gọi được**, không làm kết quả retrieval
  tốt hơn.
