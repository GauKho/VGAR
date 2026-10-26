# M2-W9-3 — Admission SWE-bench và Docker bridge

**Hoàn thành kỹ thuật ngày 24/10/2026 theo tiêu chí M2-W9-3.**
Task Xarray qua trọn `run_repair` Docker, không dùng registry fixture; hash sai
bị chặn. Final regression **317 PASS**, lint/audit/cleanup PASS.
Nguồn tiêu chí: `D:/Project/CAPSTONES/New_task/VGAR_W9_W16_Deliverables.md`, hàng M2-W9-3:
task pilot qua `run_repair` không cần `trusted_fixtures.json`; hash sai vẫn bị chặn.

## Đường chạy mới

`RepairPolicy(runtime="docker_admitted")` và keyword `admission` là opt-in.
`native_trusted_fixtures` vẫn là default, giữ nguyên registry/byte guard.
Không nhận arbitrary executor; engine tự dựng adapter cho lease của nó.
Docker mode yêu cầu experiment W9 rõ ràng để dùng đúng required-check policy.

`repair/admission.py` cung cấp:

```python
admission = admit_task(
    task, manifest_path, profile_path,
    expected_manifest_hash=approved_manifest_hash,
    expected_profile_hash=approved_profile_hash,
    bundle_hashes=approved_three_sidecar_hashes,
    source_roots=["xarray/core"],
    overlay={"tests/vgar_w9_repro_quantile.py": independent_issue_test_text},
    docker_host="unix:///var/run/docker.sock",
)
run = run_repair(
    task, RepairPolicy(runtime="docker_admitted"), generator, None, output_root,
    m1_counter=counter, tokenizer=tokenizer,
    admission=admission, experiment=experiment,
)
```

Caller lấy các expected pins từ nguồn đã duyệt độc lập. Tự tính hash từ input vừa
nhận rồi gọi là phê duyệt không tạo authentication. Admission là consistency
contract, không có chữ ký số hoặc registry mới. `task.source_repo` và bundle phải
đúng paths của máy thực chạy; snapshot hiện không tự relocate.

Kiểm trước admission/execution:

- Manifest phải đúng schema/snapshot/population dev năm task của M1; đối chiếu
  task ID, repo, base commit và nguyên issue text. Profile phải `COLLECTED`, đúng
  expected profile hash và task; không nhận hai profile `EXCLUDED` của W9-5.
- HEAD đúng base; inventory không có links/submodules/untracked source. So từng
  raw file với Git blob object ID của exact base tree, không tin clean status
  hoặc index/filter của repo. Git reads/reset tắt replacement objects bằng
  `--no-replace-objects`; Python inventory còn phải khớp profile M1.
- Ba sidecar hashes được pin riêng và consumer M1 vẫn kiểm source/range/identity.
- Allowed paths bằng toàn bộ Python production inventory dưới source roots khai
  báo, loại thư mục test/tests/testing và test_/conftest files. Roots/protected
  paths phải không chồng nhau. Không lấy editable paths từ gold patch.
- Overlay chỉ là file test mới, tên `tests/vgar_w9_repro_*.py`, được bảo vệ và pin
  nội dung. Task phải có failing selectors và regression scope rõ ràng. Overlay
  được thêm vào private lease sau copy base; không sửa checkout M1.

Session và canonical record giữ cùng `admission_required=true` + snapshot gồm
pins, task/inventory/overlay hashes, source roots, paths và Docker endpoint.
Load kiểm hai phía và revalidate inputs trước `load_run` ghi file. Save dùng
structural checks để vẫn ghi ERROR/cleanup khi source bên ngoài đã drift;
execution luôn revalidate đầy đủ. Bundle lưu cùng snapshot tại `metadata.admission`.

## Snapshot, argv và cleanup

Git init/apply/diff tiếp tục trên host trong seed/worktree riêng. Nhánh admitted
hỗ trợ `.gitattributes` bằng info/attributes có precedence cao nhất, tắt text,
filter, ident và working-tree-encoding transforms; kiểm bytes sau checkout.
Native fixture branch vẫn từ chối attributes như trước.

Mỗi command target tạo container mới với image digest + image ID + daemon ID
đã pin, Linux amd64, name/operation/admission labels riêng, `--network none`,
cap-drop ALL, no-new-privileges và pids-limit 256. Không bind mount host, không
Docker socket trong container, không cài thêm VGAR/Torch/tools hoặc pull image.

Target driver stdlib Python 3.6+ reset exact base **trước** copy candidate; kiểm
base Python identity của profile. Archive chỉ chứa regular files có path an toàn,
không `.git`/link/traversal/duplicates; attest mọi expected byte trước và sau lệnh.
Candidate source không bị reset sau apply. Overlay/source/config trên host được
kiểm lại; chỉ editable source paths được phép khác base. Không copy source target
trở về host; chỉ các report paths cố định được đưa về private reports.

Chỉ nhận template argv pytest/mypy/Ruff do engine tạo; Python được map sang
`/opt/miniconda3/envs/testbed/bin/python`, cwd `/testbed`. Pytest dùng standalone
reporter copy từ plugin M2, báo exact node IDs/outcomes, JUnit và raw streams.
Syntax cũng chạy bằng interpreter target; source snapshot/static binding ghi
Docker env/interpreter identity. Tool không có trong image được giữ lỗi raw và
diagnostic report ERROR; không cài thêm hoặc fallback host. A0/A1 có thể chấp nhận
optional static errors; A2 vẫn yêu cầu đủ static execution/delta.

Một operation bị chặn bởi command/global deadline (mỗi Docker CLI step tối đa
60 giây), bounded output và finally cleanup. Cleanup có ngân sách riêng tối đa
30 giây, chỉ remove name/image/labels thuộc operation đã reserve, kiểm không còn
container; cleanup lỗi ngăn PASS. Host Git cũng bị clip global deadline.
`--keep-workspace` chỉ giữ host lease, không giữ container.

Đây là isolation khỏi host bằng Docker và consistency attestation; không là
chứng minh chống một target chủ ý giả mạo reporter trong chính container đó.

## Pilot kiểm chứng và giới hạn

Task chọn `pydata__xarray-3305`, base
`69c7e01e5167a3137c285cb50d1978252bb8bcbf`, profile W9-5 hash
`sha256:028f8acc40abd29b2851b77fbf13dc4409aa06118bcd52005020535b4296f4b7`.
Image amd64 digest `sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89`;
Python 3.10.15/pytest 7.4.0. Canonical manifest năm task giữ nguyên.

Test mới tái hiện MCVE DataArray.quantile keep_attrs=True từ problem_statement và
control keep_attrs=False. Không đọc F2P/P2P/test_patch/gold patch/hints. Candidate
scripted là demonstration fix trong private lease, không ghi vào repo Xarray.
Handoff integration source-only lấy đúng method từ source/graph đã lưu rồi mở
rộng đủ dòng 2827–2878, tạo version/range/sidecar hashes riêng và qua consumer thật.
Không sửa graph/bundle M1 cũ; explicit arm=bm25 chỉ là caller label;
không đo/requalify thuật toán retrieval. Counter/tokenizer integration-only theo
whitespace, không gọi số units là token Qwen hoặc chạy inference.

Lần smoke 02: baseline PASS, prompt ERROR vì V11 replacement đòi complete source
lines trong khi method range bắt đầu cột 4; cleanup/source preservation PASS.
Giữ nguyên evidence lỗi. Smoke 03 bị chặn ở preflight vì checkout chỉ đăng ký V11, chưa tạo container.
Smoke 04 giữ V11 và dùng handoff đủ dòng ở trên; không đổi defaults, cap hoặc
bundle M1. Đây là qualification admission
và bridge, không qualification default V11 với paired 8k bundles/model/M3 runner.

Hai tasks W9-5 EXCLUDED vẫn chưa runnable; task này không sửa dependencies hay
collection scope để ép đủ năm. Không đóng pilot 5×3 records hoặc toàn tuần 9.
Oracle/packing/mapping/protocol batch cuối cùng và review liên thành viên vẫn là
công việc riêng. Direct API và persisted session có adapter; MCP start chưa có
input admission mới, không claim runner/MCP pilot interoperability đã nghiệm thu.

## Evidence

Root: `results/m2/w9/m2-w9-3/20261024-docker-admission/` (ignored, ngoài Git).

- `before.json`, plan và `progress.md`: điểm bắt đầu, phạm vi và rulings.
- `admission_red.json`, `bridge_red.json`, `bridge_green_01.json`: RED 18, rồi
  GREEN 18 + RED 10, rồi GREEN 28.
- `drift_red.json`: 1 FAIL/1 PASS; `drift_green.json`: focused 30 PASS.
- `runtime_preflight.json`: RAM/disk đủ và không có container; không giải phóng
  cache hoặc đổi runtime/settings.
- `prepare_smoke*.json`, `docker_smoke_02.json`: giữ cả lỗi script chuẩn bị và
  lỗi prompt; không xóa/ghi đè evidence cũ.
- `frozen_source_03.json`, `smoke-inputs-lines/`, `prepare_line_smoke.py`, `run_smoke.py`: recipe/inputs/pins và
  bản source dùng cho smoke cuối.
- `full_w78_w9_01.json`/JUnit: **315 PASS** trước fix review.
- `review_r1_red.json` → `review_r1_green.json`: **2 FAIL → 2 PASS** cho Git
  replacement config drift. Sau fix, `full_w78_w9_final.json`/JUnit: **317 PASS**,
  không FAIL/ERROR/SKIP/exclusion; command 371,876 giây. Gồm 32 tests mới và
  285 tests W78/W9 đã có. [Review độc lập](reviews/2026-10-24-m2-w9-3-admission-review.md).
- `lint_final_new.json`, `lint_final_modified.json`: PASS (full lint file mới, E9/F legacy).

## Kết quả chốt

Final run `20261024T104018047265Z-61c601678725` tại
`results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/`:
canonical **PASS, complete=true**, wrapper exit 0, 638,903 giây. Context,
workspace, baseline, prompt V11, generation fake, parse/apply và verification
PASS; selection COMPLETE; host cleanup PASS, original_source_unchanged=true.

| Test issue reproduction | Baseline | Sau patch |
|---|---|---|
| keep_attrs=True giữ units=K | FAIL | PASS |
| keep_attrs=False không giữ attrs | PASS | PASS |

`independent_audit_05.json` xác nhận đủ 14 target operations: runtime/profile,
base commit, private byte snapshot trước/sau, overlay hash, canonical/session/
bundle admission+experiment binding và frozen source đều khớp; 14 cleanup PASS.
`containers_final.json` kiểm không còn owned containers. Registry, canonical
manifest/profiles, original source và HEAD giữ nguyên. Sai profile pin bị reject
trước Docker (`negative-pin-05.json`); các hash/source cases khác nằm trong suite.

Syntax target PASS. Raw mypy/Ruff FAIL do chưa có module trong image; diagnostic
reports ERROR, ghi nhận optional theo A0, không biến thành static PASS. Không
qualification A2/tools/model hoặc chuẩn bị đủ năm tasks runnable.

Smoke04 cũng canonical PASS/audit PASS; wrapper có lỗi summary do selection
không có status, xảy ra sau canonical publish. Giữ raw ERROR và summary khôi phục
riêng; helper đã sửa trước final05. Lần 02 prompt ERROR, lần03 preflight ERROR và
lỗi script chuẩn bị đầu tiên đều giữ nguyên; không gộp thành benchmark attempts.

Review độc lập có 0 Critical/1 Important (Git replacement refs), đã sửa qua
RED2→GREEN2 và full317PASS. Không có Critical/Important còn mở; không re-review
hoặc suy thành nhóm/M1/M3 đã duyệt. Các declined-to-judge được root ghi nhận trong
review doc. Final checksum/preservation gate: `checkpoint_final.json`; receipt
`closing_checks_final.json` trong evidence root. Không commit/push, Task Status,
model/gold/cache release, Docker settings/images changes hoặc task kế tiếp.