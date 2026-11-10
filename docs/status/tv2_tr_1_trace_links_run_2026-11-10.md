# TV2 · TR-1: kết quả chạy thật trace links, 10/11/2026

Spec: `docs/superpowers/specs/2026-11-10-tv2-tr-1-trace-links-design.md`. Plan: `docs/superpowers/plans/2026-11-10-tv2-tr-1-trace-links.md`.

## Cách chạy

16 task SWE-bench có checkout trong WSL, đều thuộc bộ dev theo `split_of`; không gồm django, sympy, matplotlib, scikit-learn, sphinx vì quá nặng với máy này. Không truyền failing test. Đáp án xấp xỉ là `changed_source_files` của patch gold, như [plan] dòng 400 và [rq] cho phép.

```bash
python scripts/measure_trace_links.py --manifest <manifest.json> --repositories <thư mục checkout theo instance_id> --output <kết quả.json>
```

Hai lô (4 task astropy trong 2 phút 13 giây, 12 task còn lại trong 1 phút 2 giây) rồi gộp và tính lại bằng `summarise`. Không sót task nào, không có task sai `base_commit`.

## Issue → Component

Khoảng tin cậy 95% là bootstrap theo task, 2000 vòng, seed 0.

| Cách chọn | Số cạnh | Đúng | Precision | Recall |
|---|---|---|---|---|
| Mọi cạnh | 33 | 14 | 0,42 | 0,82 |
| `confidence` ≥ 0,5; 0,6; 0,7 (như nhau) | 27 | 14 | 0,52 [0,40–0,71] | 0,82 [0,65–1,00] |
| `confidence` ≥ 0,8 | 8 | 6 | 0,75 | 0,35 |
| Top-2 mỗi issue, trong các cạnh ≥ 0,7 | 22 | 14 | 0,64 | 0,82 |
| Top-1 mỗi issue, trong các cạnh ≥ 0,7 | 14 | 12 | 0,86 [0,67–1,00] | 0,71 [0,50–0,88] |
| Baseline: luôn chọn component nhiều file nhất | 16 | 8 | 0,50 [0,25–0,75] | 0,47 [0,25–0,71] |
| Baseline: chọn ngẫu nhiên 1 component | | | 0,10 | |

**Số báo cáo chính cho G1** là dòng `confidence` ≥ 0,7: precision 0,52, recall 0,82. MRR 0,81. Có 2 task hòa ở vị trí đầu.

Issue → file code: precision 0,04 (14/320), recall 0,56 (14/25).

**Theo nhóm:**

| Nhóm | n | Precision ≥ 0,7 | Recall ≥ 0,7 | Precision top-1 | Recall top-1 |
|---|---|---|---|---|---|
| Có traceback | 1 | 0,50 | 1,00 | 1,00 | 1,00 |
| Không có traceback | 15 | 0,52 | 0,81 | 0,85 | 0,69 |

Nhóm có traceback chỉ có 1 task nên số của nhóm này không đủ để kết luận.

## So với lần đo trước khi làm TR-1

15 task không có traceback cho đúng các cạnh như trước. Chỉ `psf__requests-1724` khác: thêm cạnh tới component `urllib3` với `confidence` 0,95 (2 anchor). Traceback thật sự đi qua code đó, nhưng patch gold chỉ sửa `requests/sessions.py`, nên cạnh này tính là sai. Đây là nguyên nhân precision ở mức ≥ 0,7 giảm từ 0,54 (14/26) xuống 0,52 (14/27). Component đúng vẫn xếp đầu.

Baseline nhiều file nhất ra 8/16, còn bản đo tạm trước đó ra 9/16. Lý do là `astropy__astropy-13398` có hai component cùng 28 file: công cụ tách hòa theo id nhỏ nhất như spec §6, bản đo tạm lấy id lớn nhất. Baseline này nhạy với cách tách hòa.

## `psf__requests-1724`

3 traceback giống nhau, tổng 33 frame.

| Kết quả | Số frame | Ghi chú |
|---|---|---|
| Symbol chứa dòng và đúng tên (0,95) | 18 | 3 frame `Function`, 15 frame `Method`; các file `api.py`, `sessions.py`, `adapters.py`, `connectionpool.py` |
| Dòng lệch, tên duy nhất (0,8) | 0 | |
| File (0,7 và 0,6) | 0 | |
| Không có cạnh | 15 | 12 frame `httplib.py` của thư viện chuẩn, 3 frame script `/Users/hwkns/test_requests.py` của người báo lỗi |

Script của người báo lỗi không bị nối nhầm vào `test_requests.py` ở gốc repo. `UnicodeDecodeError` là exception có sẵn của Python nên không có cạnh `ErrorMessage`.

## Kiểm chứng

- Test của TR-1 và `tests/test_task_graph.py` trên WSL Ubuntu (Python 3.11.17): 137 passed, 3 skipped.
- Toàn bộ test suite trên Windows (`-m "not hf and not docker"`, 29 phút 13 giây): 2784 passed, 20 skipped, 2 xfailed, 3 failed. Ba test fail đúng là ba test đã biết từ trước: `tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`, `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`.
- Hai ca bootstrap với số tính tay được thêm sau khi suite đã bắt đầu; `tests/test_trace_quality.py` chạy riêng: 18 passed.

## Kiểm tra bổ sung sau commit `3267d5b1`

Các phép kiểm dưới đây chỉ dùng bộ dev: id được lọc bằng `split_of` trước khi đọc nội dung, nên không đọc issue nào của held-out.

### Thêm 15 task của repo lớn

Trong WSL, graph của các repo lớn build được trong 11–48 giây, nên lý do loại "quá nặng" không còn đúng ở đây. Đã đo thêm 15 task có checkout trong WSL: django 4, matplotlib 4, scikit-learn 2, sphinx 2, sympy 3. Cả 15 task đều thuộc bộ dev, đúng `base_commit`, không task nào bị bỏ. Hai lô chạy hết 4 phút 36 giây và 7 phút 40 giây.

| Cách chọn | 16 task trước | 15 task repo lớn | Cả 31 task |
|---|---|---|---|
| Mọi cạnh | P 0,42 · R 0,82 | P 0,20 · R 0,43 | P 0,29 · R 0,61 |
| `confidence` ≥ 0,7 (số chính) | P 0,52 · R 0,82 | P 0,36 · R 0,38 | P 0,45 [0,34–0,58] · R 0,58 [0,42–0,76] |
| `confidence` ≥ 0,8 | P 0,75 · R 0,35 | P 0,42 · R 0,24 | P 0,55 · R 0,29 |
| Top-2 | P 0,64 · R 0,82 | P 0,44 · R 0,38 | P 0,55 · R 0,58 |
| Top-1 | P 0,86 · R 0,71 | P 0,54 · R 0,33 | P 0,70 [0,52–0,88] · R 0,50 [0,33–0,69] |
| Baseline nhiều file nhất | P 0,50 · R 0,47 | P 0,20 · R 0,14 | P 0,35 [0,19–0,52] · R 0,29 [0,16–0,44] |
| Baseline ngẫu nhiên | 0,10 | 0,04 | 0,07 |
| Issue → file | P 0,04 · R 0,56 | P 0,02 · R 0,55 | P 0,03 · R 0,55 |

MRR trên 31 task là 0,67, có 3 task hòa ở vị trí đầu. Nhóm có traceback giờ có 2 task (thêm `django__django-11087`); cả 2 đều có component đúng ở top-1.

Số đo trên 16 task trước đây lạc quan hơn thực tế. Repo lớn có nhiều component hơn hẳn (django 172, sympy 69–89), recall giảm mạnh, và cách luôn chọn component nhiều file nhất gần như không còn dùng được. Trên 31 task, khoảng tin cậy của top-1 không còn chồng với baseline nhiều file nhất ở precision, nhưng mức ≥ 0,7 vẫn chồng.

### `MENTIONS` trước và sau TR-1

Chạy code ở `bca33720` (trước TR-1) và code hiện tại trên 16 task, so toàn bộ cạnh `MENTIONS` và `TRACES_TO`, gồm đích, `confidence` và `evidence`. 15 task giống hệt nhau. Chỉ `psf__requests-1724` khác: 4 symbol trước đây chỉ được nhắc yếu (0,45–0,5, theo receiver) hoặc qua `sessions.py:313` nay có thêm bằng chứng `path_line` 0,95 từ frame, thêm 2 method trong `connectionpool.py`, và thêm 1 cạnh component.

### `FailingTest → Test` khi có failing test

Chỉ để chẩn đoán, không tính vào số đo vì agent không có thông tin này: truyền `FAIL_TO_PASS` của 16 task vào overlay. Kết quả: 88 selector, 50 nối được, không cạnh nào sai đích. Cả 38 selector không nối được đều là test chưa có ở `base_commit`, do test patch thêm vào; mọi test có sẵn ở `base_commit` đều nối được.

### `ErrorMessage → Class`

Trong 208 issue của bộ dev, phần trích `G_task` tìm được 39 exception: 33 là exception có sẵn của Python, nên theo luật không có cạnh; 6 là exception riêng của project. Các task này không có checkout riêng trong WSL, nên mỗi repo dùng một checkout khác cùng repo, vì tên và vị trí các exception này không đổi giữa các phiên bản. Cả 6 đều nối đúng:

| Issue | Exception trong issue | Đích | `confidence` |
|---|---|---|---|
| `django__django-11265` | `django.core.exceptions.FieldError` | `django.core.exceptions.FieldError` | 0,9 |
| `django__django-16938` | `django.core.exceptions.FieldError` | `django.core.exceptions.FieldError` | 0,9 |
| `django__django-14351` | `django.db.utils.ProgrammingError` | `django.db.utils.ProgrammingError` | 0,9 |
| `django__django-12858` | `SystemCheckError` | `django.core.management.base.SystemCheckError` (qua `CommandError`) | 0,6 |
| `scikit-learn__scikit-learn-10908` | `NotFittedError` | `sklearn.exceptions.NotFittedError` | 0,6 |
| `sympy__sympy-17655` | `GeometryError` | `sympy.geometry.exceptions.GeometryError` | 0,6 |

### Bao nhiêu issue có traceback tuyệt đối

21/208 task của bộ dev (10%) có frame dùng đường dẫn tuyệt đối, 16 task trong đó có frame trong `site-packages` hoặc `dist-packages`: django 9, sympy 7, astropy 2, matplotlib 1, requests 1, scikit-learn 1. Anchor của các task này có thể đổi, nên RT-1 phải đo lại retrieval trên đúng nhóm này.

### Sửa sau review

- Công cụ đo: lỗi khi build một task được ghi là `build_failed` kèm lỗi rồi chạy tiếp; thư mục không đọc được bằng git là `git_failed` kèm dòng lỗi của git; không đo được task nào thì thoát với mã 1.
- Thư viện chuẩn: nhận thêm thư mục `pypyX.Y` và thư mục `lib` của Anaconda, Miniconda.
- Test: frame trỏ tới File bị từ chối khi dùng `TRACES_TO`; `MENTIONS` theo đúng anchor với frame tương đối; recall bằng 0 khi có đáp án mà không có cạnh.
- Kiểm chứng sau khi sửa: test của TR-1 và `tests/test_task_graph.py` trên WSL 150 passed, 3 skipped; toàn bộ test suite trên Windows (37 phút 13 giây) 2797 passed, 20 skipped, 2 xfailed, 3 failed, và 3 test fail đúng là 3 test đã biết ở trên.
- Kiểm chứng cuối, với code cuối cùng: toàn bộ test suite trên Windows (35 phút 52 giây) 2798 passed, 20 skipped, 2 xfailed, 3 failed đúng là 3 test đã biết; các test liên quan trên WSL 276 passed, 3 skipped, 1 xfailed; chạy thật lại cả 31 task (4 lô, tổng khoảng 16 phút), không task nào bị bỏ, và điểm của cả 31 task giống hệt các lần chạy trước.
- `graph_version` đổi theo schema v5. Không có chỗ nào nạp graph đã lưu rồi từ chối vì khác version. Sau đó, cùng ngày, cụm version và profile legacy (`legacy_w10`, `legacy_graph_version`, nhãn resolver đóng băng) đã được gỡ vì proposal và plan 2 tuần không cần; xem ghi chú trong spec L2-2 (`docs/superpowers/specs/2026-11-08-tv2-l2-2-may-call-design.md`).

## Giới hạn

- Đáp án xấp xỉ: component được nhắc đúng nhưng không bị sửa vẫn tính là sai, như cạnh `urllib3` ở trên.
- 31 task vẫn là pilot. Khoảng tin cậy của mức ≥ 0,7 còn chồng với baseline nhiều file nhất.
- Nhóm có traceback mới có 2 task, nên chưa kết luận riêng được cho nhóm này.
- Số liệu này dùng để kiểm chứng TR-1. G1 cần chạy lại trên bộ dev rộng hơn và có mẫu gán nhãn tay ([plan] dòng 166).

## Cập nhật 11/11: thứ tự phân định khi bằng điểm

`rank_component_traces` trước đây phân định các cạnh `TRACES_TO` cùng `confidence` và cùng `anchor_count` theo id, nên package ngoài (ví dụ `fees`) đứng trước package lồng bên trong (`fees/discounts`). Giờ khi bằng điểm, component lồng sâu hơn đứng trước, sau đó mới tới id (test `test_rank_component_traces_prefers_the_nested_package_on_a_tie`). Đây là độ sâu của package, không phải độ sâu của frame trong traceback, nên không trái với việc §9 đã bỏ đề xuất "ưu tiên frame sâu nhất".

Đo lại trên cùng 31 task (`~/tr1-run/tiebreak_*.json`, `scripts/measure_trace_links.py` như trên):

| Chỉ số | Trước | Sau |
|---|---|---|
| Top-1 (≥ 0,7) | 19/27, P 0,70, R 0,50 | 20/27, P 0,74, R 0,53 |
| MRR | 0,67 | 0,69 |

Thay đổi: `astropy__astropy-13453` component đúng từ hạng 2 lên hạng 1; `django__django-10914` từ hạng 3 xuống hạng 4 (vốn không đúng ở top-1). Các task khác giữ nguyên thứ hạng.

