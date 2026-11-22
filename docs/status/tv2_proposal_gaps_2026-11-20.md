# Đối chiếu proposal với code: các mục lệch, chưa làm và quyết định (20/11/2026)

- Proposal: `D:\kltn\proposal_vgar_mcp_final_corrected.md` (đọc đủ 1.596 dòng, §0–§19).
- Plan chia việc: `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (TV1: Layer 6, bảo mật, cập nhật dần, RP1, M1,
  ablation; TV2: Layer 1–3, retrieval, impact, R1, G1, U1; TV3: Layer 4–5, GraphDiff, invariant, evidence, §12, V1, GD1, I1).
- Cách làm: đọc code `src/vgar` (graph, mcp, repair, evaluation), đếm loại node/cạnh trên 50 graph đã dựng
  (`~/rt1/graphs/base`), đọc log T2 (v1, v2, `nav_k20`). Không chạy lại từng kiểm tra; chỗ ghi "chưa thấy" dựa trên grep,
  có thể code có nhưng đặt tên khác.
- Ký hiệu: ✅ theo proposal · ◐ một phần hoặc khác cách · ✗ chưa có · **L** = lệch · **C** = chưa làm.
- Spec chỉnh phần TV2 (chờ duyệt): `docs/superpowers/specs/2026-11-20-tv2-proposal-alignment-design.md`.
- Kết quả T2 trước khi chỉnh (`nav_k20`): `docs/status/tv2_layer_harness_2026-11-19.md`.

## 1. Mức phủ theo từng mục của proposal

| Mục | | Ghi chú |
|---|---|---|
| §1–3, §16–19 | – | Không cần code. GNN đã bỏ khỏi lõi; code không có GNN |
| §4.1 Arch-CPG 8 thành phần | ✅ | G_task tạo theo từng task (overlay), không lưu trong graph |
| §4.2 G_code | ◐ | Joern tùy chọn, chỉ ở bản dựng `full`; graph `base` chỉ có `CallSite`; chưa có CodeQL |
| §4.3 G_repo | ✅ | Graph `base` có Module, File, Class, Function, Method, Test, CallSite, Import; CONTAINS, IMPORTS, CALLS, INHERITS, TESTS, MAY_CALL. Field/GlobalVariable/REFERENCES chỉ khi bật tree-sitter-graph |
| §4.4 G_arch | ✅ | Component, Port, Connector, ExternalSystem; DEPENDS_ON, EXPOSES/CONSUMES_PORT, CONTAINS_COMPONENT, COMMUNICATES_WITH. Service/DeploymentUnit/DEPLOYS_TO có code, không xuất hiện trên repo SWE-bench |
| §4.5 G_task | ✅ | Đủ 10 loại node; MENTIONS, TRACES_TO, REPRODUCES, CONFLICTS_WITH |
| §5.2 Layer 1 / 5 | ✅ | tree-sitter (tree-sitter-graph tùy chọn); Daikon (`repair/daikon.py`), pytest, mypy/ruff |
| §5.2 Layer 2 / 3 / 4 / 6 | ◐ | Có SCIP, LSP, JARVIS, Joern (tùy chọn), RefactoringMiner, SQLite, MCP. Chưa có ts-morph, SootUp/WALA, CodeQL, Glean, Kythe, UTango, Kùzu/Neo4j; GumTree chỉ so offline |
| §5.4 Core MVP | ✅ | tree-sitter, SCIP/LSP, SQLite, MCP, pytest |
| §6.1–6.4 | ✅ | Mọi cạnh có confidence và provenance (`source_tool`, `evidence`, `extractor`, `rule_id`) |
| §6.5 Lift | ✅ | Cohesion/coupling đúng công thức; DEPENDS_ON có trọng số; co-change "unavailable" |
| §6.6 Trích G_task | ◐ | Thông báo lỗi chưa thành anchor |
| Trace links | ✅ | `trace_links.py` (TR-1: P 0,45, R 0,58 ở ngưỡng ≥ 0,7) |
| §7.1–7.2 | ✅ | Graph edit có confidence và bằng chứng |
| §7.3–7.5 GraphDiff | ◐ | Chưa phát hiện tangled (`tangle_risk` = None); diff `ast` thay GumTree; GD1 chờ nhãn người |
| §8.1, §8.4, §8.5 | ✅ | `get_related_context`; schema validator + dựng G' sau patch; evidence 9 trường + score(patch) |
| §8.2, §8.3 | ◐ | F\* chỉ gồm hàm; chưa đo tỉ lệ patch thành công |
| §9.1, §9.2 | ◐ | Không có agent chạy trọn vòng; retrieval có phần không theo proposal |
| §9.3 Impact | ✅ | Đủ 5 loại cạnh và đặc trưng rủi ro |
| §10.1–10.4 | ✅ | 3 server; 8/8 resource; 11/11 tool; prompt 7 bước |
| §10.5 Bảo mật | ◐ | Tool graph chỉ đọc không có giới hạn thời gian; prompt injection chỉ đánh dấu "untrusted" |
| §11 Cập nhật dần | ◐ | Nối lại cả repo (U1: 12/12 khớp, nhanh 3,2–11×), không lần ngược phụ thuộc |
| §12.1–12.5 | ◐ | Thiếu: anchor bắt buộc, fan-out, route/OpenAPI, invariant đáng ngờ, bộ test rộng hơn |
| §13.1–13.3 | ◐ | Thiếu baseline xác minh, chỉ số sửa lỗi và xác minh, A4/A5 |
| §14 | ◐ | M1 có (chỉ Python); M2 vượt baseline văn bản ở mức file, chưa ở mức hàm; M3 có code, chưa đo tiêu chí; M4, M5 một phần |
| §15 | ◐ | Chưa cho ghi đè kiến trúc thủ công; fallback text/embedding chỉ có ở phần đo offline |

## 2. Tool và workflow so với proposal

### 2.1 Mười một tool lõi (§10.3): đủ tên và tham số chính

| Tool | Khớp | Ghi chú |
|---|---|---|
| `build_or_update_graph` | ◐ | Ghi graph, chỉ repo đã cấu hình, giới hạn 900 giây; cập nhật dần khác §11.2; không có bước xác nhận riêng |
| `search_symbols` | ✅ | Proposal không quy định cách xếp (code xếp theo chữ cái) |
| `find_task_anchors` | ◐ | Component chỉ nằm trong cạnh G_task; thông báo lỗi không thành anchor |
| `get_related_context` | ◐ | Giới hạn 100 ứng viên, hạt giống phụ, bỏ MAY_CALL, giữ 20% ngân sách, trả `diagnostics`, nhận `issue_text` từ agent |
| `get_callers` / `get_callees` | ◐ | Không trả confidence/provenance |
| `explain_dependency_path` | ✅ | Đường ngắn nhất có loại cạnh, có giới hạn |
| `analyze_patch_impact` | ✅ | `max_hops` thay `max_depth`, gắn `graph_version` thay `repo_path` |
| `verify_patch_graph_constraints` | ✅ | Dựng G' trên bản sao rồi kiểm (§8.4) |
| `run_relevant_tests` | ✅ | Chạy test trước/sau patch trên bản sao |
| `rank_patch_candidates` | ✅ | Đủ điều kiện xếp trước, rồi theo score(patch) |

Thêm ngoài §10.3: `read_file` (repository server), `get_related_tests`, `run_pytest`, `health`. Server không đặt
`instructions`; mô tả tool nói tool làm gì, không nói khi nào dùng.

### 2.2 Workflow §9.1 / §10.4

| Điểm | Khớp | Ghi chú |
|---|---|---|
| Có tool cho mọi bước; prompt `repair_with_graph_context` 7 bước | ✅ | Bước 1 `find_task_anchors` → 2 `get_related_context` → 3 `read_file` → 5 `analyze_patch_impact` → 6 `run_relevant_tests` + `verify_patch_graph_constraints` |
| `get_context_subgraph(anchor, k=2)` | ◐ | Có ở dạng resource `vgar://graph/subgraph/{id}?k=2`; agent chỉ gọi tool không dùng được |
| Host gắn dữ liệu task | ◐ | Gắn `graph_version`, `task_id`; không gắn `issue_text` |
| Bước 3 "chỉ đọc file graph chọn" | ◐ | Chỉ là hướng dẫn |
| Ai chạy vòng lặp | ✗ | Repo không còn agent chạy trọn vòng (`vgar solve --agent` đã gỡ); T2 chỉ chạy bước 1–3 với prompt riêng |

## 3. Danh sách 36 mục lệch hoặc chưa làm

### TV2 (Layer 1–3, retrieval, impact)

| # | Loại | Mục | Proposal | Code hiện tại |
|---|---|---|---|---|
| 1 | L | §9.2 | Gom hết vùng k=2 rồi xếp hạng; chỉ giới hạn tài nguyên | Dừng ở 100 ứng viên, tối đa 50 hạt giống, chọn trước bằng công thức ưu tiên riêng |
| 2 | L | §9.2 | Chỉ lặp qua `task_anchors` | Tự thêm hạt giống từ thông báo lỗi và tên thư mục |
| 3 | L | §9.2, §6.4 | Giữ MAY_CALL confidence thấp; xếp hạng bằng `edge_confidence` | Ngưỡng 0,6 loại toàn bộ MAY_CALL khi đi graph |
| 4 | L | §9.2 | `pack_until_budget(ranked)` | Giữ 20% ngân sách cho phụ thuộc của 3 hạt giống đầu |
| 5 | L | §9.2 | 6 đặc trưng | `public_api_risk` trọng số 0; `recent_change_frequency` tắt mặc định |
| 6 | L | §10.3 | `get_related_context(anchor_ids, budget_tokens)`, task đã gắn | Nhận `issue_text` từ agent (agent rút gọn) |
| 7 | L | §9.2 | Trả gói context | Kèm `diagnostics` khoảng 3.250 token (chung với TV1) |
| 8 | L | §6.4 | Cạnh có confidence, provenance | `get_callers`/`get_callees` không trả (store TV2, tool TV1) |
| 9 | L | §9.1 | Ứng viên "files/functions/components" | Component chỉ trong cạnh G_task |
| 10 | L | §6.6 | Trích "error messages" | Chỉ node từ tên exception; khớp nội dung lỗi nằm trong retrieval |
| 11 | C | §6.5 | Tín hiệu co-change | "unavailable" |
| 12 | L | §8.2 | F\* gồm Route, Config, Test | F\*_approx chỉ gồm hàm |
| 13 | C | §13.1 | Baseline "repo graph + architecture lift" | Arm `arch_no_task_trace` có trong R1, chưa có profile trong harness |
| 14 | C | §13.2 | Chất lượng ranh giới component | Có công cụ, chờ nhãn người |
| 15 | L | §9.1, §10.4 | Prompt nhận `issue_text` từ host | Harness T2: Qwen tự viết lại issue |
| 16 | L | §10.4 | Prompt 7 bước | Harness T2 dùng prompt riêng |
| 17 | C | §9.1, §10.2 | `get_context_subgraph` | Harness T2 không cho dùng resource |

### TV1 (Layer 6)

| # | Loại | Mục | Proposal | Code hiện tại |
|---|---|---|---|---|
| 18 | C | §9.1 | Agent chạy trọn vòng: sửa → impact → test → sửa tiếp | Không có agent trong repo |
| 19 | C | §13.2, §8.3 | Chỉ số sửa lỗi | Chưa đo được (phụ thuộc #18) |
| 20 | C | §13.3 | A4, A5 | Chưa chạy (phụ thuộc #18) |
| 21 | L | §10.5 | Giới hạn thời gian mọi tool | Tool graph chỉ đọc không có |
| 22 | L | §10.5 | Từ chối prompt injection | Chỉ đánh dấu "untrusted" |
| 23 | L | §10.5 | Thao tác ghi cần xác nhận | Dựa vào quyền của host/client |
| 24 | L | §11.2–11.3 | Lần ngược phụ thuộc, O(Δ + Fanout) | Nối lại cả repo, O(N); chỉ resolver tĩnh |

### TV3 (Layer 4–5, §12)

| # | Loại | Mục | Proposal | Code hiện tại |
|---|---|---|---|---|
| 25 | C | §7.3 [2] | Phát hiện tangled kiểu UTango | `tangle_risk` = None, trọng số 0 |
| 26 | C | §7.5, §14 M4 | Đánh giá bằng nhãn tay; bộ dữ liệu nhãn | Có công cụ, chưa có nhãn |
| 27 | C | §12.1 | Không mất anchor bắt buộc | Chưa thấy |
| 28 | C | §12.2 | Không tăng fan-out mất kiểm soát | Chưa thấy |
| 29 | C | §12.3 | Đổi route; xóa trường schema/protobuf/OpenAPI | Route báo `ROUTE_FACTS_UNAVAILABLE`; schema/OpenAPI chưa có |
| 30 | C | §12.4 | Invariant mới đáng ngờ | Chưa thấy; Daikon trong Docker còn vướng (ghi chú 14/11, chưa kiểm lại) |
| 31 | C | §12.5 | Bộ test rộng hơn khi chi phí cho phép | Chưa thấy |
| 32 | L | §8.5 | Trừ `w_risk × impact_risk` đo thật | Ghi "chưa đo", trừ sẵn mức phạt tối đa |
| 33 | C | §13.1 | Baseline xác minh 4 bậc | Chưa thành cánh chạy được |
| 34 | C | §13.2 | FAR, FRR, overfitting, vi phạm schema, phá API | Chưa đo được |
| 35 | C | §2.2 RQ3 | Impact graph so với "đọc diff thuần văn bản" | I1 mới so với mốc "cùng thư mục" |
| 36 | C | §14 M3 | Bắt patch rủi ro, giảm chạy toàn bộ test, evidence mỗi patch | Có code, chưa đo theo tiêu chí |

Tổng: 18 lệch, 18 chưa làm. TV2 17 mục (14 code, 3 harness), TV1 7, TV3 12.

### Lệch có lý do hoặc chỉ khác tên (ghi vào luận văn)

- §7.3: diff `ast` thay GumTree (benchmark 68 commit tổng hợp: ast + RefactoringMiner F1 0,94, GumTree + RefactoringMiner 0,81).
- §6.3–6.4: `CONTAINS` thay `HAS_METHOD`/`HAS_CALLSITE`; CallSite nối bằng `CALLS` thay `RESOLVES_TO`.
- §6.2: dựng repo một lần, G_task và trace theo từng task.
- §10.3: tham số `analyze_patch_impact` khác tên. §10.4 bước 3 chỉ là hướng dẫn.
- Các con số proposal không cho (trọng số §7.4, §8.5, §9.2; điểm confidence của cạnh và anchor) là lựa chọn của nhóm.

### Ngoài MVP (§5.4, Milestone 5)

ts-morph, SootUp/WALA, CodeQL, Glean, Kythe, Kùzu/Neo4j; G_code chỉ khi bật Joern; §6.6 "sau đó mới thêm
embedding/classifier" chưa làm, đúng thứ tự proposal.

## 4. Quyết định bỏ hay làm

| | Cần làm | Bỏ được (ghi lý do) | Cân nhắc (cần công người) |
|---|---|---|---|
| TV1 | 18, 19, 20, 21; làm chung 7, 8 với TV2 | 22, 23, 24 | – |
| TV2 | 1, 2, 3, 4, 6, 7, 9, 10, 13, 15, 16, 17 (+ 8 vì rẻ) | 5, 11, 12 | 14 |
| TV3 | 28, 32, 33, 34, 35, 36; phần Docker của 30 (nếu chạy A5) | 25, 27, 29, 31, phần "đáng ngờ" của 30 | 26 |

Lý do bỏ được:

| # | Lý do |
|---|---|
| 5 | Proposal không cho trọng số; kiểm chứng mức 2 trên dev: trọng số chỉ quyết định khoảng 7% hàm gold; bộ dữ liệu không có lịch sử commit |
| 8 | §6.4 chỉ yêu cầu lưu confidence/provenance (graph đã lưu); vẫn nên làm vì rẻ |
| 11 | 1 trong 8 tín hiệu heuristic của §6.5; cần lịch sử commit; G_arch không giúp ở T1 (MRR −0,016) |
| 12 | Repo thư viện hiếm route/config; test bị loại ở mọi cánh cho công bằng (spec 17/11 §2.4) |
| 22 | Tool tự ép chính sách, đúng cách giảm rủi ro của §15 |
| 23 | Client MCP hỏi quyền người dùng trước mỗi lời gọi tool |
| 24 | Kết quả bằng đúng bản dựng lại; tốc độ đã đo (§11.3 chỉ đòi đo) |
| 25 | Retrieval mặc định không dùng đầu ra GraphDiff |
| 27 | Câu chữ §12.1 không rõ, giá trị thấp |
| 29 | Không áp dụng cho repo thư viện |
| 30 | Phần chính (invariant bị vi phạm) đã có |
| 31 | §12.5 ghi "nếu chi phí cho phép" |

Không nên bỏ #18–20 (vòng sửa lỗi): bỏ là thu hẹp đề tài, cần cả nhóm quyết định. #33–36 đo được mà không cần #18
(patch gold và patch đột biến).

Thứ tự đề xuất: TV1 chọn agent cho #18 và TV3 làm #33–36 song song ngay; TV2 làm phần của mình sau T2; việc nhỏ (#21, #28,
#32, #7, #8) làm xen kẽ; A4/A5 (#20) chạy cuối. Ba hướng cho agent của #18: mở rộng harness T2 (Qwen, rẻ, nhưng pilot W9
được 0/6); agent thật nối qua MCP (đúng §1, §10, tốn API); thiết kế GPT điều phối + Qwen fine-tune (07/11, chưa có spec).

## 5. Bằng chứng đo được (làm cơ sở cho các mục trên)

- **Qwen rút gọn issue (#6, #15):** trong 61 lượt cánh graph của v1 và v2, `find_task_anchors` được gọi 9 lần, chỉ gửi
  2–46% độ dài issue (trung vị khoảng 4%), không lần nào ≥ 90%. `get_related_context` 8 lần, mỗi lần 1–2 anchor,
  `issue_text` 44–60 ký tự ở 7/8 lần.
- **Giới hạn 100 ứng viên với agent thật (#1):** 2 lần gọi có log đầy đủ (v2) không chạm giới hạn (16 và 94 ứng viên),
  không có hạt giống phụ. Việc chạm giới hạn ở 47/50 task của T1 là do T1 đưa toàn bộ anchor của G_task vào.
- **Ngưỡng 0,6 chỉ loại MAY_CALL (#3):** trên 3 graph `base` (requests-1724, django-10914, sympy-13480), mọi cạnh dưới 0,6
  đều là MAY_CALL (974; 54.207; 52.759 cạnh); mọi loại cạnh khác đều ≥ 0,6.
- **Qwen ít đi theo §9.1 (#15–17):** `nav_k20`, 50 lượt cánh graph: `find_task_anchors` 7, `get_related_context` 6,
  `explain_dependency_path` 1; `grep` 179, `read_file` 114, `search_symbols` 57, `get_callees` 33, `get_callers` 21.
  Câu trả lời trung vị 1 file, 1 hàm.

## 6. Đính chính trong quá trình đối chiếu

- §9.2 `extract_context_graph(task_anchors)` nhận anchor từ bên gọi. T1 (không có agent) đưa toàn bộ anchor của G_task
  vẫn là cách đọc hợp lệ; chỗ lệch thật là giới hạn 100 ứng viên. T2 là vòng agent của §9.1.
- §7: phương pháp GraphDiff (§7.3) chạy tự động; nhãn tay chỉ dùng để đánh giá (§7.5, Milestone 4).
- #8: theo chữ proposal không bắt buộc (§6.4 chỉ yêu cầu lưu), nhưng nên làm.

## 7. Bước tiếp theo

1. Duyệt spec `docs/superpowers/specs/2026-11-20-tv2-proposal-alignment-design.md` (13 mục TV2).
2. Viết kế hoạch triển khai; code theo TDD; chạy cả bộ test.
3. T1 từng bước (B0→B4) và profile `A1_arch`; chọn giới hạn tài nguyên N.
4. T2 v3: chỉ chạy cánh `graph_v1`, dùng lại cánh `base` của `nav_k20`.
5. Cập nhật bản freeze held-out, nhóm ký, chạy held-out một lần.
6. Gửi danh sách mục của TV1 (18–24) và TV3 (25–36) cho họ.

## 8. Cập nhật 21/11 (sau plan alignment, chưa commit)

Kiểm lại với code trong working tree (không có commit code nào sau bản audit). TV1/TV3 không ai sửa; kiểm mẫu #18, #21,
#25, #28, #32 vẫn như cũ.

### 8.1 Trạng thái 36 mục

| # | Trước | Nay | Ghi chú |
|---|---|---|---|
| 1 | L | ✅ | Gom hết k=2; giới hạn tài nguyên N = 6.000 (bao 49/50 task, lựa chọn của nhóm §10.5) |
| 2 | L | ✅ | Hạt giống chỉ là anchor |
| 3 | L | ✅ | MAY_CALL đi graph với confidence đã lưu |
| 4 | L | ✅ | Đóng gói thuần (phần giữ ngân sách chưa từng chạy trên graph `base`) |
| 5 | L | L (bỏ) | `public_api_risk` 0, `recent_change_frequency` tắt — như quyết định 20/11 |
| 6 | L | ✅ | Xếp hạng theo task đã gắn bởi `find_task_anchors` |
| 7 | L | ✅ | Kết quả chỉ còn `traversal_limited`, `budget`; audit giữ top-20 ứng viên + tổng số (giới hạn 64 KiB/dòng) |
| 8 | L | ✅ | Callers/callees có confidence, resolution, source_tool |
| 9 | L | ✅ | `find_task_anchors` trả `components` |
| 10 | L | ✅ | Thông báo lỗi thành anchor (lớp exception; chuỗi log khi có source) |
| 11, 12 | C, L | (bỏ) | Như quyết định 20/11 |
| 13 | C | ✅ | Profile `A1_arch`; đo: bằng A1 trên mọi metric |
| 14 | C | C | Chờ nhãn người |
| 15–17 | L, L, C | ✅ | Cánh `graph_v1`: issue gắn sẵn, prompt §10.4, `get_context_subgraph` |
| 18–24 (TV1) | | không đổi | #18 không có agent; #21 tool graph chỉ đọc chưa có timeout |
| 25–36 (TV3) | | không đổi | #25 `tangle_risk` None; #28 fan-out `NOT_RUN`; #32 trừ phạt tối đa khi chưa đo |

### 8.2 Lệch mới hoặc còn sót

| # | Loại | Mục | Proposal | Code hiện tại | Người |
|---|---|---|---|---|---|
| 37 | L | §9.2 | Ứng viên gồm `components_depending_on(anchor)` | Cờ `use_component_dependents` có nhưng mặc định tắt | TV2 |
| 38 | L | §10.2 | Resource `vgar://graph/subgraph/{id}?k=2` | Harness T2 đọc alias cũ `vgar://graph/subgraph/{id}` (cùng nội dung k=2; URI chuẩn cần host gắn context) | TV2 |
| 39 | L | §10.5 | Resource limit mỗi tool | `find_task_anchors` với issue có dòng log parse lại source mỗi lần (`message_matches`); retriever lạnh trên sympy ~40 s | TV2 |
| 40 | C | §13 | Held-out đo một lần theo bản freeze | Hash cấu hình đổi (`sha256:5849ebb8…`); bản freeze nháp chưa cập nhật, chưa ký | TV2 + nhóm |
| 41 | L | §9.1 | Agent đi trọn vòng | Harness T2 dừng sau bước 3 (đo định vị); phụ thuộc #18 | TV1 |

Đọc lại đủ §4–§15 ngày 21/11 (lần 2), thêm:

| # | Loại | Mục | Proposal | Code / đánh giá hiện tại | Người |
|---|---|---|---|---|---|
| 42 | C | §4.5 | `TESTS: Test -> Requirement/Function` trong G_task | Có `TESTS` Test→Function (G_repo); không tạo `TESTS` Test→Requirement | TV2 |
| 43 | C | §8.3, mục tiêu đề tài | Graph có ích khi gold patch phụ thuộc cross-file facts | Bộ dev 50 task chỉ 5 task nhiều file (45 task 1 file): mọi so sánh nhiều file có n = 5 | TV2 + nhóm |

Đã kiểm, khớp: §4.3/§4.4/§4.5 đủ loại node; cạnh IMPLEMENTS, REFERENCES, CONFIGURES, DEPLOYS_TO, G_code (AST_CHILD,
CFG_NEXT, DATA/CONTROL_DEPENDS_ON qua Joern); §6.5 ghi đủ 8 tín hiệu (co-change "unavailable" = #11); §6.6 route,
labels, acceptance criteria, Requirement; §7.4 đủ 5 thành phần (tangle_risk = #25); §11.3 U1 đo cả cache hit rate;
§13.1 baseline retrieval đủ (grep, BM25, embedding ở R1, neighbor, agent no-graph ở T2) và baseline graph đủ (AST-only,
A1, A1_arch, A2, A3/full); §13.2 MCP usability đo tool calls, latency, file đọc không cần.

### 8.3 Theo tiêu chí §14 Milestone 2 (kết quả đo, không phải lệch code)

- Tiêu chí: "improve gold file/function recall over grep/BM25/embedding baseline". T1 A2 (mặc định mới, n = 50): file R@1
  0,337 (bm25 0,247, neighbor 0,287: thắng); file R@5 0,683 (bm25 0,707, neighbor 0,747: thua); fn R@1 0,147, fn R@5
  0,311, fn MRR 0,260 (neighbor 0,222 / 0,471 / 0,384: thua). Mặc định mới thua code cũ ở frontier trong context
  (−0,041, CI loại 0). → Chưa đạt ở mức hàm.
- T2 (`graph_v1`, sau khi sửa bộ chấm): bằng no-graph về độ đúng, nửa số lời gọi tool; thua `graph_v0` không có ý nghĩa.
  Ngân sách 3.000 (`graph_v1_b3000`, 50 task): frontier đã thấy +0,077 (CI loại 0), fn R@1 không đổi (0,320).
