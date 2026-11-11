# TV3 · Xác minh patch Python tĩnh qua MCP

Nhánh `tv3/ev2-verified-patch` triển khai `verification` và `resource_baseline` cho snapshot SQLite legacy với resolver Python tĩnh. Host dùng `StaticVerificationProvider` cho đúng snapshot đã mở. Provider đối chiếu graph với bytes của repo, xem trước diff trong thư mục tạm, dựng graph candidate và trả evidence có SHA-256. Việc phân tích chỉ đọc source và kiểm cú pháp, chữ ký API, schema và quan hệ import. Thư mục candidate được dọn trước khi công bố kết quả.

## Đăng ký từ Python host

`store` phải là `SnapshotGraphStore` mở từ manifest READY và profile do host đăng ký. `patch_policy` ghim danh sách file Python được sửa, đường dẫn bảo vệ và giới hạn patch. Chọn `source_roots` giống lần build baseline. Truyền `structural_policy` nếu cần kiểm import bị cấm và phụ thuộc sai tầng.

```python
from vgar.mcp.proposal.contracts import SnapshotBinding
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.proposal.verification_provider import StaticVerificationProvider

provider = StaticVerificationProvider(
    store, patch_policy, source_roots=source_roots, structural_policy=structural_policy,
)
# Host ký context với graph_version, source_inventory_hash, provider.config_hash
# và task/run đã chọn. Context factory dùng cùng binding và request_id riêng.
record = ProviderBinding(
    provider,
    SnapshotBinding.from_context(baseline_context),
    frozenset({"verification", "resource_baseline"}),
)
graph_server.core_tools = CoreTools(
    ProviderRegistry((record,)), context_factory=operator_context_factory,
)
```

`snapshot_hash` trong context đọc là `graph_version`. Sidecar còn ghi `snapshot_id` của storage, hash diff gốc và phiên bản graph candidate. `provider.config_hash` ghim patch policy, structural policy, source roots, schema, resolver và storage profile. Host chọn snapshot bằng cấu hình của phiên trước khi phục vụ. Hai capability này chỉ ghi evidence vào output đã bind, không cần grant sửa repo hay chạy test.

## Diễn giải kết quả

- `verify_patch_graph_constraints(diff)` hỗ trợ unified diff sửa file Python có sẵn. `PASS` với `COMPLETE` áp dụng cho phạm vi tĩnh đã cấu hình. Check API dùng các file patch chạm tới. Check import so trên graph Python của snapshot. Vòng import cũ được giữ làm baseline để phát hiện vi phạm mới.
- `checks.source_imports` bổ sung vòng phụ thuộc mới có import nằm trong hàm, class hoặc khối điều kiện. EV-2 phân tích cú pháp từ source đã đối chiếu hash, dùng danh tính module trong snapshot và ghi file, dòng, hash cho từng cạnh trong đường dẫn. Check dựa trên quan hệ import tĩnh và chưa phân giải lời gọi import động hoặc suy đoán submodule qua thuộc tính package. Profile của phép kiểm nằm trong `config_hash`.
- Diff sai phạm vi, sai bytes baseline hoặc tạo lỗi cú pháp có lý do riêng. Phân tích API không đủ bằng chứng có thể trả `NOT_RUN`; lỗi phân tích trả `ERROR`. Một vi phạm đã xác minh vẫn có thể trả `FAIL` với `PARTIAL` nếu check khác chưa đủ dữ liệu.
- `vgar://evidence/baseline` trả `PARTIAL`, gồm fingerprint graph/schema/resolver, số file Python đã đối chiếu với source và sidecar theo task/run. Test nền và invariant được ghi `NOT_RUN`. Resource công khai chỉ trả metadata và hash.
- Check mất port, fanout theo `G_arch` và runtime invariants còn mở. Fixture hiện tại chạy provider và SQLite thật qua MCP SDK 2 ở cả modern lẫn legacy. Để dùng sidecar EV-2 cùng kết quả EV-3, xem [cách ghép EV-1](tv3_patch_ranking.md).

```powershell
python -B -m pytest -q -p no:cacheprovider tests/mcp_server/test_tv3_verification.py
```
