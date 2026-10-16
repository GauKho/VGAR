# Task Status — VGAR sau tích hợp M1 và M2 tuần 7–8

**Audit nền:** 13/10/2026. **Cập nhật trạng thái:** 16/10/2026, múi giờ Asia/Saigon.
**Repository:** `D:\Project\CAPSTONES\VGAR`.
**Căn cứ chính:** `D:\Project\CAPSTONES\New_task\project_plan_16_weeks.md`.

> **Kết luận hiện hành:** bảy task M2 tuần 7–8 đã **HT trong phạm vi prototype
> Native trên ba trusted fixtures**. Có ba real repairs A/B/C cùng V11/r002 PASS
> ngày15/10 và bản nhúng `M2_week_7_8/` trong VGAR đã được kiểm ngày16/10:
> 236 core tests PASS, 7 integration tests PASS, fake3/3 và ReadSaved3/3 PASS.
> **Chưa nối M2 mới vào MCP/LangChain của M3, chưa chạy ba real generations mới
> dưới layout r002-vgar-i001**. Full VGAR còn1 lỗi HF cũ (571PASS/2SKIP/1FAIL).
> Không đồng nhất hoàn thành M2 với hoàn thành toàn tuần7–8/toàn hệ thống.

### Phạm vi cập nhật ngày16/10/2026

- Giữ đủ150 task IDs. Đối chiếu code/evidence đã có từ M2 W5–6, M1 W7–8 và
  M2 W7–8; không làm lại toàn bộ audit hoặc chạy lại benchmark/model.
- Chuyển7 task M2 W7–8 sang HT và DoD “ít nhất3 diff hợp lệ + verification”
  sang HT **cho ba prototype real repairs đã lưu**. Các mục chung cần luồng
  agent tích hợp, M3 tools/logging và bảo vệ repo ở MCP vẫn MP.
- Cập nhật thêm2 mục W5–6 bị sót trạng thái: BM25 + evaluation ban đầu và bảng
  Graph/BM25 đã có22 paired tasks. Không biến3 SymPy timeouts thành PASS.
- M1-owner review của M2 W5–6 vẫn pending; ranking improvement của M1 và các
  gates bàn giao độc lập không tự được xác nhận. Tuần9–16 giữ trạng thái audit
  trước, không lấy prototype tuần7–8 làm nghiệm thu milestone tương lai.
- Bằng chứng hiện hành: [M1 handoff](docs/handoff/M1_W7_W8_INTEGRATION_2026-10-14.md),
  [M2 tích hợp](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md),
  [real A/B/C manifest](M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json).
  Phần audit13/10 bên dưới được giữ làm lịch sử; các cập nhật có ngày/scope riêng.

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
| M1 W7–8, nhánh `m1-w7-w8-handoff-20261014` | `b8e2461635b81d1ae790445efea5c9757d91700a` | Consumer identity/source/token guards, test-selection diagnostics và ba fixtures handoff; tích hợp14/10 |

Nhánh M1 **đã chứa toàn bộ lịch sử main**. `git merge-base` trả đúng commit
main; `git merge-base --is-ancestor origin/main origin/m1-w5-w6-20261010`
trả exit 0. Vì vậy, không copy đè file riêng lẻ và không dùng `ours/theirs` để
bỏ qua implementation: clone cả refs, tạo nhánh local
`integration/main-m1-w5-w6-20261013`, rồi `git merge --ff-only`.

HEAD ở mốc13/10 là `73814b8f...`; ngày14/10 đã fast-forward tiếp tới
`b8e2461635b81d1ae790445efea5c9757d91700a` (HEAD hiện tại). Tree commit giữ M1;
M2 W5–6 dirty changes và M2 W7–8 nhúng là local additions/changes, chưa commit.
**Không có commit mới và không push/đổi nhánh trên GitHub trong các lần tích hợp này.**
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

Các số260/AST inventory trên là snapshot13/10, **không phải tổng file hiện tại**.
Ngày16/10 đã copy đầy đủ13.071 files/5.252 directories/203.602.347bytes của M2,
kể cả local evidence/hidden/generated files, vào `VGAR/M2_week_7_8/`. Sáu file
relocation có byte gốc và before/after hashes; không xóa/sửa M2 độc lập. Xem
[copy receipt](docs/audit/2026-10-16-m2-w7-w8-integration/copy.json) và
[relocation receipt](M2_week_7_8/integration/relocation.json). Venv copy chỉ local,
không phải portable install hoặc nội dung được yêu cầu push.

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
| 5–6      |       20 |     13 |      4 |      1 |      2 |
| 7–8      |       19 |     10 |      8 |      0 |      1 |
| 9–10     |       20 |      0 |      4 |     14 |      2 |
| 11–12    |       16 |      1 |      8 |      6 |      1 |
| 13–14    |       16 |      0 |      6 |      4 |      6 |
| 15–16    |       16 |      1 |      8 |      0 |      7 |
| **Tổng** |  **150** | **47** | **48** | **25** | **30** |

Các số này là **số dòng checklist được phân loại**, không phải47 features
độc lập hay % đồ án. Mục HT về README/schema có thể thuộc tuần15–16 dù
research experiment của tuần ấy chưa chạy. [report-qa.json](docs/audit/2026-10-13/report-qa.json)
kiểm mốc13/10; bản QA cập nhật ngày16/10 lưu tại `docs/audit/2026-10-16-task-status-update/`.
Không dùng QA cũ thay việc kiểm bảng/IDs của bản mới.

## 3. Evidence mới và giới hạn kiểm thử

Mục3.1–3.3 giữ mốc audit13/10. **Mục3.4 là trạng thái mới hơn**; không đọc các
câu “chưa có assets/chưa chạy HF” của mốc cũ thành kết luận hiện hành cho M2.

### 3.1. Các lượt audit nền ngày13/10 đã thực sự chạy

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

### 3.4. Bằng chứng mới sau M1/M2 W7–8

| Kiểm tra / ngày | Kết quả | Evidence | Giới hạn |
|---|---|---|---|
| M1 handoff14/10 | M1 suite434PASS/1SKIP; handoff3/3PASS; full564PASS/1FAIL/2SKIP | [M1 integration report](docs/handoff/M1_W7_W8_INTEGRATION_2026-10-14.md) | Không chứng minh ranking improvement hay LLM repair |
| Real A/B/C15/10, V11/r002 | **3/3PASS**, cùng model/prompt/runtime, không feedback; A/C post2PASS, B post3PASS và sửa2files | [manifest](M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json) | Trusted development fixtures, không SWE-bench/MCP/independent teammate acceptance |
| Người dùng chạy lại15/10 | ModeRun,3/3case auditsPASS; full234coretestsPASS | [summary](M2_week_7_8/results/manual_abc/20261015T114826234Z-922d5c80/summary.json) | Cùng máy/môi trường; không tự tính thành người ngoài nhóm nghiệm thu |
| M2 bản nhúng16/10 | **236PASS129,27s**, gồm2regressiontests relocation mới | [canonical](M2_week_7_8/results/integration-qualification/final-core-suite/20261016T070502676971Z-3cde4ebc98db/run_record.json) | Offline suite, không real generation |
| Launcher/auditor16/10 | **7PASS8,98s**; ReadSaved3/3, relative paths/tamper/output guards | [receipt](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T071003225820Z-424ac56f6133/result.json) | ReadSaved chỉ audit old real records |
| Native fake A/B/C16/10 | **3/3PASS**, parser/apply/collection/tests/type/lint/integrity thực thi | [fake runs](M2_week_7_8/results/integration-qualification/fake-abc/) | Patch từ fixtures, không dùng làm LLM quality |
| Check16/10 | CUDA True/RTX4050, profile/pinsPASS | [receipt](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T070621462828Z-dd0d36d6e606/result.json) | Không load weights/generate |
| Full VGAR16/10 sau review | **571PASS,2SKIP,1FAIL**,81,14s | [receipt](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T071014208534Z-364e407364e4/result.json), [JUnit](docs/audit/2026-10-16-m2-w7-w8-integration/final-vgar-suite.xml) | FAIL đúng B01 cũ; symlink/Matplotlib skip không phải PASS |
| Ruff/AST/preservation16/10 | PASS; nguồn M2 độc lập và protected VGAR zero changed/missing | [Ruff](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T071231030790Z-8adba3d79c5c/result.json), [static](docs/audit/2026-10-16-m2-w7-w8-integration/static-checks.json), [preservation](docs/audit/2026-10-16-m2-w7-w8-integration/preservation-20261016T071223180685Z.json) | Snapshot trước đợt cập nhật Task Status này; không sửa receipt cũ |

HF M2 dùng `Qwen/Qwen3-4B-Instruct-2507` tại revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, greedy/FP16/device_map=auto, input6000,
output1536/reserve256; timeout generation900s/command120s/global1800s.
V11 template SHA256 `ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8`.
Pin local snapshot không phải independent full weight-byte attestation và không
phải nghiệm thu protocol model32B trong tài liệu nghiên cứu rộng hơn.

Môi trường core riêng `M2_week_7_8/.venv` và HF worker interpreter hiện có được
giữ tách biệt; không trộn tokenizers core0.22.1/HF0.22.2. Supported launcher dùng
source nhúng; bare import qua editable `.pth` cũ chưa là workflow được nghiệm thu.

**Phân biệt:** r002 là runtime của ba real repairs gốc; `r002-vgar-i001` là bản
nhúng có relocation và helper khóa input được điều chỉnh, đã offline-qualified.
Không sửa old canonical/hashes hoặc ghi Check/ReadSaved/fake thành real repairs mới.
MCP calls của M2 standalone vẫn rỗng. Xem [handoff tích hợp](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md).

## 4. Danh mục evidence và vị trí implementation

Bảng task sử dụng các mã E dưới đây để tránh lặp đường dẫn rất dài. Số dòng
code của E01–E23 mô tả audit HEAD `73814b8f` ngày13/10. E24–E33 bổ sung code và
evidence mới hơn. E10–E17 trỏ **luồng legacy ở `src/vgar/`**, không được dùng để
kết luận package mới `M2_week_7_8/src/vgar_m2_w78/` chưa có parser/verification.

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

### Evidence bổ sung ngày16/10

| Mã | File/thư mục | Vai trò và giới hạn |
|---|---|---|
| E24 | [consumer](src/vgar/contracts/consumer.py), [M1 integration](docs/handoff/M1_W7_W8_INTEGRATION_2026-10-14.md), [fixtures](tests/fixtures/w7_w8_handoff/cases.json) | M1 identity/source/token validation, changed-path diagnostics, test links/fallback và ba fixture sources |
| E25 | [V11](M2_week_7_8/prompts/repair_v11.txt), [prompt.py](M2_week_7_8/src/vgar_m2_w78/prompt.py), [presentation](M2_week_7_8/src/vgar_m2_w78/context_presentation.py) | Fixed template/hash/full-chat budget; exact snippets/permissions/counts; không host sửa raw diff |
| E26 | [HF generator](M2_week_7_8/src/vgar_m2_w78/generator_hf.py), [backend](M2_week_7_8/src/vgar_m2_w78/hf_backend.py), [profile](M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/final_profile.json) | Approved pinned Qwen4B prototype, real generation diagnostics/tokens/mask/effective config |
| E27 | [patch.py](M2_week_7_8/src/vgar_m2_w78/patch.py), [workspace.py](M2_week_7_8/src/vgar_m2_w78/workspace.py) | Strict modify-only diff/count/path guards, exact binding, whole-patch Git check/apply, private lease/byte attestation/cleanup |
| E28 | [selection](M2_week_7_8/src/vgar_m2_w78/test_selection.py), [test runner](M2_week_7_8/src/vgar_m2_w78/test_runner.py), [checks](M2_week_7_8/src/vgar_m2_w78/checks.py), [verification](M2_week_7_8/src/vgar_m2_w78/verification.py) | M1 hints+required selectors, actual collection/fallback/regression, bounded pytest/syntax/mypy/Ruff; Native trusted fixtures |
| E29 | [pipeline](M2_week_7_8/src/vgar_m2_w78/pipeline.py), [evidence](M2_week_7_8/src/vgar_m2_w78/evidence.py), [diagnostics](M2_week_7_8/src/vgar_m2_w78/diagnostics.py) | Canonical/bundle/raw/patch/timing/full command outputs/tracebacks; public API/structural fields NOT_RUN vẫn giữ nguyên |
| E30 | [real final manifest](M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json), [user rerun](M2_week_7_8/results/manual_abc/20261015T114826234Z-922d5c80/summary.json) | 3/3 real A/B/C cùngV11/r002, không feedback; B sửa thực tế2productionfiles; không benchmark |
| E31 | [integration report](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md), [launcher](run_m2_abc.ps1), [relocation receipt](M2_week_7_8/integration/relocation.json) | Bản nhúng đầy đủ; r002-vgar-i001; chưaMCP, chưafresh real generation trênlayout mới |
| E32 | [236 core tests](M2_week_7_8/results/integration-qualification/final-core-suite/20261016T070502676971Z-3cde4ebc98db/run_record.json), [integration7](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T071003225820Z-424ac56f6133/result.json), [full VGAR](docs/audit/2026-10-16-m2-w7-w8-integration/commands/20261016T071014208534Z-364e407364e4/result.json) | Suites riêng, không cộng số; VGAR còn B01 |
| E33 | [W5–6 report](docs/handoff/m2-w5-w6/COMPLETION_REPORT.md), [comparison table](results/retrieval/20261013T125307312086Z-6d6b0b52b105/REPORT.md), [acceptance](artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json) | Dev25 source profile13/10,22valid pairs,3SymPytimeouts; owner review còn pending; không gán metrics thành profile HEAD14/10 |

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
| W05-06-CHUNG-03 | BM25 + sơ bộ retrieval evaluation | **HT** | E08–09/E33: dev25 ngày13/10, BM25 25/25, Graph22/25, comparison22pairs; raw JSON/manifest/config/hash/acceptance đã có. | Đã đạt evaluation ban đầu theo gate≥20pairs; giữ3SymPytimeouts, không gọi đây là repair benchmark hoặc số đo profileHEAD mới. |
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
| W05-06-DOD-01 | Bảng Graph vs BM25 R@3/5/10 + tokens | **HT** | E33: comparison REPORT.md và JSON22validpairs, Recall@3/5/10, MRR, packed-context tokens; acceptance PASS của đợt13/10. | Bảng giữ paired denominator22/25,3timeouts và sourceprofile; không ghép lịch sử21pairs hoặc gọi metrics mới của HEAD14/10. |
| W05-06-DOD-02   | Manual-inspect ≥10 tasks                         | **CX**     | E18 ghi10 cases nhưng rubric JSON/raw contexts không có trong clone.                                        | Nhận hồ sơ10 cases hoặc inspect lại theo rubric trên pinned dev runs; cần review độc lập.                       |

### 5.4. Tuần 7–8 — Repair pipeline và verification cơ bản

**Phạm vi HT của M2:** package Native/trusted3fixtures, fixed HF Qwen4B, real
acceptance V11/r002 đã lưu và bản nhúng offline-qualified. Không phải sửa repo
bất kỳ, official SWE-bench hay MCP/LangChain end-to-end. Các mục chung/M3 giữMP
khi thiếu wiring/security của luồng integrated agent; không bắt M2 làm lại core.

| ID              | Task                                                     | Trạng thái | Đã có / thiếu / nguyên nhân                                                                                            | Giải pháp để đóng task                                                                                                  |
| --------------- | -------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| W07-08-CHUNG-01 | Agent sinh unified diff từ issue + context | **MP** | M2 E24–E30 đã validate M1 context, model sinh raw diff và verify3realcases; agent legacy E15 vẫn exact-edit, chưa gọi pipeline mới. | M3 nối mandatory retrieval/consumer và diff-output vào LangChain; không viết lại M2 hoặc dùng scripted smoke thay real repair. |
| W07-08-CHUNG-02 | Apply trong worktree | **MP** | M2 E27 đã có private seed/worktree/lease, whole-patch preflight/apply/attestation; root MCP E14 chưa delegate và B04 còn hở. | Đóng lease/ownership tại MCP và giữ cùng workspace xuyên tool calls; phần M2 trusted-fixture đã HT. |
| W07-08-CHUNG-03 | Tests/type/lint evidence | **MP** | M2 E28–E30 có actual baseline/post/collection/pytest/mypy/Ruff và bundle; legacy verify.py vẫn NOT_RUN cho type/lint. | M3 dùng M2 verification/evidence trong integrated flow; không đổi NOT_RUN của agent cũ thành PASS. |
| W07-08-M1-01 | Payload snippets/IDs/paths/metadata/relevance, versioned | **HT** | E24 consumer/DTO/sidecars validate identity/source/ranges/token counts; M2 đã dùng bundles trong3realrepairs. | Giữ M1 payload unchanged; M2 kiểm full-chat budget riêng; wrapper version không phải public schema_version. |
| W07-08-M1-02 | Cải thiện ranking trên dev, ghi heuristic/tuning | **MP** | E06 có v10/heuristics; M1 handoff14/10 không nghiệm thu ranking improvement, M2 fixturePASS không chứng minh retrieval tốt hơn. | Giữ frozen dev protocol; cần raw paired before/after report, không tự đánh HT từ434/236unit tests. |
| W07-08-M1-03 | Test-to-function links nếu suy ra được | **HT** | E24 direct/caller routes/limits/fallback; E28 tiêu thụ actual changed paths, collection thật và fallback cho caseC. | Static links không phải coverage; giữ required failing selectors và runtime collection/regression. |
| W07-08-M2-01 | Repair prompt template cố định | **HT** | E25 V11 fixed template/hash, permissions/source coordinates/counts, full-chat budget; E30 realA/B/C cùngV11PASS, không feedback. | Đã đạt prototype; giữ version/hashes và old failures. Không khẳng định prompt tối ưu toàn cục hoặc tự chỉnh khi chưa có scope mới. |
| W07-08-M2-02 | Một LLM backend cố định theo protocol | **HT** | E26/E30 approved HF Qwen3-4B Instruct2507, pinned revision, greedy/FP16/auto, fixed budgets; real3/3PASS với observed config/mask/tokens. | HT profile prototype được duyệt, không phải Qwen32B benchmark; chưa independent weight-byte attestation. B01 ở agent backend cũ còn nguyên. |
| W07-08-M2-03 | Validate/parse unified diff | **HT** | E27 strict repair parser kiểm paths/allowlist/protected files, hunk counts/truncation; raw model diff qua parser không host recount/sửa output; E30/E32. | Đã đạt modify-only hiện có; add/delete/rename không hỗ trợ ở profile này. Gold-label parser không thay repair engine. |
| W07-08-M2-04 | apply_patch vào temporary worktree | **HT** | E27 private seed/worktree+lease, exact binding, whole-patch Git check/apply, byte attestation; realB sửa cảpricing.py/invoice.py, cleanup/integrityPASS. | Đã đạt Native3trustedfixtures; repo gốc giữ nguyên. Native không phải OS sandbox hoặc quyền MCP mutation tùy ý. |
| W07-08-M2-05 | Relevant-test selection cơ bản | **HT** | E24/E28 hints từ actual changed paths trên snapshot trước patch, required selectors, actual collection/full-fixture regression; caseC fallback chạy thật. | Đã đạt fixture scope tests; hints không phải measured coverage, chưa mở rộng sang repo ngoài. |
| W07-08-M2-06 | Chạy pytest + typecheck + lint | **HT** | E28/E30 requiredFAIL→PASS, regressionPASS, syntax/mypy/RuffPASS; command/stdout/stderr/exit/time đầy đủ; E32 fullM2=236PASS. | Không cộng số tests giữa suites; API/structural checks vẫn NOT_RUN, thuộc tuần sau; fullVGAR còn B01. |
| W07-08-M2-07 | Bundle patch/failing/relevant/type/lint | **HT** | E29/E30 canonical+EvidenceBundle có applied patch, baseline failing IDs/post outcomes, selection/collection/regression, type/lint, hashes/config/tokens/tracebacks/time. | Đã có durable artifacts ngoài worktree/hash binding; M3 cần trả run/artifact refs. Chưa phải actual MCP logs. |
| W07-08-M3-01 | MCP apply_patch/run_relevant_tests/verify_patch | **MP** | Legacy E14 có exact-edit/run_pytest; M2 E27–E29 đã bàn giao nhưng chưa MCP adapters gọi đúng pipeline/lease/baseline. | Bọc shared M2 services, chốt lifecycle/ownership/public envelopes; actual MCP positive/negative tests. |
| W07-08-M3-02 | Loop retrieve→generate→patch→verify | **MP** | M2 standalone E29/E31 đã one-pass issue/context/diff/worktree/evidence; LangChain workflow E15 chưa dùng flow này. | Nối M1→M2 qua M3, giữ identity/baseline/worktree; chạy integrated smoke riêng, không lấy package copy làm MCP E2E. |
| W07-08-M3-03 | Prompt/model config/calls/latency/token usage logs | **MP** | M2 E26/E29 có prompt/model hashes, token/time/config/mask và commands; mcp_calls rỗng, chưa đầy đủ logging integrated agent. | M3 nối actual tool names/args/results/durations với canonical run_id/usage; không gán standalone logs thành MCP calls. |
| W07-08-M3-04 | Draft Methodology overview/graph/retrieval | **CX** | Có technical/handoff docs E19/E24 và báo cáo M2; chưa nhận paper draft Methodology đã đối chiếu/chốt. | Nhận draft M3 và kiểm claims/config với evidence; không đánh HT paper từ README. |
| W07-08-DOD-01 | ≥3 task diff hợp lệ + verification | **HT** | E30 realA/B/C cùngV11/r002PASS15/10; B sửa2files, required/regression/static/integrityPASS;16/10 ReadSaved3/3 và fake3/3 trên bản nhúng. | HT minimum3prototypecases; chưa real generation mới dưới r002-vgar-i001, chưa MCP/independent teammate/SWE-bench resolved rate. |
| W07-08-DOD-02 | Không ghi repo gốc | **MP** | M2 E27/E30/E31 source/integrity/cleanupPASS, nguồn độc lập preserved13071files; root MCP B04/legacy all-terminal integrity chưa hoàn thiện. | M2 đạt trusted profile; DoD toàn integrated agent còn chờ M3 enforce lease/jail và kiểm mọi terminal path. |

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

**Bảng6.1 là findings của luồng legacy tại audit13/10.** Reproductions khi đó dùng
throwaway inputs. Ngày16/10 M2 mới đã giải quyết nhiều nội dung ở package riêng,
nhưng chưa thay thế MCP/agent legacy; không đánh dấu bug legacy đã đóng chỉ vì
M2 standalone PASS. Không “sửa test cho xanh”.
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

### 6.1.1. Đối chiếu findings với M2 mới ngày16/10

| Findings | Đã có ở package M2 mới | Phần legacy / tích hợp còn lại |
|---|---|---|
| B01 HF constructor | M2 dùng backend riêng E26, real3/3PASS | B01 còn nguyên ở `src/vgar/models/`; full16/10 vẫn đúng1FAIL này |
| B03 context/prompt wiring | E24/E25/E29 mandatory consumer validation + full-chat budget trước generation | Agent legacy chưa gọi pipeline M2 mới; M3 chưa nghiệm thu integration |
| B04–B06 lease/runner/oracle | E27/E28 private lease, bounded commands, protected tests/config, baseline requiredFAIL→PASS, collection/regression | MCP legacy chưa delegate; root/selector/skip-only findings không tự hết |
| B07 repair diff | E27 strict unified diff/exact binding/Git preflight/apply; realB sửa2files | Tool legacy vẫn exact-edit; add/delete/rename ngoài profile M2 hiện tại |
| B08 verification tiers | M2 syntax/mypy/Ruff/tests PASS trong E30 | Legacy verify.py type/lint NOT_RUN; API/structural ở cả prototype vẫn NOT_RUN, chưa tuần11–12 |
| B09 durable evidence | E29/E30 canonical+bundle/raw/diffs/full outcomes/hash/timing tồn tại ngoài worktree | M3 cần nối refs/audit vào agent tools; không lấy standalone mcp_calls rỗng làm MCP evidence |
| B02/B10/B11/B12 | Không sửa các modules liên quan trong đợt nhúng M2 | Giữ findings mở/theo audit cũ; không rerun hoặc tuyên bố đã fix transport/binding/CLI/secrets |

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
| Tokenizer local đã provision, clean clone vẫn cần setup | E33 counter/assets đã verify13/10; E26/E31 profile CheckPASS16/10. | Không còn blocker cho profile local đã kiểm; assets vẫn ignored, không suy máy khác clone là đủ chạy. |
| SCIP/LSP qualification còn thiếu | Source/configs/installers và controlled tests có; chưa có strict runtime acceptance mới trong đợt tích hợpM1/M2. | Kiểm/provision theo profile được duyệt khi cần; không báo static fallback là Pyright thật PASS hoặc suy đã cài từ unit tests. |
| Raw dev25 đã có; manual≥10 còn thiếu | E33 raw BM25/Graph/comparison/acceptance13/10 có; hồ sơ manual rubric≥10 chưa được bàn giao/xác minh. | Không chạy lại dev25 chỉ để thay nhãn; manual review và M1-owner sign-off phải có evidence riêng. |
| Ba SymPy timeouts còn nguyên | E33 Graphfinal13/10 giữ3tasks16597/17318/20438 timeout300s,22pairs/25attempts; không retry. | Muốn fix cần profiling/profile riêng; không gọi do Jedi hoặc do RAM khi chưa có bằng chứng per-stage. |
| Ranking improvement M1 chưa nghiệm thu | E33 có comparison22pairs của sourceprofile13/10; handoff14/10 không chạy mới ranking experiment. | Dùng đúng paired report/denominator; cần before/after evidence cho ranking mới, không lấy fixture repairPASS thành retrieval improvement. |
| Optional tests skipped             | E21 symlink creation không có và Matplotlib chưa cài.                                    | Nghiệm thu lại ở environment có quyền symlink/optional plot; không tính skip là pass.                                                       |
| Clean install chưa test            | E23 venv reuse có PyArrow mismatch và thiếu PEFT/TRL.                                    | Tạo môi trường riêng khi setup được yêu cầu, synchronize pins rồi rerun. Không thay venv cũ trong audit.                                    |
| Real HF prototype đã đạt; MCP/freshlayout chưa nghiệm thu | E30 real3/3V11/r002PASS; E31 layouti001 chỉ offline/fake/ReadSaved/Check, không generation mới. | Giữ prototype acceptance; M3 cần integrated calls/lease/bundle smoke riêng. B01 thuộc agent backend khác, không gán sang M2 worker. |
| Runnable benchmark50–100 chưa có   | Dataset/source retrieval scripts không chạy official failing/regression environments.    | Cần M3 manifest/commands và execution profile riêng; source archive tải được không đồng nghĩa tests chạy được.                              |

### 6.4. Có phải chỉ cần thêm RAM/GPU là chạy toàn hệ thống được?

**Không.** B01/B02/B03/B04/B06 được xác định từ code, unit test, transport và
dummy inputs; các vấn đề đó độc lập với việc có GPU lớn hơn. Thiếu diff
parser, type/lint services, impact hay variant runner là thiếu implementation,
không phải máy thiếu tài nguyên.

Tài nguyên vẫn ảnh hưởng **real LLM inference** và **benchmark execution**:
weights/context không vừa VRAM có thể chậm; dependency/runtime của target có
thể làm benchmark không chạy được. Audit nền13/10 không chạy real model,
không đo peak VRAM/RAM/inference tok/s và không xác định hardware là nguyên
nhân của các SymPy timeout. Trước nâng máy/thuê GPU phải đo đúng stage và
chọn profile được duyệt, không lấy kết quả fixture thành estimate toàn benchmark.
E30 nay có real prototype observations nhỏ và E26 có device/config diagnostics;
chúng vẫn không xác định bottleneck hoặc yêu cầu tài nguyên của toàn SWE-bench.

## 7. Đề xuất thứ tự hoàn thiện

Đây là **đề xuất còn lại**, chưa tự thực hiện các bước M3/benchmark sau đây.
Core M2 prototype đã hoàn thành, không lập lại việc đã có. Không chuyển toàn bộ P0–P5
vào scope hiện tại. Owner là vai trò M1/M2/M3 theo plan, không phải phân công
mới áp đặt cho thành viên.

| Ưu tiên | Milestone đề xuất                                              | Owner chính                            | Điều kiện nghiệm thu cụ thể                                                                                                                                                                                        |
| ------- | -------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 | Đưa workspace/oracle guards M2 vào MCP | M3 chính, M2 hỗ trợ | M2 trusted pipeline đã có lease/required-case/protected-file/bounded runner; MCP phải delegate và qua wrong-root/path/selector/skip/timeout/integrity tests. |
| 2       | Đóng regression HF/resource và binding correctness             | M3 model/MCP + M1 graph                | B01 intended contract được thống nhất/test; encoded node/subgraph strict MCP pass; external imported binding không tạo false internal CALLS/TESTS; full suite không còn failure, skip được khai báo.               |
| 3       | Freeze giao diện/config cho tuần3–8                            | Cả nhóm                                | Quyết định Test-vs-FailingTest/API-risk rõ; model/weights/tokenizer/prompt/retrieval profile và budgets pin; input/output/error contracts thống nhất, không mở rộng schema tùy ý.                                  |
| 4 | Nối agent M3 với pipeline M2 đã hoàn thành | M3 chính, M1/M2 hỗ trợ | Dùng E24–E29, không viết lại prompt/parser/apply/verifier; giữ cùng run/lease/baseline và test actual MCP/LangChain retrieve→generate→patch→verify. Add/delete/rename ngoài profile phải có scope mới. |
| 5 | Đóng các gate bàn giao/đánh giá còn lại tuần5–8 | M1+M3, M2 hỗ trợ | E33 đã có22retrievalpairs và E30 đã có3realrepairs; còn manual≥10, M1-owner review, independent teammate và integrated MCP smoke. Fresh layout real Run chỉ khi chủ ý nghiệm thu mới, không lặp benchmark cũ. |
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

# HEAD hiện tại b8e2461635b81d1ae790445efea5c9757d91700a; M2 nhúng chưa commit.
git branch --show-current
git rev-parse HEAD
git status --short

# Mở báo cáo và checkpoint theo UTF-8.
Get-Content -Encoding UTF8 -LiteralPath '.\Task Status.md'
Get-Content -Encoding UTF8 -LiteralPath '.\PROGRESS.md'

# Snapshot này là LỊCH SỬ ngày13/10, không phải packages/counts mới nhất.
$snapshot = Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-13\snapshot.json' | ConvertFrom-Json
$snapshot.tests | ConvertTo-Json -Depth 8
$snapshot.packages

# Full VGAR mới nhất:571PASS/1FAIL/2SKIP; Get-Content thành công không có nghĩa pytest PASS.
[xml]$junit = Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-16-m2-w7-w8-integration\final-vgar-suite.xml'
$junit.testsuites.testsuite | Select-Object tests,failures,errors,skipped,time
$junit.testsuites.testsuite.testcase | Where-Object { $_.failure -or $_.error -or $_.skipped } |
    Select-Object classname,name,failure,error,skipped

# Full M2 bản nhúng:236PASS; đây là đọc evidence, không chạy test/model lại.
$m2 = Get-Content -Raw -Encoding UTF8 '.\M2_week_7_8\results\integration-qualification\final-core-suite\20261016T070502676971Z-3cde4ebc98db\run_record.json' | ConvertFrom-Json
$m2 | Select-Object status,complete,duration_ms
$m2.stages.pytest.stdout

# Ba real repairs đã lưu dưới cùngV11/r002; không nhầm với inference mới sau tích hợp.
$final = Get-Content -Raw -Encoding UTF8 '.\M2_week_7_8\results\final_acceptance\2026-10-15-v11-r002\run_manifest.json' | ConvertFrom-Json
$final | Select-Object status,prompt_version,runtime_revision,feedback
$final.cases | ConvertTo-Json -Depth 5

# Đọc các observations đã tái hiện trên dummy folders.
Get-Content -Raw -Encoding UTF8 '.\docs\audit\2026-10-13\probe-findings.json'

# Node resource lỗi và scope của scripted smoke đã ghi trong log.
Get-Content -Encoding UTF8 '.\docs\audit\2026-10-13\full-mcp-smoke.log'
Get-Content -Encoding UTF8 '.\docs\audit\2026-10-13\scripted-agent-smoke.log'
```

### 8.2. Chạy lại kiểm tra — chỉ khi đã có environment thích hợp

Với M2 nhúng: `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_m2_abc.ps1 -Mode Check`
chỉ kiểm profile; `-Mode ReadSaved` audit old records, `-Mode Run` mới generation.
Xem [hướng dẫn tích hợp](docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md) để không
dùng bare imports/venv cũ hoặc lẫn old records thành nghiệm thu layout mới.
Block bên dưới là kiểm legacy VGAR/MCP, không thay thế runner M2 mới.

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

### 9.1. Lịch sử audit ban đầu ngày13/10

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

**Bàn giao ở mốc13/10:** source khi đó ở HEAD `73814b8f...`; các file mới
`Task Status.md`, `PROGRESS.md`, `docs/audit/2026-10-13/` chưa commit. Các
outputs runtime dưới logs/temp được giữ riêng/ignored. Mốc tiếp theo nên là
review findings và duyệt phạm vi sửa ưu tiên1–5, không bắt đầu lại toàn bộ
graph/retrieval đã có và đã kiểm.

### 9.2. Cập nhật hiện hành ngày16/10

- HEAD `b8e246...`: M1 W7–8 đã tích hợp14/10; M2 W7–8 nhúng16/10, giữ nguyên
  bản M2 độc lập và old evidence. Xem E24–E32, không dùng snapshot13/10 làm
  inventory/testing hiện tại.
- Bảng đã cập nhật10task states:7M2 W7–8 +1DoD prototype W7–8 +2mục tổng hợp
  W5–6. Tất cả150IDs còn đủ; tổng **47HT/48MP/25CT/30CX**. Không tính % đồ án.
- Owner gates/MCP/full system còn mở được nêu rõ; không sửa status research
  tuần1–2 hoặc tự nghiệm thu tuần9–16 từ kết quả ba fixtures.
- Phiên cập nhật tài liệu này chỉ đọc code/receipts và sửa `Task Status.md`,
  nối checkpoint/QA; không chạy lại model/full suite/benchmark, không sửa code
  hoặc old manifests/canonical, không commit/push.
- [Bản trước khi cập nhật](docs/audit/2026-10-16-task-status-update/Task_Status.before.md)
  được giữ; QA mới kiểm IDs/status totals/table columns/local links và evidence refs.
- Preservation receipt ngày16/10 ở E31 là snapshot **trước** yêu cầu sửa tài liệu
  này. Task Status/PROGRESS nay thay đổi có chủ đích; không sửa expected hashes
  của receipt cũ hoặc coi document drift đó là regression code M2.
