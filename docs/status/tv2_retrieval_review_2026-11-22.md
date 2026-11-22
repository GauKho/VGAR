# Review `src/vgar/graph/retrieval.py` (22/11/2026)

Chỉ đọc, không sửa (chuỗi đo layer đang chạy server từ working tree). Mỗi điểm được kiểm bằng code liên quan hoặc dữ
liệu thật: graph `base`/`scip` trong `~/rt1/graphs`, audit log của `nav_v3/graph_v1` (47 lần gọi `get_related_context`,
top-20 ứng viên mỗi lần).

## Điểm có ảnh hưởng thật

### R1. Anchor gần như luôn đứng hạng 1 (dòng 314–325)

Công thức (không có failing test, không có lịch sử): `relevance = (0,5·task_similarity + 0,2·confidence/(1+d) +
0,1·confidence) / 0,8`. `confidence` vào hai đặc trưng (`graph_distance` và `edge_confidence`); proposal §9.2 liệt kê hai
đặc trưng riêng. Với anchor độ giống 0,20, confidence 1,0 (điểm 0,500), hàng xóm 1 bước phải có độ giống > 0,40, hàng
xóm 2 bước > 0,47 mới vượt được anchor. Độ giống thường nằm trong khoảng 0–0,4.

Dữ liệu: hạng 1 là anchor ở 30/47 lần gọi (64%). Trong T2, Qwen truyền trung vị 1 anchor, nên hạng 1 thường chính là
anchor Qwen chọn; retrieval khó đưa một hàng xóm đúng hơn lên trên. Khớp với: đổi N (48/49 task cùng hạng 1) và đổi ngân
sách không đổi kết quả.

### R2. Hàng xóm thừa hưởng độ giống của anchor, hòa điểm thì xếp theo chữ cái (dòng 758–770, 339–340)

`_path_similarity` cho mọi node đi tới qua quan hệ ngữ nghĩa điểm `max(độ giống riêng, độ giống của anchor × 0,7^d)`.
Nguồn thừa hưởng là anchor xuất phát (`rationale[1]`), không phải node liền trước. 237/853 ứng viên không phải anchor trong
top-20 (28%) dùng điểm thừa hưởng. Nhóm ứng viên cùng điểm tuyệt đối trong một top-20: trung vị 3, lớn nhất 16; hòa điểm
được tách theo khoảng cách rồi theo `path`, `symbol` (thứ tự chữ cái). Hạng 1 chưa lần nào hòa với hạng 2, nên ảnh hưởng
nằm ở hạng 2 trở xuống — chính là các hạng mà ngân sách 3.000 thêm vào.

### R3. Gói context chứa nhiều test và khối lớn (dòng 28, 341–403)

Trong 379 mục được đóng gói ở `graph_v1`: 72 Test (19%), 53 Class, 20 Module, 1 File; 115 lần một hàm bị loại vì chồng
vùng với khối đã chọn. Proposal §9.2 có `tests_covering(anchor)` nên đưa test vào là đúng chữ, nhưng với việc tìm chỗ sửa,
test chiếm ngân sách (đánh giá loại test khỏi gold). Có thể xếp test sau code hoặc tách riêng.

## Giả định ngầm (đúng trên dữ liệu hiện tại)

### R4. Nguồn của `CALLS`/`IMPORTS`/`MAY_CALL` luôn là node được chứa (dòng 489–506)

Code thay nguồn bằng cha `CONTAINS` của nó. Nếu một extractor tạo `CALLS` từ Function thẳng tới Function, lời gọi sẽ bị gán
cho class/file chứa hàm. Kiểm trên flask, xarray (`base`) và flask (`scip`): mọi `CALLS`/`MAY_CALL` từ CallSite, mọi
`IMPORTS` từ Import, không node nào có hơn một cha `CONTAINS`. Nên thêm kiểm tra (bỏ qua hoặc báo lỗi khi nguồn không phải
CallSite/Import) để không sai âm thầm khi thêm extractor.

## Hiệu năng

### R5. Mỗi lần gọi đọc và hash lại cả repo hai lần (dòng 244, 349, 405)

`_verify_snapshot` chạy trước khi xếp hạng và sau khi đóng gói (~1,1 s mỗi lần trên sympy khi profile). Cùng với
`SourceEvidence` lạnh (~40 s lần đầu trên sympy, đã đo 20/11), `trace.emit` cho từng ứng viên (tới 6.000) và việc sắp xếp
lại hàng xóm ở mỗi bước `_walk` (dòng 741–743). Không đổi kết quả.

## Nhỏ

- R6. `public_api_risk` cộng vào relevance (rủi ro bị dùng như độ liên quan); trọng số 0 nên chưa có tác dụng.
- R7. Chuỗi `profile: semantic-context-v10-source-cache` trong diagnostics không còn khớp phiên bản; dòng 568 có khoảng
  trắng thừa giữa điều kiện.

## Đã kiểm, không phải lỗi

- `failing_tests` (dòng 221–222): chỉ lấy `REPRODUCES` có đích là Issue, nguồn là node Test thật của graph
  (`task_overlay.py:107`); loại `FailingTest → BugReport` (dòng 207) bị lọc.
- Một node nhiều cha `CONTAINS`: không có trên graph đã kiểm.

## Đính chính 22/11 (khi bắt đầu sửa)

- R1: bỏ nhân `confidence` khỏi `graph_distance` **không** giảm lợi thế của anchor. Với anchor confidence 1,0 hai công thức
  cho cùng ngưỡng (hàng xóm 1 bước cần độ giống > 0,40); với confidence 0,5–0,7 công thức mới còn làm ngưỡng tăng
  (0,30–0,34 → 0,40). Nguyên nhân thật là chính đặc trưng khoảng cách (trọng số 0,2 cho `1/(1+d)`) so với độ giống thường
  0–0,4. Thay bằng thử trọng số `graph_distance` 0,2 / 0,1 / 0 qua `--arm-flags` (không đổi code).
- R4: không phải rủi ro thật. Schema (`contracts/schema.py` `EDGE_ENDPOINTS`) chỉ cho `CALLS`/`MAY_CALL` từ CallSite và
  `IMPORTS` từ Import, và `GraphContextRetriever` gọi `validate_graph_document` khi khởi tạo; graph sai bị từ chối ngay.
- R2: đã sửa — sắp xếp theo `-relevance_score`, rồi `-direct_task_similarity`, rồi khoảng cách, path, symbol
  (test `test_equal_scores_are_ordered_by_own_issue_similarity_before_the_path`); `profile` diagnostics →
  `semantic-context-v11-own-similarity-ties` (hash cấu hình không đổi vì chỉ tính trường cấu hình).

## Đề xuất (sau khi chuỗi đo xong)

1. R1: đo lại với `graph_distance = 1/(1+d)` (bỏ nhân confidence) hoặc giảm trọng số distance; đo trên T1 rồi T2.
2. R2: tách hòa điểm bằng độ giống riêng trước `path`; cân nhắc thừa hưởng từ node liền trước.
3. R3: xếp Test sau code trong gói (hoặc ngân sách riêng).
4. R4: kiểm loại node nguồn trong `_index_relations`, có test.
5. R5: cache kết quả `_verify_snapshot` theo `graph_version` trong một lần gọi; bỏ emit từng ứng viên khi không bật trace.
