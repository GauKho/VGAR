# VGAR — Graph-Augmented Reasoning cho sửa lỗi phần mềm Python

**Cập nhật: 17/10/2026 • Ngôn ngữ triển khai chính: Python.**

VGAR xây đồ thị mã nguồn để tìm context liên quan đến issue, sau đó hướng tới sinh patch và kiểm chứng patch bằng thực thi. Repository hiện chứa **M1 Graph & Retrieval, M2 baseline/evaluation, M2 Repair & Verification tuần 7–8 (đã tích hợp vào `src/vgar`), cùng agent/MCP của M3**. Các thành phần có mức độ nghiệm thu khác nhau; không được hiểu “đã có file/code” là “toàn hệ thống đã hoàn thành”.

> **Đọc trước khi chạy:** Pipeline M2 tuần 7–8 nay nằm trong `src/vgar/repair` + `src/vgar/models` và chạy bằng `vgar repair` / `vgar solve`. Ngày 17/10, code tích hợp chạy lại **3/3 real repairs A/B/C PASS** trên ba fixture phát triển; `prompt.txt`, raw output và `applied.diff` **trùng byte** với lần 15/10. `vgar solve` (LangGraph) chạy luồng cố định retrieve → generate → apply → test → verify, trong đó các bước repair là **lời gọi MCP thật** tới server `repair` (`run_record.mcp_calls` ghi lại từng call); một lần generate, chưa có vòng thử lại. Full suite VGAR gần nhất **675 PASS, 1 FAIL** (test HF legacy). Package standalone `M2_week_7_8/` đã được xóa; lịch sử của nó còn trong git.

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
| Kiểm pipeline M2 không cần model         | `vgar repair --mode fake` (mục 7)                             | Không; dùng reference patch                              |
| Đối chiếu với evidence A/B/C đã lưu      | Golden test `tests/m2/w78/test_w78_golden_v11.py` (mục 8)     | Không; so byte prompt/diff với lần chạy thật 15/10       |
| Sinh và kiểm chứng patch A/B/C mới       | `vgar repair --mode real` (mục 7)                             | **Có**, một generation/case                              |
| Chạy unit/integration tests              | Mục 8                                                         | Không phải nghiệm thu real repair                        |
| Tìm file, input, patch, stdout/stderr    | Mục 4 và 11                                                   | Không                                                    |
| Chạy M2 qua LangGraph + MCP              | `vgar solve --task ...` (mục 7)                               | Tùy `--mode`; một generation, chưa có retry              |

**Trên máy đã setup**, kiểm nhanh pipeline M2 mà không load model:

```powershell
# Không generate: dùng reference patch; in đường dẫn run_record.json.
.\.venv\Scripts\python.exe -m vgar.cli repair --task examples/m2/tasks/single_file_login.json --mode fake
# 0 = PASS, 1 = FAIL, 2 = ERROR; fake PASS chưa phải model sửa đúng.
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
| M2 W7–8: A/B/C cùng profile          | **3 real cases PASS** ngày 15/10 và chạy lại 17/10 bằng code tích hợp, trùng byte            | Chỉ ba trusted dev fixtures                                                         |
| M2 W7–8 tích hợp vào `src/vgar`      | `vgar repair`, golden test V11, M2 tests port sang `tests/m2/w78/`                           | Package standalone đã xóa; còn cần tái lập trên máy đồng đội                         |
| M3 W7–8: vòng agent dùng M2 mới      | `vgar solve`: LangGraph gọi MCP `repair_get_task_context/apply_patch/run_relevant_tests/verify_patch` | Chưa có vòng thử lại; model chưa tự chọn tool                                       |
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
| Full VGAR 17/10 sau xóa `M2_week_7_8/`      | **675 PASS, 1 FAIL**                     | FAIL là HF legacy `KeyError: generation_config` có từ trước            |
| Real A/B/C 17/10 bằng `vgar repair`         | **3/3 PASS**, trùng byte với 15/10       | Generation 148s / 194s / 69s trên RTX 4050, có CPU offload             |
| Real A/B/C 17/10 bằng `vgar solve` qua MCP  | **3/3 PASS**, trùng byte với 15/10       | 4 MCP calls/run; generation 86s / 148s / 55s; tổng 109s / 174s / 81s   |

Các suite/lượt có thể chồng lấn, **không cộng các hàng thành tổng số tests duy nhất**. Nguồn và paths đầy đủ: [báo cáo tích hợp M2](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md).

### 2.4. Kết quả real repair A/B/C — V11/r002, 15/10/2026

| Case                     | Nhiệm vụ/file thực sự thay đổi                                          | Baseline → post                                  | Pipeline / stage generation | Input / output tokens |
| ------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------ | --------------------------- | --------------------- |
| A — `single_file_login`  | Sửa xử lý login trong `auth.py`                                         | 1 required FAIL + 1 regression PASS → **2 PASS** | 68,828s / 53,250s           | 1.299 / 43            |
| B — `multi_file_invoice` | Sửa **cả `pricing.py` và `invoice.py`**                                 | 2 required FAIL + 1 regression PASS → **3 PASS** | 157,282s / 142,406s         | 1.769 / 157           |
| C — `missing_links`      | Sửa `formatter.py`; thiếu links nên collection/fallback tests chạy thật | 1 required FAIL + 1 regression PASS → **2 PASS** | 64,031s / 51,250s           | 1.169 / 43            |

**Baseline FAIL là lỗi được tái hiện trước khi sửa, không phải kết quả cuối bị FAIL.** Cả ba final audits PASS; source snapshots gốc giữ nguyên. Tổng pipeline 290,141s; tổng stage generation 246,906s. Stage generation gồm overhead worker/load/IO; không đồng nhất với timer riêng bên trong model.

Nguồn: [run_manifest.json](tests/fixtures/m2/golden_v11/run_manifest.json) và records A/B/C trong [golden_v11/](tests/fixtures/m2/golden_v11/). Ngày 15/10 người dùng chạy lại `Mode=Run` của launcher standalone cùng máy, đạt 3/3 (workflow khoảng 429,152s). Ngày 17/10, `vgar repair --mode real` chạy lại 3/3 PASS với prompt/raw output/applied diff trùng byte. Đây **chưa phải đồng đội độc lập/clean-machine acceptance**.

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
| **M2 — Repair & Verification**   | Baseline/tests/evidence W3–4; BM25/gold/metrics W5–6; prompt/generation/diff/worktree/verification W7–8 | `src/vgar/repair/`, `src/vgar/models/`, `src/vgar/evaluation/retrieval/`            |
| **M3 — MCP, Evaluation & Paper** | MCP servers/client, orchestration, protocol/experiment/report, kết nối agent tới tools                  | `src/vgar/mcp/`, `src/vgar/agents/`, `src/vgar/cli.py`; MCP tools M2 mới còn cần nối |

### 3.2. Hai luồng đang tồn tại — không được gộp nhầm

```text
LUỒNG 1: M2 TUẦN 7–8 — vgar repair / vgar solve (src/vgar/repair, src/vgar/models)
M1 frozen handoff + source snapshot + task.json (examples/m2/)
  → M2 validate identity/source/tokenizer
  → private worktree + chạy baseline
  → prompt V11 + 1 HF/Qwen generation
  → strict unified-diff parser → exact binding → Git check/apply
  → actual changed paths → M1 test-selection diagnostics
  → collection + required/regression pytest + syntax/mypy/Ruff
  → source integrity + cleanup → canonical JSON/EvidenceBundle
vgar solve chạy luồng này qua MCP server `repair`: initialize → retrieve [MCP] → generate → apply [MCP]
  → test [MCP] → verify [MCP] → finalize|failed  (vgar repair chạy cùng các bước trong process)

LUỒNG 2: AGENT/MCP EXACT-EDIT CỦA VGAR
CLI run/chat → LangChain agent → MCP client (stdio)
  ├─ graph server → graph/retrieval/SQLite
  ├─ repository server → read_file / apply_patch (exact-edit)
  └─ execution server → run_pytest
  independent verification của `vgar run` dùng workspace/test runner M2
```

Luồng 1 dùng source/consumer/counter của M1 trong chính VGAR. Với `vgar repair`, **`mcp_calls=[]`**; với `vgar solve`, `mcp_calls` liệt kê bốn tool call của server `repair`. Luồng 2 có LangChain/MCP, nhưng model vẫn sửa bằng exact-edit chứ không qua prompt V11/parser unified diff.

### 3.3. M1 được M2 kế thừa như thế nào?

M1 tạo `context.json`, `context_manifest.json`, `test_links.json` và `repair-context.txt`. Consumer M1 kiểm repo/task identity, graph version, source ranges/hash và tokenizer provenance. M2 dùng snippets đúng bytes, rồi thêm metadata trình bày như quyền sửa, vị trí/count hunk, không tự thêm source hoặc đưa gold patch vào real prompt.

Test links của M1 là **candidates**, không phải kết quả chạy tests. M2 phải collection thật, xác nhận node IDs tồn tại; thiếu links thì dùng fallback `tests` có scope đã duyệt, không đổi “không tìm được test” thành PASS.

### 3.4. Prompt và model thực tế

- Final template: [repair_v11.txt](src/vgar/agents/prompts/repair_v11.txt), version `m2-w78-v11` (phiên bản duy nhất được đăng ký), SHA256 `ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8`.
- Yêu cầu chỉ unified diff, chỉ production paths được phép, giữ signatures/indentation; replacement hunk dùng source coordinates và counts riêng. Ví dụ trung tính, không phải lời giải A/B/C.
- [prompt.py](src/vgar/repair/prompt.py) ghép instruction/issue/context, tính full-chat budget; host không recount/sửa output thay model.
- Model prototype: **`Qwen/Qwen3-4B-Instruct-2507`**, model/tokenizer revision **`cdbee75f17c01a7cc42f958dc650907174af0554`**, greedy, FP16, `device_map=auto`. Có thể offload CPU; không khẳng định toàn model nằm GPU.
- Input cap **6.000**, output cap **1.536**, reserve **256** tokens; generation **900s**, command **120s**, global **1.800s/run**.
- [configs/m2/demo.json](configs/m2/demo.json) chọn V11; `RepairPolicy` cũng mặc định V11. Model snapshot đọc từ `~/.cache/huggingface/...`, interpreter worker là `.venv` gốc.
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
├── src/vgar/                    M1 + M2 (W3–8, evaluation) + M3 agent/MCP
├── tests/                       Tests cấp VGAR; fixtures không tự collection
├── scripts/                     CLI tiện ích graph/eval/MCP/baseline/audit
├── configs/                     Node dependency locks, mẫu handoff target; m2/ policy/model/trusted fixtures
├── examples/m2/                 Task configs, source snapshots, M1 bundles của A/B/C
├── docs/                        Contracts, method, design, handoff, audit, plans
├── artifacts/                   Graph fixtures, tokenizer/graph/handoff/evidence
├── data/                        Dataset/cache/source archives/manifest/gold (local)
├── results/retrieval/           Kết quả retrieval theo run ID (local)
├── logs/                        MCP audit/debug/runtime logs (local)
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
| [repair/](src/vgar/repair/)                                            | Engine M2 W7–8: `pipeline.py` một lượt; `prompt.py` (template ở `agents/prompts/repair_v11.txt`); `patch.py` parser/apply; `workspace.py` private worktree; `test_runner.py` + `pytest_plugin.py`; `static_checks.py`; `verification.py`; `test_selection.py`; `context_*.py`; `evidence.py`, `executor.py`, `config.py`, `contracts.py` (xem mục 4.3)                                         |
| [evaluation/retrieval/](src/vgar/evaluation/retrieval/)                | `dataset.py` pin/data; `chunks.py` corpus; `bm25.py` baseline; `gold_labels.py` patch labels; `m1_adapter.py`/`graph_arm.py` bridge Graph; `scoring.py`/`metrics.py` scoring; `compare.py` paired guards; `report.py` report; `evidence.py` command recording; `evaluation.py` điều phối; `resolver_comparison.py` so resolver |
| [agents/](src/vgar/agents/)                                            | `core.py` agent/tools cho `run`/`chat`; `runtime.py` per-run settings; `workflow.py` LangGraph của `solve`; `state.py`/`routes.py` state/transitions; `nodes/` initialize, retrieve/generate/apply/test/verify (MCP), finalize; `prompts/` gồm template V11 `repair_v11.txt` của M2 và instruction agent legacy                                                                                                   |
| [mcp/](src/vgar/mcp/)                                                  | `client.py` stdio clients; `servers/` ba servers; `registry.py`/`tooling.py` tool requirements/budget; `audit.py` log; `schemas.py`/`result_parser.py` response parsing                                                                                                                                                        |
| [models/](src/vgar/models/)                                            | `generator.py` FakeGenerator của M2; `huggingface/` gồm HF worker M2 (`generator_hf.py`, `hf_backend.py`, `hf_worker.py`, `model_worker.py`, `hf_diagnostics.py`, `local_chat.py`) và local tool-calling model của agent `run`/`chat`                                                                                         |
| [config/](src/vgar/config/), [observability/](src/vgar/observability/) | Settings/env/logging; phase instrumentation/graph trace                                                                                                                                                                                                                                                                        |
| [cli.py](src/vgar/cli.py)                                              | `vgar doctor/tools/index/repair/solve/run/chat`; `vgar` entrypoint từ package root                                                                                                                                                                                                                                             |

**Jedi:** không phải resolver bắt buộc hiện tại. Default là **static** (Tree-sitter + Python bindings); **SCIP/Pyright LSP là enrichment tùy chọn**. Không đúng nếu nói mọi lượt Graph hiện đều chạy SCIP hoặc đã bỏ static.

### 4.3. M2 tuần 7–8 trong `src/vgar`

| Module/nhóm                                                                                       | Vai trò                                                                                                               |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `repair/config.py`, `repair/contracts.py`                                                         | Load policy/profile/task (`configs/m2/`, `examples/m2/`), validated task/policy/profile contracts                      |
| `repair/context_adapter.py`, `repair/context_presentation.py`, `repair/prompt.py`                 | Nhận/validate M1 context, trình bày permission/range/counts, render template V11 và full-chat budgeting               |
| `models/generator.py`, `models/huggingface/local_chat.py`                                         | Fake generator cho self-test và local chat tokenizer (không Torch); fake không được tính real                         |
| `models/huggingface/{generator_hf,hf_backend,hf_worker,model_worker}.py`                          | HF chạy trong process riêng (`python -m vgar.models.huggingface.hf_worker`), tokenize/generate, timeout/ownership     |
| `models/huggingface/hf_diagnostics.py`, `repair/diagnostics.py`                                   | Effective generation config, mask/device/token diagnostics, parser detail, Python traceback                           |
| `repair/patch.py`, `repair/workspace.py`                                                          | Strict modify-only diff parser, source binding/preflight/apply/byte attestation; private worktree, protection/cleanup |
| `repair/executor.py`, `repair/test_runner.py`, `repair/pytest_plugin.py`, `repair/test_selection.py` | Bounded command, real collection/outcomes, required/regression selection và fallback                                  |
| `repair/static_checks.py`, `repair/verification.py`                                               | Syntax/mypy/Ruff với config cố định (`configs/m2/static/`), aggregate verdict; không gán PASS cho check chưa chạy     |
| `repair/pipeline.py`, `repair/evidence.py`, `cli.py` (`vgar repair`)                              | Luồng một lượt, durable artifacts/canonical JSON, CLI                                                                 |

Bootstrap/source pin, campaign/adaptive/B-experiment và prompt V1–V10 của bản standalone **không được chuyển sang**; lịch sử của chúng nằm trong [báo cáo M2](docs/handoff/m2-w7-w8/02_BAO_CAO_TOAN_BO_M2_W7_W8.md).

**Inputs A/B/C:**

| Input                     | Đường dẫn theo repo                                                       | Dùng để làm gì?                                       |
| ------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------- |
| Task/issue và selectors   | `examples/m2/tasks/{single_file_login,multi_file_invoice,missing_links}.json` | Xác định case/source/bundle/failing tests             |
| Source gốc trước sửa      | `examples/m2/snapshots/<task_id>/`                                        | Tạo seed/private worktree, giữ nguyên bug để tái hiện |
| M1 context/manifest/links | `examples/m2/handoffs/<task_id>/`                                         | Context đã source-bound + provenance/test candidates  |
| Provenance input          | `examples/m2/inputs_receipt.json`                                         | Nguồn handoff, hashes và thông tin chuẩn bị           |
| Reference patches         | `tests/fixtures/m2/reference_patches/`                                    | Fake mode/tests, **không feed vào real model**        |
| Policy/profile/fixtures   | `configs/m2/{demo,trusted_fixtures}.json`, `configs/m2/static/`           | Model paths, budgets, fixture hashes, mypy/Ruff config |
| Evidence golden 15/10     | `tests/fixtures/m2/golden_v11/{A,B,C}/`                                   | Prompt/raw/applied diff để golden test so byte        |

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
| `run_m1_tests.py`, `smoke_real_repo_graph.py`, `smoke_w7_w8_m1.py`, `smoke_w5_w6_retrieval.py`       | Tests/smoke M1, tokenizer/context/retrieval                                                  |
| `smoke_mcp.py`, `smoke_w3_w4.py`                                                                     | MCP/tools/resources hoặc scripted integration; có known resource finding, không cam kết xanh |
| `run_agent.py`, `smoke_workflow.py`, `smoke_w3_w4_agent.py`                                          | Agent `run`/`chat` và vẽ graph workflow `solve`                                              |
| `smoke_model.py`, `smoke_hf_agent.py`                                                                | Model/agent invocation smoke; “OK” không chứng minh sửa code                                 |
| `package_m1.py`                                                                                      | Đóng gói scope M1; **không bao gồm toàn bộ package/evidence M2 nhúng**                       |

Chạy một case M2 bằng `vgar repair` (thay `run_demo.py` của bản standalone). Các script campaign/qualify/prepare_inputs của bản standalone không được chuyển sang; inputs A/B/C đã có sẵn trong `examples/m2/`.

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
| [Spec](docs/superpowers/specs/2026-10-17-m2-w7-w8-integration-design.md) và [plan](docs/superpowers/plans/2026-10-17-m2-w7-w8-integration.md) tích hợp M2 vào `src/vgar` | Bản đồ module M2 → `src/vgar`, golden test, các giai đoạn còn lại (xóa thư mục, retry)      |

**Ba file bàn giao M2 cần biết** (chép từ bản standalone, giữ nguyên nội dung lịch sử):

1. [01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md](docs/handoff/m2-w7-w8/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md): M1/M3 đọc để hiểu input/output, kết quả có số liệu, contract và phần việc phải nối tiếp.
2. [02_BAO_CAO_TOAN_BO_M2_W7_W8.md](docs/handoff/m2-w7-w8/02_BAO_CAO_TOAN_BO_M2_W7_W8.md): giải thích task, cách triển khai, V11, flow, failures, inventory từng file/thư mục; là báo cáo chi tiết, dài hơn README.
3. [03_LENH_POWERSHELL_A_B_C_V11_R002.md](docs/handoff/m2-w7-w8/03_LENH_POWERSHELL_A_B_C_V11_R002.md): commands/logs A/B/C của launcher standalone lịch sử. **Lệnh hiện hành nằm ở mục 7–8 của README này.**

Các tài liệu trên nhắc paths `M2_week_7_8/...` và `vgar_m2_w78` của bản standalone; bản tương ứng hiện hành xem bảng mục 4.3.

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
| HF worker M2                              | Load Qwen/tokenize full chat/generate trên CUDA   | Process riêng, mặc định cùng `.venv` gốc (`configs/m2/demo.json`)    |

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

### 6.4. M2 tuần 7–8: dùng chung môi trường gốc

M2 không còn cần venv riêng: `vgar repair` chạy trong `.venv` gốc, gọi pytest/mypy/Ruff bằng chính interpreter đó (`pip install -e .[dev]` có `mypy==2.4.0`, `ruff==0.17.0`), và khởi HF worker bằng `interpreter` trong [configs/m2/demo.json](configs/m2/demo.json) (mặc định `../../.venv/Scripts/python.exe`).

**Profile đã chạy real A/B/C ngày 17/10:** Python 3.11.0, Torch 2.5.1+cu121, Transformers 4.57.6, tokenizers 0.22.2, Accelerate 1.15.0, safetensors 0.8.0, RTX 4050 Laptop 6 GB (có CPU offload).

**Paths/profile trong `configs/m2/demo.json`:**

- Weights: `~/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554` (`~` được mở rộng theo user hiện tại).
- Counter manifest: `artifacts/m2/w5-w6/tokenizer_manifest.json`; tokenizer files trong `artifacts/m1/tokenizers/` (local, không commit).
- Fixtures được phép chạy native: `configs/m2/trusted_fixtures.json` (hash từng file snapshot).

Đổi weights/interpreter thì sửa `configs/m2/demo.json` hoặc truyền `--config` khác; không sửa hash trong `trusted_fixtures.json` để một snapshot khác chạy được. Cơ chế source pin (`source_pin.json`) của bản standalone đã bỏ; golden test V11 thay vai trò kiểm drift.

## 7. Chạy M2 A/B/C đã tích hợp

### 7.0. Lệnh tích hợp trong `src/vgar`: `vgar repair` và `vgar solve`

Pipeline M2 tuần 7–8 (prompt V11 → unified diff → worktree riêng → pytest/mypy/Ruff → evidence bundle) nay nằm trong `src/vgar/repair` và `src/vgar/models`, không cần thư mục `M2_week_7_8/`. Task mẫu ở `examples/m2/tasks/`, config ở `configs/m2/demo.json`.

```powershell
# Fake: dùng patch tham chiếu trong tests/fixtures/m2/reference_patches, không load model.
.\.venv\Scripts\python.exe -m vgar.cli repair --task examples/m2/tasks/single_file_login.json --mode fake
# Real: Qwen3-4B (snapshot cdbee75…) chạy trong worker riêng; một generation/task.
.\.venv\Scripts\python.exe -m vgar.cli repair --task examples/m2/tasks/single_file_login.json --mode real
# LangGraph + MCP: retrieve/apply/test/verify là tool call tới server repair; một generation, chưa có vòng thử lại.
.\.venv\Scripts\python.exe -m vgar.cli solve --task examples/m2/tasks/single_file_login.json --mode fake
# Agent tự chọn tool (get_task_context/generate_patch/apply_patch/run_relevant_tests/verify_patch); diff vẫn do bộ sinh V11 tạo.
# Fake: lần sinh 1 cố ý hỏng, lần 2 sinh lại kèm feedback và PASS. Real: --generator worker (mặc định, worker M2) hoặc agent (chính model của agent).
.\.venv\Scripts\python.exe -m vgar.cli solve --task examples/m2/tasks/single_file_login.json --mode fake --agent
.\.venv\Scripts\python.exe -m vgar.cli solve --task examples/m2/tasks/single_file_login.json --mode real --agent --generator worker
```

`vgar repair` in đường dẫn `run_record.json` và trả exit code 0/1/2 cho PASS/FAIL/ERROR. Chỉ chạy native trên fixture đã khớp byte trong `configs/m2/trusted_fixtures.json`. `vgar solve` in `[status] COMPLETED|FAILED`, đường dẫn run và `[reason]` khi fail. Với `--agent`, mỗi lần thử là một run riêng (`supersedes_run_id`), tối đa 3 lần sinh; `[trace]` trỏ tới `<output-root>/agent-traces/<thời điểm>-<task>.json` (thứ tự tool call, agent hay host gọi, các run). `--output-root` mặc định `results/solve`.

### 7.1. Trình tự khuyến nghị

```powershell
# BƯỚC 1: vào repo, UTF-8.
Set-Location 'D:\kltn\vgar_mcp_mvp_demo'
$env:PYTHONUTF8 = '1'
$py = (Resolve-Path '.\.venv\Scripts\python.exe').Path

# BƯỚC 2 — GOLDEN: so byte prompt V11/applied diff với evidence thật 15/10, không load model.
& $py -m pytest -q -p no:cacheprovider tests\m2\w78\test_w78_golden_v11.py
if ($LASTEXITCODE -ne 0) { throw 'Golden fail: pipeline/prompt đã drift, chưa chạy generation.' }

# BƯỚC 3 — RUN: CHỈ chạy khi muốn sinh/kiểm chứng patch MỚI; mỗi case một generation.
$out = Join-Path $PWD ('results\m2-real\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
foreach ($case in 'single_file_login','multi_file_invoice','missing_links') {
    & $py -m vgar.cli repair --task "examples\m2\tasks\$case.json" --mode real --output-root $out
    Write-Host "$case exit code: $LASTEXITCODE"
}
```

- `--mode real` không dùng gold patch, không tự sửa raw diff, không retry/đổi prompt nếu FAIL.
- Không chạy hai lượt model cùng lúc. Mỗi lần dùng `--output-root` mới, không ghi đè evidence cũ.
- 3/3 PASS chỉ xác nhận prototype/profile của lượt đó; không phải SWE-bench resolved rate hay MCP integration.

### 7.2. Output nằm ở đâu?

Mặc định `results/repair/` (`vgar repair`) hoặc `results/solve/` (`vgar solve`), cả hai bị `.gitignore`. Mỗi run một thư mục:

```text
<UTC-run-id>/
├── run_record.json        Record chuẩn: stages, commands, outcomes, status/reason
├── prompt.txt             Full prompt đã gửi model
├── raw_model_output.txt   Output nguyên bản, không sửa hộ model
├── candidate.diff, transport.diff, applied.diff   Candidate và patch thực đã apply
└── evidence_bundle.json   Bundle liên kết kết quả checks/provenance
<output-root>/model-workers/   Worker requests/logs/diagnostics (mode real)
```

Tên artifact cụ thể đọc từ `run_record.json` (`artifacts`), không đoán tên.

### 7.3. Đọc run mới nhất

```powershell
# CHỈ ĐỌC: chọn run_record.json mới nhất dưới một output root.
$record = Get-ChildItem -Recurse -Filter run_record.json $out | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$r = Get-Content -Raw -Encoding UTF8 $record.FullName | ConvertFrom-Json
$r | Select-Object task_id,status,reason,mode,duration_ms
```

Giữ cả run failed/incomplete để điều tra; không tự chọn “PASS mới nhất” rồi giấu failures.

## 8. Tự chạy các nhóm test và lưu kết quả

### 8.1. Phân biệt các mức test

| Lệnh/nhóm                 | Thực sự làm gì?                                       | Không chứng minh điều gì?                         |
| ------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| `pytest` root             | Kiểm code/contracts/MCP/graph/legacy runner của VGAR  | Không phải real LLM repair A/B/C                  |
| `pytest tests/m2/w78`     | Tests M2 W7–8 đã port, gồm golden V11                 | Không phải model giải issue mới                   |
| `vgar repair --mode fake` | Đi qua repair/apply/verifier bằng reference patch     | Không chứng minh LLM sinh đúng patch              |
| Golden test V11           | So byte prompt/applied diff với real records 15/10    | Không phải chạy lại inference                     |
| `vgar repair --mode real` | Real A/B/C, mỗi case một generation                   | Chỉ ba trusted dev fixtures, không toàn benchmark |

### 8.2. Tests M2 tuần 7–8 — không generate

```powershell
Set-Location 'D:\kltn\vgar_mcp_mvp_demo'
$py = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# Tests M2 đã port + golden V11; vài phút vì chạy pytest/mypy/Ruff thật trong worktree.
& $py -m pytest -q -p no:cacheprovider tests\m2\w78 tests\unit
# Lint đúng phạm vi rules M2 đã dùng; không phải tất cả Ruff rules.
& $py -m ruff check --select E9,F src\vgar\repair src\vgar\models\generator.py src\vgar\models\huggingface\generator_hf.py src\vgar\models\huggingface\hf_backend.py src\vgar\models\huggingface\hf_diagnostics.py src\vgar\models\huggingface\hf_worker.py src\vgar\models\huggingface\model_worker.py src\vgar\models\huggingface\local_chat.py tests\m2\w78
```

Lần 17/10: `tests/m2/w78` 127 PASS (gồm 3 golden), `tests/unit` 8 PASS. Không bỏ test fail khỏi suite để gọi “full PASS”.

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

# Full ROOT suite: tests/ theo pyproject (đã gồm tests/m2/w78).
& $vgarPython -m pytest -q -p no:cacheprovider "--junitxml=$qa\vgar-junit.xml" tests 2>&1 | Tee-Object -FilePath (Join-Path $qa 'vgar-console.log')
$rootExit = $LASTEXITCODE
Write-Host "VGAR full-suite exit: $rootExit; evidence: $qa"
# Đối chiếu fixture bytes sau test, không tự reset/revert source.
Get-FileHash -Algorithm SHA256 '.\artifacts\sample_graph.db',(Join-Path $qa 'sample_graph.before.db')
```

**Biết trước:** full suite 17/10 (sau khi xóa `M2_week_7_8/`) có một failure `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`. Test này dùng mocked loader nhưng đòi model dependencies khi import, không phải một real model invocation. Hai skips lúc đó là quyền symlink Windows và thiếu matplotlib. Requirement root mới có matplotlib, nên skip count trên máy mới có thể đổi.

Nếu DB fixture bị tests thay, trước khi khôi phục phải chắc không có phiên khác đang ghi; giữ bản sau-test và chỉ restore đúng backup vừa tạo. Không dùng `git reset --hard`/`git checkout --` để xử lý side effect. Không chạy `pytest .` vì có thể collection lẫn fixtures/package nhúng.

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

**`vgar run`/`vgar chat` là đường agent exact-edit, không phải cách chạy final M2 A/B/C (dùng `vgar repair`/`vgar solve`).** Có known findings về binding/security/evidence; chỉ dùng repository/fixtures tin cậy, không repository ngoài chưa duyệt.

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
- `vgar repair --task TASK.json --mode fake|real`: một lượt pipeline M2; in `run_record.json`, exit 0/1/2.
- `vgar solve --task TASK.json [--mode fake|real]`: LangGraph gọi bốn tool `repair_*` qua MCP, **một** generation; chưa có retry.
- `vgar solve --task TASK.json --agent [--generator worker|agent]`: agent tự chọn tool và có thể sinh lại kèm feedback (tối đa 3 lần); kết quả lấy từ `verify_patch` của run cuối.
- `vgar chat --repo REPO`: tương tác; không thay quy trình nghiệm thu có canonical gates.
- `--keep` giữ temporary folder để xem, có thể chiếm đĩa.
- Khi chưa đăng ký console CLI, dùng `& $vgarPython -m vgar.cli ...`.

**Không có selector ở `run` thì exit0 có thể chỉ nghĩa agent kết thúc, chưa independent verification.** “Agent says success”, tool discovery PASS và model trả OK đều không đủ để gọi repair thành công.

MCP hiện có graph tools `search_symbols/get_callers/get_callees/find_task_anchors/get_related_context/get_related_tests`; repository `health/read_file/apply_patch`; execution `health/run_pytest`. Client thêm prefix server, ví dụ `graph_search_symbols`. Repository `apply_patch` hiện nhận exact `old_text/new_text`, **không phải strict unified-diff apply M2**. Server `repair` (dùng bởi `vgar solve`) có `repair_get_task_context/apply_patch/run_relevant_tests/verify_patch` trên engine M2; xem [MCP contract](docs/mcp_tool_contract.md).

## 11. Evidence, logs và cách đọc PASS/FAIL

### 11.1. Lưu ở đâu và cần mở gì?

| Phạm vi                       | Đường dẫn/record                                            | Thông tin                                                                    |
| ----------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Historical real M2 15/10      | `tests/fixtures/m2/golden_v11/`                             | Run manifest, A/B/C prompt/raw/diff/run_record/evidence bundle               |
| `vgar repair` / `vgar solve`  | `results/repair/<id>/`, `results/solve/<id>/` (local)       | Per-case records, artifacts, worker logs (`model-workers/`)                 |
| Root manual pytest theo mục 8 | `results/manual_tests/<id>/`                                | Console logs/JUnit và DB backup                                              |
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
2. **Golden PASS:** prompt V11/applied diff trùng byte với real records đã lưu, không generation mới.
3. **Fake PASS:** pipeline chạy với reference candidate, không model success.
4. **`vgar solve` COMPLETED:** LangGraph đi hết `repair_run → finalize`, verdict lấy từ chính run M2 bên dưới.
5. **`vgar repair --mode real` PASS:** generation mới qua gates của case/profile đó.

Với A/B/C, chỉ chốt repair PASS khi raw tự parse, exact apply/attestation thành công, required baseline FAIL → post PASS, regression/collection/type/lint/syntax đã chạy và đạt, source gốc/protected files giữ nguyên, cleanup/evidence đúng. **Riêng B phải có hai production files đổi; C phải có actual fallback collection/execution.**

Các `NOT_RUN`/`SKIP` không được đổi thành PASS. API/structural verification mở rộng chưa được nghiệm thu bằng việc pytest/mypy/Ruff PASS. Private worktree có thể đã cleanup; source sửa được bảo toàn ở applied diff/evidence, không nhất thiết còn thư mục worktree để mở.

## 12. Giới hạn, lỗi đã biết và xử lý thường gặp

| Tình trạng                                          | Giải thích / cách xử lý                                                                                                                |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `& $python` báo BadExpression                       | Biến chưa gán hoặc không là executable. Gán lại `$core`/`$vgarPython` bằng Resolve-Path trong terminal hiện tại, không cài lại mọi thứ |
| `Pinned snapshot/interpreter missing`               | Path weights/interpreter trong `configs/m2/demo.json` khác máy. Sửa config hoặc truyền `--config`, không sửa hash fixtures cho qua      |
| `Native execution only allowed on ... fixtures`     | Task/snapshot không khớp `configs/m2/trusted_fixtures.json`. Đúng thiết kế: chỉ chạy native trên fixture đã duyệt                      |
| Golden test V11 fail                                | Prompt/parser/tokenizer đã drift so với real records 15/10. Tìm thay đổi gây lệch, không cập nhật golden cho qua                       |
| Source snapshots vẫn có bug sau PASS                | Đúng thiết kế: sửa ở private worktree, original không bị mutate; xem applied diff/post results                                         |
| Full VGAR lỗi `generation_config`                   | Known legacy HF constructor/test contract, đã fail trước relocation; chưa sửa trong package integration                                |
| MCP resources encoded IDs không đọc đúng            | Known legacy decoding/binding finding; xem Task Status, không lấy tool discovery làm resource PASS                                     |
| MCP repo root/path chưa lease-bound đầy đủ          | Không phải sandbox bảo mật hoàn chỉnh. Chỉ fixtures/repo tin cậy, không secrets/untrusted execution                                    |
| Graph timeout SymPy                                 | Ba failures còn nguyên; cần phase/resource profiling mới, chưa chứng minh nguyên nhân sâu                                              |
| Model OOM/chậm/CPU offload                          | Kiểm actual placement/RAM/VRAM và run diagnostics; không mặc định do prompt, không tự tăng budgets/đổi model                           |
| M2 parser FAIL                                      | Xem raw/count diagnostics; không sửa `@@`/whitespace/path của output thay model để gọi PASS                                            |
| Pip cài xong nhưng CUDA False                       | Dependencies cài được không đồng nghĩa đúng CUDA build/driver/profile; root requirements không tự chọn GPU                             |
| `package_m1.py` thiếu M2                            | Script chủ ý scope M1; không dùng ZIP M1 làm “toàn bộ VGAR + M2/evidence”                                                              |

Các findings B01–B12, vị trí code và hướng sửa nằm trong [Task Status](<Task Status.md>). M2 mới xử lý nhiều gates trong phạm vi riêng; điều đó **không tự vá tương ứng code legacy** khi chưa nối MCP.

**Chưa có nghiệm thu:** independent teammate clean run, M2 mới qua MCP, full repo repair benchmark, 50–100 SWE-bench tasks chạy được harness, resolved rate/held-out A0–A3, incremental impact/security toàn hệ thống. Ba development fixtures không đại diện các kết quả đó.

## 13. Bàn giao, tái lập và quy tắc thay đổi

1. Đọc Task Status/PROGRESS trước khi làm tiếp; không thực thi lại kế hoạch đã đóng băng chỉ vì còn file plan.
2. Code M2 hiện hành nằm trong `src/vgar`. Package standalone `M2_week_7_8/` đã xóa ngày 17/10; cần đối chiếu thì xem lịch sử git trước commit xóa.
3. Kiểm `git status`/`git diff` trước sửa; giữ các local changes của thành viên khác, đặc biệt retrieval compare/scoring.
4. Không sửa tests/reference patches/parser guards/verifier/source fixtures để làm benchmark PASS; không đánh dấu ownership M1/M3 thay người phụ trách.
5. Không xóa failures/campaigns cũ, reset quota hoặc đổi tên campaign để che lịch sử. Mỗi attempt phải có prompt/runtime/input hashes và canonical path.
6. **Không commit env/weights/secrets/cache lớn.** `.gitignore` loại data/results/logs/tokenizer assets và runtimes; clone không chứa chúng là bình thường. Cần package/release evidence riêng có hashes khi nhóm muốn đọc lại.
7. Không đảm bảo “clone + pip là chạy final profile ngay”: cần source/layout qualification, model/tokenizer assets, đúng env và bàn giao historical records khi dùng ReadSaved.
8. Source pin của bản standalone đã bỏ; golden test V11 và full suite là gate khi đổi code M2. Không cập nhật golden fixtures để test qua.
9. Preserve audit receipts cũ: [copy receipt](docs/audit/2026-10-16-m2-w7-w8-integration/copy.json) và các command/JUnit trước đó vẫn là lịch sử đúng snapshot của chúng.
10. Sau mỗi thay đổi, chạy đúng checks bị ảnh hưởng, lưu evidence vào output mới và cập nhật PROGRESS/Task Status với **ngày, profile, scope và phần còn thiếu**.

**Gợi ý bàn giao thực tế:** M1 xác nhận context/gold mapping và producer profile; M2 cung cấp engine/fixtures/V11/evidence; M3 nối adapters MCP/LangChain tới engine đã khóa, giữ root/command guards, logging và provenance. Sau đó một đồng đội dựng env riêng và chạy một case/một workflow có evidence mới trước khi gọi toàn flow tích hợp đã nghiệm thu.

README này hướng dẫn đúng các thành phần hiện có, không thay proposal hoặc tự mở rộng scope implementation. Cách nhanh nhất để hiểu repo là: **Task Status → kiến trúc mục 3 → mục 4.3 → golden test → `vgar repair --mode fake` → `--mode real` có chủ đích**.
