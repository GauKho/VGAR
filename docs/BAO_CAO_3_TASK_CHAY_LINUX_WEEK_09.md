# Báo cáo ba task Week 9 đã chạy trên Linux: M1-W9-4, M1-W9-5, M2-W9-3

Tài liệu mô tả yêu cầu, cách triển khai, kết quả, lệnh thực tế và đường dẫn log/result. Khi biên soạn chỉ đọc code/receipts, không chạy lại pytest, WSL, Docker, model hoặc gold campaign. Các con số PASS dưới đây thuộc lần chạy lịch sử được liên kết, không phải một lần kiểm thử mới ngày 25/10.

## 1. Phạm vi và cách đọc bằng chứng

| Task    | Thực thi Linux đã xác nhận                                           | Kết quả lịch sử và giới hạn                                                                                                                             |
| ------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1-W9-4 | Controller/harness trong WSL, official SWE-bench chạy Docker Linux   | QUALIFIED, **3/3 RESOLVED**; unit wrapper cuối **49 PASS** trên Linux. Raw pytest của Astropy/Matplotlib vẫn có lỗi ngoài required sets.                |
| M1-W9-5 | Unit controller trong WSL; base collection trong năm container Linux | Unit **45 PASS**; collection **3 COLLECTED / 2 EXCLUDED**. Không phải năm task runnable và không chạy test body trong bước collect.                     |
| M2-W9-3 | Controller WSL và Docker execution bridge cho Xarray                 | Scripted A0 integration **PASS**: baseline 1 FAIL/1 PASS → post 2 PASS; **14 operations / 14 cleanup PASS**. Dùng FakeGenerator, không phải model thật. |

Các bộ regression **467 PASS/1 SKIP**, **320 PASS**, **317 PASS** chạy bằng Python Windows; không cộng các số này thành số test Linux. Unit 49/45 kiểm controller logic bằng fixtures/mocks, khác official gold run và real Docker smoke.

**Đính chính đường dẫn trong trao đổi trước:** `linux_wrapper_02.junit.xml` chứa **48** test, không phải 49. Bằng chứng cuối **49 PASS** là `path_fix_06/green_linux.junit.xml` cùng receipt `path_green_linux_06.json`.

`PASS`, `RESOLVED`, `COLLECTED`, `EXCLUDED` là các trạng thái khác nhau. Đặc biệt, probe process exit 0 chỉ nói chương trình probe kết thúc và ghi JSON; phải đọc `probe-result.json → collection.exit_code/status/reason` để biết pytest có collect thành công hay không.

### 1.1. Lệnh lịch sử và lệnh hướng dẫn

Các command block ghi “lịch sử” được dựng nguyên vẹn từ **mảng `argv` đã lưu**, giữ đúng thứ tự/giá trị argument. Việc xuống dòng/đặt dấu nháy là cách trình bày mới; không khẳng định shell text gốc từng được gõ giống hệt. Không có bản ghi toàn bộ shell history hoặc mọi câu lệnh cha của recorder; không tự dựng ra những lệnh không có bằng chứng.

Phụ lục A chép toàn bộ process-command receipts trong ba run cuối, cộng các receipt điều khiển/gate cuối, control directory của campaign cuối và các lệnh pytest/lint được lưu ở ba thư mục triển khai. Nó giữ cả các lệnh exit 1, RED, các checkpoint cũ, duplicate receipts và cleanup; không xóa lỗi để làm báo cáo “toàn PASS”. Các lệnh do thư viện gọi nội bộ, như `pytest.main(...)`, và shell evaluation của upstream được mô tả riêng. Nội dung payload gold/test patch giữ trong artifact local, không chép vào tài liệu Git.

**Không chạy lại nguyên xi các helper lịch sử:** chúng chứa run ID, container ID, output paths, điều kiện lịch sử và có thể tạo file/campaign thật. Gold đã dùng hết **2/2 campaigns, 6/6 attempts**. Báo cáo ghi lại lệnh cũ để kiểm chứng; không cấp thêm quota hoặc tự khởi động Docker, reclaim cache, pull, reset hay prune.

Yêu cầu gốc: [VGAR_W9_W16_Deliverables.md](../../New_task/VGAR_W9_W16_Deliverables.md). Tài liệu tổng hợp trước: [Báo cáo toàn bộ M1/M2 Week 9](../docs/BAO_CAO_TONG_HOP_M1_M2_WEEK_09.md).

## 2. Môi trường và ranh giới Windows / WSL / container

```text
Windows: D:\Project\CAPSTONES\VGAR
  └─ wsl.exe --distribution VGAR-Harness-W9 --user root --exec ...
       └─ WSL: /mnt/d/Project/CAPSTONES/VGAR
            ├─ controller: /home/vgar/w9/venvs/controller/bin/python
            ├─ harness:    /home/vgar/w9/venvs/harness/bin/python
            └─ Docker Linux amd64, endpoint unix:///var/run/docker.sock
                 └─ target: /testbed
                    Python: /opt/miniconda3/envs/testbed/bin/python
```

| Thành phần                | Giá trị đã được ghi nhận                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| WSL distro                | `VGAR-Harness-W9`, Ubuntu 24.04.5, distro Python 3.12; target Python khác nhau theo image                                 |
| Official harness          | SWE-bench 4.1.0, commit `726c5461e2ef52d83cf1ea2107870a8bb3328d57`, source `/home/vgar/w9/swebench`                       |
| Docker                    | Desktop 4.48 / Engine 28.5.1, Linux amd64 theo qualification receipts; tài liệu không xác nhận daemon đang online hôm nay |
| Python Windows regression | `D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe`, Python 3.11.6                                    |
| Dataset revision          | `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`                                                                                |
| Cached Parquet SHA256     | `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`                                                        |

Đường dẫn `/mnt/d/.../VGAR/results/...` trong JSON và `D:\...\VGAR\results\...` trỏ cùng dữ liệu trên ổ D. `/testbed`, `/vgar`, `/tmp/vgar-*` là đường dẫn bên trong container; container đã được cleanup nên không dùng chúng như file hiện có trên Windows.

`results/`, dữ liệu, images và nhiều artifacts bị Git ignore. Clone nhánh GitHub chỉ lấy source/config/docs; các link tới log local cần package evidence tương ứng. Qualified profiles chứa daemon/image/path pins theo máy; không thay identity rồi tự xem self-hash là phê duyệt độc lập.

Thời gian ở báo cáo dùng durations monotonic của receipt. Một số đồng hồ Windows/WSL lệch nhau; không ghép timestamps của hai host thành một timeline hoặc suy diễn tốc độ từ chúng.

## 3. M1-W9-4 — Kiểm chứng official harness bằng gold patch

### 3.1. Yêu cầu và cách triển khai

Tiêu chí gốc: official harness chấm gold patch của 2–3 task là resolved; lưu log/report ngoài Git và ghi vị trí trong status M1. Implementation thực tế nằm ở `src/vgar/evaluation/harness/`, không phải `src/vgar/harness/`.

1. Chọn cố định ba task đầu của pilot: Astropy, Django, Matplotlib. Kiểm manifest, repo/base commit, issue/query identity, cached dataset revision và hash.
2. Đọc oracle riêng cho công đoạn đánh giá: developer gold patch, benchmark test patch và required F2P/P2P. Ghi `inputs/dataset.json` và `inputs/predictions.jsonl` local, `model_patch` là gold patch; không gọi LLM để sinh patch.
3. Preflight kiểm Linux amd64, harness source/module đúng pin, CLI flags, CLI/SDK cùng Docker daemon, immutable image IDs/digests, tài nguyên và inputs. Controller/harness dùng venv riêng.
4. Chạy từng task tuần tự, `--max_workers 1`; upstream timeout 1800 s và parent process timeout 3600 s. Lưu argv/cwd/stdout/stderr/raw reports cho từng invocation.
5. Đọc đúng `logs/run_evaluation/...` của upstream đã pin. Kiểm task identity, strict report booleans, patch bytes thực tế và artifact hashes; không suy RESOLVED từ process exit 0.
6. Kiểm cleanup chỉ container thuộc run, runtime/input/source integrity trước/sau; lỗi integrity/cleanup không được đổi thành RESOLVED. Campaign đạt QUALIFIED khi ít nhất 2 task đạt canonical RESOLVED.

Campaign đầu raw 3 resolved nhưng canonical UNMET/3 ERROR vì wrapper tìm nhầm `logs/evaluation`. Sau RED logic trên Linux → GREEN 49 tests, campaign mới giữ nguyên population/pins và đạt 3/3. Campaign lỗi được giữ nguyên, không sửa report cũ hay gộp PASS giữa hai campaign.

| File                                                                                                                                                                | Nội dung                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\src\vgar\evaluation\harness\gold_inputs.py](../src/vgar/evaluation/harness/gold_inputs.py)                                               | Đóng băng input/dataset/predictions và gold IDs.                                         |
| [D:\Project\CAPSTONES\VGAR\src\vgar\evaluation\harness\official.py](../src/vgar/evaluation/harness/official.py)                                                     | Preflight, invoke, campaign orchestration, artifact đọc đúng upstream layout và cleanup. |
| [D:\Project\CAPSTONES\VGAR\src\vgar\evaluation\harness\reports.py](../src/vgar/evaluation/harness/reports.py)                                                       | Đọc/kiểm canonical grading report.                                                       |
| [D:\Project\CAPSTONES\VGAR\scripts\run_official_harness.sh](../scripts/run_official_harness.sh)                                                                     | Entrypoint shell công khai; final historical run dùng helper run_gold_07.py.             |
| [D:\Project\CAPSTONES\VGAR\tests\test_official_harness.py](../tests/test_official_harness.py)                                                                       | Unit/regression wrapper, gồm regression cho logs/run_evaluation.                         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\run_gold_07.py](../results/m1/w9/m1-w9-4/20261023-local-qualification/run_gold_07.py) | Helper điều phối lịch sử, gồm gate/quota reservation/preflight/campaign; không rerun.    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\runtime\qualified-profile.json](../results/m1/w9/m1-w9-4/runtime/qualified-profile.json)                           | Qualified profile local thực tế; public config là skeleton khác.                         |
| [D:\Project\CAPSTONES\VGAR\docs\m1_w9_4_acceptance_report.md](../docs/m1_w9_4_acceptance_report.md)                                                                 | Nghiệm thu và giới hạn W9-4.                                                             |

### 3.2. Lệnh lịch sử khởi chạy final gold campaign

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.json)

```powershell
& 'wsl.exe' `
  '--distribution' `
  'VGAR-Harness-W9' `
  '--user' `
  'root' `
  '--exec' `
  '/home/vgar/w9/venvs/controller/bin/python' `
  '-B' `
  '/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/run_gold_07.py'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **227.709 s**.

Giải thích từng phần: `wsl.exe` gọi Linux từ Windows; `--distribution` chọn đúng distro đã qualification; `--user root` là user thực tế đã ghi trong receipt; `--exec` chạy trực tiếp executable, không mở interactive shell. Controller Python gọi helper; `-B` tránh ghi `.pyc`. Helper tự thêm `src` vào `sys.path`, đặt explicit Docker endpoint, chạy resource/preflight gate rồi `_campaign(..., execute=True)`.

Đây là command **lịch sử**, không phải command nên chạy lại. Helper yêu cầu đúng một campaign trước đó và tạo `gold_07_control` với `exist_ok=False`; chạy lại không phải tái lập an toàn. Quota hiện đã hết. Full helper nguyên văn có ở phụ lục B, chỉ để đọc.

### 3.3. Lệnh lịch sử unit/regression wrapper 49 PASS

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.json)

```powershell
& 'wsl.exe' `
  '--distribution' `
  'VGAR-Harness-W9' `
  '--user' `
  'root' `
  '--exec' `
  'env' `
  'PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src' `
  'PYTHONDONTWRITEBYTECODE=1' `
  'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1' `
  '/home/vgar/w9/venvs/controller/bin/python' `
  '-B' `
  '-m' `
  'pytest' `
  '/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py' `
  '-q' `
  '-p' `
  'no:cacheprovider' `
  '--tb=short' `
  '--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **3.533 s**.

Các argument bổ sung:

| Thành phần                                     | Giải thích                                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| `env PYTHONPATH=.../src`                       | Trỏ imports tới VGAR source trong WSL.                                                |
| `PYTHONDONTWRITEBYTECODE=1`                    | Không ghi bytecode, kể cả các tiến trình Python kế thừa môi trường.                   |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`             | Không tự nạp các pytest plugin cài ngoài; chỉ plugin được chỉ định/fixture cần thiết. |
| `-m pytest .../tests/test_official_harness.py` | Chạy module pytest bằng controller Python, chọn đúng file wrapper test.               |
| `-q`                                           | Output ngắn.                                                                          |
| `-p no:cacheprovider`                          | Tắt pytest cache provider; không ghi `.pytest_cache`.                                 |
| `--tb=short`                                   | Rút gọn traceback, không thay verdict.                                                |
| `--junitxml=.../green_linux.junit.xml`         | Ghi kết quả máy đọc được. Path này thuộc lần chạy lịch sử.                            |

Stdout cuối: `49 passed in 2.68s`; JUnit: tests=49, failures=0, errors=0, skipped=0. Đây là unit wrapper, không phải 49 real benchmark attempts.

### 3.4. Toàn bộ ba lệnh upstream harness đã thực thi

**astropy\_\_astropy-13398** — `cwd`: `/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398`; receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.json)

```bash
/home/vgar/w9/venvs/harness/bin/python -B -m swebench.harness.run_evaluation --dataset_name /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json --predictions_path /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl --instance_ids astropy__astropy-13398 --split test --max_workers 1 --timeout 1800 --run_id vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b --namespace swebench --instance_image_tag vgar-w9-20261023 --cache_level instance --clean False --force_rebuild False
```

**django\_\_django-11138** — `cwd`: `/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138`; receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.json)

```bash
/home/vgar/w9/venvs/harness/bin/python -B -m swebench.harness.run_evaluation --dataset_name /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json --predictions_path /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl --instance_ids django__django-11138 --split test --max_workers 1 --timeout 1800 --run_id vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9 --namespace swebench --instance_image_tag vgar-w9-20261023 --cache_level instance --clean False --force_rebuild False
```

**matplotlib\_\_matplotlib-14623** — `cwd`: `/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623`; receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.json)

```bash
/home/vgar/w9/venvs/harness/bin/python -B -m swebench.harness.run_evaluation --dataset_name /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json --predictions_path /mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl --instance_ids matplotlib__matplotlib-14623 --split test --max_workers 1 --timeout 1800 --run_id vgw9-15a7b5bf50a8487b8e7abe65627f2598 --namespace swebench --instance_image_tag vgar-w9-20261023 --cache_level instance --clean False --force_rebuild False
```

Đây là argv thực tế lấy từ `harness.json`, không dùng placeholder. Các invocation/output IDs là lịch sử.

| Flag                                                             | Ý nghĩa                                                                                   |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `-m swebench.harness.run_evaluation`                             | Dùng official harness đã pin.                                                             |
| `--dataset_name .../dataset.json`                                | Dataset local đã đóng băng cho campaign.                                                  |
| `--predictions_path .../predictions.jsonl`                       | Predictions local chứa gold patch cho kiểm chứng harness.                                 |
| `--instance_ids`                                                 | Chỉ chạy task tương ứng.                                                                  |
| `--split test`                                                   | Partition upstream; không phủ nhận project đã chọn pilot từ split dev riêng.              |
| `--max_workers 1`                                                | Không chạy nhiều task đồng thời.                                                          |
| `--timeout 1800`                                                 | Timeout đánh giá upstream cho task, khác parent process timeout.                          |
| `--run_id`                                                       | Tên invocation riêng, phân tách logs.                                                     |
| `--namespace swebench` / `--instance_image_tag vgar-w9-20261023` | Chọn official image namespace/tag đã đối chiếu với immutable pins.                        |
| `--cache_level instance`                                         | Cache image cấp instance theo harness.                                                    |
| `--clean False`                                                  | Không yêu cầu harness dọn cached images theo flag này; owned-container cleanup vẫn riêng. |
| `--force_rebuild False`                                          | Không ép rebuild image.                                                                   |

Trong `eval.sh` của từng task, test body command thực tế lần lượt là:

```bash
pytest -rA astropy/coordinates/tests/test_intermediate_transformations.py
./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 timezones.tests
pytest -rA lib/matplotlib/tests/test_axes.py
```

`-rA` xuất kết quả mọi loại test. Django dùng runner riêng cùng SQLite và một worker, không cần pytest trong image. Trước các lệnh này official script activate conda `testbed`, chuẩn bị editable installation và áp benchmark test patch trong container; không nên chạy ba dòng rời trên host rồi xem tương đương harness. Phụ lục C chép phần shell commands của từng `eval.sh`; payload test patch giữ nguyên ở file local được liên kết.

### 3.5. Kết quả cuối và giới hạn

| Task                           | Official F2P success/failure | Official P2P success/failure | Canonical | Wall s |
| ------------------------------ | ---------------------------: | ---------------------------: | --------- | -----: |
| astropy\_\_astropy-13398       |                          4/0 |                         68/0 | RESOLVED  | 93.083 |
| django\_\_django-11138         |                          1/0 |                         73/0 | RESOLVED  | 30.799 |
| matplotlib\_\_matplotlib-14623 |                          1/0 |                        400/0 | RESOLVED  | 84.610 |

Final campaign `20261024T081750218758Z-3af0d2d105bc`: complete=true, QUALIFIED, resolved_count=3, **213.537830049 s**. Outer controller command: **227.709 s**; hai số đo khác phạm vi.

Raw Astropy còn **1 failed/72 passed/3 skipped**; raw Matplotlib còn **179 failed/402 passed/73 skipped**. Required official sets đều đạt, nhưng không được viết “toàn bộ raw pytest PASS”. Không có kết quả model repair, held-out benchmark hoặc pilot 15 records từ task này.

Docker từng lỗi startup/socket; daemon lên lại sau thao tác Quit/start bình thường đã được cho phép. Không có bằng chứng chứng minh root cause đã hết vĩnh viễn. Historical helper có nhánh resource gate reclaim page cache có giới hạn (W9-4 dùng 2/3), không reset/prune dữ liệu/images; việc viết báo cáo không chạy nhánh này.

### 3.6. Đường dẫn đầy đủ log/result W9-4

| File                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Nội dung                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\run_record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/run_record.json)                                                                                                                                                                                                                                                                     | Canonical toàn campaign: QUALIFIED, resolved_count, task records và input/runtime binding.    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.json)                                                                                                                                                                                                                                                                                           | Outer command receipt; stdout/stderr nhúng trong JSON.                                        |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.stdout.log)                                                                                                                                                                                                                                                                               | Stdout của wrapper final gold.                                                                |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.stderr.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.stderr.log)                                                                                                                                                                                                                                                                               | Stderr của wrapper final gold.                                                                |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\gold-summary.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/gold-summary.json)                                                                                                                                                                                                                                                                   | Tổng hợp campaign final và quota đã dùng.                                                     |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\checkpoint_gold_final_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/checkpoint_gold_final_07.json)                                                                                                                                                                                                                                                                           | Checkpoint cuối.                                                                              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\independent_gold_audit_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/independent_gold_audit_07.json)                                                                                                                                                                                                                                                                         | Audit độc lập: PASS, cleanup/input/source/preserved campaign.                                 |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.json)                                                                                                                                                                                                                                                                                     | Receipt đúng của unit Linux 49 PASS.                                                          |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.stdout.log)                                                                                                                                                                                                                                                                         | Stdout đúng 49 passed in 2.68s.                                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_fix_06\green_linux.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml)                                                                                                                                                                                                                                                                   | JUnit cuối đúng 49 PASS.                                                                      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\linux_wrapper_02.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/linux_wrapper_02.junit.xml)                                                                                                                                                                                                                                                                                 | Lần cũ 48 PASS, không dùng làm bằng chứng 49.                                                 |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/record.json)                                                                                                                                                                                                                             | astropy\_\_astropy-13398: canonical task result và artifact hashes                            |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.json)                                                                                                                                                                                                                           | astropy\_\_astropy-13398: argv/cwd/exit/stdout/stderr official process                        |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.stdout.log)                                                                                                                                                                                                               | astropy\_\_astropy-13398: official stdout                                                     |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.stderr.log)                                                                                                                                                                                                               | astropy\_\_astropy-13398: official stderr                                                     |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/report.json)                                   | astropy\_\_astropy-13398: official grading result                                             |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/test_output.txt)                           | astropy\_\_astropy-13398: raw output test, kể cả failures ngoài required sets                 |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/run_instance.log)                         | astropy\_\_astropy-13398: official instance log                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/eval.sh)                                           | astropy\_\_astropy-13398: shell evaluation nguyên văn, gồm benchmark test-patch payload       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/record.json)                                                                                                                                                                                                                                 | django\_\_django-11138: canonical task result và artifact hashes                              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.json)                                                                                                                                                                                                                               | django\_\_django-11138: argv/cwd/exit/stdout/stderr official process                          |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.stdout.log)                                                                                                                                                                                                                   | django\_\_django-11138: official stdout                                                       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.stderr.log)                                                                                                                                                                                                                   | django\_\_django-11138: official stderr                                                       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/report.json)                                           | django\_\_django-11138: official grading result                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/test_output.txt)                                   | django\_\_django-11138: raw output test, kể cả failures ngoài required sets                   |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/run_instance.log)                                 | django\_\_django-11138: official instance log                                                 |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/eval.sh)                                                   | django\_\_django-11138: shell evaluation nguyên văn, gồm benchmark test-patch payload         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/record.json)                                                                                                                                                                                                                 | matplotlib\_\_matplotlib-14623: canonical task result và artifact hashes                      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.json)                                                                                                                                                                                                               | matplotlib\_\_matplotlib-14623: argv/cwd/exit/stdout/stderr official process                  |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.stdout.log)                                                                                                                                                                                                   | matplotlib\_\_matplotlib-14623: official stdout                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.stderr.log)                                                                                                                                                                                                   | matplotlib\_\_matplotlib-14623: official stderr                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/report.json)           | matplotlib\_\_matplotlib-14623: official grading result                                       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/test_output.txt)   | matplotlib\_\_matplotlib-14623: raw output test, kể cả failures ngoài required sets           |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/run_instance.log) | matplotlib\_\_matplotlib-14623: official instance log                                         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/eval.sh)                   | matplotlib\_\_matplotlib-14623: shell evaluation nguyên văn, gồm benchmark test-patch payload |

## 4. M1-W9-5 — Profile môi trường và base-only pytest collection

### 4.1. Yêu cầu và phương pháp

Tiêu chí gốc: cả năm pilot task có `pytest --collect-only` thành công **hoặc có lý do loại được ghi rõ**; output theo environment profile contract. Dùng chính official harness images theo chỉ đạo Docker-only.

1. Pin đủ năm task/repo/base, Docker endpoint/daemon identity và images. Public profile skeleton không đủ READY; helper lịch sử ghép frozen image records vào `qualified-runtime-02.json`.
2. Resource gate giữ Windows/Linux RAM available ít nhất 4 GiB; ổ C ít nhất 10 GiB, D ít nhất 20 GiB. Cache reclaim nếu có là nhánh được cho phép riêng của lịch sử W9-5 (dùng 1/6), không phải thao tác cần làm khi đọc báo cáo.
3. Tạo fresh owned container, không network, không host mount/socket, drop capabilities và no-new-privileges. Kiểm `/testbed` root và object base commit rồi reset exact base **trong container mới**. Đây là sửa lỗi image còn ở setup commit; không reset working tree VGAR hoặc source checkout trên host.
4. Copy probe stdlib tương thích Python 3.5+ cùng JSON config vào container. Probe lấy HEAD/clean/tracked Python inventory hash trước/sau, kiểm đúng base/source scope.
5. Giữ pytest default discovery bằng `scope=["@pytest-default"]`; không đưa toàn bộ tracked test/helper files thành argv vì một số repo có intentional negative/data fixtures.
6. Probe import pytest rồi gọi `pytest.main(['-q','-p','no:cacheprovider','--collect-only'], plugins=[recorder])` ngay trong process; plugin ghi node IDs và collection errors. Đây là lời gọi API Python thực tế, không có subprocess `python -m pytest` riêng ở bước này.
7. Timeout probe 300 s, giới hạn 8 MiB mỗi stream; không chạy test body, không cài pytest/deps để ép task thành công, không suppress warnings để ép Astropy PASS. Ghi raw stdout/stderr, probe-result, record và `task_env.json`, kiểm source integrity/cleanup.
8. `COLLECTED` cần exit pytest 0, node IDs không rỗng, không collection errors. Thiếu pytest/collection lỗi là EXCLUDED với lý do; infrastructure/source/cleanup lỗi là ERROR và không được gọi là exclusion hợp lệ.

| File                                                                                                                                                                      | Nội dung                                                                               |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\src\vgar\evaluation\harness\task_env.py](../src/vgar/evaluation/harness/task_env.py)                                                           | Host controller: pin, resource gate, fresh container/reset, profile/record/cleanup.    |
| [D:\Project\CAPSTONES\VGAR\src\vgar\evaluation\harness\collection_probe.py](../src/vgar/evaluation/harness/collection_probe.py)                                           | Target stdlib probe và in-process pytest.main collection.                              |
| [D:\Project\CAPSTONES\VGAR\scripts\prepare_task_env.py](../scripts/prepare_task_env.py)                                                                                   | CLI công khai; historical run dùng helper run_local_02.py collect.                     |
| [D:\Project\CAPSTONES\VGAR\tests\test_task_env.py](../tests/test_task_env.py)                                                                                             | Unit/regression về environment profiles và reset-before-probe.                         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\run_local_02.py](../results/m1/w9/m1-w9-5/20261024-docker-only/run_local_02.py)                     | Helper final historical invocation, image pinning và bounded resource-recovery branch. |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\qualified-runtime-02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/qualified-runtime-02.json) | Qualified controller runtime thực tế, khác per-task task_env.json.                     |

### 4.2. Lệnh lịch sử chạy collection năm task

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.json)

```powershell
& 'wsl.exe' `
  '--distribution' `
  'VGAR-Harness-W9' `
  '--user' `
  'root' `
  '--exec' `
  '/home/vgar/w9/venvs/controller/bin/python' `
  '-B' `
  '/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/run_local_02.py' `
  'collect'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **91.908 s**.

Các flag WSL/controller/-B giống §3.3. `collect` là mode của helper, không phải flag pytest. Helper xác nhận image preflight READY, đóng băng config, ghi reservation rồi gọi `task_env.prepare(..., execute=True)` vào `collection-runs`.

Không chạy lại helper này: nó tham chiếu previous ERROR/image preflight và ghi fixed evidence filenames. Entry CLI công khai là `scripts/prepare_task_env.py`; đó là đường tái lập có output mới, không phải command lịch sử đã chạy ở trên.

### 4.3. Lệnh lịch sử 45 unit test PASS trên Linux

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.json)

```powershell
& 'wsl.exe' `
  '--distribution' `
  'VGAR-Harness-W9' `
  '--user' `
  'root' `
  '--exec' `
  'env' `
  'PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src' `
  'PYTHONDONTWRITEBYTECODE=1' `
  'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1' `
  '/home/vgar/w9/venvs/controller/bin/python' `
  '-B' `
  '-m' `
  'pytest' `
  '/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py' `
  '-q' `
  '-p' `
  'no:cacheprovider' `
  '--tb=short' `
  '--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **5.617 s**.

Stdout cuối: `45 passed in 4.94s`; JUnit: 45 tests, 0 failures/errors/skips. File test chọn controller logic; real collection outcomes ở bảng tiếp theo.

### 4.4. Các lệnh Docker exec probe thực tế của cả năm task

**astropy\_\_astropy-13398** — receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.json)

```bash
docker exec --workdir /testbed 78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1 /opt/miniconda3/envs/testbed/bin/python -B /tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.py /tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.input.json /tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.result.json
```

**django\_\_django-11138** — receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.json)

```bash
docker exec --workdir /testbed 0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828 /opt/miniconda3/envs/testbed/bin/python -B /tmp/vgar-w95-a95c937412064a76ab66918a5662072f.py /tmp/vgar-w95-a95c937412064a76ab66918a5662072f.input.json /tmp/vgar-w95-a95c937412064a76ab66918a5662072f.result.json
```

**matplotlib\_\_matplotlib-14623** — receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.json)

```bash
docker exec --workdir /testbed df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c /opt/miniconda3/envs/testbed/bin/python -B /tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.py /tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.input.json /tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.result.json
```

**pydata\_\_xarray-3305** — receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.json)

```bash
docker exec --workdir /testbed 21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191 /opt/miniconda3/envs/testbed/bin/python -B /tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.py /tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.input.json /tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.result.json
```

**pylint-dev\_\_pylint-4551** — receipt [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.json)

```bash
docker exec --workdir /testbed 85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82 /opt/miniconda3/envs/testbed/bin/python -B /tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.py /tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.input.json /tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.result.json
```

`docker exec --workdir /testbed <container-id>` chạy probe trong container đang thuộc operation; `<python> -B /tmp/...py <input.json> <result.json>` là target interpreter, probe, cấu hình và file kết quả. Các IDs/paths `/tmp/vgar-*` trong block là nguyên lịch sử, không còn container để chạy lại.

Lệnh pytest thực tế được tạo trong `collection_probe.py`:

```python
code = int(pytest.main(
    ['-q', '-p', 'no:cacheprovider', '--collect-only']
    + ([] if default_discovery else scope),
    plugins=[recorder],
))
```

Với cả năm task, `default_discovery=True` vì scope là `['@pytest-default']`, nên không truyền tên file test bổ sung. `recorder` là CollectionRecorder của probe, ghi sorted unique node IDs và collectreport errors. Dòng này là trích logic, không phải đoạn standalone tự chạy khi chưa có imports/config/recorder.

### 4.5. Kết quả final collection

| Task                           | Status / reason               | Node IDs | Pytest exit | Python / pytest | Probe process s |
| ------------------------------ | ----------------------------- | -------: | ----------- | --------------- | --------------: |
| astropy\_\_astropy-13398       | EXCLUDED / COLLECTION_FAILED  |    23146 | 2           | 3.9.20 / 7.4.0  |          30.339 |
| django\_\_django-11138         | EXCLUDED / PYTEST_UNAVAILABLE |        0 | None        | 3.6.13 / None   |           0.491 |
| matplotlib\_\_matplotlib-14623 | COLLECTED                     |     7892 | 0           | 3.8.20 / 8.3.4  |            10.3 |
| pydata\_\_xarray-3305          | COLLECTED                     |     8713 | 0           | 3.10.15 / 7.4.0 |          12.133 |
| pylint-dev\_\_pylint-4551      | COLLECTED                     |     1429 | 0           | 3.9.20 / 6.2.5  |           3.043 |

Astropy có 23.146 partial node IDs và hai import/collection errors do NumPy DeprecationWarning ở `astropy/convolution/tests/test_convolve_kernels.py`; không được tính partial IDs là COLLECTED. Django không có pytest, nên collection exit là null chứ không phải 0.

Final run `w95-3178eb33a42b414d81656b21b64cc2e2`: **COMPLETE**, complete=true, **3 collected / 2 excluded**. Outer command elapsed **91.908 s**. Các probe process đều exit 0/complete vì probe đã ghi kết quả thành công, kể cả hai task EXCLUDED. Số liệu 320 regression PASS là Windows (§6), không phải real collection count.

Profile `vgar-task-env-v1` ghi task/repo/base, env_ref/image ID/daemon ID, target Python/cwd/runtime, source scope/hash, argv templates, collection result/report hash và source_before=source_after. Profile per-task dùng để M2 admission kiểm lại, không tự chứng minh đủ mọi dependency cho A2 hoặc toàn bộ test suite runnable.

### 4.6. Đường dẫn đầy đủ log/result W9-5

| File                                                                                                                                                                                                                                                                                          | Nội dung                                                                                  |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\run_record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/run_record.json)                                                                         | Tổng hợp COMPLETE, collected_count=3, excluded_count=2.                                   |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.json)                                                                                                                           | Outer WSL invocation + status/duration.                                                   |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.stdout.log)                                                                                                               | Stdout wrapper collection.                                                                |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.stderr.log](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.stderr.log)                                                                                                               | Stderr wrapper collection.                                                                |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_summary_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_summary_02.json)                                                                                                                   | Tổng hợp năm task/profile hashes.                                                         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.json)                                                                                                                         | Receipt Linux unit 45 PASS.                                                               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.stdout.log)                                                                                                             | Stdout 45 passed in 4.94s.                                                                |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.junit.xml](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml)                                                                                                               | JUnit Linux 45 PASS.                                                                      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/record.json)                                 | astropy\_\_astropy-13398: canonical task status/reason/process/profile binding            |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/task_env.json)                             | astropy\_\_astropy-13398: per-task environment profile                                    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/probe-result.json)                     | astropy\_\_astropy-13398: actual pytest exit/node IDs/errors và source before/after       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.json)                         | astropy\_\_astropy-13398: Docker probe command/exit; exit này khác pytest exit            |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.stdout.log)             | astropy\_\_astropy-13398: raw stdout collection                                           |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.stderr.log)             | astropy\_\_astropy-13398: raw stderr collection                                           |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/record.json)                                     | django\_\_django-11138: canonical task status/reason/process/profile binding              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/task_env.json)                                 | django\_\_django-11138: per-task environment profile                                      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/probe-result.json)                         | django\_\_django-11138: actual pytest exit/node IDs/errors và source before/after         |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.json)                             | django\_\_django-11138: Docker probe command/exit; exit này khác pytest exit              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.stdout.log)                 | django\_\_django-11138: raw stdout collection                                             |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.stderr.log)                 | django\_\_django-11138: raw stderr collection                                             |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/record.json)                     | matplotlib\_\_matplotlib-14623: canonical task status/reason/process/profile binding      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/task_env.json)                 | matplotlib\_\_matplotlib-14623: per-task environment profile                              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/probe-result.json)         | matplotlib\_\_matplotlib-14623: actual pytest exit/node IDs/errors và source before/after |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.json)             | matplotlib\_\_matplotlib-14623: Docker probe command/exit; exit này khác pytest exit      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.stdout.log) | matplotlib\_\_matplotlib-14623: raw stdout collection                                     |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.stderr.log) | matplotlib\_\_matplotlib-14623: raw stderr collection                                     |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/record.json)                                       | pydata\_\_xarray-3305: canonical task status/reason/process/profile binding               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/task_env.json)                                   | pydata\_\_xarray-3305: per-task environment profile                                       |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/probe-result.json)                           | pydata\_\_xarray-3305: actual pytest exit/node IDs/errors và source before/after          |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.json)                               | pydata\_\_xarray-3305: Docker probe command/exit; exit này khác pytest exit               |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.stdout.log)                   | pydata\_\_xarray-3305: raw stdout collection                                              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.stderr.log)                   | pydata\_\_xarray-3305: raw stderr collection                                              |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/record.json)                               | pylint-dev\_\_pylint-4551: canonical task status/reason/process/profile binding           |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/task_env.json)                           | pylint-dev\_\_pylint-4551: per-task environment profile                                   |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/probe-result.json)                   | pylint-dev\_\_pylint-4551: actual pytest exit/node IDs/errors và source before/after      |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.json)                       | pylint-dev\_\_pylint-4551: Docker probe command/exit; exit này khác pytest exit           |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.stdout.log)           | pylint-dev\_\_pylint-4551: raw stdout collection                                          |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.stderr.log)           | pylint-dev\_\_pylint-4551: raw stderr collection                                          |

## 5. M2-W9-3 — Manifest admission và Docker execution bridge

### 5.1. Yêu cầu và phương pháp thực hiện

Tiêu chí: pilot task từ SWE-bench manifest chạy qua `run_repair` mà không cần đăng ký vào `trusted_fixtures.json`; task/hash sai vẫn bị chặn. Implementation giữ native trusted-fixture path và thêm explicit `docker_admitted` path.

1. `admit_task(...)` nhận task, manifest và per-task M1 profile với **expected hashes được đối chiếu độc lập**; kiểm identity task/repo/base/toàn issue, manifest đúng population năm task, profile COLLECTED, raw Git blob tree và tracked Python inventory. Không chỉ tin HEAD/clean status.
2. Review phát hiện Git replacement refs có thể giả source tree dù HEAD/Python inventory trông đúng. Bổ sung `--no-replace-objects` cho host read/target reset và regression RED2 → GREEN2; không nới gate để chấp nhận source sai.
3. Editable scope là toàn bộ 36 production Python files trong `xarray/core`, được xác định từ source roots và inventory; loại test/protected paths, không chọn scope từ developer gold patch.
4. Thêm independent issue reproduction overlay `tests/vgar_w9_repro_quantile.py` với hai ca `keep_attrs=True` cần giữ units=K và false control phải bỏ attrs. Test mới absent base, protected, hash-bound; không lấy benchmark test patch/F2P/P2P làm input vòng sửa lỗi.
5. Handoff integration chứa đầy đủ original source lines 2827–2878; label counter `integration-only:whitespace`, không giả Qwen tokens hoặc paired-retrieval qualification. Prompt dùng production `m2-w78-v11`.
6. `run_repair` dùng RepairPolicy(runtime='docker_admitted', command_timeout=120, global_timeout=1800), FakeGenerator đọc candidate.diff định trước, executor=None; experiment A0 chỉ tests bắt buộc, arm=bm25 và expected bundle hashes.
7. Baseline collect/chạy issue repro trước patch phải ghi FAIL thật cho required repro và PASS cho control; áp patch trong private host worktree, sau đó kiểm lại cùng hai tests. Host source original và protected source không đổi.
8. Mỗi target operation tạo container Linux mới, exact image/daemon pinned, networknone, không mounts/socket, cap-drop ALL, no-new-privileges, pids-limit256. Driver stdlib reset exact base trước copy candidate, kiểm runtime và archive/path/regular-file/hash rules, attest bytes trước/sau.
9. Map fixed pytest/mypy/Ruff/syntax checks vào target interpreter, copy reporter độc lập; persist command/result/JUnit. Mỗi CLI step bị clip tối đa60s trong operation/global deadline. Cleanup có budget riêng tối đa30s, kiểm ownership trước rm và kiểm container không còn; cleanup lỗi không cho PASS.
10. Ghi cùng admission/experiment snapshot vào session, run record và evidence bundle. Input/profile/task/bundle/source drift hoặc pin sai phải reject; negative profile-pin test được ghi trước Docker launch.

| File                                                                                                                                                                                                | Nội dung                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\src\vgar\repair\admission.py](../src/vgar/repair/admission.py)                                                                                                           | Admission snapshot, task/profile/source/pin checks và revalidation.                     |
| [D:\Project\CAPSTONES\VGAR\src\vgar\repair\docker_executor.py](../src/vgar/repair/docker_executor.py)                                                                                               | Fresh containers, target driver, fixed commands, deadline/cleanup receipts.             |
| [D:\Project\CAPSTONES\VGAR\src\vgar\repair\pipeline.py](../src/vgar/repair/pipeline.py)                                                                                                             | run_repair orchestration.                                                               |
| [D:\Project\CAPSTONES\VGAR\src\vgar\repair\session.py](../src/vgar/repair/session.py)                                                                                                               | Persisted admission/experiment binding và phase lifecycle.                              |
| [D:\Project\CAPSTONES\VGAR\docs\m2_w9_3_admission.md](../docs/m2_w9_3_admission.md)                                                                                                                 | Contract, methods, final evidence và giới hạn.                                          |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\run_smoke.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/run_smoke.py)                                           | Helper historical: wrong-pin negative test → admission → real run_repair/FakeGenerator. |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-inputs-lines\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-inputs-lines/config.json)       | Integration task/expected pins/source_roots/overlay/bundle config.                      |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-inputs-lines\candidate.diff](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-inputs-lines/candidate.diff) | Candidate định trước, không phải patch do model sinh.                                   |

### 5.2. Lệnh lịch sử final smoke 05

Receipt: [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.json)

```powershell
& 'wsl.exe' `
  '--distribution' `
  'VGAR-Harness-W9' `
  '--user' `
  'root' `
  '--exec' `
  'env' `
  'PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src' `
  'PYTHONDONTWRITEBYTECODE=1' `
  'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1' `
  '/home/vgar/w9/venvs/controller/bin/python' `
  '-B' `
  '/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/run_smoke.py' `
  '05'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **638.903 s**.

Các biến môi trường WSL giống §3.3. Suffix `05` chọn `admission-05.json`, `negative-pin-05.json`, `smoke-summary-05.json`, `smoke-runs-05` và private worktree directory. Giữ số này ở lệnh lịch sử để đối chiếu chính xác; khi chủ động tái lập phải dùng suffix/output mới, không ghi đè lần05.

`FakeGenerator` chỉ trả candidate.diff có sẵn; generation 0 ms không phải tốc độ LLM. Một lần gọi `run_repair` bao trọn context/workspace/baseline/prompt/generation/parse/apply/selection/verification/cleanup. Phụ lục B giữ nguyên helper để thấy rõ mọi tham số API.

### 5.3. Hai lần pytest thực tế: baseline và sau patch

**Baseline — expected 1 FAIL / 1 PASS**

Process Docker probe (`argv`):

```bash
docker exec -w /testbed vgar-m2w93-4333e25387a24d4aac2c32a331e0db58 /opt/miniconda3/envs/testbed/bin/python /vgar/docker_probe.py /vgar/config.json /vgar/result.json
```

Lệnh target bên trong probe (`target_argv`):

```bash
/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml tests/vgar_w9_repro_quantile.py
```

Receipt: [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/command.json).

**Sau patch — 2 PASS**

Process Docker probe (`argv`):

```bash
docker exec -w /testbed vgar-m2w93-b504d4effcc341ca979405490af99531 /opt/miniconda3/envs/testbed/bin/python /vgar/docker_probe.py /vgar/config.json /vgar/result.json
```

Lệnh target bên trong probe (`target_argv`):

```bash
/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml tests/vgar_w9_repro_quantile.py
```

Receipt: [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/command.json).

Hai target pytest argv giống nhau; khác snapshot candidate được đưa vào fresh container. Không chạy pytest trên target source vừa dùng ở lần trước, không dựa vào state sót lại.

| Argument                                                               | Giải thích                                                                          |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `docker exec -w /testbed <owned-name>`                                 | Chạy driver bên trong đúng container operation với cwd /testbed.                    |
| `.../python /vgar/docker_probe.py /vgar/config.json /vgar/result.json` | Driver stdlib nhận config/snapshot và ghi protocol result; khác target pytest argv. |
| `-m pytest -q -p no:cacheprovider`                                     | Dùng pytest trong target image, output ngắn và tắt cache provider.                  |
| `-p vgar_pytest_reporter`                                              | Nạp reporter do M2 copy vào container; ghi kết quả node IDs/outcomes.               |
| `--m2-report-json=/vgar/nodeids.json`                                  | Output structured riêng của reporter.                                               |
| `--junitxml=/vgar/junit.xml`                                           | Output JUnit trong container, sau đó copy ra host operation directory.              |
| `tests/vgar_w9_repro_quantile.py`                                      | Independent issue repro + control, protected overlay; không benchmark oracle.       |

Trong lệnh `docker create` được lưu ở phụ lục A, `--network none`, `--cap-drop ALL`, `--security-opt no-new-privileges` và `--pids-limit 256` là isolation flags. Không có host bind mount. Docker cp dùng archive/control files đã kiểm rồi chỉ copy fixed reports về host; driver chạy target Python, không cài VGAR/Torch vào image.

### 5.4. Kết quả và cách đọc PASS

Run `20261024T104018047265Z-61c601678725`: **PASS**, complete=true, original_source_unchanged=true, outer elapsed **638.903 s**.

| Ca kiểm                     | Baseline | Sau patch |
| --------------------------- | -------- | --------- |
| keep_attrs=True giữ units=K | FAIL     | PASS      |
| keep_attrs=False bỏ attrs   | PASS     | PASS      |

Baseline stage PASS có nghĩa baseline evidence hợp lệ: đã tái hiện lỗi required và có control PASS. Nó không có nghĩa baseline pytest exit 0. Baseline target command exit1/statusFAIL là expected evidence; post exit0/statusPASS. Independent audit ghi đủ **14 operations, 14 cleanup PASS**, không còn owned containers.

Syntax target PASS. Mypy/Ruff trong image thiếu module, raw process FAIL/structured ERROR; A0 chỉ yêu cầu tests nên các static errors được ghi nhưng không bắt buộc. Không được gọi đây là A2/tool qualification hoặc “mọi command đều PASS”. Đây là pipeline/admission integration bằng scripted patch, chưa là LLM repair result, retrieval comparison hoặc benchmark resolved score.

Những smoke01–03 lỗi và RED/GREEN trước đó vẫn giữ. Smoke04 có canonical PASS/audit PASS nhưng wrapper ERROR khi đọc summary sau khi canonical đã được ghi; không gộp nó với các lỗi target trước đó. Final05 wrapper và canonical đều PASS; không dùng recovered summary của04 làm bằng chứng thay thế final05.

### 5.5. Toàn bộ 14 target operations và đường dẫn result/log

| Operation                          | Target command / loại                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Exit / status | Result và log                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `2640044ae2dd4ef4b2ced651865d724e` | `/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml --collect-only tests/vgar_w9_repro_quantile.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | 0 / PASS      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cleanup.json) |
| `4333e25387a24d4aac2c32a331e0db58` | `/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml tests/vgar_w9_repro_quantile.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cleanup.json) |
| `229613e0b4c04ed495d6290daa4ffabd` | `syntax qua driver Python (target_argv=null; xem control/config.json và target_result.json)`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 0 / PASS      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cleanup.json) |
| `d70f06f9beb844d3ab78a3f63b5f6d8c` | `/opt/miniconda3/envs/testbed/bin/python -m mypy --version`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cleanup.json) |
| `a8238dd3b72f4e8ab9ec81cb1bfa491a` | `/opt/miniconda3/envs/testbed/bin/python -m mypy --config-file /vgar/mypy.ini --no-incremental --cache-dir /vgar/mypy-cache --output json --no-error-summary xarray/core/__init__.py xarray/core/accessor_dt.py xarray/core/accessor_str.py xarray/core/alignment.py xarray/core/arithmetic.py xarray/core/combine.py xarray/core/common.py xarray/core/computation.py xarray/core/concat.py xarray/core/coordinates.py xarray/core/dask_array_compat.py xarray/core/dask_array_ops.py xarray/core/dataarray.py xarray/core/dataset.py xarray/core/dtypes.py xarray/core/duck_array_ops.py xarray/core/extensions.py xarray/core/formatting.py xarray/core/groupby.py xarray/core/indexes.py xarray/core/indexing.py xarray/core/merge.py xarray/core/missing.py xarray/core/nanops.py xarray/core/npcompat.py xarray/core/nputils.py xarray/core/ops.py xarray/core/options.py xarray/core/pdcompat.py xarray/core/pycompat.py xarray/core/resample.py xarray/core/resample_cftime.py xarray/core/rolling.py xarray/core/rolling_exp.py xarray/core/utils.py xarray/core/variable.py` | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cleanup.json) |
| `06b8252ffeea4729bcdadbfa8fc162a1` | `/opt/miniconda3/envs/testbed/bin/python -m ruff --version`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cleanup.json) |
| `a07907c5f49f4dbcb34a0d37807c8f90` | `/opt/miniconda3/envs/testbed/bin/python -m ruff check --config /vgar/ruff.toml --no-cache --no-fix --output-format json xarray/core/__init__.py xarray/core/accessor_dt.py xarray/core/accessor_str.py xarray/core/alignment.py xarray/core/arithmetic.py xarray/core/combine.py xarray/core/common.py xarray/core/computation.py xarray/core/concat.py xarray/core/coordinates.py xarray/core/dask_array_compat.py xarray/core/dask_array_ops.py xarray/core/dataarray.py xarray/core/dataset.py xarray/core/dtypes.py xarray/core/duck_array_ops.py xarray/core/extensions.py xarray/core/formatting.py xarray/core/groupby.py xarray/core/indexes.py xarray/core/indexing.py xarray/core/merge.py xarray/core/missing.py xarray/core/nanops.py xarray/core/npcompat.py xarray/core/nputils.py xarray/core/ops.py xarray/core/options.py xarray/core/pdcompat.py xarray/core/pycompat.py xarray/core/resample.py xarray/core/resample_cftime.py xarray/core/rolling.py xarray/core/rolling_exp.py xarray/core/utils.py xarray/core/variable.py`                                     | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cleanup.json) |
| `2ec2be20a12e4e129fbae07153e1bc95` | `/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml --collect-only tests/vgar_w9_repro_quantile.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | 0 / PASS      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cleanup.json) |
| `b504d4effcc341ca979405490af99531` | `/opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider -p vgar_pytest_reporter --m2-report-json=/vgar/nodeids.json --junitxml=/vgar/junit.xml tests/vgar_w9_repro_quantile.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 0 / PASS      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cleanup.json) |
| `efa21860246a47e8bd694b05e2b71ba4` | `syntax qua driver Python (target_argv=null; xem control/config.json và target_result.json)`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 0 / PASS      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cleanup.json) |
| `b91807cc234c45bf8a714f3951047cfe` | `/opt/miniconda3/envs/testbed/bin/python -m mypy --version`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cleanup.json) |
| `2516346f4e56495b8da2c6e121ac249b` | `/opt/miniconda3/envs/testbed/bin/python -m mypy --config-file /vgar/mypy.ini --no-incremental --cache-dir /vgar/mypy-cache --output json --no-error-summary xarray/core/__init__.py xarray/core/accessor_dt.py xarray/core/accessor_str.py xarray/core/alignment.py xarray/core/arithmetic.py xarray/core/combine.py xarray/core/common.py xarray/core/computation.py xarray/core/concat.py xarray/core/coordinates.py xarray/core/dask_array_compat.py xarray/core/dask_array_ops.py xarray/core/dataarray.py xarray/core/dataset.py xarray/core/dtypes.py xarray/core/duck_array_ops.py xarray/core/extensions.py xarray/core/formatting.py xarray/core/groupby.py xarray/core/indexes.py xarray/core/indexing.py xarray/core/merge.py xarray/core/missing.py xarray/core/nanops.py xarray/core/npcompat.py xarray/core/nputils.py xarray/core/ops.py xarray/core/options.py xarray/core/pdcompat.py xarray/core/pycompat.py xarray/core/resample.py xarray/core/resample_cftime.py xarray/core/rolling.py xarray/core/rolling_exp.py xarray/core/utils.py xarray/core/variable.py` | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cleanup.json) |
| `c3289d5328a247938690467c704d1da4` | `/opt/miniconda3/envs/testbed/bin/python -m ruff --version`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cleanup.json) |
| `8e4d1438d4954767af8c11f0857f3c50` | `/opt/miniconda3/envs/testbed/bin/python -m ruff check --config /vgar/ruff.toml --no-cache --no-fix --output-format json xarray/core/__init__.py xarray/core/accessor_dt.py xarray/core/accessor_str.py xarray/core/alignment.py xarray/core/arithmetic.py xarray/core/combine.py xarray/core/common.py xarray/core/computation.py xarray/core/concat.py xarray/core/coordinates.py xarray/core/dask_array_compat.py xarray/core/dask_array_ops.py xarray/core/dataarray.py xarray/core/dataset.py xarray/core/dtypes.py xarray/core/duck_array_ops.py xarray/core/extensions.py xarray/core/formatting.py xarray/core/groupby.py xarray/core/indexes.py xarray/core/indexing.py xarray/core/merge.py xarray/core/missing.py xarray/core/nanops.py xarray/core/npcompat.py xarray/core/nputils.py xarray/core/ops.py xarray/core/options.py xarray/core/pdcompat.py xarray/core/pycompat.py xarray/core/resample.py xarray/core/resample_cftime.py xarray/core/rolling.py xarray/core/rolling_exp.py xarray/core/utils.py xarray/core/variable.py`                                     | 1 / FAIL      | [command.json (stdout/stderr)](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/command.json); [target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/target_result.json); [cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cleanup.json) |

| File                                                                                                                                                                                                                                                                                                                                                      | Nội dung                                                             |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\REPORT.md](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/REPORT.md)                                                                                                   | Human-readable tóm tắt stages.                                       |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\run_record.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/run_record.json)                                                                                       | Canonical full run/stages/verdict.                                   |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\session.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/session.json)                                                                                             | Persisted phase/state và admission/experiment.                       |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\evidence_bundle.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/evidence_bundle.json)                                                                             | Evidence bundle metadata và command bindings.                        |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-summary-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-summary-05.json)                                                                                                                                                                               | Final summary PASS/complete/source unchanged.                        |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.json)                                                                                                                                                                                 | Outer WSL invocation và timing.                                      |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.stdout.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.stdout.log)                                                                                                                                                                     | Stdout outer smoke helper.                                           |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.stderr.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.stderr.log)                                                                                                                                                                     | Stderr outer smoke helper.                                           |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\independent_audit_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/independent_audit_05.json)                                                                                                                                                                       | Audit baseline/post/14operations/cleanup/pins/source.                |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\containers_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/containers_final.json)                                                                                                                                                                               | Bằng chứng kiểm containers cuối.                                     |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\negative-pin-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/negative-pin-05.json)                                                                                                                                                                                 | Expected profile hash sai bị reject trước Docker.                    |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission-05.json)                                                                                                                                                                                       | Admission snapshot final.                                            |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\checkpoint_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/checkpoint_final.json)                                                                                                                                                                               | Checkpoint final M2-W9-3.                                            |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/command.json)             | Baseline 1FAIL/1PASS: argv, target_argv, stdout/stderr/exit/duration |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/target_result.json) | Baseline 1FAIL/1PASS: target protocol/runtime/source/result          |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/junit.xml)                   | Baseline 1FAIL/1PASS: testcase verdicts                              |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/nodeids.json)             | Baseline 1FAIL/1PASS: structured outcomes từ reporter                |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cleanup.json)             | Baseline 1FAIL/1PASS: container removed/cleanup                      |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/command.json)             | Post 2PASS: argv, target_argv, stdout/stderr/exit/duration           |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/target_result.json) | Post 2PASS: target protocol/runtime/source/result                    |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/junit.xml)                   | Post 2PASS: testcase verdicts                                        |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/nodeids.json)             | Post 2PASS: structured outcomes từ reporter                          |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cleanup.json)             | Post 2PASS: container removed/cleanup                                |

## 6. Regression hỗ trợ đã PASS trên Windows — không gán sang Linux

Các command dưới đây cũng đã dùng để nghiệm thu code của ba task, nên được giữ đầy đủ theo yêu cầu “toàn bộ lệnh chạy PASS”. Interpreter `.../Scripts/python.exe` chứng minh chúng thuộc Windows. `--basetemp` và JUnit là fixed historical output, không dùng lại khi chạy mới.

### 6.1. W9-4 selected regression — 467 PASS / 1 SKIP

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.json)

```powershell
& 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe' `
  '-B' `
  '-m' `
  'pytest' `
  'tests/test_official_harness.py' `
  'tests/test_w9_bm25_handoff.py' `
  'tests/test_w9_pilot_bundles.py' `
  'tests/test_m1_handoff.py' `
  'tests/test_impact.py' `
  'tests/m2/test_dataset_split.py' `
  'tests/m2/test_retrieval_evaluation.py' `
  'tests/m2/test_retrieval_scoring.py' `
  'tests/m2/w910' `
  'tests/m2/w78/test_w78_evidence.py' `
  'tests/m2/w78/test_w78_evidence_bundle.py' `
  '-q' `
  '-p' `
  'no:cacheprovider' `
  '--tb=short' `
  '--basetemp=D:/vgar-w94-regression-20261024-0814' `
  '--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **163.75 s**.

Stdout summary:

```text
467 passed, 1 skipped in 162.70s (0:02:42)
```

| File                                                                                                                                                                                                    | Nội dung                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.json)                 | Command receipt/status/duration/stdout/stderr. |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.stdout.log)     | Raw stdout.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.stderr.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.stderr.log)     | Raw stderr.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_fix_06\regression.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml) | JUnit của regression Windows này.              |

### 6.2. W9-5 selected regression — 320 PASS

Receipt: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.json)

```powershell
& 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe' `
  '-B' `
  '-m' `
  'pytest' `
  'tests/test_task_env.py' `
  'tests/test_official_harness.py' `
  'tests/test_w9_bm25_handoff.py' `
  'tests/test_w9_pilot_bundles.py' `
  'tests/test_w9_bundle.py' `
  'tests/test_m1_handoff.py' `
  '-q' `
  '-p' `
  'no:cacheprovider' `
  '--tb=short' `
  '--basetemp=D:/vgar-w95-base-fix-20261024-0924' `
  '--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **36.423 s**.

Stdout summary:

```text
320 passed in 35.80s
```

| File                                                                                                                                                                                | Nội dung                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.json)             | Command receipt/status/duration/stdout/stderr. |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.stdout.log) | Raw stdout.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.stderr.log](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.stderr.log) | Raw stderr.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.junit.xml](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml)   | JUnit của regression Windows này.              |

### 6.3. M2 full W78/W9 — 317 PASS

Receipt: [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.json)

```powershell
& 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe' `
  '-B' `
  '-m' `
  'pytest' `
  'tests/m2/w78' `
  'tests/m2/w910' `
  '-q' `
  '-p' `
  'no:cacheprovider' `
  '--basetemp=D:/vgar-m2w93-full-final' `
  '--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml'
```

`cwd`: `D:\Project\CAPSTONES\VGAR`; status **PASS**; exit **0**; thời gian outer process **371.876 s**.

Stdout summary:

```text
317 passed in 370.63s (0:06:10)
```

| File                                                                                                                                                                                      | Nội dung                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.json)             | Command receipt/status/duration/stdout/stderr. |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.stdout.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.stdout.log) | Raw stdout.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.stderr.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.stderr.log) | Raw stderr.                                    |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml)   | JUnit của regression Windows này.              |

## 7. Hướng dẫn kiểm lại bằng chứng và tái lập có kiểm soát

### 7.1. Đọc kết quả cũ, không thực thi test

Mở PowerShell, chạy từng dòng sau. Đây là **hướng dẫn mới chỉ đọc**, không khẳng định là nguyên shell command lịch sử.

```powershell
Set-Location -LiteralPath 'D:\Project\CAPSTONES\VGAR'
$gold = Get-Content -LiteralPath 'results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/run_record.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$gold | Select-Object run_id, status, complete, resolved_count, duration_seconds
$gold.tasks | Select-Object instance_id, status, resolved, duration_seconds

$envRun = Get-Content -LiteralPath 'results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/run_record.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$envRun | Select-Object run_id, status, complete, collected_count, excluded_count
$envRun.tasks | Select-Object task_id, status, reason

$smoke = Get-Content -LiteralPath 'results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-summary-05.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$smoke | Select-Object run_id, status, complete, original_source_unchanged
```

`Set-Location` chọn repo; `Get-Content -Raw -Encoding UTF8` đọc nguyên JSON; `ConvertFrom-Json` chuyển thành object; `Select-Object` chỉ in trường cần đọc. Các biến task-specific không ghi file. Để đọc raw log dùng `Get-Content -LiteralPath '<đường dẫn log ở bảng>' -Tail 100`; `-Tail 100` chỉ hiển thị 100 dòng cuối, không phải toàn bộ log.

JUnit chỉ đọc bằng XML parser:

```powershell
$junitPath = 'D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_fix_06\green_linux.junit.xml'
[xml]$junit = Get-Content -LiteralPath $junitPath -Raw -Encoding UTF8
$junit.testsuites.testsuite | Select-Object tests, failures, errors, skipped, time
```

Kỳ vọng saved receipt: tests=49, failures=0, errors=0, skipped=0. Thay path bằng `base_prepare_green.junit.xml` để đọc 45 tests W9-5, hoặc baseline/post `junit.xml` để thấy FAIL/PASS khác nhau. Không dùng path `linux_wrapper_02.junit.xml` khi muốn xác minh 49.

### 7.2. Chạy lại unit Linux bằng output mới khi chủ động kiểm thử

Chỉ áp dụng cho máy/distro/controller đã có và dependencies tương ứng. Unit commands không thực thi gold campaign. Trong PowerShell, tự tạo thư mục output mới trên ổ D và truyền cùng path WSL cho JUnit; không dùng fixed output lịch sử.

```powershell
$runTag = 'manual-linux-unit-' + [guid]::NewGuid().ToString('N')
$outWin = Join-Path 'D:\Project\CAPSTONES\VGAR\results\manual\week9' $runTag
New-Item -ItemType Directory -Path $outWin -ErrorAction Stop | Out-Null
$outLinux = '/mnt/d/Project/CAPSTONES/VGAR/results/manual/week9/' + $runTag
wsl.exe --distribution VGAR-Harness-W9 --user root --exec env `
  PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src PYTHONDONTWRITEBYTECODE=1 `
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/vgar/w9/venvs/controller/bin/python -B -m pytest `
  /mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py `
  /mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py `
  -q -p no:cacheprovider --tb=short "--junitxml=$outLinux/unit.junit.xml"
if ($LASTEXITCODE -ne 0) { throw 'Unit test failed; inspect stdout and JUnit.' }
```

GUID tạo output mới, `New-Item -ErrorAction Stop` không âm thầm tái dùng thư mục đã tồn tại; `$outLinux` ánh xạ chính xác cùng thư mục ổ D. Lệnh gộp hai file là **hướng dẫn mới**, không phải command lịch sử 49/45 riêng; không hứa count sẽ luôn là 94 nếu source/dependencies đã thay đổi. Các unit controller có mocks khác real Docker workload.

### 7.3. Tái lập collection hoặc Docker smoke

Nhận đủ ignored package trước: manifests, paired handoff/source checkout, task profiles, exact images, qualified controller runtime và saved pins; đối chiếu hash/daemon/path trên máy nhận. Không mặc định Git clone mang theo chúng.

Collection CLI công khai: `scripts/prepare_task_env.py`; dùng qualified runtime, chọn output root mới, chạy preflight mặc định trước, đọc ready/status rồi mới chủ động execute. Không thêm `--prepare-images` nếu không định pull images. Per-task profile là `.../<task>/task_env.json`, không truyền controller runtime thay profile admission.

M2 helper `run_smoke.py` nhận suffix mới và dùng integration-only package; source/config/profile paths đang gắn máy cũ. Muốn kiểm lại trên cùng máy đã qualified có thể đổi `05` thành GUID trong command §5.2; đó là **lần chạy mới**, tốn runtime và tạo fresh containers, không phải đọc log. Trên máy khác cần qualification/pins mới. Không chạy prepare_line_smoke vào fixed input directory để ghi đè package cũ.

Gold: chỉ đọc report/log hiện có. Không chạy lại command §3.2, không thêm `--execute`, không gọi `run_gold_validation()` hoặc `_campaign(..., execute=True)` khi chưa có quota/quyết định mới. Historical helper còn nhánh cache reclaim theo approval cũ; không dùng nó như generic reproduction script.

## 8. Kết luận nghiệm thu đúng phạm vi

Ba task đã có thực thi Linux thật, với ba ý nghĩa khác nhau: W9-4 kiểm đúng official gold grading; W9-5 cung cấp environment profile và collection/exclusion evidence; M2-W9-3 nối admission với real Docker execution của repair pipeline. Kết quả không chứng minh năm task đều runnable, toàn bộ raw suites PASS, model thật đã sửa lỗi, A2 tools đã qualified, hoặc đủ pilot M3 15 records.

Khi bàn giao M3 cần gửi cả source branch lẫn ignored evidence/input package; đọc canonical status và raw logs cùng nhau. Không dùng screenshot hoặc chỉ câu “PASS” để thay JSON/JUnit/pins. Các đường dẫn local ở tài liệu là vị trí thật tại thời điểm biên soạn; container paths cũ không còn sau cleanup.

## Phụ lục A — Toàn bộ argv có process receipt trong các run cuối và gate liên quan

Mỗi mục dưới đây chép `argv` dưới dạng JSON array để giữ chính xác argument boundaries, kèm nguồn receipt, cwd, status, exit và timeout. `argv` trong `command.json` là Docker driver; `target_argv` (nếu có) là lệnh test/tool thật bên trong driver. JSON array không phải một shell command để paste trực tiếp. Có thể dựng shell bằng quy tắc quote tương ứng, nhưng IDs/paths vẫn là lịch sử và không được chạy lại mù quáng.

Mục này không đếm config argv là một process đã chạy; chỉ chọn JSON top-level có `argv`, `started_utc`, `exit_code`. Aggregate `record.json` chứa lại cùng process không được đếm lần nữa. Riêng pytest API nội bộ và upstream eval.sh xem §§3.4, 4.4 và phụ lục C. Các command được sắp theo đường dẫn receipt trong mỗi nhóm, không suy diễn thứ tự thời gian giữa Windows/WSL.

### A.1. Giải thích các nhóm lệnh trong receipts

| Lệnh / argument                                                                       | Cách đọc và mục đích thực tế                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docker info --format '{{json .}}'`                                                   | Đọc daemon identity/platform; format JSON để controller kiểm fields. Không khởi động hoặc thay settings daemon.                                                                                                   |
| `docker image inspect <image>`                                                        | Đọc local immutable image ID/digests/platform. Không tương đương pull hoặc rebuild.                                                                                                                               |
| `docker ps -q` / `ps -aq --filter name=...`                                           | Liệt kê container đang chạy / mọi trạng thái, thường giới hạn exact owned name. Output rỗng là bằng chứng không có container đó tại thời điểm kiểm.                                                               |
| `docker create --name ... --label ...`                                                | Tạo container operation mới; name/labels giúp ownership check trước cleanup. Đây là mutation runtime lịch sử, không phải lệnh chỉ đọc.                                                                            |
| `--entrypoint /bin/sleep ... infinity`                                                | Giữ container sống để copy input, chạy driver và lấy reports bằng các exec/cp riêng.                                                                                                                              |
| `--network none`                                                                      | Tắt network của target container cho W9-5/M2. Không suy official harness W9-4 có cùng policy từ flag của hai task này.                                                                                            |
| `--cap-drop ALL`, `--security-opt no-new-privileges`                                  | Giảm Linux capabilities và ngăn nâng quyền qua exec.                                                                                                                                                              |
| `--pids-limit 256`                                                                    | Giới hạn process count của M2 target container; không tự gán flag này cho W9-5 khi receipt không có.                                                                                                              |
| `docker start <id/name>` / `container inspect`                                        | Start fresh owned container; đọc lại name/image/labels trước thao tác tiếp theo.                                                                                                                                  |
| `docker cp <host-file> <container>:<path>`                                            | Đưa control/probe/config/archive vào container. Chiều ngược lại lấy result/report về host. Không có nghĩa bind mount hoặc copy toàn repo target về host.                                                          |
| `docker exec --workdir /testbed ...` / `exec -w`                                      | Chạy command trong container với cwd rõ ràng; target Python nằm trong image, khác controller/harness venv.                                                                                                        |
| `git ... rev-parse`, `cat-file`, `ls-files`, `status`                                 | Kiểm root/base object/HEAD/tracked inventory/clean state. Đây là identity checks, không phải test verdict.                                                                                                        |
| `git -C /testbed reset --hard <base>`                                                 | W9-5 đưa fresh owned container từ setup commit về exact task base; không chạy trên VGAR host. M2 driver cũng reset base trước candidate theo contract riêng.                                                      |
| `git --no-replace-objects ...`                                                        | M2 không cho replacement refs đổi nghĩa object/tree được đối chiếu; giữ expected commit identity.                                                                                                                 |
| `docker rm -f <owned-id>`                                                             | Xóa container sau ownership validation; không phải image prune/reset hoặc xóa toàn dữ liệu Docker. Sau đó exact-name ps phải rỗng.                                                                                |
| `powershell.exe ... -File <resource_gate.ps1>`                                        | W9-4 gọi resource gate Windows từ WSL; `-NoProfile` bỏ profile shell, `-ExecutionPolicy Bypass` áp dụng process đó để chạy script local, không phải chỉnh policy toàn máy.                                        |
| `powershell.exe ... Get-CimInstance ...`                                              | Đọc RAM khả dụng trên Windows cho resource receipts. Không thay RAM/swap settings.                                                                                                                                |
| `sync` và `/proc/sys/vm/drop_caches` trong historical helper                          | Flush rồi giải phóng page cache khi resource gate và approval budget cho phép. Đây là nhánh mutation lịch sử đã giới hạn; không phải test command hay thao tác cần chạy để đọc báo cáo.                           |
| `python -m mypy ... --config-file ... --no-incremental --cache-dir ... --output json` | Fixed static-check template; scope/config và output được bind. Thiếu module trong M2 image là raw FAIL, không phải PASS.                                                                                          |
| `python -m ruff check ... --no-cache --no-fix --output-format json`                   | Fixed lint template, chỉ báo diagnostics, không tự sửa candidate. `--version` dùng để ghi tool identity, cũng fail nếu module không có.                                                                           |
| `python -m pytest ... --basetemp ...`                                                 | Unit/regression process ngoài real target; interpreter/argv cho biết chạy Windows hay Linux. `--basetemp` có thể dọn thư mục temp khi pytest chạy, nên không tái dùng path lịch sử/không trỏ vào source/evidence. |

`status`, `exit_code`, `timed_out`, `output_truncated`, `complete` cần đọc cùng nhau. Exit 0 không thay thế source/runtime/cleanup integrity; null có thể là field không áp dụng hoặc command không hoàn tất, không được tự đổi thành PASS. Các group có chữ RED/green là tên artifact; verdict phải đọc field thực tế.

<details>
<summary>M1-W9-4 final gold run — 45 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.astropy__astropy\\-13398\\.vgw9\\-f7bfe9cba29d4bd9bb1a709efa8fe00b$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398",
  "started_utc": "2026-10-24T08:19:25.854321+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--dataset_name",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json",
    "--predictions_path",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl",
    "--instance_ids",
    "astropy__astropy-13398",
    "--split",
    "test",
    "--max_workers",
    "1",
    "--timeout",
    "1800",
    "--run_id",
    "vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b",
    "--namespace",
    "swebench",
    "--instance_image_tag",
    "vgar-w9-20261023",
    "--cache_level",
    "instance",
    "--clean",
    "False",
    "--force_rebuild",
    "False"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398",
  "started_utc": "2026-10-24T08:17:55.297811+00:00",
  "timeout_seconds": 3600,
  "status": "OK",
  "exit_code": 0
}
```

**3.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.astropy__astropy\\-13398\\.vgw9\\-f7bfe9cba29d4bd9bb1a709efa8fe00b$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398",
  "started_utc": "2026-10-24T08:17:55.236385+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**4.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/docker-info.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:29.651289+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**5.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-clean.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "status",
    "--porcelain",
    "--untracked-files=all"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:25.998727+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**6.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-head.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:25.918979+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**7.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-0.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:30.713333+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**8.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-1.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:30.818151+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**9.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-2.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:30.953218+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**10.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-help.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--help"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:27.891712+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**11.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-module.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import json,swebench; import swebench.harness.run_evaluation as m; print(json.dumps({\"version\":swebench.__version__,\"module\":m.__file__}))"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:26.064033+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**12.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/sdk-daemon.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import docker,json; c=docker.from_env(); print(json.dumps({\"ID\":c.info()[\"ID\"]})); c.close()"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after",
  "started_utc": "2026-10-24T08:19:30.380451+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**13.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.django__django\\-11138\\.vgw9\\-d73bf5e0922c4c90a7b2a6d1fcb613a9$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138",
  "started_utc": "2026-10-24T08:19:56.991218+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**14.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--dataset_name",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json",
    "--predictions_path",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl",
    "--instance_ids",
    "django__django-11138",
    "--split",
    "test",
    "--max_workers",
    "1",
    "--timeout",
    "1800",
    "--run_id",
    "vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9",
    "--namespace",
    "swebench",
    "--instance_image_tag",
    "vgar-w9-20261023",
    "--cache_level",
    "instance",
    "--clean",
    "False",
    "--force_rebuild",
    "False"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138",
  "started_utc": "2026-10-24T08:19:31.182987+00:00",
  "timeout_seconds": 3600,
  "status": "OK",
  "exit_code": 0
}
```

**15.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.django__django\\-11138\\.vgw9\\-d73bf5e0922c4c90a7b2a6d1fcb613a9$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138",
  "started_utc": "2026-10-24T08:19:31.112848+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**16.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/docker-info.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:20:00.836203+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**17.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-clean.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "status",
    "--porcelain",
    "--untracked-files=all"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:19:57.107227+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**18.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-head.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:19:57.043468+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**19.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-0.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:20:01.567663+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**20.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-1.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:20:01.654894+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**21.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-2.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:20:01.758757+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**22.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-help.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--help"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:19:58.951914+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**23.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-module.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import json,swebench; import swebench.harness.run_evaluation as m; print(json.dumps({\"version\":swebench.__version__,\"module\":m.__file__}))"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:19:57.181404+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**24.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/sdk-daemon.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import docker,json; c=docker.from_env(); print(json.dumps({\"ID\":c.info()[\"ID\"]})); c.close()"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after",
  "started_utc": "2026-10-24T08:20:01.314871+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**25.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.matplotlib__matplotlib\\-14623\\.vgw9\\-15a7b5bf50a8487b8e7abe65627f2598$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T08:21:24.064741+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**26.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--dataset_name",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json",
    "--predictions_path",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl",
    "--instance_ids",
    "matplotlib__matplotlib-14623",
    "--split",
    "test",
    "--max_workers",
    "1",
    "--timeout",
    "1800",
    "--run_id",
    "vgw9-15a7b5bf50a8487b8e7abe65627f2598",
    "--namespace",
    "swebench",
    "--instance_image_tag",
    "vgar-w9-20261023",
    "--cache_level",
    "instance",
    "--clean",
    "False",
    "--force_rebuild",
    "False"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T08:20:01.964471+00:00",
  "timeout_seconds": 3600,
  "status": "OK",
  "exit_code": 0
}
```

**27.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/sweb\\.eval\\.matplotlib__matplotlib\\-14623\\.vgw9\\-15a7b5bf50a8487b8e7abe65627f2598$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T08:20:01.905901+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**28.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/docker-info.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:28.035819+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**29.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-clean.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "status",
    "--porcelain",
    "--untracked-files=all"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:24.238692+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**30.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-head.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:24.147867+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**31.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-0.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:28.813418+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**32.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-1.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:28.888891+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**33.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-2.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:29.039752+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**34.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-help.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--help"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:26.100141+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**35.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-module.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import json,swebench; import swebench.harness.run_evaluation as m; print(json.dumps({\"version\":swebench.__version__,\"module\":m.__file__}))"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:24.311085+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**36.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/sdk-daemon.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import docker,json; c=docker.from_env(); print(json.dumps({\"ID\":c.info()[\"ID\"]})); c.close()"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after",
  "started_utc": "2026-10-24T08:21:28.516298+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**37.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/docker-info.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:53.999680+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**38.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-clean.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "status",
    "--porcelain",
    "--untracked-files=all"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:50.339607+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**39.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-head.json)

```json
{
  "argv": [
    "git",
    "-c",
    "safe.directory=/home/vgar/w9/swebench",
    "-C",
    "/home/vgar/w9/swebench",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:50.273279+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**40.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-0.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:54.691515+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**41.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-1.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:54.781972+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**42.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-2.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623:vgar-w9-20261023"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:54.869709+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**43.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-help.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-m",
    "swebench.harness.run_evaluation",
    "--help"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:52.329759+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**44.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-module.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import json,swebench; import swebench.harness.run_evaluation as m; print(json.dumps({\"version\":swebench.__version__,\"module\":m.__file__}))"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:50.431995+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**45.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/sdk-daemon.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import docker,json; c=docker.from_env(); print(json.dumps({\"ID\":c.info()[\"ID\"]})); c.close()"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight",
  "started_utc": "2026-10-24T08:17:54.453397+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

</details>

<details>
<summary>M1-W9-4 control directory cuối — 2 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\before-gold-host.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/before-gold-host.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "D:/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/resource_gate.ps1"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control",
  "started_utc": "2026-10-24T08:17:49.477175+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\before-preflight-host.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/before-preflight-host.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "D:/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/resource_gate.ps1"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control",
  "started_utc": "2026-10-24T08:17:42.776143+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

</details>

<details>
<summary>M1-W9-5 final collection run — 118 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after",
  "started_utc": "2026-10-24T09:28:57.430112+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398@sha256:4d7e922ae3b796147f85b37861f6dec5463001a964bd941ed6933109245fe69f"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after",
  "started_utc": "2026-10-24T09:28:57.979079+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**3.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-after.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:24.769451+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**4.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-before.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:23.874503+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**5.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-object.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "git",
    "-C",
    "/testbed",
    "cat-file",
    "-t",
    "6500928dc0e57be8f06d1162eacc3ba5e2eff692"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:23.675010+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**6.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-reset.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "git",
    "-C",
    "/testbed",
    "reset",
    "--hard",
    "6500928dc0e57be8f06d1162eacc3ba5e2eff692"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:24.087466+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**7.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-toplevel.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "--show-toplevel"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:23.434537+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**8.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before",
  "started_utc": "2026-10-24T09:28:21.905063+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**9.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398@sha256:4d7e922ae3b796147f85b37861f6dec5463001a964bd941ed6933109245fe69f"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before",
  "started_utc": "2026-10-24T09:28:22.605344+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**10.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-final.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-30bd45d44c254f17bbca6f2a686ed794$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup",
  "started_utc": "2026-10-24T09:28:57.369924+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**11.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-inspect.json)

```json
{
  "argv": ["docker", "container", "inspect", "78c037e5b6d4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup",
  "started_utc": "2026-10-24T09:28:57.025746+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**12.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-30bd45d44c254f17bbca6f2a686ed794$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup",
  "started_utc": "2026-10-24T09:28:56.941519+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**13.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-remove.json)

```json
{
  "argv": ["docker", "rm", "-f", "78c037e5b6d4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup",
  "started_utc": "2026-10-24T09:28:57.119086+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**14.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "--workdir",
    "/testbed",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1",
    "/opt/miniconda3/envs/testbed/bin/python",
    "-B",
    "/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.py",
    "/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.input.json",
    "/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:25.300611+00:00",
  "timeout_seconds": 300,
  "status": "OK",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**15.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-create.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-w95-30bd45d44c254f17bbca6f2a686ed794",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--label",
    "vgar.task=M1-W9-5",
    "--env",
    "PYTHONDONTWRITEBYTECODE=1",
    "--entrypoint",
    "/bin/sleep",
    "sha256:4d7e922ae3b796147f85b37861f6dec5463001a964bd941ed6933109245fe69f",
    "900"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:22.804446+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**16.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-inspect.json)

```json
{
  "argv": [
    "docker",
    "container",
    "inspect",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:23.344647+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**17.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-start.json)

```json
{
  "argv": [
    "docker",
    "start",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:22.991351+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**18.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-input.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/probe-input.json",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1:/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.input.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:25.180499+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**19.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-probe.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/src/vgar/evaluation/harness/collection_probe.py",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1:/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:25.005998+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**20.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-result.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "78c037e5b6d438fbf0e262a3d6475f8792cc5e756c72d6c321420ea57cbec1f1:/tmp/vgar-w95-30bd45d44c254f17bbca6f2a686ed794.result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/probe-result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:56.701957+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**21.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-w95-30bd45d44c254f17bbca6f2a686ed794$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398",
  "started_utc": "2026-10-24T09:28:22.731962+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**22.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-0\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before",
  "started_utc": "2026-10-24T09:28:21.246781+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**23.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-1\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before",
  "started_utc": "2026-10-24T09:28:58.482589+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**24.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-2\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before",
  "started_utc": "2026-10-24T09:29:05.246057+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**25.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-3\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before",
  "started_utc": "2026-10-24T09:29:21.391832+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**26.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-4\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before",
  "started_utc": "2026-10-24T09:29:39.517789+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**27.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after",
  "started_utc": "2026-10-24T09:29:04.600745+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**28.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138@sha256:811f9bf0ca067b334b574cd3589cdc989b350b2a24b68e1ddcd288fbb97d61f4"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after",
  "started_utc": "2026-10-24T09:29:05.088800+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**29.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-after.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:02.866590+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**30.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-before.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.787859+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**31.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-object.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "git",
    "-C",
    "/testbed",
    "cat-file",
    "-t",
    "c84b91b7603e488f7171fdff8f08368ef3d6b856"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.574783+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**32.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-reset.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "git",
    "-C",
    "/testbed",
    "reset",
    "--hard",
    "c84b91b7603e488f7171fdff8f08368ef3d6b856"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.969995+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**33.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-toplevel.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "--show-toplevel"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.350393+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**34.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before",
  "started_utc": "2026-10-24T09:28:59.186270+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**35.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138@sha256:811f9bf0ca067b334b574cd3589cdc989b350b2a24b68e1ddcd288fbb97d61f4"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before",
  "started_utc": "2026-10-24T09:28:59.713018+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**36.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-final.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-a95c937412064a76ab66918a5662072f$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup",
  "started_utc": "2026-10-24T09:29:04.543300+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**37.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-inspect.json)

```json
{
  "argv": ["docker", "container", "inspect", "0f99c96e4f22"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup",
  "started_utc": "2026-10-24T09:29:04.045532+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**38.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-a95c937412064a76ab66918a5662072f$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup",
  "started_utc": "2026-10-24T09:29:03.979765+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**39.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-remove.json)

```json
{
  "argv": ["docker", "rm", "-f", "0f99c96e4f22"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup",
  "started_utc": "2026-10-24T09:29:04.112689+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**40.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "--workdir",
    "/testbed",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828",
    "/opt/miniconda3/envs/testbed/bin/python",
    "-B",
    "/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.py",
    "/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.input.json",
    "/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:03.336696+00:00",
  "timeout_seconds": 300,
  "status": "OK",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**41.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-create.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-w95-a95c937412064a76ab66918a5662072f",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--label",
    "vgar.task=M1-W9-5",
    "--env",
    "PYTHONDONTWRITEBYTECODE=1",
    "--entrypoint",
    "/bin/sleep",
    "sha256:811f9bf0ca067b334b574cd3589cdc989b350b2a24b68e1ddcd288fbb97d61f4",
    "900"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:28:59.887202+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**42.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-inspect.json)

```json
{
  "argv": [
    "docker",
    "container",
    "inspect",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.265017+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**43.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-start.json)

```json
{
  "argv": [
    "docker",
    "start",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:00.029195+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**44.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-input.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/probe-input.json",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828:/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.input.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:03.223255+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**45.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-probe.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/src/vgar/evaluation/harness/collection_probe.py",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828:/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:03.072905+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**46.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-result.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "0f99c96e4f2293239bdd840be98106308257d1b4e9e8b4004e08f0b7112ee828:/tmp/vgar-w95-a95c937412064a76ab66918a5662072f.result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/probe-result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:29:03.886793+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**47.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-w95-a95c937412064a76ab66918a5662072f$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138",
  "started_utc": "2026-10-24T09:28:59.818976+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**48.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-0\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-0/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.astropy_1776_astropy-13398@sha256:4d7e922ae3b796147f85b37861f6dec5463001a964bd941ed6933109245fe69f"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-0",
  "started_utc": "2026-10-24T09:28:19.625171+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**49.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-1\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-1/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.django_1776_django-11138@sha256:811f9bf0ca067b334b574cd3589cdc989b350b2a24b68e1ddcd288fbb97d61f4"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-1",
  "started_utc": "2026-10-24T09:27:07.274153+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**50.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-2\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-2/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623@sha256:52cdd8ac0f4a8b05f40507d500680ec613092186310cbaf7895d1554e9d654dc"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-2",
  "started_utc": "2026-10-24T09:27:07.371090+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**51.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-3\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-3/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-3",
  "started_utc": "2026-10-24T09:27:07.471463+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**52.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-4\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-4/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-4551@sha256:f0f898ca4ef3fec27a985b1c2c6ca6ed3cb8fbf5be393e0bb6caf4aaf1512c8c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-4",
  "started_utc": "2026-10-24T09:28:21.117883+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**53.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-daemon\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-daemon/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-daemon",
  "started_utc": "2026-10-24T09:28:17.103540+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**54.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-resources\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before/windows-memory.json)

```json
{
  "argv": [
    "powershell.exe",
    "-NoProfile",
    "-Command",
    "$ErrorActionPreference=\"Stop\"; $o=Get-CimInstance Win32_OperatingSystem; @{available_memory_bytes=([int64]$o.FreePhysicalMemory*1024)} | ConvertTo-Json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before",
  "started_utc": "2026-10-24T09:28:16.343241+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**55.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after",
  "started_utc": "2026-10-24T09:29:20.558550+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**56.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623@sha256:52cdd8ac0f4a8b05f40507d500680ec613092186310cbaf7895d1554e9d654dc"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after",
  "started_utc": "2026-10-24T09:29:21.118669+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**57.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-after.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:08.835495+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**58.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-before.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:07.397034+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**59.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-object.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "git",
    "-C",
    "/testbed",
    "cat-file",
    "-t",
    "d65c9ca20ddf81ef91199e6d819f9d3506ef477c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:07.192745+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**60.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-reset.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "git",
    "-C",
    "/testbed",
    "reset",
    "--hard",
    "d65c9ca20ddf81ef91199e6d819f9d3506ef477c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:07.594504+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**61.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-toplevel.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "--show-toplevel"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:06.974669+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**62.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before",
  "started_utc": "2026-10-24T09:29:05.901520+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**63.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-14623@sha256:52cdd8ac0f4a8b05f40507d500680ec613092186310cbaf7895d1554e9d654dc"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before",
  "started_utc": "2026-10-24T09:29:06.356270+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**64.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-final.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-fe01312798794cb38fcc939bc64b7b31$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup",
  "started_utc": "2026-10-24T09:29:20.471258+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**65.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-inspect.json)

```json
{
  "argv": ["docker", "container", "inspect", "df22f4b90cdc"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup",
  "started_utc": "2026-10-24T09:29:20.009958+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**66.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-fe01312798794cb38fcc939bc64b7b31$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup",
  "started_utc": "2026-10-24T09:29:19.932564+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**67.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-remove.json)

```json
{
  "argv": ["docker", "rm", "-f", "df22f4b90cdc"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup",
  "started_utc": "2026-10-24T09:29:20.099823+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**68.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "--workdir",
    "/testbed",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c",
    "/opt/miniconda3/envs/testbed/bin/python",
    "-B",
    "/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.py",
    "/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.input.json",
    "/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:09.369664+00:00",
  "timeout_seconds": 300,
  "status": "OK",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**69.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-create.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-w95-fe01312798794cb38fcc939bc64b7b31",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--label",
    "vgar.task=M1-W9-5",
    "--env",
    "PYTHONDONTWRITEBYTECODE=1",
    "--entrypoint",
    "/bin/sleep",
    "sha256:52cdd8ac0f4a8b05f40507d500680ec613092186310cbaf7895d1554e9d654dc",
    "900"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:06.474506+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**70.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-inspect.json)

```json
{
  "argv": [
    "docker",
    "container",
    "inspect",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:06.897836+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**71.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-start.json)

```json
{
  "argv": [
    "docker",
    "start",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:06.619314+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**72.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-input.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/probe-input.json",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c:/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.input.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:09.261903+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**73.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-probe.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/src/vgar/evaluation/harness/collection_probe.py",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c:/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:09.086928+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**74.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-result.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "df22f4b90cdcf86d2ac6f4a3f9ae2dfd4b61fe4737d117c053b2b22dd44b2c1c:/tmp/vgar-w95-fe01312798794cb38fcc939bc64b7b31.result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/probe-result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:19.768674+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**75.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-w95-fe01312798794cb38fcc939bc64b7b31$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623",
  "started_utc": "2026-10-24T09:29:06.418467+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**76.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after",
  "started_utc": "2026-10-24T09:29:38.594085+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**77.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after",
  "started_utc": "2026-10-24T09:29:39.227251+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**78.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-after.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:25.168021+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**79.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-before.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:24.674526+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**80.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-object.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "git",
    "-C",
    "/testbed",
    "cat-file",
    "-t",
    "69c7e01e5167a3137c285cb50d1978252bb8bcbf"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:24.471040+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**81.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-reset.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "git",
    "-C",
    "/testbed",
    "reset",
    "--hard",
    "69c7e01e5167a3137c285cb50d1978252bb8bcbf"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:24.883033+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**82.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-toplevel.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "--show-toplevel"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:24.256630+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**83.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before",
  "started_utc": "2026-10-24T09:29:22.977525+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**84.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before",
  "started_utc": "2026-10-24T09:29:23.556710+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**85.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-final.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-80eaaf61de7c4182865ec18779f2dd7e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup",
  "started_utc": "2026-10-24T09:29:38.529455+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**86.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-inspect.json)

```json
{
  "argv": ["docker", "container", "inspect", "21404a404433"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup",
  "started_utc": "2026-10-24T09:29:38.218340+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**87.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-80eaaf61de7c4182865ec18779f2dd7e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup",
  "started_utc": "2026-10-24T09:29:38.114801+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**88.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-remove.json)

```json
{
  "argv": ["docker", "rm", "-f", "21404a404433"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup",
  "started_utc": "2026-10-24T09:29:38.316920+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**89.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "--workdir",
    "/testbed",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191",
    "/opt/miniconda3/envs/testbed/bin/python",
    "-B",
    "/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.py",
    "/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.input.json",
    "/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:25.715010+00:00",
  "timeout_seconds": 300,
  "status": "OK",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**90.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-create.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-w95-80eaaf61de7c4182865ec18779f2dd7e",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--label",
    "vgar.task=M1-W9-5",
    "--env",
    "PYTHONDONTWRITEBYTECODE=1",
    "--entrypoint",
    "/bin/sleep",
    "sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "900"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:23.774846+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**91.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-inspect.json)

```json
{
  "argv": [
    "docker",
    "container",
    "inspect",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:24.174178+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**92.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-start.json)

```json
{
  "argv": [
    "docker",
    "start",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:23.950383+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**93.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-input.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/probe-input.json",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191:/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.input.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:25.588969+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**94.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-probe.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/src/vgar/evaluation/harness/collection_probe.py",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191:/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:25.417911+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**95.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-result.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "21404a40443334766227d48309b7d7fa05f990f5de526dcb8e8d0ca05eb97191:/tmp/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e.result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/probe-result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:37.953188+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**96.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-w95-80eaaf61de7c4182865ec18779f2dd7e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305",
  "started_utc": "2026-10-24T09:29:23.681847+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**97.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after",
  "started_utc": "2026-10-24T09:29:46.701618+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**98.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-4551@sha256:f0f898ca4ef3fec27a985b1c2c6ca6ed3cb8fbf5be393e0bb6caf4aaf1512c8c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after",
  "started_utc": "2026-10-24T09:29:47.147148+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**99.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-after.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:42.519585+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**100.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-before.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "HEAD"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:41.922628+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**101.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-object.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "git",
    "-C",
    "/testbed",
    "cat-file",
    "-t",
    "99589b08de8c5a2c6cc61e13a37420a868c80599"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:41.714085+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**102.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-reset.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "git",
    "-C",
    "/testbed",
    "reset",
    "--hard",
    "99589b08de8c5a2c6cc61e13a37420a868c80599"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:42.107316+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**103.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-toplevel.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "git",
    "-C",
    "/testbed",
    "rev-parse",
    "--show-toplevel"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:41.466059+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**104.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/daemon.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before",
  "started_utc": "2026-10-24T09:29:40.181829+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**105.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/image.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-4551@sha256:f0f898ca4ef3fec27a985b1c2c6ca6ed3cb8fbf5be393e0bb6caf4aaf1512c8c"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before",
  "started_utc": "2026-10-24T09:29:40.777443+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**106.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-final.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-2a3b27966da9404fbfcabf24e996fbc5$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup",
  "started_utc": "2026-10-24T09:29:46.608219+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**107.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-inspect.json)

```json
{
  "argv": ["docker", "container", "inspect", "85d152e35c55"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup",
  "started_utc": "2026-10-24T09:29:46.279131+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**108.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-list.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar\\-w95\\-2a3b27966da9404fbfcabf24e996fbc5$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup",
  "started_utc": "2026-10-24T09:29:46.215207+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**109.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-remove.json)

```json
{
  "argv": ["docker", "rm", "-f", "85d152e35c55"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup",
  "started_utc": "2026-10-24T09:29:46.365800+00:00",
  "timeout_seconds": 30,
  "status": "OK",
  "exit_code": 0
}
```

**110.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "--workdir",
    "/testbed",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82",
    "/opt/miniconda3/envs/testbed/bin/python",
    "-B",
    "/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.py",
    "/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.input.json",
    "/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:42.955596+00:00",
  "timeout_seconds": 300,
  "status": "OK",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**111.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-create.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-w95-2a3b27966da9404fbfcabf24e996fbc5",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--label",
    "vgar.task=M1-W9-5",
    "--env",
    "PYTHONDONTWRITEBYTECODE=1",
    "--entrypoint",
    "/bin/sleep",
    "sha256:f0f898ca4ef3fec27a985b1c2c6ca6ed3cb8fbf5be393e0bb6caf4aaf1512c8c",
    "900"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:40.982752+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**112.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-inspect.json)

```json
{
  "argv": [
    "docker",
    "container",
    "inspect",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:41.383454+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**113.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-start.json)

```json
{
  "argv": [
    "docker",
    "start",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:41.143103+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**114.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-input.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/probe-input.json",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82:/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.input.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:42.866428+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**115.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-probe.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/src/vgar/evaluation/harness/collection_probe.py",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82:/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:42.716086+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**116.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-result.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "85d152e35c55b40c65667a5f7a80036a5d0de36327d93b8b0bf9284b005a1a82:/tmp/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5.result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/probe-result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:46.085036+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**117.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/ownership-before.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-w95-2a3b27966da9404fbfcabf24e996fbc5$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551",
  "started_utc": "2026-10-24T09:29:40.893957+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

**118.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\sdk-daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/sdk-daemon.json)

```json
{
  "argv": [
    "/home/vgar/w9/venvs/harness/bin/python",
    "-B",
    "-c",
    "import docker,json; c=docker.from_env(); print(json.dumps({\"ID\":c.info()[\"ID\"]})); c.close()"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2",
  "started_utc": "2026-10-24T09:28:19.144109+00:00",
  "timeout_seconds": 60,
  "status": "OK",
  "exit_code": 0
}
```

</details>

<details>
<summary>M2-W9-3 final smoke run — 190 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:41.625764+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:42.117918+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**3.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:42.262309+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**4.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1",
    "--label",
    "vgar.m2.operation=06b8252ffeea4729bcdadbfa8fc162a1",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:42.393233+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**5.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:42.587333+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**6.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control",
    "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:45.832285+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**7.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:46.106691+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**8.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:46.631754+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**9.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:03.898162+00:00",
  "timeout_seconds": 29.999991994000084,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**10.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "e470a4b4d519"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:04.114073+00:00",
  "timeout_seconds": 29.78935057199851,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**11.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "e470a4b4d519"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:04.224527+00:00",
  "timeout_seconds": 29.67747368399978,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**12.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:04.519858+00:00",
  "timeout_seconds": 29.384510754000075,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**13.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-06b8252ffeea4729bcdadbfa8fc162a1",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "ruff",
    "--version"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:46.106691+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**14.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:55.402434+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**15.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:57.237041+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**16.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:57.368619+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**17.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd",
    "--label",
    "vgar.m2.operation=229613e0b4c04ed495d6290daa4ffabd",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:57.488091+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**18.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:57.677381+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**19.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control",
    "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:00.463284+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**20.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:00.829302+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**21.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:01.492141+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**22.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:15.442905+00:00",
  "timeout_seconds": 29.99999334899985,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**23.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "ce518d38cd62"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:15.566661+00:00",
  "timeout_seconds": 29.88712384000064,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**24.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "ce518d38cd62"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:15.679986+00:00",
  "timeout_seconds": 29.76989581900125,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**25.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:15.908758+00:00",
  "timeout_seconds": 29.541156257000694,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**26.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-229613e0b4c04ed495d6290daa4ffabd",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": null,
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:00.829302+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**27.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:08.496009+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**28.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:09.145974+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**29.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2516346f4e56495b8da2c6e121ac249b$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:09.324353+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**30.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b",
    "--label",
    "vgar.m2.operation=2516346f4e56495b8da2c6e121ac249b",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:09.484750+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**31.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:09.686766+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**32.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control",
    "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:12.325719+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**33.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:12.589456+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**34.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:13.185296+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**35.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2516346f4e56495b8da2c6e121ac249b$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:24.751118+00:00",
  "timeout_seconds": 29.999992473998645,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**36.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "e86884bc5029"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:24.844947+00:00",
  "timeout_seconds": 29.906186058999083,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**37.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "e86884bc5029"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:25.011907+00:00",
  "timeout_seconds": 29.749376961999587,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**38.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2516346f4e56495b8da2c6e121ac249b$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:25.264077+00:00",
  "timeout_seconds": 29.498609895999834,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**39.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2516346f4e56495b8da2c6e121ac249b",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "mypy",
    "--config-file",
    "/vgar/mypy.ini",
    "--no-incremental",
    "--cache-dir",
    "/vgar/mypy-cache",
    "--output",
    "json",
    "--no-error-summary",
    "xarray/core/__init__.py",
    "xarray/core/accessor_dt.py",
    "xarray/core/accessor_str.py",
    "xarray/core/alignment.py",
    "xarray/core/arithmetic.py",
    "xarray/core/combine.py",
    "xarray/core/common.py",
    "xarray/core/computation.py",
    "xarray/core/concat.py",
    "xarray/core/coordinates.py",
    "xarray/core/dask_array_compat.py",
    "xarray/core/dask_array_ops.py",
    "xarray/core/dataarray.py",
    "xarray/core/dataset.py",
    "xarray/core/dtypes.py",
    "xarray/core/duck_array_ops.py",
    "xarray/core/extensions.py",
    "xarray/core/formatting.py",
    "xarray/core/groupby.py",
    "xarray/core/indexes.py",
    "xarray/core/indexing.py",
    "xarray/core/merge.py",
    "xarray/core/missing.py",
    "xarray/core/nanops.py",
    "xarray/core/npcompat.py",
    "xarray/core/nputils.py",
    "xarray/core/ops.py",
    "xarray/core/options.py",
    "xarray/core/pdcompat.py",
    "xarray/core/pycompat.py",
    "xarray/core/resample.py",
    "xarray/core/resample_cftime.py",
    "xarray/core/rolling.py",
    "xarray/core/rolling_exp.py",
    "xarray/core/utils.py",
    "xarray/core/variable.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:12.589456+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**40.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:31.905631+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**41.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:34.113147+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**42.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:34.245722+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**43.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e",
    "--label",
    "vgar.m2.operation=2640044ae2dd4ef4b2ced651865d724e",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:34.392398+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**44.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:34.604856+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**45.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:37.539638+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**46.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:37.954858+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**47.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:41.271575+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**48.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-008.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e:/vgar/nodeids.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/nodeids.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:41.413960+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**49.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-009.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e:/vgar/junit.xml",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/junit.xml"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:41.572604+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**50.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-010.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:56.472303+00:00",
  "timeout_seconds": 29.999991683998815,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**51.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-011.json)

```json
{
  "argv": ["docker", "container", "inspect", "9680e4ae5820"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:56.610830+00:00",
  "timeout_seconds": 29.859866115999466,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**52.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-012.json)

```json
{
  "argv": ["docker", "rm", "-f", "9680e4ae5820"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:56.732480+00:00",
  "timeout_seconds": 29.736295524000525,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**53.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-013.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:56.934403+00:00",
  "timeout_seconds": 29.534354584999164,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**54.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2640044ae2dd4ef4b2ced651865d724e",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-p",
    "vgar_pytest_reporter",
    "--m2-report-json=/vgar/nodeids.json",
    "--junitxml=/vgar/junit.xml",
    "--collect-only",
    "tests/vgar_w9_repro_quantile.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:41:37.954858+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**55.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:38.349714+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**56.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:40.379207+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**57.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:40.559120+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**58.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95",
    "--label",
    "vgar.m2.operation=2ec2be20a12e4e129fbae07153e1bc95",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:40.673199+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**59.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:40.827607+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**60.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:43.556636+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**61.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:43.839557+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**62.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:47.071995+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**63.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-008.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95:/vgar/nodeids.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/nodeids.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:47.262796+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**64.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-009.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95:/vgar/junit.xml",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/junit.xml"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:47.478432+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**65.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-010.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:04.498819+00:00",
  "timeout_seconds": 29.999992365001162,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**66.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-011.json)

```json
{
  "argv": ["docker", "container", "inspect", "3345a0a5a238"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:04.633133+00:00",
  "timeout_seconds": 29.875715074000254,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**67.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-012.json)

```json
{
  "argv": ["docker", "rm", "-f", "3345a0a5a238"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:04.752823+00:00",
  "timeout_seconds": 29.74913543399998,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**68.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-013.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:04.958543+00:00",
  "timeout_seconds": 29.541064199000175,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**69.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-2ec2be20a12e4e129fbae07153e1bc95",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-p",
    "vgar_pytest_reporter",
    "--m2-report-json=/vgar/nodeids.json",
    "--junitxml=/vgar/junit.xml",
    "--collect-only",
    "tests/vgar_w9_repro_quantile.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:46:43.839557+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**70.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:12.045461+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**71.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:12.800503+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**72.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-4333e25387a24d4aac2c32a331e0db58$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:12.950624+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**73.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58",
    "--label",
    "vgar.m2.operation=4333e25387a24d4aac2c32a331e0db58",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:13.077995+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**74.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:13.444620+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**75.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:16.348263+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**76.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:16.694427+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**77.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:21.081661+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**78.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-008.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58:/vgar/nodeids.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/nodeids.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:21.250280+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**79.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-009.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58:/vgar/junit.xml",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/junit.xml"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:21.435772+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**80.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-010.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-4333e25387a24d4aac2c32a331e0db58$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:35.978508+00:00",
  "timeout_seconds": 29.999992134000422,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**81.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-011.json)

```json
{
  "argv": ["docker", "container", "inspect", "8f609fb2c2a2"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:36.124864+00:00",
  "timeout_seconds": 29.852703558999565,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**82.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-012.json)

```json
{
  "argv": ["docker", "rm", "-f", "8f609fb2c2a2"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:36.277384+00:00",
  "timeout_seconds": 29.68852100100048,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**83.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-013.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-4333e25387a24d4aac2c32a331e0db58$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:36.509500+00:00",
  "timeout_seconds": 29.457779385000322,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**84.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-4333e25387a24d4aac2c32a331e0db58",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-p",
    "vgar_pytest_reporter",
    "--m2-report-json=/vgar/nodeids.json",
    "--junitxml=/vgar/junit.xml",
    "tests/vgar_w9_repro_quantile.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:16.694427+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**85.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:08.197211+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**86.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:08.784499+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**87.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:08.975947+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**88.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50",
    "--label",
    "vgar.m2.operation=8e4d1438d4954767af8c11f0857f3c50",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:09.086630+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**89.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:09.261952+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**90.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control",
    "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:11.595913+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**91.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:11.806954+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**92.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:12.443124+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**93.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:24.351703+00:00",
  "timeout_seconds": 29.99999184399894,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**94.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "6596c0d3eabc"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:24.465814+00:00",
  "timeout_seconds": 29.893077695998727,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**95.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "6596c0d3eabc"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:24.599006+00:00",
  "timeout_seconds": 29.759711059999972,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**96.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:24.866555+00:00",
  "timeout_seconds": 29.49934284399933,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**97.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-8e4d1438d4954767af8c11f0857f3c50",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "ruff",
    "check",
    "--config",
    "/vgar/ruff.toml",
    "--no-cache",
    "--no-fix",
    "--output-format",
    "json",
    "xarray/core/__init__.py",
    "xarray/core/accessor_dt.py",
    "xarray/core/accessor_str.py",
    "xarray/core/alignment.py",
    "xarray/core/arithmetic.py",
    "xarray/core/combine.py",
    "xarray/core/common.py",
    "xarray/core/computation.py",
    "xarray/core/concat.py",
    "xarray/core/coordinates.py",
    "xarray/core/dask_array_compat.py",
    "xarray/core/dask_array_ops.py",
    "xarray/core/dataarray.py",
    "xarray/core/dataset.py",
    "xarray/core/dtypes.py",
    "xarray/core/duck_array_ops.py",
    "xarray/core/extensions.py",
    "xarray/core/formatting.py",
    "xarray/core/groupby.py",
    "xarray/core/indexes.py",
    "xarray/core/indexing.py",
    "xarray/core/merge.py",
    "xarray/core/missing.py",
    "xarray/core/nanops.py",
    "xarray/core/npcompat.py",
    "xarray/core/nputils.py",
    "xarray/core/ops.py",
    "xarray/core/options.py",
    "xarray/core/pdcompat.py",
    "xarray/core/pycompat.py",
    "xarray/core/resample.py",
    "xarray/core/resample_cftime.py",
    "xarray/core/rolling.py",
    "xarray/core/rolling_exp.py",
    "xarray/core/utils.py",
    "xarray/core/variable.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:50:11.806954+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**98.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:22.007621+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**99.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:24.660011+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**100.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:24.837637+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**101.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90",
    "--label",
    "vgar.m2.operation=a07907c5f49f4dbcb34a0d37807c8f90",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:24.950693+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**102.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:25.107396+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**103.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control",
    "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:27.289469+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**104.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:27.587999+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**105.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:28.298742+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**106.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:46.142224+00:00",
  "timeout_seconds": 29.999992140999893,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**107.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "ba7985cbd689"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:46.262127+00:00",
  "timeout_seconds": 29.883020759998544,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**108.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "ba7985cbd689"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:46.376186+00:00",
  "timeout_seconds": 29.765205230998617,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**109.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:46.599737+00:00",
  "timeout_seconds": 29.549427554999056,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**110.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-a07907c5f49f4dbcb34a0d37807c8f90",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "ruff",
    "check",
    "--config",
    "/vgar/ruff.toml",
    "--no-cache",
    "--no-fix",
    "--output-format",
    "json",
    "xarray/core/__init__.py",
    "xarray/core/accessor_dt.py",
    "xarray/core/accessor_str.py",
    "xarray/core/alignment.py",
    "xarray/core/arithmetic.py",
    "xarray/core/combine.py",
    "xarray/core/common.py",
    "xarray/core/computation.py",
    "xarray/core/concat.py",
    "xarray/core/coordinates.py",
    "xarray/core/dask_array_compat.py",
    "xarray/core/dask_array_ops.py",
    "xarray/core/dataarray.py",
    "xarray/core/dataset.py",
    "xarray/core/dtypes.py",
    "xarray/core/duck_array_ops.py",
    "xarray/core/extensions.py",
    "xarray/core/formatting.py",
    "xarray/core/groupby.py",
    "xarray/core/indexes.py",
    "xarray/core/indexing.py",
    "xarray/core/merge.py",
    "xarray/core/missing.py",
    "xarray/core/nanops.py",
    "xarray/core/npcompat.py",
    "xarray/core/nputils.py",
    "xarray/core/ops.py",
    "xarray/core/options.py",
    "xarray/core/pdcompat.py",
    "xarray/core/pycompat.py",
    "xarray/core/resample.py",
    "xarray/core/resample_cftime.py",
    "xarray/core/rolling.py",
    "xarray/core/rolling_exp.py",
    "xarray/core/utils.py",
    "xarray/core/variable.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:45:27.587999+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**111.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:05.531011+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**112.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:06.156331+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**113.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:06.325539+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**114.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a",
    "--label",
    "vgar.m2.operation=a8238dd3b72f4e8ab9ec81cb1bfa491a",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:06.450888+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**115.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:06.631596+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**116.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control",
    "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:09.593819+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**117.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:09.932841+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**118.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:10.490206+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**119.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:27.023418+00:00",
  "timeout_seconds": 29.999992633000147,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**120.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "910be642f4b4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:27.132814+00:00",
  "timeout_seconds": 29.89458464100062,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**121.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "910be642f4b4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:27.240406+00:00",
  "timeout_seconds": 29.78319032500076,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**122.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:27.460059+00:00",
  "timeout_seconds": 29.582219337000424,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**123.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-a8238dd3b72f4e8ab9ec81cb1bfa491a",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "mypy",
    "--config-file",
    "/vgar/mypy.ini",
    "--no-incremental",
    "--cache-dir",
    "/vgar/mypy-cache",
    "--output",
    "json",
    "--no-error-summary",
    "xarray/core/__init__.py",
    "xarray/core/accessor_dt.py",
    "xarray/core/accessor_str.py",
    "xarray/core/alignment.py",
    "xarray/core/arithmetic.py",
    "xarray/core/combine.py",
    "xarray/core/common.py",
    "xarray/core/computation.py",
    "xarray/core/concat.py",
    "xarray/core/coordinates.py",
    "xarray/core/dask_array_compat.py",
    "xarray/core/dask_array_ops.py",
    "xarray/core/dataarray.py",
    "xarray/core/dataset.py",
    "xarray/core/dtypes.py",
    "xarray/core/duck_array_ops.py",
    "xarray/core/extensions.py",
    "xarray/core/formatting.py",
    "xarray/core/groupby.py",
    "xarray/core/indexes.py",
    "xarray/core/indexing.py",
    "xarray/core/merge.py",
    "xarray/core/missing.py",
    "xarray/core/nanops.py",
    "xarray/core/npcompat.py",
    "xarray/core/nputils.py",
    "xarray/core/ops.py",
    "xarray/core/options.py",
    "xarray/core/pdcompat.py",
    "xarray/core/pycompat.py",
    "xarray/core/resample.py",
    "xarray/core/resample_cftime.py",
    "xarray/core/rolling.py",
    "xarray/core/rolling_exp.py",
    "xarray/core/utils.py",
    "xarray/core/variable.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:44:09.932841+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**124.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:20.399796+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**125.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:20.894744+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**126.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b504d4effcc341ca979405490af99531$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:21.086206+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**127.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-b504d4effcc341ca979405490af99531",
    "--label",
    "vgar.m2.operation=b504d4effcc341ca979405490af99531",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:21.234735+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**128.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-b504d4effcc341ca979405490af99531"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:21.406627+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**129.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control",
    "vgar-m2w93-b504d4effcc341ca979405490af99531:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:24.587523+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**130.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-b504d4effcc341ca979405490af99531",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:24.885211+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**131.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-b504d4effcc341ca979405490af99531:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:26.931534+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**132.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-008.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-b504d4effcc341ca979405490af99531:/vgar/nodeids.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/nodeids.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:27.092067+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**133.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-009.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-b504d4effcc341ca979405490af99531:/vgar/junit.xml",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/junit.xml"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:27.293227+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**134.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-010.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b504d4effcc341ca979405490af99531$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:43.963142+00:00",
  "timeout_seconds": 29.99999075999949,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**135.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-011.json)

```json
{
  "argv": ["docker", "container", "inspect", "73a0ea43a34c"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:44.114091+00:00",
  "timeout_seconds": 29.852317279001,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**136.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-012.json)

```json
{
  "argv": ["docker", "rm", "-f", "73a0ea43a34c"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:44.294086+00:00",
  "timeout_seconds": 29.68111540999962,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**137.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-013.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b504d4effcc341ca979405490af99531$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:44.557766+00:00",
  "timeout_seconds": 29.407626391999656,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**138.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-b504d4effcc341ca979405490af99531",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-p",
    "vgar_pytest_reporter",
    "--m2-report-json=/vgar/nodeids.json",
    "--junitxml=/vgar/junit.xml",
    "tests/vgar_w9_repro_quantile.py"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:47:24.885211+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**139.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:40.012240+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**140.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:40.571647+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**141.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b91807cc234c45bf8a714f3951047cfe$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:40.752858+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**142.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe",
    "--label",
    "vgar.m2.operation=b91807cc234c45bf8a714f3951047cfe",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:40.872768+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**143.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:41.113102+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**144.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control",
    "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:43.240622+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**145.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:43.891369+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**146.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:44.487125+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**147.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b91807cc234c45bf8a714f3951047cfe$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:55.677858+00:00",
  "timeout_seconds": 29.999994112000422,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**148.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "5925d89094ea"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:55.794843+00:00",
  "timeout_seconds": 29.887539684999865,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**149.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "5925d89094ea"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:55.914152+00:00",
  "timeout_seconds": 29.773007881000012,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**150.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-b91807cc234c45bf8a714f3951047cfe$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:56.193932+00:00",
  "timeout_seconds": 29.534093472000677,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**151.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-b91807cc234c45bf8a714f3951047cfe",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "mypy",
    "--version"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:43.891369+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**152.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:39.114993+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**153.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:39.606294+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**154.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-c3289d5328a247938690467c704d1da4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:39.765428+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**155.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-c3289d5328a247938690467c704d1da4",
    "--label",
    "vgar.m2.operation=c3289d5328a247938690467c704d1da4",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:39.905115+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**156.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-c3289d5328a247938690467c704d1da4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:40.147304+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**157.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control",
    "vgar-m2w93-c3289d5328a247938690467c704d1da4:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:42.506239+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**158.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-c3289d5328a247938690467c704d1da4",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:42.788348+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**159.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-c3289d5328a247938690467c704d1da4:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:43.398805+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**160.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-c3289d5328a247938690467c704d1da4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:55.427193+00:00",
  "timeout_seconds": 29.999994396999682,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**161.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "ecbdfb24f2b2"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:55.519839+00:00",
  "timeout_seconds": 29.90842977899956,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**162.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "ecbdfb24f2b2"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:55.592004+00:00",
  "timeout_seconds": 29.843556558000273,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**163.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-c3289d5328a247938690467c704d1da4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:55.776443+00:00",
  "timeout_seconds": 29.65995155699966,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**164.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-c3289d5328a247938690467c704d1da4",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "ruff",
    "--version"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:49:42.788348+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**165.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:31.169663+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**166.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:31.734498+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**167.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:31.896573+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**168.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c",
    "--label",
    "vgar.m2.operation=d70f06f9beb844d3ab78a3f63b5f6d8c",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:32.028438+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**169.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:32.433130+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**170.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control",
    "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:35.107995+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**171.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:35.443873+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**172.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:35.972215+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**173.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:49.754373+00:00",
  "timeout_seconds": 29.99999265200131,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**174.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "11e47a242e88"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:37.087306+00:00",
  "timeout_seconds": 29.896601346001262,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**175.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "11e47a242e88"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:42:37.193091+00:00",
  "timeout_seconds": 29.77953100800005,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**176.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:50.947334+00:00",
  "timeout_seconds": 29.560316147000776,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**177.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-d70f06f9beb844d3ab78a3f63b5f6d8c",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": [
    "/opt/miniconda3/envs/testbed/bin/python",
    "-m",
    "mypy",
    "--version"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:43:35.443873+00:00",
  "timeout_seconds": 60,
  "status": "FAIL",
  "exit_code": 1,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**178.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-000.json)

```json
{
  "argv": ["docker", "info", "--format", "{{json .}}"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:09.227640+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**179.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-001.json)

```json
{
  "argv": [
    "docker",
    "image",
    "inspect",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:09.817082+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**180.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-002.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:09.986627+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**181.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-003.json)

```json
{
  "argv": [
    "docker",
    "create",
    "--name",
    "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4",
    "--label",
    "vgar.m2.operation=efa21860246a47e8bd694b05e2b71ba4",
    "--label",
    "vgar.m2.admission=sha256:b034e2af874e04f46fec4c170c420e927c25a3ea5c4ce23e02163a013c6fb305",
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--entrypoint",
    "/bin/sleep",
    "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:0e234daddf9a42b85a77ba0436f3fcbad90759921c978b127dff90d55cba0f89",
    "infinity"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:10.105118+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**182.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-004.json)

```json
{
  "argv": ["docker", "start", "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:10.342280+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**183.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-005.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control",
    "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4:/vgar"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:13.626926+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**184.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-006.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:13.973771+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**185.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-007.json)

```json
{
  "argv": [
    "docker",
    "cp",
    "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4:/vgar/result.json",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/target_result.json"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:14.717422+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**186.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-008.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:27.203998+00:00",
  "timeout_seconds": 29.999992658000338,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**187.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-009.json)

```json
{
  "argv": ["docker", "container", "inspect", "a24ab6141045"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:27.314561+00:00",
  "timeout_seconds": 29.899168645999453,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**188.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-010.json)

```json
{
  "argv": ["docker", "rm", "-f", "a24ab6141045"],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:27.444264+00:00",
  "timeout_seconds": 29.771297237999534,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**189.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-011.json)

```json
{
  "argv": [
    "docker",
    "ps",
    "-aq",
    "--filter",
    "name=^/vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4$"
  ],
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:27.699115+00:00",
  "timeout_seconds": 29.518729440000243,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

**190.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/command.json)

```json
{
  "argv": [
    "docker",
    "exec",
    "-w",
    "/testbed",
    "vgar-m2w93-efa21860246a47e8bd694b05e2b71ba4",
    "/opt/miniconda3/envs/testbed/bin/python",
    "/vgar/docker_probe.py",
    "/vgar/config.json",
    "/vgar/result.json"
  ],
  "target_argv": null,
  "cwd": "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/private-05/m2-w78-9hycckkk/worktree",
  "started_utc": "2026-10-24T10:48:13.973771+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0,
  "timed_out": false,
  "output_truncated": false,
  "complete": true
}
```

</details>

<details>
<summary>Các lệnh pytest/lint lịch sử ở ba thư mục triển khai (giữ RED/lỗi/checkpoint cũ) — 80 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_m1_handoff.py",
    "tests/test_impact.py",
    "tests/m2/test_dataset_split.py",
    "tests/m2/test_retrieval_evaluation.py",
    "tests/m2/test_retrieval_scoring.py",
    "tests/m2/w910",
    "tests/m2/w78/test_w78_evidence.py",
    "tests/m2/w78/test_w78_evidence_bundle.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w94-regression-20261024-0814",
    "--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:50.182414+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_m1_handoff.py",
    "tests/test_impact.py",
    "tests/m2/test_dataset_split.py",
    "tests/m2/test_retrieval_evaluation.py",
    "tests/m2/test_retrieval_scoring.py",
    "tests/m2/w910",
    "tests/m2/w78/test_w78_evidence.py",
    "tests/m2/w78/test_w78_evidence_bundle.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w94-regression-20261024-0814",
    "--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:50.182414+00:00",
  "timeout_seconds": 900,
  "status": "RUNNING",
  "exit_code": null
}
```

**3.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_06.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/official.py",
    "tests/test_official_harness.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:13:35.285974+00:00",
  "timeout_seconds": 90,
  "status": "ERROR",
  "exit_code": 1
}
```

**4.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_06.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/official.py",
    "tests/test_official_harness.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:13:35.285974+00:00",
  "timeout_seconds": 90,
  "status": "RUNNING",
  "exit_code": null
}
```

**5.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_changed_scope_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_changed_scope_06.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--ignore",
    "E741",
    "src/vgar/evaluation/harness/official.py",
    "tests/test_official_harness.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:15:51.948687+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0
}
```

**6.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_changed_scope_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_changed_scope_06.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--ignore",
    "E741",
    "src/vgar/evaluation/harness/official.py",
    "tests/test_official_harness.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:15:51.948687+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**7.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:03.363845+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**8.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:03.363845+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**9.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_06.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_official_harness.py",
    "-k",
    "pinned_upstream_run_evaluation_directory",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:10:47.659902+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**10.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_06.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_official_harness.py",
    "-k",
    "pinned_upstream_run_evaluation_directory",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:10:47.659902+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**11.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_linux_06.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py",
    "-k",
    "pinned_upstream_run_evaluation_directory",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/red_linux.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:11:36.674941+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**12.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_linux_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_linux_06.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py",
    "-k",
    "pinned_upstream_run_evaluation_directory",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/red_linux.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:11:36.674941+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**13.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:24:02.660819+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**14.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:24:02.660819+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**15.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "base_before_probe or missing_base_commit",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:23:03.688682+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**16.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "base_before_probe or missing_base_commit",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:23:03.688682+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**17.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:49:46.963237+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**18.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:49:46.963237+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**19.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:48:33.547498+00:00",
  "timeout_seconds": 180,
  "status": "ERROR",
  "exit_code": 1
}
```

**20.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:48:33.547498+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**21.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:10:41.240775+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**22.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:10:41.240775+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**23.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "project_default_scope",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:09:51.902011+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**24.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "project_default_scope",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:09:51.902011+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**25.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:55:04.039416+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**26.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:55:04.039416+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**27.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:52:45.402193+00:00",
  "timeout_seconds": 180,
  "status": "ERROR",
  "exit_code": 1
}
```

**28.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:52:45.402193+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**29.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\full_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/full_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/full_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:02:06.008644+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**30.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\full_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/full_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/full_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:02:06.008644+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**31.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:59:14.985877+00:00",
  "timeout_seconds": 90,
  "status": "PASS",
  "exit_code": 0
}
```

**32.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:59:14.985877+00:00",
  "timeout_seconds": 90,
  "status": "RUNNING",
  "exit_code": null
}
```

**33.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_base_fix.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:25:10.322401+00:00",
  "timeout_seconds": 90,
  "status": "PASS",
  "exit_code": 0
}
```

**34.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_base_fix.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_base_fix.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:25:10.322401+00:00",
  "timeout_seconds": 90,
  "status": "RUNNING",
  "exit_code": null
}
```

**35.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_final_candidate.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_final_candidate.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:02:11.129354+00:00",
  "timeout_seconds": 90,
  "status": "PASS",
  "exit_code": 0
}
```

**36.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_final_candidate.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_final_candidate.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "src/vgar/evaluation/harness/task_env.py",
    "src/vgar/evaluation/harness/collection_probe.py",
    "scripts/prepare_task_env.py",
    "tests/test_task_env.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:02:11.129354+00:00",
  "timeout_seconds": 90,
  "status": "RUNNING",
  "exit_code": null
}
```

**37.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\output_bound_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "collection_capture",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:01:30.776675+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**38.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\output_bound_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-k",
    "collection_capture",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:01:30.776675+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**39.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-regression-20261024-0905",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:04:58.102048+00:00",
  "timeout_seconds": 900,
  "status": "ERROR",
  "exit_code": 1
}
```

**40.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-regression-20261024-0905",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:04:58.102048+00:00",
  "timeout_seconds": 900,
  "status": "RUNNING",
  "exit_code": null
}
```

**41.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-base-fix-20261024-0924",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:25:10.677391+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**42.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-base-fix-20261024-0924",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:25:10.677391+00:00",
  "timeout_seconds": 900,
  "status": "RUNNING",
  "exit_code": null
}
```

**43.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_final_candidate.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-regression-20261024-0910",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:06:40.261779+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**44.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_final_candidate.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-regression-20261024-0910",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:06:40.261779+00:00",
  "timeout_seconds": 900,
  "status": "RUNNING",
  "exit_code": null
}
```

**45.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_frozen.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-final-20261024-0916",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:11:42.453528+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**46.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_frozen.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-final-20261024-0916",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:11:42.453528+00:00",
  "timeout_seconds": 900,
  "status": "RUNNING",
  "exit_code": null
}
```

**47.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:59:10.577297+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**48.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:59:10.577297+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**49.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:58:24.621303+00:00",
  "timeout_seconds": 180,
  "status": "ERROR",
  "exit_code": 1
}
```

**50.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.start.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:58:24.621303+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**51.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_green_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-green-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:00:27.484502+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**52.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_green_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-green-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:00:27.484502+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**53.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-red-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:58:52.523653+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**54.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-red-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:58:52.523653+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**55.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_green_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-bridge-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:05:21.165957+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**56.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_green_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-bridge-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:05:21.165957+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**57.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-bridge-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:03:20.982105+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**58.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-bridge-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:03:20.982105+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**59.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_green.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-drift-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:12:11.704005+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**60.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_green.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-drift-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:12:11.704005+00:00",
  "timeout_seconds": 180,
  "status": "RUNNING",
  "exit_code": null
}
```

**61.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "source_drift_can or resume_revalidates",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-drift-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:11:18.601883+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**62.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "source_drift_can or resume_revalidates",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-drift-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:11:18.601883+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**63.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w78",
    "tests/m2/w910",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-full-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:12:59.783627+00:00",
  "timeout_seconds": 1500,
  "status": "PASS",
  "exit_code": 0
}
```

**64.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w78",
    "tests/m2/w910",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-full-01",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:12:59.783627+00:00",
  "timeout_seconds": 1500,
  "status": "RUNNING",
  "exit_code": null
}
```

**65.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w78",
    "tests/m2/w910",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-full-final",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:39:59.249490+00:00",
  "timeout_seconds": 1500,
  "status": "PASS",
  "exit_code": 0
}
```

**66.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w78",
    "tests/m2/w910",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-full-final",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:39:59.249490+00:00",
  "timeout_seconds": 1500,
  "status": "RUNNING",
  "exit_code": null
}
```

**67.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_modified.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_modified.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "--select",
    "E9,F",
    "src/vgar/repair/contracts.py",
    "src/vgar/repair/pipeline.py",
    "src/vgar/repair/session.py",
    "src/vgar/repair/static_checks.py",
    "src/vgar/repair/verification.py",
    "src/vgar/repair/workspace.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:41:28.484672+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0
}
```

**68.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_modified.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_modified.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "--select",
    "E9,F",
    "src/vgar/repair/contracts.py",
    "src/vgar/repair/pipeline.py",
    "src/vgar/repair/session.py",
    "src/vgar/repair/static_checks.py",
    "src/vgar/repair/verification.py",
    "src/vgar/repair/workspace.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:41:28.484672+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**69.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_new.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_new.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:41:28.194515+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0
}
```

**70.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_new.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_new.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:41:28.194515+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**71.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_modified_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_modified_01.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "--select",
    "E9,F",
    "src/vgar/repair/contracts.py",
    "src/vgar/repair/pipeline.py",
    "src/vgar/repair/session.py",
    "src/vgar/repair/static_checks.py",
    "src/vgar/repair/verification.py",
    "src/vgar/repair/workspace.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:13:13.829722+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0
}
```

**72.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_modified_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_modified_01.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "--select",
    "E9,F",
    "src/vgar/repair/contracts.py",
    "src/vgar/repair/pipeline.py",
    "src/vgar/repair/session.py",
    "src/vgar/repair/static_checks.py",
    "src/vgar/repair/verification.py",
    "src/vgar/repair/workspace.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:13:13.829722+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**73.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_01.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:10:23.411930+00:00",
  "timeout_seconds": 60,
  "status": "ERROR",
  "exit_code": 1
}
```

**74.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_01.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:10:23.411930+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**75.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_02.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_02.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:13:13.551417+00:00",
  "timeout_seconds": 60,
  "status": "PASS",
  "exit_code": 0
}
```

**76.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_02.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_02.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "ruff",
    "check",
    "--no-cache",
    "src/vgar/repair/admission.py",
    "src/vgar/repair/docker_executor.py",
    "src/vgar/repair/docker_probe.py",
    "tests/m2/w910/test_admission.py",
    "tests/m2/w910/test_docker_admission.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:13:13.551417+00:00",
  "timeout_seconds": 60,
  "status": "RUNNING",
  "exit_code": null
}
```

**77.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_green.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "replacement",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-r1-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:38:28.009835+00:00",
  "timeout_seconds": 120,
  "status": "PASS",
  "exit_code": 0
}
```

**78.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_green.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "replacement",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-r1-green",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:38:28.009835+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

**79.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "replacement",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-r1-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:27:24.254855+00:00",
  "timeout_seconds": 120,
  "status": "ERROR",
  "exit_code": 1
}
```

**80.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.start.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w910/test_admission.py",
    "-k",
    "replacement",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-r1-red",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:27:24.254855+00:00",
  "timeout_seconds": 120,
  "status": "RUNNING",
  "exit_code": null
}
```

</details>

<details>
<summary>Outer/gate receipts đã dùng ở báo cáo — 8 process receipts</summary>

**1.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/run_gold_07.py"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:16:28.092772+00:00",
  "timeout_seconds": 12000,
  "status": "PASS",
  "exit_code": 0
}
```

**2.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_official_harness.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:03.363845+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**3.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_m1_handoff.py",
    "tests/test_impact.py",
    "tests/m2/test_dataset_split.py",
    "tests/m2/test_retrieval_evaluation.py",
    "tests/m2/test_retrieval_scoring.py",
    "tests/m2/w910",
    "tests/m2/w78/test_w78_evidence.py",
    "tests/m2/w78/test_w78_evidence_bundle.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w94-regression-20261024-0814",
    "--junitxml=results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T08:12:50.182414+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**4.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/run_local_02.py",
    "collect"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:27:02.170125+00:00",
  "timeout_seconds": 3000,
  "status": "PASS",
  "exit_code": 0
}
```

**5.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "-m",
    "pytest",
    "/mnt/d/Project/CAPSTONES/VGAR/tests/test_task_env.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--junitxml=/mnt/d/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:24:02.660819+00:00",
  "timeout_seconds": 180,
  "status": "PASS",
  "exit_code": 0
}
```

**6.** [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/test_task_env.py",
    "tests/test_official_harness.py",
    "tests/test_w9_bm25_handoff.py",
    "tests/test_w9_pilot_bundles.py",
    "tests/test_w9_bundle.py",
    "tests/test_m1_handoff.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--basetemp=D:/vgar-w95-base-fix-20261024-0924",
    "--junitxml=results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T09:25:10.677391+00:00",
  "timeout_seconds": 900,
  "status": "PASS",
  "exit_code": 0
}
```

**7.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.json)

```json
{
  "argv": [
    "wsl.exe",
    "--distribution",
    "VGAR-Harness-W9",
    "--user",
    "root",
    "--exec",
    "env",
    "PYTHONPATH=/mnt/d/Project/CAPSTONES/VGAR/src",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    "/home/vgar/w9/venvs/controller/bin/python",
    "-B",
    "/mnt/d/Project/CAPSTONES/VGAR/results/m2/w9/m2-w9-3/20261024-docker-admission/run_smoke.py",
    "05"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:38:48.347154+00:00",
  "timeout_seconds": 1900,
  "status": "PASS",
  "exit_code": 0
}
```

**8.** [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.json)

```json
{
  "argv": [
    "D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe",
    "-B",
    "-m",
    "pytest",
    "tests/m2/w78",
    "tests/m2/w910",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp=D:/vgar-m2w93-full-final",
    "--junitxml=results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml"
  ],
  "cwd": "D:\\Project\\CAPSTONES\\VGAR",
  "started_utc": "2026-10-24T10:39:59.249490+00:00",
  "timeout_seconds": 1500,
  "status": "PASS",
  "exit_code": 0
}
```

</details>

Tổng số process receipts đã chép: **443**. Số này gồm command wrappers/driver/CLI/cleanup và duplicate evidence cho cùng operation, **không phải số benchmark attempts hay số tests**.

## Phụ lục B — Nguyên văn ba helper lịch sử (chỉ đọc)

Helper được chép để thấy toàn bộ Python orchestration/API calls và nhánh kiểm tra. Nội dung giữ nguyên, bao gồm paths fixed, assertions lịch sử và nhánh bounded cache reclaim cũ. Không coi đây là script mới được phép thực thi. Các subprocess argv của final runs đã nằm ở phụ lục A.

<details>
<summary>run_gold_07.py</summary>

Nguồn: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\run_gold_07.py](../results/m1/w9/m1-w9-4/20261023-local-qualification/run_gold_07.py)

```python
import json, os, re, shutil, sys, time, traceback
from pathlib import Path
sys.path.insert(0,'/mnt/d/Project/CAPSTONES/VGAR/src')
from vgar.evaluation.harness.official import invoke, _campaign
from vgar.evaluation.harness.gold_inputs import write_json, GOLD_IDS
from vgar.evaluation.retrieval.evidence import sha256
root=Path('/mnt/d/Project/CAPSTONES/VGAR')
here=root/'results/m1/w9/m1-w9-4/20261023-local-qualification'
out=here/'gold_07_control'
out.mkdir(exist_ok=False)
env=os.environ.copy();env.pop('DOCKER_CONTEXT',None);env['DOCKER_HOST']='unix:///var/run/docker.sock';env['PYTHONDONTWRITEBYTECODE']='1'
def call(argv,name,timeout=60,required=True):
    r=invoke(argv,out,name,timeout=timeout,env=env)
    print(name,r['status'],r['exit_code'],round(r['duration_seconds'],2),flush=True)
    if required and r['status']!='OK': raise RuntimeError(name+': '+r['stderr'][-1500:])
    return r

def reclaim_cache(label,host_command):
    prior=list(here.glob('cache-reclaim-06-*.reservation.json'))
    if len(prior)>=3: raise RuntimeError('User-approved cache reclaim limit exhausted')
    n=len(prior)+1
    assert not call(['docker','ps','-q'],label+'-reclaim-no-running-containers')['stdout'].strip(), 'Running containers: no cache reclaim'
    before=Path('/proc/meminfo').read_text()
    write_json(here/('cache-reclaim-06-'+str(n)+'.reservation.json'),{'operation':'sync then drop_caches=1','scope':'WSL page cache; no settings/restart/data deletion','approved_maximum':3,'reason':label,'meminfo_before':before})
    call(['sync'],label+'-reclaim-sync',60)
    Path('/proc/sys/vm/drop_caches').write_text('1\n')
    write_json(here/('cache-reclaim-06-'+str(n)+'.result.json'),{'status':'APPLIED','meminfo_after':Path('/proc/meminfo').read_text()})
    for attempt in range(11):
        if attempt: time.sleep(3)
        result=call(host_command,label+'-host-after-reclaim-'+str(attempt),required=False)
        if result['status']=='OK': return result
        if 'Windows available RAM below4GiB' not in result['stderr']: break
    raise RuntimeError('Resource gate remains unmet after one cache reclaim; do not repeat blindly')


def gate(label):
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File','D:/Project/CAPSTONES/VGAR/results/m1/w9/m1-w9-4/20261023-local-qualification/resource_gate.ps1']
    host=call(command,label+'-host',required=False)
    if host['status']!='OK':
        if 'Windows available RAM below4GiB' not in host['stderr']: raise RuntimeError('Non-RAM resource gate failure')
        host=reclaim_cache(label,command)
    available=int(re.search(r'^MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)[1])*1024
    state={'linux_available_bytes':available,'C_free':shutil.disk_usage('/mnt/c').free,'D_free':shutil.disk_usage('/mnt/d').free}
    write_json(out/(label+'-linux.json'),state)
    assert available>=4*1024**3 and state['C_free']>=10*1024**3 and state['D_free']>=20*1024**3,state
    return state

try:
    runtime=json.loads((here/'runtime_07/result.json').read_text())
    assert runtime['status']=='READY'
    profile=root/'results/m1/w9/m1-w9-4/runtime/qualified-profile.json'
    manifest=root/'configs/m1/w9_pilot_manifest.json'
    hashes={'profile':sha256(profile.read_bytes()),'manifest':sha256(manifest.read_bytes())}
    gate('before-preflight')
    pre=_campaign(manifest,profile,GOLD_IDS,root/'results/m1/w9/m1-w9-4/ready-preflight-runs',execute=False)
    assert pre['status']=='NOT_RUN' and pre['complete'] and pre['preflight']['ready']
    assert len(pre['tasks'])==3 and all(t['status']=='NOT_RUN' for t in pre['tasks'])
    write_json(out/'preflight-summary.json',{'run_id':pre['run_id'],'status':pre['status'],'hashes':hashes,'tasks':[{k:t.get(k) for k in ('instance_id','status','reason')} for t in pre['tasks']]})
    gate('before-gold')
    gold_root=root/'results/m1/w9/m1-w9-4/gold-runs'
    previous=list(gold_root.glob('*/run_record.json'))
    assert len(previous)==1, 'Expected exactly one terminal campaign before justified second campaign'
    first=json.loads(previous[0].read_text())
    assert first['complete'] and first['status']=='UNMET' and first['resolved_count']==0
    assert len(first['tasks'])==3 and all(t.get('process',{}).get('status')=='OK' for t in first['tasks'])
    assert all(t['cleanup']['status']=='PASS' and t['runtime_after']['ready'] for t in first['tasks'])
    assert 'Missing/untrusted harness artifact: patch.diff' in first['tasks'][0]['traceback'], 'Expected confirmed artifact-read failure'
    assert b"task_dir/'logs/evaluation'" in (here/'path_fix_06/official.py.before').read_bytes()
    assert b"task_dir/'logs/run_evaluation'" in (root/'src/vgar/evaluation/harness/official.py').read_bytes()
    source_hash=sha256((root/'src/vgar/evaluation/harness/official.py').read_bytes())
    reservation={'state':'STARTING_SECOND_FINAL_CAMPAIGN','approved_campaign_limit':2,'approved_attempt_limit':6,'prior_attempts':3,'reason':'Verified pinned log layout fix RED-to-GREEN; prior campaign preserved','wrapper_source_hash':source_hash,'planned_task_ids':list(GOLD_IDS),'hashes':hashes,'preflight_run_id':pre['run_id'],'previous_run_id':first['run_id']}
    write_json(out/'gold-reservation.json',reservation)
    report=_campaign(manifest,profile,GOLD_IDS,gold_root,execute=True)
    assert source_hash==sha256((root/'src/vgar/evaluation/harness/official.py').read_bytes())
    assert hashes=={'profile':sha256(profile.read_bytes()),'manifest':sha256(manifest.read_bytes())}
    summary={'run_id':report['run_id'],'status':report['status'],'complete':report['complete'],'resolved_count':report['resolved_count'],'campaigns_used':2,'actual_attempts':3+sum('process' in t for t in report['tasks']),'tasks':[{k:t.get(k) for k in ('instance_id','status','reason','duration_seconds','raw_report')} for t in report['tasks']],'runtime_integrity':report.get('runtime_after',{}).get('ready'),'resource_error':report.get('resource_error',False),'duration_seconds':report['duration_seconds']}
    write_json(out/'gold-summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)
    assert report['complete'] and report['status']=='QUALIFIED' and report['resolved_count']>=2, 'Gold qualification gate not achieved; preserve actual outcomes'
except BaseException:
    write_json(out/'failure.json',{'traceback':traceback.format_exc()})
    raise
```

</details>

<details>
<summary>run_local_02.py</summary>

Nguồn: [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\run_local_02.py](../results/m1/w9/m1-w9-5/20261024-docker-only/run_local_02.py)

```python
import hashlib,json,os,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'/mnt/d/Project/CAPSTONES/VGAR/src')
from vgar.evaluation.harness import task_env as api
from vgar.evaluation.harness.gold_inputs import write_json
root=Path('/mnt/d/Project/CAPSTONES/VGAR')
e=root/'results/m1/w9/m1-w9-5/20261024-docker-only'
config=e/'pinned-runtime.json'
original_gate=api.resource_gate

def ensure_resources(directory):
    directory=Path(directory)
    try:
        return original_gate(directory/'before')
    except ValueError:
        state=json.loads((directory/'before/resources.json').read_text())
        if (state['windows_available_bytes']>=4*1024**3 or state['linux_available_bytes']<4*1024**3
                or state['c_free_bytes']<10*1024**3 or state['d_free_bytes']<20*1024**3): raise
        previous=list(e.glob('w95-cache-*.reservation.json'))
        if len(previous)>=6: raise RuntimeError('W9-5 approved6cache reclaim budget exhausted')
        n=len(previous)+1
        cache=e/('cache-'+str(n));cache.mkdir(exist_ok=False)
        env=api.docker_environment('unix:///var/run/docker.sock')
        active=api.checked(['docker','ps','-q'],cache,'no-running-containers',env=env)
        assert not active['stdout'].strip(),'No cache reclaim with active containers'
        write_json(e/('w95-cache-'+str(n)+'.reservation.json'),{'operation':'sync then drop_caches=1','approved_maximum_for_W9_5':6,'trigger':str(directory),'before':state,'container_check':'empty'})
        api.checked(['sync'],cache,'sync',env=env)
        Path('/proc/sys/vm/drop_caches').write_text('1\n')
        write_json(e/('w95-cache-'+str(n)+'.applied.json'),{'status':'APPLIED','meminfo':Path('/proc/meminfo').read_text()})
        for index in range(16):
            if index: time.sleep(3)
            try:
                result=original_gate(directory/('after-reclaim-'+str(index)))
                print('Resource gate PASS after cache reclaim',n,flush=True)
                return result
            except ValueError:
                pass
        raise RuntimeError('RAM gate not recovered after one reclaim; stopped without repeated drop')

api.resource_gate=ensure_resources
mode=sys.argv[1]
if mode=='images':
    result=api.prepare(root/'configs/m1/w9_pilot_manifest.json',config,
        root/'artifacts/m1/w9/bundles'/api.BUNDLE_RUN,root/'results/m1/w9/m1-w9-5/image-preflight-runs',prepare_images=True)
    write_json(e/'image_preflight_final.json',{'run_id':result['run_id'],'status':result['status'],'ready':result.get('ready',False)})
    assert result['status']=='NOT_RUN' and result['ready']
elif mode=='collect':
    prior=json.loads((e/'collection_summary.json').read_text());assert prior['status']=='ERROR' and prior['collected']==0
    ready=json.loads((e/'image_preflight_final.json').read_text());assert ready['ready']
    frozen=json.loads((root/'results/m1/w9/m1-w9-5/image-preflight-runs'/ready['run_id']/'frozen-images.json').read_text())
    cfg=json.loads(config.read_text());cfg['images']=frozen
    frozen_config=e/'qualified-runtime-02.json'
    write_json(frozen_config,cfg)
    write_json(e/'collection_reservation_02.json',{'state':'STARTING','task_ids':list(api.PILOT_IDS),'runtime_hash':api.canonical_hash(cfg),'controller_sources':{str(p.relative_to(root)):'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'src/vgar/evaluation/harness/task_env.py',root/'src/vgar/evaluation/harness/collection_probe.py',root/'scripts/prepare_task_env.py']},'started_utc':api.utc_now()})
    result=api.prepare(root/'configs/m1/w9_pilot_manifest.json',frozen_config,
        root/'artifacts/m1/w9/bundles'/api.BUNDLE_RUN,root/'results/m1/w9/m1-w9-5/collection-runs',execute=True)
    write_json(e/'collection_summary_02.json',{'run_id':result['run_id'],'status':result['status'],'collected':result.get('collected_count',0),'excluded':result.get('excluded_count',0),'tasks':[{k:t.get(k) for k in ('task_id','status','reason','profile','profile_hash')} for t in result['tasks']]})
    assert result['status']=='COMPLETE'
else:
    raise ValueError('Unexpected operational mode')
print('STAGE',mode,'COMPLETE',result['run_id'],flush=True)
```

</details>

<details>
<summary>run_smoke.py</summary>

Nguồn: [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\run_smoke.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/run_smoke.py)

```python
"""Run the real Docker bridge with scripted generation and a declared nonmodel counter."""
import copy
import json
from pathlib import Path
import sys
from vgar.models.generator import FakeGenerator
from vgar.repair.admission import admit_task
from vgar.repair.contracts import RepairTask,RepairPolicy
from vgar.repair.evidence import atomic_json
from vgar.repair.pipeline import run_repair

E=Path(__file__).resolve().parent
config=json.loads((E/'smoke-inputs-lines/config.json').read_text(encoding='utf-8'))
task=RepairTask.model_validate(config['task'])
kw={k:config[k] for k in ('expected_manifest_hash','expected_profile_hash','bundle_hashes','source_roots','overlay')}
class Counter:
    counter_label='integration-only:whitespace'
    def __call__(self,text):return len(text.split())
class Tokenizer:
    label='integration-only:whitespace; not model tokens'
    def apply_chat_template(self,messages,*,tokenize,add_generation_prompt):
        rendered='\n'.join(m['role']+':'+m['content'] for m in messages)+'\nassistant:'
        return rendered.split() if tokenize else rendered
# V11 uses complete original source lines from the integration-only handoff.
# This is an explicit integration profile, without changing production defaults or source bundles.
from vgar.repair.context_adapter import load_handoff
from vgar.repair.prompt import build_repair_prompt
preflight = build_repair_prompt(task, load_handoff(task, Counter(), Counter.counter_label),
    {'failed_cases': []}, Tokenizer(), RepairPolicy(prompt_version='m2-w78-v11'))
atomic_json(E/('prompt-preflight-'+sys.argv[1]+'.json'),
    {'status':'PASS','prompt_version':preflight.version,'input_whitespace_units':preflight.input_tokens,'scope':'compatibility only, not baseline evidence'})
# Negative independently expected pin must fail before any environment launch.
bad=copy.deepcopy(kw);bad['expected_profile_hash']='sha256:'+'0'*64
try:
    admit_task(task,config['manifest_path'],config['profile_path'],**bad)
except ValueError as error:
    atomic_json(E/('negative-pin-'+sys.argv[1]+'.json'),{'status':'PASS','rejected':str(error),'docker_started':False})
else:raise AssertionError('Wrong profile hash was admitted')
admission=admit_task(task,config['manifest_path'],config['profile_path'],**kw)
atomic_json(E/('admission-'+sys.argv[1]+'.json'),admission.snapshot())
run=run_repair(task,RepairPolicy(runtime='docker_admitted',prompt_version='m2-w78-v11',command_timeout=120.0,global_timeout=1800.0),
    FakeGenerator((E/'smoke-inputs-lines/candidate.diff').read_text()),None,E/('smoke-runs-'+sys.argv[1]),
    m1_counter=Counter(),tokenizer=Tokenizer(),temp_root=E/('private-'+sys.argv[1]),admission=admission,
    experiment={'variant_policy':{'variant_id':'A0','required_checks':['tests']},'arm':'bm25','expected_hashes':config['bundle_hashes']})
summary={k:run.record.get(k) for k in ('run_id','status','complete','reason','original_source_unchanged')}
summary.update(run_directory=str(run.directory),scope=config['scope'],stage_statuses={k:v.get('status', 'COMPLETE' if v.get('complete') else 'NOT_RUN') for k,v in run.record['stages'].items()})
atomic_json(E/('smoke-summary-'+sys.argv[1]+'.json'),summary)
print(json.dumps(summary),flush=True)
if summary['status']!='PASS':raise SystemExit(1)
```

</details>

## Phụ lục C — Shell evaluation của official harness, giữ payload oracle ở local

Các dòng shell dưới đây lấy từ `eval.sh` nguyên văn, **chỉ lược thân here-document chứa benchmark test patch**, đánh dấu rõ bằng comment. Lệnh `git apply` và EOF delimiter được giữ để nhận biết vị trí payload; bản trích đã lược không phải script tái thực thi tương đương. Toàn văn đúng byte nằm ở link `eval.sh` và hash tương ứng. Các `pip install`, `git checkout/config/apply`, locale setup này thuộc official disposable container, không thực hiện lên VGAR host hoặc W9-5/M2 Docker target.

**astropy\_\_astropy-13398** — [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/eval.sh)

SHA256 toàn file: `92c315c974e472f62a7151af9a39590247edf5ca864ba63967af521b8b231596`

```bash
#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6500928dc0e57be8f06d1162eacc3ba5e2eff692
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --verbose
git checkout 6500928dc0e57be8f06d1162eacc3ba5e2eff692 astropy/coordinates/tests/test_intermediate_transformations.py
git apply -v - <<'EOF_114329324912'
# [Payload benchmark test patch omitted; read the original local eval.sh.]
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA astropy/coordinates/tests/test_intermediate_transformations.py
: '>>>>> End Test Output'
git checkout 6500928dc0e57be8f06d1162eacc3ba5e2eff692 astropy/coordinates/tests/test_intermediate_transformations.py
```

**django\_\_django-11138** — [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/eval.sh)

SHA256 toàn file: `b794fdc9da7d87f991f504e676c4ce73f79c1c92573df96469d725cf1255323a`

```bash
#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
export LANG=en_US.UTF-8
export LANGUAGE=en_US:en
export LC_ALL=en_US.UTF-8
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c84b91b7603e488f7171fdff8f08368ef3d6b856
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout c84b91b7603e488f7171fdff8f08368ef3d6b856 tests/timezones/tests.py
git apply -v - <<'EOF_114329324912'
# [Payload benchmark test patch omitted; read the original local eval.sh.]
EOF_114329324912
: '>>>>> Start Test Output'
./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 timezones.tests
: '>>>>> End Test Output'
git checkout c84b91b7603e488f7171fdff8f08368ef3d6b856 tests/timezones/tests.py
```

**matplotlib\_\_matplotlib-14623** — [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/eval.sh)

SHA256 toàn file: `fc878a74f4b01c9f8f6f4929f93610388c1732e1d8db7e257b040d360908d895`

```bash
#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff d65c9ca20ddf81ef91199e6d819f9d3506ef477c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout d65c9ca20ddf81ef91199e6d819f9d3506ef477c lib/matplotlib/tests/test_axes.py
git apply -v - <<'EOF_114329324912'
# [Payload benchmark test patch omitted; read the original local eval.sh.]
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/matplotlib/tests/test_axes.py
: '>>>>> End Test Output'
git checkout d65c9ca20ddf81ef91199e6d819f9d3506ef477c lib/matplotlib/tests/test_axes.py
```

Giải thích: `source .../activate` và `conda activate testbed` chọn environment trong image; `cd /testbed` chọn repo mục tiêu; `safe.directory` cho Git trong container; `git status/show/diff` ghi trạng thái; `pip install -e` theo quy trình official setup editable package; `git checkout <base> <testfile>` phục hồi test trước/sau; `git apply` nạp benchmark test patch; các marker Start/End khoanh raw test output. Django thêm locale UTF-8. `set -uxo pipefail` bật kiểm biến chưa định nghĩa, trace và pipeline exit propagation; script **không có `-e`**, nên phải dùng grader/required sets, không suy mọi test body PASS chỉ từ outer exit 0.

## Phụ lục D — Danh mục file log/result, đường dẫn đầy đủ và SHA256

Danh mục này gồm toàn bộ file retained trong ba final run roots, cộng control/gate receipts được trích trong tài liệu; không quét lại toàn repo. Bao gồm cả control archives/configs để truy vết operation. Mỗi link hiển thị đầy đủ Windows path. File lớn/binary không được embed; SHA256 đối chiếu raw bytes. Dữ liệu local vẫn bị Git ignore. Nếu evidence package không được bàn giao, link local không xuất hiện trên GitHub.

<details>
<summary>results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc — 163 files</summary>

| File tuyệt đối | Bytes | SHA256 |
| -------------- | ----: | ------ |

| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/cleanup-list.json) | 638 | `d287fd4be4f2248b95184e84e7325ec68b3a8238100a3516a9fbc68b54f0fa78` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\cleanup-list.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\cleanup-list.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/cleanup-list.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.json) | 2342 | `6f0a9d67b66cada815207dcab194b2de541840ed02cb4133ed6d416b6350fde4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.stderr.log) | 588 | `3d24233f425af4e21138023b09f849ec43971c882d17a00ed5546c1837daad86` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/harness.stdout.log) | 447 | `7d6ae74de0d7e06e82809b678246fa353137035b5fd28d198a1b5269ce2ce7d3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/eval.sh) | 8307 | `92c315c974e472f62a7151af9a39590247edf5ca864ba63967af521b8b231596` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\patch.diff](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/patch.diff) | 13884 | `5124ad079250b10166141d9deeb28d2cdf58ca42e50fb898b0ec8819bacc06e1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/report.json) | 9269 | `5b63acb922dff2dcb3b29b84bb6107be03e541cfa38319fccad73dfab9d7e8a4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/run_instance.log) | 25643 | `1d4c5dadb2cd58ebf1c4d3ab0ae8d05949557b77363d90d43449da96330ec18f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy**astropy-13398\logs\run_evaluation\vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b\vgar-w9-gold\astropy**astropy-13398\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/logs/run_evaluation/vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b/vgar-w9-gold/astropy__astropy-13398/test_output.txt) | 321360 | `1f0f464cd7e3c1cb6e743139e7e35e5422018a5d80f159b8fb8eea8c19e8cd49` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/ownership-before.json) | 637 | `86403614cb25357422956a7be825b915732be2ebfe08fd75a03ef60ac405eb75` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\ownership-before.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\ownership-before.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/record.json) | 42253 | `2710b2c51292776d4e78ba5039a731be56fe7175351d48d540d3ae87874cf435` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/docker-info.json) | 18766 | `9619073fb355ee6bec2832d259268b4d14bc478b0662852620dc69541d02609a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\docker-info.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/docker-info.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\docker-info.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/docker-info.stdout.log) | 15148 | `a1824181d7135c984d2a1baef6e305da3550c7afe4f57c178f9b80e882d8ede9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-clean.json) | 672 | `95dd877f5c02b7dc1dea1de406343bd42e9add6d38054de841fe21b8c7781622` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-clean.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-clean.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-clean.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-clean.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-head.json) | 681 | `592656936b4033a54e23f5619056f5052513b37c0dd4b7e877159765e7cf48b9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-head.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-head.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\harness-head.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/harness-head.stdout.log) | 41 | `b82573e0e6b9f8bc354e4f5c16d22706e114bbc2e8c4a6d9e09751198d077458` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-0.json) | 3547 | `bfe065a63deb62faf215b3bb80c3c7fd56bf056fda061a355c82609b66419418` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-0.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-0.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-0.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-0.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-1.json) | 3538 | `6c0160b626d02d5cde49520ad2c972a9aa95063c98f66440d2070d8c8cc44ed1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-1.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-1.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-1.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-1.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-2.json) | 3571 | `f020e193962819b73722ed0aa142859ddf97de6f04b97e9e3f02f00971ad1eda` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-2.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-2.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\image-2.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/image-2.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-help.json) | 3869 | `0b936ee2a667b20a3db03eef6d461673ac05cefb8813f020fd92f0dea827cce7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-help.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-help.stderr.log) | 239 | `76bb8761c30833d46b280c864808724924bd37f66d5548d72fc3d7a3a9d655a8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-help.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-help.stdout.log) | 2950 | `7e80d772767ae551004a0fd3ab17b0c2d46f583d28a315bea64b3cc72a15d8d7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-module.json) | 820 | `374e5bc540f09ee208c59307b957f29818d7354a6b8acfef0e7cf2d50566065f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-module.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-module.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\runtime-module.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/runtime-module.stdout.log) | 92 | `6ac7be99f5cc1f60743ca0b4a5e1c0a94c2bd9150dbfab0c79617e8e395c4d36` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/sdk-daemon.json) | 726 | `2c657ba57548868c00c2623085a944b3a71b828f5bff345f181f88259834bd2a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\sdk-daemon.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/sdk-daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\runtime-after\sdk-daemon.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/runtime-after/sdk-daemon.stdout.log) | 47 | `bf0159deb608df7db6d56f0a1768149032c323f764a28f063b705260c1c47066` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\astropy\_\_astropy-13398\vgar-w9-gold.vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/astropy__astropy-13398/vgar-w9-gold.vgw9-f7bfe9cba29d4bd9bb1a709efa8fe00b.json) | 592 | `4731a40fe7fa7404fab386d557381d6fe73619b904debe1942f07c597811d17a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/cleanup-list.json) | 633 | `6168f549a26cb2c0650a6acb1207f5778641c5afdbb1a3af769309d1a49d7df1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\cleanup-list.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\cleanup-list.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/cleanup-list.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.json) | 2339 | `c592a427282e5d57931f1fd2a6ba15c6b2219911e0c4ee55b6f69daa651dd57b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.stderr.log) | 588 | `e9238b687541e7d9725b68309978a47c6360ddb537d9d8474ca61fff340dabf4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/harness.stdout.log) | 447 | `49171fd01a8d3b0ebb453e7a97019a1a86683fff37412107c286eac5067fe11d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/eval.sh) | 4843 | `b794fdc9da7d87f991f504e676c4ce73f79c1c92573df96469d725cf1255323a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\patch.diff](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/patch.diff) | 7548 | `9ae4408e05d1a96259df33cc7606befd29e043cfb334bfecbf254fd643df0cb8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/report.json) | 7178 | `731870ad660f2d846e6d8a24c3dd4b671f3efb97bd91c44e08aa8c7e8474cf7b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/run_instance.log) | 22905 | `af99cc234c1d56001fbaf3a962dd55a4b2b9fc7b28e8a9fe63797e97973c89b9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django**django-11138\logs\run_evaluation\vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9\vgar-w9-gold\django**django-11138\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/logs/run_evaluation/vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9/vgar-w9-gold/django__django-11138/test_output.txt) | 30048 | `33fb28500693fccb5fa4df0aa11900a35e8b70fd7d37ae69437bd39a567abc6b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/ownership-before.json) | 633 | `8efc0980ae5d9c030e51d013b246777159702076a79494bc4c779bcf9b01eaba` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\ownership-before.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\ownership-before.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/record.json) | 42222 | `891f1600ff939fe0fdabf738fe1dda6e9d72cc0be008a55a3ef187b90cf19588` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/docker-info.json) | 18764 | `3f56e1b165b71d2702b54784259b5f9a2552fad3cdf39a3d563becb1a7ff14c1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\docker-info.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/docker-info.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\docker-info.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/docker-info.stdout.log) | 15148 | `c4ee7c5b4253cb8276c54415053bd2653da9689dc440494efb5ca57a9f504c85` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-clean.json) | 671 | `591e978df6dee8ac028101e05e137691723152240e2c0f30dcc016234fcbe5d3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-clean.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-clean.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-clean.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-clean.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-head.json) | 679 | `807d9139fd6879afd40edc10042029dfadc508d1b1acc64541bc7fd5369d21dc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-head.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-head.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\harness-head.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/harness-head.stdout.log) | 41 | `b82573e0e6b9f8bc354e4f5c16d22706e114bbc2e8c4a6d9e09751198d077458` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-0.json) | 3545 | `c655ff77ae77074db939117fff7350581a395fbb1cc9e974bee7f205637e64b7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-0.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-0.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-0.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-0.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-1.json) | 3536 | `3690ece965c533f288de2abc042cd9a5889e3448e82eedd19bf295d0dae55ff5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-1.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-1.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-1.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-1.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-2.json) | 3569 | `81d2f04cfe3ce0258a1498fd4afab0fd659c024565624382328afedae4e89679` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-2.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-2.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\image-2.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/image-2.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-help.json) | 3867 | `9bc3862520d3c7b46b5d2b46883930865cadef2a900cd0608fe5d30b80ac48e0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-help.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-help.stderr.log) | 239 | `76bb8761c30833d46b280c864808724924bd37f66d5548d72fc3d7a3a9d655a8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-help.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-help.stdout.log) | 2950 | `7e80d772767ae551004a0fd3ab17b0c2d46f583d28a315bea64b3cc72a15d8d7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-module.json) | 818 | `e0f9bcbe86b91ff709a9dca9f17a1155a584ba89e9e04927550442ba83f3e3e4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-module.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-module.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\runtime-module.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/runtime-module.stdout.log) | 92 | `6ac7be99f5cc1f60743ca0b4a5e1c0a94c2bd9150dbfab0c79617e8e395c4d36` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/sdk-daemon.json) | 724 | `f7f0bfa78dbd69e0bb2f0ae87c5861e47f57aa2a06a298d9d2400dd80b1e621f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\sdk-daemon.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/sdk-daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\runtime-after\sdk-daemon.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/runtime-after/sdk-daemon.stdout.log) | 47 | `bf0159deb608df7db6d56f0a1768149032c323f764a28f063b705260c1c47066` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\django\_\_django-11138\vgar-w9-gold.vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/django__django-11138/vgar-w9-gold.vgw9-d73bf5e0922c4c90a7b2a6d1fcb613a9.json) | 588 | `dc10c644ea039203e47c577d3986cbea1bacb36f250a4ba018b927d769399e0e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\inputs\dataset.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/dataset.json) | 108328 | `e657ffede885df8756864832478bb98c6732f2501a152e593baf202582c91305` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\inputs\inputs.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/inputs.json) | 1836 | `4682d4bddb4776bf446d330cf9d149ab4375ff9bffe01b35e0ed653073e4dd73` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\inputs\predictions.jsonl](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/inputs/predictions.jsonl) | 26243 | `f44fa4bb56da759bfa1306db629074c318afa133e1521ab6fa71ad1693d4a037` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\cleanup-list.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/cleanup-list.json) | 649 | `c0cebbcacf67019b21a59ea5449e6182dccb36725bba5a445f5f7060cbb127ba` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\cleanup-list.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\cleanup-list.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/cleanup-list.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.json) | 2354 | `2291a3532202754b1d665b202b99f2c84f4be9d179c43b8a4ae129aecf4de873` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.stderr.log) | 588 | `f3583b05e76f211d18d0f96ba3d23e92e8b4f6c313d7708aeb3420000224e300` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\harness.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/harness.stdout.log) | 447 | `18b9eb29c54e721be137552e19eb92dba703f8ecdfa1acced7631ecb9fb71df3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\eval.sh](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/eval.sh) | 1194 | `fc878a74f4b01c9f8f6f4929f93610388c1732e1d8db7e257b040d360908d895` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\patch.diff](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/patch.diff) | 3862 | `bf6c58aeace23b251199ff653b448e26c5b916eabbe9f7972cd16fbb81bfbf03` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\report.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/report.json) | 36911 | `bb491e21de1472802b92c00741e0ae24e946e782a7bff058019532250be98d29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\run_instance.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/run_instance.log) | 38318 | `4388278496ca2c4e0a3e8935ee2babeb59c522a8d432e6ffdbe7c5564d2e2ea5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib**matplotlib-14623\logs\run_evaluation\vgw9-15a7b5bf50a8487b8e7abe65627f2598\vgar-w9-gold\matplotlib**matplotlib-14623\test_output.txt](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/logs/run_evaluation/vgw9-15a7b5bf50a8487b8e7abe65627f2598/vgar-w9-gold/matplotlib__matplotlib-14623/test_output.txt) | 523525 | `90d5f25b2fe920a079470939ae34fd2e989374c1b93c8bd85bbf227baff819da` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\ownership-before.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/ownership-before.json) | 649 | `ab06b22d457578481e2a6bf8464e7c4b5f5b6c001ebba44b94449994ae5b74c0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\ownership-before.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\ownership-before.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/record.json) | 42352 | `3032c70c76d0cd114d484bfd17c20177c96bf84fa9072cdf8acf1a6be8e4c584` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/docker-info.json) | 18772 | `ce43ccf49763890beaba29c425fb5754040660ab8c7dcd2dac8e21107914095e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\docker-info.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/docker-info.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\docker-info.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/docker-info.stdout.log) | 15148 | `ff67e0c6bf739872a481960ded14f82322a0df115e30f351aa49cbdaf5bb8910` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-clean.json) | 678 | `e809962b5b2d5924594710aecfb363fc8dbd7c67b40f48db9b883c858d68763e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-clean.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-clean.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-clean.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-clean.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-head.json) | 687 | `4233efca4fffda2c4e4c810efb382f9ae44a087abc62e8bdca5209b2a007860c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-head.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-head.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\harness-head.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/harness-head.stdout.log) | 41 | `b82573e0e6b9f8bc354e4f5c16d22706e114bbc2e8c4a6d9e09751198d077458` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-0.json) | 3553 | `9d922b9e3c011f1087a604d5081357058fbfd5b390175ba2f52728db63433506` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-0.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-0.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-0.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-0.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-1.json) | 3544 | `1b9b852682355a2bdc5931d8de208f8b0c3ebcf5a10024f2609a1cf2212bac76` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-1.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-1.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-1.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-1.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-2.json) | 3576 | `20328e2b927d05ce18803d2cff7309304d0a2a4b4eb2a3c863f7755ef1bef7b3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-2.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-2.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\image-2.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/image-2.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-help.json) | 3875 | `f2147f5d08a75f2a9e009b7b93f5ba6afe29d806345898789ea270b821f8047b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-help.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-help.stderr.log) | 239 | `76bb8761c30833d46b280c864808724924bd37f66d5548d72fc3d7a3a9d655a8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-help.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-help.stdout.log) | 2950 | `7e80d772767ae551004a0fd3ab17b0c2d46f583d28a315bea64b3cc72a15d8d7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-module.json) | 825 | `6c800d5dfe1e608d3132fcadc587455e197569d02565f00cd23ce38278429413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-module.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-module.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\runtime-module.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/runtime-module.stdout.log) | 92 | `6ac7be99f5cc1f60743ca0b4a5e1c0a94c2bd9150dbfab0c79617e8e395c4d36` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/sdk-daemon.json) | 731 | `86d4f4b31ed7df3634e4dc2b6ce2dc2067049c38fc53328b1ec431cd42ed14e9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\sdk-daemon.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/sdk-daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\runtime-after\sdk-daemon.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/runtime-after/sdk-daemon.stdout.log) | 47 | `bf0159deb608df7db6d56f0a1768149032c323f764a28f063b705260c1c47066` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\matplotlib\_\_matplotlib-14623\vgar-w9-gold.vgw9-15a7b5bf50a8487b8e7abe65627f2598.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/matplotlib__matplotlib-14623/vgar-w9-gold.vgw9-15a7b5bf50a8487b8e7abe65627f2598.json) | 604 | `8ea26a22dc70e92867c1f3883f1bd8087f21335c011245926e9c89cc7c6ed035` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight.json) | 36857 | `478d209fdd91ed036de8fa65da2a5d6f29ab26dbd08667cf6c378621c831ae9b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\docker-info.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/docker-info.json) | 18740 | `7061ddfea58d2fe9d84564f0a1adf0da4f3d1b382ec200c039e81870bdbcb04c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\docker-info.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/docker-info.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\docker-info.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/docker-info.stdout.log) | 15148 | `aaf3f69b664caa822008a10d9a5b2ffa8b27b8d806a352519059cd20c78226b6` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-clean.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-clean.json) | 645 | `96dedb34cfa7b8f9fdbb27d6b8029d0fd5ba15a7b229f651a8b9c2349d84e672` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-clean.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-clean.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-clean.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-clean.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-head.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-head.json) | 654 | `1174f90a29a1b650c1be61213eefce3bc6becd23dc0bbbbe7775f02c9aa8168b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-head.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-head.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\harness-head.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/harness-head.stdout.log) | 41 | `b82573e0e6b9f8bc354e4f5c16d22706e114bbc2e8c4a6d9e09751198d077458` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-0.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-0.json) | 3521 | `35ea26d96a8512c694418025c62205abee26b460cb2cd289562c77ea42005d8b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-0.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-0.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-0.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-0.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-1.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-1.json) | 3511 | `200e374c39ed5048610229f4a37775caaa99588853e15775002de01ae770dcfd` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-1.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-1.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-1.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-1.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-2.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-2.json) | 3544 | `21c5d1bc06bd14c0ef10255c7be03862cfd4756d1146e2a4a3548aafa0a6a62f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-2.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-2.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\image-2.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/image-2.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-help.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-help.json) | 3842 | `08400ca42c0662be7f26f2cc5580866d7fb95c86312eec9a2d61fcd42ad1ef60` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-help.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-help.stderr.log) | 239 | `76bb8761c30833d46b280c864808724924bd37f66d5548d72fc3d7a3a9d655a8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-help.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-help.stdout.log) | 2950 | `7e80d772767ae551004a0fd3ab17b0c2d46f583d28a315bea64b3cc72a15d8d7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-module.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-module.json) | 793 | `5c7d5a650018ede1afca653af0734d0a0dc023edb59b12fc14de7e08c141d794` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-module.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-module.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\runtime-module.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/runtime-module.stdout.log) | 92 | `6ac7be99f5cc1f60743ca0b4a5e1c0a94c2bd9150dbfab0c79617e8e395c4d36` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\sdk-daemon.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/sdk-daemon.json) | 698 | `4d12bdfe1bbf1b3bcef7d82fac541c36007f8d92c1c837feab8745c470da0c66` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\sdk-daemon.stderr.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/sdk-daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\preflight\sdk-daemon.stdout.log](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/preflight/sdk-daemon.stdout.log) | 47 | `bf0159deb608df7db6d56f0a1768149032c323f764a28f063b705260c1c47066` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\profile.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/profile.json) | 1861 | `6085ea8b5d50d4482533a605f7b8c9f99bc2d455bfbeb1ef62ebaea8c700fed7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\reservation.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/reservation.json) | 594 | `0af0b4227eb114b9647486cf9b8a9497ea7eee40aad9e50a9ded3cf4dd96156f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\gold-runs\20261024T081750218758Z-3af0d2d105bc\run_record.json](../results/m1/w9/m1-w9-4/gold-runs/20261024T081750218758Z-3af0d2d105bc/run_record.json) | 208023 | `559f736ab8621497d63780af126ad44c8869f64e98113d460f2eeca460ca1c4f` |

</details>

<details>
<summary>results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2 — 383 files</summary>

| File tuyệt đối | Bytes | SHA256 |
| -------------- | ----: | ------ |

| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/daemon.json) | 18766 | `4bccf44d5658d3ef0084ad39b840756b94b1c4a7e90295a6103460ca19f47b0d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/daemon.stdout.log) | 15148 | `afcb487d00239e98fb076a5273b55823dacccaa74391ab30c26477a11263dc1d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/image.json) | 3601 | `ab9104934d2a8c367da1b908690c11e038daa50db3e2f290e38de957a1928afd` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\after\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/after/image.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-after.json) | 703 | `b8e3b20d8fa16ccaefb2afaa9cecba86ca0b46c5db1f4acec5d2122d57984bb3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-after.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-after.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-after.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-after.stdout.log) | 41 | `6026fefa3fcac7d9f086278cd24cebb2b4502fc5e0a3beea1ceb7f8297fa1926` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-before.json) | 703 | `db8de213373a4706db4fadf65a0d7878fd5c097e8c66b2a5ca5c42712f1fdd44` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-head-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-head-before.stdout.log) | 41 | `c8cfe812a866a3a944b24f92990bbeed6063bd44f6e4572e7c6aced54d37bf74` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-object.json) | 714 | `316da9c8d817165e1c883c1bdc31d15138fea17c4f7725c92d0f15c6ccf3788a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-object.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-object.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-object.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-object.stdout.log) | 7 | `50836eee574ecff79dea3b4fd40673d7d000f7a5f177d8a6a3000b59c78383b8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-reset.json) | 788 | `f5b52a1a8ea486ec69f9a213355cc40e76ab2add8326e25e46436058cd5c16c8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-reset.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-reset.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-reset.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-reset.stdout.log) | 83 | `44c8b0818669b63de6feae247bc6c78cd0b82325ee3544217a01d001db892acf` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-toplevel.json) | 682 | `2c8ad14429f3fa2c0efb1b8165e2e6e8742410c1ad82fb82b2027df05582a3ac` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-toplevel.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-toplevel.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\base-toplevel.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/base-toplevel.stdout.log) | 9 | `8d503a71f419a498d67669b26fdfa66848bc339939d625f34a9eaa79f4b23eb0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/daemon.json) | 18763 | `5754d880b5a03a21d17984f1d4f41b39361a27bdaedb3b9a9e7a335705807daf` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/daemon.stdout.log) | 15145 | `6fc2766de38c5e44be0e30c391dac2d83e9c0afb162c85954addcbfd2253dbce` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/image.json) | 3602 | `4711bcd5f8879cfff9f711f2a2bf78edd6bbf598081072c1e88e59da3aa87429` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\before\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/before/image.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-final.json) | 618 | `1ca023b19317a708f9d2810bab442dc4149ac13522ec1654b4a933cca220f2bd` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-final.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-final.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-final.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-inspect.json) | 8823 | `e46d5f807bca2e15c348c50f8eed7b30eebefe570d90e36810fb5695abfd19bc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-inspect.stdout.log) | 7527 | `b89b22d980234acdef5edd9c93cbec022798f48b38a9f4c3d3ce551cc2bae6af` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-list.json) | 631 | `33e90008fc27959e8ef7d4eb968aa0f2ba302f26712f18b62ca376bd01147605` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-list.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-list.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-list.stdout.log) | 13 | `82a1e13b0a447fc86ebfa22a37e48c37c47dc44b7fcfdaa163f1463b2604baea` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-remove.json) | 573 | `b0e7e4a930064e2ec279f6ffa14acab1ded71b4cdaca22aeffd1e8debdb712a7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-remove.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-remove.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\cleanup\cleanup-remove.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/cleanup/cleanup-remove.stdout.log) | 13 | `82a1e13b0a447fc86ebfa22a37e48c37c47dc44b7fcfdaa163f1463b2604baea` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.json) | 2137305 | `ca7f5216130b052f997f0c2f966abe76ee0708c4cfd2a34ea76792d2e227a450` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.stderr.log) | 164 | `f7e055d1d331f3ddbb55b2c32c3ab13207b2177312380790553ed794f9443bb4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/collection.stdout.log) | 2112313 | `5d076da161fdbfa44da66d4589985bde1f830b0b100800a64c944d9a75371b90` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-create.json) | 972 | `409beee00c4bec952bcaab371544d42d2231e1f627e05a6f9cb4025e3a6e8935` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-create.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-create.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-create.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-create.stdout.log) | 65 | `b4ecbf1c59e2acd03ed40d6ce9db3f5a9a293385da51e4d53863d07007274c58` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-inspect.json) | 8867 | `ce58c0ec1ecde39fc61ada0b149453d3d558cbc54e295513bc05565cac93678e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-inspect.stdout.log) | 7527 | `b89b22d980234acdef5edd9c93cbec022798f48b38a9f4c3d3ce551cc2bae6af` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-start.json) | 661 | `c97e4f879b35445fbf2540c4b77b289fa4227ab8bc27271a76e440c1e6520199` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-start.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-start.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\container-start.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/container-start.stdout.log) | 65 | `b4ecbf1c59e2acd03ed40d6ce9db3f5a9a293385da51e4d53863d07007274c58` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-input.json) | 803 | `ca4dc2f44b3aa5cd9943c64a92ffddb59e98c2c3455978e37c07cc9a3985826e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-input.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-input.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-input.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-input.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-probe.json) | 728 | `511f6e3b61aea11244a89ef0c943ad945f2710f043e7c60d265a117c21410778` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-probe.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-probe.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-probe.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-probe.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-result.json) | 804 | `d92547ccf2e4fb9f8987589db3b64d92157688c1d1a0171a47bac677f832bff8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-result.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-result.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\copy-result.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/copy-result.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/ownership-before.json) | 605 | `9cdc032eaf2165e745735bc7f66c11ec0a45a8db46530c695c9ba3fff94a8835` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\ownership-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\ownership-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\probe-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/probe-input.json) | 132 | `c6806825fa8c1548d464be6d8c0f2da0f90dbfe5947e3e27c6997b526da86573` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/probe-result.json) | 2321156 | `6774c573776b205748ba9f9c94483d4b3f26fdab036a3224cfcb298476c2fe1f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/record.json) | 4506447 | `8904e36a814f2d6c60d12634cdc13bcaef92c8f1ef0fe2641fa3f3c698c60906` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\astropy\_\_astropy-13398\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/astropy__astropy-13398/task_env.json) | 2322270 | `51dc6ba54a275c636bb1d4c7720f8df0e580a46dd01b329769370e43a2c75b74` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-0\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before/resources.json) | 144 | `05ecff5d323e1b674e760268d2fe861340fdd2be9c5279375942c2166f20ca04` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-0\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before/windows-memory.json) | 777 | `a2713d61e866e8954b8f9402b843b287b0cc799f80ee277126067aaeb5e08ba0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-0\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-0\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-0/before/windows-memory.stdout.log) | 49 | `2f1421ced2780f69ef972b1e2eef6ee2c3efeffc8f5bd29125821c8aa043597a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-1\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before/resources.json) | 144 | `9d043900df43c4fc41621e060a9eb6777dcd4e55780ff891da24c0d645bec81c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-1\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before/windows-memory.json) | 777 | `f6ef020e5c9854ec8eca93ccbb97b020f3632da419ddfa1f18c6cf497ebc0594` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-1\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-1\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-1/before/windows-memory.stdout.log) | 49 | `2fe56b5bc47d85ee9555778d9695863adfdb5085ac8f4c04f0ab67a5bff8d8b5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-2\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before/resources.json) | 144 | `565d11803ba8bca9a4caa1c545e71afad789c3aa4d9786a03243666c9abb3da9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-2\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before/windows-memory.json) | 777 | `1337714f7bb8426f88a07a72b0139218fde4baddbcce583e46389f52cff6566f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-2\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-2\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-2/before/windows-memory.stdout.log) | 49 | `00982fa574a42c26736ede9942a9aa14fa8cd919ecc852e9fcdcfdade45307ef` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-3\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before/resources.json) | 144 | `514654924bf5902e4bcdb8704612794800357d1695fce31148c3fc24c032f0be` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-3\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before/windows-memory.json) | 777 | `96f3a88238b54e0b91dbf56059b8e9dbf996f09ef52e7ef972245333bf4587f8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-3\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-3\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-3/before/windows-memory.stdout.log) | 49 | `afe1fff861708018bbdd600bba72b8306c4b3f90099a356188823f5579b961b1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-4\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before/resources.json) | 144 | `c0dcf3b201693b1a521693f3bfee02b83bb2df3b55ca0d8677968b6ada7ee231` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-4\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before/windows-memory.json) | 777 | `61217ae9f285e84c3d1620651ae0ac1cf8ec2910ef93d981bf10380cd6c2d619` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-4\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\collection-resources-4\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/collection-resources-4/before/windows-memory.stdout.log) | 49 | `93df0ae2af2ea601842b01cbc0869adaa208b78626ed59e0aa6d2fb8804c3c73` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/daemon.json) | 18763 | `c3327f56bc3b3af868059f57d8151e887771cca9e970be6dceb1f2a3fb70ca47` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/daemon.stdout.log) | 15148 | `c36e0baade20c5698274360655f2e6a315d6f68ba0c0d569eb45be9623db5ed0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/image.json) | 3590 | `5621132583f24753d89507e4a1ac96c5f7e9785ca3f2ed891e4e5652a1c410a1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\after\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/after/image.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-after.json) | 701 | `954b86b9065b29a2c26158564507e3a885fb0442d4bb4495d1e313c0aa0195f1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-after.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-after.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-after.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-after.stdout.log) | 41 | `63149b4a6d6b44fd972d181203336a791d1bf5997791e36b6463e08dd2854ddd` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-before.json) | 701 | `6844cf950df6d88d05283d68ea037749d814615c25941e8ec91efc85848673e7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-head-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-head-before.stdout.log) | 41 | `9a58648b0e543c5af141d45d82f31fe11f0fe327d159e1063340501876459b73` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-object.json) | 712 | `9af2e2d6799f08bc8e94d44c0ccb5d337e2d0c3456c96e4d2e47aadd37a977a9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-object.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-object.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-object.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-object.stdout.log) | 7 | `50836eee574ecff79dea3b4fd40673d7d000f7a5f177d8a6a3000b59c78383b8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-reset.json) | 2393 | `c277d36228c805da16bf4eeaff370c074005555d6db7761d89c8a4f20a2b5be3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-reset.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-reset.stderr.log) | 1558 | `f0c1d3cbcd3a4cd941fa8f025e5644dc722966428edebd14c635b98193e4a874` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-reset.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-reset.stdout.log) | 83 | `39c2ededeb934f0430a140592f98d741321c6611f0e1a5ac40f098a756b85aa0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-toplevel.json) | 680 | `1d3666e6b9f80c0bd6ad3cd8cb6fc3281850d8a57b4f1838042de439363f9c48` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-toplevel.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-toplevel.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\base-toplevel.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/base-toplevel.stdout.log) | 9 | `8d503a71f419a498d67669b26fdfa66848bc339939d625f34a9eaa79f4b23eb0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/daemon.json) | 18764 | `81b124cc0ab401c29890ac9333320d3340dda06e3ebace3d79cebc472f872e85` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/daemon.stdout.log) | 15148 | `ffda45c8318e292bad58772c5878c23f7cd46ba831131ea72837079ab445b97f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/image.json) | 3591 | `f37f1725703e2b9688432d5b0729b77971995fccc1b5d19424c72d51ecc2d4ba` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\before\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/before/image.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-final.json) | 615 | `d57ce2a520769788b6023e7a03e013d506c5827c55f92470c64f89ee40e0216d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-final.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-final.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-final.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-inspect.json) | 8816 | `a52a3ab44a5ffb84b4cdc75b9f5d7357f6a556efe16c5832d0ccb8dd7cd11b4d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-inspect.stdout.log) | 7524 | `277edcb71c67ebdd4214a99d8d7b27bc37a43cf817831eb2e60f013bff5e7fa4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-list.json) | 630 | `dda4b934818070274b26ca095eeb027efcf855968bd235221ef1c0740e69468f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-list.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-list.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-list.stdout.log) | 13 | `b24e4804e878dfb63e386263600bf3c049e4194ed3a730ad39b4a0bb3bdaed7f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-remove.json) | 570 | `0bcc80bccb01021755aac5325805682a86e32221a4d7a4e4977088ca4cd03140` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-remove.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-remove.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\cleanup\cleanup-remove.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/cleanup/cleanup-remove.stdout.log) | 13 | `b24e4804e878dfb63e386263600bf3c049e4194ed3a730ad39b4a0bb3bdaed7f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.json) | 1277 | `cd2541ae16010880d25cac0e5c91d36927bf1e95f0e215df79e52919bfc908aa` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/collection.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-create.json) | 971 | `37579a1353f9a53da19ae82e96d00604236721f29f4b97c958da3e922039571a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-create.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-create.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-create.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-create.stdout.log) | 65 | `85b83642276dc818aaa2c5b4aa0caacf6ab7f81ae0edafcbe4deee3d35d4929e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-inspect.json) | 8862 | `94d7a98bf218a35826943b9a9a18cb13e7b97ece259961582f7d65dc071d9851` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-inspect.stdout.log) | 7524 | `277edcb71c67ebdd4214a99d8d7b27bc37a43cf817831eb2e60f013bff5e7fa4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-start.json) | 660 | `f42ef786cd76912519f32902f0d7b9d18ec01972c9a3b0197fef43196b4c7bde` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-start.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-start.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\container-start.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/container-start.stdout.log) | 65 | `85b83642276dc818aaa2c5b4aa0caacf6ab7f81ae0edafcbe4deee3d35d4929e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-input.json) | 799 | `2e8214d6207a298904d4ebcd52322c23a3a4d9fa5e49a98487de3d30bb6aa7e9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-input.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-input.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-input.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-input.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-probe.json) | 726 | `cf2d30aee12d4ebb962c5928f2936a4bf8858cdb86935e05159baf119f9650dc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-probe.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-probe.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-probe.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-probe.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-result.json) | 801 | `f649875be909a2ed585f432539c4ba1c83bb91f5441ab370c8422d0ca7583b21` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-result.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-result.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\copy-result.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/copy-result.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/ownership-before.json) | 602 | `9c5bd31653c36505cce6d0ba41ec0a8d2de7e23f110de28faa3358a12c10ca89` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\ownership-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\ownership-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\probe-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/probe-input.json) | 132 | `eb1a7ea82544b7150379e042ad8cbbf0cc280e47d312893d34a4fbf54c2afae8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/probe-result.json) | 761 | `e5d7d3f2b8344f109f493b3f895f69cd3b0decf410f561a143cc03bbd54e2265` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/record.json) | 3719 | `4983057254ab2241e877dd79e02262b3f31024046670a820be6f327b6410c031` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\django\_\_django-11138\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/django__django-11138/task_env.json) | 1869 | `5d052cab4cd2a6d3cc1c3819b60dc2c71a192d5734905b14f43908eeea095e12` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-0\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-0/image.json) | 3587 | `db7e5b6e5dddae472978730677c63c80067a8e0dc51179904824de04325764f1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-0\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-0/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-0\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-0/image.stdout.log) | 2730 | `3305beaafeea9fa10d2b85cecb7b1d3def0add72ff68130fe6b3f74b8bfc6e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-1\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-1/image.json) | 3578 | `bad6bcaafbc7153fdbbb1853b09aa88b9b596b76e2e901407cb6379536e9179b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-1\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-1/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-1\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-1/image.stdout.log) | 2723 | `317e7ea2f5a7a0bc1cf41b62a23df95485325dfd200510b04a90968658a89684` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-2\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-2/image.json) | 3611 | `0a6eefefcd5632825d092e72f1216c8662d42ed54255cd50c12026b793abe62d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-2\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-2/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-2\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-2/image.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-3\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-3/image.json) | 3490 | `86f5d6463389796f780311c756bb6f4885ad2b20231a23dc53d34e0957eae68e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-3\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-3/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-3\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-3/image.stdout.log) | 2639 | `11bf2bfc32314bddb7593c2d5bde9b7a4ce5a7b89c8dbc0a6adf7d2c2fc5280b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-4\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-4/image.json) | 3502 | `de7a7741659f0608d633fa86a5c12b011989882c981e21bbae7a33f80073adc9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-4\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-4/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-image-4\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-image-4/image.stdout.log) | 2647 | `8a739eeb0c113d2bf3e6e54008a09960881811147c26e0fa90c5de4167375e7c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\frozen-images.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/frozen-images.json) | 1356 | `4bcf0db74b1c8db358c86c63ab9d64a2cb7d84ce9aa86c7b8c9caff7cf00e348` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-daemon\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-daemon/daemon.json) | 18750 | `0741ec99c5f56195bc353cfb569eae69a4ed64838b9a5da014954ec069958d5e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-daemon\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-daemon/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-daemon\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-daemon/daemon.stdout.log) | 15148 | `cba7f305a17f9dc0cd0cffbf41b5ddd42d1f2e835e1931a622d56df226fd14b3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-resources\before\resources.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before/resources.json) | 144 | `25174f5badb6e77eb0a22dc75ffd655cde7bb829579eb8c8b2fd1908ef9fc6d6` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-resources\before\windows-memory.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before/windows-memory.json) | 772 | `01f5ff888f13284a411c100feda500d5eeaacf1e26da333b84f6af38f566e1f9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-resources\before\windows-memory.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before/windows-memory.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\initial-resources\before\windows-memory.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/initial-resources/before/windows-memory.stdout.log) | 49 | `d910272a46f202e0b53430013153b3ea87d546c56d1dcd6d3da0275054b80960` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/daemon.json) | 18771 | `49a5460edd6be8e95f8c7b89f4ba5b2b0c6aa0bd58f1dbde8a6a04e9c0252ce7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/daemon.stdout.log) | 15148 | `f8ffc25aaa0976fdf9eabf083217976fb4aa00fa436ffc241d3437ac75ac7fb3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/image.json) | 3631 | `e009969ac4e681e75e8aa858e33b2abed315d230f29419826d430dcea546c037` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\after\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/after/image.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-after.json) | 709 | `f11c3909a90f15acc45a16b7d47433c8cfeb496e85771776abc144469589883b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-after.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-after.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-after.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-after.stdout.log) | 41 | `6c50658098fb2389c1719ac33bf39ca13c46792691a158f328eb2d07660651fc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-before.json) | 708 | `c493519e4d544190416b786923c0d38af1f661a6566c30b2833bc30d55902acc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-head-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-head-before.stdout.log) | 41 | `2f3eb44be2ed4280dffe5411e904ef03e766f1c3d8b7dea8cfac804c5e767e29` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-object.json) | 719 | `846cec70142e8ac7cf8493e429d3d645f7ef8f8147a8efc8136a4a35fd9905d1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-object.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-object.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-object.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-object.stdout.log) | 7 | `50836eee574ecff79dea3b4fd40673d7d000f7a5f177d8a6a3000b59c78383b8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-reset.json) | 819 | `15469854b91012dcfbbcdc09446093bdea17aa8fe09c14e7a77e3104b9f8619d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-reset.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-reset.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-reset.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-reset.stdout.log) | 108 | `4f13dc02fd02bebd44bc20c4f201099fb50779042fb596cbbeafbe373b3620c0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-toplevel.json) | 687 | `f9f4a180a7fd704bc3967eae51970dfba3b5f9efc0b5db63540f031e6d4f36de` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-toplevel.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-toplevel.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\base-toplevel.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/base-toplevel.stdout.log) | 9 | `8d503a71f419a498d67669b26fdfa66848bc339939d625f34a9eaa79f4b23eb0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/daemon.json) | 18771 | `d93c59be0e2a6bafd916615c7d23ccb4e707461176f038ec6aa591f402d5db24` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/daemon.stdout.log) | 15148 | `3119388ffe7f01c1c8562a465225d776d3f2c3e98abfd0de633ca4d474e6d93b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/image.json) | 3632 | `86d8d42d6c8375fcca574c41f1428d1f32c48a2b052661135eaa82fed619a58c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\before\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/before/image.stdout.log) | 2748 | `5df213275f495faf638642714ca4dc812a59d1911e7f684243c950a43e0be413` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-final.json) | 623 | `e76c252ab00eb400c698db784308387e6385cd99b95407e599ef348d4371e1a5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-final.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-final.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-final.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-inspect.json) | 8829 | `3644df25f39906dea3d568ead9e8d5df6599488093d0402ec0be866ab748ee6a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-inspect.stdout.log) | 7527 | `4606fe8ef8f5e49c0ca047c644489198c2038457893286eb9458fe2677f430f8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-list.json) | 637 | `3ffc84a2a200249ce550f8432074ea7ddb5f4013303563910f63f8a44b4abdf9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-list.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-list.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-list.stdout.log) | 13 | `914aae07b8b557ab3dbf1d31f5b19e7ee5719b1640e1be53359040fcf13c8771` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-remove.json) | 578 | `008033cad7e46a03737aa4f3952f85a4c4198f8e8b35d1e6301aab178c019029` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-remove.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-remove.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\cleanup\cleanup-remove.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/cleanup/cleanup-remove.stdout.log) | 13 | `914aae07b8b557ab3dbf1d31f5b19e7ee5719b1640e1be53359040fcf13c8771` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.json) | 717166 | `5d0cae7b98a9336550684ee6e0d8d2c432b932035412d98f32e7d6ac32b6e297` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/collection.stdout.log) | 707824 | `45d8b50d07e2ca3c1a834a89b9a53ca7b234f93d57c99d468c9bf4685a213cb8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-create.json) | 979 | `6d8eca40970d37fccd01cc3c47737555840ea6cefa65e67126ffaa581aecef58` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-create.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-create.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-create.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-create.stdout.log) | 65 | `4e578a5c4475597b3aae3a66850a15442c249f88a1fbb1948ef1785c9d83dcca` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-inspect.json) | 8873 | `56bb7ebf15a583469b7de4b61bc6912633950c1353778ea13719cbb82fa7aa1c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-inspect.stdout.log) | 7527 | `4606fe8ef8f5e49c0ca047c644489198c2038457893286eb9458fe2677f430f8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-start.json) | 667 | `7007b8ced582dce6224ee0458f76a43904a1c6c53ff46092f8ed4ef66cdbb334` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-start.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-start.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\container-start.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/container-start.stdout.log) | 65 | `4e578a5c4475597b3aae3a66850a15442c249f88a1fbb1948ef1785c9d83dcca` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-input.json) | 815 | `ec52873f3266406d97f7bb1d4b2bab38a9c3bb6e57a6a185c79b247525e6283f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-input.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-input.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-input.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-input.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-probe.json) | 734 | `4c3bea61b5eccc770d61b194d60dc785690d1ab4fa653a5cc09caa48fd41b64e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-probe.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-probe.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-probe.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-probe.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-result.json) | 817 | `8e4cd2c73c84715d145318ea1b5abdcd751f18d34fc1da5cb39753de344f6e24` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-result.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-result.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\copy-result.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/copy-result.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/ownership-before.json) | 612 | `129128e34194729376857aa1548b515c624162e90a31e3acde5412fdde3f4286` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\ownership-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\ownership-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\probe-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/probe-input.json) | 132 | `d9e222a8f846ba7acdf763998d32161d11c6a9db0be6c42eee39a4c929e45e38` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/probe-result.json) | 777641 | `b4956b9c567e2028a07c0ab640fd965b1f97079209addeba5ec8b92de7d30736` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/record.json) | 1512283 | `ef1f9837e704d06abe97be1259389ae3291c8047e9cdefacf41239e6f583c43b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\matplotlib\_\_matplotlib-14623\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/matplotlib__matplotlib-14623/task_env.json) | 778773 | `6d232825808e08022f5682e812b941e6319f30d23e58d410cf354720fc33cd2e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/daemon.json) | 18760 | `511a4131ffbdb9536df4b787b1f1a93cd62e7baa33a60c0bc850f61cbd7a1993` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/daemon.stdout.log) | 15147 | `197ac46d7ec24653beddc9aaceaf6243639ad716a6b20aa9d36dd6a17a32da7f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/image.json) | 3501 | `ca6f1a3b010e9f3a5087418aa66aab4741da44955d7bef10b29d4324a325e13d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\after\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/after/image.stdout.log) | 2639 | `11bf2bfc32314bddb7593c2d5bde9b7a4ce5a7b89c8dbc0a6adf7d2c2fc5280b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-after.json) | 700 | `a3da8b07544010462e8a1e83dc692d501c8de1724b944433332289cce92e863a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-after.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-after.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-after.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-after.stdout.log) | 41 | `2f6c4362f030984d05dcbfca86c274bb0e1852a035e6f16c16d1474d412c987a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-before.json) | 700 | `ce4614e6fe93570614eb02ba5a835e82987b3718bdbfb347e244b2e61220603b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-head-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-head-before.stdout.log) | 41 | `3801709752fdf4b4a1eee3bbfaf4d3c32ab70a9658821779b0f783db0ae27244` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-object.json) | 710 | `d9fae484585f8c353127746f707ee9d4eec0e8633315c21b0cb7fb54370e80a5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-object.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-object.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-object.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-object.stdout.log) | 7 | `50836eee574ecff79dea3b4fd40673d7d000f7a5f177d8a6a3000b59c78383b8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-reset.json) | 776 | `0a9a1dfbe0575a1aa8265535353ded99327f978f7e714682c79a0705359bfae8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-reset.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-reset.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-reset.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-reset.stdout.log) | 72 | `17db7ea706387dee492ee3196ae0649ca154d6b172bbcaaf7e08e85e9438bdd8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-toplevel.json) | 679 | `9e8efe446bfdf90ed71bdb347d18bdd5c649a54d963d105db3a1a13db509fcb8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-toplevel.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-toplevel.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\base-toplevel.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/base-toplevel.stdout.log) | 9 | `8d503a71f419a498d67669b26fdfa66848bc339939d625f34a9eaa79f4b23eb0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/daemon.json) | 18763 | `472279fb57bfcc82e7e2cbd5dc6c4acc011f86babcae05804027e1940c1c1127` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/daemon.stdout.log) | 15148 | `c0c8c57efc1d277dae4f780847b3546ad7f121e97ac9abf8d05f465bd027b347` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/image.json) | 3502 | `f1ec3d25b30edafdb0dd3370c64b6073380cae8476e150352db1fe971076223a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\before\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/before/image.stdout.log) | 2639 | `11bf2bfc32314bddb7593c2d5bde9b7a4ce5a7b89c8dbc0a6adf7d2c2fc5280b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-final.json) | 613 | `0431d4a0fbd371982420159c3b0fad6bc9986a12c8ab17ffaf53af6768c7faf0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-final.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-final.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-final.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-inspect.json) | 8820 | `0e8b471f9858071c8ec25abe45f6f810f258db22de4bb6cfd4443e4e3840a24f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-inspect.stdout.log) | 7526 | `01d50537b2e63c76085a585cf6c5541e0dfa347053dd41c12db3741c28923019` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-list.json) | 628 | `67d44ddd0f9ad47baab1dc65406f165bc57da1f38e1cd3cdb7ce8631e7dd988c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-list.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-list.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-list.stdout.log) | 13 | `4acda86bd36e6f48a45422cbc57b29d3136e2ca8af61bef0500582691c3f2c46` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-remove.json) | 570 | `a7342fdbd3706f6dfafc3278720e18945e8c3db2f001b6fab45f11b9c83e8b75` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-remove.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-remove.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\cleanup\cleanup-remove.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/cleanup/cleanup-remove.stdout.log) | 13 | `4acda86bd36e6f48a45422cbc57b29d3136e2ca8af61bef0500582691c3f2c46` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.json) | 751052 | `f7da1f659f59aea08fcbe3696dbc1145c4272f045cf24199188fc71390ac4317` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/collection.stdout.log) | 740912 | `83eb948d8584f081ee8364a9e8c49e9cf501b7318928c926f51df7426e26f732` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-create.json) | 970 | `f8de2816bd6298b79466a4a844b89368034bb9d52d259ced393bc08e1952d867` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-create.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-create.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-create.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-create.stdout.log) | 65 | `f868da7d8d4133f8b980a2191186de152a6a1e97b172e86296312a1e636dba70` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-inspect.json) | 8863 | `b947241e7381c30d68ee264632ca00a2b67be7ddd666f6e31150931bf585ea6d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-inspect.stdout.log) | 7526 | `01d50537b2e63c76085a585cf6c5541e0dfa347053dd41c12db3741c28923019` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-start.json) | 659 | `a157c3e4a3df55c8ac4c77302ae8e4a40d84a0ccde0b1554c0e5714e2181e869` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-start.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-start.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\container-start.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/container-start.stdout.log) | 65 | `f868da7d8d4133f8b980a2191186de152a6a1e97b172e86296312a1e636dba70` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-input.json) | 797 | `87173778336f2289c3f56a838780ab00a21634c0bd7e9095e55c98eb61699978` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-input.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-input.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-input.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-input.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-probe.json) | 725 | `7c7e4cc023807ac76531a118edc88f599316e3697935576306908a9033c41fea` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-probe.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-probe.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-probe.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-probe.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-result.json) | 799 | `a1da223cfd481b52de444e18318cd30b367792cc80da76c51859fd37ae3046c3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-result.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-result.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\copy-result.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/copy-result.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/ownership-before.json) | 603 | `0cc2030ab543033d9e38daa01a25ec76db9c9fcb13ff694e71f2077d31b2b172` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\ownership-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\ownership-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\probe-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/probe-input.json) | 132 | `88e197f62b9bff04140a427a54a262fa069612a7f28ede494da19850e6d0913e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/probe-result.json) | 814991 | `7e77b3fb78755bf5663892edae71d3ec987470feadeb586dbb4239e8c603ed42` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/record.json) | 1585134 | `2c9a5dc73ada44395484448803ae16ba8a814a09f04341fc3d45bb220711662a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pydata\_\_xarray-3305\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pydata__xarray-3305/task_env.json) | 816097 | `3904ca4a8babbfbb6153438f356fe9b9ee870f49ff5a9e6484f4ee11dfe73600` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/daemon.json) | 18767 | `306ee6e44177c219a6376221262c7a8922f860d1023af85f6b155ab16a6798ac` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/daemon.stdout.log) | 15148 | `ad9c27e6141427795aca99e45e0b881014cc89ec699874cbdc9ce4c30d037be7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/image.json) | 3518 | `da5b70f0df76466a78e9874efd22a5528ef5718b4a04cb41128bd8fd9d232b0b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\after\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/after/image.stdout.log) | 2647 | `8a739eeb0c113d2bf3e6e54008a09960881811147c26e0fa90c5de4167375e7c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-after.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-after.json) | 704 | `2f086c48688a97d05c25ffe94b0237cbaf37c601e32f07faec48c72be76a88a7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-after.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-after.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-after.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-after.stdout.log) | 41 | `c4408483261981974ccf4826039f14e21edfbe81774596cbf7046b6c45d19daa` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-before.json) | 704 | `8624fa206cd6ab424729b959421ce401c27ef80b1290ec3ae2f23d208ad9a9af` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-head-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-head-before.stdout.log) | 41 | `7487428ffc05d5195d48010d9387991095e94ff4f6a0ac1a65d80254ca886bfc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-object.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-object.json) | 715 | `f2d1acbff601097042da7a2a514383fc3dbd1a1b2b66cebfad9a033921395791` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-object.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-object.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-object.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-object.stdout.log) | 7 | `50836eee574ecff79dea3b4fd40673d7d000f7a5f177d8a6a3000b59c78383b8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-reset.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-reset.json) | 765 | `b7c41082e05ea85bb6d889062ebb16d38394934f9afc8038aca598edeb17085d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-reset.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-reset.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-reset.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-reset.stdout.log) | 57 | `32bebf3e168578eb1736017fdd1f6b58e90889222c49602b0ff4a986f56f63eb` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-toplevel.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-toplevel.json) | 683 | `7fe0eac4683cf4a3b80dcc0f89b06ab40fbdbb5a79e4eb8e1739732840df87f4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-toplevel.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-toplevel.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\base-toplevel.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/base-toplevel.stdout.log) | 9 | `8d503a71f419a498d67669b26fdfa66848bc339939d625f34a9eaa79f4b23eb0` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/daemon.json) | 18767 | `beb30c35c672023eb373f9db44434128709214802911396f0d0bb9e487d15b8d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/daemon.stdout.log) | 15148 | `a92dc6f18869fc61b8bade145f5e8206e633645eb9c6748ec65f449ffd1c6e8c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\image.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/image.json) | 3518 | `49c27fa0b209a1bbf3f216f410af334766ecd22a1f104ea2f0976f4a70bd9f35` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\image.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/image.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\before\image.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/before/image.stdout.log) | 2647 | `8a739eeb0c113d2bf3e6e54008a09960881811147c26e0fa90c5de4167375e7c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-final.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-final.json) | 617 | `11ed7a6a2b8f94864c7f978c5989d916a6d31a3e63ce4d723006a8ebfe38f618` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-final.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-final.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-final.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-inspect.json) | 8825 | `16221eea9724d54db9d553a558746583cf52500eadc1a50deaa3299b24e507ac` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-inspect.stdout.log) | 7527 | `17d29c84d5c02d06b1fdad3342d95350090231c140b29b699a1b01cda22c7a0d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-list.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-list.json) | 633 | `fe47a264f2355cf1dc7b6294e562b1cad55d993c71fd43048fb740b6e19928c9` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-list.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-list.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-list.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-list.stdout.log) | 13 | `a205dea0bfa9f68a82082cac74d27146f4a7cec7c37e157af87504d9cbc12088` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-remove.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-remove.json) | 574 | `8dbb801d73e3b1760d95ef4034e7caa5abbfc6c24b7e054f384d57d7d1533ce4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-remove.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-remove.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\cleanup\cleanup-remove.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/cleanup/cleanup-remove.stdout.log) | 13 | `a205dea0bfa9f68a82082cac74d27146f4a7cec7c37e157af87504d9cbc12088` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.json) | 118063 | `b80b67a5f308c7fc560839f19d6f3ef1fd63dd3990751798fd53741fc6baf525` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\collection.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/collection.stdout.log) | 115330 | `43fc31a140d484e6d713d1ec1dc7eda82087043114256660ef1de2fa1ffe6c2d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-create.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-create.json) | 973 | `4153a869cdb430ee607376608268dfaeff5d7af36593f3fb1f1eeeea4f400d7f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-create.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-create.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-create.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-create.stdout.log) | 65 | `e7d1503e60fbeebac7c3cab914ad55fa88b66d927cc407a4dc578f3e183e092c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-inspect.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-inspect.json) | 8868 | `829bd9e1b09049c5a78433c81d0dbff9e40e390e6fec973beb784dc3040516fc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-inspect.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-inspect.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-inspect.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-inspect.stdout.log) | 7527 | `17d29c84d5c02d06b1fdad3342d95350090231c140b29b699a1b01cda22c7a0d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-start.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-start.json) | 662 | `0747352602ac702bae476f100bd84895ce09620c912d369e653aa6ce7496bb13` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-start.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-start.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\container-start.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/container-start.stdout.log) | 65 | `e7d1503e60fbeebac7c3cab914ad55fa88b66d927cc407a4dc578f3e183e092c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-input.json) | 805 | `c14914150a28d5d43740f7164720321b11c4b8665f57a9f90d64a6499e7f6f6e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-input.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-input.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-input.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-input.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-probe.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-probe.json) | 729 | `31001091be092eca42d883bca7401009979e90130639091316887b9348409160` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-probe.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-probe.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-probe.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-probe.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-result.json) | 806 | `ba80dd818ac845b29a54ff9d94c0c45f38494cf873bb0d6a87b79f3624d7b742` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-result.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-result.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\copy-result.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/copy-result.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\ownership-before.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/ownership-before.json) | 606 | `12b711076c7488117e528542ecb816408e4fafeaa8ba9d3dedf1ebcfd4cda894` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\ownership-before.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/ownership-before.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\ownership-before.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/ownership-before.stdout.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\probe-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/probe-input.json) | 132 | `4f1302580088e616026fc2d007108ae9fe2076863a79b548ac0723218fefac5c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\probe-result.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/probe-result.json) | 128418 | `aa31bfc7dee760cfe4f483019cc385fbec7e1a95ce145c12de93cb06223841e4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/record.json) | 251016 | `8b1af969bf595ffb0aa5901d8bfbcf969c19ccc045303f8ec5ea98355eb443eb` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\pylint-dev\_\_pylint-4551\task_env.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/pylint-dev__pylint-4551/task_env.json) | 129536 | `5b04271341e545dd6541b034012a6d85f581e2bbd4be0921233db4b68740a7bb` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\run_record.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/run_record.json) | 8026783 | `45823f189c55ab62da186cdc89f2ec820c4f1ea76025a9bf67af4184522c709b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\runtime-input.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/runtime-input.json) | 1632 | `a3dd9e2f69035742a2ebd888dbe1db4197967825a59a920118bd49f16f95bd18` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\sdk-daemon.json](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/sdk-daemon.json) | 696 | `2d9ac5636b75228605a07806e4e409ef44db25084439f147406557ddec801382` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\sdk-daemon.stderr.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/sdk-daemon.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\collection-runs\w95-3178eb33a42b414d81656b21b64cc2e2\sdk-daemon.stdout.log](../results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/sdk-daemon.stdout.log) | 47 | `bf0159deb608df7db6d56f0a1768149032c323f764a28f063b705260c1c47066` |

</details>

<details>
<summary>results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725 — 319 files</summary>

| File tuyệt đối | Bytes | SHA256 |
| -------------- | ----: | ------ |

| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\REPORT.md](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/REPORT.md) | 472 | `c8f73bfd093d4ef3aa7bc6ac022d44026c4ab7b2aa163fc0bfe4103cd5a28797` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\applied.diff](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/applied.diff) | 616 | `b54d909d246391f214e3a90208cf90ffe003b2dda6fbaa099a246e98d315e9df` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\candidate.diff](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/candidate.diff) | 473 | `806cd813968c5f2654b1050940be1f773fc9d0cc00376a4e7b406551b4111d8f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cleanup.json) | 52 | `53a6d047bbe5be5dade4fb73a995bf74f49edd88dc9a88a581ddf3fddac9e994` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-000.json) | 18825 | `398894702948288ecd7b080f6879131d25dc260593af8f862dffbc1ae9dfe5f7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-001.json) | 3668 | `ee0d0bae49f14c574e7f0ee635d9a34f6e9a20e544a175f77c027011e79543d2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-002.json) | 706 | `56e65e8c9bd9bc6f217a4d9cb01f7530402aa89a0268be9f095d19a31b427181` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-003.json) | 1643 | `d8c40bbb9b37ad84fe41ea998878898fd2dc1cfe0782c64be79704626a40b112` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-004.json) | 703 | `0dd39ef96aa7a9577f1371945fa5b598cf72718fb520b17fd7b943c0bf4c6c8d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-005.json) | 1022 | `ab5777ba914d260f9ca5cf45eb2c4e9ca43d6880dc70613c5dc3da59d3496316` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-006.json) | 981 | `b7d35ad6453c88df3a2b8086cb445979880b0b5ee4b7943805eb7dceb7cdd3ac` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-007.json) | 1067 | `87d63a7a646dfa99b61f8f9ea9d3dee873021980a53d3421982c9b55ac7232b6` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-008.json) | 738 | `cd4c59034b614b6abfe383e06b1d7edde5bb0d7e7f81684c59160151412c62ff` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-009.json) | 9059 | `e95a4a9f03592d8930e715121a43f91444680473bcfded26d1d870b4714873a0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-010.json) | 632 | `3423ca8a55125f5668c7503d5ad6528dd11e34e0b914cddd2cb2622a9d641e95` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/cli-011.json) | 722 | `9dd855c700eec11b8e4af8f39a934f02828dde9cd3159bbf6fe68e0138548865` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/command.json) | 52972 | `dc4a02547ab15fdfff1b8644f3b7ce96a05c5631d770c88167dac4bb7c67daa4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/config.json) | 25503 | `78c1a213f01d22b2dd38325d4555b5d0790d267c4675228c8d34ec3663eca11d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\06b8252ffeea4729bcdadbfa8fc162a1\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/06b8252ffeea4729bcdadbfa8fc162a1/target_result.json) | 50368 | `58b573b33a9019c3ed8c472c0a2977716f9187d51ea171d4d6403d598d8cd9a5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cleanup.json) | 52 | `02a8e570e075e9d10d7039d55dc0dde4768317f3e3c556bcaa742e586b18e20a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-000.json) | 18826 | `834ad61bdb1868f533b3b464fa734d731a540528f55af7b9371ce141219ebc58` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-001.json) | 3668 | `fb357b4d8e96846ccc931fbe04fce7a580313cc36ae2f00c03edd9a6cd45f539` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-002.json) | 706 | `651600d55c5685d331aa5b1385f02643f514dc9f903133a9846df523a924675c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-003.json) | 1643 | `c28eb63f1f8b7ef1e6b0d943c043d640af24141d70523ad82051ea58dfa1b54f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-004.json) | 703 | `d6ce8a9e242eb703e668ded46c42e8994e5b44a2d064d2956ffad1596b717d71` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-005.json) | 1022 | `266b948425c3b6a638bc671830dcccd34b9781c1801353abaf13b4f0aa70d2a1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-006.json) | 917 | `9709561ecae49aa0f0cea8aa5888197b964b053d57d37d6409f48214c12246bf` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-007.json) | 1068 | `26ed3484fe80b6a018eefb9e5ac51a52fc960218a3e7ecaa5d378999e822a695` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-008.json) | 736 | `2ff1cd3bb8300001d70ca55990c82b449cb05b6cb027f1a710a0fb6c0c894835` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-009.json) | 9057 | `18c33c93e50b6fc9b3c51303ef9da2259e442ac2b30d8dfd7d2350022f3452c3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-010.json) | 632 | `ab5811890dce7d87aae17d64b54955f2fb105b281d0a1cb65fce3d3b74cdb69b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/cli-011.json) | 722 | `86cf42f99b0dff2c1710780cf8a61055cf6d2007f7b51c20d01bee4f9dcbc864` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/command.json) | 52786 | `71839beacb4d24dd182e46503288876c7bb70a31da8af2fff337eced63aea054` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/config.json) | 26560 | `d00cedafd1cc9cf4053f4ae6b35ff396943d4fd684c49413b64486b3de7f3564` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\229613e0b4c04ed495d6290daa4ffabd\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/229613e0b4c04ed495d6290daa4ffabd/target_result.json) | 50336 | `cfc6882b571e6af2efc7dbe511fbfbc21fc6b74ee83eaed908d946ba2c61549b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cleanup.json) | 52 | `39a6e860a2a070d74a6e1409fe6c375bce4d28bee2187e4fee5eacf51926179b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-000.json) | 18825 | `3f64e2b3ecc96230f4a23a87b151387621c2fd187b3bab4b621acf6cdd7468d3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-001.json) | 3668 | `80c7189c5fd3316316362eb81d3c8a1a14e21ed979be18a3c6476cecc6e78b51` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-002.json) | 706 | `d0fbc0dcca40f6c2e7c3f52dfa0d5db59636c025ab2c25c1d8ee36f47923a0e9` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-003.json) | 1642 | `bf27ad48ba89879aa1e526faac3a40c8d4c01575f71febc0604c713fc9b739c3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-004.json) | 703 | `dd64313938121bb4722b91a7748f290da55f0b56c8e6471356463c56bd8f0c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-005.json) | 1022 | `2409dae0a652e5cf912734329198313fb0669dd7037e5d8bcd51a8cd192f4078` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-006.json) | 981 | `a82caf4d0f128e1b636ff2c89c7b114ed5eccbcdc0b3d66a180a4a2fc816567e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-007.json) | 1067 | `7c0c1d09aa69cd0e7f4a8f2a43e95c246472d51b7887e1a2c7e0cd5da2e65a51` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-008.json) | 737 | `7b431b698256e83353b08230d0a3b25d36b90f0a3584d68940f76cc9cc9efdc8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-009.json) | 9060 | `098ae06521eb48acbce4cf804041d91514c583b2a78258e1612da9902750ef25` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-010.json) | 633 | `9c46c30cd02ec0a00ef76b6c4ebd47d95fc28bb72a995423a34f09c9ea33be81` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/cli-011.json) | 722 | `574cac31e9933c82235faa3b579e2728ca8bdd87cfad3b9433906cf2d427a12c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/command.json) | 55634 | `6e64f0d8ed0ed422122c4ba332e364b121fa60a521a27943e9f8c51cc32a15db` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/config.json) | 26791 | `9a065d4a8f74c616156eee1854b5616cac82a82873513c13867c18909f5baf5e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2516346f4e56495b8da2c6e121ac249b\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2516346f4e56495b8da2c6e121ac249b/target_result.json) | 51656 | `73a91415f89c9797269cb78705c1cc25218d22b8d04e0df8aac9325912eb640e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cleanup.json) | 52 | `9686bd2f78507808cba26e8c409399d1d9932a51fae608697626149fe6839992` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-000.json) | 18826 | `ff2eefbc44bf36cd0383b6fc0485f7a0e7c88d974926316ac48a3b3ca0d38f0b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-001.json) | 3668 | `c0f114e9a5442070d686650d7b493acd6d63e7a11e87eec4a33759477d457120` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-002.json) | 706 | `af7746316d2d197f9454c277a9a2c42fec49667091ec5f17fdcdcb6196ad9105` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-003.json) | 1643 | `564ffabb288d362cb08f9b706695bf9bae58b78d0089b87d31954b06aa053185` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-004.json) | 703 | `022e809f4573497a4603afac8f00344304fae6a980636da5ed722df460df548a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-005.json) | 1022 | `5fbbbdd10a98ce21e08cae3b0f6c46600e42e0c68aca7d55f3742374830000fc` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-006.json) | 3380 | `ee9b350122444de3088929eca1210bc0e55330e0b30598ad48fa5168bb1a20c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-007.json) | 1067 | `677bc26908b1f89fc7a757ec2fc2d2c5f9c55926bbffd9a78f591fe2e741f4ef` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-008.json) | 1057 | `77077d8385e2f44c78d7c9bc1a0fbb307600199d61f3140dfd4f11eb30e922b0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-009.json) | 1045 | `eaed47bf2c89cc426ca3097c754cd841a258cf20ea0d5e879f25aeac9d08fafd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-010.json) | 737 | `c4a12d0e6a0c7b9f3b461411fe53908ef3ffdaeab2495720876570f7f7622d1a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-011.json) | 9059 | `042a05e514686311b8736b33014f99257b1f1cdf09d124933ac50e3521207db9` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-012.json) | 633 | `aac5e11ca61a40612d0870d65945d4441e49ce971517f5e96896b585b570f9bd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/cli-013.json) | 722 | `93fdb13bb6b46148bda3b7172380cf29ce502ed281539cf6b0c0655de3444893` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/command.json) | 55797 | `c8e2c6c38496da454d395558fe8577088cc785cb3db7448555c161b97da6fb4a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/config.json) | 25708 | `27aa3ac299c50200547a554eae2b8681750b43749a7f2951bd08dac4bcaa609b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/junit.xml) | 212 | `1ffd1046f33e13554355b1ce8372d6accd89c8d43c24cb7fb1b050815bd56b67` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/nodeids.json) | 264 | `8d12f6e55e270bfc8b1a96ad240e667e056f821b1d23f8a2ce2bb16dea70507d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2640044ae2dd4ef4b2ced651865d724e\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2640044ae2dd4ef4b2ced651865d724e/target_result.json) | 50573 | `43827ff0f18b6fe560805dc4624daf4be2274fe5e93e83af4d5b56a9951d2d84` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cleanup.json) | 52 | `1b86c9304dd5fab2d27cd37b48b32981d1c479cf85110215ddf59ca49119bbdd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-000.json) | 18826 | `99fd37d8d332f64fa7d4d3e877ee7d9592c9751213c34acf16a2e2b700e47a7d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-001.json) | 3668 | `d1adb051b3e6bb9b7b8f575684a076eab604f70a90d7a67e24773d3ae60f0aea` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-002.json) | 706 | `704f7263438d29a35bc84544ced5ea91fbd0389f3fdb4fad9254c8f77d740c2e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-003.json) | 1642 | `7ae695994a54a034db7cee63b4b810f107be84c02c890fda6b14253f3c94003d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-004.json) | 703 | `886ce0467c2d146f9fa60267574771f99e061adb2a99fce36cbba3d8bbea3a3f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-005.json) | 1022 | `33960e1ec84ee87d7ea8620a7b57092a00c967e90148d22624f2c9fbc3a553ca` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-006.json) | 3380 | `840e31db685ddcc26a1fd47cccfc97f87b7eb5b4a4aa1ba3e73b2e8f8c45f933` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-007.json) | 1067 | `7aca30bc9aff1517aeaf7653f165264d3b30382465a2d53d3500b193ac5c885d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-008.json) | 1057 | `a069507a05ccf3a6d51eb3dfb29759867f8ccc117403fa211a5ffde13374c67f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-009.json) | 1045 | `f26b037f3451bca684fef568a783850c8c42edd94ce2f341a2b1187f3cc87e27` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-010.json) | 737 | `4930974b7abaac79dab281ab286efbfa72f352eab47537ad7c5bbb77370ac100` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-011.json) | 9060 | `6cc3164c4b69b1e6b58307c79893e75b6b4ea24ba1ca3e0e991a37cd7d7af2ca` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-012.json) | 632 | `c3d4f41315932feb764cc6005341c70fd2fe6bd2883821a546f7322bcd9659e0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/cli-013.json) | 722 | `2d32c8f3feb32c87eb9d139be02bb5ac0edfc45b5d51abbd39c873eaf8b2dcb8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/command.json) | 55797 | `5b47970b48c3bf5d1fcd4b304857eaba8ab78bea6c97f00fb8bb53fddb472614` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/config.json) | 25708 | `8b89bb07b4ca803c36837e5f875ecd809c5e63a069ddb05f3f29bf44dcfe7a70` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/junit.xml) | 212 | `43d4b471905773599f8a332c18fdd378769e1f552ec816b652949b47e035245c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/nodeids.json) | 264 | `8d12f6e55e270bfc8b1a96ad240e667e056f821b1d23f8a2ce2bb16dea70507d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\2ec2be20a12e4e129fbae07153e1bc95\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/2ec2be20a12e4e129fbae07153e1bc95/target_result.json) | 50573 | `71114416e37a4100f5d4c6b9df9b2f4f5c79c7222d7e75c3b1f3e7f009eb8663` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cleanup.json) | 52 | `30d76b7b04c6f35e632ba5e01c8d348910bbd05c08e2d147019f32afb53eeee7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-000.json) | 18825 | `751fdd77c49cd94d512a9bd9220f03c901f759d3d3685a1905a56c1b3a799958` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-001.json) | 3668 | `dc3882bbadd72bc099ec510541cff32e1da2b6611bd6904d0638890474f62c38` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-002.json) | 706 | `9d5c69476d516f027d2f4c00dd9fa81b6088b12e2f5c40a47704d251ef156290` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-003.json) | 1643 | `165de44a76d17478893902dcebc978498fb87509e07ab76a1e8fd2d2a05e36b0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-004.json) | 703 | `df4260bd367b23bed74e137b07e43ff5db8f7e8f7e5fc7100425dd997b03133c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-005.json) | 1022 | `8a1cc848c72f0deab5e93aaf114f330f6b726bf3f0b21c52fa0caf5ab42ff145` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-006.json) | 5079 | `117b7c0116897834a84a514da60b072afe30067fc2b408f0a4d88fa9a4792aaa` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-007.json) | 1067 | `6ba356370db7200a2dce08bebf1ca13db4204d5d2d7eaa8bddd52ed85fdea207` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-008.json) | 1057 | `470e91d13343c4eb9e9517dd0fb869c530620275f828ba9a8830964366e69781` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-009.json) | 1045 | `3b8cf1fa84d8bf468fbe7ad71d1153ae594815a47b026c98e2996160604fe6d5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-010.json) | 737 | `cb98d94711d660532e6cf74161ef4a8fdfbfba2243c6fc9b3c40d2218d91c6a9` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-011.json) | 9059 | `3588fbc1a18af55d3da92fd5a2f42ad6d810d1912dfe24104f6689610910a52a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-012.json) | 632 | `fef115dfce0773a3de78ba5532bf814c5ae7a74e1872953af7f5c9ac03959569` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/cli-013.json) | 722 | `dff38a7e9fbb24090e02b465a52b7af114fd1f740973bdfa75449ca500b52f92` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/command.json) | 57450 | `62f3f93d12140d23e5112a70b115218cc2691585c2439abd62b16c35f79e66ba` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/config.json) | 25686 | `fdb40ba1ebcc34f6d7f4234b43dbf4a3195af247077aae8a920c99dff3473a2a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/junit.xml) | 997 | `7b4682cee232caefa0e095b2f270e98b3ab2921af58d229085a69d13ef53adfd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/nodeids.json) | 564 | `57277a152e58421875076686a5bdf6ca24a657d60fb4d37d89fe91c61fea275c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\4333e25387a24d4aac2c32a331e0db58\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/4333e25387a24d4aac2c32a331e0db58/target_result.json) | 50551 | `b7494f7ac07c65b037ff4b2076976f08f3d2d398c7b3b24f0e73d40552ea3a74` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cleanup.json) | 52 | `a62d2c1ce4bf4b52057ff97c62834322bd8228dd65b3335587a2b2db673c443a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-000.json) | 18825 | `b79296ba8710530784d3c41b6c5ea10d8a5ad0da00d36e9400e374610bc7098e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-001.json) | 3668 | `790ee118bfe9c6329a0ecf521bad659ab6eaa0935c6d80da6fbc333f7e9d1658` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-002.json) | 706 | `c10c6a216ec8adb509cd4620fb4afcbfb02d2c63472319b8f2563c86ed2128b8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-003.json) | 1643 | `0be6129d060d430dd50f0f4ff95fe265d304d618f89b075e76bb233d03bd6ad5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-004.json) | 703 | `6f1778d58f786d66b595e947643ad688fe8a1a755af40dc1beb4cd96fa250894` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-005.json) | 1022 | `36b23dc842a828e497a47e53cabddaca0d7b2afd4a24cef79f85ef18d4d89c77` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-006.json) | 981 | `2fdfade24ade95b4bc718221b59284df5853a40eb40ca766c73988d1bb40e754` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-007.json) | 1067 | `5b54bc2d4164bbfb20c0409968b81e55e993baff28e3cdd849dda5dc97f35832` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-008.json) | 736 | `9488981fd625e897cd5d8b8b3d230959aab6db6d23d78becf38fd8d849021375` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-009.json) | 9060 | `6471420c2ef43cf6f903ef1283b25db120cce36889ba5c3a0742469fcf944a51` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-010.json) | 633 | `a9572d9844a1b1d876565cd2f4b846e6cfba3e44366664d103ffba621ed1044e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/cli-011.json) | 721 | `c6fec72d0fd4cc8f9b9eed3bdc152f827e991d7928e7664a6cb67f4df98c0bb7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/command.json) | 55546 | `a6c16864e8efbd69df4e33dcd579a1a12e7a382e5fa065468ea46ed4a17fcf36` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/config.json) | 26748 | `d24579a12dbb7a9efbb21d0d815a43b373240a607bfe3da4fa021cb75f6332e1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\8e4d1438d4954767af8c11f0857f3c50\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/8e4d1438d4954767af8c11f0857f3c50/target_result.json) | 51613 | `16bceae6a8d65474db85e03c4fde474e412d031826a3ceea70f10de4c8ef0622` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cleanup.json) | 52 | `d3e5de3157debf9a1ea40c581e1423d893b754aab324f8e0afc3eb32705eadfd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-000.json) | 18826 | `68c10d23245d04adbdea8e96d29fbf6a56eb05a21a5624ff5c3941a61ea2a9da` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-001.json) | 3669 | `ac00c77f2c06999da82e07de1437990f5eb8ede9c6a862d7540331601f49749d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-002.json) | 706 | `ef2d6966a62e24dc214cb5556eaf7a2139faaa7947f55aafe3f146fa359e2dbb` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-003.json) | 1642 | `a6276a3832a55d1a3d19b21975156e9970da1c68110d770363f632d799841b5f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-004.json) | 703 | `2aac3ca5290e63459289f2896a6462bee1398f84620a87b1a9215894692707b8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-005.json) | 1022 | `4ae46a2c8451cf43d0906b51a6406dd9fca5cabede78ec98c250bbb403c0df01` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-006.json) | 981 | `f730adad924ef8de8ced7929734b1198eb7689cb29039fd4c773eaba2842101e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-007.json) | 1067 | `9d08b2c2a2b00ce8bcc394364f92667f1575971c1ae4e184bce194c536792f71` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-008.json) | 737 | `e0b5cc7da99215b5d30c22fc1dcb2d7752479727db3b299822817256896a8a9a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-009.json) | 9060 | `4e7511d04f4e68301361ef4729c0ca5fdbc14749edd1515ce51d92938f7d60ae` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-010.json) | 633 | `6912976e3f2d148b603f84e5f60b129e2f243b022872278944c59f5905f7e14b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/cli-011.json) | 722 | `85ea3921f9664f7dbd488d75128d4a2a11c0126d74a668aea15e9ae80e0629eb` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/command.json) | 55546 | `e6bda9476a212b38833055e478c4fd966f55a1e1c99ef804e226d95837296257` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/config.json) | 26748 | `89dad01824b50a938c9a966216772b5da8f049acc53ac4ac0781bf5a1f4bcb7b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a07907c5f49f4dbcb34a0d37807c8f90\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a07907c5f49f4dbcb34a0d37807c8f90/target_result.json) | 51613 | `58b204eba9a3a28947428f35c8efbb7a179fca0a6bbe89fb5d7c9659a0ae110f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cleanup.json) | 52 | `276147a1f2728254650dc20de59b028a8a3ed89d43d695b064c25a7a23ebaab5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-000.json) | 18825 | `b40b1227f550feb79ae2457a829072e4095d16225b504a485a659377f4aa8ab6` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-001.json) | 3668 | `2400cc45f48c47fd1258b13acdd07e1435190c14a76bf6e6bfd7602724a15eb5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-002.json) | 706 | `6bcbf07f700f7f64347feea244bc2e9fb5209d268c690614cea1df538c10527c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-003.json) | 1643 | `70a8cbc5e4f13fa0b415437a5223aa223a102eff111b91b0ee6ccb48fa25e3f1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-004.json) | 703 | `632a55433d1f62ccaee56901c0945094bc23b2e1a162a67c9339c4dc53004615` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-005.json) | 1022 | `ae99733953d875f29211fd24131fe10c92bc20862f893c6138edc984df688c64` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-006.json) | 981 | `8811ce029d30e9fd37b9eea6059721e40e55c51f40bbf3e2aac689b24906153d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-007.json) | 1067 | `4182795199d5411900dce3acfd5b1b110f5a8bfe81bdaf88a16b2df36c662c41` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-008.json) | 737 | `9aa6dc7a8b893df44dd623d244edae68806d0974f80eee8c57c4af2344b24f9a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-009.json) | 9058 | `d73b0115fb132855defd4399df601456dfa910aaf57b5b2fc563ca503172609e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-010.json) | 632 | `fd690a4a522b51ac193a96b3899ceb1ee954c7a60e2b382cb7a0a03ff49c9113` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/cli-011.json) | 722 | `fb040c69302a136e7bdda8e54dcd565a18c0b6aa0ac680ecec4cb4df78735798` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/command.json) | 55634 | `abf4a2bbb1bf0d2b63913725f4c7ba5816c1a206ddea639ee18e57f82440bfb0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/config.json) | 26791 | `5685a9f83ecbbdfa5960ee639a0eab26211c6247dda095cb4ca8ae75a8a3e55d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\a8238dd3b72f4e8ab9ec81cb1bfa491a\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/a8238dd3b72f4e8ab9ec81cb1bfa491a/target_result.json) | 51656 | `9c412f42f77b0eae886f3ada3d706a4b5c0b1f1fb042efabae0bf68a43643842` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cleanup.json) | 52 | `70a9b1f7f98c020138a0306e4a702bb4ee82bfd13ebdb17fcc9606f1c59a3404` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-000.json) | 18825 | `933f632789b6f54080fee70171992773f41d2053d6deed4ef7adcef0f98be870` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-001.json) | 3668 | `bda87e50c433265432221595354a1a2f9137fdd8d2e1cfd3d774b13498ef89d5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-002.json) | 706 | `f9a8d189a304ef41ea6bce524e4e1f8afdd8bd94ed5fbc7469a1889819d5b03a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-003.json) | 1643 | `271ad9e4dc6912555dabbe3c2478a03a192419d0b7081db58d5a48faba2b96f0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-004.json) | 703 | `1ceabf747465d860c61e43381d20f289b76421151d05da3f979aed5beff89f8f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-005.json) | 1022 | `40286c517dfa2f191f3ccefb7fc0aaa53faf11c9e66f1e7fa9091758813139e3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-006.json) | 3795 | `c3c41d879815f2c8f84afcbd1953b9d1fab2527651d722dd2162f0b1adeac152` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-007.json) | 1067 | `cfb3dd6f5461f1e2bafb6e38d97f9c25e4a872a0a1e12b8fa2151568aa2b7fd2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-008.json) | 1057 | `b2e627001b146d56e07e5c4d74787f7caeb97c0284a3f3fb3adf36a0220cf937` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-009.json) | 1046 | `f58b6ed59c2dd7b19bfddbb5e0094c480a5e2322d1abbc3694ba5e4207c59928` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-010.json) | 736 | `1f89528089c4795b55f2f49a8fb1a326368ece6b84eca4073dd2e5539222ef46` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-011.json) | 9057 | `b6e1b81af8ccc46310b501fcac652188f5ca5a3d0bb81e8efffc20751d7d84fc` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-012.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-012.json) | 632 | `c9a0428da74cb6790f847c03bb5c9e958cbb83a13546753d98f5afc4c2db6b2c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\cli-013.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/cli-013.json) | 722 | `4960f093b37e6c83696e5329b5132c2c49aa05c2b8b84e5eeed2210c074d1bf8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/command.json) | 56166 | `1f6b216b5bfa573c40278bd3d9fe692e4c6a1430a139de5451423fdef6a29446` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/config.json) | 25686 | `ba7709a7414a41002167a0a3abd9c9fe18501dc3e95e607d6316ef37be2f878a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/junit.xml) | 425 | `065daf1636a1aec712a8d6fc1cc739e03b853c9ea6f1b4be74443b8f102a52c3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\nodeids.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/nodeids.json) | 564 | `ee0292b4d31fb5671a366129731c755fa237927eb51557ef75179b128ff17386` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b504d4effcc341ca979405490af99531\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b504d4effcc341ca979405490af99531/target_result.json) | 50551 | `740037bb7c65a5b3c2006972205c58f6c47092b8cc307cff4fc8d395a3bb4fd7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cleanup.json) | 52 | `ed7046034b77cfc19b38ad845cc53b770125b0ae5c16289e072f6151ddbea0ed` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-000.json) | 18825 | `e17d593c50e63f456c58247796e9f67172d0b1e858b46c825a30c2dbaf1f51f2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-001.json) | 3668 | `0b8123ef18d2f0cc11b393905e0af888526ff223f120b5391adc1181f731185b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-002.json) | 706 | `a7036e34d9de57f5b7d2c2cb9f2232021ca0924bc1b927bcd4c23b2dee024b39` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-003.json) | 1643 | `a44d12f6feb1c367d8c610bb670792872795d7470e309f2771055c17810b85ad` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-004.json) | 703 | `b508945753e951bd2a99bbcab38789ceef36ea086ebcb7f93dc9b4c9bdf64a98` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-005.json) | 1022 | `f7239a4bc3b51db5db8c8c918f0a9263d98adc6ba7e0c83f82d951698fb0fb34` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-006.json) | 981 | `f7790cb317636a053efe1bf2d7104b6afae0b9cfde1a2edc851a9c8f90e1fa23` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-007.json) | 1068 | `1a3c8145229aa8f9e230246b4617e1c5694acdc2cfc298a27c9ca9f1deea9969` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-008.json) | 737 | `3d8de9f14f07f85a92c924cd6077e7d0718ad0ccccd94035ea36993293f3d87b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-009.json) | 9060 | `8c9be613b18b6f5210040113d45b3ab0b7585a3fd6d676e218edd3b0a5ef7054` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-010.json) | 633 | `755c7202112c8e31b36fd910a01e62b312978e94f2db66ee92287f552b13462f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/cli-011.json) | 722 | `dc338dfc757edccb2f3eae268169cbaee512524d3489f98806b56880a0e1187d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/command.json) | 52972 | `2cf7887de40e468abe279a5aff86056a68d61eae759328fb93c5a829910d8ad4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/config.json) | 25503 | `d37a38dc93203e02342fcaf1dc37d16bc14d4eaa5eaf229da37ad6a06c28bb47` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\b91807cc234c45bf8a714f3951047cfe\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/b91807cc234c45bf8a714f3951047cfe/target_result.json) | 50368 | `89f664082907b8ffa55673fb01f5875361fe2676e2e7d37e3d60047eef5bf677` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cleanup.json) | 52 | `41a1b8ef17537ea3c3990ad851d0c6b9dc91b586beacdb83ddc9b4599425fb29` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-000.json) | 18825 | `41fffdc42a19344af0d506f7430dc982e26330656ebbabe805bb6534f637060c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-001.json) | 3668 | `336419390305dccfd364478cfc5f5217d4d65e1b21c0f9e53b99d3788b5ec332` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-002.json) | 706 | `87f80b58adaf2b43fcfe99bb3232efba98b04564243a6ff9681567da50480782` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-003.json) | 1643 | `96bf0399231464f60c3160da017a14a1a1bcd567ae59e5ca62cd5d0b3fbc8896` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-004.json) | 703 | `3f009d4c17f1a5fc158c59ef62afd82a10dc7abc65722891312bd5cabd315e41` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-005.json) | 1022 | `5bb142ba8e4c5cd08b8825863f64f8d885533a25e6ae610e74a9a40b016a2e23` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-006.json) | 981 | `0cfb11cec428f2b4c14c7d745059576eca47ee89fe20d1784099ad888ced32e6` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-007.json) | 1068 | `4809324a8f73a0d3af7d7c77051d013424f3d1035090ada41795b4842879a575` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-008.json) | 737 | `5e2c8f987acba67e58f2509bb0d8425ac9f0dd278780417fe94df80ecfbaac57` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-009.json) | 9059 | `1dda78bb15b2514220034da662ab2eb97e2f43a6634181bddede3c9a0bf990b5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-010.json) | 633 | `9313925721fb1b4fa12fb9b4ad982fd5f36488b87cc2c15a65740bbbfe6e5d5a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/cli-011.json) | 721 | `a219927d135b18002f106bd515fd3cdf0ecad03cf48cb98eae98b85fa35c2e54` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/command.json) | 52972 | `75a3c15b27db72f7a7d5f929378aa6fd9cece5b1458bf5a4b8218a577032cfef` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/config.json) | 25503 | `afee155f6285192a3f45340f7aa2d6ebee627b1944c85dc0bc9eececebedfbf1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\c3289d5328a247938690467c704d1da4\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/c3289d5328a247938690467c704d1da4/target_result.json) | 50368 | `cd0905d48d0c63adec324589ce2c939308c9b4f72d11949c8c5179d1e765e131` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cleanup.json) | 52 | `c8d1347f482849889e88d0df512153bb08896dd13a98a666110d34f7cf16abaf` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-000.json) | 18824 | `b5f6d178c4476aca2c3c9b0614a3686948150c0096e7b34d3c510ace4651308f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-001.json) | 3668 | `93780995afa88f1f05d3f32f8d624c9baef17aed530f48d3a4325822a76b6e17` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-002.json) | 706 | `02eba256727b3c54cd2085a2d9ce3454e6c7c7a35b58534418a9ae46cfdc3554` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-003.json) | 1643 | `d4cb889cd30e00e3429b3334ef2edc3430a8e7cc65088a903a135520ed3803b0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-004.json) | 703 | `79d3036206e46c59d253f3ee0f4103e85a719aa51cb8d44f3c249e5ce04a6b0e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-005.json) | 1022 | `8502e870f161f065e7f316da284165e0d2e3f0713d165066b0e394c29e861df1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-006.json) | 981 | `f4a8cb0f5ba485c0a78a8fcace2c6be09f35a78ae4967cf1ee0a4fbc5d096952` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-007.json) | 1067 | `a96bb35216206da9b438ed79639d2de60a8439f358a5eed1eca910bbd448d4e6` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-008.json) | 736 | `f44528973849febc8bc384dcc16e1d0232cf0f5db4bf412d140108186724ff52` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-009.json) | 9058 | `5eb117a707869fcb6b75c7c71c3e6aea4b704954fc2d8f2783d20b9cb81f21b2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-010.json) | 632 | `125855cbfcaf1ce063bedbaca4fb7d6a69e1c8d629856ea537f5981628f5a81b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/cli-011.json) | 722 | `3302f38757cda876aa45c62c7d8c0291456f0b7dd3da2cd803d144d2369dd819` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/command.json) | 52972 | `2dd2813fc1bc243767c9407c397a333f8e92fc800bb99ab7fc8367d6aa37d2ed` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/config.json) | 25503 | `d546c7c744cff1b9a4c8e61195394cf2f4a034903819ad57e568caef8eeb3f80` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/snapshot.tar) | 6287360 | `cc50ae0965aa7ac65a5f119b00563a456a33203d94404d11a6f6d6eeb2cb1cd4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\d70f06f9beb844d3ab78a3f63b5f6d8c\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/d70f06f9beb844d3ab78a3f63b5f6d8c/target_result.json) | 50368 | `09ed0ac8909a94b03b0a08a78e7ad2b502237abc56d254130eb3cfb3fe618190` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cleanup.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cleanup.json) | 52 | `820206df04c3d51c89f93b7bd9e082f49ba9488ddf4a0f5613ce359947cfef8f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-000.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-000.json) | 18825 | `7a696fab18412b8892e40dfeea60c7a58bbebeafeaebec9f8dc8644ea898f4a0` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-001.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-001.json) | 3668 | `92843696f2e22a2a6820ec761ca60c7d33f50e369d21f532ec7cd96d4ccd5e3a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-002.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-002.json) | 706 | `7d583936e690236fca353b112eb89a8b9e89a21636c157d213817c8c759e2139` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-003.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-003.json) | 1643 | `19cdf1c922857dfc7214d9c0ac3b0a994debe92f1977d6ece04ff4d5652b03bb` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-004.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-004.json) | 703 | `23de10558358ec6e91538e73f1725bc4b745a90acd3725f3fec824f1b2c20bee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-005.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-005.json) | 1022 | `8ebbfe595a382af1718842ba01ee2626a6330d2601c3fdde59e79d0cbc967c3a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-006.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-006.json) | 917 | `fdcd30099d787e6b6c926e7699b4be5584792a6425925581cc7007f2d793606d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-007.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-007.json) | 1068 | `b14a7ddb019736ad4e7773b47c3830efc406f0b8702a2704ca99e7286f5ecf34` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-008.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-008.json) | 737 | `830c9f7fc60bbb87b494642b3ecac83b1ff277e1adc1ca3a52ade15bae750c3d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-009.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-009.json) | 9060 | `6ac0075a9b0867bf07dc6a6dc244a9d1dd7050659c2004fc6a03aa795af530cc` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-010.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-010.json) | 633 | `5ba6a71f38f9463ca8dda7c1d4e197d521cda75400aed91706500e3f3931b324` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\cli-011.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/cli-011.json) | 722 | `e20ac3cee951d6b35b022a78d75296bdee446dc61bbb39a4d401c7b3ecfe17d2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\command.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/command.json) | 52786 | `28e8a8ea8c0a385cd1e1daed9da8b1e07aa5c9b46b9964d96f111be634939a2d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/config.json) | 26560 | `1111370d214b188ed75f787ea49bd7557256b91b50d2607fa58994df9791da26` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\docker_probe.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/docker_probe.py) | 6782 | `01408b2d5dcb36136290426905d810b7cec9896fce3cfacc0fe7ff9a24860c19` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\mypy.ini](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/mypy.ini) | 88 | `5dd48be92168fadb88322eaa068922fa3249f8cba740ca4ac3c13c0d7a6fa7ee` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\ruff.toml](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/ruff.toml) | 29 | `17bb1eb2799030893f3059f4092c772439d9861afcf71ca3f5a6dc277660b4c7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\snapshot.tar](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/snapshot.tar) | 6287360 | `3c0578b2419804d31474bfbf52b0b98a5f0cc481490ca6b02776b9991e204656` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\control\vgar_pytest_reporter.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/control/vgar_pytest_reporter.py) | 1586 | `787194d25bad8c9e3b4f815db804cc1f4eba129fbf5832ef1c86222f18ecdfc4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\docker\efa21860246a47e8bd694b05e2b71ba4\target_result.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/docker/efa21860246a47e8bd694b05e2b71ba4/target_result.json) | 50336 | `22045774d88ac040d6a5d99070c903099d107c9ad18f508f7446e9a7a3acdf37` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\evidence_bundle.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/evidence_bundle.json) | 35884 | `ad39e4772d32f54dcd950835074c7de64b691f70cd5e20ae510daadac66ef842` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\prompt.txt](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/prompt.txt) | 9177 | `32fa2cdc6868f58ca52eb3105d754bc67601b581b3b81bfdb0c9061e1b6ad8a4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\raw_model_output.txt](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/raw_model_output.txt) | 473 | `806cd813968c5f2654b1050940be1f773fc9d0cc00376a4e7b406551b4111d8f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\run_record.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/run_record.json) | 2808895 | `fc28a05c2df5afeb0f5f681e8dbd755d9ccc8d249a28e5235ec93e1bbe0619d9` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\session.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/session.json) | 2770978 | `db4d3bfdfb10dcbd95450524dbe35e689c07a94a492b147f9f1de493441d2840` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-runs-05\20261024T104018047265Z-61c601678725\transport.diff](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-runs-05/20261024T104018047265Z-61c601678725/transport.diff) | 473 | `806cd813968c5f2654b1050940be1f773fc9d0cc00376a4e7b406551b4111d8f` |

</details>

<details>
<summary>supplement — 122 files</summary>

| File tuyệt đối | Bytes | SHA256 |
| -------------- | ----: | ------ |

| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\checkpoint_gold_final_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/checkpoint_gold_final_07.json) | 1089 | `b248a67b3db5468fcafffea581b4b6bc8fb53632649ad2d03d123634e6b5792f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.json) | 1846 | `f8a540e4dd7747445fae1c18d91d134a1df21f4784692d4196cbb0a4e1e12c8f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.start.json) | 949 | `f400051e6050f46bc9fb0d24dcac0a297e27d3f3d8ecd882a4cb60d5504e9e40` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.stderr.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\final_regression_06.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/final_regression_06.stdout.log) | 755 | `393078e23af94d706b05c1723d03c547c8081e045d2e6b86d3c091d45e234625` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\before-gold-host.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/before-gold-host.json) | 1196 | `124d68e138c6dbb819b6ceb2dea76b6a1f150c2ac1831ee4888a469706270eb4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\before-preflight-host.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/before-preflight-host.json) | 1196 | `9716176598055c8720b30931187e78bfe6c746e3bb47039a770ef21dc62aecef` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_07_control\gold-summary.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_07_control/gold-summary.json) | 1505 | `558ce5d132ea44df2e7c3331ce03db9a6788710215fd1cd41437b249c357b841` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.json) | 2773 | `8d4de151692ce4f547fa1ff3b8fb75427e91df7f4ac8d283a2d168d14ba5b665` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.stderr.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\gold_campaign_07.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/gold_campaign_07.stdout.log) | 2115 | `802df4807374bfd495e2bf4a0459bad4c0c09b89b89db5b108db83c0be52f0d7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\independent_gold_audit_07.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/independent_gold_audit_07.json) | 10159 | `238a59061fdb2c5dd3b1224065e7240c739df8c8c0689eac397db950d0b94a12` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_06.json) | 1159 | `1410844f189de91c5b14cbec7498ba686214b032e7202ad9cdc1208ece516f99` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_06.start.json) | 403 | `2e22347241ffe9b75f74024823c4414da68590bc872f3bd02964eb554dd9732c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_changed_scope_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_changed_scope_06.json) | 577 | `21c72bfeb335afd0ad44f6ac3e27aaef90177e5ec9a31d417e581ac348efaf8f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\lint_changed_scope_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/lint_changed_scope_06.start.json) | 433 | `ea4c357f709850f08602bea7cf37e92df1acfc989caea53471f38e6d5ccfdc9a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\linux_wrapper_02.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/linux_wrapper_02.junit.xml) | 6819 | `99a7ca4adfbede73b195ad1ecd7e7582fba090060ff2d0649c4effa3dcbf9355` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_fix_06\green_linux.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/green_linux.junit.xml) | 6952 | `96804df9c989d2a0bc49f238ed790289ce1cf526a997ef3d0082fea3991fc6e2` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_fix_06\regression.junit.xml](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_fix_06/regression.junit.xml) | 61371 | `5350cbea0bbfbd7ccddbbb331ca3c3368b2cf5ebccd941614a395dbd28e6ff4b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.json) | 1155 | `72324eef013406cf577e32fe623ab3a6481d3cc1e791c162f4646915141f1992` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.start.json) | 792 | `cebab54dee4e58fc7461adf22ac66741d49d4e63bf7cbcfa33f60f4e4fc89ac1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_green_linux_06.stdout.log](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_green_linux_06.stdout.log) | 241 | `aefb970c0bca34f9f98685813990695ea5f18d6f1f5191b12983564536f3e817` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_06.json) | 7575 | `6694eb1f5b95f5a75c9eeac1a61d461366ceb1abe5654436a767272d0a463cbf` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_06.start.json) | 566 | `8af937c085fb307b07fafa6e24104f838b054cf669f5a4559b345d59b8531f45` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_linux_06.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_linux_06.json) | 2108 | `4ef929d0d4207569707567373f027c02057209fdba13501afe5a01fd7e5b7d7d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\path_red_linux_06.start.json](../results/m1/w9/m1-w9-4/20261023-local-qualification/path_red_linux_06.start.json) | 850 | `b8be7c329b64770c59719fd4e9053b8bdb9d7cff8c9533e8d1a85f6229b8a2cd` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\20261023-local-qualification\run_gold_07.py](../results/m1/w9/m1-w9-4/20261023-local-qualification/run_gold_07.py) | 6386 | `1deace8758c09ab149bf50fd54123ac9301bdff6dafe8eec68246cd1df8d783d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-4\runtime\qualified-profile.json](../results/m1/w9/m1-w9-4/runtime/qualified-profile.json) | 1861 | `6085ea8b5d50d4482533a605f7b8c9f99bc2d455bfbeb1ef62ebaea8c700fed7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.json) | 1121 | `754a55cff62b4cb28f55f23c0fe25aa181d2827056ea8f3ead54ded41739165d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.junit.xml](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.junit.xml) | 5763 | `2a5d80f19fb00cd8fd678c82c40da058ce99fe23dfcf5b868f24433eedfbbe51` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.start.json) | 771 | `b10b6d7bfa176691b0ebd1f99d43274ba33d9cb328cf4625ad57351b59445cbe` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_green.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_green.stdout.log) | 228 | `bd68296c54005c24dd5e2755d253fb608f993220d56e6b7341f86fd265c43bb8` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.json) | 2439 | `ea633e30be5f2858351374b775cbb978a6c2145aef42e2d827750b2783f4d7f4` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\base_prepare_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/base_prepare_red.start.json) | 829 | `84dfdc7b9af2888677669361d8e4785ad60238908e727b03096c58ad9ae6f489` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.json) | 914 | `4c9d819eaa8ec57ad74fbaf80a7c0dc728ffc1150429168d3fd6d453d43a7334` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.stderr.log](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_run_02.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_run_02.stdout.log) | 321 | `64707e1d0fd12279be1a8c264d59cb2adaccd654c3f525a919299cb22338754d` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\collection_summary_02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/collection_summary_02.json) | 1988 | `8a79447b96acd54a4f05164402be65affe6be75cbb01d74713a1509250879af3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.json) | 1125 | `33034f34e059f6760d8bcea5702913c9731ab85fe58c1c4c9d1b18e7acacca2b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_green.start.json) | 773 | `e414aa0d1f8a4732911cb80379192b157f899d2addcb230e8a82ad7f341bed31` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.json) | 28805 | `b15c9468f1f77d570e908d7468e6a2f6316fa29081cc7c23b407d0c53f2bc390` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\contract_probe_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/contract_probe_red.start.json) | 771 | `a3b0fa06c6ba9bc74777dfcc3aea0c122bf627efa484c4c329ea10973592cf36` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.json) | 1115 | `f20c1bbc00beff6e99f08fc5c5234c8d83b2a6fdd533a8dd0265e119ec5322b2` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_green.start.json) | 768 | `bc31c9f06bc9ed586fd52c4fcf84226cb0aec9d47ce93da124050cda21deff56` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.json) | 1759 | `022c828216b52ee1cc753b3fb1e3e71dd19ed106ba20860b17f35bc04944fcdc` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\discovery_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/discovery_red.start.json) | 807 | `c4a52bab0ea94be9c46b45331fa1d27996c38a89d5dba4933d068411100cf705` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.json) | 1109 | `d4e281ffdcf00730c048bab9e694f52ec5d6a5194eae488c044f8dde29f4e713` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_green.start.json) | 765 | `5ccfeaab4aa0b672af52101562ec17de2ac9111ebf611dec1bad7d26c7387f82` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.json) | 5294 | `c17f1a44f09919c35efd2de0da3a14e35244a498d8c27151293dae985196a995` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\docker_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/docker_red.start.json) | 763 | `7b2321279374f752c7aede2ca3e10be5b770f40629155d6e300b56d24f6ac11b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\full_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/full_green.json) | 1105 | `3735f9eca69cc9e374b60668c894a8dc21de1fd74368905c9f5ac04f7578853e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\full_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/full_green.start.json) | 763 | `024831dbf6303425d3716145f94991e97309b2427425dec0bc901ed31e77f948` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint.json) | 631 | `7821fb8b0ea9dc87f1943cb9bc12db15ead5b6c1edb31ec080e53a24e7af5be7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint.start.json) | 487 | `6c5040b7161e5550a69b5bec2eca8592d5865bd2451305c7538530d8fe86a4d1` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_base_fix.json) | 631 | `49ab9cdc429f5c295f001dc9fd7f3b1e00f3d22235d22090cdfb2c3ccb02d87f` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_base_fix.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_base_fix.start.json) | 487 | `a65234a2e1f81bcfe03362fff0ba5d094882eaaf2bc8f19de32ae4627234b2c3` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_final_candidate.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_final_candidate.json) | 631 | `6705b37930d11426e806f5524d1c752a1563c3b2c9d2c4cd08fbbafd54b05c65` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\lint_final_candidate.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/lint_final_candidate.start.json) | 487 | `52c427f1964bb7f53637d8cf1f27cd54c4fe2667770d4fd3dfaa5c171164114c` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\output_bound_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.json) | 2330 | `695bc5c4f9e3b9ff7acd6c0d7ce6a2ab7ba139b1a498c990068eab7b18a4462e` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\output_bound_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/output_bound_red.start.json) | 807 | `30565f95e20da6c5e47f53b96f8fbc9705277de0b4e976e2384a1ccf5f14d52b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\qualified-runtime-02.json](../results/m1/w9/m1-w9-5/20261024-docker-only/qualified-runtime-02.json) | 1632 | `a3dd9e2f69035742a2ebd888dbe1db4197967825a59a920118bd49f16f95bd18` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression.json) | 5299 | `907887a1ddb2adccf355fbbc4d50fceee2136257f123f13d772c4b343025a616` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression.start.json) | 722 | `b7eaee930c4f1da1b7666e479b615b5387f6935a66c9b9f497b29cf8cfb82a9a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.json) | 1425 | `819b13156a092d84457d66738c575e7cb15d8d4c5990170e0a4e1c8443ae13a7` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.junit.xml](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.junit.xml) | 42026 | `95bbf732b2266c34b847c131dd4b3340366a2ef442d523e78c8ff445c08ca2da` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.start.json) | 729 | `53c0181baa3373d7af2399e22463e5bc6effbc899f702f35b6b0b9fa5dd3f26a` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.stderr.log](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_base_fix.stdout.log](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_base_fix.stdout.log) | 558 | `146ef41bd8d34c63d6144ae0cd8c6cc96c079b58896094c8a5b49aea5f398009` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_final_candidate.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.json) | 1441 | `860631b7aa2a6b9825f249656f70576275fa71178972aedc02ef018ecfb0699b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_final_candidate.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_final_candidate.start.json) | 738 | `129006e91d5f968ce1bbab999f343d4eb568c57511d21a5869cefe51d1207440` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_frozen.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.json) | 1419 | `b3614b1009c3d661181835ea09ac863dcefbd905f856d203092d7f8bd218ed51` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\regression_frozen.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/regression_frozen.start.json) | 724 | `59ba44c45e4c02b59be0e7e1ccd6673d3407d23c9baf4d6ae4f1145a9f7a8706` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\run_local_02.py](../results/m1/w9/m1-w9-5/20261024-docker-only/run_local_02.py) | 4178 | `9c3b57cc0a13449ec0f08e955ea80d53b2ed3784ffdfce4be0bba9e8bde66902` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_green.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.json) | 1113 | `96a8a0496974bbfb7aa6f3ac3775a51b1a1c9d2b8b8409da4ae5e2f6be73f6c2` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_green.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_green.start.json) | 767 | `4fadd4f8146c39cef70590d96de95b12fa2d3c6310b8d2043628c3ecd1e026b5` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_red.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.json) | 2686 | `b89b6daf39615cb717f13b1aec40d5bad2da3ab03d59dd8aab06a89f833fee8b` |
| [D:\Project\CAPSTONES\VGAR\results\m1\w9\m1-w9-5\20261024-docker-only\semantic_red.start.json](../results/m1/w9/m1-w9-5/20261024-docker-only/semantic_red.start.json) | 765 | `a315985fdc80eb055899b227e70a2baf83a6a74f5bd1a8f6da3c02a167c40b07` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission-05.json) | 26582 | `25b6cb0e733797ee9cdb5be69837b37f7b1ec3d9d157b0a8f76f8e5e26b179a2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_green_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.json) | 24549 | `f2ab2bbd56a24fb2e14d83a326ba8cdf8a006913ac04149b7000e278a457f002` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_green_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_green_01.start.json) | 530 | `381eebd9274649c3427a27dca4a5fe6c9e1043be1213da2c32794a637cd12698` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.json) | 28252 | `d1035638425003740b2378ff1936bdacaa6088232bc2d27985f7547e3a01b609` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\admission_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/admission_red.start.json) | 523 | `358a6e08c8c8a15e3105d6205b467633840a4fe24f8dbad2d645c3e0ef09fa91` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_green_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.json) | 943 | `9b24ebdae32c0346994f46a945f8f446ce4b372d50f9c124524e895e2b15a8e1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_green_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_green_01.start.json) | 578 | `7690fbf804e8cf954da30101e28f62b7303558d2797e642403a683c4fe5f7643` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.json) | 16375 | `cf3bfc2cbdaf8659bfb03a54e09ca97645d27bde4901fb8c822030fe26987db2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\bridge_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/bridge_red.start.json) | 571 | `7d539d8cc80dfe84b72e25833a5328bede70c2a8e1da299b753d6de4e7f6e70c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\checkpoint_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/checkpoint_final.json) | 4301 | `21d0b610ab85c0600971af0777916dd0e03e93df5a6c215129b0e310c891c344` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\containers_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/containers_final.json) | 730 | `5c78b2d617b8eec0a40c3b3cfbca4099b08a4852e3ec547044479d3af6e4750a` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.json) | 1421 | `816f32f543a420aaa3d184e2e62937f0ace2785ed81ce2615d2df146cec35453` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.stderr.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\docker_smoke_05.stdout.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/docker_smoke_05.stdout.log) | 628 | `7a4cf9acf7e6856fc454a7c64dd655a31cec02eb1f04632742f187b4228beb00` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_green.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.json) | 934 | `d159a00a7728ce20d71a8f6fbca8b0d9f6ac3e827a187a61729cc9dae02b9c37` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_green.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_green.start.json) | 573 | `53951775820c0de34c4a4adbfbbd14f2f6791d957e849cba40a924758c31d20d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.json) | 5622 | `7c1212e61489a8b9c0aafd996af14be729ab389d2d6fce321d92c59e665f4b74` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\drift_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/drift_red.start.json) | 580 | `3b1971c368d298493dd0f58868e7ebb2a39df58c1947f324b3fefc0f67d5789b` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.json) | 1237 | `c2c2e4db0486f357c9fab573b06208fb69a27ea9dad32c441920f791fc419021` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_01.start.json) | 529 | `da73b82df67a333ca20f596d57040baefca01c8b0be02209e0a5db4405fc0628` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.json) | 1245 | `d81e952a55d58ad61c88066d58dd5cd1f6972ca73408859852c2667a09043de5` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.junit.xml](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.junit.xml) | 43703 | `a1aeede0d3bd73b5d37120a55d2d8bf9054cf3e9068836f4a4f92feaa6bb5f93` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.start.json) | 535 | `f0d2db78bf3d26dbedfa4362aff06ce6b3b3090c13af9877e46e4f0ab1f6a01f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.stderr.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.stderr.log) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\full_w78_w9_final.stdout.log](../results/m2/w9/m2-w9-3/20261024-docker-admission/full_w78_w9_final.stdout.log) | 572 | `e4f413339bd3e539d23a5deec48154de9c891b943e436297fa50a1e583c89dc1` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\independent_audit_05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/independent_audit_05.json) | 13177 | `66864bec98be523d7d850fba5d3d061c95b3fab625ec03a437edf68e9ca72d6e` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_modified.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_modified.json) | 735 | `8681aad02800a5848a24d0f65ffa3e846d3c2fb20fadec68343d838a4ed8702f` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_modified.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_modified.start.json) | 591 | `688446b2d58cbe80b53f3e1a1747a537134985d166313681c6dc71e8f03d94a2` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_new.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_new.json) | 685 | `d5257612fb85461f12052ad9b980b75a47cfd58167daa6f09a27567e121bdc49` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_final_new.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_final_new.start.json) | 542 | `f639a5cf7d29d4bbcd1f53703c7d3962276d030532ab640c9a9e06526ff7ebfe` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_modified_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_modified_01.json) | 735 | `8669af4011b837dfbb5b37784b9198de18cfc843ca1c03e390bde0b037a53333` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_modified_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_modified_01.start.json) | 591 | `aa64a471de229f700752d5cca8ee9be3c445a38111074df452071f9e1f26baf4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_01.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_01.json) | 987 | `7225ba71bf58744e100d37f89b0b778451240cffab971d54d5323de1eaee6c48` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_01.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_01.start.json) | 542 | `a830b3d8ba279bc0637c151b87ccbef6db66c54ff2b6203d100216327c8452e8` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_02.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_02.json) | 686 | `7ac37585136dc809db6e493f214254bd9c46f9a28d1d9009e346131f9c708ce4` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\lint_new_02.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/lint_new_02.start.json) | 542 | `c2b724229ceb59de4d2925b8a9be8ece600f0d0be9801589895abed116812f8d` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\negative-pin-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/negative-pin-05.json) | 128 | `4fa273fb71a8fa50d8e5bcfbb9f1baa80f87afba91a53511c01ab97644fe7495` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_green.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.json) | 936 | `fc188efe5b6bbc3c415e7f4cda504cdcd85c02d6530583645c37c88ad82ff21c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_green.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_green.start.json) | 558 | `cea9d618d8b84c2b7a702676509f17d53289898247e61c8433a7fc087ef686a3` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_red.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.json) | 4036 | `2d852b21bbab4f404354a888baf4a37cdafb7271e10ab485cdc4f0bb2bffe1b7` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\review_r1_red.start.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/review_r1_red.start.json) | 554 | `323a83f5aa73841605e4688524ae936fc4b2fa1c424c1869f8ef5cf8741c1f50` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\run_smoke.py](../results/m2/w9/m2-w9-3/20261024-docker-admission/run_smoke.py) | 3325 | `db71be0ac598b6b4768fe75b4df8daa98caaed2ecd5bc06a3a3033fbc0d2c7cd` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-inputs-lines\candidate.diff](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-inputs-lines/candidate.diff) | 485 | `6ff8c0fba9d649a5a68639b5c2bfbb4addcc1c3013b468fe4270497ef1193b76` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-inputs-lines\config.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-inputs-lines/config.json) | 5909 | `549339c98e1de1966911f4ba137e5148f041d281b04de2f390daeedc2952323c` |
| [D:\Project\CAPSTONES\VGAR\results\m2\w9\m2-w9-3\20261024-docker-admission\smoke-summary-05.json](../results/m2/w9/m2-w9-3/20261024-docker-admission/smoke-summary-05.json) | 689 | `e652e37a1a1876022893b4e7406a61ade9a31ed702a394f12011d9ea33a5de40` |

</details>

Tổng retained files được lập chỉ mục: **987**. Danh mục không chứa thêm file ngoài các roots nêu trên và các supplement đã dùng trong báo cáo.
