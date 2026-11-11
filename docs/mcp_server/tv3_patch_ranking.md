# TV3 · Xếp hạng patch từ evidence đã đo

`EvidenceRankingProvider` triển khai `rank_patch_candidates`. Host ghim một danh mục `diff_hash → CandidateEvidence(graph, tests)` bằng `EvidenceRef` đã nhận từ EV-2 và EV-3. Request MCP giữ nguyên dạng danh sách candidate và diff. Ranking chỉ đọc các sidecar đã được chọn và ghi một receipt tổng hợp.

## Ghép qua Python host

1. Mở baseline SQLite được ghim và ký context đọc với `graph_version`. Dùng cùng `SnapshotBinding` cho verifier, executor và ranking. Khi khởi tạo `DiffTestsProvider`, truyền `snapshot_id` lấy từ identity của SQLite, tách biệt với `graph_version`.
2. Chạy verify và diff-test qua adapter tương ứng. Chọn chính xác evidence ref của từng kết quả. Host lưu các cặp ref theo `diff_hash`. Nếu một phép đo chưa chạy, để ref tương ứng rỗng.
3. Truyền `RankingPolicy` đã chọn và dùng cùng `required_checks` ở registry. Host quyết định trọng số, tên check bắt buộc và cặp evidence trước khi phục vụ.

```python
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.ranking_provider import CandidateEvidence, EvidenceRankingProvider
from vgar.mcp.proposal.tools import CoreTools

provider = EvidenceRankingProvider(
    binding, snapshot_id=store.identity.snapshot_id, policy=ranking_policy,
    evidence_by_diff={diff_hash: CandidateEvidence(graph=graph_ref, tests=test_ref)},
)
record = ProviderBinding(provider, binding, frozenset({"ranking"}))
graph_server.core_tools = CoreTools(
    ProviderRegistry((record,), required_checks=ranking_policy.required_checks),
    context_factory=operator_context_factory,
)
```

Provider kiểm SHA-256 của sidecar, diff, loại producer, storage snapshot và context. Khi cả hai phép đo đã ghi candidate, hash của các file thay đổi phải khớp. Sidecar ghim sai hoặc đã bị sửa làm request bị từ chối. Receipt xếp hạng lưu chính sách, hash chính sách, kết quả, chín trường evidence và các ref đầu vào.

Nếu sidecar có `checks.source_imports`, verdict graph `PASS` yêu cầu phép kiểm đó là `PASS`. EV-1 từ chối receipt mâu thuẫn với `FAIL`, `ERROR` hoặc `NOT_RUN` trong phép kiểm import nguồn.

## Diễn giải điểm và trạng thái

Trong profile này, điểm test chia đều giữa test gate và các test lỗi đã sửa. Các phần còn lại theo công thức proposal gồm schema, import bị cấm, API, invariant và phạt rủi ro impact. `PASS` và `FAIL` là kết quả đã đo cho từng phép kiểm. `NOT_RUN` và `ERROR` để lại khoảng chưa xác định. Khi impact chưa đo, cận dưới dự trù toàn bộ phần phạt. Trường `score` trả cận dưới, còn receipt giữ cả cận trên.

Ứng viên đủ điều kiện khi cả verdict graph và test là `PASS` và mọi check bắt buộc đều qua. Kết quả ưu tiên ứng viên đủ điều kiện, sau đó sắp điểm giảm dần và dùng candidate ID để phân xử hòa. Fixture của nhóm minh họa hai patch trên cùng snapshot và ghim các trọng số thử nghiệm trong test. Typecheck, lint, invariant và impact vẫn là `NOT_RUN` trong lát cắt này.

Khi host cấu hình `semantic_contract` cho EV-3, EV-1 kiểm hash định nghĩa và outcomes baseline/candidate theo node ID của từng ví dụ. Kết quả được đưa vào `semantic_invariant_preserved`, có thể đặt làm check bắt buộc. Phạm vi ngữ nghĩa là tập ví dụ host đã ghim.

## Chạy lại fixture bàn giao

Từ gốc repo, kích hoạt môi trường MCP SDK2 của TV1 theo [runbook](runbook.md) và chạy fixture cho cả hai chế độ STDIO.

```powershell
$env:PYTHONUTF8 = '1'
$runId = [guid]::NewGuid().ToString('N').Substring(0, 8)
$smokeRoot = Join-Path ([IO.Path]::GetTempPath()) "vgar-tv3-$runId"
python -B -m pytest -q -p no:cacheprovider tests/mcp_server/test_tv3_ranking.py `
  -k verify_test_rank_over_stdio --basetemp $smokeRoot --junitxml "$smokeRoot.xml"
```

Mỗi chế độ tạo một SQLite snapshot cố định và dùng cùng `SnapshotBinding` cho ba phiên STDIO. Test đọc resource `vgar://evidence/baseline`, gọi `verify_patch_graph_constraints` và `run_relevant_tests` cho cả hai diff, rồi chọn các `EvidenceRef` đã kiểm SHA-256 trước khi mở phiên `rank_patch_candidates`. Test kiểm byte hash của file ứng viên giữa EV-2 và EV-3, số lần apply và cleanup của workspace.

GOOD qua hai test và đứng đầu với `0.70`. BAD sửa test mục tiêu, làm hỏng test hồi quy và bị loại với `0.45`. Kết quả, binding, snapshot ID và các ref nằm trong `ev-wire*/output/tv3-handoff-summary.json` dưới `--basetemp`; các sidecar nằm cạnh summary. Resource baseline báo `PARTIAL`. Fixture dùng chạy test native với hai diff đã ghim. Binding production, Docker admission và các check kiến trúc cần schema TV2 vẫn là các mốc tích hợp tiếp theo.
