# T2 — Audit mypy baseline delta và declaration line map

Ngày06/11/2026. **DONE phần code/fixture local. Điều tra10 gold thật chưa hoàn tất, chờ raw export M3.**

## Thay đổi và quy tắc

Mapper cũ chỉ giữ dòng duy nhất trong toàn file thay đổi. Reproducer synthetic có hai function cùng dòng `return value`; thêm header làm diagnostic nợ cũ bị introduced/unmatched dù declaration không đổi.

- Giữ thuật toán cũ trong `_build_unique_line_map()` để audit đối chiếu; giữ unchanged-file identity và cutoff10.000 dòng cho file thay đổi.
- `build_line_map()` bổ sung span FunctionDef, AsyncFunctionDef hoặc ClassDef có cùng chuỗi scope cha duy nhất ở cả hai phía; mọi scope cha phải duy nhất. So sánh chính xác các dòng source trong span, gồm decorator và indentation.
- Declaration thay đổi, đổi tên/scope, owner trùng hoặc AST không parse được không nhận bằng chứng bổ sung này; fallback unique-line cũ giữ nguyên. Đây không phải semantic type equivalence.
- Mapping xung đột bị loại, giữ quan hệ một-một. Không nới identity/tool/path/code/severity/message/column hoặc multiset. DiagnosticDelta và identity_version/policy vẫn m2-static-delta-v1; audit ghi fingerprint mapper/source riêng.
- Không đổi version/config mypy, không bỏ diagnostic hoặc required checks, không sửa frozen pool/vector/bảng lịch sử. Hàm mapping dùng chung cho static checks nên gate bao gồm mypy/Ruff/syntax.

## Audit offline và output

CLI `scripts/audit_mypy_deltas.py` chỉ đọc export và code verifier; không import/thực thi source đích, chạy pytest đích, model hoặc Docker. Chỉ đọc pool index/patches và các reference GOOD cần thiết, không quét snapshot.tar hay control archive.

Kiểm canonical pool/hash và campaign population/hash/policies; kiểm vector/sidecar/baseline snapshot/source proof và raw mypy output đối chiếu report. Kiểm scope, interpreter, tool version và config. CWD cũ là string prefix để replay parser, không tìm source cũ ngoài export. Trước/sau kiểm hash input đã dùng; link/reparse/traversal hoặc input drift không được coi là bằng chứng PASS.

Giữ mọi GOOD slot trong pool đã validate, kể cả input missing/ERROR/NOT_RUN. Pool không validate được thì population không được coi là đã xác minh. Không đoán10 task đều false reject từ tổng số lỗi, không thay task để đủ mẫu.

| Classification | Ý nghĩa |
|---|---|
| FALSE_REJECT_CONFIRMED | Chỉ xét mypy delta: mapper cũ FAIL, mapper mới PASS nhờ source span bất biến. Không đồng nghĩa patch cuối ACCEPT. |
| NO_NEW_DIAGNOSTICS | Mapper mới không có introduced error/warning. |
| INTRODUCED_BY_RULE | Diagnostic vẫn mới theo quy tắc; không chứng minh gold sai hành vi. |
| UNRESOLVED | Còn diagnostic chưa chứng minh là nợ cũ; không được miễn lỗi. |
| MISSING_EVIDENCE | Thiếu/hỏng evidence hoặc binding/tool/integrity không đủ; reason nêu nguyên nhân. |

Một task có thể có nhiều loại diagnostic trong `diagnostics[]`. JSON giữ delta cũ/mới, baseline/post source context, mapping/scope/span, tool binding và code fingerprints. Không yêu cầu raw vector có `post.static.mypy.delta` lưu sẵn.

Output mới gồm inputs.json, audit.json, rows.csv, report.md, artifact_hashes.json. READY_FOR_REVIEW/exit0 nghĩa là đủ dữ liệu cho audit, không phải phê duyệt nhóm; unresolved vẫn có thể READY vì dữ liệu đầy đủ nhưng chưa kết luận nguồn gốc diagnostic. Thiếu/hỏng dữ liệu trả PARTIAL/exit2 và giữ ledger. Không overwrite output hoặc chồng lấn input.

## Kiểm chứng thực tế

- Map RED10 FAIL/1 PASS →52 PASS. CLI chưa tồn tại ban đầu tạo16 setup ERROR; các bước triển khai bắt được2 FAIL do policy JSON/fixture newline, sau sửa audit16 PASS. Thêm repeated-read drift RED1, sửa giữ hash lần đọc đầu; gate cuối audit22 PASS.
- Gate cuối8 module: **276 PASS,0 FAIL/ERROR/SKIP**, 82.314s JUnit. Ruff scoped exit0; có warning noqa đã tồn tại trong comment static_diagnostics.py, không sửa lịch sử để giấu warning. Whitespace scoped PASS.
- Review độc lập:0 Critical/Important,1 Minor được hoãn về replay prefix Windows; xem giới hạn dưới. Không có review nhóm giả.
- Demo ready synthetic:1 GOOD, delta cũ FAIL→mới PASS,1 MAPPING_RECOVERED, giữ10 reported IDs chưa xác minh.
- Demo partial synthetic:2 GOOD, gồm1 recovered và1 SOURCE_MISSING; exit2, không thay task. Demo missing export:1 GOOD còn trong ledger, exit2, không có measurement giả.
- Không có raw của10 gold được báo; chưa phân loại được matplotlib13989/20488/20676, xarray3993/4629, pylint4604, sympy11618, astropy13453/13977, sphinx11510. Không công bố FRR mới.

## Lệnh và file map

```powershell
$vgarPython = 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VGAR_GRAPH_BACKEND = 'demo'
& $vgarPython -B -m pytest tests/m2/w910/test_static_diagnostics.py tests/m2/w910/test_baseline_delta.py tests/m2/w910/test_static_tools.py tests/m2/w1112/test_mypy_audit.py tests/m2/w1112/test_verifier_eval.py tests/m2/w1112/test_verifier_campaign.py tests/m2/w1112/test_a3_verification.py tests/m2/w78/test_verifier_eval_integration.py -q -ra -p no:cacheprovider --basetemp '<NEW_TEMP>/tests' --junitxml '<NEW_TEMP>/green.xml'
& $vgarPython -B -m ruff check --no-cache src/vgar/repair/static_diagnostics.py scripts/audit_mypy_deltas.py tests/m2/w910/test_static_diagnostics.py tests/m2/w1112/test_mypy_audit.py
& $vgarPython -B scripts/audit_mypy_deltas.py --pool '<EXPORT_POOL>' --campaign '<EXPORT_CAMPAIGN>' --expected-pool-hash '<PINNED_HASH>' --output-root '<NEW_AUDIT_DIRECTORY>'
```

`-B` tắt bytecode, no:cacheprovider tắt pytest cache, `-ra` hiện skip; temp/output mới ngoài source. Tất cả argv/env/exit code, gồm các RED/GREEN trung gian và whitespace, ở `results/m2/w1112/t2/20261106-mypy-delta-audit/commands.json`/commands.md; wrapper gate.py và demo.py cũng được lưu. Không dùng lệnh lọc RED để thay gate đầy đủ.

| File | T2 |
|---|---|
| src/vgar/repair/static_diagnostics.py | Tách legacy mapper, thêm exact declaration spans và conflict merge. Identity/compare/model không đổi. |
| scripts/audit_mypy_deltas.py | CLI mới, chỉ đọc và audit GOOD slots có kiểm chứng. |
| tests/m2/w910/test_static_diagnostics.py | Chỉ thêm regression, giữ tests cũ. |
| tests/m2/w1112/test_mypy_audit.py | Fixture sealed source/vector, raw reports/binding/drift/traversal/reparse, missing ledger, unresolved/introduced và deterministic output. |
| PROGRESS.md, docs/status/m2.md | Bổ sung trạng thái, giữ lịch sử. |
| docs/m2_t2_mypy_delta_audit.md, docs/checkpoints/2026-11-06-t2-mypy-delta-audit.md | File mới: phương pháp, bằng chứng và điểm tiếp tục. |

Đường dẫn tương đối từ D:/Project/CAPSTONES/VGAR. Artifact `results/m2/w1112/t2/20261106-mypy-delta-audit/` gồm log/JUnit, demos, fixture inputs, review, source fingerprints và preservation/checksums.

## Hạn chế và bàn giao M3

Minor còn lại: message mypy có chứa prefix cwd Windows dạng backslash có thể không được chuẩn hóa giống lúc parse ban đầu khi audit replay; audit trả PARTIAL vì raw/report mismatch, không tự cho PASS. Review phân loại low-severity portability; hoãn theo workflow, không có bằng chứng đây là nguyên nhân10 gold Docker. Không tự bỏ mismatch để vượt kiểm tra.

M3 cung cấp frozen pool/hash, campaign ledger, linked GOOD vectors, API/structural sidecars, baseline source snapshot và baseline/post mypy raw commands/reports/source snapshots. Dùng export giữ các reference tương đối, output audit mới; không sửa vector cũ để thêm delta. Hashes chứng minh tính nhất quán với pool pin, không tự xác thực quá trình thực thi.

Phần local đã sẵn, T2 điều tra10 gold vẫn chờ raw và review nhóm. Giữ T4/T5/T6/T7, báo cáo Codex Diff, DB, config/tool locks và artifacts cũ. Không commit/push hoặc chạy campaign thật. **Dừng sau T2 local, chờ xác nhận T3.**
