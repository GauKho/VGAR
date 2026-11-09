# A3 ×25 — chặng 2 preparation, 06/11/2026

**PARTIAL / WAITING_RESOURCE. Chưa hoàn thành chặng2; không chuyển sang smoke chặng3.**

Plan: [A3 25 dev local campaign](../superpowers/plans/2026-11-06-a3-25-dev-local-campaign.md). Người dùng xác nhận chặng2 sau inventory. Giữ nhánh `m2/w12-a3-verifier-d15-20261105`, HEAD `3f77fcf6` và toàn bộ dirty work T2/T4/T5/T6/T7.

## Đã thực hiện

- Bật distro **VGAR-Harness-W9** và khởi động Docker Desktop đúng1 lần, không reset/reinstall/settings/prune. Daemon Linux x86_64 hoạt động, Docker28.5.1; ID `7b8241d1-62a7-4e81-974d-dc5b7fa9250c`.
- Inventory Docker: có5 images W9 cũ, giữ nguyên; **0/25 image W10 đúng digest**. Có0 container lúc kiểm; không chạy container trong chặng này.
- Xác minh registry index và platform linux/amd64 manifests của đúng25 digests:25/25 hash khớp,79 unique layers, **15.197.303.046 bytes nén (~14,15GiB)**. Đây không phải dung lượng giải nén hoặc tổng disk cần dùng.
- Metadata lượt đầu là OCI indexes nên có layers=[]; số0 trong `registry_sizes.json` **không phải image size**. Đã lần theo child manifests bằng digest, kết quả có thẩm quyền ở `platform_sizes.json`. Giữ cả logs để audit.
- Fetch thành công **25/25 source Git checkout** vào `/home/vgar/w10-a3-local/repositories/<task_id>`, đúng25 base commits, source clean, tree hash và actual blob hashes khớp, tổng50.518 blobs,0 mismatch. Không chạy code/test của repo đích, không apply gold patch.
- Tạo working copy riêng `/home/vgar/vgar-a3-local-20261106`:926 file từ code Windows hiện tại, gồm tracked+dirty/untracked implementation và tokenizer assets; SHA-256 copy khớp, không hardlink. Repo Windows không bị đổi bởi clone/copy/fetch.
- Venv SDK cũ `/home/vgar/w9/venvs/harness/bin/python` có Docker7.1.0/ghapi1.1.1; là candidate cần kiểm thêm, chưa tự qualification. Venv controller thiếu tree-sitter/tokenizers/PyYAML/torch/transformers; chưa cài dependencies mới.
- WSL có `/dev/dxg` và socket Docker; đây không phải GPU model inference/qualification. Filesystem Linux báo volume ảo lớn, nhưng capacity gate dùng **physical D:** nơi chứa VHDX.

## Blocker tại bước pull

Gate trước image đầu tiên lúc **19:08:29 giờ Việt Nam**:

- RAM host khả dụng **4.241.809.408 bytes≈3,95GiB**, thấp hơn4GiB yêu cầu (4.294.967.296 bytes).
- C trống14.105.104.384 bytes; D trống65.089.515.520 bytes≈60,62GiB. Lần dừng này do **RAM**, không phải thiếu disk đã chứng minh.
- Script trả WAITING_RESOURCE trước khi gọi docker pull: **0 image tải**,0 pull logs; không cài venv, qualification hoặc export sau khi gate thất bại.
- Không tự giảm ngưỡng, đổi RAM/swap WSL, dọn cache/standby memory, tắt ứng dụng hoặc xóa images. Đã hỏi người dùng đóng bớt ứng dụng thêm khoảng1–2GiB và báo tiếp tục.

Model/tokenizer/Parquet cache D: đã xác minh ở chặng1 vẫn được tận dụng theo plan; không tải lại. Chưa nạp model hoặc sửa đường dẫn trong config tracked.

## Chưa làm

1. Pull các pinned image digests còn thiếu và kiểm dung lượng sau từng image; không coi15,20GB nén là đủ disk sau unpack.
2. Tạo venv/controller Linux đủ dependencies và chọn model interpreter; không dùng Python Windows cho Linux worker.
3. Qualification local bằng runtime riêng relocated SDK path, profile/attestation mới theo daemon hiện tại.
4. Export graph + graph/BM25 bundle B1500, current resolver/ranking, `--limit25`; consumer/source finalize checks.
5. Local repair config và stage1/2 A3+A2 comparison-only configs được validate; hiện **0 validated configs**, không tạo stub để claim ready.

Full batch vẫn sauT1; T3/raw10 gold còn dependency như plan. Không triển khai T1/T3/T10 hoặc chuyển task khác.

## Evidence và khôi phục

TEMP: `C:\Users\pc\AppData\Local\Temp\vg-a3-prepare-82527b76`.

Output: `results/m2/w1112/a3-25/20261106T115908Z-prepare/` (bản archive và closing manifest là bằng chứng lưu dài hạn).

- `source_preparation.json`, `source-*.json`:25 rows, argv/log fetch600s limit, head/tree/blob/clean proofs.
- `code_copy.json`:926 file hashes và paths; working copy owner marker ghi run_id.
- `docker-info.json`, `docker-images.json`, `docker-df.json`, `image_inventory.json`: daemon/local images trước pull.
- `registry-*.json`, `platform-*.json`, `platform_images.json`, `platform_sizes.json`: frozen digest metadata và dedup compressed-byte sum.
- `linux_probe.json`: Python/package metadata, RAM/swap/physical disk và socket/CUDA-device presence.
- `image_preparation.json`: WAITING_RESOURCE ở task đầu, chưa pull.
- `preparation_summary.json`, `ledger.json`, `before.json`, `verification_before_docs.json`: điểm dừng và preservation. Năm accounting assertions không phải pytest/model/Docker test PASS.
- Git diff không được reset; tài liệu PROGRESS/status được bổ sung sau inventory, giữ nguyên lịch sử.

**Không chạy lại** `prepare_sources.py` hoặc `copy_code.py`: chúng đã xong và cố ý refuse overwrite. Tiếp tục bằng re-check RAM/disk/daemon/owned source proof, giữ raw WAITING_RESOURCE lượt1 riêng rồi mới chạy phần image preparation còn thiếu nếu người dùng đã báo tài nguyên sẵn sàng. Không chọn lại task hoặc budget. Nếu Codex ngắt, đọc summary/checkpoint và kiểm process trước mọi relaunch.

Docker Desktop/distro đã được bật theo phạm vi chặng2; không tự shutdown/restart để giải phóng RAM. Không có owned background preparation job sau điểm dừng này. Không commit/push, model/campaign, smoke hoặc target tests.

## Resume 02 — sau người dùng báo tiếp tục, 06/11/2026

- RAM đầu lượt đạt khoảng7,02GiB; không còn job preparation cũ. Không chạy lại fetch25 source/copy926 files.
- Đã pull thành công **2/25 images**: astropy-13033 và django-10914, đúng digests đã pin. 5 images W9 cũ giữ nguyên.
- Trước matplotlib-13989, gate RAM lại dừng: **1.059.123.200 bytes≈0,99GiB**; D còn59.244.650.496 bytes≈55,18GiB. Không bắt đầu pull image thứ3.
- Controller mới `/home/vgar/w10-a3-local/venvs/controller/bin/python` đã cài `scripts/requirements_m1.txt` cùng PyYAML6.0.3/Jinja2 3.1.6; `pip check` PASS và imports graph/manifest/tokenizer PASS. Không sửa venv W9, chưa cài model stack/static tool bundle, chưa chạy model hoặc pytest.
- Probe19:19:02: `vmmemWSL` working set8.376.565.760 bytes; Linux Cached6.637.876KiB≈6,33GiB, MemAvailable7.057.820KiB≈6,73GiB. Đây là bằng chứng page cache chiếm phần lớn RAM VM, không suy là model leak. Windows available thấp dù Linux reclaimable cao; không tự thay gate host4GiB bằng Linux MemAvailable.
- Đã hỏi người dùng về **reclaim page cache RAM tối đa5 lượt**, chỉ khi jobs preparation/container đã dừng: `sync`, rồi ghi1 vào `/proc/sys/vm/drop_caches`, đo lại; không xóa dữ liệu/images/model, không đổi `.wslconfig` hoặc services/settings. **Chưa có xác nhận ở thời điểm ghi checkpoint, chưa chạy reclaim.** Helper có guard yêu cầu authorization file, không coi việc tạo helper là quyền thực thi.
- Lưu lượt tiếp tục riêng ở TEMP `.../vg-a3-prepare-82527b76/resume-02` và artifact `.../20261106T115908Z-prepare/resume-02/`, giữ output311 files đã seal của lượt1. Source/model/graph profile/campaign khác chưa thay đổi; 0 qualification/bundle/config validate.
- Tiếp tục: sau khi có quyết định của người dùng, re-check gate; nếu được phép mới reclaim trong quota và resume images với logs mới, giữ2 images đã tải. Không chạy lại venv-create hoặc source/copy scripts. Không auto-prune/cache clear/shutdown WSL để lấy RAM.

## Resume 03 — reclaim được duyệt, đang chuẩn bị images

Người dùng đã xác nhận rõ **tối đa5 lượt reclaim page cache RAM trong chặng2**. Đây thay thế trạng thái chưa được duyệt của mục Resume02, không mở quyền prune/xóa dữ liệu/images hoặc sửa settings/shutdown WSL.

- Counter có thẩm quyền: `TEMP/vg-a3-prepare-82527b76/resume-02/page_cache_reclaims.json`, tổng cộng không quá5, gồm cả lượt1 đã dùng trước khi resume image preparation.
- Helper ghi `sync` rồi `drop_caches=1`, chỉ khi không có container/job preparation đang hoạt động; đo Linux/host trước–sau. Host page reporting cần thêm thời gian sau khi Linux cache đã drop; không coi số5s đầu là kết quả đã ổn định.
- Lượt1 đã đưa host từ khoảng1GiB về6,80GiB sau khi ổn định; không dữ liệu/images/model nào bị xóa. Giữ gate host4GiB, C10GiB, D30GiB.
- Lượt images mới dùng `resume-03/prepare_images_bounded.py`, tự skip images đã có, ghi log riêng, chỉ reclaim khi gate RAM thiếu và còn quota. Dừng khi quota hết hoặc disk không đạt; không đổi population/order/digests.
- Khi ghi mục này: **6/25 images ready,3/5 reclaim đã dùng**, image tiếp theo đang xử lý. Đọc `resume-03/image_preparation.json` và quota file để có số mới nhất, không dùng con số snapshot này như kết quả cuối.
- Process tool session hiện tại13896 (Windows controller; PID thay đổi theo phiên). Nếu Codex bị ngắt, kiểm process `prepare_images_bounded.py` và child docker pull trước mọi relaunch; không chạy thêm một controller song song.
- Runtime/repair path copies đã tạo trong `/home/vgar/w10-a3-local/inputs/`, chỉ relocate paths, policy/model identity giữ nguyên. Đây chưa là validated experiment configs. Static/model-stack helper mới chỉ được chuẩn bị, chưa chạy.
- TEMP lượt này `C:/Users/pc/AppData/Local/Temp/vg-a3-prepare-82527b76/resume-03`; artifact cuối sẽ bổ sung dưới `.../20261106T115908Z-prepare/resume-03/` bằng output mới, không ghi đè lượt1/2.

### Kết thúc lượt03 — WAITING_RESOURCE_RECLAIM_QUOTA_EXHAUSTED

**Chặng2 vẫn PARTIAL, không DONE, không chuyển sang smoke3.** Controller đã thoát, không còn image pull/job preparation do phiên này chạy nền.

- Inventory Docker thực tế sau khi controller dừng xác nhận **12/25 pinned images ready**,13 còn thiếu; đủ5 images W9 ban đầu vẫn tồn tại,0 container đang chạy.
- Có sẵn toàn bộ11 images của stage1 và image đầu stage2 `sympy__sympy-11618`. Dừng trước `astropy__astropy-13453`; không loại task này khỏi population vì thiếu tài nguyên.
- Đã dùng **5/5 lượt reclaim** theo đúng quyền được người dùng xác nhận. Tất cả action exit0, counter1…5 liên tục; không thực hiện lượt6 hoặc xóa dữ liệu/images/model. Counter và authorization được chụp vào artifact.
- Gate dừng lúc19:41:21: RAM **4.166.696.960 bytes≈3,88GiB<4GiB**, D35.353.612.288 bytes≈32,93GiB. Probe sau khi job thoát lúc19:42 còn RAM≈3,80GiB, D≈32,64GiB. Lượt dừng này do RAM và quota hết; disk còn vượt gate30GiB nhưng khoảng trống cho phần thiếu/unpack chưa được bảo đảm.
- Hai bản path config đã tạo: `/home/vgar/w10-a3-local/inputs/task_env_runtime.json` relocate SDK sang `/home/vgar/w9/venvs/harness/bin/python`; `repair_local.json` relocate model snapshot sang cache D:, interpreter sang controller riêng và tokenizer manifest sang Linux code copy. Policy/model identity giữ nguyên, **chưa là experiment configs được validate**.
- Model stack và static tool bundle chưa cài/build, qualification profiles0, bundle pairs0, validated experiment configs0. Các helper tương ứng mới được chuẩn bị, **không thực thi**; không tính là đầu ra hoàn thành.
- Sources25/25 và Linux code copy926 files giữ nguyên, không fetch/copy lại. Controller nhẹ vẫn có pip check/imports PASS từ lượt02. Không target tests, model calls, campaign, T1/T3/T10 hoặc commit/push.

Artifact lượt03: `results/m2/w1112/a3-25/20261106T115908Z-prepare/resume-03/`, gồm `preparation_summary.json`, `final_image_inventory.json`, image inspect/pull logs, local path input receipt, authorization/quota history, preservation/closing checks và hashes. Giữ nguyên311 entries lượt1 và27 entries lượt02 đã seal.

**Khôi phục:** không chạy lại `prepare_sources.py`, `copy_code.py`, `prepare_venv.py` hoặc `prepare_local_inputs.py` vì chúng đã xong. Kiểm process và resource gate trước khi resume. Không gọi `reclaim_page_cache.py` nữa với quyền hiện tại: quota đã hết. Nếu host tự có≥4GiB RAM thì có thể tiếp tục dưới quyền chuẩn bị đã có, nhưng vẫn phải kiểm disk trước từng image; mọi quyền reclaim bổ sung hoặc thay đổi gate/settings cần người dùng quyết định riêng. Giữ images đã tải và logs mới, không ghi đè các lượt đã seal.

## Resume 04 — người dùng yêu cầu tiếp tục tải đủ25 images

- Đầu lượt host đã tự hồi RAM≈6,07GiB, D≈41,70GiB, WSL working set≈1,51GiB; không có preparation process cũ. Không suy nguyên nhân dung lượng tăng hoặc thao tác của người dùng khi chưa có bằng chứng; kiểm lại images thực trước pull.
- Script mới `TEMP/vg-a3-prepare-82527b76/resume-04/complete_images.py` skip images đã có, giữ pinned25 IDs/digests. **Không gọi reclaim helper**, assert quota history vẫn đúng5 và bytes không đổi.
- Giữ gate RAM4GiB/C10GiB/D30GiB trước pull. Nếu RAM thấp có thể chờ hệ thống tự hồi tối đa300s/lần,600s tổng, chỉ đọc host memory; không drop cache, shutdown, thay settings hoặc hạ ngưỡng. Mỗi sleep5s, logs natural_resource_waits.json.
- Snapshot khi ghi checkpoint:14/25 ready, Matplotlib-20488 đang xử lý; quota vẫn5/5, chưa natural wait. Số hiện hành lấy từ image_preparation.json, không dùng snapshot làm kết quả cuối.
- Tool session đang theo dõi94562; khi khôi phục phải kiểm process `complete_images.py`/docker pull trước relaunch. Không chạy controller thứ2, không tạo lại source/venv/code copy đã xong.
- Artifact lượt này sẽ nằm riêng dưới `.../20261106T115908Z-prepare/resume-04/`. Lượt1/2/3 giữ nguyên, không ghi đè. Chưa nghiệm thu đủimages hoặc chặng2 ở thời điểm này.

### Kết thúc lượt04 — 15/25 images, chờ quyền reclaim bổ sung

- Đã thêm3 images đúng digest: astropy-13453, django-10973, matplotlib-20488. Inventory trực tiếp xác nhận **15/25 ready,10 còn thiếu**,5 images W9 cũ giữ nguyên và0 container.
- Matplotlib-20488 hoàn tất sau188,031s, D còn39.105.531.904 bytes≈36,42GiB, RAM1.433.358.336 bytes≈1,33GiB ngay sau pull.
- Trước requests-1766, đã chờ hệ thống tự hồi **300,359s** bằng host-memory sampling mỗi5s, không gọi WSL hoặc reclaim trong lúc chờ. RAM cuối1.681.690.624 bytes≈1,57GiB vẫn dưới4GiB; controller thoát với `WAITING_RESOURCE_AFTER_NATURAL_WAIT`.
- Giữ nguyên quota5/5; **0 reclaim bổ sung**, không giảm gate/đổi settings, không xóa file/image hoặc đổi population. Không model/test/qualification/bundle/config validate.
- Đã hỏi user duyệt thêm tối đa5 reclaim RAM, **tổng tối đa10 trong chặng2**. Chưa có xác nhận tại thời điểm checkpoint; helper đề xuất có guard authorization file và chưa chạy. Không xem yêu cầu tải đủ25 là tự động nới quota5.
- Output mới `results/m2/w1112/a3-25/20261106T115908Z-prepare/resume-04/`; TEMP cùng suffix. Process controller đã thoát, không còn owned preparation job. Resume sau quyền mới phải skip15 images đã có, không chạy lại source/code/venv hoặc ghi đè các lượt đã seal.

## Resume 05 — người dùng duyệt thêm5 reclaim, tổng tối đa10

- Quyền mới được người dùng xác nhận trực tiếp; tạo `resume-04/additional_reclaim_authorization.json`, tối đa5 bổ sung, tổng10 trong chặng2. Không mở quyền xóa data/images/model, thay settings hoặc shutdown.
- Counter gốc5 lượt ở resume02 giữ nguyên bytes. Counter bổ sung ở `resume-04/additional_page_cache_reclaims.json`, tổng dùng=5+độ dài counter bổ sung, các lượt bổ sung số6…10. Helper reserve counter trước action để không vượt quota nếu bị ngắt.
- Lượt6 đã COMPLETE, host RAM sau≈6,91GiB; chỉ `sync`+drop_caches=1 khi jobs/container idle. Không chạy lại nguồn/code/venv.
- Tiến trình mới `resume-05/finish_pinned_images.py` skip15 images đã có, gates cũ RAM4GiB/C10GiB/D30GiB. Snapshot17/25 ready, quota6/10; xem JSON hiện hành để lấy số mới nhất.
- Tool session theo dõi47109; kiểm process/child docker pull trước relaunch. Giữ một worker, không controller thứ2. Chưa claim25 images hoặc chặng2 DONE.
- TEMP `C:/Users/pc/AppData/Local/Temp/vg-a3-prepare-82527b76/resume-05`, artifact cuối sẽ nằm dưới prepare/resume-05 riêng; các lượt1…4 đã seal giữ nguyên.

### Lượt05: gate đĩa và phần tải5 images cuối

- Controller đầu đã dừng tại20/25, quota7/10, vì D30.850.760.704 bytes≈28,73GiB dưới gate30GiB của script, trước Sphinx-11510. Đĩa chưa đầy; không coi reclaim RAM là giải pháp dung lượng đĩa.
- Metadata cho5 còn lại (Sphinx-11510, Sympy-12481, Astropy-13977, Django-11087, Matplotlib-20676) có9 unique layers chưa được20 pinned images tham chiếu, tổng nén2.074.373.099 bytes; unpack chưa biết, old W9 có thể chia sẻ thêm.
- Đã trình bày phương án D≥20GiB **chỉ tải5 images còn lại**, RAM≥4GiB/C≥10GiB và tổng reclaim≤10; gate smoke/campaign không đổi. User đáp “tiếp tục tải cho đến khi hoàn thành25/25” ngay sau đề xuất cụ thể; thực hiện theo xác nhận ngữ cảnh này, không mở quyền xóa dữ liệu hoặc đổi settings.
- Authorization riêng `resume-05/disk_gate_authorization.json`; helper `proposed_finish_last_five.py` chỉ cho phép missing IDs trong danh sách5 đã freeze, refuse widen exception nếu một image previously-ready khác mất.
- Khi ghi:20/25 ready, đã dùng8/10 reclaim; helper cuối đang chạy, tool session43351. Controller đầu47109 đã thoát. **Khi khôi phục kiểm process proposed_finish_last_five.py/child docker pull trước relaunch**; không chạy đồng thời controller cũ.
- Logs cuối ở `resume-05/last-five/`; counter bổ sung vẫn ở resume04. Chưa claim25 hoặc DONE chặng2; không mở qualification/model/test/smoke3.

### Hoàn tất phần tải images —25/25, 06/11/2026

**Đã hoàn thành yêu cầu tải đủ25/25 images W10. Chặng2 tổng thể vẫn PARTIAL, không phải25 task đã chạy test hoặc A3 DONE.**

- Helper cuối thoát0 sau Matplotlib-20676. Consumer audit lúc20:42:48 giờ Việt Nam gọi Docker inspect trực tiếp **25/25 pinned references**, xác nhận RepoDigests khớp và toàn bộ platform `linux/amd64`, đúng11+14 IDs đã khóa.
- `verified_image_inventory.json` có mỗi task/ref/image ID/size/platform; `verified-<task>.json` giữ raw inspect. Không chỉ tin dòng producer báo25/25.
- **5 images W9 cũ còn nguyên**,0 container đang chạy; không prune/xóa files/images/model hoặc đổi settings. Image helper không import/execute source repo đích.
- Tổng reclaim dùng **9/10 lượt**:5 gốc +4 bổ sung (6…9), tất cả COMPLETE/action exit0. Counter5 gốc không đổi bytes, còn1 lượt chưa dùng; không dùng lượt10 chỉ để làm đẹp số RAM sau tải.
- D20GiB chỉ áp dụng5 downloads cuối theo phương án đã trình bày/xác nhận trong hội thoại; RAM4/C10 và gate smoke/campaign giữ nguyên. Cuối pull D23.301.013.504 bytes≈21,70GiB, RAM3.900.710.912 bytes≈3,63GiB; resource snapshot sau audit lưu riêng, không suy đạt gate smoke30GiB.
- Source Git25/25, Linux code copy926 files và controller nhẹ đã có từ trước; không fetch/copy/cài lại. Các runtime/repair path copies không đổi policy/model pins.
- **Còn lại trong chặng2:** model runtime, portable static tools, qualification/profiles local, graph+BM25 bundles, validated A3/A2 comparison configs. Hiện profiles0/bundle pairs0/validated experiment configs0; không giả các bước đó đã hoàn thành từ việc có images.
- Không model call, target tests, container execution, smoke3, T1/T3/T10 hoặc commit/push. Fullbatch vẫn sauT1 và các dependency đã ghi trong plan.

Artifact cuối lượt05: `results/m2/w1112/a3-25/20261106T115908Z-prepare/resume-05/`, gồm image_acceptance/verified_image_inventory/raw inspect, last-five logs, authorization, quota history và closure hashes. Giữ nguyên các lượt đã seal trước đó. Nếu khôi phục: **không chạy lại download controllers**; dùng image_acceptance/consumer audit để tiếp tục phần preparation còn thiếu sau khi kiểm tài nguyên.

Review độc lập chỉ đọc cho phần images: không finding Critical/Important; xác minh25 pins/platform/population và9/10 quota, không thay human sign-off hoặc nghiệm thu A3. Hạn chế vận hành: snapshot20:44:50 có RAM≈3,74GiB và D≈21,36GiB, chưa đạt gates smoke4/30; D20 exception chỉ downloads đã kết thúc. Artifact `review.json` và `resources_final.json` lưu rõ. Trong artifact, kết quả20 images được giữ dưới `interim20/`; file nghiệm thu cuối là `image_acceptance.json`/`verified_image_inventory.json`, không nhầm với audit trung gian.

## Resume 06 — tiếp tục assets/config chặng 2

- TEMP riêng: `C:/Users/pc/AppData/Local/Temp/vg-a3-prepare-82527b76/resume-06`. Đã chụp 34 hashes bảo vệ, HEAD và git status vào `before_files.json`; không tạo lại sources/code copy/images.
- Đầu lượt: RAM khả dụng 7.783.292.928 bytes≈7,25 GiB, C≈11,58 GiB, D≈30,27 GiB; không có preparation job cũ. Không suy nguyên nhân tài nguyên tăng.
- Static tools đã build PASS vào `/home/vgar/w10-a3-local/static-tools`: Python 3.11.17, mypy 2.4.0, Ruff 0.17.0 đúng lock; `static_bundle.json` và build logs lưu phiên bản thực. Không thay bundle cũ hay source script; wrapper artifact chỉ normalize LF và relocate ROOT. Không tạo pip/uv download cache mới.
- Qualification preflight PASS, SDK/CLI daemon khớp. Execute hoàn tất 25/25 COLLECTED, cleanup PASS, trong 126,103 s. Raw run: `/home/vgar/w10-a3-local/qualification/resume06-execute/w95-53dfc905b43f477aa5190d0afa24c6d6/`. Consumer validate đủ 25 profiles, lưu `/home/vgar/w10-a3-local/profiles/<task>.json`; `profile_acceptance.json` ghi hashes/daemon. Đây là sentinel base-only, không phải repro baseline qualification hoặc test issue đã PASS/FAIL đúng mong đợi.
- Helper orchestration đầu dùng Python hệ thống cho bước import consumer nên lỗi `ModuleNotFoundError` sau khi qualification đã hoàn tất. `accept_profiles.py` chạy bằng controller venv, chỉ đọc/validate/copy profiles đã tạo; không chạy lại qualification. Giữ nguyên logs lỗi và receipt thành công, không che lỗi bằng producer exit0.
- Export: `export_bundles.py` đã tạo cặp Astropy-13033 PASS cả hai arm, source finalize PASS; dừng trước Django vì RAM host còn 2.644.070.400 bytes <4 GiB. Process thoát, RAM tự hồi≈4,22 GiB. Không dùng reclaim tại bước này.
- `export_remaining_bundles.py` tiếp tục cùng output `/home/vgar/w10-a3-local/w12/bundles/repair/resume06/`, skip cặp đã PASS, không overwrite. Consumer không đọc thêm toàn bộ graph JSON chỉ để lấy graph_version (dùng binding đã được consumer xác minh), giảm RAM controller; production exporter/retrieval không sửa. Ledger mới `bundle_resume_ledger.json`, acceptance mới `bundle_resume_acceptance.json`; giữ ledger/acceptance lượt đầu bất biến.
- Tại checkpoint này export đang xử lý Django-10914, tool session12349. **Khi khôi phục phải kiểm process/ledger trước relaunch**; không chạy controller thứ hai. Hai lock `DATA/a3-export.lock` và `DATA/repositories/a3-source-read.lock` thuộc controller, không xóa khi process còn chạy.
- Quyết định vận hành: qualification dùng nguyên resource gate sẵn có của repo (RAM host/Linux4 GiB, C10 GiB, D20 GiB); export kiểm host4/C10/D20 trước từng worker. Đây là preparation, không nới gate **trước smoke D30 GiB** và không kéo dài ngoại lệ download5 images. Model runtime chưa chạy; chưa có validated experiment configs; chưa đủ điều kiện kết luận chặng2 DONE.
- Quota reclaim vẫn9/10, còn1 lượt; chưa thêm quyền. Không model load/generation, issue tests, smoke3, campaign, T1/T3/T10 hoặc commit/push.

### Resume06 — cập nhật 22:06, 19 cặp PASS / part4 đang chạy

- Sau Django-10914, helper đã dùng lượt reclaim **10/10 cuối được duyệt**, COMPLETE; counter bổ sung có đúng5 entries6…10, counter5 gốc không đổi. `reclaim_acceptance.json` và bản chụp counters lưu trong resume06. **Không còn quota reclaim.**
- `export_part3.py` tiếp tục từ task3, giữ 2 cặp cũ, đạt18/25 cặp consumer PASS/source finalize PASS. Mỗi task vẫn timeout600s; có chờ RAM tự hồi tối đa60s trước worker, không reclaim. Dừng trước pytest-7205 vì host4.237.611.008 bytes<4GiB sau61,55s natural wait. Giữ `bundle_part3_ledger.json`, `bundle_part3_acceptance.json`, `bundle_part3_stop.json` như bằng chứng PARTIAL.
- Sau process thoát, host RAM tự hồi lên4.383.379.456 bytes>4GiB; đã chạy `export_part4.py`, đọc ledger18 cặp PASS, chỉ tạo 7 task còn thiếu trong cùng output, không overwrite/re-export cặp đã hoàn thành. Ledger/acceptance mới mang tên `bundle_part4_*`.
- Snapshot22:06: đã **19/25 cặp PASS**, đang xử lý scikit-learn-10844. Tool session **74912**, controller part3/session59161 đã thoát. Khi khôi phục kiểm process part4/worker và `bundle_part4_ledger.json`; không relaunch controller thứ2. Quota10/10 không được reset.
- Đã lưu bản sao 1.994 files, 3.913.056 bytes gồm raw qualification preflight/execute, 25 profiles, inputs và static manifest dưới TEMP resume06/`qualified-assets/`; đối chiếu hashes nguồn/copy. Đây là artifact mới, không sửa raw runs hoặc artifacts resume01…05.
- Còn model runtime, hoàn tất7→0 cặp cuối, derive/validate4 config, final inventory/preservation/review/archive. `derive_configs.py`, `prepare_model_stack.py`, `audit_assets.py`, `archive_stage2.py` mới được chuẩn bị, **chưa thực thi** tại snapshot này. Không tính helper chưa chạy là đầu ra DONE; không smoke3/model/issue tests/campaign.

### Quyền mới sau22:08 — reclaim theo nhu cầu trong phần còn lại chặng2

- Người dùng nói rõ: **“bạn có thể tự reclaim và tiếp tục chạy nếu RAM thiếu”**. Áp dụng cho page cache RAM trong phần còn lại chặng2; không mở quyền xóa dữ liệu/images/model, đổi settings/shutdown hoặc chuyển chặng3. Không hỏi lại quyền này ở mỗi lượt.
- Giữ nguyên hai counters5+5 cũ, đã dùng10/10. Quyền mới ghi riêng `stage2_on_demand_authorization.json`; hành động mới từ lượt11 ghi `on_demand_reclaims.json`, reserve trước action. User không đặt cap số mới; helper chỉ thực hiện tối đa một action mỗi gate RAM thiếu, đo lại rồi vẫn dừng nếu gate không đạt, không lặp reclaim vô hạn ở một điểm.
- `reclaim_on_demand.py` kiểm host RAM<4GiB, không container hoặc worker export/qualification/install/model đang chạy; chỉ `sync && printf 1 > /proc/sys/vm/drop_caches`. Controller idle không được coi là worker đang phân tích. Gate RAM4/C10/D20 preparation và D30 trước smoke không đổi; lỗi disk không được chữa bằng reclaim RAM.
- Part4 đã dừng sau **20/25 cặp PASS**, trước Sphinx-11510. Controller mới `export_autonomous.py` đọc ledger20 cặp, chỉ export5 task thiếu, có hook reclaim theo quyền mới tại ranh giới idle. Tool session **12216**; các controller cũ đã thoát. Ledger/acceptance hiện hành `bundle_final_ledger.json` / `bundle_final_acceptance.json` (file acceptance chỉ có khi controller kết thúc).
- Khi khôi phục kiểm controller/worker/counter mới trước relaunch, giữ mọi accepted pairs và raw logs; không dùng lại helper capped10 để vượt cap cũ. Chưa kết luận25 cặp hoặc chặng2 DONE ở thời điểm ghi.

### Resume06 — export hoàn tất25/25; runtime đang cài

- `export_autonomous.py` đã thoát0. **`bundle_final_acceptance.json`: PASS,25 accepted pairs/50 accepted bundles/50 expected slots**, đủ11+14 task IDs. Mỗi task có full Git tree/blob proof trước–sau, source finalize PASS và consumer đọc sidecars thực; không ERROR/TIMEOUT. Không loại task vì retrieval outcome.
- Output thật: `/home/vgar/w10-a3-local/w12/bundles/repair/resume06/<task>/{graph,bm25,graph.json}`. Ledger cuối `bundle_final_ledger.json`; các ledger/acceptance part1…4 là lịch sử dừng tài nguyên, không dùng chúng làm số cuối. Không export lại hoặc xóa25 task directories đã PASS.
- Reclaim mới theo quyền on-demand đã có lượt11 COMPLETE, gate đạt; không sửa counters10 cũ. Xem `on_demand_reclaims.json` để lấy tổng hiện hành, không dùng snapshot này làm cap mới.
- Đã chuyển tuần tự sang runtime: `run_stage2_operation.py runtime`, tool session **2437**, cài thư viện bằng `prepare_model_stack.py` vào controller venv, `--no-cache-dir`, Torch2.5.1+cu121 từ index PyTorch chính thức; Transformers4.57.6/Accelerate1.15.0/Tokenizers0.22.1 theo helper đã chuẩn bị. **Đang cài, chưa nghiệm thu versions/import/CUDA.** Không tải model weights, không model load/generation.
- Khi khôi phục phải kiểm process/pip và `runtime-operation.json`/`torch-install.json` trước mọi lần chạy lại; không overwrite logs hoặc reinstall phần đã thành công. `derive_configs.py` và `audit_assets.py` vẫn chưa chạy, chưa seal resume06 hoặc kết luận chặng2 DONE.

## Kết thúc resume06 — chặng2 ASSETS_PREPARED, dừng trước chặng3

### Kết quả thực tế

- Source/images25 tái sử dụng, không tải lại. Qualification25/25 COLLECTED, cleanup PASS; static tools Python3.11.17/mypy2.4.0/Ruff0.17.0 đúng lock. Sentinel qualification không chứng minh repro baseline hoặc test issue đã đúng.
- Export cuối **25 pairs/50 bundles/50 slots PASS**, không ERROR/TIMEOUT/NOT_RUN; đầy đủ source tree/blob proof trước–sau và consumer sidecars. Resolver `tree-sitter+python-static-v4-external-import`, ranking pin `sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a`, B1500 cả hai arm, BM25 k1=1.2/b=0.75 đã đối chiếu trên artifacts thực.
- Runtime operation exit0 trong619,943s: Torch2.5.1+cu121, Transformers4.57.6, Tokenizers0.22.1, Accelerate1.15.0; pip check/freeze/import và CUDA availability PASS, `torch_cuda=12.1`, model_loaded=false. Thư viện cài trong controller venv riêng, không tải lại/nạp model weights. Pip điều chỉnh HuggingFace Hub1.33.0→0.36.2 theo dependencies Transformers trong venv này; actual freeze được lưu. Không thay W9 venv hoặc machine settings.
- Config operation exit0 trong95,840s;4 configs `load_experiment()` PASS, fairness cả4 PASS và source maps A2/A3 cùng stage giống hệt. Model/prompt/budget/900–120–1800 không đổi. A2 chỉ comparison-only, chưa chạy.
- Planning A3 đủ25 rows:20 có task inputs,3 prior exclusions,2 thiếu repro. Đây là planning inventory, **không phải20 launch-ready**, chưa preflight stage4. Không tạo repro giả hoặc thay eligibility. Từng profile, graph document, graph bundle và BM25 bundle của25 task đều có hash khác W10 lịch sử; `config_acceptance.json/w10_comparison` ghi từng task. Không gọi comparison local là controlled paired comparison với A2 lịch sử.
- Audit operation exit0 trong12,978s:926 Linux code-copy files nguyên vẹn;25 profiles/images đúng daemon;5 W9 images cũ còn nguyên;0 container;404 data files/4.597.061.468 bytes≈4,28GiB được stream SHA-256. Raw graph/bundle lớn giữ trong WSL, evidence Windows lưu inventory/hashes để tránh sao chép thêm4,28GiB.
- Theo quyền on-demand mới, đã thêm3 reclaim11/12/13 COMPLETE (trước Sphinx export, configs, audit), tổng13; counters5+5 cũ không đổi. Chỉ RAM page cache ở idle, không xóa files/images/model, thay settings hoặc shutdown. File `on_demand_reclaims.json` ghi từng action/reservation, authorization riêng lưu nguyên phạm vi chặng2.

### Đường dẫn và receipts

- Evidence mới: `results/m2/w1112/a3-25/20261106T115908Z-prepare/resume-06/`; TEMP cùng suffix. `stage2_summary.json`, `profile_acceptance.json`, **`bundle_final_acceptance.json`**, `config_acceptance.json`, `linux_asset_inventory.json`, operation/log receipts và `commands.json` là đầu vào khôi phục; các part1…4 là lịch sử PARTIAL.
- WSL data root `/home/vgar/w10-a3-local`; code `/home/vgar/vgar-a3-local-20261106`; controller `/home/vgar/w10-a3-local/venvs/controller/bin/python`; static bundle `/home/vgar/w10-a3-local/static-tools`.
- Profiles `/home/vgar/w10-a3-local/profiles/<task>.json`; raw qualification run đã ghi bên trên. Graph/bundles `/home/vgar/w10-a3-local/w12/bundles/repair/resume06/<task>/`.
- Configs `/home/vgar/w10-a3-local/inputs/experiments-resume06/{a3_stage1,a3_stage2,a2_stage1,a2_stage2}.json`. Experiment IDs: A3 stage1 `55b7efdd613206e9`, stage2 `e43e5b3e572f8cae`; A2 comparison stage1 `100fd897d38f86ff`, stage2 `843c858f440d42ab`. Bản sao bytes4 configs nằm trong evidence `configs/`; không dùng config của máy M3 cũ để launch local.
- Có thể xem WSL data từ Windows tại `\\wsl.localhost\VGAR-Harness-W9\home\vgar\w10-a3-local\`. Không di chuyển/sửa bytes inputs sau validation; đổi inputs/code ở stage4 cần freeze/preflight lại.

### Giới hạn và khôi phục

- Snapshot22:37:00 ngày06/11/2026: host RAM2.889.715.712 bytes≈2,69GiB; C12.418.318.336 bytes≈11,57GiB; D19.920.302.080 bytes≈18,55GiB; không owned preparation job hoặc container còn chạy. **Gate trước smoke vẫn RAM4/C10/D30**, chưa đạt RAM/D; D cần thêm≈11,45GiB để tới30, chưa gồm sizing campaign sau smoke. Không tự prune/xóa dữ liệu/compact VHD hoặc nới ngưỡng.
- Model runtime/config/assets PASS không đồng nghĩa model inference, issue baseline, grading hoặc A3 thành công. Không có model call, issue tests, smoke3, campaign, T1/T3/T10 hoặc commit/push trong lượt này. Không chạy regression stage4 trước khi được giao; không đưa số PASS lịch sử vào gate mới.
- **Không relaunch bất kỳ source/image/export/install/qualification helper nào đã PASS.** Sessions12216/2437/52829/44531 đã thoát; trước bước mới vẫn kiểm process/resources/receipts. Chặng2 hoàn tất assets/config, M2-W12-1 vẫn chưa DONE thực nghiệm. Chờ người dùng giao chặng3; fullbatch vẫn sauT1 và các dependencies của plan, không tự vượt điểm dừng.

### Review và bảo toàn cuối

- Review fresh-context chỉ đọc cho chặng2: **không Critical/Important/Minor**; independently kiểm population/bindings,1.994 hashes qualification,4 configs, raw runtime/counters/preservation và trực tiếp rehash379 WSL assets ngoài25 graph lớn. Review không thay human/cross-role sign-off, không đánh giá lại dirty implementation T2/T4/T5/T6/T7, inference hoặc kết luận thực nghiệm. Reviewer đọc evidence/implementation cho25 graph lớn và926 code files; primary audit đã hash đủ các files này. `review.json` ghi phạm vi/giới hạn đầy đủ.
- Kiểm bảo toàn xác nhận chỉ3 tài liệu được phép thay đổi: PROGRESS, status M2, checkpoint này;31 files được bảo vệ (gồm dirty code/tests/báo cáo/DB/index), HEAD/path-status set và toàn bộ lịch sử tài liệu giữ nguyên.532 entries của artifacts preparation các lượt trước khớp seals. Scoped whitespace check PASS; không sửa whitespace có sẵn trong báo cáo người dùng.
- Archive/seal resume06 do executor tạo và đối chiếu sau review; receipt `archive_mapping.json`, `closing_checks.json`, `artifact_hashes.json`. Không coi review trước archive là bằng chứng seal đã tạo; chỉ dùng seal thực khi khôi phục. Không có operation/model/campaign mới sau audit.
