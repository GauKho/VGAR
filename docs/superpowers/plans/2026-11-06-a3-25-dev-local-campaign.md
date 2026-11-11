# Plan chạy A3 thật trên cùng 25 dev task W10

> **For agentic workers:** Dùng `superpowers:executing-plans` khi được giao thực hiện từng chặng. Checklist dưới đây là kế hoạch, chưa phải bằng chứng đã chạy. Mỗi xác nhận chỉ thực hiện một chặng, báo cáo rồi dừng. Không commit/push.

**Mục tiêu:** chạy batch A3 với model thật và Docker verification trên đúng population W10 gồm 11 + 14 = 25 dev task, giữ đầy đủ exclusions/errors/timeouts và evidence để nghiệm thu M2-W12-1.

**Kiến trúc:** dùng runner hiện có `run_repair_experiment.py` → `make_launch()` → `run_repair()`. Một lượt sinh mỗi attempt, arm graph, A3 thêm API/structural vào required checks của A2 W10. Model chạy trong worker của máy WSL/GPU; test/static verification chạy trong Docker images đã qualify. Không dùng `solve --agent` hoặc suy A3 từ record A1.

**Công nghệ:** Python/venv Linux đã xác minh, WSL2, Docker Desktop Linux containers, Qwen3-4B-Instruct-2507, tokenizer local đã pin, static resolver/profile hiện có.

**Spec:** [thiết kế W11–W12](../specs/2026-10-31-w11-w12-design.md), [phân công song song](../specs/2026-10-31-w11-w12-parallel-split-design.md), [bàn giao A3 M2](../../m2_w12_1_a3.md). Deliverables gốc: `D:\Project\CAPSTONES\New_task\VGAR_W9_W16_Deliverables.md`, M2-W12-1. Lựa chọn đã duyệt trong hội thoại thay pilot 5 task/re-plan bằng 25 task/một lượt sinh.

## 1. Quyết định và giới hạn

- Người dùng đã chọn ngày 06/11/2026: **readiness và smoke trước; batch 25 task sau khi xử lý T1**. Plan này không tự triển khai T1 hoặc T3.
- Mục đích là tạo record A3 trực tiếp. Không thay bằng mutant evaluation, gold verification, fixture, agent demo hoặc verdict suy diễn.
- Giữ nguyên dirty work T2/T4/T5/T6/T7 và báo cáo người dùng. Không reset/clean/stash, sửa artifact lịch sử, thay task hoặc đổi model/prompt/budget/ranking để làm kết quả đẹp hơn.
- Giữ policy hiện hành: V11 `m2-w78-v11`, input cap 6000, output cap 1536, reserved margin 256, generation timeout 900 s, command timeout 120 s, global timeout 1800 s.
- A3: `normalized`, `path_listing=context`, graph; required `tests, syntax, mypy, ruff, api, structural`; serialized recorded checks giữ bốn tên cũ.
- Model: `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, float16, device_map auto, do_sample false. Di chuyển đường dẫn local không đổi nội dung/model identity.
- Không áp ĐX1–ĐX5, không đổi sang timeout 1500/2700, quantization, agent retry hoặc held-out. Nếu nhóm quyết định đổi protocol, dừng để sửa plan trước launch.
- Một worker, chạy tuần tự; không chạy mutant pool, agent/model khác hoặc tác vụ GPU/Docker nặng cùng lúc. Không prune/xóa cache/images, đổi `.wslconfig`, shutdown WSL hoặc sửa Docker settings.
- Raw nằm trong output mới, không commit. Có đầy đủ record không đồng nghĩa patch phải ACCEPT/resolved; cũng không đồng nghĩa nhóm đã review/merge/freeze.

## 2. Hiện trạng đã kiểm và phần chưa biết

Snapshot chỉ đọc ngày **06/11/2026**, không phải readiness certificate:

| Nội dung | Quan sát thực tế |
|---|---|
| Repo/nhánh | `D:\Project\CAPSTONES\VGAR`, `m2/w12-a3-verifier-d15-20261105` |
| HEAD | `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`; có nhiều thay đổi chưa commit, kể cả production code T2/T4/T5/T6/T7 |
| A3/runner | Đã có A3.json, fairness, preflight, runner/resume, GPU sampler và aggregate đọc variants động |
| RAM host | Tổng 16.491.000 KiB, trống 5.094.712 KiB, khoảng 4,86 GiB lúc đo |
| GPU | RTX 4050 Laptop; tổng 6141 MiB, trống 5319 MiB lúc đo |
| Đĩa | C trống 14.718.296.064 bytes ≈13,7 GiB; D trống 66.286.714.880 bytes ≈61,7 GiB |
| WSL | `VGAR-Harness-W9` và `docker-desktop`, đều WSL2, đều **Stopped** |
| Data trong checkout Windows | `data/` hiện chỉ có `w9`; không chứng minh W10 có/không có ở nơi khác |
| Model config | `configs/m2/w9_pilot_linux.json` còn snapshot `/mnt/c/Users/nlhnh/...` và interpreter `~/vgar/.venv/bin/python`; chưa xác minh trên máy này |
| Chưa kiểm | Docker daemon/identity, images/digests, assets trong distro, CUDA/venv Linux, source inventories, W10 raw, repro inputs và tổng dung lượng cần tải |

Không khởi động distro/Docker hay nạp model trong bước lập plan. Không lấy lỗi access denied của sandbox làm bằng chứng Docker hỏng; các số trên được đọc lại ngoài sandbox với quyền được duyệt.

**Blocker khoa học:** T1 chưa sửa, API NOT_RUN có thể làm A3 VERIFICATION_INCOMPLETE; T3 `astropy-13033` gold TEST_FAILED còn phải điều tra. T2 local đã có fix/reproducer, nhưng 10 gold thật vẫn chưa xác minh khi chưa có raw. Không coi các kết quả cũ đã được sửa chỉ vì code local PASS.

## 3. Population và accounting

Nguồn duy nhất: `configs/m3/w10_dev_stage1.json` và `configs/m3/w10_dev_stage2.json`, không dùng dev-25 retrieval tuning.

| Stage | Thứ tự task giữ nguyên |
|---|---|
| 1 — 11 | astropy__astropy-13033; django__django-10914; matplotlib__matplotlib-13989; mwaskom__seaborn-3069; pallets__flask-5014; psf__requests-1724; pydata__xarray-3993; pylint-dev__pylint-4604; pytest-dev__pytest-5631; scikit-learn__scikit-learn-10297; sphinx-doc__sphinx-10673 |
| 2 — 14 | sympy__sympy-11618; astropy__astropy-13453; django__django-10973; matplotlib__matplotlib-20488; psf__requests-1766; pydata__xarray-4629; pylint-dev__pylint-4970; pytest-dev__pytest-7205; scikit-learn__scikit-learn-10844; sphinx-doc__sphinx-11510; sympy__sympy-12481; astropy__astropy-13977; django__django-11087; matplotlib__matplotlib-20676 |

- Dataset revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
- Manifest pin `sha256:11e0b7b1168236e246dc8334db45ad932223a16ae7af0de149f30f25585f4177`.
- Parquet SHA-256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`, chỉ dùng ở bước evaluation sau generation.
- Kiểm 11 + 14 = 25 unique IDs, không trùng stage. Expected A3 slots = **25**, không phải 75 hoặc 150.
- Manifest W10 chứa **50 task**; chỉ 25 task đầu đúng bằng stage1 + stage2 theo thứ tự (đã đối chiếu khi lập plan). Mọi export/qualification phải giữ prefix 25 đã kiểm; không export/chạy cả 50 vì bỏ quên `--limit 25`.
- Hai task không có repro đáng tin cậy đã được quyết định trước run: requests-1724 và pylint-4970; giữ lý do ở `configs/m3/w10_dev/tasks/EXCLUDED.md` và trong ledger. Không tạo repro giả hoặc tự đổi lịch sử thành NOT_APPLICABLE.
- Giữ exclusions D18/D25 hiện có, gồm stage2 astropy-13453, astropy-13977, django-11087 OVER_CAP. Không tự mở lại chỉ vì preflight A3 mới vừa cap. Nếu cần đổi eligibility, phải có quyết định trước campaign và sửa plan/binding so sánh.
- W10 lịch sử có 20 RUNNABLE/25; **không mặc định A3 hôm nay cũng có đúng 20** trước inventory/preflight. Thiếu file của task vốn runnable là dependency/input error phải xử lý; không biến thành exclusion thuận tiện.
- Báo 25 slots = terminal + interrupted/pending + not_run; trong terminal tách source exclusion, over-cap, model failure, timeout, verifier outcome và infra error. Không yêu cầu cả 25 đều gọi model hoặc đều PASS.

## 4. Thiết kế vận hành và file map

Ưu tiên dùng nguyên runner hiện có; không thêm runner hay sửa engine trong campaign. Nếu phát hiện bug mới cần sửa, dừng, nêu reproducer và xin giao task sửa riêng; sau sửa phải freeze/preflight lại.

| File/module có sẵn | Vai trò trong plan |
|---|---|
| `scripts/run_repair_experiment.py` | preflight, run, status, aggregate; dùng cùng output root cho preflight/run |
| `scripts/derive_experiment_config.py` | Sinh config mới từ stage template, lấy đúng variant W10/A3, recompute bundle pins |
| `scripts/export_w9_pilot_bundles.py` | Export hai arm trên manifest được approved; hỗ trợ W10 qua `--approved-manifest` |
| `src/vgar/evaluation/repair/{manifest,fairness,runner,launch,preflight,aggregate}.py` | Admission/planning, fairness, ledger, engine, token audit, tổng hợp |
| `src/vgar/repair/{admission,docker_executor,verification}.py` | Lease riêng, Docker source attestation, baseline và post checks |
| `scripts/grade_repair_candidates.py` | Official harness cho candidate hợp lệ, preflight trước execute |
| `scripts/analyze_repair_timeouts.py` | D15 trên raw W10/A3, không nạp model |

Output đề xuất: `results/m2/w1112/a3-25/<run_id>/`. Đây là lựa chọn tổ chức artifact của plan, không đổi quyền sở hữu module M3. Bản chạy Linux phải có working copy chứa **đúng dirty code hiện tại và T1 sau khi hoàn thành**, không chỉ clone HEAD cũ từ GitHub. Giữ CRLF/LF đúng bytes của code đã freeze, kiểm nội dung copy; không chỉnh hàng loạt line endings trong repo Windows.

```text
<run_id>/
  readiness/       machine, assets, 25-row input inventory, image/disk plan
  inputs/          stage1/2 A3 configs, A2 comparison-only configs, local repair config
  freeze/          full SHA-256 inventory, dirty diff/untracked inventory, pins
  tools/           one-off readiness/smoke helpers + argv (nếu cần)
  smoke/           Docker baseline/report/transport/cleanup evidence, không model
  runs/            <experiment_id>/{preflight.json,experiment.json,attempts/,engine/}
  logs/            stdout/stderr + process exit codes + timestamps/resources
  grades/          harness records, nếu chạy grading
  aggregate-1/     aggregate.json/.md
  aggregate-2/     lần sinh đối chiếu byte-identical
  d15/             input selection/rows/summary/report
  handoff/         25-slot audit, review limits, artifact hashes, export index
```

**Review focus:** đường dẫn model của máy khác; daemon/profile đổi identity; preflight exit0 có row lỗi; resume dùng sai code/binding; so A2 lịch sử với A3 có bundle/verifier khác. Các chặng dưới có gate riêng cho năm trường hợp này.

## 5. Chặng 1 — Readiness chỉ đọc (có thể làm ngay)

**Lệnh giao việc:** “Thực hiện A3 — chặng 1 readiness”. Không launch campaign.

- [ ] Chụp git status/diff, hash file dirty/untracked, fixture DB và báo cáo đang có. Lưu mốc phục hồi, không ghi đè PROGRESS/status cũ.
- [ ] Kiểm Docker/WSL hiện trạng, distro/version, mount/data/model locations. Nếu đang tắt, ghi `WAITING_ENVIRONMENT`; việc bật môi trường thuộc chặng 2, không tự sửa dịch vụ.
- [ ] Nếu daemon đang chạy: đọc version, context/host, daemon ID và image inventory/digests. Dùng timeout hữu hạn từng lệnh, không kéo image ở chặng này.
- [ ] Inventory đúng 25 rows: base commit/source tree/blob hashes, profile+attestation+image/runtime, graph/bundle sidecars+hashes, issue-only overlay/repro/selector/scope, excluded reason. Không quét toàn máy để tìm tài sản; chỉ kiểm locations có căn cứ từ config/distro/home/cache hiện có.
- [ ] Đối chiếu model/tokenizer/interpreter với pins; không import target repo, không mở model weights để infer. Thiếu model/venv/CUDA phải có danh sách cần chuẩn bị và dung lượng.
- [ ] Đo host và WSL RAM, GPU, filesystem/data/Docker backing volume. RAM trống host khi VM tắt không là RAM trống khi cả Docker/model chạy.
- [ ] Sinh `readiness.json`, `assets.csv`, `missing_inputs.md`, `commands.json`; từng item READY/MISSING/UNVERIFIED/EXCLUDED, tách inventory khỏi campaign result. Kết luận READY_FOR_PREPARATION hoặc WAITING_*.

Ngưỡng vận hành đề xuất của plan, **không phải số đo từ spec**: trước smoke RAM khả dụng host ≥4 GiB, C còn ≥10 GiB, volume data/Docker còn ≥30 GiB; sau khi biết images còn thiếu phải cộng nhu cầu tải/unpack riêng. Trước full batch dùng dung lượng smoke đo được để ước lượng phần còn lại +20% +10 GiB dự phòng; thiếu thì WAITING_RESOURCE, không tự dọn. RAM/GPU cũng phải qua smoke thật, không bảo đảm chỉ từ ngưỡng số.

**Dừng:** báo inventory và danh sách cần chuẩn bị; không tự sang chặng 2.

## 6. Chặng 2 — Chuẩn bị assets/local config riêng

**Điều kiện:** người dùng giao chặng 2 sau khi đã thấy missing inventory của chặng 1. Không đổi machine settings hoặc xóa dữ liệu.

- [ ] Dùng distro `VGAR-Harness-W9` nếu Linux/Python/CUDA/Docker integration phù hợp; không mặc định có Ubuntu hay `~/vgar`. Chỉ bật Docker/distro như phạm vi chặng đã được giao. Nếu lỗi startup, dừng ở báo cáo nguyên nhân, không reset/reinstall.
- [ ] Tạo working copy Linux mới có ownership riêng; chép cả tracked changes và untracked implementation cần thiết. Không hardlink source, không thay checkout Windows, không dùng HEAD để bỏ mất T2/T4/T5/T6/T7. Ghi hash chuyển giao hai phía.
- [ ] Tái sử dụng W10 assets hiện có nếu hash khớp. Chuẩn bị checkout pinned base thiếu ở data root riêng; không apply gold lên checkout đó. Chỉ fetch/pull/download đúng danh sách đã thống nhất sau inventory; không lấy tag latest.
- [ ] Profile còn bind daemon/image khác: không sửa ID/hash bằng tay. Cần qualify lại trên daemon local bằng implementation hiện có, lưu profile/attestation mới ở data root riêng và ghi relocation/environment difference. Không nới admission để chạy cho được.
- [ ] Qualification dùng `scripts/prepare_task_env.py`, approved manifest W10, `--limit 25`, runtime copy từ `configs/m1/w10_task_env_profile.json`. Runtime hiện còn `sdk_python=/home/nam/spike-swebench/bin/python`; phải relocate sang **SDK venv Linux đủ dependencies đã kiểm**, giữ image digest pins/timeout 300 và lưu diff. Chạy preflight trước `--execute`; chỉ thêm `--prepare-images` cho digests thiếu đã được thống nhất. Không dùng default W9 manifest/runtime hoặc diễn giải sentinel qualification thành repro test đã FAIL đúng issue.
- [ ] Tạo bản local của repair config trong `inputs/`; chỉ thay snapshot/interpreter/tokenizer paths cho đúng máy. Giữ model bytes/revision, prompt và toàn bộ policy values ở mục 1; tokenizer manifest relative path phải được resolve lại từ vị trí config mới.
- [ ] Bundle: nếu đúng current source/resolver/ranking và consumer PASS thì reuse. Nếu chưa có, export mới bằng manifest W10 đã pin, **`--limit 25` sau khi assert prefix bằng union hai stage**, static resolver, B1500, issue-only, một worker; lưu hai arm vì derive_config hiện đọc cả hai. Không tune ranking hoặc đọc gold để chọn context.
- [ ] Ranking pin hiện hành `sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a`; kiểm resolver v4 và source inventory riêng, không chỉ graph_version. Re-export không mặc định bằng W10 cũ: so từng bundle hash và báo khác biệt.
- [ ] Sinh 2 config A3 stage1/2 và 2 config A2 comparison-only trên cùng inputs; A2 configs chỉ để fairness, **không chạy thêm A2 trong plan này**. Thay `repair_config` sang local copy, validate lại bằng `load_experiment()` sau thay; tất cả relative paths phải resolve đúng từ file mới.
- [ ] `derive_config()` copy exclusions từ template: kiểm keys vẫn thuộc task_ids. Full stage giữ nguyên 11/14; nếu helper smoke dùng subset phải lọc cả maps theo subset và giữ exclusions tương ứng, không tạo invalid config.

Lệnh export/derive mẫu trong WSL, chỉ dùng **sau** inventory đã gán đúng các biến local; đây là template, chưa chạy trong phiên lập plan:

```bash
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 VGAR_GRAPH_BACKEND=demo
export PYTHONPATH="$VGAR_REPO/src"
cd "$VGAR_REPO"
# PY: interpreter Linux; DATA: data root; RUN: output mới; BUNDLE_REL: đường @data/... của export đã kiểm.
# LOCAL_REPAIR phải có đúng semantic policy/model ở mục 1; không dùng nguyên đường /mnt/c/Users/nlhnh.
"$PY" -B scripts/export_w9_pilot_bundles.py \
  --manifest configs/m1/w10_dev_manifest.json \
  --approved-manifest configs/m1/w10_dev_manifest.json \
  --profile configs/m1/w9_bundle_profile_repair.json \
  --tokenizer-manifest "$M1_TOKENIZER" \
  --sources-root "$DATA/repositories" --output-root "$BUNDLE_OUTPUT" --limit 25

for stage in 1 2; do
  TASKS=$("$PY" -B -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["source"]["task_ids"]))' "configs/m3/w10_dev_stage${stage}.json")
  "$PY" -B scripts/derive_experiment_config.py \
    --template "configs/m3/w10_dev_stage${stage}.json" --data-root "$DATA" \
    --tasks "$TASKS" --bundle-dir "$BUNDLE_REL" --variants A3:graph \
    --out "$RUN/inputs/a3-stage${stage}.json"
done
```

Script derive hiện load config template trước khi có cơ hội sửa repair_config local. Nếu đường template chưa tồn tại trên máy: helper trong `tools/` phải tạo template trung gian với **mọi path đã resolve đúng**, chỉ relocate repair_config/model assets; dùng template đó cho derive, không sửa configs tracked. Tương tự tạo A2 bằng `--variants A2:graph`. Lưu argv thực, template trung gian và diff JSON để chứng minh chỉ thay paths/pins đã có lý do.

**Dừng:** bàn giao local input package và diff/pins; chưa model, chưa T1.

## 7. Chặng 3 — Smoke Docker không model (trước T1)

**Mục tiêu:** kiểm transport, report, baseline, static tools, protected source và cleanup. Không kiểm chất lượng patch hoặc nghiệm thu A3.

- [ ] Chọn trước **django__django-10914** và **pallets__flask-5014** để có native-runner/pytest coverage; không chọn lại sau khi xem outcome. Astropy-13033 giữ nguyên trong population và xử lý theo T3, không dùng làm smoke ban đầu để né việc điều tra đã biết.
- [ ] Dùng helper one-off tại `tools/smoke_a3_environment.py`, không thêm production API: `load_experiment` → `plan_task` → `admit_task` → `prepare_admitted_workspace` → `DockerExecutor` → `capture_baseline(..., variant=A3 bound graph, artifact_root=...)`. Giữ deadline và gọi lease cleanup trong finally; ghi lỗi cleanup/integrity thay vì che bằng PASS.
- [ ] Helper không gọi generator/build_generation, không apply patch, không cần gold. Nếu phiên bản runner dùng native Django, đi đúng adapter đã có; không ép pytest cho Django.
- [ ] PASS smoke khi source/overlay/runtime attestation đúng; required issue test FAIL trên baseline vì lỗi cần sửa, regression outcomes đầy đủ; baseline qualification PASS; static reports COMPLETE hoặc UNAVAILABLE đúng contract và reason (không báo tất cả tool chạy thành công nếu UNAVAILABLE).
- [ ] Kiểm T5 report metadata/copy/hash thật; nếu gặp collection error phải có JSON/JUnit/exit matching, không đoán từ stdout. Thiếu report vẫn ERROR. Smoke baseline collection FAIL không qualified.
- [ ] Kiểm T6 receipt, không còn host snapshot.tar của operation đã hoàn tất, giữ report được consumer đọc; không xóa artifact cũ. Không còn owned container/lease, source hashes trước/sau không đổi. Không áp yêu cầu source tar đã xóa lên fake-container copies/historical evidence.
- [ ] Ghi thời gian, disk growth, RAM/WSL swap, command latency để điều chỉnh dự báo tài nguyên. Nếu Docker treo/RAM thiếu, dừng WAITING_RESOURCE/ENVIRONMENT; không tự tăng timeout hay thay policy.
- [ ] Lưu `smoke.json`, command logs, baseline reports, transport receipts và preservation checks. Baseline-only smoke không phải repair PASS; không tạo fake campaign terminal ACCEPT hoặc ghi vào 25-slot A3 ledger.

**Dừng:** báo smoke gate. Đây không thay H7 dry-run toàn chuỗi của M1 và không tự khởi chạy full chain đó.

## 8. Chặng 4 — Sau T1: freeze, regression và preflight launch gate

**Dependency bắt buộc:** T1 được giao/triển khai riêng, có regression và evidence hỗ trợ scope API. T3 phải có kết luận hoặc giới hạn được nhóm chấp nhận rõ trước launch; không âm thầm bỏ astropy-13033. T2 10 gold chưa đủ raw vẫn ghi chưa xác minh, không làm giả kết luận.

- [ ] Chốt code revision + full hashes của dirty/untracked implementation, policies, model/tokenizer, test overlays, graph/bundles, resolver/ranking, source inventories. Copy T1 sang Linux, kiểm byte hashes; không update code giữa batch. HEAD riêng không đủ để freeze repo dirty.
- [ ] Chạy gate liên quan trên code Linux sẽ chạy thật: A3 integration/verification, policy/fairness, manifest/preflight/derive/runner/sampler, Docker admission/report, collection failure và static-delta regression; kiểm T1/T3 gate theo task tương ứng. Không chạy lại toàn suite dài chỉ để cộng số PASS.
- [ ] Gọi `check_arm_fairness()` với **cả A2 và A3 configs của cả hai stage**. So thêm task-level source/profile/graph/bundle/selector hashes giữa A2/A3; fairness_identity hiện không tự chứng minh mọi task input giống nhau.
- [ ] Đối chiếu A2 lịch sử: cùng task IDs chưa đủ; nếu khác code verifier, bundle/resolver, model, prompt, eligibility hoặc timeout, báo version mismatch. Không gộp thành paired controlled comparison với A2 W10. Chạy A2 contemporary cần giao việc riêng, không tự mở thêm 25 GPU run.
- [ ] Preflight từng config A3 bằng tokenizer thật; kiểm JSON có đúng 11/14 rows, IDs/arm/policy/pins và context hashes đúng freeze. Thay đổi config/code/input sau preflight buộc freeze/preflight lại.
- [ ] **Không dùng CLI exit0 làm launch gate:** preflight() vẫn có thể trả ERROR/OVER_CAP, require_preflight() chỉ kiểm file tồn tại. Helper/audit phải từ chối ERROR chưa giải quyết; expected exclusions giữ row/reason; task mới OVER_CAP phải có quyết định eligibility trước launch, không cắt context/tăng cap tự động.
- [ ] Chỉ allowlist các row không launch đã có quyết định và evidence từ trước (hai task thiếu repro và ba task D18/D25); giữ **raw reason thực của runner**, kể cả TASK_INPUT_MISSING nếu đó là cách input lịch sử biểu diễn thiếu repro. Không đổi raw ERROR thành NOT_APPLICABLE, không allowlist một TASK_INPUT_MISSING mới của task khác. Lưu allowlist kèm reason/evidence trước launch và kiểm mọi row còn lại FITS.
- [ ] Preflight dùng failing selectors thay baseline failed cases; prompt thực có thể khác. Kiểm prompt thực lúc run, giữ runtime cap; PROMPT_OVER_CAP thực phải báo, không bypass.

Lệnh gate mẫu (temp mới ngắn ngoài repo, lưu exit code riêng):

```bash
"$PY" -B -m pytest \
  tests/m2/w910/test_policy.py tests/m2/w910/test_arm_fairness.py \
  tests/m2/w1112/test_a3_verification.py tests/m2/w78/test_a3_integration.py \
  tests/m2/w1112/test_collection_failure.py tests/m2/w910/test_docker_admission.py \
  tests/m2/w910/test_static_diagnostics.py tests/m2/w910/test_baseline_delta.py \
  tests/m3/test_manifest.py tests/m3/test_preflight.py tests/m3/test_derive_config.py \
  tests/m3/test_runner.py tests/m3/test_runner_code_state.py tests/m3/test_gpu.py \
  -q -p no:cacheprovider --basetemp "$QA_TMP/tests" --junitxml "$RUN/logs/launch-gate.xml"

for stage in 1 2; do
  "$PY" -B scripts/run_repair_experiment.py preflight \
    --config "$RUN/inputs/a3-stage${stage}.json" --data-root "$DATA" --output-root "$RUN/runs"
done
```

Gate smoke dùng Docker thật tách riêng khỏi unit fixture ở trên. SKIP/UNAVAILABLE có lý do được giữ, không gọi full check coverage nếu chưa đo.

**Dừng:** báo LAUNCH_READY hoặc BLOCKED, kèm population/eligibility và fingerprint cuối; chờ người dùng giao batch.

## 9. Chặng 5 — Batch thật A3, 25 slots

**Điều kiện:** chặng 4 LAUNCH_READY và người dùng giao chạy batch. Không chạy thêm A0/A1/A2 hoặc mutant pool.

- [ ] Gắn nguồn điện, tắt sleep theo thao tác người dùng nếu cần; không tự sửa settings. Đảm bảo không workload nặng khác, đủ disk dự báo và image đã local; không pull trong khi batch đang đo.
- [ ] Chạy stage1 rồi stage2, một worker. Lưu stdout/stderr và process exit code; khi pipe qua tee dùng `set -o pipefail`/PIPESTATUS, không lấy exit của tee làm exit runner.
- [ ] Theo dõi resource/cleanup giữa stage; dừng nếu integrity/daemon/disk/resource không bảo đảm. Không tự retry patch fail hoặc generation timeout.
- [ ] Expected **25 terminal ledger entries** cuối (kể cả expected exclusions). Số engine run/model calls có thể thấp hơn 25; ghi rõ lý do từng row. Mỗi attempt đi tới generation chỉ gọi model một lần.

```bash
set -o pipefail
"$PY" -B scripts/run_repair_experiment.py run \
  --config "$RUN/inputs/a3-stage1.json" --data-root "$DATA" --output-root "$RUN/runs" \
  2>&1 | tee "$RUN/logs/a3-stage1.log"
# Kiểm exit, ledger, resource và freeze hashes rồi mới chạy stage2.
"$PY" -B scripts/run_repair_experiment.py run \
  --config "$RUN/inputs/a3-stage2.json" --data-root "$DATA" --output-root "$RUN/runs" \
  2>&1 | tee "$RUN/logs/a3-stage2.log"
```

**Gián đoạn/resume:** runner exit130/INTERRUPTED phải giữ record. Chạy lại cùng config/output/code đã freeze để resume; runner bỏ các pair đã có TERMINAL. Nếu code/input đã đổi thì không nối batch cũ, tạo campaign mới và báo mixed binding. Terminal ERROR không tự rerun; cần người dùng duyệt từng rerun và lý do, dùng `--rerun TASK:A3 --reason ...`, giữ supersession audit. Không chọn attempt đẹp nhất.

Runner exit0 chỉ nghĩa vòng chạy kết thúc, **không** chứng minh mọi patch PASS hoặc hạ tầng không lỗi. Kết luận dựa ledger+engine+sidecars+cleanup, không chỉ console.

**Dừng:** báo 25-slot accounting, failures/timeouts/exclusions và artifact root, không tự grading.

## 10. Chặng 6 — Consumer audit, grading và tổng hợp

- [ ] Đọc lại bytes thực của attempts, canonical run records, evidence_bundle, API/structural details và Docker/static/test reports; validate IDs, policy/source/runtime/config hashes, refs, attestation, cleanup, baseline/post và finalization.
- [ ] Với task dừng trước verification, check NOT_RUN là thực tế phải giữ; không dựng sidecar hoặc ép đủ sáu checks. Với task đã verify, chỉ ACCEPT khi tất cả required checks đạt theo engine; NOT_RUN không thành PASS.
- [ ] Latest terminal/supersession/pending được audit. Aggregate hiện chọn latest terminal và có thể nhìn terminal cũ nếu rerun mới pending; nếu còn pending, không dùng bảng như kết quả cuối và công bố selection audit riêng.
- [ ] Harness: chạy `grade_repair_candidates.py` mặc định preflight trước, kiểm candidates/eligibility rồi mới `--execute` nếu chặng này được giao. Giữ F2P/P2P và resolved tách khỏi verifier ACCEPT; candidate không tồn tại/không hợp lệ không bịa kết quả grading. Không lấy gold làm context/generation input.
- [ ] Aggregate từ hai stage A3, dùng Parquet đã pin chỉ ở bước evaluation. Đọc variants động; markdown hiện còn heading literal A0-A2, vì vậy báo giới hạn heading và kiểm JSON có A3, **không tự sửa aggregate production** trong plan vận hành.
- [ ] Chạy aggregate hai lần vào hai thư mục mới, so bytes. Báo A3 N=25, funnel/cost/coverage, API reasons, structural subchecks, timeout/truncation và errors. Không gọi false accept/reject counts của funnel là FAR/FRR mutant pool.
- [ ] Không có harness grades thì F8/resolved chưa nghiệm thu; ghi NOT_GRADED, không đổi thành UNRESOLVED/0 resolved đã đo.

Lệnh mẫu (EXP1/EXP2 lấy từ load_experiment trên configs đã freeze; GRADES là file thật do harness trả):

```bash
"$PY" -B scripts/grade_repair_candidates.py \
  --experiment-dir "$RUN/runs/$EXP1" --experiment-dir "$RUN/runs/$EXP2" \
  --manifest configs/m1/w10_dev_manifest.json --approved-manifest configs/m1/w10_dev_manifest.json \
  --dataset-parquet "$PARQUET" --output-root "$RUN/grades/preflight"
# Sau khi đọc preflight: lặp lại với output mới grades/execute và --execute.

"$PY" -B scripts/run_repair_experiment.py aggregate \
  --config "$RUN/inputs/a3-stage1.json" --config "$RUN/inputs/a3-stage2.json" \
  --data-root "$DATA" --output-root "$RUN/runs" --grades "$GRADES" \
  --parquet "$PARQUET" --out "$RUN/aggregate-1"
# Lặp đúng lệnh aggregate, chỉ đổi --out thành aggregate-2, rồi so SHA-256 từng file.
```

**Dừng:** báo audit/grading/funnel, không tự chạy D15 hoặc đóng mutant campaign.

## 11. Chặng 7 — D15 thật, export và nghiệm thu

- [ ] Nhận raw W10 stage1/2 có experiment.json, attempts và linked engine records. Nếu chưa có, chỉ phân tích phần A3 đã có và ghi PARTIAL; không nhận summary thay raw.
- [ ] D15 nhận hai W10 experiment dirs và hai A3 experiment dirs. Tách mixed binding, giữ timeout là censored, unknown khác zero; không suy generation timeout chỉ từ duration.
- [ ] Báo generation/run/command timeout riêng, input/output tokens, completed-time stats/correlation, VRAM peak và samples_failed. Đề xuất timeout chỉ từ dữ liệu đủ điều kiện, không sửa 900/1800 tự động.
- [ ] Export có relative layout, giữ sidecars thật, inventories và checksum trước/sau. Kiểm Windows consumer đọc export mà không cần truy cập đường tuyệt đối WSL cũ; input hashes không đổi.
- [ ] Cập nhật `docs/status/m2.md`, `PROGRESS.md`, checkpoint và báo cáo A3; giữ lịch sử. M3 nhận record/aggregate cho tài liệu do M3 sở hữu; không ký review hoặc sửa board thay nhóm.

```bash
"$PY" -B scripts/analyze_repair_timeouts.py \
  --w10-experiment "$W10_EXP1" --w10-experiment "$W10_EXP2" \
  --w12-experiment "$RUN/runs/$EXP1" --w12-experiment "$RUN/runs/$EXP2" \
  --output-root "$RUN/d15"
```

**Tiêu chí kết thúc:**

1. Đúng population và frozen protocol, 25 slots có record cuối hoặc exclusion được giải thích; không còn pending/NOT_RUN ngoài quyết định đã công bố.
2. Mọi included runnable task được attempt thật với model/Docker, không giả bằng fixture; lỗi/timeout vẫn báo nguyên trạng, không đòi 25 ACCEPT.
3. Không integrity/cleanup failure chưa xử lý, artifact references/hashes/source immutability đạt; coverage các checks được trình bày đúng.
4. Có bảng A3 và evidence thật; nếu grading chưa thực hiện thì nêu rõ giới hạn resolved. So A2 chỉ trong binding cho phép, mixed code/input không thành kết luận nhân quả.
5. D15 và đề xuất timeout cần dữ liệu/review riêng; thiếu W10 raw không tự biến thành DONE D15. M2-W12-2 cũng không tự DONE vì đã có A3.
6. Review khác vai trò/CI/merge và quyết định nhóm được ghi đúng trạng thái, không tạo chữ ký/tag.

## 12. Chi phí, rủi ro và điểm khởi đầu

- 25 × 1800 s = **12,5 giờ budget engine danh nghĩa** nếu cả 25 đều launch; 20 × 1800 = 10 giờ nếu eligibility vẫn như W10. Đây không là upper bound wall-clock toàn campaign: preparation, runner/admission/cleanup, grading và lần được duyệt chạy lại còn ở ngoài. Không hứa hoàn tất trong một đêm trước smoke.
- GPU 6 GB/fp16 có thể offload RAM, chậm và gần generation timeout. Batch worker khác agent thường trực, nhưng phải đo trên máy hiện tại. Không tự quantize/tăng RAM VM để cứu run.
- Disk nguy cơ cao nếu phải tải thêm nhiều images hoặc còn historical archives; T6 chỉ giảm transport của operation mới. Không bảo đảm 61,7 GiB hiện tại đủ trước inventory.
- API vẫn có thể NOT_RUN sau T1 ở trường hợp thực sự không hỗ trợ; đó là limitation phải báo, không nới required checks. Thiếu structural YAML chỉ cycle áp dụng, layer/forbidden NOT_RUN riêng như quyết định đã duyệt.
- Mỗi chặng có quyền dừng độc lập. **Bước tiếp theo có thể giao ngay: chặng 1 readiness.** Plan này không là lệnh launch hoặc quyền tự chuyển qua bảy chặng.

## Reference — chỉ dùng nguồn repo/tài liệu dự án

- `D:\Project\CAPSTONES\New_task\VGAR_W9_W16_Deliverables.md`, M2-W12-1 và cổng W12.
- [Spec kỹ thuật W11–W12](../specs/2026-10-31-w11-w12-design.md), §M2-W12-1 và Q3/Q4.
- [Phân công W11–W12](../specs/2026-10-31-w11-w12-parallel-split-design.md), C3/H3/H4 và batch 25 task.
- [Policy/fairness A3 đã triển khai](../../m2_w12_1_a3.md).
- [Trạng thái M3 và số W10 lịch sử](../../status/m3.md), [đề xuất ĐX chưa tự áp dụng](../../status/m3_a0_a3_plan_2026-11-04.md).
- [Ranking freeze](../../m1_retrieval_method.md), [runbook H7 riêng](../../m1_w12_dry_run_runbook.md).
- [Checkpoint T2](../../checkpoints/2026-11-06-t2-mypy-delta-audit.md), cùng checkpoints T4/T5/T6/T7 ngày 06/11.
- Source of truth cho lệnh/API: `scripts/{derive_experiment_config,run_repair_experiment,grade_repair_candidates,analyze_repair_timeouts}.py`, `src/vgar/evaluation/repair/`, `src/vgar/repair/{admission,docker_executor,verification}.py`.

Không sử dụng paper hoặc khẳng định ngoại vi cần xác minh web trong plan này. Mọi lệnh trong tài liệu là **lệnh dự kiến**, không phải log đã chạy campaign.
