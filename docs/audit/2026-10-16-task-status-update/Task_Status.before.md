P

# Task Status — VGAR sau tích hợp main và M1

**Ngày kiểm tra:** 13/10/2026, múi giờ Asia/Saigon.**Repository mới:** `D:\Project\CAPSTONES\VGAR`.**Căn cứ chính:** `D:\Project\CAPSTONES\New_task\project_plan_16_weeks.md`.

> **Kết luận:** hai nhánh đã được tích hợp bằng fast-forward, không có conflict
> code. Repo có nền tảng graph/retrieval, MCP và baseline verification; **chưa
> hoàn thành pipeline repair theo toàn bộ yêu cầu tuần 7–8**, chưa có impact,
> incremental graph update và evaluation A0–A3 đầy đủ. Suite sau tích hợp còn
> một test lỗi; smoke resource MCP nghiêm ngặt cũng lỗi. Không nên tuyên bố
> “toàn hệ thống đã chạy thành công” từ kết quả scripted smoke.

## Mục lục

**Cập nhật triển khai M2 tuần5–6 ngày13/10/2026:** baseline HEAD giữ nguyên, thêm diff hẹp M2 compare/scoring. W05-06-M2-03 CX→HT theo approved gate25attempted/22validpairs;3Graphtimeouts công khai, không claim25/25PASS. W05-06-M2-04 giữMP, technical consumer/handoff đã đạt nhưng M1-owner review pending. Các kết luận audit và task ownership khác bên dưới giữ nguyên, không được thay bằng kết quả targeted tests. Evidence hiện hành: [báo cáo M2](docs/handoff/m2-w5-w6/COMPLETION_REPORT.md), [handoff](docs/handoff/m2-w5-w6/CONTEXT_GOLD_HANDOFF.md), [acceptance receipt](artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json).

1. [Nguồn, cách tích hợp và phạm vi kiểm tra](#1-nguồn-cách-tích-hợp-và-phạm-vi-kiểm-tra)
2. [Quy ước trạng thái](#2-quy-ước-trạng-thái)
3. [Evidence mới và giới hạn kiểm thử](#3-evidence-mới-và-giới-hạn-kiểm-thử)
4. [Danh mục evidence và vị trí implementation](#4-danh-mục-evidence-và-vị-trí-implementation)
5. [Trạng thái từng task theo 16 tuần](#5-trạng-thái-từng-task-theo-16-tuần)
6. [Lỗi, sai lệch và blocker](#6-lỗi-sai-lệch-và-blocker)
7. [Đề xuất thứ tự hoàn thiện](#7-đề-xuất-thứ-tự-hoàn-thiện)
8. [Đọc và tự kiểm tra lại kết quả](#8-đọc-và-tự-kiểm-tra-lại-kết-quả)
9. [Việc đã làm và việc không làm trong phiên này](#9-việc-đã-làm-và-việc-không-làm-trong-phiên-này)

## 1. Nguồn, cách tích hợp và phạm vi kiểm tra

### 1.1. Hai nhánh nguồn

| Nguồn                                                                                    | Commit được clone/pin                      | Vai trò                                                              |
| ---------------------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------- |
| [GauKho/VGAR — main](https://github.com/GauKho/VGAR/tree/main)                           | `b39e0dbf87645d39b9a68e87b19d0655df264a05` | Nền tảng tích hợp của nhóm                                           |
| [GauKho/VGAR — m1-w5-w6-20261010](https://github.com/GauKho/VGAR/tree/m1-w5-w6-20261010) | `73814b8f89666c71b1911e42e98b8ecc7f6e3e99` | Các thay đổi graph/retrieval, SCIP/LSP, handoff và orchestration/log |

Nhánh M1 **đã chứa toàn bộ lịch sử main**. `git merge-base` trả đúng commit
main; `git merge-base --is-ancestor origin/main origin/m1-w5-w6-20261010`
trả exit 0. Vì vậy, không copy đè file riêng lẻ và không dùng `ours/theirs` để
bỏ qua implementation: clone cả refs, tạo nhánh local
`integration/main-m1-w5-w6-20261013`, rồi `git merge --ff-only`.

HEAD cuối là `73814b8f...`. Tree của commit tích hợp khớp nhánh M1; main vẫn
có trong lịch sử. **Không có commit mới và không push/đổi nhánh trên GitHub.**
Nhánh integration local ban đầu được tạo từ `origin/main`; không tự push nó
vào remote main bằng các lệnh ở báo cáo này.

Năm commit sau main là `d3fdfbe6`, `86d2e68c`, `d7586f1f`, `4ce181b3`,
`73814b8f`. Chúng bao gồm code orchestration P0, logging, cleanup runtime,
graph retrieval không dùng Jedi và adapter SCIP/LSP/handoff. Tên nhánh
`w5-w6` **không có nghĩa mọi file chỉ thuộc tuần 5–6**, hoặc cả tuần đã được
nghiệm thu.

### 1.2. Dữ liệu/cache bị bỏ khỏi checkout theo nhánh nguồn

Commit `d7586f1f` đã bỏ tracking nhiều file runtime: downloaded dataset/source
trees, gold patches, kết quả benchmark và log. Khi fast-forward, các file ấy
được bỏ khỏi checkout đúng theo commit nguồn; **không phải lỗi clone/merge**.
Chúng còn trong Git history `origin/main`, nhưng kết quả lịch sử không mặc
định chứng minh được code ở HEAD hiện nay.

Main clone có 38.511 tracked files; commit tích hợp có **260 tracked files**:
93 trong `src`, 61 trong `tests` (gồm fixtures), 37 scripts, 25 docs, 30
artifacts nền tảng, 8 configs và 6 file/cấu hình gốc khác. Các file audit mới
không nằm trong số 260. [inventory.json](docs/audit/2026-10-13/inventory.json)
lưu đường dẫn, kích thước, SHA256 và AST definitions của từng file Python.
AST parse trên toàn bộ file Python được track không ghi nhận syntax error;
điều này **không chứng minh logic đúng hoặc package build thành công**.

Main baseline tests ghi thêm 4 dòng vào log vốn được track. Đã lưu bản log
sau test ở [main-mcp-audit-after-baseline.jsonl](docs/audit/2026-10-13/main-mcp-audit-after-baseline.jsonl)
và stash riêng thay đổi log để Git cho phép fast-forward. Stash có message
`audit-main-baseline-generated-mcp-log-20261013`; không apply lên nhánh đã bỏ
tracking log. Không mất evidence, không rollback code của thành viên.

### 1.3. Tài liệu có quyền quyết định scope

- Checklist chính có **150 mục**: mục tiêu chung, task M1/M2/M3, DoD và ba
  mục con A0/A1/A2. Bảng bên dưới giữ đủ từng ID, không bỏ qua mục research.
- [Bản snapshot kế hoạch](docs/audit/2026-10-13/project_plan_16_weeks.snapshot.md)
  có SHA256 `e349be0599fb2082b2ae4caa52241332a1c8b776ffe54b2c85fdf535e7c1ea53`,
  trùng file gốc. [plan-checklist.json](docs/audit/2026-10-13/plan-checklist.json)
  giữ nguyên câu chữ, số dòng và hierarchy; bảng dùng tên rút gọn cho dễ đọc.
- Proposal gốc và kế hoạch P0–P5 không thay thế scope 16 tuần. **Full CPG,
  GraphDiff/history, architecture lift tự động, Daikon, fine-tuning và đa
  ngôn ngữ là extension**, không tính là task MVP bị thiếu.
- `New_task/research_design.md` tồn tại ngoài clone, nhưng nói Qwen2.5-Coder
  32B/vLLM, Docker bắt buộc và một protocol rộng hơn code hiện tại. File đó
  không phải bằng chứng runtime này đã tuân thủ các yêu cầu ấy. Cần nhóm
  thống nhất protocol; báo cáo này không tự nâng model lên 32B hay chuyển
  execution sang Docker.
- Tuần 1–2 là research/governance: không thấy artifact trong clone không
  đồng nghĩa thành viên chưa nghiên cứu ngoài repo. Những mục đó dùng nhãn
  **CX**, không kết luận “chưa làm” từ việc không có source code.

## 2. Quy ước trạng thái

| Mã     | Trạng thái                        | Cách hiểu                                                                                                                                                |
| ------ | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **HT** | Hoàn thành trong phạm vi được nêu | Có implementation/tài liệu thích hợp và evidence kiểm tra tương ứng. Không suy từ đó toàn milestone hoặc benchmark đã hoàn thành.                        |
| **MP** | Chưa hoàn thành — đã làm một phần | Có nền tảng, nhưng còn thiếu yêu cầu, lỗi, nối consumer, runtime acceptance hoặc deliverable cần thiết.                                                  |
| **CT** | Chưa triển khai trong clone này   | Không thấy producer/runner/module/experiment cần thiết; placeholder hoặc thành phần tiền đề không thay được implementation.                              |
| **CX** | Chưa xác minh / thiếu evidence    | Có ghi nhận lịch sử hoặc nội dung có thể nằm ngoài repo, nhưng không đủ dữ liệu để xác nhận trên snapshot này. Không khẳng định task chưa từng được làm. |

“HT” cho tài liệu schema không phải “HT” cho chức năng dùng schema. Tests
mock/scripted không được đổi nhãn thành LLM thật. Kết quả benchmark cũ không
được đổi nhãn thành kết quả của HEAD hiện tại. Nhiều mục chung/DoD lặp lại
task thành viên, nên **không lấy tỷ lệ checkbox làm % tiến độ hoặc công sức**.

### Tổng hợp checklist

| Tuần     | Tổng mục |     HT |     MP |     CT |     CX |
| -------- | -------: | -----: | -----: | -----: | -----: |
| 1–2      |       21 |      6 |      5 |      0 |     10 |
| 3–4      |       22 |     16 |      5 |      0 |      1 |
| 5–6      |       20 |     11 |      5 |      1 |      3 |
| 7–8      |       19 |      2 |     14 |      1 |      2 |
| 9–10     |       20 |      0 |      4 |     14 |      2 |
| 11–12    |       16 |      1 |      8 |      6 |      1 |
| 13–14    |       16 |      0 |      6 |      4 |      6 |
| 15–16    |       16 |      1 |      8 |      0 |      7 |
| **Tổng** |  **150** | **37** | **55** | **26** | **32** |

Các số này là **số dòng checklist được phân loại**, không phải37 features
độc lập hay % đồ án. Mục HT về README/schema có thể thuộc tuần15–16 dù
research experiment của tuần ấy chưa chạy. [report-qa.json](docs/audit/2026-10-13/report-qa.json)
kiểm đủ150 IDs, không thiếu/trùng ID và không có link local hỏng.

## 3. Evidence mới và giới hạn kiểm thử

### 3.1. Các lượt đã thực sự chạy

| Kiểm tra                                        | Kết quả mới                                                | Evidence                                                                                                                                                    | Giới hạn                                                                                                      |
| ----------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Full pytest trên main trước tích hợp            | **196 passed, 1 skipped**, exit 0, **63,08 s**             | [log](docs/audit/2026-10-13/main-baseline.log), [JUnit](docs/audit/2026-10-13/main-baseline.xml)                                                            | Không chạy model hoặc SWE-bench repair                                                                        |
| Full pytest sau tích hợp                        | **411 passed, 1 failed, 2 skipped**, exit 1, **51,34 s**   | [log](docs/audit/2026-10-13/integrated-tests.log), [JUnit](docs/audit/2026-10-13/integrated-tests.xml)                                                      | HF test mock lỗi; không được nói suite xanh                                                                   |
| LangGraph/LangChain agent → MCP → edit → pytest | **PASS 16 checks**, 6 tool calls, **16,2 s**, exit 0       | [scripted log](docs/audit/2026-10-13/scripted-agent-smoke.log), [artifacts](docs/audit/2026-10-13/scripted-agent-artifacts/)                                | `--model scripted`: biết sẵn edit đúng. Không chứng minh HF sửa lỗi được                                      |
| Full MCP smoke với resource gate nghiêm ngặt    | **FAIL**, exit 1 ở node resource                           | [log](docs/audit/2026-10-13/full-mcp-smoke.log), [audit](docs/audit/2026-10-13/full-mcp-artifacts/mcp_audit.jsonl)                                          | Graph tools/summary đã pass; dừng trước các stage patch/evidence phía sau. Không tính stage chưa chạy là PASS |
| Reproduction có kiểm soát trên thư mục tạm      | Script exit 0,**xác nhận 5 observations**                  | [probe JSON](docs/audit/2026-10-13/probe-findings.json), [log](docs/audit/2026-10-13/probe-findings.log), [script](docs/audit/2026-10-13/probe_findings.py) | Exit 0 nghĩa thu thập xong findings,**không phải 5 lỗi đã được sửa**                                          |
| Inventory/checklist/AST                         | 260 tracked files, 150 checklist items, 0 AST parse errors | [snapshot](docs/audit/2026-10-13/snapshot.json), [inventory](docs/audit/2026-10-13/inventory.json)                                                          | Static inventory không chứng minh mọi nhánh hành vi đã test                                                   |

Hai skip: Windows không cho tạo symlink trong test bảo vệ link, và thiếu
optional `matplotlib` trong test plot. Skip là chưa kiểm tra được ở môi
trường này, không phải PASS. Nhóm graph/context/SCIP/LSP/source/token trong
JUnit gồm 312 case được chọn theo tên, 311 pass và 1 skip; đây là subset
của 414 case, **không cộng thêm vào tổng**.

### 3.2. Interpreter và dependencies

Đã tái sử dụng **chỉ interpreter/packages** ở
`D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe`, Python 3.11.6;
`PYTHONPATH` và pytest `pythonpath` trỏ vào `D:\Project\CAPSTONES\VGAR\src`.
MCP con dùng cùng Python và source VGAR mới. Không chạy source hệ thống cũ,
không cài/đổi package trong venv ấy.

Các bản chính: pytest 8.4.2, Pydantic 2.13.5, MCP 1.30.0, LangChain 1.4.0,
LangGraph 1.2.11, adapters 0.3.2, Tree-sitter 0.25.2, grammar 0.25.0,
Transformers 4.57.6, tokenizers 0.22.2, Torch 2.11.0+cu128. PyArrow đang là
25.0.1 khác pin 23.0.1; PEFT/TRL không có trong môi trường đã kiểm tra.
**Chưa nghiệm thu clean install của pyproject hoặc requirements M1.**
Xem packages đầy đủ trong snapshot; không coi thiếu PEFT/TRL là lỗi retrieval
hay bằng chứng fine-tuning là bắt buộc.

Không tải model weights, không chạy HF repair thật, không tải/rerun 25 hay
50–100 SWE-bench tasks, không cài SCIP/Pyright runtimes. Tokenizer manifest
được track nhưng bốn assets của nó không có trong clone. Các indexer runtime
cũng là outputs ignored phải provision riêng theo installer, không phải
file source bị commit thiếu.

### 3.3. Evidence lịch sử cần thận trọng

- [Handoff W5–6](docs/m1_w5_w6_handoff_2026-10-10.md), mục 5: khai báo BM25
  25/25, Graph primary 21/25, Django chạy phục hồi riêng thành công, tổng 22/25
  Graph tasks có kết quả, còn ba SymPy timeout 300 s. Bảng chung vẫn là 21
  pairs; không tự cộng lượt chạy khác profile thành một full25 mới.
- Bảng ấy có file R@5 BM25 53,97% vs Graph 32,14%, function R@5 27,18% vs
  16,47%. Đây là **số do tài liệu lịch sử khai báo**, không được tái tính
  trong audit hiện tại; raw result files của bảng không có trong clone.
- Manual inspection lịch sử ghi 10 tasks: 2 hữu ích, 4 một phần, 4 ít phù
  hợp. JSON rubrics/cases được dẫn tới đường dẫn ignored, không có trong
  clone để xác minh chi tiết.
- [Retrieval method](docs/m1_retrieval_method.md) ngày 12/10 có profile v10 và
  khai báo bounded dev7, 19/21 resolver runs; đây không phải full25 hay
  held-out. Chưa có raw evidence chuyển giao tương ứng.
- [Edge review CSV](artifacts/m1/graph-quality/edge_review.csv) có 20 dòng
  review lịch sử ngày 01/10, nhưng một dòng tham chiếu Jedi đã bị xóa.
  Không dùng nó để tuyên bố precision của SCIP/LSP tại HEAD hiện nay.

## 4. Danh mục evidence và vị trí implementation

Bảng task sử dụng các mã E dưới đây để tránh lặp đường dẫn rất dài. Số dòng
code áp dụng HEAD `73814b8f`; link mở đúng file trong clone này.

| Mã  | File/thư mục                                                                                                                                                                                                                                                                                 | Vai trò và giới hạn                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| E01 | [graph_schema.md](docs/graph_schema.md), [schema.py](src/vgar/contracts/schema.py), [context.py](src/vgar/contracts/context.py)                                                                                                                                                              | Node/edge vocabulary, ranges, confidence/provenance, DTO; không có literal FailingTest                                    |
| E02 | [builder.py](src/vgar/graph/builder.py), [builder tests](tests/test_graph_builder.py), [robustness tests](tests/test_graph_builder_robustness.py)                                                                                                                                            | Tree-sitter + AST/symtable; L111 parser, L286 file extraction, L1329–1355 import/name fallback                            |
| E03 | [sqlite_store.py](src/vgar/graph/sqlite_store.py), [sqlite_service.py](src/vgar/graph/sqlite_service.py)                                                                                                                                                                                     | Persist/query/full snapshots; service L57–60 yêu cầu source root và tokenizer khi retrieve                                |
| E04 | [scip_resolver.py](src/vgar/graph/scip_resolver.py), [lsp_resolver.py](src/vgar/graph/lsp_resolver.py), [configs](configs/), [install SCIP](scripts/install_scip_runtime.ps1), [install LSP](scripts/install_lsp_runtime.ps1)                                                                | Optional SCIP/Pyright LSP, pin/config/fallback; unit fixtures không thay indexer thật                                     |
| E05 | [grounding.py](src/vgar/graph/grounding.py), [task_overlay.py](src/vgar/graph/task_overlay.py)                                                                                                                                                                                               | Issue → anchors/trace; Test → Issue REPRODUCES là báo cáo đầu vào, không phải test execution                              |
| E06 | [retrieval.py](src/vgar/graph/retrieval.py), [token_counter.py](src/vgar/graph/token_counter.py), [retrieval method](docs/m1_retrieval_method.md)                                                                                                                                            | Traversal/ranking/source checks/snippet token budget; risk weight mặc định 0; native packing khác fair evaluator          |
| E07 | [test_selection.py](src/vgar/graph/test_selection.py), [handoff.py](src/vgar/graph/handoff.py), [consumer validation](src/vgar/contracts/handoff.py), [prompt_context.py](src/vgar/contracts/prompt_context.py)                                                                              | Context sidecars và static test hints; chưa collect/run tests, chưa gọi trong production repair                           |
| E08 | [bm25.py](src/vgar/evaluation/retrieval/bm25.py), [chunks.py](src/vgar/evaluation/retrieval/chunks.py), [gold_labels.py](src/vgar/evaluation/retrieval/gold_labels.py), [scoring.py](src/vgar/evaluation/retrieval/scoring.py), [metrics.py](src/vgar/evaluation/retrieval/metrics.py)       | BM25, gold changed-code proxy, shared ranking/packed scoring, Recall/MRR; gold parser không phải repair patch engine      |
| E09 | [dataset.py](src/vgar/evaluation/retrieval/dataset.py), [evaluation.py](src/vgar/evaluation/retrieval/evaluation.py), [run_graph_retrieval.py](scripts/run_graph_retrieval.py), [compare.py](src/vgar/evaluation/retrieval/compare.py), [report.py](src/vgar/evaluation/retrieval/report.py) | Retrieval manifests/cache/runners/paired bootstrap; không official repair grading hoặc environment-readiness              |
| E10 | [workspace.py](src/vgar/repair/workspace.py), [workspace tests](tests/m2/test_workspace.py)                                                                                                                                                                                                  | Bản sao disposable, hash/size/path guards/cleanup; không OS/container sandbox và không ràng buộc root MCP                 |
| E11 | [test_runner.py](src/vgar/repair/test_runner.py), [runner tests](tests/m2/test_test_runner.py)                                                                                                                                                                                               | Bounded pytest, selectors, Windows Job, JUnit; L182 coi exit 0 là PASS dù tất cả cases skipped                            |
| E12 | [baseline.py](src/vgar/repair/baseline.py), [evidence_writer.py](src/vgar/repair/evidence_writer.py), [contracts/evidence.py](src/vgar/contracts/evidence.py), [evidence design](docs/evidence_bundle_schema.md)                                                                             | Baseline + pending/atomic final JSON; không tự nối vào workflow repair                                                    |
| E13 | [graph_server.py](src/vgar/mcp/servers/graph_server.py), [client.py](src/vgar/mcp/client.py), [tooling.py](src/vgar/mcp/tooling.py), [schemas.py](src/vgar/mcp/schemas.py)                                                                                                                   | 6 graph tools, 3 resources, graph envelope/audit; resource L135/155 không URL-decode node ID                              |
| E14 | [repository_server.py](src/vgar/mcp/servers/repository_server.py), [execution_server.py](src/vgar/mcp/servers/execution_server.py)                                                                                                                                                           | read/exact edit/pytest; root do caller chọn, không lease jail; execution runner khác E11                                  |
| E15 | [workflow.py](src/vgar/agents/workflow.py), [prepare.py](src/vgar/agents/nodes/prepare.py), [repair.py](src/vgar/agents/nodes/repair.py), [verify.py](src/vgar/agents/nodes/verify.py), [finalize.py](src/vgar/agents/nodes/finalize.py), [cli.py](src/vgar/cli.py)                          | Outer prepare→agent→pytest→retry; thiếu deterministic retrieve và durable repair bundle; verify L49–52 NOT_RUN các checks |
| E16 | [settings.py](src/vgar/config/settings.py), [hf_model.py](src/vgar/models/huggingface/hf_model.py), [local_hf_chat_model.py](src/vgar/models/huggingface/local_hf_chat_model.py), [system prompt](src/vgar/agents/prompts/system.md)                                                         | HF model mặc định, tool bridge; chưa pin weights SHA/full prompt budget/token usage; repair prompt riêng rỗng             |
| E17 | [instrumentation.py](src/vgar/observability/instrumentation.py), [phase_logger.py](src/vgar/observability/phase_logger.py), [graph_trace.py](src/vgar/observability/graph_trace.py)                                                                                                          | Logs/timing; redaction regex L31–32 double-escaped; chưa unified audit/performance report                                 |
| E18 | [handoff W5–6](docs/m1_w5_w6_handoff_2026-10-10.md), [handoff W7–8](docs/m1_w7_w8_scip_handoff_2026-10-11.md), [graph quality](docs/graph_quality_report.md)                                                                                                                                 | Báo cáo lịch sử; xem giới hạn §3.3, không dùng thay raw/current evidence                                                  |
| E19 | [verification_design.md](docs/verification_design.md), [schema design](docs/evidence_bundle_schema.md), [README](README.md), [mcp contract](docs/mcp_tool_contract.md)                                                                                                                       | Technical docs đã có; chưa phải final paper/protocol đã ký                                                                |
| E20 | [package_m1.py](scripts/package_m1.py), [pyproject.toml](pyproject.toml), [README](README.md)                                                                                                                                                                                                | Packaging/install scaffolding; không clean-machine artifact acceptance                                                    |
| E21 | [Full suite mới](docs/audit/2026-10-13/integrated-tests.xml), [main baseline](docs/audit/2026-10-13/main-baseline.xml)                                                                                                                                                                       | Evidence thực tế trong phiên; count/pass/fail/skip/seconds, không LLM/benchmark                                           |
| E22 | [scripted smoke](docs/audit/2026-10-13/scripted-agent-smoke.log), [strict MCP smoke](docs/audit/2026-10-13/full-mcp-smoke.log), [probes](docs/audit/2026-10-13/probe-findings.json)                                                                                                          | Actual transport orchestration, resource failure và controlled reproductions                                              |
| E23 | [snapshot](docs/audit/2026-10-13/snapshot.json), [inventory](docs/audit/2026-10-13/inventory.json), [checklist](docs/audit/2026-10-13/plan-checklist.json)                                                                                                                                   | Toàn bộ tracked-file coverage, package versions và canonical checklist                                                    |

## 5. Trạng thái từng task theo 16 tuần

Mỗi dòng có ID duy nhất đối chiếu được với số dòng plan trong
`plan-checklist.json`. **CT của tuần tương lai không có nghĩa dự án bị trễ**;
đây là inventory năng lực hiện có, không đánh giá lịch làm việc của nhóm.

### 5.1. Tuần 1–2 — Research design và kiến trúc

| ID              | Task                                                                | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                                  | Giải pháp để đóng task                                                                         |
| --------------- | ------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| W01-02-CHUNG-01 | Chốt claim graph retrieval + verification cho multi-file repair     | **CX**     | README thể hiện hướng nghiên cứu; không có scope/protocol sign-off trong clone.                                              | Nhóm xác nhận RQ/claim theo evidence, lưu biên bản hoặc ADR.                                   |
| W01-02-CHUNG-02 | Python, SWE-bench Verified/Lite, một model cố định                  | **MP**     | E08–09 dùng Python/Verified; E16 dùng một Qwen4B mặc định. Protocol ngoài repo lại nêu model32B; chưa thống nhất.            | Chốt một protocol runtime/benchmark cho MVP, tránh dùng mặc định như model đã frozen.          |
| W01-02-CHUNG-03 | Chốt version/model/temperature/budget/timeout/iterations/calls      | **MP**     | Settings có nhiều giới hạn; tokenizer SHA có trong manifest. HF weights không pin revision; full-prompt budget chưa enforce. | Pin model/tokenizer SHA, prompt hash và budget; ghi timeout per-stage và artifact.             |
| W01-02-CHUNG-04 | Chốt graph MVP và optional layers                                   | **HT**     | E01 công bố vocabulary, validation và giới hạn; Layers 3/4 không cần cho MVP.                                                | Giữ freeze; biểu diễn FailingTest còn là deviation riêng ở W5–6.                               |
| W01-02-CHUNG-05 | Repo, issue board, branching/PR convention, source layout           | **MP**     | Repo và source phân domain có thật; issue board/PR convention không thấy bằng chứng trong clone.                             | Lưu contribution/ownership rules và link board; kiểm cấu hình GitHub riêng.                    |
| W01-02-CHUNG-06 | Protocol trước benchmark chính                                      | **CX**     | Có specs evaluation kỹ thuật; external research_design khác runtime, không có freeze được nhóm xác nhận.                     | Chốt protocol đơn nhất trước chạy chính, giữ manifest/hash và change log.                      |
| W01-02-M1-01    | Đọc/tóm tắt 8–10 paper graph/localization                           | **CX**     | Không có bảng tóm tắt đủ số lượng trong 25 docs được track.                                                                  | Nhận hồ sơ nghiên cứu từ M1, không yêu cầu viết lại nếu đã làm ngoài repo.                     |
| W01-02-M1-02    | Viết docs/graph_schema.md                                           | **HT**     | E01 có node/edge/properties/confidence/provenance và source-range semantics.                                                 | Bảo trì cùng contract tests khi có thay đổi được duyệt.                                        |
| W01-02-M1-03    | Schema File/Module/Class/Function/Method/Import/CallSite/Test/Issue | **HT**     | E01 NODE_TYPES chứa đủ; Issue qua task overlay E05.                                                                          | Không biến Issue overlay thành chứng cứ test execution.                                        |
| W01-02-M1-04    | Schema CONTAINS/IMPORTS/CALLS/REFERENCES/TESTS/MENTIONS/REPRODUCES  | **HT**     | E01 schema, E02/E05 producers; REFERENCES là mức MVP, không full dataflow.                                                   | Giữ ghi rõ coverage và provenance.                                                             |
| W01-02-M2-01    | Đọc/tóm tắt 8–10 paper APR/validation                               | **CX**     | Không thấy literature summaries đủ số bài trong clone.                                                                       | Bổ sung hoặc liên kết hồ sơ M2 đã nghiên cứu.                                                  |
| W01-02-M2-02    | Viết docs/verification_design.md                                    | **HT**     | E19 có trình tự baseline, lỗi, limits, safety.                                                                               | Tài liệu này chỉ đóng design baseline W3–4, không giả là design W7–12 hoàn chỉnh.              |
| W01-02-M2-03    | Chốt failing/relevant tests/type/lint/API signature MVP             | **MP**     | E12/E19 dành fields cho các tiers; chưa có policy/commands/acceptance thống nhất của các tiers sau baseline.                 | Viết policy check bắt buộc/optional/NOT_RUN và failure semantics cùng M3.                      |
| W01-02-M2-04    | Thiết kế JSON schema EvidenceBundle                                 | **HT**     | E12 Pydantic models, validators và schema docs; E21 contract tests pass.                                                     | Versioning phải theo freeze; schema existence không tính tier đã chạy.                         |
| W01-02-M3-01    | Đọc/tóm tắt 8–10 paper benchmark/MCP/security                       | **CX**     | Không có hồ sơ đọc đủ số lượng trong clone.                                                                                  | Nhận/bổ sung literature summaries của M3.                                                      |
| W01-02-M3-02    | docs/research_design.md với RQ/hypothesis/split/fairness            | **CX**     | File không nằm trong clone; New_task có bản ngoài repo với những giả định khác code.                                         | Nhóm rà soát, thống nhất scope16W rồi bàn giao bản canonical; không copy mù nội dung rộng hơn. |
| W01-02-M3-03    | Literature table 30–50 papers                                       | **CX**     | Không thấy docs/literature_review.csv hoặc bảng tương đương đủ bài.                                                          | Bàn giao bảng có primary links và nội dung review.                                             |
| W01-02-M3-04    | Cài thử SDK/adapters/SWE-bench tooling                              | **MP**     | MCP/adapters chạy thật ở E22; chỉ có retrieval dataset tooling, chưa official harness/environment probe.                     | Giữ môi trường MCP đã kiểm, tạo profile execution/harness riêng khi cần benchmark.             |
| W01-02-DOD-01   | Nhóm ký scope/protocol                                              | **CX**     | Sign-off là thông tin quản trị không có bằng chứng trong clone.                                                              | Lưu approval/link, không suy từ code.                                                          |
| W01-02-DOD-02   | Branch protection/PR review                                         | **CX**     | Git clone không cho biết branch protection; không kiểm dashboard/quyền quản trị GitHub.                                      | Maintainer kiểm settings và lưu quy trình review.                                              |
| W01-02-DOD-03   | Ít nhất 20 paper trong literature table                             | **CX**     | Chưa có bảng để đếm; không khẳng định nhóm chưa đọc.                                                                         | Bàn giao và đếm bài đã review thật, không chỉ danh sách tên.                                   |

### 5.2. Tuần 3–4 — Graph MVP, baseline verification và MCP

| ID              | Task                                                      | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                                       | Giải pháp để đóng task                                                                                        |
| --------------- | --------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| W03-04-CHUNG-01 | Xây graph repository Python                               | **HT**     | E02–03 builder/persist/query; smoke build sample có 40 nodes/52 edges.                                                            | Không suy graph precision toàn repo từ fixture; xử lý B10.                                                    |
| W03-04-CHUNG-02 | MCP server và LangChain client kết nối                    | **HT**     | E22 scripted transport thực chạy 6 calls qua graph/repository/execution.                                                          | Resource node có lỗi riêng B02, không phủ nhận tool connectivity đã pass.                                     |
| W03-04-CHUNG-03 | Tests trên repo nhỏ trước benchmark                       | **HT**     | E21 parser/storage/grounding/baseline/runner fixtures đã chạy.                                                                    | Ghi riêng mocks, skip và lỗi HF, không gộp thành benchmark.                                                   |
| W03-04-M1-01    | Tích hợp Tree-sitter Python                               | **HT**     | E02 parser và grammar thực; E21 regression tests pass.                                                                            | Giữ pin 0.25.2/0.25.0 đã công bố.                                                                             |
| W03-04-M1-02    | Extract file/module/class/function/method/import/callsite | **HT**     | E02 producers và tests; extraction giới hạn theo schema docs.                                                                     | Bổ sung scopes phức tạp theo dev failures, không hứa full Python semantics.                                   |
| W03-04-M1-03    | Build nodes/edges cơ bản                                  | **HT**     | E02 schema validation, file rollback, CALLS/IMPORTS/TESTS, E21.                                                                   | Sửa heuristic explicit-import sai B10 trước mở rộng graph.                                                    |
| W03-04-M1-04    | SCIP/LSP/Pyright/Jedi symbol resolution tối thiểu         | **MP**     | E04 có SCIP/LSP code và fixture tests; Jedi đã bỏ. Indexer thật chưa cài/chạy tại clone này.                                      | Cài runtime từ lock, chạy strict fixture smoke; không coi fallback static là indexer PASS.                    |
| W03-04-M1-05    | Import/direct calls có confidence/provenance              | **MP**     | E02 làm được nhiều direct calls; probe B10 xác nhận explicit external import bị nối sai nội bộ ở confidence0.6.                   | Chặn name fallback khi đã biết explicit import khác module; giữ unresolved/candidate riêng.                   |
| W03-04-M1-06    | SQLite hoặc Kùzu persistence                              | **HT**     | E03 SQLite transactional snapshots/query, E21 tests pass.                                                                         | SQLite đáp ứng lựa chọn plan, không cần thêm Kùzu.                                                            |
| W03-04-M1-07    | Unit tests parser/extractor/query                         | **HT**     | E21 tests tương ứng chạy thành công; có regression fixtures.                                                                      | Thêm regression negative cho B10 và transport resource B02.                                                   |
| W03-04-M2-01    | Sandbox/worktree để patch an toàn                         | **MP**     | E10 disposable copies/cleanup pass; E14 cho model chọn root khác lease, probe B04 chứng minh. Không OS sandbox.                   | Bind server-owned writable lease root; integrity trên mọi terminal path; không chỉ nhắc trong prompt.         |
| W03-04-M2-02    | Pytest wrapper                                            | **HT**     | E11 runner bounded/Job/JUnit và regression tests.                                                                                 | HT cho wrapper chức năng W3–4; skipped-only semantics B06 và MCP runner B05 phải sửa trước repair acceptance. |
| W03-04-M2-03    | Baseline command/stdout/stderr/exit/duration              | **HT**     | E12 baseline + runner; E21 tests xác nhận PASS/FAIL/TIMEOUT/cleanup và records.                                                   | Không dùng baseline evidence làm bằng chứng model đã tạo patch.                                               |
| W03-04-M2-04    | Schema EvidenceBundle + writer JSON                       | **HT**     | E12 atomic pending/final writer, unique run paths, schema tests pass.                                                             | Nối writer này vào repair workflow ở tuần7–8; hiện chỉ baseline.                                              |
| W03-04-M3-01    | MCP server tối thiểu                                      | **HT**     | E13–14 ba server stdio và discovery thật E22.                                                                                     | Không tính uniform schema/security/full tools đã hoàn chỉnh.                                                  |
| W03-04-M3-02    | Ba resources repo summary/node/subgraph                   | **MP**     | Resource functions có code; summary pass nhưng encoded node qua MCP FAIL B02. Subgraph trực tiếp pass, chưa nghiệm thu transport. | Decode ID đúng một lần ở boundary, thêm MCP round-trip tests cho node/subgraph.                               |
| W03-04-M3-03    | search_symbols/get_callers/get_callees                    | **HT**     | E13 typed tools, E22 real MCP calls đều pass.                                                                                     | Callers/callees trực tiếp; multi-hop do retrieval đảm nhiệm.                                                  |
| W03-04-M3-04    | LangChain MCP client/adapters                             | **HT**     | E13 MultiServerMCPClient đúng interpreter/source, scripted orchestration E22.                                                     | Nối context capabilities mới vào consumer, không cần đổi transport.                                           |
| W03-04-M3-05    | Audit tool calls cơ bản                                   | **HT**     | E13 graph structured audit có request/status/duration, E22 saved JSONL.                                                           | HT ở mức graph cơ bản, không toàn bộ repair tools/token/performance.                                          |
| W03-04-DOD-01   | Callers/callees/imports hợp lý                            | **MP**     | Fixture và ordinary queries pass; B10 false binding cản tuyên bố quality rộng hơn.                                                | Review cases external import/shadowing, chặn false edges và tái kiểm sample.                                  |
| W03-04-DOD-02   | Manual validation ≥20 call/import edges                   | **CX**     | E18/CSV có20 rows lịch sử lexical/Jedi, không đủ attribution cho snapshot/resolver mới.                                           | Annotate20 edges hiện tại, lưu expected/actual/source/rule và peer sign-off.                                  |
| W03-04-DOD-03   | Node/edge/build-time log/dashboard                        | **HT**     | Builder statistics E02; E22 sample smoke và E18 metrics lịch sử ghi counts/timing.                                                | Ghi từng resolver/source SHA; một build time không phải performance benchmark.                                |

### 5.3. Tuần 5–6 — Task grounding và retrieval

| ID              | Task                                             | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                 | Giải pháp để đóng task                                                                                          |
| --------------- | ------------------------------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| W05-06-CHUNG-01 | Issue/failing tests nối graph                    | **HT**     | E05 Issue overlay + MENTIONS/REPRODUCES và tests.                                                           | Đây là reported failing tests, không execution evidence; literal FailingTest ở dòng M1-03 là deviation.         |
| W05-06-CHUNG-02 | Graph context dưới token budget                  | **HT**     | E06 producer source/range/hash/counter guards, E21 tests.                                                   | HT module độc lập; production agent wiring còn thiếu B03, full prompt budget chưa tính.                         |
| W05-06-CHUNG-03 | BM25 + sơ bộ retrieval evaluation                | **MP**     | E08–09 code/test có; E18 số25 lịch sử nhưng raw evidence/results/manifest không chuyển giao.                | Khôi phục raw dev evidence đúng SHA hoặc chạy lại có pin, không lấy docs làm số mới.                            |
| W05-06-M1-01    | find_task_anchors(issue,failing_tests)           | **HT**     | E05 implementation và E21 path/symbol/stack/test cases.                                                     | Giữ ambiguity/unmatched diagnostics thay vì đoán target.                                                        |
| W05-06-M1-02    | Path/symbol/trace/test/route/API anchors         | **HT**     | E05 literal/heuristic matching có tests; không chạy issue code.                                             | Công bố giới hạn dynamic routes và unknown receiver.                                                            |
| W05-06-M1-03    | Issue/FailingTest nodes và trace edges           | **MP**     | Issue có; dùng Test sẵn → Issue, NODE_TYPES không có FailingTest.                                           | Nhóm duyệt biểu diễn tương đương bằng ADR hoặc bổ sung node theo contract review; không tự đổi schema.          |
| W05-06-M1-04    | get_related_context(anchor_ids,budget)           | **HT**     | E06 retrieval + E03 facade; task_id/version/issue tường minh, không phụ thuộc session.                      | Provision source/counter khi dùng facade; sửa production setup B03.                                             |
| W05-06-M1-05    | k-hop/callers/callees/tests/dependents           | **HT**     | E06 semantic folding/reverse relations/bounded traversal; E21 tests.                                        | Chỉ graph MVP; folder hints không phải architecture dependencies.                                               |
| W05-06-M1-06    | Rank distance/confidence/test proximity/API risk | **MP**     | E06 có features nhưng API-risk weight mặc định0; history cần dữ liệu caller cung cấp.                       | Duyệt tắt risk trong default hoặc thử weight trên dev, lưu report; không tuyên bố risk đang ảnh hưởng rank.     |
| W05-06-M1-07    | Pack snippets trong token budget                 | **HT**     | E06 pack whole source snippets, verified token counter và validate total.                                   | Assets phải provision riêng; không đồng nhất snippets-only với full prompt tokens.                              |
| W05-06-M2-01    | BM25 trên function/code chunks                   | **HT**     | E08 BM25 k1=1.2/b=0.75, corpus code chunks; E21 tests chống gold leakage.                                   | Giữ cùng query/corpus/token policy với Graph khi so sánh.                                                       |
| W05-06-M2-02    | Gold file/function từ developer patch            | **HT**     | E08 diff→old/new AST labels, dedup/function mapping/coverage; E21 tests.                                    | Gold là changed-code proxy; mapping không đầy đủ phải báo denominator, không coi root-cause truth.              |
| W05-06-M2-03    | Retrieval eval20–30 SWE-bench tasks              | **HT**     | Đợt triển khai13/10: pinned dev25, BM25 25/25; Graph22/25 và3SymPy timeout300s;22valid primary pairs/current source hashes/actual counter đã verify. [Report](docs/handoff/m2-w5-w6/COMPLETION_REPORT.md), [receipt](artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json). | HT evaluation theo gate≥20pairs; không phải mọi task chạyPASS hay repair success. Giữ3timeouts/limitations; không tune M1 để Graph thắng. |
| W05-06-M2-04    | Phối hợp context format/gold mapping             | **MP**     | Actual M1 producer→M2 proof2items/47tokens/0unmapped;121targeted testsPASS, patch identity/range guards/diagnostics có evidence; paired22 đã verify. [Handoff](docs/handoff/m2-w5-w6/CONTEXT_GOLD_HANDOFF.md). | Còn M1-owner review/sign-off về source/range/order/mapping; agent không ký thay. GiữMP đến khi có xác nhận người phụ trách và receipt scope. |
| W05-06-M3-01    | MCP anchors/context tools                        | **HT**     | E13 đăng ký typed tools, E21 boundary tests; graph service không duplicate SQLite schema.                   | Tool có mặt không chứng minh model gọi đúng hoặc default app đã cấu hình.                                       |
| W05-06-M3-02    | Issue→anchors→context→display flow               | **MP**     | scripts/smoke_w5_w6_retrieval.py có flow adapter thật; chưa chạy với tokenizer assets ở clone này.          | Provision tokenizer-only bundle, chạy smoke và lưu data wrapper/overlay consistency.                            |
| W05-06-M3-03    | Subset50–100 task có environment chạy được       | **CT**     | E09 chỉ chọn/archive nguồn phục vụ retrieval; không F2P/P2P environment probe hoặc manifest runnable50–100. | Tách environment-readiness khỏi retrieval: pinned commands/harness, baseline/gold/regression evidence per task. |
| W05-06-M3-04    | Draft Related Work graph/retrieval               | **CX**     | Technical docs không phải Related Work có paper citations; không thấy draft trong clone.                    | Nhận/bổ sung draft nghiên cứu từ M3; không gán code README là paper.                                            |
| W05-06-DOD-01   | Bảng Graph vs BM25 R@3/5/10 + tokens             | **CX**     | E18 có bảng21 pairs lịch sử; code E09 tái tạo được khi có raw runs, hiện không có.                          | Bàn giao run JSON/config/hash/manifest và regenerate cùng protocol; không trộn native/fair packing.             |
| W05-06-DOD-02   | Manual-inspect ≥10 tasks                         | **CX**     | E18 ghi10 cases nhưng rubric JSON/raw contexts không có trong clone.                                        | Nhận hồ sơ10 cases hoặc inspect lại theo rubric trên pinned dev runs; cần review độc lập.                       |

### 5.4. Tuần 7–8 — Repair pipeline và verification cơ bản

| ID              | Task                                                     | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                            | Giải pháp để đóng task                                                                                                  |
| --------------- | -------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| W07-08-CHUNG-01 | Agent sinh unified diff từ issue + context               | **MP**     | Agent gọi exact-edit tools; diff do difflib tạo sau edit. M1 context chưa deterministic vào prompt B03/B07.            | Retrieve/validate/render trước generate, model trả diff, parse/preflight rồi apply.                                     |
| W07-08-CHUNG-02 | Apply trong worktree                                     | **MP**     | Scripted smoke sửa disposable copy; root MCP không bound và chưa atomic multi-file diff.                               | Fix lease boundary B04 rồi diff engine B07; lưu file/diff hashes.                                                       |
| W07-08-CHUNG-03 | Tests/type/lint evidence                                 | **MP**     | Failing pytest có; type/lint luôn NOT_RUN ở verify.                                                                    | Implement commands/policy và lưu actual results, không đổi NOT_RUN thành PASS.                                          |
| W07-08-M1-01    | Payload snippets/IDs/paths/metadata/relevance, versioned | **HT**     | E01/E07 DTO, wrapper vgar.context.v1, source sidecars/consumer validation; E21 tests.                                  | Wrapper format không phải schema_version; M2 kiểm full prompt budget riêng.                                             |
| W07-08-M1-02    | Cải thiện ranking trên dev, ghi heuristic/tuning         | **MP**     | E06 profile v10/heuristics có docs; dev7/19-of21 ghi lịch sử, chưa raw/current report chứng minh improvement.          | Giữ frozen dev protocol, review misses, chỉ đổi heuristic có log và paired before/after evidence.                       |
| W07-08-M1-03    | Test-to-function links nếu suy ra được                   | **HT**     | E02 TESTS + E07 direct/caller traversal/fallback, E21 tests.                                                           | Static candidates không phải coverage/collection; M2 vẫn collect và giữ required failing cases.                         |
| W07-08-M2-01    | Repair prompt template cố định                           | **MP**     | E16 system.md là instruction chung; repair.md rỗng, first/retry prompts chưa hash/version/context integration.         | Viết fixed diff-output repair template, pin/hash/version, include path/symbol/range và source binding.                  |
| W07-08-M2-02    | Một LLM backend cố định theo protocol                    | **MP**     | E16 HF/Qwen tool bridge có; B01 constructor test fail, weights SHA chưa pin, real repair chưa chạy trong audit.        | Chốt constructor semantics và revision, kiểm invocation/tool-call rồi ba dev repair cases có evidence.                  |
| W07-08-M2-03    | Validate/parse unified diff                              | **CT**     | Gold parser E08 chỉ phục vụ labels; E14 repair dùng exact edit, không nhận model diff.                                 | Thêm strict diff parser/count/path/hunk guards cho repair, tests malformed/tampered/multi-file.                         |
| W07-08-M2-04    | apply_patch vào temporary worktree                       | **MP**     | E10 + E14 áp một replacement vào file có sẵn, E22 smoke pass; không diff preflight/atomic multi-file/add-delete.       | Preflight toàn patch trên lease, bảo vệ oracle, atomic apply/rollback; exact edit giữ tên riêng nếu cần.                |
| W07-08-M2-05    | Relevant-test selection cơ bản                           | **MP**     | E07 graph hints có; E15 verify chỉ dùng failing_tests do người dùng truyền.                                            | Consume hints trên snapshot trước patch, union failing selectors, collect trên worktree, explicit fallback.             |
| W07-08-M2-06    | Chạy pytest + typecheck + lint                           | **MP**     | E11 pytest có; E15 type/lint NOT_RUN, không runner ruff/mypy/Pyright diagnostics.                                      | Thêm runners bounded theo policy, baseline/postpatch nếu cần tránh nhiễu lỗi cũ.                                        |
| W07-08-M2-07    | Bundle patch/failing/relevant/type/lint                  | **MP**     | E12 baseline bundle có; E15 repair chỉ dict/tail, chưa writer, chưa diff aggregate, không phân failing/relevant tiers. | Pending/final bundle mỗi task/attempt, full stdout/stderr/cases/diff/config ngoài temp; mark tier chưa chạy trung thực. |
| W07-08-M3-01    | MCP apply_patch/run_relevant_tests/verify_patch          | **MP**     | E14 chỉ exact apply_patch/run_pytest; chưa hai tools run_relevant_tests/verify_patch.                                  | Adapter mỏng gọi M2 shared services, thống nhất envelope/error/lease/audit.                                             |
| W07-08-M3-02    | Loop retrieve→generate→patch→verify                      | **MP**     | E15 có prepare→agent→verify→retry, E22 scripted inner loop; thiếu mandatory retrieval/context/diff contract.           | Nối M1/M2 theo từng stage, test default/stale env và consumer end-to-end.                                               |
| W07-08-M3-03    | Prompt/model config/calls/latency/token usage logs       | **MP**     | E17 có traces/duration/call count; E16 không token usage/model revision/prompt hash, artifacts repair thiếu.           | Meter actual tokenizer input/output, pin config, unified run_id/audit, save metadata trong bundle.                      |
| W07-08-M3-04    | Draft Methodology overview/graph/retrieval               | **CX**     | Có schema/method docs E19, không thấy paper draft với cấu hình/claim thống nhất.                                       | Nhận draft M3 rồi đối chiếu actual implementation, không đưa features tương lai vào “đã làm”.                           |
| W07-08-DOD-01   | ≥3 task diff hợp lệ + verification                       | **CX**     | E22 chỉ một fixture scripted; không có ba real-model diff/evidence records.                                            | Sau fixed core, chạy ≥3 small dev cases (gồm multi-file), lưu model/config/diff/tests/source integrity.                 |
| W07-08-DOD-02   | Không ghi repo gốc                                       | **MP**     | Scripted source hash unchanged; B04 cho root tùy ý, finalize failed path không kiểm integrity.                         | Enforce lease ở tools, protected files và all-terminal integrity; test wrong-root/agent-error cases.                    |

### 5.5. Tuần 9–10 — Impact analysis và ablation sơ bộ

| ID              | Task                                                        | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                     | Giải pháp để đóng task                                                                                      |
| --------------- | ----------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| W09-10-CHUNG-01 | Diff→graph nodes                                            | **CT**     | Gold diff mapping E08 chỉ trích labels; không có repair hunk→graph ID producer.                                 | Map changed files/ranges tới nodes của baseline snapshot, ghi add/delete/unmapped.                          |
| W09-10-CHUNG-02 | Impact report                                               | **CT**     | impact_report trong state chỉ placeholder, không có module xuất report.                                         | Tạo bounded impact service sau khi có diff binding, giữ rationale/confidence.                               |
| W09-10-CHUNG-03 | A0–A2 trên subset đủ lớn                                    | **CT**     | Graph/BM25 retrieval không phải repair variants; chưa E2E experiment driver.                                    | Chốt variant policy và chạy paired dev30–50 sau nghiệm thu tuần7–8.                                         |
| W09-10-M1-01    | File/range/symbol diff-to-node                              | **CT**     | Không implementation; changed_paths của test selection không đủ hunk mapping.                                   | Dùng source ranges và graph snapshot, kiểm identity; fixture thêm/xóa/sửa file/hàm.                         |
| W09-10-M1-02    | Reverse CALLS/IMPORTS/TESTS/component impact                | **CT**     | E06/E07 có traversal tiền đề, chưa API nhận patch hay affected entities.                                        | Tái dùng graph quan hệ hiện có; component phần chưa có phải ghi unsupported, không bịa edge.                |
| W09-10-M1-03    | Changed API/fan-in/affected callers/tests/components risks  | **CT**     | Retrieval public-risk proxy không biết API bị patch đổi.                                                        | Tính patch-bound risk; từng feature có evidence/available flag, tránh dùng tên feature như semantics proof. |
| W09-10-M1-04    | Impact JSON report                                          | **CT**     | Không analyze_patch_impact producer trong src/scripts.                                                          | Report changed/impacted/unmapped/risk/limits cùng graph/source/patch hashes.                                |
| W09-10-M2-01    | Implement variants A0–A2                                    | **CT**     | Có retrieval modules và tests-only verifier rời, không có configurable repair experiment arms.                  | Driver chọn retrieval/verification policy, dùng cùng model/prompt/budget/timeout/tasks.                     |
| W09-10-M2-02    | A0 BM25 + tests only                                        | **MP**     | E08 BM25 và E11 pytest là tiền đề; chưa BM25→prompt→diff→verification arm.                                      | Nối BM25 vào shared repair runner; record tests-only đúng policy.                                           |
| W09-10-M2-03    | A1 Graph + tests only                                       | **MP**     | Graph + agent/test loop có, nhưng chưa deterministic graph context/arm driver.                                  | Nối M1 context và pin cùng settings với A0; hạn chế tool access không phá fairness.                         |
| W09-10-M2-04    | A2 Graph + tests + type/lint                                | **CT**     | Type/lint runners chưa có nên không thể gọi A2 đầy đủ.                                                          | Dùng runner tuần7–8, thêm exact A2 verification policy và schema assertions.                                |
| W09-10-M2-05    | Chạy30–50 development repair tasks                          | **CT**     | Không repair benchmark results/driver; retrieval dev25 không thay thế.                                          | Pilot nhỏ trước, sau đó paired manifest30–50 với runnable execution configs.                                |
| W09-10-M2-06    | Patch success/false accept proxy/tokens/latency             | **CT**     | Recall/MRR là retrieval metrics, không repair success; chưa trusted repair oracle/proxy pool.                   | Lưu per-task oracle/cost/timing, nêu rõ proxy và denominator; aggregate từ artifacts.                       |
| W09-10-M2-07    | Failure reason có cấu trúc                                  | **MP**     | E12 FailureReason codes và E15 failure_class có; chưa uniform durable repair records/experiment taxonomy.       | Chuẩn hóa stage/code/message/cause/evidence_ref, lưu mọi terminal outcome kể cả timeout.                    |
| W09-10-M3-01    | MCP analyze_patch_impact                                    | **CT**     | E13 không expose tool impact.                                                                                   | Adapter mỏng cho M1 impact service, typed args/error/hash/audit.                                            |
| W09-10-M3-02    | Impact report trong feedback prompt                         | **CT**     | Retry prompt chỉ tests/tail/no-patch, không impact.                                                             | Ghép impact evidence đã kiểm vào feedback, bounded tokens, không biến heuristic thành bắt buộc semantics.   |
| W09-10-M3-03    | Draft Methodology repair/impact/verification                | **CX**     | Có baseline technical docs, không draft paper chứng minh nội dung này.                                          | Nhận/bổ sung Methodology phản ánh đúng phần đã implement và limits.                                         |
| W09-10-M3-04    | Draft Experimental Design datasets/split/baselines/fairness | **MP**     | E09 deterministic split/query/fairness guards và specs; không canonical paper draft/repair protocol thống nhất. | Viết draft từ protocol đã duyệt, phân biệt retrieval vs repair experiments và primary vs oracle.            |
| W09-10-DOD-01   | A0–A2 E2E cùng subset/config                                | **CT**     | Chưa repair arms/driver/required tiers.                                                                         | Nghiệm thu stage trace/config equality và cùng population trước bảng kết quả.                               |
| W09-10-DOD-02   | Ít nhất một bảng kết quả không chỉ demo                     | **CX**     | Bảng retrieval lịch sử có, nhưng không có bảng ablation repair dev theo milestone9–10.                          | Tạo bảng từ runs A0–A2, lưu scripts/JSON/config và failed-task denominator.                                 |

### 5.6. Tuần 11–12 — MCP hoàn chỉnh, security/performance

| ID              | Task                                                   | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                       | Giải pháp để đóng task                                                                                               |
| --------------- | ------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| W11-12-CHUNG-01 | MCP tool surface cần thiết                             | **MP**     | Có11 tools, thiếu run_relevant_tests/verify_patch/impact; envelopes khác nhau giữa servers.                       | Hoàn thiện surface từ services M1/M2, không nhân bản implementation ở server.                                        |
| W11-12-CHUNG-02 | Security guardrails tối thiểu                          | **MP**     | Có safe-relative-path, fixed pytest command, secrets lọc một phần; B04/B05/B12 còn hở.                            | Lease allowlist/read-only default/selector/timeout/output bounds + minimal child env + redaction tests.              |
| W11-12-CHUNG-03 | Performance và incremental measurements                | **MP**     | Có duration fields/full-build stats; chưa incremental service và benchmark report.                                | Đo cold/warm đúng changed-file updater, MCP overhead và cache rate; không gọi load cache là incremental.             |
| W11-12-M1-01    | Incremental graph update changed files                 | **CT**     | E02 full build + E03 ingest snapshot; cache snapshot không reparse delta.                                         | Reparse changed inventory, relink dependencies, tạo version mới; kiểm equivalence với full rebuild.                  |
| W11-12-M1-02    | Reparse/relink/cache invalidate                        | **MP**     | E09 cache keys source/profile/implementation + source guards có; thiếu affected-symbol update.                    | Thêm update transaction và invalidation đúng dependency closure, giữ nguồn truth rõ.                                 |
| W11-12-M1-03    | Cold/warm times/node count/cache hit report            | **MP**     | Builder/trace có timing/hit diagnostics; không report cold-vs-incremental warm theo patch.                        | Repeated bounded benchmark cùng source/delta, ghi distribution và counters thực.                                     |
| W11-12-M2-01    | Export/signature API compatibility                     | **CT**     | api_check fields NOT_RUN, không actual API comparator.                                                            | So exported names/signature baseline/postpatch; policy có exceptions/config, fixtures API delete/change.             |
| W11-12-M2-02    | Forbidden import/layer/cycle theo config               | **CT**     | Schema CONTAINS-cycle validation không kiểm vi phạm do patch hay architecture layers.                             | Repo-config rules với baseline comparison; không áp “mọi CALLS/IMPORTS phải acyclic” mặc định.                       |
| W11-12-M2-03    | A3 graph + graph/API verification                      | **CT**     | Required checks và repair variant driver chưa có.                                                                 | Nối checks vào policyA3 cùng arms A0–A2; lưu check results và unknowns.                                              |
| W11-12-M2-04    | False accept/reject trên pool/mutations                | **CT**     | Chưa labeled patch pool/verification classifier evaluation. Probe skip-only là một finding, không metric dataset. | Labeled synthetic mutants/good patches, independent expected outcomes, TP/FP/FN/TN và denominator.                   |
| W11-12-M3-01    | Tool schemas + error responses hoàn chỉnh              | **MP**     | E13 graph envelope nhất quán; E14 legacy payload/status/errors khác và surface thiếu.                             | Thống nhất typed schema/error taxonomy/audit sau contract review; test MCP transport failures.                       |
| W11-12-M3-02    | Path jail/read-only/allowlist/timeout/audit            | **MP**     | E10 guards không enforce root của E14; timeout không hard maximum, complete audit/secret policy thiếu.            | Shared runner, lease capabilities, read-only mutation gate, bound argv/output, all-tool durable audit.               |
| W11-12-M3-03    | Latency/tokens/calls/read redundancy                   | **MP**     | Duration và counts có logs; LocalChatModel không usage metadata, chưa aggregation/read redundancy report.         | Meter từng actual invocation/tool, aggregate p50/p95/calls/duplicate reads với run config.                           |
| W11-12-M3-04    | Draft Results retrieval/repair/verification/efficiency | **CX**     | Technical/handoff tables không thay paper Results; thiếu repair/verification metrics.                             | Viết từ reproducible runs, giữ thiếu evidence là pending thay vì tự ước lượng số.                                    |
| W11-12-DOD-01   | Tools không chạy command tùy ý                         | **HT**     | E11/E14 executable/argv pytest cố định, shell=False; không tool nhận raw shell command.                           | Đây là điều kiện hẹp: pytest vẫn chạy code target, selectors/root/secrets còn lỗi; không đồng nghĩa sandbox an toàn. |
| W11-12-DOD-02   | Cold/warm và MCP overhead số liệu                      | **CT**     | Không combined incremental/performance benchmark report hiện tại.                                                 | Sau updater, benchmark cùng workload; tách pure service time khỏi transport/process spawn.                           |

### 5.7. Tuần 13–14 — Held-out và failure analysis

| ID              | Task                                             | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                                     | Giải pháp để đóng task                                                                             |
| --------------- | ------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| W13-14-CHUNG-01 | Dừng tuning trước held-out                       | **CX**     | Có dev/heldout guards E09; không frozen release/approval cho final runs.                                                        | Freeze code/profile/config/hash trước mở final outputs; giữ change log.                            |
| W13-14-CHUNG-02 | Held-out evaluation đã chốt                      | **CT**     | Có CLI flag cho retrieval heldout nhưng không artifacts final và chưa repair arms.                                              | Freeze manifest, chạy đúng population/config, lưu outcomes cả failure/timeouts.                    |
| W13-14-CHUNG-03 | Failure analysis có hệ thống                     | **MP**     | Handoffs ghi một số timeout/misses; không final taxonomy10–15 failures/arm.                                                     | Phân loại stage/retrieval/patch/verification/env/model từ saved runs, không đoán từ duration.      |
| W13-14-M1-01    | Retrieval trên held-out                          | **CT**     | E09 hỗ trợ flag/guards; không run evidence ở clone này.                                                                         | Chạy một lần frozen profile sau dev acceptance; không tune bằng gold heldout.                      |
| W13-14-M1-02    | Final Recall/MRR/tokens table                    | **MP**     | Metric/report code E08–09 có; chưa heldout final results/table.                                                                 | Aggregate từ final records với denominator/mapping eligibility và token policy.                    |
| W13-14-M1-03    | Single-file vs multi-file stratification         | **MP**     | Manifest đánh dấu is_multi_file và selectable file threshold; report chủ yếu by-repo, chưa strata table.                        | Group paired tasks theo source-file count, không đổi population sau nhìn kết quả.                  |
| W13-14-M1-04    | Phân tích10–15 retrieval failures                | **CX**     | Inspection shortlist/history10 dev cases không chứng minh10–15 heldout failure analyses.                                        | Annotate failure taxonomy và source/context/gold refs, giữ sampling rule.                          |
| W13-14-M2-01    | A0–A3 held-out                                   | **CT**     | Repair variants/runtime/oracles chưa hoàn chỉnh.                                                                                | Chạy cùng final manifest và fixed config sau A0–A3 pilot.                                          |
| W13-14-M2-02    | Resolved/multi-file/false accept-reject/coverage | **CT**     | Không trusted repair grading/verification confusion matrix/coverage report.                                                     | Dùng oracle đã chọn; static test hints không gọi runtime coverage; báo relevant-case execution rõ. |
| W13-14-M2-03    | Phân tích10–15 repair/verification failures      | **CX**     | Chưa heldout repair artifacts để phân tích; test regression không thay repair failure cases.                                    | Thu outcome đầy đủ rồi classify lỗi stage/model/patch/oracle/env trên sample rule.                 |
| W13-14-M3-01    | Mean/median/std hoặc CI                          | **MP**     | E09 aggregate means và paired bootstrap95% có tests, nhưng chưa final evaluation inputs.                                        | Tái dùng statistical code trên final population, lưu seed/rounds/eligible N.                       |
| W13-14-M3-02    | Paired comparison cùng task                      | **MP**     | E09 kiểm cùng dataset/query/corpus/config và paired stats; current final table chưa có.                                         | Chạy all arms cùng tasks; missing/failed outcomes phải report, không chỉ chọn pairs đẹp.           |
| W13-14-M3-03    | Plots/tables caption/config notes hoàn chỉnh     | **MP**     | E09 report generator và optional graph plot có, không final paper-ready charts/tables.                                          | Sinh figures từ saved records, caption phân biệt rank/packed/native/repair và profile.             |
| W13-14-M3-04    | Threats to Validity đầy đủ                       | **CX**     | External research_design có một phần, nhưng không final draft trong clone; chưa đầy đủ reliability/security của actual runtime. | Viết threats từ thực nghiệm và limitations hiện có, nêu contamination/proxy/tests/native safety.   |
| W13-14-DOD-01   | Mọi số paper có script tái tạo                   | **CX**     | Có generators cho retrieval; không paper/final numbers/raw inputs đầy đủ để kiểm.                                               | Map claim→table→script→artifact/hash; rerun độc lập ít nhất một bảng.                              |
| W13-14-DOD-02   | Không đổi protocol sau held-out                  | **CX**     | Chưa có final freeze/sign-off/heldout run history kiểm chứng.                                                                   | Freeze trước chạy; đổi sau đó phải ghi amendment và exploratory label, không coi pre-registered.   |

### 5.8. Tuần 15–16 — Paper, artifact, submission

| ID              | Task                                               | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                         | Giải pháp để đóng task                                                                                                   |
| --------------- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| W15-16-CHUNG-01 | Artifact tái lập được                              | **MP**     | E20 package script/README/source configs có; thiếu full frozen environments/input/runtime/results/repro acceptance. | Package code + pinned manifests + small demo/evidence; tài nguyên lớn tải bằng scripts/checksum, không commit mọi cache. |
| W15-16-CHUNG-02 | Paper theo evidence                                | **CX**     | Không final paper trong clone để review claims.                                                                     | Nhận paper, kiểm từng claim với artifact; giữ honest unknown/failed outcomes.                                            |
| W15-16-CHUNG-03 | Review chéo/submission                             | **CX**     | Review audit hiện tại không thay peer review nhóm/venue submission.                                                 | Lưu reviewer sign-off, rehearsal và checklist submission.                                                                |
| W15-16-M1-01    | Final Methodology graph/grounding/retrieval        | **MP**     | E01/E06/E19 technical docs khá rõ; chưa final paper section/config thống nhất.                                      | Chuyển thành Methodology có citations/equations/limits theo actual frozen profile.                                       |
| W15-16-M1-02    | Builder/schema migration/unit tests release check  | **MP**     | E21 nhiều graph tests pass; migrations/full release/profile quality chưa acceptance, B10 còn lỗi.                   | Fix findings; test migration/rebuild behavior, clean fixture/resource/optional runtime release checks.                   |
| W15-16-M1-03    | README graph/retrieval modules                     | **HT**     | E20 README mục5 + contracts/handoff docs hướng dẫn graph, SCIP/LSP, context/tokenizer, limits.                      | Tài liệu có không đồng nghĩa clean-install/benchmark đã PASS; sửa các stale historical statements khi release.           |
| W15-16-M2-01    | Final Methodology repair/impact/verification       | **MP**     | Baseline docs E19 có; repair/impact còn thiếu implementation và actual final text.                                  | Hoàn thiện runtime rồi mô tả chính xác policy/evidence/layers và unsupported behavior.                                   |
| W15-16-M2-02    | Cleanup/runner/report release check                | **MP**     | E21 baseline cleanup/timeout tests pass; MCP safety/skip acceptance/durable repair report còn B04–B09.              | Test all terminal paths, protected files, kill tree, evidence retained khi cleanup; không suppress lỗi silently.         |
| W15-16-M2-03    | README repair/verification modules                 | **MP**     | README mục7 và docs giải thích baseline; không manual cho full W7–12 pipeline chưa tồn tại.                         | Bổ sung guide phân first-run/rerun, selectors/outputs/status/limits cho pipeline thực tế.                                |
| W15-16-M3-01    | Final Intro/Abstract/Conclusion/Results/Threats    | **CX**     | Không paper final trong clone.                                                                                      | Tập hợp sections từ evidence và peer review; không tự chèn results chưa đo.                                              |
| W15-16-M3-02    | Docker/devcontainer/install/manifest/repro script  | **MP**     | E20 pyproject, M1 runtime installers, prepare_manifest có; không Dockerfile/devcontainer/full repair repro package. | Chọn execution profile đã duyệt, pin dependency/runtime, one-command demo và one-table reproduction.                     |
| W15-16-M3-03    | Người ngoài nhóm chạy README                       | **CX**     | Không độc lập outsider run record. Audit trên máy người dùng không thay điều kiện này.                              | Nhờ người ngoài clone clean, lưu OS/versions/commands/logs/issues/sign-off.                                              |
| W15-16-M3-04    | Venue/formatting/ethics/artifact/authorship        | **CX**     | Quyết định tổ chức, không có record trong clone.                                                                    | Nhóm chọn venue và kiểm checklist yêu cầu chính thức trước submission.                                                   |
| W15-16-DOD-01   | Máy sạch chạy demo và tái tạo một bảng             | **CX**     | Audit dùng venv có sẵn, không full clean install và không raw benchmark dataset.                                    | Tạo environment mới, chạy setup/demo/repro table từ frozen input; ghi lần chạy independent.                              |
| W15-16-DOD-02   | Paper không overclaim, có evidence cho main claims | **CX**     | Chưa paper final/heldout results để kiểm.                                                                           | Claim-to-evidence audit, phân biệt code có/đã test/mock/real-model/benchmark.                                            |
| W15-16-DOD-03   | Issue list limitations/future work                 | **MP**     | E18 có limitations và report này có findings; chưa issue list release do nhóm quản lý.                              | Chuyển findings/limitations thành issue có owner/priority/acceptance; không coi report là remote issues đã tạo.          |

## 6. Lỗi, sai lệch và blocker

**Chưa sửa các lỗi dưới đây trong phiên audit.** Các reproductions chỉ dùng
throwaway inputs; không sửa repo của người dùng hoặc “sửa test cho xanh”.
Một số lỗi đã có từ main, không phải tất cả do tích hợp M1 gây ra.

### 6.1. Lỗi đã có bằng chứng cụ thể

| ID / mức độ                                            | Vấn đề và evidence                                                                                                                           | Nguyên nhân, tác động                                                                                                                                                                                                                                  | Hướng sửa đề xuất                                                                                                                                                                                                                          |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **B01 — Important, regression được xác nhận**          | HF constructor test FAIL ở`tests/test_hf_model.py:L53`; main test ấy PASS. E16 `hf_model.py:L78`, E21 JUnit.                                 | Diff nguồn bỏ`construction_config=deepcopy(...)` và argument `pipeline(generation_config=...)`. Mock test đọc argument không còn có nên KeyError. Config greedy vẫn được gán trên model/pipeline sau đó: **không đủ căn cứ nói inference thật crash**. | Chốt intended constructor contract; restore explicit config nếu đó là policy, hoặc cập nhật test có chủ đích để kiểm effective behavior với supported Transformers. Kiểm constructor lẫn actual invocation; không bỏ assertion để che lỗi. |
| **B02 — Important, MCP transport FAIL**                | E22 strict smoke dừng ở encoded node resource; audit ghi`NODE_NOT_FOUND` với `vgar%3A...%2F...`. Raw ID lookup pass trong probe.             | `graph_server.py:L135–139/L155–157` nhận encoded ID nhưng không URL-decode trước store lookup. Direct service unit tests bỏ qua serialization nên pass.                                                                                                | Decode đúng một lần tại resource boundary, validate ID, test MCP thật với slash/colon cho cả node/subgraph; chạy lại strict smoke.                                                                                                         |
| **B03 — Important, integration thiếu**                 | E15`prepare.py:L33`, `workflow.py:L54`, `_first_prompt`; E03 serviceL59 và probe `GraphNotReadyError`.                                       | Outer flow đi prepare→repair không mandatory anchors/context. Settings không mang root/tokenizer; clean default env thiếu chúng. Env cũ có thể trỏ target khác. Tools tồn tại không tự đồng nghĩa consumer đã dùng.                                    | Bind repo root/tokenizer/version/task ID theo từng run, deterministic retrieve+validate+render trước model; full prompt budget. Kiểm env cleared/stale.                                                                                    |
| **B04 — Critical, mutation boundary**                  | E14`_root(repo_path)` nhận bất kỳ thư mục tồn tại. Probe chọn alternate dummy root vẫn patch PASS; chỉ dummy folders bị sửa.                 | Path jail chỉ bảo vệ**root do model chọn**, không root được hệ thống cấp. Prompt yêu cầu dùng workcopy là instruction, không security enforcement. Source hash sau run chỉ phát hiện, không ngăn ghi đè.                                               | Server-owned lease root/capability, không cho tùy ý chọn root; read-only default và writable lease explicit. Kiểm root gốc/sibling/link bị từ chối; integrity mọi terminal path.                                                           |
| **B05 — Important, runner không thống nhất**           | E14`execution_server.py:L33–67` khác E11.                                                                                                    | Selector chỉ chặn flags/newlines, không jail`../`/absolute; timeout do caller chọn không upper bound; capture_output không memory bound; không kill descendants như Job runner. Cắt12K output sau khi capture không giới hạn RAM lúc chạy.             | MCP delegate shared M2 runner; max timeout/output/selector policy do server quyết định; actual MCP negative/timeout/output tests.                                                                                                          |
| **B06 — Important, false accept**                      | E11`test_runner.py:L182`; probe JSON: exit0, `passed=0/skipped=1`, overall PASS, testcase NOT_RUN. E15 verifyL41.                            | Gate chấp nhận PASS+mọi fingerprint change; tests/conftest còn sửa được; không reproduce failing oracle trước repair. Có thể skip testcase, sửa assertion hoặc đổi file không liên quan để gate pass.                                                  | Bảo vệ oracle tests/config, baseline reproduction, collect/execute required cases; all-skipped/missing phải VERIFICATION_INCOMPLETE. Kiểm relevant/regression outcomes riêng.                                                              |
| **B07 — Important, diff engine chưa có**               | E14`apply_patch(path,old_text,new_text)` L44–68; E08 gold parser thuộc evaluator.                                                            | Model không tạo unified diff để parser apply: tool thay một đoạn rồi difflib tạo diff sau. Không add/delete hoặc atomic/preflight multi-file.                                                                                                          | Strict repair diff parser + preflight whole patch + lease-bound atomic application/rollback; không nhầm gold parser thành patch service.                                                                                                   |
| **B08 — Important, tiers thiếu**                       | E15 verifyL49–52 type/lint/API/structure NOT_RUN.                                                                                            | Contract fields là chỗ dành sẵn, không check implementation. Không có A2/A3 đầy đủ.                                                                                                                                                                    | Runners/policy cho tuần7–8 trước; API/structural đúng tuần11–12 sau. Giữ NOT_RUN/ERROR khi không thực thi được.                                                                                                                            |
| **B09 — Important, repair evidence không durable**     | E15 verify giữ2000-char tail/dict, workflow cleanup; E12 writer chỉ baseline.                                                                | Không call writer cho repair attempts; không aggregate patch/diff hashes; workdir/db bị cleanup nên paths không còn dùng được. stdout/token/prompt/config không đủ để tái hiện.                                                                        | Pending/final artifacts ngoài workspace, full TestRunResult/EvidenceBundle per attempt, source integrity và aggregate diff, flush trước cleanup kể cả error.                                                                               |
| **B10 — Important, static binding sai**                | E02`builder.py:L1329–1355`, testL121–143; probe external `wrong.module.unique_helper` bị nối tới `src/a.py:a.unique_helper`, confidence0.60. | Explicit import không tìm thấy target lại dùng globally unique name.`.60` đạt default confidence gate, tạo false CALLS và có thể TESTS. Đây là precision issue, không chỉ dynamic call unresolved.                                                     | Không name-fallback khi explicit binding đã thuộc module khác; giữ unresolved/candidate-reference không executable edge. Regression negative cho import ngoài repo.                                                                        |
| **B11 — Important, verdict của CLI run yếu hơn solve** | E15`cli.py:L240–276`.                                                                                                                        | `ok=True` nếu không selector; workspace_modified chỉ print, không kết hợp verdict. Exit0 có thể chỉ nghĩa command xong, không repair verified. Solve cũng thiếu original integrity trên failed/agent-error path.                                       | Một shared verdict policy: không oracle → NOT_RUN/không repair success; require allowed meaningful patch/actual cases/source integrity; check terminal paths nhất quán.                                                                    |
| **B12 — Important, secret protection/logging**         | E13 clientL17 + E16 SECRET_KEYS chỉ3 tên; E17 instrumentationL31–32, phase_loggerL17; CLI debug callbacks.                                   | Những credential env khác có thể truyền tới execution/test. Regex raw chứa`\\b`/`\\s` nên không match Bearer/password text bình thường; phase_logger không redactor.                                                                                   | Minimal allowlisted child env, một shared redactor; sửa escapes và test**dummy** credential trong args/log/errors/env. Không mở/in ra secret thật để kiểm.                                                                                 |

B04–B11 phần lớn có tiền đề từ main; B01 và instrumentation redactor B12
nằm trong các thay đổi sau main. B02 tồn tại tại boundary resource có sẵn;
integration không tự sửa nó. Không quy mọi vấn đề cho code M1.

### 6.2. Sai lệch có thể có chủ đích, cần nhóm quyết định

| Nội dung                              | Thực tế                                                                                                               | Cách xử lý đúng                                                                                                      |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Literal FailingTest trong W5–6        | Schema có Test/Issue; REPRODUCES gắn reported Test vào Issue, execution_verified=false.                               | Duyệt biểu diễn tương đương bằng ADR hoặc sửa contract có review. Không tự thêm node chỉ để tên giống plan.          |
| Public API risk trong default ranking | Feature có diagnostics nhưng weight0.0.                                                                               | Có thể là lựa chọn hợp lý trên dev, nhưng cần evidence/approval thay đổi yêu cầu; không nói risk đang góp vào score. |
| Một model cố định                     | Default Qwen3-4B; tokenizer manifest pin SHA, weights loader không pin SHA. External research_design lại nói32B/vLLM. | Nhóm chọn runtime/protocol duy nhất cho scope16W; không biến model lớn thành prerequisite tự động.                   |
| Context budget                        | Native M1 snippets-only, whole-range; fair evaluator thêm headers/clip80 lines.                                       | Báo rank/packed/native/full-prompt metrics riêng; không lấy7593 tokens lịch sử làm actual whole-prompt cost.         |
| Test links                            | Static direct/transitive hints; chưa runtime coverage/pytest collection.                                              | Gọi đúng là candidates/hints; M2 collect/run và giữ oracle.                                                          |

### 6.3. Blocker chuyển giao/môi trường — không phải tất cả là bug code

| Blocker                            | Bằng chứng hiện có                                                                       | Vì sao chưa hoàn thành / cách xử lý                                                                                                         |
| ---------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Tokenizer assets thiếu             | Manifest E06/E23 có nhưng assets_directory không tồn tại trong clone.                    | Outputs ignored phải provision từ pinned SHA hoặc nhận bundle có checksum. Không tải weights chỉ để chạy retrieval.                         |
| SCIP/LSP runtime thiếu             | Source/configs/installers có; runtime install directories chưa được provision.           | Cài riêng bằng locked npm ci rồi strict smoke; static fallback không được báo là Pyright thật PASS.                                         |
| Raw dev25/manual inspection thiếu  | Các paths E18 đều không nằm trong clone hiện tại.                                        | Nhận release artifact/result JSON kèm config/manifest/source hashes hoặc chạy lại; không copy số cũ vào bảng mới.                           |
| Ba SymPy timeout lịch sử           | E18 ghi task16597/17318/20438 vượt300s; không raw profiling current.                     | Tách build/grounding/traversal/source/tokenization timing trước lựa chọn tối ưu. Không kết luận Jedi là nguyên nhân hiện tại vì Jedi đã bỏ. |
| Graph recall thấp hơn BM25 lịch sử | E18 bảng21 pairs có recall thấp hơn, current v10 không có full25 mới.                    | Review failed anchors/candidates/packing trên dev, so paired same-budget; không tăng tài nguyên để “chữa recall” khi chưa profiling.        |
| Optional tests skipped             | E21 symlink creation không có và Matplotlib chưa cài.                                    | Nghiệm thu lại ở environment có quyền symlink/optional plot; không tính skip là pass.                                                       |
| Clean install chưa test            | E23 venv reuse có PyArrow mismatch và thiếu PEFT/TRL.                                    | Tạo môi trường riêng khi setup được yêu cầu, synchronize pins rồi rerun. Không thay venv cũ trong audit.                                    |
| Real HF repair chưa nghiệm thu     | Không chạy weights/inference; một constructor unit regression, chỉ scripted repair pass. | Sau fix core, real invocation + tool-call + ≥3 small cases có artifacts. Không suy lỗi tài nguyên từ unit test mock.                        |
| Runnable benchmark50–100 chưa có   | Dataset/source retrieval scripts không chạy official failing/regression environments.    | Cần M3 manifest/commands và execution profile riêng; source archive tải được không đồng nghĩa tests chạy được.                              |

### 6.4. Có phải chỉ cần thêm RAM/GPU là chạy toàn hệ thống được?

**Không.** B01/B02/B03/B04/B06 được xác định từ code, unit test, transport và
dummy inputs; các vấn đề đó độc lập với việc có GPU lớn hơn. Thiếu diff
parser, type/lint services, impact hay variant runner là thiếu implementation,
không phải máy thiếu tài nguyên.

Tài nguyên vẫn ảnh hưởng **real LLM inference** và **benchmark execution**:
weights/context không vừa VRAM có thể chậm; dependency/runtime của target có
thể làm benchmark không chạy được. Nhưng audit này không chạy real model,
không đo peak VRAM/RAM/inference tok/s và không xác định hardware là nguyên
nhân của các SymPy timeout. Trước nâng máy/thuê GPU phải đo đúng stage và
chọn profile được duyệt, không lấy kết quả fixture thành estimate toàn benchmark.

## 7. Đề xuất thứ tự hoàn thiện

Đây là **đề xuất**, chưa thực hiện sửa source. Không chuyển toàn bộ P0–P5
vào scope hiện tại. Owner là vai trò M1/M2/M3 theo plan, không phải phân công
mới áp đặt cho thành viên.

| Ưu tiên | Milestone đề xuất                                              | Owner chính                            | Điều kiện nghiệm thu cụ thể                                                                                                                                                                                        |
| ------- | -------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1       | Bảo vệ workspace và trusted oracle                             | M2+M3                                  | Wrong-root/path/link/selector bị reject; protected tests/config không đổi; all-skipped/missing cases không repair PASS; integrity mọi terminal path. Shared runner quản lý timeout/output/descendants.             |
| 2       | Đóng regression HF/resource và binding correctness             | M3 model/MCP + M1 graph                | B01 intended contract được thống nhất/test; encoded node/subgraph strict MCP pass; external imported binding không tạo false internal CALLS/TESTS; full suite không còn failure, skip được khai báo.               |
| 3       | Freeze giao diện/config cho tuần3–8                            | Cả nhóm                                | Quyết định Test-vs-FailingTest/API-risk rõ; model/weights/tokenizer/prompt/retrieval profile và budgets pin; input/output/error contracts thống nhất, không mở rộng schema tùy ý.                                  |
| 4       | Hoàn thành M2/M3 repair tuần7–8                                | M2+M3, M1 hỗ trợ                       | M1 retrieve/validate/render → fixed prompt → model diff → strict parse/preflight → atomic lease apply → failing+relevant tests/type/lint → durable bundle; negative/multi-file/add/delete/timeout cases được kiểm. |
| 5       | Nghiệm thu evidence tuần5–6 và demo tuần7–8                    | M1+M2+M3                               | Pinned dev20–30 retrieval, paired Graph/BM25/tokens +10 inspected cases; riêng ≥3 genuine HF repair cases có model/prompt/diff/test/source integrity. Không dùng scripted cho model quality.                       |
| 6       | Impact + A0–A2 tuần9–10                                        | M1 impact, M2 variants, M3 integration | Diff-to-node/report và policy arms có thật; dev30–50 same-task/config E2E; structured failures/repair oracle/timing/token records.                                                                                 |
| 7       | Incremental + API/structural/A3/security/performance tuần11–12 | Theo ownership plan                    | Full-vs-incremental equivalence, cold/warm stats; configured baseline-aware checks; labeled mutants good/bad; complete MCP guards/audit/latency.                                                                   |
| 8       | Held-out rồi paper/artifact tuần13–16                          | Cả nhóm                                | Freeze trước final runs, A0–A3/retrieval strata/failure taxonomy/CI; claim→script→artifact mapping; clean outsider demo/table repro và submission review.                                                          |

### 7.1. Cách xử lý các task chưa đủ evidence

1. Tìm/nhận đúng artifact cũ trước khi chạy lại. Kiểm source/profile/model/
   dataset hashes; chỉ dùng nếu attribution rõ. Không làm lại việc thành viên
   đã có bằng chứng hợp lệ.
2. Nếu cần chạy mới, dùng **pilot nhỏ** và unique output directory trước
   full evaluation; không chạy held-out để debug prompt/ranking.
3. Timeout cần per-stage profiling và budget. Không tăng timeout/GPU hoặc
   thay resolver nhiều lần khi chưa xác định stage nghẽn.
4. Nếu phải đổi profile/model/budget, ghi ADR/amendment và giữ run cũ; không
   gọi đó là kết quả của protocol cũ.
5. Mọi failure vẫn tạo record hoàn chỉnh: status, stage, reason, stdout/
   stderr, exit, duration, config/hash. Dừng retry lặp không có giả thuyết mới.

## 8. Đọc và tự kiểm tra lại kết quả

### 8.1. Chỉ đọc — không cài, không chạy model/test lại

```powershell
# Chọn repo mới đã tích hợp; không phải hệ thống cũ.
Set-Location 'D:\Project\CAPSTONES\VGAR'

# Kiểm tra HEAD/branch: HEAD mong đợi 73814b8f..., local integration branch.
git branch --show-current
git rev-parse HEAD
git status --short

# Mở báo cáo và checkpoint theo UTF-8.
Get-Content -Encoding UTF8 -LiteralPath '.\Task Status.md'
Get-Content -Encoding UTF8 -LiteralPath '.\PROGRESS.md'

# Runtime/versions/plan hash và test-suite counts đã lưu.
$snapshot = Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-13\snapshot.json' | ConvertFrom-Json
$snapshot.tests | ConvertTo-Json -Depth 8
$snapshot.packages

# Đọc failure/skip cụ thể; không dùng exit của Get-Content làm exit của pytest.
[xml]$junit = Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-13\integrated-tests.xml'
$junit.testsuites.testsuite | Select-Object tests,failures,errors,skipped,time
$junit.testsuites.testsuite.testcase | Where-Object { $_.failure -or $_.error -or $_.skipped } |
    Select-Object classname,name,failure,error,skipped

# Đọc các observations đã tái hiện trên dummy folders.
Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-13\probe-findings.json'

# Node resource lỗi và scope của scripted smoke đã ghi trong log.
Get-Content -Encoding UTF8 '.\docs\audit\2026-10-13\full-mcp-smoke.log'
Get-Content -Encoding UTF8 '.\docs\audit\2026-10-13\scripted-agent-smoke.log'
```

### 8.2. Chạy lại kiểm tra — chỉ khi đã có environment thích hợp

Không có lệnh reinstall trong block này. Kiểm tra venv của **VGAR mới**
trước; nếu chưa có, cài đặt là một bước setup riêng, không giả rằng clone
đã mang theo environment. Venv tái sử dụng ở audit chỉ chứng minh môi trường
đã ghi trong snapshot, không thay clean-install test.

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Chưa có .venv của repo mới. Cần setup environment trước; không tự trỏ sang code repo cũ.'
}
$python = (Resolve-Path -LiteralPath $python).Path
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = (Resolve-Path '.\src').Path

# Kiểm tra source package thực tế được import.
& $python -c "import vgar; print(vgar.__file__)"

# Offline product test suite; test HF ở đây mock loader, không tải weights.
# Chọn thư mục output MỚI để không ghi đè evidence của audit 13/10.
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$runDir = Join-Path '.\artifacts\audit-reruns' $runId
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
& $python -m pytest -q -p no:cacheprovider "--junitxml=$runDir\tests.xml"
$pytestExit = $LASTEXITCODE
Write-Host "pytest exit: $pytestExit"
# Trên source chưa fix: lỗi HF B01 có thể vẫn xuất hiện; không bỏ test để gọi suite PASS.

# Orchestrator/model giả lập; không phải demo năng lực HF.
& $python '.\scripts\smoke_w3_w4_agent.py' --model scripted --keep
$scriptedExit = $LASTEXITCODE
Write-Host "scripted smoke exit: $scriptedExit"

# Real MCP resource gate; hiện tại dự kiến FAIL B02 nếu source chưa sửa.
& $python '.\scripts\smoke_w3_w4_full.py' --strict-resources --keep
$resourceExit = $LASTEXITCODE
Write-Host "strict resource smoke exit: $resourceExit"
```

Những lệnh này có thể cập nhật fixture SQLite/logs khi service initialize,
và tạo artifact/temp directories. Chạy `git status` sau đó, không reset
code của thành viên. Trong audit, test đã cập nhật SQLite fixture; đã giữ
bản sau tests tại [sample_graph-after-tests.db](docs/audit/2026-10-13/sample_graph-after-tests.db)
rồi phục hồi **riêng fixture đó** từ HEAD. Không rollback source changes.

Không chạy các lệnh `--model hf`, provisioning tokenizer/indexer hay
`prepare_manifest` để đọc báo cáo này. Chúng là bước setup/acceptance mới và
có thể dùng network/tài nguyên. Không chạy rerun với output paths của evidence
13/10 nếu muốn giữ nguyên mốc so sánh.

### 8.3. Khi cập nhật trạng thái ở phiên sau

- Giữ ID150 mục, ghi commit/source hash và ngày. Nếu scope được nhóm duyệt
  thay đổi, link ADR; không đổi nghĩa task âm thầm.
- Bổ sung evidence path/command/exit/config rồi mới đổi MP/CX sang HT.
- Đóng bug phải có regression reproduction trước/sau và relevant suite;
  không đóng B01 vì đã xóa test, hoặc B02 vì đã bỏ strict-resource gate.
- Baseline/source inventory và script capture hiện nằm tại
  `docs/audit/2026-10-13`; reruns phải có thư mục/run ID riêng.
- `PROGRESS.md` là checkpoint hành động; `Task Status.md` là đối chiếu
  requirements. Dùng code + evidence hiện tại làm truth khi docs cũ khác nhau.

## 9. Việc đã làm và việc không làm trong phiên này

### Đã làm

1. Clone vào repo mới, lấy cả refs, kiểm ancestry và diff trước tích hợp.
2. Chạy main baseline; giữ generated log; fast-forward có chọn lựa theo
   ancestry, không bỏ implementation main/M1 bằng copy đè.
3. Kiểm inventory toàn bộ260 tracked files, AST/code signatures và150
   checkbox chính; đọc/review graph, evaluation, repair, MCP/model/workflow,
   config, tests, docs và handoff boundaries.
4. Chạy suite sau tích hợp, scripted smoke, strict-resource smoke và
   bounded reproductions; lưu transcript/JUnit/JSON/artifacts.
5. Dùng review đọc-only độc lập cho M1 và repair/MCP theo Superpowers;
   đối chiếu findings với code/evidence, không tin kết luận chưa kiểm.
6. Tạo báo cáo này và [PROGRESS.md](PROGRESS.md). Chỉ thêm audit/report
   helpers/inputs/evidence; không thay thuật toán hoặc product tests.

### Không làm

- Không sửa code sản phẩm cho các bug tìm thấy, không triển khai tasks
  tuần tương lai, không đưa lại changes của các repo cũ đã bỏ.
- Không cài package vào venv cũ; không fine-tune, tải/chạy weights, benchmark
  dev/held-out lớn, thuê GPU, nâng model hay bắt buộc Docker.
- Không thêm branch protection/remote issue/PR, không commit/push.
- Không xác nhận sign-off nhóm, paper/literature ngoài clone hoặc môi trường
  target runnable khi không có evidence.

**Bàn giao:** source integration đang ở HEAD `73814b8f...`; các file mới
`Task Status.md`, `PROGRESS.md`, `docs/audit/2026-10-13/` chưa commit. Các
outputs runtime dưới logs/temp được giữ riêng/ignored. Mốc tiếp theo nên là
review findings và duyệt phạm vi sửa ưu tiên1–5, không bắt đầu lại toàn bộ
graph/retrieval đã có và đã kiểm.
