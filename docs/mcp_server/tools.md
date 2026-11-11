# L6-2 — Adapter cho 11 core tools

## Phạm vi và trạng thái

L6-2 mở rộng bằng adapter trên runtime SDK2 của L6-1 và guards của L6-5. Không LangChain/LangGraph, không model, Docker hoặc agent loop. User đã có quyền tự quyết; không cần vòng duyệt TV2/TV3. Thiếu implementation provider vẫn là dependency kỹ thuật.

Production entrypoints đăng ký **20 tools**: 15 legacy và 5 bổ sung, bao gồm đủ 11 core names. Resources vẫn 3, prompt vẫn 0. Đăng ký không đồng nghĩa provider đã sẵn sàng.

| Core tool | Đường thực thi và mức sẵn sàng |
|---|---|
| search_symbols | Legacy service; giữ signature/payload. Khi host cấu hình context, kiểm source và actual backend snapshot. |
| find_task_anchors | Giữ graph_version/task_id bắt buộc; đối chiếu trusted context khi có. |
| get_related_context | Giữ budget và tokenizer/ranking legacy; không giả rich graph mới. |
| get_callers / get_callees | Depth 1 giữ shape/order cũ. Depth >1 cần traversal provider; thiếu provider/context trả ERROR. |
| analyze_patch_impact | Giữ ImpactReport hiện có; không thêm architecture facts hoặc đổi schema legacy. |
| build_or_update_graph | Adapter/grant/lifecycle sẵn; production WAITING_PROVIDER và L6-6 orchestration. |
| explain_dependency_path | Adapter có bounded typed witness; production WAITING_PROVIDER. |
| verify_patch_graph_constraints | Adapter có binding/evidence validation; thiếu provider trả domain NOT_RUN/CAPABILITY_UNAVAILABLE. |
| rank_patch_candidates | Adapter kiểm ID/hash, evidence, required checks và stable tie-break; production WAITING_PROVIDER. |
| execution_run_relevant_tests | Adapter grant/private-workspace lifecycle; production WAITING_PROVIDER. Không phải repair_run_relevant_tests(run_dir). |

Các provider fixture đều **synthetic**. Receipt `executed=true` trong fixture chỉ mô phỏng giao diện executor, không chứng minh đã chạy pytest của task thật. Không dùng kết quả này làm Repair/Ablation experiment.

## Interface và bootstrap

`src/vgar/mcp/proposal/contracts.py` chứa frozen Pydantic DTO, `extra='forbid'`: SnapshotBinding, BuildRequest/Result, DiffRequest, PathRequest/Result, TraversalRequest/Result, CheckEvidence, TestEvidence/Receipt, Candidate, RankRequest/Result. Tuple/nested DTO tránh mutable metadata; bool không được dùng làm depth/score; NaN/Infinity bị từ chối.

Diff hash = SHA-256 của UTF-8 bytes chính xác, **không đổi CRLF**. Input hash cho grant = canonical JSON của request DTO. SnapshotBinding gồm snapshot/source/config hashes và task/run IDs. Config hash phải pin cấu hình semantic/schema/resolver/tokenizer/ranking áp dụng cho provider; adapter không tự suy profile từ graph_version cũ.

`ports.py` định nghĩa GraphProvider, VerificationProvider, TestProvider và immutable ProviderRegistry/ProviderBinding. Capabilities: build/path/traversal/verification/ranking/tests. Không dynamic-import provider từ model arguments. Build và tests yêu cầu async method, lifecycle `guarded-v1`; test provider cần `candidate_workspace` relative path do host bind.

Ví dụ bootstrap trusted khi đã nhận provider thật:

```python
from vgar.mcp.proposal.contracts import SnapshotBinding
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.servers import graph_server

# provider, baseline_context và host_context_factory được operator tạo;
# không đọc chúng từ MCP JSON hoặc confirmed=true.
record = ProviderBinding(
    provider=provider,
    binding=SnapshotBinding.from_context(baseline_context),
    capabilities=frozenset({"path"}),
)
graph_server.core_tools = CoreTools(
    ProviderRegistry((record,)), context_factory=host_context_factory,
)
graph_server.main()
```

Bootstrap thực hiện trước khi serving, không thay registry giữa request. Context factory tạo context/request ID và grant theo chính sách operator; không tự cấp grant cho mọi diff trong production. Registry mặc định rỗng và không có factory. `test_only=True` là API test bootstrap riêng; production main từ chối registry này. Fixture wire chủ động dùng entrypoint test riêng, không thay config launcher production.

Chưa cấu hình host factory thì legacy tools giữ lease/service hiện có. Khi đã cấu hình, cả legacy core query và adapter mới dùng trusted scope. Legacy query từ backend snapshot khác bị từ chối; SQLite store phải pin `requested_graph_version` (operator `VGAR_GRAPH_VERSION`), không dùng latest. Required args legacy không được rút gọn.

## Bounds, evidence và lifecycle

- Default operator limits: 2 hops, 200 result nodes, 10.000 examined edges, 20 candidates, 65.536 UTF-8 bytes/diff. Không phải budget hay protocol thí nghiệm mới. Evidence đọc tối đa theo SecurityLimits của host; quá cap trả lỗi.
- Path kiểm endpoint/edge continuity và hướng; traversal kiểm hop, node dedup, seed exclusion, caps. Adapter không thực hiện BFS/ranking/verification algorithm thay provider. Truncation/unsupported/reasons được giữ trong output.
- Check PASS cần coverage COMPLETE, scope và evidence sidecar thực khớp hash. Unknown khác measured zero. Path/evidence lỗi hoặc output binding sai không thành PASS.
- Candidate chỉ có ID/diff/hash từ caller. Required-check policy do host bind; không tự chọn policy A4. Eligibility yêu cầu evidence thực, đủ đúng tập required checks và tất cả PASS. Không có policy/evidence thì không đủ điều kiện. Sort theo eligible trước, score giảm dần, candidate ID tăng dần.
- Build và tests dùng async lock theo repo trước OS lock; OS contention được poll không chặn event loop. Source được kiểm lại **sau khi lấy khóa, trước consume grant/provider call**. Grant single-use dùng đúng operation/request hash.
- Provider async phải hợp tác cancellation và dùng process-tree guard L6-5 cho CPU/blocking/executor jobs; không bọc thread để giả đã dừng. Adapter áp worker limit và remaining deadline, giữ cancellation propagation, ghi host operation receipt.
- Test provider sở hữu admission, candidate state/apply-once, executor và cleanup. Receipt phải bind đúng diff và workspace đã được host cấp. Candidate đã apply phải được provider xác minh state; applied_count là tổng số apply của candidate, không phải yêu cầu apply thêm lần nữa. Không gọi repair finalizer.
- Cleanup manifest kiểm **mọi file kể cả ignored/cache, cùng empty directories**. Build phải giữ nguyên lease. Test chỉ được xóa đúng candidate subtree host đã bind; phần còn lại phải nguyên vẹn. Thay đổi/lưu rác không thể nhận PASS chỉ vì provider khai cleaned=true. Wrapper không tự xóa dữ liệu nghi rò rỉ; trả ERROR và giữ bằng chứng cho operator.
- Host receipt `cleanup_observed` chỉ là kiểm filesystem lease, không thay container/runtime attestation của executor. Python provider/operator cùng tài khoản là trusted code; đây không phải OS sandbox chống plugin Python độc hại.

## Kiểm chứng và phục hồi

Artifact: `results/mcp_server/tools/20261108T141511Z-adapters/`. Xem final summary, preservation và command receipts; giữ cả RED/failed runs để không che lịch sử.

```powershell
$sdk2 = 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VGAR_GRAPH_BACKEND = 'demo'
$env:PYTHONPATH = "$PWD\src"
& $sdk2 -B -m pytest tests/mcp_server/test_core_tools.py tests/mcp_server/test_provider_binding.py tests/mcp_server/test_core_wire.py -q -p no:cacheprovider --basetemp "$env:TEMP\vg-l62-user-01"
```

Chọn temp mới mỗi lần. Wire fixture cần SDK2 env; legacy LC client chạy bằng venv CUDA cũ, không cài framework vào SDK2. Lệnh đầy đủ đã chạy nằm ở `commands.md` và từng `*/command.json` trong artifact. Runtime checker kiểm legacy subset + core additions; receipt L6-1/L6-5 cũ giữ nguyên. Không dùng tracked DB để thử query; plugin regression chỉ redirect tracked sample DB sang temp copy.

**Điểm dừng:** đóng phần adapter local khi gate đạt; production chờ provider/capability và L6-6 tương ứng. Không tự triển khai thuật toán, resources, prompt, storage hoặc campaign.
