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
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env } # lần đầu, không overwrite secrets
```

Sau `pip install -e .` có lệnh `vgar`. Nếu chưa muốn cài entry point: `python -m vgar.cli <lệnh>`.

---

## 2. Cấu hình (`.env`)

Toàn bộ cấu hình nằm ở `src/vgar/config/settings.py` và được nạp từ `.env`. Không còn YAML (`configs/*.yaml` không được đọc nữa).

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
| `VGAR_GRAPH_SOURCE_ROOT` | – | Source root khớp SQLite snapshot, cần cho W6 context |
| `VGAR_TOKENIZER_MANIFEST` | – | Manifest tokenizer local đã pin, không tải weights |
| `VGAR_ALLOW_FALLBACK_COUNTER` | `0` | Bytes/4 diagnostic fixture, không official benchmark |
| `VGAR_WORKSPACE_ROOT` | – | Disposable workspace host cấp; tools không nhận root tùy ý |
| `VGAR_MCP_AUDIT_LOG` | `logs/mcp_audit.jsonl` | File audit của MCP server |
| `VGAR_M2_TEMP_ROOT` | `<cha của repo>/m2-temp` | Thư mục workspace tạm của script M2 (chưa nằm trong `Settings`, đọc trực tiếp bởi script) |

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
vgar tools                 # dựng 3 MCP server, liệt kê 10 tool
vgar index tests/fixtures/m2/failing_repo --db artifacts/graph.db
vgar run "Fix the failing test" --repo tests/fixtures/m2/failing_repo `
    --selector tests/test_demo.py::test_answer
vgar chat --repo tests/fixtures/m2/failing_repo        # REPL, giữ lịch sử hội thoại
```

| Lệnh | Việc làm | Cần model |
|---|---|---|
| `vgar doctor` | In settings đã resolve và cho biết `HF_TOKEN` có được đặt không | không |
| `vgar tools` | Spawn graph/repository/execution server và liệt kê tool (kỳ vọng: 10) | không |
| `vgar index REPO --db PATH` | Build graph snapshot của REPO vào SQLite (mặc định `artifacts/graph.db`) | không |
| `vgar run "<task>" --repo REPO` | Chạy agent một lượt | có |
| `vgar chat --repo REPO` | Chạy agent nhiều lượt; dòng trống hoặc Ctrl-D để thoát | có |

Tùy chọn của `run` và `chat`:

| Cờ | Ý nghĩa |
|---|---|
| `--selector tests/x.py::test_y` | pytest selector. Với `run`, CLI tự chạy lại pytest độc lập sau khi agent xong |
| `--keep` | Giữ thư mục tạm để kiểm tra sau |

### Cách `run` và `chat` hoạt động

`run`/`chat` và workflow `solve` bind graph source vào **disposable workspace mới** và chọn snapshot ready trong DB vừa tạo, không kế thừa source/version của repo khác. W6 `get_related_context` vẫn cần `VGAR_TOKENIZER_MANIFEST` trỏ đến manifest/assets đã pin (ví dụ `artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json`); thiếu assets thì làm bước provision trong [hướng dẫn retrieval](docs/m5_m6_retrieval_evaluation.md), không dùng fallback cho benchmark. Host giữ tokenizer policy, không cho model tự chọn root. Sau khi workspace bị sửa, snapshot cũ có thể bị từ chối do hash mismatch; đợt này **không có automatic incremental reindex**.

```text
REPO ──index──► graph.db (tạm, backend=sqlite)
  └──copy────► workspace tạm (vgar-m2-*)  ◄── agent chỉ sửa bản này
                         │
                 pytest độc lập ──► PASS/FAIL (không tin lời agent)
```

- Repo gốc không bị sửa. CLI so sánh fingerprint trước và sau, rồi in `source repo untouched`.
- Exit code của `run` là 0 khi pytest độc lập PASS và repo gốc không đổi, ngược lại là 1. Nếu không truyền `--selector`, bước pytest độc lập bị bỏ qua.
- Khi bỏ selector, exit 0 không chứng minh repair qua tests. Discovery W6 tools cũng không thay cho binding source root/tokenizer; dùng W6 smoke bên dưới để kiểm integration, không suy ra model agent đã nghiệm thu benchmark.
- `VGAR_MAX_TOOL_CALLS` (mặc định 30) là giới hạn **cứng cho mỗi lượt chạy agent** (một `ainvoke`; với `solve` là mỗi lần retry). Khi chạm giới hạn, lời gọi tool tiếp theo bị chặn và lượt đó kết thúc; bước pytest độc lập vẫn chạy sau đó. Cơ chế nằm trong `agents/core.py`.
- `run` và `chat` luôn dùng graph tạm của chính REPO, bất kể `VGAR_GRAPH_BACKEND` trong `.env`. `.env` chỉ quyết định backend cho `vgar tools` và các script.

### Smoke test

```powershell
python scripts/smoke_w3_w4_agent.py --model scripted   # không cần GPU, kiểm tra orchestrator + MCP
python scripts/smoke_w3_w4_agent.py --model hf --query "Fix the failing test tests/test_demo.py::test_answer"
```

Scripted PASS chỉ kiểm đường fixture orchestrator/MCP đã chạy; nếu HF fail, cần đọc log model/runtime/tool-call. Không loại trừ integration/resource lỗi chỉ từ một smoke PASS.

---

## 4. Test

```powershell
python -m pytest -q
```

`pyproject.toml` đã đặt `pythonpath = ["src"]` và bỏ qua `tests/fixtures`. `tests/test_hf_model.py` cần `torch` và `transformers`. Nếu chỉ muốn kiểm tra phần không cần GPU: `python -m pytest -q --ignore=tests/test_hf_model.py`.

`tests/test_settings.py` bao phủ: giá trị mặc định, override qua env, lỗi parse, từ chối provider/temperature sai, và việc server con không nhận secret.

---

## 5. Graph (M1)

Graph builder extract `Repository`, `File`, `Module`, `Class`, `Function`, `Method`, `Test`, `Import`, `CallSite`. Ngoài ra nó tạo containment, resolve import nội bộ/ngoại bộ, kế thừa cơ bản và các call trực tiếp/qua import/qua `self`.

Jedi 0.20.0 là tầng static-analysis bổ sung cho các call còn unresolved, chỉ chấp nhận kết quả map ngược được về symbol nội bộ. Call không resolve được vẫn được giữ dưới dạng `CallSite` có `candidate_count=0`.

Build thủ công qua JSON rồi nạp vào SQLite:

```powershell
python scripts\build_graph.py tests\fixtures\sample_repo artifacts\sample_graph.json `
    --repo-key "demo/vgar-fixture" --revision "fixture-revision"

python scripts\load_graph_fixture.py artifacts\sample_graph.json artifacts\sample_graph.db
```

Thêm `--no-jedi` vào `build_graph.py` để đo baseline Tree-sitter/resolver nội bộ.

Dùng graph SQLite với MCP server:

```powershell
$env:VGAR_GRAPH_BACKEND  = "sqlite"
$env:VGAR_GRAPH_DATABASE = "artifacts\sample_graph.db"
vgar tools
```

Ghi chú hợp đồng:

- Graph document không công khai `schema_version`; `graph_version` chỉ nhận dạng một snapshot.
- `src/vgar/contracts/context.py` định nghĩa ContextPayload; `src/vgar/contracts/error.py` cung cấp stable error codes.
- MCP server chỉ gọi `GraphService`; không copy SQLite schema hay query logic vào server. `sqlite_service.py` import DTO từ `vgar.contracts.graph`, đây là ranh giới tương thích, không nhân bản contract.
- Backend `demo` vẫn là mặc định, nên các smoke flow cũ không bị phá.

Snapshot lịch sử trước CLI: 227 nodes, 263 edges, 19 resolved call edges (review khi đó 19/19 đúng), 57 unresolved call sites. Không phải số đo code hiện tại sau đợt sửa 06/10/2026.

---

## 6. MCP tools

Tên tool có prefix theo server (`tool_name_prefix=True`):

| Server | Tool |
|---|---|
| graph | `graph_search_symbols`, `graph_get_callers`, `graph_get_callees`, `graph_find_task_anchors`, `graph_get_related_context` |
| repository | `repository_health`, `repository_read_file`, `repository_apply_patch` |
| execution | `execution_health`, `execution_run_pytest` |

Server được dựng trong `src/vgar/mcp/client.py` bằng `sys.executable -m vgar.mcp.servers.<name>_server`, nên luôn dùng cùng Python/venv với tiến trình gọi. Mọi tool call của graph server được ghi vào `VGAR_MCP_AUDIT_LOG`. Xem `docs/mcp_tool_contract.md` cho schema chi tiết.

Tools cả ba server dùng envelope/audit chung. W6: gọi find_task_anchors(issue_text, failing_tests=None), lấy data.task_handle/data.anchor_ids, rồi get_related_context(anchor_ids, budget_tokens, task_handle). SQLite giữ binding qua session stateless; data context vẫn frozen ContextPayload, diagnostics trong metadata. Demo retrieval trả GRAPH_NOT_READY; caller/callee chỉ depth=1.

Lease chặn root/path trái phép theo capability policy, **không phải OS/container sandbox**. Pytest external repo có thể thực thi arbitrary host code; lọc HF_TOKEN không bảo đảm không đọc filesystem secrets. Chỉ chạy repo tin cậy hoặc môi trường cách ly được duyệt.

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

### Retrieval tuần 5–6, không model/GPU

```powershell
python scripts\smoke_w5_w6.py --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json
python scripts\run_graph_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --task-id django__django-11138 --task-id matplotlib__matplotlib-14623 --task-id pydata__xarray-3993 --task-timeout-seconds 300 --offline --rebuild-trees --no-jedi
```

Cần tokenizer/source cache đúng pin đã có. Profile benchmark chính no-Jedi được người dùng duyệt ngày07/10/2026; không thay app default hoặc trộn với các run Jedi. Chỉ chạy dev25 sau pilot đạt. Hướng dẫn setup một lần, tự chọn run, compare/resume/metrics: [vận hành](docs/m5_m6_retrieval_evaluation.md). [PROGRESS](PROGRESS.md) và [nghiệm thu](docs/w5_w6_completion.md) ghi evidence thật; unit/fixture PASS không thay paired25/manual10/environment50–100. Task environment50–100/smoke3 bị người dùng loại trừ khỏi đợt triển khai này, không được đánh dấu hoàn thành.

Checkpoint mới07/10: pilot no-Jedi3/3 giữnguyên; sau fixduplicate inheritance và snapshot preparation, run mới **23success/2WinError5/25attempts**, comparison **23pairs/COMPARED_PARTIAL**. Minimum20 đã có nhưng **strict gate25completed pairs/owner sign-off chưa đủ**. [Hướng dẫn/trạng thái hiện tại,mục6](docs/GIAI_THICH_VGAR_TRUOC_SAU_FIX_TUAN_3_6_VA_CACH_KIEM_THU.md), [REPORT23](results/retrieval/20261007T122342844612Z-12c751a0b3f6/REPORT.md), [manual self-audit10](docs/reviews/2026-10-07-manual-retrieval-audit-10.md). Suitecode **365passed/4skipped**; không suy Graph thắngBM25 hoặc repair thành công. Windows rename/Jedi method đã lỗi lặp thì dừng, coldSympy limits giữriêng; environment excluded, không commit/push đợt này. [Kết quả19/25 lịch sử](docs/reviews/2026-10-07-dev25-no-jedi-results.md) giữnguyên.

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
