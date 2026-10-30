# M3-W10-3: Qwen tự gọi `analyze_patch_impact` trong vòng retry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent của `vgar solve --agent` có tool thứ 6 không tham số `analyze_patch_impact`. Khi được gọi, host gửi diff đã apply của lần thử thất bại qua MCP stdio tới server `graph`, rồi đưa `ImpactReport` vào câu trả lời của tool và vào feedback của lần retry.

**Architecture:** `AgentRepairHost` (`src/vgar/agents/tool_agent.py`) lưu diff đã apply và impact của từng run. Lần gọi đầu tiên, host index `task.source_repo` vào `work_dir/impact-graph.db` và mở client MCP stdio chỉ nối server `graph` (sqlite + `VGAR_REPOSITORY_ROOT`). Retry truyền `impact=` vào `build_feedback`. Agent giả gọi tool sau khi test FAIL. Một script riêng chạy Qwen thật với generator theo kịch bản (patch sai hợp lệ, sau đó reference).

**Tech Stack:** Python 3.11, LangChain `create_agent`, `langchain_mcp_adapters` (stdio), FastMCP, pytest.

**Spec:** `docs/superpowers/specs/2026-10-30-m3-w10-3-impact-tool-agent-design.md`

## Global Constraints

- Chỉ sửa file M3: `src/vgar/agents/`, `src/vgar/mcp/client.py`, `scripts/`, `tests/`, `docs/status/m3.md`. Không sửa `graph/impact.py`, `mcp/servers/graph_server.py`, engine repair M2, workflow cố định hay runner ablation.
- Tool không tham số (`NoArgs`). Qwen không bao giờ truyền diff, đường dẫn hay `graph_version`.
- Host không bao giờ tự gọi impact thay Qwen. Trace chỉ ghi `by == "agent"` cho tool này.
- Không ghi nội dung diff vào trace. Audit của graph server đã chỉ ghi hash.
- Không sửa `os.environ` của tiến trình cha.
- `MAX_TOOL_CALLS = 15` giữ nguyên.
- Lệnh test: `python -m pytest ...` từ thư mục gốc repo (Windows, venv đang kích hoạt).
- **Người dùng tự commit.** Không chạy `git commit`/`git push`. Bước cuối mỗi task là liệt kê file đã đổi.
- Phong cách: như `tool_agent.py` (dòng ngắn, ít comment, trả lời plain text qua `_reply`).

## Review Focus

1. Run thất bại do `PATCH_PARSE_ERROR` (apply chưa PASS) → gọi impact phải bị `HOST_REFUSED`, không index graph. *(test ở Task 3: `test_impact_refused_after_parse_error`)*
2. Qwen gọi impact rồi lại gọi lần nữa trong cùng run → lần 2 bị từ chối, server graph không được gọi lại. *(Task 3: `test_impact_refused_twice_in_one_run`)*
3. Impact của run 1 không được rò sang feedback của run 3 khi run 2 không gọi impact. *(Task 3: `test_impact_is_not_carried_to_a_later_retry`)*
4. Server graph lỗi hoặc spawn thất bại → `STATUS: ERROR`, retry vẫn sinh patch, feedback không có dòng impact. *(Task 3: `test_impact_error_keeps_retry_going`)*
5. Repo nguồn không đổi sau khi index graph (db nằm trong `work_dir`, không trong `source_repo`). *(Task 4: assert `result["status"] == "COMPLETED"`, `_result` đã kiểm fingerprint)*

---

### Task 1: Patch sai hợp lệ cho 3 task fixture

**Files:**
- Create: `tests/fixtures/m2/wrong_patches/single_file_login.diff`, `multi_file_invoice.diff`, `missing_links.diff`
- Modify: `tests/unit/test_agent_solve.py` (thêm test và hằng `WRONG`)

**Interfaces:**
- Produces: `tests/fixtures/m2/wrong_patches/<task>.diff`. Mỗi file là unified diff sửa đúng file mà reference patch sửa, `git apply` được trên `examples/m2/snapshots/<task>`, và failing selector của task vẫn FAIL. Gợi ý: `single_file_login` `return bool(value)` → `return bool(value) and True`; `multi_file_invoice` sửa `pricing.py` thành `return price - discount_percent * 1`; `missing_links` `return name` → `return name or ""`. Chỉ dùng nếu kiểm chứng ở Step 2 cho ra đúng apply PASS + test FAIL.
- Produces trong test module: `WRONG = REPO / "tests/fixtures/m2/wrong_patches"`.

- [ ] **Step 1: Viết test**

```python
@pytest.mark.parametrize("letter,case", CASES)
def test_wrong_patch_applies_and_still_fails(letter, case, tmp_path):
    raw = (WRONG / f"{case}.diff").read_text(encoding="utf-8")
    steps = ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]
    result = solve(tmp_path, task=REPO / f"examples/m2/tasks/{case}.json",
                   model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([raw]))
    trace = trace_of(result)
    assert replies(trace, "apply_patch")[0].startswith("STATUS: PASS")
    assert replies(trace, "run_relevant_tests")[0].startswith("STATUS: FAIL")
    assert result["status"] == "FAILED"
```

(`replies` là helper hiện có, trả nội dung các tool message theo tên. Dùng đúng tên helper trong file.)

- [ ] **Step 2: Chạy test, viết 3 patch, chạy lại tới khi PASS**

Run: `python -m pytest tests/unit/test_agent_solve.py -k wrong_patch -v`
Expected: lần đầu FAIL (thiếu file), sau khi thêm patch thì 3 PASS.

- [ ] **Step 3: Liệt kê file đã đổi cho người dùng**

---

### Task 2: Client MCP graph cho một repo, kèm test gọi thật qua stdio

**Files:**
- Modify: `src/vgar/mcp/client.py` (`create_mcp_client`)
- Modify: `src/vgar/agents/runtime.py` (thêm hàm `impact_graph_tool`)
- Test: `tests/unit/test_agent_impact_tool.py` (mới)

**Interfaces:**
- Produces: `create_mcp_client(settings=None, servers=SERVER_NAMES, extra_env: dict[str, str] | None = None)`. `extra_env` được merge vào env của tiến trình con, sau `settings.to_env()`.
- Produces: `async def impact_graph_tool(settings: Settings, source_repo: Path, database: Path) -> tuple[Any, str]` trong `runtime.py`. Hàm này gọi `index_repo(source_repo, database)` và đọc `graph_version` bằng `SQLiteGraphStore(database).resolve_graph_version()`. Sau đó tạo client với `replace(settings, graph=replace(settings.graph, backend="sqlite", database=database, version=version))`, `servers=("graph",)`, `extra_env={"VGAR_REPOSITORY_ROOT": str(source_repo)}`, và trả `(tool "graph_analyze_patch_impact", version)`.

- [ ] **Step 1: Viết test gọi tool qua stdio thật**

```python
def test_impact_graph_tool_answers_over_stdio(tmp_path):
    repo = REPO / "examples/m2/snapshots/single_file_login"
    tool, version = asyncio.run(impact_graph_tool(get_settings(), repo, tmp_path / "g.db"))
    wrong = (REPO / "tests/fixtures/m2/wrong_patches/single_file_login.diff").read_text(encoding="utf-8")
    result = parse_mcp_json_result(asyncio.run(tool.ainvoke({"diff": wrong, "graph_version": version})))
    assert result["status"] == "PASS" and version.startswith("sha256:")
    assert [n["path"] for n in result["data"]["changed"]] == ["auth.py"]
    assert result["data"]["impacted"]["status"] in ("COMPLETE", "PARTIAL")
```

- [ ] **Step 2: Chạy, thấy FAIL (ImportError)**

Run: `python -m pytest tests/unit/test_agent_impact_tool.py -v`

- [ ] **Step 3: Cài `extra_env` và `impact_graph_tool`**

- [ ] **Step 4: Chạy lại test này cùng test MCP hiện có**

Run: `python -m pytest tests/unit/test_agent_impact_tool.py tests/test_w10_impact_mcp.py -v`
Expected: tất cả PASS. Nếu impact báo `Source inventory differs from graph snapshot`, đó là do cách index, không phải do patch. Sửa trong `impact_graph_tool`, không sửa `impact.py`.

- [ ] **Step 5: Liệt kê file đã đổi**

---

### Task 3: Tool `analyze_patch_impact` của host, feedback và prompt

**Files:**
- Modify: `src/vgar/agents/tool_agent.py`
- Modify: `src/vgar/agents/prompts/repair_agent.md`
- Test: `tests/unit/test_agent_impact_tool.py`

**Interfaces:**
- Consumes: `impact_graph_tool` (Task 2), `_impact_message` và `build_feedback(record, impact=)` (`feedback.py`), `WRONG` (Task 1).
- Produces trên `AgentRepairHost`:
  - mỗi dict run có thêm `"impact_called": False` và `"impact": None`;
  - `self.applied_diff: str | None`, được gán diff vừa apply khi `apply_patch` PASS (đặt về `None` khi mở run mới);
  - `self.graph: tuple[Any, str] | None`, tạo lười bằng `impact_graph_tool(self.runtime.base_settings(), Path(self.task.source_repo), self.work_dir / "impact-graph.db")`;
  - `async def analyze_patch_impact(self) -> str`;
  - `langchain_tools()` trả 6 tool. Tool mới tên `"analyze_patch_impact"`, mô tả: `"After an applied patch failed its tests, show which callers, importers and tests depend on the code it changed. Optional; call before generate_patch."`
- Hành vi của `analyze_patch_impact`, theo thứ tự:
  1. `run is None` → `_refuse(..., "No task yet; call get_task_context first.")`
  2. `not (run["applied"] and run["failed"])` → `_refuse(..., "Impact needs an applied patch that failed its tests.")`
  3. `run["impact_called"]` → `_refuse(..., "Impact was already analyzed for this attempt.")`
  4. Đặt `impact_called = True`. Lấy graph, gọi tool với `{"diff": self.applied_diff, "graph_version": version}`, parse bằng `parse_mcp_json_result`. Mọi exception (index lỗi, transport lỗi) thành `{"status": "ERROR", "reason": "TOOL_ERROR", "detail": ...}`, giống `_call`.
  5. PASS → `run["impact"] = result["data"]`, `_log(..., "PASS", None, start)`, trả `_reply("PASS", [("IMPACT", _impact_message(data))], self._next())`.
  6. Ngược lại → `_log(..., "ERROR", code, start)`, trả `_reply("ERROR", [("REASON", code), ("DETAIL", message)], self._next())`, với `code`/`message` lấy từ `result["error"]` hoặc `reason`/`detail`.
- Trong nhánh retry của `generate_patch`: `feedback = build_feedback(self._record(), impact=run["impact"])`, trong đó `run` là run vừa thất bại.
- Prompt: thêm một gạch đầu dòng tool vào danh sách, và một câu sau đoạn retry: `"After run_relevant_tests reports FAIL and attempts are left, you may call analyze_patch_impact once before generate_patch; it shows what depends on the code the patch changed and adds it to the feedback."` Đổi `"Tools (none of them take arguments)"` cho phù hợp với 6 tool nếu câu đó có đếm số tool. "Usual order" giữ nguyên.

- [ ] **Step 1: Viết test (dùng `SequenceAgent` và `solve` import từ `tests/unit/test_agent_solve.py`, hoặc chuyển chúng sang `tests/unit/conftest.py` nếu import chéo bất tiện)**

```python
FAIL_THEN_IMPACT = ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests",
                    "analyze_patch_impact", "generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]

def test_impact_reply_and_feedback(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                   generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    trace = trace_of(result)
    impact = [c for c in trace["calls"] if c["tool"] == "analyze_patch_impact"]
    assert [(c["by"], c["status"]) for c in impact] == [("agent", "PASS")]
    assert replies(trace, "analyze_patch_impact")[0].startswith("STATUS: PASS\nIMPACT: Static graph impact")
    second = records(trace)[1]
    assert "Static graph impact of the previous patch" in second["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED"

def test_impact_refused_before_task(tmp_path): ...       # steps ["analyze_patch_impact", ...] → "HOST_REFUSED" trong trace, reply có "No task yet"
def test_impact_refused_before_failure(tmp_path): ...    # sau apply PASS, trước test → "Impact needs an applied patch"
def test_impact_refused_after_parse_error(tmp_path): ... # generator [break_diff(REF)], apply FAIL → refused; assert not (tmp_path / ...).exists() không cần: assert host không index bằng cách monkeypatch impact_graph_tool đếm số lần gọi == 0
def test_impact_refused_twice_in_one_run(tmp_path): ...  # gọi impact 2 lần liên tiếp → lần 2 "already analyzed"; đếm impact_graph_tool == 1
def test_impact_is_not_carried_to_a_later_retry(tmp_path): ...  # [WRONG, WRONG, REF]; impact chỉ ở run 1 → run 3 feedback không có "Static graph impact"
def test_impact_error_keeps_retry_going(tmp_path, monkeypatch): ...  # monkeypatch impact_graph_tool raise RuntimeError → reply "STATUS: ERROR", run 2 vẫn được tạo, feedback không có dòng impact
def test_agent_has_six_tools(): ...  # tên tool theo thứ tự, tool cuối là analyze_patch_impact, args_schema NoArgs
```

`WRONG_LOGIN = (WRONG / "single_file_login.diff").read_text(...)`. `records(trace)` là helper hiện có, đọc run record từ trace (dòng 3 trong phần test của file solve). Dùng đúng tên trong file. Khi monkeypatch, patch `vgar.agents.tool_agent.impact_graph_tool` (tên được import vào module).

- [ ] **Step 2: Chạy, thấy FAIL**

Run: `python -m pytest tests/unit/test_agent_impact_tool.py -v`

- [ ] **Step 3: Cài host tool, wiring feedback và prompt**

- [ ] **Step 4: Chạy test mới cùng toàn bộ test agent**

Run: `python -m pytest tests/unit/test_agent_impact_tool.py tests/unit/test_agent_solve.py tests/unit/test_agent_feedback.py tests/unit/test_agent_fakes.py -v`
Expected: tất cả PASS. Test cũ không gọi impact nên feedback của chúng không đổi (spec §4.1 mục 4).

- [ ] **Step 5: Liệt kê file đã đổi**

---

### Task 4: Agent giả gọi impact, test end-to-end fake

**Files:**
- Modify: `src/vgar/agents/fakes.py` (`ScriptedRepairAgent.next_tool`)
- Test: `tests/unit/test_agent_impact_tool.py`, `tests/unit/test_agent_fakes.py` nếu có test về `next_tool`

**Interfaces:**
- `ScriptedRepairAgent.next_tool`: sau `run_relevant_tests` không PASS và `ATTEMPTS LEFT > 0` → `"analyze_patch_impact"`. Sau `analyze_patch_impact` (bất kỳ STATUS nào) → `"generate_patch"`. `apply_patch` FAIL vẫn đi thẳng tới `generate_patch` như cũ.
- **Quyết định của mình (spec §3.5):** fake mode mặc định của `select_generator` vẫn là `[break_diff(ref), ref]`. Lần đầu fail ở apply nên fake mặc định không gọi impact, và test cũ giữ nguyên. Test mới tự truyền generator `[WRONG, REF]`.

- [ ] **Step 1: Viết test**

```python
@pytest.mark.parametrize("letter,case", CASES)
def test_scripted_agent_calls_impact_after_test_failure(letter, case, tmp_path):
    wrong = (WRONG / f"{case}.diff").read_text(encoding="utf-8")
    ref = (REPO / f"tests/fixtures/m2/reference_patches/{case}.diff").read_text(encoding="utf-8")
    result = solve(tmp_path, task=REPO / f"examples/m2/tasks/{case}.json",
                   generator=ScriptedPatchGenerator([wrong, ref]))
    trace = trace_of(result)
    assert calls(trace, "agent") == ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests",
                                     "analyze_patch_impact", "generate_patch", "apply_patch",
                                     "run_relevant_tests", "verify_patch"]
    assert "Static graph impact of the previous patch" in records(trace)[1]["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED" and result["recommendation"] == "ACCEPT"
```

- [ ] **Step 2: Chạy, thấy FAIL** (agent giả chưa gọi impact)

Run: `python -m pytest tests/unit/test_agent_impact_tool.py -k scripted -v`

- [ ] **Step 3: Sửa `next_tool`**

- [ ] **Step 4: Chạy toàn bộ suite**

Run: `python -m pytest -q`
Expected: không có fail mới so với baseline (lần chạy gần nhất: 1389 passed, 16 skipped, 1 xfailed, có 1 test fail từ trước đã deselect). Ghi lại số liệu thật.

- [ ] **Step 5: Liệt kê file đã đổi**

---

### Task 5: Script kiểm tra bằng Qwen thật và cập nhật status

**Files:**
- Create: `scripts/check_agent_impact_real.py`
- Modify: `docs/status/m3.md` (dòng M3-W10-3 và M3-W10-4, mục "chuyển W11" ở dòng ~159)

**Interfaces:**
- Consumes: `run_agent_task`, `Runtime`, `ScriptedPatchGenerator`, `default_agent_model` (tool_agent), `load_config`, fixture `WRONG`/reference.
- CLI: `python scripts/check_agent_impact_real.py [--tasks single_file_login,multi_file_invoice,missing_links] [--out results/agent-impact-real]`.
- Hành vi:
  - Nạp model **một lần**: `default_agent_model(Runtime(mode="real"), profile)`.
  - Với mỗi task chạy tuần tự `run_agent_task(task_path=..., runtime=Runtime(mode="real", output_root=<out>/runs, generator=ScriptedPatchGenerator([wrong, ref])), model=model)`.
  - Đọc trace và ghi `<out>/<UTC stamp>/summary.json`, mỗi task một dòng: `task`, `impact_called` (agent có gọi không), `impact_status`, `feedback_has_impact` (run 2 có dòng impact không), `recommendation`, `tool_calls`, `duration_ms`, `trace_path`.
  - In bảng ra stdout, kèm dòng `GATE: PASS` nếu có ít nhất 1 task với `impact_called and impact_status == "PASS" and feedback_has_impact`, ngược lại `GATE: FAIL`.
  - Hàm `summarize(trace: dict) -> dict` tách riêng để test được không cần GPU.
- Test: `tests/unit/test_agent_impact_tool.py::test_summarize_reads_a_fake_trace`. Chạy fake solve như Task 4, gọi `summarize(trace_of(result))`, assert `impact_called is True`, `impact_status == "PASS"`, `feedback_has_impact is True`.

- [ ] **Step 1: Viết test `summarize`, chạy, thấy FAIL**

Run: `python -m pytest tests/unit/test_agent_impact_tool.py -k summarize -v`

- [ ] **Step 2: Viết script, chạy test, thấy PASS**

- [ ] **Step 3: Kiểm tra script parse được tham số mà không nạp model**

Run: `python scripts/check_agent_impact_real.py --help`
Expected: in usage, exit 0.

- [ ] **Step 4: Giao lệnh chạy thật cho người dùng (không tự chạy GPU)**

Trước đó kiểm không có tiến trình `hf_worker`/model nào đang chạy. Đưa lệnh `.venv\Scripts\python.exe scripts\check_agent_impact_real.py > results\agent-impact-real.log 2>&1` và chờ người dùng dán output.

- [ ] **Step 5: Khi có kết quả, cập nhật `docs/status/m3.md`**

Dòng M3-W10-3: "Xong: Qwen gọi qua stdio trong vòng retry", kèm bảng 3 task đúng như output (kể cả task Qwen bỏ qua tool). Dòng M3-W10-4: bỏ "chuyển W11". Mục danh sách việc W11 (dòng ~159): bỏ mục "Gọi `analyze_patch_impact` trong vòng retry của `tool_agent`".

- [ ] **Step 6: Liệt kê toàn bộ file của plan để người dùng commit**
