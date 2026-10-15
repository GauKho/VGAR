# Review extension V3/V4 trước inference

Một fresh-context gpt-6-astra reviewer đọc code/plan/tests, không sửa file, không
chạy GPU/test hoặc childagents. Không Critical; ba Important được xử lý trong
một fix pass TDD, trước khi freeze campaign.

| Finding | Fix | Regression tests |
|---|---|---|
| Task JSON mutable sau snapshot | Hash từng task JSON, use frozen DTO, compare task trong canonical với snapshot | frozen snapshot task files; changed task blocks reservation |
| Ledger FAIL→PASS có thể đổi nhánh resume | Reassess canonical+artifacts, kiểm identities/status/hash/gateerrors và derived state | FAIL→PASS ledger tamper; historical artifact tamper |
| Gate audit thiếu actual collection/fallback/export | Required IDs/commands/nodeIDs, selection+unlinked fallback C; applied bytes phải khớp successful git diff command | missingselection/fallback/collectioncmd/IDs và export mismatch |

RED9 +22priorPASS: `results/tests/20261014T142938010173Z-dbc87ea000d3/run_record.json`.
GREEN 33 tests: `results/tests/20261014T143217983380Z-886c0cfa06d3/run_record.json`.
Full suite sau fix: 126 PASS tại `results/tests/20261014T143340455463Z-3177af8ceb35/run_record.json`.
Full suite cuối sau campaign: **126 passed in 87.16s**, exit 0 tại
`results/tests/20261014T144408789514Z-d6a80718ea70/run_record.json`.
Không sửa parser/verifier,
không lấy structural simulated evidence trong tests làm modelrun thật.

Review không đánh giá modelquality, future results, adversarialrepo/cache/benchmark,
oldparser/verifier/JUnit minor hoặc actualtests (reviewer không chạy). Những giới
hạn này được ledger và report rõ; author actualevidence/humanrepro gates riêng.
