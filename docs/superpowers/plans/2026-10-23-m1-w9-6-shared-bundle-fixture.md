# M1-W9-6 — Bundle fixture dùng chung M2/M3

Plan đã được người dùng duyệt23/10/2026; thực thi inline tại VGAR hiện tại.
Spec: New_task/VGAR_W9_W16_Deliverables.md, M1-W9-6; kế hoạch M1 ngày23/10 mục11.

## Mục tiêu / ràng buộc

- Copy nguyên bytes source single_file_login sang fixture riêng, giữ lỗi/tests.
- Static graph, producer/consumer hiện có; một bundle, counterfixture len(text)
  nhãnfixture-only:characters, không coi là tokenizer/modelbenchmark.
- Relative task paths, source/sidecar hashes, deterministic regeneration vào
  output mới; optional local tokenizer manifest, không network/fallback.
- Không đổi src/publicDTO/admission/trustedregistry hoặc fixturesW78; không
  dependencies/Docker/WSL/model/harness/commit/push/TaskStatus. W9-4 vẫnBLOCKED.

## Checklist

- [x] Snapshot/status/environment hiện có; bảo toàn dirtyimplementation.
- [x] TestsRED trước script; thực thi consumer thật trên RepairTask.
- [x] Scriptbuild/validate, canonicalfixture và profile/README, GREEN.
- [x] Portable/determinism/tamper/counter/hints/pathguards; selectedregression/Ruff.
- [x] Review độc lập, evidence/status/checkpoint; dừngW9-6.

## Thiết kế và nghiệm thu

`scripts/build_w9_bundle_fixture.py` tạo vào --output-root mới, optional
--tokenizer-manifest. CLIvalidate fixture chuẩn dùng --validate-root, không
ghi lại output. Helper load_fixture resolve task bằng load_task hiện có, kiểm
profile/hash/taskidentity rồi gọi load_handoff; không bypass admission.

Task.json/source/bundle/profile không absolutepaths/timestamps. Snapshot graph
deterministic theo content và relativepaths. ScratchSQLite ngoài output, không
đưa DB/cache vào fixture. Profile hashes task/source/sidecars, không tựhash.

Tests phải chứng minh source/sourceW78 không đổi, copyUnicode/spaces loadPASS,
invalididentity/hash/source/snippet/counts/counter/sidecar fail, editsafterload
detected, missingtokenizer khôngfallback, nooverwrite/overlaps bịchặn. Qwenrecipe
không là gate consumerfixture; nếu thực thi local ghi riêng actualidentity/counts.

Evidence: results/m1/w9/m1-w9-6/20261023-fixture/; từng command exclusivefile,
stdout/stderr/exit/UTC/duration/JUnit/snapshots. Không gọi selected là fullsuite.
Finalreview tập trung task_idbinding, portability/CRLF, outputpathguards,
tokenizer-mode separation và không tựtuyên bố runtime/collection/repairPASS.
