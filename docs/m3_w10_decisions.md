# Quyết định M3 cho W10 (ablation A0–A2 trên dev)

Lập 27/10/2026. Phạm vi: W10, dev split, hai nấc 10 → 30 task. Spec: `docs/superpowers/specs/2026-10-27-w10-dev-ablation-design.md`, plan: `docs/superpowers/plans/2026-10-27-w10-dev-ablation.md`. Tiếp nối `docs/m3_w9_decisions.md` (D1–D12).

**Trạng thái chung: M3 ĐỀ XUẤT, người dùng đã duyệt spec ngày 27/10.** Các mục đánh dấu ⚠️ là ranh giới bảo mật hoặc luật chuẩn hóa; PR tương ứng cần người duyệt theo CODEOWNERS.

| ID | Quyết định | Trạng thái |
|---|---|---|
| D13 | Chuẩn hóa diff bằng `patch_mode` trong variant | Chốt 27/10 (spec duyệt) |
| D14 | Population hai nấc, `min_source_files=1`, loại pilot, quy tắc tiền tố | Chốt 27/10 (spec duyệt) |
| D15 | Oracle là test tái hiện viết tay; harness chấm `applied.diff`; F8 = chấp nhận và resolved | Chốt 27/10 (spec duyệt) |
| D16 | Chạy test bằng runner gốc của repo (Django, sympy), không cần pytest | Chốt 27/10 (spike + người dùng duyệt) |
| D17 | Symlink file trong repo (Django `docs/_theme/*.png`) được inventory theo chuỗi đích | Chốt 27/10 (người dùng chọn phương án a) |
| D18 | Sửa D14: tiền tố đếm task RUNNABLE; qualify pytest bằng sentinel thay cho collect toàn repo | Chốt 29/10 (spike + người dùng duyệt), trước khi chạy nấc 1 |
| D19 | Prompt chỉ liệt kê path được phép có trong context (`path_listing`); quyền sửa giữ nguyên | Chốt 29/10 (người dùng chọn phương án A), trước khi chạy nấc 1 |

## D13. Chuẩn hóa diff (`patch_mode`)

- **Chọn:** variant có thêm `"patch_mode": "strict" | "normalized"`. W10 dùng `configs/m2/variants/w10/A{0,1,2}.json`, cả ba đều `normalized`. Module `src/vgar/repair/patch_normalize.py` áp đúng 6 luật ở spec §5.4: bỏ qua số dòng trong header `@@`, dòng rỗng trong thân hunk là context rỗng, bỏ hunk no-op, tìm khối cũ khớp chính xác và duy nhất (chỉ tìm sau hunk trước), sinh lại unified diff rồi cho đi qua đúng `_bind` và `git apply` của đường strict.
- **Lý do:** spike 27/10 trên 6 diff pilot cho thấy 2/6 chỉ sai định dạng. Không chuẩn hóa thì bảng A0–A2 đo khả năng viết header `@@` của model 4B, không đo retrieval.
- **Không được cứu:** khối cũ không có (`CONTEXT_NOT_FOUND`) hoặc có nhiều chỗ (`CONTEXT_AMBIGUOUS`), và mọi luật cấp file của parser strict (path a/b, path bảo vệ, giới hạn byte/file/dòng, rename).
- **Thêm so với spec (⚠️):** header của **cùng một file lặp liên tiếp** được coi là nối tiếp file đó (diff `pylint_A1` lặp `diagrams.py` 4 lần; spec §1 ghi case này apply được). Header trùng nhưng không liên tiếp vẫn bị từ chối. Dòng trống ở cuối hunk bị bỏ (chỉ làm ngắn context). Hunk không có dòng cũ nào là `CONTEXT_AMBIGUOUS`.
- **Hash:** `patch_mode = "strict"` không xuất hiện trong `model_dump`, nên `policy_hash` của A0/A1/A2 W9 và experiment id pilot `55ee3300aca339e8` không đổi (có test khóa).
- **Evidence:** stage `parse_patch` luôn ghi `patch_normalization = {mode, strict_parse_ok, strict_apply_ok, hunks_total, hunks_noop_dropped, hunks_relocated, normalized_diff_sha256}`, kể cả khi FAIL. `strict_*` là kết quả chạy thử đường strict trên raw output, chỉ để báo F2, không ảnh hưởng kết cục.
- **Kiểm:** 6 diff pilot ra đúng bảng spec §1 (2 apply được, 2 `NO_OP`, 2 `CONTEXT_NOT_FOUND`).

## D14. Population hai nấc

- **Chọn:** manifest khóa `configs/m1/w10_dev_manifest.json` (hash `sha256:11e0b7b1…`): 50 ứng viên dev, `min_source_files=1`, round-robin theo repo, bỏ 5 task pilot, có thêm trường `version` (không phải thông tin gold). Population nấc 1 là tiền tố ngắn nhất có đủ 10 task `COLLECTED`; nấc 2 là tiền tố ngắn nhất có đủ 30. Experiment nấc 2 chỉ chạy 20 task mới (`source.task_ids`), bảng 30 task là hợp của hai experiment.
- **Lý do:** dev chỉ có 28 task sửa nhiều file, không đủ 30. Báo thêm subgroup multi-file/single-file.
- **Hệ quả thực tế:** round-robin cho Django 5 và sympy 4 trên 50 (không phải 46% Django như cả tập dev). Mọi task Django trong 50 ứng viên là Django 3.0 (Python 3.6), nên D12 cho mypy `UNAVAILABLE` ở các task này.
- **Không được làm:** chọn lại task sau khi thấy kết quả; thêm ứng viên ngoài manifest khóa; bỏ task loại khỏi mẫu số.

## D15. Oracle và cách chấm

- **Chọn:** oracle trong vòng lặp là test tái hiện viết tay theo D4 (chỉ từ problem statement, phải FAIL trên base trong image). Harness SWE-bench 4.1.0 chấm **mọi** candidate đã apply, trên `applied.diff` (bản đã chuẩn hóa và đã apply), không phải raw output. Chỉ số chính F8 = run `PASS` **và** harness `RESOLVED`. Phần còn lại cho false accept/reject.
- **Ghép grade:** khóa theo `(experiment, task, variant, run_id)`; grade của attempt cũ không bao giờ gắn sang lần rerun. Harness và aggregate cùng chọn attempt `TERMINAL` mới nhất.
- **Phễu:** F1 sinh xong, F2 apply strict, F3 apply sau chuẩn hóa, F4 sửa đúng file, F5 sửa đúng hàm (graph đã pin hash, kiểm `repo_key` và `repository_revision`; không map được thì `unavailable`), F6 test tái hiện pass, F7 hệ thống chấp nhận, F8 resolved. Mẫu số luôn là toàn population, kể cả task loại, lỗi hoặc chưa chạy.
- **Task không viết được test đáng tin:** ghi trong `configs/m3/w10_dev/tasks/EXCLUDED.md` trước khi chạy (ví dụ `psf__requests-1724`: lỗi chỉ có trên Python 2.7). Task đó vẫn nằm trong mẫu số (`TASK_INPUT_MISSING`).
- **Đề xuất cần nhóm xem (⚠️):** `fallback_scope` của W10 hiện chỉ gồm test tái hiện, chưa có module test gốc của repo. Lý do: baseline đòi không có `ERROR` trong scope, và module gốc có thể lỗi môi trường. Hệ quả: F7 không bắt được regression ngoài test tái hiện; harness (F8) vẫn chạy PASS_TO_PASS chính thức.

## D16. Runner gốc của repo

- **Chọn:** lệnh test lấy từ bảng `configs/m1/swebench_410_test_cmds.json`, sinh từ `MAP_REPO_VERSION_TO_SPECS` của swebench 4.1.0, theo `(repo, version)`. Repo hoặc version không có trong bảng thì báo lỗi, không mặc định pytest. Sphinx (`tox --current-env -epy39 -v --`) được ghi là tương đương pytest. Django (`tests/runtests.py`) và sympy (`bin/test`) chạy qua `src/vgar/repair/native_runner.py` (Python ≥ 3.5, chỉ stdlib), ghi report đúng hợp đồng của `pytest_plugin`, node id dạng pytest.
- **Lý do:** image Django và sympy không có pytest. Không có runner gốc thì phần lớn dev (Django + sympy = 62%) bị loại.
- **Bố cục test tái hiện (⚠️ nới luật overlay của admission):** dấu `vgar_w9_repro_` được nằm ở bất kỳ thành phần nào của đường dẫn. Django: app `tests/vgar_w9_repro_<id>/`. Sympy: `sympy/vgar_w9_repro_<id>/test_repro.py` (`bin/test` chỉ chạy `test_*.py` nằm trong package; đã kiểm: file ở `tests/` gốc ra 0 test). Vẫn giữ: file mới, bị bảo vệ, có giới hạn, `.py`, không rỗng.
- **Profile môi trường:** pytest giữ schema v1; runner gốc dùng v2 (`test_runner`, `native_command`), qualify bằng một test sentinel do tool tự viết rồi xóa.
- **Sửa kèm:** `docker_probe.py` chấp nhận image không có pytest; đọc config bằng UTF-8, và `docker exec` chạy với `LC_ALL=C.UTF-8`. Python 3.5/3.6 dưới locale C mặc định ASCII và crash với tên file không phải ASCII của Django (Python ≥ 3.7 tự chuyển UTF-8 theo PEP 538, nên pilot W9 không gặp).
- **Kiểm 27/10, Docker thật:** qualify Django 3.0 và sympy 1.7 ra `COLLECTED`; `native_runner.py` chạy đúng trên image Django 1.11 (Python 3.5.6); collect và run qua `DockerExecutor` pass cho cả Django và sympy, `/testbed` không đổi.

## D17. Symlink trong repo

- **Chọn (⚠️ ranh giới bảo mật của workspace):** `workspace.inventory` ghi symlink tới file thành `symlink:` + sha256 của chuỗi đích, không bao giờ đi theo link; đổi đích là drift. Vẫn từ chối symlink tới thư mục, junction, symlink `*.py`, đích tuyệt đối và đích thoát ra ngoài repo. `base_inventory` nhận mode 120000 của git và đối chiếu chuỗi đích với blob. `create_workspace` tạo lại đúng symlink. `DockerExecutor` chỉ gửi file thường; symlink đã có trong `/testbed` sau khi reset về base.
- **Lý do:** checkout Django có 4 symlink `docs/_theme/*.png`; luật cũ làm mọi task Django fail admission.
- **Giới hạn:** chỉ hỗ trợ host Linux (WSL), đúng với spec §4. Trên Windows, git checkout symlink thành file thường và admission vẫn từ chối.

## D18. Sửa D14: đếm task RUNNABLE, qualify pytest bằng sentinel

- **Sửa quy tắc tiền tố (người dùng quyết 28/10):** population nấc 1 là tiền tố ngắn nhất có đủ 10 task **RUNNABLE**, không phải 10 task `COLLECTED`. RUNNABLE = qualify `COLLECTED`, có test tái hiện đã kiểm FAIL trên base, và preflight `FITS` ở cả 3 arm. Task OVER_CAP hoặc không viết được test tái hiện thì loại kèm lý do và kéo dài tiền tố, không cắt context bằng tay. Task loại vẫn nằm trong mẫu số.
- **Qualify pytest bằng sentinel (⚠️ đổi luật qualify của M1):** với runner pytest, qualify collect một file test do tool tự viết (`vgar_sentinel/test_vgar_sentinel.py`) rồi xóa, thay cho `@pytest-default` (collect toàn repo). Đây cùng cơ chế với sentinel của runner gốc ở D16. Profile vẫn là schema v1, với `scope = ['@pytest-sentinel']`. Probe vẫn đòi repo sạch và đúng base trước và sau khi chạy. Pilot W9 giữ `@pytest-default`.
- **Lý do:** qualify chặt hơn mức oracle cần. Engine chỉ chạy `fallback_scope`, tức test tái hiện (D15), nhưng qualify lại loại task vì module không liên quan không collect được. Spike 29/10 trong image, đúng base: 6/6 task từng bị loại (astropy-13033/13453 lỗi numpy, pytest-5631 thiếu hypothesis, pytest-7205, sklearn-10297/10844 treo khi collect) đều collect được test tái hiện dưới 1 s, và test FAIL đúng lý do của issue. Sentinel collect được trên cả 6 task đó và 2 task đối chứng, repo sạch sau khi chạy.
- **Giới hạn:** sentinel chỉ chứng minh pytest và conftest của repo chạy được. Việc test tái hiện có import được không do `verify_repro.py` kiểm trước khi chạy, và do baseline của engine kiểm lúc chạy (repro phải FAIL; `ERROR` thì run dừng ở `VERIFICATION_INCOMPLETE`).
- **Hệ quả:** phải qualify lại toàn bộ tiền tố với luật mới. Tiền tố nấc 1 có thể ngắn lại. Hợp lệ vì nấc 1 chưa chạy, và manifest khóa không đổi.

## D19. Prompt chỉ liệt kê path có trong context (`path_listing`)

- **Chọn:** variant có thêm `"path_listing": "all" | "context"`. W10 dùng `context` ở cả A0, A1, A2. Với `context`, mục "Allowed production paths" của prompt chỉ liệt kê các path được phép có mặt trong context của bundle, kèm câu "Other non-protected production paths are also allowed but not listed." Kiểm tra quyền (`patch.py`, `patch_normalize.py`, `DockerExecutor`) vẫn dùng toàn bộ `allowed_source_paths`.
- **Lý do:** preflight 27/10 ra OVER_CAP ở django-10914, django-10973 (khoảng 12–13k token), sympy-11618 (khoảng 10k) và pylint-4604 arm graph (6.129 > 6.000), vì prompt liệt kê mọi file production (Django khoảng 1.800 file). Bỏ các task này làm Django và sympy vắng mặt có hệ thống trong ablation.
- **Không chọn:** thu hẹp chính `allowed_source_paths` về file trong context. Context của BM25 và graph khác nhau, nên mỗi arm sẽ được sửa một tập file khác nhau, làm lệch phép so sánh.
- **Hash:** `path_listing = "all"` không xuất hiện trong `model_dump`, nên `policy_hash` của A0/A1/A2 W9 và experiment pilot không đổi (có test khóa). Fairness gate coi `path_listing` là trường chung, nên các arm lệch nhau thì runner từ chối. Preflight đo đúng prompt mà run sẽ dùng.
- **Evidence:** metadata của prompt ghi `path_listing = {mode, listed, allowed}`.

## D20. Hết hạn toàn cục của run là `RUN_TIMEOUT`

- **Chọn (người dùng quyết 29/10):** khi run dùng hết `global_timeout` (`TimeoutError('Global run deadline exhausted')`, hằng `GLOBAL_DEADLINE` trong `repair/executor.py`), `session._step` ghi `status = ERROR`, `reason = RUN_TIMEOUT` thay cho `INTERNAL_ERROR` (hoặc `WORKTREE_ERROR` nếu đang ở stage workspace). `failure.stage` vẫn là stage nơi run dừng. `TimeoutError` khác (không đúng thông điệp đó) vẫn là `INTERNAL_ERROR`.
- **Lý do:** §7.2 không cho phép `ERROR` do hạ tầng ở nấc 1. Trước đây hết hạn toàn cục và bug engine thật ra cùng mã, nên không tách được trong bảng mã failure của aggregate. `RUN_TIMEOUT` là kết cục về ngân sách thời gian, hợp lệ như `FAIL` do model.
- **`GENERATION_TIMEOUT` (người dùng quyết 29/10):** worker bị dừng vì hết `generation_timeout` (900 s) trong khi deadline toàn cục còn thì `HFGenerator.generate` trả `timed_out = True` và `record_generation` ghi `ERROR / GENERATION_TIMEOUT`, stage `generation`. Worker lỗi vì lý do khác vẫn là `INTERNAL_ERROR`. Nếu deadline toàn cục cũng đã hết thì `remaining_timeout` chạy trước, ra `RUN_TIMEOUT`.
- **Không đổi:** cờ `timed_out` của runner (`launch.classify_record`) vẫn dò theo thông điệp như cũ.
## D21. Kho image Docker là overlay2, qualify lại trên kho này

- **Bối cảnh (29/10):** người dùng xóa các image để làm lại từ đầu, và chế độ containerd của Docker Desktop được tắt. Lần qualify `w95-8cbbc39e…` chạy khi Docker dùng kho containerd, nơi `image_id` là digest của manifest. Image pull lại vào overlay2 có cùng digest đã pin nhưng `Id` khác (digest của config), nên `DockerExecutor` (so `Id` với `profile.image_id`) sẽ từ chối mọi run.
- **Chọn (người dùng quyết):** cố định kho overlay2 (containerd tắt) cho mọi qualify, run và chấm harness từ nay. Qualify lại theo từng nấc: nấc 1 dùng `--limit 11`. Profile cũ được chuyển sang `~/w10/profiles.containerd-20261029`, không xóa. Bundle export `20261028T200348Z-1f8a08c33ac9` được dùng lại vì export không phụ thuộc qualify.
- **Không đổi:** manifest, luật tiền tố và RUNNABLE (D18), test tái hiện. Chưa có run nào, nên qualify lại không phải là chọn lại task sau khi thấy kết quả.
- **Đĩa:** chỉ giữ image của nấc đang chạy. Image xóa đi có thể pull lại theo digest.
## D22. Sửa hạ tầng sau stage 1 (chạy lại 13 run lỗi hạ tầng)

Stage 1 (`9f1b2346fa028094`) có 13/30 run lỗi hạ tầng nên §7.2 không đạt. Nguyên nhân gốc lấy từ run record; người dùng duyệt cả 3 fix ngày 29/10.

- **Selector (8 run: pylint ×3, pytest ×3, django A1, sphinx A1; patch đã apply PASS):** `select_relevant_tests` gộp `task.fallback_scope` với `fallback_scope` trong hint của bundle (371–1.707 file test), rồi `DockerExecutor` từ chối vì selector nằm ngoài scope đã admit. **Sửa:** khi có Docker admission, chỉ chạy `task.fallback_scope` (đúng D15). Hint vẫn ghi trong `selection.report`. Fixture native không đổi.
- **Plugin pytest (astropy ×3, baseline):** `docker_probe` đặt `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, nên `pytest-doctestplus` của image không nạp, `--doctest-rst` trong `setup.cfg` bị coi là sai tham số (exit 4). **Sửa (người dùng chọn):** bỏ biến này cho lệnh chạy trong container, khớp với qualify và harness chính thức. Image đã pin theo digest. Đã kiểm trên container thật: trước sửa exit 4, sau sửa exit 0 và collect đúng test tái hiện.
- **Ruff (django A2, sphinx A2, `BASELINE_NOT_QUALIFIED`):** Ruff in `warning: Invalid \`# noqa\` directive on <path>:<line>: …` ra stderr vì comment kiểu cũ trong source của repo, và parser coi mọi stderr là lỗi công cụ. **Sửa:** riêng Ruff, chấp nhận đúng mẫu cảnh báo này; mọi stderr khác vẫn là `ERROR`. Stderr gốc vẫn nằm trong command record. Đã kiểm trên output thật: cả hai run chuyển từ `ERROR` sang `COMPLETE`.
- **Không phải lỗi hạ tầng (giữ nguyên):** 13 run model ra CONTEXT_NOT_FOUND, NO_OP hoặc PATCH_PARSE_ERROR; 3 run chạm `output_cap` 1536 token (VERIFICATION_INCOMPLETE ở generation); 3 run requests-1724 TASK_INPUT_MISSING.
- **Chạy lại:** chỉ 13 run lỗi hạ tầng, bằng `--rerun TASK:VARIANT --reason ...` (§7). Config experiment không đổi. Các run hợp lệ không chạy lại.- **Bổ sung 30/10 (sau lần chạy lại):** 11/13 run chạy lại ra kết cục hợp lệ. django-10914 A1/A2 ra `FINALIZATION_ERROR`: run thật là FAIL `TEST_FAILED`, nhưng `pipeline._project_bundle` chép mypy `UNAVAILABLE` (testbed Python 3.6, D12) vào `CheckResult`, mà contract công khai chỉ cho `PASS/FAIL/ERROR/NOT_RUN`. **Sửa:** khi chiếu sang bundle, `UNAVAILABLE` thành `NOT_RUN`; run record giữ nguyên `UNAVAILABLE`, contract `evidence.py` không đổi. Đã rà mọi record stage 1: không còn status ngoài tập cho phép. Chạy lại 2 run này với `rerun_reason` riêng.
## D23. Qualify theo cửa sổ (`--offset`)

- **Chọn:** `prepare_task_env.py --offset K --limit N` qualify các task K+1..N của tiền tố. `prepare()` báo lỗi nếu `offset` không phải số nguyên ≥ 0, nếu ở chế độ pilot, nếu thiếu `--limit`, hoặc nếu `offset >= limit`. Report ghi cả `offset` và `limit`, nên một lần qualify theo cửa sổ không bị đọc nhầm thành toàn bộ tiền tố.
- **Lý do:** `--limit N` cần image của cả N task cùng lúc (khoảng 2 GB/task); đĩa không đủ cho N = 25. Theo D21, mỗi lúc chỉ giữ image của nấc đang chạy.
- **Population không đổi:** tiền tố 1..N vẫn là đơn vị chọn task (D18), được ghép từ lần qualify của nấc 1 (`w95-a78cd61f…`, task 1..11) và lần qualify cửa sổ của nấc 2 (task 12..25). Cùng manifest, cùng runtime profile đã pin, cùng daemon.

## D24. Nấc 2 gồm 10 task mới, tổng 20 (amendment cho §2 và M3-W10-1)

- **Chọn (người dùng quyết 30/10):** nấc 2 = tiền tố 12..25. Trong 14 task này có 10 task RUNNABLE. Bị loại nhưng vẫn ở mẫu số: `pylint-dev__pylint-4970` (không có test tái hiện, EXCLUDED.md); arm graph của `astropy__astropy-13453`, `astropy__astropy-13977`, `django__django-11087` (OVER_CAP). Tổng hai nấc là **20 task RUNNABLE trên tiền tố 25 task**, thay cho mục tiêu 30 của spec §2 và khoảng 30–50 của M3-W10-1.
- **Lý do:** test tái hiện và bundle của task 12..25 đã có sẵn; chỉ cần khoảng 29 GB image và khoảng 30 run GPU. Mở rộng lên 30 task cần viết thêm khoảng 13–15 test tái hiện, pull khoảng 30 GB image theo đợt và chạy thêm khoảng 30 run.
- **Hệ quả:** độ mạnh thống kê thấp hơn; nấc 1 có F8 = 0 ở cả 3 arm. Việc mở rộng lên 30 (task 26 trở đi) được ghi thành tùy chọn cho W11, chạy bằng một experiment thứ ba có cùng config (fairness giữa các experiment đã có kiểm tự động).
- **Không đổi:** luật tiền tố và RUNNABLE (D18), manifest, config các arm. Chưa có run nào của nấc 2, nên đây không phải chọn task sau khi thấy kết quả.
## D25. Loại task trước khi chạy bằng config (`source.excluded`)

- **Chọn:** config experiment có thêm `source.excluded: {task_id: lý do}`. Runner và preflight ghi `TASK_EXCLUDED` kèm lý do cho task đó ở **cả 3 arm**, và không chạy gì. Lý do rỗng hoặc task không thuộc experiment thì báo lỗi. Trường này nằm trong identity của experiment, nên thêm hay sửa sẽ đổi `experiment_id`. Config không có trường này (pilot W9, nấc 1) thì identity không đổi.
- **Lý do:** D18 loại task OVER_CAP ở bất kỳ arm nào, nhưng runner không có cơ chế làm việc đó. Nếu không loại, A0 vẫn chạy (lệch so sánh giữa các arm), còn A1/A2 hỏng ở `build_repair_prompt` thành `INTERNAL_ERROR`, trông như lỗi hạ tầng.
- **Nấc 2:** `astropy__astropy-13453` (A1/A2 10.439 > 6.000), `astropy__astropy-13977` (6.570 > 6.000) và `django__django-11087` (7.202 > 6.000), lấy từ preflight trước khi chạy. Preflight sau khi loại: 30 FITS + 9 TASK_EXCLUDED + 3 TASK_INPUT_MISSING.

## D26. Giữ nguyên `GENERATION_TIMEOUT` của nấc 2, báo là yếu tố gây nhiễu

- **Chọn (người dùng quyết 30/10):** không tăng budget, không chạy lại. 7 run `GENERATION_TIMEOUT` của nấc 2 (`cfb605118a52b835`) là kết cục cuối hợp lệ theo D20 và nằm trong mẫu số. Gộp hai nấc: A0 1, A1 3, A2 4 (A1/A2: `scikit-learn__scikit-learn-10844`, `sphinx-doc__sphinx-11510`, `matplotlib__matplotlib-20676`; A2 thêm `django__django-10914` ở nấc 1; A0: `sympy__sympy-12481`).
- **Lý do:** timeout là budget của model, không phải lỗi hạ tầng, nên không được chạy lại (spec §2). Tăng budget giữa chừng làm lệch config so với nấc 1 và các run đã có kết cục.
- **Hệ quả khi báo cáo:** timeout lệch về arm graph, nhiều khả năng do prompt dài hơn (input trung bình A0 3.701, A1 4.337, A2 4.327 token). F1 của A1/A2 (17/25, 16/25) thấp hơn A0 (19/25) một phần vì timeout, nên so F1 giữa các arm phải kèm số timeout. F4/F5 (định vị) không bị ảnh hưởng theo hướng có lợi cho graph: run timeout tính là không đạt. Ghi vào Methodology/Threats.
- **Kèm theo:** N = 25 task trong mẫu số (20 RUNNABLE), dưới mức 30–50 của M3-W10-1 (xem D24). 7 run thiếu `gpu_peak_mib` vì `GpuPeakSampler` bỏ cả đỉnh khi một mẫu `nvidia-smi` lỗi; chỉ ảnh hưởng chỉ số cost, chuyển sang W11.