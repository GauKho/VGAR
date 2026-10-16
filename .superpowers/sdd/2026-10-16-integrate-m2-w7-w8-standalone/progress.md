# SDD ledger — plan: docs/superpowers/plans/2026-10-16-integrate-m2-w7-w8-standalone.md

## Phạm vi được duyệt

Người dùng xác nhận tích hợp M2/A/B/C trong VGAR; chưa MCP/LangChain, giữ nguồn M2, không commit/push.

## Pre-flight

- Task1 → Task2: bản nhúng đầy đủ + hashes cung cấp đầu vào relocation; preserve original bytes trước khi thay paths.
- Task2 → Task3: root launcher gọi nested runner; root tests không import nested conftest hoặc trộn core/HF environments.
- Ruling: làm tại VGAR theo explicit target của người dùng, không tạo worktree mới; chỉ paths mới và README/PROGRESS được chủ đích sửa. Chi phí nếu sai: phải tách lại package, nhưng original M2 và VGAR dirty files có byte receipts để đối chiếu.
- Ruling: giữ cả generated files/venv trong bản sao local để không bỏ sót nội dung; không đưa chúng lên Git. Venv copy chỉ dùng tại máy này, không coi là bản cài portable.
- Ruling: layout thay đổi được đặt `r002-vgar-i001`, không đổi manifests r002 cũ. Config delta phải explicit, mọi core Python giữ nguyên hash.

## Task 1

Đang snapshot/copy; đọc `docs/audit/2026-10-16-m2-w7-w8-integration/{before,copy}.json` để resume, không copy đè lại.

Task1: complete — copy.json PASS:13071files/5252directories/203602347bytes, source/copy/protected VGAR zero mismatches. Serial verify236.828s. Interrupted old session không copy lại. Parallel recheck đã hoàn tất nhưng từ chối ghi đè copy.json (FileExistsError), receipt cũ giữ nguyên; không cần retry stagecopy.

## Task2 — Ruling sau full-suite RED

- First embedded suite `core-suite/20261016T070016836352Z-33ac2d07ec5b`:233PASS/1FAIL134.53s. Chính xác: `test_freeze_is_b_only_and_preserves_parser_tests_and_history` từ chối relocated `tests/conftest.py` ở b_inputs.py:39. Không phải lỗi model/parser.
- Ruling: thêm adapter `frozen_input_matches` vào **bản nhúng** b_inputs.py, cho phép duy nhất ba before/after byte-hash pairs cho config/demo, config/source_pin và conftest, bắt buộc original backup khớp. Mọi source/tests khác giữ guard cũ; historical files không sửa. Chi phí nếu sai: freezer có thể chấp nhận thay đổi ngoài layout, nên tests fake-original và tamper bắt buộc FAIL.
- Runtime ID giữ r002-vgar-i001 đang qualification, không phải release cũ; manifest ban đầu được giữ tại integration/relocation-initial-draft.json. Kế hoạch5files thành6files, không đổi phạm vi repair/MCP.
- RED2 `relocation-red/20261016T070154964571Z-3efd2661c713` → GREEN5 gồm original B CLI test `relocation-green/20261016T070312973200Z-fdb856a7bff5`:2.04s. Chưa chạy real generation.

## Task2: complete; Task3 đang finalization

- Full embedded suite236PASS/129.27s; recorder130.016s, `final-core-suite/20261016T070502676971Z-3cde4ebc98db`.
- Fake A/B/C3/3PASS dưới `results/integration-qualification/fake-abc`, không real model. Check CUDA/pins PASS: command `20261016T070621462828Z-dd0d36d6e606`,5.370s.
- Full VGAR đầu:570PASS/1knownFAIL/2SKIP116.21s; command `20261016T070513810071Z-5cb299e8f45c`. HF failure như baseline; không sửa model M3.
- Independent reviewer: no Critical; Important explicit relative Python/SavedRoot paths đổi nghĩa sau chdir. RED `review-relative-path-red/20261016T070857760064Z-bf5301c48832` tái hiện trước fix. Root launcher giờ normalize cả Python/SavedRoot/OutputRoot theo caller PowerShell location trước delegate; không sửa nested core.
- Bảy root integration tests và full VGAR post-review đang chạy. Chờ terminal receipts rồi restore duy nhất SQLite fixture do tests tạo, final preservation và báo cáo.
- Ruling với declined-to-judge: không fresh real inference (không claim); executor kiểm preservation/full-core bằng receipts; known HF baseline báo riêng; MCP/portable venv/bare imports ngoài phạm vi. Supported launchers prepend embedded src, docs cảnh báo old editable .pth; full corpus do executor hash từng file thay vì reviewer đọc vendor.
- Reviewer minor wording “chỉ2config delta” đã được sửa trong lượt hoàn thiện tài liệu vốn thuộc Task3 để mô tả đúng helper delta; không thêm behavior hoặc suite cho prose.

## Task3: complete — 16/10/2026

- Review fix GREEN7/8.98s command20261016T071003225820Z-424ac56f6133. Final full VGAR571PASS/2SKIP/1knownFAIL81.14s command20261016T071014208534Z-364e407364e4; không claim suite xanh. Nested full236PASS129.27s và nested code không đổi sau suite đó.
- Final Ruff command20261016T071231030790Z-8adba3d79c5c PASS; hai PowerShellAST và diffcheckPASS.
- sample_graph.db changed bởi tests, afterhash052da10f... đã archive; restore đúngbeforehashe85df9f6... Không dùng gitreset/checkout.
- Final SHA preservation PASS6.375s:13071sourcefiles/5252directories; source added/changed/missing0; protectedVGARchanged/missing0; copiedmismatches0; originalbackuperrors0. Receiptpreservation-20261016T071223180685Z.json.
- Root README/report/PROGRESS hoàn tất. Không inference mới, không commit/push; mọi campaign cũ/evidence giữ nguyên. Không xóa workspace ledger vì chưa commit (cần resume).
- Điểm dừng: phần đã duyệt hoàn tất; người dùng có thể explicitRun để nghiệm thu3generations mới. MCP, portableinstall/bareimports, knownHFfix hoặc publish là yêu cầu tiếp theo riêng, không tự triển khai.

## Task 2 — RED

`M2_week_7_8/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/m2/test_w78_integration.py::test_readsaved_uses_embedded_runtime_and_current_vgar`
đã FAIL đúng lý do thiếu `run_m2_abc.ps1`: 1failed/0.09s, exit1. Chưa có product code launcher tại thời điểm RED.
