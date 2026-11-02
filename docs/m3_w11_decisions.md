# Quyết định M3 cho W11–12

Lập 01/11/2026. Phạm vi: W11–12. Spec chia việc: `docs/superpowers/specs/2026-10-31-w11-w12-parallel-split-design.md` (gọi tắt *spec chia việc*). Spec kỹ thuật: `docs/superpowers/specs/2026-10-31-w11-w12-design.md`. Tiếp nối `docs/m3_w10_decisions.md` (D13–D26).

**Mã:** D1–D20 trong spec là mã nợ, nên các đề xuất ở đây đánh mã **E**.

**Trạng thái chung: M3 ĐỀ XUẤT. Chưa được nhóm duyệt.** Đưa ra buổi họp ngày 1 của W11 (spec chia việc §1.3), duyệt cùng C3, C5, N3.

**Nội dung file:** contract C5 (M1) và C4 (M3) ở cuối file, cùng các đề xuất bổ sung E1–E7.

| ID | Đề xuất | Chủ | Gắn với | Trạng thái |
|---|---|---|---|---|
| E1 | Sửa B10 thì phải đổi nhãn resolver trong `graph_version`, có test khóa | M1 | PR B10 (H2) | **Thay bằng E5 (iii)** (02/11) |
| E2 | Config ranking đóng băng là config mặc định trong code | M1 | C5 | Đề xuất |
| E3 | Viết luật nhận một bước tune trước khi tune | M1 | M1-W11-2 | Đề xuất |
| E4 | Nâng xử lý anchor nhiễu (D5) từ "nếu còn thời gian" thành bước bắt buộc | M1 | M1-W11-2 | Đề xuất |
| E5 | Chỉ chạy lại các ô (task, arm) có context hoặc test link đổi, kèm ô đối chứng | M1 + M3 | N3 | **Chốt hướng (iii)** (02/11); export + so hash chưa chạy, cần chọn chủ |
| E6 | Attempt record ghi hash ranking và `graph_version`; aggregate và fairness không gộp record khác hash | M3, M2 | C3, C5 | Đề xuất; phần M3 (`context_manifest.ranking_config_hash` + runner) đã làm 02/11, chờ M2 duyệt; `fairness.py` (M2) và `aggregate.py` (W12) chưa làm |
| E7 | `solve --agent` (RQ5) chỉ chạy sau H3 | M3 | M3-W12-1 | Đề xuất |

## E1. B10 phải đổi `graph_version`

- **Đề xuất:** PR B10 đổi nhãn resolver trong `_calculate_graph_version` (`src/vgar/graph/builder.py:251`, hiện là `tree-sitter+python-static-v3-method-aliases`) sang một nhãn mới, ví dụ `...-v4-explicit-import`. Thêm test (đề xuất mã **G7**): cùng repo và revision, đổi nhãn resolver thì `graph_version` phải đổi.
- **Lý do:** `graph_version` hiện chỉ hash repo, revision và nhãn viết cứng này. Nếu sửa B10 mà giữ nguyên nhãn thì graph trước và sau B10 có cùng `graph_version`. Handoff và sidecar kiểm khớp theo `graph_version` (`src/vgar/graph/handoff.py:29, 55`), nên graph cũ còn trong cache sẽ được dùng tiếp mà không báo lỗi, và record mới không phân biệt được với record W10.
- **Sửa spec chia việc:** dòng B10 ở §2 (W11 ngày 1–2) thêm G7. Phụ lục A thêm G7.
- **Công:** khoảng 1 giờ, nằm trong PR B10.

## E2. Config đóng băng là config mặc định của code

- **Đề xuất:** thêm vào C5: *"Config đóng băng là giá trị mặc định của `RetrievalConfig` và `_WEIGHTS` trong `src/vgar/graph/retrieval.py`. Hash là sha256 của `asdict(RetrievalConfig())` ở dạng JSON có `sort_keys`. Test G6 khóa giá trị hash này."*
- **Lý do:** cả 4 chỗ tạo retriever đều không truyền `config=` mà dùng giá trị mặc định: `graph/handoff.py:60`, `graph/sqlite_service.py:64`, `evaluation/retrieval/bm25_handoff.py:44`, `evaluation/retrieval/pilot_export.py:54`. Nếu đóng băng bằng một file config riêng mà không sửa giá trị mặc định, chỉ cần một chỗ quên đọc file là chỗ đó chạy config cũ. Khi đó repair loop và MCP graph server không chạy đúng config đã ghi trong protocol freeze, và không có lỗi nào báo ra.
- **Ngoại lệ duy nhất:** dòng "graph trước tune" của bảng R1 truyền tường minh `RetrievalConfig(weights=OLD_WEIGHTS)`. Output dòng này có hash khác nên không lẫn với config đóng băng.
- **Kèm theo:** bảng trọng số ở `docs/m1_retrieval_method.md:147-154` vẫn ghi trọng số gốc của proposal (0.2/0.3/0.2/0.2/0.1/0.1), không khớp code. Code đã đổi từ commit `73814b8f` ngày 12/10 sang 0.5/0.2/0.1/0.2/0.0/0.1. Cần sửa bảng này cùng lúc với E2.

## E3. Luật nhận một bước tune

- **Đề xuất:** M1 ghi luật vào `docs/m1_retrieval_method.md` **trước** khi tune (W11 ngày 3). Bản đề xuất:
  - Mỗi bước (a), (b), (c), (d) so với bước được nhận ngay trước nó, trên cùng 25 task dev, cùng k của bảng R1.
  - **Nhận** bước khi Recall@k trung bình tăng **và** khoảng tin cậy 95% bootstrap ghép cặp theo task (seed cố định, ghi vào doc) của chênh lệch không chứa 0. Nếu không đạt, bỏ bước đó và giữ config của bước trước.
  - Bước (a) là sửa lỗi (B10), luôn được nhận. Vẫn ghi số của nó vào R1.
  - Ghi thêm số task được lợi và số task bị hại của từng bước.
- **Lý do:** spec chỉ yêu cầu "mỗi bước có số Recall@k". Với 25 task, và khoảng tin cậy retrieval ở W10 đã chứa 0, chênh lệch nhỏ có thể chỉ là nhiễu. Nếu không đặt luật trước thì việc chọn config sau khi đã thấy số là overfit dev.
- **Lưu ý về bước (b):** commit `73814b8f` (12/10) đã cố ý đặt `public_api_risk = 0`, với lý do ở `docs/m1_retrieval_method.md:55-57`. Bật lại thì phải qua được luật trên.
- **Lưu ý về bước (c):** bằng chứng của D3 (67 node impacted, phần lớn ở hop 2) là từ **impact** (`graph/impact.py`), không phải retrieval. `RetrievalConfig` không có trọng số theo loại edge. M1 cần chốt bước (c) sửa ở đâu: thêm một field vào `RetrievalConfig` (field đó cũng vào hash C5), hay chuyển sang impact.

## E4. Nâng ưu tiên D5 (anchor nhiễu)

- **Đề xuất:** đưa D5 thành bước (d) bắt buộc của M1-W11-2, đứng ngay sau (a). Hiện spec ghi "nếu còn thời gian".
- **Lý do:** đây là bước có bằng chứng mạnh nhất. Ngày 13/10 đã kiểm lại cả 66 giá trị Recall@5 của W5–6, và các ô Graph có recall = 0 là do anchor nhiễu ở `src/vgar/graph/grounding.py`: token trong code block được coi là explicit, chữ viết hoa đầu câu được coi là code_like (pylint-4604, pylint-6386). Chi tiết ở `docs/m3_w5_w6_zero_recall_analysis.md`. Ngược lại, (b) và (c) mới là giả thuyết.
- **Nếu trễ:** để (b) và (c) xuống ưu tiên thấp thay cho D5, đúng tinh thần "cắt trước" ở §1.7.

## E5. Chỉ chạy lại các ô có context hoặc test link đổi (sửa N3)

- **Đề xuất:** thay N3 "chạy lại A1/A2 × 25 nếu ranking đổi" bằng:
  1. Sau H3, export context của 20 task dev có record engine (60 ô) với graph sau B10 và config đóng băng. Export cần repo của các task, mà repo đang nằm trên máy M3 (`~/w10/repositories`), nên export chạy trên máy M3. Việc này không cần GPU.
  2. So **hai hash** với record W10 của từng ô (task, arm):
     - `stages.prompt.metadata.original_m1_context_sha256`: context đưa vào prompt;
     - `stages.context.hashes["test_links.json"]`: test link lấy từ graph, dùng để chọn test khi verify.
  3. Chỉ chạy lại ô có ít nhất một hash khác, hoặc ô không có hash. Thêm **2 ô đối chứng** có hash không đổi để xác nhận output trùng với W10.
  4. Nếu ô đối chứng ra output khác W10 thì chạy lại toàn bộ, như N3 cũ.
- **Lý do:** decode greedy (`temperature = 0.0`, `src/vgar/config/settings.py:63`), nên cùng model và cùng prompt thì cùng output. Ô có context không đổi không cần GPU.
- **Áp cho cả A0, không chỉ A1/A2.** A0 (`arm: bm25`) không duyệt edge, nhưng corpus BM25 lấy từ node của graph (`evaluation/retrieval/bm25_handoff.py:44-52`), và A0 cũng có `test_links.json` từ graph. B10 chủ yếu đổi edge nên context của A0 nhiều khả năng giữ nguyên, nhưng vẫn phải so để biết chắc. (Đính chính so với nhận định trước: không thể mặc định A0 không bị ảnh hưởng.)
- **⚠️ Phát hiện 01/11 khi làm E1: E1 làm E5 mất tác dụng.** Context render và prompt M2 đều có dòng `Graph snapshot: <graph_version>` (`src/vgar/contracts/prompt_context.py:12`, `src/vgar/repair/context_presentation.py:19`). E1 đổi `graph_version` của mọi graph, nên prompt của **cả 60 ô** (kể cả A0) đều đổi, và bộ lọc hash sẽ đánh dấu chạy lại toàn bộ. Có ba lựa chọn, cần nhóm chọn:
  - (i) giữ E1 và chạy lại toàn bộ A0–A2, khoảng 75 run, khoảng 9 giờ GPU;
  - (ii) bỏ E1, buộc `--rebuild-graphs` khi build bundle, và chấp nhận rủi ro dùng nhầm cache cũ;
  - (iii) giữ an toàn cache bằng một trường `resolver_profile` riêng trong sidecar, **không** đưa vào `graph_version`. Cách này phải đổi contract handoff (M1).

  **Chốt 02/11: hướng (iii), đã implement.**
  - `graph_version` hash nhãn cố định `GRAPH_VERSION_RESOLVER_LABEL` (= nhãn v3 cũ, không bump nữa). Nhờ vậy `graph_version`, dòng `Graph snapshot` và context hash của fixture W9 trùng lại giá trị trước E1 (đã kiểm: fixture W9 dựng lại có `graph_version` `sha256:1a480ca3…` và `context_sha256` `sha256:4895b364…` như HEAD).
  - Resolver thật ghi ở `statistics.resolver.profile` (`RESOLVER_PROFILE`, v4). `context_manifest.json` có thêm `resolver_profile`, là trường không bắt buộc nên sidecar W10 vẫn đọc được.
  - Kiểm ở hai chỗ: `validate_context_handoff(..., expected_resolver_profile=...)` và `create_test_hints` báo lỗi khi profile không khớp.
  - **Không** thêm trường vào `test_links.json`, để hash ở bước 2 vẫn so được với record W10.
  - G7 viết lại: `graph_version` của fixture bằng hash trước B10; profile là v4.
  - Cache retrieval vốn đã an toàn: khóa cache gồm `builder_hash`, tức hash toàn bộ `src/` (`scripts/run_graph_retrieval.py:68`).
  - **Cần M2 review:** contract handoff có thêm trường và thêm tham số không bắt buộc. Consumer của M2 chưa truyền `expected_resolver_profile`.
- **Điều kiện "ranking đổi" phải tính cả graph:** riêng B10 đã làm output retrieval đổi dù trọng số giữ nguyên. Vì vậy điều kiện so là hash, không chỉ trọng số.
- **Đã kiểm record W10 (01/11, M3)** ở `~/w10/results/m3/{9f1b2346fa028094, cfb605118a52b835}/engine/*/attempt-*/*/run_record.json`:
  - Có 20 task có record engine, tức 60 ô. Các task còn lại trong N = 25 là `TASK_EXCLUDED` hoặc `TASK_INPUT_MISSING`, không có record.
  - Có `original_m1_context_sha256`: A0 22/23 record, A1 25/26, A2 23/26. Có `graph_version` (`task.graph_version`) và `stages.context.hashes`: mọi record.
  - **A1 và A2 có cùng context hash ở mọi task.** Đúng như mong đợi, vì hai arm chỉ khác `required_checks`. Một lần export cho mỗi task là so được cả hai arm.
  - **So với attempt cuối của mỗi ô** (attempt được tính sau các lần rerun hạ tầng D22): **60/60 ô có hash**. Các record attempt-1 thiếu hash đều là run hỏng hạ tầng, dừng trước stage prompt và đã được chạy lại. Ví dụ, A2 của django-10914 và sphinx-10673 bị baseline `ERROR` ở attempt-1; attempt-2 có hash trùng với A1 (django `sha256:157d8ece…`, sphinx `sha256:62decbaf…`). Hash context và `test_links.json` giữ nguyên qua mọi attempt của cùng một ô.
  - Script so: phải lấy **attempt có số lớn nhất** của mỗi ô, không lấy attempt-1.
  - Runner A0–A2 **không** gọi `analyze_patch_impact` (chữ "impact" trong record chỉ là text của repo), nên không có output impact cần so.
- **Chủ:** cần chọn. Script export thuộc `src/vgar/evaluation/retrieval/` (của M1). Record W10 nằm trên máy M3. Đề xuất: M1 viết script export, M3 chạy so sánh. Khoảng 0,5 ngày.
- **Sửa spec chia việc nếu duyệt:**
  - **§1.5:** thêm điểm bàn giao **H3b** (W11 ngày 5, M3): danh sách ô phải chạy lại. Spec hiện ghi "chỉ có 5 điểm bàn giao".
  - **§1.6 bước 2:** batch = A3 × 25 cộng các ô trong danh sách H3b cộng 2 ô đối chứng. Có thể có cả ô **A0**: spec hiện không dự trù chạy lại A0.
  - **§1.7 "không cắt":** đổi "chạy lại A1/A2 sau tune (nếu ranking đổi)" thành "chạy lại các ô có hash đổi".
  - **N3 (§1.3):** thay bằng E5.
- **Ảnh hưởng §1.6:** batch W12 có thể ngắn hơn khoảng 10 giờ nếu nhiều ô không đổi.

## E6. Record ghi hash ranking và `graph_version`; không gộp record khác hash

- **Đề xuất:**
  - `runner.py` (M3) ghi `ranking_config_hash` (theo C5) và `graph_version` vào mỗi attempt record của arm graph.
  - `aggregate.py` (M3) và `fairness.py` (M2) chỉ gộp các ô vào cùng một bảng khi **input hiệu dụng** của chúng khớp nhau. Hai cách khớp:
    - **Ô chạy mới:** cùng `ranking_config_hash` và cùng `graph_version`.
    - **Ô giữ lại từ W10 theo E5:** ô này không có `ranking_config_hash`, và (từ khi chốt E5 (iii), 02/11) `graph_version` của nó trùng graph mới, nên `graph_version` không đủ để phân biệt; dùng hai hash ở E5 bước 2. Ô được gộp khi hai hash ở E5 bước 2 trùng với export mới, và record được đánh dấu `reused_from: <experiment W10>` kèm hai hash đó. Quy tắc này áp cho cả A0, A1 và A2.
  - Bảng ghi rõ số ô dùng lại và số ô chạy mới theo từng arm.
- **Đính chính:** bản trước yêu cầu "cùng `graph_version`" cho mọi ô. Quy tắc đó loại mất các ô E5 định giữ lại, vì E1 làm `graph_version` của mọi ô đổi.
- **Lý do:** `policy_hash` (`src/vgar/repair/policy.py:60`) chỉ hash các field của `VariantPolicy`, và theo D17 thì phải như vậy. Hệ quả là A2 chạy config cũ và A2 chạy config mới có cùng `policy_hash`. Fairness hiện tại vì thế không phát hiện được khi bảng trộn record của hai config.
- **Gắn với:** C3 (luật fairness) và C5 (hash). Test đề xuất: aggregate có record A2 với hai hash ranking khác nhau thì từ chối.
- **Lịch:** phần `runner.py` làm cùng PR `samples_failed` (W11 ngày 5, M3). Phần `fairness.py` làm cùng PR `A3.json` (W11 ngày 4, M2). Phần `aggregate.py` làm cùng PR thêm A3 (W12 ngày 2, M3). Không phát sinh slot mới.

## E7. `solve --agent` (RQ5) chạy sau H3

- **Đề xuất:** smoke ở W11 ngày 5 (D20) vẫn chạy chế độ fake như cũ. Lần chạy thật × 5 task ở W12 ngày 4 phải dùng graph sau B10 và config đóng băng. Record ghi hash ranking theo E6.
- **Lý do:** `solve --agent` chạy "config như A2", mà A2 dùng graph retrieval. Chạy trước H3 thì số RQ5 đo trên config khác với config đã ghi trong protocol freeze.
- **Ảnh hưởng lịch:** không đổi. Lịch của spec chia việc (W12 ngày 4) đã nằm sau H3. Phần mới duy nhất là ghi hash theo E6. Mục này chỉ để ghi rõ rằng **không được** chạy `solve --agent` thật sớm hơn lịch.

## C5. Schema config ranking và cách tính hash (M1 đề xuất, M3 duyệt; vì một người giữ cả M1 và M3 nên M2 duyệt thay)

Trạng thái: **đã implement trên working tree ngày 01/11** (plan `docs/superpowers/plans/2026-11-01-m1-w11-graph-ranking.md`, Task 3). Chưa merge.

- **Schema:** config ranking chính là dataclass `RetrievalConfig` (`src/vgar/graph/retrieval.py`). Không có file config riêng. Mọi field đều thuộc config:

  | Nhóm | Field | Mặc định hiện tại |
  |---|---|---|
  | Giới hạn duyệt | `max_hops`, `max_candidates`, `min_edge_confidence` | 2, 100, 0.6 |
  | Trọng số (6 feature) | `weights`: `task_similarity`, `graph_distance`, `edge_confidence`, `failing_test_proximity`, `public_api_risk`, `recent_change_frequency` | 0.5, 0.2, 0.1, 0.2, 0.0, 0.1 |
  | Ngân sách | `reference_budget_fraction` | 0.2 |
  | Cờ evidence | `use_source_evidence`, `prefer_relevant_paths`, `gate_failing_test_evidence`, `use_diagnostic_evidence`, `use_component_seeds`, `use_topic_evidence` | True, True, True, True, True, False |

- **Hash:** `ranking_config_hash(config) = "sha256:" + sha256(json.dumps(asdict(config), sort_keys=True, separators=(",", ":")))`. Thứ tự khóa không ảnh hưởng (test G6b). Đổi bất kỳ field nào thì hash đổi (G6). Hash mặc định hiện tại là `sha256:993f02c9…`.
- **Nơi ghi hash:**
  - `RetrievalResult.config["ranking_config_hash"]`, diagnostics của mỗi lần retrieve;
  - `result.json` của `scripts/run_graph_retrieval.py`, ở `config.retrieval.ranking_config_hash`;
  - attempt record của runner: **E6**, M3 làm ở W11 ngày 5.
- **Không thuộc hash ranking:**
  - `budget_tokens`, counter, snippet policy: đã có trong config của run và trong fairness;
  - graph: định danh bằng `graph_version`, gồm `RESOLVER_PROFILE` và nội dung file (E1).

  Muốn biết một output retrieval đến từ đâu thì phải xem **cặp** `(ranking_config_hash, graph_version)`.
- **Thử từng bước tune:** dùng `--retrieval-config <file.json>`. File chứa một phần field của `RetrievalConfig`; field lạ thì bị từ chối. Đây là cách duy nhất chạy một config khác giá trị mặc định.
- **Đóng băng (E2):** config thắng ở Task 6 được ghi thành **giá trị mặc định** của `RetrievalConfig`. Hash của nó được ghim trong `tests/test_graph_retrieval.py` (G6c) và trong `docs/m1_retrieval_method.md`. Sau tag `protocol-freeze`, đổi config là sửa protocol, cần cả nhóm duyệt.
- **Không ảnh hưởng `policy_hash`:** `policy_hash` của A0–A2 không chứa config ranking (D17). Vì vậy E6 mới là chỗ chặn việc trộn record của hai config ranking khác nhau.

## C4. Envelope và enum mã lỗi MCP (M3 đề xuất, M1 và M2 duyệt)

> **Trạng thái 02/11:** đã làm cho cả 4 server theo đề xuất dưới đây (giữ tên `status`/`request_id`; `TIMEOUT` không retryable). `repair_server` trả envelope, verdict của engine ở `data.verdict`; client đọc qua `agents/nodes/mcp_repair._unwrap`. Hai câu hỏi ở cuối mục vẫn cần M1 và M2 xác nhận khi review PR.

### Hiện trạng (kiểm code 01/11)

- **Đã có một envelope** ở `src/vgar/mcp/schemas.py`: `{status, data, error{code, message, details}, metadata{duration_ms, request_id, ...}}`. `src/vgar/mcp/tooling.py:run_tool` bọc mỗi call, luôn ghi một dòng audit có `request_id`, và giấu message của lỗi lạ (`INTERNAL_ERROR`).
- **Graph server** đã dùng envelope này cho cả 7 tool. `tests/test_mcp_tool_contract.py` (11 test) khóa hành vi đó.
- **Ba server còn lại không dùng envelope:**
  - `repair_server` trả `{status, reason, detail, ...}` ở cấp ngoài cùng; mọi lỗi đều là `reason: TOOL_ERROR`.
  - `repository_server` và `execution_server` trả dict tự do, `status` có thể là `OK`, `PASS`, `FAIL` hoặc `ERROR`.
- **`status` đang mang hai nghĩa.** Ở graph, `ERROR` nghĩa là *tool không trả lời được*. Ở repair, `ERROR` có thể là *tool trả lời được, nhưng verification chưa hoàn tất* (verdict của engine M2). Agent không phân biệt được hai trường hợp này, nên không biết lúc nào cần sửa lời gọi và lúc nào cần sửa patch.

### Đề xuất

**1. Giữ envelope đang có, không đổi tên field.** Spec chia việc §1.3 đề xuất `{ok, data | error, audit_id}`. Bản dưới đây giữ đúng ngữ nghĩa đó nhưng giữ tên field cũ, để graph server và 11 test hiện có không phải sửa:

| Spec §1.3 | Field giữ lại | Quy tắc |
|---|---|---|
| `ok` | `status` ∈ {`PASS`, `ERROR`} | `PASS` khi tool trả lời được, `ERROR` khi không. **Bỏ `FAIL` và `NOT_RUN` khỏi envelope** |
| `data` | `data` | Có khi và chỉ khi `status = PASS` |
| `error{code, message, retryable}` | `error{code, message, retryable, details}` | Có khi và chỉ khi `status = ERROR`. **Thêm `retryable: bool`** |
| `audit_id` | `metadata.request_id` | Trùng với `request_id` của dòng audit. Thêm `metadata.server` |

**2. Verdict của repair nằm trong `data`, không nằm ở envelope.** Ví dụ, `verify_patch` khi verification chưa hoàn tất trả:

```json
{"status": "PASS",
 "data": {"verdict": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
          "recommendation": "REJECT", "evidence": {}, "run_dir": "..."},
 "error": null,
 "metadata": {"request_id": "...", "duration_ms": 0, "server": "repair", "tool": "verify_patch"}}
```

`data.verdict` giữ nguyên giá trị của engine M2 (`PASS`/`FAIL`/`ERROR`, theo `recommendation_for` trong `src/vgar/repair/pipeline.py:38`). `run_relevant_tests` và `apply_patch` làm tương tự. Cách này **không đổi** `run_record.mcp_calls`, evidence hay `policy_hash`.

**3. Text lấy từ repo** (S12, S16): `metadata.untrusted = true` cho mọi tool trả nội dung file, snippet hoặc docstring. `data.truncated` là cờ báo output bị cắt theo trần do server đặt (S5, S16).

**4. Resource** (`vgar://graph/...`) vẫn trả document thô và lỗi ở cấp protocol, như hiện tại. Resource vẫn được audit (`audit_resource`). S10 chỉ áp cho tool.

### Enum mã lỗi (`src/vgar/mcp/schemas.py`)

`retryable` nghĩa là gọi lại **đúng lời gọi đó, không sửa gì**, có thể thành công. Agent không được retry mã có `retryable = false` mà giữ nguyên tham số.

| Mã | retryable | Khi nào | Test |
|---|---|---|---|
| `INVALID_ARGUMENT` | false | Tham số sai kiểu hoặc giá trị (`ValueError` ở biên) | đã có |
| `INTERNAL_ERROR` | false | Lỗi không lường trước. Message chỉ có tên exception; message đầy đủ chỉ nằm trong audit | đã có |
| `INVALID_QUERY`, `INVALID_LIMIT`, `NODE_NOT_FOUND`, `GRAPH_ERROR` | false | Giữ nguyên mã của `GraphError` (`src/vgar/contracts/error.py`) | đã có |
| `GRAPH_NOT_READY` | **true** | Graph đang được index (index lười trong `work_dir`) | đã có |
| `PATH_OUTSIDE_ROOT` | false | Path thoát khỏi root theo lease | S1 |
| `ROOT_NOT_LEASED` | false | `repo_path` hoặc `run_dir` không thuộc lease | S2 |
| `SELECTOR_REJECTED` | false | Selector test không qua bộ kiểm | S3 |
| `TIMEOUT` | false | Hết timeout do server đặt; cả cây tiến trình đã bị dừng | S4 |
| `TOOL_ORDER_VIOLATION` | false | Gọi sai thứ tự `get_task_context → apply_patch → run_relevant_tests → verify_patch` (hiện là `ValueError` ở `repair_server.py:47`) | mới |
| `RUN_NOT_FOUND` | false | `run_dir` không tồn tại hoặc không có `session.json` | mới |
| `MCP_TRANSPORT_ERROR` | false | **Phía client**: server chết hoặc mất kết nối. Hiện `tool_agent.py:252` tự tạo `TOOL_ERROR` | mới |

`TOOL_ERROR` bị **bỏ**. Mã nào không có trong bảng thì contract test fail.

Output bị cắt **không phải lỗi**: tool vẫn trả `PASS` với `data.truncated = true`. Test fail cũng không phải lỗi: `PASS` với `data.verdict = FAIL`.

### Phạm vi và người sửa

- **M3:** `schemas.py`, `tooling.py`, `repair_server.py`, `repository_server.py`, `execution_server.py`, `graph_server.py` (từ W11 ngày 3), `agents/tool_agent.py`, `agents/nodes/mcp_repair.py`, `agents/workflow.py`, `agents/feedback.py`, `docs/mcp_tool_contract.md`, `tests/test_mcp_tool_contract.py`.
  - Các consumer trong `agents/` hiện đọc `result["status"]`, `result["reason"]`, `result["detail"]` ở cấp ngoài cùng, phải đổi sang `data.verdict`, `data.reason` hoặc `error.code`.
  - `health()` của các server cũng trả envelope.
  - Graph tool đã đúng hình dạng envelope. Phần còn thiếu là `metadata.server` và `metadata.untrusted` (vì `get_related_context` trả snippet). Hai phần này thêm qua `run_tool` sau W11 ngày 3, khi `graph_server.py` đã thuộc M3.
- **M1:** không phải sửa gì. Không đụng PR B02 (W11 ngày 1–2).
- **M2 (C6):** runner test chung **không** tự dựng envelope. Runner trả kết quả thường, hoặc raise exception có thuộc tính `code` lấy từ enum trên (`SELECTOR_REJECTED`, `TIMEOUT`). `run_tool` lo phần map sang envelope. Engine M2 cũng không phải đổi gì. **Mục này sửa C6 ở spec chia việc §1.3**, vì C6 hiện ghi runner "trả kết quả theo C4".
- **Lịch (spec chia việc §4):** spec đặt envelope C4 vào W11 ngày 5. Nhưng legacy server (ngày 1–2) và security S1–S5 (ngày 4) đã sửa cùng các file server, và cần các mã `PATH_OUTSIDE_ROOT`, `ROOT_NOT_LEASED`, `SELECTOR_REJECTED`, `TIMEOUT`. Vì vậy:
  - **enum** trong `schemas.py` cùng `retryable` vào PR đầu tiên của ngày 1–2;
  - repository và execution server viết theo envelope ngay ở ngày 1–2, không sửa hai lần;
  - ngày 5 chỉ còn `repair_server`, các consumer ở `agents/` và test S10.

  Mỗi phần vẫn là một PR riêng, mỗi PR ≤ 300 dòng (§1.2).
- **Không ảnh hưởng ablation:** runner A0–A3 (`evaluation/repair/launch.py`) gọi thẳng `run_repair`, không qua MCP (D20). Record W10 và `policy_hash` vì vậy không đổi.

### Test S10 (`tests/test_mcp_tool_contract.py`)

- Tham số hóa theo **mọi tool đã đăng ký ở cả 4 server**. Mỗi tool có một call thành công và một call lỗi, và cả hai đều validate được bằng `ToolResponse`.
- `error` có khi và chỉ khi `status = ERROR`; `data` có khi và chỉ khi `status = PASS`.
- `error.code` thuộc enum, và `retryable` khớp bảng.
- `metadata.request_id` có trong đúng một dòng audit (gộp với S8).
- Tool trả text từ repo có `metadata.untrusted = true` (gộp với S12).

### Cần nhóm chốt

1. **Giữ tên field cũ (`status`, `request_id`) hay đổi sang `ok`, `audit_id` như spec §1.3?** M3 đề xuất giữ tên cũ, vì graph server và 11 test đã chạy với tên này. Nếu đổi tên thì phải sửa cả graph server, chạm file của M1 trong W11 ngày 1–2.
2. **`TIMEOUT` có nên `retryable = true` không?** M3 đề xuất `false`: timeout do server đặt và có tính tất định, nên gọi lại nguyên tham số sẽ lại timeout và chỉ tốn lượt của agent.
