# T5 — Collection evidence, 06/11/2026

**DONE code/fixture local; dừng chờ người dùng xác nhận T4.** Không commit/push.

- Gate cuối: 264 PASS/2 SKIP/0 FAIL/ERROR, 192.931s JUnit; Ruff và whitespace scoped PASS. Hai skip đã có (Windows POSIX modes, optional vermin).
- RED27→implementation; coverage RED2→GREEN2, precedence RED4→GREEN4; review1 Important mở rộng RED12→GREEN12. Không finding hoãn.
- Post collection có JSON/JUnit hoàn chỉnh, exit2 khớp và baseline qualified: TEST_COLLECTION_FAILED. Thiếu report/malformed/timeout/integrity/required incomplete giữ ERROR.
- Probe metadata AVAILABLE/MISSING; host chỉ copy report AVAILABLE và kiểm hash/size. Không suy collection failure từ việc docker cp thiếu file.
- Public FailureCode vẫn TEST_FAILED; detailed message TEST_COLLECTION_FAILED. Vector schema/policy/metrics không đổi.
- Demo trusted fixture sinh vector có baseline PASS/post collection FAIL; A0–A3 FAIL; synthetic, không Docker/campaign benchmark.
- Hướng dẫn và file map: [T5 guide](../m2_t5_collection_failures.md).
- Artifact: `results/m2/w1112/t5/20261106-collection-evidence/`; final.log/.xml, commands.json/.md, review.json, preservation.json, demos/, source/, artifact_hashes.json.
- TEMP ledger: `C:/Users/pc/AppData/Local/Temp/vgt5-x19v3u52/ledger.md`. Không chạy lại phần đã PASS nếu không có thay đổi liên quan.
- T6 source cleanup block và thân tests giữ nguyên; fixture Docker cập nhật metadata để tương thích probe mới. T7 guard không đổi; report Codex Diff, DB và artifact T6/T7 giữ nguyên.
- Chờ M3 Docker smoke và raw evidence/run mới cho4 slot đã báo; không chốt chúng đã được xử lý. Không tự chạy T4 hoặc thay timeout.
