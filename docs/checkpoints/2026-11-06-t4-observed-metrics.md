# T4 — Observed FAR/FRR,06/11/2026

**DONE code/fixture local; dừng chờ xác nhận T2.** Không commit/push.

- Giữ FAR/FRR hiện hành và complete; thêm observed counts/rates/coverage theo planned slots, tách vector ERROR khỏi check FAIL.
- Accounting planned/generated/NOT_APPLICABLE/pool ERROR/pending; A0/A1 bằng nhau. Không đổi frozen pool/hash hoặc exclusion.
- Renderer copy input, enrich summary cũ khi đủ counters, missing/zero giữ N/A; output deterministic, có PARTIAL và chú thích ERROR không phải proven detection.
- RED12 FAIL → GREEN127 PASS/0 FAIL/ERROR/SKIP, 57.139s JUnit. Ruff/whitespace scoped PASS. Review độc lập không finding.
- Demo synthetic12 slot: observed BAD3/GOOD1, coverage0,3/0,5, FAR/FRR cũ N/A, observed0/1, complete=false. Tất cả4 vector là ERROR, không phải4 phát hiện. Có thêm fixture pending.
- Guide/file map/lệnh: `docs/m2_t4_observed_metrics.md`.
- Artifact `results/m2/w1112/t4/20261106-observed-metrics/` gồm green.log/.xml, commands, demos/, review, preservation, source snapshots và artifact_hashes.json.
- TEMP ledger `C:/Users/pc/AppData/Local/Temp/vgt4-e7rye289/ledger.md`; không làm lại gate đã PASS nếu không có thay đổi liên quan.
- Giữ T5/T6/T7 và report/DB/artifacts cũ. Chưa có số liệu campaign thật mới; không tự tiếp T2 hoặc chạy model/Docker.
