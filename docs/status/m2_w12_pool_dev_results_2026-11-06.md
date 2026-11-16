# Kết quả mutant pool trên dev và danh sách việc cần sửa (06/11/2026)

> Người ghi: M3. Đọc trước khi sửa verifier hoặc chạy lại pool. Spec liên quan:
> `docs/superpowers/specs/2026-11-05-m2-w12-closure-design.md` (W1).
> **Số trong file này là số sơ bộ:** code verifier sẽ còn được sửa (§4), nên bản chính thức phải chạy lại trên commit
> freeze.

## 1. Định danh lần chạy

| Mục | Giá trị |
|---|---|
| Code | `~/vgar-a3`, commit `3f77fcf6`, checkout `core.autocrlf=true` và `*.sh eol=lf` (spec §7.1) |
| Pool | `pool-20261105T062327Z`, `pool_hash sha256:8abbc1727432495156d41994c9167c9c681c6dd473747d20dc8f37db64946f6f`, seed 0 |
| Campaign | `D:\kltn\vgar_mcp_mvp_demo\results\m2\w1112\campaign-20261105T190700Z`, `campaign_hash sha256:fba70b062b470054942f7ef4167371ba6aa0d8a6507adb2397d1f48e50880787` |
| Bảng | `D:\kltn\vgar_mcp_mvp_demo\results\m2\w1112\tables-20261105T190700Z\` (`V1.md`, `V2.md`, `verification_pool_counts.json`) |
| Config | `configs/m3/w10_dev_stage1.json`, `configs/m3/w10_dev_stage2.json`; data root `~/w10`; Docker overlay2 |
| Thời gian | 06/11, khoảng 02:07–08:30, chạy bằng `~/run_pool.sh` (tự xoá `snapshot.tar` của slot đã xong) |
| Trạng thái | 138/138 slot EVALUATED; 12 pool ERROR (2 task trong `configs/m3/w10_dev/tasks/EXCLUDED.md`); 0 NOT_RUN. CLI trả exit 2 và `complete: false` vì có pool ERROR |

**Bản pool trên D: đã bị xoá khi dọn đĩa.** Bản duy nhất còn lại nằm ở
`~/vgar-a3/results/m2/w1112/pool-20261105T062327Z`, và lệnh `report` cần nó. Phải chép lưu ra D: (§5, việc T9).

Các campaign khác trong cùng thư mục (`062327Z`, `081117Z`, `102239Z`, `103206Z`, `135051Z`, `135926Z`, `181856Z`,
`182101Z`, `campaign-`) đều hỏng hoặc bị ngắt: thiếu Docker, đầy đĩa, thiếu image, `Ctrl-C`. **Không dùng các
campaign này trong bảng.**

## 2. V1 (patch hỏng = positive)

| Arm | TP | FP | FN | TN | BAD ERROR | GOOD ERROR | FAR tính tay | FRR tính tay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | 24 | 1 | 91 | 22 | 18 | 0 | 91/115 = 79% | 1/23 = 4% |
| A1 | 24 | 1 | 91 | 22 | 18 | 0 | 91/115 = 79% | 1/23 = 4% |
| A2 | 92 | 11 | 23 | 12 | 19 | 0 | 23/115 = 20% | 11/23 = 48% |
| A3 | 115 | 23 | 0 | 0 | 114 | 23 | 0/115 = 0% | 23/23 = 100% |

- TP và FP đếm mọi verdict không ACCEPT, kể cả ERROR.
- Code ghi FAR/FRR là `N/A` vì có pool ERROR (T4). Hai cột "tính tay" lấy mẫu số là số patch đã sinh: 115 BAD, 23
  GOOD.
- A0 và A1 giống hệt nhau là đúng thiết kế: cả hai chỉ bắt buộc `tests`.

## 3. V2 (số mutant bị từ chối vì FAIL, theo loại; mỗi loại 23 patch)

| Loại mutant | A0/A1 | A2 | A3 |
|---|---:|---:|---:|
| condition_flip | 1 | 15 | 0 |
| import_cycle | 2 | 17 | 1 |
| public_function_delete | 1 | 13 | 0 |
| signature_change | 1 | 18 | 0 |
| test_skip | 1 | 10 | 0 |

Ở A3, gần như mọi mutant nằm ở cột ERROR/incomplete. Bảng đầy đủ: `V2.md`.

## 4. Phát hiện

1. **A3 suy biến:** `api` ra `NOT_RUN` ở 133/133 vector hợp lệ (`API_UNSUPPORTED_DECLARATION`,
   `API_INHERITED_CONSTRUCTOR`, `API_AMBIGUOUS_BINDING`, `API_UNSUPPORTED_EXPORT`). Theo V10, `NOT_RUN` dẫn tới
   `VERIFICATION_INCOMPLETE`, nên A3 từ chối mọi patch. Phép so sánh A3/A2 vì vậy chưa có nghĩa.
   `structural`: 102 PASS, 19 FAIL, 12 ERROR.
2. **mypy làm FRR của A2 lên 48%:** 10/11 patch gold bị A2 từ chối là do `TYPECHECK_FAILED`. Các task:
   matplotlib-13989, xarray-3993, pylint-4604, sympy-11618, astropy-13453, matplotlib-20488, xarray-4629,
   sphinx-11510, astropy-13977, matplotlib-20676.
3. **Patch gold của astropy-13033 FAIL ở test**, nên bị từ chối ở mọi arm (`TEST_FAILED`).
4. **4 lỗi integrity cùng một kiểu `docker cp ... /vgar/nodeids.json`:** flask-5014 `public_function_delete`,
   pytest-5631 `test_skip`, astropy-13453 `import_cycle`, pytest-7205 `public_function_delete`. Slot của flask lỗi
   giống hệt ở cả 3 lần chạy, tức lặp lại được.
5. **Dung lượng:** mỗi slot ghi khoảng 14 bản `control/snapshot.tar` 39 MB; nếu không xoá, campaign chiếm khoảng
   55 GB. `report` không đọc file này (`verifier_eval.py` `_read_vector`, `_validate_source_proof`), nhưng có đọc và
   kiểm hash `checks/baseline.json`.

## 5. Danh sách việc cần sửa

| Mã | Việc | Người làm | Bằng chứng | Xong khi |
|---|---|---|---|---|
| T1 | A3: nhóm chọn (a) A3 chỉ là phép đo, hoặc (b) `api_check` chỉ xét symbol public mà patch thật sự đổi, để cấu trúc chưa hỗ trợ ở chỗ khác trong file không làm cả file `NOT_RUN` | Nhóm chọn; M2 sửa nếu (b) | §4.1 | Trên pool, `api` có PASS hoặc FAIL ở phần lớn vector; GOOD không còn bị từ chối hàng loạt |
| T2 | mypy từ chối 10 patch gold: kiểm lỗi mới là thật hay do so baseline sai (line map, cách định danh diagnostic). Nếu thật thì ghi vào threats; nếu sai thì sửa | M2 | §4.2; `post.static.mypy.delta` trong vector của các slot GOOD | Có giải thích cho từng task; sửa xong FRR của A2 phản ánh đúng |
| T3 | Patch gold astropy-13033 FAIL ở test: kiểm cách chọn test, môi trường, plugin pytest | M2 | §4.3 | Có nguyên nhân; sửa được, hoặc ghi là ngoại lệ có lý do |
| T4 | FAR/FRR `N/A` khi có pool ERROR: quyết định cách xử lý 2 task bị loại (đổi thành NOT_APPLICABLE có lý do, hoặc tính tỉ lệ trên slot đã sinh kèm chú thích) | M2 đề xuất; nhóm duyệt | `verifier_eval.py` (`metrics`: `if result[prefix + '_pool_errors']: ... = None`) | V1/V2 có tỉ lệ kèm mẫu số rõ |
| T5 | Lỗi `nodeids.json`: khi mutant làm pytest không collect được, ghi thành phát hiện (collection FAIL) thay vì `CHECK_INTEGRITY_ERROR` | M2 | §4.4; `docker/*/cli-*.json` của 4 slot | 4 slot ra FAIL hoặc ERROR có lý do, không còn là lỗi hạ tầng |
| T6 | `DockerExecutor` xoá `control/snapshot.tar` sau `docker cp`. Tuỳ chọn: ghi `checks/baseline.json` một lần cho mỗi task | M2 | §4.5; `docker_executor.py:327-358` | Pool đầy đủ chiếm khoảng 10–15 GB mà không cần vòng dọn; batch GPU cũng nhẹ đi |
| T7 | Câu báo lỗi `must not overlap frozen pool` phải tách được trường hợp thư mục output đã tồn tại | M2 | `verifier_eval.py:328-329` | Báo đúng nguyên nhân |
| T8 | Sửa CRLF triệt để: `-text` cho `configs/m1/w9_bundle_profile_repair.json` trong `.gitattributes`, commit đúng bytes CRLF đang ghim | Người dùng (vai M1) | Spec §1, C6 | Clone sạch trên Linux chạy được config W10/W12 |
| T9 | Chép lưu pool về D:: `cp -a ~/vgar-a3/results/m2/w1112/pool-20261105T062327Z /mnt/d/kltn/vgar_mcp_mvp_demo/results/m2/w1112/` | Người dùng | §1 | Pool có ở cả hai nơi |
| T10 | Chốt timeout (ĐX2) từ D15 trên W10: timeout sinh A0 1/20, A1 3/20, A2 4/20; trung vị 615 ms/token, nên 1536 token mất khoảng 945 s > 900 s | Nhóm; M2 viết đề xuất | `results/m2/w1112/d15-w10-20261105T102228Z/` | Có quyết định ghi kèm ngày |
| T11 | Sau T1–T7: chạy lại pool **chính thức** trên commit dự kiến freeze bằng `~/run_pool.sh`, khoảng 6–7 giờ | Người dùng | Spec W1 | V1/V2 chính thức cho freeze |

Thứ tự: T9 ngay; T1, T4, T10 cần nhóm chốt; T2, T3, T5, T6, T7 M2 làm song song; T8 trước khi gắn tag freeze; T11
sau cùng.
