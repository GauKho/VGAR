# TV3 · Chạy test trên diff qua MCP

`DiffTestsProvider` nối `execution.run_relevant_tests(diff)` với pytest runner của luồng repair. Host ghim task, snapshot, phạm vi test và workspace trước khi serving. Tool nhận diff và cần grant dùng một lần đúng hash của request. Kết quả baseline và candidate nằm trong sidecar của đúng run/task/snapshot.

## Đăng ký từ Python host

```python
from vgar.mcp.proposal.contracts import SnapshotBinding
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools

binding = SnapshotBinding.from_context(baseline_context)
provider = DiffTestsProvider(
    task, policy, binding, candidate_workspace="ev3-candidate", admission=admission,
)
record = ProviderBinding(
    provider, binding, frozenset({"tests"}), lifecycle="guarded-v1",
    candidate_workspace=provider.candidate_workspace,
)
execution_server.core_tools = CoreTools(
    ProviderRegistry((record,)), context_factory=operator_context_factory,
)
```

- Với `docker_admitted`, host cung cấp `RepairAdmission` từ luồng admission hiện có. Profile cần ghim checkout, overlay, image và daemon đã qualification. Lượt kiểm tra TV3 trên Windows dùng fixture native. Đường Docker cần chạy kiểm chứng với admission và image thật của nhóm.
- Với `native_trusted_fixtures`, host cung cấp `approved_fixture_diffs` gồm các SHA-256 của patch đã kiểm trước. Provider đối chiếu bytes repo với registry fixture và đối chiếu hash diff trước khi tạo workspace.
- `candidate_workspace` là tên thư mục trực tiếp trong lease root. Provider tạo mới, dọn workspace thuộc request và xác minh source gốc trước khi ghi sidecar. Nếu thư mục đã tồn tại, request bị từ chối.
- Khi dùng evidence cho EV-1, truyền thêm `snapshot_id` của storage lúc khởi tạo. Sidecar test giữ ID này cùng hash bytes các file sau khi apply để đối chiếu với sidecar graph. Xem [cách ghép EV-1](tv3_patch_ranking.md).

## Đọc kết quả

Provider đo baseline trên `fallback_scope` đã ghim. Sau khi lỗi dự kiến tái hiện, provider áp diff đúng một lần và chạy lại cùng phạm vi. `PASS` yêu cầu các test baseline bị lỗi chuyển sang pass và các test baseline đã pass giữ nguyên kết quả. `FAIL` là lỗi test đã đo. Baseline không tái hiện trả `NOT_RUN`. Lỗi runner, evidence hoặc integrity trả `ERROR` hoặc bị từ chối tại adapter.

Envelope MCP xác nhận tool trả lời được. Đọc `data.status` để lấy verdict. `data.receipt` ghi số lần apply, việc chạy candidate và cleanup. Sidecar giữ outcomes, hash JUnit, mã thoát và thời gian. `coverage=COMPLETE` chỉ phạm vi đánh giá verdict. Coverage theo node vẫn là `NOT_MEASURED` cho đến L5-3.

## Ví dụ kiểm contract ngữ nghĩa

Host có thể truyền `semantic_contract` khi khởi tạo `DiffTestsProvider` cho fixture native đã được duyệt. Các ví dụ chỉ định hàm trong file thuộc phạm vi patch, đối số JSON và kết quả mong đợi.

```python
from vgar.repair.semantic_contract import ContractExample, SemanticContract

contract = SemanticContract(examples=(
    ContractExample(case_id="bob", module="auth", function="login", args=("bob",), expected=True),
))
```

Pytest chạy ví dụ ở baseline và candidate với node ID như `vgar_contract::bob`. Baseline phải qua mọi ví dụ trước khi apply. Candidate sai kết quả mong đợi được ghi thành test hồi quy fail. Sidecar ghim định nghĩa contract bằng SHA-256 và lưu verdict theo từng node ID. Plugin hiện hỗ trợ fixture native. Đường Docker cần xác nhận cách cung cấp plugin và chạy gate với image của nhóm.

```powershell
python -B -m pytest -q -p no:cacheprovider tests/mcp_server/test_tv3_diff_tests.py
```
