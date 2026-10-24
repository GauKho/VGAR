# M1-W9-2 — Mapping unified diff vào node baseline

Triển khai ngày23/10/2026, trong VGAR. Chỉ xử lý ảnh hưởng trực tiếp trên graph
baseline; chưa tính callers/tests impacted hoặc risk của tuần10.

## 1. Input, output và API

Code: `src/vgar/graph/impact.py`; contract đã chốt: `contracts/impact.py`.
Tests: `tests/test_impact.py`; fixtures source riêng: `tests/fixtures/m1_w9_impact/`.

```python
from pathlib import Path
from vgar.graph.impact import diff_to_nodes
from vgar.repair.patch import PatchPolicy

report = diff_to_nodes(
    raw_diff, document, Path(source_repo),
    patch_policy=PatchPolicy(allowed_paths=('app.py', 'other.py'), protected_paths=('tests',)),
)
print(report.canonical_json())
```

`raw_diff`: chuỗi UTF-8 unified diff nguyên bản; `document`: graph document ứng với
source baseline được caller chấp nhận; `source_repo`: snapshot source hiện hữu.
API chỉ đọc source/graph. Không generate/apply/run tests target hoặc tạo Git worktree.
Chính test harness mới ghi mapping JSON vào evidence riêng; API không ghi output file.

Output `ImpactReport`: changed/unmapped, hashes và actual parser limits;
impacted/risk luôn NOT_COMPUTED. COMPLETE mô tả đã xử lý hết mapping input,
không chứng minh map được tất cả thay đổi hay patch sửa đúng lỗi.

## 2. Flow xử lý

```text
raw diff + approved graph + baseline directory + PatchPolicy
   → graph schema / inventory / hash / byte-range validation
   → existing parser → _bind read-only exact source/offset/EOF check
   → changed blocks (context-only lines excluded)
   → smallest Function/Method/Class per changed baseline line
   → merge node evidence + preserve all unmapped reasons
   → recheck source/graph → ImpactReport
```

Mỗi source-backed range được kiểm tọa độ byte/dòng/cột và content hash; Function/
Method/Class không được có range rỗng, kể cả symbol không bị patch chạm. Inventory
Python theo discovery exclusions hiện hữu; File nodes phải bind toàn file bytes.
Filesystem links được phát hiện tại root/source inventory bị từ chối. Hash source
chỉ là inventory Python, không attestation toàn repo hoặc xác minh Git commit.
Caller phải cung cấp identity đáng tin; checksum không chứng minh tính xác thực.

`_bind` của parser repair được tái sử dụng để kiểm read-only, không gọi `apply_patch`.
Đây là dependency nội bộ: nếu M2 thay semantics/shape parser/binder thì phải kiểm
regression mapping. Predicted bytes của binder không được ghi vào source.

## 3. Quy tắc mapping

| Tình huống | Xử lý |
|---|---|
| Xóa/thay dòng trong symbol | Chọn symbol có byte-range nhỏ nhất giao với dòng baseline thực bị xóa/thay |
| Nested definitions | Không tự đánh dấu tất cả ancestors; dùng smallest range |
| Pure insertion | Dùng boundary byte baseline; chỉ map khi nằm strictly bên trong symbol |
| Insertion ở đầu/rìa/EOF ngoài symbol | NO_BASELINE_SYMBOL_AT_INSERTION, không gán sang hàm gần nhất |
| Xóa nguyên hàm | Giữ node/range baseline của hàm đã bị xóa |
| Module/import/blank-line change không có symbol | MODULE_LEVEL_CHANGE |
| Nhiều candidate nhỏ nhất cùng kích thước | AMBIGUOUS_BASELINE_SYMBOL, không đoán một ID |
| Cùng node nhiều blocks | Một changed entry, gộp spans; có replacement thì basis baseline_changed_lines |
| Block có nhiều node/phần ngoài node | Toàn bộ changed block giữ như supporting span cho từng node; unmapped giữ cùng block và reason |
| Context-only lines | Không thành changed spans, kể cả hunk context đi qua function khác |

Supporting spans giữ **full changed-block coordinates**, không tuyên bố là exact
sub-range của một symbol. Vì vậy một span có thể xuất hiện ở nhiều changed entries
và unmapped; không được cộng counts từ mọi entries để tính tổng patch size.
Hunk index bắt đầu từ1 trong từng file; ranges graph dùng UTF-8/end-exclusive.

**Decorator limitation:** graph builder hiện đặt decorator ngoài function range.
Thay decorator ở module level được giữ unmapped, không bịa ownership bằng semantic
inference. Test riêng chứng minh điều này; tests nested/UTF-8 kiểm body trong file
có decorator, không gọi đó là semantic decorator impact support.

Malformed diff, source/hash/range mismatch, hunk source sai, unsupported operations
hoặc path ngoài allowlist gây ValueError (GraphValidationError là subtype). Không
trả report COMPLETE cho các lỗi đó. Parser giữ nguyên modify-only: thêm/xóa hàm
trong file tồn tại khác với thêm/xóa/rename file chưa hỗ trợ.

## 4. Tự kiểm thử trên PowerShell

Các lệnh chạy từ VGAR, dùng interpreter sẵn có; không cài lại dependencies.

```powershell
# Vào repo và xác định interpreter để tránh biến $python rỗng.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = 'D:\Project\CAPSTONES\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Không tìm thấy interpreter' }

# Import source local và tránh plugin ngoài ảnh hưởng kết quả.
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONUTF8 = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'

# Chạy riêng mapping; tests dùng source copy tạm, không sửa fixture chuẩn.
& $python -B -m pytest tests/test_impact.py -k diff_to_nodes -q -p no:cacheprovider
$LASTEXITCODE

# Chạy schema + mapping và parser regression cùng nhau.
& $python -B -m pytest tests/test_impact.py tests/m2/w78/test_w78_patch.py -q -p no:cacheprovider
$LASTEXITCODE
```

Mong muốn exit0. Test tạo symlink thật có thể SKIP vì Windows không có developer
mode/quyền tạo link; phải đọc skip reason, không gọi nó là symlink runtime PASS.
Không nâng quyền hoặc thay Windows security settings chỉ để xóa một skip.

## 5. Evidence, lịch sử và phạm vi nghiệm thu

Root: `results/m1/w9/m1-w9-2/20261023-mapping/` (ignored).
Mỗi command record giữ argv/cwd/interpreter, UTC, monotonic duration, stdout/stderr,
exit và JUnit. Mỗi lần gọi mapper trong tests lưu UUID riêng bên dưới command root:
`input.diff`, `graph.json`, `mapping.json` hoặc `exception.json` có traceback.
Mapping report chứa graph/source/patch identity; source fixture và source variants
đọc được trong fixture files và tests. Không sử dụng model/gold patch SWE-bench.

- RED đầu:22 failures vì chưa có module. Console recorder lỗi cp1252 khi in Unicode
  sau khi đã lưu JSON; đã sửa stdout UTF-8, không xóa evidence này.
- GREEN đầu:17PASS/5FAIL do test đoán opaque ID thiếu module prefix; sửa assertion
  lấy ID của symbol từ graph document đã dựng độc lập, không đổi production IDs.
- GREEN tiếp:25PASS/1SKIP. Lint6findings đã sửa; parser/source guards không nới.
- Review độc lập phát hiện untouched symbol range rỗng: RED1FAIL1PASS; sửa kiểm
  nonempty mọi symbol; GREEN2PASS. Decorator ngoài range có test unmapped riêng.

Số liệu cuối và exclusions xem `docs/status/m1.md` và final_regression.json.
Full repository suite/qualified environment vẫn ghi riêng, không suy từ selected tests.
Review agent là code QA, không M3 approval. Ngoại lệ W9-1 không tự mở rộng W9-2.
Không commit/push, không sửa Task Status.md; dừng tại W9-2.
