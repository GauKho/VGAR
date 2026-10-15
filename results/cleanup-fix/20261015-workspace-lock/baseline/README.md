# M2 tuần 7–8 — Repair & Verification

**Logging update 15/10/2026:** đã bổ sung parser location/count diagnostics,
chained traceback và observer effective HF config/attention mask. Không chạy
thêm model; B vẫn BLOCKED. Xem [hướng dẫn log](docs/LOG_DIAGNOSTICS_VA_CACH_DOC_LOI.md).
Full suite logging hiện tại **175 PASS**, Ruff PASS; observer mới chỉ được
kiểm offline và đối chiếu source HF đã pin, chưa nghiệm thu bằng generation GPU.
Code đã khác frozen runtime của campaign cũ: đọc lịch sử bằng archive-based
`--history` theo hướng dẫn, không reset/bypass guard để dùng `--status` cũ.

**Kết quả mới nhất, 15/10/2026:** đã triển khai adaptive prompt V5–V9 và controller
giới hạn 4 B +4 C +3 final. **C real PASS dưới V9; B BLOCKED sau 4 FAIL; final
A/B/C chưa chạy, nghiệm thu 3/3 chưa đạt.** Campaign đã kết thúc FAIL, không còn
model chạy. Không reset hoặc dùng slots dư để chạy B lần 5. Full self-test
**152 PASS**, Ruff và audit bảo toàn source/evidence PASS.
Xem [báo cáo thực tế](results/adaptive_acceptance/2026-10-15-v5-plus/REPORT.md),
[hướng dẫn V5+](docs/ADAPTIVE_V5_PLUS_VA_CACH_DOC_EVIDENCE.md) và [PROGRESS](PROGRESS.md).
Các kết quả V3/V4 bên dưới là lịch sử, không phải campaign hiện hành.

Package độc lập theo plan đã duyệt ngày 14/10/2026. Không thay `VGAR`, không
fine-tune, không chạy SWE-bench hoặc tự tích hợp MCP. M1 là dependency chỉ đọc
ở commit `b8e2461635b81d1ae790445efea5c9757d91700a`.

Chức năng: nhận/validate gói M1 → fixed prompt → một generation → strict unified
diff → private Git worktree → pytest/collection/syntax/mypy/Ruff → evidence.
Giữ source/tests/config gốc. Native **không phải OS sandbox**; CLI chỉ chấp nhận
ba fixture đã khóa byte hashes, không dùng để chạy repo không tin cậy.

**Trước extension V3/V4 (historical):** Qwen trả format không hợp lệ hai lượt A
(v1 SEARCH/REPLACE; v2 sai hunk counts). Parser chặn, source không đổi. Không chạy
lại phương pháp hiện tại; lệnh real bên dưới là tham khảo cho lần nghiệm thu mới
sau quyết định của owner. Ba fake PASS chỉ chứng minh engine, không LLM repair.

Ngày14/10 user đã duyệt extension V3/V4 có giới hạn; xem
[prompt/campaign mới](docs/PROMPT_V3_V4_VA_NGHIEM_THU_REAL.md) và latest section
trong PROGRESS. Không tự rerun V1/V2. `scripts/run_acceptance.py --status` chỉ đọc;
`--run` dùng cùng campaign,6newattempts/2failures, không tự reset.

**Lịch sử campaign V3/V4 ngày 14/10:** terminal **FAIL / FAILURE_LIMIT**, dừng sau
bốn runs và hai failures. A-V3/V4 real PASS; B-V3 thiếu sửa invoice, B-V4 sai
dòng bắt đầu hunk; C chưa chạy. Không chạy thêm LLM hoặc reset manifest.
Prompt/controller đã cải thiện; gate **3/3 real repairs cùng version chưa đạt**.
Full self-test cuối: **126 tests PASS**; Ruff E9/F PASS. Xem
[báo cáo campaign](results/acceptance/2026-10-14-prompt-v3-v4/REPORT.md) và [checkpoint](PROGRESS.md).

## Chạy trên máy hiện tại — không cài lại

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# Offline tests. Mỗi lần có JSON/REPORT riêng; không tải model.
& $python .\scripts\record_tests.py tests --timeout-seconds 180
$LASTEXITCODE
# Offline demo dùng reference diff, CHỈ để kiểm engine/verification; không tính LLM success.
& $python .\scripts\run_demo.py --task .\examples\tasks\multi_file_invoice.json --mode fake
$LASTEXITCODE
# LỆNH REAL CŨ chỉ là tham khảo, để comment tránh chạy lại V2/campaign đã hết cap.
# & $python .\scripts\run_demo.py --task .\examples\tasks\single_file_login.json --mode real
# Cần owner duyệt phương pháp/phiên thử mới trước khi chạy thêm LLM.
# Tổng hợp chỉ đọc; không inference lại. Không trộn kết quả v1 với v2.
& $python .\scripts\summarize_runs.py --mode real --prompt-version m2-w78-v2
# CHỈ ĐỌC: kết quả V3/V4 nằm trong campaign riêng, không lẫn với V2.
& $python .\scripts\run_acceptance.py --status
```

Chỉ sau single-file qua **valid diff + verification** mới dùng tasks
`multi_file_invoice.json` rồi `missing_links.json` ở real mode. Hiện gate chưa đạt.
Run FAIL/ERROR vẫn cần đọc JSON; không chạy lặp phương
pháp cũ. Mặc định 1 generation/run, global1800s, generation900s, command120s;
input6000/output1536/reserve256. Không coi model trả OK là repair PASS.

## Setup lần đầu trên máy khác

1. Đặt M2 và checkout VGAR M1 pinned ở hai thư mục sibling. Không chỉ clone main
   rồi giả định có consumer mới. Có Python3.11, Git và source/contracts đúng pin.
2. Chạy một lần, hoặc khi dependencies đổi:

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
py -3.11 -m venv .venv
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $python -m pip install -e '.[dev]'
```

3. Tokenizer assets không có trong Git: cung cấp bốn files theo manifest M1 hoặc
   provision bằng `VGAR/scripts/provision_m1_tokenizer.py --help`, đúng model/SHA.
   Đặt đường dẫn manifest trong `config/demo.json`. Counter kiểm hashes, không tải
   weights. Full prompt offline dùng cùng assets và Jinja template, không Torch.
4. `examples/tasks`, snapshots, handoffs và receipt đã được chuẩn bị tại máy này.
   Nếu nhận đủ package thì không phải chạy `prepare_inputs.py` lại. Script này
   chỉ dùng khi có M1 archived export tương ứng; không overwrite inputs đã sửa.
5. Real mode cần riêng một interpreter có Torch CUDA/Accelerate/Transformers
   tương thích và cached weights Qwen3-4B tại SHA đã chốt. Profile hiện tái dùng
   **interpreter** `../vgar_mcp_mvp/.venv`, không import/sửa source repo cũ.
   Trên máy khác sửa path interpreter/snapshot trong config sau qualification;
   không tự đổi model/SHA, không để fake fallback. Core venv không chứa Torch.
6. Chạy `record_tests.py` trước; nếu phù hợp tài nguyên thì qualifier
   `scripts/qualify_model.py` rồi repair. Không auto-download weights; worker
   dùng `local_files_only=True`, HF offline.

Byte manifests hiện thuộc fixture Windows CRLF. ZIP giữ nguyên bytes. Khi clone
Git trên Windows cần checkout EOL khớp; source/hash mismatch phải review/export
lại, không sửa hashes để bỏ guard. Chưa nghiệm thu Linux/container portability.

## Output và cách hiểu

- `results/tests/<UTC-ID>/run_record.json`, JUnit, REPORT: kết quả tự kiểm code M2.
- `results/repair/<UTC-ID>/run_record.json`: toàn bộ stage inputs, commands,
  stdout/stderr, exit, UTC start/end, monotonic durations, exact pytest outcomes,
  model/token/prompt/source metadata, patch và reasons.
- `prompt.txt`, `raw_model_output.txt`, `candidate.diff`, `transport.diff`,
  `applied.diff`, `evidence_bundle.json`: chỉ tạo khi stage tương ứng có dữ liệu.
- `transport.diff` chỉ bind EOL LF/CRLF để Git giữ bytes; không sửa content/hunk
  counts. Raw output giữ riêng. Không convert SEARCH/REPLACE thành diff để tính PASS.
- `PASS`: plausible theo suite/policy fixture, không proof mọi semantics.
- `FAIL`: patch/behavior/static checks không đạt. `ERROR`: input/runtime/incomplete.
- `NOT_RUN`: stage chưa chạy; không được tự xem là PASS.
- API/structural graph checks là NOT_RUN (tuần sau); chưa có M3 MCP integration.

Chi tiết: [Handoff](docs/HANDOFF_M1_M3.md), [hướng dẫn Việt](docs/GIAI_THICH_M2_W7_W8_VA_CACH_KIEM_THU.md),
[PROGRESS](PROGRESS.md), [failures](docs/FAILURES.md), [reuse](docs/REUSE_MAP.md).
Kết quả hiện tại: [báo cáo triển khai](docs/COMPLETION_REPORT.md),
[final review và fixes](docs/FINAL_REVIEW.md).

