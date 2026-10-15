# Failures và phương pháp không lặp lại

## Trạng thái mới nhất — final V11/r002 đã PASS 3/3

Sau các approvals tiếp theo, B tuning V11/r002 đã PASS, rồi người dùng yêu cầu
final A/B/C cùng một prompt/runtime. Ba runs mới không feedback đều PASS; combined
audit ở `results/final_acceptance/2026-10-15-v11-r002/audits/20261015T073438247626Z-8ce2a58ef084/run_record.json`.
Không sửa raw/counts/tests/guards, không reset campaigns cũ. B không còn BLOCKED;
final3 không còn NOT_RUN. Giữ nguyên các failures bên dưới như lịch sử phương pháp.
V10 B mới từng FAIL vì wrapper BEGIN/END FORMAT DIFF; V11 loại wrapper khỏi ví dụ,
r002 sửa nhầm phân loại timeout metadata; xem `KET_QUA_B_EVIDENCE_DRIVEN_2026_10_15.md`.
Xem `NGHIEM_THU_FINAL_A_B_C_V11_R002.md` cho final evidence và các gate bên ngoài
còn chưa nghiệm thu: teammate reproduction và M3 MCP integration, không benchmark.

## Checkpoint lịch sử — 15/10/2026, campaign V5+ đã terminal

**FAIL / TUNING_QUOTA_EXHAUSTED**; B BLOCKED4lượt, C PASS1lượt, final NOT_RUN.
Không chạy lại hoặc tạo campaign để bỏ qua cap. Các mục14/10 bên dưới là lịch sử.

| Attempt / prompt | Canonical trong results/adaptive_acceptance/2026-10-15-v5-plus | Lỗi đã quan sát | Cách cải thiện đã thử / điều không lặp |
|---|---|---|---|
| B1 / V5 | attempts/01/20261015T003703727090Z-e62648364844/run_record.json | Hunk counts exceeded: invoice body3, count2 | V6 thêm neutral3-line example; không sửa @@ hộ model |
| B2 / V6 | attempts/02/20261015T004240341955Z-b5e07ce0a4e0/run_record.json | Malformed hunk: count6 thay3; raw còn chứa tests diff không được phép | V7 bỏ examples/numeric copying, rút gọn và tách snippet count khỏi file length; không sửa tests |
| B3 / V7 | attempts/03/20261015T004931535482Z-daa3ae13e75e/run_record.json | Correct paths/starts/counts, thiếu context marker trước def và statement giữ nguyên | V8 body-only whitespace example; không trim/dedent hoặc thêm prefix hộ model |
| B4 / V8 | attempts/04/20261015T005533899467Z-16d544650f34/run_record.json | Protected or unapproved path: model sinh host_path_policy.json từ metadata | B quota exhausted. V9 nhấn metadata≠file và -/+ whole snippet, chỉ chạy C; **không B5** |
| C1 / V9 | attempts/05/20261015T005816855246Z-a997178dc2f5/run_record.json | Không có failure; real repair PASS | Collection/fallback2tests và staticPASS, sourceunchanged; không tối ưu/rerun C đãPASS |
| Final A/B/C | Không có real run | B chưa tuningPASS | NOT_RUN theo gate, không dùng A historical/C tuning để claim3sameversion |

Tất cả5 outputs EOS, không truncated/timeout/OOM, source gốc không đổi. B dừng
trước apply; chưa có kết luận semantic repair B. File raw/prompt/public bundle
cùng canonical folder; log worker trong attempts/NN/model-workers. Full152tests
PASS và final audit PASS không thay đổi trạng thái thực nghiệm FAIL.

Minor đã ghi nhận, chưa sửa: static-check feedback chọn stdout pytest thay vì
diagnostic của checker; đọc full canonical stage khi điều tra. Deep JUnit counter
reconciliation chưa nằm trong extension. Human replay/M3 integration chưa nghiệm thu.

## Lịch sử trước extension V5+

| Task/profile | Evidence | Nguyên nhân | Trạng thái / bước tiếp |
|---|---|---|---|
| Setup dependencies | Sandbox pip WinError10013 | Socket bị chặn, không phải Python dependency không tồn tại | Approved elevated install đã thành công; không sửa venv cũ |
| M3 LF/Unicode apply | tests/20261014T083507819545Z-93001d8645af | Private apply kế thừa global autocrlf=true, bytes không khớp prediction | Đã cố định private seed config; full43 GREEN; không đổi global |
| Real A prompt-v1 | repair/20261014T090352481580Z-8f8da9b4cddd | Qwen sinh SEARCH/REPLACE thay unified diff | FAIL trước apply; source unchanged; giữ raw. Không convert output hoặc retry v1 |
| Real A prompt-v2 | repair/20261014T091104527173Z-8e59e14c75c7 | Header đòi 3 old/new lines nhưng body chỉ có 2; strict parser báo Truncated or malformed hunk | FAIL trước apply, source unchanged; đã dừng phương pháp sau hai failures |
| Real B/C | Chưa có execution run | A chưa qua format gate; không chạy tiếp model đã fail hai lần | NOT_RUN, không fake fallback; cần owner duyệt phương pháp mới |
| Final review | tests/test_finalization.py và test_review_guards.py | Lỗi terminal trước export/cleanup; raw pytest PASS che required skip; thiếu deadline ở setup/tokenize; không check applied diff export | Một fix pass có RED→GREEN; xem final tests và PROGRESS |

Expected RED records của TDD không phải lỗi còn tồn tại: chúng chứng minh guards
bắt thiếu implementation. Mỗi record chứa đầy đủ stdout/stderr/exit/timing.
Không cộng các lần fake/invocation qualifier vào repair success. Không lấy
timeout hoặc missing required test thành PASS.

## Campaign V3/V4 — final14/10, không chạy lặp

| Task/version | Evidence trong results/acceptance/2026-10-14-prompt-v3-v4 | Nguyên nhân / phương pháp cần tránh |
|---|---|---|
| A V3 | attempts/01/20261014T143611380216Z-4cfb6e98732e | RealPASS; không còn blockerformat củaA dướiV3 |
| B V3 | attempts/02/20261014T143724950165Z-28712948b7fb | Model chỉ sửapricing; invoicebug còn, TEST_FAILED. Không rerununchangedV3 |
| A V4 | attempts/03/20261014T143844748488Z-ca62ce11f2d2 | RealPASS; không poolA-V3 thành kết quảversionV4 |
| B V4 | attempts/04/20261014T143948282795Z-dc2133321dfe | Headerinvoice bắt đầu1, functionsource bắt đầu4; exactpreflightreject. Không hostfixline/recount/relaxguards hoặc rerunV4 |
| C và3/3gate | NOT_RUN / chưađạt | Failurecap2 reached, campaignterminalFAIL; không dùngremaining2slots hoặc resetmanifest |

No timeout/OOM observed, không có cơ sở kết luận thiếu tài nguyên là nguyên
nhân4runs này. Twofailures khác nhau (semanticomission/coordinate). Tiếp theo
cần ownerdecision cho phương pháp mới; không tự thêmV5/changebackend/training.

