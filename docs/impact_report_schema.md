# ImpactReport — contract M1-W9-1

Ngày lập: 23/10/2026. **Được chấp thuận kỹ thuật theo ủy quyền người dùng cho M1-W9-1**.
Người dùng đảm nhiệm M1/M2 và miễn review M3 riêng task này; không ghi M3 đã approve.
Receipt: [review và nghiệm thu](reviews/2026-10-23-m1-w9-1-close-review.md).
Định nghĩa duy nhất: `src/vgar/contracts/impact.py`. Tests: `tests/test_impact.py`.
Đây là DTO; chưa triển khai `diff_to_nodes`, reverse impact, risk calculation hoặc MCP.

## 1. Mục đích và cách dùng

M1 cung cấp một ngôn ngữ chung để M2/M3 đọc phần code bị patch tác động trực tiếp,
phần chưa map và identity của inputs. M1-W9-2 mới kiểm graph/source và tạo report
từ diff. W10 mới tính impacted callers/tests và risk. Không import producer mới
trước khi contract được chốt theo điều kiện nghiệm thu áp dụng. Contract này đã
được review theo ngoại lệ người dùng; trạng thái commit/merge ghi riêng trong receipt.

```python
from vgar.contracts.impact import ImpactReport
report = ImpactReport.model_validate(payload)
portable = report.canonical_json()
reloaded = ImpactReport.model_validate_json(portable)
```

Mọi model strict, từ chối extra fields; bool không phải int. `ValidationError`
nghĩa dữ liệu sai cấu trúc, không phải một report mapping thành công.
Không thêm `schema_version`. Ngày ghi nhận không là bằng chứng review đúng ngày 1–2.

## 2. Fields và ngữ nghĩa

| Field | Kiểu / yêu cầu | Ý nghĩa |
|---|---|---|
| repo_key | string có ký tự không trắng | Namespace repo; node IDs opaque, không tự parse ID |
| repository_revision | string không trắng | Commit hoặc fixture revision được caller phê duyệt; DTO không chứng minh Git checkout |
| graph_version | string không trắng | Snapshot ID do graph producer tạo, không buộc là SHA của JSON file |
| graph_hash | sha256: + 64 hex lowercase | `canonical_hash(document)` trên graph document đầy đủ |
| source_hash | cùng định dạng | `canonical_hash({relative_python_path: byte_sha256, ...})`; byte_sha256 có prefix sha256: |
| patch_hash | cùng định dạng | SHA-256 **bytes diff gốc** UTF-8, có prefix sha256:; không normalize newline/fences |
| source_scope | python-inventory | Source inventory Python theo scope discovery của graph; không attestation toàn repo/config/test environment |
| changed | list ChangedNode, bắt buộc | Symbol baseline có bằng chứng changed spans; unique node_id |
| unmapped | list UnmappedChange, bắt buộc | Mọi changed span/phần span không map, có path/reason; không bỏ đi |
| impacted | status NOT_COMPUTED, items=[] | Chưa tính gián tiếp; không phải kết luận không có caller ảnh hưởng |
| risk | status NOT_COMPUTED, features=[] hoặc unavailable features | Chưa đo risk, không gán risk=0 |
| limits | MappingLimits, default công khai | Giới hạn mapping/parser và completeness của mapping, không của repair |

Inventory phải theo discovery profile của graph được pin; producer lưu profile/scope
cùng graph artifact. Hash dictionary inventory dùng UTF-8 exact bytes của từng file,
đường dẫn POSIX relative. Không hash text đã đổi CRLF hay source archives normalize.
Canonical JSON: sort object keys, UTF-8 không ASCII escaping, không whitespace,
không NaN/Infinity, arrays giữ thứ tự. `canonical_hash` dành cho dict; patch hash
phải dùng bytes trực tiếp, không gọi canonical_hash lên patch string.

`canonical_json()` của report sort changed theo path/node ID, supporting spans theo
thứ tự fields coordinates, unmapped theo JSON sorted keys; sort features theo name
và limits reasons/unsupported_operations. Không mutate model. Hash graph document
vẫn giữ node/edge array order; không tuyên bố mọi graph semantic tương đương có
cùng graph_hash khi producer thay thứ tự arrays.

### ChangedNode và ChangeSpan

- `node_id`: ID baseline; `path`: normalized relative POSIX; `kind`: Function/Method/Class.
- `source_range`: start_line/end_line >=1, columns >=0 byte UTF-8, end exclusive,
  nonempty. Đây là range symbol baseline, không range snippet đã đánh số lại.
- `basis`: `baseline_changed_lines` hoặc `insertion_in_existing_scope`.
- `spans`: list không rỗng, không duplicate; `hunk_index` >=1 **trong file đó**.
- Mỗi span có old_start/old_count/new_start/new_count: đếm riêng changed block,
  không gồm context-only lines. Start của phía count>0 bắt đầu từ1; count=0 cho
  phép start=0 (vị trí chèn/xóa trước dòng đầu). Phía rỗng dùng boundary sau
  dòng start như convention unified diff. Hai counts không được cùng0.
- Một node chỉ có một entry; gộp mọi supporting span vào đó. Một changed block
  đụng nhiều symbols có thể cần chia spans; producer W9-2 quyết định theo lines
  thật, không đánh dấu function chỉ vì hunk context đi qua nó.

DTO kiểm cấu trúc; **không tự xác minh ID/range có trong graph**, không chứng minh
spans đã phủ hết raw patch hay counts khớp hunk. Các kiểm đó thuộc producer W9-2
và parser hiện có; không được coi `model_validate` PASS là diff apply PASS.

### UnmappedChange và limits

`UnmappedChange` gồm path, span, reason thuộc một trong:
NO_BASELINE_SYMBOL_AT_INSERTION, MODULE_LEVEL_CHANGE, NO_MATCHING_BASELINE_SYMBOL,
AMBIGUOUS_BASELINE_SYMBOL, UNSUPPORTED_SOURCE, MAPPING_LIMIT.
Thêm function mới có thể chưa có node baseline, phải giữ unmapped thay vì bịa ID.
Xóa function dùng node cũ. Thêm/xóa/rename **file** vẫn bị parser repair từ chối;
parser error không được đổi thành một mapping report COMPLETE.

`limits.scope=baseline-symbol-mapping`; COMPLETE cho phép unmapped có lý do:
đã xử lý hết input nhưng có phần không map. PARTIAL phải có reasons; truncated
không được đi cùng COMPLETE. Default parser caps 262144 bytes/5files/500changed
lines, unsupported operations add_file/delete_file/rename_file; caller producer
phải ghi **actual PatchPolicy** thay defaults nếu dùng policy khác. Default
không chứng minh parser đã chạy. Không có cap riêng cho mapping ở W9-1.

Risk features nếu khai báo: name, available=false, value=null, reason=NOT_COMPUTED.
Không có scoring hoặc risk threshold ở DTO hiện tại. W10 mở rộng status/types
phải qua contract review, không tự dùng fields mới trong consumer.

## 3. Ví dụ addition chưa có baseline symbol

Hashes dưới đây synthetic để minh họa schema, không là evidence graph/diff thật.

```json
{
  "repo_key": "demo/project",
  "repository_revision": "fixture-v1",
  "graph_version": "fixture-graph-v1",
  "graph_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "source_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "patch_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "changed": [],
  "unmapped": [{
    "path": "app.py",
    "span": {"hunk_index": 1, "old_start": 3, "old_count": 0, "new_start": 4, "new_count": 2},
    "reason": "NO_BASELINE_SYMBOL_AT_INSERTION"
  }]
}
```

## 4. Review và kiểm chứng

Codex review theo ủy quyền của người dùng đảm nhiệm M1/M2: parser coordinates/
count semantics, source/patch identity, verification/evidence, JSON roundtrip,
naming/status và completeness. Không coi NOT_COMPUTED là PASS. Review M3 được
người dùng miễn riêng M1-W9-1; không ký thay hoặc suy ra phê duyệt M3 cho MCP.
Receipt lưu ngày thực, hashes và evidence; mapping/producer vẫn là W9-2.

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = 'D:\Project\CAPSTONES\.venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& $python -B -m pytest tests/test_impact.py -k schema -q -p no:cacheprovider
$LASTEXITCODE
```

Mong muốn: exit0. Không cần tokenizer/model/Docker cho DTO tests. Không cài lại
dependencies để chạy lệnh nếu interpreter đã có pytest/Pydantic phù hợp.
Evidence task: `results/m1/w9/m1-w9-1/20261023-contract/`; trạng thái và số tests
thực tế được cập nhật tại `docs/status/m1.md`. Evidence nghiệm thu mới tại
`results/m1/w9/m1-w9-1/20261023-close-review/`; giữ nguyên evidence ban đầu.
Dừng sau W9-1.
