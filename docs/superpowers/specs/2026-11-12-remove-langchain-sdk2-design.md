# Bỏ LangChain, nâng MCP SDK lên 2.2.0 (chỉ giữ server MCP)

Ngày: 12/11/2026 · Người đề xuất: TV2 (tích hợp) · Quyết định của nhóm: "bỏ langchain, chỉ cần các server mcp".

## 1. Mục đích

Repo chỉ còn phục vụ **3 server MCP** (graph, execution, repository) để gắn vào coding agent bên ngoài; agent bên ngoài (Claude) tự sửa code nên không cần `repair_server` (quyết định người dùng 12/11) (Claude Code, Cursor…) theo hướng dẫn build-server `2026-07-28`. Muốn vậy phải chạy MCP SDK 2.x. Thứ duy nhất chặn SDK2 trong cùng một venv là `langchain-mcp-adapters==0.3.2` (bản mới nhất, vẫn đòi `mcp<2`). Nhóm chọn bỏ toàn bộ phần agent dùng LangChain thay vì giữ hai venv.

## 2. Mục tiêu

1. `pyproject.toml` không còn `langchain`, `langgraph`, `langchain-huggingface`, `langchain-mcp-adapters`; `mcp` ghim `==2.2.0` (đúng `requirements/mcp-server.lock` của TV1).
2. Một `.venv` duy nhất chạy được: `vgar index`, `vgar doctor`, 3 server MCP qua stdio, và giao thức `2026-07-28`.
3. Suite: không có lỗi mới so với baseline (32 lỗi hiện tại); 29 lỗi do thiếu SDK2 phải chuyển sang PASS hoặc được giải thích từng cái.
4. Server vẫn chạy trên graph thật (giữ nguyên kết quả đợt nối layer 11–12/11).
5. Logging và debug theo hướng dẫn build-server `2026-07-28` (yêu cầu người dùng 12/11): không ghi stdout; `logging.getLogger(__name__)` ở mọi module server; log ra stderr để host thu; không dùng logging qua giao thức (deprecated ở `2026-07-28`); mức log bật bằng `VGAR_MCP_LOG_LEVEL` (mặc định `WARNING`); có `docs/mcp_server/debugging.md` (Inspector, nơi xem log của Claude Code / Claude Desktop / OpenCode, audit log, lỗi thường gặp).

## 3. Không làm (non-goals)

- Không viết agent mới, không thay LangChain bằng framework khác.
- Không đổi hành vi tool/resource/prompt của 3 server còn lại.
- Không xóa engine M2 trong `src/vgar/repair/` (patch, workspace, executor, api/structural check, source_imports, verification, evidence…): graph server, execution server, `patch_evidence.py` và provider của TV3 đang dùng. `pipeline.py`, `session.py` và lệnh `vgar repair --mode fake` giữ nguyên trong đợt này (chỉ bỏ nhánh `real`); dọn tiếp là việc của đợt sau nếu nhóm muốn.
- Không nâng lên 2.3.0 (chưa có lock và nghiệm thu).
- Không sửa `requirements/mcp-server.lock` của TV1.

## 4. Phạm vi xóa

### 4.1 Code (xóa hẳn; lịch sử còn trong git)

| Nhóm | File |
|---|---|
| Agent LangChain | toàn bộ `src/vgar/agents/` |
| Client MCP qua adapter | `src/vgar/mcp/client.py`; bỏ `create_mcp_client` khỏi `src/vgar/mcp/__init__.py` |
| Model bọc LangChain | `src/vgar/models/factory.py`, `src/vgar/models/huggingface/hf_model.py`, `src/vgar/models/huggingface/local_hf_chat_model.py`; sửa `src/vgar/models/huggingface/__init__.py` cho khớp |
| CLI | bỏ các lệnh `tools`, `solve`, `run`, `chat`; bỏ import `langchain_core` ở đầu `src/vgar/cli.py`. Giữ `doctor`, `index`, `repair` |
| Script chỉ phục vụ agent | `scripts/smoke_hf_agent.py`, `scripts/smoke_mcp.py`, `scripts/smoke_model.py`, `scripts/smoke_workflow.py`, `scripts/smoke_w3_w4_agent.py`, `scripts/check_agent_impact_real.py`; `smoke_w3_w4.py`, `smoke_w5_w6_retrieval.py`, `smoke_w7_w8_m1.py` xóa nếu chỉ chạy qua agent, ngược lại sửa |

| Generator Qwen V11 thật (quyết định người dùng 12/11: chỉ build server MCP, không xây agentic AI) | `src/vgar/models/huggingface/{generator_hf,hf_backend,hf_worker,model_worker,hf_diagnostics}.py`; nhánh `mode == "real"` trong `src/vgar/repair/pipeline.py` (`build_tokenizer`, `build_generation`) và lệnh `vgar repair`. `mode="real"` bị từ chối rõ ràng (`ValueError`) |
| Repair server (quyết định người dùng 12/11: Claude tự sửa code) | `src/vgar/mcp/servers/repair_server.py`; mục `vgar-repair` trong `configs/mcp_server/{claude-code,inspector-legacy,inspector-modern}.template.json` và `entrypoints`/`operator_bindings` trong `configs/mcp_server/runtime.json`; câu nhắc `repair_server` trong docstring `repository_server.py`; danh sách server trong script kiểm của TV1 nếu có. Test: `tests/m2/w78/test_w78_repair_server.py` xóa; `test_w1112_evidence_integration.py`, `test_runner_contract.py`, `tests/mcp_server/test_concurrency.py`, `test_mcp_legacy_servers.py`, `test_mcp_security.py` chỉ cắt phần gọi repair server |

**Giữ:**
- `src/vgar/models/huggingface/local_chat.py`: bộ đếm token prompt (Jinja2 + `tokenizers`, không model); `pipeline.build_tokenizer(mode="fake")` và `evaluation/repair/preflight.py` dùng.
- `src/vgar/models/{base,config,generator}.py`: `FakeGenerator` cho chế độ `fake` và test engine M2.
- Script của TV1 `scripts/mcp_server/{check_runtime,_runtime_probe,_runtime_worker,smoke_mcp,_preflight_worker}.py`: công cụ kiểm runtime server MCP (L6-1, L6-8); chỉ nhắc LangChain để kiểm "venv không có LangChain".
- `session.py` quét `src/vgar/agents/prompts` để lấy fingerprint; thư mục mất thì `rglob` trả rỗng, không lỗi, nên không cần sửa.

### 4.1b Engine sinh patch M2 (bổ sung 12/11, người dùng chọn "bỏ ngay trong đợt này": build MCP, không phải agentic AI)

Server MCP chỉ kéo engine sinh patch vì `diff_tests_provider.py` (EV-3, TV3) và `docker_executor.py` import `DeadlineExecutor`, `require_trusted_fixture` từ `repair/pipeline.py`.

- **Chuyển** `StopRun`, `require_trusted_fixture`, `DeadlineExecutor` sang `src/vgar/repair/deadline.py`; sửa import ở `diff_tests_provider.py`, `docker_executor.py`, `evaluation/repair/verifier_eval.py`.
- **Xóa** (vòng sinh patch bằng mô hình và chiến dịch chạy nó): `repair/{pipeline,session,prompt,failure}.py`, `models/` (toàn bộ), lệnh `vgar repair` (CLI còn `doctor`, `index`), `evaluation/repair/{launch,runner,gpu,preflight,aggregate,derive_config}.py`, `evaluation/{dry_run,agent_metrics}.py`, `evaluation/harness/candidates.py`; script `run_repair_experiment.py`, `derive_experiment_config.py`, `dry_run_heldout_chain.py`, `grade_repair_candidates.py`, `aggregate_agent_traces.py`; test chỉ kiểm các phần trên.
- **Giữ** phép đo Verification của plan 2 tuần (tuần 2 ngày 4: `build_mutant_pool.py`, `evaluate_mutant_pool.py`; pilot V1 của TV3 dùng `verifier_eval.confusion_metrics`): `evaluation/repair/{mutant_pool,verifier_eval,fairness,manifest}.py`. Hai file sau hash mẫu prompt V11 làm dấu vân tay cấu hình thí nghiệm, nên mẫu `repair_v11.txt` và hàm `template_path` chuyển sang `src/vgar/evaluation/repair/prompt_fingerprint.py` (+ `src/vgar/evaluation/repair/prompts/repair_v11.txt`, giữ nguyên từng byte): chỉ dùng để hash, không dựng prompt.

### 4.1c Code chết của plan 16 tuần (bổ sung 12/11, người dùng chốt danh sách)

Chỉ giữ file của plan 2 tuần và proposal. Xóa kèm test:
- Script: `run_agent.py`, `accept_m1_tokenizer.py`, `provision_m1_tokenizer.py`, `export_m1_handoff.py`, `consume_m1_handoff.py`, `demo_w7_w8_handoff.py`, `package_m1.py`, `run_m1_tests.py`, `smoke_w5_w6_resolvers.py`, `build_w9_bundle_fixture.py`, `export_w9_pilot_bundles.py`, `prepare_w9_pilot_inputs.py`, `analyze_repair_timeouts.py`, `compare_tune_steps.py`, `check_results_sources.py`, `smoke_real_repo_graph.py`, `find_task_anchors.py`, `visualize_graph.py`.
- `src`: `evaluation/results_sources.py`, `graph/visualization.py`, `config/logging.py`; cùng module `src` chỉ các file trên dùng (mồ côi sau khi xóa).
- Giữ (plan 2 tuần dùng): `build_graph.py` + `load_graph_fixture.py` (dựng graph đủ tùy chọn JARVIS/Joern/SCIP rồi nạp SQLite), `get_related_context.py`, `build_task_overlay.py`, script RT-1/TR-1/SC-1 của TV2, `audit_mypy_deltas.py`, `graph/ast_diff.py` (TV3 L4-4), script chuẩn bị môi trường SWE-bench (`prepare_manifest.py`, `prepare_task_env.py`, `pin_task_images.py`, `build_swebench_test_cmds.py`), `grade_repair_candidates.py`, `aggregate_agent_traces.py`.

### 4.2 Test

- Xóa test chỉ kiểm phần bị xóa: `tests/unit/test_agent_*.py`, `test_workflow.py`, `test_state.py`, `test_tool_budget.py`, `test_trace_*.py`, `test_x2b_diagnosis_fixes.py`, `tests/m3/test_agent_admitted.py`, `tests/test_cli_run_chat.py`, `tests/test_mcp_day5.py` (nếu chỉ qua client adapter).
- File trộn (một phần kiểm server, một phần kiểm agent/client): chỉ xóa các test dùng phần bị xóa, giữ phần còn lại — `test_settings.py`, `test_w10_impact_mcp.py`, `test_mcp_security.py`, `test_redaction.py`, `test_mcp_result_parser.py`, `test_mcp_legacy_servers.py`, `tests/mcp_server/test_legacy_compatibility.py`, `test_runtime_cli.py`, `test_sdk_runtime.py`, `tests/m2/w78/test_w78_repair_server.py`.
- Mỗi file bị xóa hoặc cắt được ghi vào báo cáo kèm lý do.

### 4.3 Dependency (`pyproject.toml`)

- `dependencies` (lõi, khớp `requirements/mcp-server.in` của TV1): `mcp==2.2.0`, `pydantic>=2.12,<3`, `packaging>=24`, `filelock==4.2.9`, `python-dotenv>=1`, `tree-sitter==0.25.2`, `tree-sitter-python==0.25.0`, `PyYAML>=6,<7`, `tokenizers>=0.22.0,<=0.23.0`, `Jinja2>=3.1`.
- **Bỏ hẳn** gói ML: `torch`, `accelerate`, `transformers`, `safetensors`, `pyarrow`, `datasets`, `peft`, `trl`. Lý do: generator thật đã xóa; `repair_server` không cần (TV1 chạy nó trong venv SDK2 không có torch). Import torch còn sót ở `observability/machine.py` phải là import lười có bắt `ImportError`; nếu không thì sửa.
- Giữ các extra `dev`, `history`, `plot`, `code-graph`.

## 5. Cách làm và kiểm

1. **Venv thử ngoài repo** (`<scratchpad>/venv-sdk2`): cài `-e .[dev,history]` theo `pyproject` mới, chạy suite, so với baseline. Chỉ khi đạt mục tiêu 2–3 mới đụng `.venv` thật.
2. **Nâng `.venv` thật**: `pip uninstall` 4 gói LangChain, `pip install -e .[dev,history]` (kéo `mcp 2.2.0`). Gói ML đang có trong `.venv` không gỡ trong đợt này (không ảnh hưởng server; người dùng tự gỡ nếu muốn tiết kiệm dung lượng).
3. Kiểm tay: `vgar index` repo demo; Inspector hoặc client SDK2 liệt kê tool ở cả `2026-07-28` và `legacy`; gắn lại Claude Code và gọi `search_symbols`, `verify`, `run_relevant_tests`, `rank`; thử bấm dừng giữa lời gọi xem còn "Connection closed" không.
4. Cập nhật `README.md`, `.env.example` (nếu nhắc agent), `docs/mcp_server/runtime.md` (bỏ đoạn "root metadata giữ MCP<2 và LangChain"), báo cáo chạy ở `docs/status/`.

## 6. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Code SDK1-only trong server (`mcp.server.fastmcp`, `mcp.types`) gãy trên SDK2 | `server_factory.py` của TV1 đã rẽ nhánh SDK1/SDK2; venv thử sẽ lộ chỗ còn sót |
| Bỏ `repair_server` đụng phần L6 của TV1 (L6-1 nói "4 server") và các template Inspector/Claude Code | Ghi rõ trong báo cáo để TV1 biết; nhóm đã quyết định chỉ cần server cho agent bên ngoài |
| `Jinja2`/`tokenizers` trước đây đến gián tiếp qua `transformers` | Đưa thẳng vào lõi (mục 4.3) |
| Demo bảo vệ từng dùng agent Qwen qua LangChain | Nhóm đã quyết định bỏ; demo dùng coding agent bên ngoài gắn MCP |
| Thành viên khác còn venv cũ | Báo trong báo cáo: cài lại bằng `pip install -e .[dev]` |

## 7. Bàn giao

Người dùng tự commit. Báo cáo chạy liệt kê: file xóa, file sửa, test xóa/cắt kèm lý do, suite trước/sau, kết quả kiểm tay.
