# TV2 · Bỏ LangChain, engine sinh patch và repair server; nâng MCP SDK 2.2.0: báo cáo chạy (12/11/2026)

Spec: `docs/superpowers/specs/2026-11-12-remove-langchain-sdk2-design.md` (§4.1, §4.1b, §4.1c). Plan: `docs/superpowers/plans/2026-11-12-remove-langchain-sdk2.md`. Ledger: `.superpowers/sdd/2026-11-12-remove-langchain-sdk2/progress.md`. Nền: commit `611e9984`. Chưa commit (người dùng tự commit).

## Quyết định của nhóm

Repo chỉ còn **3 server MCP** (`vgar-graph`, `vgar-execution`, `vgar-repository`) để gắn vào coding agent bên ngoài (Claude Code, OpenCode với mô hình local). Agent bên ngoài tự sửa code, nên không còn agent LangChain, generator Qwen V11, `repair_server` hay engine sinh patch M2. Code chỉ thuộc plan 16 tuần mà hệ thống plan 2 tuần không dùng cũng đã xóa.

## Kết quả

| | Trước (`ea4d6fac` + nối layer, `.venv` SDK 1.30) | Sau (`.venv` SDK 2.2.0) |
|---|---|---|
| MCP SDK | `mcp 1.30.0` + `langchain-mcp-adapters 0.3.2` | `mcp 2.2.0`, `mcp-types 2.2.0`; không còn gói LangChain/LangGraph/LangSmith |
| Server | 4 (có `repair_server`), 20 tool công khai | 3, 16 tool công khai |
| Giao thức | `2025-11-25` | `2026-07-28` và `2025-11-25` (legacy) |
| Suite đầy đủ | 32 fail / 3.675 pass | **5 fail / 3.106 pass / 26 skip**, không lỗi mới |
| Hủy lời gọi | server trả `{"error":{"code":0,"message":"Request cancelled"}}` cho id đã hủy → Claude Code đóng kết nối ("Connection closed") | không trả lời id đã hủy, server vẫn sống |

5 lỗi còn lại đều có từ trước: 4 lane `sdk1-legacy` cần interpreter legacy của TV1 (`environments/vgar-week78-cuda`, không có trên máy) và `test_official_harness::test_campaign_reads_pinned_upstream_run_evaluation_directory` (lỗi sẵn trên HEAD). 29 lỗi do thiếu SDK2 đã hết.

## Kiểm bằng SDK2

- Stdio thật trên `vgar-demo-shop`, cả `2026-07-28` và `legacy`: 11 tool; `search_symbols` PASS, backend `sqlite`; `get_callers` depth 2 → 8 symbol; `verify_patch_graph_constraints` PASS; `rank_patch_candidates` xếp patch sửa đủ (0,8, đủ điều kiện) trên patch sửa thiếu (0,3, bị loại); `run_relevant_tests` chọn 7 test, `test_bug` được sửa.
- **MCP Inspector** (`npx @modelcontextprotocol/inspector --cli`, biến qua `-e`) liệt kê đủ 11 tool ở `--protocol-era modern` và `legacy`.
- Log theo hướng dẫn build-server: `VGAR_MCP_LOG_LEVEL=INFO` cho dòng khởi động và một dòng `tool=… status=… duration_ms=… request_id=…` mỗi lời gọi trên stderr; stdout chỉ có JSON-RPC.

## Đã xóa

| Nhóm | Nội dung |
|---|---|
| LangChain | `src/vgar/agents/`, `mcp/client.py`, `mcp/result_parser.py`, `models/factory.py`, `models/huggingface/{hf_model,local_hf_chat_model}.py`, lệnh `vgar tools/solve/run/chat`, 9 script smoke |
| Generator và engine sinh patch | `models/` (toàn bộ), `repair/{pipeline,session,prompt,failure,context_presentation,patch_normalize,test_selection}.py`, lệnh `vgar repair`, `evaluation/repair/{launch,runner,gpu,preflight,aggregate,derive_config}.py`, `evaluation/{dry_run,failure_class}.py`, `observability/{machine,code_state,phase_logger,quiet}.py`, `scripts/{run_repair_experiment,derive_experiment_config,dry_run_heldout_chain}.py` |
| Repair server | `mcp/servers/repair_server.py`; 4 tool `repair_*` khỏi registry và `tests/fixtures/mcp_server/expected_contract.json`; `vgar-repair` khỏi 3 template và `runtime.json`; lane `repair` trong script kiểm của TV1 |
| Plan 16 tuần | 18 script (bàn giao M1, pilot W9, tokenizer M1, thí nghiệm M2/M3 cũ, script cũ trùng chức năng, vẽ graph), `evaluation/{results_sources,retrieval/pilot_export}.py`, `graph/visualization.py`, `config/logging.py` |
| Cấu hình | `ModelSettings`, `AgentSettings`, `Settings.to_env`, `SECRET_KEYS` (chỉ client/agent dùng); phần Model/Agent trong `.env.example` |
| `pyproject.toml` | `langchain*`, `langgraph`, `torch`, `accelerate`, `transformers`, `safetensors`, `datasets`, `peft`, `trl`; lõi ghim `mcp==2.2.0` |

Mỗi test bị xóa hoặc cắt có một dòng lý do trong ledger (`Task 2:` … `Task 8:`).

## Đã giữ hoặc chuyển

- `vgar index` chuyển sang `src/vgar/graph/indexing.py`.
- `StopRun`, `require_trusted_fixture`, `DeadlineExecutor` (provider EV-3 của TV3 và `docker_executor` cần) chuyển nguyên sang `src/vgar/repair/deadline.py`.
- Phép đo Verification của plan tuần 2 (`build_mutant_pool.py`, `evaluate_mutant_pool.py`, `audit_mypy_deltas.py`, `evaluation/repair/{mutant_pool,verifier_eval,fairness,manifest}.py`): giữ. Mẫu `repair_v11.txt` chuyển nguyên từng byte sang `src/vgar/evaluation/repair/prompts/` cùng `prompt_fingerprint.template_path`, chỉ dùng để hash cấu hình thí nghiệm.
- `grade_repair_candidates.py` + `harness/candidates.py` (chấm patch bằng harness SWE-bench chính thức) và `aggregate_agent_traces.py` + `agent_metrics.py` (MCP usability): khôi phục theo plan tuần 2 của TV1; `candidates.py` tự đọc biên bản lần chạy thay vì import runner đã xóa. **Cả hai chưa chạy trực tiếp được với Claude Code/OpenCode, cần adapter:** phần chấm điểm cần đúng layout của runner M2 cũ (`attempts/*/attempt-*.json` có `engine_run_dir` trỏ tới thư mục chứa `run_record.json` với `stages.apply.status == PASS` và `applied.diff`); phần usability cần file trace của `vgar solve --agent` đã xóa (tên `<UTC>-<task>.json`, trường `calls`, `mode`, `by`) ngoài audit log, và `MCP_TOOLS` trong `agent_metrics.py` còn trỏ tới server `repair`.
- `pyarrow` giữ trong lõi: phần đánh giá đọc parquet SWE-bench.
- `build_graph.py` + `load_graph_fixture.py` (dựng graph có JARVIS/Joern/SCIP rồi nạp SQLite), `get_related_context.py`, `build_task_overlay.py`, script RT-1/TR-1/SC-1, script chuẩn bị môi trường SWE-bench.

## Mới

- `src/vgar/mcp/logging_setup.py`: `VGAR_MCP_LOG_LEVEL` (mặc định `WARNING`), một handler stderr cho logger `vgar`, cấu hình chỉ trong `main()` của server.
- Log mỗi lời gọi trong `vgar.mcp.tooling.run_tool`; log khởi động và lỗi khởi động ở 3 server.
- `docs/mcp_server/debugging.md`: bật log, nơi xem log của Claude Code / Claude Desktop / OpenCode, audit log, lệnh Inspector đã chạy thử, lỗi thường gặp.
- `README.md` viết lại cho repo chỉ còn server MCP.
- Test chặn `tests/test_tv2_removed_stack.py`: không tham chiếu tới phần đã xóa, toàn bộ package import được khi chặn LangChain và gói ML, template chỉ còn 3 server, `pyproject` đúng spec, công cụ Verification còn đủ, settings không còn phần model/agent.

## Cài lại cho thành viên khác

```powershell
pip uninstall -y langchain langchain-core langgraph langgraph-checkpoint langgraph-prebuilt langgraph-sdk langchain-huggingface langchain-mcp-adapters langsmith langchain-protocol
pip install -e ".[dev,history,code-graph]"
```

Sau khi nâng: trong Claude Code gõ `/mcp` và kết nối lại `vgar-graph`, `vgar-execution`; trong OpenCode đổi `"protocol"` sang `"2026-07-28"`.

## Ghi chú cho TV1 và TV3

- **TV1:** L6-1 còn 3 server, 16 tool; template Inspector/Claude Code và `runtime.json` đã bỏ `vgar-repair`. Cổng tuần 1 phần Inspector `modern`/`legacy` đã kiểm được trên máy TV2. Công cụ đo tuần 2: `run_repair_experiment.py` và `dry_run_heldout_chain.py` đã xóa (chạy generator Qwen); patch cho phép đo Repair nay đến từ agent bên ngoài và cần một adapter ghi đúng layout runner cũ (xem mục Đã giữ) trước khi `grade_repair_candidates.py` chấm; MCP usability cần adapter đọc audit log của 3 server thay cho trace của `vgar solve --agent`. Ablation A0–A5 cần chốt lại cách đo (ngữ cảnh đóng băng cho retrieval/verification, agent thật có và không có MCP cho usability).
- **TV3:** `diff_tests_provider.py` và `docker_executor.py` import từ `vgar.repair.deadline` thay cho `vgar.repair.pipeline`; hành vi không đổi.

## Lệnh tái tạo

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest -q tests/test_tv2_removed_stack.py tests/mcp_server/test_tv2_server_logging.py
npx -y @modelcontextprotocol/inspector --cli -e VGAR_GRAPH_BACKEND=sqlite -e VGAR_GRAPH_DATABASE=<db> -e VGAR_REPOSITORY_ROOT=<repo> .venv/Scripts/python.exe -m vgar.mcp.servers.graph_server --protocol-era modern --method tools/list
```
