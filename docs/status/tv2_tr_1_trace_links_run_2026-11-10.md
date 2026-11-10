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

## Giới hạn

- Đáp án xấp xỉ: component được nhắc đúng nhưng không bị sửa vẫn tính là sai, như cạnh `urllib3` ở trên.
- 16 task chỉ đủ cho pilot, các khoảng tin cậy của precision ≥ 0,7 và baseline chồng lên nhau. Khoảng của top-1 cũng chồng với baseline, nên chưa đủ để nói top-1 tốt hơn một cách chắc chắn.
- Số liệu này dùng để kiểm chứng TR-1. G1 cần chạy lại trên bộ dev rộng hơn và có mẫu gán nhãn tay ([plan] dòng 166).
