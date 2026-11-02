# M2-W11-1 — Kiểm tra tương thích API bằng AST

Ngày triển khai: 02/11/2026. Base: `d018cca5`, nhánh `m3/w11-day5`.
Phạm vi: riêng M2-W11-1 theo plan M2 W11–W12 đã được người dùng duyệt.

## API và cách dùng

```python
from vgar.repair.api_check import check_api, with_api_risk

before = {"package/api.py": b"def public(value): return value\n"}
after = {"package/api.py": b"def public(value, option=None): return value\n"}
analysis = check_api(before, after, callers_in_repo=None)
assert analysis.status == "PASS"  # Thêm tham số có default là tương thích.
assert analysis.details["signature_changed"] == {"available": True, "value": True}

# impact_report phải được tạo cho đúng baseline và patch của hai snapshot này.
# enriched = with_api_risk(impact_report, analysis)
```

Chữ ký:

```python
check_api(before: Mapping[str, bytes], after: Mapping[str, bytes], *,
          callers_in_repo: Mapping[str, Sequence[str]] | None = None) -> CheckAnalysis
with_api_risk(report: ImpactReport, analysis: CheckAnalysis) -> ImpactReport
```

`CheckAnalysis` là dataclass nội bộ gồm `status`, tuple `reasons`, và `details`
JSON-ready. Contract evidence công khai `{status, reasons, details_ref}` sẽ được
nối ở **M2-W11-3**, chưa triển khai trong task này. Checker không đọc/ghi file,
không import hay thực thi source, decorator, default expression hoặc dependency
của repository đích. AST được compile để kiểm tra syntax/scope tĩnh (ví dụ tham
số trùng, `return` ngoài hàm), nhưng code object không được thực thi hay ghi ra đĩa.

Hai mapping phải chứa đầy đủ bytes của cùng phạm vi source muốn so sánh. Path
chỉ có ở baseline được hiểu là file bị xóa; chỉ có ở candidate là file mới.
Không dùng mapping thiếu file do đọc lỗi để đại diện cho một snapshot hợp lệ.
Path phải là repository-relative POSIX `.py`, normalized; không absolute,
traversal, dấu phân cách Windows hoặc `.git`. Nội dung phải là `bytes`.
Sai input boundary raise `ValueError`; lỗi syntax của source là kết quả `ERROR`.

## Quy tắc và kết quả

- Public theo `__all__` literal list/tuple; không có thì tên không bắt đầu `_`.
  Export bị bỏ khỏi `__all__` vẫn là removal dù implementation còn trong file.
- So module function/class và public method của public class, gồm constructor.
  Nested local function và private implementation không thuộc public surface.
- Xóa export/symbol: `FAIL`, reason `API_SYMBOL_REMOVED`.
- Thêm required parameter, bỏ/đổi thứ tự positional parameter, mất khả năng gọi
  keyword, mất default, mất keyword-only parameter hoặc `*args`/`**kwargs`:
  `FAIL`, reason `API_SIGNATURE_INCOMPATIBLE` với chi tiết từng trường hợp.
- Thêm optional parameter, sửa thân hàm/private: tương thích. Annotation hoặc
  giá trị default đổi được ghi nhận là signature change; không tự suy ra lỗi
  semantic type checking.
- Source parse lỗi: `ERROR/API_PARSE_ERROR`. Export động, re-export chưa resolve,
  public binding mơ hồ và declaration chưa hỗ trợ: `NOT_RUN`, kèm diagnostics.
- Alias/lambda/factory gán cho public name và constructor async/decorated chưa
  hỗ trợ được ghi unknown; không coi chúng là giá trị đã kiểm signature.
- Phạm vi rỗng: `NOT_RUN/API_EMPTY_SCOPE`; không hiểu là đã kiểm không có lỗi.
- Khi nhiều file có kết quả khác nhau: `ERROR > NOT_RUN > FAIL > PASS`. Những
  break đã tìm thấy vẫn có trong `changes`; unknown không bị che bởi partial FAIL.

`details` lưu `source_hashes` SHA-256 của raw bytes mỗi phía, paths, coverage,
changes theo symbol, diagnostics và `signature_changed`. Thứ tự ổn định, không
timestamp hay UUID trong analysis. CRLF và Unicode được parse bằng AST; raw hash
vẫn phân biệt đúng bytes nguồn. `coverage=COMPLETE` chỉ nói đến phạm vi AST đã
cung cấp, không có nghĩa đo toàn bộ API runtime hoặc toàn repository.

`callers_in_repo=None` là chưa cung cấp; `{}` là đã cung cấp tập rỗng. References
được copy sang diagnostic riêng và không làm điều kiện cho verdict: không thấy
caller không cho phép bỏ qua API break. Đây không phải test coverage.

## Adapter risk và bàn giao M1

`with_api_risk` trả bản sao đã validate bằng `ImpactReport`; chỉ thay/thêm phần
tử `risk.features[name="signature_changed"]`, giữ identity, traversal, limits và
các feature khác. Không mutate report hoặc analysis đầu vào.

- Đã phân tích đủ: feature `available=true`, `value` là bool, kể cả measured false.
- Unknown/error: `available=false`, `value=null`, reason `NOT_COMPUTED` theo enum
  contract hiện tại. Nguyên nhân cụ thể nằm trong analysis, không thêm enum/schema.

**Caller phải bind analysis vào đúng baseline, phạm vi và applied patch của report.**
Adapter không tự chứng minh binding này từ hai object tùy ý. M1 nhận interface,
analysis và adapter để nối vào producer/consumer impact chung. Task này không sửa
`graph/**`, `contracts/impact.py`, graph MCP server hoặc payload mặc định W9.
Vì vậy gọi impact API cũ trực tiếp vẫn có thể thấy `signature_changed=NOT_COMPUTED`.

## Kiểm chứng và artifact

```powershell
$vgarPython = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VGAR_GRAPH_BACKEND = 'demo'
$vgarTemp = Join-Path $env:TEMP ('vg-api-' + [guid]::NewGuid().ToString('N').Substring(0,8))
& $vgarPython -B -m pytest tests/m2/w1112/test_api_check.py -q -p no:cacheprovider --basetemp $vgarTemp
```

Không cần Docker, GPU, model hoặc dataset. Test V1–V5 và các boundary liên quan
nằm trong file trên; test adapter dùng report tổng hợp, không sửa fixture DB.
Kết quả chạy thực tế, review và các giới hạn cuối cùng được ghi trong
`docs/status/m2.md`; không coi số test dự kiến là số đã PASS.

Evidence của phiên triển khai:
`results/m2/w1112/m2-w11-1-20261102-api-check/` (gitignored). Gồm baseline fingerprint,
RED/GREEN và regression logs/JUnit, JSON demo từ checker thật, review, preservation
audit và hướng dẫn tiếp tục. Demo là synthetic contract example, không phải
SWE-bench/model result.

Chưa nối structural/evidence/A3 hoặc chạy task tiếp theo; không commit/push.
