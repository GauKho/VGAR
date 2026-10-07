# Review VGAR sau tích hợp M1, M2, M3 — nghiệm thu tích hợp tuần 3–6

Ngày kiểm tra: **06/10/2026**. Repository: `D:\Project\CAPSTONES\VGAR`.

**Điều chỉnh phạm vi theo người dùng:** Tuần 1–2 là research của nhóm, không cần tích hợp vào repo. Báo cáo và kế hoạch sửa chỉ đánh giá lỗi/tiến độ tích hợp tuần 3–6; không coi thiếu tài liệu research trong checkout là task chưa hoàn thành của VGAR. Các schema/contract hiện có vẫn được dùng làm đầu vào kỹ thuật. Giữ tên file và artifact audit cũ để bảo toàn liên kết/bằng chứng.

Commit được kiểm tra: `b39e0dbf87645d39b9a68e87b19d0655df264a05`, branch local `main`. Git status và diff ban đầu sạch. Không pull, commit, push hoặc sửa code sản phẩm trong lần review này.

## 1. Kết luận ngắn gọn

**Các module đã được ghép vào cùng repository, nhưng chưa hoàn thành nghiệm thu tích hợp tuần 5–6.** Không phải chỉ thiếu tài nguyên: đã tái hiện các lỗi logic/contract thực sự bằng fixture nhỏ, không cần GPU hay model.

- Bộ test hiện có: **196 passed, 1 skipped**, pytest exit code `0`; wrapper ghi duration `72578 ms`, pytest báo `69.25 s`.
- BM25 đã có **hai run thật, mỗi run hoàn tất 25/25 task**; không phải chỉ demo synthetic.
- Graph API nội bộ có grounding, overlay, traversal/ranking và token packing.
- Graph runner đã có, nhưng các run lưu trước đây chưa chứng minh được Graph evaluation hoàn tất trên 20–30 task.
- Comparator đọc sai shape của Graph runner; MCP thiếu hai tool grounding/context của tuần 5–6.
- Builder rollback và retriever xác minh snapshot không đồng bộ; một file bị bỏ có thể làm retrieval cả task thất bại.
- Có vấn đề source scope: cache source SWE-bench bị coi là source của VGAR khi index chính VGAR; workspace/hash cũng tính cả dữ liệu thí nghiệm.
- Có lỗi inheritance tạo self-loop, coverage thiếu với conditional/duplicate definitions, cache integrity chưa đủ, và boundary ghi file qua MCP chưa buộc vào workspace được cấp phép.

**Test pass không đồng nghĩa với đã đạt Definition of Done.** Suite hiện tại chưa có các regression test nối đúng những ranh giới vừa nêu.

Kế hoạch sửa: [2026-10-06-fix-vgar-integration-week-1-6.md](../superpowers/plans/2026-10-06-fix-vgar-integration-week-1-6.md). **Chưa triển khai; chờ bạn xác nhận.**

## 2. Căn cứ và giới hạn

### 2.1 Tài liệu làm chuẩn

1. [project_plan_16_weeks.md](../../../New_task/project_plan_16_weeks.md), yêu cầu tích hợp tuần 3–6. Research tuần 1–2 không thuộc nghiệm thu repo.
2. [VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md](../../../New_task/VGAR_MCP_Contract_Freeze_Plan_No_Schema_Versioning.md).
3. Code, fixture và artifact hiện tại của VGAR; tài liệu handoff 01–05/10 chỉ được dùng đúng ngày/snapshot của chúng.

Thư mục thực tế là `New_task`, không phải `New_teak`.

Tuần 7 trở đi **không bị tính là thiếu của tuần 5–6**: full repair pipeline, type/lint/API verification hoàn chỉnh, patch impact, incremental graph, A0–A3 repair ablation, held-out repair evaluation, fine-tuning, full MCP performance/security. Một số code repair đã có sớm; review chỉ kiểm tra các hồi quy và yêu cầu source/workspace/contract đã áp dụng từ trước.

Không thay proposal cũ bằng plan mới, cũng không thực hiện plan đang đóng băng của `vgar_mcp_mvp`. Đây là audit riêng theo plan mới mà bạn đang dùng cho VGAR.

### 2.2 Đã kiểm tra những gì?

| Nhóm | Kiểm tra |
|---|---|
| Git và môi trường | Status/diff/history/HEAD, Python và phiên bản dependency có sẵn; không cài mới |
| Graph M1 | Builder/rollback/IDs/resolution, grounding/overlay, retrieval/snapshot/tokenizer, SQLite service và port |
| Evaluation M2 | BM25/chunks, gold diff mapping, rank/packed metrics, adapter, archive/tree cache, Graph runner và comparator/report |
| M2 tuần 3–4 | Workspace, fingerprint, pytest wrapper, baseline, evidence writer/contracts |
| M3 | MCP server/client/registry/envelope/resources, settings/model loader, agent/workflow/CLI ở các ranh giới liên quan |
| Tài liệu/packaging | README, docs/specs/handoff, manifest, pyproject, cấu hình YAML và các đường dẫn evidence |
| Test | Chạy toàn bộ `tests` bằng wrapper bounded, không chạy model; thêm probe nhỏ ngoài source tree |
| Kết quả đã lưu | Đọc các `result.json` run-level; không quét toàn bộ snippets hay chạy lại 25 task |

Đây là review module/luồng/giao diện và kiểm thử có chọn rủi ro; không phải chứng minh hình thức rằng mọi dòng code đều không có lỗi. Không chạy inference thật, harness grading, hay benchmark lớn trong audit. Các vấn đề chưa tái hiện lại trên task thật được ghi rõ là lịch sử/rủi ro.

### 2.3 Môi trường kiểm thử

VGAR chưa có `.venv` riêng tại thời điểm kiểm tra. Python ở CAPSTONES `.venv` là 3.13 và thiếu Jedi. Để không cài lại hoặc thay môi trường của bạn, audit dùng interpreter có sẵn:

```text
D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe
Python 3.11.6
pytest 8.4.2; jedi 0.20.0; mcp 1.30.0
langgraph 1.2.11; pydantic 2.13.5; tree-sitter 0.25.2
```

**Chỉ mượn interpreter**, imports/source và pytest cwd là VGAR; không sửa hoặc chạy lại hệ thống cũ. Đường dẫn Python trong evidence không có nghĩa đang kiểm thử code của repo cũ.

Một test skip: `tests.m2.test_workspace::test_external_symlink_rejected`, vì môi trường không cho tạo symlink. Vì vậy không tuyên bố đã kiểm chứng rejection symlink bằng thực nghiệm trên máy này.

## 3. Luồng hiện tại và điểm đứt

```text
                          EVALUATION NGOẠI TUYẾN
SWE-bench manifest + base_commit
  ├─ archive source → AST chunks → BM25 rank ──────────────┐
  └─ archive → Python tree → M1 graph                    │
                  ↓                                     │
             task overlay → anchors → candidates        │
                  ↓                                     │
             M2 graph_rank adapter                      │
                  └─ shared rank/packed scoring ← gold patch (chỉ evaluator)
                           ↓
                  per-task JSON + run summary
                           ↓
                  comparator → REPORT.md
                  [F01: arms bị đọc thành arm]

                          MCP / LANGCHAIN
Issue → client → Graph MCP
                  ├─ search_symbols / get_callers / get_callees: có
                  └─ find_task_anchors / get_related_context: chưa expose [F02]

M1 graph build bỏ failed file → retriever so với file set trên đĩa
                  └─ nhận nhầm file đã biết bị bỏ là source mới [F03]

Index chính VGAR → thấy data/repositories/trees/.../*.py [F04]
Copy/hash chính VGAR → đọc cả data/results trước timeout [F05]
```

Lưu ý: chạy retrieval không tạo patch và không đo repair success. Graph evaluation gọi API nội bộ M1, **không đi qua MCP**. Agent hiện tại dùng LangChain/LangGraph nhưng chưa tự động có grounding/context chỉ vì các file M1 đã được copy vào repository.

## 4. Các lỗi/gap đã xác định

Mức ưu tiên: **P0** chặn core integration hoặc có nguy cơ ghi sai source; **P1** ảnh hưởng kết quả/khả năng tái lập/hoàn thành tuần 6; **P2** metadata/tài liệu/chất lượng phụ. Đây là priority sửa, không phải thang CVSS.

Evidence bổ sung nằm tại [artifacts/reviews/2026-10-06-w1-w6](../../artifacts/reviews/2026-10-06-w1-w6). Trong các probe, `issue_reproduced=true` nghĩa **đã tái hiện lỗi**, không phải đã sửa. Exit `0` của diagnostic driver chỉ nghĩa chạy xong phép chẩn đoán.

### F01 — Graph producer và comparator bất đồng `arms`/`arm` — P0

- Producer: [run_graph_retrieval.py](../../scripts/run_graph_retrieval.py), `summary_row` khoảng dòng 160; xuất `arms: {graph: ..., graph_f2p: ...}`.
- Consumer: [compare.py](../../src/vgar/evaluation/retrieval/compare.py), `_validate_graph_run()` dòng 34; đọc `t.get('arm')`.
- Hậu quả: một summary Graph hợp lệ bị từ chối là BM25-style, ngăn bảng Graph vs BM25.
- Tái hiện: dùng summary thật của `pydata__xarray-3993` từ run ngày 05/10; lỗi `field 'arm' missing`.
- Nguyên nhân suite không bắt: `tests/m2/test_graph_arm.py::test_compare_runs_end_to_end_and_report` tự thêm `arm='graph'` vào fixture, trong khi runner thật không thêm.
- Evidence: `probes.json`, `F01-producer-consumer-arms`.

Run thật dùng trong probe còn `complete=false`; không lấy nó làm benchmark final. Probe chỉ kiểm tra trực tiếp validator trên summary đã được ghi, không bypass `_load()` để giả vờ đã so sánh thành công.

### F02 — Thiếu cầu nối MCP/LangChain cho retrieval tuần 5–6 — P0 về milestone

- [graph_server.py](../../src/vgar/mcp/servers/graph_server.py) chỉ đăng ký `search_symbols`, `get_callers`, `get_callees`.
- [port.py](../../src/vgar/graph/port.py), service adapter và required-tool registry vẫn là W3–W4.
- `TaskAnchorFinder` và `GraphContextRetriever` tồn tại nhưng không tự xuất hiện trong MCP.
- Tái hiện: gọi `mcp.list_tools()` trên server đang dùng, chỉ có ba tool trên.
- Hậu quả: flow tuần 5–6 `issue → anchors → context → display` chưa hoạt động qua MCP/LangChain. Các script CLI riêng M1 không thay thế deliverable này.
- Evidence: `probes.json`, `F02-mcp-tools`.

Đây là phần **chưa triển khai tích hợp**, không phải kết luận API nội bộ M1 không làm được retrieval.

### F03 — Rollback file và snapshot verification không cùng quy tắc — P0

- [builder.py](../../src/vgar/graph/builder.py), `_extract_file()` khoảng dòng 302: bỏ nodes/edges/module của file failed.
- [retrieval.py](../../src/vgar/graph/retrieval.py), `_verify_snapshot()` dòng 298: đòi toàn bộ `.py` trên đĩa trùng đúng File nodes.
- File bị bỏ vẫn nằm trên đĩa, vì thế được báo nhầm là `added`/source đổi. Rebuild theo cùng logic tiếp tục thất bại.
- Tái hiện: `bad.py` bị lỗi extraction synthetic; `good.py::ok` còn hợp lệ; retrieval `ok` vẫn nhận `GraphError: Source file set differs ...`.
- Rollback còn để `symbols_by_qualified_name` chứa ID đã bị xóa, làm trạng thái nội bộ không nhất quán; hai guard missing-module chưa phải transaction rollback đầy đủ.
- Evidence: `probes.json`, `F03-rollback-vs-snapshot`.

**Không sửa bằng bỏ kiểm hash/snapshot.** Cần quản lý failed-file inventory/hash và transaction rollback thống nhất, vẫn phát hiện file thật sự đổi sau khi build.

### F04 — Cache source SWE-bench bị đưa vào graph của VGAR — P1, chặn chạy trên chính VGAR

- `PythonGraphBuilder._discover_python_files()` dòng 160 dùng `rglob('*.py')`; ignore list không có các cache path của evaluation mới.
- Tái hiện fixture: graph chứa cả `src/pkg/live.py` và `data/repositories/trees/foreign/pkg/alien.py`.
- Khi target là VGAR có nhiều source tree benchmark, graph có thể trộn code từ repository khác, tăng node/edge/RAM và làm query không còn chỉ đại diện application source của target.
- [runtime.py](../../src/vgar/agents/runtime.py) `index_repo()` không truyền source scope riêng để tránh điều này.
- Evidence: `probes.json`, `F04-F05-cache-scope`.

Trên một source tree SWE-bench riêng không chứa các cache này, lỗi pollution này không tự xảy ra. Không được quy mọi MemoryError của Graph runner cho F04.

### F05 — Workspace/fingerprint tính cả cache; pre-test work không có timeout/evidence — P1

- [workspace.py](../../src/vgar/repair/workspace.py), `_source_files()` không loại `data/` hay `results/` theo các operational path của VGAR.
- Archive/graph/result lớn có thể làm `create_workspace()` vượt giới hạn **16 MiB/file, 256 MiB tổng**, dù code target nhỏ.
- [record_m2_test.py](../../scripts/record_m2_test.py) gọi `fingerprint_source(ROOT)` trước `begin_run()` và trước wrapper timeout. `--timeout-seconds 240` không giới hạn bước hash này.
- Tái hiện: synthetic cache nằm trong fingerprint; fixture với size limit hạ xuống 512 bytes bị chặn bởi cache 1024 bytes, không cần tạo archive lớn thật.
- Quan sát audit: lần dùng recorder ban đầu chưa tạo pending JSON trong lúc fingerprint; đã hủy riêng invocation đó, sau đó wrapper trực tiếp chạy suite xong.
- Evidence: `probes.json`, `F04-F05-cache-scope`, `F05-workspace-limit`; `interrupted-recorder.json`.

Không đo được tổng size/thời gian hash cache thật, nên không đưa ra số GB hay thời gian tự suy đoán. Cần source scope theo repository/profile; **không blanket-ignore mọi package tên `data`** của repo khác.

### F06 — M1 extraction và M2 function identities khác coverage — P1

- M2 [chunks.py](../../src/vgar/evaluation/retrieval/chunks.py) dùng AST, đi vào conditional blocks và phân biệt duplicate definitions bằng `@definition:start:end`.
- M1 `_walk_scope()` chỉ xử lý trực tiếp class/function/import; không đi vào các `if/else` scope ở module/class để tìm definitions.
- Duplicate function cùng qualified name tạo cùng M1 node ID; `_add_node()` báo duplicate, rollback **cả file**, không chỉ một function.
- Tái hiện 1: hai `def choose()` cùng module → M1 0 function và failed file; M2 2 identities.
- Tái hiện 2: hai conditional definitions trong if/else → M1 0 function, M2 2 identities.
- Hậu quả: mất anchors/functions/retrieval coverage; F03 có thể khuếch đại thành cả task fail. Không nên đổ toàn bộ mismatch cho adapter M2.
- Evidence: `probes.json`, hai entry `F06-*`.

Gold từ developer patch là **changed-code proxy**, không phải tập relevance đầy đủ. New-file/new-function và unmappable labels cần coverage/denominator rõ ràng, không biến mọi missing label thành recall=0 tùy tiện.

### F07 — Tree/cache integrity chưa đủ — P1

- [graph_arm.py](../../src/vgar/evaluation/retrieval/graph_arm.py), `extract_python_tree()` dòng 32: nếu marker đúng repo/commit thì trả metadata cũ, không kiểm tree bytes hiện tại.
- Tái hiện: đổi `return 1` thành `return 999` trong tree fixture; extractor vẫn trả tree hash cũ.
- [run_graph_retrieval.py](../../scripts/run_graph_retrieval.py), `load_or_build_graph()` dòng 38: graph cache key chỉ gồm builder.py hash/repo/commit/Jedi flag; không bao quát resolver/schema/dependency/source tree fingerprint, không xác minh hash của cache pair khi reuse.
- Nguy cơ: rebuild graph từ tree đã đổi nhưng chấm gold/BM25 trên archive gốc; stale edge sau resolver change; provenance không còn đủ để so sánh.
- Evidence: `probes.json`, `F07-tree-integrity`; graph cache key được xác nhận bằng source inspection, chưa chủ động corrupt cache thật.

### F08 — Capped rank nhưng giữ packed metrics uncapped — P1 về cách diễn giải

- [compare.py](../../src/vgar/evaluation/retrieval/compare.py), `cap_bm25()` dòng 66: chỉ rescore rank; context_tokens/packed coverage giữ từ full ranking.
- Đây là behavior được unit test hiện có chủ động giữ, **không phải phép tính ngẫu nhiên sai**. Vấn đề là report đặt cùng cột `bm25@cap`, khiến dễ hiểu nhầm cả rank lẫn packed đều dùng top-cap candidates.
- Tái hiện cap=1: rank không thấy gold, nhưng packed gold coverage vẫn 1 từ candidate thứ hai ở uncapped context.
- Cap mặc định100 còn không được đối chiếu với `max_candidates` Graph khi bạn đổi cấu hình.
- Evidence: `probes.json`, `F08-cap-scoring`; tests `test_cap_bm25_only_changes_rank_metrics`.

Sửa theo protocol rõ ràng: primary full-rank BM25 vs bounded Graph, capped-rank chỉ sensitivity; hoặc nếu chọn capped system thì phải repack cùng candidate set. Không đổi cách tính chỉ để số Graph đẹp hơn.

### F09 — Detector property setter nhận nhầm mọi dotted decorator — P2

- [builder.py](../../src/vgar/graph/builder.py), `_is_setter_decorator()` dòng 188: chỉ cần có dấu `.` là trả True.
- `@app.get('/users')`, `@pytest.mark.parametrize(...)` cũng được coi là setter.
- Hậu quả: suffix `.setter` và `renamed_duplicate_count` sai semantics; gây khó hiểu node ID/provenance. Chưa chứng minh tất cả route retrieval thất bại vì lỗi này, vì qualified_name vẫn có thể match.
- Evidence: `probes.json`, `F09-setter-rule`.

### F10 — Inheritance resolve sai khi class mới che tên imported base — P0

Ví dụ Python hợp lệ:

```python
from pkg.base import A
class A(A):
    pass
```

- Base expression được đánh giá theo binding trước khi class mới gán vào tên `A`.
- Builder hiện đã ghi class mới vào `module.definitions['A']`, rồi `_link_inheritance()` dùng `_resolve_symbol()` lấy chính class mới làm base.
- Kết quả `INHERITS A → A`; frozen validator đúng khi từ chối self-loop.
- Tái hiện fixture hai file: `GraphValidationError: edges[8] must not be a self-loop`.
- Evidence: `extra-probes.json`, `F10-shadowed-inheritance`; code `_link_inheritance()` dòng781, `_resolve_symbol()` dòng1013.

Không sửa bằng nới validator cho phép self inheritance. Cần binding-aware resolution; nếu không resolve tin cậy thì để unresolved kèm diagnostic, không tạo edge giả.

### F11 — MCP write root chưa buộc vào workspace; envelope/execution khác M2 wrapper — P0/P1

- [repository_server.py](../../src/vgar/mcp/servers/repository_server.py), `_root()` chỉ đòi path tồn tại. `apply_patch(repo_path, ...)` nhận root do model cung cấp; path jail chỉ tương đối với root đó, không chứng minh root là leased workspace.
- Prompt bảo model dùng workspace không phải một guard ở server. Final source hash chỉ phát hiện **sau khi** source bị sửa, không ngăn được write.
- Tái hiện: tool nhận đường dẫn synthetic `simulated-original` thay vì `simulated-workspace`, vẫn sửa file và trả PASS. **Không sửa repository thật của bạn.**
- Response patch hiện không có common `data/error/metadata`; validate bằng `ToolResponse` thất bại thiếu metadata. Health/read còn status `OK` trong khi common contract dùng PASS/FAIL/ERROR/NOT_RUN.
- [execution_server.py](../../src/vgar/mcp/servers/execution_server.py) dùng `subprocess.run` riêng, không dùng M2 `run_tests`: thiếu đầy đủ command/duration/JUnit, selector traversal checks và process-tree/output guards của wrapper. Không chủ động chạy selector thoát root trong audit.
- Graph tools có audit/envelope; repository/execution tools chưa dùng cùng `_tool/run_tool` wrapper.
- Evidence: `extra-probes.json`, `F11-mcp-write-root`; source inspection hai MCP servers.

Đây là tối thiểu để không ghi vào repo gốc và giữ contract trước tuần6, **không yêu cầu triển khai toàn bộ security của tuần11–12**.

### F12 — Evaluation fingerprint bỏ sót tests nested — P2 về provenance

- [evidence.py](../../src/vgar/evaluation/retrieval/evidence.py), `source_fingerprint()` dòng39 chỉ `tests/*.py`.
- Thay đổi `tests/m2/...`, `tests/unit/...`, fixtures không nằm trong digest này.
- Probe xác nhận `tests/m2/test_graph_arm.py` và `tests/unit/test_workflow.py` không có trong danh sách fingerprint.
- Evidence: `extra-probes.json`, `F12-fingerprint-coverage`.

Fingerprint của audit bổ sung dùng phạm vi code/tests recursive và đã xác nhận code không đổi trước/sau suite; không dùng digest thiếu coverage để tuyên bố source toàn bộ bất biến.

## 5. Các rủi ro và thiếu sót khác cần khép lại

### R01 — MemoryError/latency và thiếu stage diagnostics

Run cuối đã lưu có **7 MemoryError**, nhưng chỉ error_class và error string; không có traceback/stage/RSS để xác định từng lỗi phát sinh ở parser, Jedi, copy graph, validation hay packing.

Source cho thấy ít nhất ba bản document có thể đồng thời tồn tại: document gốc, `TaskOverlayBuilder` deepcopy, `GraphContextRetriever` deepcopy; thêm indexes/validation/sources/Jedi cache. Đây là **yếu tố tăng memory đã xác nhận bằng code**, chưa phải kết luận nguyên nhân duy nhất của 7 lỗi thật.

Graph runner chưa có per-task watchdog/resume/worker isolation, catch string không trace. Khi bị ngắt, run có thể giữ `RUNNING/complete=false`. Chưa xác minh process của các run lịch sử còn chạy: truy vấn Win32_Process bị Access denied; **không suy từ status JSON rằng process đang sống**, không kill process ngoài invocation audit.

Cần thêm bounded diagnostics trước khi quyết định thuê RAM lớn. Retrieval tuần5–6 không dùng GPU hay LLM generation; thay GPU không tự sửa F01/F03/F10.

### R02 — Quan sát runtime model/context, không thuộc đợt sửa retrieval này

- Settings chọn Qwen3-4B-Instruct-2507, temperature0, max_new_tokens512, token_budget8000.
- Model/tokenizer `from_pretrained(model_id)` không truyền immutable revision; runtime model có thể khác tokenizer-only manifest đã pin của M1.
- `AgentSettings.token_budget` hiện không được dùng để assemble/truncate agent context; trường `context` của state chưa thành flow grounding/context.
- Model loader test là mocked; audit không chứng minh inference thật end-to-end trên GPU của bạn.

Quan sát này không được quy thành task research tuần 1–2 chưa hoàn thành hoặc yêu cầu đưa research vào repo. Kế hoạch hiện tại không sửa model inference loader. Phần cần làm ở tuần 6 là expose/display bounded retrieval context và giữ tokenizer/config evaluation nhất quán; không triển khai full repair prompt/token telemetry của tuần 7–8.

### R03 — Comparison fairness/acceptance còn yếu

Comparator đã kiểm revision/budget/counter/scoring/snippet, và per-task query/corpus/base_commit — đây là phần tốt cần giữ. Tuy nhiên:

- Chưa so sánh patch_hash/gold-label identity và dataset_id; chưa ràng buộc duplicate task IDs/manifest population rõ ràng.
- Khi không có paired task, code có thể tạo `NO_PAIRED_TASKS` nhưng `exit_code=0`; đây không phải đã đạt DoD.
- Gộp chỉ tasks succeeded cả hai có thể gây survivor bias. Cần báo attempted/failed/skipped và denominator, không chỉ mean đẹp của tasks còn sống.

Những điểm này xác nhận bằng source inspection, chưa tạo một comparison artifact giả bằng cách thêm `arm` để qua F01.

### R04 — `graph_f2p` dùng thông tin benchmark oracle

`run_graph_retrieval.py` truyền `FAIL_TO_PASS` của dataset vào enhanced arm. Script ghi `uses_fail_to_pass=true`, nhưng manifest query policy là `problem_statement_only_no_hints_or_gold`.

`FAIL_TO_PASS` là test identifiers từ benchmark metadata, không đồng nghĩa với stack trace/test failure đã quan sát tại base environment. Có thể dùng làm **oracle-assisted diagnostic arm**, phải ghi rõ và không trộn với Graph issue-only khi claim fairness. Không nói gold developer patch đang bị đưa vào ranker; code hiện dùng patch để evaluator tạo nhãn, không đưa vào issue query.

### R05 — `get_callers/get_callees(depth)` echo depth nhưng chỉ direct query

Server docstring công khai chỉ áp depth1, nhưng vẫn nhận/echo depth2 hoặc lớn hơn. Trả `depth=2` không chứng minh đã traverse2hop. Native `GraphContextRetriever` có k-hop riêng. Sửa tối thiểu: reject depth khác1 hoặc implement và kiểm chứng đúng semantics; không đổi shape âm thầm.

### R06 — Tài liệu handoff và plan cũ chưa phản ánh integration hiện tại

- `comparison.md`/handoff03Oct nói chưa có Graph–BM25 pipeline, trong khi code05Oct đã thêm runner/comparator.
- Spec builder05Oct còn ghi lookup không có guard, nhưng code/commit `93c4d786` đã thêm guard.
- Spec nhầm 9 failures thành build success ~36% và dự đoán guards đem lại ~100%; artifact không hỗ trợ dự đoán đó.
- `docs/mcp_tool_contract.md` chỉ ba signature, chưa đủ contract tuần6.
- References research/literature có target ngoài checkout; việc không có `research_design.md`/`literature_review.csv` trong VGAR không được coi là lỗi hoặc task research chưa hoàn thành. Riêng báo cáo kiểm tra retrieval thủ công 10 task thuộc nghiệm thu tuần 5–6 chưa có bằng chứng hoàn tất trong checkout.
- `configs/*.yaml` còn tồn tại nhưng runtime settings không đọc; không sửa YAML rồi tưởng runtime đã đổi.

Tài liệu lịch sử có thể giữ, nhưng phải dán snapshot/date và có checkpoint hiện tại thay vì ghi lại lịch sử thành hiện tại.

## 6. Artifact benchmark hiện có: đọc đúng trạng thái

Nguồn: [saved-runs.json](../../artifacts/reviews/2026-10-06-w1-w6/saved-runs.json), tổng hợp từ `results/retrieval/*/result.json`, đọc tại thời điểm audit.

| Run | Loại | Complete | Succeeded/attempted | Ý nghĩa |
|---|---|---:|---:|---|
| `20261005T045625580136Z-7fa20ac5dd80` | BM25 | true | 25/25 | Baseline thật hoàn tất |
| `20261005T082810770056Z-7a3ad261d8e4` | BM25 | true | 25/25 | Baseline thật hoàn tất, source digest khác run đầu |
| `20261005T090644654026Z-fcd8ac1549ac` | Graph | false | 0/9 | 9 KeyError; incomplete, không phải 9/25 thành công |
| `20261005T143304598084Z-82ffcaf800a0` | Graph | true | 0/25 | 25 KeyError, gồm stale-node/path errors |
| `20261005T150325371577Z-af2d2254d25f` | Graph | true | 0/25 | 25 KeyError liên quan paths/Jedi ở máy chạy trước |
| `20261005T160912420600Z-6c31fae9c81f` | Graph | true | 0/25 | 25 AttributeError Path/type |
| `20261005T163220576118Z-66891db96f14` | Graph | false | 1/12 | 7 MemoryError, 3 snapshot GraphError, 1 self-loop GraphValidationError |

Các error lịch sử không có đủ traceback để gán mọi KeyError/Path error cho code đang kiểm tra. Source digests khác nhau; không tuyên bố lỗi cũ đều vẫn tồn tại. **Hai lỗi snapshot/self-inheritance có tái hiện độc lập trên source hiện tại**, nhưng chưa map fixture mới vào đúng task lịch sử.

Ví dụ BM25 run `082810...`, macro means (25 eligible tasks):

| Metric | @3 | @5 | @10 |
|---|---:|---:|---:|
| Gold-file Recall | 0.3600 | 0.5267 | 0.5933 |
| Gold-function Recall | 0.2000 | 0.2783 | 0.4217 |

Mean context tokens: `7997.28`, tokenizer counter thật, không fallback. Đây là metric retrieval changed-code proxy, **không phải 52.67% task sửa thành công**. Không lấy baseline cũ làm paired mới nếu scorer/source protocol thay đổi mà chưa kiểm compatibility.

## 7. Tiến độ đối chiếu các task tích hợp tuần 3–6

Quy ước: **Có** = implementation/evidence tồn tại ở mức nêu; **Một phần** = có nhưng chưa đủ gate; **Chưa có bằng chứng** không đồng nghĩa người phụ trách chưa từng làm ở nơi khác. Không tính phần trăm chung từ số checkbox vì mức công việc khác nhau.

### 7.1 Research tuần 1–2 không thuộc nghiệm thu repo

Theo yêu cầu người dùng, không tạo bảng trạng thái hoàn thành/chưa hoàn thành research tuần 1–2 từ checkout VGAR và không yêu cầu tích hợp các tài liệu đó. Schema, vocabulary và contract có sẵn được giữ làm nền tảng cho tuần 3–6; đây không phải việc triển khai lại research.

### 7.2 Tuần 3–4

| Yêu cầu | Trạng thái | Evidence / giới hạn |
|---|---|---|
| Tree-sitter + entities + basic edges | Có, cần robustness fix | Tests pass trên fixtures; F03/F06/F09/F10 |
| Minimal resolver | Có | Jedi/lexical rules; không bắt buộc phải dùng SCIP/Pyright thay Jedi |
| Imports/direct calls + confidence/provenance | Có | Builder và schema; chưa chứng minh call recall toàn benchmark |
| SQLite persistent graph/query | Có | Store/service/query/DTO tests |
| Builder/query trên 1–2 repo mẫu | Có evidence | sample_repo/jedi_repo và tests, checkpoint01Oct |
| Sandbox/workspace | Có trên source nhỏ, một phần tích hợp | Workspace copy/limits/tests; F05, F11 |
| pytest runner | Có | `repair/test_runner.py`, test timeout/output/selector/JUnit, suite hiện tại |
| Baseline command/stdout/stderr/exit/duration | Có | `repair/baseline.py`, writer, artifacts/tests/m2 |
| Evidence JSON/schema | Có | Begin/finish atomic records, status rõ |
| MCP server/resources3URI | Có | Graph server, MCP resource tests |
| LangChain client3graph tools | Có | Adapters/client + scripts/smoke/test tooling; không chạy smoke model thật trong audit |
| Audit graph tool/resource calls | Có | `mcp/tooling.py`/audit; chưa phủ repo/execution (F11) |
| >=20 inspected call/import edges | Có checkpoint | CSV20rows01Oct source-inspected bởi Codex; human sign-off riêng, không coi 20 MATCH là population recall |
| Node/edge/buildtime log | Có checkpoint | `artifacts/m1/graph-quality/build_metrics.json`; không dùng numbers cũ cho graph hiện tại |

### 7.3 Tuần 5–6: trọng tâm nghiệm thu

| Owner / task | Trạng thái | Có ở đâu / còn thiếu |
|---|---|---|
| M1 find_task_anchors | Có API nội bộ | `graph/grounding.py`, tests/task_anchors |
| M1 path/symbol/stacktrace/test/route | Có baseline | Literal routes/symbol matching, ambiguity/unmatched rõ; không deep dynamic routing |
| M1 Issue/FailingTest + trace | Một phần theo wording plan | Issue + Test đã có + MENTIONS/REPRODUCES; **không có node type FailingTest riêng**. Frozen schema chỉ Test/Issue, cần ADR giải thích, không tự thêm schema |
| M1 get_related_context | Có API nội bộ | `graph/retrieval.py`, source verification và tests; F03 ảnh hưởng benchmark |
| M1 k-hop/callers/callees/tests/dependents | Có baseline | Semantic adjacency imports/calls/test links/inherits/contains; architecture_dependencies được ghi unavailable, không đòi full architecture layer lúc này |
| M1 rank distance/confidence/test proximity/API risk | Có heuristics | RetrievalConfig/features; risk là heuristic, chưa calibration/semantic proof |
| M1 token-bounded packing | Có native API | Shared ContextPayload + pinned tokenizer; native snippet-only khác evaluator header80lines, phải tách metric |
| M2 BM25 function/code chunks | Có | `evaluation/retrieval/bm25.py`, `chunks.py`, runner |
| M2 gold-file/gold-function | Có baseline, chưa đủ cross-arm cases | `gold_labels.py`, CorpusIndex; F06 và mapping audit cần bổ sung |
| M2 eval20–30 SWE-bench | Có **BM2525**, chưa hoàn thành toàn tích hợp | Hai baseline run thật; Graph paired chưa đạt |
| M2 phối hợp debug context/gold | Một phần | Shared scorer/adapter có; producer/comparator và extraction edge cases vẫn lỗi |
| M3 expose anchors/context MCP | Chưa | F02 |
| M3 LangChain issue→anchors→context→display | Chưa thấy flow hoàn chỉnh | Không có tools nên chưa thể coi agent/tool discovery cũ là đã đạt |
| M3 subset50–100 có env chạy | Một phần | Dev100manifest12repos, min_source_files1; dev25multi-file7repos; **không có environment readiness/command audit cho50–100** |
| M3 draft Related Work graph/retrieval | Tài liệu nghiên cứu của nhóm | Không dùng việc thiếu draft trong checkout làm blocker sửa lỗi/tích hợp code; nhóm quản lý nội dung báo cáo riêng |
| DoD Graph vs BM25 Recall3/5/10 + token cost | **Chưa đạt** | F01 và chưa có completed paired benchmark |
| DoD >=10task manual inspect | **Chưa có bằng chứng hoàn tất** | `docs/m5_m6_retrieval_evaluation.md` chưa có; gợi ý inspection trong script không phải đã inspect |

**M2 W5–W6 riêng:** baseline và evaluator đã làm thực chất; task phối hợp/nhãn/mapping còn cần sửa và nghiệm thu với M1. **Cả nhóm W5–W6:** còn thiếu deliverables M3 và DoD chung, không thể ghi hoàn thành 100% chỉ bằng bộ test fixture.

Manifest 100 task có single-file tasks là đúng khả năng của selector `min_source_files=1`; không được gọi toàn bộ 100 task là multi-file. Dev25 vẫn chọn multi-file. Split 40%/60% theo hash chỉ là policy code hiện tại, chưa thay cho sign-off protocol của nhóm.

## 8. Vì sao vấn đề xuất hiện khi ghép module?

1. **Module test dùng fixture tự tạo thay vì shape từ runner thật:** bỏ qua `arms`/`arm`.
2. **Invariant cross-module không được test cùng nhau:** builder allowed partial/rollback nhưng retrieval assumes full File inventory.
3. **M2 thêm operational data vào cùng repo mà M1/workspace scope không đổi:** code scan/copy/hash tưởng mọi file là source target.
4. **Representation/coverage khác nhau:** AST M2 và Tree-sitter M1 không cùng xử lý conditional/duplicate/decorators/bindings.
5. **API nội bộ chưa được nối sang transport:** merge file M1 không tạo MCP tool hay consumer flow tự động.
6. **Benchmark evidence thiếu chẩn đoán:** error string không trace/stage, cache chưa đủ dependency fingerprint, không bounded per-task lifecycle.
7. **Tài liệu từng thành viên giữ snapshot cũ:** các checkbox/spec/handoff chưa có single current checkpoint được nhóm review.

Đây là các nguyên nhân kỹ thuật, không phải kết luận lỗi thuộc về một cá nhân. Từng owner cần phối hợp tại interface, không rewrite module đang hoạt động.

## 9. Tài nguyên: có nên tiếp tục?

**Có thể tiếp tục, nhưng không chạy lại 25 Graph tasks ngay.**

- Unit/integration fixtures và retrieval-only eval không cần model weights/GPU. Không cần fine-tune để sửa các lỗi hiện tại.
- Sửa F01/F03/F10 trước; cô lập source scope và cache; thêm stage/trace/RSS/timeout; rồi thử3task cached/offline có một repo gặp rollback.
- Nếu Jedi vẫn quá nặng, no-Jedi có thể là diagnostic profile riêng. Không âm thầm đổi resolver giữa baseline/Graph chính thức để gọi là cùng cấu hình.
- Chỉ tối ưu graph ownership sau khi đo; giữ snapshot immutability tests, không bỏ deepcopy tất cả mà để caller mutation thay graph giữa run.
- Chỉ quyết định máy nhiều RAM/cloud sau khi có stage-level evidence. Audit không đo máy hiện tại VRAM/RAM free nên không kê cấu hình như một bảo đảm.

## 10. Kiểm thử đã làm và nơi đọc kết quả

| Artifact | Nội dung |
|---|---|
| `suite.json` | Actual pytest argv/command, stdout/stderr, exit/duration,197cases gồm196PASS+1skip, timeout/output flags |
| `suite-invocation.json` | Interpreter/platform/cwd/argv, duration driver, code hashes, `code_unchanged=true` |
| `probes.json` | 10 phép probe cho F01–F09, inputs nhỏ và observed outputs/errors |
| `probe-invocation.json` | Provenance/argv/code hashes của batch probe |
| `extra-probes.json` | Self-inheritance, MCP root/envelope, fingerprint nested-tests |
| `extra-invocation.json` | Provenance của batch bổ sung |
| `saved-runs.json` | Tóm tắt7run đã lưu, source digests, statuses/counters/errors |
| `interrupted-recorder.json` | Invocation recorder bị hủy trước pytest, không bịa duration/kết quả |
| `audit_checks.txt` | Diagnostic driver portable; không phải production implementation hay benchmark runner |

Đường dẫn đầy đủ: `D:\Project\CAPSTONES\VGAR\artifacts\reviews\2026-10-06-w1-w6\`.

Các lần kiểm tra đã chạy bằng driver ở `D:\Project\CAPSTONES\.audit-tmp\vgar-review-w1-w6-20261006\audit_checks.py`; fixtures chỉ được tạo dưới `.audit-tmp`, không đụng source fixture/demo gốc. Bản `.txt` giúp người khác xem/tái chạy sau khi clone, không thêm một source `.py` nữa vào index target.

Muốn tự xem kết quả, không cần chạy lại:

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$evidence = '.\artifacts\reviews\2026-10-06-w1-w6'
$suite = Get-Content -Raw -Encoding UTF8 (Join-Path $evidence 'suite.json') | ConvertFrom-Json
$suite | Select-Object status,exit_code,duration_ms
$suite.cases | Group-Object status | Select-Object Name,Count
$suite.stdout
Get-Content -Raw -Encoding UTF8 (Join-Path $evidence 'probes.json') | ConvertFrom-Json
```

Tái chạy diagnostic driver (chỉ khi muốn; chưa phải fix): dùng Python có dependency của VGAR, đặt output trong một folder tạm ngoài repo để không ghi lại evidence cũ. Copy `.txt` thành `.py` vào `D:\Project\CAPSTONES\.audit-tmp\vgar-review-w1-w6-20261006\` hoặc folder tương đương có parent CAPSTONES; driver nhận VGAR theo vị trí workspace. Sau đó chạy `python -B <driver> suite`, `probe`, `extra`. Các probes chủ động sửa **synthetic tree/original** để chứng minh guard, không sửa repository VGAR. Đừng chạy driver trực tiếp vào folder evidence chuẩn nếu muốn giữ artifact cũ bất biến.

## 11. Checkpoint và quyết định cần duyệt

- [x] Review status/diff/history và docs liên quan; phạm vi nghiệm thu repo đã giới hạn tuần 3–6 theo người dùng.
- [x] Chạy existing suite và lưu đầy đủ result.
- [x] Tái hiện lỗi cross-module nhỏ, không tải model/dataset mới.
- [x] Đối chiếu deliverable với code/evidence hiện tại.
- [x] Lập kế hoạch fix có milestones, owners, tests, acceptance gates.
- [ ] Người dùng duyệt kế hoạch sửa.
- [ ] Bắt đầu sửa production code/test regressions.
- [ ] Benchmark paired20–30 + manual10 + MCP retrieval flow nghiệm thu.

Các file mới của lần này chỉ là **review, fix plan, checkpoint và evidence**. Source code và tests sản phẩm giữ nguyên. Không đặt task tuần7–16 thành lỗi tuần6, không triển khai fine-tuning, không chuyển lại hệ thống cũ.
