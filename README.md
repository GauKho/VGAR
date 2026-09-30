# VGAR-MCP — M1 Graph & Retrieval

Thư mục làm việc độc lập. Mục tiêu là xây graph construction, storage và retrieval.

## Cấu trúc hiện tại

```text
M1/
├── src/vgar/graph/
│   ├── builder.py
│   ├── context.py
│   ├── errors.py
│   ├── schema.py
│   ├── sqlite_store.py
│   ├── sqlite_service.py
│   └── factory.py
├── scripts/load_graph_fixture.py
├── scripts/build_graph.py
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

## Chạy test schema độc lập

Từ `D:\KLTN\M1`:

```powershell
$env:PYTHONPATH = "D:\KLTN\M1\src"
python -m unittest discover -s tests -p "test_graph_schema.py" -v
```

Môi trường phát triển chuẩn hiện tại là `.venv-win` (Python 3.12). Chạy toàn bộ tests:

```powershell
$env:PYTHONPATH = "D:\KLTN\M1\src;D:\KLTN\VGAR\src"
$env:PYTHONDONTWRITEBYTECODE = "1"
& ".\.venv-win\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
```

## Chạy contract test với M3

Sau khi cài dependencies trong môi trường phát triển:

```powershell
$env:PYTHONPATH = "D:\KLTN\M1\src;D:\KLTN\VGAR\src"
python -m unittest discover -s tests -p "test_sqlite_graph_service.py" -v
```

Thứ tự `M1\src` trước `VGAR\src` cho phép thêm implementation `vgar.graph.*`, còn DTO `vgar.contracts.graph` và port tiếp tục lấy từ repo M3.

## Cách tích hợp dự kiến

M3 chỉ cần thay điểm khởi tạo trong `graph_server.py` từ `DemoGraphService()` sang factory khi hai bên sẵn sàng merge. Backend `demo` vẫn là mặc định, vì vậy smoke flow hiện tại của M3 không bị phá.

Không copy SQLite schema hoặc query logic vào MCP server. MCP server chỉ gọi `GraphService` để giữ storage implementation thuộc M1.

## Build Graph MVP

```powershell
$env:PYTHONPATH = "D:\KLTN\M1\src;D:\KLTN\VGAR\src"

& ".\.venv\Scripts\python.exe" .\scripts\build_graph.py `
  .\tests\fixtures\sample_repo `
  .\artifacts\sample_graph.json `
  --repo-key "demo/vgar-fixture" `
  --revision "fixture-revision"

& ".\.venv\Scripts\python.exe" .\scripts\load_graph_fixture.py `
  .\artifacts\sample_graph.json `
  .\artifacts\sample_graph.db
```

Graph builder hiện extract `Repository`, `File`, `Module`, `Class`, `Function`, `Method`, `Test`, `Import`, `CallSite`; tạo containment, resolve internal/external imports, inheritance cơ bản và direct/imported/self calls. Jedi 0.20.0 là tầng static-analysis enrichment cho các call còn unresolved, chỉ chấp nhận kết quả map ngược được về symbol nội bộ. Unresolved calls vẫn được giữ dưới dạng `CallSite` có `candidate_count=0`.

Graph document không công khai `schema_version`. `graph_version` chỉ nhận dạng snapshot cụ thể. `context.py` định nghĩa và kiểm tra `ContextPayload`; `errors.py` cung cấp error code ổn định để M3 ánh xạ vào MCP response.

Có thể tắt Jedi để đo baseline Tree-sitter/resolver nội bộ bằng cờ `--no-jedi` khi chạy `build_graph.py`.

## Checkpoint hiện tại

- 27/27 tests pass.
- End-to-end source → graph → validation → SQLite → M3 DTO pass.
- Manual review xác nhận 19/19 edge `CALLS` đã resolve trên repo VGAR đúng đích.
- Graph thật của VGAR: 227 nodes, 263 edges, 19 resolved và 57 unresolved call sites.
- Factory giữ demo backend làm mặc định.
