# Đợt 4: sửa vòng sửa lỗi của agent sau lượt OpenCode A/B trên ShopFlow (TV2, 23/11/2026)

Trạng thái: **phần A và phần B đã cài đặt 23/11/2026** theo plan `docs/superpowers/plans/2026-11-23-tv2-agent-loop-fixes.md`;
phần B qua cổng D2 (R1 dev-50, `docs/status/tv2_batch4_grounding_2026-11-23.md`). Quyết định ở §6.1 áp dụng theo đề xuất (D1 = c, D2 = R1 hai lần, D3 = phần A trước). Khác plan một chỗ: lỗi
`graph_version` cũ giữ mã `GRAPH_NOT_READY` (`StaleGraphVersionError`), vì đó là mã sẵn có của version không có trong
database; `details` vẫn nêu version hiện hành. Nguồn số liệu:
`docs/status/tv2_opencode_ab_shopflow_2026-11-22.md` (lượt A-vi, B-vi, B-en, A-en). Không đổi contract của TV1.

## 1. Vì sao

Nhánh có VGAR (A) không thắng nhánh không VGAR (B) ở cả hai cặp lượt (A-vi sửa đúng 2 lỗi, B-vi 5; A-en 5, B-en 6). Lỗi
nằm ở vòng sửa lỗi mà proposal §9.1 mô tả (tìm anchor → lấy ngữ cảnh → sửa → kiểm → sửa tiếp hoặc nộp), không phải ở thiếu
layer (đã kiểm 23/11: bật SCIP làm retrieval hơi xấu đi, xem §4.8).

| Hiện tượng trong log | Lượt | Nguyên nhân trong code |
|---|---|---|
| Sửa file xong, `get_related_context` báo "Source content differs from graph snapshot; rebuild graph"; agent dựng lại graph, thay đổi chưa kiểm bị nuốt vào graph. A-en: sửa `ship_order` [93] → lỗi [99] → dựng lại [100]; chính thay đổi này gây lỗi mất kho và **không bao giờ được kiểm**. File nháp `test_bug.py` cũng gây lỗi "file set differs" [56]. | A-en | `GraphContextRetriever._verify_snapshot` (`retrieval.py:798-818`) đọc thư mục làm việc và đòi khớp từng byte với graph; gọi ở `retrieval.py:248, 354, 410` và qua `_message_sources` (`sqlite_service.py:118-123`, dùng cho cả `find_task_anchors`) |
| Agent dựng lại graph **trước** khi kiểm → `analyze_patch_impact` ERROR, `verify` NOT_RUN (NO_CHANGES). A-vi: agent vẫn báo PASS; A-en: agent báo đúng "NOT checked" nhưng B09/B13 không được kiểm. | A-vi lỗi 4–5, A-en [111] | `build_or_update_graph` (`graph_server.py:427-454`) nhận mọi thay đổi của thư mục làm việc mà không kiểm; mỗi lần build xoá phiên bản cũ (`sqlite_store.py:718-729`) nên không kiểm lại được |
| Agent truyền `graph_version` cũ → lại nhận "rebuild graph" → dựng lại thừa (ra đúng version cũ). | A-vi ×3, A-en [56]→[57] | `_document` (`sqlite_service.py:73-81`) giữ mãi phiên bản đã bị xoá trong bộ nhớ; lỗi rơi xuống `_verify_snapshot` với thông báo sai lý do |
| `search_symbols("cancel_order ship_order transition_to")` → 0 kết quả | A-en ×3 | Một `LIKE '%cả chuỗi%'` (`sqlite_store.py:340-354`) |
| `find_task_anchors` không trúng hàm lỗi ở lỗi nào: lỗi 1–2 ra `Customer`, lỗi 4 ra `Order`, lỗi 5 không có anchor; lần chạy thử 23/11: 0/5 câu tiếng Anh | A-vi, A-en | Chỉ khớp nguyên tên (`grounding.py:362-364`); chữ hoa đầu câu bị coi là tên code (`grounding.py:393`; cùng nguyên nhân với phân tích W5–W6 ngày 13/10); thông báo lỗi trích trong câu bị bỏ qua vì chỉ nhận dòng có nhãn `XxxError:` (`source_evidence.py:12`) và mảnh thông báo giữ cả dấu câu (`source_evidence.py:84-89`); không có đường lùi khi không tìm được anchor |

## 2. Mục tiêu

- Tool đọc graph (`get_related_context`, `find_task_anchors`) chạy được khi thư mục làm việc đã sửa hoặc có file nháp, và
  trả **mã mà graph được dựng từ đó**, kèm danh sách file đang khác graph.
- Không thay đổi nào đi vào graph mà chưa được kiểm (impact + ràng buộc graph) ít nhất một lần (cách làm: quyết định D1).
- `graph_version` không còn hiện hành → lỗi nói đúng lý do và nêu version hiện hành.
- `search_symbols` nhận nhiều tên trong một truy vấn.
- Grounding theo §6.6 ("symbol mentions", "error messages") và §15 ("fallback to text/embedding"): khớp theo phần của
  tên, không coi chữ hoa đầu câu là code, khớp thông báo lỗi được trích trong câu, lùi về tìm theo văn bản khi không có
  anchor.

**Không làm:** bật SCIP/LSP mặc định (§4.8); grounding route cho router kiểu bảng dispatch; node cho hằng cấp module
(`ALLOWED_TRANSITIONS`, `LOW_STOCK_THRESHOLD`); các mục xếp hạng của bản rà retrieval 22/11; tự chạy test khi build; hỗ trợ
thêm/xoá file trong patch; sửa prompt kịch bản OpenCode.

**Không chấp nhận:** tool ghi vào thư mục làm việc của người dùng (mọi bước kiểm vẫn chạy trên bản sao tạm); kết quả khác
nhau giữa Windows và Linux; luật grounding chỉnh cho vừa 5 câu lỗi của ShopFlow mà làm R1 kém đi (xem §5.2).

## 3. Hai phần, làm theo thứ tự

| Phần | Mục | Đổi xếp hạng R1? | Rủi ro |
|---|---|---|---|
| **A** (vòng agent) | 1. Retrieval đọc mã đã lưu · 2. Build không nuốt thay đổi chưa kiểm + version cũ · 3. `search_symbols` nhiều từ | Không (cùng byte khi thư mục sạch) | Thấp |
| **B** (grounding) | 4. Bốn luật grounding | Có (anchor đổi → ngữ cảnh và trace link đổi) | Trung bình, cần đo lại R1 |

B dựa vào A: luật G3, G4 cần mã nguồn mà A đưa vào retriever (§4.5).

## 4. Thiết kế

### 4.1 Mục 1: retrieval đọc mã đã lưu (phần A)

Đợt 3 đã lưu byte các file `.py` theo từng `graph_version` (bảng `sources`; `SQLiteGraphService.snapshot_sources`
kiểm từng file với `content_hash` của node File). Retrieval vẫn đọc thư mục làm việc.

- `GraphContextRetriever.__init__` nhận thêm `sources: Mapping[str, bytes] | None = None`. Khi có: `_verify_snapshot()`
  trả `sources`, không đọc thư mục làm việc; bước kiểm lại sau khi đóng gói (`retrieval.py:410`) bỏ qua (byte bất biến).
  Khi `None`: giữ nguyên hành vi hiện tại (harness R1/ablation, graph cũ không lưu mã).
- `SQLiteGraphService._retriever` truyền `sources=self.snapshot_sources(graph_version)`. `_message_sources` đi qua
  retriever nên `find_task_anchors` cũng hết bị chặn. Nếu `snapshot_sources` báo mã đã lưu không khớp graph (database
  hỏng), lỗi đó được trả nguyên văn như hiện nay.
- Kết quả `get_related_context` thêm `diagnostics.worktree_changes`: danh sách đường dẫn `.py` đang khác graph (sửa, thêm,
  xoá; so hash một lượt, bằng một trong hai lượt hash hiện nay). Khi danh sách không rỗng, thêm câu nhắc: ngữ cảnh là mã của
  graph; thay đổi ở các file này chưa có trong đó cho tới khi kiểm rồi dựng lại.
- Snippet và số dòng là của graph, khớp với `range` của node (đúng lý do guard cũ tồn tại).
- Chỉ `get_related_context` có `worktree_changes` (tool duy nhất trả mã); `find_task_anchors` trả id và đường dẫn nên không
  cần.
- Thư mục sạch: cùng byte → cùng xếp hạng; test so `rank_hash` hai chế độ.

### 4.2 Mục 2a: build gặp thay đổi chưa kiểm (phần A, **quyết định D1**)

| Cách | Ý tưởng | Được | Mất |
|---|---|---|---|
| a. Cảnh báo | Build như cũ; kết quả có `unchecked_changes` | Ít code nhất | Thay đổi đã bị nuốt; phiên bản cũ bị xoá nên không kiểm lại được |
| b. Chặn | Build từ chối, nêu file và cách kiểm; tham số `allow_unchecked=true` để vượt | Agent buộc phải kiểm; tool vẫn đơn nhiệm | Đổi chữ ký tool (fixture contract); agent có thể quen truyền cờ vượt; đổi nhánh hay `git pull` cũng bị chặn |
| **c. Tự kiểm rồi build (đề xuất)** | Trước khi build, server chạy `analyze_patch_impact` + `verify_patch_graph_constraints` trên diff thư mục làm việc so với graph (dùng lại kết quả nếu agent đã kiểm đúng diff đó), trả kết quả trong `checks_before_update`, rồi build | Mọi thay đổi vào graph đều đã được kiểm ít nhất một lần; không đổi chữ ký tool; khớp §11.2 (cập nhật kèm `recheck_local_invariants`) | Build chậm thêm một lần verify khi agent chưa kiểm (ShopFlow: không đáng kể; repo lớn: thêm một lần dựng graph ứng viên) |

Thiết kế theo c (nếu D1 chọn khác, mục này đổi theo):

- Chỉ ở nhánh build của chính server (`_live().run()`); nhánh host tin cậy của TV1 (`_trusted_build_host`) không đổi.
- Khi đã có graph hiện hành **và** graph có mã đã lưu: `resolve_diff(graph_service, version, "")` (hàm của đợt 3).
  - Không có thay đổi → `checks_before_update: {"status": "NO_CHANGES"}`.
  - `resolve_diff` báo lỗi (diff quá giới hạn, ký tự xuống dòng lạ) hoặc chỉ có thay đổi không kiểm được (file mới, file
    xoá, chỉ đổi xuống dòng) → `{"status": "NOT_RUN", "reason": …, "checked_diff": …}`.
  - Còn lại → `verify` qua `_verified(checked)` (cache sẵn có theo cặp version + diff) và `analyze` qua
    `graph_service.analyze_patch_impact(checked, graph_version=version)` với mặc định của tool (`max_hops=2`,
    `max_nodes=200`) → `{"status": "CHECKED", "verify": {"status", "reasons"}, "impact": {"status", "changed_count",
    "impacted_count", "port_check"}, "checked_diff": …, "tests": "not run"}`. Kết quả đầy đủ vào audit log.
  - `analyze` có cache theo cùng khoá với `verify` (version + sha256 của diff, không lưu kết quả lỗi), để agent đã kiểm
    đúng thứ tự không tốn thêm gì khi build.
  - Lỗi bất ngờ trong bước tự kiểm → `NOT_RUN` với thông báo lỗi; build vẫn chạy.
- Trường `checks_before_update` do tool `build_or_update_graph` trong `graph_server.py` ghép vào kết quả build;
  `LiveGraphBuilder` không đổi.
- Build **luôn tiếp tục**: graph phải phản ánh thư mục làm việc; verdict FAIL được báo, không chặn.
- Chưa có graph (lần build đầu) → không kiểm. Graph cũ không lưu mã → `NOT_RUN` với lý do "graph has no stored source"
  (đợt 3 tự lưu mã ở lần build này).
- Docstring `build_or_update_graph`: nêu việc tự kiểm và trường `checks_before_update`. Thông báo NO_CHANGES của
  `analyze_patch_impact` thêm: "if you just rebuilt the graph, that build checked the change: see checks_before_update".

### 4.3 Mục 2b: `graph_version` không còn hiện hành (phần A)

- Không phục vụ từ bộ nhớ một phiên bản không còn `ready` trong database. Các tool nhận `graph_version`
  (`find_task_anchors`, `get_related_context`, `get_related_tests`, `analyze_patch_impact`) trả lỗi nói đúng lý do:
  "graph_version … is no longer the graph of this repository (each build_or_update_graph replaces it); current: …; use the
  current version and call find_task_anchors again if you need anchors", kèm `details.current_graph_version`.
- Sau mỗi lần server build thành công, bỏ các document/retriever của phiên bản khác khỏi cache (tránh dùng nhầm và tăng bộ
  nhớ). `_tasks` (đề bài đã gắn với `task_id`) giữ nguyên vì chỉ chứa đề bài.

### 4.4 Mục 3: `search_symbols` nhiều từ (phần A)

- Tách truy vấn theo khoảng trắng và dấu phẩy thành các từ (giữ `.` và `_` trong từ để còn tìm theo tên đầy đủ); bỏ trùng;
  bỏ từ ngắn hơn 3 ký tự (trừ khi truy vấn chỉ có một từ); tối đa 10 từ.
- Một từ → đúng câu SQL và thứ tự hiện nay (tương thích ngược).
- Nhiều từ → symbol khớp nếu khớp **bất kỳ** từ nào (cùng ba cột `name`, `qualified_name`, `path`, không phân biệt hoa
  thường, vẫn bỏ module ngoài). Thứ tự: khớp nguyên truy vấn trước (luật hiện nay), rồi số từ khớp giảm dần, rồi trùng nguyên
  tên một từ, rồi `qualified_name`, `id`. Áp `limit` sau khi xếp. Mỗi từ lấy tối đa 200 ứng viên trước khi xếp, để từ ngắn
  như `get` trên repo lớn không kéo cả nghìn dòng.
- Dạng kết quả không đổi. Docstring: nhiều tên cách nhau bằng khoảng trắng trả symbol khớp bất kỳ tên nào, khớp nhiều nhất
  đứng trước.

### 4.5 Mục 4: grounding theo §6.6 (phần B)

| Cách | Được | Mất |
|---|---|---|
| **a. Thêm luật vào `TaskAnchorFinder` / task overlay (đề xuất)** | Đúng §6.6, §15; chạy offline, giải thích được từng anchor; đo được trên R1 | Đổi anchor → đổi xếp hạng R1, trace link; phải đo lại |
| b. Grounding bằng embedding | Bắt được từ đồng nghĩa | Cần model embedding (nặng, chậm), khó giải thích; §6.6 xếp embedding "sau đó" |
| c. Chỉ đổi prompt (agent tái hiện lỗi trước, gửi dòng exception) | Rẻ | Không sửa server; phụ thuộc agent |

Bốn luật (tên evidence mới trong ngoặc). Các loại evidence và điểm hiện có không đổi.

- **G1. Phần của tên** (`name_part`). Tách tên symbol (Class/Function/Method, không gồm Test) thành phần theo `_` và chữ
  hoa giữa tên. Một từ trong đề bài khớp một phần tên khi bằng nhau, hoặc phần tên dài ít nhất 4 ký tự và từ bắt đầu bằng
  phần đó (`cancelled` → `cancel`, `shipped` → `ship`, `reserved` → `reserve`). Điểm symbol theo độ phủ có trọng số IDF
  của phần tên (phần hiếm nặng hơn, ví dụ `coupon` nặng hơn `order`). Chỉ nhận symbol có ít nhất một phần hiếm được khớp và
  độ phủ ≥ 0,5. Điểm anchor 0,3–0,5, tối đa 5 anchor loại này. Không bao giờ cao hơn tên được nhắc đúng nguyên văn. Chỉ áp
  cho đề bài, không áp cho tên test được báo (đã khớp chính xác).
- **G2. Chữ hoa đầu câu** (luật `code_like`, `grounding.py:393`). Một từ chỉ viết hoa chữ cái đầu, không có `_` hay `.`,
  đứng đầu câu (đầu văn bản hoặc dòng, sau `.`, `!`, `?`, `:` hoặc dấu gạch đầu dòng) là chữ thường của câu: điểm 0,4 thay
  vì 0,6. Từ viết hoa giữa câu và tên kiểu `OrderService` giữ luật cũ.
- **G3. Thông báo lỗi được trích** (`quoted_message`). Cụm trong ngoặc kép (thẳng hoặc cong), ít nhất 2 từ, không nằm trong
  code span, được dùng như dòng thông báo cho `message_matches`. So khớp sau khi chuẩn hoá cả hai phía (chữ thường, gộp
  khoảng trắng, bỏ dấu câu ở hai đầu mảnh thông báo): mảnh thông báo nằm trong cụm trích (luật hiện nay của dòng có nhãn),
  hoặc cụm trích có ít nhất 4 từ nằm trong mảnh thông báo. Điểm như `error_message` hiện nay (0,85 khi chỉ một hàm khớp;
  0,5 khi mẫu dùng chung). Luật "mảnh thông báo ít nhất 4 từ" giữ nguyên, nên thông báo chung chung như "invalid email: …"
  vẫn không làm anchor. Luật này sửa ở bộ trích dùng chung (`diagnostic_lines`, `diagnostic_matches` trong
  `source_evidence.py`), nên tín hiệu thông báo lỗi trong xếp hạng của retrieval (`retrieval.py:244-258`) cũng thấy cụm
  trích; phần này nằm trong phép đo R1 của §5.2.
- **G4. Lùi về văn bản** (`text_match`). Khi G1–G3 và các luật cũ không cho anchor nào, xếp các Function/Method (không gồm
  test) theo `SourceEvidence.similarity` giữa thân hàm và các từ của đề bài trên mã đã lưu; lấy tối đa 3 hàm vượt ngưỡng, điểm
  0,2. Graph không lưu mã thì bỏ qua.

Ràng buộc chung:
- Chỉ đọc và phân tích mã nguồn khi cần: đề bài có dòng có nhãn hoặc cụm trích (G3), hoặc không còn anchor nào (G4). Đề bài
  bình thường có anchor thì không phân tích mã (giữ chi phí hiện nay). `SourceEvidence` trên mã đã lưu dựng tối đa một
  lần cho mỗi `graph_version` (mã bất biến), vì issue SWE-bench hay có cụm trong ngoặc kép và repo lớn phân tích mất vài
  giây.
- Đổi `profile` của task overlay (`task-overlay-v13-error-anchors` → v14) để kết quả cũ và mới không bị trộn.
- Ngưỡng và hằng số cụ thể của G1, G4 do người cài đặt chọn trong các giới hạn trên, **chốt trước khi chạy R1** và ghi vào
  báo cáo.

### 4.6 Tương thích

- Chữ ký tool không đổi, nên `tests/fixtures/mcp_server/expected_contract.json` không đổi (fixture không chứa docstring).
  Trường mới trong kết quả: `diagnostics.worktree_changes` (`get_related_context`), `checks_before_update` (build).
- Nhánh host tin cậy của TV1 và contract `DiffRequest` không đổi.
- Harness R1/ablation tạo `GraphContextRetriever` không truyền `sources` → phần A không đổi số R1; phần B đổi grounding nên
  đổi số R1 (đo ở §5.2).
- Database cũ không có bảng `sources` hoặc chưa lưu mã: retrieval giữ hành vi cũ; build báo `NOT_RUN` cho bước tự kiểm.

### 4.7 Tài liệu

Docstring của `build_or_update_graph`, `get_related_context`, `search_symbols`, `find_task_anchors` (theo quy tắc
build-server: docstring có Args, không in ra stdout, logger theo module). README bước 4: build tự kiểm thay đổi chưa kiểm.

### 4.8 Ngoài phạm vi (ghi nhận)

- **SCIP/LSP mặc định:** proposal §5.4 coi "SCIP hoặc LSP" là bắt buộc. Nhưng R1 ngày 18/11 (`tv2_r1_scip_2026-11-18.md`)
  cho thấy SCIP làm retrieval hơi xấu đi (R@5 hàm 0,338 → 0,311 ở cấu hình server; MRR −0,021, CI không chứa 0 ở RT-1),
  build chậm khoảng 16 lần; mọi lần build với layer tuỳ chọn là build lại toàn bộ (`live_build.py:87-88`); runtime chưa cài
  trên Windows. Ghi là lệch §5.4 có chủ đích, kèm bằng chứng; đo lại SCIP sau đợt này cho `get_callers` và
  `analyze_patch_impact` (chưa đo).
- Route kiểu bảng dispatch (ShopFlow: G_arch ghi `route_config: absent`), hằng cấp module, file nháp do agent tạo (server
  không ngăn được; `worktree_changes` liệt kê chúng).

## 5. Kiểm chứng

### 5.1 Phần A

- TDD cho từng hành vi:
  - retrieval có `sources`: sau khi sửa file hoặc thêm file `.py`, `get_related_context` và `find_task_anchors` (đề bài có
    dòng lỗi có nhãn) chạy được; snippet bằng byte đã lưu; `worktree_changes` đúng; graph không lưu mã → hành vi cũ;
    thư mục sạch → `rank_hash` hai chế độ bằng nhau;
  - build (theo D1): có thay đổi → `checks_before_update` đúng trạng thái và dùng lại kết quả verify đã có (spy gọi đúng một
    lần); thư mục sạch → NO_CHANGES; lần build đầu → không kiểm; file mới/xoá hoặc diff quá giới hạn → NOT_RUN và build vẫn
    chạy; graph không lưu mã → NOT_RUN;
  - version cũ: bốn tool trả lỗi nêu version hiện hành; cache bỏ phiên bản cũ sau build;
  - `search_symbols`: truy vấn ba tên trả đủ ba symbol; truy vấn một từ cho kết quả và thứ tự y như cũ; từ ngắn bị bỏ;
    `limit` áp sau khi xếp.
- Toàn bộ bộ test: không thêm lỗi ngoài danh sách lỗi đã biết.
- Chạy tay trên bản sao ShopFlow: build → sửa `order_service.py` → `get_related_context` chạy, có `worktree_changes` →
  build → `checks_before_update` = CHECKED.

### 5.2 Phần B

- Test cho từng luật G1–G4 trên graph tổng hợp, kể cả trường hợp âm (từ phổ biến không tạo anchor; Title-case giữa câu giữ
  điểm cũ; thông báo dưới 4 từ không khớp).
- Thăm dò ShopFlow: 14 dòng mô tả lỗi và 6 quy tắc đặc tả (tiếng Anh, `repair_agent/shopflow_opencode_scenario_en.md`),
  trước và sau: anchor trong top 5 trúng file lỗi và trúng hàm lỗi (theo `buggy_locations` của `bugs.json`). Báo cáo bảng,
  không đặt ngưỡng.
- **R1 dev-50** (WSL, CPU, không cần GPU): chạy **hai lần** trên cùng máy, code sau phần A (nền) và code sau phần B, vì
  `r1_now50` (16/11) dựng trên code cũ hơn (trước sửa xếp hạng R2 ngày 22/11). Khoảng 1,3–1,5 giờ mỗi lần. Trước khi chạy,
  kiểm dữ liệu `~/rt1` còn đủ (đã dọn `graphs/scip`, `scip_lsp`, cache uv ngày 22/11). So cấu hình server `task_trace` và
  RT-1 theo cặp; chấp nhận khi không chỉ số nào có CI95 nằm hẳn dưới 0. Báo cáo trong `docs/status/`.

## 6. Quyết định

### 6.1 Cần TV2 chọn

- **D1. Build gặp thay đổi chưa kiểm** (§4.2): a cảnh báo, b chặn + cờ vượt, **c tự kiểm rồi build (đề xuất)**.
- **D2. Cổng chấp nhận phần B:** **chạy R1 dev-50 hai lần (khoảng 3 giờ CPU trong WSL, mình chạy nền) và không chỉ số
  nào giảm có ý nghĩa (đề xuất)**, hoặc chỉ dùng test + thăm dò ShopFlow (nhanh hơn, nhưng không biết grounding mới có làm
  hỏng SWE-bench không).
- **D3. Thứ tự:** **làm và commit phần A trước, rồi mới làm phần B (đề xuất)**, hoặc làm cả hai rồi commit một lần.

### 6.2 Mình tự chọn (sửa được khi duyệt)

- Ngữ cảnh lấy từ mã của graph, kèm danh sách file đang khác (§4.1), thay vì đọc file đã sửa (file đã sửa lệch số dòng với
  node).
- Version cũ trả lỗi kèm version hiện hành, không tự chuyển sang version mới (anchor cũ có thể không còn đúng).
- `search_symbols` dùng "khớp bất kỳ từ nào" có xếp hạng, không dùng "phải khớp mọi từ" (truy vấn của agent liệt kê nhiều
  tên khác nhau, nên "mọi từ" vẫn ra 0).
- G2 chỉ áp cho chữ hoa đầu câu (không bỏ hẳn Title-case), để tên lớp viết giữa câu trong issue SWE-bench giữ điểm.
- G3 dùng chung điểm và luật "ít nhất 4 từ" của thông báo có nhãn; G4 chỉ chạy khi không có anchor nào.
- Bước tự kiểm khi build không chạy test (chậm); kết quả ghi `tests: "not run"`.
- `analyze` có cache giống `verify`; `search_symbols` lấy tối đa 200 ứng viên mỗi từ; `SourceEvidence` dựng một lần mỗi
  `graph_version`.
- G3 sửa bộ trích thông báo dùng chung, nên retrieval cũng dùng cụm trích (thay vì tách riêng cho grounding và giữ hai luật
  khác nhau).
