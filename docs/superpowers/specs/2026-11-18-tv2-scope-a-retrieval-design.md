# Thiết kế: Phạm vi A cho retrieval (TV2, R1) — 18/11/2026

> **Tạm dừng 19/11/2026:** người dùng đưa code lõi về đúng bản đã commit (bám proposal) để làm agent harness trước; quay lại phạm vi A sau. Kết quả tune25 và patch test/cánh nằm trong `.superpowers/sdd/2026-11-18-tv2-scope-a-retrieval/`.

Trạng thái: **bản nháp, chờ duyệt.** Nhóm đã chọn (a): làm phạm vi A trên tập dev, đăng ký vào bản freeze, rồi mới chạy
held-out. Song song có luồng B (`docs/status/tv2_option_b_parallel_plan_2026-11-18.md`).

Cập nhật 18/11 (sau khi xem đường đi qua MCP): lọc anchor theo cách **hạ trần hạt giống trong `_walk`** (mục 3.1);
thêm **cấu hình phục vụ** cho MCP server (mục 3.5), danh sách mục khung xương trong `diagnostics`, test qua MCP, và sửa
nhãn "cấu hình phục vụ" trong tài liệu R1.

## 1. Vì sao làm

R1 trên 50 task dev cho thấy nút thắt của graph nằm ở **danh sách ứng viên và thứ hạng mức hàm**, không nằm ở độ đủ
của cạnh:

| Bằng chứng | Số |
|---|---|
| Graph thuần thua baseline văn bản ở mức hàm | R@5 hàm: `task_trace_rt1` 0,363; BM25 0,389; neighbor 0,471 |
| Hàm gold không vào danh sách ứng viên | reach hàm 0,573 (trung bình theo task); khoảng 40–48% hàm gold không có mặt |
| Anchor nhiễu | 96,7 anchor/task, tối đa 727; hạt giống bị cắt cứng ở 50 (`_anchor_seed_limit`) |
| Thêm cạnh đúng không giúp, còn làm loãng | SCIP: recall cạnh 0,418 → 0,527 nhưng MRR hàm −0,021 (CI [−0,049; −0,004]); full layer: không chỉ số nào tăng |
| Gói context luôn lấp 12k token; 42% là thân class/file/module | mô phỏng 12 task |

Mô phỏng trên dữ liệu đã lưu (không phải số đo của code mới):
- Mở rộng method con **theo file** rồi **xếp lại theo thân hàm**: R@5 hàm 0,363 → khoảng 0,41; R@1 hàm 0,147 → 0,222.
  Nếu chỉ nối thêm vào cuối danh sách thì top-5 không đổi.
- Trần reach nếu mở rộng theo file của anchor: 0,50 → 0,69–0,76 (gộp theo hàm).
- Giữ top-20 anchor vẫn giữ được 34/36 task có anchor nằm trong file gold.
- Khung xương cho class/file/module: cùng nội dung giảm khoảng 37% token; file gold lên sớm 2.719 → 1.296 token.

## 2. Mục tiêu và giới hạn

**Mục tiêu:** một cấu hình retrieval mới, gọi là cánh `task_trace_a`, chỉ dùng graph (không trộn văn bản), tốt hơn
`task_trace_rt1` ở mức hàm và gói context gọn hơn, đo trên dev rồi đăng ký vào bản freeze.

**Không làm trong phạm vi này:** PPR, PCST, đóng gói theo vai trò, điểm đa tín hiệu có trọng số học, SCIP/LSP,
trộn RRF vào cánh chính, đổi bộ đếm token, sửa proposal. Các mục này là hướng mở rộng.

**Không được làm hỏng:**
- `RetrievalConfig()` và `RT1_CONFIG` giữ nguyên `ranking_config_hash` (bản freeze đã ghi hash của `RT1_CONFIG`).
- Server MCP (`get_related_context`) giữ hành vi cũ: mọi thứ mới nằm sau cờ mặc định tắt.
- Hợp đồng `ContextPayload` không đổi trường.

## 3. Thiết kế

Ba thay đổi về xếp hạng và đóng gói trong `src/vgar/graph/retrieval.py`, dùng bốn trường mới của `RetrievalConfig`
(`anchor_seed_limit`, `file_expansion`, `skeleton_packing`, `pack_stop_ratio`), cộng một chỗ chọn cấu hình cho MCP
server (3.5). Giá trị tắt của bốn trường được thêm vào `RT1_FLAG_DEFAULTS`, nên `ranking_config_hash` của các cấu
hình cũ không đổi.

### 3.1 Hạ trần hạt giống của `_walk`: `anchor_seed_limit: int = 0` (0 = giữ trần cũ)

- **Hiện tại:** không có ngưỡng điểm nào loại anchor. `_walk` sắp mọi hạt giống theo độ ưu tiên
  `0,5 × độ giống với issue + 0,3 × điểm anchor` rồi giữ tối đa `_anchor_seed_limit()` = `max_candidates // 2` = 50
  hạt giống (`retrieval.py:670-673, 704-711`). Trung bình 96,7 anchor/task nên trần 50 thường bị chạm.
- **Làm gì:** khi `anchor_seed_limit > 0`, `_anchor_seed_limit()` trả về giá trị này thay cho `max_candidates // 2`.
  **Cách chọn giữ nguyên** (độ ưu tiên của `_walk`), chỉ hạ số lượng. Vì độ ưu tiên đã pha độ giống với issue, các anchor
  cùng điểm (thường 0,75) được phân định bằng nội dung chứ không bằng `node_id`.
- **Giữ nguyên số hạt giống component:** `component_limit` (`retrieval.py:251`) hiện tính từ `_anchor_seed_limit()`.
  Nó phải tiếp tục tính từ trần cũ (`max_candidates // 2`), để thay đổi chỉ tác động lên hạt giống anchor.
- **Qua MCP:** không phụ thuộc overlay hay `issue_text`. Khi agent không gửi `issue_text`, độ giống bằng 0 và thứ tự
  rơi về điểm anchor rồi `node_id`, như hiện tại; không có trường hợp bị bỏ hết anchor.
- **Trần áp chung cho mọi hạt giống:** như hiện tại, trần của `_walk` tính chung cho hạt giống anchor, chẩn đoán,
  component và trace (`retrieval.py:704-711`); chúng vẫn vào `starts` như cũ và cạnh tranh theo cùng độ ưu tiên.
  Hạ trần vì vậy có thể bỏ cả hạt giống chẩn đoán/component có độ ưu tiên thấp; đây là chủ ý (một trần, một luật chọn).
- **Không đổi:** kiểm tra hợp lệ của mọi `anchor_ids`, điểm anchor trong chấm điểm, cách dựng từng loại hạt giống.
- **Vì sao không lọc theo điểm anchor:** nhiều anchor cùng điểm 0,75 nên thứ tự sẽ phụ thuộc `node_id`; và qua MCP, khi
  thiếu `issue_text` thì overlay không có điểm, dễ bỏ nhầm anchor. Con số "top-20 giữ 34/36 task có anchor gold" đo theo
  điểm anchor nên chỉ là tham khảo; số thật lấy từ lượt chỉnh trên `tune25`.

### 3.2 Mở rộng method con theo file, xếp lại theo thân hàm: `file_expansion: int = 0` (0 = tắt)

- **Ở đâu:** trong `retrieve()`, sau `_walk` (`retrieval.py:278`), trước khi tính điểm ứng viên.
- **Làm gì:**
  1. Lấy tập file chứa các hạt giống anchor mà `_walk` đã thật sự dùng (sau trần ở 3.1).
  2. Lấy mọi nút `Function`/`Method` thuộc các file đó mà chưa có trong `states` và qua được `include`.
  3. Xếp chúng theo `self._source_evidence.similarity(node_id, task_words)` (từ khóa thân hàm, trọng số IDF, đã có
     sẵn cho mọi hàm), giữ `file_expansion` nút đầu **tính cho cả task** (không phải mỗi file), bỏ các nút có độ giống
     bằng 0. Anchor là nút `File` thì dùng chính file đó. Không có `issue_text` (không có từ để so) thì bước này không
     thêm nút nào.
  4. Thêm vào `states` với `distance = 1`, `confidence = 0,85 × điểm anchor của file` (lấy điểm anchor cao nhất trong
     file), `rationale = ("FILE_EXPANSION",)`.
- **Chấm điểm:** các nút mở rộng đi qua **đúng** công thức 6 đặc trưng như mọi ứng viên khác
  (`task_similarity` qua `_path_similarity`, nên chúng được chấm theo độ giống trực tiếp). Chúng **cạnh tranh** với ứng
  viên cũ chứ không bị nối vào cuối.
- **Độ dài danh sách:** sau khi chấm điểm, danh sách ứng viên cắt lại còn `max_candidates` (100) như cũ. Như vậy reach
  và R@k so được công bằng với `task_trace_rt1` (cùng độ dài danh sách); mở rộng chỉ có lợi nếu nút mới thắng nút cũ.
- **Vì sao theo file chứ không chỉ theo class:** mô phỏng cho thấy mở rộng theo class chỉ thêm khoảng +0,06 reach,
  theo file thêm tới khoảng +0,19.

### 3.3 Đóng gói khung xương và dừng sớm: `skeleton_packing: bool = False`, `pack_stop_ratio: float = 0.0`

- **Ở đâu:** vòng đóng gói (`retrieval.py:344-400`) và `_snippet` (`retrieval.py:816`).
- **Khung xương:** khi bật, mục loại `Class`, `File`, `Module` được đóng gói dưới dạng khung xương: dòng import, dòng
  khai báo class, chữ ký mỗi `def` kèm `...`, bỏ thân hàm. Dựng bằng `ast` trên đúng đoạn mã của nút. Mục
  `Function`/`Method` giữ nguyên thân đầy đủ. `token_count` tính trên văn bản khung xương.
- **Luật chồng lấn:** hiện tại một mục class đã chọn chặn mọi method nằm trong nó
  (`overlapping_selected_range`). Khi bật khung xương, **chỉ mục có thân đầy đủ mới chặn** các mục nằm trong nó;
  mục khung xương không chặn method bên trong, để thân method gold vẫn vào được gói. Nếu thân đầy đủ của một method đã
  có, khung xương của class bao nó vẫn được phép (chỉ thêm chữ ký).
- **Dừng sớm:** khi `pack_stop_ratio > 0`, ngừng đóng gói khi `relevance_score` của ứng viên tiếp theo nhỏ hơn
  `pack_stop_ratio × relevance_score` của ứng viên đầu. Ghi lý do `score_below_stop_ratio` vào `omissions`.
  Dùng tỉ lệ so với ứng viên đầu thay vì ngưỡng tuyệt đối, vì thang điểm khác nhau giữa các task.
- **Không đổi:** ngân sách 12.000 token vẫn là trần; phần đặt chỗ cho dependency (`reference_budget_fraction`) giữ nguyên.
- **Báo cho agent:** `RetrievalResult` thêm danh sách node được đóng gói dạng khung xương; `SQLiteGraphService`
  đưa nó vào `diagnostics.skeleton_items` của kết quả MCP. Chỉ **thêm khóa** trong `diagnostics`; các trường của
  `ContextPayload` không đổi nên client cũ không hỏng. Agent muốn xem thân đầy đủ thì gọi `read_file`
  (tool `read_symbol` là đề xuất A2, ngoài phạm vi này).

### 3.4 Cánh đo mới

- `ablation_matrix/retrieval_variants.py`: thêm `task_trace_a = ("overlay", {**RT1 flags, anchor_seed_limit,
  file_expansion, skeleton_packing, pack_stop_ratio}, False)` với giá trị đã chỉnh ở mục 4.
- `ablation_matrix/run_r1_ablation.py`: thêm cặp `task_trace_a − task_trace_rt1` và `task_trace_a − task_trace` vào
  `PAIRS`. Việc đổi `PRIMARY_PAIRS` để ở bước đăng ký freeze (điểm đồng bộ S2 với luồng B).

### 3.5 Cấu hình phục vụ cho MCP server

- **Hiện trạng (đã kiểm):** `graph_server.get_related_context` (`src/vgar/mcp/servers/graph_server.py:228`) gọi
  `SQLiteGraphService.get_related_context` **không truyền `config`**, nên server dùng `RetrievalConfig()` mặc định
  (`may_call_factor = 0`). Cấu hình đó tương đương cánh **`task_trace`** của R1, không phải `task_trace_rt1`.
- **Thêm:** hằng `SERVED_CONFIG` trong `src/vgar/graph/retrieval.py`; `graph_server.py` truyền
  `config=SERVED_CONFIG` xuống service. Trong phạm vi này **`SERVED_CONFIG = RetrievalConfig()`**: hành vi server giữ
  nguyên, chỉ làm rõ chỗ chọn cấu hình.
- **Sau held-out:** nếu cánh thắng là `task_trace_a` (hoặc `RT1_CONFIG`), đổi `SERVED_CONFIG` bằng một dòng, kèm test
  và ghi vào báo cáo. Không đổi trước held-out, để agent và R1 không lệch nhau trong lúc đo.
- **Sửa nhãn tài liệu:** các chỗ gọi `task_trace_rt1` là "cấu hình phục vụ" (chú thích `PRIMARY_PAIRS` trong
  `run_r1_ablation.py`, báo cáo R1, `tv2_r1_scip_2026-11-18.md`, `tv2_open_issues_2026-11-18.md`) đổi thành
  "ứng viên RT-1"; ghi rõ server hiện chạy cấu hình tương đương `task_trace`.
- **Đo tác động lên agent thật** (số lần gọi tool, file đọc thừa) là M1 của TV1, làm sau khi `SERVED_CONFIG` đổi.

## 4. Cách chỉnh và kiểm chứng

Tách tập theo RT-1: chỉnh trên `~/rt1/tune25.txt`, kiểm chứng trên 25 task còn lại của bộ dev. Ghi rõ trong báo cáo
rằng cả 50 task đã từng được xem trong phân tích R1; kết luận chính chỉ đến từ held-out.

**Chỉnh tuần tự trên `tune25`** (mỗi bước giữ giá trị tốt nhất của bước trước):

| Bước | Biến | Giá trị thử | Chọn theo |
|---|---|---|---|
| 1 | `anchor_seed_limit` | 10, 20, 30 (3.2, 3.3 tắt) | R@5 hàm, rồi reach hàm, rồi giá trị nhỏ hơn |
| 2 | `file_expansion` | 20, 50, 100 | R@5 hàm, rồi MRR hàm |
| 3 | `skeleton_packing` + `pack_stop_ratio` | bật + 0; bật + 0,3; bật + 0,5 | token context ít nhất mà Recall@B hàm không giảm quá 0,02 so với bước 2 |

Mỗi giá trị là một cánh trong cùng lượt chạy; graph build một lần mỗi task, mỗi cánh chỉ thêm 1–5 giây.
Khoảng 9 cánh × 25 task: dưới 1 giờ.

**Bổ sung luật chọn cho lượt lưới (chốt 19/11 18:32 UTC, khi lượt lưới mới xong 11/25 task và chưa ai xem kết quả):**
bài toán gốc là lỗi đa file, nên ngoài R@5/MRR hàm, một cánh chỉ được chọn nếu so với cánh nền của bước đó
(`a_seed20` cho mức mở rộng; cánh `a_e*` đã chọn cho đóng gói) **không giảm quá 0,02** ở cả hai chỉ số
`packed_all_gold_files_in_context` (đủ mọi file gold trong gói) và `packed_frontier_in_context` (frontier recall@B).
Mọi bảng so sánh báo thêm riêng nhóm task có ≥ 2 file gold.

**Tiêu chí thành công, ghi trước khi chạy kiểm chứng** (so với `task_trace_rt1` trên 25 task kiểm chứng và trên cả 50 task):

| Chỉ số | Tiêu chí |
|---|---|
| Reach hàm (trung bình theo task) | ≥ 0,64 (hiện 0,573) |
| R@5 hàm | không thấp hơn 0,363; mục tiêu 0,40–0,42 |
| Recall@B hàm | không giảm quá 0,02 |
| Đủ mọi file gold trong gói (`packed_all_gold_files_in_context`) và frontier recall@B | không giảm quá 0,02; báo riêng nhóm ≥ 2 file gold |
| Token context | giảm ít nhất 30% trung bình (khi có khung xương + dừng sớm) |
| Token tới hàm gold đầu tiên | báo cáo cả hai cách: chỉ task trúng, và đủ task với task trượt = 12.000 |

Đạt tiêu chí thì `task_trace_a` vào bản freeze làm cánh chính (phương án (i) của luồng B). Không đạt thì freeze với
`task_trace_rt1` (phương án (ii)) và phạm vi A chỉ được báo cáo như thử nghiệm trên dev.

**Thử thêm, không bắt buộc:** `task_trace_a` trên graph có SCIP, để kiểm tra giả thuyết "cạnh đúng chỉ có ích khi xếp hạng
chặt hơn". Lượt này mất vài giờ vì phải lập index SCIP.

**Luật chạy:**
- Không chạy cùng lúc với G1 hay lượt đo nặng khác.
- **Không dùng `--prune`** khi chỉnh trên `tune25`, để không xóa archive và cây mã của kit G1 (lỗi E10).
- Ra thư mục kết quả mới, ví dụ `~/rt1/results/scope_a_tune25` và `~/rt1/results/scope_a_val25`.

## 5. Kiểm thử

Thêm vào `tests/test_graph_retrieval.py` (dùng fixture nhỏ có sẵn), mỗi test thất bại trước khi cài và qua sau khi cài:

1. `RetrievalConfig()` và `RT1_CONFIG` giữ đúng `ranking_config_hash` cũ.
2. `anchor_seed_limit=1` với hai anchor: `_walk` chỉ dùng một hạt giống (hạt có độ ưu tiên cao hơn); số hạt giống
   component không đổi so với cấu hình mặc định.
3. `file_expansion`: một method cùng file với anchor, có từ trong thân trùng issue nhưng không nối bằng cạnh, xuất hiện
   trong ứng viên với rationale `FILE_EXPANSION`; method cùng file nhưng độ giống bằng 0 thì không.
4. Danh sách ứng viên khi bật mở rộng vẫn không dài quá `max_candidates`.
5. `skeleton_packing`: mục class được đóng gói không còn thân method, ít token hơn, và thân đầy đủ của một method bên
   trong class vẫn được đóng gói.
6. `pack_stop_ratio=0,5`: ứng viên có điểm dưới một nửa ứng viên đầu bị bỏ với lý do `score_below_stop_ratio`.
7. Qua MCP (`tests/mcp_server`): `get_related_context` của graph server truyền `SERVED_CONFIG` xuống service;
   khi `SERVED_CONFIG` bật khung xương thì kết quả có `diagnostics.skeleton_items`; khi `issue_text` rỗng thì lệnh
   vẫn trả về context, không lỗi và không mất anchor.
8. `SERVED_CONFIG == RetrievalConfig()` (server giữ nguyên hành vi trong phạm vi này).

Chạy lại các bộ test liên quan (`tests/test_graph_retrieval.py`, `tests/mcp_server`, `ablation_matrix/tests`).

## 6. Rủi ro

| Rủi ro | Giảm thế nào |
|---|---|
| Mở rộng theo file kéo vào nhiều hàm không liên quan ở file lớn | Giới hạn `file_expansion`; bỏ nút có độ giống bằng 0; cắt danh sách về 100 sau khi chấm điểm |
| Khung xương làm mất thân hàm gold khi method gold chỉ có mặt qua mục class | Luật chồng lấn mới cho phép thân method đầy đủ vào gói; mở rộng 3.2 đưa method thành mục riêng |
| Dừng sớm làm giảm Recall@B | Chỉnh trên `tune25` với tiêu chí Recall@B không giảm quá 0,02 |
| Chỉnh quá khớp trên dev | Tách 25/25; số chính chỉ lấy từ held-out |
| 14/50 task không có anchor nào trong file gold | Ngoài tầm của phạm vi A; ghi là giới hạn |
| Hạ trần bỏ mất hạt giống đúng có độ ưu tiên thấp | Thử 10/20/30 trên `tune25`, chọn theo R@5 hàm rồi reach; chọn giá trị nhỏ hơn chỉ khi bằng nhau |
| Agent không gửi `issue_text` qua MCP | 3.1 không phụ thuộc overlay; 3.2 tự không thêm nút; test 7 kiểm tra trường hợp này |
| Agent chỉ thấy chữ ký ở mục khung xương | `diagnostics.skeleton_items`; agent dùng `read_file`; tool `read_symbol` (A2) là việc sau |
| `SERVED_CONFIG` đổi khi chưa có số held-out | Trong phạm vi này giữ `RetrievalConfig()`; test 8 khóa lại; chỉ đổi sau held-out |

## 7. Công việc và thời gian

| # | Việc | Thời gian |
|---|---|---|
| 1 | Test cho mục 5 (thất bại trước) | 1 giờ |
| 2 | Cài 3.1 và 3.2 | 2–3 giờ |
| 3 | Cài 3.3 (gồm `diagnostics.skeleton_items`) | 3–4 giờ |
| 4 | Cài 3.5 (`SERVED_CONFIG`) + sửa nhãn tài liệu | 0,5 giờ |
| 5 | Cánh `task_trace_a` + cặp trong `PAIRS` | 0,5 giờ |
| 6 | Chỉnh trên `tune25` (chạy sau khi G1 xong) | khoảng 1 giờ máy |
| 7 | Kiểm chứng 25 task + báo cáo dev | khoảng 1 giờ máy + 1 giờ viết |
| 8 | Gửi cấu hình cho luồng B (điểm đồng bộ S2) | — |

Tổng: khoảng 2 ngày làm việc tới điểm S2.

## 8. Để lại cho người làm

- Cách dựng khung xương bằng `ast` (giữ decorator hay không, xử lý class lồng nhau) miễn là đúng mục 3.3 và test 5.
- Tên chính xác của trường omission mới, miễn là có ghi lý do.
- Cách giữ `component_limit` tính từ trần cũ (ví dụ một hàm riêng cho trần mặc định), miễn là test 2 qua.
- Cách đưa danh sách khung xương từ `RetrievalResult` sang `diagnostics.skeleton_items`, miễn là không đổi trường của
  `ContextPayload`.
