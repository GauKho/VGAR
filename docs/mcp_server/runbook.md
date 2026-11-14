# VGAR MCP — Runbook preflight và bàn giao L6-8

> **Cập nhật 12/11/2026 (TV2, quyết định của nhóm):** repo chỉ còn **3 server** (`graph`, `repository`, `execution`); `repair_server`, client LangChain (`create_mcp_client`), agent và generator Qwen đã bị xóa. `pyproject.toml` ghim `mcp==2.2.0` (đúng `requirements/mcp-server.lock`), nên **một `.venv` duy nhất** chạy server SDK2: `pip install -e ".[dev,history,code-graph]"`. Lane SDK1/LangChain bên dưới chỉ còn là lịch sử nghiệm thu L6-1. Chi tiết: `docs/superpowers/specs/2026-11-12-remove-langchain-sdk2-design.md`, báo cáo `docs/status/tv2_remove_langchain_sdk2_run_2026-11-12.md`; debug và logging: `docs/mcp_server/debugging.md`.

Ngày: **09/11/2026 (Asia/Saigon)**. Task này chỉ thực hiện **offline preflight**, không cài client/package, login, gọi model hoặc nghiệm thu toàn bộ L6-8.

## Các mức kết quả

1. Inventory: đăng ký20 tools, gồm11 core; graph có8 canonical resources+1alias và1prompt. Listing không chứng minh provider chạy production.
2. Scripted SDK smoke: các server đọc/query/fixture tests/prompt/resource thực sự được gọi, có data/denial/protocol receipts. Không phải Inspector hoặc external-agent smoke.
3. Real legacy build on fixture: production static builder/controller/SQLite chạy cold→reuse→warm→read; source đầu vào synthetic, không phải graph schema mới hoặc experiment.
4. Provider/client integration: chỉ đóng khi provider thật đúng schema/binding đã tích hợp và external client thực sự gọi thành công. Hiện còn dependency; không dùng fixture hoặc trạng thái PASS của SDK để thay.

`DONE kỹ thuật preflight` và `L6-8 PARTIAL/BLOCKED_DEPENDENCIES` có thể đồng thời đúng.

## Chạy preflight

```powershell
$vgarPython = 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
vgar index <repo> --db <graph>.db   # dựng graph thật (backend demo đã bỏ)
$env:VGAR_GRAPH_BACKEND = 'sqlite'; $env:VGAR_GRAPH_DATABASE = '<graph>.db'; $env:VGAR_REPOSITORY_ROOT = '<repo>'
$env:PYTHONPATH = "$PWD\src"
& $vgarPython -B scripts/mcp_server/smoke_mcp.py --preflight `
  --client-python $vgarPython --server-python $vgarPython `
  --output-root 'results/mcp_server/preflight/<fresh-run>/campaign'
```

Mỗi lần chọn output mới. CLI từ chối overwrite, output chồng lấn input hoặc path escape. Output trong checkout chỉ được đặt dưới preflight results; không dùng DB tracked để thử write/migrate. `-B`/no pytest cache bảo vệ checkout khỏi bytecode/cache mới.

Exit0: đủ local evidence để chuyển sang external validation; không tự là full L6-8 PASS. Exit2: hoàn thành kiểm tra nhưng còn dependencies/unknown (kết quả dự kiến hiện tại). Exit1: runtime/integrity/tooling lỗi; không đổi lỗi hash/binding/schema thành một dependency bình thường để làm xanh.

Đọc theo thứ tự: `summary.json`/`report.md` → `dependencies.md` → `bootstrap.json`, `clients.json`, `inventory.json`, `graph-consumer.json` → command/wire receipts → preservation/checksums. Input/code/DB hashes được đối chiếu trước–sau. Graph consumer đọc các sidecars thật, manifest/DB/source/binding/evidence, không chỉ tin producer khai PASS.

CLI không có agent loop, install command hoặc provider auto-discovery từ model. Fixed helper actions được chạy bounded, environment allowlist trước import/spawn; stdout MCP chỉ protocol. Mọi denied operation có thể ghi control audit, nhưng không được tạo worker/DB/candidate work. Authority keys/grants fixture ở temp riêng, không đưa vào report/config export.

## Runtime và bootstrap

SDK2 server dùng interpreter riêng theo `configs/mcp_server/runtime.json`, không cài distribution VGAR gốc/mcp<2 hoặc sửa môi trường CUDA. Runtime legacy được giữ cho compatibility tests. Không suy protocol version từ SDK major: receipts ghi negotiation thực của mode modern2026-07-28 và legacy.

Default graph/execution bootstrap đang không bind provider mới. L6-6 có `GraphJobController` legacy thật nhưng cần host đăng ký bằng Python bootstrap, signed context và exact per-operation grants. Config JSON về command/env không tự tạo registry, source/tokenizer binding hoặc authorization.

Xem `tools.md`, `resources.md`, `prompts.md`, `graph_jobs.md`, `storage_backends.md` cho từng contract/lifecycle. Khi đọc snapshot, host dùng manifest/version/profile cụ thể; source hash phải thuộc snapshot đã chọn và khớp source hiện hành. Không ghép graph_version cũ với source_hash mới hoặc fallback latest/demo để che mismatch.

## Config Inspector và Claude Code

Ba file `.template.json` trong `configs/mcp_server/` chỉ là **TEMPLATE_NOT_EXECUTED**. `preflight-templates.json` ghi trạng thái và command template. Không ghi `.mcp.json` ở root, `~/.claude.json`, global settings hoặc PATH.

- Inspector modern và legacy đều là STDIO qua command/args, khác `protocolEra`. Inspector thực chưa chạy; version chưa chọn/pin trong offline task. Không dùng `npx ...@latest` hoặc tự tải trong preflight.
- Các `${...}` là placeholders phải được operator thay từ trusted private roots/manifest/hashes. Chưa render/bind không được gọi READY. Snapshot hashes/roots không lấy tùy ý từ model. Empty selector list giữ deny-default, không mở wildcard.
- Claude executable được dò ở PATH và vị trí native đã biết, gọi **chỉ --version/--help**. Sự hiện diện của `--mcp-config`/`--strict-mcp-config` không chứng minh account, session isolation hay protocol mode đã PASS. Auth giữ NOT_CHECKED_OFFLINE; không đọc credential store hoặc chạy login/agent.
- Mẫu lệnh Claude dùng executable tuyệt đối cùng config riêng. Việc khởi chạy phiên thật, kiểm project approvals/isolation/permissions và model/account chỉ thực hiện trong bước được yêu cầu sau; không dùng bypass-permissions.

## Bàn giao dependency

`dependencies.json`/`.md` là ma trận sinh từ observation, gồm consumer/capability, trạng thái, evidence refs, phần phải bàn giao, owner/task, phần TV1 tích hợp và gate đóng. TV1/TV2/TV3 là nhãn phân công nội bộ của Final_Task, không đồng nhất M1/M2/M3 cũ.

Ưu tiên SC-1 và graph provider của TV2: schema/IDs/endpoints/validator/fingerprint, builder/update, traversal/path, architecture/task/trace views, source/profile/tokenizer binding và oracle full rebuild. TV1 còn phải nối bootstrap, adapter, storage profile/projection và orchestration; SQLite legacy PASS không tự lưu được Component/Port.

TV3 bàn giao graph verification/coverage, GOOD/BAD evidence và ranking (EV-1/2), admitted diff-test lifecycle/baseline evidence (EV-3). Code API/structural legacy đã có là phần tái sử dụng, không được báo rằng mọi implementation TV3 đều chưa tồn tại; cần adapter đúng contract mới và evidence binding.

Capability nào được bàn giao thì tích hợp/test capability đó, không phải chờ mọi task của thành viên hoàn tất. Không triển khai thay thuật toán của họ trong preflight. Internal technical review không phải chữ ký review TV2/TV3 và không tạo yêu cầu duyệt lại người dùng đã bỏ.

## Tự chạy test

```powershell
& $vgarPython -B -m pytest tests/mcp_server/test_end_to_end.py `
  tests/mcp_server/test_runtime_cli.py -q -p no:cacheprovider `
  --basetemp "$env:TEMP\vg-preflight-new-01"
```

Unit receipts có nhãn synthetic chỉ kiểm consumer/control logic. Real CLI chạy lại các SDK smoke và static builder/storage trên fixture; không dùng dummy provider để đóng chain path→context→impact→GOOD/BAD verify→rank→evidence. Nếu thiếu provider thì chain này NOT_RUN với dependency rõ. Không chạy lại toàn suite dài khi không có thay đổi liên quan.

Artifact task: `results/mcp_server/preflight/20261109T055933Z-offline/`. Final log/JUnit/summary và bảo toàn được append sau actual execution. Không commit/push; dừng sau preflight, không tự chuyển external experiment.

## Reference — liên kết từ kế hoạch; không truy cập mạng trong preflight

- [MCP Inspector](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector)
- [Protocol eras](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector/protocol-eras)
- [Inspector CLI](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector/cli)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)


## Kết quả thực thi đã lưu

- `results/mcp_server/preflight/20261109T055933Z-offline/campaign-02/`: exit2/PARTIAL, local_checks PASS; dependencies.md có20dòng và owner/gate cụ thể.
- 8/8 SDK2 wire lanes PASS; modern2026-07-28 và legacy2025-11-25. Hai real static-builder fixture chains có cold/reuse/warm và snapshot read PASS.
- SDK2 final50 PASS (31preflight); legacy40 PASS+1skip cũ, không cộng unique total. Logs/commands/JUnit nằm tại thư mục task cha; Ruff/pipcheck PASS. CLI preservation2903files PASS; báo cáo bảo toàn task/seal nằm `preservation.json`.
- Inspector, Claude session và full production chain NOT_RUN. Chưa đóng L6-8; bước tiếp theo cần lệnh riêng và provider/schema/bootstrap/client theo ma trận.

`${VGAR_SOURCE_ROOT}` trong templates là thư mục Python source `D:/Project/CAPSTONES/VGAR/src`, không phải root repo. Graph resources chỉ đọc snapshot sau khi operator cung cấp manifest/version/resolver/profile đã xác minh. Grounding/retrieval còn cần `VGAR_REPOSITORY_ROOT` tương ứng (token đếm bằng byte UTF-8/4, không cần tokenizer); templates không giả định đã có các asset/binding đó. Registry/controller production không tự bind qua env JSON.
