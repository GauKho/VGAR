# Bỏ LangChain, generator thật và repair server; nâng MCP SDK 2.2.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repo chỉ còn 3 server MCP (graph, execution, repository) chạy trên MCP SDK `2.2.0` trong một `.venv`, không còn LangChain, generator Qwen thật hay `repair_server`.

**Architecture:** Xóa theo từng khối độc lập (agent LangChain → generator thật → repair server), mỗi khối có test chặn tái xuất hiện (quét tham chiếu + import toàn bộ package khi chặn các gói đã bỏ). Sau đó đổi `pyproject.toml`, thử SDK2 trên venv tạm ngoài repo, đạt mới nâng `.venv` thật.

**Tech Stack:** Python 3.11, MCP SDK `mcp==2.2.0` (+ `mcp-types`), pytest, tree-sitter, SQLite.

**Spec:** `docs/superpowers/specs/2026-11-12-remove-langchain-sdk2-design.md` (duyệt 12/11/2026).

## Global Constraints

- `mcp==2.2.0` đúng `requirements/mcp-server.lock` của TV1; không sửa file lock đó; không lên 2.3.0.
- Lõi `dependencies`: `mcp==2.2.0`, `pydantic>=2.12,<3`, `packaging>=24`, `filelock==4.2.9`, `python-dotenv>=1`, `tree-sitter==0.25.2`, `tree-sitter-python==0.25.0`, `PyYAML>=6,<7`, `tokenizers>=0.22.0,<=0.23.0`, `Jinja2>=3.1`. Extra giữ: `dev`, `history`, `plot`, `code-graph`.
- Không còn `langchain`, `langgraph`, `langchain-huggingface`, `langchain-mcp-adapters`, `torch`, `accelerate`, `transformers`, `safetensors`, `pyarrow`, `datasets`, `peft`, `trl` trong `pyproject.toml`.
- Không đổi hành vi tool/resource/prompt của 3 server còn lại. Không xóa engine trong `src/vgar/repair/` ngoài nhánh `real`.
- Quy tắc build-server: không ghi stdout trong code server, logger theo module, docstring có `Args:`.
- Không commit, không push (người dùng tự commit). Không sửa `src` khi suite đang chạy.
- Baseline suite (trên `.venv` SDK 1.30, trước plan): 32 fail / 3.675 pass; 29 lỗi do thiếu SDK2, 3 lỗi có sẵn trên HEAD (`test_runner_contract::test_different_arm_contexts_can_share_template_without_same_prompt`, `test_official_harness::test_campaign_reads_pinned_upstream_run_evaluation_directory`, `test_w9_bundle::test_checked_in_fixture_validates_and_matches_recipe`). Danh sách: `.superpowers/sdd/2026-11-11-tv2-layer-integration/retest_failures.txt`.
- Test bị xóa hoặc cắt: chỉ test kiểm phần bị xóa; mỗi file ghi vào ledger kèm lý do.

## Review Focus

1. `vgar index` mất khi xóa `src/vgar/agents/` (hàm `index_repo` đang nằm ở `agents/runtime.py`) → người dùng không dựng được graph. Test: Task 1 `test_index_repo_lives_in_graph_package`, `test_cli_index_builds_a_database`.
2. Import lười bên trong hàm còn trỏ tới module đã xóa (import-all không bắt được) → lỗi chỉ hiện khi gọi đúng nhánh. Test: Task 2/3/4 `test_no_reference_to_removed_modules` quét chuỗi trong `src/` và `scripts/`.
3. Template Claude Code / Inspector hoặc `runtime.json` còn `vgar-repair` → host báo server không khởi động. Test: Task 4 `test_templates_list_exactly_three_servers`.
4. Server dưới SDK2 thương lượng `2026-07-28` hoặc schema tool (ví dụ `Candidate`) khác SDK1 → agent gọi hỏng. Kiểm: Task 8 bước stdio ở cả `2026-07-28` và `legacy`.
5. Hủy lời gọi giữa chừng dưới SDK2 vẫn làm host đóng kết nối. Kiểm: Task 9 bước hủy; ghi kết quả, không sửa SDK.

---

### Task 1: Chuyển `index_repo` ra khỏi `agents/`

**Files:**
- Create: `src/vgar/graph/indexing.py`
- Modify: `src/vgar/cli.py` (dòng 34 import, dòng 207 `cmd_index`)
- Test: `tests/test_graph_indexing.py`

**Interfaces:**
- Produces: `vgar.graph.indexing.index_repo(repo: Path, db: Path) -> int` — giữ nguyên thân hàm ở `src/vgar/agents/runtime.py:18-26` (`repo_key=repo.name`, `repository_revision="cli"`, tạo thư mục cha của `db`, trả số node).

- [ ] **Step 1: Viết test lỗi**

```python
def test_index_repo_lives_in_graph_package(tmp_path):
    from vgar.graph.indexing import index_repo
    count = index_repo(FIXTURE_REPO, tmp_path / "x" / "g.db")
    assert count > 0 and (tmp_path / "x" / "g.db").exists()

def test_cli_index_builds_a_database(tmp_path):
    result = subprocess.run([sys.executable, "-m", "vgar.cli", "index", str(FIXTURE_REPO), "--db", str(tmp_path / "g.db")],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0 and "nodes ->" in result.stdout
```
(`FIXTURE_REPO` từ `tests/graph_fixture.py`.)

- [ ] **Step 2:** `.venv/Scripts/python.exe -m pytest -q tests/test_graph_indexing.py` → FAIL `ModuleNotFoundError: vgar.graph.indexing`.
- [ ] **Step 3:** Tạo `indexing.py` (logger module, docstring `Args:`), `cli.py` import từ đó. `agents/runtime.py` tạm import lại từ `vgar.graph.indexing` để không gãy trước Task 2.
- [ ] **Step 4:** Chạy lại → PASS; thêm `tests/test_cli*.py` hiện có → không lỗi mới.

### Task 2: Xóa agent LangChain, client adapter và model bọc LangChain

**Files:**
- Delete: `src/vgar/agents/` (toàn bộ), `src/vgar/mcp/client.py`, `src/vgar/models/factory.py`, `src/vgar/models/huggingface/hf_model.py`, `src/vgar/models/huggingface/local_hf_chat_model.py`
- Modify: `src/vgar/mcp/__init__.py` (bỏ `create_mcp_client`, `__getattr__`), `src/vgar/models/huggingface/__init__.py` (bỏ `create_local_chat_model`), `src/vgar/cli.py` (bỏ import `langchain_core` dòng 31–32, handler callback, các lệnh `tools`, `solve`, `run`, `chat` và hàm riêng của chúng; docstring đầu file chỉ còn `doctor`, `index`, `repair`)
- Delete script: `scripts/smoke_hf_agent.py`, `scripts/smoke_mcp.py`, `scripts/smoke_model.py`, `scripts/smoke_workflow.py`, `scripts/smoke_w3_w4_agent.py`, `scripts/check_agent_impact_real.py`; `scripts/smoke_w3_w4.py`, `scripts/smoke_w5_w6_retrieval.py`, `scripts/smoke_w7_w8_m1.py`: xóa nếu chỉ chạy qua agent/client, ngược lại cắt phần đó
- Delete test: `tests/unit/test_agent_*.py`, `tests/unit/{test_workflow,test_state,test_tool_budget,test_trace_console,test_trace_report,test_trace_x2b_fixes,test_x2b_diagnosis_fixes}.py`, `tests/m3/test_agent_admitted.py`, `tests/test_cli_run_chat.py`
- Trim test (chỉ xóa hàm test dùng phần bị xóa): `tests/test_settings.py`, `tests/test_w10_impact_mcp.py`, `tests/test_mcp_security.py`, `tests/test_redaction.py`, `tests/test_mcp_result_parser.py`, `tests/test_mcp_legacy_servers.py`, `tests/mcp_server/test_legacy_compatibility.py`, `tests/mcp_server/test_runtime_cli.py`, `tests/mcp_server/test_sdk_runtime.py`, `tests/test_mcp_day5.py` (xóa cả file nếu mọi test đi qua client adapter)
- Create test: `tests/test_tv2_removed_stack.py`

**Interfaces:**
- Consumes: `vgar.graph.indexing.index_repo` (Task 1).
- Produces: hằng `REMOVED` trong `tests/test_tv2_removed_stack.py` — Task 3, 4 thêm phần tử vào đó.

- [ ] **Step 1: Viết test lỗi** `tests/test_tv2_removed_stack.py`

```python
BLOCKED = ("langchain", "langchain_core", "langgraph", "langchain_mcp_adapters", "langchain_huggingface")
REMOVED = ("vgar.agents", "vgar.mcp.client", "vgar.models.factory", "hf_model", "local_hf_chat_model",
           "langchain", "langgraph", "create_mcp_client")

def test_no_reference_to_removed_modules():
    hits = [f"{p}:{n}" for p in [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/**/*.py")]
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if any(name in line for name in REMOVED) and not _allowed(p, line)]
    assert hits == []

def test_every_vgar_module_imports_without_blocked_packages():
    # chạy trong subprocess: sys.modules[name] = None cho mọi BLOCKED, rồi pkgutil.walk_packages(vgar) import từng module
    assert result.returncode == 0, result.stderr
```
`_allowed`: chỉ cho phép `scripts/mcp_server/check_runtime.py` và `_runtime_probe.py` nhắc `langchain` (cờ `--require-no-langchain`).

- [ ] **Step 2:** Chạy → FAIL (liệt kê tham chiếu; import `vgar.cli` lỗi vì `langchain_core` bị chặn).
- [ ] **Step 3:** Xóa và sửa theo danh sách Files. Mỗi file test bị xóa/cắt: một dòng ledger `Task 2: test <file>::<hàm> — <lý do>`.
- [ ] **Step 4:** Chạy test mới → PASS. Chạy suite đầy đủ (redirect vào workspace, so với baseline): chỉ được mất các test đã ghi ledger; không lỗi mới.

### Task 3: Xóa generator Qwen thật

**Files:**
- Delete: `src/vgar/models/huggingface/{generator_hf,hf_backend,hf_worker,model_worker,hf_diagnostics}.py`
- Modify: `src/vgar/repair/pipeline.py:144-170` (`build_tokenizer`, `build_generation`: bỏ nhánh `real`), `src/vgar/cli.py` (`--mode` của `repair` chỉ còn `choices=("fake",)`, bỏ `profile if args.mode == "real"`)
- Delete/trim test: `tests/m2/w78/{test_w78_generator,test_w78_hf_adapter,test_w78_generation_diagnostics,test_w78_diagnostic_logging,test_w78_tokenizer_flags,test_w78_review_guards}.py` — xóa test dùng module bị xóa, giữ test chỉ dùng `local_chat`/pipeline fake; `tests/m2/w78/test_w78_local_chat.py` chỉ cắt phần `HFChatTokenizer`
- Test: `tests/test_tv2_removed_stack.py`

**Interfaces:**
- Produces: `build_tokenizer(mode="real", ...)` và `build_generation(mode="real", ...)` raise `ValueError("Real generation was removed; only mode 'fake' is supported")`.

- [ ] **Step 1: Thêm test lỗi**

```python
REMOVED += ("generator_hf", "hf_backend", "hf_worker", "model_worker", "hf_diagnostics", "HFGenerator", "HFChatTokenizer")
BLOCKED += ("torch", "transformers", "accelerate", "peft", "trl", "datasets")

def test_real_generation_is_rejected():
    from vgar.repair.pipeline import build_tokenizer
    with pytest.raises(ValueError, match="Real generation was removed"):
        build_tokenizer("real", policy=None, profile=SimpleNamespace(tokenizer_manifest=MANIFEST), output_root=tmp_path)
```
(`MANIFEST`: manifest tokenizer mà test fake hiện có dùng; lấy từ `configs/m2`.)

- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Xóa và sửa theo Files; `observability/machine.py`, `quiet.py` giữ (đã import lười có `except Exception`).
- [ ] **Step 4:** Test mới PASS; `pytest -q tests/m2/w78` không lỗi mới ngoài test đã ghi ledger.

### Task 4: Xóa `repair_server`

**Files:**
- Delete: `src/vgar/mcp/servers/repair_server.py`, `tests/m2/w78/test_w78_repair_server.py`
- Modify: `configs/mcp_server/{claude-code,inspector-legacy,inspector-modern}.template.json` (bỏ `vgar-repair`), `configs/mcp_server/runtime.json` (bỏ `entrypoints.repair`, `operator_bindings.repair`), `scripts/mcp_server/check_runtime.py:67` (bỏ `"repair"` khỏi tuple), `scripts/mcp_server/_runtime_worker.py:120-135` (bỏ nhánh `repair`), `scripts/mcp_server/smoke_mcp.py`/`_preflight_worker.py` nếu liệt kê repair, `src/vgar/mcp/servers/repository_server.py:4` (docstring)
- Trim test: `tests/m2/w78/test_w1112_evidence_integration.py`, `tests/m2/w910/test_runner_contract.py`, `tests/mcp_server/test_concurrency.py`, `tests/test_mcp_legacy_servers.py`, `tests/test_mcp_security.py` (chỉ phần gọi repair server)
- Test: `tests/test_tv2_removed_stack.py`

- [ ] **Step 1: Thêm test lỗi**

```python
REMOVED += ("repair_server", "vgar-repair")

def test_templates_list_exactly_three_servers():
    for name in ("claude-code", "inspector-legacy", "inspector-modern"):
        servers = json.loads((ROOT / f"configs/mcp_server/{name}.template.json").read_text())["mcpServers"]
        assert set(servers) == {"vgar-graph", "vgar-repository", "vgar-execution"}
    assert set(json.loads((ROOT / "configs/mcp_server/runtime.json").read_text())["entrypoints"]) == {"graph", "repository", "execution"}
```
(Nếu template inspector có khóa khác `mcpServers`, đọc đúng khóa của file; ghi ruling.)

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Sửa theo Files. **Step 4:** Test PASS; `pytest -q tests/mcp_server tests/m2` không lỗi mới ngoài ledger.

### Task 5: `pyproject.toml` theo spec

**Files:** Modify `pyproject.toml`; Test `tests/test_tv2_removed_stack.py`

- [ ] **Step 1: Thêm test lỗi**

```python
def test_pyproject_dependencies_match_the_spec():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {re.split(r"[<>=\[ ]", d, 1)[0].lower() for d in project["dependencies"]}
    assert names == {"mcp", "pydantic", "packaging", "filelock", "python-dotenv", "tree-sitter",
                     "tree-sitter-python", "pyyaml", "tokenizers", "jinja2"}
    assert "mcp==2.2.0" in project["dependencies"]
    assert set(project["optional-dependencies"]) == {"dev", "history", "plot", "code-graph"}
```
- [ ] **Step 2:** FAIL. **Step 3:** Sửa `dependencies` đúng Global Constraints; giữ `[project.scripts]`, `package-data`, pytest config. **Step 4:** PASS.

### Task 6: Logging và debug theo hướng dẫn build-server

Căn cứ (hướng dẫn `2026-07-28`, trang build-server và tools/debugging): STDIO server không bao giờ ghi stdout; dùng `logging` của thư viện chuẩn (ghi stderr); một logger mỗi module `logging.getLogger(__name__)`, gọi từ tool; host tự thu stderr của server stdio; logging qua giao thức (`notifications/message`, `ctx.log`) **đã deprecated** ở `2026-07-28` nên không dùng. Hướng dẫn không quy định biến môi trường cho mức log — `VGAR_MCP_LOG_LEVEL` là quyết định của plan này.

**Files:**
- Modify: `src/vgar/mcp/tooling.py` (logger module; log trong `run_tool` và `run_tool_async`), `src/vgar/mcp/servers/{graph_server,execution_server,repository_server}.py` (logger module; cấu hình mức log và log khởi động trong `main()`), `src/vgar/mcp/server_factory.py` (logger module; truyền mức log)
- Create: `src/vgar/mcp/logging_setup.py`, `docs/mcp_server/debugging.md`
- Modify test: `tests/mcp_server/test_tv2_no_stdout.py`; Create test: `tests/mcp_server/test_tv2_server_logging.py`

**Interfaces:**
- Produces: `vgar.mcp.logging_setup.configure_server_logging() -> str` — đọc `VGAR_MCP_LOG_LEVEL` (mặc định `"WARNING"`, giữ trace spec P8 của TV1 "không có dòng INFO theo từng request"; giá trị lạ → `WARNING` kèm một dòng cảnh báo), gắn đúng một `StreamHandler(sys.stderr)` vào logger `vgar` với định dạng `%(asctime)s %(levelname)s %(name)s: %(message)s`, trả về tên mức; gọi lại nhiều lần không thêm handler trùng.
- Produces: mỗi lời gọi tool ghi qua `vgar.mcp.tooling`: `INFO` khi xong `tool=<tên> server=<server> status=<PASS|FAIL|ERROR> duration_ms=<n> request_id=<id>`; `DEBUG` khi bắt đầu `tool=<tên> args=<chỉ tên tham số và kích thước/hash, không ghi nội dung diff hay giá trị bí mật>`; lỗi ngoài dự kiến `logger.exception`.
- Produces: `main()` của mỗi server: gọi `configure_server_logging()` trước `mcp.run(transport="stdio")`; `INFO` khởi động gồm tên server, phiên bản `mcp`, backend, đường dẫn DB, `graph_version`, repo root (không ghi biến môi trường khác); lỗi khởi động (ví dụ "Graph database not found") ghi `logger.error` rồi mới raise.

- [ ] **Step 1: Viết test lỗi** `tests/mcp_server/test_tv2_server_logging.py`

```python
def test_info_level_logs_each_tool_call_on_stderr_only(tmp_path):
    # bật graph_server qua stdio (subprocess, env real_graph_env + VGAR_MCP_LOG_LEVEL=INFO), gọi search_symbols
    assert response["status"] == "PASS"                       # stdout vẫn là JSON-RPC hợp lệ
    assert "tool=search_symbols" in stderr and "status=PASS" in stderr
    assert "vgar-graph" in stderr and "backend=sqlite" in stderr   # dòng khởi động

def test_default_level_has_no_per_call_info_lines(tmp_path):
    # như trên nhưng không đặt VGAR_MCP_LOG_LEVEL
    assert "tool=search_symbols" not in stderr

def test_debug_level_never_logs_diff_content(tmp_path):
    # VGAR_MCP_LOG_LEVEL=DEBUG, gọi verify_patch_graph_constraints với diff chứa chuỗi "SECRET_MARKER"
    assert "SECRET_MARKER" not in stderr and "diff_sha256" in stderr

def test_missing_database_is_logged_before_exit(tmp_path):
    # VGAR_GRAPH_DATABASE trỏ file không có
    assert process.returncode != 0 and "Graph database not found" in stderr

def test_configure_server_logging_is_idempotent(monkeypatch):
    monkeypatch.setenv("VGAR_MCP_LOG_LEVEL", "debug")
    assert configure_server_logging() == "DEBUG" == configure_server_logging()
    assert len([h for h in logging.getLogger("vgar").handlers if getattr(h, "_vgar", False)]) == 1
```
Mở rộng `test_new_modules_never_print` trong `test_tv2_no_stdout.py`: thêm `src/vgar/mcp/servers/*.py`, `src/vgar/mcp/tooling.py`, `src/vgar/mcp/logging_setup.py`, `src/vgar/mcp/server_factory.py`.

- [ ] **Step 2:** `pytest -q tests/mcp_server/test_tv2_server_logging.py tests/mcp_server/test_tv2_no_stdout.py` → FAIL (`ModuleNotFoundError: vgar.mcp.logging_setup`; không có dòng `tool=`).
- [ ] **Step 3:** Cài đặt theo Interfaces. Mức log `create_server(log_level=...)` lấy từ `configure_server_logging()` thay cho chuỗi cứng `"WARNING"`.
- [ ] **Step 4:** Chạy lại → PASS; `pytest -q tests/mcp_server tests/test_mcp_tool_contract.py` không lỗi mới.
- [ ] **Step 5:** `docs/mcp_server/debugging.md`: bật log (`VGAR_MCP_LOG_LEVEL=DEBUG|INFO|WARNING` trong `env` của cấu hình host); nơi xem log — Claude Code: `%LOCALAPPDATA%\claude-cli-nodejs\Cache\<project>\mcp-logs-<server>\*.jsonl`, Claude Desktop: `%APPDATA%\Claude\logs\mcp*.log` (theo hướng dẫn), OpenCode: `opencode mcp list`; audit log `VGAR_MCP_AUDIT_LOG` (mọi lời gọi tool, dùng cho chỉ số MCP usability); MCP Inspector với Python (`npx @modelcontextprotocol/inspector --cli <python> -m vgar.mcp.servers.graph_server --protocol-era modern --method tools/list` — kiểm lệnh thật ở Task 7 trước khi ghi); lỗi thường gặp theo hướng dẫn: đường dẫn tuyệt đối, server stdio chỉ nhận một phần biến môi trường nên phải khai trong `env`, sai bản giao thức (`-32022`), và lỗi "Connection closed" khi hủy lời gọi (kết quả Task 8).

### Task 7: Bỏ engine sinh patch M2 (spec §4.1b)

**Files:** Create `src/vgar/repair/deadline.py`, `src/vgar/evaluation/repair/prompt_fingerprint.py`, `src/vgar/evaluation/repair/prompts/repair_v11.txt` (git mv); Modify `src/vgar/mcp/proposal/diff_tests_provider.py`, `src/vgar/repair/docker_executor.py`, `src/vgar/evaluation/repair/{verifier_eval,fairness,manifest}.py`, `src/vgar/cli.py`; Delete theo spec §4.1b; Test `tests/test_tv2_removed_stack.py`.

**Interfaces:** Produces `vgar.repair.deadline.{StopRun, require_trusted_fixture, DeadlineExecutor}` (thân giữ nguyên từ `pipeline.py`); `vgar.evaluation.repair.prompt_fingerprint.template_path(version: str) -> Path` (giữ nguyên hành vi `repair.prompt.template_path`).

- [ ] **Step 1: Test lỗi** — thêm vào `REMOVED`: `"vgar.repair.pipeline"`, `"vgar.repair.session"`, `"vgar.repair.prompt"`, `"vgar.repair.failure"`, `"vgar.models"`, `"evaluation.repair.launch"`, `"evaluation.repair.runner"`, `"evaluation.repair.gpu"`, `"evaluation.repair.preflight"`, `"evaluation.repair.aggregate"`, `"evaluation.repair.derive_config"`, `"evaluation.dry_run"`, `"evaluation.agent_metrics"`, `"harness.candidates"`; thêm `test_verification_tools_survive`: import `vgar.evaluation.repair.{mutant_pool,verifier_eval,fairness,manifest}` và `vgar.repair.deadline` được; `template_path("m2-w78-v11")` trỏ tới `src/vgar/evaluation/repair/prompts/repair_v11.txt` có cùng SHA-256 với bản ở HEAD.
- [ ] **Step 2:** chạy → FAIL. **Step 3:** chuyển/xóa theo spec; mỗi test xóa/cắt ghi ledger. **Step 4:** test mới PASS; `pytest -q tests/m2 tests/m3 tests/mcp_server` không lỗi mới ngoài test đã ghi ledger.

### Task 8: Thử SDK2 trên venv tạm (ngoài repo)

**Files:** không sửa ngoài code cần cho SDK2 (mỗi chỗ sửa là một ruling + test).

- [ ] **Step 1:** `.venv/Scripts/python.exe -m venv <scratchpad>/venv-sdk2`; `<venv>/Scripts/python.exe -m pip install -e ".[dev,history]"` → Expected: cài `mcp 2.2.0`, `mcp-types 2.2.0`; `pip check` sạch; `pip list` không có `langchain*`, `torch`.
- [ ] **Step 2:** Suite đầy đủ bằng venv tạm, redirect vào workspace; so danh sách lỗi với baseline. Expected: 29 lỗi SDK2 chuyển PASS; 3 lỗi HEAD còn; không lỗi mới ngoài test đã xóa ở Task 2–4.
- [ ] **Step 3:** Mỗi lỗi mới: `superpowers:systematic-debugging`; sửa code dùng API chỉ có ở SDK1 bằng nhánh SDK2 theo mẫu `server_factory.py`; test SDK1-only (ví dụ dùng `mcp.client.stdio`/`ClientSession` khi SDK2 đổi API) sửa sang `from mcp import Client`. Ghi ruling.
- [ ] **Step 4:** Stdio thật bằng venv tạm (đặt `VGAR_MCP_LOG_LEVEL=INFO`, kiểm stderr có dòng khởi động và dòng `tool=` cho từng lời gọi, stdout chỉ JSON-RPC; chạy thử lệnh Inspector của `debugging.md` nếu có `npx`): `vgar index` repo demo vào DB tạm; client SDK2 nối `graph_server` ở `2026-07-28` và `legacy`: liệt kê 11 tool, `search_symbols`, `get_callers(depth=2)`, `verify_patch_graph_constraints`, `rank_patch_candidates` (có `diff_hash`) → `PASS`, `backend = "sqlite"`; `execution_server.run_relevant_tests` → kết quả có `selectors`. `scripts/mcp_server/check_runtime.py --require-no-langchain` với venv tạm → PASS cho 3 server.

### Task 9: Nâng `.venv` thật

- [ ] **Step 1:** Chỉ khi Task 8 đạt. `.venv/Scripts/python.exe -m pip uninstall -y langchain langchain-core langgraph langchain-huggingface langchain-mcp-adapters`; `pip install -e ".[dev,history]"` → `mcp 2.2.0`. Gói ML để nguyên (spec §5.2).
- [ ] **Step 2:** Suite đầy đủ bằng `.venv` → cùng kết quả Task 8 Step 2.
- [ ] **Step 3:** Hủy lời gọi: client SDK2 gửi `notifications/cancelled` giữa `rank_patch_candidates`; ghi server có còn gửi phản hồi cho request đã hủy không (nguyên nhân "Connection closed" ở Claude Code) và server còn sống không. Chỉ ghi kết quả.
- [ ] **Step 4:** Lệnh cho người dùng (không tự chạy): đổi `protocol` sang `"2026-07-28"` trong cấu hình OpenCode; `/mcp` kết nối lại trong Claude Code.

### Task 10: Tài liệu và báo cáo

**Files:** `README.md`, `.env.example` (bỏ phần agent/model LangChain nếu có), `docs/mcp_server/runtime.md` (bỏ đoạn "root metadata giữ MCP<2 và LangChain", chỉ còn 3 server), `docs/mcp_server/runbook.md` (bỏ repair server); Create `docs/status/tv2_remove_langchain_sdk2_run_2026-11-12.md`

- [ ] **Step 1:** Báo cáo gồm: file xóa, file sửa, mọi test xóa/cắt kèm lý do (từ ledger), suite trước/sau, kết quả stdio 2 chế độ, kết quả hủy lời gọi, lệnh cài lại cho thành viên khác (`pip install -e .[dev]`), ghi chú cho TV1 (L6-1 còn 3 server; template đã đổi; ablation Repair không còn đi qua repair server).
- [ ] **Step 2:** `pytest -q tests/test_tv2_removed_stack.py tests/test_graph_indexing.py tests/mcp_server/test_tv2_server_logging.py tests/mcp_server/test_tv2_no_stdout.py` → PASS.
