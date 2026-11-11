# T2 — mypy delta audit,06/11/2026

**DONE code/fixture local; 10 gold thật chưa xác minh. Dừng chờ xác nhận T3.**

- Exact unchanged declaration map, unique ancestor scopes, decorators, one-to-one conflicts; legacy unique-line map/cutoff/identity/multiset/DiagnosticDelta giữ nguyên.
- Audit offline kiểm pool/campaign/vector/sidecar/raw mypy/source bindings, GOOD ledger đầy đủ, old/new delta và context; missing/invalid→PARTIAL, không sửa lịch sử.
- Gate cuối **276 PASS/0 FAIL/ERROR/SKIP**, 82.314s JUnit; Ruff exit0 (warning noqa comment có sẵn), whitespace PASS.
- Map RED10→52 PASS; CLI ban đầu16 setup ERROR thiếu file, intermediate2 FAIL policy JSON/fixtureCRLF→16 PASS; drift RED1 đã sửa và audit cuối22 PASS.
- Review0 Critical/Important,1 Minor hoãn: replay message có prefix cwd Windows backslash có thể PARTIAL; không gây false PASS. Chi tiết guide/review.json.
- Demo synthetic ready1 GOOD recovered; partial2 GOOD (1 recovered,1 missing); missing-export1 GOOD giữ ledger. Cả10 reported IDs vẫn unverified.
- Artifact `results/m2/w1112/t2/20261106-mypy-delta-audit/`: green.log/.xml, commands.json/.md, demos/, fixture-inputs/, review, preservation, source snapshots, artifact_hashes.json.
- Guide `docs/m2_t2_mypy_delta_audit.md` có lệnh, file map và yêu cầu export M3. TEMP ledger `C:/Users/pc/AppData/Local/Temp/vgt2-dqwbzjag/ledger.md`.
- Không làm lại gate đã PASS nếu không có thay đổi liên quan. Không đổi mypy/config/required checks, pool/vector/bảng cũ, timeout hoặc metrics T4; giữ T5/T6/T7 và dirty changes.
- Không commit/push, chạy model/Docker/campaign hoặc tự T3. Chờ raw để xác định10 gold; chưa có FRR thực nghiệm mới.
