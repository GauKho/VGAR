# M2-W9-4 — Arm và policy provenance xuyên session

Approved user plan23/10/2026, inline tại dirtyVGAR. Spec chính:
New_task/VGAR_W9_W16_Deliverables.md, M2-W9-4; reviewM3 mục(d) đã duyệt hướng.

- [x] Snapshot/status/checkpoint; preserve dirtyM1/M2. Baseline repair-server10PASS.
- [x] TestsRED cho internal RepairExperiment, explicitarm/derivedpolicyhash,
  optionalexpected3sidecarhashes; no global A0/A1/A2mapping inference.
- [x] Adapter opt-in; run/start_session/MCPgetcontext optionalexperiment;
  storeimmutable snapshot ởrecord/session, kiểmreload trướcwrite; bindbundlehash.
- [x] Wire variant thật vào baseline/completeverificationW9-2, khôngmetadata-only.
- [x] EvidenceBundle.metadata.experiment, canonicalhash finalconsistent;
  legacyNonegiữ nguyên; noDTO/status/schema_version/admission/promptbudgetchange.
- [x] NewW9tests + allW9 + allW78 khôngexclude, repairserver sau sửapipeline,
  consumerregression/Ruff, evidence/JUnit/UTC/duration/version/snapshots.
- [x] Review độc lập, docs/interface/decision/status/PROGRESS/checkpoint; dừng.

APIinput: RepairExperiment(variant_policy, arm, expected_hashes=None). Effective
policyarm bindexplicit nếunull, rejectmismatch; policyhash khôngnhậncallertựkhai.
Record/session experiment cóvariant_id,arm,policy_hash,variant_policy,
expected_hashes,bundle_hashes(actualsauvalidation); so sánh/validate khi reload.
Namespacebundle metadata.experiment. Không tựtuyên bố callerlabel chứngminharm.

Không dependencies/Docker/WSL/model/harness/commit/push/TaskStatus hoặcW9-3.
Native chỉapprovedW78fixtures, W9sharedfixture chỉconsumer khôngbypassregistry.
Pilot/runnerM3interoperability ghiNOT_RUN, khônglàgate bổ sungtechnicaltask.
Evidence: results/m2/w9/m2-w9-4/20261023-implementation/.

## Bổ sung được người dùng cho phép trong lúc kiểm chứng

- Review phát hiện hai khe hở reload: xóa cả hai profile và baseline hash thiếu/sai.
  Đã thêm tests RED, sửa bằng marker internal `experiment_required=true` và kiểm
  baseline hai phía. GREEN 6 focused tests; legacy thực sự không profile giữ nguyên.
- Full suite lần đầu 278 PASS / 1 FAIL do source mapping của environment trỏ
  đường dẫn không tồn tại. Người dùng cho phép sửa đúng một file `.pth` để trỏ
  `D:/Project/CAPSTONES/VGAR/src`; lưu bytes gốc/hashes, probe và test gốc PASS.
  Không cài dependencies, không sửa test/plugin/executor để né gate.
- Reviewer độc lập không thay phê duyệt M3. Runner M3 thực tế chưa có ở checkout.
- Chỉ kết thúc W9-4 sau final gates/checkpoint; không tự chuyển W9-3/task khác.

Kết quả cuối: full W7–8/W9 285 PASS không exclusions; W9 + repair server 141
PASS; consumer regression 226 PASS; Ruff và review fix PASS. Các nhóm có chồng
lặp, không cộng dồn. Giữ 11 terminal fake records, không model inference.
M2-W9-4 hoàn thành kỹ thuật; runner M3/admission/pilot không tự ghi PASS.
