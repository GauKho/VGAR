# M2-W9-2 — Static diagnostics và verification tương đối với baseline

Lập ngày 21/10/2026; nghiệm thu bổ sung ngày 22/10/2026. Baseline repo `525f9936a3c0abe5ea056c532c1f889ce84627a7`.

**Trạng thái: M2-W9-2 hoàn thành theo tiêu chí deliverable của `VGAR_W9_W16_Deliverables.md`.** Ngày 22/10 đã sửa lỗi boolean mypy column qua RED→GREEN; parser/verifier logic 60 PASS, selected regression 122 PASS/2 deselected, gồm ba native scenarios. Review liên thành viên, pinned-tool/full-runtime qualification và real pilot được ghi riêng, không bổ sung thành điều kiện đóng W9-2. Chưa nối variant vào root session/pipeline; chưa chạy SWE-bench hoặc model repair. Không tự đóng M2-W9-0 hay thực hiện M2-W9-3/4.

## 1. Task giải quyết điều gì?

Trước W9, baseline phải sạch syntax/mypy/Ruff tuyệt đối. Một repo có lỗi type từ trước sẽ bị loại dù lỗi đó không liên quan patch. Sau patch, cả ba static checks luôn bắt buộc nên không thể biểu diễn đúng A0/A1 tests-only.

W9-2 bổ sung đường kiểm chứng opt-in:

| Tình huống | A0/A1 | A2 |
|---|---|---|
| Required test chưa tái hiện FAIL ở baseline | Không qualify | Không qualify |
| Lỗi static cũ, tool chạy đủ và có dữ liệu hợp lệ | Không tự loại baseline | Không tự loại baseline |
| Post tests PASS, static chỉ còn lỗi cũ đã ghép được | Có thể PASS | Có thể PASS |
| Post tests PASS, có diagnostic error/warning mới | Ghi check FAIL nhưng `required=false` | FAIL |
| Static tool lỗi/thiếu output | Ghi check ERROR, không làm gate riêng | ERROR nếu check bắt buộc |
| Tests thiếu/regression, source/config/scope/version drift, hết global deadline | Không được biến thành PASS | Không được biến thành PASS |

`baseline.status=PASS` nghĩa baseline **đủ điều kiện làm mốc**, không nghĩa tests của code lỗi đã PASS. Ví dụ required test FAIL và mypy còn debt vẫn có thể là baseline hợp lệ.

## 2. Các file đã thêm/sửa

| File | Vai trò |
|---|---|
| `src/vgar/repair/static_diagnostics.py` | Model diagnostic/report/delta; parser Ruff JSON và mypy JSON-lines; line map và multiset matching |
| `src/vgar/repair/static_checks.py` | Giữ nhánh cũ; thêm `variant` opt-in để chạy structured checks, ghi source snapshot/config/scope/version và lỗi công cụ |
| `src/vgar/repair/verification.py` | Qualification baseline và post verdict theo policy; giữ raw status; kiểm drift và protected files |
| `tests/m2/w910/test_static_diagnostics.py` | 34 parser/comparator tests; gồm 9 cases column bổ sung ngày 22/10 |
| `tests/m2/w910/test_baseline_delta.py` | 26 tests logic verification, guards và JSON roundtrip, dùng output subprocess kiểm soát |
| `tests/m2/w910/test_w9_native_delta.py` | 3 scenarios dùng private worktree, strict apply, pytest/mypy/Ruff thật |
| `tests/fixtures/m2_w9/diagnostics/` | Hai mẫu JSON/JSONL tự soạn theo tool format; không phải benchmark output hoặc log của pin thật |
| `tests/fixtures/m2_w9/static_debt/` | Source có existing type debt và hai tests; test required ban đầu FAIL |

Policy/config W9-1, parser/apply engine, tests W78, registry, public DTO, session/pipeline entrypoint và source của người dùng không bị sửa để làm PASS.

## 3. Luồng xử lý

```text
VariantPolicy + source scope đã chọn
    ↓
Collect và baseline tests thật/controlled theo loại test
    ↓
Snapshot source + static tools + tool/config/interpreter/scope binding
    ↓
Baseline qualify: required test tái hiện FAIL; required tool reports đầy đủ
    ↓
Patch được apply và test sau patch
    ↓
Static reports sau patch → map dòng source → diagnostic delta
    ↓
Áp required checks + config/source/version guards → verdict
```

Có ba lớp kết quả riêng:

1. **Command/raw check:** exit code, stdout/stderr, timeout, status thực tế; không viết lại debt thành PASS.
2. **Delta check:** PASS nếu không có diagnostic error/warning mới và dữ liệu so sánh đầy đủ; ERROR nếu không đủ bằng chứng.
3. **Policy verdict:** chỉ check `required=true` mới dùng làm gate static; tests và guards vẫn phải đạt.

Ví dụ A2 có `static.mypy.status=FAIL` do lỗi cũ, nhưng `policy_checks.mypy.status=PASS` vì không phát hiện lỗi mới. Verdict có thể PASS mà không hề giấu raw mypy FAIL.

### 3.1. Parser và binding

`parse_tool_report(tool, command, tool_version)` đọc JSON Ruff hoặc JSON-lines mypy. `command.diagnostic_context` là metadata do host cung cấp: scope/hash, config hash và interpreter reference. Không tin output text đơn thuần để suy ra scope.

- Chuẩn hóa path về repository-relative, chỉ nhận diagnostic thuộc scope; ngoài scope → report ERROR, không bỏ qua.
- Mypy column phải là integer không âm, không nhận boolean/float/chuỗi/null; kiểm trước phép cộng 1 để chuyển 0-based thành 1-based. Ruff vốn 1-based, giữ validation hiện tại.
- Giữ code/severity/message; chỉ normalize CRLF và workspace prefix, không xóa tên biến/type có ý nghĩa.
- Exit code không khớp diagnostics, output hỏng/truncated, timeout, tool lỗi hoặc stderr chưa phân loại → ERROR; không đổi thành tập lỗi rỗng.
- Raw command và version probe giữ nguyên trong static evidence; report có raw-output hash.
- Tool version được quan sát thực, không điền pin mong muốn vào log. Baseline/post drift không được coi là phép so hợp lệ.

`run_static_checks` W9 kiểm tất cả file trong scope, thu syntax errors theo từng file, dùng config do VGAR giữ, không chạy auto-fix. Scope baseline/post cố định theo `task.allowed_source_paths`. Mypy follow-import có thể báo lỗi ngoài scope; khi đó profile hiện tại báo ERROR bảo thủ, chưa tự mở rộng phạm vi kiểm.

### 3.2. Comparator

So theo multiset: hai diagnostic trùng nhau vẫn được tính hai lần. Xóa một lỗi nhưng thêm lỗi khác không trở thành PASS chỉ vì tổng số lỗi không tăng.

Identity gồm tool/path/code/severity/message/column. Dòng baseline được ánh xạ sang dòng sau patch nếu source line còn nguyên và có anchor duy nhất trong file. Dòng bị sửa hoặc lặp gây mơ hồ được giữ ở introduced/unmatched một cách bảo thủ; có thể gây false reject, không phải chứng minh tương đương ngữ nghĩa.

`introduced`, `persisting`, `resolved`, `unmatched` giữ dữ liệu để đọc lại. `resolved` là diagnostic baseline không được ghép; **khi có unmatched, không được dùng riêng trường này để tuyên bố đã sửa hết lỗi cũ**. Reports incomplete hoặc binding drift trả delta ERROR.

Để giới hạn chi phí, file trên 10.000 dòng không ghép line map: không có matching được chứng minh, có thể FAIL bảo thủ nếu còn debt. Không sửa budget hoặc đẩy việc này thành graph analysis tuần sau.

### 3.3. API và phạm vi integration

Các hàm hiện hỗ trợ keyword mới:

```python
capture_baseline(task, lease, executor, repair_policy, *, variant=None)
run_static_checks(lease, targets, repair_policy, executor, *, variant=None)
complete_verification(partial, task, lease, applied, baseline, executor,
                      repair_policy, *, variant=None)
verify_patch(task, lease, applied, baseline, selection, executor,
             repair_policy, *, variant=None)
```

Truyền `variant=load_variant(...)` vào cả baseline và post. Không truyền variant thì hành vi strict-static W78 giữ nguyên. Đổi/mất variant giữa baseline/post bị chặn. Scope binding được lưu dạng JSON-compatible để không phát sinh false drift khi nạp lại baseline.

**Root `run_repair`/`RepairSession` chưa nhận và chuyển VariantPolicy mới.** Đây là phần wiring/provenance của W9-4 theo kế hoạch; admission/env bridge thuộc W9-3. Public EvidenceBundle chưa được đổi: evidence W9-2 là canonical dictionaries của verifier và artifact tests, không phải tuyên bố phiên MCP đã chạy A0/A2 mới.

Global deadline vẫn cần guard trước/sau operation của session (`session.observe`). `_invoke_static` truyền tiếp TimeoutError, chỉ chuyển OSError I/O thành tool evidence. Một command có thể dùng hết deadline rồi trả `timed_out` thay vì raise; direct caller phải giữ outer deadline guard, không chỉ dựa vào command timeout clipping. M2-W9-4 phải bảo toàn guard hiện có.

Syntax hiện chạy AST trong interpreter native của test fixture. Chưa có qualification Python khác host cho repo ngoài; environment adapter của M1/M2 sẽ giải quyết sau. Không chạy repo SWE-bench bằng cách gán trusted flag.

## 4. Kết quả kiểm thử ban đầu — 21/10/2026

Evidence root: `results/m2/w9/m2-w9-2/20261021/`, ignored và không commit raw results.

| Evidence | Kết quả / mục đích |
|---|---|
| `before.json` | Snapshot files có sẵn và versions trước khi đổi code |
| `diagnostics_red.json` | 25 FAIL do module mới chưa tồn tại — RED có chủ đích |
| `diagnostics_green.json` | 25 PASS sau implement parser/comparator |
| `baseline_red.json` | 21 FAIL, 2 PASS, 1 warning; chưa có keyword variant. Một helper bị pytest nhầm là test, đã đổi tên |
| `baseline_green.json` | 22 PASS cho baseline/policy logic đầu tiên |
| `guard_red.json` | Bắt hai lỗi mới về post snapshot thiếu và optional IO exception |
| `guard_green.json` | 24 PASS, 1 FAIL: TimeoutError bị bắt nhầm qua OSError |
| `guard_fixed.json` | 50 PASS sau tách TimeoutError; gồm 25 parser + 25 verifier lúc đó |
| `serialization_red.json`, `serialization_green.json` | RED→GREEN cho tuple/list scope binding sau JSON roundtrip |
| `native.json` | 3 PASS bằng subprocess tools thật, pytest duration 22,96 giây |
| `regression.json` | **113 PASS, 2 deselected**, pytest duration 32,33 giây; command duration 32.868 ms |
| `lint.json` | Giữ lần lint đầu có style findings, gồm cả patterns từ legacy |
| `lint_new.json` | Full lint trên 4 files mới PASS |
| `lint_modified.json` | E9/F trên 2 modules legacy được sửa PASS; không rewrite style toàn file |

113 tests gồm **54 tests W9-2 mới + 28 policy tests W9-1 + 31 tests liên quan hiện hữu**. Không cộng các lần chạy trước vào 113. Hai tests deselected là W78 `test_baseline_to_repair_and_static_evidence`, `test_verify_patch_equals_tests_then_completion`, do cần fixture/tokenizer M1 chưa provision.

Final regression có chạy lại ba native scenarios, vì code đã đổi để sửa JSON binding. `native/` giữ mỗi invocation riêng bằng UUID, không gộp thành sáu task độc lập hoặc resolved rate.

### 4.1. Ba native scenarios

| Case | Baseline | Patch từ test fixture | Post tests | Kết quả verifier |
|---|---|---|---|---|
| A2, không thêm debt | 1 required FAIL + 1 regression PASS; có mypy debt | Sửa `answer()` trả 2 | 2 PASS | PASS; raw mypy vẫn FAIL vì debt cũ |
| A0, thêm debt | Như trên | Sửa answer và thêm hàm có return type sai | 2 PASS | PASS; delta mypy FAIL nhưng không required |
| A2, thêm debt | Như trên | Cùng dạng patch có debt mới | 2 PASS | FAIL đúng mong đợi; phát hiện introduced diagnostic |

Các patch do unit test cung cấp để kiểm verifier, không do LLM sinh. “3 tests PASS” nghĩa ba tests xác nhận hành vi đúng, trong đó một scenario cố ý mong verifier trả FAIL. Không phải ba real repair tasks đều được ACCEPT.

Native test đã chạy Git private worktree, strict parser/apply, pytest, mypy, Ruff; kiểm source gốc không đổi và private workspace được cleanup. Artifact native lưu baseline/post đầy đủ, command streams, outcomes, JUnit text, apply và integrity flag. Không có source/test/gold SWE-bench trong quá trình này.

### 4.2. Qualification còn thiếu và minor được ghi lại

- Tools thật đã dùng: Python 3.13.0, mypy **1.20.2**, Ruff **0.16.5**; không phải repo pins mypy 2.4.0/Ruff 0.17.0. Đây là compatibility smoke, không thay qualified run theo pin. Không cài/hạ cấp environment dùng chung.
- Full repository/full W78 suite chưa chạy; tokenizer và một số dependencies vẫn chưa qualified. Ghi NOT_RUN thay vì suy từ selected tests ra toàn repo PASS.
- Review độc lập ngày 21/10 không phát hiện Critical/Important. Minor lúc đó là JSON mypy có `column: true/false` bị cộng 1 trước strict validation. **Đã xử lý ngày 22/10**, xem mục 4.3; giữ lịch sử phát hiện, không sửa evidence cũ. Không gọi parser đã bao phủ mọi schema sai có thể xảy ra.
- Chưa có human review receipt M1/M3; không thay chữ ký nhóm bằng review agent.

### 4.3. Nghiệm thu bổ sung — 22/10/2026

Nguồn nghiệm thu là M2-W9-2 trong plan W9–16: baseline có lỗi mypy cũ vẫn qualify, diagnostic mới bị xử lý đúng policy và A0 ghi static là `recorded, not required`. Dependency M2-W9-1 đã hoàn thành. Không cần chờ M1/M3 duyệt riêng hoặc chạy SWE-bench để đóng deliverable verifier.

Root evidence mới: `results/m2/w9/m2-w9-2/20261022-close-delta/`. Mọi evidence ngày 21/10 được giữ nguyên.

**Nguyên nhân và bản sửa hẹp:** Python cho phép boolean tham gia số học; `true + 1` thành 2, `false + 1` thành 1. Khi Pydantic nhận giá trị sau phép cộng thì thông tin kiểu sai đã mất. Parser nay kiểm `type(column) is int` và `column >= 0` trước khi cộng 1; malformed row trả report `ERROR`, không thêm diagnostic giả và vẫn giữ các diagnostic hợp lệ đã đọc trước đó. Public APIs, comparator/delta, required sets và guards không đổi.

| Lượt | Kết quả | Evidence |
|---|---|---|
| Column RED trước sửa | 2 FAIL đúng tại true/false, 7 PASS, 25 deselected; exit 1 | `column_red.json`, `column_red.junit.xml` |
| Column GREEN | 9 PASS, 25 deselected; exit 0; command 792 ms | `column_green.json`, `column_green.junit.xml` |
| Parser + baseline-delta | 60 PASS; exit 0; command 1.329 ms | `logic.json`, `logic.junit.xml` |
| Selected regression, gồm native | 122 PASS, 2 deselected; pytest 31,59 giây; command 32.286 ms | `regression.json`, `regression.junit.xml` |
| Full lint bốn files mới của W9-2 | PASS; command 126 ms | `lint_new.json` |
| E9/F hai modules legacy liên quan | PASS; command 121 ms | `lint_modified.json` |
| Source preservation | Đối chiếu trước/sau; chỉ parser, parser tests, báo cáo W9-2, status M2 và PROGRESS được phép đổi | `before.json`, `after.json` |

122 tests gồm **63 W9-2 (34 parser/comparator + 26 baseline/verifier + 3 native) + 28 policy W9-1 + 31 existing**. 60 logic tests và 9 column tests là tập con của regression, không cộng thành tổng mới. Hai deselections giữ nguyên tên và lý do ở mục 4; không che thành 124 PASS.

Trong ba native artifacts mới ở `native/`: A2 giữ debt cũ cho verdict PASS; A0 thêm debt cho verdict PASS nhưng mypy delta FAIL; A2 thêm debt cho verdict FAIL đúng mong đợi. Cả ba baseline qualify, apply PASS, post tests PASS và source gốc không đổi. Native test xác nhận private workspace cleanup, không dùng LLM/gold SWE-bench.

Runtime quan sát: Python 3.13.0, pytest 8.4.2, Pydantic 2.13.5, mypy 1.20.2, Ruff 0.16.5. Không cài thêm package hoặc qualification pin; full runtime/full repository vẫn chưa được xác nhận. Mỗi command JSON lưu argv/cwd/interpreter, stdout/stderr, UTC start/end, duration monotonic, exit code/timeout; JUnit và native reports giữ outcomes/raw commands. Không có regression default W7–8 trong các tests đã chọn; không suy ra full W7–8 suite đã PASS.

## 5. Cách tự chạy lại trong PowerShell

```powershell
# Root repo và interpreter đã dùng trong evidence; không tự cài package.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = 'D:\Project\CAPSTONES\.venv\Scripts\python.exe'

# Khớp chế độ tests độc lập; không ghi bytecode hoặc nạp external pytest plugins.
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')

# Parser và verifier logic: mong đợi 60 PASS sau bản sửa ngày 22/10, không chạy model.
& $python -B -m pytest tests/m2/w910/test_static_diagnostics.py tests/m2/w910/test_baseline_delta.py -q -p no:cacheprovider
$LASTEXITCODE

# 3 native scenarios: chạy tools thật trong worktree tạm, không cần tokenizer/LLM.
& $python -B -m pytest tests/m2/w910/test_w9_native_delta.py -q -p no:cacheprovider
$LASTEXITCODE
```

Hai lệnh trên tự tạo dữ liệu ở pytest temp; không ghi đè artifact canonical của lần trước. Khi chạy tests khác cần plugins, dùng PowerShell session mới hoặc khôi phục biến môi trường tương ứng. Muốn lưu evidence đầy đủ một lần chạy mới, dùng output root mới; không sửa JSON hoặc log cũ.

## 6. Bàn giao, phần còn chờ và điểm dừng

M1 reviewer kiểm thuật toán/fixtures và requirement scope/version. M3 có thể đọc `policy_checks`, nhưng chưa có quyền giả định session root đã emit các fields đó. Khi tích hợp W9-4 phải giữ policy hash, raw status, delta và guard deadline; public projection cần mô tả rõ raw static FAIL nhưng optional/delta PASS.

M2-W9-3 (admission/env), W9-4 (arm/session/evidence wiring) chưa triển khai. Qualification pin tools, full W78, mapping và nhóm review còn chờ; đây không phải các điều kiện bổ sung để đóng W9-2. Không commit/push.

**Kết luận: hoàn thành riêng M2-W9-2 theo tiêu chí deliverable, không tuyên bố cả tuần 9 hoặc pipeline SWE-bench đã Done.**

**Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**

## Reference

Các tài liệu chính thức đã mở công khai trong phiên này, ngày 21/10/2026:

- [mypy command line](https://mypy.readthedocs.io/en/stable/command_line.html): JSON output và explicit config. Tài liệu đang hiển thị 2.4.0; không dùng nó để giả phiên bản thực chạy là 2.4.0.
- [mypy JSON formatter source](https://raw.githubusercontent.com/python/mypy/master/mypy/error_formatter.py): xác minh cấu trúc JSON-lines và field names từ source chính thức; nhánh master không phải runtime pin được qualification trong phiên này.
- [Ruff configuration/CLI](https://docs.astral.sh/ruff/configuration/): output format/config và CLI controls.

Multiset matching, unique-line map, JSON binding và policy verdict là thiết kế triển khai của VGAR theo plan được duyệt, không gán cho một paper bên ngoài.
