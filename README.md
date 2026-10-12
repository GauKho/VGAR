# VGAR-MCP

Verified Graph-Augmented Reasoning via Model Context Protocol: agent sửa lỗi Python dựa trên graph của repository, gọi tool qua MCP và xác minh patch bằng test.

```text
vgar CLI ──► LangChain / LangGraph agent ──► langchain-mcp-adapters
                   │                              │
          Settings (.env)                 ┌───────┼────────────┐
                   │                    graph   repository   execution
             HF model (local)           (M1)       (M2)        (M2)
```

| Phần | Owner | Thư mục |
|---|---|---|
| Graph & Retrieval | M1 | `src/vgar/graph/` |
| Repair & Verification | M2 | `src/vgar/repair/`, `src/vgar/mcp/servers/{repository,execution}_server.py` |
| MCP, Agent, Evaluation | M3 | `src/vgar/mcp/`, `src/vgar/agents/`, `src/vgar/cli.py` |
| Config, Model | chung | `src/vgar/config/`, `src/vgar/models/` |

---

## 1. Cài đặt

Yêu cầu: Python 3.11–3.13. GPU CUDA là tùy chọn nhưng nên có cho model local.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .            # thêm '.[dev]' nếu cần pytest
copy .env.example .env      # rồi điền HF_TOKEN
```

Sau `pip install -e .` có lệnh `vgar`. Nếu chưa muốn cài entry point: `python -m vgar.cli <lệnh>`.

Nếu chỉ chạy graph/retrieval M1, có thể dùng môi trường riêng với Python 3.11:

```powershell
py -3.11 -m venv .venv-m1
.\.venv-m1\Scripts\Activate.ps1
python -m pip install -r scripts\requirements_m1.txt
$env:PYTHONPATH = (Resolve-Path .\src).Path
```

Môi trường này dùng cho các script và test M1, không cần GPU hay model weights.

Đóng gói source hiện tại, gồm các thay đổi chưa commit:

```powershell
python scripts\package_m1.py --list   # xem danh sách file trước
python scripts\package_m1.py          # tạo ZIP mới trong dist/
```

Gói gồm source, tests, configs, docs, graph fixtures và evidence nền tảng đã lưu
trong repository. Runtime Node, môi trường Python, tokenizer assets và kết quả
chạy local không đi kèm. Manifest trong ZIP ghi hash từng file; đây là gói source,
không phải môi trường chạy đã cài sẵn.

---

## 2. Cấu hình (`.env`)

Cấu hình chung nằm ở `src/vgar/config/settings.py` và được nạp từ `.env`. Không còn YAML (`configs/*.yaml` không được đọc nữa).

**Thứ tự ưu tiên:** biến môi trường thật > `.env` > giá trị mặc định trong code.

Ví dụ đặt tạm một biến cho một phiên shell: `$env:MAX_NEW_TOKENS = "1024"`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VGAR_MODEL_PROVIDER` | `huggingface` | Hiện chỉ hỗ trợ `huggingface` |
| `HF_MODEL_ID` | `Qwen/Qwen3-4B-Instruct-2507` | Model local |
| `HF_TOKEN` | – | Token HF, chỉ dùng ở tiến trình chính |
| `VGAR_TEMPERATURE` | `0` | Model local chỉ chạy greedy; giá trị khác 0 sẽ báo lỗi |
| `MAX_NEW_TOKENS` | `512` | Giới hạn token sinh ra |
| `VGAR_DEVICE_MAP` | `auto` | Truyền vào `device_map` của transformers |
| `VGAR_TORCH_DTYPE` | `auto` | Truyền vào `torch_dtype` |
| `MAX_ITERATIONS` | `5` | |
| `VGAR_MAX_TOOL_CALLS` | `30` | CLI cảnh báo nếu agent vượt ngân sách này |
| `VGAR_RECURSION_LIMIT` | `50` | `recursion_limit` của LangGraph |
| `VGAR_TOKEN_BUDGET` | `8000` | Ngân sách context retrieval |
| `VGAR_GRAPH_BACKEND` | `demo` | `demo` hoặc `sqlite` |
| `VGAR_GRAPH_DATABASE` | – | Bắt buộc khi backend là `sqlite`; đường dẫn tương đối tính từ thư mục gốc project |
| `VGAR_GRAPH_VERSION` | – | Ghim một snapshot; để trống = snapshot ready mới nhất |
| `VGAR_REPOSITORY_ROOT` | – | Thư mục repo nguồn tương ứng với snapshot, dùng khi lấy context M1 |
| `VGAR_TOKENIZER_MANIFEST` | – | Manifest tokenizer local để kiểm tra assets và đếm token cho context M1 |
| `VGAR_MCP_AUDIT_LOG` | `logs/mcp_audit.jsonl` | File audit của MCP server |
| `VGAR_M2_TEMP_ROOT` | `<cha của repo>/m2-temp` | Thư mục workspace tạm của script M2 (chưa nằm trong `Settings`, đọc trực tiếp bởi script) |

`VGAR_REPOSITORY_ROOT` và `VGAR_TOKENIZER_MANIFEST` được graph backend đọc trực tiếp từ môi trường; cần đặt khi dùng `get_related_context` với backend `sqlite`.

Quy tắc cần nhớ:

- Biến để trống (`VGAR_GRAPH_VERSION=`) được coi là chưa đặt.
- Giá trị sai kiểu (ví dụ `MAX_NEW_TOKENS=abc`) báo lỗi nêu đúng tên biến.
- Các MCP server con nhận `VGAR_*` từ `Settings` nhưng **không** nhận `HF_TOKEN`, vì `execution_server` chạy pytest trên repo không tin cậy.
- Code mới không gọi `os.getenv` cho biến `VGAR_*`/`HF_*`; hãy dùng `get_settings()`.

```python
from vgar.config import get_settings

s = get_settings()
s.model.model_id, s.agent.max_tool_calls, s.graph.backend
```

---

## 3. CLI

```powershell
vgar doctor                # in settings đã resolve, không load model
vgar tools                 # dựng 3 MCP server, liệt kê tool
vgar index tests/fixtures/m2/failing_repo --db artifacts/graph.db
vgar run "Fix the failing test" --repo tests/fixtures/m2/failing_repo `
    --selector tests/test_demo.py::test_answer
vgar chat --repo tests/fixtures/m2/failing_repo        # REPL, giữ lịch sử hội thoại
```

| Lệnh | Việc làm | Cần model |
|---|---|---|
| `vgar doctor` | In settings đã resolve và cho biết `HF_TOKEN` có được đặt không | không |
| `vgar tools` | Spawn graph/repository/execution server và liệt kê tool | không |
| `vgar index REPO --db PATH` | Build graph snapshot của REPO vào SQLite (mặc định `artifacts/graph.db`) | không |
| `vgar run "<task>" --repo REPO` | Chạy agent một lượt | có |
| `vgar chat --repo REPO` | Chạy agent nhiều lượt; dòng trống hoặc Ctrl-D để thoát | có |

Tùy chọn của `run` và `chat`:

| Cờ | Ý nghĩa |
|---|---|
| `--selector tests/x.py::test_y` | pytest selector. Với `run`, CLI tự chạy lại pytest độc lập sau khi agent xong |
| `--keep` | Giữ thư mục tạm để kiểm tra sau |

### Cách `run` và `chat` hoạt động

```text
REPO ──index──► graph.db (tạm, backend=sqlite)
  └──copy────► workspace tạm (vgar-m2-*)  ◄── agent chỉ sửa bản này
                         │
                 pytest độc lập ──► PASS/FAIL (không tin lời agent)
```

- Repo gốc không bị sửa. CLI so sánh fingerprint trước và sau, rồi in `source repo untouched`.
- Exit code của `run` là 0 khi pytest độc lập PASS và repo gốc không đổi, ngược lại là 1. Nếu không truyền `--selector`, bước pytest độc lập bị bỏ qua.
- `VGAR_MAX_TOOL_CALLS` (mặc định 30) là giới hạn **cứng cho mỗi lượt chạy agent** (một `ainvoke`; với `solve` là mỗi lần retry). Khi chạm giới hạn, lời gọi tool tiếp theo bị chặn và lượt đó kết thúc; bước pytest độc lập vẫn chạy sau đó. Cơ chế nằm trong `agents/core.py`.
- `run` và `chat` luôn dùng graph tạm của chính REPO, bất kể `VGAR_GRAPH_BACKEND` trong `.env`. `.env` chỉ quyết định backend cho `vgar tools` và các script.

### Smoke test

```powershell
python scripts/smoke_w3_w4_agent.py --model scripted   # không cần GPU, kiểm tra orchestrator + MCP
python scripts/smoke_w3_w4_agent.py --model hf --query "Fix the failing test tests/test_demo.py::test_answer"
```

Nếu `scripted` pass mà `hf` fail, lỗi nằm ở model (prompt hoặc định dạng tool-call), không phải ở MCP hay orchestrator.

---

## 4. Test

```powershell
python -m pytest -q
```

`pyproject.toml` đã đặt `pythonpath = ["src"]` và bỏ qua `tests/fixtures`. `tests/test_hf_model.py` cần `torch` và `transformers`. Nếu chỉ muốn kiểm tra phần không cần GPU: `python -m pytest -q --ignore=tests/test_hf_model.py`.

`tests/test_settings.py` bao phủ: giá trị mặc định, override qua env, lỗi parse, từ chối provider/temperature sai, và việc server con không nhận secret.

Chạy riêng bộ test M1:

```powershell
python scripts\run_m1_tests.py
```

Smoke test W5–6 kiểm tra luồng issue → anchors → context qua MCP, không gọi model. Thay đường dẫn manifest bằng tokenizer local đã provision:

```powershell
python scripts\smoke_w5_w6_retrieval.py --tokenizer-manifest path\to\tokenizer_manifest.json
```

Manifest được tạo bằng `scripts/provision_m1_tokenizer.py`; dùng `--help` để xem các tham số.

---

## 5. Graph (M1)

Graph builder extract `Repository`, `File`, `Module`, `Class`, `Function`, `Method`, `Test`, `Import`, `CallSite`. Ngoài ra nó tạo containment, resolve import nội bộ/ngoại bộ, kế thừa cơ bản và các call trực tiếp/qua import/qua `self`.

Builder mặc định dùng Tree-sitter để extract cú pháp và Python `ast`/`symtable` để phân giải symbol theo scope, không dùng Jedi. Một số method call có thể resolve từ annotation của tham số khi xác định được class nội bộ. Call không resolve được vẫn được giữ dưới dạng `CallSite` có `candidate_count=0`; lời gọi động hoặc mơ hồ có thể còn unresolved.

Có thể bật SCIP enrichment bằng `scip-python` (dựa trên Pyright). Runtime Node được cài riêng; graph/retrieval Python không cần model weights:

```powershell
.\scripts\install_scip_runtime.ps1
$env:PYTHONPATH = 'src'
python scripts\build_graph.py tests\fixtures\sample_repo artifacts\m1\w7-w8\graph.json `
    --repo-key "demo/vgar-fixture" --revision "fixture-revision" --resolver scip `
    --debug-log artifacts\m1\w7-w8\debug.jsonl
```

SCIP ưu tiên symbol có định nghĩa nội bộ. Nếu indexer lỗi, timeout hoặc không có occurrence phù hợp, builder dùng resolver tĩnh và ghi lý do fallback; `--strict-resolver` yêu cầu dừng khi index không dùng được. Index gắn với hash source; bundle cũ hoặc sai checksum không được dùng. Symbol ngoài repo hoặc mơ hồ không được nối thành edge nội bộ bằng phỏng đoán.

Phần resolver W5–W6 có thêm client LSP dùng Pyright. `--resolver lsp` dùng LSP cùng static; `--resolver scip-lsp` ưu tiên SCIP và tra LSP cho các call còn thiếu hoặc có binding static yếu. LSP không ghi đè binding SCIP đã xác định:

```powershell
.\scripts\install_lsp_runtime.ps1
python scripts\build_graph.py tests\fixtures\sample_repo artifacts\m1\w5-w6\graph.json `
    --repo-key "demo/vgar-fixture" --revision "fixture-revision" --resolver scip-lsp `
    --lsp-timeout 30 --lsp-max-requests 200 --debug-log artifacts\m1\w5-w6\debug.jsonl
```

Pyright được ghim qua package lock. Khi server lỗi hoặc hết giới hạn, các call chưa có kết quả dùng static fallback; kết quả ngoài repo hoặc mơ hồ giữ unresolved. Có thể kiểm tra runtime thật bằng `python scripts\smoke_w5_w6_resolvers.py`. Đây là kiểm chứng tích hợp trên fixture, chưa chứng minh cải thiện retrieval trên toàn bộ benchmark.

`VGAR_GRAPH_DEBUG_LOG` bật log JSONL cho resolver, retrieval và test selection; `VGAR_GRAPH_DEBUG_RUN_ID` liên kết các bước cùng một run. Có thể vẽ plot trực tiếp bằng `vgar.graph.visualization.plot_graph_tracking(document)`; hàm trả Matplotlib figure, dùng `plt.show()` hoặc `figure.savefig(...)` khi cần:

```powershell
python -m pip install -r scripts\requirements_m1_plot.txt
python scripts\visualize_graph.py artifacts\m1\w7-w8\graph.json --show `
    --debug-log artifacts\m1\w7-w8\debug.jsonl
```

Build thủ công qua JSON rồi nạp vào SQLite:

```powershell
python scripts\build_graph.py tests\fixtures\sample_repo artifacts\sample_graph.json `
    --repo-key "demo/vgar-fixture" --revision "fixture-revision"

python scripts\load_graph_fixture.py artifacts\sample_graph.json artifacts\sample_graph.db
```

Task grounding tìm anchors từ issue, đường dẫn, symbol, stack trace và failing-test report. Task overlay giữ node `Issue` cùng các liên kết `MENTIONS`/`REPRODUCES` riêng cho từng task; không ghi vào snapshot repo.

Retrieval duyệt các quan hệ graph từ anchors, xếp hạng và đóng gói source snippets theo ngân sách token. API nhận `graph_version` và `task_id` tường minh; nội dung nguồn được kiểm tra với snapshot trước khi trả context. Failing-test report là đầu vào được cung cấp, không phải kết quả chạy test của graph service.

Response context có nhãn `context_format="vgar.context.v1"`, revision và source hashes ở wrapper; shape `ContextPayload` giữ nguyên. `vgar.contracts.prompt_context.render_context_for_repair` chuyển payload thành phần context cho prompt M2, giữ path/symbol/range. Token budget chỉ tính snippets, chưa bao gồm phần hướng dẫn và prompt hoàn chỉnh.

`get_related_tests` nhận symbol IDs hoặc `changed_paths`, tìm test qua liên kết trực tiếp và caller trung gian có giới hạn. Nếu thiếu link, dùng failing tests hoặc danh sách `selected_tests` được cung cấp; nếu cả hai trống, response báo cần chọn suite. Đây là lựa chọn test tĩnh, không phải bằng chứng coverage. Smoke M1 W7–8 mặc định dùng static, kiểm tra graph → MCP context/test selection và gói bàn giao, không gọi LLM:

```powershell
python scripts\smoke_w7_w8_m1.py --tokenizer-manifest path\to\tokenizer_manifest.json
```

Thêm `--resolver scip` khi muốn kiểm tra SCIP sau khi cài runtime riêng.

Gói bàn giao M1 gồm `context.json`, `context_manifest.json`, `test_links.json` và phần context cho prompt. Manifest tách hash toàn file khỏi hash snippet, khai báo phạm vi Python sources và giữ nguyên byte/range. `vgar.contracts.handoff.validate_context_handoff` kiểm snapshot/source/token counts trước prompt; `adapt_test_hints` trả mapping và selectors dạng tuple cho M2. Cách export và nhận gói ở [context contract](docs/context_payload_contract.md). M2 vẫn kiểm tổng prompt budget, pytest collection và verification sau patch.

So sánh static và SCIP trên cùng dev manifest:

```powershell
python scripts\compare_static_vs_scip.py . data\manifests\verified-c104f840cc67-dev-25.json `
    --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --limit 5
```

Mỗi lần chạy lưu JSON, context và debug logs trong `results/retrieval/`. Runner giữ cùng task, token counter và cấu hình retrieval; ghi riêng lỗi/timeout của SCIP và không thay bằng kết quả static. Snapshot giữ Python, stubs và cấu hình project/Pyright; chưa cài dependencies riêng của target. Số liệu chỉ phục vụ đánh giá retrieval trên dev, không đo khả năng sửa lỗi của LLM.

SCIP dùng cấu hình tại target và thêm import roots `src`/`lib` khi có các thư mục này. Cấu hình JSON có sẵn được giữ nguyên. Có thể chọn task bằng `--instance-id`, hoặc giới hạn indexing bằng `--scip-target-only`; index theo một thư mục chỉ cung cấp thông tin cho phạm vi đó, các phần thiếu occurrence dùng static fallback.

Indexer mặc định dùng Python của tiến trình M1. Khi dùng môi trường target riêng, truyền `--scip-python` cùng `--scip-environment` của môi trường đó.

Dùng graph SQLite với MCP server:

```powershell
$env:VGAR_GRAPH_BACKEND  = "sqlite"
$env:VGAR_GRAPH_DATABASE = "artifacts\sample_graph.db"
vgar tools
```

Ghi chú hợp đồng:

- Graph document không công khai `schema_version`; `graph_version` chỉ nhận dạng một snapshot.
- `context.py` định nghĩa và kiểm tra `ContextPayload`; `errors.py` cung cấp error code ổn định để ánh xạ vào MCP response.
- MCP server chỉ gọi `GraphService`; không copy SQLite schema hay query logic vào server. `sqlite_service.py` import DTO từ `vgar.contracts.graph`, đây là ranh giới tương thích, không nhân bản contract.
- Backend `demo` vẫn là mặc định, nên các smoke flow cũ không bị phá.

Số liệu tham khảo từ snapshot repo VGAR trước khi thêm CLI: 227 nodes, 263 edges, 19 call edge resolved (review thủ công: 19/19 đúng đích), 57 call site unresolved. Các số liệu này chỉ áp dụng cho snapshot đã đo.

---

## 6. MCP tools

Tên tool có prefix theo server (`tool_name_prefix=True`):

| Server | Tool |
|---|---|
| graph | `graph_search_symbols`, `graph_get_callers`, `graph_get_callees`, `graph_find_task_anchors`, `graph_get_related_context`, `graph_get_related_tests` |
| repository | `repository_health`, `repository_read_file`, `repository_apply_patch` |
| execution | `execution_health`, `execution_run_pytest` |

Graph server cũng cung cấp các resource `vgar://repo/summary`, `vgar://graph/node/{node_id}` và `vgar://graph/subgraph/{node_id}`. `get_callers`/`get_callees` trả quan hệ gọi trực tiếp; duyệt nhiều hop để lấy context nằm trong `get_related_context`.

Server được dựng trong `src/vgar/mcp/client.py` bằng `sys.executable -m vgar.mcp.servers.<name>_server`, nên luôn dùng cùng Python/venv với tiến trình gọi. Mọi tool call của graph server được ghi vào `VGAR_MCP_AUDIT_LOG`. Xem `docs/mcp_tool_contract.md` cho schema chi tiết.

---

## 7. Baseline repair/verification (M2)

Các script này không gọi LLM, không sửa repo nguồn, không apply patch. Chúng chạy test trong workspace tạm và lưu EvidenceBundle trước khi có patch.

```powershell
$env:VGAR_M2_TEMP_ROOT = 'D:\Project\CAPSTONES\m2-temp'   # tùy chọn
python scripts\record_m2_test.py tests/m2 --timeout-seconds 120
python scripts\run_m2_baseline.py tests\fixtures\sample_repo tests/test_auth.py --task-id sample-auth
```

Mỗi lần chạy lưu một JSON chi tiết vào `artifacts/m2/test-runs/`. Ví dụ cố ý fail, exit code 1 nhưng vẫn lưu evidence:

```powershell
python scripts\run_m2_baseline.py tests\fixtures\m2\failing_repo tests/test_demo.py --task-id deliberate-fail
```

Xem `docs/verification_design.md` (phạm vi, an toàn), `docs/evidence_bundle_schema.md` (các field JSON) và `docs/m2_w3_w4_handoff.md` (ghi nhận kiểm chứng, việc hoãn lại). Kiểm tra log test thô để tìm secret trước khi chia sẻ artifact.

---

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `Unsupported VGAR_MODEL_PROVIDER` | Sai giá trị trong `.env`; hiện chỉ có `huggingface` |
| `Local HF model is greedy-only` | `VGAR_TEMPERATURE` khác 0 |
| `VGAR_GRAPH_DATABASE is required when VGAR_GRAPH_BACKEND=sqlite` | Backend là `sqlite` nhưng chưa đặt đường dẫn DB |
| Cảnh báo "unauthenticated requests to the HF Hub" | `HF_TOKEN` chưa có trong `.env` hoặc còn giá trị mẫu `hf_your_token_here` |
| Log có "offloaded to the cpu", chạy hàng trăm giây | Model không vừa VRAM nên phải offload; xem lại `VGAR_TORCH_DTYPE`, `VGAR_DEVICE_MAP` hoặc dùng model nhỏ hơn |
| `vgar: command not found` | Chưa kích hoạt venv hoặc chưa `pip install -e .`; dùng tạm `python -m vgar.cli ...` |
| `vgar tools` trả 0 tool hoặc treo | Một MCP server con không khởi động được; chạy thử `python -m vgar.mcp.servers.graph_server` để xem lỗi import |
| Đổi `.env` nhưng không có tác dụng | Biến cùng tên đã được đặt trong shell; biến môi trường thật luôn thắng `.env` |
