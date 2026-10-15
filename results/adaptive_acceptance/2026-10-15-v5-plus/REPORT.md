# Adaptive real repair V5+ — kết quả cuối ngày 15/10/2026

**Campaign FAIL / TUNING_QUOTA_EXHAUSTED. C real PASS; B BLOCKED; final3 chưa đạt.**
Implementation và phiên thử có giới hạn đã hoàn tất; không còn generation/pending.
Không reset campaign hoặc dùng slots dư để vượt cap. Approval: 4 B +4 C +3 final.
Năm lượt thực tế: 4 B FAIL, 1 C PASS. Không có final run hoặc final_profile.json.

## 1. Bảng từng lượt — không bỏ failures

Thời gian là latency toàn run, bao gồm setup/baseline/prompt/generation/finalization.
Generation thuần được ghi riêng trong `summary.json` và canonical.

| # | Phase / case | Prompt | Status | Input / output tokens | Latency (giây) | Nguyên nhân / kết quả |
|---|---|---|---|---|---|---|
| 01 | Tuning B / multi_file_invoice | V5 | FAIL | 1614 /134 | 189.641 | Hunk invoice có 3 dòng old/new nhưng header khai báo 2; Hunk counts exceeded |
| 02 | Tuning B / multi_file_invoice | V6 | FAIL | 1799 /261 | 271.938 | Khai báo count6 thay vì3; raw còn chứa diff tests trái policy; parser bắt malformed hunk trước |
| 03 | Tuning B / multi_file_invoice | V7 | FAIL | 1584 /124 | 133.422 | Đúng 2 paths và starts/counts; thiếu space prefix trước def, unchanged assignment chỉ4 thay vì5 spaces |
| 04 | Tuning B / multi_file_invoice | V8 | FAIL | 1655 /49 | 75.734 | Model sinh host_path_policy.json từ metadata; Protected or unapproved path |
| 05 | Tuning C / missing_links | V9 | PASS | 957 /43 | 65.359 | Strict parse, apply, collection/fallback, 2 tests và static checks PASS |

Tổng **7.609 input /611 output tokens**, tổng latency **736.094 giây** của năm runs,
không bao gồm engineering/tests/thời gian giữa các lượt. API cost ghi nhận0USD;
không có nghĩa điện/local compute/Codex usage miễn phí. Các output đều EOS,
không truncated; không timeout/OOM trong năm lượt. CUDA peak theo run nằm trong JSON.

## 2. Evidence chính xác

Mỗi đường dẫn dưới đây tính từ campaign folder này:

| # | Canonical |
|---|---|
| 01 | `attempts/01/20261015T003703727090Z-e62648364844/run_record.json` |
| 02 | `attempts/02/20261015T004240341955Z-b5e07ce0a4e0/run_record.json` |
| 03 | `attempts/03/20261015T004931535482Z-daa3ae13e75e/run_record.json` |
| 04 | `attempts/04/20261015T005533899467Z-16d544650f34/run_record.json` |
| 05 | `attempts/05/20261015T005816855246Z-a997178dc2f5/run_record.json` |

Trong cùng canonical folder có `prompt.txt`, `raw_model_output.txt`,
`evidence_bundle.json`, `REPORT.md`. C có thêm `candidate.diff`, `transport.diff`,
`applied.diff`; xem danh sách actual trong folder. B FAIL trước apply nên không có
applied.diff, post tests/type/lint NOT_RUN; không coi baseline tests là post PASS.
Worker request/response ở `attempts/NN/model-workers/<worker-id>/`.
`campaign.json` lưu owner/counters/revision và canonical hashes;
`revisions/*.json` lưu parent failed record/reason/hypothesis/template hash.
`summary.json` tổng hợp nhưng không thay thế canonical.

## 3. C đã PASS những gì?

V9 nhấn mạnh metadata không phải source file, dùng standard unified diff thay
nguyên đoạn bằng các dòng '-' rồi '+' để tránh thiếu context-prefix. Đây là output
model trực tiếp; host không sửa/count lại/convert diff. Neutral example đã qua
strict parser và Git apply offline trước inference; không chứa lời giải fixture.

- Task: `examples/tasks/missing_links.json`; source gốc: `examples/snapshots/missing_links/`.
- Model pin giữ nguyên Qwen3-4B; C không nhận previous feedback của B.
- Source bug: formatter giữ whitespace. Patch model đổi `return name` thành
  `return name.strip()` trong formatter.py, giữ signature.
- Baseline: `test_label_trim` FAIL, `test_label_empty` PASS. Baseline stage PASS
  nghĩa capture baseline thành công, không phải bug đã hết trước repair.
- M1 mapping unlinked; selection fallback_required=true, selected=['tests'].
  Post `--collect-only tests` thực thi exit0, lấy đúng2 node IDs.
- Post `pytest tests`: **2 PASS**, required failure được sửa, baseline PASS được giữ.
  Syntax/mypy/Ruff PASS, public EvidenceBundle hợp lệ và trỏ đúng canonical hash.
- Original source unchanged=true; patch chỉ apply trong private worktree đã cleanup.
  Vì vậy mở source gốc vẫn thấy bug là đúng thiết kế, không phải thiếu patch export.

## 4. Vì sao chưa nghiệm thu toàn bộ?

B dùng hết4 lượt tuning, chưa có output đạt parser, nên **B BLOCKED**. Controller
chuyển C theo plan; C PASS ngay lượt1 nên không chạy tiếp C. Final A/B/C chỉ được
chạy nếu BOTH B và C tuning PASS. Vì B không đạt, final **NOT_RUN**, final_version=null.
Không ghép A-V3/V4 historical với C-V9, không coi fake/OK invocation là real repair.
Không chạy B5 bằng ba C slots hay ba final slots chưa dùng. Không tạo thêm V10
vô ích khi campaign đã terminal. Chạy tiếp cần quyết định/phạm vi mới của owner.

Lỗi quan sát trực tiếp ở B là tuân thủ format/path của model; chưa có bằng chứng
thử semantic verification B trong phiên này. Prompt có ảnh hưởng (V7 tốt hơn ở
counts/paths, V8 lại lệch metadata), nhưng không chứng minh chỉ prompt là nguyên
nhân duy nhất hoặc tăng tài nguyên sẽ chữa. CPU offload làm chậm generation;
không phải lý do parser từ chối output đã hoàn thành EOS.

## 5. Gate kỹ thuật và phần đã thay đổi

Full self-test **152 passed in 88.51s**, recorder89.203s, exit0:
`results/tests/20261015T005945598043Z-a4f4d47f3d8d/run_record.json` (tính từ package root).
Final Ruff và audit PASS:
`results/checks/20261015T010114900109Z-cfbffe5811a9/run_record.json`.
Audit xác nhận frozen files/revisions,5 bundles/canonical hashes,3 sources,
quota/terminal/no live owner,69 archived runtime files/69 historical files và
4 protected dirty VGAR files. **Audit PASS không đổi campaign FAIL thành PASS.**

Documentation handoff audit PASS,5 Markdown files/6 PowerShell blocks/13 tables:
`results/checks/20261015T010602134092Z-5a277ccd02b2/run_record.json`.
Git status/diff VGAR được ghi read-only bằng safe.directory chỉ trong command,
không chỉnh global config. Archive và ledger giữ nguyên để khôi phục, không xóa.

Đã thêm adaptive controller/CLI, prompt V5–V9, tests và guide; sửa bốn module
contracts/context_presentation/prompt/pipeline. Source VGAR, parser/verifier,
fixture tests/gold/registry/model/config/budgets không đổi; no commit/push.
Một fresh review + một TDD fix pass: `docs/REVIEW_ADAPTIVE_V5_PLUS_2026_10_15.md`.
Minor feedback diagnostic selection và deep JUnit reconciliation vẫn deferred;
human reproduction/M3 integration chưa có xác nhận, không thuộc gate đã ký.
Ba fixtures là development/prototype, không phải SWE-bench resolved rate.
