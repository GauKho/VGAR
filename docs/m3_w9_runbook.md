# Runbook M3 tuần 9: commit, GitHub và pilot

Lập 25/10/2026. Các bước theo đúng thứ tự. Lệnh PowerShell gõ trong Windows Terminal; lệnh `bash` chạy trong WSL (`wsl -d Ubuntu`).
Quyết định nền: `docs/m3_w9_decisions.md`. Trạng thái và checklist: `docs/status/m3.md`.

## Phần A. Commit thành 5 PR

Không commit `artifacts/sample_graph.db`: file này bị một test có sẵn ghi đè khi chạy suite.

```powershell
git checkout -- artifacts/sample_graph.db

# PR 1: CI (M3-W9-1)
git switch -c m3/w09-ci
git add .github/workflows/tests.yml pyproject.toml tests/test_hf_model.py
git commit -m "ci: run pytest on every PR without model weights"
git push -u origin m3/w09-ci

# PR 2: quy trình (M3-W9-4), sau khi điền handle vào CODEOWNERS
git switch -c m3/w09-process main
git add .github/CODEOWNERS docs/status/m3.md
git commit -m "docs: add CODEOWNERS and M3 status"

# PR 3: runner (M3-W9-2) cùng spec, plan, quyết định và runbook
git switch -c m3/w09-runner main
git add src/vgar/evaluation/repair scripts/run_repair_experiment.py tests/m3 configs/m3 configs/m2/w9_pilot_linux.json docs/superpowers docs/m3_w9_decisions.md docs/m3_w9_runbook.md
git commit -m "feat(runner): resumable task x variant runner with preflight and GPU peak"

# PR 4: budget export cho repair (module M1, nhờ M1 review), D5
git switch -c m3/w09-export-budget main
git add src/vgar/evaluation/retrieval/pilot_export.py scripts/export_w9_pilot_bundles.py tests/test_w9_pilot_bundles.py configs/m1/w9_bundle_profile_repair.json
git commit -m "feat(export): shared snippet budget for repair bundles (B=1500 profile)"

# PR 5: trình bày snippet method thụt lề (module M2, nhờ M2 review), D11
git switch -c m3/w09-presentation-indent main
git add src/vgar/repair/context_presentation.py tests/m2/w910/test_context_presentation_lines.py
git commit -m "fix(repair): present indented method snippets as whole lines for V11 replacement"
git add src/vgar/repair/docker_executor.py tests/m2/w910/test_docker_admission.py
git commit -m "fix(repair): make docker control files readable by cap-less container root on Linux"
git add src/vgar/repair/config.py tests/m2/w78/test_w78_config.py
git commit -m "fix(repair): keep the venv interpreter path unresolved so workers see venv packages"
```
`configs/m3/w9_pilot.json` (hash do M3 sinh, D10) đi cùng PR 3 hoặc một PR riêng sau khi M1 xem dữ liệu.

Các file đang nằm trên nhánh `m3/w09-runner-ci` dưới dạng chưa commit. `git switch -c` mang chúng sang nhánh mới. Mỗi PR chỉ `git add` phần của mình; phần còn lại vẫn nằm trong working tree cho PR sau. PR 2 và PR 3 cần CI của PR 1 đã có trên `main` để chạy được check `tests`.

## Phần B. GitHub (người có quyền admin `GauKho/VGAR`)

1. **Đo CI:** mở PR 1, xem job `tests` (thời gian, kết quả). Ghi thời gian vào `docs/status/m3.md` §2. Nếu dưới 10 phút thì giảm `timeout-minutes` xuống 15.
2. **Branch protection** (Settings → Branches → Add rule cho `main`): Require a pull request, 1 approval, Require review from Code Owners, Require status checks → `tests`, Do not allow bypassing. Hoặc dùng lệnh:
   ```bash
   gh api -X PUT repos/GauKho/VGAR/branches/main/protection --input - <<'EOF'
   {"required_status_checks": {"strict": true, "contexts": ["tests"]},
    "enforce_admins": true,
    "required_pull_request_reviews": {"required_approving_review_count": 1, "require_code_owner_reviews": true},
    "restrictions": null}
   EOF
   ```
3. **Chứng minh chặn:** mở một PR nháp thêm `assert False` vào một test → không merge được. Mở một PR chưa có review → không merge được. Ghi link vào `docs/status/m3.md` §3.
4. **Board:** tạo Project với cột Todo / In progress / In review / Done. Tạo issue cho từng deliverable W9 theo Phụ lục C của plan, cùng một issue cho test `xfail` ở `tests/test_hf_model.py`, rồi thay chữ "TODO" trong `reason` bằng link issue.

## Phần C. Pilot 15 record

### Bước 1. WSL2, Docker, GPU

```powershell
wsl --install -d Ubuntu        # bỏ qua nếu đã có
```
Docker Desktop → Settings → Resources → WSL integration → bật cho Ubuntu. Sau đó kiểm trong WSL:
```bash
ls -l /var/run/docker.sock && docker info --format '{{.OSType}} {{.ID}}'
nvidia-smi --query-gpu=name,memory.total --format=csv
```

### Bước 2. Repo và venv trong WSL

Code và dữ liệu đặt trong filesystem của WSL (`~`), không đặt dưới `/mnt/d`: admission ghi đường dẫn tuyệt đối, còn Git và Docker chạy chậm trên ổ Windows.
```bash
git clone https://github.com/GauKho/VGAR.git ~/vgar && cd ~/vgar && git switch m3/w09-runner
python3.11 -m venv .venv && . .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[dev]"
python -c "import torch; print(torch.cuda.is_available())"     # phải in True
python scripts/provision_m1_tokenizer.py --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 --assets-root artifacts/m1/tokenizers \
  --manifest /tmp/tokenizer_manifest.json
huggingface-cli download Qwen/Qwen3-4B-Instruct-2507 --revision cdbee75f17c01a7cc42f958dc650907174af0554
pytest tests/m3 -q                                             # 42 passed
```
`configs/m2/w9_pilot_linux.json` trỏ tới `~/vgar/.venv/bin/python` và snapshot trong `~/.cache/huggingface`. Nếu clone hoặc cache ở chỗ khác thì sửa hai dòng này.

### Bước 3. Dữ liệu dưới `~/w9` (data root)

```
~/w9/repositories/<task_id>/            checkout đúng base_commit, sạch
~/w9/profiles/<task_id>.json            task_env.json của M1-W9-5 (cả 2 EXCLUDED)
~/w9/bundles/<task_id>/{bm25,graph}/    context.json, context_manifest.json, test_links.json
```

**Cách 1 (khuyên dùng): xin M1.**
- 5 file `task_env.json` cùng `qualified-runtime-02.json`, từ `results/m1/w9/m1-w9-5/20261024-docker-only/`.
- `pilot_audit.json` của M1-W9-3, để lấy sidecar hash.
- Bundle export lại theo budget mới (D5; cần M1 sửa code, xem decisions).

Checkout tự tạo được bằng `scripts/prepare_w9_pilot_inputs.py --prepare-sources --sources-root ~/w9/repositories` (tham số cache xem `docs/m1_w9_3_dual_arm_bundles.md` §chạy).

**Cách 2: M3 tự sinh lại.**
- Profile: chạy `prepare_task_env.py --runtime <runtime đã qualify> --prepare-images`, rồi `--execute` (`docs/m1_w9_5_task_env.md` §CLI).
- Bundle: chạy `export_w9_pilot_bundles.py` (`docs/m1_w9_3_dual_arm_bundles.md`).

Theo D10, ghi rằng hash do M3 sinh. Cả hai script đều đòi tài nguyên lớn: khoảng 4 GiB RAM trống và 10–20 GiB đĩa cho image.

### Bước 4. Config pilot

```bash
cp configs/m3/w9_pilot.template.json configs/m3/w9_pilot.json
```
Thay mọi `FILL`:
- `profiles.*.sha256` = trường `profile_hash` trong từng `task_env.json`, **theo con số M1 gửi** chứ không đọc lại từ file vừa nhận (D10);
- `bundles.*.*.hashes` = sidecar hash trong audit export.

`manifest.sha256` đã điền sẵn.

### Bước 5. Kiểm test tái hiện FAIL trên base

Với mỗi task COLLECTED có input (xem `configs/m3/w9_pilot/tasks/README.md`), chạy test trong image của task. Image SWE-bench đã có sẵn repo ở base commit, đã build, tại `/testbed`, nên **không mount checkout** (mount đè sẽ mất phần build, ví dụ C extension của matplotlib):
```bash
T=pydata__xarray-3305; IMG=$(python -c "import json;print(json.load(open('$HOME/w9/profiles/$T.json'))['env_ref'].removeprefix('docker://'))")
docker run --rm --network none -v $PWD/configs/m3/w9_pilot/tasks:/repro:ro -w /testbed $IMG \
  bash -lc "git log --format='%H %s' -2 && git diff --name-only <base_commit> HEAD | wc -l && cp /repro/$T.repro.py /tmp/test_repro.py && /opt/miniconda3/envs/testbed/bin/python -m pytest -q -p no:cacheprovider /tmp/test_repro.py"
```
Image SWE-bench có thêm một commit tên `SWE-bench` nằm trên base, nên `HEAD` khác `base_commit`. Phải kiểm: commit cha là đúng `base_commit` trong manifest, và `git diff --name-only <base_commit> HEAD` ra 0 file (đã kiểm với Xarray ngày 25/10). Kết quả phải là **1 failed** vì lỗi của issue. PASS nghĩa là test sai; lỗi import hay cú pháp nghĩa là test hỏng. Sửa test rồi chạy lại.

### Bước 6. Preflight

Từ Windows Terminal:
```powershell
wsl -d Ubuntu -- bash -lc "cd ~/vgar && .venv/bin/python scripts/run_repair_experiment.py preflight --config configs/m3/w9_pilot.json --data-root ~/w9"
```
Mong đợi:
- Astropy, Django: `ERROR TASK_EXCLUDED`.
- Task không có input: `ERROR TASK_INPUT_MISSING`.
- Các cặp còn lại: `FITS`.

Nếu có `OVER_CAP`: tính lại budget B theo D5 và nhờ M1 export lại. Không cắt tay.

### Bước 7. Chạy pilot

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/vgar && .venv/bin/python scripts/run_repair_experiment.py run --config configs/m3/w9_pilot.json --data-root ~/w9"
wsl -d Ubuntu -- bash -lc "cd ~/vgar && .venv/bin/python scripts/run_repair_experiment.py status --config configs/m3/w9_pilot.json --data-root ~/w9"
```
- Ctrl+C an toàn: attempt bị ghi `INTERRUPTED`; chạy lại cùng lệnh để làm tiếp.
- Không xóa `results/m3/<experiment_id>/`.
- Muốn chạy lại một cặp đã xong thì dùng `--rerun TASK:VARIANT --reason "<lý do>"`, và ghi lý do vào `docs/status/m3.md`.

### Bước 8. Ghi kết quả

Dán bảng `status` vào `docs/status/m3.md` §5, kèm:
- thời gian trung bình và tối đa chỉ trên các attempt không `timed_out`, cùng số attempt `≥ 30 phút`;
- VRAM peak (số đo toàn device, máy 6 GB có offload);
- so với ngưỡng 30 phút/task: giữ N, giảm N hay thuê máy (điền Phụ lục B của plan);
- giới hạn: số task chạy thật, oracle là test tái hiện chứ không phải harness, A2 thiếu tool (D9), hash do ai sinh (D10).
