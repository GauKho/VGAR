# VGAR — Graph-Augmented Reasoning cho sửa lỗi phần mềm Python

**Cập nhật: 16/10/2026 • Ngôn ngữ triển khai chính: Python.**

VGAR xây đồ thị mã nguồn để tìm context liên quan đến issue, sau đó hướng tới sinh patch và kiểm chứng patch bằng thực thi. Repository hiện chứa **M1 Graph & Retrieval, M2 baseline/evaluation và package M2 Repair & Verification tuần 7–8, cùng agent/MCP của M3**. Các thành phần có mức độ nghiệm thu khác nhau; không được hiểu “đã có file/code” là “toàn hệ thống đã hoàn thành”.

> **Đọc trước khi chạy:** M2 mới đã có **3/3 real repairs A/B/C PASS** với prompt V11/runtime r002 trên ba fixture phát triển. Bản nhúng trong VGAR đã qua **236 core tests PASS**, nhưng **chưa có ba real generations mới sau relocation** và **chưa nối M2 mới vào agent MCP/LangChain**. Full suite VGAR gần nhất là **571 PASS, 1 FAIL, 2 SKIP**, không phải toàn bộ PASS. Các số dưới đây là evidence đã lưu theo ngày/profile, không phải kết quả mới được chạy trong lần viết README này.

## Mục lục

1. [Bắt đầu từ đâu](#1-bắt-đầu-từ-đâu)
2. [Trạng thái và kết quả hiện tại](#2-trạng-thái-và-kết-quả-hiện-tại)
3. [Kiến trúc, trách nhiệm M1/M2/M3 và flow](#3-kiến-trúc-trách-nhiệm-m1m2m3-và-flow)
4. [Cấu trúc repository và vai trò các file](#4-cấu-trúc-repository-và-vai-trò-các-file)
5. [Tài liệu quan trọng nên đọc](#5-tài-liệu-quan-trọng-nên-đọc)
6. [Cài đặt một lần và chuẩn bị môi trường](#6-cài-đặt-một-lần-và-chuẩn-bị-môi-trường)
7. [Chạy M2 A/B/C đã tích hợp](#7-chạy-m2-abc-đã-tích-hợp)
8. [Tự chạy các nhóm test và lưu kết quả](#8-tự-chạy-các-nhóm-test-và-lưu-kết-quả)
9. [Sử dụng M1 graph, handoff và retrieval evaluation](#9-sử-dụng-m1-graph-handoff-và-retrieval-evaluation)
10. [Agent MCP/LangChain hiện có và cấu hình](#10-agent-mcplangchain-hiện-có-và-cấu-hình)
11. [Evidence, logs và cách đọc PASS/FAIL](#11-evidence-logs-và-cách-đọc-passfail)
12. [Giới hạn, lỗi đã biết và xử lý thường gặp](#12-giới-hạn-lỗi-đã-biết-và-xử-lý-thường-gặp)
13. [Bàn giao, tái lập và quy tắc thay đổi](#13-bàn-giao-tái-lập-và-quy-tắc-thay-đổi)

## 1. Bắt đầu từ đâu

| Bạn muốn làm gì?                         | Đi tới                                                        | Có load model/sinh patch mới không?                      |
| ---------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------- |
| Nắm tiến độ đề tài theo kế hoạch 16 tuần | [Task Status.md](<Task Status.md>) và mục 2                   | Không                                                    |
| Hiểu graph, retrieval, baseline BM25     | Mục 3, 4, 9 và docs M1/M2 W5–6                                | Không cần weights                                        |
| Kiểm prerequisite M2 trên máy hiện tại   | `run_m2_abc.ps1 -Mode Check`                                  | Không load weights/generate; có probe môi trường HF/CUDA |
| Xem lại A/B/C đã thành công              | `run_m2_abc.ps1 -Mode ReadSaved`                              | Không; chỉ audit evidence đã lưu                         |
| Sinh và kiểm chứng patch A/B/C mới       | `run_m2_abc.ps1 -Mode Run`                                    | **Có**, một generation/case, dừng khi lỗi                |
| Chạy unit/integration tests              | Mục 8                                                         | Không phải nghiệm thu real repair                        |
| Tìm file, input, patch, stdout/stderr    | Mục 4 và 11                                                   | Không                                                    |
| Nối M2 mới vào MCP/LangChain             | Đọc tài liệu bàn giao; đây là phần tích hợp **chưa hoàn tất** | Không có lệnh README nào tự hoàn thành việc này          |

**Trên máy đã setup và giữ đúng profile hiện tại**, kiểm trước bằng:

```powershell
# Không cài lại, không generate. Mặc định của root launcher cũng là Check.
powershell -NoProfile -ExecutionPolicy Bypass -File 'D:\Project\CAPSTONES\VGAR\run_m2_abc.ps1' -Mode Check
# Đọc ngay exit code: 0 chỉ là prerequisite/profile đã qua, chưa phải repair PASS.
$LASTEXITCODE
```

**Máy mới/clone mới:** bắt đầu mục 6, không dùng ngay lệnh trên rồi kỳ vọng tự có weights, environment và evidence. Tài nguyên local hiện có không đồng nghĩa đã được commit/push lên GitHub.

## 2. Trạng thái và kết quả hiện tại

### 2.1. Phạm vi và nguồn code

- Nguồn remote: [GauKho/VGAR](https://github.com/GauKho/VGAR).
- Checkout local đang được mô tả: `D:\Project\CAPSTONES\VGAR`.
- Branch local: `integration/main-m1-w5-w6-20261013`; HEAD `b8e2461635b81d1ae790445efea5c9757d91700a`.
- Đã tích hợp main → M1 W5–6 → M1 W7–8; M2 W5–6 có diff local, M2 W7–8 là package nhúng có receipt riêng.
- README phản ánh **working tree hiện tại**, bao gồm nội dung chưa commit. Không giả định checkout remote hiện chứa mọi file/evidence liệt kê ở đây.
- Snapshot xuất bản nhánh riêng, exclusions và lưu ý source pin khi clone: [PUBLICATION_2026-10-16.md](docs/handoff/PUBLICATION_2026-10-16.md). `.gitattributes` giữ nguyên bytes của package/evidence và shared boundary đã khóa hash.
- Kế hoạch chính: `D:\Project\CAPSTONES\New_task\project_plan_16_weeks.md`, **nằm ngoài repository**. Các kế hoạch P0–P5 lịch sử không tự được kích hoạt lại.

### 2.2. Bảng tóm tắt task hiện tại

Quy ước của [Task Status](<Task Status.md>): **HT** hoàn thành trong phạm vi nêu rõ; **MP** hoàn thành một phần; **CT** chưa triển khai; **CX** chưa xác minh/thiếu evidence. Đây không phải phần trăm chất lượng đồ án.

| Nhóm việc                            | Đã có/đã chứng minh                                                                          | Còn thiếu hoặc giới hạn                                                             |
| ------------------------------------ | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| M1 W3–4: graph Python/SQLite         | Tree-sitter, static bindings, DTO, graph store/query, tests                                  | Static resolution có giới hạn; không coi tests giả lập là nghiệm thu mọi resolver   |
| M2 W3–4: baseline và evidence        | Private workspace, pytest wrapper, baseline command/stdout/stderr/exit/duration, JSON writer | Baseline runner **không tự sửa lỗi**; Native không phải sandbox OS                  |
| M3 W3–6: MCP và client               | Graph/repository/execution servers, client, tool audit, agent/workflow                       | Còn findings legacy trong Task Status; không suy an toàn hệ thống từ một smoke PASS |
| M1 W5–6: grounding/retrieval         | Task anchors, graph context, token budget, static/SCIP/LSP adapters                          | Ranking improvement và profile resolver cần evidence tương ứng                      |
| M2 W5–6: BM25, gold extraction       | BM25 function/code chunks, gold-file/function từ developer patch                             | Gold là changed-code proxy, không phải tập lời giải đúng duy nhất                   |
| M2 W5–6: retrieval evaluation        | 25 attempted, **22 valid pairs**, đạt gate ≥20 đã duyệt                                      | Graph có **3 SymPy timeout**; không phải 25/25 Graph PASS                           |
| M2 W5–6: phối hợp mapping M1         | Guards identity/range, diagnostics, consumer proof, hồ sơ bàn giao                           | `W05-06-M2-04` còn **MP**, đợi chủ task M1 review/sign-off                          |
| M1 W7–8: context/handoff/tests links | Payload/manifest/consumer, source binding, ba handoff bundles                                | Không đồng nhất link suy luận với coverage thực đo; ranking còn MP                  |
| M2 W7–8: **7/7 task M2 HT**          | Prompt cố định, HF backend, diff parser/apply, test selection, pytest/type/lint, evidence    | HT **trên trusted-fixture prototype**, không phải toàn SWE-bench                    |
| M2 W7–8: A/B/C cùng profile          | **3 real cases PASS**, V11/r002 ngày 15/10                                                   | Bản layout `r002-vgar-i001` chưa chạy lại ba generations thật                       |
| Package M2 vào VGAR                  | Copy đầy đủ có hashes, launcher, 236 core tests, 7 integration tests                         | Chưa nối vào MCP/LangChain; còn cần tái lập trên máy đồng đội                       |
| M3 W7–8: vòng agent dùng M2 mới      | Agent cũ và package M2 cùng tồn tại                                                          | Chưa có adapter MCP cho flow M2 mới; common integrated flow vẫn MP                  |
| Tuần 9–16                            | Có thiết kế và một số thành phần nền/lịch sử                                                 | Chưa được nghiệm thu impact/ablation/held-out/final artifact chỉ từ ba prototype    |

Toàn bộ **150 task IDs**: **47 HT / 48 MP / 25 CT / 30 CX**. Riêng tuần 7–8: **10 HT / 8 MP / 0 CT / 1 CX**. Các mục chung/M1/M2/M3/DoD có giao nhau; **không cộng hoặc quy đổi thành “đã xong 31% hệ thống”**. Xem từng ID/nguyên nhân/giải pháp trong Task Status.

### 2.3. Kết quả kiểm thử đã lưu

| Evidence/profile                            | Kết quả                                  | Diễn giải                                                              |
| ------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------- |
| M1 handoff tích hợp 14/10                   | 434 PASS, 1 SKIP; handoff demo 3/3       | M1/contract tests và handoff, không phải LLM sửa code                  |
| Full M2 bản nhúng 16/10                     | **236 PASS**, 129,27 giây pytest         | Core/unit/integration của package M2                                   |
| Root launcher/auditor tests 16/10           | **7 PASS**, 8,98 giây                    | Gồm path tương đối và kiểm từ chối tampering                           |
| Fake A/B/C sau relocation                   | **3/3 PASS**                             | Patch tham chiếu có sẵn; kiểm pipeline, **không tính real generation** |
| Check / ReadSaved sau relocation            | PASS / **3/3 saved real audits PASS**    | Prerequisite / audit lại lịch sử, không sinh patch mới                 |
| Full VGAR 16/10                             | **571 PASS, 1 FAIL, 2 SKIP**, 81,14 giây | Lỗi HF legacy `KeyError: generation_config` đã tồn tại trước tích hợp  |
| Ruff E9,F và PowerShell AST tại integration | PASS                                     | Theo đúng phạm vi kiểm đã ghi, không tuyên bố mọi lint rule đều PASS   |

Các suite/lượt có thể chồng lấn, **không cộng các hàng thành tổng số tests duy nhất**. Nguồn và paths đầy đủ: [báo cáo tích hợp M2](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md).

### 2.4. Kết quả real repair A/B/C — V11/r002, 15/10/2026

| Case                     | Nhiệm vụ/file thực sự thay đổi                                          | Baseline → post                                  | Pipeline / stage generation | Input / output tokens |
| ------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------ | --------------------------- | --------------------- |
| A — `single_file_login`  | Sửa xử lý login trong `auth.py`                                         | 1 required FAIL + 1 regression PASS → **2 PASS** | 68,828s / 53,250s           | 1.299 / 43            |
| B — `multi_file_invoice` | Sửa **cả `pricing.py` và `invoice.py`**                                 | 2 required FAIL + 1 regression PASS → **3 PASS** | 157,282s / 142,406s         | 1.769 / 157           |
| C — `missing_links`      | Sửa `formatter.py`; thiếu links nên collection/fallback tests chạy thật | 1 required FAIL + 1 regression PASS → **2 PASS** | 64,031s / 51,250s           | 1.169 / 43            |

**Baseline FAIL là lỗi được tái hiện trước khi sửa, không phải kết quả cuối bị FAIL.** Cả ba final audits PASS; source snapshots gốc giữ nguyên. Tổng pipeline 290,141s; tổng stage generation 246,906s. Stage generation gồm overhead worker/load/IO; không đồng nhất với timer riêng bên trong model.

Nguồn: [run_manifest.json](M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json). Người dùng đã chạy lại `Mode=Run` cùng máy và đạt 3/3, workflow khoảng 429,152s, tại [summary.json](M2_week_7_8/results/manual_abc/20261015T114826234Z-922d5c80/summary.json). Đây **chưa phải đồng đội độc lập/clean-machine acceptance**.

### 2.5. Kết quả retrieval — M2 W5–6, 13/10/2026

Hai arm dùng chung 25 dev tasks; BM25 25/25 thành công, Graph 22/25 thành công. Bảng dưới chỉ so **cùng 22 valid pairs**, không so mean của hai population khác nhau:

| Metric                        | BM25 full rank | Graph issue-only |   N |
| ----------------------------- | -------------: | ---------------: | --: |
| File Recall@5                 |       0,537879 |         0,446970 |  22 |
| Function Recall@5             |       0,274621 |         0,315239 |  22 |
| File MRR                      |       0,578182 |         0,605395 |  22 |
| Function MRR                  |       0,428167 |         0,418428 |  22 |
| Packed gold-function coverage |       0,445921 |         0,413724 |  22 |
| Mean packed tokens            |      7.997,909 |        7.966,545 |  22 |

- **Recall@5:** tỷ lệ gold files/functions của từng task tìm thấy trong top 5 sau dedup, rồi lấy macro mean.
- **MRR:** trung bình nghịch đảo vị trí gold hit đầu tiên; miss góp 0, denominator theo eligible tasks.
- **Packed coverage:** gold xuất hiện trong context thực đóng gói dưới budget 8.000 tokens; khác phép đo full ranking.
- Function gold lấy từ patch/source mapping; không đủ nhãn thì giữ ineligible/diagnostics, không tùy ý tính 0.
- Hai CI 95% của delta Recall@5 đều chứa 0: **chưa chứng minh Graph tốt hơn BM25 tổng quát**.
- `sympy__sympy-16597`, `sympy__sympy-17318`, `sympy__sympy-20438` timeout 300s/task. Biết vượt deadline; chưa có profiling đủ để quy cho RAM/Jedi hay một phase cụ thể.
- Đây là retrieval evaluation **không gọi LLM, không apply patch, không chạy SWE-bench harness**, không phải resolved rate.

Đọc [báo cáo M2 W5–6](docs/handoff/m2-w5-w6/COMPLETION_REPORT.md) và [REPORT so sánh](results/retrieval/20261013T125307312086Z-6d6b0b52b105/REPORT.md). Profile được đo trước HEAD hiện tại; không coi đây là benchmark vừa đo lại cho mọi code mới.

## 3. Kiến trúc, trách nhiệm M1/M2/M3 và flow

### 3.1. Trách nhiệm các thành phần

| Vai trò                          | Chịu trách nhiệm chính                                                                                  | Nơi triển khai                                                                      |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **M1 — Graph & Retrieval**       | Parse Python, graph/store, task anchors, context, tokenizer manifest, test links và handoff             | `src/vgar/graph/`, DTO/consumer trong `src/vgar/contracts/`                         |
| **M2 — Repair & Verification**   | Baseline/tests/evidence W3–4; BM25/gold/metrics W5–6; prompt/generation/diff/worktree/verification W7–8 | `src/vgar/repair/`, `src/vgar/evaluation/retrieval/`, `M2_week_7_8/`                |
| **M3 — MCP, Evaluation & Paper** | MCP servers/client, orchestration, protocol/experiment/report, kết nối agent tới tools                  | `src/vgar/mcp/`, `src/vgar/agents/`, `src/vgar/cli.py`; integration mới còn cần nối |

### 3.2. Hai luồng đang tồn tại — không được gộp nhầm

```text
LUỒNG 1: M2 TUẦN 7–8 ĐÃ NGHIỆM THU PROTOTYPE
M1 frozen handoff + source snapshot + task.json
  → M2 validate identity/source/tokenizer
  → private worktree + chạy baseline
  → prompt V11 + 1 HF/Qwen generation
  → strict unified-diff parser → exact binding → Git check/apply
  → actual changed paths → M1 test-selection diagnostics
  → collection + required/regression pytest + syntax/mypy/Ruff
  → source integrity + cleanup → canonical JSON/EvidenceBundle + audit

LUỒNG 2: AGENT/MCP CỦA VGAR HIỆN CÓ
CLI run/solve/chat → LangChain/LangGraph agent → MCP client (stdio)
  ├─ graph server → graph/retrieval/SQLite
  ├─ repository server → read_file / apply_patch (exact-edit cũ)
  └─ execution server → run_pytest (runner cũ)
             ╳ chưa nối sang engine M2 mới ở luồng 1
```

Luồng 1 dùng source/consumer/counter của M1 trong chính VGAR, nhưng **`mcp_calls=[]`**: không có MCP call. Luồng 2 có LangChain/LangGraph/MCP, nhưng không vì vậy đã dùng V11 hay verifier mới.

### 3.3. M1 được M2 kế thừa như thế nào?

M1 tạo `context.json`, `context_manifest.json`, `test_links.json` và `repair-context.txt`. Consumer M1 kiểm repo/task identity, graph version, source ranges/hash và tokenizer provenance. M2 dùng snippets đúng bytes, rồi thêm metadata trình bày như quyền sửa, vị trí/count hunk, không tự thêm source hoặc đưa gold patch vào real prompt.

Test links của M1 là **candidates**, không phải kết quả chạy tests. M2 phải collection thật, xác nhận node IDs tồn tại; thiếu links thì dùng fallback `tests` có scope đã duyệt, không đổi “không tìm được test” thành PASS.

### 3.4. Prompt và model thực tế

- Final template: [repair_v11.txt](M2_week_7_8/prompts/repair_v11.txt), version `m2-w78-v11`, SHA256 `ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8`.
- Yêu cầu chỉ unified diff, chỉ production paths được phép, giữ signatures/indentation; replacement hunk dùng source coordinates và counts riêng. Ví dụ trung tính, không phải lời giải A/B/C.
- [prompt.py](M2_week_7_8/src/vgar_m2_w78/prompt.py) ghép instruction/issue/context, tính full-chat budget; host không recount/sửa output thay model.
- Model prototype: **`Qwen/Qwen3-4B-Instruct-2507`**, model/tokenizer revision **`cdbee75f17c01a7cc42f958dc650907174af0554`**, greedy, FP16, `device_map=auto`. Có thể offload CPU; không khẳng định toàn model nằm GPU.
- Input cap **6.000**, output cap **1.536**, reserve **256** tokens; generation **900s**, command **120s**, global **1.800s/run**.
- `config/demo.json` vẫn giữ default V2 cho lịch sử. **Final launcher chủ động chọn V11**; bare `run_demo.py --mode real` không tương đương final profile.
- Đây không phải fine-tuned model, không chứng minh mô hình planner/coder kép hay benchmark Qwen32B. Có dependencies training không có nghĩa repo đã fine-tune xong.

## 4. Cấu trúc repository và vai trò các file

### 4.1. Bản đồ thư mục

```text
VGAR/
├── README.md                    Tài liệu vào cửa này
├── requirement.txt              Dependencies môi trường root (không phải M2 core)
├── pyproject.toml               Metadata package vgar-mcp, CLI, pytest config
├── .env.example                 Mẫu cấu hình agent legacy, không chứa secret thật
├── .gitignore                   Loại local env, data, results, logs, runtimes
├── Task Status.md               Checklist 150 task IDs, evidence, blockers
├── PROGRESS.md                  Checkpoint qua các phiên làm việc
├── run_m2_abc.ps1                Root launcher M2: Check / ReadSaved / Run
├── src/vgar/                    M1 + M2 tuần cũ/evaluation + M3 agent/MCP
├── tests/                       Tests cấp VGAR; fixtures không tự collection
├── scripts/                     CLI tiện ích graph/eval/MCP/baseline/audit
├── configs/                     Node dependency locks, mẫu handoff target
├── docs/                        Contracts, method, design, handoff, audit, plans
├── artifacts/                   Graph fixtures, tokenizer/graph/handoff/evidence
├── data/                        Dataset/cache/source archives/manifest/gold (local)
├── results/retrieval/           Kết quả retrieval theo run ID (local)
├── logs/                        MCP audit/debug/runtime logs (local)
├── M2_week_7_8/                 Package repair mới, namespace vgar_m2_w78
│   ├── src/vgar_m2_w78/         Repair engine/verification/evidence
│   ├── config/                 Policy, model paths, reference source pin
│   ├── prompts/                Templates V1–V11 và lịch sử prompt
│   ├── examples/               Task configs, source snapshots, M1 bundles
│   ├── tests/                  Unit/regression tests + reference patches
│   ├── scripts/                Entry points chạy/record/campaign
│   ├── docs/                   Ba tài liệu bàn giao/báo cáo/lệnh chi tiết
│   ├── integration/            Relocation receipt và original bytes sáu file
│   ├── results/                Full lịch sử repair/qualification + runs mới
│   ├── test_abc_v11_r002.ps1    Runner A/B/C bên trong (default Run!)
│   ├── requirement.txt         Exact core pins, hướng dẫn HF riêng
│   ├── pyproject.toml          Package riêng vgar-m2-w78
│   └── .venv/, .workspaces/    Local env/workspaces; không phải portable source
└── .venv-m2-w5-w6/              Eval environment local, không bắt buộc có khi clone
```

`.git/` là Git metadata; `.claude/` và `.superpowers/` là cấu hình/checkpoint công cụ hỗ trợ phát triển, **không phải dependency chạy hệ thống**. Các `__pycache__`/`.ruff_cache`/`.mypy_cache` là caches, không phải kết quả nghiên cứu.

### 4.2. Source cấp VGAR

| Thư mục/file                                                           | Chức năng                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [contracts/](src/vgar/contracts/)                                      | `graph.py` node/edge; `context.py` payload; `handoff.py` manifest/target; `consumer.py` validate handoff; `prompt_context.py` render; `repair.py`/`evidence.py` test/evidence DTOs; `schema.py`/`error.py` contract helpers                                                                                                    |
| [graph/](src/vgar/graph/)                                              | `builder.py` parse/extract/static bindings; `sqlite_store.py` lưu; `sqlite_service.py` truy vấn; `demo_service.py`/`factory.py`/`port.py` backend interface                                                                                                                                                                    |
| Graph grounding/retrieval                                              | `grounding.py`, `task_overlay.py` nối issue/anchors; `retrieval.py` traverse/rank/pack; `token_counter.py` kiểm local tokenizer; `handoff.py` export bundle; `test_selection.py` suy test candidates                                                                                                                           |
| Graph enrichers/diagnostics                                            | `scip_resolver.py`/`scip_profile.py`/`scip_wire.py`, `lsp_resolver.py`, `source_evidence.py`, `method_aliases.py`, `return_contracts.py`, `visualization.py`                                                                                                                                                                   |
| [repair/](src/vgar/repair/)                                            | `workspace.py` copy/fingerprint; `test_runner.py` pytest/JUnit wrapper; `baseline.py` orchestration baseline; `evidence_writer.py` writer. **Không phải unified-diff engine M2 mới**                                                                                                                                           |
| [evaluation/retrieval/](src/vgar/evaluation/retrieval/)                | `dataset.py` pin/data; `chunks.py` corpus; `bm25.py` baseline; `gold_labels.py` patch labels; `m1_adapter.py`/`graph_arm.py` bridge Graph; `scoring.py`/`metrics.py` scoring; `compare.py` paired guards; `report.py` report; `evidence.py` command recording; `evaluation.py` điều phối; `resolver_comparison.py` so resolver |
| [agents/](src/vgar/agents/)                                            | `core.py` agent/tools; `runtime.py` build/index; `workflow.py` graph orchestration; `state.py`/`routes.py` state/transitions; `nodes/` prepare/repair/verify/finalize; `prompts/` instruction legacy                                                                                                                           |
| [mcp/](src/vgar/mcp/)                                                  | `client.py` stdio clients; `servers/` ba servers; `registry.py`/`tooling.py` tool requirements/budget; `audit.py` log; `schemas.py`/`result_parser.py` response parsing                                                                                                                                                        |
| [models/](src/vgar/models/)                                            | Factory/config/base và `huggingface/` local tool-calling model của agent cũ; khác HF worker M2                                                                                                                                                                                                                                 |
| [config/](src/vgar/config/), [observability/](src/vgar/observability/) | Settings/env/logging; phase instrumentation/graph trace                                                                                                                                                                                                                                                                        |
| [cli.py](src/vgar/cli.py)                                              | `vgar doctor/tools/index/run/solve/chat`; `vgar` entrypoint từ package root                                                                                                                                                                                                                                                    |

**Jedi:** không phải resolver bắt buộc hiện tại. Default là **static** (Tree-sitter + Python bindings); **SCIP/Pyright LSP là enrichment tùy chọn**. Không đúng nếu nói mọi lượt Graph hiện đều chạy SCIP hoặc đã bỏ static.

### 4.3. Bên trong M2 tuần 7–8

| Module/nhóm                                                              | Vai trò                                                                                                               |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| `bootstrap.py`, `config.py`, `contracts.py`                              | Reference/source pin, load policy/profile và validated task/artifact contracts                                        |
| `context_adapter.py`, `context_presentation.py`, `prompt.py`             | Nhận/validate M1 context, trình bày permission/range/counts, render template và full-chat budgeting                   |
| `generator.py`, `local_chat.py`                                          | Fake generator cho self-test và local chat tokenizer; fake không được tính real                                       |
| `generator_hf.py`, `hf_backend.py`, `hf_worker.py`, `model_worker.py`    | RPC/process HF riêng, tokenize/generate, timeout/ownership; core env không phải HF env                                |
| `hf_diagnostics.py`, `diagnostics.py`                                    | Effective generation config, mask/device/token diagnostics, parser detail, Python traceback                           |
| `patch.py`, `workspace.py`                                               | Strict modify-only diff parser, source binding/preflight/apply/byte attestation; private worktree, protection/cleanup |
| `executor.py`, `test_runner.py`, `pytest_plugin.py`, `test_selection.py` | Bounded command, real collection/outcomes, required/regression selection và fallback                                  |
| `checks.py`, `verification.py`                                           | Syntax/mypy/Ruff, aggregate verdict; không gán PASS cho check chưa chạy                                               |
| `pipeline.py`, `evidence.py`, `cli.py`                                   | Luồng một lượt, durable artifacts/canonical JSON, CLI                                                                 |
| `campaign.py`, `adaptive_campaign.py`                                    | Campaign/revision/attempt và strict record assessor                                                                   |
| `b_inputs.py`, `b_experiment.py`, `b_acceptance.py`                      | Frozen B inputs, runtime fingerprints/quota/resume và B-specific acceptance; lịch sử phát triển không được reset      |

**Inputs A/B/C ở bản nhúng:**

| Input                     | Đường dẫn theo repo                                                                    | Dùng để làm gì?                                       |
| ------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Task/issue và selectors   | `M2_week_7_8/examples/tasks/{single_file_login,multi_file_invoice,missing_links}.json` | Xác định case/source/bundle/failing tests             |
| Source gốc trước sửa      | `M2_week_7_8/examples/snapshots/<task_id>/`                                            | Tạo seed/private worktree, giữ nguyên bug để tái hiện |
| M1 context/manifest/links | `M2_week_7_8/examples/handoffs/<task_id>/`                                             | Context đã source-bound + provenance/test candidates  |
| Provenance input          | `M2_week_7_8/examples/inputs_receipt.json`                                             | Nguồn handoff, hashes và thông tin chuẩn bị           |
| Reference patches         | `M2_week_7_8/tests/fixtures/reference_patches/`                                        | Fake tests/guards, **không feed vào real model**      |
| Source pin/profile        | `M2_week_7_8/config/{source_pin,demo}.json`                                            | Khóa shared VGAR boundary, model paths và budgets     |

Ba case lấy từ fixture/handoff M1, nguồn [cases.json](tests/fixtures/w7_w8_handoff/cases.json), **không phải ba SWE-bench tasks**.

### 4.4. Scripts — chọn đúng mục đích

| Nhóm scripts root                                                                                    | Mục đích                                                                                     |
| ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `build_graph.py`, `load_graph_fixture.py`, `visualize_graph.py`                                      | Build graph JSON, load SQLite, visualize; dùng output mới, không ghi đè fixture              |
| `find_task_anchors.py`, `build_task_overlay.py`, `get_related_context.py`                            | Ground task và retrieve context độc lập                                                      |
| `provision_m1_tokenizer.py`, `accept_m1_tokenizer.py`                                                | Tải tokenizer đúng SHA, tạo/kiểm manifest; không tải model weights                           |
| `install_scip_runtime.ps1`, `install_lsp_runtime.ps1`, `scip_windows_compat.cjs`                     | Node runtime theo lockfile và compatibility shim Windows                                     |
| `export_m1_handoff.py`, `consume_m1_handoff.py`, `demo_w7_w8_handoff.py`                             | Export/validate/review handoff; không tự là repair                                           |
| `prepare_manifest.py`, `run_bm25_retrieval.py`, `run_graph_retrieval.py`, `compare_graph_vs_bm25.py` | Dataset manifest → retrieval arms → paired report                                            |
| `compare_static_vs_scip.py`, `smoke_w5_w6_resolvers.py`                                              | So/kiểm resolver profile, không tự thay kết quả static đã lưu                                |
| `run_m2_baseline.py`, `record_m2_test.py`                                                            | Baseline repo tin cậy / ghi pytest JSON; baseline không có generation                        |
| `run_m1_tests.py`, `smoke_real_repo_graph.py`, `smoke_w7_w8_m1.py`, `smoke_w5_w6_retrieval.py`       | Tests/smoke M1, tokenizer/context/retrieval                                                  |
| `smoke_mcp.py`, `smoke_w3_w4.py`, `smoke_w3_w4_full.py`                                              | MCP/tools/resources hoặc scripted integration; có known resource finding, không cam kết xanh |
| `run_agent.py`, `smoke_workflow.py`, `smoke_w3_w4_agent.py`, `smoke_w3_w4_repair_loop.py`            | Agent/workflow legacy; khác package M2 mới                                                   |
| `smoke_model.py`, `smoke_hf_agent.py`                                                                | Model/agent invocation smoke; “OK” không chứng minh sửa code                                 |
| `package_m1.py`                                                                                      | Đóng gói scope M1; **không bao gồm toàn bộ package/evidence M2 nhúng**                       |
| `check_m2_integration.py`                                                                            | So preservation snapshot integration; document drift sau snapshot cũng có thể bị báo         |

Scripts trong M2: `run_demo.py` chạy một case fake/real; `record_tests.py` ghi self-tests; `qualify_model.py` kiểm profile; `prepare_inputs.py` chuẩn bị input có hashes; `run_acceptance.py`/`run_adaptive_acceptance.py`/`run_b_experiment.py` điều phối các campaign lịch sử; `summarize_runs.py` tổng hợp. **Không init/reset campaign cũ hoặc chạy lại prepare_inputs chỉ để xem kết quả.** Dùng root launcher cho final A/B/C.

## 5. Tài liệu quan trọng nên đọc

| Tài liệu                                                                                                                                                                  | Khi nào dùng?                                                                               |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| [Task Status.md](<Task Status.md>)                                                                                                                                        | Nguồn tổng hợp 150 task IDs, evidence, lỗi và việc còn thiếu theo plan16W                   |
| [PROGRESS.md](PROGRESS.md)                                                                                                                                                | Resume đúng checkpoint, tránh làm lại hoặc đụng dirty code                                  |
| [M2 integration handoff 16/10](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md)                                                                                           | Nguồn ưu tiên về **layout/path mới** và qualification bản nhúng                             |
| [M1 integration handoff 14/10](docs/handoff/M1_W7_W8_INTEGRATION_2026-10-14.md)                                                                                           | Nguồn M1 tích hợp, commit, fixtures/contracts và giới hạn                                   |
| [M2 W5–6 completion](docs/handoff/m2-w5-w6/COMPLETION_REPORT.md), [context/gold handoff](docs/handoff/m2-w5-w6/CONTEXT_GOLD_HANDOFF.md)                                   | Metrics/protocol/evidence, lỗi range/identity đã sửa, M1-owner pending                      |
| [M2 W5–6 unfinished](docs/handoff/m2-w5-w6/UNFINISHED_TASKS.md), [ledger](docs/handoff/m2-w5-w6/EXECUTION_LEDGER.md), [protocol](docs/handoff/m2-w5-w6/PROTOCOL.md)       | Biết failed methods/timeouts và fair comparison, không thử lại mù                           |
| [Graph schema](docs/graph_schema.md), [context contract](docs/context_payload_contract.md), [retrieval design](docs/retrieval_design.md)                                  | Hiểu node/edge/payload/ranking/budget                                                       |
| [M1 method](docs/m1_retrieval_method.md), [tokenizer acceptance](docs/m1_tokenizer_acceptance.md), [M1 docs index](docs/m1_documents.md)                                  | Profile/provenance/token counting và tài liệu M1                                            |
| [MCP contract](docs/mcp_tool_contract.md), [M3 boundary](docs/m3_system_boundary.md), [agent state](docs/agent_state.md)                                                  | Kết nối tools/state, phân biệt thiết kế với implementation thật                             |
| [Verification design](docs/verification_design.md), [evidence schema](docs/evidence_bundle_schema.md), [M2 W3–4 guide](docs/GIAI_THICH_VGAR_M2_W3_W4_VA_CACH_KIEM_THU.md) | Baseline/test wrapper/evidence thế hệ trước                                                 |
| [Model backend](docs/model_backend.md)                                                                                                                                    | Backend của agent legacy, không phải profile HF worker M2 mới                               |
| [Integration plan](docs/superpowers/plans/2026-10-16-integrate-m2-w7-w8-standalone.md), [audit artifacts](docs/audit/)                                                    | Phạm vi được duyệt, backups, command receipts và provenance; không là lệnh tự động mở scope |

**Năm file bàn giao M2 cần biết:**

1. [01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md](M2_week_7_8/docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md): M1/M3 đọc để hiểu input/output, kết quả có số liệu, contract và phần việc phải nối tiếp.
2. [02_BAO_CAO_TOAN_BO_M2_W7_W8.md](M2_week_7_8/docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md): giải thích task, cách triển khai, V11, flow, failures, inventory từng file/thư mục; là báo cáo chi tiết, dài hơn README.
3. [03_LENH_POWERSHELL_A_B_C_V11_R002.md](M2_week_7_8/docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md): giải thích commands/logs A/B/C. Có paths của bản standalone lịch sử; **trong VGAR ưu tiên mục 6–8 của README này và integration handoff**.
4. [M2 requirement.txt](M2_week_7_8/requirement.txt): cài core pins vào môi trường riêng, không cài lẫn root requirements.
5. [test_abc_v11_r002.ps1](M2_week_7_8/test_abc_v11_r002.ps1): runner bên trong. Dùng [run_m2_abc.ps1](run_m2_abc.ps1) ở root để mặc định an toàn Check, không vô tình generate.

Nếu tài liệu lịch sử khác path/status hiện tại: đối chiếu code, receipt mới và ngày/profile; **không sửa manifests/evidence cũ để chúng có vẻ được tạo dưới layout mới**.

## 6. Cài đặt một lần và chuẩn bị môi trường

### 6.1. Những gì cần cài ngoài pip

| Thành phần                      | Cần khi nào?                   | Ghi chú                                                                        |
| ------------------------------- | ------------------------------ | ------------------------------------------------------------------------------ |
| Python x64                      | Mọi luồng                      | Metadata cho phép ≥3.11,<3.14; **profile M2 đã đo dùng 3.11.6**                |
| Git                             | Clone và M2 worktree/apply     | Cần có trên PATH                                                               |
| Windows PowerShell 5.1          | Các runner `.ps1` hiện tại     | Root runner gọi Windows `powershell.exe`; chưa nghiệm thu Linux/PS7            |
| NVIDIA GPU + driver phù hợp     | Real M2 profile CUDA           | Máy đã đo là RTX 4050 Laptop; CPU-only không phải profile đã nghiệm thu        |
| Node.js + npm                   | **Tùy chọn**, SCIP/Pyright LSP | Không cần cho default static/BM25; version Node phải tương thích packages lock |
| Qwen weights + tokenizer assets | Real M2 / manifest counting    | Không được cài bằng root requirements; tải/provision riêng, khóa hashes        |
| Dung lượng đĩa/RAM              | Data/model/evidence            | Không chỉ tính file source; CPU offload/cache có thể tăng RAM/time             |

SQLite dùng `sqlite3` của Python, không `pip install sqlite3`. **Không cần Docker, Ollama hay W&B cho ba Native A/B/C hiện tại.** Việc chúng có trong hướng nghiên cứu trước không biến thành prerequisites luồng này.

### 6.2. Tách môi trường để tránh xung đột

| Môi trường                                | Mục đích                                          | Nguồn dependencies                                                   |
| ----------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------- |
| `.venv-vgar` — gợi ý tạo mới              | Root VGAR, agent/MCP, root tests, đầy đủ metadata | [requirement.txt](requirement.txt), sau đó editable install root     |
| `.venv-m1` — tùy chọn, thay cho full root | Chỉ graph/handoff/M1 tests, không model stack     | `scripts/requirements_m1.txt`; chủ động `PYTHONPATH=src`             |
| `M2_week_7_8/.venv`                       | Core M2, pytest/mypy/Ruff và orchestration        | **`M2_week_7_8/requirement.txt`**                                    |
| HF worker riêng                           | Load Qwen/tokenize full chat/generate trên CUDA   | Năm pins HF ở mục 6.4; **tokenizers 0.22.2**, không trộn core 0.22.1 |

Không cần tạo cả `.venv-vgar` lẫn `.venv-m1` nếu chỉ dùng một đường. Environment `.venv-m2-w5-w6` local dùng cho evidence retrieval trước đây (Python 3.13.0), không phải M2 W7–8 đã qualify.

**Root requirement.txt** phản ánh toàn bộ dependencies/optional dev+plot hiện khai báo trong [pyproject.toml](pyproject.toml); không phải lockfile transitive. Nó bao gồm PEFT/TRL vì metadata root đang yêu cầu, dù workflow A/B/C không fine-tune. Clean install đầy đủ **chưa được nghiệm thu** trong lần viết tài liệu này. Environment root đã dùng kiểm thử có PyArrow 25.0.1, khác khai báo 23.0.1; không gọi nó là bản tái lập exact của requirement mới.

### 6.3. Cài root VGAR — chỉ lần đầu trên môi trường mới

Các lệnh trong README dùng PowerShell terminal của VS Code. Thay đường dẫn ở `Set-Location` nếu máy khác. Không tạo đè env đang có.

```powershell
# MỖI TERMINAL: vào đúng repo, dùng UTF-8; không cần activate venv.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# CHỈ KIỂM TRA: kỳ vọng thấy phiên bản Git và Python 3.11 đã cài.
git --version
py -3.11 --version

# CHỈ LẦN ĐẦU: tạo môi trường root riêng, tuyệt đối không cài vào M2 core.
if (-not (Test-Path -LiteralPath '.\.venv-vgar\Scripts\python.exe')) {
    py -3.11 -m venv .venv-vgar
    if ($LASTEXITCODE -ne 0) { throw 'Không tạo được root venv.' }
}

# MỖI TERMINAL: gán absolute interpreter; không phụ thuộc prompt (.venv).
$vgarPython = (Resolve-Path '.\.venv-vgar\Scripts\python.exe').Path

# CHỈ LẦN ĐẦU/KHI DEPENDENCIES ĐƯỢC DUYỆT THAY ĐỔI: có tải packages, có thể lâu.
& $vgarPython -m pip install -r .\requirement.txt
if ($LASTEXITCODE -ne 0) { throw 'Cài dependencies thất bại; giữ log và dừng.' }

# CHỈ LẦN ĐẦU: đăng ký package/CLI, không resolve lại dependencies.
& $vgarPython -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable install thất bại.' }

# KIỂM TRA SAU CÀI: không tải weights, không chạy agent.
& $vgarPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency conflicts; không tiếp tục như đã cài thành công.' }
& $vgarPython -m vgar.cli doctor
```

File `requirement.txt` **không chọn CUDA build thay bạn**. CPU Torch vẫn có thể cài thành công; `torch.cuda.is_available()` mới kiểm được CUDA ở environment đó. Không thay Torch của môi trường đã qualify chỉ để làm root env giống nó.

**Mỗi lần mở terminal sau này chỉ cần** vào repo, đặt UTF-8 và gán lại `$vgarPython`/`$core` tương ứng. Không chạy lại `venv`/`pip install`/`npm ci`/provision nếu profile không đổi.

### 6.4. M2 trên máy hiện tại và máy mới

**Máy hiện tại:** core env/weights/HF env/tokenizer đã có. Dùng Check → ReadSaved → Run, **không cài lại**.

**Máy mới:** có thể chuẩn bị core như sau, nhưng đây **chưa phải lệnh tự động dựng toàn profile nghiệm thu**:

```powershell
# CHỈ LẦN ĐẦU: đứng ở VGAR; tạo core M2 nếu chưa có, không tái sử dụng venv copy từ máy khác.
if (-not (Test-Path -LiteralPath '.\M2_week_7_8\.venv\Scripts\python.exe')) {
    py -3.11 -m venv .\M2_week_7_8\.venv
    if ($LASTEXITCODE -ne 0) { throw 'Không tạo được M2 core venv.' }
}
# GÁN INTERPRETER: dùng file .exe có thật, không dùng biến $python chưa khai báo.
$core = (Resolve-Path '.\M2_week_7_8\.venv\Scripts\python.exe').Path
# CHỈ LẦN ĐẦU: bảy core pins; KHÔNG dùng root requirement.txt ở đây.
& $core -m pip install -r .\M2_week_7_8\requirement.txt
if ($LASTEXITCODE -ne 0) { throw 'M2 core install fail.' }
& $core -m pip check
```

Core pins: pydantic 2.13.5, python-dotenv 1.2.3, tokenizers 0.22.1, Jinja2 3.1.6, pytest 8.4.2, mypy 1.20.2, Ruff 0.16.7.

HF worker đã đo dùng **Torch 2.11.0+cu128 / Transformers 4.57.6 / tokenizers 0.22.2 / Accelerate 1.15.0 / safetensors 0.8.0**. Các câu lệnh cài riêng đã ghi trong M2 requirement; Torch CUDA cần PyTorch cu128 index, không mặc định PyPI là đủ. Không đưa root requirements vào env HF đã khóa.

**Paths/profile hiện có:**

- HF interpreter: `D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe`. Chỉ mượn dependencies từ env này, **không chạy source hệ thống cũ**.
- Weights: `D:\Project\CAPSTONES\.cache\huggingface\hub\models--Qwen--Qwen3-4B-Instruct-2507\snapshots\cdbee75f17c01a7cc42f958dc650907174af0554`.
- Counter manifest: `VGAR\artifacts\m2\w5-w6\tokenizer_manifest.json`; tokenizer files trong `artifacts/m1/tokenizers/`.
- Source pin: HEAD `b8e246...` và **12 shared boundary file hashes**, kiểm từ `config/source_pin.json`.
- Current integration: **`r002-vgar-i001`**; cha là runtime r002, không gọi layout mới là byte-identical r002.

Các paths này phụ thuộc máy. Đổi path/interpreter/weights/profile hoặc HEAD phải có **relocation/profile receipt và qualification mới**, không âm thầm sửa JSON/expected hashes để Check PASS. Chỉ cài pip hoặc truyền `-Python` **không đủ** chuyển toàn profile.

Venv copy có thể chứa editable `.pth` trỏ source standalone cũ. Launchers/scripts được hỗ trợ chủ động chọn source nhúng; **không dùng bare import/console entrypoint cũ để suy rằng chạy đúng bản nhúng**. Không cài lại env hiện tại chỉ để “sửa” điều này.

## 7. Chạy M2 A/B/C đã tích hợp

### 7.1. Trình tự khuyến nghị trên profile hiện tại

```powershell
# BƯỚC 1: vào VGAR; không vào M2 độc lập cạnh VGAR.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$env:PYTHONUTF8 = '1'

# BƯỚC 2 — CHECK: kiểm source/runtime/prompt/fixtures/pins/CUDA, không load weights.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode Check
if ($LASTEXITCODE -ne 0) { throw 'Check fail: xem logs, chưa chạy generation.' }

# BƯỚC 3 — READSAVED: audit ba real records đã lưu; cần có historical evidence local.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode ReadSaved
if ($LASTEXITCODE -ne 0) { throw 'Saved evidence audit fail hoặc thiếu files.' }

# BƯỚC 4 — RUN: CHỈ chạy khi muốn sinh/kiểm chứng patch MỚI cho A, B, C.
# Full self-tests + Ruff, rồi từng case một generation; có thể tốn thời gian/GPU/RAM.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode Run
$abcExit = $LASTEXITCODE
Write-Host "A/B/C workflow exit code: $abcExit"
```

**Một lệnh chạy mới từ đầu đến cuối trên máy đã đủ prerequisites:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'D:\Project\CAPSTONES\VGAR\run_m2_abc.ps1' -Mode Run
```

- Root default `Check`; runner bên trong default `Run`. Luôn ghi rõ mode.
- `Run` không dùng gold patch, không tự sửa raw diff, không retry/đổi prompt nếu FAIL.
- Dừng ở lỗi đầu tiên; case chưa tới là **chưa chạy**, không tính FAIL/PASS thay.
- Không khuyến nghị `-SkipSelfTests` cho nghiệm thu. Không chạy hai workflow model cùng lúc.
- Bên trong runner reject `PYTHONOPTIMIZE`, paths reparse và output đã tồn tại. Mỗi lần tạo output mới, không ghi đè evidence cũ.
- 3/3 PASS trong `Run` chỉ xác nhận prototype/profile của lượt đó; không phải SWE-bench resolved rate hay MCP integration.

### 7.2. Output mới nằm ở đâu?

Tự tạo: `VGAR\M2_week_7_8\results\manual_abc\<UTC-run-id>\`. Console kết thúc in `DONE mode=...; summary=...`.

```text
<UTC-run-id>/
├── summary.json                Verdict toàn workflow, mode/integration_id/cases
├── all_logs.txt                Console tổng hợp; có command/exit/start-end/duration
├── preflight.json, profile.json
├── *.command.json, *.console.log
├── self_tests/<id>/             Pytest record/JUnit khi Mode Run
├── audit_A.json, audit_B.json, audit_C.json
└── A/, B/, C/
    ├── <canonical-id>/
    │   ├── run_record.json     Record chuẩn của từng case
    │   ├── REPORT.md
    │   ├── prompt.txt         Full prompt đã gửi model
    │   ├── raw_model_output.txt  Output nguyên bản, không sửa hộ model
    │   ├── candidate.diff, applied.diff  Candidate và patch thực đã apply
    │   └── evidence_bundle.json  Bundle liên kết kết quả checks/provenance
    └── model-workers/         Worker requests/logs/diagnostics
```

Tên artifact cụ thể đọc từ canonical record, không đoán tên hoặc tự nối absolute paths lịch sử.

### 7.3. Tự chọn Run mới nhất, không dán folder thủ công

Đoạn này **chỉ chọn Mode=Run của r002-vgar-i001**, không nhầm Check/ReadSaved/historical Run:

```powershell
# CHỈ ĐỌC: chạy từ VGAR; chỉ duyệt summary của workflow, không quét venv hay toàn source.
$resultsRoot = Join-Path $PWD 'M2_week_7_8\results\manual_abc'
if (-not (Test-Path -LiteralPath $resultsRoot)) { throw 'Chưa có results/manual_abc.' }
$candidates = @(Get-ChildItem -LiteralPath $resultsRoot -Directory | ForEach-Object {
    $path = Join-Path $_.FullName 'summary.json'
    if (Test-Path -LiteralPath $path) {
        $s = Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json
        if ($s.mode -eq 'Run' -and $s.PSObject.Properties['integration_id'] -and $s.integration_id -eq 'r002-vgar-i001') {
            [pscustomobject]@{ Path = $path; Summary = $s; Started = $s.started_utc }
        }
    }
})
$selected = $candidates | Sort-Object Started -Descending | Select-Object -First 1
if (-not $selected) { throw 'Chưa có real Run của layout mới; historical/ReadSaved không thay thế Run.' }
$run = Split-Path $selected.Path -Parent
Write-Host "Selected run: $run"
$selected.Summary | Select-Object status,complete,mode,integration_id,started_utc,ended_utc,reason
$selected.Summary.cases | Select-Object letter,task_id,status,input_tokens,output_tokens,duration_ms
Get-Content -Encoding UTF8 (Join-Path $run 'all_logs.txt')
```

Giữ cả latest failed/incomplete run để điều tra; không tự chọn “PASS mới nhất” rồi giấu failures.

## 8. Tự chạy các nhóm test và lưu kết quả

### 8.1. Phân biệt các mức test

| Lệnh/nhóm                 | Thực sự làm gì?                                       | Không chứng minh điều gì?                         |
| ------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| `pytest` root             | Kiểm code/contracts/MCP/graph/legacy runner của VGAR  | Không phải real LLM repair A/B/C                  |
| M2 `record_tests.py`      | Pytest package M2, ghi đầy đủ canonical test evidence | Không phải model giải issue mới                   |
| `run_demo.py --mode fake` | Đi qua repair/apply/verifier bằng reference patch     | Không chứng minh LLM sinh đúng patch              |
| `-Mode ReadSaved`         | Audit lại real records có sẵn                         | Không phải chạy lại inference                     |
| `-Mode Run`               | Self-tests rồi real A/B/C và audit                    | Chỉ ba trusted dev fixtures, không toàn benchmark |

### 8.2. Full M2 core suite — không generate

```powershell
# MỖI TERMINAL: gán core có thật trước; lỗi "& $python" thường do biến rỗng.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$core = (Resolve-Path '.\M2_week_7_8\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# Kết quả ghi vào thư mục mới tự sinh dưới package, không đè saved runs.
Push-Location '.\M2_week_7_8'
try {
    & $core .\scripts\record_tests.py tests --timeout-seconds 240 --output-root .\results\tests
    $suiteExit = $LASTEXITCODE
    Write-Host "M2 full-suite exit code: $suiteExit"
    # Lint đúng phạm vi/rules đã dùng; không phải tất cả Ruff rules.
    & $core -m ruff check --select E9,F src scripts tests
    $lintExit = $LASTEXITCODE
    Write-Host "M2 Ruff exit code: $lintExit"
} finally {
    Pop-Location
}
```

Recorder in path `results/tests/<id>/run_record.json`. Nó chứa pytest stage stdout/stderr/exit/duration và `junit.xml` cùng run. Baseline đã lưu: 236 PASS; máy/profile thay đổi có thể khác, phải xem log thực tế. Không bỏ test fail khỏi suite để gọi “full PASS”.

### 8.3. M1 tests và root full suite

```powershell
# Dùng root env đã cài ở mục 6.3; không dùng M2 core để collection toàn VGAR.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$vgarPython = (Resolve-Path '.\.venv-vgar\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (Resolve-Path '.\src').Path
# Tạo evidence folder mới cho phiên kiểm thử, không cần nhập run ID.
$qa = Join-Path $PWD ('results\manual_tests\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $qa -ErrorAction Stop | Out-Null
# Backup fixture DB trước full suite; tests hiện có có thể thay bytes DB này.
Copy-Item -LiteralPath '.\artifacts\sample_graph.db' -Destination (Join-Path $qa 'sample_graph.before.db')

# Chỉ M1: có console/JUnit; không load Qwen weights.
& $vgarPython .\scripts\run_m1_tests.py "--junitxml=$qa\m1-junit.xml" 2>&1 | Tee-Object -FilePath (Join-Path $qa 'm1-console.log')
$m1Exit = $LASTEXITCODE
Write-Host "M1 exit: $m1Exit"

# Full ROOT suite: tests/ theo pyproject, không trộn M2 nested suite.
& $vgarPython -m pytest -q -p no:cacheprovider "--junitxml=$qa\vgar-junit.xml" tests 2>&1 | Tee-Object -FilePath (Join-Path $qa 'vgar-console.log')
$rootExit = $LASTEXITCODE
Write-Host "VGAR full-suite exit: $rootExit; evidence: $qa"
# Đối chiếu fixture bytes sau test, không tự reset/revert source.
Get-FileHash -Algorithm SHA256 '.\artifacts\sample_graph.db',(Join-Path $qa 'sample_graph.before.db')
```

**Biết trước:** full suite gần nhất có một failure `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`. Test này dùng mocked loader nhưng đòi model dependencies khi import, không phải một real model invocation. Hai skips lúc đó là quyền symlink Windows và thiếu matplotlib. Requirement root mới có matplotlib, nên skip count trên máy mới có thể đổi.

Nếu DB fixture bị tests thay, trước khi khôi phục phải chắc không có phiên khác đang ghi; giữ bản sau-test và chỉ restore đúng backup vừa tạo. Không dùng `git reset --hard`/`git checkout --` để xử lý side effect. Không chạy `pytest .` vì có thể collection lẫn fixtures/package nhúng.

### 8.4. Test runner baseline tuần 3–4

`scripts/run_m2_baseline.py` nhận **repo tin cậy + selectors**, tạo workspace rồi chạy baseline. Không có bước LLM/apply patch. Ví dụ chỉ dùng fixture trong repo:

```powershell
# Chạy từ VGAR bằng root env; selector 'tests' nghĩa toàn thư mục tests của repo đích.
& $vgarPython .\scripts\run_m2_baseline.py .\tests\fixtures\sample_repo tests --task-id readme-baseline --timeout-seconds 120
$LASTEXITCODE
```

Artifact mặc định: `artifacts/m2/test-runs/`. Nếu baseline tái hiện bug và trả FAIL, đó có thể là kết quả mong muốn của bước **trước sửa**, không phải repair engine sửa thất bại.

`record_m2_test.py` còn hỗ trợ ghi unit tests root, nhưng fingerprint toàn workspace trước/sau có thể rất chậm khi đã có data/env/evidence lớn. Timeout pytest không giới hạn phần fingerprint. Không khuyến nghị dùng recorder này để hash cả repo hiện tại chỉ nhằm kiểm nhanh.

## 9. Sử dụng M1 graph, handoff và retrieval evaluation

### 9.1. M1-only setup và graph static

Nếu không cần model/MCP agent đầy đủ, có thể dùng env riêng theo [scripts/requirements_m1.txt](scripts/requirements_m1.txt). File này pin pydantic/dotenv khác M2 core; **không cài vào core M2**.

```powershell
# CHỈ LẦN ĐẦU CHO M1-ONLY: không cần tạo nếu đã dùng .venv-vgar.
if (-not (Test-Path -LiteralPath '.\.venv-m1\Scripts\python.exe')) {
    py -3.11 -m venv .venv-m1
    if ($LASTEXITCODE -ne 0) { throw 'M1 venv fail.' }
}
$m1Python = (Resolve-Path '.\.venv-m1\Scripts\python.exe').Path
& $m1Python -m pip install -r .\scripts\requirements_m1.txt
if ($LASTEXITCODE -ne 0) { throw 'M1 dependencies fail.' }
# MỖI TERMINAL: scripts M1 dùng source checkout này, không cài model stack.
$env:PYTHONPATH = (Resolve-Path '.\src').Path
# Output mới riêng, không ghi đè artifacts/sample_graph.db của tests.
$m1Out = Join-Path $PWD ('results\manual_m1\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $m1Out -ErrorAction Stop | Out-Null
& $m1Python .\scripts\build_graph.py .\tests\fixtures\sample_repo (Join-Path $m1Out 'graph.json') --repo-key demo/readme --revision fixture-v1 --resolver static --debug-log (Join-Path $m1Out 'graph-debug.jsonl')
if ($LASTEXITCODE -ne 0) { throw 'Graph build fail; đọc graph-debug.jsonl.' }
```

Input là source `.py`; output graph JSON chứa nodes/edges/metadata, không phải patch. Graph build mặc định static không cần CUDA/weights.

**SCIP/LSP tùy chọn, chỉ setup khi cần profile đó:**

```powershell
# CHỈ KIỂM TRA: Node/npm phải có sẵn trước cài optional resolver.
node --version
npm.cmd --version
# CHỈ LẦN ĐẦU: npm ci theo lockfiles; có tải packages, không cần cho static.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_scip_runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_lsp_runtime.ps1
```

SCIP khóa `@sourcegraph/scip-python=0.6.6`; LSP khóa `pyright=1.1.414`. `build_graph.py --resolver scip|lsp|scip-lsp` hỗ trợ explicit interpreter/import roots/timeouts. Dùng `--strict-resolver` nếu thí nghiệm yêu cầu không fallback; xem diagnostics về resolver **thực sự** dùng, không gắn nhãn SCIP cho static fallback.

### 9.2. Tokenizer và handoff M1

Token budget dùng local tokenizer manifest với assets/revision/hashes. **Counter không cần model weights**, nhưng có package tokenizers và assets đúng pin. Nếu manifest hiện có đúng thì reuse, không tải lại.

Các interface có thật:

```powershell
# CHỈ ĐỌC HELP: xem arguments trước khi provision/export vào môi trường mới.
& $m1Python .\scripts\provision_m1_tokenizer.py --help
& $m1Python .\scripts\export_m1_handoff.py --help
& $m1Python .\scripts\consume_m1_handoff.py --help
```

`provision_m1_tokenizer.py` cần `--model-id`, `--revision`, `--assets-root`, `--manifest`. `consume_m1_handoff.py` cần `--bundle`, `--repository`, `--task-config`, `--tokenizer-manifest`; có thể lặp `--changed-path` cho actual diff paths. Task config do bên nhận duyệt độc lập, không tin quyền sửa do bundle tự khai.

Nếu muốn sinh **handoff demo mới** bằng assets đã provision (không generate LLM):

```powershell
# Chạy producer M1/consumer diagnostics trên ba fixtures, output mới dưới artifacts/m1/w7-w8/handoff-demos.
& $m1Python .\scripts\demo_w7_w8_handoff.py --tokenizer-manifest .\artifacts\m2\w5-w6\tokenizer_manifest.json
$LASTEXITCODE
```

Demo này không chứng minh model đã tạo patch. `context_format=vgar.context.v1` là wrapper format identifier, không tự đổi thành public `schema_version`; `graph_version` là định danh snapshot.

### 9.3. W5–6 evaluation: đọc saved trước, rerun có chủ đích

**Inputs:** `data/manifests/verified-c104f840cc67-dev-25.json`, nguồn pre-patch từ `data/repositories/archives/`, dataset `princeton-nlp/SWE-bench_Verified` revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`. **Primary query chỉ problem_statement**, không dùng gold paths/patch/hints/FAIL_TO_PASS để tìm context. Gold patch chỉ dùng chọn eligibility/chấm labels.

| Đầu ra đã có               | Folder                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------- |
| BM25 final25               | `results/retrieval/20261013T120702363418Z-b067d65c7d70`                                 |
| Graph final25, 3 timeout   | `results/retrieval/20261013T121221258372Z-9ae258fd202e`                                 |
| Paired comparison 22       | `results/retrieval/20261013T125307312086Z-6d6b0b52b105`                                 |
| Final acceptance ≥20 pairs | `artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json` |

Nếu thật sự muốn rerun, sau khi đã chuẩn bị đúng manifest/assets/source cache, dùng interpreter tương thích riêng cho evaluation. Ví dụ **pilot 3 tasks**, không phải thay thế final25:

```powershell
# GÁN EVAL ENV LOCAL HIỆN CÓ; máy khác phải tạo/provision env tương thích trước.
$evalPython = (Resolve-Path '.\.venv-m2-w5-w6\Scripts\python.exe').Path
$manifest = (Resolve-Path '.\data\manifests\verified-c104f840cc67-dev-25.json').Path
$counter = (Resolve-Path '.\artifacts\m2\w5-w6\tokenizer_manifest.json').Path
$env:PYTHONPATH = (Resolve-Path '.\src').Path
# CÓ CHẠY RETRIEVAL LẠI: --offline yêu cầu cache đầy đủ; thiếu cache thì dừng, không phải lỗi model.
& $evalPython .\scripts\run_bm25_retrieval.py . $manifest --limit 3 --budget-tokens 8000 --tokenizer-manifest $counter --offline
$LASTEXITCODE
& $evalPython .\scripts\run_graph_retrieval.py . $manifest --limit 3 --budget-tokens 8000 --tokenizer-manifest $counter --task-timeout 300 --offline
$LASTEXITCODE
```

Mỗi command in run path mới; giữ path BM25/Graph đúng profile/population khi so sánh. `compare_graph_vs_bm25.py` nhận `root bm25_run graph_run`; Graph CLI không tự sinh standalone REPORT, report so sánh nằm ở comparison folder. Không chọn run đơn thuần “mới nhất” rồi trộn pilot với full25.

Đọc [protocol](docs/handoff/m2-w5-w6/PROTOCOL.md) trước khi thay query/counter/ranking/dataset. Không dùng `--allow-fallback-counter` cho official primary results; bytes/4 chỉ diagnostic. Không tune trên held-out hay đổi task để né ba timeout.

## 10. Agent MCP/LangChain hiện có và cấu hình

**Phần này là đường legacy/root, không phải cách chạy final M2 A/B/C.** Có known findings về binding/security/evidence; chỉ dùng repository/fixtures tin cậy, không repository ngoài chưa duyệt.

### 10.1. Settings của agent

Tạo `.env` từ `.env.example` **một lần nếu cần agent root**, không ghi đè file có sẵn và không giữ token placeholder như secret thật.

```powershell
# CHỈ LẦN ĐẦU CHO LEGACY AGENT: không đổi M2 profile hoặc secrets có sẵn.
if (-not (Test-Path -LiteralPath '.\.env')) {
    Copy-Item -LiteralPath '.\.env.example' -Destination '.\.env'
}
# CHỈ ĐỌC: resolved settings; không load Qwen.
& $vgarPython -m vgar.cli doctor
# MCP TOOL DISCOVERY: spawn stdio servers, không generate model.
& $vgarPython -m vgar.cli tools
```

Thứ tự Settings: environment thật > `.env` > defaults; `get_settings` có cache trong process.

| Biến                                                            | Mặc định/ý nghĩa                                              |
| --------------------------------------------------------------- | ------------------------------------------------------------- |
| `VGAR_MODEL_PROVIDER`, `HF_MODEL_ID`                            | `huggingface`, `Qwen/Qwen3-4B-Instruct-2507` cho agent cũ     |
| `VGAR_TEMPERATURE`                                              | 0; không dùng thay đổi sampling để lách protocol              |
| `MAX_NEW_TOKENS`                                                | 512 **legacy**, không phải cap 1.536 của M2 final             |
| `VGAR_DEVICE_MAP`, `VGAR_TORCH_DTYPE`                           | `auto`, `auto` của backend cũ; M2 profile riêng FP16          |
| `MAX_ITERATIONS`, `VGAR_MAX_TOOL_CALLS`, `VGAR_RECURSION_LIMIT` | 5 / 30 / 50; giới hạn khác nhau, không phải một timeout chung |
| `VGAR_TOKEN_BUDGET`                                             | 8.000 cho root flow; khác full-chat M2 budgeting              |
| `VGAR_GRAPH_BACKEND`                                            | `demo` hoặc `sqlite`                                          |
| `VGAR_GRAPH_DATABASE`, `VGAR_GRAPH_VERSION`                     | Database path/snapshot khi dùng SQLite                        |
| `VGAR_MCP_AUDIT_LOG`                                            | `logs/mcp_audit.jsonl`                                        |
| `HF_TOKEN`                                                      | Nếu cần tải truy cập HF; không đưa vào Git/log chia sẻ        |

`VGAR_REPOSITORY_ROOT` và `VGAR_TOKENIZER_MANIFEST` còn được graph service đọc trực tiếp khi cần source/counter cho related context; chưa được cấu hình/forward thống nhất bởi Settings. Kiểm env/binding cụ thể, không giả định chỉ đặt SQLite DB là mọi context tool đều hoạt động.

### 10.2. Các lệnh CLI thực tế

- `vgar index REPO --db PATH`: build/load graph snapshot.
- `vgar run "ISSUE" --repo REPO --selector tests`: gọi agent trên disposable copy và independent pytest theo selector.
- `vgar solve "ISSUE" --repo REPO --selector TEST1 --selector TEST2`: workflow repair/verify/retry; selector bắt buộc, repeatable.
- `vgar chat --repo REPO`: tương tác; không thay quy trình nghiệm thu có canonical gates.
- `--keep` giữ temporary folder để xem, có thể chiếm đĩa.
- Khi chưa đăng ký console CLI, dùng `& $vgarPython -m vgar.cli ...`.

**Không có selector ở `run` thì exit0 có thể chỉ nghĩa agent kết thúc, chưa independent verification.** “Agent says success”, tool discovery PASS và model trả OK đều không đủ để gọi repair thành công.

MCP hiện có graph tools `search_symbols/get_callers/get_callees/find_task_anchors/get_related_context/get_related_tests`; repository `health/read_file/apply_patch`; execution `health/run_pytest`. Client thêm prefix server, ví dụ `graph_search_symbols`. Repository `apply_patch` hiện nhận exact `old_text/new_text`, **không phải strict unified-diff apply M2 mới**. Các adapter mới `run_relevant_tests/verify_patch` vẫn cần M3 nối.

## 11. Evidence, logs và cách đọc PASS/FAIL

### 11.1. Lưu ở đâu và cần mở gì?

| Phạm vi                       | Đường dẫn/record                                            | Thông tin                                                                    |
| ----------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Historical real M2            | `M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/` | Manifest/profile, A/B/C canonical records, final audits                      |
| Manual A/B/C mới              | `M2_week_7_8/results/manual_abc/<id>/`                      | Summary/all_logs, command receipts, self-tests, per-case records/worker logs |
| M2 unit test runs             | `M2_week_7_8/results/tests/<id>/`                           | `run_record.json` → `stages.pytest`; command/stdout/stderr/exit/time, JUnit  |
| Root manual pytest theo mục 8 | `results/manual_tests/<id>/`                                | Console logs/JUnit và DB backup                                              |
| M2 baseline tuần 3–4          | `artifacts/m2/test-runs/`                                   | JSON test_result, source before/after, command/outcomes                      |
| W5–6 retrieval                | `results/retrieval/<id>/`                                   | Run `result.json`, `tasks/<instance_id>.json`, reports khi có                |
| W5–6 command evidence         | `artifacts/m2/w5-w6/commands/<id>/result.json`              | argv/cwd/interpreter/stdout/stderr/exit/duration/fingerprint                 |
| Integration audit             | `docs/audit/2026-10-16-m2-w7-w8-integration/`               | Copy/preservation/SQLite receipts, full-suite results/XML, review            |
| Task Status QA                | `docs/audit/2026-10-16-task-status-update/`                 | Before snapshot, validation150IDs/tables/links/evidence                      |
| Legacy MCP/graph logging      | `logs/` hoặc explicit `--debug-log`                         | MCP audit JSONL, graph trace, phase console                                  |

**Với M2 repair canonical**, lần theo artifact references trong `run_record.json` để xem prompt đã render, raw output nguyên bản, parser diagnostics, candidate/applied diff, baseline/post checks, EvidenceBundle và REPORT. Không dùng file raw/candidate của một run với verdict của run khác.

Diagnostics M2 gồm:

- UTC bắt đầu/kết thúc, duration pipeline/stages/commands; duration = kết thúc − bắt đầu (monotonic timer khi phù hợp), **không phải bắt đầu − kết thúc**.
- Command/argv/cwd, stdout/stderr, exit code, timeout/complete; baseline và post outcomes.
- Parser raw line/file/hunk, expected/observed counts và `counts_complete`; scanned count chưa hoàn chỉnh không được coi là full count.
- Full exception traceback khi pipeline/worker ghi nhận lỗi.
- Input/output token counts, effective generation configuration, observed attention mask/device placement.
- Source integrity, protected tests/config, cleanup, provenance/hash liên kết artifacts.

Root phase logger dùng `[VGAR] PHASE_START/OUTPUT/END/ERROR` với monotonic duration và output tóm tắt; **không phải mọi root log đều có UTC start/end hoặc toàn bộ payload/raw**. Summarizer cắt bớt nội dung, không phải secret redactor. Không lấy logging chi tiết của M2 để tuyên bố toàn legacy agent đã có cùng chuẩn.

### 11.2. Năm ý nghĩa PASS khác nhau

1. **Pytest PASS:** code self-test đạt; chưa chứng minh LLM sinh patch.
2. **Check PASS:** profile/assets/source/pins hợp lệ, không repair.
3. **Fake PASS:** pipeline chạy với reference candidate, không model success.
4. **ReadSaved PASS:** audit historical real record đạt, không generation mới.
5. **Run + case audit PASS:** generation mới qua gates của case/profile đó.

Với A/B/C, chỉ chốt repair PASS khi raw tự parse, exact apply/attestation thành công, required baseline FAIL → post PASS, regression/collection/type/lint/syntax đã chạy và đạt, source gốc/protected files giữ nguyên, cleanup/evidence đúng. **Riêng B phải có hai production files đổi; C phải có actual fallback collection/execution.**

Các `NOT_RUN`/`SKIP` không được đổi thành PASS. API/structural verification mở rộng chưa được nghiệm thu bằng việc pytest/mypy/Ruff PASS. Private worktree có thể đã cleanup; source sửa được bảo toàn ở applied diff/evidence, không nhất thiết còn thư mục worktree để mở.

## 12. Giới hạn, lỗi đã biết và xử lý thường gặp

| Tình trạng                                          | Giải thích / cách xử lý                                                                                                                |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `& $python` báo BadExpression                       | Biến chưa gán hoặc không là executable. Gán lại `$core`/`$vgarPython` bằng Resolve-Path trong terminal hiện tại, không cài lại mọi thứ |
| Check thiếu Python/core/HF/weights/tokenizer        | Chưa đủ prerequisite hoặc path khác máy. Đọc preflight/console, không sửa expected hash cho qua                                        |
| “Qualified runtime changed”/reference HEAD mismatch | Runtime/config/source đã drift, kể cả root commit mới. Cần reviewed profile/relocation qualification, không bypass guard               |
| ReadSaved thiếu records                             | Results thường bị ignore Git; cần team bàn giao evidence kèm hashes. Không kết luận model FAIL vì clone không có evidence              |
| Source snapshots vẫn có bug sau PASS                | Đúng thiết kế: sửa ở private worktree, original không bị mutate; xem applied diff/post results                                         |
| Full VGAR lỗi `generation_config`                   | Known legacy HF constructor/test contract, đã fail trước relocation; chưa sửa trong package integration                                |
| MCP resources encoded IDs không đọc đúng            | Known legacy decoding/binding finding; xem Task Status, không lấy tool discovery làm resource PASS                                     |
| MCP repo root/path chưa lease-bound đầy đủ          | Không phải sandbox bảo mật hoàn chỉnh. Chỉ fixtures/repo tin cậy, không secrets/untrusted execution                                    |
| Graph timeout SymPy                                 | Ba failures còn nguyên; cần phase/resource profiling mới, chưa chứng minh nguyên nhân sâu                                              |
| Model OOM/chậm/CPU offload                          | Kiểm actual placement/RAM/VRAM và run diagnostics; không mặc định do prompt, không tự tăng budgets/đổi model                           |
| M2 parser FAIL                                      | Xem raw/count diagnostics; không sửa `@@`/whitespace/path của output thay model để gọi PASS                                            |
| Pip cài xong nhưng CUDA False                       | Dependencies cài được không đồng nghĩa đúng CUDA build/driver/profile; root requirements không tự chọn GPU                             |
| Full preservation auditor báo drift sau sửa docs    | Receipt khóa snapshot cũ. README/Task Status/PROGRESS đã đổi theo yêu cầu sau đó; giữ diff/receipt mới, không sửa lịch sử              |
| `package_m1.py` thiếu M2                            | Script chủ ý scope M1; không dùng ZIP M1 làm “toàn bộ VGAR + M2/evidence”                                                              |

Các findings B01–B12, vị trí code và hướng sửa nằm trong [Task Status](<Task Status.md>). M2 mới xử lý nhiều gates trong phạm vi riêng; điều đó **không tự vá tương ứng code legacy** khi chưa nối MCP.

**Chưa có nghiệm thu:** independent teammate clean run, M2 mới qua MCP, full repo repair benchmark, 50–100 SWE-bench tasks chạy được harness, resolved rate/held-out A0–A3, incremental impact/security toàn hệ thống. Ba development fixtures không đại diện các kết quả đó.

## 13. Bàn giao, tái lập và quy tắc thay đổi

1. Đọc Task Status/PROGRESS trước khi làm tiếp; không thực thi lại kế hoạch đã đóng băng chỉ vì còn file plan.
2. Giữ original `D:\Project\CAPSTONES\M2_week_7_8` độc lập. Bản đang chạy trong VGAR là `VGAR\M2_week_7_8`; không copy đè khi đã có evidence mới.
3. Kiểm `git status`/`git diff` trước sửa; giữ các local changes của thành viên khác, đặc biệt retrieval compare/scoring.
4. Không sửa tests/reference patches/parser guards/verifier/source fixtures để làm benchmark PASS; không đánh dấu ownership M1/M3 thay người phụ trách.
5. Không xóa failures/campaigns cũ, reset quota hoặc đổi tên campaign để che lịch sử. Mỗi attempt phải có prompt/runtime/input hashes và canonical path.
6. **Không commit env/weights/secrets/cache lớn.** `.gitignore` loại data/results/logs/tokenizer assets và runtimes; clone không chứa chúng là bình thường. Cần package/release evidence riêng có hashes khi nhóm muốn đọc lại.
7. Không đảm bảo “clone + pip là chạy final profile ngay”: cần source/layout qualification, model/tokenizer assets, đúng env và bàn giao historical records khi dùng ReadSaved.
8. Mọi root commit thay HEAD hiện bị source pin bắt. Khi chuẩn bị commit/release, lập qualification/receipt cập nhật minh bạch, không âm thầm bỏ kiểm.
9. Preserve audit receipts cũ: [copy receipt](docs/audit/2026-10-16-m2-w7-w8-integration/copy.json), [relocation receipt](M2_week_7_8/integration/relocation.json), các command/JUnit trước đó vẫn là lịch sử đúng snapshot của chúng.
10. Sau mỗi thay đổi, chạy đúng checks bị ảnh hưởng, lưu evidence vào output mới và cập nhật PROGRESS/Task Status với **ngày, profile, scope và phần còn thiếu**.

**Gợi ý bàn giao thực tế:** M1 xác nhận context/gold mapping và producer profile; M2 cung cấp engine/fixtures/V11/evidence; M3 nối adapters MCP/LangChain tới engine đã khóa, giữ root/command guards, logging và provenance. Sau đó một đồng đội dựng env riêng và chạy một case/một workflow có evidence mới trước khi gọi toàn flow tích hợp đã nghiệm thu.

README này hướng dẫn đúng các thành phần hiện có, không thay proposal hoặc tự mở rộng scope implementation. Cách nhanh nhất để hiểu repo là: **Task Status → kiến trúc mục 3 → M2 integration handoff → ReadSaved → self-tests → Run có chủ đích**.
