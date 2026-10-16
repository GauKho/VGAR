# Tích hợp M2 tuần 7–8 vào VGAR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Thực hiện theo checklist; không commit/push.

**Goal:** chạy được M2 và A/B/C từ VGAR, bảo toàn toàn bộ nội dung M2 và thư mục nguồn độc lập.

**Architecture:** nhúng bản sao đầy đủ tại `VGAR/M2_week_7_8/`, giữ namespace `vgar_m2_w78` và môi trường core riêng. Chỉ điều chỉnh đường dẫn ở bản nhúng; receipt/hash và bản gốc của từng file điều chỉnh được giữ. Launcher tại root VGAR gọi runner M2, không đổi agent/MCP của M3.

**Tech Stack:** Python 3.11, PowerShell, pytest, Git, SHA256; dùng dependencies/model đã có, không cài hoặc tải lại.

**Spec:** yêu cầu người dùng ngày16/10/2026 và xác nhận “làm phần đầu”: toàn bộ M2/A/B/C trong VGAR, chưa nối MCP/LangChain. Bản này cụ thể hóa phương án đã xác nhận, triển khai ngay, không mở vòng duyệt mới.

## Global Constraints

- Không xóa, sửa hoặc chạy test ghi vào `D:/Project/CAPSTONES/M2_week_7_8`.
- Giữ hai dirty source files retrieval cùng các untracked files hiện có của VGAR.
- Không thay prompt V11, parser/verifier, fixtures/tests semantics, model/SHA/budget.
- Không ghi lại old canonical records, frozen campaign manifests hoặc tuyên bố layout mới là byte-identical r002.
- Copy cả hidden files, môi trường và local evidence; `.venv` được copy để dùng tại máy này, không được hứa portable hoặc đưa lên Git.
- Integration ID riêng `r002-vgar-i001`; cấu hình đường dẫn, test discovery, launcher và adapter khóa input lịch sử thay đổi. Repair/parser/verifier giữ r002; một helper `b_inputs.py` có hash integration riêng theo ruling từ full-suite RED.
- Không MCP/LangChain, không SWE-bench, không sửa hệ thống cũ, không commit/push.
- Chạy trực tiếp tại VGAR theo yêu cầu; không tạo worktree/branch khác. Các file mới được cô lập trong package nhúng và các đường dẫn mới.

## Review Focus

1. Chạy từ thư mục bất kỳ: mọi root/config/output phải bind đúng VGAR, không vô tình chạy source M2 cũ.
2. Paths tương đối và historical absolute paths: chỉ rebase khi so sánh trong bộ nhớ, không sửa evidence cũ.
3. Runtime drift: chỉ nhận đúng hai config relocation đã ghi hash; sửa core/config/prompt phải bị chặn.
4. Output mới: không ghi đè evidence, không cho output ra ngoài results hoặc qua reparse point.
5. Nested pytest/venv: không gộp dependencies hoặc lẫn test discovery; bảo toàn fixture SQLite do root tests có side effect.

### Task 1: Snapshot và bản nhúng đầy đủ

**Files:** tạo `docs/audit/2026-10-16-m2-w7-w8-integration/`; tạo `M2_week_7_8/`; giữ backup file relocation tại `M2_week_7_8/integration/originals/`.
**Interfaces:** receipt ghi relative path, size, SHA256 của mọi source file; before/after bảo vệ cả M2 và VGAR.

- [x] Ghi baseline Git/status/hash; kiểm không có junction/symlink hoặc destination có sẵn.
- [x] Copy toàn bộ M2, kể cả hidden; đối chiếu từng file và directory trước khi sửa.
- [x] Lưu byte gốc những file cần thay đường dẫn; không di chuyển nguồn.

### Task 2: Relocation và launcher

**Files:** mới `run_m2_abc.ps1`, `scripts/check_m2_integration.py`, `tests/m2/test_w78_integration.py`, `tests/m2/test_w78_preservation.py`; sửa **chỉ bản nhúng** `config/source_pin.json`, `config/demo.json`, `pyproject.toml`, `tests/conftest.py`, `test_abc_v11_r002.ps1`, `src/vgar_m2_w78/b_inputs.py`; mới `integration/relocation.json` và `tests/test_integration_relocation.py`.
**Interfaces:** launcher nhận `-Mode Run|Check|ReadSaved`, `-Python`, `-OutputRoot`, `-SavedRoot`, `-SkipSelfTests`; mặc định Check để không vô tình sinh model. Explicit Run mới inference. Trả nguyên exit code.

- [x] RED: ReadSaved từ root phải audit3/3 bằng copied source và pinned VGAR; output ngoài boundary bị chặn.
- [x] Reference root trỏ VGAR cha; model/tokenizer/interpreter vẫn đúng assets đã duyệt.
- [x] Repair core hash r002 nguyên; hai config và một freeze-input adapter nằm trong delta allowlist có hash cứng. Adapter chỉ nhận ba before/after pairs, đòi backup byte gốc và reject tamper; historical audit so sánh paths trong bộ nhớ, canonical files không bị sửa.
- [x] GREEN: launcher hành xử đúng, PowerShell syntax hợp lệ, code drift bị chặn.

### Task 3: Kiểm thử và bàn giao

**Files:** root `README.md`, `PROGRESS.md`; mới `docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md`; evidence dưới audit/results mới.

- [x] Full core suite nhúng, Ruff; ReadSaved3/3 và Check thực tế, không tính là generation mới.
- [x] Chạy full suite VGAR, lưu stdout/stderr/exit/duration/JUnit; ghi đúng lỗi baseline nếu còn, không sửa ngoài scope.
- [x] Review độc lập một lượt theo skill, xử lý regression integration có bằng chứng.
- [x] Hash nguồn M2 trước/sau phải giống toàn bộ; dirty VGAR trước/sau nguyên ngoại trừ README/PROGRESS chủ đích và backup SQLite của test.
- [x] Hướng dẫn lệnh A/B/C mới, vị trí input/output, khác biệt lịch sử/current; không claim MCP hoặc real acceptance mới khi chỉ re-audit.

## Kết quả đóng plan

Ngày16/10/2026: copy/preservation PASS13071files; full M2 **236PASS**;
launcher/auditor **7PASS**; fake A/B/C3/3PASS; ReadSaved3/3PASS; Check/Ruff/ASTPASS.
Full VGAR **571PASS/2SKIP/1knownFAIL** (HF generation_config baseline), không claim
toàn suite xanh. Không fresh inference/commit/push. Xem handoff và PROGRESS để
biết exact receipts, six-file delta/ruling và lệnh Run mới.

## Quyết định triển khai

Người dùng đã yêu cầu triển khai và chốt phương án hẹp. Dùng Native, không hỏi duyệt lại từng task. Không commit/push. Engineering verification không tự chạy lại 3 generations nếu không cần: ReadSaved kiểm binding/evidence, core suite kiểm pipeline; lệnh `-Mode Run` được bàn giao để người dùng chạy mới.
