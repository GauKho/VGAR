# TV2 · L2-2: cạnh `MAY_CALL` kèm confidence và provenance

> **Trạng thái:** bản nháp, chờ duyệt. Soạn ngày 08/11/2026.
>
> **Nguồn:** plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), và các file trong
> `C:\Users\nlhnh\Downloads\context` (**[cp]** `check proposal.txt`, **[mm]** `metrics matrix.txt`, **[test]** `test.txt`).
>
> **Đánh dấu:** **(P)** là proposal ghi. **(TV2 chốt)** là quyết định của TV2 trong phiên 08/11, proposal không ghi.
> **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt.

## 1. Bối cảnh và lý do

[plan] L2-2 (ngày 1): "Cạnh `MAY_CALL` kèm confidence và provenance (`source_tool`, `evidence`)".

- Hiện lời gọi chưa resolve không có cạnh nào, chỉ được đếm trong `unresolved_call_count` ([cp] dòng 68).
- Trên graph xarray-4629 chế độ `static`, 22.644 trong 32.018 lời gọi (70,7%) chưa resolve (đếm ngày 08/11 trên file graph
  đã build, 39.279 node và 54.448 cạnh).
- Proposal yêu cầu: "Nếu không resolve được, vẫn giữ edge với confidence thấp" ([P] dòng 551), dạng
  `CallSite --MAY_CALL[confidence=0.42]--> CandidateMethod` (dòng 554), và graph phải lưu confidence, provenance (dòng 557–567).
- Đây cũng là cách giảm rủi ro "call graph của Python nhiễu" ([P] dòng 1472; [plan] §8).

## 2. Mục tiêu, phạm vi loại trừ, điều cần tránh

**Mục tiêu**

1. `PythonGraphBuilder` sinh cạnh `MAY_CALL` **mặc định** ở mọi resolver (`static`, `scip`, `lsp`, `scip-lsp`) **(TV2 chốt)**.
2. Mỗi cạnh có confidence thấp, `source_tool` đúng nguồn và `evidence` không rỗng **(P)**.
3. Graph qua `validate_graph_document`, có test tầng 1 bằng `pytest` trên repo mẫu viết tay ([plan] Phụ lục A.2).

**Không làm trong spec này (giao cho task khác, xem §8)**

- Retrieval, impact, `get_callers`, `get_callees` đọc `MAY_CALL`: [plan] giao cho RT-1, IM-1, L6-2.
- Tầng ứng viên PyCG/JARVIS: L2-1.
- Node `ExternalSystem` cho lời gọi ra ngoài repo: GA-2 ([P] dòng 258).
- Báo cáo P/R tách riêng `CALLS` và `MAY_CALL`: G1 (tuần 2).
- Sửa cạnh `CALLS` hiện có, kể cả mức confidence của chúng.

**Điều cần tránh**

- Không làm thay đổi cạnh hoặc node đã có. Bỏ hết cạnh `MAY_CALL` thì phần còn lại phải giống hệt graph trước khi có spec này.
- Không để `MAY_CALL` lọt vào các đường đọc hiện có (xem §6).
- Không tạo cạnh khi SCIP/LSP đã xác định lời gọi ra ngoài repo hoặc không gọi được: comment ở `builder.py:1056` cấm đoán
  thành cạnh nội bộ trong trường hợp này.

## 3. Khi nào sinh cạnh

Sửa trong `_resolve_calls` (`builder.py:1036`), là bước linking.

| Tình huống tại `_resolve_calls` | Sinh `MAY_CALL`? | Ứng viên | `match_kind` |
|---|---|---|---|
| SCIP `ambiguous` (`builder.py:1055`) | Có **(TV2 chốt)** | `scip_targets` | `scip_ambiguous` |
| LSP `ambiguous` (`builder.py:1064`) | Có **(TV2 chốt)** | `lsp_targets` | `lsp_ambiguous` |
| Không tìm được đích, `target_id is None` (`builder.py:1085`) | Có **(TV2 chốt)** | So tên (§4) | `name` |
| SCIP `external_or_non_callable`, `local_non_callable` | Không **(TV2 chốt)** | | |
| LSP `external_or_non_callable` | Không **(TV2 chốt)** | | |
| Đã có cạnh `CALLS` | Không | | |

- Với `ambiguous`, nếu danh sách của SCIP/LSP sau khi quy đổi (§4.2) rỗng thì không sinh cạnh và **không** chuyển sang so tên **(đề xuất)**.
- Trường hợp `has_lexical_binding=True` vẫn đi vào so tên **(đề xuất)**. Ví dụ `def f(repo): repo.check()`: `repo` là biến cục bộ
  nhưng đây chính là lời gọi đa hình mà `MAY_CALL` nhắm tới. Lời gọi không có dấu chấm đã bị bộ lọc §4.3 loại.
- `CallSite` vẫn giữ `resolution_status="unresolved"` và `candidate_count=0`, vì `candidate_count` chỉ đếm cạnh `CALLS`
  (`schema.py:303, 313`). `unresolved_call_count` không đổi.

## 4. Ứng viên

### 4.1 So tên

Tên cần tìm là phần sau dấu chấm cuối của `callee_text`, và phải là identifier hợp lệ. Ứng viên là mọi node Function/Method
trong repo có `name` bằng tên đó **(TV2 chốt)**.

Node `Test` không phải ứng viên **(đề xuất)**: [P] chỉ nói "CandidateMethod".

### 4.2 Lời gọi class

`CandidateMethod` chỉ gồm Method và Function **(TV2 chốt)**. Nếu tên khớp một Class, hoặc SCIP/LSP trả về một Class, ứng viên
là `__init__` và `__new__` do chính class đó định nghĩa. Class không tự định nghĩa thì không có ứng viên.

### 4.3 Bộ lọc (TV2 chốt)

Áp dụng theo thứ tự:

1. `callee_text` có dấu chấm. Chỉ áp dụng cho `match_kind="name"`.
2. Bỏ thư viện ngoài. Lấy gốc của lời gọi là phần trước dấu chấm đầu tiên.
   - Nếu gốc có trong `module.imported_modules` hoặc `module.imported_symbols` và module đích nằm ngoài `self.modules`
     (không có trong đó và cũng không là tiền tố của module nào trong đó, để giữ namespace package), loại.
   - `import numpy as np` thì `np.` bị loại; `import xarray as xr` trong repo xarray thì được giữ.
   - Gốc không phải tên import (`self`, biến cục bộ) thì giữ.
   - Chỉ áp dụng cho `match_kind="name"`.
3. Sau khi khử trùng, nếu có hơn 5 ứng viên thì **bỏ hẳn lời gọi đó**, không chọn 5 ứng viên tốt nhất **(TV2 chốt, điểm A)**.
   Áp dụng cho mọi `match_kind`.

Số cạnh ước tính trên xarray ở `static`: khoảng 15.914 (+29%). Lần đếm đó dùng danh sách thư viện liệt kê tay và chưa quy đổi
class, nên số thật sẽ lệch một ít.

Giới hạn đã biết: ở chế độ `static`, `data.get()` với `data` là dict của Python không phân biệt được là gọi ra ngoài repo, nên
vẫn có thể sinh cạnh sai. Không xử lý trong spec này.

## 5. Nội dung cạnh

```json
{
  "type": "MAY_CALL",
  "source_id": "<CallSite>",
  "target_id": "<Function hoặc Method>",
  "confidence": 0.5,
  "resolution": "heuristic",
  "provenance": {
    "source_tool": "vgar-builder-heuristic",
    "source_tool_version": "0.1.0",
    "rule_id": "python.call.may_call.name.v1",
    "source_revision": "<revision>",
    "evidence": ["name_match", "same_module_scope", "unresolved_type"]
  },
  "properties": {"match_kind": "name", "candidate_count": 3}
}
```

### 5.1 Confidence (TV2 chốt, điểm B)

```text
confidence = min(0.50, round(0.6·tool_precision + 0.2·type_match + 0.2·import_path_coherence, 2))
```

| Thành phần | Giá trị |
|---|---|
| `tool_precision` | 0.5 khi so tên **(TV2 chốt)**; 0.7 khi SCIP/LSP `ambiguous` **(đề xuất)** |
| `type_match` | 0, vì lời gọi đã khớp kiểu thì không còn là chưa resolve **(TV2 chốt)** |
| `import_path_coherence` | 1 nếu ứng viên cùng module với lời gọi, hoặc module của ứng viên được file đó import; ngược lại 0 **(TV2 chốt)** |

Kết quả: so tên là 0.30 hoặc 0.50; SCIP/LSP `ambiguous` là 0.42 hoặc 0.50. Mức trần 0.50 áp dụng cho mọi `MAY_CALL` **(TV2 chốt)**.
Công thức do TV2 đặt; proposal chỉ có ví dụ 0.42 (dòng 554).

Giới hạn đã biết: số ứng viên không ảnh hưởng tới confidence.

Một module được tính là "được import" nếu nó có trong giá trị của `imported_modules`, là phần module của `imported_symbols`, hoặc
là `f"{module}.{name}"` của `imported_symbols` (trường hợp `from pkg import mod`) **(đề xuất)**.

### 5.2 Provenance

| `match_kind` | `source_tool` | `rule_id` |
|---|---|---|
| `name` | `vgar-builder-heuristic` **(TV2 chốt)** | `python.call.may_call.name.v1` |
| `scip_ambiguous` | `resolver_report["tool"]` và `tool_version`, như cạnh `CALLS` của SCIP (`builder.py:1165`) | `python.call.may_call.scip_ambiguous.v1` |
| `lsp_ambiguous` | Tên và version trong `server_info`, như cạnh `CALLS` của LSP (`builder.py:1169`) | `python.call.may_call.lsp_ambiguous.v1` |

`evidence` là danh sách chuỗi, không được rỗng **(P, TV2 chốt)**. Lưu ý `_add_edge` hiện luôn đặt `evidence: []` (`builder.py:1805`).

- `name`: luôn có `name_match` và `unresolved_type`.
- `scip_ambiguous`, `lsp_ambiguous`: luôn có đúng giá trị `match_kind`.
- Mọi loại: thêm `same_module_scope` nếu cùng module; thêm `import_path` nếu module của ứng viên được import.

## 6. Thay đổi ở các phần khác

| Chỗ | Thay đổi |
|---|---|
| `contracts/schema.py`, `EDGE_ENDPOINTS` | Thêm `"MAY_CALL": {("CallSite", "Function"), ("CallSite", "Method")}`, comment "Proposed, pending team review" như các loại Layer 1 |
| `validate_graph_document` | Trong nhánh kiểm tra từng cạnh không tin cậy: cạnh `MAY_CALL` phải có `provenance.evidence` là danh sách không rỗng và `confidence <= 0.50` |
| `sqlite_store.py:525`, `get_subgraph` | Thêm điều kiện loại `MAY_CALL` **(đề xuất)**. Query này duyệt mọi loại cạnh, và có giới hạn `limit`, nên cạnh phỏng đoán sẽ đẩy cạnh chắc chắn ra khỏi `vgar://graph/subgraph` |
| `incremental.py`, `affected_node_count` | Bỏ qua `MAY_CALL` khi so cạnh, để metric "affected nodes" của U1 không bị đổi (bổ sung sau review cuối, 08/11) |
| `statistics` của document | Thêm `statistics["may_call"]`: `rule_version` (`"may-call-v1"`), `edge_count`, `callsite_count`, `skipped_over_cap`, `by_match_kind` |

Các đường đọc khác đã lọc theo loại cạnh nên không cần sửa: `retrieval.py:419-445`, `impact.py:217`, `test_selection.py:44`,
`structural_check.py:122-127`, `visualization.py:25`, các truy vấn caller/callee `sqlite_store.py:369, 398`.

**Định danh và profile (TV2 chốt 08/11, thay cho đề xuất ban đầu giữ nguyên `graph_version`).**

- Một schema `S`, hai profile: `full_vgar_mcp` (mặc định) và `legacy_w10`. `validate_graph_document(..., profile=...)`; profile legacy từ chối
  mọi loại node/cạnh ngoài bộ W10. `project_legacy_w10(document)` trả bản legacy từ graph đầy đủ.
- `graph_version` đầy đủ thêm `SCHEMA_VERSION`, `BUILDER_VERSION` (có `RULE_VERSION`) và `RESOLVER_PROFILE` vào hash, giữ nguyên phần hash nội dung file.
- `statistics.legacy_graph_version` là định danh cũ của cùng source, nhờ đó quyết định E5 (iii) vẫn đúng cho đường W10. Bản legacy dùng định danh này.
- `RESOLVER_PROFILE` giữ nguyên giá trị, vì logic resolve `CALLS` không đổi, nên dữ liệu đã lưu của `structural_check.py` và `verification_checks.py`
  vẫn hợp lệ. Registry nhiều profile chưa cần tới.
- `SQLiteGraphStore.ingest` với `graph_version` đã có: nếu `ready` thì ghi log và giữ graph đã lưu; nếu chưa `ready` thì báo lỗi.

**Incremental không cần sửa.** Linking chạy lại toàn repo (`incremental.py:3-6`), nên nếu chỉ sinh `MAY_CALL` trong `_resolve_calls`
thì một file thay đổi sẽ tự cập nhật ứng viên ở file khác. Câu trả lời 10 của TV2 mô tả cơ chế hủy cache theo tên; repo hiện không
cần cơ chế này.

## 7. Test và tiêu chí nghiệm thu

File mới `tests/test_may_call.py`, dùng repo mẫu viết tay với đáp án ghi sẵn:

1. Ba method `check` ở ba class, gọi `self.repo.check()`: đúng 3 cạnh, đúng confidence và `evidence`.
2. `import numpy as np` + `np.check()`: không có cạnh.
3. `check()` không dấu chấm: không có cạnh.
4. Sáu ứng viên: không có cạnh và `skipped_over_cap` tăng.
5. Tham số hàm `def f(repo): repo.check()`: có cạnh.
6. Lời gọi class có `__init__`: cạnh trỏ tới `__init__`, không trỏ tới Class. Class không có `__init__`: không có cạnh.
7. `import_path_coherence`: ứng viên cùng module hoặc được import là 0.50, còn lại 0.30.
8. SCIP và LSP `ambiguous` (giả lập resolver): đúng `match_kind`, `source_tool`, confidence 0.42 hoặc 0.50.
9. SCIP `external_or_non_callable`: không có cạnh.
10. Validate từ chối cạnh `MAY_CALL` có `evidence` rỗng hoặc `confidence > 0.50`.
11. Bỏ hết cạnh `MAY_CALL` và `statistics["may_call"]`: phần còn lại giống hệt graph sinh với `MAY_CALL` tắt nội bộ trong test.
12. Incremental: thêm một method `check` ở file A, cạnh ở file B được cập nhật, document bằng đúng build lại toàn bộ.
13. `get_subgraph` không trả cạnh `MAY_CALL`.

**Nghiệm thu**

- Toàn bộ test trên xanh, nhóm test graph hiện có không bị hỏng. Test nào đếm cạnh mà phải đổi số thì ghi rõ trong báo cáo.
- Chạy thật `build_graph.py` trên `vgar-demo-shop` và `pydata__xarray-4629` ở `static`, và xarray ở `scip`. Báo cáo số cạnh, phân bố
  `match_kind` tại `docs/status/`.

Việc 11 cần một cách tắt nội bộ dành cho test; người làm tự chọn cách, không đưa ra CLI.

## 8. Yêu cầu chuyển cho task sau

| Task | Yêu cầu (nguồn: câu trả lời của TV2 ngày 08/11) |
|---|---|
| RT-1 | Retrieval dùng `MAY_CALL` và xếp sau `CALLS`. Phải vượt ngưỡng `min_edge_confidence=0.6`. Xem xét dùng đặc trưng `edge_confidence` sẵn có ([P] dòng 986) trước khi thêm hệ số phạt. Thêm trường vào `RetrievalConfig` sẽ đổi hash đóng băng (`test_graph_retrieval.py:59`) |
| IM-1 | Impact phân cấp: `CALLS` là ảnh hưởng trực tiếp, `MAY_CALL` là ảnh hưởng phỏng đoán. Phải duyệt `MAY_CALL` sau `CALLS` vì kết quả bị cắt ở `max_nodes` (`impact.py:251`). `ImpactRelation` (`contracts/impact.py:93`) phải mở rộng |
| L6-2 (TV1) | `get_callers`/`get_callees` không trộn `MAY_CALL` với kết quả chắc chắn, vì [test] mục 1 chấm "caller, callee đúng" |
| L2-1 | PyCG/JARVIS là một `match_kind` mới, cùng cấu trúc cạnh, mức trần 0.50. Câu 11, 13, 14 cần chạy thử PyCG trước |
| G1 (tuần 2) | Báo riêng Exact Call Edge P/R (`CALLS`) và Extended Recall (`CALLS` + `MAY_CALL`). Vì lời gọi quá 5 ứng viên bị bỏ, cần định nghĩa lại `@k` |
| GA-2 | Lời gọi ra ngoài repo gắn với `ExternalSystem` |

## 9. Các ý không phải của proposal

Những ý sau là quyết định của TV2, không được trích là "theo proposal":

- Công thức confidence có trọng số (proposal chỉ có công thức cho GraphDiff, dòng 727).
- Bộ lọc và giới hạn 5 ứng viên. Ngân sách token trong proposal là mặc định 12.000 (dòng 972). Path jail (dòng 1130) nói về quyền truy cập repo.
- Hệ số phạt ở retrieval và phân cấp cảnh báo ở impact (§9.3 của proposal không liệt kê `MAY_CALL`).
- `symbol_candidates` trong incremental (proposal chỉ có `reverse_dependencies`, dòng 1169).
- Node `ExternalSymbol`.

## 10. Việc nhóm cần biết

`MAY_CALL` được sinh mặc định nên mọi graph đều đổi. Schema của `MAY_CALL` chưa qua buổi chốt hợp đồng ([plan] dòng 95), và [plan] Phụ lục B
dòng 470 ghi đáp án test của mỗi người phụ thuộc schema mới. TV1 và TV3 cần được báo trước khi ghép nối.

## 11. Để lại cho người làm

Tên hàm và cách tổ chức helper, cấu trúc index tên, cách tắt nội bộ cho test số 11, và số lượng file test nếu cần tách.
