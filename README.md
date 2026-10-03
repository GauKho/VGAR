# VGAR-MCP — M1 Graph & Retrieval

Repo tích hợp M1/M2/M3. M1 phụ trách graph construction, storage và retrieval.

## Cấu trúc hiện tại

```text
VGAR/
├── src/vgar/graph/
│   ├── builder.py
│   ├── context.py
│   ├── grounding.py
│   ├── task_overlay.py
│   ├── retrieval.py
│   ├── token_counter.py
│   ├── sqlite_store.py
│   ├── sqlite_service.py
│   └── factory.py
├── src/vgar/contracts/      # schema/error/DTO dùng chung
├── scripts/run_m1_tests.py
├── scripts/find_task_anchors.py
├── scripts/build_task_overlay.py
├── scripts/get_related_context.py
├── scripts/build_graph.py
├── scripts/load_graph_fixture.py
└── tests/
    ├── fixtures/
    ├── test_graph_schema.py
    └── test_sqlite_graph_service.py
```

## Ranh giới với M3

M1 không sở hữu MCP decorators, MCP transport hoặc LangChain/LangGraph orchestration. M1 cung cấp backend tuân theo interface hiện có của M3:

```python
search_symbols(query: str, limit: int = 20)
get_callers(symbol_id: str)
get_callees(symbol_id: str)
```

`sqlite_service.py` cố ý import DTO từ `vgar.contracts.graph` của M3. Đây là compatibility boundary; không nhân bản contract sang M1.

## Chạy kiểm thử M1

Chạy từ thư mục gốc của bản clone, sau khi đã chuẩn bị môi trường Windows
Python và các dependency của VGAR. Checkpoint M1 đã dùng Python 3.12,
Tree-sitter 0.25.2, grammar Python 0.25.0 và Jedi 0.20.0.
Ví dụ dưới chọn interpreter trong `.venv` của bản clone; nếu dùng môi trường
khác, thay đường dẫn `$m1Python` bằng interpreter tương ứng:

```powershell
$m1Python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $m1Python scripts/run_m1_tests.py
```

Script ưu tiên `VGAR/src` để không lấy nhầm editable package từ workspace M1 cũ.
Đây là bộ test M1, gồm schema, builder, context, SQLite, pipeline, grounding,
overlay, retrieval và tokenizer. Dependencies của VGAR được khai báo trong
`pyproject.toml`; đổi file này không tự cập nhật môi trường đã cài trước đây.

Để chạy cả phần tokenizer, cài runtime riêng ngoài repo và provision assets
đúng revision một lần. Các lệnh cài/provision cần mạng:

```powershell
$m1TokenizerRuntime = Join-Path (Get-Location).Path '..\runtime\m1-tokenizers'
& $m1Python -m pip install --target $m1TokenizerRuntime --no-deps `
  -r scripts/requirements_m1_tokenizer.txt
& $m1Python scripts/provision_m1_tokenizer.py `
  --model-id 'Qwen/Qwen3-4B-Instruct-2507' `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --assets-root artifacts/m1/tokenizers `
  --manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json
$env:PYTHONPATH = $m1TokenizerRuntime
& $m1Python scripts/run_m1_tests.py
```

Assets tokenizer được Git-ignore; người clone cần provision riêng. Sau khi
chuẩn bị xong, counter dùng assets local. Nếu thiếu runtime/assets, các tests
tokenizer có thể skip; lượt đó không thay cho bằng chứng 95/95 không skip.
Đường dẫn môi trường checkpoint cũ `D:/KLTN/M1` hiện không tồn tại; xem
[handoff hiện tại](docs/m1_handoff_2026-10-03.md) để đối chiếu môi trường.

## Trạng thái M1 và tài liệu bàn giao

M1 đang ở **W5–W6 theo deliverables của kế hoạch 16 tuần**: graph builder,
grounding/task overlay, traversal/ranking, source-verified snippets và context
packing đã triển khai. Context models dùng chung qua re-export; validator đã
từ chối Windows drive paths theo quyết định được duyệt.

Checkpoint ngày 03/10/2026 ghi nhận **95/95 tests M1 đạt, không skip**, cùng
standalone API/CLI và token budget boundary checks. Counter dùng tokenizer
Qwen đã pin revision, budget **8000 token cho snippets**. Các mốc 49/67/86 tests
là checkpoint trước đó; logs và manifests nằm trong `artifacts/m1/`.
Đây là bằng chứng đã lưu, không phải xác nhận một lượt chạy mới trên bản clone.

Đánh giá Graph–BM25 trên dev tasks và tích hợp consumer M2/M3 còn thiếu;
**chưa đóng toàn bộ W5–W6**. Ngân sách snippet không đại diện tổng prompt.

| Tài liệu M1 | Vai trò |
|---|---|
| [Handoff ngày 03/10](docs/m1_handoff_2026-10-03.md) | Deliverables, bằng chứng, môi trường và công việc tiếp theo |
| [Retrieval method](docs/m1_retrieval_method.md) | API, traversal/ranking, source checks và packing |
| [Tokenizer acceptance](docs/m1_tokenizer_acceptance.md) | Revision/hashes, counting policy và kết quả nghiệm thu |
| [Contract decision log](docs/m1_contract_decision_log.md) | Quyết định đã duyệt và consumer sign-off còn thiếu |
| [Change scope](docs/m1_change_scope_2026-10-03.md) | Phạm vi M1 và ảnh hưởng của thay đổi dùng chung |
| [Document index](docs/m1_documents.md) | Mục lục contract, thiết kế, nghiên cứu và bằng chứng |

## Cách tích hợp dự kiến

Factory đã hỗ trợ backend SQLite; backend `demo` vẫn là mặc định.
M3 sở hữu cấu hình MCP và integration flow. Grounding hiện chạy độc lập ở M1.

Không copy SQLite schema hoặc query logic vào MCP server. MCP server chỉ gọi `GraphService` để giữ storage implementation thuộc M1.

## M2 W3–W4: baseline repair/verification infrastructure

This integrated `VGAR` tree contains M1 graph and M3 MCP code plus M2's disposable workspace, pytest wrapper, and pre-patch EvidenceBundle. Run the commands below from this `VGAR` root for M2.

Install the development test dependency in a Python 3.11–3.13 environment (the full project dependencies are listed in `pyproject.toml`):

```powershell
python -m pip install -e '.[dev]'
$env:VGAR_M2_TEMP_ROOT = 'D:\Project\CAPSTONES\m2-temp'
python scripts\record_m2_test.py tests/m2 --timeout-seconds 120
python scripts\run_m2_baseline.py tests\fixtures\sample_repo tests/test_auth.py --task-id sample-auth
```

Every invocation saves one detailed JSON under `artifacts/m2/test-runs/`. A deliberate failing example returns exit code 1 while still saving evidence:

```powershell
python scripts\run_m2_baseline.py tests\fixtures\m2\failing_repo tests/test_demo.py --task-id deliberate-fail
```

See `docs/verification_design.md` for scope/safety, `docs/evidence_bundle_schema.md` for JSON fields, and `docs/m2_w3_w4_handoff.md` for verification records and deferred work. These W3–W4 scripts do not invoke an LLM, modify the source repo, apply a patch, or add MCP execution tools. Review raw test logs for secrets before sharing artifacts.

## Build Graph MVP

```powershell
$m1Python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONPATH = (Resolve-Path '.\src').Path

& $m1Python .\scripts\build_graph.py `
  .\tests\fixtures\sample_repo `
  .\artifacts\sample_graph.json `
  --repo-key "demo/vgar-fixture" `
  --revision "fixture-revision"

& $m1Python .\scripts\load_graph_fixture.py `
  .\artifacts\sample_graph.json `
  .\artifacts\sample_graph.db
```

Graph builder hiện extract `Repository`, `File`, `Module`, `Class`, `Function`, `Method`, `Test`, `Import`, `CallSite`; tạo containment, resolve internal/external imports, inheritance cơ bản và direct/imported/self calls. Jedi 0.20.0 là tầng static-analysis enrichment cho các call còn unresolved, chỉ chấp nhận kết quả map ngược được về symbol nội bộ. Unresolved calls vẫn được giữ dưới dạng `CallSite` có `candidate_count=0`.

Graph document không công khai `schema_version`. `graph_version` chỉ nhận dạng snapshot cụ thể. Context models kiểm tra `ContextPayload`; `vgar.contracts.error` cung cấp error code dùng chung. Xem [graph schema](docs/graph_schema.md) và [grounding/retrieval](docs/retrieval_design.md).

Có thể tắt Jedi để đo baseline Tree-sitter/resolver nội bộ bằng cờ `--no-jedi` khi chạy `build_graph.py`.

## Checkpoint graph ngày 01/10/2026 — lịch sử

- 46/46 tests M1 pass tại checkpoint 01/10/2026.
- End-to-end source → graph → validation → SQLite → M3 DTO pass.
- Build toàn repo tích hợp vượt qua validation khi bật và tắt Jedi, sau khi sửa Tree-sitter và builder.
- Số liệu build và mẫu kiểm source được ghi trong [graph quality report](docs/graph_quality_report.md); không dùng số graph của workspace M1 cũ làm số liệu repo tích hợp.
- Tại checkpoint này, `find_task_anchors` đã hỗ trợ path, line, traceback, symbol và pytest selector. Retrieval/packing được bổ sung sau đó, như phần trạng thái M1 ở trên.
- Factory giữ demo backend làm mặc định.
