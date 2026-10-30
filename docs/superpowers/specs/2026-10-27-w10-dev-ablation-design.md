# Week 10: ablation A0–A2 trên dev, hai nấc 10 → 30 task (M1, M2, M3)

Ngày: 27/10/2026 · Người làm: M3 (`GauKho`) làm toàn bộ deliverable W10 của M1, M2, M3 · Nguồn: `VGAR_W9_W16_Deliverables (1).md` v2, mục Tuần 10
Trạng thái: bản thiết kế, chờ duyệt. Chưa viết code.

## 1. Bối cảnh và lý do

W9 đã có đủ đường chạy `bundle → generate → apply → test → verify → run record` cho 5 task pilot (experiment `55ee3300aca339e8`, 15/15 record). Kết quả pilot: A0/A1 resolve 0/6. A2 dừng ở baseline vì image thiếu mypy/Ruff. Lỗi này đã sửa ở D12 (nhánh `m3/w10-a2-static-tools`): baseline A2 qualify 3/3 task, nhưng chưa có run nào có model sinh patch.

Thử nghiệm ngày 27/10 (dùng xong bỏ) chạy lại 6 diff pilot với bước chuẩn hóa offline. Lỗi chia đều thành ba nhóm:

| Nhóm | Run | Chuẩn hóa có cứu không |
|---|---|---|
| Sai định dạng (header sai số dòng, thiếu context cuối hunk) | Matplotlib A0, Pylint A1 | Có, cả hai apply được. Nhưng Matplotlib không sửa issue, Pylint gây `NameError` |
| No-op (chép lại code không đổi) | Matplotlib A1, Xarray A1 | Không |
| Bịa context (hàm hoặc dòng không tồn tại) | Xarray A0, Pylint A0 | Không, và không được cứu |

Kết luận: điểm nghẽn là năng lực của Qwen3-4B base cùng chất lượng định vị, không phải compute. Bảng A0–A2 chỉ có cột resolve sẽ gần như toàn 0 và không phân biệt được các arm. W10 vì vậy báo thêm một **phễu chẩn đoán**. Trong đó chỉ số **định vị** (sửa đúng file, đúng hàm) là nơi retrieval BM25 (A0) và graph (A1) có thể khác nhau, kể cả khi resolve bằng 0.

## 2. Mục tiêu, ngoài phạm vi, điều không được xảy ra

**Mục tiêu (đúng cổng W10)**
- Bảng A0–A2 trên dev do script sinh ra từ record đã lưu, cùng population, cùng config, có kiểm tự động việc config các arm tương đương.
- Mẫu số đầy đủ: mọi task trong population đều có record cho cả 3 arm, kể cả task bị loại hoặc lỗi.
- Chạy hai nấc: **nấc 1 có 10 task**, chỉ lên **nấc 2 (tổng 30 task)** khi nấc 1 đạt tiêu chí ổn định ở §7.

**Ngoài phạm vi W10**
- Đổi model, fine-tune V11, nhiều lần thử mỗi task, đổi định dạng output (search/replace). Ghi thành quyết định cho W11 dựa trên kết quả phễu (§9).
- Kiểm định thống kê (bootstrap, McNemar): để W14 (M3-W14-1). W10 chỉ báo số đếm và tỷ lệ.
- Held-out split. `dataset.py` chỉ mở held-out sau protocol freeze ở W12.
- A3 và impact feedback trong vòng lặp. M1-W10-1/2 và M3-W10-3/4 làm nếu còn thời gian, nếu không thì chuyển sang W11 (§8). Chúng phục vụ A3 ở W12, không nằm trong bảng W10.

**Điều không được xảy ra**
- Gold patch, `test_patch` hoặc FAIL_TO_PASS của SWE-bench lọt vào prompt, bundle, test tái hiện hay bất kỳ input nào của generator. Gold patch chỉ được đọc trong `aggregate.py` và harness, sau khi run đã kết thúc.
- Chọn hoặc đổi task sau khi đã thấy kết quả. 30 task của cả hai nấc được khóa trong một manifest trước khi chạy nấc 1.
- Chạy lại một run đã có kết cục cuối vì kết quả không đẹp. Chỉ chạy lại khi có lỗi hạ tầng, và phải có `rerun_reason`.
- Bước chuẩn hóa "cứu" một hunk bịa: nếu khối dòng cũ không tìm thấy đúng một lần thì FAIL.
- Các arm khác config nhau mà runner vẫn chạy.
- Bỏ task lỗi khỏi mẫu số, hoặc báo tỷ lệ chỉ trên các task chạy được mà không kèm mẫu số đầy đủ.
- Gộp số chuẩn hóa với số strict: luôn báo cả `strict_apply` lẫn `normalized_apply`.

## 3. Quyết định đã chốt

**Do người dùng chốt**
- Một người (M3) làm cả M1, M2, M3 cho W10. Spec viết cho cả nhóm.
- Hai nấc: 10 task trước, ổn định thì lên 30.
- Sửa ở pipeline, không đổi model trong W10. Chuẩn hóa diff áp như nhau cho mọi arm.
- A2 dùng bộ static tool theo D12, phương án (a): giữ đủ population, mypy `UNAVAILABLE` với testbed Python < 3.7, báo subgroup.

**Do M3 quyết định (người dùng kiểm khi đọc)**
- Population lấy **cả task sửa một file lẫn nhiều file** (`min_source_files=1`), báo thêm subgroup multi-file. Lý do: `project_plan_16_weeks.md` §Metrics có sẵn chỉ số "multi-file resolved rate". Chỉ lấy multi-file thì model 4B gần như chắc chắn ra 0.
- Oracle trong vòng lặp là **test tái hiện viết tay** theo quy tắc D4 của W9 (viết từ problem statement, phải FAIL trên base, không đọc gold patch hay test_patch). "Resolved" do harness chấm riêng. Như vậy M2-W12-2 (FAR/FRR) vẫn còn oracle độc lập.
- Harness chấm **mọi candidate đã apply được**, kể cả candidate bị verifier từ chối. Chỉ số chính "resolved" chỉ tính candidate được hệ thống chấp nhận (run `PASS`) **và** được harness chấm resolved. Phần còn lại dùng cho false accept/reject.
- Diff chuẩn hóa là một trường trong variant (`patch_mode`), nên tự nằm trong `policy_hash`.

## 4. Ràng buộc từ code hiện có

- Variant: `configs/m2/variants/A{0,1,2}.json` có `arm: null`. Arm do experiment config gán: A0 = `bm25`, A1 = `graph`, A2 = `graph` (`configs/m3/w9_pilot.json`). A0 với A1 so retrieval, A1 với A2 so static check.
- Engine (`vgar.repair.pipeline.run_repair`): mỗi attempt sinh tối đa một lần, không có retry hay feedback trong A0–A2. Interface ở `docs/repair_runner_interface.md`.
- Parser strict ở `src/vgar/repair/patch.py`: `_parse_unified_diff` kiểm số dòng trong header ("Hunk counts exceeded", "Truncated or malformed hunk"). `_bind` kiểm offset ("Hunk offset does not match exact original/output position") và context ("Original hunk context/removal mismatch"). No-op bị từ chối bằng "Empty/no-op/over-limit candidate" / "No-op file change", hiện gộp vào `PATCH_PARSE_ERROR`. `apply_patch` chạy `git apply --check --index`.
- Attempt record của runner có `stage: None` với mọi FAIL của pilot. Chỉ record bị loại mới có `stage: 'plan'`. `run_record.stages.<name>.error.code` thì có sẵn.
- `run_record.stages.generation` đã có `input_tokens`, `output_tokens`, `generation_ms`, `model_load_ms`, `finish_reason`, `truncated`.
- Tập dev (đếm ngày 27/10 trên parquet đã pin): 208 task, trong đó **chỉ 28 task sửa nhiều file**. Django chiếm 96/208 (46%), tiếp theo là sympy 33, sphinx 15, matplotlib 14, scikit-learn 14, astropy 9, xarray 8, pytest 7, pylint 6, requests 4, seaborn 1, flask 1. Chỉ lấy multi-file thì không bao giờ đủ 30 task.
- Chọn task: `scripts/prepare_manifest.py` → `dataset.select_tasks(rows, count, split, min_source_files)`, round-robin theo repo, dataset `princeton-nlp/SWE-bench_Verified` rev `c104f840…`. `changed_source_files(patch)` cho biết các file của gold patch. Manifest **không** lưu gold patch.
- Môi trường: `scripts/prepare_task_env.py` sinh profile cho từng task. Pilot loại 2/5 task: Astropy lỗi collection, Django thiếu pytest. Admission chỉ nhận `COLLECTED`. Engine hiện chỉ chạy test bằng pytest.
- Spike ngày 27/10 (swebench 4.1.0, image `django-11138` và `sympy-20590`, `--network none`): **cả hai image đều không có pytest**, nhưng runner gốc của repo chạy được offline:
  - Django: tạo app mới `tests/vgar_repro/` (`__init__.py`, `tests.py` dùng `SimpleTestCase`) rồi chạy `./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 vgar_repro`. App mới được phát hiện, exit 1 khi có test fail. `parse_log_django` đọc đúng, nhưng thêm một key thừa dạng tên ngắn (`test_fail`).
  - Sympy: đặt file `sympy/vgar_repro/tests/test_repro.py` (hàm `test_*`, `assert` trần) rồi chạy `bin/test -C --verbose <file>`. Exit 1 khi có test fail. `parse_log_sympy` ghi key không thống nhất: test fail có tiền tố `path:`, test pass thì không.
  - Django và sympy chiếm 129/208 task dev (62%). Không hỗ trợ runner gốc thì phần lớn dev bị loại.
- Bundle: `scripts/export_w9_pilot_bundles.py` với `configs/m1/w9_bundle_profile_repair.json`. Bundle 8k có thể vượt `input_cap` 6000 của prompt, nên W9 đã chỉnh budget export (xem `docs/m3_w9_decisions.md`).
- Harness: `src/vgar/evaluation/harness/official.py::_campaign` cố định `GOLD_IDS` (3 task pilot) và chỉ chấm gold patch. `build_command` đã nhận `predictions_path`.
- Graph: chỉ có cạnh `CALLS`, `IMPORTS`, `CONTAINS`; chưa có `INHERITS`, `TESTS`. `diff_to_nodes(raw_diff, document, source_repo)` map diff vào node.
- Hạ tầng: runner phải chạy trong WSL2 (Docker qua `unix://`). GPU RTX 4050 6 GB. Mỗi image SWE-bench 4–7,5 GB; disk WSL còn khoảng 937 GB. Bộ static tool phải dựng trước một lần bằng `scripts/build_static_tools.sh`.
- Thời gian (pilot): khoảng 6,1 phút/run A0/A1, A2 ước khoảng 21 phút/task khi chạy đủ static. 30 run ≈ 3–5 giờ, 90 run ≈ 6,5–10,5 giờ.
- Quy trình: PR vào `main` theo CODEOWNERS. Dù một người viết code, PR đổi `src/vgar/repair/` vẫn cần `@tmthien220205-ai` duyệt, PR đổi `src/vgar/graph/` hay `harness/` cần `@17dangkhoi17` duyệt.
- Phụ thuộc chưa merge: D12 (nhánh `m3/w10-a2-static-tools`) phải merge trước khi chạy nấc 1.

## 5. Thiết kế theo vai trò

### 5.1 Population hai nấc (M1-W10-3)

- Một manifest dev khóa duy nhất: `configs/m1/w10_dev_manifest.json`, `min_source_files=1`, `count` khoảng 50 ứng viên theo thứ tự round-robin cố định, dataset rev giống W9. Loại 5 task pilot để population W10 độc lập với pilot.
- Profile môi trường cho ứng viên **theo thứ tự**. **Population nấc 1** = tiền tố ngắn nhất của danh sách có đủ 10 task `COLLECTED`. **Population nấc 2** = tiền tố ngắn nhất có đủ 30 task `COLLECTED`, luôn chứa nấc 1. Task `EXCLUDED` nằm trong tiền tố vẫn có record (`TASK_EXCLUDED`) và vẫn nằm trong mẫu số.
- Nếu 50 ứng viên chưa đủ 30 task `COLLECTED`: dừng ở số task có được và ghi rõ. Không tự thêm ứng viên ngoài manifest khóa.
- Bundle hai arm (`bm25`, `graph`) cho mọi task `COLLECTED`, cùng tokenizer và budget như W9 (`w9_bundle_profile_repair.json`). Prompt của mọi task phải nằm trong `input_cap`. Task nào vượt thì ghi lý do loại, không âm thầm cắt.
- Đầu ra: manifest, profile và hash bundle được ghi vào experiment config `configs/m3/w10_dev_stage1.json` và `w10_dev_stage2.json` (cùng định dạng `vgar-m3-experiment-v1`).

### 5.1b Adapter test runner theo repo (M2, task mới, nằm trên đường găng)

- Profile môi trường có thêm trường `test_runner ∈ {pytest, django_runtests, sympy_bin_test}`, chọn theo repo. Lệnh lấy từ `test_cmd` của swebench 4.1.0 (`MAP_REPO_VERSION_TO_SPECS`), thêm phần chọn file test tái hiện. Thiếu trường thì mặc định `pytest`, để profile và golden cũ không đổi.
- Test tái hiện viết theo kiểu của repo: Django là app `tests/vgar_repro/` với `SimpleTestCase` hoặc `TestCase`, sympy là `sympy/vgar_repro/tests/test_repro.py`. Vẫn theo quy tắc D4.
- Kết quả từng test: dùng exit code cùng parser trong `MAP_REPO_TO_PARSER`, so theo **tên hàm test** (bỏ tiền tố path hoặc class) để tránh key không thống nhất mà spike đã thấy. Test tái hiện mà parser không thấy thì xem là `FAIL`, không coi là pass.
- Admission: task Django và sympy chạy được runner gốc thì được `COLLECTED`. "Thiếu pytest" không còn là lý do loại.
- Kiểm thu: test tích hợp trên 2 image ở trên, mỗi image có 1 test pass và 1 test fail, offline. Thêm unit test parser với log đã lưu từ spike.

### 5.2 Harness chấm candidate (M1-W10-4)

- Mở rộng `official.py`: bỏ ràng buộc `GOLD_IDS`, nhận danh sách `(instance_id, model_patch)` bất kỳ từ một experiment, sinh file predictions theo định dạng SWE-bench, chạy `run_evaluation` từng task (`--max_workers 1`), lưu report ngoài Git trong `results/`.
- Đầu vào: mọi candidate có stage apply `PASS` (sau chuẩn hóa). Diff được chấm là **diff mà engine đã apply** (bản chuẩn hóa), không phải raw output.
- Đầu ra cho mỗi `task × variant`: `harness_status ∈ {RESOLVED, UNRESOLVED, ERROR, NOT_GRADED}`. Run không có candidate apply được thì ghi `NOT_GRADED`.
- Kiểm thu: chấm lại 15 run pilot W9 (tiêu chí gốc của M1-W10-4), rồi chấm nấc 1.

### 5.3 Impact (M1-W10-1, M1-W10-2): làm sau đường găng

Giữ đúng tiêu chí trong kế hoạch: đi ngược `CALLS`/`IMPORTS` có giới hạn hop, `INHERITS`/`TESTS` ghi `unsupported`, mỗi risk feature có cờ `available`. Phần truy vấn ngược và tra node theo range đặt trong `sqlite_store`. Không chặn cổng W10.

### 5.4 Chuẩn hóa diff (M2-W10-1b, task mới)

Variant có thêm trường `"patch_mode": "strict" | "normalized"`. W10 dùng `normalized` cho cả A0, A1, A2. Thiếu trường này thì mặc định `strict`, để fixture và golden cũ không đổi.

Khi `normalized`, chỉ nới các luật sau. Mọi luật khác của parser giữ nguyên: path a/b, protected path, giới hạn byte, file và dòng, cấm rename, cấm text thừa.
1. Bỏ qua số dòng và offset trong header `@@`. Thân hunk kết thúc ở `@@` kế tiếp, ở header file kế tiếp, hoặc ở cuối diff.
2. Một dòng rỗng trong thân hunk được coi là dòng context rỗng (model hay bỏ dấu cách đầu dòng).
3. Với mỗi hunk: khối cũ gồm các dòng context và `-`, khối mới gồm các dòng context và `+`. Khối cũ bằng khối mới thì bỏ hunk đó và đếm là no-op.
4. Tìm khối cũ trong file ở base, khớp chính xác, tìm từ sau vị trí kết thúc của hunk trước trong cùng file. Có 0 chỗ khớp → `CONTEXT_NOT_FOUND`. Có từ 2 chỗ trở lên → `CONTEXT_AMBIGUOUS`. Có đúng 1 chỗ → thay bằng khối mới.
5. Mọi hunk là no-op hoặc file không đổi → `NO_OP`.
6. Sinh lại unified diff chuẩn từ nội dung trước và sau, rồi cho đi qua đúng đường `_bind` và `git apply --check` hiện có.

Ghi vào stage `parse_patch` hoặc `apply`: `patch_normalization = {mode, strict_parse_ok, strict_apply_ok, hunks_total, hunks_noop_dropped, hunks_relocated, normalized_diff_sha256}`. Trong đó `strict_*` là kết quả chạy thử đường strict trên raw output, chỉ để ghi lại, không ảnh hưởng kết cục.

Kiểm thu: unit test cho từng luật, dùng 6 diff pilot làm fixture. Kết quả phải đúng như bảng ở §1: 2 apply được, 2 `NO_OP`, 2 `CONTEXT_NOT_FOUND`.

### 5.5 Mã failure có cấu trúc (M2-W10-1)

- Mọi kết cục cuối, kể cả timeout và loại task, có `failure = {stage, code, cause, evidence_ref}`, không để `null`. Runner chép `stage` và `code` vào attempt record (hiện đang là `stage: None`).
- Thêm mã mới: `NO_OP`, `CONTEXT_NOT_FOUND`, `CONTEXT_AMBIGUOUS`. `PATCH_PARSE_ERROR` chỉ còn dùng cho lỗi cú pháp thật mà chuẩn hóa không xử lý được.
- Kiểm thu: test xác nhận không còn record nào thiếu `stage` hoặc `reason`, chạy trên fixture và trên 15 record pilot.

### 5.6 Cost và timing theo task (M2-W10-2)

Runner gom từ `run_record` (không parse log) các trường `input_tokens`, `output_tokens`, `generation_ms`, `model_load_ms`, `wall_ms`, `generation_count` (= 1 trong A0–A2). Trường nào không có thì ghi `null` kèm lý do.

### 5.7 Kiểm config tương đương (M2-W10-3)

`tests/m2/w910/test_arm_fairness.py` cùng một bước kiểm trong runner trước khi chạy. Các arm trong một experiment phải trùng nhau về model id và revision, tokenizer revision, prompt template hash, `input_cap`/`output_cap`, budget bundle, timeout và `patch_mode`. Chỉ được khác `arm` và `required_checks`. Lệch thì runner từ chối, không có record nào được ghi.

### 5.8 Chạy dev (M3-W10-1)

- Test tái hiện cho mọi task `COLLECTED` của nấc đang chạy: `configs/m3/w10_dev/tasks/<id>.json` và `<id>.repro.py`, theo đúng quy trình D4 và runbook W9 (bước kiểm FAIL trên base trong image).
- Chạy tuần tự bằng `scripts/run_repair_experiment.py` trong WSL. Nấc 1 là 30 run. Nấc 2 chạy **chỉ 20 task mới** trong một experiment riêng có cùng config. Bảng 30 task là hợp của hai experiment, và kiểm config tương đương **giữa hai experiment** theo §5.7.

### 5.9 Aggregate và phễu (M3-W10-2)

`src/vgar/evaluation/repair/aggregate.py` cùng `run_repair_experiment.py --aggregate <experiment...>`. Đọc record đã lưu, report harness và gold patch (từ parquet đã pin), rồi sinh ra bảng Markdown cùng JSON. Chạy lại phải ra đúng từng byte (DoD-02).

Chỉ số được **chốt trước khi chạy**. Mẫu số luôn là N = toàn bộ task trong population, kể cả task bị loại:

| # | Bước phễu | Định nghĩa |
|---|---|---|
| F1 | Sinh xong | stage generation `PASS` |
| F2 | Apply strict | `strict_apply_ok` |
| F3 | Apply sau chuẩn hóa | stage apply `PASS` |
| F4 | Sửa đúng file | file trong candidate giao với `changed_source_files(gold)` khác rỗng |
| F5 | Sửa đúng hàm | `diff_to_nodes(candidate)` giao với `diff_to_nodes(gold)` ở mức hàm khác rỗng. Không map được thì ghi `unavailable` và đếm riêng |
| F6 | Test tái hiện pass | stage verification, phần tests, `PASS` |
| F7 | Hệ thống chấp nhận | run `PASS` (A2 có thêm static) |
| F8 | **Resolved (chỉ số chính)** | F7 và harness `RESOLVED` |
| — | Chẩn đoán verifier | harness `RESOLVED` mà bị từ chối (false reject), chấp nhận mà `UNRESOLVED` (false accept) |

Kèm theo: phân bố mã failure theo arm, cost và timing trung bình (§5.6), và các subgroup: multi-file / single-file, mypy `available` / `UNAVAILABLE`. Chỉ báo số đếm và tỷ lệ, không có p-value.

### 5.10 Methodology v1 (M3-W10-5)

`docs/paper/`: mục 5.2 và 5.4 theo engine thật (unified diff, chuẩn hóa §5.4, `git apply`, worktree, mypy/Ruff theo D12, baseline-delta). Kèm bản nháp Experimental Design có population hai nấc, phễu §5.9 và giới hạn. Viết trong lúc chờ run.

## 6. Ghi quyết định

Thêm D13 (chuẩn hóa diff, `patch_mode`), D14 (population hai nấc, `min_source_files=1`), D15 (oracle trong vòng lặp và cách chấm harness) vào `docs/m3_w9_decisions.md` hoặc một file `docs/m3_w10_decisions.md` mới (builder chọn).

## 7. Tiêu chí ổn định để lên nấc 2

Cả 4 điều sau đều phải đúng với nấc 1:
1. Mỗi task trong population nấc 1 có đủ 3 record ở trạng thái cuối.
2. Không có `ERROR` do hạ tầng (Docker, tokenizer, quyền file, worker). `FAIL` do model và `TASK_EXCLUDED` vẫn hợp lệ.
3. `--aggregate` chạy hai lần ra kết quả giống hệt nhau.
4. Harness chấm xong mọi candidate apply được (không còn `ERROR` của harness).

Không đạt: sửa hạ tầng, ghi `rerun_reason`, chạy lại các run lỗi hạ tầng của nấc 1, rồi kiểm lại. Kết quả của model **không** phải điều kiện để lên nấc 2.

## 8. Thứ tự và tiến độ

| Ngày | Đường găng | Làm xen |
|---|---|---|
| 1 | Merge D12. Manifest khóa. Adapter test runner (§5.1b). Profile, image và bundle cho ứng viên nấc 1 | Chuẩn hóa diff (§5.4) và test |
| 2 | 10 test tái hiện. §5.5, §5.7 | §5.6 |
| 3 | Chạy nấc 1 qua đêm (30 run) | Harness tổng quát hóa (§5.2), chấm pilot |
| 4 | Harness chấm nấc 1, `aggregate`, kiểm §7 | Methodology |
| 5–7 | Profile, bundle và 20 test tái hiện cho nấc 2, chạy qua đêm (60 run), aggregate 30 task | M1-W10-1/2, M3-W10-3/4 nếu còn thời gian |

Tải image (khoảng 150–250 GB cho khoảng 45 task) chạy nền từ ngày 1.

## 9. Rủi ro

- **Resolve vẫn bằng 0 trên cả 30 task.** Đây là kết quả hợp lệ. Phễu cho biết model hỏng ở bước nào. Nếu F4/F5 cao mà F8 thấp, điểm nghẽn là năng lực model, và W11 nên đánh giá model fine-tune V11. Nếu F4 thấp thì điểm nghẽn là retrieval.
- Viết 30 test tái hiện tốn thời gian. Test viết sai (PASS trên base) bị loại bằng bước kiểm FAIL trên base. Task không viết được test tái hiện đáng tin thì ghi `EXCLUDED` kèm lý do **trước khi chạy**, vẫn nằm trong mẫu số.
- Tỷ lệ loại có thể cao hơn 40% của pilot, và 50 ứng viên có thể không đủ 30 task. Khi đó báo đúng N có được.
- Review chéo: một người viết toàn bộ code, nên PR vẫn phải chờ M1/M2 duyệt theo CODEOWNERS. Nên mở PR sớm, mỗi vai trò một PR.
- `diff_to_nodes` có thể không map được một số candidate, nên F5 có thể bị `unavailable` nhiều.

## 10. Để builder quyết

- Tên file cụ thể, cấu trúc module của chuẩn hóa (trong `patch.py` hay một module riêng), định dạng file predictions.
- Số ứng viên chính xác (khoảng 50) và seed, miễn là khóa trước khi chạy.
- Cách trình bày bảng Markdown, miễn là sinh ra từ script.
- Chia PR theo vai trò và theo thứ tự đường găng.
