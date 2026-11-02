# M1 W11: cập nhật graph tăng dần (incremental) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `IncrementalGraphBuilder` cho ra graph giống hệt `PythonGraphBuilder.build` sau mỗi lần sửa source. File không đổi thì không parse lại. Mỗi lần cập nhật trả về số liệu cho bảng U1.

**Architecture:**
- Một lớp con riêng tư `_CachingGraphBuilder(PythonGraphBuilder)` chặn ba chỗ của `build()`:
  - `_extract_file`: nạp lại từ cache, hoặc trích xuất mới rồi ghi lại;
  - `_parse_python_ast`: cache cây `ast` của method alias;
  - `_validate`: validate theo phần.
- Toàn bộ phần link vẫn chạy nguyên như `build()`, nên kết quả khớp full rebuild ngay từ thiết kế.
- `IncrementalGraphBuilder` giữ cache qua các lần cập nhật. Mỗi lần cập nhật tạo một `_CachingGraphBuilder` mới, vì `PythonGraphBuilder` chỉ dùng được một lần.

**Tech Stack:** Python 3.11, tree-sitter, pytest.

**Spec:**
- `docs/superpowers/specs/2026-11-01-m1-w11-incremental-design.md` (thiết kế đã duyệt 01/11).
- Nghiệm thu từ deliverables v2 M1-W11-1: `pytest tests/test_incremental.py` PASS.

## Global Constraints

- **Output của `PythonGraphBuilder.build` không được đổi một byte nào** (spec §2 anti-goal, §6). Graph của `tests/fixtures/sample_repo` sau Task 2 phải có cùng sha256 với trước Task 2.
- CI: `python -m pytest -m "not hf and not docker" -q --deselect tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory` phải xanh. Test bị loại là lỗi có từ trước, đã ghi trong plan ranking.
- Chỉ static resolver. Truyền `scip` hoặc `lsp` thì báo `ValueError("incremental update supports the static resolver only; run a full build")`.
- Cache chỉ nằm trong bộ nhớ.
- **Người dùng tự commit.** Mỗi task kết thúc bằng danh sách file. Nhánh `m1/w11-incremental`, mỗi PR khoảng 300 dòng diff trở xuống (Task 1–2 là PR1, Task 3–4 là PR2 nếu vượt). Reviewer là M2.
- **Không sửa `src/` khi retrieval Task 6 của plan ranking đang chạy:** mỗi worker của run nạp lại source. Kiểm `.superpowers/sdd/2026-11-01-m1-w11-graph-ranking/task6-step1-retrieval.log` đã xong rồi mới làm Task 2.

## Review Focus

1. **Hai lần cập nhật liên tiếp:** phần link sửa trực tiếp `properties` của node (`symbol_aliases` trong `method_aliases.py:93`, `resolution_status` của Import trong `_link_imports`). Nếu node trong cache bị sửa theo, lần cập nhật thứ hai sẽ gắn alias trùng → Task 3, test `[two_updates]`.
2. **`graph_version` ghi sẵn trong node từ cache:** node được ghi version tại lúc tạo. Nạp lại từ cache mà không cập nhật version thì document không qua được validate → Task 3, mọi test G3.
3. **File lỗi parse** vẫn phải có File node với `parse_status = "failed"` và có mục trong `skipped_failed_files`, cả khi nạp từ cache → Task 3, test `[failed_file_cached]`.
4. **Edge treo khi validate theo phần:** edge lấy từ cache trỏ tới node đã bị xóa phải bị bắt → Task 1, test `test_trusted_edge_to_missing_node_still_fails`.
5. **File đổi tên** (xóa đường dẫn cũ, thêm đường dẫn mới, cùng nội dung): khóa cache có đường dẫn nên phải trích xuất lại, không được dùng lại node mang id của đường dẫn cũ → Task 3, test `[rename_file]`.

---

### Task 1: Validate theo phần trong `validate_graph_document`

**Files:**
- Modify: `src/vgar/contracts/schema.py:111-264`
- Test: `tests/test_graph_schema.py`

**Interfaces:**
- Produces: `validate_graph_document(document, *, trusted_ids: frozenset[str] = frozenset()) -> None`.
  - Node hoặc edge có `id` thuộc `trusted_ids` được **bỏ qua phần kiểm field**:
    - node: `repo_key`, `name`, `qualified_name`, `properties` là Mapping, `path` và `range` của node có nguồn hoặc Module nội bộ;
    - edge: `confidence`, `provenance`, `properties`.
  - **Phần kiểm cấu trúc luôn chạy cho mọi item:**
    - id không rỗng và không trùng;
    - `type` hợp lệ;
    - đúng 1 Repository;
    - `graph_version` khớp document;
    - đầu mút edge tồn tại và đúng cặp loại;
    - không self-loop;
    - không có chu trình CONTAINS;
    - `candidate_count` của CallSite khớp số edge CALLS.
  - Mặc định `frozenset()` cho kết quả y như cũ.

- [ ] **Step 1: Viết test**
  - `test_trusted_node_skips_field_checks`: lấy document hợp lệ từ `PythonGraphBuilder(...).build(sample_repo)`, xóa `name` của một Function. `validate_graph_document(doc, trusted_ids=frozenset({id}))` không raise. Gọi không có `trusted_ids` thì raise `GraphValidationError` có chuỗi `".name must be a non-empty string"`.
  - `test_trusted_edge_to_missing_node_still_fails` (Review Focus 4): thêm một edge CALLS trỏ tới `"missing"`, id của edge nằm trong `trusted_ids` → vẫn raise, có chuỗi `"target_id does not exist"`.
  - `test_trusted_items_still_need_matching_graph_version`: đổi `graph_version` của một node được trust → raise.
- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_graph_schema.py -q -k trusted`. Kỳ vọng: FAIL, `TypeError: unexpected keyword argument 'trusted_ids'`.
- [ ] **Step 3: Implement.** Bọc phần kiểm field bằng `if node_id not in trusted_ids` hoặc `if edge_id not in trusted_ids`. Giữ nguyên thứ tự và nội dung thông báo lỗi.
- [ ] **Step 4: Chạy lại.** `python -m pytest tests/test_graph_schema.py tests/test_graph_builder.py tests/test_graph_builder_robustness.py -q`. Kỳ vọng: PASS.
- [ ] **Step 5: Bàn giao.** Danh sách file: `src/vgar/contracts/schema.py`, `tests/test_graph_schema.py`. `contracts/schema.py` không có trong bảng sở hữu §1.4; vì là schema của graph nên coi là của M1, và ghi điểm này vào mô tả PR.

### Task 2: Thêm hook vào builder, không đổi hành vi

**Files:**
- Modify: `src/vgar/graph/builder.py` (`build()`: gọi `self._validate(document)` thay cho `validate_graph_document(document)`; truyền `parse=self._parse_python_ast` cho `annotate_method_aliases`; thêm hai method)
- Modify: `src/vgar/graph/method_aliases.py:31,47` (tham số `parse`)
- Test: `tests/test_graph_builder.py`

**Interfaces:**
- Produces: `PythonGraphBuilder._validate(self, document: dict) -> None`, mặc định gọi `validate_graph_document(document)`.
- Produces: `PythonGraphBuilder._parse_python_ast(self, root: Path, path: str) -> ast.Module`. Hàm làm đúng như dòng 47 hiện tại, `ast.parse((root / path).read_bytes(), filename=path)`, và để `SyntaxError`/`UnicodeError` bay ra ngoài cho người gọi bắt.
- Produces: `annotate_method_aliases(root, nodes, parse: Callable[[Path, str], ast.Module] | None = None)`. Khi `None`, hành vi như cũ.

- [ ] **Step 1: Ghi baseline.** Trước khi sửa, chạy lệnh sau và lưu kết quả vào ledger:
  ```
  python -c "import hashlib,json;from pathlib import Path;from vgar.graph.builder import PythonGraphBuilder as B;d=B(repo_key='demo/vgar-fixture',repository_revision='fixture-revision').build(Path('tests/fixtures/sample_repo'));d['statistics'].pop('build_time_ms');print(hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest())"
  ```
- [ ] **Step 2: Viết test** `test_build_uses_overridable_hooks`. Tạo lớp con của `PythonGraphBuilder`, ghi lại các lần gọi `_validate` và `_parse_python_ast`, rồi build `TYPED_REPOSITORY`. Kiểm `_validate` được gọi đúng 1 lần, và `_parse_python_ast` được gọi cho mọi path có node Class hoặc Method.
- [ ] **Step 3: Chạy test.** Kỳ vọng: FAIL, hook không được gọi.
- [ ] **Step 4: Implement** các hook như phần Interfaces.
- [ ] **Step 5: Kiểm.** Chạy lại lệnh ở Step 1, kỳ vọng ra **đúng cùng hash**. Chạy `python -m pytest tests/test_graph_builder.py tests/test_graph_builder_robustness.py tests/test_graph_retrieval.py -q`, kỳ vọng PASS.
- [ ] **Step 6: Bàn giao.** Danh sách file: `builder.py`, `method_aliases.py`, `tests/test_graph_builder.py`.

### Task 3: `IncrementalGraphBuilder`, các test G3, G4, G5

**Files:**
- Create: `src/vgar/graph/incremental.py`
- Create: `tests/test_incremental.py`

**Interfaces:**
- Consumes:
  - `_validate`, `_parse_python_ast` (Task 2);
  - `validate_graph_document(..., trusted_ids=...)` (Task 1);
  - `RESOLVER_PROFILE` (`builder.py`).
- Produces:
  - `IncrementalGraphBuilder(repo_key: str, repository_revision: str, *, source_roots=None, scip=None, lsp=None)`. Nếu `scip` hoặc `lsp` khác `None` thì báo lỗi theo Global Constraints.
  - `.build(root) -> dict`: lần đầu, cache rỗng.
  - `.update(root) -> tuple[dict, UpdateSummary]`.
  - `UpdateSummary` (dataclass, frozen) có các field:
    - `changed_files: tuple[str, ...]`, `added_files: tuple[str, ...]`, `deleted_files: tuple[str, ...]`
    - `cache_hits: int`, `total_files: int`
    - `extract_seconds: float`, `validate_seconds: float`, `total_seconds: float`
    - `affected_node_count: int` (Task 4 điền số; Task 3 để 0)

**Cách làm (các quyết định người làm không tự suy ra được):**
- **Khóa cache:** `(relative_path, sha256(bytes), RESOLVER_PROFILE)`.
- **Giá trị cache** là `_FileRecord`, ghi lại từ lúc **bắt đầu** `_extract_file` (lấy độ dài các list trước khi gọi `super()._extract_file`), gồm:
  - `nodes`, `edges`, `calls`, `classes`: phần slice thêm vào;
  - `index_writes`: lấy bằng cách override `_set_index`, ghi `(tên chỉ mục, key, value)`. Tên chỉ mục là một trong `symbols_by_qualified_name`, `scope_tables`, `scope_parents`, `unmodified_parameters`, `typed_parameters`, tra theo identity của dict;
  - `module`: `(module_name, _ModuleState)` nếu `self.modules[module_name]` đổi identity, ngược lại là `None`;
  - delta của `skipped_overload_count` và `renamed_duplicate_count`;
  - các mục mới của `skipped_failed_files`.
- **Lưu vào cache bản sạch:** chép node và edge ở hai tầng, `{**item, "properties": dict(item["properties"])}`, **ngay sau khi trích xuất**, trước khi phần link chạy.
- **Khi nạp lại từ cache:**
  - chép hai tầng thêm một lần nữa;
  - đặt `graph_version` của mọi item bằng `self.graph_version` hiện tại;
  - nối vào `self.nodes`, `self.edges`, `self.nodes_by_id`, `self.calls`, `self.classes`;
  - ghi lại `index_writes` theo đúng thứ tự;
  - gán module, cộng các bộ đếm.

  Việc nạp diễn ra trong chính vòng lặp `for file_path in python_files` của `build()`, nên thứ tự giữ đúng như full build.
- **Cache cây `ast`** cho `_parse_python_ast`, khóa `(path, sha256(bytes))`. Cây chỉ được đọc, không bị sửa.
- **`trusted_ids`** của `_validate` là id của mọi node và edge được nạp từ cache. Item mới trích xuất và mọi edge do phần link tạo ra đều được validate đầy đủ.
- File không còn trên đĩa thì bị xóa khỏi cả hai cache.

- [ ] **Step 1: Viết test.** Dùng helper `_write(root, files: dict[str, str | None])`, trong đó `None` nghĩa là xóa file. Helper `_full(root)` là `PythonGraphBuilder(...).build(root)`. Helper `_normalized(doc)` trả về `json.dumps(doc, sort_keys=True)` sau khi bỏ `statistics.build_time_ms`. Mỗi test G3: `inc.build(root)` → sửa file → `doc, _ = inc.update(root)` → `assert _normalized(doc) == _normalized(_full(root))`. Các trường hợp tham số hóa:
  - `[modify]`: sửa thân hàm;
  - `[add_file]`: thêm file có hàm được gọi từ file cũ;
  - `[delete_file]`;
  - `[rename_function]`: đổi tên hàm có caller;
  - `[move_import]`: `from a import f` → `from b import f`;
  - `[name_loses_uniqueness]`: thêm `def helper()` ở `src/x.py`, trong khi `src/y.py` gọi `helper()` mà không import;
  - `[duplicate_module_order]`: `src/a.py` và `lib/a.py` với `source_roots=("src", "lib")` cho cả hai builder, sửa `lib/a.py`;
  - `[two_updates]` (Review Focus 1): class có method alias `alias = impl`, cập nhật hai lần liên tiếp với hai thay đổi khác nhau, cả hai lần đều khớp full rebuild;
  - `[failed_file_cached]` (Review Focus 3): một file lỗi cú pháp không đổi, sửa một file khác;
  - `[rename_file]` (Review Focus 5): đổi `src/a.py` thành `src/b.py`, giữ nguyên nội dung.

  Các test còn lại:
  - **G4** `test_incremental_relinks_callers_when_callee_deleted`: xóa hàm được gọi từ file khác → không còn edge CALLS nào tới id cũ, và document khớp full rebuild;
  - **G5** `test_incremental_noop_keeps_version_and_hits_cache`: update khi không có gì đổi → `graph_version` giữ nguyên, `cache_hits == total_files`, các tuple file đổi, thêm, xóa đều rỗng, document khớp lần trước;
  - **G5b** `test_incremental_rejects_scip_and_lsp`: `IncrementalGraphBuilder(..., lsp=object())` → `ValueError` có chuỗi `"static resolver only"`.
- [ ] **Step 2: Chạy test.** `python -m pytest tests/test_incremental.py -q`. Kỳ vọng: FAIL, `ModuleNotFoundError: vgar.graph.incremental`.
- [ ] **Step 3: Implement** `src/vgar/graph/incremental.py` theo phần "Cách làm".
- [ ] **Step 4: Chạy lại.** Kỳ vọng: tất cả PASS. Nếu một trường hợp G3 lệch, in diff của node và edge đầu tiên khác nhau, rồi dùng superpowers:systematic-debugging. **Không** được nới cách chuẩn hóa để test qua.
- [ ] **Step 5: Bàn giao.** Danh sách file: `incremental.py`, `tests/test_incremental.py`.

### Task 4: Số liệu cho U1 (node bị ảnh hưởng, thời gian)

**Files:**
- Modify: `src/vgar/graph/incremental.py`
- Test: `tests/test_incremental.py`

**Interfaces:**
- Produces: `UpdateSummary.affected_node_count`. Đây là số id node thuộc một trong các nhóm sau, khi so document trước với document sau:
  - node được thêm hoặc bị xóa;
  - node là đầu mút của một edge có trong lần này mà không có ở lần trước, hoặc ngược lại. Hai edge được coi là cùng một edge khi trùng bộ `(type, source_id, target_id)`.

  Tính **sau khi** đã ghi `total_seconds`, để thời gian so sánh không lẫn vào số đo.
- Produces: `extract_seconds` gồm cả thời gian nạp từ cache; `validate_seconds` là thời gian của `_validate`.

- [ ] **Step 1: Viết test**
  - `test_summary_counts_files_and_cache_hits`: repo 3 file, sửa 1, thêm 1, xóa 1 → mỗi tuple có đúng 1 path, `cache_hits == 1`, `total_files == 3`.
  - `test_affected_nodes_cover_changed_function_and_its_caller`: `a.py` gọi `b.f`; đổi tên `b.f` thành `b.g` và sửa caller → `affected_node_count` ≥ 3 (node cũ, node mới, CallSite của caller). Với G5 thì `affected_node_count == 0`.
  - `test_summary_timings_are_consistent`: `0 <= extract_seconds <= total_seconds` và `0 <= validate_seconds <= total_seconds`.
- [ ] **Step 2: Chạy test.** Kỳ vọng: FAIL ở các assert về `affected_node_count`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy file test incremental, rồi chạy cả suite** theo lệnh CI ở Global Constraints. Kỳ vọng: 0 failed. Sau khi chạy, khôi phục `artifacts/sample_graph.db` bằng `git checkout -- artifacts/sample_graph.db`, vì suite ghi lại file này.
- [ ] **Step 5: Đo nhanh để kiểm ước lượng** (không phải bảng U1, việc đó là W12). Trên `data/repositories/trees/pydata__xarray-8cc34cb412ba89ebca12fc84f76a9e452628f1bc`: build một lần, sửa nội dung một file trong **bản sao** của tree đặt ở thư mục scratch, rồi `update`. Ghi `total_seconds` so với thời gian full build vào ledger. Kỳ vọng nhanh hơn khoảng 10 lần trở lên. Nếu dưới 5 lần thì báo người dùng trước khi bàn giao.
- [ ] **Step 6: Bàn giao.** Danh sách file như Task 3. Mô tả PR ghi rõ độ phức tạp: phần parse là O(Δ), phần link là O(N) (spec §4.2).
