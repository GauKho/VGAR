# VGAR-MCP — Research design và khung protocol

> **Trạng thái:** bản nháp, M3 ráp ngày 31/10/2026. **Chưa được nhóm ký.**
> **Vai trò:** trả nợ deliverable W1–2 (`docs/research_design.md`, task CHUNG-01/06, M3-02, CHUNG-03 pin model và budget). Đồng thời là **khung cho `docs/protocol_freeze_heldout.md`** (M3-W12-2): freeze sẽ chép §3–§10, điền các mục **[MỞ]** ở §11 rồi ký.
> **Nguồn:** `D:\kltn\proposal_vgar_mcp_final_corrected.md` (RQ, metrics §13), `D:\kltn\project_plan_16_weeks.md` (scope, ablation, metrics tối thiểu), `VGAR_W9_W16_Deliverables (1).md` v2, spec W9 `docs/superpowers/specs/2026-10-25-m3-w9-design.md`, spec W10 `docs/superpowers/specs/2026-10-27-w10-dev-ablation-design.md`, quyết định D1–D12 (`docs/m3_w9_decisions.md`, `docs/m2_w9_decisions.md`) và D13–D26 (`docs/m3_w10_decisions.md`).
> **Quy ước:** mục nào ghi "đã chốt (Dxx)" thì nguồn là quyết định đó. Tài liệu này không tạo quyết định mới. Mọi mục chưa có quyết định đều đánh dấu **[MỞ]**.

## 1. Claim và phạm vi

**Claim nghiên cứu** (plan W1–2): graph-guided retrieval kết hợp verification evidence giúp coding agent sửa lỗi đa file tốt hơn so với retrieval văn bản (BM25) và verification chỉ dùng test.

**Phạm vi đã thực hiện** (plan, mục Scope MVP):

| Hạng mục | Chốt |
|---|---|
| Ngôn ngữ | Python |
| Benchmark | SWE-bench Verified (§3) |
| Model | Một model cố định, pin theo revision (§6) |
| Graph | Layer 1 (tree-sitter), Layer 2 (symbol resolution), Layer 5 (tests/typecheck/lint), Layer 6 (SQLite + MCP) |
| Arch-CPG | Có `G_code`, `G_repo`. Không có `G_arch`; `G_task` chỉ có ở dạng Issue/anchor |

**Ngoài phạm vi**, theo quy tắc cắt scope của plan. Phải ghi vào Limitations, không được claim:
- `G_arch` và architecture lift, nên không có risk theo component.
- GraphDiff (proposal §7), Layer 3 Joern/CodeQL, Layer 4.
- Semantic invariant kiểu Daikon (proposal §12.4), nên không có A4.
- Baseline embedding, grep và agent default exploration (proposal §13.1). Retrieval chỉ so với BM25.
- MCP prompts (proposal §10.4). Đa ngôn ngữ. Fine-tuning.

## 2. Câu hỏi nghiên cứu, giả thuyết, phép đo

RQ lấy từ proposal §2.2, đã thu hẹp theo §1. Cột "Task đo" chỉ ra deliverable nào sinh số liệu.

| RQ | Giả thuyết (có hướng, kiểm trên held-out) | Phép đo | Task đo | Ghi chú |
|---|---|---|---|---|
| **RQ1** Graph construction | H1: graph dựng từ tool open-source có độ chính xác edge `CALLS`/`IMPORTS` đủ dùng cho retrieval | Precision/recall edge trên mẫu gán tay; tỷ lệ call site unresolved; build time | **Chưa có task trong v2** | [MỞ] cần người nhận (§11, mục O6) |
| **RQ2** Retrieval | H2: graph retrieval có Recall@k cao hơn BM25 ở cùng budget token | Gold-file/function Recall@3/5/10, MRR, token cost; báo thêm Recall@B tại budget repair B = 1500 (D5) | M1-W13-1/2 | Phân tầng single-file/multi-file |
| **RQ3** Patch impact | H3: impact từ graph chứa vùng bị ảnh hưởng thật nhiều hơn baseline chỉ đọc diff | **Chưa định nghĩa** | **Chưa có task trong v2** | [MỞ] O6. Hiện chỉ có bằng chứng khả thi: 16/16 `ImpactReport` sinh được từ patch thật (W10) |
| **RQ4** Verification | H4a: graph retrieval làm tăng tỷ lệ sửa đúng vị trí và tỷ lệ resolved (A1 so với A0). H4b: thêm check làm giảm false accept mà không tăng false reject quá mức (A2, A3 so với A1) | Phễu F1–F8 (§8), FAR/FRR trên patch pool (M2-W12-2) và trên held-out | M2-W12-2, M3-W13-1, M2-W14-2 | |
| **RQ5** MCP usability | H5: agent gọi được graph qua MCP với latency và chi phí token chấp nhận được | Tool calls/task, latency p50/p95, token/task, invalid call rate, audit-log completeness | M3-W12-1 | Hai metric cuối chưa có trong M3-W12-1 (O7) |

## 3. Benchmark và split

| Mục | Giá trị đã pin | Nguồn |
|---|---|---|
| Dataset | `princeton-nlp/SWE-bench_Verified` | manifest W10 |
| Revision | `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` | `configs/m1/w10_dev_manifest.json` |
| Hash parquet | `sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd` | như trên |
| Luật split | `sha256_instance_id_first8hex_mod100_lt40_dev_v1`: dev khoảng 40%, held-out khoảng 60%, chỉ phụ thuộc `instance_id` | `src/vgar/evaluation/retrieval/dataset.py:16–25` (quyết định W5–6) |
| Cỡ split | dev 208 task (28 task sửa nhiều file), held-out 292 task | spec W10 §4 |
| Chặn held-out | `require_split` tính lại split từ `instance_id`; muốn mở held-out phải có `--allow-heldout` và quyết định ghi lại | `dataset.py:28–38` |
| Harness chấm | swebench 4.1.0, chạy offline trong Docker (WSL2) | D15, D16 |

**Dev** dùng để phát triển và tune. **Held-out** chỉ được chạy một lần, sau khi protocol được ký và gắn tag `protocol-freeze`.

## 4. Chọn population

Các luật dưới đây đã chốt trên dev và **áp nguyên cho held-out**.

1. **Manifest khóa trước khi chạy** (D14). Danh sách ứng viên lấy theo round-robin repo rồi theo `instance_id` (`repo_round_robin_then_instance_id_v1`), `min_source_files = 1`, không có seed ngẫu nhiên. Manifest không chứa gold patch. Query policy: `problem_statement_only_no_hints_or_gold`.
2. **Tiền tố RUNNABLE** (D18). Population là tiền tố ngắn nhất của danh sách có đủ N task RUNNABLE. RUNNABLE gồm ba điều kiện: qualify `COLLECTED`, có test tái hiện đã kiểm FAIL trên base, và preflight `FITS` ở mọi arm.
3. **Task bị loại vẫn nằm trong mẫu số.** Các lý do loại: `TASK_EXCLUDED` (qualify thất bại, hoặc OVER_CAP ở bất kỳ arm nào), `TASK_INPUT_MISSING` (không viết được test tái hiện đáng tin, ghi vào `EXCLUDED.md` trước khi chạy). Task OVER_CAP ở một arm bị loại ở **mọi arm** qua `source.excluded` (D25).
4. **Không chọn lại task sau khi thấy kết quả** (D14, D24). Qualify lại hoặc mở rộng tiền tố chỉ được làm khi tiền tố đó chưa có run nào (D21, D24).
5. Qualify có thể chạy theo cửa sổ `--offset/--limit` (D23). Đơn vị chọn task vẫn là tiền tố.

**Trạng thái dev (W10):** N = 25 task trong mẫu số, 20 RUNNABLE, trên hai experiment `9f1b2346fa028094` (nấc 1) và `cfb605118a52b835` (nấc 2). Con số này dưới mức 30–50 của plan (D24, amendment).

## 5. Biến thể (ablation)

Theo bảng ablation tối thiểu của plan. Bảng §13.3 của proposal đã được plan định nghĩa lại theo quy tắc cắt scope; Methodology phải ghi rõ điều này.

| Variant | Arm retrieval (D1) | Check bắt buộc | File | Đo gì |
|---|---|---|---|---|
| A0 | `bm25` | `tests` | `configs/m2/variants/w10/A0.json` | Baseline retrieval văn bản |
| A1 | `graph` | `tests` | `configs/m2/variants/w10/A1.json` | Đóng góp của graph retrieval (so với A0) |
| A2 | `graph` | `tests, syntax, mypy, ruff` (baseline delta) | `configs/m2/variants/w10/A2.json` | Đóng góp của evidence cơ bản (so với A1) |
| A3 | `graph` | A2 + `api_check` + `structural_check` | `configs/m2/variants/A3.json` (chưa có) | Đóng góp của graph verification (so với A2). **[MỞ] O4** |

Các trường chung, giống nhau ở mọi arm:
- `patch_mode = "normalized"` (D13): chuẩn hóa diff theo đúng 6 luật. Không cứu khối context bịa (`CONTEXT_NOT_FOUND`) hoặc khối khớp nhiều chỗ (`CONTEXT_AMBIGUOUS`). Luôn báo cả strict lẫn normalized.
- `path_listing = "context"` (D19): prompt chỉ liệt kê các path có trong context. Quyền sửa vẫn là toàn bộ `allowed_source_paths`, giống nhau giữa các arm (D6).
- `static_mode = "baseline_delta"`, `diagnostic_identity_version = "m2-static-delta-v1"`: chỉ FAIL khi có diagnostic mới so với baseline (M2-W9-2).
- Mỗi attempt sinh tối đa một lần. A0–A2 không có retry hay feedback (spec W10 §4).

**Bộ static tool cho A2 (D12):** Python 3.11.17, mypy 2.4.0 (`--python-version 3.10`), Ruff 0.17.0, được copy vào container. Testbed Python < 3.7 thì mypy ghi `UNAVAILABLE` (không bao giờ tính là PASS) và Ruff vẫn bắt buộc. Báo subgroup "đủ mypy + Ruff" và "chỉ Ruff".

## 6. Cấu hình đã pin (model, prompt, budget)

Đây là nội dung CHUNG-03. Hash là sha256 của nội dung file đã commit tại `483f4394`. Khi freeze phải **tính lại trên máy chạy** bằng `vgar.repair.evidence.digest`, và kết quả phải trùng.

### 6.1. Model và tokenizer (D7)

| Mục | Giá trị |
|---|---|
| Model | `Qwen/Qwen3-4B-Instruct-2507` |
| HF revision | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Precision, decoding | fp16, `do_sample = false` (greedy), `device_map = auto` |
| Tokenizer manifest | `artifacts/m2/w5-w6/tokenizer_manifest.json` · `sha256:35a7802c98c4555577da4a5b085d32ca5fbad410ba49b889bd67228b4cfdef3c` (pin `tokenizer.json` `aeb13307…`, cùng revision) |
| Phần cứng | Laptop RTX 4050 6 GB, CPU offload, WSL2 Ubuntu. Docker Desktop dùng kho overlay2, tắt containerd (D21) |

### 6.2. Prompt

| Mục | Giá trị |
|---|---|
| `prompt_version` | `m2-w78-v11` |
| Template | `src/vgar/agents/prompts/repair_v11.txt` · `sha256:ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8` |
| Trình bày snippet | Method thụt lề được lấy thành dòng nguyên (D11) |
| Danh sách path | `path_listing = context` (D19) |

### 6.3. Budget và timeout

File `configs/m2/w9_pilot_linux.json` · `sha256:9295396838693ec0f0f9d17ea447657ae0f14fdce0c9b44b286306469744fcdf`.

| Mục | Giá trị | Nguồn |
|---|---|---|
| `input_cap` / `output_cap` / `reserved_margin` | 6000 / 1536 / 256 token | D5, D7 |
| Budget context khi repair, chung cho hai arm | B = 1500 token | D5 (đo preflight 25/10) |
| `generation_timeout` | 900 s, hết thì `GENERATION_TIMEOUT` | D7, D20 |
| `command_timeout` | 120 s | D7 |
| `global_timeout` | 1800 s, hết thì `RUN_TIMEOUT` | D7, D20 |
| Số lần sinh mỗi attempt | 1 | spec W10 §4 |

### 6.4. Retrieval bundle

File `configs/m1/w9_bundle_profile_repair.json` · `sha256:c33ba915ef010738482114ab7f13bd5273e5bd9e9286292d73038921321d96e4`. Nội dung: profile `w9-repair-node-range-issue-only-v1-b1500`, resolver `static`, BM25 `k1 = 1.2`, `b = 0.75`, `test_hint_policy = issue-only`.

Experiment config pin thêm hash của bundle profile ở dạng `vgar.repair.evidence.digest` (`sha256:325dd4d4…`), cùng hash `graph.json` của từng task.

### 6.5. Môi trường test

| Mục | Giá trị |
|---|---|
| Lệnh test theo `(repo, version)` | `configs/m1/swebench_410_test_cmds.json` · `sha256:b6551162ee88f7151ebabd1bf1eb32d6e2af15ee59d9cc588d261e14f0207312`. Django và sympy dùng runner gốc qua `native_runner.py` (D16) |
| Qualify | Pytest dùng sentinel `@pytest-sentinel` (D18); runner gốc dùng sentinel v2 (D16) |
| Container | `--network none`, image pin theo digest; symlink được inventory theo chuỗi đích (D17) |
| Static tools lock | `configs/m2/static/tools.lock.json` · `sha256:8dba9cdebe18cea025de635aa9c630117bf9a924f6109b69d7ff53a351b7e5c4` |

## 7. Oracle và cách chấm

1. **Oracle trong vòng lặp** (D4, D15): test tái hiện **viết tay từ problem statement**. Người viết không đọc gold patch, `test_patch` hay FAIL_TO_PASS/PASS_TO_PASS. Test phải FAIL trên base, chạy trong image của task. Với runner gốc, test đặt ở `tests/vgar_w9_repro_<id>/` (Django) hoặc `sympy/vgar_w9_repro_<id>/` (sympy) (D16). `fallback_scope` chỉ gồm test tái hiện (D15, D22).
2. **Resolved chính thức:** harness swebench 4.1.0 chấm **mọi** candidate đã apply, trên `applied.diff` (bản đã chuẩn hóa), không chấm raw output. Grade được ghép theo khóa `(experiment, task, variant, run_id)` (D15).
3. **Gold patch** chỉ được đọc trong `aggregate.py` và harness, sau khi run kết thúc (spec W10 §2).

## 8. Metric

### 8.1. Phễu repair, chốt trước khi chạy (spec W10 §5.9)

Mẫu số luôn là **toàn bộ population N**, kể cả task bị loại, lỗi hoặc chưa chạy.

| # | Bước | Định nghĩa |
|---|---|---|
| F1 | Sinh xong | stage generation `PASS` |
| F2 | Apply strict | `strict_apply_ok` |
| F3 | Apply sau chuẩn hóa | stage apply `PASS` |
| F4 | Sửa đúng file | file của candidate giao với file của gold khác rỗng |
| F5 | Sửa đúng hàm | `diff_to_nodes(candidate)` giao với `diff_to_nodes(gold)` khác rỗng; không map được thì ghi `unavailable` và đếm riêng |
| F6 | Test tái hiện pass | phần tests của verification `PASS` |
| F7 | Hệ thống chấp nhận | run `PASS` |
| F8 | Resolved | F7 và harness `RESOLVED` |
| — | Chẩn đoán verifier | False accept: chấp nhận nhưng `UNRESOLVED`. False reject: bị từ chối nhưng `RESOLVED` |

### 8.2. Metric khác

- **Retrieval:** Recall@3/5/10 (file, hàm), MRR, token. Báo tại budget 8000 và tại B = 1500.
- **Verification:** FAR/FRR trên patch pool có nhãn (M2-W12-2), API-break detection, structural-violation detection.
- **Cost:** `input_tokens`, `output_tokens`, `generation_ms`, `model_load_ms`, `wall_ms`, `generation_count`, VRAM peak toàn device. Đọc từ record, không parse log (M2-W10-2).
- **Subgroup:** multi-file / single-file; mypy available / `UNAVAILABLE`.
- **Metric chính:** **[MỞ] O1**.

### 8.3. Kết quả dev để tham khảo (không dùng để chốt giả thuyết)

N = 25 task mỗi arm:
- F8 = 0 ở cả ba arm.
- F4: A0 2, A1 4, A2 4.
- `GENERATION_TIMEOUT`: A0 1, A1 3, A2 4.
- Chi tiết ở `docs/status/m3.md` §6.3.

## 9. Kiểm soát công bằng và quy tắc chạy

**Fairness gate tự động** (`src/vgar/evaluation/repair/fairness.py`, M2-W10-3):
- Các arm chỉ được khác nhau ở `variant_id`, `arm`, `required_checks`.
- Giữa các experiment phải trùng nhau: model id và revision, hash tokenizer manifest, hash template prompt, toàn bộ policy (cap, timeout, runtime), hash bundle profile, và các trường chung của variant.
- Lệch thì runner từ chối và không ghi record nào.

**Định danh:** `experiment_id` là hash của config sau khi resolve (manifest, profile, variant, repair config, bundle hash, model id và revision, tokenizer, template). Đổi bất kỳ thứ gì trong đó là ra experiment mới (spec W9 §4.3).

**Quy tắc chạy:**
- Chạy tuần tự task × variant. Resume theo ledger; mỗi experiment chỉ có một process (lock của OS).
- Chỉ chạy lại khi lỗi **hạ tầng**, bằng `--rerun TASK:VARIANT --reason`. Attempt cũ được giữ (D22).
  "Hạ tầng" là cột `class = INFRA` trong `status`/`aggregate` (`src/vgar/evaluation/failure_class.py`), không phân loại tay;
  mỗi attempt ghi commit VGAR (`code`), `aggregate` cảnh báo `MIXED_CODE` khi các attempt chạy trên code khác nhau.
- `RUN_TIMEOUT` và `GENERATION_TIMEOUT` là kết cục hợp lệ về ngân sách, **không chạy lại** (D20, D26).
- Không tăng budget giữa chừng (D26).
- Hash dữ liệu do chính người chạy sinh ra phải ghi nguồn gốc. Với held-out, hash phải do **người khác người chạy** cung cấp hoặc kiểm lại (D10).
- Không đổi model, prompt, budget, manifest hay metric sau khi đã thấy kết quả held-out. Mọi thay đổi phải ghi amendment (plan, Quy ước chung).

## 10. Phân tích thống kê (W14)

- Paired bootstrap 95% CI giữa các cặp arm trên cùng task: A1 với A0, A2 với A1, A3 với A2 (M3-W14-1, tái dùng `_bootstrap` ở `retrieval/compare.py`). Ghi seed và số vòng resample.
- McNemar cho metric nhị phân theo cặp task. Phải báo số cặp lệch. Nếu bằng 0 thì ghi "không kiểm định được", không báo p-value.
- Mọi bảng sinh từ record bằng một lệnh (`scripts/make_tables.py`, M3-W14-2).

## 11. Mục phải chốt trong protocol freeze (W12)

| # | Mục | Lựa chọn hiện có | Ai chốt |
|---|---|---|---|
| O1 | **Metric chính** | (a) F8 resolved, theo plan W13–14. Dev đang 0/25, nên McNemar có nguy cơ không có cặp lệch. (b) F4/F5 định vị cùng Recall@k và FAR/FRR là chính, F8 là phụ. **Phải chốt trước khi thấy held-out** | Cả nhóm |
| O2 | **Timeout và budget** | (a) Giữ 900/1800 s và báo confound timeout ở arm graph như một threat (D26). (b) Tăng cho **mọi** arm và chạy lại dev với config mới trước freeze | Cả nhóm (ảnh hưởng compute) |
| O3 | **Config retrieval sau khi tune** | Freeze dùng config sau M1-W11-2 và sửa B10. Nếu ranking đổi thì phải chạy lại A1/A2 trên dev với đúng config đó. Ghi hash bundle profile mới | M1 đề xuất, nhóm duyệt |
| O4 | **Định nghĩa A3** | Policy `A3.json`, hai check API/structural, có re-plan hay không, N pilot | M2 đề xuất, nhóm duyệt |
| O5 | **Held-out N và compute** | Khoảng 7,4 phút/run (W10). N × 4 arm, ví dụ N = 25 là khoảng 100 run, khoảng 12,5 giờ máy, chưa tính harness và viết test tái hiện. Chốt N, cách viết test tái hiện cho held-out (ai viết, tách khỏi người chạy?) và máy chạy | Cả nhóm |
| O6 | **RQ1 và RQ3** | Cần người nhận và định nghĩa phép đo: kiểm tay edge (RQ1); impact so với baseline chỉ đọc diff, ví dụ impact có chứa file/test mà gold chạm tới không (RQ3). Nếu không làm thì ghi rõ trong Limitations | Cả nhóm |
| O7 | **Metric MCP** | Thêm invalid call rate và audit-log completeness vào M3-W12-1, hoặc ghi lý do bỏ | M3 |
| O8 | **Hash held-out** | Manifest held-out (luật §4), profile và bundle, sinh và kiểm bởi người khác người chạy (D10) | M1 sinh, M3 kiểm |
| O9 | **Ký scope** | Gộp chữ ký DoD W1–2 (scope và protocol) với chữ ký freeze | Cả nhóm |

**Khi freeze**, `docs/protocol_freeze_heldout.md` phải có đủ:
- §3–§9 của tài liệu này, với hash đã tính lại trên máy chạy;
- quyết định O1–O9;
- lệnh chạy chính xác (preflight, run, harness, aggregate);
- chữ ký M1, M2, M3 và tag `protocol-freeze`.

## 12. Threats đã biết (đưa vào Threats to Validity)

- **Năng lực model:** Qwen3-4B trên GPU 6 GB. Thất bại chủ yếu là `NO_OP` và `CONTEXT_NOT_FOUND`, nên resolved rate thấp có thể che mất khác biệt giữa các arm.
- **Confound timeout:** prompt của arm graph dài hơn (input trung bình A0 3.701, A1 4.337 token), làm timeout lệch về graph (D26).
- **Thuế trình bày:** mỗi snippet tốn khoảng 210 token metadata. Graph trả nhiều snippet nhỏ hơn, nên với cùng B, prompt graph tốn khoảng 1,8–2,5 lần B so với khoảng 1,1–1,2 lần của BM25 (D5). A0 và A1 vì vậy khác nhau ở cả yếu tố này.
- **Oracle:** test tái hiện do thành viên nhóm viết, nên có thể yếu hoặc lệch. Có hai lớp giảm thiểu: test phải FAIL trên base, và harness chính thức chấm F8.
- **Hiệu lực ngoài:** population thiên về các repo dựng được môi trường. Task Django trong mẫu là Django 3.0 (Python 3.6), nên mypy `UNAVAILABLE` (D12, D14).
- **Cỡ mẫu nhỏ:** dev N = 25 (D24).
- **Chuẩn hóa diff:** nới định dạng output (D13); luôn báo kèm F2 strict.
- **Graph:** khoảng 79% call site chưa resolve; lỗi B10 nối nhầm import; nhiễu IMPORTS ở hop 2 trong impact.
- **Provenance:** dữ liệu dev do chính M3 sinh và chạy (D10).
