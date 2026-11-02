# Thiết kế: cập nhật graph tăng dần (M1-W11-1)

> **Ngày:** 01/11/2026 · **Người soạn:** người dùng (đang giữ vai M1 và M3) cùng Claude Code
> **Trạng thái:** thiết kế đã thống nhất trong buổi brainstorm #4. Chờ người dùng duyệt tài liệu, sau đó viết plan.
> **Nguồn:**
> - deliverables v2, M1-W11-1 và M1-W12-1;
> - spec chia việc `2026-10-31-w11-w12-parallel-split-design.md` §2 (W11 ngày 4–5, W12 ngày 1–2), Phụ lục A (G3, G4, G5);
> - proposal §11 (`D:\kltn\proposal_vgar_mcp_final_corrected.md`).

## 1. Mục đích

Incremental update chỉ cần **đủ để chạy bảng U1 và trả lời proposal §11.3**: một lần cập nhật nhanh hơn full rebuild bao nhiêu, và kết quả có đúng không (người dùng chọn). Nó **không** được nối vào vòng repair, MCP server hay `vgar solve`.

Vì vậy hai yêu cầu chính là:
1. **Đúng tuyệt đối:** graph sau khi cập nhật phải giống hệt full rebuild trên cùng source (G3).
2. **Đo được:** có số liệu cold build, warm update, cache hit và node bị ảnh hưởng cho U1.

## 2. Goals, non-goals, anti-goals

**Goals**
- `pytest tests/test_incremental.py` PASS (tiêu chí nghiệm thu của v2).
- Một lần cập nhật có kết quả giống hệt full rebuild ở mọi loại thay đổi trong G3, kể cả trường hợp một tên mất tính duy nhất trên toàn repo.
- Cung cấp đủ số liệu cho `scripts/bench_incremental.py` (W12 ngày 2).

**Non-goals**
- Dùng trong vòng repair, agent hay MCP server.
- Lưu cache ra đĩa, hoặc dùng chung cache giữa các tiến trình.
- Hỗ trợ SCIP hoặc LSP.
- Link lại theo vùng ảnh hưởng, tức đúng O(Δ + Fanout) của proposal (xem §4.2).
- Sửa `src/vgar/graph/task_overlay.py`.

**Anti-goals** (những thứ làm thiết kế thất bại dù về kỹ thuật vẫn "chạy")
- Graph sau cập nhật khác full rebuild ở bất kỳ node hay edge nào mà không có lỗi báo ra.
- Bảng U1 hoặc báo cáo ngầm nói rằng phần link là O(Δ + Fanout).
- Làm đổi output của full build. Graph của `PythonGraphBuilder.build` phải giữ nguyên, nên `graph_version` và fixture hiện có không đổi.

## 3. Số đo nền (01/11, xarray 151 file, full build mất 6,0 giây)

Số đo lấy lúc máy đang chạy retrieval nền, nên tỉ lệ dùng được nhưng số tuyệt đối có nhiễu.

| Bước của `build()` | Tỉ lệ | Cache theo file được không? |
|---|---|---|
| `_extract_file` (tree-sitter) | 64% | Được |
| `annotate_method_aliases` (parse thêm bằng `ast` theo từng file, `method_aliases.py:45-47`) | 24% | Được, phần parse theo từng file |
| `validate_graph_document` | 5% | Không. Làm theo phần (§4.3) |
| Link (`_resolve_calls`, `_link_imports`, `_link_inheritance`, chỉ mục tên) | khoảng 5% | Không. Chạy lại toàn bộ (§4.2) |
| Các bước khác (hash, thống kê, discover) | khoảng 1% | — |

Ước lượng cho một lần cập nhật sửa 1 file: **khoảng 0,4 giây, nhanh hơn full build khoảng 14 lần.** Đây là ước lượng, bảng U1 sẽ đo thật.

## 4. Thiết kế đã chốt

### 4.1. Cache kết quả trích xuất theo từng file

- **Khóa:** `(đường dẫn tương đối, sha256 nội dung file, RESOLVER_PROFILE)`. Nếu `RESOLVER_PROFILE` đổi thì toàn bộ cache mất hiệu lực.
- **Giá trị:** mọi thứ `_extract_file` sinh ra cho file đó (node, edge cục bộ, trạng thái module, call record, class record, scope table, typed parameter, các lần ghi vào chỉ mục dùng chung), cộng phần kết quả parse `ast` của `annotate_method_aliases` cho file đó.
- **Khi cập nhật:**
  - file có khóa trùng → lấy lại từ cache (cache hit);
  - file đổi nội dung hoặc file mới → trích xuất lại;
  - file đã xóa → bỏ khỏi cache.
- **Thứ tự:** kết quả của các file phải được nạp lại **theo đúng thứ tự `_discover_python_files`** như full build. Builder có những xử lý phụ thuộc thứ tự: ghi đè chỉ mục khi trùng qualified name, giữ module cũ khi trùng tên module (`builder.py`, khoảng dòng 384–413), đổi tên định nghĩa trùng. Nạp sai thứ tự sẽ cho graph khác full build.
- **Vì sao cache theo file là an toàn (đã kiểm 01/11):** node id luôn chứa đường dẫn file (`builder.py:593`, `:670`), và việc đổi tên khi trùng id (`@definition:…`) chỉ xảy ra giữa các định nghĩa trong **cùng một file**. Vì vậy trích xuất một file gần như không đọc kết quả của file khác. **Ngoại lệ duy nhất** (phát hiện lúc implement): `ordinal` của edge Repository → File (rule `repository.file.v1`) bằng `len(self.modules)` tại thời điểm tới file đó, nên phải tính lại khi nạp từ cache. Phụ thuộc giữa các file chỉ nằm ở các lần **ghi** vào chỉ mục dùng chung (`symbols_by_qualified_name`, `self.modules`), và nạp lại theo đúng thứ tự là tái tạo được. Các bộ đếm (`renamed_duplicate_count`, `skipped_overload_count`) phải được lưu theo từng file rồi cộng lại.
- **Gợi ý:** builder đã có cơ chế snapshot và rollback cho từng file (`_index_changes`, quanh `builder.py:342-423`), dùng để gỡ phần của một file khi file đó lỗi. Có thể dùng chính cơ chế này để ghi lại phần đóng góp của từng file.
- **File lỗi parse** (`skipped_failed_files`) cũng được cache theo khóa như trên, để kết quả lần sau giống full build.
- Cache chỉ nằm trong bộ nhớ của một đối tượng Python.

### 4.2. Link lại toàn bộ (người dùng chọn)

- Sau khi nạp lại kết quả của mọi file, chạy lại **toàn bộ** các bước sau trên cả repo:
  - `_build_unique_symbol_index`
  - phần ghép của `annotate_method_aliases`
  - `_link_imports`
  - `_link_inheritance`
  - `_resolve_calls`

  Chạy đúng thứ tự như trong `build()`.
- Nhờ vậy lỗi C1 (chỉ mục tên duy nhất là toàn repo, nên thêm một hàm ở file X có thể đổi cách resolve call ở file Y không import X) tự hết, mà không cần theo dõi phụ thuộc.
- **Độ phức tạp trung thực:** phần parse là O(Δ). Phần link là O(N), đo được khoảng 5% thời gian full build trên xarray. Báo cáo U1 phải ghi đúng như vậy, và nói rõ speedup đến từ việc không parse lại file không đổi.

### 4.3. Validate theo phần (người dùng chọn)

Một lần cập nhật **không** gọi `validate_graph_document` trên cả document. Thay vào đó:
- **Kiểm schema** từng node và từng edge **mới hoặc đã đổi** so với graph của lần trước, dùng cùng luật schema với `validate_graph_document`.
- **Luôn kiểm toàn vẹn trên toàn graph** (tôi chọn). Đây là bước rẻ, chỉ tra tập hợp:
  - mọi `source_id` và `target_id` của edge đều có node;
  - không có node id trùng lặp.

  Bước này chặn trường hợp validate theo phần bỏ sót edge treo.
- Test G3 so với full rebuild, mà full rebuild thì vẫn validate cả document. Vì vậy độ đúng của validate theo phần cũng được kiểm gián tiếp.

### 4.4. `graph_version` và document

- `graph_version` được tính lại bằng `_calculate_graph_version` trên nội dung hiện tại, giống full build. Có file đổi thì version đổi. Không file nào đổi thì version giữ nguyên.
- Mọi node và edge mang `graph_version` mới, giống full build.
- `statistics` phải giống full build, trừ `build_time_ms`.

### 4.5. Phạm vi resolver

Nếu builder được tạo với `scip` hoặc `lsp` thì incremental **báo lỗi rõ ràng** (ví dụ `ValueError("incremental update supports the static resolver only; run a full build")`) **(tôi chọn)**. Không tự động chuyển sang full build mà không báo.

### 4.6. Số liệu cho U1

Mỗi lần cập nhật trả về, ngoài document, một bản tóm tắt gồm:
- số file đổi, thêm, xóa;
- cache hit = số file lấy từ cache / tổng số file;
- thời gian từng phần: trích xuất, link, validate, tổng;
- **node bị ảnh hưởng**, tính bằng cách so graph trước và sau: node được thêm, bị xóa, hoặc có edge vào/ra thay đổi. Con số này **chỉ để báo cáo**, không dùng để quyết định cập nhật.

## 5. Kiểm chứng (`tests/test_incremental.py`)

Fixture dùng repo nhỏ dựng trong `tmp_path`, theo cách `_build_files` trong `tests/test_graph_builder.py`. Mỗi test làm 3 bước: build lần đầu, sửa source, cập nhật. Sau đó so với `PythonGraphBuilder(...).build()` mới trên cùng source.

So sánh **document đã chuẩn hóa**: node và edge sắp theo id, bỏ `statistics.build_time_ms`. Mọi thứ còn lại phải bằng nhau, kể cả `graph_version`.

| ID | Trường hợp | Kỳ vọng |
|---|---|---|
| G3 `[modify]` | Sửa thân một hàm | Bằng full rebuild |
| G3 `[add_file]` | Thêm file mới có hàm được gọi từ file cũ | Bằng full rebuild |
| G3 `[delete_file]` | Xóa một file | Bằng full rebuild |
| G3 `[rename_function]` | Đổi tên một hàm có caller | Bằng full rebuild |
| G3 `[move_import]` | Chuyển một import sang module khác | Bằng full rebuild |
| G3 `[name_loses_uniqueness]` (C1) | Thêm hàm `helper` ở file X; file Y gọi `helper()` mà không import (trước đó resolve bằng fallback tên duy nhất) | Bằng full rebuild: edge heuristic của Y biến mất |
| G3 `[duplicate_module_order]` | Hai file có cùng tên module; sửa file thứ hai | Bằng full rebuild |
| G4 | Xóa hàm được gọi từ file khác | Không còn edge CALLS từ caller tới hàm đã xóa, không có edge treo |
| G5 | Gọi cập nhật khi không có file đổi | `graph_version` không đổi, cache hit = 100%, document bằng lần trước |
| G5b | Builder có cấu hình `scip` hoặc `lsp` | Báo lỗi theo §4.5 |

## 6. Ràng buộc

- Không đổi output của `PythonGraphBuilder.build`. Toàn bộ suite hiện có phải xanh mà không phải dựng lại fixture.
- Chạy được trong CI (`pytest -m "not hf and not docker"`), không cần mạng hay Docker.
- Các file được sửa thuộc quyền của M1: `src/vgar/graph/incremental.py` (mới), `src/vgar/graph/builder.py`, `src/vgar/graph/method_aliases.py`, `tests/test_incremental.py` (mới).
- Mỗi PR khoảng 300 dòng diff trở xuống. Nếu vượt thì tách: (1) tách phần trích xuất và phần link trong builder, chưa đổi hành vi; (2) thêm incremental cùng các test.

## 7. Để lại cho người làm

- Tên class và hàm. Gợi ý: `IncrementalGraphBuilder(repo_key, repository_revision, *, source_roots)`, có `build(root) -> dict` cho lần đầu và `update(root) -> tuple[dict, UpdateSummary]` cho các lần sau.
- Cách tách `build()` thành phần trích xuất và phần link mà không đổi kết quả. Phải giữ nguyên thứ tự gọi.
- Cấu trúc dữ liệu cụ thể của mục cache.
- Cách so "node hay edge đã đổi" để validate theo phần, ví dụ so bằng giá trị hoặc bằng hash từng item.
- Nếu `src/vgar/contracts/schema.py` chưa có hàm validate từng node hoặc edge thì tách hàm đó ra từ `validate_graph_document`, giữ nguyên luật. Phải để `validate_graph_document` dùng lại chính hàm này, để không có hai bộ luật khác nhau.
- Lặp lại bao nhiêu lần để đo p50 và p95 (thuộc `bench_incremental.py`, W12).

## 8. Quyết định của Claude (để người dùng kiểm khi đọc)

- Luôn kiểm toàn vẹn edge và node trên toàn graph, kể cả khi đã validate theo phần (§4.3).
- Gặp SCIP hoặc LSP thì báo lỗi, không tự chuyển sang full build mà im lặng (§4.5).
- Cache chỉ nằm trong bộ nhớ, không ghi ra đĩa (§4.1).
- Thêm hai trường hợp G3 ngoài danh sách trong spec: `name_loses_uniqueness` (C1) và `duplicate_module_order`, cùng test G5b (§5).
- Cache cả phần parse của `annotate_method_aliases`, vì bước này chiếm 24% thời gian full build (§3, §4.1).
