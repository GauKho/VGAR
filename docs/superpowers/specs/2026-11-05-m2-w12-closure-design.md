# M2 tuần 12: đóng các phần còn thiếu trước protocol freeze (design)

> **Ngày:** 05/11/2026. **Người viết:** M3 (người dùng làm cả M1 và M3). **Người duyệt:** người dùng; M2 duyệt phần
> việc của M2. **Trạng thái:** bản nháp, chờ duyệt.
>
> Nguồn: plan W9–W16 v2 (`D:\kltn\VGAR_W9_W16_Deliverables (1).md`, tuần 12–13), lịch W12 trong
> `docs/status/w11_w12_assignment.md`, spec M3 W12 `docs/superpowers/specs/2026-11-03-m3-w12-design.md`, kế hoạch
> A0–A3 `docs/status/m3_a0_a3_plan_2026-11-04.md`, báo cáo M2 `docs/BAO_CAO_TONG_HOP_M2_W12_D15.md` (bản mới nhất
> nằm ở `C:\Users\nlhnh\Downloads\`, có thêm §14).

## 0. Vì sao có spec này

- **Theo plan:** W12 kết thúc bằng protocol freeze (cả ba người ký, gắn tag `protocol-freeze`). W13 chạy held-out
  A0–A3 đúng một lần theo protocol. Sau W13 chỉ còn làm demo (người dùng, 05/11). Vì vậy mọi số liệu dev mà freeze cần
  phải có **trước khi ký**.
- **Hiện trạng:** code M2 (A3, mutant pool, verifier eval, D15) đã fast-forward vào `m3/w12-all` ở commit `3f77fcf6`
  ngày 05/11, nhưng **chưa có lần chạy thật nào cho ra số**. Báo cáo M2 tự ghi "DONE kỹ thuật, chưa DONE thực nghiệm".
- **Mục tiêu của spec:** đưa M2-W12-1 (A3), M2-W12-2 (pool → V1/V2) và D15/M2-X2 (timeout) từ "DONE kỹ thuật" sang
  "đủ bằng chứng để điền freeze". Kèm theo là các việc tích hợp mà freeze cần, và hai điều kiện môi trường mới phát
  hiện trong ngày 05/11.

## 1. Hiện trạng (đã kiểm ngày 05/11)

| Mục | Hiện trạng | Bằng chứng |
|---|---|---|
| Code M2 | 5 commit của nhánh `origin/m2/w12-a3-verifier-d15-20261105` đã fast-forward vào `m3/w12-all` (`3f77fcf6`). Không xoá file nào; chỉ sửa tại chỗ `policy.py`, `static_checks.py`, 2 file test, 1 spec (định dạng) | `git diff --numstat c88290a1 3f77fcf6` |
| Hash policy | Hash A0–A2 (cả bộ W9 lẫn `w10/`) giống hệt trước merge. A3 khi `arm` chưa bind = `sha256:f66a8f71…99a4` | `load_variant` + `policy_hash` ở hai commit |
| Mutant pool | Đã build thật 2 lần (06:20Z, 06:23Z), **cùng** `pool_hash` `sha256:8abbc172…6f6f`: builder lặp lại được trên dữ liệu thật. 150 slot = 25 task × (1 gold + 5 mutant); 138 CREATED, 12 ERROR, 0 NOT_APPLICABLE, `ready: false` | `results/m2/w1112/pool-20261105T062327Z/pool.json` (repo Windows; bản chép trong `~/vgar-a3`) |
| 12 slot ERROR | Đều thuộc 2 task `psf__requests-1724` và `pylint-dev__pylint-4970`, lý do `TASK_INPUT_OR_SOURCE_NOT_READY`. Hai task này **bị loại có chủ đích từ 28/10**, vì không viết được test tái hiện; repo không có file input của chúng | `configs/m3/w10_dev/tasks/EXCLUDED.md` |
| Campaign pool | **0 vector thật**, qua 3 lần thử | Bảng dưới |
| Record A3 | 0. Chưa config experiment nào có A3. `scripts/derive_experiment_config.py` (M1-W12, 6 test) đã hỗ trợ `A3:graph`. Bundle W12 mới export cho 5 task (X2b), chưa đủ 25 task | `~/w10/w12/bundles/repair/20261103T091200Z-8753efad12d5/` |
| D15 | Công cụ sẵn sàng. Export W10 trên WSL đúng cấu trúc (`experiment.json`, `attempts/`, `engine/`): `~/w10/results/m3/9f1b2346fa028094` (stage1) và `~/w10/results/m3/cfb605118a52b835` (stage2). Chạy được ngay, kết quả sẽ là `PARTIAL` cho tới khi có A3 | `docs/m2_d15_timeout_analysis.md` |
| Test/CI | Gate của M2: 654 test thu hẹp. Full suite trên `3f77fcf6` **chưa có kết quả hợp lệ**: lần chạy trong worktree Windows thiếu file gitignored (tokenizer); lần chạy so sánh bị dừng vì máy thiếu RAM. Workflow chỉ chạy khi có PR hoặc push `main` | `.github/workflows/tests.yml:47` |
| Báo cáo M2 | Có câu đã cũ: "chưa commit" (§1.1); "0 patch thật" (§3.3, §12); xếp 2 task bị loại thành "thiếu input trên đường dẫn Windows" | Báo cáo M2 |

Ba lần thử campaign pool ngày 05/11:

| Lần | Chạy từ | Kết quả | Nguyên nhân |
|---|---|---|---|
| `campaign-20261105T062327Z` | `/mnt/d` | 67 `CHECK_INTEGRITY_ERROR`, 1 `INTERRUPTED`, 70 `NOT_RUN`. Vẫn ghi **2,43 GB** | Docker CLI chưa có trong WSL: `docker could not be found in this WSL 2 distro` |
| `campaign-20261105T081117Z` | `/mnt/d` | 18 slot đều `OSError: [Errno 5] Input/output error` | Nhiều khả năng là **ổ D: đầy**: ít phút sau, một lần ghi lên D: báo `ENOSPC` và `df` báo 0 byte trống; lần chạy trước vừa ghi 2,43 GB. Khoảng 15:41, D: lại có 9 GB trống; chưa rõ thứ gì đã giải phóng chỗ |
| `campaign-20261105T082112Z.log` (`~/vgar-a3`) | ext4 | Dừng trước slot đầu: `ValueError: Pinned bundle profile hash mismatch` | Lỗi CRLF/LF, xem dưới |

**Hai điều kiện môi trường mới phát hiện:**

1. **Dung lượng đĩa.** Mỗi slot pool **và** mỗi repair run đều ghi `checks/baseline.json`, kể cả slot hỏng sớm. Kích
   thước đo được:

   | Repo | astropy | django | matplotlib | scikit-learn | xarray | pylint | pytest | seaborn | flask |
   |---|---|---|---|---|---|---|---|---|---|
   | MB | 114 | 103 | 78 | 61 | 29 | 23 | 18 | 16 | 4 |

   Sáu slot của cùng một task ghi sáu bản giống nhau. Ước tính (9 repo đã đo, các repo còn lại suy theo cỡ):
   - pool 138 slot: **khoảng 8–10 GB**;
   - batch chỉ A3 (20 run): khoảng 1 GB;
   - batch A0–A3 (80 run): khoảng 4 GB.

   Hiện còn trống: C: 13 GB (ext4 của WSL và Docker Desktop nằm trên C:), D: khoảng 9 GB.
2. **Checkout phải khớp byte với checkout đã ghim hash.** `configs/m3/w10_dev_stage{1,2}.json` ghim
   `configs/m1/w9_bundle_profile_repair.json` bằng `sha256:325dd4…`. Đó là hash của bản **CRLF**, có được trên Windows
   (`core.autocrlf=true`) và trong clone cũ `~/vgar`. Bản trong git là LF (`sha256:c33ba9…`), nên một `git clone`
   sạch trên Linux bị từ chối (`manifest.py:114-115`). Quét toàn bộ pin của `configs/**`: đây là pin nội dung **duy
   nhất** bị ảnh hưởng. Các pin `manifest` so với trường `manifest_hash` bên trong file, không băm nội dung file.
   `derive_experiment_config.py` chép pin này sang config W12, nên batch W12 và held-out cũng sẽ dính.

**Gate fairness so sánh cả repair policy.** `fairness_identity()` (`src/vgar/evaluation/repair/fairness.py:31-37`)
gồm `exp.policy.model_dump()`, tức gồm cả timeout, cùng với model, tokenizer, template prompt, `bundle_profile_sha` và
phần chung của các variant. `aggregate()` gọi gate trên **mọi** experiment được gộp (`aggregate.py:214`). Hệ quả: nếu
batch W12 dùng timeout khác W10, không gộp được A3 mới với A0–A2 của W10; phải chạy lại mọi arm dưới cùng config.

## 2. Mục tiêu, không làm, và các kiểu thất bại

### 2.1. Mục tiêu

- **G0. Môi trường chạy được:** đủ dung lượng đĩa cho campaign và batch; checkout có bytes khớp các pin.
- **G1. V1/V2 trên dev:** một campaign pool **hợp lệ**, chạy trên Docker đã admitted. Mọi slot CREATED được verify một
  lần; bảng V1 (FAR/FRR theo A0–A3) và V2 (theo loại mutant) có đủ mẫu số; chạy lại `report` ra bảng giống hệt.
- **G2. Timeout cho freeze (H8):** có đề xuất timeout của M2 dựa trên D15 với dữ liệu W10 thật, và nhóm chốt ĐX2
  **trước khi** chạy batch GPU W12.
- **G3. Record A3 trên dev (nghiệm thu M2-W12-1):** A3 chạy thật trong batch W12, trên cùng config với A2 mà nó được
  so. Ledger có đủ 25 task, kể cả task bị loại hay lỗi. M2 kiểm record theo checklist ở §5.4.
- **G4. Tích hợp:** full suite offline có kết quả trên commit sẽ freeze; CI xanh trên PR; code M2 được review theo
  CODEOWNERS.
- **G5. Ô freeze của M2 được điền:** hash A3, timeout, tham chiếu pool, campaign và V1/V2. Bàn giao cho M3-W12-2.
- **G6. Báo cáo M2 đúng sự thật:** sửa các câu đã cũ, thêm kết quả G1–G3 khi có.

### 2.2. Không làm

- Không chạy gì trên held-out (đó là W13).
- Không viết phép suy A2/A3 từ A1 (ĐX1). A3 chạy thật, đúng theo plan. ĐX1 cho held-out, nếu nhóm duyệt sau, là
  spec khác.
- Không đổi logic pool hay verifier, không đổi population, không thêm re-plan cho A3.
- Không đổi timeout trong config W10 đã chạy. Timeout mới, nếu có, chỉ áp cho config W12.
- Không tune retrieval.

### 2.3. Thất bại dù vẫn "chạy được"

- Bảng V1/V2 lấy từ campaign có lỗi hạ tầng hàng loạt, như ba lần thử ngày 05/11.
- `ERROR` hoặc `NOT_RUN` bị tính thành phát hiện lỗi (detection) hay bị giấu trong cờ "complete".
- A3 khác A2 ở bất cứ thứ gì ngoài `required_checks`: config, bundle, timeout hoặc commit code.
- Hai task bị loại được trình bày như dữ liệu thiếu; đổi task sau khi đã thấy kết quả.
- Gọi static hint là "coverage" (D18).
- Đổi giá trị pin cho khớp với checkout. Pin là thứ W10 đã chạy; phải sửa checkout cho khớp pin, không làm ngược lại.
- Chạy campaign khi ổ C: sắp đầy, làm hỏng Windows, WSL hoặc Docker.

## 3. Ràng buộc

- **Người dùng tự chạy mọi job GPU và Docker** rồi dán output. Không ai khác khởi chạy.
- **Người dùng tự commit.** Mỗi phần một PR; review theo CODEOWNERS (`src/vgar/repair/`, `configs/m2/`: M1 duyệt;
  `fairness.py`, `gpu.py`: M3 duyệt). Người dùng đang đóng vai M1 và M3, nên là người review code M2.
- **Một máy:** batch GPU, pool, dry-run và agent run không chạy chồng nhau (lịch W12, ngày 3).
- **Mọi I/O của campaign và batch nằm trên ext4 của WSL, không qua `/mnt/d`.**
- `results/` nằm trong gitignore (`.gitignore:22`). Kết quả không commit; đường dẫn ghi trong `docs/status/m3.md`.
- Test mới, nếu có, không cần GPU, Docker hay mạng; CI `-m "not hf and not docker"` phải giữ xanh.

## 4. Quyết định

### 4.1. Người dùng hoặc nhóm đã chốt

- W13 chạy held-out theo plan; freeze phải xong trước đó (người dùng, 05/11).
- A3 = A2 + `api`, `structural`; 25 task W10; mỗi attempt sinh một lượt, không re-plan (chốt khi M2 triển khai,
  `docs/m2_w12_1_a3.md` §1).
- Metric chính F3, F4, Recall@k, FAR/FRR; ba phép so sánh A1/A0, A2/A1, A3/A2 (03/11, spec M3 W12 §4.3).
- Pool chạy trên máy M3, theo phương án N.
- Batch W12 = A3 × 25 + các ô có hash đổi (H3b) + 2 ô đối chứng (E5 hướng (iii), chốt 02/11). Thành phần batch này
  chỉ đúng khi giữ timeout W10; đổi timeout thì phải chạy lại mọi arm (§4.3).

### 4.2. Lựa chọn của người viết (cần người dùng duyệt)

| Mã | Lựa chọn | Lý do |
|---|---|---|
| C1 | **Đổi thứ tự so với lịch W12:** chạy pool **trước** batch GPU. D15 trên dữ liệu W10 chạy ngay, song song | Pool đã sẵn sàng. Batch thì chưa: còn thiếu config có A3, bundle đủ 25 task và quyết định timeout. D15 chạy offline, nhẹ, không đụng Docker hay GPU |
| C2 | A3 chạy thật như một variant riêng (không dùng ĐX1) | Plan ghi "đủ `N × 4` record". Không cần thêm code |
| C3 | Chạy từ một clone trên ext4 (`~/vgar-a3`), checkout bằng `core.autocrlf=true` để bytes giống checkout Windows và `~/vgar`. Venv `~/vgar/.venv` | Tránh `/mnt/d`; bytes khớp các pin mà W10 đã chạy |
| C4 | Ba lần thử hỏng: đổi tên thư mục thêm hậu tố `-void-docker-missing`, `-void-disk-full`, `-void-crlf`. Trong thư mục hỏng chỉ xoá `vectors/*/checks/baseline.json` (2,4 GB, trùng nội dung, không phải bằng chứng lỗi); giữ `vector.json`, `docker/cli-*.json`, `campaign.json`, log. Không dùng trong bảng | Giữ bằng chứng mà vẫn trả lại dung lượng |
| C5 | Phân công: **người dùng** chạy mọi thứ. **M2** sinh V1/V2, viết đề xuất timeout, kiểm record A3, thêm cột verify cho P1, sửa báo cáo. Nếu M2 không kịp mốc H10/H8 thì người dùng làm và M2 review (ĐX4) | Đúng phân công trong plan |
| C6 | **Sửa CRLF triệt để:** thêm `configs/m1/w9_bundle_profile_repair.json -text` vào `.gitattributes` và commit lại file với **đúng bytes CRLF** đang ghim (`sha256:325dd4…`). Không đổi giá trị pin | Clone sạch trên mọi hệ điều hành đều khớp pin; W10 và W12 giữ nguyên identity. `.gitattributes` đã có tiền lệ cho file M2 cần giữ bytes. Cần làm trước khi gắn tag freeze (R5) |
| C7 | Ngưỡng đĩa: **C: còn trống ≥ 20 GB** trước W1; kiểm lại trước W3 | Pool khoảng 8–10 GB, cộng chỗ cho container, `/tmp` và Windows |

### 4.3. Chờ nhóm chốt: ĐX2 (timeout), và nó quyết định quy mô batch

| Phương án | Timeout sinh / toàn cục | Batch W12 | Ước tính GPU (W10: khoảng 7,3 phút/run) |
|---|---|---|---|
| Giữ W10 | 900 s / 1800 s | A3 × 20 task chạy được + ô H3b + 2 ô đối chứng. A0–A2 dùng lại W10 cho ô có hash không đổi. **Cần làm thêm danh sách H3b**, hiện chưa có trong repo: sau khi export bundle 25 task, so hash context và `test_links.json` với record W10 (E5 bước 2) | Khoảng 2,5 giờ + số ô H3b |
| Đổi (ĐX2) | 1500 s / 2700 s, hoặc số khác theo D15 | **A0–A3 × 20 = 80 run**, vì gate fairness không cho gộp với W10 | Khoảng 10–16 giờ (chạy qua đêm) |

Nếu tới mốc H8 nhóm vẫn chưa chốt: giữ 900/1800 và ghi confound timeout ở arm graph (D26) vào Threats. Đây là
fallback đã ghi trong spec M3 W12 §8.

## 5. Các phần việc

### 5.1. W0: điều kiện môi trường

**Người làm:** người dùng.

1. **Đĩa:** đưa ổ C: về ≥ 20 GB trống (C7). Áp dụng C4 cho ba thư mục hỏng: trả lại khoảng 2,4 GB trên D:. Bản pool
   trùng `pool-20261105T062012Z` (41 MB, cùng hash) có thể xoá. Dọn file cá nhân để lấy thêm chỗ là việc của người
   dùng.
2. **Checkout:** sửa `~/vgar-a3` thành checkout CRLF (§7.1), rồi kiểm hash file profile bằng `sha256:325dd4…`.
3. **Sửa CRLF triệt để (C6):** một PR nhỏ gồm `.gitattributes` và bytes của file profile. Có thể làm sau W1, nhưng
   phải xong trước khi gắn tag freeze.
4. **Docker:** `docker info --format '{{json .}}'` chạy được trong WSL.

**Xong khi:** C: còn ≥ 20 GB trống; trong `~/vgar-a3`, `sha256sum configs/m1/w9_bundle_profile_repair.json` ra
`325dd4d4…`; `load_experiment` của hai config stage chạy qua.

### 5.2. W1: campaign pool → V1/V2 (H10)

**Người làm:** người dùng chạy; M2 sinh bảng. **Đầu vào:** pool `pool-20261105T062327Z`, `POOL_HASH` ở §1, config
`configs/m3/w10_dev_stage{1,2}.json`, data root `~/w10`.

1. Làm xong W0.
2. Kiểm trước khi chạy: thư mục output **chưa tồn tại**; biến môi trường được `echo` ra đúng; còn đủ đĩa.
3. Chạy `evaluate_mutant_pool.py run` trong `tmux` (§7.2).
4. **Luật dừng sớm:** nếu 3 vector đầu đều là `CHECK_INTEGRITY_ERROR` với cùng một lý do hạ tầng thì dừng, sửa môi
   trường, rồi chạy lại vào thư mục output **mới**. Công cụ không resume; mỗi lần chạy phải ghi vào thư mục mới.
5. Sau khoảng 5 slot đầu: ước lại tổng thời gian và dung lượng (`du -sh $CAMPAIGN`), ghi vào `docs/status/m3.md`. Nếu
   ước tính dung lượng vượt chỗ trống thì dừng và báo lại.
6. Chạy xong: chạy `report` vào một thư mục bảng thứ hai, rồi so: bảng phải giống hệt.
7. Bàn giao H10: đường dẫn campaign, bảng, `campaign_hash` và log, ghi vào `docs/status/m3.md`.
8. **M2** viết V1/V2 kèm chú thích mẫu số: planned 150, generated 138, pool ERROR 12 (ghi tên 2 task và lý do từ
   `EXCLUDED.md`), evaluated, NOT_RUN/pending. `ERROR` tách khỏi `FAIL`. Không dùng chữ "coverage".

**Xong khi:** không còn slot CREATED nào ở `NOT_RUN`; mọi vector hợp lệ có binding với pool; `report` chạy lại ra bảng
giống hệt; V1/V2 có đủ mẫu số. Slot `ERROR` do task hay patch (không phải hạ tầng) vẫn hợp lệ và được báo cáo riêng.

### 5.3. W2: D15 → đề xuất timeout (H8) và ĐX2

**Người làm:** người dùng chạy công cụ; M2 phân tích và đề xuất; nhóm chốt.

1. Chạy `analyze_repair_timeouts.py` trên hai export W10 (§7.3). Trạng thái `PARTIAL` với exit 2 là **dự kiến**, vì
   chưa có A3. Công cụ chỉ dùng thư viện chuẩn, không cần Docker, GPU hay checkout CRLF.
2. M2 đọc report: phân phối `generation_ms` theo arm và theo `input_tokens`; số `GENERATION_TIMEOUT` và
   `RUN_TIMEOUT` mỗi arm (các giá trị bị cắt, tức censored, báo riêng). Sau đó viết đề xuất vào `docs/status/m2.md`:
   con số, lý do, và tác động lên GPU theo bảng §4.3.
3. Nhóm chốt ĐX2 trước khi khởi chạy W3. Nếu chưa chốt kịp thì dùng fallback ở §4.3.
4. Sau W3: chạy lại công cụ, thêm export A3 qua `--w12-experiment`. Kỳ vọng `READY_FOR_REVIEW`. Báo cáo D15 cuối chỉ
   **xác nhận hoặc ghi lệch**, không đổi timeout đã dùng. Lệch thì ghi amendment hoặc threat.

**Xong khi:** đề xuất có số liệu nằm trong `docs/status/m2.md`; ĐX2 được ghi trong `docs/m3_w11_decisions.md` (hoặc
file quyết định W12), kèm ngày và người chốt.

### 5.4. W3: record A3 trên dev (nghiệm thu M2-W12-1)

**Người làm:** người dùng sinh config và chạy batch; M2 kiểm record.

**Tiền điều kiện (không thuộc M2):**
- bundle đủ 25 task, export bằng ranking đã đóng băng (vai M1);
- ĐX2 đã chốt (W2);
- danh sách ô H3b (E5);
- W0 đạt.

1. Sinh config bằng `scripts/derive_experiment_config.py`, cùng template và cùng `--bundle-dir` với các ô A2 sẽ được
   so. **A3 nằm trong một config riêng chỉ có `--variants A3:graph`**, vì cohort W12 của công cụ D15 chỉ nhận experiment
   khai báo đúng một variant A3 (`scripts/analyze_repair_timeouts.py:518-520`). Các ô A0–A2 phải chạy lại (ô H3b, hoặc
   cả 60 ô nếu đổi timeout) nằm ở config thứ hai, cùng template, bundle và repair policy. D15 không phân tích các ô
   chạy lại này; chúng chỉ dùng cho bảng A0–A3.
2. **Kiểm fairness trước khi khởi chạy:** gọi `check_arm_fairness` trên đúng tập experiment sẽ được gộp trong aggregate.
   Runner chỉ kiểm từng config riêng (`run_repair_experiment.py:64`), không kiểm chéo giữa các config. Nếu gate báo lỗi
   giữa A2 của W10 và A3 của W12 thì chạy lại A2 trong config W12; **không** gán nhãn lại.
3. `preflight`, rồi `run`.
4. **M2 kiểm record A3 theo checklist:**
   - ledger có đủ 25 task: 20 chạy được, 2 `EXCLUDED`, 3 `OVER_CAP` (`astropy__astropy-13453`,
     `astropy__astropy-13977`, `django__django-11087`), mỗi task có lý do;
   - mỗi engine record có `checks/api.json`, `checks/structural.json` và hash compatibility;
   - `variant_policy_hash` là hash A3 khi đã bind `arm=graph`;
   - verdict khớp bảng trong `docs/m2_w12_1_a3.md` §4: FAIL → `REVISE` với `API_BREAK` hoặc `STRUCTURAL_VIOLATION`;
     ERROR/NOT_RUN → `REJECT` với `VERIFICATION_INCOMPLETE`;
   - với cùng một task, prompt hash của A3 trùng A2, như W10 đã quan sát;
   - timeout và trạng thái lỗi được ghi đầy đủ.
5. M2 thêm cột verify cho bảng P1 từ repair record, không lấy từ số đếm của pool.
6. Export experiment A3 cho W2 bước 4.

**Xong khi:** checklist bước 4 đạt; aggregate gộp được A2 và A3 mà gate fairness không báo lỗi.

### 5.5. W4: tích hợp (full suite, review, CI)

1. Chạy full suite offline trong `~/vgar-a3` (có `artifacts/m1`): `-m "not hf and not docker"`. Ghi lại số test
   pass/fail. Nếu có fail thì chạy cùng suite trên `c88290a1` trong cùng môi trường để so. Fail mới do code M2 thì M2
   sửa trước freeze. Chạy sau pool để không tranh CPU và đĩa với Docker.
2. Review code M2 (người dùng, theo CODEOWNERS). Các ghi chú đã có từ lần đọc ngày 05/11; M2 quyết định sửa ngay hay
   mở issue:
   - `verifier_eval.py` import hàm private `_assess_w9_static` (và `expand_required`) từ `verification.py`, nên nếu
     M3 sau này sửa `verification.py` thì có thể làm hỏng M2;
   - `evaluate_pool` báo `must not overlap frozen pool` cả khi lỗi thật là thư mục output **đã tồn tại**
     (`verifier_eval.py:328-329`), khiến người chạy hiểu sai hai lần trong ngày 05/11;
   - mỗi slot ghi lại `checks/baseline.json` dù 6 slot của một task dùng cùng source: ghi một lần cho mỗi task sẽ giảm
     dung lượng pool khoảng 6 lần. Pool held-out ở W14 (M2-W14-2) sẽ gặp lại vấn đề này. Đây là đề xuất cho M2, không
     chặn W1.
3. Mở PR để CI chạy. **CI xanh là điều kiện để gắn tag freeze** lên commit đó.

**Xong khi:** có kết quả full suite ghi trong `docs/status/m3.md`; review đã duyệt; CI xanh trên commit dự kiến freeze.

### 5.6. W5: điền các ô freeze của M2 (bàn giao M3-W12-2)

- §3: hash A3 lấy **từ run record** (đã bind `arm=graph`). Không dùng giá trị `f66a8f71…`, vì đó là hash khi
  `arm=null`.
- §4: timeout theo ĐX2.
- Tham chiếu pool, campaign và bảng V1/V2. Nếu V1/V2 chưa xong khi ký thì ghi "đang chờ"; điều này được phép theo
  fallback H10, vì định nghĩa metric đã chốt.
- Ghi chú tái lập: tag freeze phải nằm trên commit đã có C6. Nếu không, phải ghi vào protocol rằng checkout cần
  `core.autocrlf=true`.
- Cùng code: pool và batch phải chạy trên code verifier giống commit freeze. Nếu từ lúc chạy tới commit freeze có
  thay đổi trong `src/vgar/repair/**` hoặc `src/vgar/evaluation/repair/{verifier_eval,mutant_pool}.py` thì chạy lại
  phần bị ảnh hưởng, hoặc ghi amendment giải thích vì sao verdict không đổi. Thay đổi chỉ ở `.gitattributes`, bytes
  của file profile (C6) hay câu báo lỗi thì không cần chạy lại.

### 5.7. W6: sửa báo cáo M2 (M2)

- §1.1: code W12/D15 đã commit (`3f77fcf6`) và đã merge vào `m3/w12-all` ngày 05/11.
- §3.3 và §12: pool đã build thật ngày 05/11 (hash, 138/150) và trạng thái campaign theo W1.
- Hai task: ghi "loại trước khi chạy (EXCLUDED.md, 28/10)", không ghi "thiếu input trên Windows".
- Thêm mục "Kết quả dev W12" trỏ tới V1/V2, record A3 và D15 khi có. Đồng bộ bản trong repo với bản có §14.

**Xong khi:** người dùng review bản sửa. Việc này được làm sau freeze nhưng phải xong trước khi viết Results (W15).

## 6. Thứ tự trên máy M3

1. W2 bước 1: D15 trên W10. Chạy được bất cứ lúc nào, vài phút, không dùng Docker hay GPU.
2. W0: dọn đĩa, sửa checkout, kiểm Docker.
3. W1: campaign pool trên Docker, ước 3–5 giờ; ước lại thời gian và dung lượng sau 5 slot đầu.
4. W4 bước 1: full suite, sau pool.
5. Nhóm chốt ĐX2, dựa trên kết quả W2.
6. W3: batch GPU (qua đêm nếu đổi timeout).
7. Dry-run ×2 (M1-W12-2, H7). Runbook yêu cầu pool đã xong và đã có `A3.json`.
8. Agent run X2b (H11).
9. W2 bước 4 (D15 cuối), W0 bước 3 (C6) nếu chưa làm, W5 (điền ô freeze), CI xanh, rồi ký.

Nếu trễ, áp thứ tự cắt của plan: A3 lùi thành "chỉ là phép đo" (giữ API check làm phép đo, bỏ vai trò quyết định);
**không** cắt pool/V1 và dry-run.

## 7. Runbook (WSL)

### 7.1. Clone trên ext4, bytes giống checkout Windows

Sửa clone đang có (`results/` và `artifacts/` nằm trong gitignore nên được giữ nguyên):

```bash
cd ~/vgar-a3
git config core.autocrlf true
printf '*.sh text eol=lf\n' > .git/info/attributes    # script bash phải giữ LF, nếu không bash chạy hỏng
git rm -r -q --cached . && git reset -q --hard HEAD
sha256sum configs/m1/w9_bundle_profile_repair.json   # phải là 325dd4d42d77fa21…
git status --short | head                             # phải trống
git log --oneline -1                                  # commit đã merge (3f77fcf6) hoặc commit dự kiến freeze
ls artifacts/m1 results/m2/w1112/pool-20261105T062327Z/pool.json
```

Clone mới thì dùng `git clone -c core.autocrlf=true /mnt/d/kltn/vgar_mcp_mvp_demo ~/vgar-a3`, thêm
`.git/info/attributes` như trên rồi `git rm -r -q --cached . && git reset -q --hard HEAD`, sau đó chép `artifacts/m1`
và thư mục pool như cũ. Biến dùng chung và phép kiểm config:

```bash
export PY=~/vgar/.venv/bin/python DATA_ROOT=~/w10
export POOL=results/m2/w1112/pool-20261105T062327Z
export POOL_HASH=sha256:8abbc1727432495156d41994c9167c9c681c6dd473747d20dc8f37db64946f6f
$PY -c "import sys; sys.path.insert(0, 'src'); from pathlib import Path
from vgar.evaluation.repair.manifest import load_experiment
for p in ('configs/m3/w10_dev_stage1.json', 'configs/m3/w10_dev_stage2.json'):
    load_experiment(Path(p), Path('$DATA_ROOT'))
print('LOAD_OK')"
```

Dọn ba thư mục hỏng theo C4, chỉ sau khi người dùng đồng ý (chạy trên WSL):

```bash
cd /mnt/d/kltn/vgar_mcp_mvp_demo/results/m2/w1112
find campaign-20261105T062327Z campaign-20261105T081117Z -path '*/checks/baseline.json' -delete
mv campaign-20261105T062327Z campaign-20261105T062327Z-void-docker-missing
mv campaign-20261105T081117Z campaign-20261105T081117Z-void-disk-full
mv ~/vgar-a3/results/m2/w1112/campaign-20261105T082112Z.log ~/vgar-a3/results/m2/w1112/campaign-20261105T082112Z-void-crlf.log
df -h /mnt/c /mnt/d
```

### 7.2. Pool

```bash
df -h / /mnt/c                                         # C: phải còn ≥ 20 GB
export RUN=$(date -u +%Y%m%dT%H%M%SZ) CAMPAIGN=results/m2/w1112/campaign-$RUN TABLES=results/m2/w1112/tables-$RUN
echo "RUN=$RUN"; test -e "$CAMPAIGN" && echo DA_TON_TAI || echo MOI_OK
docker info --format '{{json .}}' > /dev/null && echo DOCKER_OK
$PY -B scripts/evaluate_mutant_pool.py run --pool "$POOL" --expected-pool-hash "$POOL_HASH" --data-root "$DATA_ROOT" \
  --config configs/m3/w10_dev_stage1.json --config configs/m3/w10_dev_stage2.json \
  --output-root "$CAMPAIGN" --table-root "$TABLES" --temp-root /tmp/vgar-pool-$RUN 2>&1 | tee "$CAMPAIGN.log"
# Theo dõi (pane khác, export lại CAMPAIGN):
ls $CAMPAIGN/vectors | wc -l; grep -l CHECK_INTEGRITY_ERROR $CAMPAIGN/vectors/*/vector.json | wc -l; du -sh $CAMPAIGN
# Đối chiếu bảng:
$PY -B scripts/evaluate_mutant_pool.py report --pool "$POOL" --expected-pool-hash "$POOL_HASH" \
  --output-root "$CAMPAIGN" --table-root "$TABLES-replay" && diff -r "$TABLES" "$TABLES-replay"
```

### 7.3. D15

```bash
$PY -B scripts/analyze_repair_timeouts.py \
  --w10-experiment ~/w10/results/m3/9f1b2346fa028094 \
  --w10-experiment ~/w10/results/m3/cfb605118a52b835 \
  --output-root ~/vgar-a3/results/m2/w1112/d15-w10-$(date -u +%Y%m%dT%H%M%SZ); echo "exit=$?"
```

Sau W3, thêm `--w12-experiment <thư mục experiment A3>` và chạy lại vào thư mục output mới.

## 8. Xử lý sự cố

| Dấu hiệu | Nghĩa | Làm gì |
|---|---|---|
| `Fresh campaign output must not overlap frozen pool` | Thư mục output **đã tồn tại** (hoặc chồng lên pool) | Đặt `RUN` mới. Không xoá campaign cũ |
| `CHECK_INTEGRITY_ERROR`, `Docker operation incomplete: ['info', '--format']`, `cli-000.json` có `docker could not be found in this WSL 2 distro` | WSL integration của Docker Desktop đang tắt | Bật cho distro Ubuntu, rồi chạy lại vào output mới |
| `OSError: [Errno 5] Input/output error` hoặc `ENOSPC` | Ổ đích đầy (nhất là qua `/mnt/d`) | `df -h`; dọn chỗ theo W0; chạy từ ext4 |
| `ValueError: Pinned bundle profile hash mismatch` | Checkout có bytes LF, pin là CRLF | §7.1. Không sửa pin |
| `RUN_TIMEOUT` ở một vài slot | Verify vượt timeout toàn cục | Giữ `ERROR`, báo riêng; không chạy lại riêng slot đó |
| Bị ngắt giữa chừng (`INTERRUPTED`) | Campaign dang dở | Công cụ không resume: chạy lại toàn bộ vào output mới; giữ bản dang dở làm bằng chứng |
| `duplicate session: pool` khi mở tmux | Session cũ còn tồn tại; lệnh đang chạy **ngoài** tmux | `tmux attach -t pool` để xem, hoặc `tmux kill-session -t pool` rồi mở lại |

## 9. Định nghĩa xong (tổng)

Phần M2 tuần 12 đủ để ký freeze khi:
- W0 đạt, gồm cả C6;
- W1 xong, hoặc V1/V2 ghi "đang chờ" theo fallback H10;
- W2 có đề xuất và ĐX2 đã chốt;
- W3 đạt checklist;
- W4 có CI xanh;
- W5 đã điền.

W6 được làm sau freeze nhưng phải xong trước W15.

## 10. Rủi ro

- **Đĩa:** pool khoảng 8–10 GB cộng batch 1–4 GB, trong khi C: chỉ còn 13 GB. Đây là lý do có ngưỡng C7 và đề xuất
  ghi baseline một lần cho mỗi task (W4).
- **Thời gian máy:** pool 3–5 giờ, batch (2,5 hoặc 10–16 giờ theo §4.3), dry-run ×2 và X2b đều trên một máy.
- **Tái lập (R5):** khi chưa có C6, clone sạch trên Linux không chạy được config W10/W12. Checkout CRLF (§7.1) cũng
  làm script `.sh` hỏng nếu thiếu dòng `*.sh text eol=lf`. Trong `~/vgar`, `build_static_tools.sh` đang là LF còn
  `run_official_harness.sh` là CRLF. Nếu nhóm muốn, C6 có thể thêm luôn `*.sh text eol=lf` vào `.gitattributes`.
- **Population của các bảng khác nhau:** FAR/FRR tính trên 23 task, vì pool không có prompt nên chạy được cả 3 task
  OVER_CAP; F3/F4 của A3 tính trên 20 task. Phải ghi rõ ở cả hai bảng.
- **Phiên bản tool:** mypy/Ruff trên Windows của M2 khác pin. Pool và batch chạy trong container có tool đóng gói theo
  pin (D12), nên số liệu dev không phụ thuộc máy M2. Gate local của M2 thì vẫn không chứng nhận được CI.
- **Gate fairness báo lỗi** khi gộp W10 với W12, đặc biệt khi đổi timeout (§1, §4.3).
- **Thời hạn pool:** pool verify bằng repair policy của config W10. Nếu ĐX2 tăng timeout toàn cục, slot nào từng chạm
  1800 s sẽ khác giữa pool và freeze. Ghi vào V1/V2 nếu có.

## 11. Để người làm tự quyết

- Tên thư mục output và cách chép kết quả về `/mnt/d`.
- Dùng `tmux` hay công cụ khác.
- Có sửa ngay các ghi chú review ở W4 bước 2 không (M2 quyết định).
- Định dạng ghi chú đề xuất timeout trong `docs/status/m2.md`.
- Dọn file nào để có chỗ trống (người dùng).

## 12. Cần người dùng hoặc nhóm chốt

1. Duyệt các lựa chọn C1–C7 (§4.2), đặc biệt C4 (xoá `baseline.json` trong ba thư mục hỏng) và C6 (sửa CRLF).
2. **Đĩa:** dọn được C: lên ≥ 20 GB trống không? Nếu không, M2 phải sửa để ghi `checks/baseline.json` một lần cho mỗi
   task (kèm test) **trước** W1. Đây là thay đổi code verifier, nên phải vào commit freeze (§5.6).
3. ĐX2: timeout. Quyết định này đổi quy mô batch GPU (§4.3).
4. Nếu M2 không kịp H8/H10: người dùng nhận phần nào (ĐX4).
