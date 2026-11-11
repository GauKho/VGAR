# MCP server runtime — L6-1

## Phạm vi

L6-1 chuyển bốn server sang factory chọn SDK và tách runtime khỏi legacy LangChain client. Không thêm tool/resource/prompt, provider hoặc native agent host. H1 hiện ACCEPTED_FOR_IMPLEMENTATION theo xác nhận người dùng ngày 08/11/2026 rằng nhóm đã chốt plan, không cần thêm vòng review TV2/TV3. Runtime acceptance chỉ nghiệm thu L6-1, không suy rằng schema/provider mới đã được triển khai.

Code cần quan tâm:

- `src/vgar/mcp/server_factory.py`: SDK2 → `MCPServer`, SDK1 → `FastMCP`; version sai/major khác từ chối; dependency SDK2 lỗi không fallback.
- MCP package lazy-export `create_mcp_client`; registry chỉ cần Protocol có `name`, không import BaseTool lúc runtime. Legacy client implementation giữ nguyên.
- Bốn server giữ tên, signatures, decorators và envelope; entry points đều explicit STDIO. Hai `dict(...)` trong repair server đổi sang dict literal để đáp ứng lint, không đổi values/signatures.
- `scripts/mcp_server/check_runtime.py` và hai helper chỉ là scripted test client/probe. Không có model/generator/conversation loop. Gate dùng explicit checks, không dựa vào `assert` có thể bị Python `-O` bỏ qua; child environment pin `PYTHONOPTIMIZE=0`.

## Runtime riêng và tái tạo

Config operator: [runtime.json](../../configs/mcp_server/runtime.json). SDK candidate cố định MCP2.2.0, lock cho **Windows amd64 / CPython3.11**, gồm56 distributions có exact version và wheel SHA-256; pip/setuptools bootstrap của venv không thuộc56 dependency này. Không dùng lock này như lock Linux hoặc Python khác.

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$legacyPython = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
$serverPython = 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

Venv SDK2 đã được tạo trong phiên L6-1. Chỉ dùng lệnh tạo dưới đây khi đích **chưa tồn tại**, không chạy đè hoặc nâng venv cũ:

```powershell
& $legacyPython -B -m venv 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2'
& $serverPython -B -m pip install --require-hashes -r requirements/mcp-server.lock
& $serverPython -B -m pip check
```

Không dùng `--system-site-packages`, `pip install -e .` hoặc `--no-deps`. Root metadata vẫn giữ MCP<2 và LangChain cho legacy lane; resolver đã xác minh MCP2.2.0 xung đột `langchain-mcp-adapters==0.3.2`. Runtime server không có LangChain/LangGraph/Torch/Transformers. `huggingface-hub` là dependency của native tokenizer; sự có mặt của package này không đồng nghĩa model được tải hoặc gọi.

## Kiểm runtime/wire không cần model

Mỗi lệnh cần output mới chưa tồn tại; không ghi đè receipts cũ:

```powershell
$runId = Get-Date -Format 'yyyyMMddTHHmmss'
& $serverPython -B scripts/mcp_server/check_runtime.py `
  --client-python $serverPython --server-python $serverPython `
  --require-no-langchain `
  --output-root "results/mcp_server/runtime/$runId-sdk2"

& $legacyPython -B scripts/mcp_server/check_runtime.py `
  --client-python $legacyPython --server-python $serverPython `
  --require-no-langchain `
  --output-root "results/mcp_server/runtime/$runId-sdk1-client"
```

SDK2 client chạy cả mode modern `2026-07-28` và legacy handshake (thực thương lượng `2025-11-25`). SDK1 client chỉ legacy. Để kiểm factory SDK1 riêng, dùng legacy interpreter cho cả hai argument, bỏ `--require-no-langchain` vì legacy env vốn có framework; không gọi đó là runtime clean.

Mỗi server có wire receipt:

| Server | Kiểm thực hiện |
|---|---|
| graph |15-tool inventory được chia theo server; query PASS/ERROR, callers/callees, summary/node/subgraph trên **DB temp copy** |
| repository |health, đọc fixture, từ chối path escape |
| execution |health, pytest fixture nhỏ trong lease, từ chối selector |
| repair |trusted single_file_login + tokenizer local/hash-pinned + reference diff; context/apply/tests/verify đến ACCEPT; lỗi thứ tự, missing run và finalizer lần hai |

Source repair gốc không apply patch; private worktree được cleanup. Fixture smoke synthetic không phải dev experiment, không gọi generator/model/Docker. Ba resources hiện có được kiểm dưới dạng1 static resource +2 templates; chưa có prompt, nên gate ghi `PENDING_L6-4`.

Controller dùng bounded executor hiện có: mỗi worker tối đa240s, process-tree boundary Windows Job/POSIX group; SDK2 RPC timeout90s. Có test server chết khi handshake và worker timeout kèm descendant cleanup. Đây chưa phải nghiệm thu full cancellation/concurrency L6-5.

Output gồm inventory packages/classes, command argv/exit/deadline/stdout/stderr, wire responses/audit, prompt disposition và summary. Exit0 chỉ khi tất cả server/mode bắt buộc PASS; lỗi probe không chạy tiếp wire. Không dùng `assert` để quyết định PASS.

## Chạy trực tiếp một server bằng config operator

```powershell
$runtime = Get-Content -LiteralPath 'configs/mcp_server/runtime.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$env:PYTHONPATH = $runtime.source_root
$env:PYTHONOPTIMIZE = '0'
# Operator phải cấp audit output và lease/run root phù hợp trước khi gọi tools.
# Graph production phải có VGAR_GRAPH_BACKEND=sqlite và explicit READY DB riêng.
& $runtime.python -B -m $runtime.entrypoints.repository
```

Server chờ MCP trên stdin/stdout; terminal không phải test client. stdout chỉ protocol; logs stderr/file. Config này không tự cấp quyền ghi/read root và không ghi global settings của Inspector/Claude Code. Kết nối external host thuộc L6-8.

## Gate và tình trạng

Artifact gốc: `results/mcp_server/runtime/20261108T121938Z-sdk2/`. Acceptance cuối phải đọc `runtime-acceptance.json` và `summary.json`, không suy từ tên venv/config. Log/JUnit và commands từng bước nằm trong artifact, gồm cả các lần RED và lint chưa đạt.

Regression legacy có1 skip cũ: `test_read_file_rejects_symlink_escape`, lý do `symlinks unavailable` trên Windows. Không thêm skip/xfail mới. New lifecycle test chạy SDK2; legacy export test chạy env cũ có LC, không cài LC để chạy nó trong SDK2.

SQLite tests legacy dùng plugin **chỉ trong artifact** để redirect tracked `sample_graph.db` sang copy per-test. Không sửa assertions hoặc production queries. Ruff chạy scoped `--no-cache`; lần đầu cache bị sandbox từ chối được giữ log, không thay cache/quyền. Global diff-check có15 trailing-whitespace cũ trong báo cáo M2 được bảo vệ; whitespace L6-1 phải PASS riêng.

Source tham khảo đã đối chiếu khi lập/triển khai plan: [migration SDK](https://py.sdk.modelcontextprotocol.io/migration/), [official client](https://py.sdk.modelcontextprotocol.io/client/), [release2.2.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0). API/type/constructor cho candidate được đối chiếu source tag2.2.0, không dùng latest để đổi pin.

Dừng sau L6-1; chưa triển khai L6-5 hoặc các task khác. Không commit/push.
