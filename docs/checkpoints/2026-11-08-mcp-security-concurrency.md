# Checkpoint L6-5 — security/concurrency — 08/11/2026

## Phạm vi và baseline

Chỉ L6-5; không L6-2/6/7, model/Docker/campaign/commit/push. H1 đã ACCEPTED_FOR_IMPLEMENTATION theo quyền tự quyết người dùng. Không đặt review TV2/TV3 làm blocker; chưa có provider mới.

Artifact `results/mcp_server/security/20261108T131906Z-guards/`. Baseline HEAD3f77fcf6 và current dirty/untracked được ghi trước thay đổi;589 protected files gồm source/runtime/docs cũ và toàn bộ artifacts H1/L6-1/plan-confirmation. Không quét dữ liệu/model/cache/WSL hoặc đổi venv.

## Mốc ban đầu — IN_PROGRESS (lịch sử)

- RED23 cases (3fail/20error): chưa có proposal foundations; audit race tái hiện118/120 dòng và cancellation không audit. Sau bước đầu GREEN23 PASS.
- Đã thêm immutable host-bound context/HMAC seal, exact single-use grants, defaults, path/reparse guards, process/thread locks, session commit/managed marker, publication primitive, subprocess cancellation/cleanup.
- Audit append có OS lock, fsync, tail/size checks, sensitive-key/known-value redaction và bound reader. Legacy terminal tool event shape giữ nguyên. Repository protected-read guard và repair whole-cycle session lock đã nối.
- Legacy client env lọc secrets và tắt dotenv reload cho child. New authority không được cấp bởi MCP JSON/confirmed flag; legacy giữ lease/admission, không tự cấp quyền adapter mới.
- Tests concurrency/jobs mở rộng đang chạy hoặc chờ kiểm kết quả; chưa DONE. Kiểm artifact command logs trước khi chạy lại.

## Kết quả cuối — DONE kỹ thuật L6-5

- SDK2 release gate78 PASS/0fail/error/skip, gồm59 security cases +19 runtime/compatibility cases. Legacy100 PASS/1skip cũ (Windows symlink unavailable); wire16/16 PASS SDK2 modern/legacy và SDK1 cross/native lanes. Không cộng các nhóm overlap thành unique tests.
- Independent technical review không còn Critical/Important blockers sau root-overlap/hash/shared-cancel/publication fixes; final commit ordering có shared request OS lock, không giữ repo lock để cancel. Review chỉ đọc, không thay quyền self-approval của người dùng.
- Tạo6 module foundations dưới MCP proposal,5 test files (gồm conftest), security config/runbook/checkpoint. Sửa5 MCP source files và requirements input; contract/status/PROGRESS append-only. Không sửa legacy fingerprint, graph schema/algorithms, engine/policy hoặc sealed artifacts.
- Grant replay hai process chỉ một PASS; audit120/120 records, session24 updates; actual repair apply-once; native Windows junction; job phase barriers/cancel/timeout/output-cap/marker-I/O cleanup; SDK async terminal audit; publication source/stage/final boundary checks.
- Source hash mới canonical inventory policy vgar-bound-source-v1; không đổi hash dữ liệu cũ. SQLite thread test prewarms READY snapshot như factory, không claim concurrent legacy schema migration an toàn; đó thuộc L6-7.
- Ruff scoped/owned whitespace PASS, global15 whitespace cũ được giữ. Filelock4.2.9 thành direct dependency nhưng không cài/nâng packages hoặc sửa lock/runtime cũ.
- Final artifact có `review.json`, `preservation.json`, `summary.json`, `artifact_hashes.json`, command stdout/stderr/JUnit và wire audit/receipts, giữ cả failed/RED evidence. H1 ACCEPTED_FOR_IMPLEMENTATION; các adapter/provider integration còn task sau.
- **Dừng sau L6-5; không commit/push hoặc chuyển task khác.**

## Khôi phục

Đọc checkpoint/status/security runbook và final summary/preservation trước; đối chiếu git status với baseline+owned files. Không chạy lại install/runtime creation hoặc ghi đè artifacts. Nhận task kế tiếp khi người dùng giao; production provider integration chưa được thay bằng fixture PASS.
