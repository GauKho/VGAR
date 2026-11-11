# T4 — FAR/FRR hiện hành và observed FAR/FRR

Ngày06/11/2026. **DONE công cụ/fixture local; không phải số liệu campaign mới.**

## Quy tắc tính

BAD là positive. ACCEPT trên BAD là FN, non-ACCEPT trên BAD là TP; ACCEPT trên GOOD là TN, non-ACCEPT trên GOOD là FP. ERROR terminal thuộc non-ACCEPT theo quyết định nhóm, nhưng được đếm riêng, **không phải proven detection**.

| Trường | Cách tính và mẫu số |
|---|---|
| FAR, FRR | Giữ hành vi cũ: FN/generated BAD và FP/generated GOOD khi đủ điều kiện. Pending của nhãn hoặc pool ERROR tương ứng làm N/A. |
| bad_observed, good_observed | Số patch có verdict terminal PASS/FAIL/ERROR; không gồm NOT_RUN hoặc pool ERROR chưa sinh patch. |
| observed_FAR | FN / bad_observed. |
| observed_FRR | FP / good_observed. |
| bad_observed_coverage, good_observed_coverage | observed / planned của nhãn; planned vẫn gồm NOT_APPLICABLE và pool ERROR. |

Mẫu số0 hoặc không xác định → N/A (`null` trong JSON). Coverage là tỉ lệ0–1, không phải phần trăm. Có số observed không làm `complete` thành true. Coverage100% cũng không chứng minh mọi check đã chạy được: vector ERROR vẫn là một verdict terminal đã đo.

Accounting được kiểm trong report consumer: `planned = generated + NOT_APPLICABLE + pool ERROR`; `generated = observed + pending`. A0/A1 giữ thống kê verification bằng nhau. NOT_APPLICABLE/operator không áp dụng vẫn giữ riêng; không đổi exclusion thành ERROR hoặc ngược lại.

## Giao diện, renderer và tương thích

- `confusion_metrics(rows)` bổ sung observed counts/rates; coverage chỉ có khi `report_campaign()` biết planned slots. Chữ ký API không đổi.
- Summary schema vẫn `vgar-verifier-tables-v1`, giữ các field cũ và bổ sung6 field observed/coverage. Frozen pool/hash, vector/repair policy và verdict T5 không đổi.
- `render_tables()` làm việc trên bản sao. Với summary cũ, observed được suy từ generated minus pending nếu đủ counters hợp lệ; rate cần thêm FN/FP, coverage cần planned. Thiếu dữ liệu giữ unknown, không tự đoán zero.
- V1 có hai mức FAR/FRR, planned/generated/observed, coverage, NOT_APPLICABLE, FAIL rejection, vector ERROR, pool ERROR và pending. V2 có non-ACCEPT rate cũ và observed non-ACCEPT rate (`1-observed_FAR`), mẫu số BAD và coverage theo operator.
- Observation scope là PARTIAL khi observed nhỏ hơn planned, UNKNOWN khi thiếu count, FULL khi bằng nhau. FULL chỉ nói về coverage. Chú thích trong cả hai bảng nêu ERROR không chứng minh phát hiện mutant.
- Tên output/CLI không đổi: V1.md, V2.md, verification_pool_counts.json. Render lặp lại byte-identical; không sửa input summary.

## Kết quả kiểm thử và fixture

- RED:12 FAIL đúng do thiếu tính năng; GREEN toàn bộ hai module verifier và integration: **127 PASS,0 FAIL/ERROR/SKIP**, 57.139s JUnit. Ruff và whitespace scoped PASS.
- Review độc lập theo baseline T4: không finding, không deferred. Không thay review nhóm hoặc nghiệm thu thực nghiệm.
- Demo synthetic pool có2 task/12 slot: planned BAD10/GOOD2, generated và observed BAD3/GOOD1; NOT_APPLICABLE BAD2; pool ERROR BAD5/GOOD1. FAR/FRR hiện hành N/A; observed FAR0/FRR1, coverage0,3/0,5; complete=false.
- Demo này có3 BAD vector ERROR và1 GOOD vector ERROR, **0 check FAIL**, nên không được nói đã phát hiện3 mutant. Nó minh họa mẫu số và việc tách lỗi.
- Demo pending: BAD generated3 nhưng chưa có measurement, observed FAR N/A/coverage0; GOOD observed1/FRR1/coverage1. Campaign vẫn incomplete. Không có task/model/Docker benchmark nào được chạy thêm.
- Một lần dựng demo thất bại do pytest rút gọn tên thư mục temp; đã sửa pattern tìm fixture, giữ log lần thất bại. Không phải lỗi production hoặc test gate.

## File và lệnh

- `src/vgar/evaluation/repair/verifier_eval.py`: observed metrics, accounting, legacy enrichment và bảng.
- `tests/m2/w1112/test_verifier_eval.py`: oracle terminal/pending/zero; giữ tests T5.
- `tests/m2/w1112/test_verifier_campaign.py`: pool ERROR, NOT_APPLICABLE, operator coverage, pending, legacy unknown/determinism; giữ guard T7.
- `PROGRESS.md`, `docs/status/m2.md`: thêm trạng thái, giữ lịch sử. Tài liệu này và `docs/checkpoints/2026-11-06-t4-observed-metrics.md` là file mới.

Đường dẫn tương đối từ `D:/Project/CAPSTONES/VGAR/`. Artifact `results/m2/w1112/t4/20261106-observed-metrics/` có argv/env/exit code trong commands.json/.md, log/JUnit, bảng synthetic, review, source snapshots, preservation và checksums.

```powershell
$vgarPython = 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VGAR_GRAPH_BACKEND = 'demo'
& $vgarPython -B -m pytest tests/m2/w1112/test_verifier_eval.py tests/m2/w1112/test_verifier_campaign.py -k 'observed or legacy_summary or pool_input_errors_leave_rates' -q -ra -p no:cacheprovider --basetemp '<NEW_TEMP>/red-t' --junitxml '<NEW_TEMP>/red.xml'
& $vgarPython -B -m pytest tests/m2/w1112/test_verifier_eval.py tests/m2/w1112/test_verifier_campaign.py tests/m2/w78/test_verifier_eval_integration.py -q -ra -p no:cacheprovider --basetemp '<NEW_TEMP>/green-t' --junitxml '<NEW_TEMP>/green.xml'
& $vgarPython -B -m ruff check --no-cache src/vgar/evaluation/repair/verifier_eval.py tests/m2/w1112/test_verifier_eval.py tests/m2/w1112/test_verifier_campaign.py
git -c core.whitespace=cr-at-eol diff --check -- src/vgar/evaluation/repair/verifier_eval.py tests/m2/w1112/test_verifier_eval.py tests/m2/w1112/test_verifier_campaign.py PROGRESS.md docs/status/m2.md
```

Lệnh RED trên đã FAIL trước implementation; sau fix nó phải PASS. `-B` tắt bytecode, no:cacheprovider tắt pytest cache, `-ra` hiện lý do skip, basetemp mới ngoài repo; `-k` chỉ dùng reproducer, gate GREEN không lọc. Wrapper `gate.py` lưu argv thực và exit code. Khi chạy lại phải thay temp, không dùng output lịch sử.

## Bàn giao và điểm dừng

T5/T6/T7, report Codex Diff và DB giữ nguyên; các function verdict/guard cũ không đổi trong T4. Không sửa pool/hash hoặc bảng cũ, không tự diễn giải lại exclusion từ EXCLUDED.md. Chỉ áp dụng report mới lên export hợp lệ và output mới khi nhóm yêu cầu; không tuyên bố có FAR/FRR campaign thật mới.

Không commit/push, đổi timeout hoặc chạy campaign/model. **Dừng sau T4, chờ người dùng xác nhận T2.**
