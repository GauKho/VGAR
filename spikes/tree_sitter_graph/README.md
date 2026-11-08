# Spike L1-1: tree-sitter-graph trên vgar-demo-shop (08/11/2026)

> **Đã đưa vào pipeline.** Bộ luật đang được duy trì nằm ở `src/vgar/graph/tsg/python.tsg`; phần chạy
> và ghép fact nằm ở `src/vgar/graph/tsg_extractor.py` và `PythonGraphBuilder(tsg=...)`. Để bật:
> `scripts/build_graph.py --tsg-executable ... --tsg-tree-sitter-dir ...`, hoặc đặt biến
> `VGAR_TSG_EXECUTABLE` + `VGAR_TSG_TREE_SITTER_DIR`. Thư mục spike này chỉ giữ lại làm bằng chứng
> đối chiếu với builder.

**Mục tiêu:** xác nhận tree-sitter-graph chạy được trên máy Windows của nhóm. Luật `python.tsg` phải sinh ra
Class, Function, Method, CallSite, `HAS_METHOD`, `HAS_CALLSITE` khớp với `PythonGraphBuilder`, kèm thêm
GlobalVariable và Field mà builder chưa có.

**Kết quả: ĐẠT.** Khớp 100% với builder trên cả vgar-demo-shop lẫn `pydata__xarray-4629`.

## Kết quả

Khóa so sánh là (loại, path, tên, dòng bắt đầu); với cạnh là (loại, path, tên nguồn, tên đích, dòng đích).
Builder chạy không bật SCIP/LSP.

| Loại | demo-shop (13 file): TSG = builder | xarray-4629 @ `a41edc7b` (149 file): TSG = builder | Lệch |
|---|---|---|---|
| Class | 4 | 322 | 0 |
| Function (gồm Test cấp module) | 19 | 1703 | 0 |
| Method (gồm Test trong class) | 3 | 2833 | 0 |
| CallSite | 46 | 32018 | 0 |
| `HAS_METHOD` | 3 | 2833 | 0 |
| `HAS_CALLSITE` | 46 | 32018 | 0 |
| GlobalVariable (mới) | 5 | 358 | 0 khi so với `ast` cùng định nghĩa |
| Field (mới) | 12 | 489 | 0 khi so với `ast` cùng định nghĩa |

Builder chưa có GlobalVariable và Field, nên hai loại này được kiểm tra chéo bằng một script `ast` độc lập
dùng cùng định nghĩa:
- **GlobalVariable:** `Assign`/`AnnAssign` có target là một `Name` nằm trực tiếp dưới module.
- **Field:** `AnnAssign` trong thân class, hoặc `self.x = ...` trong method (không tính def/lambda lồng bên trong).

`self._quantities[sku] = ...` bị bỏ qua đúng, vì đó là gán vào phần tử chứ không phải khai báo field.

**Muốn khớp hoàn toàn với builder, luật phải bắt chước đúng cách `_walk_scope` duyệt cây:**
1. Builder bỏ qua các stub `@overload` (`builder.py:475`). Luật đánh dấu chúng `overload = "yes"`.
   xarray có 7 stub như vậy.
2. Builder gán type `Test` cho method test nằm trong class. `compare.py` coi những node này là Method.

**Lỗi builder tìm ra nhờ spike (đã sửa 08/11):** `_walk_scope` có đi vào thân `if`/`for`/`while`/`try`/`with`,
nhưng **không** đi vào `else`/`elif`/`except`/`finally`. Vì vậy trên xarray builder bỏ sót 9 def/class và
35 lời gọi bên trong chúng. Ví dụ:
- `nanmedian` (`core/dask_array_compat.py:65`);
- class `Panel` (`core/pdcompat.py:49`);
- `func` (`core/computation.py:689`);
- `wrapped_func` (`core/common.py:50, 89`).

Bản sửa nằm ở `builder.py` (vòng lặp "Conditional definitions"), kèm test
`test_definitions_in_else_elif_except_finally_branches_are_extracted`. Các số ở bảng trên là sau khi sửa.
Trước khi sửa, bảng là Class 321, Function 1695, CallSite 31983; khi đó luật phải có thêm một bước gán
"Unwalked" để khớp với builder.

**Giới hạn còn lại:** một decorator gồm cả `@overload` lẫn `@typing.overload` sẽ làm luật lỗi (gán thuộc tính
hai lần). Chưa đo riêng thời gian chạy TSG: cả lần chạy xarray, gồm TSG
(149 lần gọi CLI) và builder, mất khoảng 26 giây.

## File

| File | Nội dung |
|---|---|
| `python.tsg` | Luật tree-sitter-graph cho grammar `tree-sitter-python` v0.23.6 |
| `compare.py` | Chạy CLI trên từng file `.py`, đọc JSON, lọc node "Discard"/`@overload`, so với `PythonGraphBuilder`, ghi `report.json` |
| `ast_check.py` | Kiểm tra chéo GlobalVariable/Field trong `report.json` bằng `ast` |

## Những điều học được về tree-sitter-graph

- **Điều kiện `if` chỉ nhận giá trị lấy từ capture.** Giá trị đọc từ biến kế thừa (`inherit`) không dùng được trong
  điều kiện; dùng sẽ báo lỗi `Expected local value`. Cách làm trong spike:
  - phân biệt Method với Function bằng chính pattern của query;
  - lời gọi nằm ngoài def được gắn vào node "Discard" của file, rồi bước chuẩn hóa lọc bỏ.
- **Mỗi file là một graph riêng.** Id node là số thứ tự trong từng file, nên bước chuẩn hóa phải tự gán id theo
  hợp đồng `vgar:...` và tự nối các file với nhau.
- **Định dạng JSON** là một list node `{id, edges: [{sink, attrs}], attrs}`. Mỗi giá trị có dạng
  `{"type": "string", "string": ...}` hoặc `{"type": "int", "int": ...}`.

## Cài đặt trên Windows (các vướng mắc đã gặp)

1. **Lệch ABI của grammar.** tree-sitter-graph 0.12.0 link với `tree-sitter ^0.24`, chỉ đọc grammar ABI ≤ 14.
   `tree-sitter-python` v0.25.0 (bản repo đang dùng qua pip) là ABI 15, nên spike dùng **v0.23.6** (ABI 14).
   So `node-types.json` của hai bản: tên node và field trùng nhau, chỉ khác là v0.23.6 có thêm `except_group_clause`.
2. **Cần trình biên dịch C**, cả lúc build lẫn lúc chạy (loader biên dịch grammar lần đầu rồi cache vào
   `TREE_SITTER_LIBDIR`). Máy không có Windows SDK, nên MSVC không link được. Cách đã dùng:
   **WinLibs GCC 16.2.0 UCRT** (portable) + toolchain Rust `stable-x86_64-pc-windows-gnu`.
3. Nếu build bằng MSVC trong Git Bash, `/usr/bin/link` sẽ che mất `link.exe`.

## Chạy lại

```bash
MINGW=/d/tools/winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r3/mingw64/bin
export PATH="$MINGW:$PATH" CC=gcc
cargo +stable-x86_64-pc-windows-gnu install --features cli tree-sitter-graph --version 0.12.0 --locked --root <TSG>

git clone https://github.com/tree-sitter/tree-sitter-python <GRAMMARS>/tree-sitter-python
git -C <GRAMMARS>/tree-sitter-python checkout v0.23.6
# <TSDIR>/config.json = {"parser-directories": ["<GRAMMARS>"]}

python spikes/tree_sitter_graph/compare.py --repo D:/kltn/vgar-demo-shop/vgar-demo-shop \
  --tsg-exe <TSG>/bin/tree-sitter-graph.exe --tree-sitter-dir <TSDIR> --out <OUT>

# xarray-4629 tại base commit của task
git init <REPOS>/pydata__xarray-4629 && cd <REPOS>/pydata__xarray-4629
git remote add origin https://github.com/pydata/xarray.git
git fetch --depth 1 origin a41edc7bf5302f2ea327943c0c48c532b12009bc && git checkout FETCH_HEAD
```
