# M1-W9-4 — Receipt review kỹ thuật offline

Ngày ghi nhận23/10/2026. Một reviewer Codex fresh-context đọc implementation,
plan và upstream pin, không sửa repo hoặc chạy Docker/harness/model. Đây là
technical QA, **không phải M3 approval**, không chứng minh gold resolved.

Plan: `docs/superpowers/plans/2026-10-23-m1-w9-4-official-harness-offline.md`.
Phạm vi: module harness mới, shell, profile, tests và tài liệu riêng W9-4;
không review lại M1/M2 cũ. Base/head vẫn525f9936a3c0abe5ea056c532c1f889ce84627a7,
các files W9-4 chưa commit. Hash cuối lưu trong evidence snapshot.

## Findings và xử lý

Không finding Critical hoặc Minor riêng. Năm finding Important được chấp nhận
và xử lý trong một fix pass, không nhờ reviewer lặp lại.

| Finding | Nguy cơ | Cách sửa / regression test |
|---|---|---|
| CLI Docker khác daemon của SDK | Preflight image và cleanup có thể ở daemon A, còn harness ở B | Profile thêm explicit docker_host; bỏ ambient DOCKER_CONTEXT, cùng env cho CLI/SDK/harness/cleanup, so daemon ID thực. Hai tests daemon/context |
| Official timeout bị ghi ERROR | Upstream catch timeout, exit0, không có report; mất phân loại TIMEOUT | Chỉ khi patch đúng bytes và cả test_output/run log đúng dấu timeout của pin thì ghi OFFICIAL_TEST_TIMEOUT. Test process exit0 + no report |
| Cleanup ERROR vẫn chạy tiếp/QUALIFIED | Container orphan có thể còn chạy khi launch task tiếp | Dừng campaign, các task sau NOT_RUN; cleanup/process recovery lỗi veto qualification. Test cleanup failure |
| Input biến mất trong finally | Task có thể còn RESOLVED và thiếu terminal record | Integrity read có report riêng, OSError→ERROR, chốt record task rồi dừng; không cộng resolved. Test deleted input |
| Pipe drain không giới hạn sau kill | Descendant giữ pipe gây treo dù deadline hết | POSIX Popen tạo session riêng, signal chỉ owned group; drain5+5giây và wait1giây có bound; giữ partial output, báo recovery không hoàn chỉnh để dừng. Test bounded drain |

Evidence `results/m1/w9/m1-w9-4/20261023-offline/`:
`review_red.json`:6FAIL/42PASS (hai tests cho finding daemon),
`review_green.json`:48PASS. Regression cuối/lint/snapshot ghi trong cùng root;
không cộng tests giữa các lần chạy để báo tổng.

## Những phần reviewer không phán quyết và ruling của implementer

| Phần không kiểm thực tế | Ruling và ảnh hưởng |
|---|---|
| Linux/Docker/images và terminate/remove thật | Giữ external qualification gate BLOCKED; tests mock không thay bằng chứng thật. Nếu môi trường khác kỳ vọng, phải dừng qualification và điều tra |
| Gold3task / ngưỡng2resolved | Chưa chạy, NOT_RUN; không đóng toàn bộ W9-4 hoặc suy model repair thành công |
| Tính lại hash Parquet gốc trong review | Implementer đã chạy input preparation trên cache thật và đối chiếu hash pin; reviewer chỉ kiểm logic. Đây không phải dataset audit độc lập lần hai |
| Unrelated M1/M2/full suite/model quality/M3 approval | Giữ nguyên scope; kiểm before/after để bảo toàn files. Selected regression không được gọi full-suite, code QA không thay review M3 |

Không có deferred minor do reviewer nêu. Các limitations còn lại được ghi rõ,
không dùng wording “production-ready Linux” hoặc “gold qualification PASS”.
